"""Tests for harness.worktrees (G1) — pool, durable leases, landed semantics."""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import worktrees
from harness.worktrees import Pool, WorktreeError


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                         text=True)
    if out.returncode != 0:
        raise AssertionError(f"git {args}: {out.stderr}")
    return out.stdout


class WorktreeBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.dir.name, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        with open(os.path.join(self.repo, "f.txt"), "w") as fh:
            fh.write("seed\n")
        git(self.repo, "add", "f.txt")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.pool = Pool(self.repo, os.path.join(self.dir.name, "pool"),
                         max_members=2)

    def tearDown(self):
        self.dir.cleanup()

    def feature_branch(self, name, content, merge=False, squash=False):
        git(self.repo, "checkout", "-q", "-b", name)
        with open(os.path.join(self.repo, f"{name}.txt"), "w") as fh:
            fh.write(content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", f"work on {name}")
        git(self.repo, "checkout", "-q", "main")
        if merge:
            git(self.repo, "merge", "-q", "--no-ff", name, "-m", f"merge {name}")
        if squash:
            # land the same patch under a different SHA (like a squash-merge):
            # cherry-pick then amend the message so ancestry can't match
            git(self.repo, "cherry-pick", name)
            git(self.repo, "commit", "-q", "--amend", "-m",
                f"squash-landed {name}")


class PoolTests(WorktreeBase):
    def test_acquire_creates_and_leases(self):
        path = self.pool.acquire("main", "pipeline-1")
        self.assertTrue(os.path.isfile(os.path.join(path, "f.txt")))
        self.assertEqual(self.pool.status()["leased"][path], "pipeline-1")

    def test_leases_are_durable_across_pool_instances(self):
        path = self.pool.acquire("main", "pipeline-1")
        fresh = Pool(self.repo, self.pool.pool_dir, max_members=2)
        # the fresh instance (a "new process") still sees the lease
        self.assertEqual(fresh.status()["leased"][path], "pipeline-1")
        other = fresh.acquire("main", "pipeline-2")
        self.assertNotEqual(other, path)  # never hands out a leased member

    def test_release_then_reuse_keeps_env_warm(self):
        path = self.pool.acquire("main", "p1")
        cache = os.path.join(path, "node_modules_stand_in")
        os.makedirs(cache)  # untracked build cache
        self.pool.release(path)
        again = self.pool.acquire("main", "p2")
        self.assertEqual(again, path)             # reused, not recreated
        self.assertTrue(os.path.isdir(cache))     # env survived (the point)

    def test_pool_cap_refuses_loudly(self):
        self.pool.acquire("main", "p1")
        self.pool.acquire("main", "p2")
        with self.assertRaises(WorktreeError):
            self.pool.acquire("main", "p3")

    def test_dirty_member_never_silently_reused(self):
        path = self.pool.acquire("main", "p1")
        with open(os.path.join(path, "f.txt"), "a") as fh:
            fh.write("dirty edit\n")
        self.pool.release(path)
        other = self.pool.acquire("main", "p2")
        self.assertNotEqual(other, path)  # grew the pool instead

    def test_corrupt_state_is_loud(self):
        self.pool.acquire("main", "p1")
        with open(self.pool.state_path, "w") as fh:
            fh.write("{broken")
        with self.assertRaises(WorktreeError):
            self.pool.status()


class LandedTests(WorktreeBase):
    def test_merged_branch_is_landed_by_ancestry(self):
        self.feature_branch("feat-a", "a\n", merge=True)
        got = worktrees.landed(self.repo, "feat-a")
        self.assertTrue(got["landed"])
        self.assertEqual(got["how"], "ancestor")

    def test_squash_equivalent_is_landed_by_patch_id(self):
        self.feature_branch("feat-b", "b\n", squash=True)
        got = worktrees.landed(self.repo, "feat-b")
        self.assertTrue(got["landed"])
        self.assertIn("patch-id", got["how"])

    def test_unmerged_branch_is_not_landed(self):
        self.feature_branch("feat-c", "c\n")
        got = worktrees.landed(self.repo, "feat-c")
        self.assertFalse(got["landed"])

    def test_missing_ref_is_loud(self):
        with self.assertRaises(WorktreeError):
            worktrees.landed(self.repo, "ghost-branch")


class TeardownTests(WorktreeBase):
    def test_leased_member_refused_without_flag(self):
        path = self.pool.acquire("main", "p1")
        with self.assertRaises(WorktreeError) as ctx:
            self.pool.teardown(path)
        self.assertIn("include_leased", str(ctx.exception))
        got = self.pool.teardown(path, include_leased=True)
        self.assertEqual(got["removed"], path)

    def test_unlanded_work_refused_without_flag(self):
        self.feature_branch("feat-d", "d\n")  # unmerged
        path = self.pool.acquire("feat-d", "p1")
        self.pool.release(path)
        with self.assertRaises(WorktreeError) as ctx:
            self.pool.teardown(path)
        self.assertIn("include_unlanded", str(ctx.exception))
        got = self.pool.teardown(path, include_unlanded=True)
        self.assertIn(path, got["removed"])
        self.assertTrue(got["accepted_risks"])

    def test_landed_clean_member_tears_down_freely(self):
        path = self.pool.acquire("main", "p1")
        self.pool.release(path)
        got = self.pool.teardown(path)
        self.assertEqual(got["accepted_risks"], [])
        self.assertEqual(self.pool.status()["members"], 0)

    def test_non_member_refused(self):
        with self.assertRaises(WorktreeError):
            self.pool.teardown("/not/a/member")


if __name__ == "__main__":
    unittest.main()
