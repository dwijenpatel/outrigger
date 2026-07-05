"""Tests for harness.planning (I2) — plan readiness + content-bound ratification."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import closure, ledger as ledger_mod, planning
from harness.planning import PlanningError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPEC_BODY = (
    "## Scope\nTenant-scoped customer records.\n\n"
    "## Interfaces\n`POST /customers` `{name, phone}` -> 201 `{id}`.\n\n"
    "## Acceptance criteria\n- tenant B cannot read tenant A's customers\n"
    "- empty name -> 422 with field error\n\n## Non-goals\nSearch, import.\n")


def tasks_doc():
    return {"tasks": [
        {"id": "t1", "phase": "p1", "profile": "critical", "deps": []},
        {"id": "t2", "phase": "p1", "profile": "routine", "deps": ["t1"]},
    ]}


class PlanFixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.plan = os.path.join(self.dir.name, "plan")
        os.makedirs(os.path.join(self.plan, "specs"))
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            json.dump(tasks_doc(), fh)
        for tid in ("t1", "t2"):
            with open(os.path.join(self.plan, "specs", f"{tid}.md"), "w") as fh:
                fh.write(SPEC_BODY)
        with open(os.path.join(self.plan, "floors.json"), "w") as fh:
            json.dump({"floors": [{"glob": "pilot/**/auth/**",
                                   "min_profile": "critical"}]}, fh)
        self.snapshot = os.path.join(self.dir.name, "snapshot.json")
        closure.freeze_snapshot(
            ledger_mod.Ledger(ledger_mod.validate_tasks(tasks_doc())),
            self.snapshot)

    def tearDown(self):
        self.dir.cleanup()

    def ready(self):
        return planning.plan_ready(self.plan, self.snapshot)

    def failing_check(self, result):
        return next(c for c in result["checks"] if not c["ok"])


class PlanReadyTests(PlanFixture):
    def test_unratified_plan_not_ready(self):
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertEqual(self.failing_check(result)["check"], "ratification")
        self.assertIn("plan-build", self.failing_check(result)["detail"])

    def test_ratified_plan_ready(self):
        planning.ratify(self.plan, "dwijen")
        result = self.ready()
        self.assertTrue(result["ready"], result["why"])
        self.assertIn("approved by dwijen",
                      result["checks"][-1]["detail"])

    def test_edit_after_ratification_voids_it(self):
        planning.ratify(self.plan, "dwijen")
        with open(os.path.join(self.plan, "specs", "t1.md"), "a") as fh:
            fh.write("\n(edited after approval)\n")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("changed after ratification", result["why"])

    def test_missing_spec_blocks(self):
        os.unlink(os.path.join(self.plan, "specs", "t2.md"))
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("no spec file", result["why"])
        self.assertIn("t2", result["why"])

    def test_thin_spec_blocks(self):
        with open(os.path.join(self.plan, "specs", "t2.md"), "w") as fh:
            fh.write("do the thing")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("too thin", result["why"])

    def test_missing_floors_blocks(self):
        os.unlink(os.path.join(self.plan, "floors.json"))
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("risk floors are part of the plan", result["why"])

    def test_snapshot_ledger_drift_blocks(self):
        doc = tasks_doc()
        doc["tasks"].append({"id": "t3", "phase": "p1", "profile": "routine",
                             "deps": []})
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            json.dump(doc, fh)
        with open(os.path.join(self.plan, "specs", "t3.md"), "w") as fh:
            fh.write(SPEC_BODY)
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("does not match tasks.json", result["why"])

    def test_missing_snapshot_blocks(self):
        os.unlink(self.snapshot)
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("snapshot", result["why"])

    def test_malformed_ledger_blocks(self):
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            fh.write("not json")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertEqual(self.failing_check(result)["check"], "ledger")


class RatifyTests(PlanFixture):
    def test_ratify_writes_content_bound_stamp(self):
        doc = planning.ratify(self.plan, "dwijen")
        self.assertEqual(doc["content_hash"], planning.content_hash(self.plan))
        self.assertEqual(doc["approved_by"], "dwijen")

    def test_ratify_refuses_blank_approver(self):
        with self.assertRaises(PlanningError):
            planning.ratify(self.plan, "  ")

    def test_ratify_refuses_malformed_plan(self):
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            fh.write("{}")
        with self.assertRaises((PlanningError, ledger_mod.LedgerError)):
            planning.ratify(self.plan, "dwijen")

    def test_stamp_itself_not_hashed(self):
        before = planning.content_hash(self.plan)
        planning.ratify(self.plan, "dwijen")
        self.assertEqual(planning.content_hash(self.plan), before)


class CliTests(PlanFixture):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "harness.planning", *args],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)

    def test_ready_exit_codes(self):
        not_ready = self.run_cli("ready", "--plan-dir", self.plan,
                                 "--snapshot", self.snapshot)
        self.assertEqual(not_ready.returncode, 2)
        self.assertIn("plan NOT ready", not_ready.stderr)
        self.run_cli("ratify", "--plan-dir", self.plan,
                     "--approved-by", "dwijen")
        ready = self.run_cli("ready", "--plan-dir", self.plan,
                             "--snapshot", self.snapshot)
        self.assertEqual(ready.returncode, 0)


if __name__ == "__main__":
    unittest.main()
