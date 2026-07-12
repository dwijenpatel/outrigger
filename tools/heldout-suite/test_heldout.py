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


PASSING_TEST = """\
import unittest
import notes

class Regression(unittest.TestCase):
    def test_version_attribute_exists(self):
        self.assertTrue(hasattr(notes, "VERSION"))
"""

FAILING_TEST = """\
import unittest
import notes

class NewBehavior(unittest.TestCase):
    def test_tags_enabled(self):
        self.assertTrue(getattr(notes, "TAGS_ENABLED", False))
"""

IMPORT_ERROR_TEST = """\
import notes_tags  # does not exist on base
"""


class SuiteFixture(MaterializeFixture):
    """A materialized workspace whose suite the tests author programmatically."""

    def setUp(self):
        super().setUp()
        self.materialize()
        self.workspace = os.path.join(self.out, "tags-add")
        self.suite = os.path.join(self.workspace, "suite")

    def author(self, **files):
        for name, content in files.items():
            with open(os.path.join(self.suite, name), "w") as fh:
                fh.write(content)

    def validate(self, expect=0):
        proc = heldout("validate", "--workspace", self.workspace, "--repo", self.repo)
        self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        return proc

    def seal(self, *flags, expect=0):
        proc = heldout("seal", "--workspace", self.workspace, "--repo", self.repo, *flags)
        self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        return proc

    def verify(self, expect=0):
        proc = heldout("verify", "--workspace", self.workspace)
        self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        return proc

    def read_manifest(self):
        with open(os.path.join(self.workspace, "manifest.json")) as fh:
            return json.load(fh)


class ValidateAndSealTests(SuiteFixture):
    def test_all_pass_suite_violates_policy_and_refuses_seal(self):
        self.author(**{"test_regression.py": PASSING_TEST})
        proc = self.validate(expect=1)
        self.assertIn("fails-on-base policy violated", proc.stderr)
        proc = self.seal(expect=1)
        self.assertIn("seal refused", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "manifest.json")))

    def test_teeth_suite_validates_seals_with_split_and_anchor(self):
        self.author(**{"test_regression.py": PASSING_TEST, "test_new.py": FAILING_TEST})
        proc = self.validate()
        record = json.loads(proc.stdout)
        self.assertEqual(record["split"], {"failed": 1, "errored": 0, "passed": 1})
        self.assertEqual(record["base_sha"], self.base_sha)

        proc = self.seal()
        summary = json.loads(proc.stdout)
        self.assertRegex(summary["manifest_sha256"], r"^[0-9a-f]{64}$")
        manifest = self.read_manifest()
        self.assertEqual(manifest["fails_on_base"], {"failed": 1, "errored": 0, "passed": 1})
        self.assertEqual(manifest["base_sha"], self.base_sha)
        self.assertEqual(sorted(manifest["files"]), ["test_new.py", "test_regression.py"])
        # spec_hash is the hash of the exact task.json bytes
        import hashlib
        with open(os.path.join(self.workspace, "authoring", "task.json"), "rb") as fh:
            self.assertEqual(manifest["spec_hash"], hashlib.sha256(fh.read()).hexdigest())
        # deny-fragment denies the whole workspace, absolutely
        with open(os.path.join(self.workspace, "deny-fragment.json")) as fh:
            deny = json.load(fh)
        # the fragment carries the REAL path (deny rules resolve symlinks)
        self.assertEqual(deny["deny_read"], [os.path.realpath(self.workspace)])
        self.assertTrue(os.path.isabs(deny["deny_read"][0]))

    def test_import_error_counts_as_failing(self):
        self.author(**{"test_broken.py": IMPORT_ERROR_TEST})
        proc = self.validate()
        record = json.loads(proc.stdout)
        self.assertGreaterEqual(record["split"]["errored"], 1)

    def test_reseal_requires_retire_and_preserves_evidence(self):
        self.author(**{"test_new.py": FAILING_TEST})
        self.seal()
        proc = self.seal(expect=1)
        self.assertIn("--retire", proc.stderr)

        old_manifest = self.read_manifest()
        self.author(**{"test_new.py": FAILING_TEST + "\n# edited\n"})
        self.seal("--retire")
        retired_root = os.path.join(self.workspace, "retired")
        [stamp] = os.listdir(retired_root)
        with open(os.path.join(retired_root, stamp, "manifest.json")) as fh:
            archived = json.load(fh)
        self.assertEqual(archived, old_manifest)
        self.assertTrue(
            os.path.isfile(os.path.join(retired_root, stamp, "suite-snapshot", "test_new.py"))
        )

    def test_adjudicated_reseal_records_the_block(self):
        self.author(**{"test_new.py": FAILING_TEST})
        self.seal()
        self.author(**{"test_new.py": FAILING_TEST + "\n# operator fix\n"})
        self.seal(
            "--retire",
            "--adjudicated-by", "dwijen",
            "--adjudication-note", "test asserted beyond the spec",
        )
        adjudication = self.read_manifest()["adjudication"]
        self.assertEqual(adjudication["by"], "dwijen")
        self.assertIn("beyond the spec", adjudication["note"])
        # flags go together
        proc = self.seal("--retire", "--adjudicated-by", "dwijen", expect=2)
        self.assertIn("go together", proc.stderr)

    def test_worktrees_cleaned_up(self):
        self.author(**{"test_new.py": FAILING_TEST})
        self.validate()
        listing = sh(self.repo, "git", "worktree", "list", "--porcelain")
        self.assertEqual(listing.count("worktree "), 1)


class VerifyTests(SuiteFixture):
    def setUp(self):
        super().setUp()
        self.author(**{"test_regression.py": PASSING_TEST, "test_new.py": FAILING_TEST})
        self.seal()

    def test_fresh_seal_verifies(self):
        self.verify()

    def test_modified_test_file_diverges(self):
        self.author(**{"test_new.py": FAILING_TEST + "\n# tampered\n"})
        proc = self.verify(expect=1)
        self.assertIn("changed since sealing", proc.stdout)

    def test_extra_file_diverges(self):
        self.author(**{"test_sneaky.py": PASSING_TEST})
        proc = self.verify(expect=1)
        self.assertIn("extra suite file", proc.stdout)

    def test_missing_file_diverges(self):
        os.remove(os.path.join(self.suite, "test_new.py"))
        proc = self.verify(expect=1)
        self.assertIn("missing suite file", proc.stdout)

    def test_modified_spec_diverges(self):
        task_json = os.path.join(self.workspace, "authoring", "task.json")
        with open(task_json) as fh:
            inputs = json.load(fh)
        inputs["goal"] = "quietly different"
        with open(task_json, "w") as fh:
            json.dump(inputs, fh)
        proc = self.verify(expect=1)
        self.assertIn("spec changed since sealing", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
