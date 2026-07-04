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
