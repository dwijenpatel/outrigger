"""codex_p tests — the full launcher flow against a stub `codex` binary on
PATH (no AI, no network, no quota). What the stub cannot prove — that the
real Codex sandbox actually holds, and that the live event schema matches the
parser — is the operator-run smoke probe's job (SMOKE.md).

Run: python3 tools/exec-loop/launchers/test_codex_p.py
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX_P = os.path.join(HERE, "codex_p.py")

sys.path.insert(0, HERE)
import codex_p  # noqa: E402  (unit-test parse_events/validate directly)

STUB = """\
#!/usr/bin/env python3
import json, os, sys, time
if "--version" in sys.argv[1:]:
    print("codex-stub 0.0.1")
    sys.exit(0)
stub_dir = os.environ["CODEX_STUB_DIR"]
with open(os.path.join(stub_dir, "argv.json"), "w") as fh:
    json.dump(sys.argv[1:], fh)
data = sys.stdin.read() if "-" in sys.argv[1:] else ""
with open(os.path.join(stub_dir, "stdin.txt"), "w") as fh:
    fh.write(data)
args = sys.argv[1:]
if "--output-last-message" in args and os.environ.get("CODEX_STUB_NO_LAST_MSG") != "1":
    path = args[args.index("--output-last-message") + 1]
    with open(path, "w") as fh:
        fh.write(os.environ.get("CODEX_STUB_LAST_MSG", "stub final message"))
events = os.environ.get("CODEX_STUB_EVENTS")
if events is None:
    events = (
        '{"type":"session.created","session_id":"stub"}\\n'
        '{"type":"turn.completed","usage":'
        '{"input_tokens":1200,"cached_input_tokens":800,"output_tokens":45}}\\n'
    )
sys.stdout.write(events)
sys.stdout.flush()
time.sleep(float(os.environ.get("CODEX_STUB_SLEEP", "0")))
sys.exit(int(os.environ.get("CODEX_STUB_EXIT", "0")))
"""


class CodexPFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.bin_dir = os.path.join(root, "bin")
        self.stub_dir = os.path.join(root, "stub-io")
        self.workdir = os.path.join(root, "work")
        for d in (self.bin_dir, self.stub_dir, self.workdir):
            os.mkdir(d)
        stub_path = os.path.join(self.bin_dir, "codex")
        with open(stub_path, "w") as fh:
            fh.write(STUB)
        os.chmod(stub_path, os.stat(stub_path).st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.tmp.cleanup()

    def make_bundle(self, params_overrides=None, instructions="Do the thing.\n"):
        bundle = tempfile.mkdtemp(dir=self.tmp.name, prefix="bundle-")
        params = {
            "contract": 1,
            "role": "author",
            "attempt": 1,
            "worker": {"tool": "codex", "model": "gpt-5.2-codex"},
            "isolation": {"deny_read": [], "sandbox": True, "network": True},
            "cwd": self.workdir,
            "timeout_s": 600,
        }
        for key, value in (params_overrides or {}).items():
            if isinstance(value, dict) and isinstance(params.get(key), dict):
                params[key].update(value)
            else:
                params[key] = value
        with open(os.path.join(bundle, "params.json"), "w") as fh:
            json.dump(params, fh)
        if instructions is not None:
            with open(os.path.join(bundle, "instructions.md"), "w") as fh:
                fh.write(instructions)
        return bundle

    def run_launcher(self, bundle, env_extra=None, dry_run=False):
        env = dict(os.environ)
        env["PATH"] = self.bin_dir + os.pathsep + env.get("PATH", "")
        env["CODEX_STUB_DIR"] = self.stub_dir
        env.update(env_extra or {})
        argv = [sys.executable, CODEX_P] + (["--dry-run"] if dry_run else []) + [bundle]
        return subprocess.run(argv, capture_output=True, text=True, env=env)

    def result(self, bundle):
        with open(os.path.join(bundle, "result.json")) as fh:
            return json.load(fh)

    def stub_argv(self):
        with open(os.path.join(self.stub_dir, "argv.json")) as fh:
            return json.load(fh)

    def stub_invoked(self):
        return os.path.exists(os.path.join(self.stub_dir, "argv.json"))


class CodexPTests(CodexPFixture):
    def test_happy_path_contract(self):
        bundle = self.make_bundle(instructions="You are the TEST-AUTHOR.\n")
        proc = self.run_launcher(bundle)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        res = self.result(bundle)
        self.assertEqual(res["contract"], 1)
        self.assertTrue(res["ok"])
        self.assertEqual(res["exit"], 0)
        self.assertFalse(res["timed_out"])
        self.assertEqual(res["binary"]["version"], "codex-stub 0.0.1")
        self.assertTrue(res["binary"]["path"].endswith("codex"))
        self.assertEqual(res["usage"]["input_tokens"], 1200)
        self.assertEqual(res["usage"]["cache_read_tokens"], 800)
        self.assertEqual(res["usage"]["output_tokens"], 45)
        self.assertEqual(res["usage"]["num_turns"], 1)
        self.assertIsNone(res["usage"]["cost_usd"])
        # the prompt traveled via stdin, verbatim
        with open(os.path.join(self.stub_dir, "stdin.txt")) as fh:
            self.assertEqual(fh.read(), "You are the TEST-AUTHOR.\n")
        # transcript is the captured final message; raw events kept alongside
        with open(os.path.join(bundle, "transcript.txt")) as fh:
            self.assertEqual(fh.read(), "stub final message")
        self.assertTrue(os.path.getsize(os.path.join(bundle, "events.jsonl")) > 0)
        argv = self.stub_argv()
        self.assertEqual(argv[0], "exec")
        for expected in ("--json", "--skip-git-repo-check", "--ephemeral"):
            self.assertIn(expected, argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(argv[argv.index("--model") + 1], "gpt-5.2-codex")
        self.assertEqual(argv[argv.index("--cd") + 1], self.workdir)
        self.assertEqual(argv[-1], "-")
        self.assertIn("sandbox_workspace_write.network_access=true", argv)

    def test_effort_flag_and_network_false(self):
        bundle = self.make_bundle({
            "worker": {"effort": "high"},
            "isolation": {"network": False},
        })
        proc = self.run_launcher(bundle)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        argv = self.stub_argv()
        self.assertIn('model_reasoning_effort="high"', argv)
        self.assertNotIn("sandbox_workspace_write.network_access=true", argv)

    def test_deny_read_refused_fail_closed(self):
        bundle = self.make_bundle({"isolation": {"deny_read": ["/somewhere/sealed"]}})
        proc = self.run_launcher(bundle)
        self.assertEqual(proc.returncode, 2)
        res = self.result(bundle)
        self.assertFalse(res["ok"])
        self.assertIn("deny_read", res["refused_reason"])
        self.assertIn("unwalled", res["refused_reason"])
        self.assertFalse(self.stub_invoked(), "refusal must not launch anything")

    def test_unknown_contract_and_wrong_tool_refused(self):
        for overrides, needle in (
            ({"contract": 2}, "unknown params contract"),
            ({"worker": {"tool": "claude"}}, "wrong launcher"),
            ({"isolation": {"sandbox": False}}, "sandboxed"),
        ):
            bundle = self.make_bundle(overrides)
            proc = self.run_launcher(bundle)
            self.assertEqual(proc.returncode, 2, f"{overrides}: {proc.stderr}")
            self.assertIn(needle, self.result(bundle)["refused_reason"])
        self.assertFalse(self.stub_invoked())

    def test_timeout_kills_process_group(self):
        bundle = self.make_bundle({"timeout_s": 1})
        proc = self.run_launcher(bundle, env_extra={"CODEX_STUB_SLEEP": "10"})
        self.assertEqual(proc.returncode, 1)
        res = self.result(bundle)
        self.assertFalse(res["ok"])
        self.assertTrue(res["timed_out"])
        self.assertIsNone(res["exit"])

    def test_usage_parse_miss_never_fails_a_good_launch(self):
        bundle = self.make_bundle()
        proc = self.run_launcher(
            bundle, env_extra={"CODEX_STUB_EVENTS": "plain text, not JSONL at all\n"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        res = self.result(bundle)
        self.assertTrue(res["ok"], "telemetry miss must not fail the launch")
        self.assertIn("error", res["usage"])

    def test_failure_carries_error_summary_for_wall_classification(self):
        bundle = self.make_bundle()
        events = (
            '{"type":"error","message":"stream error"}\n'
            "Codex usage limit reached, try again at 9pm.\n"
        )
        proc = self.run_launcher(bundle, env_extra={
            "CODEX_STUB_EVENTS": events,
            "CODEX_STUB_EXIT": "1",
            "CODEX_STUB_NO_LAST_MSG": "1",
        })
        self.assertEqual(proc.returncode, 1)
        res = self.result(bundle)
        self.assertFalse(res["ok"])
        self.assertIn("usage limit", res["error_summary"].lower())

    def test_vendor_error_event_fails_closed_even_on_exit_0(self):
        bundle = self.make_bundle()
        proc = self.run_launcher(bundle, env_extra={
            "CODEX_STUB_EVENTS": '{"type":"turn.failed","message":"boom"}\n'})
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(self.result(bundle)["ok"])

    def test_dry_run_executes_nothing(self):
        bundle = self.make_bundle()
        proc = self.run_launcher(bundle, dry_run=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plan = json.loads(proc.stdout)
        self.assertTrue(plan["dry_run"])
        self.assertIn("workspace-write", plan["argv"])
        self.assertFalse(self.stub_invoked(), "--dry-run must not execute the binary")
        self.assertFalse(os.path.exists(os.path.join(bundle, "result.json")))


class ParseEventsUnitTests(unittest.TestCase):
    def test_last_usage_wins_and_alternate_shapes_are_read(self):
        stdout = "\n".join([
            '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":1}}',
            '{"msg":{"type":"token_count","info":{"total_token_usage":'
            '{"input_tokens":500,"cached_input_tokens":300,"output_tokens":22}}}}',
        ])
        usage, is_error = codex_p.parse_events(stdout)
        self.assertEqual(usage["input_tokens"], 500)
        self.assertEqual(usage["cache_read_tokens"], 300)
        self.assertFalse(is_error)

    def test_empty_and_garbage_inputs_are_failsafe(self):
        for stdout in ("", None, "not json\n{broken", '{"type":"x"}'):
            usage, _ = codex_p.parse_events(stdout)
            self.assertIn("error", usage)


if __name__ == "__main__":
    unittest.main(verbosity=2)
