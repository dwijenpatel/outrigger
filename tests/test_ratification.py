"""Tests for harness.ratification (E3) — decision cards + stale guard."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ratification as rat
from harness.ratification import RatificationError


def card(**patch):
    doc = {"card_id": "panel-shrink-routine",
           "situation": "214 routine tasks, 0 escapes, canaries 100% caught.",
           "recommendation": "Shrink routine panel 3 -> 2 lenses (est. -9%/wk).",
           "options": [{"key": "approve", "label": "Approve the shrink"},
                       {"key": "decline", "label": "Keep 3 lenses"},
                       {"key": "defer", "label": "Ask again after 100 tasks"}]}
    doc.update(patch)
    return doc


class RenderParseTests(unittest.TestCase):
    def test_roundtrip(self):
        text = rat.render_card(card(), triage="Numbers check out.")
        parsed = rat.parse_cards(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["card_id"], "panel-shrink-routine")
        self.assertEqual([o["key"] for o in parsed[0]["options"]],
                         ["approve", "decline", "defer"])
        self.assertEqual(parsed[0]["state"]["content_hash"],
                         rat.content_hash(card()))

    def test_failed_triage_publishes_anyway(self):
        text = rat.render_card(card(), triage=None)
        self.assertIn("advisory fails", text)
        self.assertEqual(len(rat.parse_cards(text)), 1)

    def test_multiple_cards_parse(self):
        text = rat.render_card(card()) + "\n" + rat.render_card(
            card(card_id="other-card"))
        self.assertEqual([c["card_id"] for c in rat.parse_cards(text)],
                         ["panel-shrink-routine", "other-card"])

    def test_bad_cards_rejected(self):
        for patch in ({"options": [{"key": "only", "label": "x"}]},
                      {"options": [{"key": "a b", "label": "x"},
                                   {"key": "c", "label": "y"}]},
                      {"situation": ""}):
            with self.assertRaises(RatificationError):
                rat.render_card(card(**patch))

    def test_missing_state_comment_is_loud(self):
        with self.assertRaises(RatificationError):
            rat.parse_cards("## card: broken\nno state here\n")


class DecisionTests(unittest.TestCase):
    def tick(self, text, key):
        return text.replace(f"- [ ] Approve the shrink <!-- opt:{key} -->",
                            f"- [x] Approve the shrink <!-- opt:{key} -->")

    def test_untouched_card_is_pending(self):
        parsed = rat.parse_cards(rat.render_card(card()))[0]
        self.assertEqual(rat.decision_of(parsed)["status"], "pending")

    def test_single_tick_decides(self):
        text = self.tick(rat.render_card(card()), "approve")
        parsed = rat.parse_cards(text)[0]
        got = rat.decision_of(parsed)
        self.assertEqual((got["status"], got["key"]), ("decided", "approve"))

    def test_two_ticks_refused_never_guessed(self):
        text = rat.render_card(card())
        text = text.replace("- [ ] Approve the shrink <!-- opt:approve -->",
                            "- [x] Approve the shrink <!-- opt:approve -->")
        text = text.replace("- [ ] Keep 3 lenses <!-- opt:decline -->",
                            "- [X] Keep 3 lenses <!-- opt:decline -->")
        got = rat.decision_of(rat.parse_cards(text)[0])
        self.assertEqual(got["status"], "ambiguous")


class StaleGuardTests(unittest.TestCase):
    def test_unchanged_card_ratifies(self):
        text = rat.render_card(card()).replace(
            "- [ ] Approve the shrink <!-- opt:approve -->",
            "- [x] Approve the shrink <!-- opt:approve -->")
        parsed = rat.parse_cards(text)[0]
        got = rat.ratify(parsed, card())
        self.assertTrue(got["ratified"])
        self.assertEqual(got["key"], "approve")

    def test_changed_substance_refuses(self):
        text = rat.render_card(card()).replace(
            "- [ ] Approve the shrink <!-- opt:approve -->",
            "- [x] Approve the shrink <!-- opt:approve -->")
        parsed = rat.parse_cards(text)[0]
        changed = card(recommendation="Shrink to ONE lens (est. -20%/wk).")
        got = rat.ratify(parsed, changed)
        self.assertEqual(got["status"], "stale")
        self.assertFalse(got["ratified"])

    def test_pending_card_never_ratifies(self):
        parsed = rat.parse_cards(rat.render_card(card()))[0]
        self.assertFalse(rat.ratify(parsed, card())["ratified"])

    def test_triage_change_does_not_invalidate_review(self):
        # triage is advisory: same substance, different triage text -> same hash
        a = rat.parse_cards(rat.render_card(card(), triage="looks fine"))[0]
        b = rat.parse_cards(rat.render_card(card(), triage="different words"))[0]
        self.assertEqual(a["state"]["content_hash"], b["state"]["content_hash"])


class TriageCacheTests(unittest.TestCase):
    def test_one_triage_per_revision(self):
        c = card()
        h = rat.content_hash(c)
        self.assertTrue(rat.needs_triage(c, {}))
        self.assertFalse(rat.needs_triage(c, {h: "cached triage"}))
        changed = card(recommendation="different")
        self.assertTrue(rat.needs_triage(changed, {h: "cached triage"}))


class BlockerCardTests(unittest.TestCase):
    def test_blocker_becomes_card(self):
        blocker = {"task_id": "t9",
                   "repro": "route optimizer needs a maps API key",
                   "recommendation": "google routes",
                   "options": [{"key": "google", "label": "Google Routes"},
                               {"key": "mapbox", "label": "Mapbox"}]}
        c = rat.blocker_to_card(blocker)
        text = rat.render_card(c)
        parsed = rat.parse_cards(text)[0]
        self.assertEqual(parsed["card_id"], "blocker-t9")
        self.assertEqual(len(parsed["options"]), 2)


if __name__ == "__main__":
    unittest.main()


class CrossProviderCardTests(unittest.TestCase):
    """H5 — cross-provider validator is a ratified option, never a default."""

    def correlation(self, blind):
        return {"correlated_blind_spots": len(blind), "blind_spot_ids": blind,
                "trials_scored": 6, "sole_catcher_trials": 1}

    def test_blind_spot_recommends_adoption(self):
        doc = rat.cross_provider_card("critical", self.correlation(["c3"]))
        rat.validate_card(doc)
        self.assertIn("c3", doc["situation"])
        self.assertIn("Add one cross-provider validator", doc["recommendation"])
        self.assertEqual([o["key"] for o in doc["options"]],
                         ["adopt", "hold"])
        # renders as a committed card without error
        self.assertIn("<!-- opt:adopt -->", rat.render_card(doc))

    def test_no_blind_spot_recommends_hold(self):
        doc = rat.cross_provider_card("critical", self.correlation([]))
        self.assertIn("Hold", doc["recommendation"])
        self.assertIn("none", doc["situation"])

    def test_card_id_is_per_profile(self):
        self.assertEqual(
            rat.cross_provider_card("high", self.correlation([]))["card_id"],
            "cross-provider-validator-high")
