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
        got = calibration.downgrade_allowed(
            self.log.trials(), escapes=[],
            discovery={"active": True, "why": "hunt 2 merges ago"})
        self.assertTrue(got["allowed"])
        self.assertIn("discovery active", got["why"])

    def test_downgrade_frozen_without_discovery_channel(self):
        # H6: clean canaries + zero escapes still gate nothing when nothing
        # could have discovered an escape
        for i in range(3):
            self.plant_and_result(f"c{i}", True)
        unchecked = calibration.downgrade_allowed(self.log.trials(), escapes=[])
        self.assertFalse(unchecked["allowed"])
        self.assertIn("discovery channel inactive", unchecked["why"])
        lapsed = calibration.downgrade_allowed(
            self.log.trials(), escapes=[],
            discovery=calibration.discovery_active(11, every_n_merges=10))
        self.assertFalse(lapsed["allowed"])
        self.assertIn("overdue", lapsed["why"])

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
        got = calibration.downgrade_allowed(
            self.log.trials(), escapes=[], min_trials=3, recent_window=5,
            discovery={"active": True, "why": "hunt current"})
        self.assertTrue(got["allowed"])

    def test_escape_newer_than_trials_freezes(self):
        for i in range(3):
            self.plant_and_result(f"c{i}", True)
        escapes = [{"ts": "9999-01-01T00:00:00Z", "kind": "escape"}]
        got = calibration.downgrade_allowed(self.log.trials(), escapes=escapes)
        self.assertFalse(got["allowed"])
        self.assertIn("escape", got["why"])


class PanelCorrelationTests(unittest.TestCase):
    """H5 — all-lenses-missed canaries are correlated blind spots."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = CanaryLog(os.path.join(self.dir.name, "canaries.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def trial(self, cid, lens_results):
        self.log.plant(cid, "planted defect", "task/x",
                       expected_lens="correctness")
        self.log.result(cid, caught=any(lens_results.values()),
                        lens_results=lens_results)

    def test_inconsistent_lens_results_refused(self):
        self.log.plant("c1", "planted", "task/x", expected_lens="correctness")
        with self.assertRaises(CalibrationError):
            self.log.result("c1", caught=False,
                            lens_results={"correctness": True})

    def test_empty_lens_results_refused(self):
        self.log.plant("c1", "planted", "task/x", expected_lens="correctness")
        with self.assertRaises(CalibrationError):
            self.log.result("c1", caught=False, lens_results={})

    def test_blind_spot_detected(self):
        self.trial("c1", {"correctness": False, "security": False})
        self.trial("c2", {"correctness": True, "security": False})
        got = calibration.panel_correlation(self.log.trials())
        self.assertEqual(got["trials_scored"], 2)
        self.assertEqual(got["correlated_blind_spots"], 1)
        self.assertEqual(got["blind_spot_ids"], ["c1"])
        self.assertEqual(got["sole_catcher_trials"], 1)
        self.assertIn("EVERY lens", got["why"])
        self.assertEqual(got["per_lens"]["correctness"],
                         {"trials": 2, "caught": 1})
        self.assertEqual(got["per_lens"]["security"],
                         {"trials": 2, "caught": 0})

    def test_no_blind_spots_reports_diversity_carrying(self):
        self.trial("c1", {"correctness": True, "security": False})
        got = calibration.panel_correlation(self.log.trials())
        self.assertEqual(got["correlated_blind_spots"], 0)
        self.assertIn("lens diversity", got["why"])

    def test_unscored_trials_reported_never_guessed(self):
        self.log.plant("c1", "planted", "task/x", expected_lens="correctness")
        self.log.result("c1", caught=True, caught_by_lens="correctness")
        got = calibration.panel_correlation(self.log.trials())
        self.assertEqual(got["trials_scored"], 0)
        self.assertEqual(got["trials_unscored"], 1)
        self.assertIn("unmeasured", got["why"])


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
        self.assertEqual(sorted(plan["rerun_fresh"]), sorted(CORPUS))

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


class EscapeDiscoveryTests(unittest.TestCase):
    """H6 — backfill rule, hunt log, deterministic sample, channel check."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.escapes = EscapesLog(os.path.join(self.dir.name, "escapes.jsonl"))
        self.hunts = calibration.HuntLog(
            os.path.join(self.dir.name, "hunts.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def test_backfill_attributes_to_merging_task_and_panel(self):
        rec = calibration.backfill_escape(
            self.escapes, merged_task="t3",
            description="pagination drops the last row",
            severity="major", discovered_in="t9",
            panel_lenses=["correctness", "regression"])
        self.assertEqual(rec["task_id"], "t3")
        self.assertEqual(rec["discovered_by"], "backfill:t9")
        self.assertEqual(rec["panel_lenses"], ["correctness", "regression"])
        self.assertEqual(len(self.escapes.read()), 1)

    def test_self_discovery_is_not_an_escape(self):
        with self.assertRaises(CalibrationError):
            calibration.backfill_escape(
                self.escapes, merged_task="t3", description="x",
                severity="minor", discovered_in="t3")

    def test_hunt_log_validates(self):
        rec = self.hunts.record("hunt-1", ["t1", "t2"], ["correctness"], 0)
        self.assertEqual(rec["kind"], "hunt")
        with self.assertRaises(CalibrationError):
            self.hunts.record("hunt-2", [], ["correctness"], 0)
        with self.assertRaises(CalibrationError):
            self.hunts.record("hunt-3", ["t1"], [], -1)

    def test_hunt_sample_deterministic_and_seeded(self):
        ids = [f"t{i}" for i in range(20)]
        a = calibration.hunt_sample(ids, k=3, seed="round-1")
        b = calibration.hunt_sample(ids, k=3, seed="round-1")
        c = calibration.hunt_sample(ids, k=3, seed="round-2")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        self.assertNotEqual(a, c)  # different round samples differently
        self.assertEqual(calibration.hunt_sample([], k=3), [])

    def test_discovery_active_states(self):
        never = calibration.discovery_active(None)
        self.assertFalse(never["active"])
        self.assertIn("never", never["why"].replace("has ever", "never"))
        fresh = calibration.discovery_active(3, every_n_merges=10)
        self.assertTrue(fresh["active"])
        lapsed = calibration.discovery_active(11, every_n_merges=10)
        self.assertFalse(lapsed["active"])
        with self.assertRaises(CalibrationError):
            calibration.discovery_active(-1)
        with self.assertRaises(CalibrationError):
            calibration.discovery_active(1, every_n_merges=0)
