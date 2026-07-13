#!/usr/bin/env python3
"""plan-preflight — sound structural validation of a plan.json file.

One thing well: given a plan file (contract v1), prove the things a machine
CAN prove — schema validity, unique ids, resolvable dependencies, and an
acyclic task graph (the mathematical precondition for any sound structural
check to exist at all) — and *surface* the things only a human ratifier can
judge (empty acceptance checks, open questions, unmatched requires) as
warnings, never verdicts.

Hard failures are only the sound ones. Warnings never fail the check unless
--strict is passed — that flag exists as the experiment knob for measuring
whether a machine determinacy bar beats human eyeballing (design T3); it is
not the default and nothing in this tool pads a plan to appease it.

Pure stdlib. Contract: README.md next to this file.
Exit codes: 0 ok · 1 plan invalid (or warnings under --strict) · 2 usage/IO error.
"""

import argparse
import datetime
import json
import re
import sys

CONTRACT = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Risk tiers (added 2026-07-12, additive-optional within contract 1): the
# operator's declared blast-radius/budget context, set in the interview.
# Consumers compose machinery per tier; absence means "full" — lowering the
# guard is always an explicit, recorded choice, never a default.
TIERS = ("full", "gate-only", "bare")

TOP_KEYS = {
    "contract",
    "goal",
    "non_goals",
    "constraints",
    "decisions",
    "open_questions",
    "tasks",
    "external",
    "ratified",
    "risk_tier",
}
TASK_KEYS = {"id", "title", "spec", "depends_on", "checks", "provides", "requires", "tier"}
TASK_REQUIRED = ("id", "title", "spec")


def is_str_list(value):
    return isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def parse_ts(value):
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate(plan):
    """Return (errors, warnings, tasks_by_id). Sound checks -> errors; judgment
    signals -> warnings."""
    errors, warnings = [], []

    if not isinstance(plan, dict):
        return ["plan is not a JSON object"], [], {}

    unknown = sorted(set(plan) - TOP_KEYS)
    if unknown:
        errors.append(f"unknown top-level key(s): {', '.join(unknown)}")

    if plan.get("contract") != CONTRACT:
        errors.append(
            f"contract must be {CONTRACT} (found {plan.get('contract')!r})"
        )

    goal = plan.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("goal must be a non-empty string")

    for key in ("non_goals", "constraints", "open_questions", "external"):
        if key in plan and not is_str_list(plan[key]):
            errors.append(f"{key} must be a list of non-empty strings")

    if "risk_tier" in plan and plan["risk_tier"] not in TIERS:
        errors.append(
            f"risk_tier must be one of {'/'.join(TIERS)} (found {plan['risk_tier']!r})"
        )

    if "decisions" in plan:
        if not isinstance(plan["decisions"], list):
            errors.append("decisions must be a list")
        else:
            for idx, dec in enumerate(plan["decisions"]):
                if (
                    not isinstance(dec, dict)
                    or set(dec) != {"q", "a"}
                    or not all(isinstance(dec[k], str) and dec[k].strip() for k in ("q", "a"))
                ):
                    errors.append(
                        f"decisions[{idx}] must be an object with exactly "
                        'non-empty string keys "q" and "a"'
                    )

    if "ratified" in plan:
        rat = plan["ratified"]
        if (
            not isinstance(rat, dict)
            or set(rat) != {"by", "ts"}
            or not all(isinstance(rat[k], str) and rat[k].strip() for k in ("by", "ts"))
        ):
            errors.append('ratified must be an object with exactly keys "by" and "ts"')
        else:
            try:
                parse_ts(rat["ts"])
            except (ValueError, TypeError):
                errors.append(f"ratified.ts is not RFC3339/ISO-8601: {rat['ts']!r}")

    tasks = plan.get("tasks")
    tasks_by_id = {}
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty list")
        return errors, warnings, tasks_by_id

    for idx, task in enumerate(tasks):
        where = f"tasks[{idx}]"
        if not isinstance(task, dict):
            errors.append(f"{where} is not a JSON object")
            continue
        unknown = sorted(set(task) - TASK_KEYS)
        if unknown:
            errors.append(f"{where}: unknown key(s): {', '.join(unknown)}")
        missing = [k for k in TASK_REQUIRED if k not in task]
        if missing:
            errors.append(f"{where}: missing required key(s): {', '.join(missing)}")
            continue
        tid = task["id"]
        if not isinstance(tid, str) or not ID_RE.match(tid):
            errors.append(f"{where}: id must match [a-z0-9][a-z0-9-]* (found {tid!r})")
            continue
        if tid in tasks_by_id:
            errors.append(f"duplicate task id: {tid}")
            continue
        for key in ("title", "spec"):
            if not isinstance(task[key], str) or not task[key].strip():
                errors.append(f"task {tid}: {key} must be a non-empty string")
        for key in ("depends_on", "checks", "provides", "requires"):
            if key in task and not is_str_list(task[key]):
                errors.append(f"task {tid}: {key} must be a list of non-empty strings")
        if "tier" in task and task["tier"] not in TIERS:
            errors.append(
                f"task {tid}: tier must be one of {'/'.join(TIERS)} (found {task['tier']!r})"
            )
        tasks_by_id[tid] = task

    # Dependency integrity (sound).
    for tid, task in tasks_by_id.items():
        for dep in task.get("depends_on", []):
            if dep == tid:
                errors.append(f"task {tid} depends on itself")
            elif dep not in tasks_by_id:
                errors.append(f"task {tid} depends on unknown task {dep!r}")

    # Acyclicity (sound — M7: only an acyclic graph admits a sound preflight).
    if not errors:
        cycle = find_cycle(tasks_by_id)
        if cycle:
            errors.append("dependency cycle: " + " -> ".join(cycle))

    # Judgment signals (warnings — ratification input, never verdicts).
    provided = set(plan.get("external", []))
    for task in tasks_by_id.values():
        provided.update(task.get("provides", []))
    plan_tier = plan.get("risk_tier", "full")
    for tid, task in sorted(tasks_by_id.items()):
        effective_tier = task.get("tier", plan_tier) if plan_tier in TIERS else task.get("tier", "full")
        if not task.get("checks"):
            warnings.append(
                f"task {tid} has no acceptance checks — completion will rest on judgment, not execution"
            )
            if effective_tier == "gate-only":
                warnings.append(
                    f"task {tid} is gate-only with no checks — a gate with nothing to run is a rubber stamp; the loop will refuse it"
                )
        for req in task.get("requires", []):
            if req not in provided:
                warnings.append(
                    f"task {tid} requires {req!r}, which no task provides and external does not list"
                )
    if plan.get("open_questions"):
        warnings.append(
            f"{len(plan['open_questions'])} open question(s) remain — the ratifier is accepting them unresolved"
        )

    return errors, warnings, tasks_by_id


def find_cycle(tasks_by_id):
    """DFS cycle detection. Returns the cycle path (ids) or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tasks_by_id}
    parent = {}

    def dfs(node):
        color[node] = GRAY
        for dep in sorted(tasks_by_id[node].get("depends_on", [])):
            if color[dep] == GRAY:
                path = [dep, node]
                cursor = node
                while parent.get(cursor) is not None and cursor != dep:
                    cursor = parent[cursor]
                    path.append(cursor)
                return list(reversed(path))
            if color[dep] == WHITE:
                parent[dep] = node
                found = dfs(dep)
                if found:
                    return found
        color[node] = BLACK
        return None

    for tid in sorted(tasks_by_id):
        if color[tid] == WHITE:
            found = dfs(tid)
            if found:
                return found
    return None


def topo_order(tasks_by_id):
    """Deterministic Kahn topological order: among all currently-ready tasks,
    always emit the lexicographically smallest id next."""
    remaining = {
        tid: set(task.get("depends_on", [])) for tid, task in tasks_by_id.items()
    }
    order = []
    while remaining:
        ready = sorted(tid for tid, deps in remaining.items() if not deps)
        if not ready:  # unreachable once validate() proved acyclicity; defensive
            break
        node = ready[0]
        order.append(node)
        del remaining[node]
        for deps in remaining.values():
            deps.discard(node)
    return order


def load_plan(path):
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        print(f"error: cannot read plan: {exc}", file=sys.stderr)
        return None, 2
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [f"plan is not valid JSON: {exc.msg} (line {exc.lineno})"],
                    "warnings": [],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return None, 1


def cmd_check(args):
    plan, early_exit = load_plan(args.plan)
    if plan is None:
        return early_exit

    errors, warnings, tasks_by_id = validate(plan)
    if args.require_ratified and "ratified" not in plan:
        errors.append("plan is not ratified (required by --require-ratified)")

    ok = not errors and not (args.strict and warnings)
    edges = sum(len(t.get("depends_on", [])) for t in tasks_by_id.values())
    report = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "strict": bool(args.strict),
        "ratified": "ratified" in plan if isinstance(plan, dict) else False,
        "stats": {
            "tasks": len(tasks_by_id),
            "edges": edges,
            "roots": sorted(
                tid for tid, t in tasks_by_id.items() if not t.get("depends_on")
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 1


def cmd_order(args):
    plan, early_exit = load_plan(args.plan)
    if plan is None:
        return early_exit
    errors, _, tasks_by_id = validate(plan)
    if errors:
        print(
            json.dumps({"ok": False, "errors": errors}, indent=2, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    for tid in topo_order(tasks_by_id):
        print(tid)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="preflight.py", description="sound structural validation of plan.json (contract v1)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="validate; errors are sound, warnings are for the ratifier")
    p_check.add_argument("plan", help="plan.json path")
    p_check.add_argument(
        "--strict",
        action="store_true",
        help="promote warnings to failures (the T3 experiment knob; not the default)",
    )
    p_check.add_argument(
        "--require-ratified",
        action="store_true",
        help="fail unless the plan carries a ratified{by,ts} stamp",
    )
    p_check.set_defaults(fn=cmd_check)

    p_order = sub.add_parser("order", help="print a deterministic topological task order")
    p_order.add_argument("plan", help="plan.json path")
    p_order.set_defaults(fn=cmd_order)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
