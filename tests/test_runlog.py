"""Tests for harness.runlog — canonical telemetry stream (design §5.1/§8)."""

import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import runlog


def task(**overrides):
    rec = {"profile": "routine", "total_tokens": 1000, "ts": "2026-07-04T10:00:00Z"}
    rec.update(overrides)
    return rec


class ValidateRecordTests(unittest.TestCase):
    def test_minimal_task_record_normalizes(self):
        rec = runlog.validate_record({"profile": "routine", "total_tokens": 5})
        self.assertEqual(rec["event"], runlog.TASK_COMPLETE)
        runlog.parse_ts(rec["ts"])  # auto-filled and parseable

    def test_missing_profile_rejected(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"total_tokens": 5})

    def test_unknown_profile_rejected(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record(task(profile="mega"))

    def test_missing_total_tokens_rejected(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"profile": "routine"})

    def test_negative_and_bool_tokens_rejected(self):
        for bad in (-1, True, "12"):
            with self.assertRaises(runlog.RunLogError):
                runlog.validate_record(task(total_tokens=bad))

    def test_optional_enums_checked(self):
        for field, bad in [("tier", "gold"), ("effort", "turbo"),
                           ("outcome", "meh"), ("predicted_bucket", "XXL"),
                           ("role", "bystander")]:
            with self.assertRaises(runlog.RunLogError):
                runlog.validate_record(task(**{field: bad}))

    def test_valid_full_record_passes(self):
        rec = runlog.validate_record(task(
            tier="cheap", effort="low", outcome="pass", predicted_bucket="S",
            role="implementer", escaped=False, wall_secs=12.5,
            input_tokens=100, output_tokens=200, cache_read_tokens=5000,
            cache_creation_tokens=300))
        self.assertEqual(rec["tier"], "cheap")

    def test_non_task_event_needs_only_ts(self):
        rec = runlog.validate_record({"event": "governor_decision", "status": "ok"})
        self.assertEqual(rec["event"], "governor_decision")

    def test_bad_ts_rejected(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record(task(ts="yesterday-ish"))

    def test_escaped_must_be_bool(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record(task(escaped="no"))


class RunLogFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = runlog.RunLog(os.path.join(self.dir.name, "sub", "run-log.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_reads_empty(self):
        records, errors = self.log.read()
        self.assertEqual((records, errors), ([], []))

    def test_append_then_read_roundtrip(self):
        self.log.append(task())
        self.log.append(task(profile="high", total_tokens=9000))
        records, errors = self.log.read()
        self.assertEqual(errors, [])
        self.assertEqual([r["profile"] for r in records], ["routine", "high"])

    def test_append_rejects_invalid_without_writing(self):
        with self.assertRaises(runlog.RunLogError):
            self.log.append(task(profile="bogus"))
        self.assertEqual(self.log.read(), ([], []))

    def test_read_skips_corrupt_lines_and_reports(self):
        self.log.append(task())
        with open(self.log.path, "a") as fh:
            fh.write("{not json\n")
            fh.write(json.dumps({"profile": "routine"}) + "\n")  # missing tokens
        self.log.append(task(profile="critical"))
        records, errors = self.log.read()
        self.assertEqual(len(records), 2)
        self.assertEqual([lineno for lineno, _ in errors], [2, 3])

    def test_runlog_feeds_populate_estimates(self):
        """Records must be directly consumable by populate_estimates.compute()."""
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools", "budget-governor"))
        import populate_estimates
        for i in range(3):
            self.log.append(task(total_tokens=1000 * (i + 1)))
        records, _ = self.log.read()
        estimates, unknown = populate_estimates.compute(records)
        self.assertEqual(unknown, set())
        self.assertEqual(estimates["routine"]["sample_size"], 3)


class WindowAndSumTests(unittest.TestCase):
    def test_in_window_filters_by_ts(self):
        records = [task(ts="2026-07-04T06:00:00Z"),
                   task(ts="2026-07-04T09:00:00Z"),
                   task(ts="2026-07-04T11:00:00Z")]
        start = dt.datetime(2026, 7, 4, 8, 0, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 7, 4, 10, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(len(runlog.in_window(records, start, end)), 1)
        self.assertEqual(len(runlog.in_window(records, start)), 2)

    def test_sum_tokens_uses_total_when_no_components(self):
        self.assertEqual(runlog.sum_tokens([task(), task(total_tokens=500)]), 1500)

    def test_sum_tokens_weights_cache_reads(self):
        rec = task(input_tokens=100, output_tokens=200,
                   cache_creation_tokens=50, cache_read_tokens=10000,
                   total_tokens=10350)
        self.assertEqual(runlog.sum_tokens([rec]), 10350)          # default weight 1.0
        self.assertEqual(runlog.sum_tokens([rec], cache_read_weight=0.1), 1350)

    def test_to_predictor_records_shape(self):
        records = [task(predicted_bucket="M", escaped=True),
                   task(),  # no bucket → excluded
                   {"event": "governor_decision", "ts": "2026-07-04T10:00:00Z"}]
        out = runlog.to_predictor_records(records)
        self.assertEqual(out, [{"predicted_bucket": "M",
                                "actual_total_tokens": 1000,
                                "escaped": True}])

    def test_predictor_projection_feeds_validate_predictor(self):
        """Projected records must satisfy validate_predictor's expected fields."""
        out = runlog.to_predictor_records([task(predicted_bucket="XS")])
        rec = out[0]
        self.assertIn(rec["predicted_bucket"], runlog.BUCKETS)
        self.assertIsInstance(rec["actual_total_tokens"], int)
        self.assertIsInstance(rec["escaped"], bool)


if __name__ == "__main__":
    unittest.main()


class ModelFieldTests(unittest.TestCase):
    """I10 — the concrete model id rides every task_complete record."""

    def base(self, **patch):
        doc = {"event": "task_complete", "profile": "routine",
               "total_tokens": 100, "tier": "cheap", "effort": "low"}
        doc.update(patch)
        return doc

    def test_model_accepted_and_preserved(self):
        out = runlog.validate_record(self.base(model="claude-haiku-4-5"))
        self.assertEqual(out["model"], "claude-haiku-4-5")

    def test_model_optional(self):
        runlog.validate_record(self.base())  # no raise

    def test_bad_model_is_loud(self):
        for bad in ("", "   ", 7, None):
            with self.assertRaises(runlog.RunLogError):
                runlog.validate_record(self.base(model=bad))

    def test_spawncheck_resolution_feeds_the_record(self):
        # the loop merges spawncheck's resolved params straight in — the
        # requested spawn, never a worker self-report
        from harness import spawncheck
        resolved = spawncheck.validate_spawn(tier="cheap", effort="low")
        out = runlog.validate_record(self.base(
            tier=resolved["tier"], model=resolved["model"],
            effort=resolved["effort"]))
        self.assertEqual(out["model"], resolved["model"])
        self.assertTrue(out["model"])  # a concrete id, not a tier name
        self.assertNotIn(out["model"], ("cheap", "standard", "capable", "max"))


class WorkerEventTests(unittest.TestCase):
    """I15 (P2-12) — spawn/abort/park are validated events, not improvisations."""

    RESOLVED = {"model": "claude-haiku-4-5-20251001", "tier": "cheap",
                "effort": "low"}

    def test_worker_event_builds_validated_records(self):
        rec = runlog.worker_event(runlog.TASK_SPAWN, "GL2", "implementer",
                                  self.RESOLVED, attempt=1)
        self.assertEqual(rec["event"], "task_spawn")
        self.assertEqual(rec["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(rec["attempt"], 1)
        aborted = runlog.worker_event(runlog.TASK_ABORTED, "GL2",
                                      "test_author",
                                      {"model": "claude-fable-5",
                                       "tier": "max", "effort": "high"})
        self.assertEqual(aborted["event"], "task_aborted")

    def test_worker_events_validate_fields(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"event": "task_spawn", "role": "implementer"})
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"event": "task_parked", "task_id": "t",
                                    "role": "goblin"})
        with self.assertRaises(runlog.RunLogError):
            runlog.worker_event("task_finished", "t", "implementer",
                                self.RESOLVED)

    def test_attempt_validated_everywhere(self):
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"event": "task_complete",
                                    "profile": "routine", "total_tokens": 1,
                                    "attempt": 0})
        ok = runlog.validate_record({"event": "task_complete",
                                     "profile": "routine", "total_tokens": 1,
                                     "attempt": 3})
        self.assertEqual(ok["attempt"], 3)

    def test_spawn_total_tokens_optional_but_typed(self):
        rec = runlog.worker_event(runlog.TASK_SPAWN, "t", "implementer",
                                  self.RESOLVED)
        self.assertNotIn("total_tokens", rec)
        with self.assertRaises(runlog.RunLogError):
            runlog.validate_record({"event": "task_spawn", "task_id": "t",
                                    "role": "implementer",
                                    "total_tokens": -5})
