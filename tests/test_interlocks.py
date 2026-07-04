"""Tests for harness.interlocks (H2) — merge + spawn interlocks."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import gate, interlocks
from harness.interlocks import InterlockError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def make_repo(root):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    with open(os.path.join(repo, "x"), "w") as fh:
        fh.write("x\n")
    _git(repo, "add", "x")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "checkout", "-q", "-b", "task/t1")
    with open(os.path.join(repo, "y"), "w") as fh:
        fh.write("y\n")
    _git(repo, "add", "y")
    _git(repo, "commit", "-q", "-m", "work")
    _git(repo, "checkout", "-q", "main")
    return repo


def head_of(repo, ref):
    out = subprocess.run(["git", "-C", repo, "rev-parse", ref],
                         capture_output=True, text=True)
    return out.stdout.strip()


class MergeInterlockTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.dir.name)
        self.stamps = os.path.join(self.dir.name, "state", "gate-stamps")
        self.marker = os.path.join(self.dir.name, "state", "run.marker")

    def tearDown(self):
        self.dir.cleanup()

    def arm(self):
        os.makedirs(os.path.dirname(self.marker), exist_ok=True)
        with open(self.marker, "w") as fh:
            json.dump({"owner": "t", "pid": os.getpid()}, fh)

    def check(self, cmd, **kw):
        return interlocks.check_merge(cmd, self.repo, self.stamps,
                                      self.marker, **kw)

    def stamp(self, ref="task/t1", head=None, now_iso=None):
        return interlocks.write_gate_stamp(
            self.stamps, ref, head or head_of(self.repo, ref), "main",
            ok=True, now_iso=now_iso)

    def test_inert_outside_firing(self):
        self.assertIsNone(self.check("git merge task/t1"))

    def test_non_git_and_non_merge_commands_pass(self):
        self.arm()
        self.assertIsNone(self.check("ls -la"))
        self.assertIsNone(self.check("git status"))
        self.assertIsNone(self.check("git commit -m 'merge later'"))

    def test_unstamped_merge_blocked_in_firing(self):
        self.arm()
        violation = self.check("git merge task/t1")
        self.assertIn("no PASS gate stamp", violation)

    def test_stamped_merge_allowed(self):
        self.arm()
        self.stamp()
        self.assertIsNone(self.check("git merge --no-ff task/t1 -m 'Merge'"))

    def test_flag_value_not_mistaken_for_target(self):
        self.arm()
        self.stamp("task/t1")
        # -m's value must not be read as the merge target
        self.assertIsNone(self.check("git merge -m 'task/other' task/t1"))

    def test_stale_stamp_blocked(self):
        self.arm()
        self.stamp(now_iso="2020-01-01T00:00:00Z")
        violation = self.check("git merge task/t1")
        self.assertIn("stale", violation)

    def test_moved_head_blocked(self):
        self.arm()
        self.stamp(head="0" * 40)
        violation = self.check("git merge task/t1")
        self.assertIn("moved since the gate", violation)

    def test_merge_state_ops_pass(self):
        self.arm()
        self.assertIsNone(self.check("git merge --abort"))
        self.assertIsNone(self.check("git merge --continue"))

    def test_undeterminable_target_fails_closed(self):
        self.arm()
        violation = self.check("git merge")
        self.assertIn("fail-closed", violation)

    def test_unparseable_command_fails_closed_in_firing(self):
        self.arm()
        violation = self.check("git merge 'unbalanced")
        self.assertIn("fail-closed", violation)
        # ...but stays inert outside one
        os.unlink(self.marker)
        self.assertIsNone(self.check("git merge 'unbalanced"))

    def test_push_to_protected_ref_requires_stamp(self):
        self.arm()
        violation = self.check("git push origin task/t1:main")
        self.assertIn("no PASS gate stamp", violation)
        self.stamp()
        self.assertIsNone(self.check("git push origin task/t1:main"))

    def test_push_to_feature_ref_passes(self):
        self.arm()
        self.assertIsNone(self.check("git push origin task/t1"))

    def test_bare_push_on_protected_branch_requires_stamp(self):
        self.arm()  # repo is on main
        violation = self.check("git push")
        self.assertIn("gate stamp", violation)
        interlocks.write_gate_stamp(self.stamps, "main",
                                    head_of(self.repo, "main"), "main", ok=True)
        self.assertIsNone(self.check("git push"))

    def test_write_gate_stamp_refuses_fail_and_pass_only(self):
        self.assertIsNone(interlocks.write_gate_stamp(
            self.stamps, "task/t1", "abc", "main", ok=False))
        self.assertFalse(os.path.exists(
            os.path.join(self.stamps, "task__t1.json")))

    def test_non_string_command_raises(self):
        with self.assertRaises(InterlockError):
            self.check(None)


class SpawnInterlockTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.marker = os.path.join(self.dir.name, "state", "run.marker")
        self.stamp = os.path.join(self.dir.name, "state",
                                  "admission-stamp.json")

    def tearDown(self):
        self.dir.cleanup()

    def arm(self):
        os.makedirs(os.path.dirname(self.marker), exist_ok=True)
        with open(self.marker, "w") as fh:
            json.dump({"owner": "t", "pid": os.getpid()}, fh)

    def check(self, tool="Task", tool_input=None, **kw):
        return interlocks.check_spawn(tool, tool_input or {}, self.marker,
                                      self.stamp, **kw)

    def test_inert_outside_firing(self):
        self.assertIsNone(self.check())

    def test_non_spawn_tools_pass(self):
        self.arm()
        self.assertIsNone(self.check("Read"))
        self.assertIsNone(self.check(
            "Bash", {"command": "python3 -m harness.governor"}))

    def test_task_spawn_without_stamp_blocked(self):
        self.arm()
        violation = self.check()
        self.assertIn("no admission stamp", violation)

    def test_headless_claude_spawn_without_stamp_blocked(self):
        self.arm()
        violation = self.check("Bash", {"command": "claude -p 'do task'"})
        self.assertIn("no admission stamp", violation)

    def test_fresh_stamp_passes(self):
        self.arm()
        interlocks.write_admission_stamp(self.stamp, {"task_id": "t1"})
        self.assertIsNone(self.check())

    def test_stale_stamp_blocked(self):
        self.arm()
        interlocks.write_admission_stamp(self.stamp, {"task_id": "t1"},
                                         now_iso="2020-01-01T00:00:00Z")
        violation = self.check()
        self.assertIn("stale", violation)

    def test_freshness_boundary_uses_injected_now(self):
        self.arm()
        doc = interlocks.write_admission_stamp(self.stamp, {"task_id": "t1"})
        anchor = interlocks._iso_to_epoch(doc["ts"])
        self.assertIsNone(self.check(now_ts=anchor + 899))
        self.assertIsNotNone(self.check(now_ts=anchor + 901))

    def test_non_admit_stamp_blocked(self):
        self.arm()
        os.makedirs(os.path.dirname(self.stamp), exist_ok=True)
        with open(self.stamp, "w") as fh:
            json.dump({"decision": "defer", "ts": "2100-01-01T00:00:00Z"}, fh)
        violation = self.check(now_ts=time.time())
        self.assertIn("does not record an admit", violation)


class GateStampIntegrationTests(unittest.TestCase):
    def test_gate_pass_writes_stamp_fail_does_not(self):
        with tempfile.TemporaryDirectory() as root:
            repo = make_repo(root)
            stamps = os.path.join(root, "stamps")
            report = gate.run_gate(repo, "task/t1", base="main",
                                   stamp_dir=stamps)
            self.assertTrue(report["ok"])
            stamp = interlocks.read_gate_stamp(stamps, "task/t1")
            self.assertEqual(stamp["head"], head_of(repo, "task/t1"))
            # a failing gate (dirty tree) leaves no stamp
            _git(repo, "checkout", "-q", "task/t1")
            with open(os.path.join(repo, "z"), "w") as fh:
                fh.write("dirty\n")
            with open(os.path.join(repo, "z"), "a"):
                pass
            os.makedirs(os.path.join(root, "stamps2"), exist_ok=True)
            report2 = gate.run_gate(repo, "task/t1", base="main",
                                    stamp_dir=os.path.join(root, "stamps2"))
            self.assertFalse(report2["ok"])
            self.assertIsNone(interlocks.read_gate_stamp(
                os.path.join(root, "stamps2"), "task/t1"))


if __name__ == "__main__":
    unittest.main()
