#!/usr/bin/env python3
"""merge-gate — a blocking correctness gate over the *merged* tree.

One thing well: given a git repo, a base, a candidate ref, and sound-verifier
commands, judge PASS/FAIL by (1) materializing base+candidate as a real merge
in a throwaway worktree and (2) running every check there. Emit a stamped
report file; exit 0 only on all-pass. `verify` re-checks a stamp's freshness
against the repo's current refs — the anti-merge-skew interlock.

There is deliberately no advisory mode and no zero-check PASS.
Pure stdlib. Contract: README.md next to this file.

Exit codes: 0 pass/fresh · 1 fail/conflict/stale · 2 usage or environment error.
"""

import argparse
import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

TOOL = "merge-gate"
TAIL_LINES = 100


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(repo, *args, check=True):
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        raise GateEnvError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


class GateEnvError(Exception):
    """Environment/usage failure — exit 2, never a verdict."""


def resolve(repo, ref):
    proc = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if proc.returncode != 0:
        raise GateEnvError(f"cannot resolve ref {ref!r} in {repo}")
    return proc.stdout.strip()


def run_check(cmd, cwd, timeout_s):
    """Run one verifier via the shell in the merged worktree. Returns a dict."""
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        output, _ = proc.communicate()
    duration = round(time.monotonic() - started, 3)
    lines = (output or "").splitlines()
    return {
        "cmd": cmd,
        "exit": None if timed_out else proc.returncode,
        "timed_out": timed_out,
        "duration_s": duration,
        "output_lines": len(lines),
        "output_tail": lines[-TAIL_LINES:],
    }


def cmd_run(args):
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(
        os.path.join(repo, ".git")
    ):
        raise GateEnvError(f"not a git repository: {repo}")

    base_sha = resolve(repo, args.base)
    source_sha = resolve(repo, args.ref)

    report = {
        "tool": TOOL,
        "ts": utcnow(),
        "repo": repo,
        "base": {"ref": args.base, "sha": base_sha},
        "source": {"ref": args.ref, "sha": source_sha},
        "merge": {"performed": False, "up_to_date": False, "conflicts": []},
        "checks": [],
        "ok": False,
    }

    worktree = tempfile.mkdtemp(prefix="merge-gate-")
    try:
        # Clean-checkout reproduction: judge a pristine materialization, never
        # the caller's (possibly dirty) working tree.
        git(repo, "worktree", "add", "--detach", worktree, base_sha)

        # Judge the MERGED tree — proven green against base-as-of-now plus the
        # change, not the source tip alone (the v1 B-4 merge-skew lesson).
        merge = git(worktree, "merge", "--no-ff", "--no-commit", source_sha, check=False)
        if merge.returncode != 0:
            conflicts = git(
                worktree, "diff", "--name-only", "--diff-filter=U", check=False
            ).stdout.split()
            report["merge"]["conflicts"] = sorted(conflicts)
            report["merge"]["performed"] = False
        else:
            report["merge"]["performed"] = True
            ready = True
            if "Already up to date" in (merge.stdout + merge.stderr):
                report["merge"]["up_to_date"] = True
            else:
                # Commit the judged merge in the throwaway worktree BEFORE
                # running checks, so checks see exactly the state a landed
                # merge would have: HEAD's tree is the judged tree, status is
                # clean. Without this (smoke run 4, 2026-07-12), HEAD lags the
                # judged tree and status is dirty by construction — any
                # legitimate suite test consulting git state fails
                # environmentally, deterministically, on every attempt.
                # Synthetic identity; hooks skipped — the gate judges via its
                # checks, never via the target repo's hooks.
                committed = git(
                    worktree,
                    "-c", "user.name=merge-gate",
                    "-c", "user.email=merge-gate@invalid",
                    "commit", "--no-verify", "-q",
                    "-m", f"merge-gate: judged merge of {source_sha[:12]} onto {base_sha[:12]}",
                    check=False,
                )
                if committed.returncode != 0:
                    # Fail closed: never run checks against a half-made state.
                    report["merge"]["commit_error"] = committed.stderr.strip()[:400]
                    ready = False
                else:
                    report["merge"]["judged_commit"] = git(
                        worktree, "rev-parse", "HEAD", check=False
                    ).stdout.strip()
            # All checks must pass — and they only run on a committed merge.
            if ready:
                for cmd in args.check:
                    result = run_check(cmd, worktree, args.timeout)
                    report["checks"].append(result)
                report["ok"] = bool(report["checks"]) and all(
                    c["exit"] == 0 for c in report["checks"]
                )
    finally:
        git(repo, "worktree", "remove", "--force", worktree, check=False)
        git(repo, "worktree", "prune", check=False)
        shutil.rmtree(worktree, ignore_errors=True)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "report": os.path.abspath(args.report),
                "base": report["base"],
                "source": report["source"],
                "conflicts": report["merge"]["conflicts"],
                "checks": [
                    {"cmd": c["cmd"], "exit": c["exit"], "timed_out": c["timed_out"]}
                    for c in report["checks"]
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["ok"] else 1


def cmd_verify(args):
    try:
        with open(args.report, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise GateEnvError(f"cannot read report: {exc}")
    for key in ("tool", "ok", "base", "source"):
        if key not in report:
            raise GateEnvError(f"malformed report: missing {key!r}")
    if report["tool"] != TOOL:
        raise GateEnvError(f"not a {TOOL} report: tool={report['tool']!r}")

    repo = os.path.abspath(args.repo)
    reasons = []
    if report["ok"] is not True:
        reasons.append("report is not a PASS")
    for side in ("base", "source"):
        ref, sha = report[side]["ref"], report[side]["sha"]
        try:
            current = resolve(repo, ref)
        except GateEnvError:
            reasons.append(f"{side} ref {ref!r} no longer resolves")
            continue
        if current != sha:
            reasons.append(
                f"{side} moved since gating: {ref} is {current[:12]}, stamp has {sha[:12]}"
            )
    fresh = not reasons
    print(json.dumps({"fresh": fresh, "reasons": reasons}, indent=2, sort_keys=True))
    return 0 if fresh else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gate.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="gate a candidate ref against base on the merged tree")
    p_run.add_argument("--repo", default=".", help="git repository (default: .)")
    p_run.add_argument("--base", default="main", help="target branch/ref (default: main)")
    p_run.add_argument("--ref", required=True, help="candidate branch/ref to judge")
    p_run.add_argument(
        "--check",
        action="append",
        required=True,
        help="sound-verifier shell command run in the merged worktree; repeatable; ALL must exit 0",
    )
    p_run.add_argument(
        "--report", default="merge-gate-report.json", help="stamped report output path"
    )
    p_run.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="per-check deadline in seconds (default 1800); a hung verifier is a FAIL, not a wait",
    )
    p_run.set_defaults(fn=cmd_run)

    p_verify = sub.add_parser(
        "verify", help="re-check a stamp's freshness against current refs (anti-merge-skew)"
    )
    p_verify.add_argument("--report", required=True, help="report file from `run`")
    p_verify.add_argument("--repo", default=".", help="git repository (default: .)")
    p_verify.set_defaults(fn=cmd_verify)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except GateEnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
