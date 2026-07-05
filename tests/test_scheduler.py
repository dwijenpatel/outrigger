"""Tests for harness.scheduler (B2) — preflight DAG, priority, safety, admission."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ledger as ledger_mod, scheduler
from harness.ledger import EventLog, Ledger


def make_ledger(tasks):
    return Ledger(ledger_mod.validate_tasks({"tasks": tasks}))


def chain_ledger():
    # a -> b -> c (chain) plus independent d; e soft-depends on b
    return make_ledger([
        {"id": "a", "phase": "p1", "profile": "routine", "deps": []},
        {"id": "b", "phase": "p1", "profile": "routine", "deps": ["a"]},
        {"id": "c", "phase": "p2", "profile": "critical", "deps": ["b"]},
        {"id": "d", "phase": "p2", "profile": "elevated", "deps": []},
        {"id": "e", "phase": "p2", "profile": "routine", "deps": [],
         "may_be_invalidated_by": ["b"]},
    ])


ESTIMATES = {"_meta": {"min_samples_per_profile": 1},
             "cost_estimate_by_profile": {
                 "routine": {"p95": 100_000, "sample_size": 10},
                 "elevated": {"p95": 200_000, "sample_size": 10},
                 "high": {"p95": 300_000, "sample_size": 10},
                 "critical": {"p95": 400_000, "sample_size": 10}}}


class PreflightTests(unittest.TestCase):
    def test_dag_passes(self):
        self.assertTrue(scheduler.preflight(chain_ledger())["ok"])

    def test_cycle_reported_with_members(self):
        ldg = make_ledger([
            {"id": "x", "phase": "p", "profile": "routine", "deps": ["y"]},
            {"id": "y", "phase": "p", "profile": "routine", "deps": ["x"]},
            {"id": "z", "phase": "p", "profile": "routine", "deps": []},
        ])
        check = scheduler.preflight(ldg)
        self.assertFalse(check["ok"])
        self.assertEqual(len(check["cycles"]), 1)
        self.assertEqual(set(check["cycles"][0]), {"x", "y"})


class PriorityTests(unittest.TestCase):
    def test_critical_path_lengths(self):
        cp = scheduler.critical_path_lengths(chain_ledger())
        self.assertEqual(cp["a"], 3)  # a -> b -> c
        self.assertEqual(cp["b"], 2)
        self.assertEqual(cp["c"], 1)
        self.assertEqual(cp["d"], 1)

    def test_longer_chain_beats_higher_risk(self):
        # a unlocks 2 downstream tasks; d is higher-risk but unlocks nothing:
        # critical-path first, then risk (§6.1).
        ldg = chain_ledger()
        log_dir = tempfile.TemporaryDirectory()
        try:
            log = EventLog(os.path.join(log_dir.name, "e.jsonl"))
            out = scheduler.tick(ldg, log, occupancy=0.1, slots=1,
                                 estimates_doc=ESTIMATES,
                                 window_ceiling_tokens=10_000_000)
            self.assertEqual(out["start"], ["a"])
            deferred_ids = [d["task"] for d in out["deferred"]]
            self.assertEqual(deferred_ids[0], "d")  # next in priority: risk
        finally:
            log_dir.cleanup()

    def test_risk_breaks_critical_path_ties(self):
        ldg = make_ledger([
            {"id": "low", "phase": "p", "profile": "routine", "deps": []},
            {"id": "hot", "phase": "p", "profile": "critical", "deps": []},
        ])
        with tempfile.TemporaryDirectory() as d:
            log = EventLog(os.path.join(d, "e.jsonl"))
            out = scheduler.tick(ldg, log, occupancy=0.1, slots=1,
                                 estimates_doc=ESTIMATES,
                                 window_ceiling_tokens=10_000_000)
            self.assertEqual(out["start"], ["hot"])


class SafetyAndStateTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = EventLog(os.path.join(self.dir.name, "e.jsonl"))
        self.ldg = chain_ledger()

    def tearDown(self):
        self.dir.cleanup()

    def test_soft_edge_holds_task_until_source_done(self):
        out = scheduler.tick(self.ldg, self.log, occupancy=0.1, slots=5,
                             estimates_doc=ESTIMATES,
                             window_ceiling_tokens=10_000_000)
        self.assertIn("e", out["held_unsafe"])  # b not done yet
        self.assertNotIn("e", out["start"])
        # complete a and b -> e becomes safe
        for tid in ("a", "b"):
            self.log.record_status(tid, "in_progress")
            self.log.record_status(tid, "done")
        out2 = scheduler.tick(self.ldg, self.log, occupancy=0.1, slots=5,
                              estimates_doc=ESTIMATES,
                              window_ceiling_tokens=10_000_000)
        self.assertIn("e", out2["start"])
        self.assertEqual(out2["held_unsafe"], [])

    def test_reconciled_artifacts_feed_the_candidate_set(self):
        # events never say a is done, but the gate artifact does -> b runnable
        self.log.record_status("a", "in_progress")
        out = scheduler.tick(self.ldg, self.log,
                             artifacts={"a": {"gate": "pass"}},
                             occupancy=0.1, slots=5, estimates_doc=ESTIMATES,
                             window_ceiling_tokens=10_000_000)
        self.assertIn("b", out["start"])
        self.assertEqual(len(out["discrepancies"]), 1)

    def test_cycle_members_surface_in_tick(self):
        ldg = make_ledger([
            {"id": "x", "phase": "p", "profile": "routine", "deps": ["y"]},
            {"id": "y", "phase": "p", "profile": "routine", "deps": ["x"]},
        ])
        out = scheduler.tick(ldg, self.log, occupancy=0.1)
        self.assertFalse(out["preflight_ok"])
        self.assertEqual(out["on_cycle"], ["x", "y"])
        self.assertEqual(out["start"], [])


class AdmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = EventLog(os.path.join(self.dir.name, "e.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def test_slots_cap_respected(self):
        ldg = make_ledger([
            {"id": t, "phase": "p", "profile": "routine", "deps": []}
            for t in ("t1", "t2", "t3")])
        out = scheduler.tick(ldg, self.log, occupancy=0.1, slots=2,
                             estimates_doc=ESTIMATES,
                             window_ceiling_tokens=100_000_000)
        self.assertEqual(len(out["start"]), 2)
        self.assertEqual(out["deferred"][0]["reason"], "no idle slot")

    def test_in_flight_consumes_slots(self):
        ldg = make_ledger([
            {"id": "t1", "phase": "p", "profile": "routine", "deps": []}])
        out = scheduler.tick(ldg, self.log, occupancy=0.1, slots=1, in_flight=1,
                             estimates_doc=ESTIMATES,
                             window_ceiling_tokens=100_000_000)
        self.assertEqual(out["start"], [])

    def test_window_admission_defers_heavy_task(self):
        ldg = make_ledger([
            {"id": "big", "phase": "p", "profile": "critical", "deps": []}])
        # 0.6 occupancy + 400k/1M = 1.0 projected >= 0.8 -> defer
        out = scheduler.tick(ldg, self.log, occupancy=0.6, slots=1,
                             estimates_doc=ESTIMATES,
                             window_ceiling_tokens=1_000_000)
        self.assertEqual(out["start"], [])
        self.assertIn("would cross", out["deferred"][0]["reason"])

    def test_concurrent_slot_pays_pipeline_warmup(self):
        ldg = make_ledger([
            {"id": "t1", "phase": "p", "profile": "routine", "deps": []},
            {"id": "t2", "phase": "p", "profile": "routine", "deps": []}])
        # ceiling 1M, occupancy 0.5: t1 projects 0.6 (admit). t2 at slot 2 pays
        # 150k warmup: 0.5 + (100k+150k)/1M = 0.75 < 0.8 admit; warmup 250k ->
        # 0.85 defer.
        ok = scheduler.tick(ldg, self.log, occupancy=0.5, slots=2,
                            estimates_doc=ESTIMATES,
                            window_ceiling_tokens=1_000_000,
                            pipeline_warmup_tokens=150_000)
        self.assertEqual(len(ok["start"]), 2)
        tight = scheduler.tick(ldg, self.log, occupancy=0.5, slots=2,
                               estimates_doc=ESTIMATES,
                               window_ceiling_tokens=1_000_000,
                               pipeline_warmup_tokens=250_000)
        self.assertEqual(len(tight["start"]), 1)

    def test_unknown_occupancy_never_admits(self):
        ldg = make_ledger([
            {"id": "t1", "phase": "p", "profile": "routine", "deps": []}])
        out = scheduler.tick(ldg, self.log, occupancy=None, slots=1,
                             estimates_doc=ESTIMATES,
                             window_ceiling_tokens=1_000_000)
        self.assertEqual(out["start"], [])
        self.assertEqual(out["window_phase"], "unknown")


class WindowPhaseTests(unittest.TestCase):
    def test_phase_classification(self):
        self.assertEqual(scheduler.window_phase(0.1), "fresh")
        self.assertEqual(scheduler.window_phase(0.4), "mid")
        self.assertEqual(scheduler.window_phase(0.7), "tail")
        self.assertEqual(scheduler.window_phase(None), "unknown")

    def test_tail_runs_cheap_serial_work_first(self):
        ldg = make_ledger([
            {"id": "big", "phase": "p", "profile": "critical", "deps": [],
             "may_be_invalidated_by": []},
            {"id": "small", "phase": "p", "profile": "routine", "deps": []}])
        with tempfile.TemporaryDirectory() as d:
            log = EventLog(os.path.join(d, "e.jsonl"))
            out = scheduler.tick(ldg, log, occupancy=0.7, slots=3,
                                 estimates_doc=ESTIMATES,
                                 window_ceiling_tokens=100_000_000)
            # tail: serial (1 slot even though 3 offered), cheapest first
            self.assertEqual(out["window_phase"], "tail")
            self.assertEqual(out["start"], ["small"])

    def test_bad_config_rejected(self):
        with self.assertRaises(scheduler.SchedulerError):
            scheduler.window_phase(0.5, fresh_below=0.9, tail_above=0.5)


if __name__ == "__main__":
    unittest.main()


class ResetHeadroomPhaseTests(unittest.TestCase):
    """I17 — imminent-reset headroom demotes tail to mid; unknown never waived."""

    def test_tail_waived_only_with_headroom(self):
        from harness import scheduler
        self.assertEqual(scheduler.window_phase(0.62), "tail")
        self.assertEqual(scheduler.window_phase(
            0.62, reset_headroom_clears=True), "mid")
        self.assertEqual(scheduler.window_phase(
            None, reset_headroom_clears=True), "unknown")
        self.assertEqual(scheduler.window_phase(
            0.1, reset_headroom_clears=True), "fresh")
