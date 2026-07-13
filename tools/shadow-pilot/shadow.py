#!/usr/bin/env python3
"""shadow-pilot — one T2 shadow comparison for one completed harness task.

The amended pilot-1 protocol (docs/research/internal/t2-pilot-1/protocol.md,
Amendment 1): after the harness lands a real full-tier task, this tool
- has a THIRD blind author write an ARBITER suite from the ratified spec
  against the task's pre-task base state (never seeing either implementation),
- runs the plain-assistant SHADOW arm on the same spec in a throwaway clone
  (its work never lands anywhere),
- grades BOTH landed states with the sealed arbiter suite, symmetrically,
- appends one comparison record to shadow-log.jsonl and writes blinded diffs.

SPENDS REAL QUOTA (one author + one shadow session, ~$3-4): operator-run or
operator-directed, never wired into the loop or CI. Composition per R5:
sibling artifacts are invoked ONLY as subprocess CLIs (heldout-suite,
merge-gate, run-ledger); workers only through the launcher file contract.

Exit codes: 0 comparison recorded (whoever won) - 2 usage/setup error -
1 infrastructure failure mid-comparison (partial artifacts kept).
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
HELDOUT = os.path.join(TOOLS, "heldout-suite", "heldout.py")
GATE = os.path.join(TOOLS, "merge-gate", "gate.py")
LEDGER = os.path.join(TOOLS, "run-ledger", "ledger.py")
ROLE_MD = os.path.join(TOOLS, "heldout-suite", "ROLE.md")


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(argv, cwd=None, timeout=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def git(repo, *args):
    proc = run(["git", "-C", repo, *args])
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class ShadowError(Exception):
    pass


def clone_at(repo, sha, dst, branch):
    rc, _, err = git(".", "clone", "-q", "--no-hardlinks", repo, dst)
    if rc != 0:
        raise ShadowError(f"clone failed: {err}")
    rc, _, err = git(dst, "checkout", "-q", "-b", branch, sha)
    if rc != 0:
        raise ShadowError(f"checkout {sha[:12]} failed: {err}")


def launch(launcher, bundle_dir, role, worker, isolation, cwd, instructions, timeout_s):
    """Launcher file contract (tools/exec-loop/launchers/CONTRACT.md)."""
    os.makedirs(bundle_dir)
    with open(os.path.join(bundle_dir, "instructions.md"), "w", encoding="utf-8") as fh:
        fh.write(instructions)
    with open(os.path.join(bundle_dir, "params.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {"contract": 1, "role": role, "worker": worker, "isolation": isolation,
             "cwd": cwd, "timeout_s": timeout_s},
            fh, indent=2,
        )
    proc = run([sys.executable, launcher, bundle_dir], timeout=timeout_s + 120)
    result_path = os.path.join(bundle_dir, "result.json")
    result = {}
    if os.path.exists(result_path):
        with open(result_path, encoding="utf-8") as fh:
            result = json.load(fh)
    result["launcher_exit"] = proc.returncode
    return result


def suite_commands(ws):
    with open(os.path.join(ws, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    suite_args = " ".join(manifest["run"]["argv"][1:])
    return [
        f"python3 {HELDOUT} verify --workspace {ws}",
        f"PYTHONPATH=. python3 {suite_args}",
    ], manifest


def grade(repo, sha, checks, report_path):
    """Run every check against a committed state (self-judge gate, the
    closure trick): PASS means exactly 'these commands exited 0 there'."""
    argv = [sys.executable, GATE, "run", "--repo", repo,
            "--base", sha, "--ref", sha, "--report", report_path]
    for cmd in checks:
        argv += ["--check", cmd]
    proc = run(argv)
    report = {}
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as fh:
            report = json.load(fh)
    failing = [c["cmd"] for c in report.get("checks", []) if c.get("exit") != 0]
    return {"ok": proc.returncode == 0, "failing": failing, "report": report_path}


def arbiter_instructions(ws, base_clone, task_id):
    return "\n\n".join([
        f"You are the ARBITER TEST-AUTHOR for task `{task_id}` — a third, independent "
        "author whose suite will judge two implementations you will never see.",
        f"Your authoring workspace is: {ws}",
        f"Read {ws}/authoring/task.json (the task and plan context) and "
        f"{ws}/authoring/AUTHORING.md, then follow the role contract at {ROLE_MD}.",
        f"The reference repository (the PRE-CHANGE base state) is: {base_clone} — read it "
        "for conventions and real module paths. Write stdlib-unittest tests into "
        f"{ws}/suite/ as test_*.py files.",
        "Author from the spec alone. At least one test must FAIL against the unchanged "
        "base (seal policy); base-passing regression guards are welcome. You never run seal.",
    ])


def shadow_instructions(plan, task):
    return "\n\n".join([
        f"You are implementing task `{task['id']}`: {task['title']}",
        f"SPEC:\n{task['spec']}",
        f"PLAN GOAL: {plan.get('goal', '')}",
        "PLAN CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in plan.get("constraints", [])),
        "DECISIONS (context — do not re-decide):\n"
        + "\n".join(f"- Q: {d['q']}\n  A: {d['a']}" for d in plan.get("decisions", [])),
        "Implement the spec in this repository (your cwd). Run the task's stated checks"
        + (f" ({'; '.join(task.get('checks', []))})" if task.get("checks") else "")
        + " and the repository's existing tests, fix what fails, and COMMIT all changes "
        "(git add -A && git commit) when you judge the work done. Work not committed "
        "does not exist. Do not touch paths outside this repository.",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shadow.py", description=__doc__.splitlines()[0])
    parser.add_argument("--plan", required=True, help="the ratified plan.json the harness ran")
    parser.add_argument("--task", required=True, help="task id within the plan")
    parser.add_argument("--repo", required=True, help="the real repository (arm H landed here)")
    parser.add_argument("--base", required=True, help="SHA the task started from (gate report base)")
    parser.add_argument("--merged", required=True, help="SHA the harness landed (arm H state)")
    parser.add_argument("--out", required=True, help="shadow-pilot output dir (log + artifacts)")
    parser.add_argument("--launcher", required=True, help="launcher executable")
    parser.add_argument("--model", default="claude-opus-4-8", help="worker model (both spawns)")
    parser.add_argument("--effort", default="xhigh")
    parser.add_argument("--timeout-s", type=int, default=3600)
    args = parser.parse_args(argv)

    try:
        with open(args.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read plan: {exc}", file=sys.stderr)
        return 2
    task = next((t for t in plan.get("tasks", []) if t.get("id") == args.task), None)
    if task is None:
        print(f"error: task {args.task!r} not in plan", file=sys.stderr)
        return 2
    tier = task.get("tier") or plan.get("risk_tier") or "full"
    if tier != "full":
        print(f"warning: task tier is {tier!r} — shadow comparisons target full-tier tasks",
              file=sys.stderr)
    repo = os.path.realpath(args.repo)
    for name, sha in (("base", args.base), ("merged", args.merged)):
        rc, _, _ = git(repo, "rev-parse", "--verify", f"{sha}^{{commit}}")
        if rc != 0:
            print(f"error: --{name} {sha!r} does not resolve in {repo}", file=sys.stderr)
            return 2

    stamp = utcnow().replace(":", "")
    cmp_dir = os.path.join(os.path.realpath(args.out), f"{args.task}-{stamp}")
    os.makedirs(cmp_dir)
    log_path = os.path.join(os.path.realpath(args.out), "shadow-log.jsonl")
    base_clone = os.path.join(cmp_dir, "base-clone")
    shadow_clone = os.path.join(cmp_dir, "shadow-clone")
    worker = {"tool": "claude", "model": args.model, "effort": args.effort}

    try:
        # 1. Arbiter: blind third author against the PRE-task base state.
        clone_at(repo, args.base, base_clone, "arbiter-base")
        mat = run([sys.executable, HELDOUT, "materialize", "--plan", args.plan,
                   "--task", args.task, "--repo", base_clone, "--base", args.base,
                   "--out", os.path.join(cmp_dir, "arbiter")])
        if mat.returncode != 0:
            raise ShadowError(f"materialize failed: {mat.stderr.strip()}")
        ws = os.path.join(cmp_dir, "arbiter", args.task)
        arbiter_result = launch(
            args.launcher, os.path.join(cmp_dir, "bundle-arbiter"), "author", worker,
            # Contamination wall: the arbiter must never see EITHER implementation —
            # the live repo holds arm H's landed code.
            {"deny_read": [repo], "sandbox": True, "network": True},
            ws, arbiter_instructions(ws, base_clone, args.task), args.timeout_s,
        )
        if not arbiter_result.get("ok"):
            raise ShadowError(f"arbiter author failed: {json.dumps({k: arbiter_result.get(k) for k in ('exit', 'refused_reason', 'error_summary')})}")
        seal = run([sys.executable, HELDOUT, "seal", "--workspace", ws, "--repo", base_clone])
        if seal.returncode != 0:
            raise ShadowError(f"arbiter seal failed: {seal.stderr.strip()}")
        seal_summary = json.loads(seal.stdout)

        # 2. Shadow arm: the plain assistant, throwaway clone, never lands.
        clone_at(repo, args.base, shadow_clone, "shadow")
        shadow_result = launch(
            args.launcher, os.path.join(cmp_dir, "bundle-shadow"), "shadow", worker,
            # The shadow must see neither the arbiter suite nor arm H's code.
            {"deny_read": [os.path.realpath(ws), repo], "sandbox": True, "network": True},
            shadow_clone, shadow_instructions(plan, task), args.timeout_s,
        )
        rc, ahead, _ = git(shadow_clone, "rev-list", "--count", f"{args.base}..HEAD")
        shadow_landed = shadow_result.get("ok", False) and int(ahead or "0") > 0
        rc, shadow_sha, _ = git(shadow_clone, "rev-parse", "HEAD")

        # 3. Grade both arms with the same instrument.
        checks, manifest = suite_commands(ws)
        checks = list(task.get("checks", [])) + checks
        grade_h = grade(repo, args.merged, checks, os.path.join(cmp_dir, "grade-armH.json"))
        grade_n = (grade(shadow_clone, shadow_sha, checks, os.path.join(cmp_dir, "grade-armN.json"))
                   if shadow_landed else {"ok": False, "failing": ["(shadow produced no committed work)"], "report": None})

        # 4. Blinded diffs: deterministic-but-opaque A/B order; mapping sealed
        #    in its own file the reviewer opens only after reviewing.
        flip = int(hashlib.sha256(f"{args.task}-{stamp}".encode()).hexdigest(), 16) % 2
        _, diff_h, _ = git(repo, "diff", f"{args.base}..{args.merged}")
        diff_n = ""
        if shadow_landed:
            _, diff_n, _ = git(shadow_clone, "diff", f"{args.base}..HEAD")
        pair = [("harness", diff_h), ("shadow", diff_n)]
        if flip:
            pair.reverse()
        for label, diff in zip(("A", "B"), pair):
            with open(os.path.join(cmp_dir, f"diff-{label}.patch"), "w", encoding="utf-8") as fh:
                fh.write(diff[1] + "\n")
        with open(os.path.join(cmp_dir, "SEALED-mapping.json"), "w", encoding="utf-8") as fh:
            json.dump({"A": pair[0][0], "B": pair[1][0],
                       "note": "open AFTER the blinded review; record whether you could tell"},
                      fh, indent=2)

        # 5. One comparison record, appended to the accumulating log.
        record = {
            "task": args.task, "tier": tier, "plan": os.path.realpath(args.plan),
            "base": args.base, "merged": args.merged,
            "shadow_sha": shadow_sha if shadow_landed else None,
            "shadow_landed": shadow_landed,
            "arbiter": {"manifest_sha256": seal_summary.get("manifest_sha256"),
                        "fails_on_base": seal_summary.get("fails_on_base"),
                        "usage": arbiter_result.get("usage")},
            "shadow_usage": shadow_result.get("usage"),
            "grade_armH": {"ok": grade_h["ok"], "failing": grade_h["failing"]},
            "grade_armN": {"ok": grade_n["ok"], "failing": grade_n["failing"]},
            "artifacts": cmp_dir,
        }
        append = run([sys.executable, LEDGER, "append", log_path,
                      "--kind", "measurement", "--subject", f"t2/shadow/{args.task}",
                      "--source", "shadow-pilot", "--data", json.dumps(record)])
        if append.returncode != 0:
            raise ShadowError(f"log append failed: {append.stderr.strip()}")

        print(json.dumps({"ok": True, "armH_ok": grade_h["ok"], "armN_ok": grade_n["ok"],
                          "log": log_path, "artifacts": cmp_dir}, indent=2))
        return 0
    except ShadowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc), "artifacts": cmp_dir}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
