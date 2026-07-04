"""Tests for harness.spawncheck — the §5.3 (model, effort) allowlist gate."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import spawncheck

TIERS_DOC = {
    "tiers": {"cheap": "model-c", "standard": "model-s",
              "capable": "model-p", "max": "model-m"},
    "efforts": ["low", "medium", "high", "xhigh", "max"],
    "extra_allowed_models": ["model-legacy"],
}

PROFILES = {
    "routine": {"starting_tier": "cheap", "validator_count": 1,
                "lenses": ["correctness"], "effort": "low"},
    "critical": {"starting_tier": "max", "validator_count": 4,
                 "lenses": ["correctness", "repro", "security", "perf"],
                 "effort": "high"},
}


class LoadTiersTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_covers_all_tiers(self):
        doc = spawncheck.load_tiers()
        for name in spawncheck.TIER_NAMES:
            self.assertTrue(doc["tiers"][name])
        self.assertIn("low", doc["efforts"])

    def test_missing_tier_rejected(self):
        broken = {"tiers": {"cheap": "x"}, "efforts": ["low"]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(broken, fh)
            path = fh.name
        try:
            with self.assertRaises(spawncheck.SpawnValidationError):
                spawncheck.load_tiers(path)
        finally:
            os.unlink(path)


class ValidateSpawnTests(unittest.TestCase):
    def test_tier_resolves_to_model(self):
        out = spawncheck.validate_spawn(tier="cheap", effort="low", tiers_doc=TIERS_DOC)
        self.assertEqual(out, {"model": "model-c", "effort": "low", "tier": "cheap"})

    def test_model_reverse_resolves_tier(self):
        out = spawncheck.validate_spawn(model="model-m", tiers_doc=TIERS_DOC)
        self.assertEqual(out["tier"], "max")
        self.assertIsNone(out["effort"])

    def test_extra_allowed_model_passes_with_no_tier(self):
        out = spawncheck.validate_spawn(model="model-legacy", tiers_doc=TIERS_DOC)
        self.assertIsNone(out["tier"])

    def test_unknown_model_rejected(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.validate_spawn(model="claude-typo-9", tiers_doc=TIERS_DOC)

    def test_unknown_tier_rejected(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.validate_spawn(tier="platinum", tiers_doc=TIERS_DOC)

    def test_invalid_effort_rejected_even_though_primitive_accepts_it(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.validate_spawn(tier="cheap", effort="turbo", tiers_doc=TIERS_DOC)

    def test_conflicting_model_and_tier_rejected(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.validate_spawn(model="model-s", tier="cheap", tiers_doc=TIERS_DOC)

    def test_consistent_model_and_tier_accepted(self):
        out = spawncheck.validate_spawn(model="model-c", tier="cheap",
                                        tiers_doc=TIERS_DOC)
        self.assertEqual(out["model"], "model-c")

    def test_neither_model_nor_tier_rejected(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.validate_spawn(effort="low", tiers_doc=TIERS_DOC)

    def test_none_effort_allowed(self):
        out = spawncheck.validate_spawn(tier="standard", tiers_doc=TIERS_DOC)
        self.assertIsNone(out["effort"])


class RequireResultTests(unittest.TestCase):
    def test_null_result_raises(self):
        with self.assertRaises(spawncheck.NullSpawnResult):
            spawncheck.require_result(None, context="validator panel lens=repro")

    def test_real_results_pass_through(self):
        for value in ("text", {"verdict": "PASS"}, [], 0, False):
            self.assertEqual(spawncheck.require_result(value), value)


class ProfileSpawnParamsTests(unittest.TestCase):
    def test_profile_resolves_fully(self):
        out = spawncheck.profile_spawn_params("critical", tiers_doc=TIERS_DOC,
                                              profiles=PROFILES)
        self.assertEqual(out["model"], "model-m")
        self.assertEqual(out["effort"], "high")
        self.assertEqual(out["validator_count"], 4)
        self.assertEqual(len(out["lenses"]), 4)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.profile_spawn_params("mega", tiers_doc=TIERS_DOC,
                                            profiles=PROFILES)

    def test_bad_validator_count_rejected(self):
        broken = {"p": {"starting_tier": "cheap", "validator_count": 0,
                        "lenses": ["x"], "effort": "low"}}
        with self.assertRaises(spawncheck.SpawnValidationError):
            spawncheck.profile_spawn_params("p", tiers_doc=TIERS_DOC, profiles=broken)

    def test_shipped_estimates_file_profiles_all_resolve(self):
        """Every profile in the real profile-tier-estimates.json must produce a fully
        validated spawn tuple against the real tiers.json — config drift breaks here."""
        profiles = spawncheck.load_risk_profiles()
        for name in profiles:
            out = spawncheck.profile_spawn_params(name)
            self.assertTrue(out["model"])
            self.assertIn(out["effort"], spawncheck.load_tiers()["efforts"])


if __name__ == "__main__":
    unittest.main()
