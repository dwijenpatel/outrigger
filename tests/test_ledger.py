"""Tests for harness.ledger — disk-is-the-memory task state (design §3.4/§9)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ledger as ledger_mod
from harness.ledger import Ledger, LedgerError, StatusIndex


def tasks_doc():
    return {"tasks": [
        {"id": "t1", "phase": "p1", "profile": "routine", "deps": []},
        {"id": "t2", "phase": "p1", "profile": "elevated", "deps": ["t1"]},
        {"id": "t3", "phase": "p2", "profile": "high", "deps": ["t1"],
         "may_be_invalidated_by": ["t2"]},
    ]}


class ValidateTasksTests(unittest.TestCase):
    def test_valid_doc_normalizes(self):
        tasks = ledger_mod.validate_tasks(tasks_doc())
        self.assertEqual(set(tasks), {"t1", "t2", "t3"})
        self.assertEqual(tasks["t1"]["may_be_invalidated_by"], [])

    def test_duplicate_id_rejected(self):
        doc = tasks_doc()
        doc["tasks"].append(dict(doc["tasks"][0]))
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_unknown_dep_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["deps"] = ["ghost"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_self_dep_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["deps"] = ["t1"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_unknown_soft_edge_rejected(self):
        doc = tasks_doc()
        doc["tasks"][0]["may_be_invalidated_by"] = ["ghost"]
        with self.assertRaises(LedgerError):
            ledger_mod.validate_tasks(doc)

    def test_bad_profile_and_missing_phase_rejected(self):
        for patch in ({"profile": "mega"}, {"phase": ""}):
            doc = tasks_doc()
            doc["tasks"][0].update(patch)
            with self.assertRaises(LedgerError):
                ledger_mod.validate_tasks(doc)

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(tasks_doc(), fh)
            path = fh.name
        try:
            self.assertIn("t2", Ledger.load(path))
        finally:
            os.unlink(path)


class StatusIndexTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.index = StatusIndex(os.path.join(self.dir.name, "state", "index.json"))
        self.ledger = Ledger(ledger_mod.validate_tasks(tasks_doc()))

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_means_all_not_started(self):
        self.assertEqual(self.index.status_of("t1"), "not_started")

    def test_legal_lifecycle_persists(self):
        self.index.update("t1", "in_progress", ledger=self.ledger)
        self.index.update("t1", "done", ledger=self.ledger)
        self.assertEqual(self.index.status_of("t1"), "done")

    def test_illegal_transitions_rejected(self):
        with self.assertRaises(LedgerError):
            self.index.update("t1", "done")  # not_started -> done skips work
        self.index.update("t1", "in_progress")
        self.index.update("t1", "done")
        with self.assertRaises(LedgerError):
            self.index.update("t1", "in_progress")  # done is terminal

    def test_same_status_is_idempotent(self):
        self.index.update("t1", "in_progress")
        self.index.update("t1", "in_progress", note="still going")
        self.assertEqual(self.index.status_of("t1"), "in_progress")

    def test_parked_roundtrip_with_note(self):
        self.index.update("t2", "in_progress")
        entry = self.index.update("t2", "parked", note="blocked on operator answer")
        self.assertEqual(entry["note"], "blocked on operator answer")
        self.index.update("t2", "in_progress")

    def test_failed_allows_retry(self):
        self.index.update("t1", "in_progress")
        self.index.update("t1", "failed")
        self.index.update("t1", "in_progress")

    def test_unknown_status_rejected(self):
        with self.assertRaises(LedgerError):
            self.index.update("t1", "half_done")

    def test_phantom_task_rejected_when_ledger_given(self):
        with self.assertRaises(LedgerError):
            self.index.update("t9", "in_progress", ledger=self.ledger)

    def test_corrupt_index_is_a_loud_stop_not_a_reset(self):
        os.makedirs(os.path.dirname(self.index.path), exist_ok=True)
        with open(self.index.path, "w") as fh:
            fh.write('{"tasks": {')  # simulated torn write
        with self.assertRaises(LedgerError):
            self.index.read()

    def test_write_is_atomic_no_temp_droppings(self):
        self.index.update("t1", "in_progress")
        entries = os.listdir(os.path.dirname(self.index.path))
        self.assertEqual(entries, ["index.json"])

    def test_resume_marker_roundtrip(self):
        self.assertIsNone(self.index.get_resume_marker())
        self.index.set_resume_marker({"reason": "pause threshold",
                                      "binding_window": "five_hour"})
        marker = self.index.get_resume_marker()
        self.assertEqual(marker["reason"], "pause threshold")
        self.assertIn("set_at", marker)
        self.index.clear_resume_marker()
        self.assertIsNone(self.index.get_resume_marker())


class RunnableAndSummaryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.index = StatusIndex(os.path.join(self.dir.name, "index.json"))
        self.ledger = Ledger(ledger_mod.validate_tasks(tasks_doc()))

    def tearDown(self):
        self.dir.cleanup()

    def test_fresh_state_only_root_runnable(self):
        self.assertEqual(ledger_mod.runnable(self.ledger, self.index), ["t1"])

    def test_dep_completion_unlocks_cross_phase(self):
        self.index.update("t1", "in_progress")
        self.assertEqual(ledger_mod.runnable(self.ledger, self.index), [])
        self.index.update("t1", "done")
        # t3 is in phase p2 but becomes runnable alongside p1's t2 (§6.1 cross-phase)
        self.assertEqual(sorted(ledger_mod.runnable(self.ledger, self.index)),
                         ["t2", "t3"])

    def test_cycle_tasks_never_runnable_not_crash(self):
        doc = {"tasks": [
            {"id": "a", "phase": "p", "profile": "routine", "deps": ["b"]},
            {"id": "b", "phase": "p", "profile": "routine", "deps": ["a"]},
        ]}
        cyclic = Ledger(ledger_mod.validate_tasks(doc))
        self.assertEqual(ledger_mod.runnable(cyclic, self.index), [])

    def test_summary_resume_view(self):
        self.index.update("t1", "in_progress")
        self.index.update("t1", "done")
        self.index.update("t2", "in_progress")
        self.index.update("t2", "parked", note="waiting")
        view = ledger_mod.summary(self.ledger, self.index)
        self.assertEqual(view["counts"]["done"], 1)
        self.assertEqual(view["parked"], ["t2"])
        self.assertEqual(view["runnable"], ["t3"])
        self.assertFalse(view["complete"])

    def test_summary_complete_flag(self):
        for tid in ("t1", "t2", "t3"):
            self.index.update(tid, "in_progress")
            self.index.update(tid, "done")
        self.assertTrue(ledger_mod.summary(self.ledger, self.index)["complete"])


if __name__ == "__main__":
    unittest.main()
