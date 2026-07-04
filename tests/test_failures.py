"""Tests for harness.failures + governor sticky-estimate rollup (A5, design §5.1)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import failures, governor


class ClassifyTests(unittest.TestCase):
    def test_credit_exhaustion_is_permanent(self):
        got = failures.classify("API Error: Your credit balance is too low")
        self.assertEqual(got["class"], "permanent")

    def test_auth_errors_are_permanent(self):
        for text in ("authentication_error: invalid x-api-key",
                     "401 Unauthorized",
                     "Expired OAuth token supplied credentials"):
            self.assertEqual(failures.classify(text)["class"], "permanent", text)

    def test_rate_limit_and_overload_are_retryable(self):
        for text in ("429 Too Many Requests", "server overloaded", "rate_limit_error"):
            self.assertEqual(failures.classify(text)["class"], "retryable", text)

    def test_network_trouble_is_retryable(self):
        for text in ("connection reset by peer", "request timed out", "502 Bad Gateway"):
            self.assertEqual(failures.classify(text)["class"], "retryable", text)

    def test_unknown_defaults_to_retryable_with_honest_why(self):
        got = failures.classify("something entirely novel exploded")
        self.assertEqual(got["class"], "retryable")
        self.assertIsNone(got["matched"])

    def test_config_patterns_consulted_before_defaults(self):
        extra = failures.load_patterns(
            [{"pattern": r"rate.?limit", "class": "permanent",
              "why": "operator wants rate limits fatal"}])
        got = failures.classify("rate limit reached", extra_patterns=extra)
        self.assertEqual(got["class"], "permanent")

    def test_bad_config_is_loud(self):
        for doc in ([{"pattern": "x", "class": "fatal"}],
                    [{"pattern": "(", "class": "permanent"}],
                    [{"pattern": "", "class": "permanent"}],
                    {"pattern": "x"}):
            with self.assertRaises(failures.FailureConfigError):
                failures.load_patterns(doc)


class NextActionTests(unittest.TestCase):
    def test_permanent_aborts_immediately(self):
        got = failures.next_action({"class": "permanent", "why": "auth"}, attempt=1)
        self.assertEqual(got["action"], "abort")

    def test_retryable_backs_off_exponentially_with_cap(self):
        cls = {"class": "retryable", "why": "429"}
        delays = [failures.next_action(cls, attempt=n, base_delay_secs=30,
                                       max_delay_secs=200)["delay_secs"]
                  for n in (1, 2, 3, 4)]
        self.assertEqual(delays, [30, 60, 120, 200])  # capped at max

    def test_retryable_gives_up_at_attempt_cap(self):
        cls = {"class": "retryable", "why": "429"}
        got = failures.next_action(cls, attempt=5, max_attempts=5)
        self.assertEqual(got["action"], "abort")

    def test_bad_attempt_rejected(self):
        with self.assertRaises(failures.FailureConfigError):
            failures.next_action({"class": "retryable", "why": ""}, attempt=0)


class StickyEstimateTests(unittest.TestCase):
    def decision(self, source, optimistic, windows, status="ok"):
        return {"event": "governor_decision", "source": source,
                "optimistic": optimistic, "windows": windows, "status": status}

    def test_all_measured_is_not_estimated(self):
        rollup = governor.summarize_decisions([
            self.decision("statusline", False, {"five_hour": 0.4}),
            self.decision("statusline", False, {"five_hour": 0.5}),
        ])
        self.assertFalse(rollup["estimated"])
        self.assertEqual(rollup["worst_windows"], {"five_hour": 0.5})

    def test_one_estimate_reading_makes_the_rollup_sticky(self):
        rollup = governor.summarize_decisions([
            self.decision("statusline", False, {"five_hour": 0.4}),
            self.decision("estimate", True, {"five_hour": 0.6}),
            self.decision("statusline", False, {"five_hour": 0.5}),
        ])
        self.assertTrue(rollup["estimated"])  # sticky: one ~ poisons the total
        self.assertEqual(rollup["worst_windows"], {"five_hour": 0.6})
        self.assertIn("estimate", rollup["sources"])

    def test_status_flags_roll_up(self):
        rollup = governor.summarize_decisions([
            self.decision("statusline", False, {"five_hour": 0.85}, status="degrade"),
            self.decision("estimate", True, {}, status="unknown"),
        ])
        self.assertTrue(rollup["any_degrade"])
        self.assertTrue(rollup["any_unknown"])
        self.assertFalse(rollup["any_pause"])

    def test_non_governor_records_ignored(self):
        rollup = governor.summarize_decisions([
            {"event": "task_complete", "optimistic": True},
            self.decision("statusline", False, {"five_hour": 0.2}),
        ])
        self.assertEqual(rollup["readings"], 1)
        self.assertFalse(rollup["estimated"])

    def test_fmt_estimated(self):
        self.assertEqual(governor.fmt_estimated(1234, True), "~1234")
        self.assertEqual(governor.fmt_estimated(1234, False), "1234")
        self.assertEqual(governor.fmt_estimated(12.0, True), "~12")


if __name__ == "__main__":
    unittest.main()
