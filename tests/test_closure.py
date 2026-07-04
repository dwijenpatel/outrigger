"""Tests for harness.closure (E5) — frozen snapshot, fresh evidence, bounds."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import closure, ledger as ledger_mod
from harness.closure import ClosureError
from harness.ledger import EventLog, Ledger

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tasks_doc():
    return {"tasks": [
        {"id": "t1", "phase": "p1", "profile": "routine", "deps": []},
        {"id": "t2", "phase": "p1", "profile": "routine", "deps": []},
    ]}


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ldg = Ledger(ledger_mod.validate_tasks(tasks_doc()))
        self.log = EventLog(os.path.join(self.dir.name, "events.jsonl"))
        self.snap_path = os.path.join(self.dir.name, "snapshot.json")
        self.snap = closure.freeze_snapshot(self.ldg, self.snap_path)

    def tearDown(self):
        self.dir.cleanup()

    def done(self, *tids):
        for t in tids:
            self.log.record_status(t, "in_progress")
            self.log.record_status(t, "done")

    def test_snapshot_roundtrip_and_tamper_detection(self):
        loaded = closure.load_snapshot(self.snap_path)
        self.assertEqual(loaded["task_ids"], ["t1", "t2"])
        with open(self.snap_path) as fh:
            doc = json.load(fh)
        doc["task_ids"] = ["t1"]  # quietly drop a task
        with open(self.snap_path, "w") as fh:
            json.dump(doc, fh)
        with self.assertRaises(ClosureError):
            closure.load_snapshot(self.snap_path)

    def test_incomplete_while_tasks_remain(self):
        self.done("t1")
        got = closure.closure_check(self.snap, self.ldg, self.log)
        self.assertEqual(got["status"], "incomplete")
        self.assertIn("t2", got["why"])

    def test_closes_when_all_snapshot_tasks_done(self):
        self.done("t1", "t2")
        got = closure.closure_check(self.snap, self.ldg, self.log)
        self.assertTrue(got["complete"])

    def test_live_ledger_rescope_cannot_shrink_done(self):
        # live ledger lost t2 without a ratified descope -> incomplete
        shrunk = Ledger(ledger_mod.validate_tasks({"tasks": [
            {"id": "t1", "phase": "p1", "profile": "routine", "deps": []}]}))
        self.done("t1")
        got = closure.closure_check(self.snap, shrunk, self.log)
        self.assertEqual(got["status"], "incomplete")
        self.assertIn("vanished", got["why"])

    def test_ratified_descope_is_honored(self):
        shrunk = Ledger(ledger_mod.validate_tasks({"tasks": [
            {"id": "t1", "phase": "p1", "profile": "routine", "deps": []}]}))
        self.done("t1")
        got = closure.closure_check(self.snap, shrunk, self.log,
                                    ratified_descopes=["t2"])
        self.assertTrue(got["complete"])
        self.assertIn("descope", got["why"])

    def test_unknown_descope_is_loud(self):
        with self.assertRaises(ClosureError):
            closure.closure_check(self.snap, self.ldg, self.log,
                                  ratified_descopes=["ghost"])

    def test_fresh_evidence_rule(self):
        self.done("t1", "t2")
        stale = closure.closure_check(
            self.snap, self.ldg, self.log,
            evidence_ts="2026-07-04T10:00:00Z",
            last_remediation_ts="2026-07-04T11:00:00Z")
        self.assertEqual(stale["status"], "stale_evidence")
        fresh = closure.closure_check(
            self.snap, self.ldg, self.log,
            evidence_ts="2026-07-04T12:00:00Z",
            last_remediation_ts="2026-07-04T11:00:00Z")
        self.assertTrue(fresh["complete"])

    def test_bounded_remediation_escalates(self):
        got = closure.closure_check(self.snap, self.ldg, self.log,
                                    remediation_rounds=3, max_rounds=3)
        self.assertEqual(got["status"], "escalate")
        self.assertIn("operator", got["why"])

    def test_gate_hook_end_to_end(self):
        ledger_path = os.path.join(self.dir.name, "tasks.json")
        with open(ledger_path, "w") as fh:
            json.dump(tasks_doc(), fh)
        script = os.path.join(REPO_ROOT, "hooks", "closure_gate.py")
        base = [sys.executable, script, "--snapshot", self.snap_path,
                "--ledger", ledger_path, "--events", self.log.path]
        blocked = subprocess.run(base, capture_output=True, text=True,
                                 timeout=30)
        self.assertEqual(blocked.returncode, 2)
        self.done("t1", "t2")
        clear = subprocess.run(base, capture_output=True, text=True, timeout=30)
        self.assertEqual(clear.returncode, 0)
        # fail-closed on a missing snapshot
        broken = subprocess.run(
            [sys.executable, script, "--snapshot", "/none.json",
             "--ledger", ledger_path, "--events", self.log.path],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(broken.returncode, 2)


if __name__ == "__main__":
    unittest.main()
