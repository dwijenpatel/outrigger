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


if __name__ == "__main__":
    unittest.main(verbosity=2)
