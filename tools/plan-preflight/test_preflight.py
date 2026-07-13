"""plan-preflight tests — sound checks hard-fail, judgment signals warn.

Run: python3 tools/plan-preflight/test_preflight.py
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PREFLIGHT = os.path.join(HERE, "preflight.py")

VALID = {
    "contract": 1,
    "goal": "Add a password-reset flow.",
    "non_goals": ["No email-provider migration."],
    "decisions": [{"q": "Token TTL?", "a": "15 minutes, single use."}],
    "tasks": [
        {
            "id": "schema",
            "title": "Reset-token table",
            "spec": "Add reset_tokens table with single-use semantics.",
            "checks": ["python3 -m pytest tests/test_schema.py -q"],
            "provides": ["reset-token-store"],
        },
        {
            "id": "endpoint",
            "title": "Reset endpoints",
            "spec": "POST /reset-request and POST /reset-confirm per decisions.",
            "depends_on": ["schema"],
            "requires": ["reset-token-store", "mailer"],
            "checks": ["python3 -m pytest tests/test_reset.py -q"],
        },
    ],
    "external": ["mailer"],
}


def run_cli(args, plan=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "plan.json")
        if isinstance(plan, str):
            with open(path, "w") as fh:
                fh.write(plan)
        elif plan is not None:
            with open(path, "w") as fh:
                json.dump(plan, fh)
        proc = subprocess.run(
            [sys.executable, PREFLIGHT, *args, path],
            capture_output=True,
            text=True,
        )
    return proc


def check(plan, *flags):
    proc = run_cli(["check", *flags], plan)
    body = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, body


def errors_text(body):
    return "; ".join(body.get("errors", []))


def warnings_text(body):
    return "; ".join(body.get("warnings", []))


class SoundChecksHardFail(unittest.TestCase):
    def test_valid_plan_passes_with_expected_warnings_only(self):
        code, body = check(VALID)
        self.assertEqual(code, 0, body)
        self.assertTrue(body["ok"])
        self.assertEqual(body["errors"], [])
        self.assertEqual(body["stats"], {"tasks": 2, "edges": 1, "roots": ["schema"]})

    def test_invalid_json_fails(self):
        proc = run_cli(["check"], plan="{nope")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not valid JSON", proc.stdout)

    def test_missing_file_is_env_error(self):
        proc = subprocess.run(
            [sys.executable, PREFLIGHT, "check", "/nonexistent/plan.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)

    def test_wrong_contract_and_empty_goal(self):
        plan = copy.deepcopy(VALID)
        plan["contract"] = 2
        plan["goal"] = "  "
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("contract must be 1", errors_text(body))
        self.assertIn("goal must be a non-empty string", errors_text(body))

    def test_unknown_keys_rejected_at_both_levels(self):
        plan = copy.deepcopy(VALID)
        plan["extra"] = True
        plan["tasks"][0]["dependson"] = ["typo"]
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("unknown top-level key(s): extra", errors_text(body))
        self.assertIn("unknown key(s): dependson", errors_text(body))

    def test_risk_tiers_validated(self):
        # valid: plan-level tier + per-task override
        plan = copy.deepcopy(VALID)
        plan["risk_tier"] = "gate-only"
        plan["tasks"][0]["tier"] = "full"
        code, body = check(plan)
        self.assertEqual(code, 0, body)
        # invalid values are sound errors at both levels
        plan = copy.deepcopy(VALID)
        plan["risk_tier"] = "yolo"
        plan["tasks"][0]["tier"] = "medium"
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("risk_tier must be one of full/gate-only/bare", errors_text(body))
        self.assertIn("tier must be one of full/gate-only/bare", errors_text(body))

    def test_gate_only_without_checks_warns(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"][0]["tier"] = "gate-only"
        del plan["tasks"][0]["checks"]
        code, body = check(plan)
        self.assertEqual(code, 0, body)  # judgment signal, not a sound error
        self.assertIn("rubber stamp", warnings_text(body))

    def test_duplicate_and_malformed_ids(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"][1]["id"] = "schema"
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("duplicate task id: schema", errors_text(body))

        plan = copy.deepcopy(VALID)
        plan["tasks"][0]["id"] = "Bad_ID"
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("id must match", errors_text(body))

    def test_dangling_and_self_dependencies(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"][1]["depends_on"] = ["ghost", "endpoint"]
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("depends on unknown task 'ghost'", errors_text(body))
        self.assertIn("depends on itself", errors_text(body))

    def test_cycle_detected_and_named(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"][0]["depends_on"] = ["endpoint"]
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn("dependency cycle:", errors_text(body))
        self.assertIn("schema", errors_text(body))
        self.assertIn("endpoint", errors_text(body))

    def test_malformed_ratified_and_decisions(self):
        plan = copy.deepcopy(VALID)
        plan["ratified"] = {"by": "dwijen"}  # missing ts
        plan["decisions"] = [{"q": "only a question"}]
        code, body = check(plan)
        self.assertEqual(code, 1)
        self.assertIn('ratified must be an object with exactly keys "by" and "ts"', errors_text(body))
        self.assertIn("decisions[0]", errors_text(body))


class JudgmentSignalsWarn(unittest.TestCase):
    def test_empty_checks_warns_but_passes(self):
        plan = copy.deepcopy(VALID)
        del plan["tasks"][0]["checks"]
        code, body = check(plan)
        self.assertEqual(code, 0)  # never force plan-padding
        self.assertIn("no acceptance checks", warnings_text(body))

    def test_unmatched_requires_warns_matched_does_not(self):
        code, body = check(VALID)
        self.assertEqual(code, 0)
        self.assertNotIn("requires", warnings_text(body))  # mailer is external

        plan = copy.deepcopy(VALID)
        plan["external"] = []
        code, body = check(plan)
        self.assertEqual(code, 0)
        self.assertIn("requires 'mailer'", warnings_text(body))

    def test_open_questions_warn(self):
        plan = copy.deepcopy(VALID)
        plan["open_questions"] = ["Rate-limit resets per IP?"]
        code, body = check(plan)
        self.assertEqual(code, 0)
        self.assertIn("open question(s) remain", warnings_text(body))

    def test_strict_promotes_warnings_to_failure(self):
        plan = copy.deepcopy(VALID)
        plan["open_questions"] = ["Unresolved."]
        code, body = check(plan, "--strict")
        self.assertEqual(code, 1)
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"], [])  # still not errors — the knob flips ok only

    def test_require_ratified(self):
        code, body = check(VALID, "--require-ratified")
        self.assertEqual(code, 1)
        self.assertIn("not ratified", errors_text(body))

        plan = copy.deepcopy(VALID)
        plan["ratified"] = {"by": "dwijen", "ts": "2026-07-11T20:00:00Z"}
        code, body = check(plan, "--require-ratified")
        self.assertEqual(code, 0, body)
        self.assertTrue(body["ratified"])


class OrderTests(unittest.TestCase):
    def test_topological_and_deterministic(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"].append(
            {
                "id": "docs",
                "title": "Document the flow",
                "spec": "Write reset-flow docs.",
                "depends_on": ["schema"],
            }
        )
        proc = run_cli(["order"], plan)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.split(), ["schema", "docs", "endpoint"])

    def test_order_refuses_invalid_plan(self):
        plan = copy.deepcopy(VALID)
        plan["tasks"][0]["depends_on"] = ["endpoint"]  # cycle
        proc = run_cli(["order"], plan)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
