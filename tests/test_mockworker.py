"""Tests for harness.mockworker (A6) + the zero-quota loop integration test.

The integration test is the point of A6: it drives ledger -> admission ->
mock worker -> run-log -> governor end to end without spending any quota.
"""

import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import admission, failures, governor, ledger as ledger_mod, mockworker
from harness.ledger import EventLog, Ledger
from harness.mockworker import MockWorker, MockWorkerError


class MockWorkerTests(unittest.TestCase):
    def test_static_usage_reports_scripted_numbers(self):
        w = MockWorker([{"outcome": "pass",
                         "usage": {"input_tokens": 100, "output_tokens": 10}}])
        result = w.run_turn()
        self.assertEqual(result["usage"]["total_tokens"], 110)
        self.assertEqual(result["outcome"], "pass")

    def test_cumulative_usage_scales_with_successful_turns_only(self):
        w = MockWorker([
            {"outcome": "pass", "usage": {"input_tokens": 100}},
            {"outcome": "fail", "usage": {"input_tokens": 100}},
            {"outcome": "pass", "usage": {"input_tokens": 100}},
        ], usage_mode="cumulative")
        first = w.run_turn()["usage"]["input_tokens"]
        failed = w.run_turn()["usage"]["input_tokens"]
        second = w.run_turn()["usage"]["input_tokens"]
        self.assertEqual(first, 100)    # 1 successful turn
        self.assertEqual(failed, 100)   # failure doesn't increment the multiplier
        self.assertEqual(second, 200)   # 2 successful turns

    def test_workspace_effects_apply_only_on_pass(self):
        with tempfile.TemporaryDirectory() as cwd:
            w = MockWorker([
                {"outcome": "fail",
                 "workspace_effects": [{"path": "out.txt", "append": "FAIL\n"}]},
                {"outcome": "pass",
                 "workspace_effects": [{"path": "out.txt", "append": "PASS\n"}]},
            ], cwd=cwd)
            w.run_turn()
            self.assertFalse(os.path.exists(os.path.join(cwd, "out.txt")))
            w.run_turn()
            with open(os.path.join(cwd, "out.txt")) as fh:
                self.assertEqual(fh.read(), "PASS\n")

    def test_error_turns_feed_the_failure_taxonomy(self):
        w = MockWorker([{"error": "429 Too Many Requests"},
                        {"error": "credit balance is too low"}])
        first = failures.classify(w.run_turn()["error"])
        second = failures.classify(w.run_turn()["error"])
        self.assertEqual(first["class"], "retryable")
        self.assertEqual(second["class"], "permanent")

    def test_cancelled_turn_has_no_effects_and_no_success(self):
        with tempfile.TemporaryDirectory() as cwd:
            w = MockWorker([{"cancelled": True,
                             "usage": {"input_tokens": 5}}], cwd=cwd)
            result = w.run_turn()
            self.assertEqual(result["kind"], "cancelled")
            self.assertEqual(w.successful_turns, 0)
            self.assertEqual(os.listdir(cwd), [])

    def test_script_exhaustion_is_loud(self):
        w = MockWorker([{"outcome": "pass"}])
        w.run_turn()
        with self.assertRaises(MockWorkerError):
            w.run_turn()

    def test_bad_scripts_rejected(self):
        bad = (
            [],                                            # empty
            [{"outcome": "pass", "error": "x"}],           # two kinds
            [{"outcome": "meh"}],                          # unknown outcome
            [{"outcome": "pass", "usage": {"wat": 1}}],    # unknown usage field
            [{"outcome": "pass", "usage": {"input_tokens": -1}}],
            [{"outcome": "pass",
              "workspace_effects": [{"path": "/abs", "append": "x"}]}],
            [{"outcome": "pass",
              "workspace_effects": [{"path": "../up", "append": "x"}]}],
        )
        for script in bad:
            with self.assertRaises(MockWorkerError, msg=script):
                MockWorker(script)

    def test_runlog_record_bridge_validates(self):
        w = MockWorker([{"outcome": "pass", "usage": {"input_tokens": 1000,
                                                      "cache_read_tokens": 5000}}])
        rec = w.to_runlog_record(w.run_turn(), task_id="t1", role="implementer",
                                 profile="routine", tier="cheap",
                                 model_id="m", effort="low")
        self.assertEqual(rec["total_tokens"], 6000)
        self.assertEqual(rec["event"], "task_complete")


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "traces", "run1.jsonl")

    def tearDown(self):
        self.dir.cleanup()

    def test_record_then_replay_roundtrip(self):
        w = MockWorker([{"outcome": "pass", "usage": {"input_tokens": 10}},
                        {"error": "timeout"}])
        events = [w.run_turn(), w.run_turn()]
        mockworker.record_trace(self.path, events)
        replayed = mockworker.replay_trace(self.path)
        self.assertEqual(len(replayed), 2)
        self.assertEqual(replayed[0]["kind"], "result")
        self.assertEqual(replayed[1]["kind"], "error")

    def test_worker_from_trace_replays_identically(self):
        original = MockWorker([{"outcome": "pass",
                                "usage": {"input_tokens": 42}}])
        mockworker.record_trace(self.path, [original.run_turn()])
        clone = mockworker.worker_from_trace(self.path)
        result = clone.run_turn()
        self.assertEqual(result["usage"]["input_tokens"], 42)
        self.assertEqual(result["outcome"], "pass")

    def test_corrupt_trace_is_loud(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as fh:
            fh.write('{"kind": "result"}\n{broken\n')
        with self.assertRaises(MockWorkerError):
            mockworker.replay_trace(self.path)

    def test_empty_trace_is_loud(self):
        mockworker.record_trace(self.path, [])
        with self.assertRaises(MockWorkerError):
            mockworker.worker_from_trace(self.path)


class LoopIntegrationTest(unittest.TestCase):
    """Zero-quota e2e: ledger -> governor -> admission -> mock worker -> run-log.

    Two tasks; the first burns most of a calibrated ceiling, so window-aware
    admission must defer the second. Every moving part is the real module.
    """

    def test_admission_defers_after_mock_burn(self):
        with tempfile.TemporaryDirectory() as root:
            log = EventLog(os.path.join(root, "events.jsonl"))
            ldg = Ledger(ledger_mod.validate_tasks({"tasks": [
                {"id": "t1", "phase": "p1", "profile": "routine", "deps": []},
                {"id": "t2", "phase": "p1", "profile": "routine", "deps": []},
            ]}))
            estimates = {"_meta": {"min_samples_per_profile": 1},
                         "cost_estimate_by_profile":
                             {"routine": {"p95": 400_000, "sample_size": 20}}}
            ceiling = 1_000_000  # calibrated-for-test window ceiling
            worker = MockWorker(
                [{"outcome": "pass", "usage": {"input_tokens": 100_000,
                                               "cache_read_tokens": 500_000}}])
            records = []

            # -- task t1: admitted in a fresh window, runs, accounts its burn
            occ0 = governor.estimate_from_runlog(
                records, now=datetime.datetime.now(datetime.timezone.utc),
                ceilings={"five_hour": ceiling})
            first = admission.admit_task(
                "routine", occ0.windows.get("five_hour"),
                estimates_doc=estimates, window_ceiling_tokens=ceiling)
            self.assertTrue(first["admit"])
            log.record_status("t1", "in_progress", ledger=ldg)
            result = worker.run_turn()
            records.append(worker.to_runlog_record(
                result, task_id="t1", role="implementer", profile="routine",
                tier="cheap", model_id="m", effort="low"))
            log.record_status("t1", "done", ledger=ldg)

            # -- task t2: the estimate rung now sees 600k of 1M burned (0.6);
            # 0.6 + 400k/1M forecast = 1.0 projected >= 0.8 degrade -> defer
            occ1 = governor.estimate_from_runlog(
                records, now=datetime.datetime.now(datetime.timezone.utc),
                ceilings={"five_hour": ceiling})
            self.assertAlmostEqual(occ1.windows["five_hour"], 0.6)
            self.assertTrue(occ1.optimistic)  # estimate rung is honest about itself
            second = admission.admit_task(
                "routine", occ1.windows["five_hour"],
                estimates_doc=estimates, window_ceiling_tokens=ceiling)
            self.assertFalse(second["admit"])

            # -- the ledger view agrees: t1 done, t2 still runnable (deferred,
            # not blocked), and the governor decision rolls up sticky-estimated
            self.assertEqual(ledger_mod.runnable(ldg, log), ["t2"])
            decision = governor.decide(occ1)
            rollup = governor.summarize_decisions([decision])
            self.assertTrue(rollup["estimated"])
            self.assertEqual(
                governor.fmt_estimated(600_000, rollup["estimated"]), "~600000")


if __name__ == "__main__":
    unittest.main()
