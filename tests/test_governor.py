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


class StalenessAndPreflightTests(unittest.TestCase):
    """H8 — readings carry age; stale rungs fall through; preflight gates
    firing starts."""

    def statusline(self, pct=40):
        return {"rate_limits": {"five_hour": {"used_percentage": pct}}}

    def oauth(self, pct=50):
        return {"five_hour": {"utilization": pct}}

    def test_fresh_reading_carries_age(self):
        occ = governor.resolve(statusline_doc=self.statusline(),
                               statusline_read_at=1000.0, now_ts=1100.0)
        self.assertEqual(occ.source, "statusline")
        self.assertAlmostEqual(occ.age_s, 100.0)

    def test_stale_statusline_falls_through_to_oauth(self):
        occ = governor.resolve(statusline_doc=self.statusline(),
                               statusline_read_at=0.0,
                               oauth_doc=self.oauth(),
                               oauth_read_at=900.0, now_ts=1000.0,
                               stale_after_s=600)
        self.assertEqual(occ.source, "oauth-usage")

    def test_all_live_rungs_stale_falls_to_estimate(self):
        occ = governor.resolve(statusline_doc=self.statusline(),
                               statusline_read_at=0.0,
                               runlog_records=[], now_ts=100_000.0,
                               stale_after_s=600)
        self.assertEqual(occ.source, "estimate")
        self.assertTrue(occ.optimistic)

    def test_stale_only_rung_raises(self):
        with self.assertRaises(governor.GovernorError) as ctx:
            governor.resolve(statusline_doc=self.statusline(),
                             statusline_read_at=0.0, now_ts=100_000.0)
        self.assertIn("staleness ceiling", str(ctx.exception))

    def test_future_timestamp_is_a_rung_failure(self):
        with self.assertRaises(governor.GovernorError) as ctx:
            governor.resolve(statusline_doc=self.statusline(),
                             statusline_read_at=2000.0, now_ts=1000.0)
        self.assertIn("future", str(ctx.exception))

    def test_age_unknown_without_timestamps_behaves_as_before(self):
        occ = governor.resolve(statusline_doc=self.statusline())
        self.assertIsNone(occ.age_s)
        decision = governor.decide(occ)
        self.assertEqual(decision["effective_thresholds"]["degrade"], 0.8)

    def test_age_widens_the_margin(self):
        # 0.78 occupancy: ok on fresh data, degrade on a 300s-old reading
        occ = governor.resolve(statusline_doc=self.statusline(78),
                               statusline_read_at=700.0, now_ts=1000.0,
                               stale_after_s=600)
        decision = governor.decide(occ)
        self.assertAlmostEqual(
            decision["effective_thresholds"]["degrade"], 0.75)
        self.assertEqual(decision["status"], "degrade")
        self.assertAlmostEqual(decision["reading_age_s"], 300.0)
        fresh = governor.decide(governor.resolve(
            statusline_doc=self.statusline(78)))
        self.assertEqual(fresh["status"], "ok")

    def test_preflight_normal_with_live_rung(self):
        got = governor.preflight(statusline_doc=self.statusline(),
                                 statusline_read_at=950.0, now_ts=1000.0)
        self.assertEqual(got["mode"], "normal")
        self.assertEqual(got["restrictions"], [])
        self.assertIn("statusline", got["why"])

    def test_preflight_conservative_without_live_rung(self):
        got = governor.preflight()
        self.assertEqual(got["mode"], "conservative")
        self.assertAlmostEqual(got["thresholds"]["degrade"], 0.65)
        self.assertIn("cheap-serial only", got["restrictions"])
        self.assertIn("never clears a preflight", got["why"])

    def test_preflight_conservative_on_stale_only_data(self):
        got = governor.preflight(statusline_doc=self.statusline(),
                                 statusline_read_at=0.0, now_ts=100_000.0)
        self.assertEqual(got["mode"], "conservative")
        self.assertIn("staleness ceiling", got["why"])

    def test_preflight_cli_exit_codes(self):
        import subprocess
        conservative = subprocess.run(
            [sys.executable, "-m", "harness.governor", "--preflight"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(conservative.returncode, 3)
        self.assertIn("conservative", conservative.stdout)


class BootstrapAndSourceRobustnessTests(unittest.TestCase):
    """P2-2/P2-4 — missing sources degrade; bootstrap is explicit + attributed."""

    def test_missing_source_file_is_a_skipped_rung_not_a_crash(self):
        import subprocess
        got = subprocess.run(
            [sys.executable, "-m", "harness.governor", "--preflight",
             "--statusline-json", "/nonexistent/dump.json"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(got.returncode, 3)  # conservative, not a traceback
        self.assertNotIn("Traceback", got.stderr)
        self.assertIn("rung skipped", got.stderr)

    def test_assumed_occupancy_requires_attribution_and_bounds(self):
        with self.assertRaises(governor.GovernorError):
            governor.assumed_occupancy(0.3, "")
        for bad in (-0.1, 1.0, 1.5, True):
            with self.assertRaises(governor.GovernorError):
                governor.assumed_occupancy(bad, "dwijen")

    def test_assumed_occupancy_is_attributed_and_optimistic(self):
        occ = governor.assumed_occupancy(0.3, "dwijen")
        self.assertEqual(occ.source, "operator-assumed:dwijen")
        self.assertTrue(occ.optimistic)
        decision = governor.decide(occ)
        self.assertEqual(decision["status"], "ok")
        self.assertTrue(decision["optimistic"])  # sticky-~ downstream

    def test_cli_bootstrap_breaks_the_p2_4_deadlock(self):
        import subprocess
        # no sources at all + assumption → a usable, attributed decision
        got = subprocess.run(
            [sys.executable, "-m", "harness.governor",
             "--assume-occupancy", "0.3", "--acked-by", "dwijen"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("operator-assumed:dwijen", got.stdout)
        # ...but only with attribution
        refused = subprocess.run(
            [sys.executable, "-m", "harness.governor",
             "--assume-occupancy", "0.3"],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(refused.returncode, 0)

    def test_real_source_beats_the_assumption(self):
        import subprocess
        got = subprocess.run(
            [sys.executable, "-m", "harness.governor",
             "--statusline-json",
             '{"rate_limits": {"five_hour": {"used_percentage": 90}}}',
             "--assume-occupancy", "0.1", "--acked-by", "dwijen"],
            capture_output=True, text=True, timeout=30)
        self.assertIn('"statusline"', got.stdout)
        self.assertIn("degrade", got.stdout)
