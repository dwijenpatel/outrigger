"""Tests for harness.calibration (D4) and harness.replay (D3)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import calibration, replay
from harness.calibration import CalibrationError, CanaryLog, EscapesLog
from harness.replay import ReplayCounts, ReplayError


class EscapesLogTests(unittest.TestCase):
    def test_record_and_read(self):
        with tempfile.TemporaryDirectory() as root:
            log = EscapesLog(os.path.join(root, "escapes.jsonl"))
            log.record("t7", "cross-tenant read on crew_schedules", "critical",
                       discovered_by="operator", panel_lenses=["correctness"])
            recs = log.read()
            self.assertEqual(recs[0]["kind"], "escape")
            self.assertEqual(recs[0]["severity"], "critical")

    def test_bad_records_loud(self):
        with tempfile.TemporaryDirectory() as root:
            log = EscapesLog(os.path.join(root, "e.jsonl"))
            with self.assertRaises(CalibrationError):
                log.record("", "desc", "critical", "op")
            with self.assertRaises(CalibrationError):
                log.record("t1", "desc", "catastrophic", "op")


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = CanaryLog(os.path.join(self.dir.name, "canaries.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def plant_and_result(self, cid, caught):
        self.log.plant(cid, "off-by-one planted in pagination", "task/x",
                       expected_lens="correctness")
        self.log.result(cid, caught=caught,
                        caught_by_lens="correctness" if caught else None)

    def test_result_requires_a_real_trial(self):
        with self.assertRaises(CalibrationError):
            self.log.result("ghost", caught=True)

    def test_downgrade_frozen_until_enough_trials(self):
        self.plant_and_result("c1", True)
        got = calibration.downgrade_allowed(self.log.trials(), escapes=[])
        self.assertFalse(got["allowed"])
        self.assertIn("required before trusting", got["why"])

    def test_downgrade_allowed_after_clean_trials(self):
        for i in range(3):
            self.plant_and_result(f"c{i}", True)
        got = calibration.downgrade_allowed(self.log.trials(), escapes=[])
        self.assertTrue(got["allowed"])

    def test_a_miss_freezes_the_downgrade(self):
        for i in range(2):
            self.plant_and_result(f"c{i}", True)
        self.plant_and_result("c-missed", False)
        got = calibration.downgrade_allowed(self.log.trials(), escapes=[])
        self.assertFalse(got["allowed"])
        self.assertIn("c-missed", got["why"])

    def test_old_miss_outside_window_can_age_out(self):
        self.plant_and_result("old-miss", False)
        for i in range(5):
            self.plant_and_result(f"c{i}", True)
        got = calibration.downgrade_allowed(self.log.trials(), escapes=[],
                                            min_trials=3, recent_window=5)
        self.assertTrue(got["allowed"])

    def test_escape_newer_than_trials_freezes(self):
        for i in range(3):
            self.plant_and_result(f"c{i}", True)
        escapes = [{"ts": "9999-01-01T00:00:00Z", "kind": "escape"}]
        got = calibration.downgrade_allowed(self.log.trials(), escapes=escapes)
        self.assertFalse(got["allowed"])
        self.assertIn("escape", got["why"])


class KillRateTests(unittest.TestCase):
    def test_kill_rate_math(self):
        trials = [{"killed": True}, {"killed": True}, {"killed": False}]
        self.assertAlmostEqual(calibration.kill_rate(trials), 2 / 3)
        self.assertIsNone(calibration.kill_rate([]))

    def test_weak_oracle_raises_rigor(self):
        got = calibration.rigor_adjustment(0.5)
        self.assertEqual(got["adjustment"], "raise")

    def test_unknown_rate_treated_as_weak(self):
        self.assertEqual(calibration.rigor_adjustment(None)["adjustment"], "raise")

    def test_strong_oracle_holds_never_lowers(self):
        got = calibration.rigor_adjustment(0.9)
        self.assertEqual(got["adjustment"], "hold")
        self.assertIn("downgrades still need canary proof", got["why"])


MANIFEST = {
    "tests/test_billing.py": ["billing/charge.py", "billing/plan.py"],
    "tests/test_auth.py": ["auth/session.py"],
    "tests/test_ui.py": ["ui/list.py"],
}
CORPUS = sorted(MANIFEST) + ["tests/test_orphan.py"]  # orphan: no dep record


class ReplayPlanTests(unittest.TestCase):
    def test_disabled_by_default_everything_fresh(self):
        plan = replay.replay_plan(MANIFEST, ["ui/list.py"], CORPUS)
        self.assertFalse(plan["enabled"])
        self.assertEqual(plan["replay"], [])
        self.assertEqual(sorted(plan["rerun_fresh"]), CORPUS)

    def test_safe_rts_never_skips_affected(self):
        plan = replay.replay_plan(MANIFEST, ["billing/charge.py"], CORPUS,
                                  enabled=True)
        self.assertIn("tests/test_billing.py", plan["rerun_fresh"])
        self.assertIn("tests/test_auth.py", plan["replay"])
        self.assertIn("tests/test_ui.py", plan["replay"])

    def test_unanalyzable_falls_back_to_fresh(self):
        plan = replay.replay_plan(MANIFEST, ["ui/list.py"], CORPUS, enabled=True)
        self.assertIn("tests/test_orphan.py", plan["rerun_fresh"])
        self.assertIn("no dependency record", plan["reasons"]["tests/test_orphan.py"])

    def test_floored_surfaces_never_replay(self):
        plan = replay.replay_plan(MANIFEST, ["ui/list.py"], CORPUS,
                                  floored_paths=["auth/session.py"], enabled=True)
        self.assertIn("tests/test_auth.py", plan["rerun_fresh"])
        self.assertIn("never replayed", plan["reasons"]["tests/test_auth.py"])

    def test_leakage_budget_rotates_overused_entries(self):
        plan = replay.replay_plan(MANIFEST, ["ui/list.py"], CORPUS,
                                  replay_counts={"tests/test_auth.py": 10},
                                  replay_budget=10, enabled=True)
        self.assertIn("tests/test_auth.py", plan["rerun_fresh"])
        self.assertIn("leakage budget", plan["reasons"]["tests/test_auth.py"])

    def test_fresh_authoring_always_required_on_nonempty_diff(self):
        plan = replay.replay_plan(MANIFEST, ["ui/list.py"], CORPUS, enabled=True)
        self.assertTrue(plan["fresh_authoring_required"])
        empty = replay.replay_plan(MANIFEST, [], CORPUS, enabled=True)
        self.assertFalse(empty["fresh_authoring_required"])

    def test_bad_manifest_loud(self):
        with self.assertRaises(ReplayError):
            replay.replay_plan({"t": "not-a-list"}, [], [], enabled=True)


class ReplayCountsTests(unittest.TestCase):
    def test_record_and_rotate_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            counts = ReplayCounts(os.path.join(root, "counts.json"))
            counts.record_replays(["a", "b"])
            counts.record_replays(["a"])
            self.assertEqual(counts.read(), {"a": 2, "b": 1})
            counts.rotate(["a"])
            self.assertEqual(counts.read(), {"b": 1})

    def test_corrupt_state_loud(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "counts.json")
            with open(path, "w") as fh:
                fh.write("{broken")
            with self.assertRaises(ReplayError):
                ReplayCounts(path).read()


if __name__ == "__main__":
    unittest.main()
