"""exec-loop tests — task 1 (launcher contract); tasks 2+ extend this file.

Run: python3 tools/exec-loop/test_exec_loop.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "launchers", "mock.py")
CLAUDE_P = os.path.join(HERE, "launchers", "claude_p.py")


def make_bundle(root, *, role="implementer", worker=None, isolation=None, cwd=None,
                timeout_s=30, instructions="Do the task described in your workspace."):
    bundle = os.path.join(root, "bundle")
    os.makedirs(bundle, exist_ok=True)
    with open(os.path.join(bundle, "instructions.md"), "w") as fh:
        fh.write(instructions)
    params = {
        "role": role,
        "worker": worker or {"tool": "claude", "model": "claude-sonnet-5", "effort": "xhigh"},
        "isolation": isolation if isolation is not None
        else {"deny_read": [], "sandbox": True, "network": True},
        "cwd": cwd or root,
        "timeout_s": timeout_s,
    }
    with open(os.path.join(bundle, "params.json"), "w") as fh:
        json.dump(params, fh)
    return bundle


def run_launcher(launcher, bundle, *flags, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, launcher, *flags, bundle],
        capture_output=True,
        text=True,
        env=env,
    )


def read_result(bundle):
    with open(os.path.join(bundle, "result.json")) as fh:
        return json.load(fh)


class MockLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def scenario(self, content):
        path = os.path.join(self.root, "scenario.sh")
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def test_contract_compliance_happy_path(self):
        scenario = self.scenario("echo working\ntouch produced.txt\n")
        bundle = make_bundle(self.root)
        proc = run_launcher(MOCK, bundle, env_extra={"MOCK_SCRIPT": scenario})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = read_result(bundle)
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit"], 0)
        self.assertTrue(result["started_at"] and result["finished_at"])
        with open(os.path.join(bundle, "transcript.txt")) as fh:
            self.assertIn("working", fh.read())
        self.assertTrue(os.path.exists(os.path.join(self.root, "produced.txt")))

    def test_worker_failure_reported_not_hidden(self):
        scenario = self.scenario("echo boom\nexit 3\n")
        bundle = make_bundle(self.root)
        proc = run_launcher(MOCK, bundle, env_extra={"MOCK_SCRIPT": scenario})
        self.assertEqual(proc.returncode, 1)
        result = read_result(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit"], 3)

    def test_timeout_kills_the_process_group(self):
        scenario = self.scenario("sleep 30\n")
        bundle = make_bundle(self.root, timeout_s=1)
        t0 = time.monotonic()
        proc = run_launcher(MOCK, bundle, env_extra={"MOCK_SCRIPT": scenario})
        elapsed = time.monotonic() - t0
        self.assertNotEqual(proc.returncode, 0)
        self.assertLess(elapsed, 10, "timeout did not kill the worker promptly")
        result = read_result(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit"])

    def test_refusal_directive_simulates_fail_closed(self):
        scenario = self.scenario("#MOCK_REFUSE cannot express isolation intent\necho never\n")
        bundle = make_bundle(self.root)
        proc = run_launcher(MOCK, bundle, env_extra={"MOCK_SCRIPT": scenario})
        self.assertEqual(proc.returncode, 2)
        result = read_result(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("isolation intent", result["refused_reason"])
        self.assertFalse(os.path.exists(os.path.join(bundle, "transcript.txt")))


class ClaudePDryRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.deny = os.path.join(self.root, "heldout-ws")
        os.makedirs(self.deny)

    def tearDown(self):
        self.tmp.cleanup()

    def dry_run(self, **kwargs):
        bundle = make_bundle(self.root, **kwargs)
        proc = run_launcher(CLAUDE_P, bundle, "--dry-run")
        return bundle, proc

    def test_author_dry_run_argv_and_settings(self):
        bundle, proc = self.dry_run(
            role="author",
            worker={"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
            isolation={"deny_read": [self.deny], "sandbox": True, "network": True},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        argv = out["argv"]
        self.assertEqual(argv[0:2], ["claude", "-p"])
        for token in ["--model", "claude-opus-4-8", "--effort", "xhigh", "--settings"]:
            self.assertIn(token, argv)
        settings = out["generated_settings"]
        self.assertIn(f"Read({self.deny})", settings["permissions"]["deny"])
        self.assertIn(f"Read({self.deny}/**)", settings["permissions"]["deny"])
        self.assertTrue(settings["sandbox"]["enabled"])
        self.assertTrue(settings["sandbox"]["network"])
        # the settings file is materialized in the bundle for inspection
        with open(os.path.join(bundle, "generated-settings.json")) as fh:
            self.assertEqual(json.load(fh), settings)
        # dry-run executed nothing
        self.assertFalse(os.path.exists(os.path.join(bundle, "result.json")))
        self.assertFalse(os.path.exists(os.path.join(bundle, "transcript.txt")))

    def test_implementer_dry_run_sonnet_triple(self):
        _, proc = self.dry_run(
            worker={"tool": "claude", "model": "claude-sonnet-5", "effort": "xhigh"},
            isolation={"deny_read": [self.deny], "sandbox": True, "network": True},
        )
        self.assertEqual(proc.returncode, 0)
        argv = json.loads(proc.stdout)["argv"]
        self.assertIn("claude-sonnet-5", argv)

    def test_fail_closed_on_unknown_isolation_field(self):
        bundle, proc = self.dry_run(
            isolation={"deny_read": [], "sandbox": True, "network": True, "deny_write": ["/x"]},
        )
        self.assertEqual(proc.returncode, 2)
        result = read_result(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("deny_write", result["refused_reason"])

    def test_fail_closed_on_network_denial_without_sandbox(self):
        bundle, proc = self.dry_run(
            isolation={"deny_read": [], "sandbox": False, "network": False},
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("sandbox", read_result(bundle)["refused_reason"])

    def test_fail_closed_on_wrong_tool(self):
        bundle, proc = self.dry_run(
            worker={"tool": "codex", "model": "gpt-x"},
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("wrong launcher", read_result(bundle)["refused_reason"])

    def test_fail_closed_on_relative_deny_path(self):
        bundle, proc = self.dry_run(
            isolation={"deny_read": ["relative/path"], "sandbox": True, "network": True},
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("absolute", read_result(bundle)["refused_reason"])


sys.path.insert(0, HERE)
import loop as loop_mod  # noqa: E402


AUTHOR_TEETH = """\
mkdir -p suite
cat > suite/test_new.py <<'PY'
import unittest
import notes

class NewBehavior(unittest.TestCase):
    def test_secret_marker_zzz(self):
        self.assertTrue(getattr(notes, "TAGS_ENABLED", False))

class Regression(unittest.TestCase):
    def test_version_exists(self):
        self.assertTrue(hasattr(notes, "VERSION"))
PY
"""

AUTHOR_TOOTHLESS = """\
mkdir -p suite
cat > suite/test_soft.py <<'PY'
import unittest
import notes

class Soft(unittest.TestCase):
    def test_version_exists(self):
        self.assertTrue(hasattr(notes, "VERSION"))
PY
"""

IMPL_CORRECT = """\
printf '\\nTAGS_ENABLED = True\\n' >> notes.py
git add -A
git commit -qm "add tags flag"
"""

IMPL_WRONG = """\
printf '# no real change\\n' >> README.md
git add -A
git commit -qm "cosmetic"
"""

IMPL_PROTECTED = """\
mkdir -p protected
printf 'tamper\\n' > protected/oops.txt
git add -A
git commit -qm "touch machinery"
"""


class TaskCycleFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.repo = os.path.join(root, "repo")
        os.mkdir(self.repo)
        self._sh(self.repo, "git", "init", "-q", "-b", "main")
        self._sh(self.repo, "git", "config", "user.name", "loop-test")
        self._sh(self.repo, "git", "config", "user.email", "loop@example.invalid")
        with open(os.path.join(self.repo, "notes.py"), "w") as fh:
            fh.write("VERSION = 1\n")
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("fixture\n")
        self._sh(self.repo, "git", "add", "-A")
        self._sh(self.repo, "git", "commit", "-q", "-m", "base")

        self.plan_path = os.path.join(root, "plan.json")
        with open(self.plan_path, "w") as fh:
            json.dump(
                {
                    "contract": 1,
                    "goal": "Add a tags flag to notes.",
                    "constraints": ["Keep VERSION intact."],
                    "decisions": [{"q": "Flag name?", "a": "TAGS_ENABLED."}],
                    "tasks": [
                        {
                            "id": "tags-flag",
                            "title": "Add TAGS_ENABLED",
                            "spec": "Add TAGS_ENABLED = True to notes.py.",
                            "checks": ["true"],
                        }
                    ],
                },
                fh,
            )
        self.heldout_out = os.path.join(root, "heldout")
        self.scenarios = os.path.join(root, "scenarios")
        os.mkdir(self.scenarios)
        config = dict(loop_mod.DEFAULT_CONFIG)
        config["launcher"] = MOCK
        config["protect_paths"] = ["protected/"]
        config["author_timeout_s"] = 60
        config["implementer_timeout_s"] = 60
        self.loop = loop_mod.Loop(self.plan_path, self.repo, self.heldout_out, config)
        self._env_keys = []

    def tearDown(self):
        for key in self._env_keys:
            os.environ.pop(key, None)
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

    def set_env(self, **kv):
        for key, value in kv.items():
            os.environ[key] = value
            self._env_keys.append(key)

    def task(self):
        return self.loop.plan["tasks"][0]

    def bundles_for(self, role, attempt):
        root = os.path.join(self.loop.workdir, "bundles")
        found = []
        for name in sorted(os.listdir(root)):
            if name.endswith(f"-{role}-a{attempt}"):
                with open(os.path.join(root, name, "params.json")) as fh:
                    found.append((os.path.join(root, name), json.load(fh)))
        return found


class TaskCycleTests(TaskCycleFixture):
    def test_happy_path_merges_and_records(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
            MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_CORRECT),
        )
        result = self.loop.task_cycle(self.task())
        self.assertEqual(result["outcome"], "merged")
        with open(os.path.join(self.repo, "notes.py")) as fh:
            self.assertIn("TAGS_ENABLED", fh.read())
        subjects = [r["subject"] for r in self.loop.ledger_records()]
        for expected in ("seal", "gate-a1", "merged"):
            self.assertTrue(any(expected in s for s in subjects), subjects)
        self.assertFalse(os.path.exists(os.path.join(self.loop.workdir, "wt-tags-flag-a1")))

    def test_gate_fail_escalates_with_redacted_feedback(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
            MOCK_SCRIPT_IMPLEMENTER_A1=self.scenario("impl1.sh", IMPL_WRONG),
            MOCK_SCRIPT_IMPLEMENTER_A2=self.scenario("impl2.sh", IMPL_CORRECT),
        )
        result = self.loop.task_cycle(self.task())
        self.assertEqual(result["outcome"], "merged")
        [(bundle, params)] = self.bundles_for("implementer", 2)
        # escalation: attempt 2 is the Opus triple (decision 3)
        self.assertEqual(params["worker"]["model"], "claude-opus-4-8")
        with open(os.path.join(bundle, "instructions.md")) as fh:
            instructions = fh.read()
        # the silent-leak test (decision 5): held-out contents never reach a retry
        self.assertNotIn("secret_marker_zzz", instructions)
        self.assertIn("HELD-OUT SUITE", instructions)
        self.assertIn("withheld", instructions)

    def test_attempts_exhausted_halts_with_blocker(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
            MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_WRONG),
        )
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.task_cycle(self.task())
        self.assertEqual(ctx.exception.reason, "attempts-exhausted")
        self.assertIn("HELD-OUT SUITE", ctx.exception.detail["last_feedback"])
        rc = subprocess.run(
            ["git", "-C", self.repo, "log", "--oneline"], capture_output=True, text=True
        ).stdout
        self.assertNotIn("tags flag", rc)

    def test_protected_path_diff_is_blocked_before_gating(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
            MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_PROTECTED),
        )
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.task_cycle(self.task())
        self.assertEqual(ctx.exception.reason, "protected-paths")
        self.assertEqual(ctx.exception.detail["paths"], ["protected/oops.txt"])
        subjects = [r["subject"] for r in self.loop.ledger_records()]
        self.assertFalse(any("gate" in s for s in subjects), "gating must not have run")

    def test_toothless_author_retries_then_blocks(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TOOTHLESS),
        )
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.task_cycle(self.task())
        self.assertEqual(ctx.exception.reason, "author-policy-exhausted")
        self.assertEqual(len(self.bundles_for("author", 1)), 1)
        self.assertEqual(len(self.bundles_for("author", 2)), 1)

    def test_sealed_fresh_suite_is_reused_not_reauthored(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
            MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_CORRECT),
        )
        ws = self.loop.ensure_suite(self.task())
        self.assertTrue(os.path.exists(os.path.join(ws, "manifest.json")))
        author_runs_before = len(self.bundles_for("author", 1))
        ws2 = self.loop.ensure_suite(self.task())
        self.assertEqual(ws, ws2)
        self.assertEqual(len(self.bundles_for("author", 1)), author_runs_before)

    def test_stale_suite_after_plan_change_is_a_blocker(self):
        self.set_env(
            MOCK_SCRIPT_AUTHOR=self.scenario("author.sh", AUTHOR_TEETH),
        )
        self.loop.ensure_suite(self.task())
        self.loop.plan["decisions"].append({"q": "New?", "a": "Changed."})
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.ensure_suite(self.task())
        self.assertEqual(ctx.exception.reason, "suite-stale-spec-changed")
        self.assertEqual(ctx.exception.detail["changed_field"], "decisions")


if __name__ == "__main__":
    unittest.main(verbosity=2)
