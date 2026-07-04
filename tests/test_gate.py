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
        blocked = next(s for s in report["steps"] if not s["ok"])
        self.assertEqual(blocked["step"], "require_clean")
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


class ReproReplayTests(unittest.TestCase):
    """H4 — a FAIL must demonstrate itself before it blocks; unreproduced
    findings are false-FAIL candidates routed to humans, not escalation."""

    REPRODUCES = f"{sys.executable} -c \"import sys; sys.exit(1)\""
    DOES_NOT = f"{sys.executable} -c \"import sys; sys.exit(0)\""

    def setUp(self):
        self.root_ctx = tempfile.TemporaryDirectory()
        self.root = self.root_ctx.name
        self.fx = RepoFixture(self.root)
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n\n"
                       "def sub(a, b):\n    return a - b\n"})

    def tearDown(self):
        self.root_ctx.cleanup()

    def fail_panel(self, findings):
        vdir = os.path.join(self.root, "verdicts-fail")
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, "correctness.json"), "w") as fh:
            json.dump({"lens": "correctness", "verdict": "FAIL",
                       "evidence": ["observed X"], "intent": "t",
                       "findings": findings}, fh)
        return vdir

    def run_gate(self, findings, repro_mode="replay", **kw):
        defaults = dict(repo=self.fx.repo, branch="task/good", base="main",
                        test_cmd=TEST_CMD, task_profile="routine",
                        verdict_dir=self.fail_panel(findings),
                        repro_mode=repro_mode)
        defaults.update(kw)
        return gate.run_gate(**defaults)

    def finding(self, **kw):
        base = {"severity": "error", "action": "ask-user",
                "summary": "claimed defect"}
        base.update(kw)
        return base

    def verdict_step(self, report):
        return next(s for s in report["steps"] if s["step"] == "verdicts")

    def test_reproduced_fail_blocks_confirmed(self):
        report = self.run_gate(
            [self.finding(repro={"command": self.REPRODUCES})])
        self.assertFalse(report["ok"])
        self.assertIn("CONFIRMED by replay", self.verdict_step(report)["detail"])
        self.assertNotIn("needs_adjudication", report)
        self.assertEqual(report["false_fail"]["reproduced"], 1)

    def test_unreproduced_fail_downgrades_to_adjudication(self):
        report = self.run_gate(
            [self.finding(repro={"command": self.DOES_NOT})])
        self.assertFalse(report["ok"])  # still no auto-merge — human decides
        self.assertTrue(report["needs_adjudication"])
        self.assertIn("NOT the", self.verdict_step(report)["detail"])
        self.assertEqual(report["false_fail"]["unreproduced"], 1)
        downgraded = report["downgraded_findings"]
        self.assertEqual(downgraded[0]["action"], "ask-user")
        self.assertTrue(downgraded[0]["unreproduced"])
        self.assertEqual(
            report["false_fail"]["by_lens"]["correctness"]["unreproduced"], 1)

    def test_expect_substring_checked(self):
        cmd = (f"{sys.executable} -c \"print('tenant B saw tenant A rows'); "
               f"import sys; sys.exit(1)\"")
        reproduced = self.run_gate([self.finding(repro={
            "command": cmd, "expect_substring": "tenant B saw tenant A"})])
        self.assertIn("CONFIRMED", self.verdict_step(reproduced)["detail"])
        missing = self.run_gate([self.finding(repro={
            "command": cmd, "expect_substring": "no such output"})])
        self.assertTrue(missing["needs_adjudication"])

    def test_no_repro_error_blocks_in_replay_mode(self):
        report = self.run_gate([self.finding()])
        self.assertFalse(report["ok"])
        self.assertIn("without an executable repro",
                      self.verdict_step(report)["detail"])
        self.assertNotIn("needs_adjudication", report)

    def test_no_repro_error_downgrades_in_strict_mode(self):
        report = self.run_gate([self.finding()], repro_mode="strict")
        self.assertFalse(report["ok"])
        self.assertTrue(report["needs_adjudication"])
        self.assertTrue(report["downgraded_findings"][0]["unreplayable"])

    def test_off_mode_keeps_legacy_behavior(self):
        report = self.run_gate([self.finding()], repro_mode="off")
        self.assertFalse(report["ok"])
        self.assertIn("all-must-pass violated",
                      self.verdict_step(report)["detail"])
        self.assertNotIn("false_fail", report)

    def test_warning_findings_not_replayed(self):
        report = self.run_gate(
            [self.finding(severity="warning", repro={"command":
                                                     self.REPRODUCES})])
        self.assertTrue(report["needs_adjudication"])
        self.assertEqual(report["false_fail"]["error_findings"], 0)

    def test_malformed_repro_fails_closed(self):
        report = self.run_gate([self.finding(repro={"command": ""})])
        self.assertFalse(report["ok"])
        self.assertIn("fail-closed", self.verdict_step(report)["detail"])

    def test_unknown_repro_mode_is_loud(self):
        with self.assertRaises(gate.GateError):
            self.run_gate([self.finding()], repro_mode="maybe")

    def test_false_fail_records_bridge(self):
        report = self.run_gate(
            [self.finding(repro={"command": self.DOES_NOT})])
        records = gate.false_fail_records(report, task_id="t1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], "false_fail")
        self.assertEqual(records[0]["lens"], "correctness")
        self.assertEqual(records[0]["unreproduced"], 1)
        self.assertEqual(records[0]["task_id"], "t1")
        from harness import runlog
        runlog.validate_record(records[0])  # accepted by the run-log schema
        self.assertEqual(gate.false_fail_records({"false_fail": None}), [])


class EvidenceScrubTests(unittest.TestCase):
    """H7 — gate evidence artifacts never name held-out content."""

    def test_full_log_and_report_scrubbed_against_vault_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            fx = RepoFixture(root)
            vault_dir = os.path.join(root, ".vault")
            vault.write_canary(vault_dir)
            with open(os.path.join(vault_dir, "test_holdout_secret.py"),
                      "w") as fh:
                fh.write("def test_hidden(): assert True\n")
            vault.save_manifest(vault_dir, vault.build_manifest(vault_dir))
            # the visible suite's output mentions a held-out identifier
            fx.branch("task/leaky", {"test_app.py":
                      "import unittest, app\n"
                      "class T(unittest.TestCase):\n"
                      "    def test_add(self):\n"
                      "        print('invariant pinned by "
                      "test_holdout_secret')\n"
                      "        self.assertEqual(app.add(1, 2), 3)\n"
                      "if __name__ == '__main__': unittest.main()\n"})
            evidence_dir = os.path.join(root, "evidence")
            report = gate.run_gate(
                fx.repo, "task/leaky", base="main",
                test_cmd=f"{sys.executable} -m unittest test_app -v",
                vault_path=vault_dir, evidence_dir=evidence_dir,
                verdict_dir=make_panel(root, [("correctness", "PASS")]))
            self.assertTrue(report["ok"], report["steps"])
            with open(os.path.join(evidence_dir,
                                   "test-output-full.log")) as fh:
                full_log = fh.read()
            self.assertNotIn("test_holdout_secret", full_log)
            self.assertIn("vault:", full_log)  # the identifier was tokenized
            with open(os.path.join(evidence_dir, "gate-report.json")) as fh:
                committed = fh.read()
            self.assertNotIn("test_holdout_secret", committed)


class RequiredStepsManifestTests(unittest.TestCase):
    """H3 — a required step whose input is absent fails closed, never
    'caller's choice'."""

    MANIFEST = json.dumps({
        "routine": ["visible_tests", "verdicts"],
        "critical": ["visible_tests", "verdicts", "risk_floor",
                     "heldout_drop"]})

    def setUp(self):
        self.root_ctx = tempfile.TemporaryDirectory()
        self.root = self.root_ctx.name
        self.fx = RepoFixture(self.root)
        self.fx.write("gate-required.json", self.MANIFEST)
        git(self.fx.repo, "add", "-A")
        git(self.fx.repo, "commit", "-q", "-m", "manifest")
        self.fx.branch("task/good", {"app.py":
                       "def add(a, b):\n    return a + b\n\n"
                       "def sub(a, b):\n    return a - b\n"})

    def tearDown(self):
        self.root_ctx.cleanup()

    def gate_kw(self, **kw):
        defaults = dict(repo=self.fx.repo, branch="task/good", base="main",
                        task_profile="routine",
                        required_steps_path="gate-required.json")
        defaults.update(kw)
        return defaults

    def blocking_step(self, report):
        return next(s for s in report["steps"] if not s["ok"])

    def test_missing_required_input_fails_closed(self):
        report = gate.run_gate(**self.gate_kw())  # no test_cmd, no verdicts
        self.assertFalse(report["ok"])
        blocked = self.blocking_step(report)
        self.assertEqual(blocked["step"], "required_steps")
        self.assertIn("visible_tests", blocked["detail"])
        self.assertIn("fail-closed", blocked["detail"])

    def test_supplied_required_inputs_proceed(self):
        report = gate.run_gate(**self.gate_kw(
            test_cmd=TEST_CMD,
            verdict_dir=make_panel(self.root, [("correctness", "PASS")])))
        self.assertTrue(report["ok"], report["steps"])
        self.assertEqual(report["steps"][0]["step"], "required_steps")
        self.assertTrue(report["steps"][0]["ok"])

    def test_critical_profile_requires_vault_too(self):
        report = gate.run_gate(**self.gate_kw(
            task_profile="critical", test_cmd=TEST_CMD,
            verdict_dir=make_panel(self.root, [("correctness", "PASS")]),
            floor_config_path="floors.json"))
        self.assertFalse(report["ok"])
        self.assertIn("heldout_drop", self.blocking_step(report)["detail"])

    def test_unreadable_manifest_fails_closed(self):
        report = gate.run_gate(**self.gate_kw(
            required_steps_path="ghost.json", test_cmd=TEST_CMD))
        self.assertFalse(report["ok"])
        self.assertIn("cannot load", self.blocking_step(report)["detail"])

    def test_tampered_manifest_on_branch_is_ignored(self):
        # the branch under test empties its own manifest — the gate must read
        # the ratified base ref's copy and still require the steps
        self.fx.branch("task/tamper", {"gate-required.json": "{}"})
        report = gate.run_gate(**self.gate_kw(branch="task/tamper"))
        self.assertFalse(report["ok"])
        self.assertEqual(self.blocking_step(report)["step"], "required_steps")

    def test_malformed_manifest_is_loud(self):
        self.fx.write("bad.json", json.dumps({"routine": ["no_such_step"]}))
        git(self.fx.repo, "add", "-A")
        git(self.fx.repo, "commit", "-q", "-m", "bad manifest")
        report = gate.run_gate(**self.gate_kw(
            required_steps_path="bad.json", test_cmd=TEST_CMD))
        self.assertFalse(report["ok"])
        self.assertIn("unknown step", self.blocking_step(report)["detail"])

    def test_validate_required_steps_rejects_bad_shapes(self):
        for doc in (["routine"], {"ghost_profile": []},
                    {"routine": "visible_tests"}):
            with self.assertRaises(gate.GateError):
                gate.validate_required_steps(doc)

    def test_repo_default_manifest_is_valid_and_total(self):
        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "harness", "config", "gate-required-steps.json")
        with open(cfg_path) as fh:
            manifest = gate.validate_required_steps(json.load(fh))
        from harness.runlog import PROFILES
        self.assertEqual(set(manifest), set(PROFILES))
        for profile in PROFILES:
            self.assertIn("visible_tests", manifest[profile])
            self.assertIn("verdicts", manifest[profile])


if __name__ == "__main__":
    unittest.main()
