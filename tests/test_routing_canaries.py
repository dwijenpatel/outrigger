"""Tests for harness.routing_canaries (E4)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import routing_canaries as rc
from harness.routing_canaries import RoutingError


FIXTURES = [
    {"id": "a", "prompt": "start a firing", "expected_skills": ["build-loop"]},
    {"id": "b", "prompt": "start and review", "expected_skills": ["build-loop",
                                                                  "review"]},
    {"id": "neg", "prompt": "what time is it", "expected_skills": []},
]


class FixtureValidationTests(unittest.TestCase):
    def test_committed_fixtures_are_valid_with_negatives(self):
        fixtures = rc.load_fixtures()
        self.assertTrue(any(not f["expected_skills"] for f in fixtures))

    def test_no_negative_controls_rejected(self):
        with self.assertRaises(RoutingError):
            rc.validate_fixtures([{"id": "x", "prompt": "p",
                                   "expected_skills": ["s"]}])

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(RoutingError):
            rc.validate_fixtures([
                {"id": "x", "prompt": "p", "expected_skills": []},
                {"id": "x", "prompt": "q", "expected_skills": ["s"]}])


class ScoringTests(unittest.TestCase):
    def test_exact_match_passes(self):
        got = rc.score_fixture(["build-loop"], ["build-loop"])
        self.assertTrue(got["pass"])
        self.assertEqual((got["precision"], got["recall"]), (1.0, 1.0))

    def test_under_invocation_hits_recall(self):
        got = rc.score_fixture(["build-loop", "review"], ["build-loop"])
        self.assertFalse(got["pass"])
        self.assertEqual(got["recall"], 0.5)
        self.assertEqual(got["precision"], 1.0)
        self.assertEqual(got["missing"], ["review"])

    def test_over_invocation_hits_precision(self):
        got = rc.score_fixture([], ["build-loop"])
        self.assertFalse(got["pass"])
        self.assertEqual(got["precision"], 0.0)

    def test_negative_control_clean_pass(self):
        got = rc.score_fixture([], [])
        self.assertTrue(got["pass"])
        self.assertEqual((got["precision"], got["recall"]), (1.0, 1.0))

    def test_run_scoring_aggregates_and_reports_holes(self):
        run = rc.score_run(FIXTURES, {"a": ["build-loop"],
                                      "neg": ["build-loop"]})
        self.assertEqual(run["coverage_holes"], ["b"])  # never silently skipped
        self.assertEqual(run["negative_control_violations"], 1)
        self.assertEqual(run["scored"], 2)
        self.assertAlmostEqual(run["perfect_match_rate"], 0.5)


class FingerprintTests(unittest.TestCase):
    FPS = {"build-loop": ["phase-gated: run them at the stated point"],
           "review": ["adversarially verify each finding first"]}

    def test_body_phrase_proves_loading(self):
        transcript = "...phase-gated: run them at the stated point, every..."
        got = rc.fingerprint_hits(transcript, self.FPS)
        self.assertTrue(got["build-loop"])
        self.assertFalse(got["review"])

    def test_short_fingerprints_rejected(self):
        with self.assertRaises(RoutingError):
            rc.fingerprint_hits("text", {"s": ["short"]})


if __name__ == "__main__":
    unittest.main()
