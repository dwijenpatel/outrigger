"""Tests for harness.governor — source ladder + observe-only thresholds (design §5.1)."""

import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import governor, runlog

NOW = dt.datetime(2026, 7, 4, 12, 0, tzinfo=dt.timezone.utc)

STATUSLINE = {
    "rate_limits": {
        "five_hour": {"used_percentage": 42.0, "resets_at": 1783600000},
        "seven_day": {"used_percentage": 61.5, "resets_at": 1783900000},
    },
    "context_window": {"current_usage": {"cache_read_tokens": 12345}},
}

OAUTH = {
    "five_hour": {"utilization": 88, "resets_at": 1783600000},
    "seven_day": {"utilization": 30},
    "seven_day_sonnet": {"utilization": 10},
}


def task(ts, tokens, tier=None):
    rec = {"profile": "routine", "total_tokens": tokens, "ts": ts}
    if tier:
        rec["tier"] = tier
    return rec


class StatuslineRungTests(unittest.TestCase):
    def test_parses_percentages_and_resets(self):
        occ = governor.read_statusline(STATUSLINE)
        self.assertEqual(occ.source, "statusline")
        self.assertAlmostEqual(occ.windows["five_hour"], 0.42)
        self.assertAlmostEqual(occ.windows["seven_day"], 0.615)
        self.assertEqual(occ.resets_at["five_hour"], 1783600000)
        self.assertFalse(occ.optimistic)

    def test_missing_rate_limits_raises(self):
        with self.assertRaises(governor.GovernorError):
            governor.read_statusline({"model": "x"})

    def test_empty_rate_limits_raises(self):
        with self.assertRaises(governor.GovernorError):
            governor.read_statusline({"rate_limits": {"five_hour": {}}})

    def test_negative_utilization_raises(self):
        with self.assertRaises(governor.GovernorError):
            governor.read_statusline(
                {"rate_limits": {"five_hour": {"used_percentage": -3}}})


class OauthRungTests(unittest.TestCase):
    def test_parses_flat_document(self):
        occ = governor.read_oauth_usage(OAUTH)
        self.assertEqual(occ.source, "oauth-usage")
        self.assertAlmostEqual(occ.windows["five_hour"], 0.88)
        self.assertAlmostEqual(occ.windows["seven_day_sonnet"], 0.10)

    def test_parses_nested_rate_limits_shape_too(self):
        occ = governor.read_oauth_usage({"rate_limits": OAUTH})
        self.assertAlmostEqual(occ.windows["five_hour"], 0.88)


class EstimateRungTests(unittest.TestCase):
    def test_trailing_windows_and_ceilings(self):
        records = [
            task("2026-07-04T11:00:00Z", 1000),          # inside 5h and 7d
            task("2026-07-04T02:00:00Z", 500),           # outside 5h, inside 7d
            task("2026-06-20T00:00:00Z", 999999),        # outside both
        ]
        occ = governor.estimate_from_runlog(
            records, NOW, ceilings={"five_hour": 10000, "seven_day": 15000})
        self.assertTrue(occ.optimistic)
        self.assertEqual(occ.tokens["five_hour"], 1000)
        self.assertEqual(occ.tokens["seven_day"], 1500)
        self.assertAlmostEqual(occ.windows["five_hour"], 0.1)
        self.assertAlmostEqual(occ.windows["seven_day"], 0.1)

    def test_no_ceilings_means_no_fractions(self):
        occ = governor.estimate_from_runlog([task("2026-07-04T11:00:00Z", 1000)], NOW)
        self.assertEqual(occ.windows, {})
        self.assertEqual(occ.tokens["five_hour"], 1000)

    def test_sonnet_window_counts_only_standard_tier(self):
        records = [task("2026-07-04T11:00:00Z", 1000, tier="standard"),
                   task("2026-07-04T11:00:00Z", 800, tier="cheap")]
        occ = governor.estimate_from_runlog(records, NOW)
        self.assertEqual(occ.tokens["seven_day_sonnet"], 1000)
        self.assertEqual(occ.tokens["seven_day"], 1800)

    def test_explicit_five_hour_anchor(self):
        records = [task("2026-07-04T05:00:00Z", 700)]  # 7h ago: outside trailing 5h
        anchor = dt.datetime(2026, 7, 4, 4, 0, tzinfo=dt.timezone.utc)
        occ = governor.estimate_from_runlog(records, NOW, five_hour_anchor=anchor)
        self.assertEqual(occ.tokens["five_hour"], 700)


class ResolveLadderTests(unittest.TestCase):
    def test_statusline_wins_over_others(self):
        occ = governor.resolve(statusline_doc=STATUSLINE, oauth_doc=OAUTH,
                               runlog_records=[], now=NOW)
        self.assertEqual(occ.source, "statusline")

    def test_bad_statusline_falls_through_to_oauth(self):
        occ = governor.resolve(statusline_doc={"broken": True}, oauth_doc=OAUTH)
        self.assertEqual(occ.source, "oauth-usage")

    def test_falls_through_to_estimate(self):
        occ = governor.resolve(statusline_doc={"broken": True},
                               runlog_records=[task("2026-07-04T11:00:00Z", 42)],
                               now=NOW)
        self.assertEqual(occ.source, "estimate")

    def test_no_sources_raises(self):
        with self.assertRaises(governor.GovernorError):
            governor.resolve()


class DecideTests(unittest.TestCase):
    def occ(self, **windows):
        return governor.Occupancy(source="test", windows=windows)

    def test_ok_below_degrade(self):
        d = governor.decide(self.occ(five_hour=0.5, seven_day=0.79))
        self.assertEqual(d["status"], "ok")
        self.assertFalse(d["enforced"])

    def test_degrade_at_threshold_binding_window_reported(self):
        d = governor.decide(self.occ(five_hour=0.80, seven_day=0.2))
        self.assertEqual(d["status"], "degrade")
        self.assertEqual(d["binding_window"], "five_hour")

    def test_pause_at_threshold(self):
        d = governor.decide(self.occ(seven_day=0.96))
        self.assertEqual(d["status"], "pause")

    def test_observe_mode_never_enforces(self):
        d = governor.decide(self.occ(five_hour=0.99), mode="observe")
        self.assertEqual(d["status"], "pause")
        self.assertFalse(d["enforced"])

    def test_enforce_mode_enforces_only_crossings(self):
        self.assertTrue(governor.decide(self.occ(five_hour=0.85),
                                        mode="enforce")["enforced"])
        self.assertFalse(governor.decide(self.occ(five_hour=0.1),
                                         mode="enforce")["enforced"])

    def test_unknown_when_no_fractions(self):
        d = governor.decide(governor.Occupancy(source="estimate", windows={},
                                               optimistic=True))
        self.assertEqual(d["status"], "unknown")
        self.assertIsNone(d["binding_window"])

    def test_bad_thresholds_rejected(self):
        with self.assertRaises(governor.GovernorError):
            governor.decide(self.occ(five_hour=0.1), degrade=0.9, pause=0.8)
        with self.assertRaises(governor.GovernorError):
            governor.decide(self.occ(five_hour=0.1), mode="yolo")


class LoggingAndCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_log_decision_lands_in_runlog(self):
        path = os.path.join(self.dir.name, "log.jsonl")
        decision = governor.decide(
            governor.Occupancy(source="test", windows={"five_hour": 0.85}))
        governor.log_decision(path, decision)
        records, errors = runlog.RunLog(path).read()
        self.assertEqual(errors, [])
        self.assertEqual(records[0]["event"], governor.GOVERNOR_EVENT)
        self.assertEqual(records[0]["status"], "degrade")

    def test_cli_statusline_inline_json(self):
        log_path = os.path.join(self.dir.name, "log.jsonl")
        out = io.StringIO()
        with redirect_stdout(out):
            code = governor._cli(["--statusline-json", json.dumps(STATUSLINE),
                                  "--log", log_path])
        self.assertEqual(code, 0)
        decision = json.loads(out.getvalue())
        self.assertEqual(decision["status"], "ok")
        records, _ = runlog.RunLog(log_path).read()
        self.assertEqual(len(records), 1)

    def test_cli_exit_code_signals_crossing(self):
        hot = {"rate_limits": {"five_hour": {"used_percentage": 97}}}
        out = io.StringIO()
        with redirect_stdout(out):
            code = governor._cli(["--statusline-json", json.dumps(hot)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "pause")


if __name__ == "__main__":
    unittest.main()
