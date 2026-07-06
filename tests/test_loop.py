"""Tests for harness.loop (E2) + the statusline-dump shim."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ledger as ledger_mod, loop
from harness.ledger import EventLog, Ledger
from harness.loop import LessonsCorpus, LoopError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RunMarkerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.marker = os.path.join(self.dir.name, "state", "run.marker")

    def tearDown(self):
        self.dir.cleanup()

    def test_acquire_release_roundtrip(self):
        got = loop.acquire_run_marker(self.marker, "firing-1")
        self.assertEqual(got["owner"], "firing-1")
        self.assertTrue(loop.release_run_marker(self.marker))
        self.assertFalse(loop.release_run_marker(self.marker))

    def test_live_owner_refuses_second_firing(self):
        loop.acquire_run_marker(self.marker, "firing-1")  # our own live pid
        with self.assertRaises(LoopError):
            loop.acquire_run_marker(self.marker, "firing-2")

    def test_dead_owner_self_heals(self):
        os.makedirs(os.path.dirname(self.marker), exist_ok=True)
        with open(self.marker, "w") as fh:
            json.dump({"owner": "ghost", "pid": 2 ** 22 + 1234,
                       "acquired_at": "2026-01-01T00:00:00Z"}, fh)
        got = loop.acquire_run_marker(self.marker, "firing-2")
        self.assertEqual(got["owner"], "firing-2")

    def test_torn_marker_reclaimed(self):
        os.makedirs(os.path.dirname(self.marker), exist_ok=True)
        with open(self.marker, "w") as fh:
            fh.write("{torn")
        got = loop.acquire_run_marker(self.marker, "firing-3")
        self.assertEqual(got["owner"], "firing-3")


class HeadlessTests(unittest.TestCase):
    def test_headless_env_sets_flag_and_strips_api_key(self):
        env = loop.headless_env({"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-x"})
        self.assertEqual(env["DISABLE_NON_ESSENTIAL_MODEL_CALLS"], "1")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual(env["PATH"], "/bin")

    def test_worker_settings_strict_by_default(self):
        s = loop.worker_settings()
        self.assertFalse(s["sandbox"]["allowUnsandboxedCommands"])
        self.assertTrue(s["sandbox"]["failIfUnavailable"])

    def test_worker_settings_with_vault_merges_isolation(self):
        s = loop.worker_settings(vault_path=".vault")
        self.assertIn("Read(.vault/**)", s["permissions"]["deny"])
        self.assertEqual(s["sandbox"]["denyRead"], [".vault"])

    def test_worker_settings_deny_machinery_unconditionally(self):
        # H10: with or without a vault, workers cannot file-tool-edit the
        # loop's own machinery — no branch-name loophole
        for s in (loop.worker_settings(),
                  loop.worker_settings(vault_path=".vault")):
            denies = s["permissions"]["deny"]
            for glob in ("harness/**", "hooks/**", ".claude/**",
                         "docs/plan/**", "docs/design/**", "tools/**"):
                for tool in ("Edit", "Write", "NotebookEdit"):
                    self.assertIn(f"{tool}({glob})", denies)

    def test_machinery_denies_do_not_displace_vault_denies(self):
        denies = loop.worker_settings(vault_path=".vault")["permissions"]["deny"]
        self.assertIn("Edit(harness/**)", denies)
        self.assertIn("Edit(.vault/**)", denies)


class ResumeContextTests(unittest.TestCase):
    def test_bundle_is_artifact_only(self):
        with tempfile.TemporaryDirectory() as root:
            repo = os.path.join(root, "repo")
            os.makedirs(repo)
            subprocess.run(["git", "-C", repo, "init", "-q", "-b", "main"],
                           check=True)
            subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"],
                           check=True)
            subprocess.run(["git", "-C", repo, "config", "user.name", "t"],
                           check=True)
            with open(os.path.join(repo, "f"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "-C", repo, "add", "f"], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"],
                           check=True)
            ldg = Ledger(ledger_mod.validate_tasks({"tasks": [
                {"id": "t1", "phase": "p", "profile": "routine", "deps": []}]}))
            log = EventLog(os.path.join(root, "events.jsonl"))
            log.record_status("t1", "in_progress")
            ctx = loop.resume_context(repo, ldg, log)
            self.assertEqual(ctx["git"]["branch"], "main")
            self.assertFalse(ctx["git"]["dirty"])
            self.assertIn("tasks: 0 of 1 done", ctx["ledger_digest"])
            self.assertEqual(len(ctx["pending_events"]), 1)
            self.assertIn("claims-not-evidence", ctx["rule"])


class LessonsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.corpus = LessonsCorpus(os.path.join(self.dir.name, "lessons.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def test_add_and_exact_dedup(self):
        self.corpus.add("RLS needs FORCE for table owners", ["db"], "t1")
        got = self.corpus.add("RLS needs FORCE for table owners", ["db"], "t2")
        self.assertTrue(got.get("deduped"))
        self.assertEqual(len(self.corpus.read()), 1)

    def test_selection_is_curated_not_the_whole_corpus(self):
        for i in range(10):
            self.corpus.add(f"db lesson {i}", ["db"], f"t{i}")
        self.corpus.add("ui lesson", ["ui"], "t99")
        got = self.corpus.select_for_task(
            {"subsystem": "db", "phase": "p1", "profile": "high"}, cap=3)
        self.assertEqual(len(got), 3)
        self.assertTrue(all("db" in l["tags"] for l in got))
        # newest first
        self.assertEqual(got[0]["text"], "db lesson 9")

    def test_general_lessons_backfill(self):
        self.corpus.add("always check exit status, not piped tails",
                        ["general"], "t0")
        got = self.corpus.select_for_task({"subsystem": "ui"}, cap=5)
        self.assertEqual(len(got), 1)


class SkillBudgetTests(unittest.TestCase):
    def test_real_inventory_within_budget(self):
        got = loop.skill_budget_check(
            [os.path.join(REPO_ROOT, ".claude", "skills")])
        self.assertTrue(got["ok"], got["why"])
        self.assertGreaterEqual(got["skills"], 1)

    def test_overflow_is_loud(self):
        with tempfile.TemporaryDirectory() as root:
            sdir = os.path.join(root, "skills", "fat")
            os.makedirs(sdir)
            with open(os.path.join(sdir, "SKILL.md"), "w") as fh:
                fh.write("---\ndescription: " + "x" * 500 + "\n---\nbody")
            got = loop.skill_budget_check([os.path.join(root, "skills")],
                                          budget_chars=100)
            self.assertFalse(got["ok"])
            self.assertIn("silently vanish", got["why"])


class StatuslineDumpTests(unittest.TestCase):
    def test_shim_tees_json_and_prints_line(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "sl.json")
            doc = {"rate_limits": {"five_hour": {"used_percentage": 41.0},
                                   "seven_day": {"used_percentage": 63.0}}}
            proc = subprocess.run(
                [sys.executable,
                 os.path.join(REPO_ROOT, "hooks", "statusline_dump.py"),
                 "--out", out],
                input=json.dumps(doc), capture_output=True, text=True,
                timeout=30)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("5h 41%", proc.stdout)
            with open(out) as fh:
                dumped = json.load(fh)
            self.assertIn("_captured_at", dumped)
            # and the governor can read the dump directly
            from harness import governor
            occ = governor.read_statusline(dumped)
            self.assertAlmostEqual(occ.windows["five_hour"], 0.41)

    def test_shim_resolves_out_from_input_json_when_no_flag(self):
        # I9b/P2-6: statusline commands don't get $CLAUDE_PROJECT_DIR — the
        # project dir rides the input JSON; --out is optional
        with tempfile.TemporaryDirectory() as root:
            doc = {"workspace": {"project_dir": root},
                   "rate_limits": {"five_hour": {"used_percentage": 12.0}}}
            proc = subprocess.run(
                [sys.executable,
                 os.path.join(REPO_ROOT, "hooks", "statusline_dump.py")],
                input=json.dumps(doc), capture_output=True, text=True,
                timeout=30)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("5h 12%", proc.stdout)
            with open(os.path.join(root, "state",
                                   "statusline-dump.json")) as fh:
                self.assertIn("_captured_at", json.load(fh))

    def test_shim_ignores_unexpanded_env_var_in_out(self):
        # the exact P2-6 failure shape: an --out carrying a literal '$VAR'
        # falls back to input-JSON resolution instead of writing to '/state'
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sldump", os.path.join(REPO_ROOT, "hooks", "statusline_dump.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        got = mod.resolve_out("$CLAUDE_PROJECT_DIR/state/x.json",
                              {"workspace": {"project_dir": "/proj"}})
        self.assertEqual(got, "/proj/state/statusline-dump.json")
        self.assertEqual(mod.resolve_out("/explicit/out.json", {}),
                         "/explicit/out.json")

    def test_shim_never_breaks_the_session(self):
        proc = subprocess.run(
            [sys.executable,
             os.path.join(REPO_ROOT, "hooks", "statusline_dump.py"),
             "--out", "/nonexistent-dir-x/y.json"],
            input="not json", capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0)  # statusline must not crash


if __name__ == "__main__":
    unittest.main()


class PauseRequestTests(unittest.TestCase):
    """I11 — the graceful-pause flag: attributed, durable, fail-safe."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "state", "pause.request")

    def tearDown(self):
        self.dir.cleanup()

    def test_roundtrip(self):
        self.assertIsNone(loop.pause_requested(self.path))
        doc = loop.request_pause(self.path, "stepping away", "dwijen")
        self.assertEqual(doc["requested_by"], "dwijen")
        got = loop.pause_requested(self.path)
        self.assertEqual(got["reason"], "stepping away")
        self.assertIn("requested_at", got)
        self.assertTrue(loop.clear_pause_request(self.path))
        self.assertIsNone(loop.pause_requested(self.path))
        self.assertFalse(loop.clear_pause_request(self.path))

    def test_attribution_required(self):
        with self.assertRaises(loop.LoopError):
            loop.request_pause(self.path, "why", "  ")

    def test_corrupt_request_still_pauses_fail_safe(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as fh:
            fh.write("not json{")
        got = loop.pause_requested(self.path)
        self.assertIsNotNone(got)
        self.assertIn("pausing anyway", got["reason"])

    def test_acknowledge_pause_is_the_receipt_before_the_drain(self):
        loop.request_pause(self.path, "stepping away", "dwijen")
        ack_path = os.path.join(self.dir.name, "state", "pause.ack")
        doc = loop.acknowledge_pause(self.path, ack_path,
                                     ["GL2-auth:implementer"])
        self.assertEqual(doc["draining"], ["GL2-auth:implementer"])
        self.assertEqual(doc["request"]["requested_by"], "dwijen")
        with open(ack_path) as fh:
            on_disk = json.load(fh)
        self.assertIn("seen_at", on_disk)
        self.assertIn("no new admissions", on_disk["policy"])

    def test_acknowledge_without_a_request_is_loud(self):
        with self.assertRaises(LoopError):
            loop.acknowledge_pause(
                self.path, os.path.join(self.dir.name, "state", "pause.ack"),
                [])


class PermissionModeTests(unittest.TestCase):
    """I30 — a firing must know (when the build tells it) what mode it runs in."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "statusline-dump.json")

    def tearDown(self):
        self.dir.cleanup()

    def _write(self, doc):
        with open(self.path, "w") as fh:
            json.dump(doc, fh)

    def test_reads_the_mode_when_present(self):
        self._write({"permission_mode": "auto", "rate_limits": {}})
        self.assertEqual(loop.permission_mode(self.path), "auto")
        self._write({"permission_mode": "default"})
        self.assertEqual(loop.permission_mode(self.path), "default")
        self.assertNotIn("default", loop.FIRING_PERMISSION_MODES)
        self.assertNotIn("acceptEdits", loop.FIRING_PERMISSION_MODES)

    def test_absence_is_unknown_never_wrong(self):
        self._write({"rate_limits": {}})  # 2.1.201: field not emitted
        self.assertIsNone(loop.permission_mode(self.path))
        self.assertIsNone(loop.permission_mode(
            os.path.join(self.dir.name, "missing.json")))
        self._write({"permission_mode": ""})
        self.assertIsNone(loop.permission_mode(self.path))


class HeadlessWorkerTests(unittest.TestCase):
    """I26 — the spawn path where model AND effort verifiably bind."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_cmd_carries_every_requested_knob(self):
        cmd = loop.headless_worker_cmd(
            "implement T1", "claude-sonnet-5", effort="max",
            system_prompt="You are the implementer.",
            json_schema_path="harness/config/schemas/handoff.json",
            disallowed_tools=["Edit", "Write"], max_turns=40)
        joined = " ".join(cmd)
        self.assertEqual(cmd[:3], ["claude", "-p", "implement T1"])
        self.assertIn("--model claude-sonnet-5", joined)
        self.assertIn("--effort max", joined)
        self.assertIn("--output-format json", joined)
        self.assertIn("--max-turns 40", joined)
        self.assertIn("--dangerously-skip-permissions", joined)
        self.assertIn("--append-system-prompt You are the implementer.",
                      joined)
        # P3v2-9: the CLI parses --json-schema as INLINE JSON, not a path
        schema_value = cmd[cmd.index("--json-schema") + 1]
        self.assertEqual(json.loads(schema_value)["title"], "worker handoff")
        self.assertIn("--disallowedTools Edit,Write", joined)
        self.assertIn("--no-session-persistence", joined)
        with self.assertRaises(LoopError):
            loop.headless_worker_cmd("x", "claude-sonnet-5",
                                     json_schema_path="/nope/missing.json")

    def test_parse_strips_code_fences_from_a_compliant_worker(self):
        # P3v2-10: fenced final JSON must not read as a contract violation
        handoff = {"outcome": "pass", "summary": "s", "intent": "i",
                   "key_changes_made": ["x"], "key_learnings": []}
        fenced = "```json\n" + json.dumps(handoff, indent=1) + "\n```"
        got = loop.parse_worker_result(json.dumps({"result": fenced}))
        self.assertEqual(got["parsed"]["outcome"], "pass")

    def test_headless_patterns_load_as_a_tuple(self):
        # P3v2-11: the documented incantation must not raise on the tuple
        from harness import failures
        extras = failures.load_patterns(loop.HEADLESS_FAILURE_PATTERNS)
        got = failures.classify(
            'API Error: 429 {"error": "You\'re out of usage credits '
            'for Fable 5"}', extra_patterns=extras)
        self.assertEqual(got["class"], failures.PERMANENT)
        self.assertIn("park", got["why"])

    def test_run_headless_worker_enforces_the_wall_deadline(self):
        import sys
        hang = loop.run_headless_worker(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cwd=self.dir.name, timeout_s=1)
        self.assertTrue(hang["timed_out"])
        self.assertFalse(hang["ok"])
        self.assertIsNone(hang["exit"])
        self.assertLess(hang["wall_secs"], 30)
        fine = loop.run_headless_worker(
            [sys.executable, "-c", "print('{\"result\": \"done\"}')"],
            cwd=self.dir.name, timeout_s=30)
        self.assertTrue(fine["ok"])
        self.assertEqual(fine["exit"], 0)
        self.assertIn("result", fine["stdout"])

    def test_cmd_validates_against_the_allowlist(self):
        from harness.spawncheck import SpawnValidationError
        with self.assertRaises(SpawnValidationError):
            loop.headless_worker_cmd("x", "gpt-99-turbo")
        with self.assertRaises(SpawnValidationError):
            loop.headless_worker_cmd("x", "claude-sonnet-5", effort="ultra")
        with self.assertRaises(LoopError):
            loop.headless_worker_cmd("  ", "claude-sonnet-5")
        with self.assertRaises(LoopError):
            loop.headless_worker_cmd("x", "claude-sonnet-5", max_turns=0)

    def test_spawn_interlock_governs_the_headless_cmd(self):
        import shlex
        from harness import interlocks
        marker = os.path.join(self.dir.name, "run.marker")
        stamp = os.path.join(self.dir.name, "admission-stamp.json")
        loop.acquire_run_marker(marker, "smoke")
        try:
            cmd = " ".join(shlex.quote(c) for c in loop.headless_worker_cmd(
                "implement T1", "claude-sonnet-5", effort="xhigh"))
            self.assertIsNotNone(interlocks.check_spawn(
                "Bash", {"command": cmd}, marker, stamp))
            interlocks.write_admission_stamp(stamp,
                                             {"task_id": "T1", "tick": 1})
            self.assertIsNone(interlocks.check_spawn(
                "Bash", {"command": cmd}, marker, stamp))
        finally:
            loop.release_run_marker(marker)

    def test_overlay_binds_worker_settings_to_the_worktree(self):
        wt = os.path.join(self.dir.name, "wt")
        os.makedirs(wt)
        vault = os.path.join(self.dir.name, "outside-vault")
        os.makedirs(vault)
        path = loop.write_worker_overlay(wt, vault)
        self.assertTrue(path.endswith(
            os.path.join(".claude", "settings.local.json")))
        with open(path) as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk, loop.worker_settings(vault))
        self.assertFalse(on_disk["sandbox"]["allowUnsandboxedCommands"])

    def test_parse_worker_result_normalizes_and_stays_loud(self):
        handoff = {"outcome": "pass", "summary": "s", "intent": "i",
                   "key_changes_made": ["x"], "key_learnings": []}
        doc = {"result": json.dumps(handoff), "session_id": "s1",
               "usage": {"input_tokens": 10, "output_tokens": 5},
               "total_cost_usd": 0.01}
        got = loop.parse_worker_result(json.dumps(doc))
        self.assertEqual(got["parsed"]["outcome"], "pass")
        self.assertEqual(got["usage"]["output_tokens"], 5)
        prose = loop.parse_worker_result(json.dumps(
            {"result": "I did things but forgot the contract"}))
        self.assertIsNone(prose["parsed"])  # the ladder's business, no crash
        with self.assertRaises(LoopError):
            loop.parse_worker_result("not json at all")
        with self.assertRaises(LoopError):
            loop.parse_worker_result(json.dumps({"no_result": True}))

    def test_headless_failure_patterns_classify(self):
        from harness import failures
        extras = failures.load_patterns(list(loop.HEADLESS_FAILURE_PATTERNS))
        got = failures.classify("Error: reached max turns (40)",
                                extra_patterns=extras)
        self.assertEqual(got["class"], failures.PERMANENT)
        got = failures.classify(
            "There's an issue with the selected model (gpt-99-turbo). It may "
            "not exist or you may not have access to it.",
            extra_patterns=extras)
        self.assertEqual(got["class"], failures.PERMANENT)
