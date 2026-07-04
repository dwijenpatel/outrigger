"""Tests for harness.liveness (B3) — multi-signal park, observe-only."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import liveness
from harness.liveness import Vitals


def productive_step(v, tokens=1000):
    v.record_step(tokens=tokens, git_delta_bytes=500, artifacts_written=1)


class SignatureTests(unittest.TestCase):
    def test_incidental_detail_collapses(self):
        a = liveness.error_signature("AssertionError at /tmp/x1/test_gate.py line 42")
        b = liveness.error_signature("AssertionError at /tmp/x9/test_gate.py line 57")
        self.assertEqual(a, b)

    def test_different_errors_differ(self):
        a = liveness.error_signature("ImportError: no module named foo")
        b = liveness.error_signature("AssertionError: expected 3 got 4")
        self.assertNotEqual(a, b)


class AssessTests(unittest.TestCase):
    def test_healthy_task_continues(self):
        v = Vitals()
        for _ in range(3):
            productive_step(v)
        out = liveness.assess(v, step_cap=10)
        self.assertEqual(out["recommendation"], "continue")
        self.assertEqual(out["signals"], [])

    def test_step_cap_fires(self):
        v = Vitals()
        for _ in range(4):
            productive_step(v)
        out = liveness.assess(v, step_cap=3)
        self.assertEqual(out["signals"][0]["signal"], "step_cap")
        self.assertEqual(out["recommendation"], "park")

    def test_token_cap_fires_mid_flight(self):
        v = Vitals()
        productive_step(v, tokens=250_000)
        cap = liveness.token_cap_from_forecast(100_000)  # 200k at 2.0x
        out = liveness.assess(v, step_cap=100, token_cap=cap)
        self.assertEqual(out["signals"][0]["signal"], "token_cap")

    def test_none_forecast_means_no_token_cap(self):
        self.assertIsNone(liveness.token_cap_from_forecast(None))
        v = Vitals()
        productive_step(v, tokens=10_000_000)
        out = liveness.assess(v, step_cap=100, token_cap=None)
        self.assertEqual(out["recommendation"], "continue")

    def test_repeated_error_signature_fires(self):
        v = Vitals()
        for i in range(3):
            v.record_step(tokens=100, error=f"tests failed at line {i}",
                          git_delta_bytes=10)
        out = liveness.assess(v, step_cap=100)
        self.assertEqual(out["signals"][0]["signal"], "repeated_error")

    def test_different_errors_do_not_fire(self):
        v = Vitals()
        v.record_step(tokens=1, error="ImportError: foo", git_delta_bytes=1)
        v.record_step(tokens=1, error="AssertionError: bar", git_delta_bytes=1)
        v.record_step(tokens=1, error="TypeError: baz", git_delta_bytes=1)
        out = liveness.assess(v, step_cap=100)
        self.assertEqual(out["recommendation"], "continue")

    def test_success_resets_error_streak(self):
        v = Vitals()
        v.record_step(tokens=1, error="tests failed", git_delta_bytes=1)
        v.record_step(tokens=1, error="tests failed", git_delta_bytes=1)
        productive_step(v)  # no error
        v.record_step(tokens=1, error="tests failed", git_delta_bytes=1)
        out = liveness.assess(v, step_cap=100)
        self.assertEqual(out["recommendation"], "continue")

    def test_noop_streak_fires_and_resets(self):
        v = Vitals()
        v.record_step(tokens=100)  # zero delta, zero artifacts
        v.record_step(tokens=100)
        out = liveness.assess(v, step_cap=100)
        self.assertEqual(out["signals"][0]["signal"], "no_op")
        productive_step(v)
        out2 = liveness.assess(v, step_cap=100)
        self.assertEqual(out2["recommendation"], "continue")

    def test_slow_grind_fires(self):
        v = Vitals()
        v.record_step(tokens=1, wall_secs=5000, git_delta_bytes=1)
        out = liveness.assess(v, step_cap=100, wall_cap_secs=3600)
        self.assertEqual(out["signals"][0]["signal"], "slow_grind")

    def test_multi_signal_lists_everything(self):
        v = Vitals()
        for _ in range(5):
            v.record_step(tokens=100_000, error="same failure")
        out = liveness.assess(v, step_cap=3, token_cap=200_000)
        kinds = {s["signal"] for s in out["signals"]}
        self.assertEqual(kinds, {"step_cap", "token_cap", "repeated_error", "no_op"})

    def test_observe_only_never_enforces(self):
        v = Vitals()
        for _ in range(5):
            v.record_step(tokens=100)
        observe = liveness.assess(v, step_cap=1)
        enforce = liveness.assess(v, step_cap=1, mode="enforce")
        self.assertEqual(observe["recommendation"], "park")
        self.assertFalse(observe["enforced"])
        self.assertTrue(enforce["enforced"])

    def test_bad_inputs_loud(self):
        with self.assertRaises(liveness.LivenessError):
            liveness.assess(Vitals(), step_cap=0)
        with self.assertRaises(liveness.LivenessError):
            liveness.token_cap_from_forecast(100, multiplier=1.0)
        with self.assertRaises(liveness.LivenessError):
            Vitals().record_step(tokens=-1)


if __name__ == "__main__":
    unittest.main()
