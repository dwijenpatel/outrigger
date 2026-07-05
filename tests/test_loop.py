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
