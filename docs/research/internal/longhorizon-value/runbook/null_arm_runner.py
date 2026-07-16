#!/usr/bin/env python3
"""null_arm_runner.py — the ungated control arms (N: diligent Sonnet 5,
F: frontier-solo Opus 4.8) for the long-horizon value experiment.

Per ratified plan, in chain order: one fresh worker session gets the SAME
instruction body the gated arm's implementer receives (title, spec, plan
goal/constraints/decisions, the same checks) with exactly one delta — it
works on the repo's `main` branch directly (no worktree, no blind suite,
no gate, no retry, no stop channel). The session self-tests and commits;
the runner records HEAD before/after and proceeds to the next task
REGARDLESS of the session's outcome (registered protocol: the ungated arms
have no stop channel — a session that lands nothing is recorded, and the
chain continues so downstream compounding can be measured).

Infrastructure failures are different from arm outcomes: a launcher
REFUSAL or spawn failure aborts the run (fix the environment, re-run —
completed tasks are skipped via the ledger); a session that ran (even to
timeout) is an arm outcome and never aborts.

Usage:
  python3 null_arm_runner.py --arm N --model claude-sonnet-5  --repo ~/repos/eaitl-arm-N --yes
  python3 null_arm_runner.py --arm F --model claude-opus-4-8  --repo ~/repos/eaitl-arm-F --yes
  ... --dry-run      # launcher --dry-run: print what WOULD spawn; no quota, no ledger
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUTRIGGER = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
SPECS = os.path.abspath(os.path.join(HERE, "..", "specs"))
LAUNCHER = os.path.join(OUTRIGGER, "tools", "exec-loop", "launchers", "claude_p.py")
PREFLIGHT = os.path.join(OUTRIGGER, "tools", "plan-preflight", "preflight.py")
LEDGER_CLI = os.path.join(OUTRIGGER, "tools", "run-ledger", "ledger.py")
TIMEOUT_S = 3600  # identical to the gated arm's implementer_timeout_s


def chain_plans():
    with open(os.path.join(HERE, "chain-order.txt"), encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]


def instructions(plan, task):
    # The gated arm's implementer prompt (exec-loop implementer_instructions),
    # reproduced section-for-section; the ONLY delta is the working-copy
    # sentence — main branch instead of a dedicated worktree. Fairness
    # invariant: same spec, same context, same checks, same commit protocol.
    checks = f" ({'; '.join(task.get('checks', []))})" if task.get("checks") else ""
    return "\n\n".join([
        f"You are the IMPLEMENTER for task `{task['id']}`: {task['title']}",
        f"SPEC:\n{task['spec']}",
        f"PLAN GOAL: {plan.get('goal', '')}",
        "PLAN CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in plan.get("constraints", [])),
        "DECISIONS (the why — do not re-decide these):\n"
        + "\n".join(f"- Q: {d['q']}\n  A: {d['a']}" for d in plan.get("decisions", [])),
        "You are on the `main` branch of the repository (your cwd). Implement the "
        "spec, run the task's own checks" + checks +
        ", then COMMIT all changes (git add -A && git commit). Work not committed does "
        "not exist. Do not touch paths outside this repository.",
    ])


def git_head(repo):
    out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def ledger_append(ledger, subject, data):
    subprocess.run([sys.executable, LEDGER_CLI, "append", ledger,
                    "--kind", "run", "--subject", subject,
                    "--data", json.dumps(data)], check=True)


def completed_tasks(ledger):
    done = set()
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                data = rec.get("data", {})
                if data.get("session_ran"):
                    done.add(data.get("task_id"))
    return done


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["N", "F"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--bundles", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.yes:
        print("This run SPENDS REAL QUOTA: 11 fresh worker sessions "
              f"({args.model} @ xhigh). Pass --yes to proceed, or --dry-run "
              "to validate wiring for free.", file=sys.stderr)
        return 2

    repo = os.path.abspath(os.path.expanduser(args.repo))
    runs = os.path.join(HERE, "..", "runs", f"arm-{args.arm}")
    ledger = args.ledger or os.path.join(runs, "ledger.jsonl")
    default_bundles = "bundles-dryrun" if args.dry_run else "bundles"
    bundles = args.bundles or os.path.join(runs, default_bundles)
    os.makedirs(bundles, exist_ok=True)

    done = set() if args.dry_run else completed_tasks(ledger)
    for seq, plan_name in enumerate(chain_plans(), 1):
        plan_path = os.path.join(SPECS, plan_name)
        # Admission parity with the gated arm: ratified plans only.
        adm = subprocess.run([sys.executable, PREFLIGHT, "check", plan_path,
                              "--require-ratified"], capture_output=True)
        if adm.returncode != 0:
            print(f"ABORT: preflight refused {plan_name}", file=sys.stderr)
            return 2
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        task = plan["tasks"][0]
        if task["id"] in done:
            print(f"=== skip (session already ran): {task['id']}")
            continue

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        bundle = os.path.join(bundles, f"{ts}-{seq:03d}-{task['id']}-arm{args.arm}")
        os.makedirs(bundle)
        with open(os.path.join(bundle, "instructions.md"), "w", encoding="utf-8") as fh:
            fh.write(instructions(plan, task))
        with open(os.path.join(bundle, "params.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "contract": 1,
                "role": "implementer",
                "attempt": 1,
                "worker": {"tool": "claude", "model": args.model, "effort": "xhigh"},
                "isolation": {"deny_read": [], "sandbox": True, "network": True},
                "cwd": repo,
                "timeout_s": TIMEOUT_S,
            }, fh, indent=2)

        head_before = git_head(repo)
        print(f"=== arm {args.arm}: {task['id']} ({plan_name}) @ {head_before[:9]}")
        launch_argv = [sys.executable, LAUNCHER] + (["--dry-run"] if args.dry_run else []) + [bundle]
        launch = subprocess.run(launch_argv)
        if args.dry_run:
            continue

        result = {}
        result_path = os.path.join(bundle, "result.json")
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as fh:
                result = json.load(fh)
        refused = result.get("refused_reason")
        session_ran = bool(result.get("ok")) or (
            launch.returncode == 0 and not refused)
        timed_out = (not result.get("ok", False)) and not refused and launch.returncode != 0

        head_after = git_head(repo)
        record = {
            "arm": args.arm, "task_id": task["id"], "plan": plan_name,
            "model": args.model, "bundle": os.path.abspath(bundle),
            "launcher_exit": launch.returncode,
            "session_ran": session_ran or timed_out,
            "refused_reason": refused,
            "head_before": head_before, "head_after": head_after,
            "committed": head_before != head_after,
            "usage": result.get("usage"),
        }
        ledger_append(ledger, f"longhorizon/arm-{args.arm}/{task['id']}/implementer", record)

        if refused or (launch.returncode != 0 and not record["session_ran"]):
            print(f"ABORT: launcher failure on {task['id']} "
                  f"(refused: {refused}) — infrastructure, not an arm outcome. "
                  "Fix and re-run; ran sessions are skipped.", file=sys.stderr)
            return 1
        status = "committed" if record["committed"] else "NO COMMIT (recorded; chain continues)"
        print(f"    session done -> {status}")

    if args.dry_run:
        print(f"ARM {args.arm} DRY-RUN COMPLETE — nothing spawned, no quota spent. "
              f"Bundles under {bundles}")
    else:
        print(f"ARM {args.arm} COMPLETE (all sessions ran). Ledger: {ledger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
