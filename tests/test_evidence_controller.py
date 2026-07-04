"""Tests for harness.evidence (F1) and harness.controller (F2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import controller, evidence
from harness.controller import ControllerError


def rec(role="implementer", tier="cheap", effort="low", profile="routine",
        tokens=1000, outcome="pass"):
    return {"event": "task_complete", "role": role, "tier": tier,
            "effort": effort, "profile": profile, "total_tokens": tokens,
            "outcome": outcome}


TRIALS_OK = [{"canary_id": f"c{i}", "caught": True,
              "ts": f"2026-07-04T0{i}:00:00Z"} for i in range(3)]


class RollupTests(unittest.TestCase):
    def test_cells_aggregate(self):
        roll = evidence.rollup([rec(), rec(tokens=2000, outcome="fail"),
                                rec(tier="capable", profile="critical")])
        cheap = roll["cells"][("implementer", "cheap", "low", "routine")]
        self.assertEqual(cheap["tasks"], 2)
        self.assertEqual(cheap["tokens"], 3000)
        self.assertEqual(cheap["fails"], 1)
        self.assertEqual(roll["totals"]["tasks"], 3)

    def test_non_task_events_ignored(self):
        roll = evidence.rollup([{"event": "governor_decision"}])
        self.assertEqual(roll["totals"]["tasks"], 0)

    def test_catch_rate_never_fabricated(self):
        self.assertIsNone(evidence.catch_rate([], 0)["rate"])
        got = evidence.catch_rate([{"d": 1}], 10)
        self.assertAlmostEqual(got["rate"], 0.1)


class EvidenceMdTests(unittest.TestCase):
    def gen(self, **kw):
        defaults = dict(
            runlog_records=[rec(), rec(tier="capable", profile="critical")],
            escapes=[], canary_trials=TRIALS_OK,
            governor_decisions=[{"event": "governor_decision",
                                 "source": "statusline", "optimistic": False,
                                 "windows": {"five_hour": 0.4},
                                 "status": "ok"}],
            merged_tasks=2)
        defaults.update(kw)
        return evidence.generate_evidence_md(**defaults)

    def test_aggregate_header_first(self):
        text = self.gen()
        self.assertTrue(text.splitlines()[0].startswith("evidence: 2 worker"))
        self.assertIn("canaries 3/3 caught", text.splitlines()[0])

    def test_definitive_empties(self):
        text = self.gen(runlog_records=[], merged_tasks=0)
        self.assertIn("worker runs: 0 recorded", text)
        self.assertIn("escapes: 0 recorded", text)
        self.assertIn("n/a (0 merged tasks", text)

    def test_sticky_estimate_marks_totals(self):
        text = self.gen(governor_decisions=[
            {"event": "governor_decision", "source": "estimate",
             "optimistic": True, "windows": {}, "status": "unknown"}])
        self.assertIn("~", text.splitlines()[0])
        self.assertIn("totals estimated (~)", text)

    def test_unmeasured_kill_rate_treated_weak(self):
        self.assertIn("treated as weak", self.gen())
        strong = self.gen(kill_trials=[{"killed": True}] * 9 +
                          [{"killed": False}])
        self.assertIn("kill-rate: 90%", strong)

    def test_escapes_table_when_present(self):
        text = self.gen(escapes=[{"description": "tenant leak", "task_id": "t3",
                                  "severity": "critical",
                                  "discovered_by": "operator"}])
        self.assertIn("| tenant leak | t3 | critical | operator |", text)


class ControllerTests(unittest.TestCase):
    def proposal(self, **kw):
        defaults = dict(lever="validator_count", direction="downgrade",
                        profile="routine", change="3 -> 2 lenses on routine",
                        cell_samples=214, cost_benefit="est. -9% weekly tokens",
                        pending_unresolved_proposals=0,
                        canary_trials=TRIALS_OK, escapes=[])
        defaults.update(kw)
        return controller.propose(**defaults)

    def test_clean_downgrade_proposes_a_card_with_arm_plan(self):
        got = self.proposal()
        self.assertTrue(got["proposed"])
        card = got["card"]
        self.assertEqual(card["card_id"], "lever-validator_count-routine-downgrade")
        self.assertEqual(card["evaluation_plan"]["design"], "paired-arm")
        self.assertIn("terciles", card["evaluation_plan"]["strata"])
        # and it renders as a real E3 card
        from harness import ratification
        self.assertIn("<!-- opt:approve -->", ratification.render_card(card))

    def test_one_lever_at_a_time(self):
        got = self.proposal(pending_unresolved_proposals=1)
        self.assertFalse(got["proposed"])
        self.assertIn("one lever at a time", got["why"])

    def test_sample_floor(self):
        got = self.proposal(cell_samples=5)
        self.assertFalse(got["proposed"])
        self.assertIn("thin cell", got["why"])

    def test_protected_profiles_strengthen_only(self):
        for profile in ("high", "critical"):
            got = self.proposal(profile=profile)
            self.assertFalse(got["proposed"], profile)
            self.assertIn("strengthen-only", got["why"])
        # strengthening a protected profile is fine
        got = self.proposal(profile="critical", direction="strengthen",
                            change="add a fourth lens")
        self.assertTrue(got["proposed"])

    def test_downgrade_without_canary_proof_refused(self):
        got = self.proposal(canary_trials=TRIALS_OK[:1])
        self.assertFalse(got["proposed"])
        self.assertIn("calibration proof", got["why"])
        missed = TRIALS_OK[:2] + [{"canary_id": "cx", "caught": False,
                                   "ts": "2026-07-04T09:00:00Z"}]
        got = self.proposal(canary_trials=missed)
        self.assertFalse(got["proposed"])

    def test_bad_inputs_loud(self):
        with self.assertRaises(ControllerError):
            self.proposal(lever="magic")
        with self.assertRaises(ControllerError):
            self.proposal(cost_benefit="")


if __name__ == "__main__":
    unittest.main()
