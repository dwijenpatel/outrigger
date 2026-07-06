#!/usr/bin/env python3
"""Firing smoke test (I5) — a scripted, zero-quota walk of the build-loop
step sequence in a scratch clone of THIS repo.

Hermetic suites missed P1-5/P1-7-class *composition* defects (each module
green, the sequence broken) and P2-6/P2-8-class *execution* gaps
(registration checks passing while the hook never fires). This module walks
the skill's actual order — plan-ready → marker/closure-hook → quota
bootstrap → admission → interlocked spawn → worker → verdicts → gate
(vault-materialized held-out run included) → interlocked merge → records →
clean close — against real machinery in a throwaway clone, with a **fake
``claude`` binary** standing in for the headless worker (I26 shape) and the
statusline shim fed synthetic stdin (execution proof, not registration
proof).

Zero quota, no network: every model-shaped step is mocked at the process
boundary; everything else is the real code.

CLI:

    python3 -m harness.smoketest [--workdir DIR] [--keep]

Exit 0 when every step passed; 2 otherwise (report on stdout either way).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

from . import admission as _admission
from . import closure as _closure
from . import gate as _gate
from . import governor as _governor
from . import interlocks as _interlocks
from . import ledger as _ledger
from . import loop as _loop
from . import planning as _planning
from . import runlog as _runlog
from . import vault as _vault

_REPO_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, sys
argv = sys.argv[1:]
def need(flag):
    if flag not in argv:
        print(json.dumps({"error": "missing flag " + flag}), file=sys.stderr)
        sys.exit(9)
for flag in ("-p", "--model", "--effort", "--output-format",
             "--max-turns", "--dangerously-skip-permissions"):
    need(flag)
handoff = {"outcome": "pass", "summary": "smoke worker ran",
           "intent": "prove the headless harvest path",
           "key_changes_made": ["(smoke) no-op"], "key_learnings": [],
           "files_touched": []}
print(json.dumps({"result": json.dumps(handoff), "session_id": "smoke-1",
                  "usage": {"input_tokens": 111, "output_tokens": 22},
                  "total_cost_usd": 0.0}))
"""

SPEC_T1 = """# T1-feature — scoped spec (smoke fixture)

Pinned interface: `app.mul(a, b)` returns the arithmetic product of two ints.
Acceptance criteria: visible test `test_app.py` covers mul(3, 4) == 12; the
held-out corpus pins mul(2, 3) == 6 from the spec alone. Constraints: pure
function, no I/O, no new dependencies. Deliverable paths: app.py,
test_app.py only (floors guard protected/**).
"""


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True,
                   capture_output=True, text=True)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _write(root, rel, content):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    return path


def run_smoke(workdir: str, repo_src: str | None = None) -> dict:
    """Walk the firing sequence once. Returns {"ok", "steps": [...]}."""
    steps: list = []
    src = repo_src or _REPO_SRC

    def step(name, ok, detail):
        steps.append({"step": name, "ok": bool(ok), "detail": detail})
        return ok

    def finish():
        ok = all(s["ok"] for s in steps)
        failing = next((s for s in steps if not s["ok"]), None)
        return {"ok": ok, "steps": steps, "workdir": workdir,
                "why": ("smoke green: all "
                        f"{len(steps)} steps passed" if ok else
                        f"{failing['step']}: {failing['detail']}")}

    clone = os.path.join(workdir, "clone")
    vault_dir = os.path.join(workdir, "outside-vault")
    state = os.path.join(clone, "state")
    py = sys.executable

    # 1. scratch clone of the harness repo (committed machinery only; pinned
    # to main so the walk is identical no matter which branch the source
    # checkout happens to be on)
    subprocess.run(["git", "clone", "-q", "--branch", "main", src, clone],
                   check=True, capture_output=True)
    _git(clone, "config", "user.email", "smoke@harness")
    _git(clone, "config", "user.name", "smoke")
    step("clone", os.path.isdir(os.path.join(clone, "harness")),
         "scratch clone with committed machinery")

    # 2. quota bootstrap BEFORE any live source exists: preflight must refuse
    proc = subprocess.run(
        [py, "-m", "harness.governor", "--preflight",
         "--statusline-json", os.path.join(state, "statusline-dump.json")],
        cwd=clone, capture_output=True, text=True)
    step("preflight_cold", proc.returncode == 3,
         f"no live rung -> conservative (exit {proc.returncode})")
    proc = subprocess.run(
        [py, "-m", "harness.governor", "--assume-occupancy", "0.3",
         "--acked-by", "smoke-operator"],
        cwd=clone, capture_output=True, text=True)
    assumed_ok = proc.returncode == 0 and "operator-assumed" in proc.stdout
    step("bootstrap_assumption", assumed_ok,
         "acked assumption is attributed, never ambient")

    # 3. statusline shim: EXECUTION proof via synthetic stdin (P2-6/P2-8) —
    # including the permission_mode field (I30; ships in newer CLIs)
    stdin_doc = json.dumps({
        "workspace": {"project_dir": clone},
        "permission_mode": "auto",
        "rate_limits": {"five_hour": {"used_percentage": 10},
                        "seven_day": {"used_percentage": 30}}})
    proc = subprocess.run([py, os.path.join(clone, "hooks",
                                            "statusline_dump.py")],
                          input=stdin_doc, cwd=clone,
                          capture_output=True, text=True)
    dump_path = os.path.join(state, "statusline-dump.json")
    step("statusline_shim",
         os.path.isfile(dump_path)
         and _loop.permission_mode(dump_path) == "auto",
         "shim executed on synthetic stdin; dump at the resolved path; "
         "permission_mode readable through loop.permission_mode (I30)")
    proc = subprocess.run(
        [py, "-m", "harness.governor", "--statusline-json", dump_path],
        cwd=clone, capture_output=True, text=True)
    live_ok = False
    if proc.returncode == 0:
        try:
            live_ok = json.loads(proc.stdout).get("source") == "statusline"
        except json.JSONDecodeError:
            live_ok = False
    step("governor_live_rung", live_ok,
         "decide consumed the shim's dump as the statusline rung")

    # 4. vault: sanctioned configure CLI + a held-out corpus with manifest
    proc = subprocess.run(
        [py, "-m", "harness.vault", "configure", "--vault-path", vault_dir],
        cwd=clone, capture_output=True, text=True)
    step("vault_configure", proc.returncode == 0,
         f"configure exit {proc.returncode}: {proc.stderr.strip()[:120]}")
    _write(vault_dir, "T1-feature/test_heldout_smoke.py",
           "import app\n\n\ndef test_heldout_mul():\n"
           "    assert app.mul(2, 3) == 6\n")
    _write(vault_dir, "T1-feature/conftest.py",
           "import os, sys\nsys.path.insert(0, os.getcwd())\n")
    _write(vault_dir, "manifest.json",
           json.dumps({"entries": _vault.build_manifest(vault_dir)},
                      indent=1, sort_keys=True))

    # 5. plan fixture (ledger + scoped spec + floors + touches) — committed,
    # ratified, frozen: exactly what plan-build leaves behind
    _write(clone, "app.py", "def mul(a, b):\n    return a * b\n")
    _write(clone, "test_app.py",
           "import unittest\nimport app\n\n\nclass T(unittest.TestCase):\n"
           "    def test_mul(self):\n"
           "        self.assertEqual(app.mul(3, 4), 12)\n\n\n"
           "if __name__ == '__main__':\n    unittest.main()\n")
    _write(clone, os.path.join("plan", "tasks.json"), json.dumps({
        "tasks": [{"id": "T1-feature", "phase": "1", "profile": "routine",
                   "deps": [], "may_be_invalidated_by": [],
                   "touches": ["app.py", "test_app.py"]}]}, indent=1))
    _write(clone, os.path.join("plan", "specs", "T1-feature.md"), SPEC_T1)
    _write(clone, os.path.join("plan", "floors.json"), json.dumps(
        {"floors": [{"glob": "protected/**", "min_profile": "high"}]}))
    ledger = _planning.load_tasks(os.path.join(clone, "plan"))
    _closure.freeze_snapshot(ledger, os.path.join(state,
                                                  "plan-snapshot.json"))
    _planning.ratify(os.path.join(clone, "plan"), "smoke-operator")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "smoke: plan + vault config + seed app")

    ready = _planning.plan_ready(
        os.path.join(clone, "plan"), os.path.join(state,
                                                  "plan-snapshot.json"),
        vault_config_path=os.path.join(clone, "harness", "config",
                                       "vault-isolation.json"),
        repo_root=clone)
    step("plan_ready", ready["ready"], ready["why"])

    # 6. marker + closure hook config (fail-closed stop machinery armed)
    marker_path = os.path.join(state, "run.marker")
    _loop.acquire_run_marker(marker_path, "smoke-firing")
    _loop.closure_hook_config(
        os.path.join(state, "closure-hook.json"),
        snapshot=os.path.join(state, "plan-snapshot.json"),
        ledger=os.path.join("plan", "tasks.json"),
        events=os.path.join(state, "ledger-events.jsonl"))
    step("marker_and_closure_hook",
         _loop.run_marker_live(marker_path) is not None,
         "run marker live; closure hook config on disk")

    # 7. cold-start admission at the acked assumption (P3-1 ladder)
    decision = _admission.admit_task("routine", occupancy=0.3)
    step("admission_cold_start", decision.get("admit") is True,
         decision.get("why", "no reason returned"))
    stamp_path = os.path.join(state, "admission-stamp.json")
    _interlocks.write_admission_stamp(stamp_path,
                                      {"task_id": "T1-feature", "tick": 1})

    # 8. interlocked spawn: the I26 headless command, governed by the stamp
    events = _ledger.EventLog(os.path.join(state, "ledger-events.jsonl"))
    runlog = _runlog.RunLog(os.path.join(state, "run-log.jsonl"))
    from . import spawncheck as _spawncheck
    resolved = _spawncheck.validate_spawn(model="claude-sonnet-5",
                                          effort="max")
    worker_cmd = _loop.headless_worker_cmd(
        "Implement T1-feature per plan/specs/T1-feature.md; final message = "
        "handoff JSON only.", resolved["model"], effort=resolved["effort"],
        system_prompt="smoke worker", max_turns=10)
    cmd_str = " ".join(shlex.quote(c) for c in worker_cmd)
    no_stamp = _interlocks.check_spawn(
        "Bash", {"command": cmd_str}, marker_path,
        os.path.join(state, "missing-stamp.json"))
    with_stamp = _interlocks.check_spawn(
        "Bash", {"command": cmd_str}, marker_path, stamp_path)
    step("spawn_interlock", no_stamp is not None and with_stamp is None,
         "headless cmd blocked without a fresh admission stamp; "
         "allowed with one")

    # 9. worker phase in a task worktree: write-ahead spawn record, overlay,
    # fake-claude headless run (harvest), workspace effect, commit
    wt = os.path.join(workdir, "wt-T1")
    _git(clone, "worktree", "add", "-q", "-b", "task/T1-feature", wt, "main")
    overlay = _loop.write_worker_overlay(wt, vault_dir)
    events.record_status("T1-feature", "in_progress",
                         note="smoke: admitted, spawning")
    runlog.append(_runlog.worker_event(
        "task_spawn", "T1-feature", "implementer", resolved, attempt=1,
        branch="task/T1-feature", firing="smoke-firing"))
    fake_bin = os.path.join(workdir, "bin")
    fake_claude = _write(fake_bin, "claude", FAKE_CLAUDE)
    os.chmod(fake_claude, 0o755)
    env = _loop.headless_env(dict(os.environ))
    env["PATH"] = fake_bin + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(worker_cmd, cwd=wt, env=env,
                          capture_output=True, text=True, timeout=60)
    harvest = None
    if proc.returncode == 0:
        try:
            harvest = _loop.parse_worker_result(proc.stdout)
        except _loop.LoopError:
            harvest = None
    step("headless_worker_harvest",
         bool(harvest and harvest["parsed"]
              and harvest["parsed"]["outcome"] == "pass"
              and harvest["usage"].get("output_tokens") == 22),
         f"fake claude exit {proc.returncode}; parsed handoff + usage "
         f"{'ok' if harvest else proc.stderr.strip()[:120]}")
    step("worker_overlay_untracked",
         os.path.isfile(overlay) and not subprocess.run(
             ["git", "-C", wt, "status", "--porcelain"],
             capture_output=True, text=True).stdout.strip(),
         "settings.local.json bound in the worktree and gitignored "
         "(require_clean stays green)")
    _write(wt, "app.py",
           "def mul(a, b):\n    return a * b\n\n\n"
           "def mul_all(items):\n"
           "    total = 1\n"
           "    for item in items:\n        total = mul(total, item)\n"
           "    return total\n")
    _write(wt, "test_app.py",
           "import unittest\nimport app\n\n\nclass T(unittest.TestCase):\n"
           "    def test_mul(self):\n"
           "        self.assertEqual(app.mul(3, 4), 12)\n\n"
           "    def test_mul_all(self):\n"
           "        self.assertEqual(app.mul_all([2, 3, 4]), 24)\n\n\n"
           "if __name__ == '__main__':\n    unittest.main()\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "T1: mul_all")

    # 10. blind verdict (routine panel = 1 lens) + the full gate, including
    # the vault-materialized held-out run and the PASS stamp
    vdir = os.path.join(state, "verdicts", "T1-feature")
    _write(clone, os.path.relpath(os.path.join(vdir, "correctness.json"),
                                  clone),
           json.dumps({"lens": "correctness", "verdict": "PASS",
                       "evidence": ["visible suite green in clean checkout"],
                       "intent": "smoke lens"}))
    report = _gate.run_gate(
        repo=wt, branch="task/T1-feature", base="main",
        test_cmd=f"{py} -m unittest test_app -v",
        verdict_dir=vdir, task_profile="routine",
        floor_config_path=os.path.join("plan", "floors.json"),
        vault_path=vault_dir,
        evidence_dir=os.path.join(state, "evidence", "T1-feature"),
        stamp_dir=os.path.join(state, "gate-stamps"),
        required_steps_path=os.path.join("harness", "config",
                                         "gate-required-steps.json"),
        heldout_cmd=f"{py} -m pytest .heldout -q")
    heldout_step = next((s for s in report["steps"]
                         if s["step"] == "heldout_tests"), None)
    step("gate_pass", report["ok"],
         report.get("why") or "; ".join(
             f"{s['step']}:{'ok' if s['ok'] else s['detail'][:80]}"
             for s in report["steps"] if not s["ok"]) or "gate green")
    step("gate_heldout_ran", bool(heldout_step and heldout_step["ok"]),
         (heldout_step or {}).get("detail", "heldout step missing")[:120])

    # 11. interlocked merge, then records + clean close
    merge_cmd = "git merge --no-ff task/T1-feature -m merge-T1"
    verdict = _interlocks.check_merge(
        merge_cmd, repo_dir=clone,
        stamp_dir=os.path.join(state, "gate-stamps"),
        marker_path=marker_path)
    step("merge_interlock", verdict is None,
         verdict or "fresh PASS stamp for branch+HEAD -> merge allowed")
    _git(clone, "merge", "--no-ff", "task/T1-feature", "-m", "merge-T1")
    usage = harvest["usage"] if harvest else {}
    runlog.append({"event": "task_complete", "task_id": "T1-feature",
                   "role": "implementer", "outcome": "pass", "attempt": 1,
                   "profile": "routine", "model": resolved["model"],
                   "tier": resolved["tier"], "effort": resolved["effort"],
                   "total_tokens": (usage.get("input_tokens", 0)
                                    + usage.get("output_tokens", 0)),
                   "firing": "smoke-firing"})
    events.record_status("T1-feature", "done",
                         note="smoke: merged via gate stamp")
    events.set_resume_marker({"firing": "smoke-firing",
                              "reason": "smoke complete",
                              "completed": "T1-feature"})
    _loop.release_run_marker(marker_path)
    proc = subprocess.run([py, os.path.join(clone, "hooks",
                                            "closure_gate.py")],
                          cwd=clone, input="{}", capture_output=True,
                          text=True)
    step("closure_inert_after_release", proc.returncode == 0,
         f"closure hook exit {proc.returncode} with marker released")

    # 12. the tree the next firing resumes from: clean, validated, stamped
    dirty = subprocess.run(["git", "-C", clone, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    records, record_errors = runlog.read()
    step("final_state",
         not dirty and not record_errors and len(records) == 2
         and _loop.run_marker_live(marker_path) is None
         and os.path.isfile(os.path.join(
             state, "gate-stamps", "task__T1-feature.json")),
         (f"dirty tree: {dirty[:120]}" if dirty else
          f"record errors: {record_errors[:2]}" if record_errors else
          "clean tree; run-log validates; marker released; stamp present"))
    return finish()


def _cli(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workdir", help="scratch dir (default: mkdtemp)")
    p.add_argument("--repo", help="repo to clone (default: this checkout)")
    p.add_argument("--keep", action="store_true",
                   help="keep the scratch dir for inspection")
    args = p.parse_args(argv)
    workdir = args.workdir or tempfile.mkdtemp(prefix="firing-smoke-")
    os.makedirs(workdir, exist_ok=True)
    try:
        result = run_smoke(workdir, repo_src=args.repo)
    finally:
        if not args.keep and not args.workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    print(json.dumps({k: v for k, v in result.items() if k != "workdir"},
                     indent=2))
    if not result["ok"]:
        print(f"smoke NOT green: {result['why']}", file=sys.stderr)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(_cli())
