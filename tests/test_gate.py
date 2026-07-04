"""Tests for harness.gate (D2) — clean-checkout gate, verdicts, typed findings."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import gate, vault


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


class RepoFixture:
    """A tiny repo: main has passing tests + floors config; a feature branch
    adds a change (optionally breaking the tests / touching floored paths)."""

    def __init__(self, root):
        self.repo = os.path.join(root, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        self.write("app.py", "def add(a, b):\n    return a + b\n")
        self.write("test_app.py",
                   "import unittest, app\n"
                   "class T(unittest.TestCase):\n"
                   "    def test_add(self): self.assertEqual(app.add(1, 2), 3)\n"
                   "if __name__ == '__main__': unittest.main()\n")
        self.write("floors.json", json.dumps(
            {"floors": [{"glob": "billing/**", "min_profile": "critical"}]}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")

    def write(self, rel, content):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path) or self.repo, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    def branch(self, name, files, message="change"):
        git(self.repo, "checkout", "-q", "-b", name, "main")
        for rel, content in files.items():
            self.write(rel, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", message)
        git(self.repo, "checkout", "-q", "main")


TEST_CMD = f"{sys.executable} -m unittest test_app -v"


def make_panel(root, verdicts):
    vdir = os.path.join(root, "verdicts")
    os.makedirs(vdir, exist_ok=True)
    for i, (lens, verdict) in enumerate(verdicts):
        with open(os.path.join(vdir, f"{i}-{lens}.json"), "w") as fh:
            json.dump({"lens": lens, "verdict": verdict,
                       "evidence": "quoted behavior here"}, fh)
    return vdir


class FindingsTests(unittest.TestCase):
    def test_error_findings_block_regardless_of_action(self):
        tri = gate.triage_findings(
            [{"severity": "error", "action": "auto-fix", "summary": "bad",
              "step": "lint"}])
        self.assertEqual(len(tri["blockers"]), 1)

    def test_autofix_budget_respected_per_step(self):
        findings = [{"severity": "warning", "action": "auto-fix",
                     "summary": f"w{i}", "step": "lint"} for i in range(7)]
        tri = gate.triage_findings(findings, budgets={"lint": 5})
        self.assertEqual(len(tri["auto_fix"]), 5)
        self.assertEqual(len(tri["needs_human"]), 2)
        self.assertTrue(all(f.get("budget_exceeded")
                            for f in tri["needs_human"]))

    def test_review_class_defaults_to_always_human(self):
        tri = gate.triage_findings(
            [{"severity": "warning", "action": "auto-fix", "summary": "style",
              "step": "review"}])
        self.assertEqual(tri["auto_fix"], [])
        self.assertEqual(len(tri["needs_human"]), 1)

    def test_info_noop_recorded_only(self):
        tri = gate.triage_findings(
            [{"severity": "info", "action": "no-op", "summary": "fyi"}])
        self.assertEqual(len(tri["info"]), 1)

    def test_malformed_findings_loud(self):
        for bad in ({"severity": "mega", "action": "no-op", "summary": "x"},
                    {"severity": "info", "action": "later", "summary": "x"},
                    {"severity": "info", "action": "no-op", "summary": ""}):
            with self.assertRaises(gate.GateError):
                gate.triage_findings([bad])


class VerdictTests(unittest.TestCase):
    def test_all_pass_ok(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = make_panel(root, [("correctness", "PASS"), ("security", "PASS")])
            panel = gate.check_verdicts(gate.read_verdicts(vdir))
            self.assertTrue(panel["ok"])

    def test_one_fail_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = make_panel(root, [("correctness", "PASS"), ("security", "FAIL")])
            panel = gate.check_verdicts(gate.read_verdicts(vdir))
            self.assertFalse(panel["ok"])
            self.assertEqual(panel["failing"], ["security"])

    def test_empty_panel_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = os.path.join(root, "empty")
            os.makedirs(vdir)
            panel = gate.check_verdicts(gate.read_verdicts(vdir))
            self.assertFalse(panel["ok"])
            self.assertIn("no panel, no pass", panel["why"])

    def test_corrupt_verdict_is_loud(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = os.path.join(root, "v")
            os.makedirs(vdir)
            with open(os.path.join(vdir, "x.json"), "w") as fh:
                fh.write("{broken")
            with self.assertRaises(gate.GateError):
                gate.read_verdicts(vdir)


class GateEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.root_ctx = tempfile.TemporaryDirectory()
        self.root = self.root_ctx.name
        self.fx = RepoFixture(self.root)

    def tearDown(self):
        self.root_ctx.cleanup()

    def run_gate(self, branch, **kw):
        defaults = dict(
            repo=self.fx.repo, branch=branch, base="main", test_cmd=TEST_CMD,
            verdict_dir=make_panel(self.root, [("correctness", "PASS")]),
            task_profile="routine",
            floor_config_path="floors.json",
            evidence_dir=os.path.join(self.root, "evidence"))
        defaults.update(kw)
        return gate.run_gate(**defaults)

    def test_green_branch_passes_all_steps(self):
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n\n"
                       "def sub(a, b):\n    return a - b\n"})
        report = self.run_gate("task/good")
        self.assertTrue(report["ok"], report["steps"])
        self.assertTrue(all(s["ok"] for s in report["steps"]))
        # evidence trail written
        with open(os.path.join(self.root, "evidence", "gate-report.json")) as fh:
            self.assertTrue(json.load(fh)["ok"])

    def test_red_tests_block_with_full_log_spilled(self):
        self.fx.branch("task/broken", {"app.py":
                       "def add(a, b):\n    return a - b\n"})
        report = self.run_gate("task/broken")
        self.assertFalse(report["ok"])
        failing = [s for s in report["steps"] if not s["ok"]]
        self.assertEqual(failing[0]["step"], "visible_tests")
        self.assertIn("grep it", failing[0]["detail"])
        with open(report["full_log"]) as fh:
            self.assertIn("FAILED", fh.read())

    def test_dirty_tree_refused_with_require_clean(self):
        self.fx.branch("task/good", {"app.py": "def add(a, b): return a + b\n"})
        self.fx.write("scratch.txt", "uncommitted")
        report = self.run_gate("task/good")
        self.assertFalse(report["ok"])
        self.assertEqual(report["steps"][0]["step"], "require_clean")
        os.unlink(os.path.join(self.fx.repo, "scratch.txt"))

    def test_mistagged_floored_diff_blocks_before_tests_run(self):
        self.fx.branch("task/sneaky", {"billing/charge.py": "PLAN = 'x'\n"})
        report = self.run_gate("task/sneaky", task_profile="routine")
        self.assertFalse(report["ok"])
        steps = {s["step"]: s for s in report["steps"]}
        self.assertFalse(steps["risk_floor"]["ok"])
        self.assertNotIn("visible_tests", steps)  # fail-fast: no checkout spent

    def test_floored_diff_passes_at_adequate_profile(self):
        self.fx.branch("task/billing", {"billing/charge.py": "PLAN = 'x'\n"})
        report = self.run_gate("task/billing", task_profile="critical")
        self.assertTrue(report["ok"], report["steps"])

    def test_tampered_floor_config_on_branch_is_ignored(self):
        # branch weakens floors.json in its own diff; gate reads base's copy
        self.fx.branch("task/evil", {
            "billing/charge.py": "PLAN = 'x'\n",
            "floors.json": json.dumps({"floors": []})})
        report = self.run_gate("task/evil", task_profile="routine")
        steps = {s["step"]: s for s in report["steps"]}
        self.assertFalse(steps["risk_floor"]["ok"])

    def test_machinery_edit_on_task_branch_blocks(self):
        self.fx.branch("task/hack", {"hooks/git_guard.py": "# neutered\n"})
        report = self.run_gate("task/hack")
        steps = {s["step"]: s for s in report["steps"]}
        self.assertFalse(steps["machinery_paths"]["ok"])

    def test_failing_verdict_blocks_after_green_tests(self):
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n# touch\n"})
        report = self.run_gate(
            "task/good",
            verdict_dir=make_panel(self.root, [("correctness", "PASS"),
                                               ("security", "FAIL")]))
        self.assertFalse(report["ok"])
        steps = {s["step"]: s for s in report["steps"]}
        self.assertTrue(steps["visible_tests"]["ok"])
        self.assertFalse(steps["verdicts"]["ok"])

    def test_heldout_drop_blocks(self):
        vdir = os.path.join(self.root, "vault")
        vault.write_canary(vdir)
        with open(os.path.join(vdir, "test_h.py"), "w") as fh:
            fh.write("def test_h(): pass\n")
        vault.save_manifest(vdir, vault.build_manifest(vdir))
        os.unlink(os.path.join(vdir, "test_h.py"))
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n# t\n"})
        report = self.run_gate("task/good", vault_path=vdir)
        steps = {s["step"]: s for s in report["steps"]}
        self.assertFalse(steps["heldout_drop"]["ok"])

    def test_error_finding_blocks_green_everything(self):
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n# t2\n"})
        report = self.run_gate(
            "task/good",
            findings=[{"severity": "error", "action": "ask-user",
                       "summary": "vault canary read succeeded under fallback",
                       "step": "review"}])
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["findings"]["blockers"]), 1)

    def test_empty_diff_short_circuits_green(self):
        self.fx.branch("task/noop", {})
        # branch with no changes vs main
        report = self.run_gate("task/noop")
        self.assertTrue(report["ok"])
        self.assertEqual(report["steps"][-1]["step"], "empty_diff")

    def test_render_report_turn_economy(self):
        self.fx.branch("task/broken2", {"app.py": "def add(a, b): return 0\n"})
        report = self.run_gate("task/broken2")
        text = gate.render_report(report)
        first = text.splitlines()[0]
        self.assertTrue(first.startswith("gate: FAIL"))
        self.assertIn("blocking step: visible_tests", text)
        self.assertIn("| step | ok | detail |", text)


if __name__ == "__main__":
    unittest.main()
