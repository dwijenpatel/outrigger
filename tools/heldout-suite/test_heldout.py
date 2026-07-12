"""heldout-suite tests — task 1 (materialize); tasks 2+ extend this file.

Run: python3 tools/heldout-suite/test_heldout.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HELDOUT = os.path.join(HERE, "heldout.py")


def sh(cwd, *argv):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    assert proc.returncode == 0, f"{argv}: {proc.stderr}"
    return proc.stdout


def heldout(*argv):
    return subprocess.run(
        [sys.executable, HELDOUT, *argv], capture_output=True, text=True
    )


PLAN = {
    "contract": 1,
    "goal": "Add tags to the notes CLI.",
    "non_goals": ["No storage-engine change."],
    "constraints": ["Existing notes.json entries stay readable."],
    "decisions": [{"q": "Tag syntax?", "a": "--tag, repeatable."}],
    "tasks": [
        {
            "id": "tags-add",
            "title": "Tag support on add",
            "spec": "Support --tag (repeatable) on the add command; persist tags as a list.",
            "checks": ["python3 test_notes.py"],
            "provides": ["tagged-notes"],
        },
        {
            "id": "tags-list",
            "title": "Filter list by tag",
            "spec": "SIBLING-SECRET: list --tag X filters notes.",
            "depends_on": ["tags-add"],
            "requires": ["tagged-notes"],
            "checks": ["python3 test_notes.py"],
        },
    ],
}


class MaterializeFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.repo = os.path.join(root, "repo")
        os.mkdir(self.repo)
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "config", "user.name", "t")
        sh(self.repo, "git", "config", "user.email", "t@example.invalid")
        with open(os.path.join(self.repo, "notes.py"), "w") as fh:
            fh.write("VERSION = 1\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "-m", "base")
        self.base_sha = sh(self.repo, "git", "rev-parse", "HEAD").strip()

        self.plan = os.path.join(root, "plan.json")
        with open(self.plan, "w") as fh:
            json.dump(PLAN, fh)
        self.out = os.path.join(root, "heldout")

    def tearDown(self):
        self.tmp.cleanup()

    def materialize(self, task="tags-add", out=None, repo=None, expect=0):
        proc = heldout(
            "materialize",
            "--plan", self.plan,
            "--task", task,
            "--repo", repo or self.repo,
            "--base", "main",
            "--out", out or self.out,
        )
        self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        return proc


class MaterializeTests(MaterializeFixture):
    def test_workspace_contents_and_scope(self):
        proc = self.materialize()
        summary = json.loads(proc.stdout)
        workspace = summary["workspace"]
        self.assertEqual(summary["base"]["sha"], self.base_sha)

        with open(os.path.join(workspace, "authoring", "task.json")) as fh:
            raw = fh.read()
        inputs = json.loads(raw)
        # this task's full entry + the plan preamble
        self.assertEqual(inputs["task"]["id"], "tags-add")
        self.assertEqual(inputs["goal"], PLAN["goal"])
        self.assertEqual(inputs["decisions"], PLAN["decisions"])
        self.assertEqual(inputs["base"]["sha"], self.base_sha)
        # never sibling tasks (decision 5): the sibling's marker must be absent
        self.assertNotIn("SIBLING-SECRET", raw)
        self.assertNotIn("tags-list", raw)
        # empty suite dir, ready for the author
        self.assertEqual(os.listdir(os.path.join(workspace, "suite")), [])
        # the generated pointer
        with open(os.path.join(workspace, "authoring", "AUTHORING.md")) as fh:
            authoring = fh.read()
        self.assertIn("suite/", authoring)
        self.assertIn("ROLE.md", authoring)
        self.assertIn(self.base_sha, authoring)

    def test_refuses_out_inside_repo(self):
        proc = self.materialize(out=os.path.join(self.repo, "heldout"), expect=1)
        self.assertIn("inside the target repo", proc.stderr)

    def test_refuses_out_symlinked_into_repo(self):
        link = os.path.join(self.tmp.name, "sneaky")
        os.symlink(os.path.join(self.repo, "hidden"), link)
        proc = self.materialize(out=link, expect=1)
        self.assertIn("inside the target repo", proc.stderr)

    def test_refuses_existing_workspace(self):
        self.materialize()
        proc = self.materialize(expect=1)
        self.assertIn("already exists", proc.stderr)
        self.assertIn("retire", proc.stderr)

    def test_unknown_task_and_bad_plan_are_input_errors(self):
        proc = self.materialize(task="nope", expect=2)
        self.assertIn("not found in plan", proc.stderr)

        with open(self.plan, "w") as fh:
            fh.write('{"contract": 2, "tasks": []}')
        proc = self.materialize(expect=2)
        self.assertIn("contract", proc.stderr)

    def test_not_a_repo_is_input_error(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.mkdir(empty)
        self.materialize(repo=empty, expect=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
