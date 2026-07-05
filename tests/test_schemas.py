"""Tests for harness.schemas (E1) — verdict/handoff/blocker contracts."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import schemas
from harness.schemas import SchemaError


def good_verdict(**patch):
    doc = {"lens": "security", "verdict": "FAIL",
           "evidence": ["SET tenant B claims returned tenant A rows"],
           "intent": "verify cross-tenant isolation on crew_schedules",
           "findings": [{"severity": "error", "action": "ask-user",
                         "summary": "RLS policy missing FORCE"}]}
    doc.update(patch)
    return doc


def good_handoff(**patch):
    doc = {"outcome": "pass", "summary": "RLS policies added",
           "intent": "implement tenancy isolation",
           "key_changes_made": ["RLS covers SELECT/UPDATE/DELETE with FORCE"],
           "key_learnings": [],
           "files_touched": ["db/policies.sql"]}
    doc.update(patch)
    return doc


def good_blocker(**patch):
    doc = {"task_id": "t9", "repro": "route optimizer needs a maps API key",
           "recommendation": "google routes: better traffic data",
           "options": [{"key": "google", "label": "Google Routes"},
                       {"key": "mapbox", "label": "Mapbox"}]}
    doc.update(patch)
    return doc


class VerdictTests(unittest.TestCase):
    def test_good_verdict_passes(self):
        self.assertEqual(schemas.validate_verdict(good_verdict())["lens"],
                         "security")

    def test_fail_without_findings_rejected(self):
        with self.assertRaises(SchemaError):
            schemas.validate_verdict(good_verdict(findings=[]))

    def test_pass_without_findings_fine(self):
        doc = good_verdict(verdict="PASS", findings=[])
        self.assertEqual(schemas.validate_verdict(doc)["verdict"], "PASS")

    def test_empty_evidence_rejected(self):
        with self.assertRaises(SchemaError):
            schemas.validate_verdict(good_verdict(evidence=[]))

    def test_missing_intent_rejected(self):
        doc = good_verdict()
        del doc["intent"]
        with self.assertRaises(SchemaError):
            schemas.validate_verdict(doc)

    def test_bad_finding_shape_rejected(self):
        bad = good_verdict(findings=[{"severity": "mega", "action": "no-op",
                                      "summary": "x"}])
        with self.assertRaises(SchemaError):
            schemas.validate_verdict(bad)


class HandoffTests(unittest.TestCase):
    def test_good_handoff_passes(self):
        self.assertEqual(schemas.validate_handoff(good_handoff())["outcome"],
                         "pass")

    def test_pass_with_no_material_changes_rejected(self):
        # the no-op rule at the schema layer
        with self.assertRaises(SchemaError):
            schemas.validate_handoff(good_handoff(key_changes_made=[]))

    def test_fail_with_no_changes_is_fine(self):
        doc = good_handoff(outcome="fail", key_changes_made=[],
                           summary="could not satisfy contract test 3")
        self.assertEqual(schemas.validate_handoff(doc)["outcome"], "fail")

    def test_empty_learnings_is_a_definitive_answer(self):
        self.assertEqual(schemas.validate_handoff(good_handoff())["key_learnings"],
                         [])

    def test_bad_outcome_rejected(self):
        with self.assertRaises(SchemaError):
            schemas.validate_handoff(good_handoff(outcome="meh"))


class BlockerTests(unittest.TestCase):
    def test_good_blocker_passes(self):
        self.assertEqual(schemas.validate_blocker(good_blocker())["task_id"], "t9")

    def test_single_option_rejected(self):
        with self.assertRaises(SchemaError):
            schemas.validate_blocker(good_blocker(
                options=[{"key": "only", "label": "Only choice"}]))

    def test_duplicate_option_keys_rejected(self):
        with self.assertRaises(SchemaError):
            schemas.validate_blocker(good_blocker(
                options=[{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]))

    def test_lifecycle_fields_validate(self):
        # I21 (P3v2-1): asked_at/resolved make operator-wait disk-derivable.
        doc = schemas.validate_blocker(good_blocker(
            kind="H9-spec-ambiguity",
            asked_at="2026-07-05T12:15:12Z",
            resolved={"decision": "proceed-as-read", "by": "dwijen",
                      "at": "2026-07-05T20:40:45Z"}))
        self.assertEqual(doc["resolved"]["decision"], "proceed-as-read")

    def test_bad_lifecycle_fields_loud(self):
        with self.assertRaises(SchemaError):
            schemas.validate_blocker(good_blocker(asked_at=1720180512))
        with self.assertRaises(SchemaError):
            schemas.validate_blocker(good_blocker(resolved="done"))
        with self.assertRaises(SchemaError):  # a resolution names its human
            schemas.validate_blocker(good_blocker(
                resolved={"decision": "proceed-as-read"}))


class JsonSchemaParityTests(unittest.TestCase):
    """The committed JSON Schemas must agree with the Python validators on the
    required-field surface (spot parity, not full equivalence)."""

    def test_schemas_load_and_require_the_same_core_fields(self):
        verdict = schemas.load_json_schema("verdict")
        self.assertEqual(set(verdict["required"]),
                         {"lens", "verdict", "evidence", "intent"})
        handoff = schemas.load_json_schema("handoff")
        self.assertEqual(set(handoff["required"]),
                         {"outcome", "summary", "intent", "key_changes_made",
                          "key_learnings"})
        blocker = schemas.load_json_schema("blocker")
        self.assertEqual(set(blocker["required"]),
                         {"task_id", "repro", "options", "recommendation"})

    def test_agent_definitions_exist_and_reference_schemas(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name, schema_ref in (("implementer.md", "handoff"),
                                 ("validator.md", "verdict"),
                                 ("test-author.md", "handoff")):
            path = os.path.join(root, ".claude", "agents", name)
            with open(path) as fh:
                body = fh.read()
            self.assertIn("JSON only", body, name)
            self.assertIn(schema_ref, body, name)


if __name__ == "__main__":
    unittest.main()


class AmbiguityBlockerTests(unittest.TestCase):
    """H9 — spec ambiguities park high/critical tasks pre-implementation."""

    def handoff(self, ambiguities):
        return {"outcome": "pass", "summary": "authored 4 held-out tests",
                "intent": "pin the pagination contract",
                "key_changes_made": ["pins last-page boundary"],
                "key_learnings": [],
                "spec_ambiguities": ambiguities}

    def test_high_profile_ambiguities_become_blockers(self):
        blockers = schemas.ambiguity_blockers(
            self.handoff(["Is page size 1-indexed or 0-indexed?",
                          "Does 'user' include service accounts?"]),
            task_id="t7", profile="high")
        self.assertEqual(len(blockers), 2)
        for b in blockers:
            schemas.validate_blocker(b)  # already validated; stays valid
            self.assertEqual(b["task_id"], "t7")
            self.assertIn("pre-implementation", b["repro"])
            self.assertEqual([o["key"] for o in b["options"]],
                             ["clarify", "proceed-as-read"])
        self.assertIn("1-indexed", blockers[0]["repro"])

    def test_routine_profile_stays_advisory(self):
        blockers = schemas.ambiguity_blockers(
            self.handoff(["ambiguous wording"]), task_id="t7",
            profile="routine")
        self.assertEqual(blockers, [])

    def test_no_ambiguities_no_blockers(self):
        self.assertEqual(
            schemas.ambiguity_blockers(self.handoff([]), "t7", "critical"),
            [])

    def test_malformed_ambiguities_loud(self):
        with self.assertRaises(SchemaError):
            schemas.validate_handoff(self.handoff([""]))
        with self.assertRaises(SchemaError):
            schemas.validate_handoff(self.handoff("not a list"))

    def test_structured_entries_validate(self):
        doc = self.handoff([
            {"text": "Is deletion soft or hard?", "corpus_covers": "both"},
            {"text": "Which timezone for due dates?"}])
        self.assertEqual(len(schemas.validate_handoff(doc)["spec_ambiguities"]),
                         2)
        with self.assertRaises(SchemaError):  # object form needs text
            schemas.validate_handoff(self.handoff([{"corpus_covers": "both"}]))
        with self.assertRaises(SchemaError):  # unknown coverage is loud
            schemas.validate_handoff(self.handoff(
                [{"text": "x?", "corpus_covers": "maybe"}]))
        with self.assertRaises(SchemaError):  # neither string nor object
            schemas.validate_handoff(self.handoff([42]))

    def test_dual_covered_entries_discharged(self):
        # I20 (P3v2-1): corpus-absorbs-both-readings entries never block;
        # numbering stays over the full list so blockers trace to the handoff.
        blockers = schemas.ambiguity_blockers(
            self.handoff([
                {"text": "Is deletion soft or hard?", "corpus_covers": "both"},
                "Which timezone for due dates?",
                {"text": "Are names case-folded?",
                 "corpus_covers": "one-reading"}]),
            task_id="t7", profile="high")
        self.assertEqual(len(blockers), 2)
        self.assertIn("ambiguity 2/3", blockers[0]["repro"])
        self.assertIn("timezone", blockers[0]["repro"])
        self.assertIn("ambiguity 3/3", blockers[1]["repro"])

    def test_all_discharged_means_no_blockers(self):
        self.assertEqual(schemas.ambiguity_blockers(
            self.handoff([{"text": "a?", "corpus_covers": "both"},
                          {"text": "b?", "corpus_covers": "both"}]),
            task_id="t7", profile="critical"), [])

    def test_blocker_card_roundtrip(self):
        from harness import ratification
        blocker = schemas.ambiguity_blockers(
            self.handoff(["Which tenant sees archived rows?"]),
            task_id="t9", profile="critical")[0]
        card = ratification.blocker_to_card(blocker)
        text = ratification.render_card(card)
        self.assertIn("Which tenant sees archived rows?", text)
        self.assertIn("<!-- opt:clarify -->", text)
