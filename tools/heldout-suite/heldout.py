#!/usr/bin/env python3
"""heldout-suite — the held-out test suite lifecycle: materialize, validate, seal, verify.

One thing well: manage the GRADED tests' lifecycle so that the agent writing the
code never writes, sees, or reaches the tests that judge it (design D2/D11).
This tool prepares an authoring workspace OUTSIDE the target repo, checks an
authored suite has teeth against the pre-change code (fails-on-base), and locks
it with a spec-hash-bound manifest plus a deny-fragment for the implementer's
spawner. It never launches any agent — who authors is composition (ROLE.md is
the authoring contract).

Pure stdlib. Contract: README.md next to this file. Built from the ratified
plans/heldout-suite.plan.json.

Exit codes: 0 ok · 1 refusal or policy failure · 2 usage or input error.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

PLAN_CONTRACT = 1


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail(code, message):
    print(f"error: {message}", file=sys.stderr)
    return code


def git(repo, *args):
    """Run git in repo; returns (rc, stdout). Never raises on git failure."""
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def repo_toplevel(repo):
    rc, out, _ = git(repo, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if rc == 0 else None


def resolve_commit(repo, ref):
    rc, out, _ = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return out if rc == 0 else None


def path_inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


AUTHORING_MD = """\
# Authoring workspace — held-out suite for task `{task_id}`

You are the TEST-AUTHOR for exactly one task. Full role instructions:
`ROLE.md` in the heldout-suite artifact directory of the orchestrating repo
(tools/heldout-suite/ROLE.md). The short version:

- **Your inputs are `task.json` (in this directory) and the base checkout of
  the target repository — nothing else.** task.json holds the task's spec and
  the plan-level goal/non-goals/constraints/decisions (the why). There is no
  implementation yet; you write tests from the SPEC.
- **Write stdlib-unittest tests as `test_*.py` files into `../suite/`.**
- Your suite will be judged by `heldout.py validate` against a clean checkout
  of base commit `{base_sha}`: the runner must complete, and **at least one
  test must fail on base** (a suite that fully passes before the change proves
  nothing). Base-passing regression guards are allowed and welcome.
- You may run `validate` yourself, iteratively. You never run `seal`.
- You never assert your suite is good — validate and the seal decide.
"""


def cmd_materialize(args):
    top = repo_toplevel(args.repo)
    if top is None:
        return fail(2, f"not a git repository: {args.repo}")

    out_real = os.path.realpath(args.out)
    if path_inside(out_real, top):
        return fail(
            1,
            f"--out resolves inside the target repo ({out_real}) — held-out suites "
            "never live in the judged tree; choose a location outside it",
        )

    base_sha = resolve_commit(args.repo, args.base)
    if base_sha is None:
        return fail(2, f"cannot resolve base ref {args.base!r} in {args.repo}")

    try:
        with open(args.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
    except OSError as exc:
        return fail(2, f"cannot read plan: {exc}")
    except json.JSONDecodeError as exc:
        return fail(2, f"plan is not valid JSON: {exc.msg}")

    if not isinstance(plan, dict) or plan.get("contract") != PLAN_CONTRACT:
        return fail(2, f"plan contract must be {PLAN_CONTRACT}")
    tasks = {
        t.get("id"): t
        for t in plan.get("tasks", [])
        if isinstance(t, dict) and isinstance(t.get("id"), str)
    }
    if args.task not in tasks:
        return fail(2, f"task {args.task!r} not found in plan (has: {', '.join(sorted(tasks))})")

    workspace = os.path.join(out_real, args.task)
    if os.path.exists(workspace):
        return fail(
            1,
            f"workspace already exists: {workspace} — re-materialization of a sealed "
            "workspace is the retire flow in seal, never an overwrite",
        )

    # The interview-scoped inputs (plan decisions[4]): this task's full entry
    # plus the plan-level preamble. Never other tasks' specs.
    task_inputs = {
        "task": tasks[args.task],
        "goal": plan.get("goal", ""),
        "non_goals": plan.get("non_goals", []),
        "constraints": plan.get("constraints", []),
        "decisions": plan.get("decisions", []),
        "base": {"ref": args.base, "sha": base_sha},
        "plan_contract": PLAN_CONTRACT,
    }

    authoring = os.path.join(workspace, "authoring")
    suite = os.path.join(workspace, "suite")
    os.makedirs(authoring)
    os.makedirs(suite)
    write_json(os.path.join(authoring, "task.json"), task_inputs)
    with open(os.path.join(authoring, "AUTHORING.md"), "w", encoding="utf-8") as fh:
        fh.write(AUTHORING_MD.format(task_id=args.task, base_sha=base_sha))

    print(
        json.dumps(
            {
                "workspace": workspace,
                "task_id": args.task,
                "base": {"ref": args.base, "sha": base_sha},
                "files": ["authoring/task.json", "authoring/AUTHORING.md", "suite/"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="heldout.py", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mat = sub.add_parser(
        "materialize", help="build an authoring workspace outside the repo"
    )
    p_mat.add_argument("--plan", required=True, help="ratified plan.json path")
    p_mat.add_argument("--task", required=True, help="task id within the plan")
    p_mat.add_argument("--repo", required=True, help="target git repository")
    p_mat.add_argument("--base", default="main", help="base ref (default: main)")
    p_mat.add_argument(
        "--out", required=True, help="workspace parent directory — must be OUTSIDE the repo"
    )
    p_mat.set_defaults(fn=cmd_materialize)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
