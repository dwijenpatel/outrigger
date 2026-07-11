"""merge-gate tests — merged-tree judging, conflicts, timeouts, stamp freshness.

The last test class is the B-4 regression suite: a stamp must go stale the
moment the base moves, because the gate only ever proved the merge against
base-as-of-gating.

Run: python3 tools/merge-gate/test_gate.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "gate.py")


def sh(cwd, *argv):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    assert proc.returncode == 0, f"{argv}: {proc.stderr}"
    return proc.stdout


def gate(*argv):
    return subprocess.run(
        [sys.executable, GATE, *argv], capture_output=True, text=True
    )


class GateFixture(unittest.TestCase):
    """A repo where main advanced AFTER the feature branches were cut, so a
    merged-tree check can prove the gate saw base-as-of-now, not the fork point."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.mkdir(self.repo)
        # the report lives OUTSIDE the repo so branch switches never touch it
        self.report = os.path.join(self.tmp.name, "report.json")
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "config", "user.name", "gate-test")
        sh(self.repo, "git", "config", "user.email", "gate-test@example.invalid")
        self.write("value.txt", "1\n")
        self.commit("A: value=1")
        # Branches cut at A:
        sh(self.repo, "git", "branch", "feat-pass")
        sh(self.repo, "git", "branch", "feat-fail")
        sh(self.repo, "git", "branch", "feat-conflict")
        # feature work
        sh(self.repo, "git", "checkout", "-q", "feat-pass")
        self.write("feature.txt", "ok\n")
        self.commit("feat-pass: add feature")
        sh(self.repo, "git", "checkout", "-q", "feat-conflict")
        self.write("value.txt", "2\n")
        self.commit("feat-conflict: value=2")
        # main advances past the fork point (value=3) — the merged tree must
        # contain BOTH value=3 and the feature file.
        sh(self.repo, "git", "checkout", "-q", "main")
        self.write("value.txt", "3\n")
        self.commit("B: value=3")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        with open(os.path.join(self.repo, name), "w") as fh:
            fh.write(content)

    def commit(self, msg):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "-m", msg)

    def read_report(self):
        with open(self.report) as fh:
            return json.load(fh)


class RunTests(GateFixture):
    def test_pass_judges_the_merged_tree(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "grep -q 3 value.txt",   # only true on base-as-of-NOW
            "--check", "test -f feature.txt",   # only true with the change
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = self.read_report()
        self.assertTrue(report["ok"])
        self.assertTrue(report["merge"]["performed"])
        self.assertEqual(len(report["checks"]), 2)
        self.assertTrue(all(c["exit"] == 0 for c in report["checks"]))
        # the stamp binds BOTH sides
        for side in ("base", "source"):
            self.assertRegex(report[side]["sha"], r"^[0-9a-f]{40}$")

    def test_any_failing_check_fails_the_gate(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "test -f feature.txt",
            "--check", "test -f nope.txt",
        )
        self.assertEqual(proc.returncode, 1)
        report = self.read_report()
        self.assertFalse(report["ok"])
        exits = [c["exit"] for c in report["checks"]]
        self.assertIn(0, exits)
        self.assertIn(1, exits)

    def test_conflict_is_a_fail_with_named_files_and_no_checks_run(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-conflict", "--report", self.report,
            "--check", "true",
        )
        self.assertEqual(proc.returncode, 1)
        report = self.read_report()
        self.assertFalse(report["ok"])
        self.assertEqual(report["merge"]["conflicts"], ["value.txt"])
        self.assertEqual(report["checks"], [])

    def test_hung_verifier_is_a_fail_not_a_wait(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--timeout", "1", "--check", "sleep 5",
        )
        self.assertEqual(proc.returncode, 1)
        [check] = self.read_report()["checks"]
        self.assertTrue(check["timed_out"])
        self.assertIsNone(check["exit"])
        self.assertLess(check["duration_s"], 4)

    def test_dirty_main_worktree_does_not_leak_into_the_judged_tree(self):
        self.write("uncommitted.txt", "dirty\n")  # never committed
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "test ! -f uncommitted.txt",
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_zero_checks_is_a_usage_error_never_a_pass(self):
        proc = gate("run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report)
        self.assertEqual(proc.returncode, 2)

    def test_unresolvable_ref_is_env_error(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "no-such-branch", "--report", self.report,
            "--check", "true",
        )
        self.assertEqual(proc.returncode, 2)

    def test_worktrees_are_cleaned_up(self):
        gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "true",
        )
        listing = sh(self.repo, "git", "worktree", "list", "--porcelain")
        self.assertEqual(listing.count("worktree "), 1)  # only the main worktree


class VerifyTests(GateFixture):
    def gate_pass(self):
        proc = gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "test -f feature.txt",
        )
        assert proc.returncode == 0

    def test_fresh_stamp_verifies(self):
        self.gate_pass()
        proc = gate("verify", "--report", self.report, "--repo", self.repo)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(json.loads(proc.stdout)["fresh"])

    def test_base_move_goes_stale__the_B4_regression(self):
        self.gate_pass()
        self.write("value.txt", "4\n")
        self.commit("C: base moves after gating")
        proc = gate("verify", "--report", self.report, "--repo", self.repo)
        self.assertEqual(proc.returncode, 1)
        result = json.loads(proc.stdout)
        self.assertFalse(result["fresh"])
        self.assertTrue(any("base moved since gating" in r for r in result["reasons"]))

    def test_source_move_goes_stale(self):
        self.gate_pass()
        sh(self.repo, "git", "checkout", "-q", "feat-pass")
        self.write("feature.txt", "changed after gating\n")
        self.commit("post-gate tamper")
        sh(self.repo, "git", "checkout", "-q", "main")
        proc = gate("verify", "--report", self.report, "--repo", self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(
            any("source moved" in r for r in json.loads(proc.stdout)["reasons"])
        )

    def test_fail_stamp_never_verifies(self):
        gate(
            "run", "--repo", self.repo, "--ref", "feat-pass", "--report", self.report,
            "--check", "false",
        )
        proc = gate("verify", "--report", self.report, "--repo", self.repo)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("report is not a PASS", proc.stdout)

    def test_malformed_report_is_env_error(self):
        with open(self.report, "w") as fh:
            fh.write('{"tool": "merge-gate"}')
        proc = gate("verify", "--report", self.report, "--repo", self.repo)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
