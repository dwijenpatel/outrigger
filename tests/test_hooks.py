"""Tests for harness.hooks + the hooks/ scripts (C1–C3, design §5.2/§7)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")


def run_hook(script, stdin_doc, args=()):
    return subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, script), *args],
        input=json.dumps(stdin_doc), capture_output=True, text=True, timeout=30)


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def make_repo(root):
    git_env_repo = os.path.join(root, "repo")
    os.makedirs(git_env_repo)
    git(git_env_repo, "init", "-q", "-b", "main")
    git(git_env_repo, "config", "user.email", "t@t")
    git(git_env_repo, "config", "user.name", "t")
    return git_env_repo


class GlobTests(unittest.TestCase):
    def test_double_star_crosses_separators(self):
        self.assertTrue(hooks.path_matches("harness/config/tiers.json", "harness/**"))
        self.assertTrue(hooks.path_matches("a/b/c/CLAUDE.md", "**/CLAUDE.md"))
        self.assertFalse(hooks.path_matches("src/app.py", "harness/**"))

    def test_single_star_stays_within_segment(self):
        self.assertTrue(hooks.path_matches("hooks/x.py", "hooks/*.py"))
        self.assertFalse(hooks.path_matches("hooks/sub/x.py", "hooks/*.py"))


class PrefixEditTests(unittest.TestCase):
    def test_prefix_files_warn(self):
        for path in ("CLAUDE.md", ".claude/settings.json", "sub/dir/CLAUDE.md",
                     ".claude/agents/implementer.md"):
            got = hooks.check_prefix_edit("Edit", {"file_path": path})
            self.assertIsNotNone(got, path)
            self.assertIn("frozen prompt prefix", got)

    def test_ordinary_files_pass_silently(self):
        self.assertIsNone(hooks.check_prefix_edit("Edit", {"file_path": "src/x.py"}))

    def test_non_edit_tools_ignored(self):
        self.assertIsNone(hooks.check_prefix_edit("Bash", {"command": "vi CLAUDE.md"}))

    def test_script_is_advisory_never_blocks(self):
        warn = run_hook("prefix_edit_warn.py",
                        {"tool_name": "Edit", "tool_input": {"file_path": "CLAUDE.md"}})
        self.assertEqual(warn.returncode, 0)
        self.assertIn("prefix-edit warning", warn.stderr)
        # even garbage input is fail-open for the advisory layer
        broken = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "prefix_edit_warn.py")],
            input="not json", capture_output=True, text=True, timeout=30)
        self.assertEqual(broken.returncode, 0)


class DestructiveGitTests(unittest.TestCase):
    def test_destructive_commands_flagged(self):
        bad = ("git push --force origin main",
               "git push -f",
               "git reset --hard HEAD~3",
               "git clean -fd",
               "git checkout -- .",
               "git branch -D feature",
               "git push origin --delete feature",
               "git filter-branch --all",
               "git stash drop",
               "git rebase -i HEAD~5")
        for cmd in bad:
            self.assertIsNotNone(hooks.check_destructive_git(cmd), cmd)

    def test_safe_git_passes(self):
        good = ("git status", "git push origin feat/x", "git checkout -b feat/y",
                "git reset HEAD file.py", "git stash", "git branch -d merged",
                "git log --oneline", "git clean -n")
        for cmd in good:
            self.assertIsNone(hooks.check_destructive_git(cmd), cmd)

    def test_non_git_commands_ignored(self):
        self.assertIsNone(hooks.check_destructive_git("rm -rf build/"))

    def test_script_blocks_with_exit_2(self):
        out = run_hook("git_guard.py", {"tool_name": "Bash",
                                        "tool_input": {"command": "git push -f"}})
        self.assertEqual(out.returncode, 2)
        self.assertIn("destructive git blocked", out.stderr)

    def test_script_fails_closed_on_garbage(self):
        broken = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "git_guard.py")],
            input="not json", capture_output=True, text=True, timeout=30)
        self.assertEqual(broken.returncode, 2)
        self.assertIn("fail-closed", broken.stderr)


class MachineryPathTests(unittest.TestCase):
    def test_task_branch_cannot_edit_machinery(self):
        got = hooks.check_machinery_paths(
            "Edit", {"file_path": "harness/governor.py"}, branch="task/t42")
        self.assertIn("machinery-path edit blocked", got)

    def test_allowed_branches_may_edit_machinery(self):
        for branch in ("main", "feat/b4-x", "chore/plan", "docs/amend"):
            self.assertIsNone(hooks.check_machinery_paths(
                "Edit", {"file_path": "harness/governor.py"}, branch=branch),
                branch)

    def test_unknown_branch_fails_closed(self):
        got = hooks.check_machinery_paths(
            "Write", {"file_path": "hooks/git_guard.py"}, branch=None)
        self.assertIn("fail-closed", got)

    def test_non_machinery_paths_pass_on_task_branches(self):
        self.assertIsNone(hooks.check_machinery_paths(
            "Edit", {"file_path": "src/app.py"}, branch="task/t42"))
        self.assertIsNone(hooks.check_machinery_paths(
            "Edit", {"file_path": "pilot/greenlane/app/models.py"},
            branch="task/GL4"))

    def test_task_branch_cannot_edit_the_ratified_plan(self):
        # I6/P2-2: the spec is the panel's immutable shared context — an
        # implementer must not be able to edit the contract it is judged
        # against; plan changes go through ratification, not task branches
        for path in ("plan/specs/GL5-schedules-generator.md",
                     "plan/tasks.json", "plan/floors.json"):
            got = hooks.check_machinery_paths(
                "Edit", {"file_path": path}, branch="task/GL5")
            self.assertIn("machinery-path edit blocked", got, path)

    def test_worker_settings_deny_the_plan_dir(self):
        from harness import loop
        denies = loop.worker_settings()["permissions"]["deny"]
        self.assertIn("Edit(plan/**)", denies)
        self.assertIn("Write(plan/**)", denies)


class RatifiedConfigTests(unittest.TestCase):
    def test_config_read_from_ratified_ref_not_working_tree(self):
        with tempfile.TemporaryDirectory() as root:
            repo = make_repo(root)
            cfg = os.path.join(repo, "gate.json")
            with open(cfg, "w") as fh:
                json.dump({"floors": [{"glob": "billing/**",
                                       "min_profile": "critical"}]}, fh)
            git(repo, "add", "gate.json")
            git(repo, "commit", "-q", "-m", "ratified config")
            # task branch tampers with the config in its working tree
            git(repo, "checkout", "-q", "-b", "task/evil")
            with open(cfg, "w") as fh:
                json.dump({"floors": []}, fh)
            doc = hooks.load_ratified_config(repo, "gate.json", ref="main")
            self.assertEqual(doc["floors"][0]["min_profile"], "critical")

    def test_missing_config_returns_none_for_fail_closed_caller(self):
        with tempfile.TemporaryDirectory() as root:
            repo = make_repo(root)
            self.assertIsNone(hooks.load_ratified_config(repo, "nope.json"))

    def test_non_object_config_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            repo = make_repo(root)
            with open(os.path.join(repo, "bad.json"), "w") as fh:
                fh.write("[1, 2]")
            git(repo, "add", "bad.json")
            git(repo, "commit", "-q", "-m", "x")
            self.assertIsNone(hooks.load_ratified_config(repo, "bad.json"))


class RiskFloorTests(unittest.TestCase):
    FLOORS = [{"glob": "billing/**", "min_profile": "critical"},
              {"glob": "auth/**", "min_profile": "high"}]

    def test_floor_map_validation_is_loud(self):
        for doc in ({"not": "a list"}, [{"glob": ""}],
                    [{"glob": "x", "min_profile": "mega"}]):
            with self.assertRaises(hooks.HookError):
                hooks.validate_floor_map(doc)

    def test_mistagged_task_cannot_merge_cheaply(self):
        got = hooks.check_risk_floor(
            "routine", ["billing/stripe.py", "README.md"], self.FLOORS)
        self.assertFalse(got["ok"])
        self.assertEqual(got["required"], "critical")

    def test_highest_floor_wins_across_paths(self):
        got = hooks.check_risk_floor(
            "high", ["auth/session.py", "billing/plan.py"], self.FLOORS)
        self.assertFalse(got["ok"])         # billing demands critical
        self.assertEqual(got["required"], "critical")

    def test_adequate_profile_passes(self):
        got = hooks.check_risk_floor("critical", ["billing/stripe.py"], self.FLOORS)
        self.assertTrue(got["ok"])

    def test_unfloored_paths_pass_any_profile(self):
        got = hooks.check_risk_floor("routine", ["src/ui/list.tsx"], self.FLOORS)
        self.assertTrue(got["ok"])
        self.assertIsNone(got["required"])

    def test_gate_script_end_to_end(self):
        with tempfile.TemporaryDirectory() as root:
            repo = make_repo(root)
            with open(os.path.join(repo, "floors.json"), "w") as fh:
                json.dump({"floors": self.FLOORS}, fh)
            git(repo, "add", "floors.json")
            git(repo, "commit", "-q", "-m", "floors")
            base = [sys.executable, os.path.join(HOOKS_DIR, "risk_floor_check.py"),
                    "--floor-config", "floors.json", "--ref", "main",
                    "--repo", repo]
            violate = subprocess.run(
                base + ["--profile", "routine", "billing/stripe.py"],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(violate.returncode, 2)
            ok = subprocess.run(
                base + ["--profile", "critical", "billing/stripe.py"],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(ok.returncode, 0)
            # unloadable config -> fail closed
            missing = subprocess.run(
                [sys.executable, os.path.join(HOOKS_DIR, "risk_floor_check.py"),
                 "--floor-config", "ghost.json", "--repo", repo,
                 "--profile", "critical"],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
