"""Tests for harness.admission — quantile-forecast admission rule (design §5.1/§6.2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import admission

ESTIMATES = {
    "_meta": {"min_samples_per_profile": 8},
    "cost_estimate_by_profile": {
        "routine": {"p50": 40000, "p90": 70000, "p95": 80000, "sample_size": 12},
        "elevated": {"p50": 90000, "p90": 150000, "p95": 160000, "sample_size": 3},
        "high": {"p50": None, "p90": None, "p95": None, "sample_size": 0},
    },
}


class ForecastTests(unittest.TestCase):
    def test_well_sampled_profile_uses_raw_p95(self):
        fc = admission.forecast_tokens("routine", ESTIMATES)
        self.assertEqual(fc["tokens"], 80000)
        self.assertFalse(fc["low_confidence"])

    def test_below_floor_sample_widens(self):
        fc = admission.forecast_tokens("elevated", ESTIMATES)
        self.assertTrue(fc["low_confidence"])
        self.assertEqual(fc["tokens"], 160000 * 1.5)

    def test_null_estimate_stays_none_never_fabricated(self):
        fc = admission.forecast_tokens("high", ESTIMATES)
        self.assertIsNone(fc["tokens"])
        self.assertTrue(fc["low_confidence"])

    def test_unknown_profile_raises(self):
        with self.assertRaises(admission.AdmissionError):
            admission.forecast_tokens("mega", ESTIMATES)

    def test_shipped_estimates_file_loads_and_is_unpopulated_safe(self):
        """The real (still-null) estimates file must flow through without invented
        numbers: forecast None, low confidence."""
        doc = admission.load_estimates()
        for profile in doc["cost_estimate_by_profile"]:
            fc = admission.forecast_tokens(profile, doc)
            if fc["sample_size"] == 0:
                self.assertIsNone(fc["tokens"])


class AdmitTests(unittest.TestCase):
    def fc(self, tokens, low=False):
        return {"tokens": tokens, "sample_size": 12, "low_confidence": low,
                "quantile": "p95"}

    def test_exact_rule_admits_when_projection_below_degrade(self):
        d = admission.admit(0.30, self.fc(80000), window_ceiling_tokens=1_000_000)
        self.assertTrue(d["admit"])
        self.assertAlmostEqual(d["projected_occupancy"], 0.38)

    def test_exact_rule_defers_when_projection_crosses(self):
        d = admission.admit(0.75, self.fc(80000), window_ceiling_tokens=1_000_000)
        self.assertFalse(d["admit"])
        self.assertAlmostEqual(d["projected_occupancy"], 0.83)

    def test_heavy_task_admitted_early_in_fresh_window(self):
        """Design §5.1: a heavy critical task is admitted in a fresh window..."""
        d = admission.admit(0.05, self.fc(400000), window_ceiling_tokens=1_000_000)
        self.assertTrue(d["admit"])

    def test_same_heavy_task_deferred_near_wall(self):
        """...and near a wall it is not."""
        d = admission.admit(0.60, self.fc(400000), window_ceiling_tokens=1_000_000)
        self.assertFalse(d["admit"])

    def test_at_or_over_degrade_always_defers(self):
        d = admission.admit(0.80, self.fc(1), window_ceiling_tokens=10**9)
        self.assertFalse(d["admit"])

    def test_unknown_occupancy_never_admits(self):
        d = admission.admit(None, self.fc(1000), window_ceiling_tokens=10**9)
        self.assertFalse(d["admit"])

    def test_no_ceiling_falls_back_to_margin(self):
        self.assertTrue(admission.admit(0.50, self.fc(80000))["admit"])   # < 0.65
        self.assertFalse(admission.admit(0.70, self.fc(80000))["admit"])  # >= 0.65

    def test_no_estimate_falls_back_to_margin(self):
        self.assertTrue(admission.admit(0.10, self.fc(None))["admit"])
        d = admission.admit(0.66, self.fc(None))
        self.assertFalse(d["admit"])
        self.assertIn("no cost estimate", d["reason"])

    def test_bad_params_rejected(self):
        with self.assertRaises(admission.AdmissionError):
            admission.admit(0.1, self.fc(1), degrade=0)
        with self.assertRaises(admission.AdmissionError):
            admission.admit(0.1, self.fc(1), unknown_cost_margin=-0.1)


class AdmitTaskTests(unittest.TestCase):
    def test_end_to_end_with_populated_table(self):
        d = admission.admit_task("routine", occupancy=0.2, estimates_doc=ESTIMATES,
                                 window_ceiling_tokens=1_000_000)
        self.assertTrue(d["admit"])
        self.assertEqual(d["forecast"]["tokens"], 80000)

    def test_end_to_end_with_shipped_unpopulated_table_is_conservative(self):
        """With the repo's real (null) estimates: mid-window admits under the margin
        rule, high occupancy defers — but nothing crashes and nothing is invented."""
        low = admission.admit_task("critical", occupancy=0.10)
        high = admission.admit_task("critical", occupancy=0.70)
        self.assertTrue(low["admit"])
        self.assertFalse(high["admit"])
        self.assertIsNone(low["forecast"]["tokens"])


if __name__ == "__main__":
    unittest.main()
