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

sys.path.insert(0, os.path.join(HERE, "launchers"))
import claude_p  # noqa: E402  (unit-test parse_session directly)


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


class ParseSessionTests(unittest.TestCase):
    """The launcher's --output-format json parsing is fail-safe (schema is
    vendor-build); token capture must never crash a good launch."""

    def test_extracts_usage_and_text(self):
        raw = json.dumps({
            "result": "done implementing",
            "is_error": False,
            "num_turns": 12,
            "total_cost_usd": 0.1234,
            "duration_api_ms": 4567,
            "usage": {
                "input_tokens": 100, "output_tokens": 200,
                "cache_read_input_tokens": 3000, "cache_creation_input_tokens": 40,
            },
        })
        text, usage, is_error = claude_p.parse_session(raw)
        self.assertEqual(text, "done implementing")
        self.assertFalse(is_error)
        self.assertEqual(usage["input_tokens"], 100)
        self.assertEqual(usage["output_tokens"], 200)
        self.assertEqual(usage["cache_read_tokens"], 3000)
        self.assertEqual(usage["cache_creation_tokens"], 40)
        self.assertEqual(usage["cost_usd"], 0.1234)
        self.assertEqual(usage["num_turns"], 12)

    def test_unparseable_is_flagged_not_fatal(self):
        text, usage, is_error = claude_p.parse_session("not json at all")
        self.assertIn("error", usage)
        self.assertIsNone(is_error)
        self.assertEqual(text, "not json at all")

    def test_tolerates_noise_around_json(self):
        raw = "warning: something\n" + json.dumps({"result": "ok", "usage": {"output_tokens": 5}})
        text, usage, is_error = claude_p.parse_session(raw)
        self.assertEqual(text, "ok")
        self.assertEqual(usage["output_tokens"], 5)

    def test_missing_usage_fields_are_none_not_crash(self):
        raw = json.dumps({"result": "hi"})  # no usage block at all
        text, usage, is_error = claude_p.parse_session(raw)
        self.assertEqual(text, "hi")
        self.assertIsNone(usage["input_tokens"])
        self.assertIsNone(usage["cost_usd"])


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
        # commits run unattended via sandbox auto-allow, NOT bypassPermissions
        # (which dropped the wall in smoke run 2)
        self.assertIn("acceptEdits", argv)
        self.assertNotIn("bypassPermissions", argv)
        settings = out["generated_settings"]
        # in-process Read tool wall: // = absolute path
        self.assertIn(f"Read(/{self.deny})", settings["permissions"]["deny"])
        self.assertIn(f"Read(/{self.deny}/**)", settings["permissions"]["deny"])
        # OS bash wall + unattended sandboxed bash + no escape hatch
        sandbox = settings["sandbox"]
        self.assertTrue(sandbox["enabled"])
        self.assertTrue(sandbox["autoAllowBashIfSandboxed"])
        self.assertFalse(sandbox["allowUnsandboxedCommands"])
        self.assertEqual(sandbox["excludedCommands"], [])
        self.assertEqual(sandbox["filesystem"]["denyRead"], [self.deny])
        # sandbox-can't-start must abort, not warn-and-run-unsandboxed
        # (vendor default is the fail-open; operator-caught 2026-07-12)
        self.assertTrue(sandbox["failIfUnavailable"])
        # binary provenance: dry-run records the resolved path (never execs
        # for a version — dry-run executes nothing); real runs add version
        self.assertIn("binary", out)
        self.assertIn("path", out["binary"])
        self.assertNotIn("version", out["binary"])
        # structured output so token usage is captured in result.json
        i = argv.index("--output-format")
        self.assertEqual(argv[i + 1], "json")
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

    def retier(self, plan_tier=None, task_tier=None, drop_checks=False):
        """Rewrite the plan with tier fields and rebuild the Loop."""
        with open(self.plan_path) as fh:
            plan = json.load(fh)
        if plan_tier:
            plan["risk_tier"] = plan_tier
        if task_tier:
            plan["tasks"][0]["tier"] = task_tier
        if drop_checks:
            plan["tasks"][0].pop("checks", None)
        with open(self.plan_path, "w") as fh:
            json.dump(plan, fh)
        self.loop = loop_mod.Loop(
            self.plan_path, self.repo, self.heldout_out, self.loop.config
        )

    def bundles_for(self, role, attempt):
        root = os.path.join(self.loop.workdir, "bundles")
        found = []
        for name in sorted(os.listdir(root)):
            params_path = os.path.join(root, name, "params.json")
            if not os.path.exists(params_path):
                continue
            with open(params_path) as fh:
                params = json.load(fh)
            if params.get("role") == role and params.get("attempt") == attempt:
                found.append((os.path.join(root, name), params))
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
        records = self.loop.ledger_records()
        subjects = [r["subject"] for r in records]
        for expected in ("seal", "gate-a1", "merged"):
            self.assertTrue(any(expected in s for s in subjects), subjects)
        self.assertFalse(os.path.exists(os.path.join(self.loop.workdir, "wt-tags-flag-a1")))
        # instrumentation: seal carries author suite size; gate carries impl churn
        seal = next(r for r in records if r["subject"].endswith("/seal"))
        self.assertEqual(seal["data"]["suite"]["files"], 1)
        self.assertGreater(seal["data"]["suite"]["lines"], 0)
        self.assertIn("author_usage", seal["data"])  # None under mock; key present
        gate = next(r for r in records if "/gate-a1" in r["subject"])
        churn = gate["data"]["churn"]
        self.assertEqual(churn["files"], 1)          # only notes.py touched
        self.assertGreaterEqual(churn["insertions"], 1)
        self.assertEqual(churn["deletions"], 0)
        self.assertIn("impl_usage", gate["data"])

    def test_gate_only_skips_author_and_gates_on_task_checks(self):
        self.retier(task_tier="gate-only")
        # no author scenario set: an author spawn would fail loudly
        self.set_env(MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_CORRECT))
        result = self.loop.task_cycle(self.task())
        self.assertEqual(result["outcome"], "merged")
        records = self.loop.ledger_records()
        subjects = [r["subject"] for r in records]
        self.assertFalse(any("/seal" in s for s in subjects), subjects)
        self.assertFalse(any("author" in s for s in subjects), subjects)
        self.assertFalse(os.path.exists(self.loop.workspace("tags-flag")))
        gate = next(r for r in records if "/gate-a1" in r["subject"])
        self.assertEqual(gate["data"]["tier"], "gate-only")

    def test_gate_only_with_no_checks_blocks_before_any_spawn(self):
        self.retier(task_tier="gate-only", drop_checks=True)
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.task_cycle(self.task())
        self.assertEqual(ctx.exception.reason, "gate-only-task-has-no-checks")
        self.assertFalse(any("/spawn/" in r["subject"] for r in self.loop.ledger_records()))

    def test_bare_lands_a_single_strong_session_without_gate(self):
        self.retier(task_tier="bare")
        self.set_env(MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_CORRECT))
        result = self.loop.task_cycle(self.task())
        self.assertEqual(result["outcome"], "merged")
        records = self.loop.ledger_records()
        subjects = [r["subject"] for r in records]
        self.assertFalse(any("/gate-" in s for s in subjects), subjects)
        self.assertFalse(any("/seal" in s for s in subjects), subjects)
        merged = next(r for r in records if "/merged" in r["subject"])
        self.assertEqual(merged["data"]["tier"], "bare")
        self.assertIn("churn", merged["data"])  # telemetry home for gateless bare
        # the single session is the STRONG worker
        [(_, params)] = self.bundles_for("implementer", 1)
        self.assertEqual(params["worker"]["model"], "claude-opus-4-8")

    def test_bare_failure_blocks_without_escalation(self):
        self.retier(task_tier="bare")
        self.set_env(MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", "true\n"))
        with self.assertRaises(loop_mod.Blocker) as ctx:
            self.loop.task_cycle(self.task())
        self.assertEqual(ctx.exception.reason, "bare-task-failed")
        spawns = [r for r in self.loop.ledger_records() if "/spawn/" in r["subject"]]
        self.assertEqual(len(spawns), 1, "bare gets one attempt, never an escalation")

    def test_plan_level_risk_tier_is_the_task_default(self):
        self.retier(plan_tier="bare")
        self.set_env(MOCK_SCRIPT_IMPLEMENTER=self.scenario("impl.sh", IMPL_CORRECT))
        result = self.loop.task_cycle(self.task())
        self.assertEqual(result["outcome"], "merged")
        merged = next(r for r in self.loop.ledger_records() if "/merged" in r["subject"])
        self.assertEqual(merged["data"]["tier"], "bare")

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


LOOP_CLI = os.path.join(HERE, "loop.py")

AUTHOR_GENERIC = """\
TID=$(basename "$PWD")
mkdir -p suite
cat > suite/test_gen.py <<PY
import os, unittest

class NewMarker(unittest.TestCase):
    def test_done_marker(self):
        self.assertTrue(os.path.exists("done-$TID.txt"))
PY
"""

IMPL_GENERIC = """\
TID=$(git rev-parse --abbrev-ref HEAD | sed -e 's|task/||' -e 's|-a[0-9]*$||')
touch "done-$TID.txt"
git add -A
git commit -qm "done $TID"
"""

IMPL_NOOP = """\
printf '# nothing real\\n' >> README.md
git add -A
git commit -qm noop
"""

# Does its own task correctly AND silently deletes task one's marker — the
# cross-task regression that per-task gates cannot see (their verifiers only
# cover the current task). Whole-build closure must catch it.
IMPL_REGRESSES_PRIOR = """\
TID=$(git rev-parse --abbrev-ref HEAD | sed -e 's|task/||' -e 's|-a[0-9]*$||')
rm -f done-t-one.txt
touch "done-$TID.txt"
git add -A
git commit -qm "done $TID (and quietly broke t-one)"
"""

# Does its own task correctly, but an "external writer" (the operator, another
# tool) commits to main mid-attempt. The judged tree can then no longer land
# fast-forward; the loop must refuse rather than land an unjudged merge.
IMPL_EXTERNAL_WRITER = """\
git -C "$REPO_PATH" commit --allow-empty -qm "external mid-run commit"
TID=$(git rev-parse --abbrev-ref HEAD | sed -e 's|task/||' -e 's|-a[0-9]*$||')
touch "done-$TID.txt"
git add -A
git commit -qm "done $TID"
"""


class WalkerFixture(TaskCycleFixture):
    """Reuses the repo fixture; swaps in a ratified two-task plan and drives
    the real CLI."""

    def setUp(self):
        super().setUp()
        with open(self.plan_path, "w") as fh:
            json.dump(
                {
                    "contract": 1,
                    "goal": "Produce done-markers for two tasks.",
                    "decisions": [{"q": "Marker shape?", "a": "done-<task-id>.txt on main."}],
                    "tasks": [
                        {"id": "t-one", "title": "Marker one",
                         "spec": "Create done-t-one.txt.", "checks": ["true"]},
                        {"id": "t-two", "title": "Marker two",
                         "spec": "Create done-t-two.txt.", "checks": ["true"],
                         "depends_on": ["t-one"]},
                    ],
                    "ratified": {"by": "dwijen", "ts": "2026-07-12T00:00:00Z"},
                },
                fh,
            )
        self.ledger_path = os.path.join(self.tmp.name, "ledger.jsonl")

    def run_cli(self, env_extra=None, plan=None):
        env = dict(os.environ)
        env.update(env_extra or {})
        return subprocess.run(
            [
                sys.executable, LOOP_CLI, "run",
                "--plan", plan or self.plan_path,
                "--repo", self.repo,
                "--heldout-out", self.heldout_out,
                "--launcher", MOCK,
                "--ledger", self.ledger_path,
            ],
            capture_output=True,
            text=True,
            env=env,
        )

    def generic_env(self, impl=IMPL_GENERIC):
        return {
            "MOCK_SCRIPT_AUTHOR": self.scenario("author-gen.sh", AUTHOR_GENERIC),
            "MOCK_SCRIPT_IMPLEMENTER": self.scenario("impl-gen.sh", impl),
        }

    def ledger_subjects(self):
        if not os.path.exists(self.ledger_path):
            return []
        subjects = []
        with open(self.ledger_path) as fh:
            for line in fh:
                subjects.append(json.loads(line)["subject"])
        return subjects

    def spawn_count(self):
        return sum(1 for s in self.ledger_subjects() if "/spawn/" in s)


class WalkerTests(WalkerFixture):
    def test_full_plan_runs_to_exit_0(self):
        proc = self.run_cli(self.generic_env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for marker in ("done-t-one.txt", "done-t-two.txt"):
            self.assertTrue(os.path.exists(os.path.join(self.repo, marker)), marker)
        self.assertEqual(self.spawn_count(), 4)  # 2 authors + 2 implementers

    def test_restart_derives_done_and_respawns_nothing(self):
        self.assertEqual(self.run_cli(self.generic_env()).returncode, 0)
        before = self.spawn_count()
        proc = self.run_cli(self.generic_env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.spawn_count(), before, "restart must not re-run merged tasks")

    def test_unratified_plan_refused(self):
        unratified = os.path.join(self.tmp.name, "unratified.json")
        with open(self.plan_path) as fh:
            plan = json.load(fh)
        del plan["ratified"]
        with open(unratified, "w") as fh:
            json.dump(plan, fh)
        proc = self.run_cli(self.generic_env(), plan=unratified)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ratified", (proc.stderr + proc.stdout).lower())

    def test_second_loop_refused_by_lock(self):
        import fcntl

        workdir = os.path.join(self.heldout_out, "_runs", "plan")
        os.makedirs(workdir, exist_ok=True)
        with open(os.path.join(workdir, "loop.lock"), "w") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            proc = self.run_cli(self.generic_env())
            self.assertEqual(proc.returncode, 2)
            self.assertIn("lock", proc.stderr)

    def test_closure_grants_completion_with_stamp(self):
        proc = self.run_cli(self.generic_env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        closure = [
            json.loads(line) for line in open(self.ledger_path)
            if '"exec-loop/plan/closure"' in line
        ]
        self.assertEqual(len(closure), 1)
        data = closure[0]["data"]
        self.assertTrue(data["ok"])
        main_sha = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "main"],
            capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(data["sha"], main_sha)  # bound to final main
        self.assertTrue(data["plan_sha256"])     # bound to the frozen plan
        self.assertTrue(os.path.exists(data["report"]))
        with open(data["report"]) as fh:
            report = json.load(fh)
        # closure replayed BOTH suites (verify + run per task) + both checks
        self.assertEqual(len(report["checks"]), data["checks"])
        self.assertGreaterEqual(
            sum(1 for c in report["checks"] if "verify" in c["cmd"]), 2
        )

    def test_closure_catches_cross_task_regression(self):
        proc = self.run_cli(self.generic_env(impl=IMPL_REGRESSES_PRIOR))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        # the regression really landed at task level (both gates passed)...
        self.assertFalse(os.path.exists(os.path.join(self.repo, "done-t-one.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.repo, "done-t-two.txt")))
        # ...and closure is what caught it
        with open(os.path.join(self.heldout_out, "_runs", "plan", "blocker.json")) as fh:
            blocker = json.load(fh)
        self.assertEqual(blocker["reason"], "closure-failed")
        self.assertTrue(
            any("t-one" in cmd for cmd in blocker["detail"]["failing"]),
            blocker["detail"]["failing"],
        )

    def test_mixed_tier_plan_closure_replays_only_full_suites(self):
        with open(self.plan_path) as fh:
            plan = json.load(fh)
        plan["tasks"][1]["tier"] = "gate-only"
        with open(self.plan_path, "w") as fh:
            json.dump(plan, fh)
        proc = self.run_cli(self.generic_env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.spawn_count(), 3, "1 author (t-one only) + 2 implementers")
        closure = [
            json.loads(line) for line in open(self.ledger_path)
            if '"exec-loop/plan/closure"' in line
        ]
        self.assertEqual(len(closure), 1)
        with open(closure[0]["data"]["report"]) as fh:
            cmds = [c["cmd"] for c in json.load(fh)["checks"]]
        self.assertTrue(any("t-one" in c for c in cmds), cmds)   # full suite replayed
        self.assertFalse(
            any("t-two" in c for c in cmds), cmds                # no suite ever existed
        )

    def test_closure_idempotent_on_restart(self):
        self.assertEqual(self.run_cli(self.generic_env()).returncode, 0)
        proc = self.run_cli(self.generic_env())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        closure_count = sum(
            1 for line in open(self.ledger_path)
            if '"exec-loop/plan/closure"' in line
        )
        self.assertEqual(closure_count, 1, "unchanged main+plan must not re-run closure")

    def test_two_plans_same_repo_contend_on_repo_lock(self):
        import fcntl

        common = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True,
        ).stdout.strip()
        if not os.path.isabs(common):
            common = os.path.join(self.repo, common)
        with open(os.path.join(common, "exec-loop.lock"), "w") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # a DIFFERENTLY-NAMED plan against the same repo must refuse
            plan2 = os.path.join(self.tmp.name, "second-plan.json")
            with open(self.plan_path) as src, open(plan2, "w") as dst:
                json.dump(json.load(src), dst)
            proc = self.run_cli(self.generic_env(), plan=plan2)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("repository", proc.stderr)

    def test_external_main_move_refuses_non_ff_landing(self):
        env = self.generic_env(impl=IMPL_EXTERNAL_WRITER)
        env["REPO_PATH"] = self.repo
        proc = self.run_cli(env)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        with open(os.path.join(self.heldout_out, "_runs", "plan", "blocker.json")) as fh:
            blocker = json.load(fh)
        self.assertEqual(blocker["reason"], "merge-not-fast-forward")
        # nothing landed: the worker's marker is NOT on main
        self.assertFalse(os.path.exists(os.path.join(self.repo, "done-t-one.txt")))

    def test_exhaustion_blocks_halts_all_and_stays_blocked_on_restart(self):
        proc = self.run_cli(self.generic_env(impl=IMPL_NOOP))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        blocker_path = os.path.join(self.heldout_out, "_runs", "plan", "blocker.json")
        with open(blocker_path) as fh:
            blocker = json.load(fh)
        self.assertEqual(blocker["reason"], "attempts-exhausted")
        # halt-all: t-two never started
        self.assertFalse(any("t-two" in s for s in self.ledger_subjects()))
        # restart derives the exhaustion from the ledger without new spawns
        before = self.spawn_count()
        proc = self.run_cli(self.generic_env(impl=IMPL_NOOP))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.spawn_count(), before)


AUTHOR_INTERRUPTIBLE = """\
TID=$(basename "$PWD")
if [ "$TID" = "t-two" ] && [ ! -f "$MOCK_FLAG_FILE" ]; then
  echo "simulated interruption before t-two authoring"
  exit 3
fi
mkdir -p suite
cat > suite/test_gen.py <<PY
import os, unittest

class NewMarker(unittest.TestCase):
    def test_done_marker(self):
        self.assertTrue(os.path.exists("done-$TID.txt"))
PY
"""


class E2ETests(WalkerFixture):
    """Task e2e-mock: the ratified integration scenarios through the real CLI.
    Scenarios 1 (full success), 3 (exhaustion halt-all), and clean-restart are
    covered by WalkerTests; here: fail-once-escalate, protected-path block,
    and interrupted-mid-plan resume."""

    def test_fail_once_then_escalate_to_opus_and_complete(self):
        env = self.generic_env()
        env["MOCK_SCRIPT_IMPLEMENTER_A1"] = self.scenario("impl-a1-wrong.sh", IMPL_NOOP)
        env["MOCK_SCRIPT_IMPLEMENTER_A2"] = self.scenario("impl-a2-right.sh", IMPL_GENERIC)
        proc = self.run_cli(env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        subjects = self.ledger_subjects()
        self.assertEqual(sum(1 for s in subjects if s.endswith("gate-a1")), 2)
        self.assertEqual(sum(1 for s in subjects if s.endswith("gate-a2")), 2)
        # every attempt-2 bundle carries the escalation triple
        bundles_root = os.path.join(self.heldout_out, "_runs", "plan", "bundles")
        a2_params = []
        for name in os.listdir(bundles_root):
            params_path = os.path.join(bundles_root, name, "params.json")
            if os.path.exists(params_path):
                with open(params_path) as fh:
                    params = json.load(fh)
                if params.get("role") == "implementer" and params.get("attempt") == 2:
                    a2_params.append(params)
        self.assertEqual(len(a2_params), 2)
        for params in a2_params:
            self.assertEqual(params["worker"]["model"], "claude-opus-4-8")

    def test_protected_path_diff_blocks_via_cli(self):
        config_path = os.path.join(self.tmp.name, "config.json")
        with open(config_path, "w") as fh:
            json.dump({"protect_paths": ["protected/"]}, fh)
        env = self.generic_env(impl=IMPL_PROTECTED)
        proc = subprocess.run(
            [
                sys.executable, LOOP_CLI, "run",
                "--plan", self.plan_path,
                "--repo", self.repo,
                "--heldout-out", self.heldout_out,
                "--launcher", MOCK,
                "--ledger", self.ledger_path,
                "--config", config_path,
            ],
            capture_output=True, text=True, env={**os.environ, **env},
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        with open(os.path.join(self.heldout_out, "_runs", "plan", "blocker.json")) as fh:
            blocker = json.load(fh)
        self.assertEqual(blocker["reason"], "protected-paths")
        self.assertEqual(blocker["detail"]["paths"], ["protected/oops.txt"])
        self.assertFalse(any("gate" in s for s in self.ledger_subjects()))

    def test_interrupted_mid_plan_resumes_without_rework(self):
        flag = os.path.join(self.tmp.name, "resume-flag")
        env = {
            "MOCK_SCRIPT_AUTHOR": self.scenario("author-int.sh", AUTHOR_INTERRUPTIBLE),
            "MOCK_SCRIPT_IMPLEMENTER": self.scenario("impl-gen.sh", IMPL_GENERIC),
            "MOCK_FLAG_FILE": flag,
        }
        first = self.run_cli(env)
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "done-t-one.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "done-t-two.txt")))
        t_one_spawns = sum(1 for s in self.ledger_subjects() if "t-one/spawn" in s)

        with open(flag, "w") as fh:
            fh.write("resume\n")
        second = self.run_cli(env)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "done-t-two.txt")))
        self.assertEqual(
            sum(1 for s in self.ledger_subjects() if "t-one/spawn" in s),
            t_one_spawns,
            "resume must not re-run the merged task",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
