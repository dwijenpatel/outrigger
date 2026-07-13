"""shadow-pilot tests — the whole comparison flow through the mock launcher
(no AI, no network, no quota). Run: python3 tools/shadow-pilot/test_shadow.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHADOW = os.path.join(HERE, "shadow.py")
MOCK = os.path.join(os.path.dirname(HERE), "exec-loop", "launchers", "mock.py")

ARBITER_AUTHOR = """\
mkdir -p suite
cat > suite/test_arbiter.py <<'PY'
import unittest
import notes

class NewBehavior(unittest.TestCase):
    def test_tags_flag_present(self):
        self.assertTrue(getattr(notes, "TAGS_ENABLED", False))

class Regression(unittest.TestCase):
    def test_version_survives(self):
        self.assertTrue(hasattr(notes, "VERSION"))
PY
"""

SHADOW_GOOD = """\
printf '\\nTAGS_ENABLED = True\\n' >> notes.py
git add -A
git commit -qm "shadow: add tags flag"
"""

SHADOW_WRONG = """\
printf '# looks busy, changes nothing\\n' >> README.md
git add -A
git commit -qm "shadow: cosmetic"
"""

SHADOW_NO_COMMIT = """\
printf '\\nTAGS_ENABLED = True\\n' >> notes.py
"""


class ShadowFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.repo = os.path.join(root, "repo")
        os.mkdir(self.repo)
        self._sh(self.repo, "git", "init", "-q", "-b", "main")
        self._sh(self.repo, "git", "config", "user.name", "t")
        self._sh(self.repo, "git", "config", "user.email", "t@example.invalid")
        with open(os.path.join(self.repo, "notes.py"), "w") as fh:
            fh.write("VERSION = 1\n")
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("fixture\n")
        self._sh(self.repo, "git", "add", "-A")
        self._sh(self.repo, "git", "commit", "-qm", "base")
        self.base = self._sh(self.repo, "git", "rev-parse", "HEAD").strip()
        # simulate the harness having landed the task
        with open(os.path.join(self.repo, "notes.py"), "a") as fh:
            fh.write("\nTAGS_ENABLED = True\n")
        self._sh(self.repo, "git", "add", "-A")
        self._sh(self.repo, "git", "commit", "-qm", "harness: tags flag")
        self.merged = self._sh(self.repo, "git", "rev-parse", "HEAD").strip()

        self.plan = os.path.join(root, "plan.json")
        with open(self.plan, "w") as fh:
            json.dump({
                "contract": 1,
                "goal": "Add a tags flag.",
                "constraints": ["Keep VERSION intact."],
                "decisions": [{"q": "Flag?", "a": "TAGS_ENABLED."}],
                "tasks": [{"id": "tags-flag", "title": "Add TAGS_ENABLED",
                           "spec": "Add TAGS_ENABLED = True to notes.py.",
                           "checks": ["true"]}],
                "ratified": {"by": "t", "ts": "2026-07-12T00:00:00Z"},
            }, fh)
        self.out = os.path.join(root, "shadow-out")
        os.mkdir(self.out)
        self.scenarios = os.path.join(root, "scenarios")
        os.mkdir(self.scenarios)

    def tearDown(self):
        self.tmp.cleanup()

    def _sh(self, cwd, *argv):
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        assert proc.returncode == 0, f"{argv}: {proc.stderr}"
        return proc.stdout

    def scenario(self, name, content):
        path = os.path.join(self.scenarios, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def run_shadow(self, shadow_script):
        env = dict(os.environ)
        env["MOCK_SCRIPT_AUTHOR"] = self.scenario("author.sh", ARBITER_AUTHOR)
        env["MOCK_SCRIPT_SHADOW"] = self.scenario("shadow.sh", shadow_script)
        return subprocess.run(
            [sys.executable, SHADOW, "--plan", self.plan, "--task", "tags-flag",
             "--repo", self.repo, "--base", self.base, "--merged", self.merged,
             "--out", self.out, "--launcher", MOCK],
            capture_output=True, text=True, env=env,
        )

    def log_records(self):
        path = os.path.join(self.out, "shadow-log.jsonl")
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def cmp_dir(self, record):
        return record["data"]["artifacts"]


class ShadowTests(ShadowFixture):
    def test_good_shadow_both_arms_pass(self):
        proc = self.run_shadow(SHADOW_GOOD)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (rec,) = self.log_records()
        data = rec["data"]
        self.assertTrue(data["grade_armH"]["ok"])
        self.assertTrue(data["grade_armN"]["ok"])
        self.assertTrue(data["shadow_landed"])
        self.assertTrue(data["arbiter"]["manifest_sha256"])
        # blinded diffs + sealed mapping exist and map to both arms
        d = self.cmp_dir(rec)
        with open(os.path.join(d, "SEALED-mapping.json")) as fh:
            mapping = json.load(fh)
        self.assertEqual({mapping["A"], mapping["B"]}, {"harness", "shadow"})
        for label in ("A", "B"):
            self.assertTrue(os.path.getsize(os.path.join(d, f"diff-{label}.patch")) > 0)

    def test_wrong_shadow_is_caught_by_arbiter_only_on_its_arm(self):
        proc = self.run_shadow(SHADOW_WRONG)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (rec,) = self.log_records()
        data = rec["data"]
        self.assertTrue(data["grade_armH"]["ok"])       # harness arm unaffected
        self.assertFalse(data["grade_armN"]["ok"])      # the mechanism catch, recorded
        self.assertTrue(any("unittest" in c or "python" in c
                            for c in data["grade_armN"]["failing"]))

    def test_shadow_without_commit_is_a_recorded_null_result(self):
        proc = self.run_shadow(SHADOW_NO_COMMIT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (rec,) = self.log_records()
        data = rec["data"]
        self.assertFalse(data["shadow_landed"])
        self.assertFalse(data["grade_armN"]["ok"])
        self.assertIn("no committed work", data["grade_armN"]["failing"][0])

    def test_contamination_walls_in_bundle_params(self):
        self.run_shadow(SHADOW_GOOD)
        (rec,) = self.log_records()
        d = self.cmp_dir(rec)
        with open(os.path.join(d, "bundle-arbiter", "params.json")) as fh:
            arb = json.load(fh)
        with open(os.path.join(d, "bundle-shadow", "params.json")) as fh:
            sh = json.load(fh)
        real = os.path.realpath(self.repo)
        # arbiter never sees either implementation (the live repo holds arm H)
        self.assertIn(real, arb["isolation"]["deny_read"])
        # shadow never sees the arbiter suite nor arm H
        self.assertIn(real, sh["isolation"]["deny_read"])
        self.assertTrue(any(p.endswith(os.path.join("arbiter", "tags-flag"))
                            for p in sh["isolation"]["deny_read"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
