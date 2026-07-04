#!/usr/bin/env python3
"""C5 — gate self-test harness: every gate proves itself with a failing case.

Design §7: enforcement that has never been seen to block is assumed broken. For
each gate this runs (a) a **violation case that must block** (exit 2) and (b) a
**clean case that must pass** (exit 0) — both in hermetic scratch fixtures, so
the self-test spends zero tokens and touches nothing real. The advisory C1 hook
is proven to warn *and* to never block. The **vault canary** is exercised both
ways: a readable vault must be *detected* as broken, and a denied vault must
report isolation OK.

The vault-canary production check (`--vault <path>`) is honest about
environment: run from an unsandboxed operator context the vault will read
successfully and the canary REPORTS THE BOUNDARY BROKEN — that is the correct
answer, not a self-test bug; the passing run must happen from the worker
context the gate actually spawns.

CLI: ``python3 -m harness.selftest`` → JSON report, exit 0 only if every gate
proved both directions.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile

from . import vault as _vault

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO_ROOT, "hooks")


def _run(script: str, stdin_doc=None, args=(), cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, os.path.join(HOOKS, script), *args],
        input=json.dumps(stdin_doc) if stdin_doc is not None else "",
        capture_output=True, text=True, timeout=60, cwd=cwd)


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def _make_repo(root: str) -> str:
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "selftest@harness")
    _git(repo, "config", "user.name", "selftest")
    return repo


def _case(name, must_block: bool, proc) -> dict:
    blocked = proc.returncode == 2
    ok = blocked if must_block else proc.returncode == 0
    return {"case": name, "expected": "block" if must_block else "pass",
            "got": f"exit {proc.returncode}", "ok": ok,
            "stderr": proc.stderr.strip()[:200]}


def run_selftests() -> dict:
    """Prove every gate both ways. Returns {"ok": bool, "cases": [...]}."""
    cases = []

    # -- C1 advisory: warns on prefix edit, never blocks (even on garbage) ----
    warn = _run("prefix_edit_warn.py",
                {"tool_name": "Edit", "tool_input": {"file_path": "CLAUDE.md"}})
    cases.append({"case": "C1 warns on prefix edit", "expected": "warn+pass",
                  "got": f"exit {warn.returncode}",
                  "ok": warn.returncode == 0 and "prefix-edit" in warn.stderr,
                  "stderr": warn.stderr.strip()[:200]})
    garbage = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "prefix_edit_warn.py")],
        input="not json", capture_output=True, text=True, timeout=60)
    cases.append({"case": "C1 fails OPEN on garbage (advisory)",
                  "expected": "pass", "got": f"exit {garbage.returncode}",
                  "ok": garbage.returncode == 0, "stderr": ""})

    # -- C2 destructive git ----------------------------------------------------
    cases.append(_case("C2 blocks force push", True, _run(
        "git_guard.py", {"tool_name": "Bash",
                         "tool_input": {"command": "git push --force"}})))
    cases.append(_case("C2 passes safe git", False, _run(
        "git_guard.py", {"tool_name": "Bash",
                         "tool_input": {"command": "git status"}})))
    cases.append(_case("C2 fails CLOSED on garbage", True, subprocess.run(
        [sys.executable, os.path.join(HOOKS, "git_guard.py")],
        input="not json", capture_output=True, text=True, timeout=60)))

    with tempfile.TemporaryDirectory() as root:
        repo = _make_repo(root)

        # -- C2 machinery paths on a task branch --------------------------------
        with open(os.path.join(repo, "x"), "w") as fh:
            fh.write("x")
        _git(repo, "add", "x")
        _git(repo, "commit", "-q", "-m", "seed")
        _git(repo, "checkout", "-q", "-b", "task/t1")
        cases.append(_case("C2 blocks machinery edit on task branch", True, _run(
            "git_guard.py",
            {"tool_name": "Edit", "cwd": repo,
             "tool_input": {"file_path": "harness/governor.py"}})))
        cases.append(_case("C2 passes product edit on task branch", False, _run(
            "git_guard.py",
            {"tool_name": "Edit", "cwd": repo,
             "tool_input": {"file_path": "src/app.py"}})))

        # -- C3 risk floor, config from the ratified ref ------------------------
        _git(repo, "checkout", "-q", "main")
        with open(os.path.join(repo, "floors.json"), "w") as fh:
            json.dump({"floors": [{"glob": "billing/**",
                                   "min_profile": "critical"}]}, fh)
        _git(repo, "add", "floors.json")
        _git(repo, "commit", "-q", "-m", "floors")
        base = ["--floor-config", "floors.json", "--ref", "main", "--repo", repo]
        cases.append(_case("C3 blocks mis-tagged floored diff", True, _run(
            "risk_floor_check.py",
            args=base + ["--profile", "routine", "billing/stripe.py"])))
        cases.append(_case("C3 passes adequate profile", False, _run(
            "risk_floor_check.py",
            args=base + ["--profile", "critical", "billing/stripe.py"])))
        cases.append(_case("C3 fails CLOSED on missing config", True, _run(
            "risk_floor_check.py",
            args=["--floor-config", "ghost.json", "--repo", repo,
                  "--profile", "critical"])))

        # -- C4 held-out drop ----------------------------------------------------
        vault_dir = os.path.join(root, "vault")
        _vault.write_canary(vault_dir)
        with open(os.path.join(vault_dir, "test_holdout.py"), "w") as fh:
            fh.write("def test_hidden(): assert True\n")
        _vault.save_manifest(vault_dir, _vault.build_manifest(vault_dir))
        cases.append(_case("C4 passes intact corpus", False, _run(
            "heldout_drop_check.py", args=["--vault", vault_dir])))
        os.unlink(os.path.join(vault_dir, "test_holdout.py"))
        cases.append(_case("C4 blocks dropped held-out test", True, _run(
            "heldout_drop_check.py", args=["--vault", vault_dir])))
        cases.append(_case("C4 fails CLOSED on missing manifest", True, _run(
            "heldout_drop_check.py", args=["--vault", os.path.join(root, "no")])))

        # -- D1 vault canary, both directions ------------------------------------
        readable = _vault.canary_read_attempt(vault_dir)
        cases.append({"case": "canary DETECTS a readable vault",
                      "expected": "isolation_ok=False",
                      "got": str(readable["isolation_ok"]),
                      "ok": readable["isolation_ok"] is False,
                      "stderr": readable["detail"][:200]})
        denied = os.path.join(root, "denied-vault")
        _vault.write_canary(denied)
        os.chmod(denied, 0)  # simulate the OS-enforced denial
        try:
            blocked_read = _vault.canary_read_attempt(denied)
        finally:
            os.chmod(denied, stat.S_IRWXU)
        cases.append({"case": "canary passes when the read is denied",
                      "expected": "isolation_ok=True",
                      "got": str(blocked_read["isolation_ok"]),
                      "ok": blocked_read["isolation_ok"] is True,
                      "stderr": blocked_read["detail"][:200]})

        # -- D1 isolation declaration completeness --------------------------------
        with open(os.path.join(REPO_ROOT, "harness", "config",
                               "vault-isolation.json")) as fh:
            declared = json.load(fh)
        missing = _vault.validate_isolation(declared)
        cases.append({"case": "isolation declaration covers all six layers",
                      "expected": "no missing layers", "got": str(missing or "ok"),
                      "ok": not missing, "stderr": ""})

    return {"ok": all(c["ok"] for c in cases), "cases": cases,
            "proved": sum(c["ok"] for c in cases), "total": len(cases)}


def _cli(argv=None) -> int:
    report = run_selftests()
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
