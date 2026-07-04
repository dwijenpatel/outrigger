#!/usr/bin/env python3
"""E5/H1 — Stop-hook gate: block "done" while the closure gate says otherwise.

Two modes:

**Hook mode (no CLI args)** — the registered Stop hook (H1). Reads the hook
stdin JSON, resolves the project dir (CLAUDE_PROJECT_DIR > hook ``cwd`` >
cwd), and:

- no **live** run marker (``state/run.marker``) → exit 0. The gate guards
  firings, not operator sessions — inert outside a firing.
- live marker → closure inputs come from ``state/closure-hook.json`` (written
  by ``loop.closure_hook_config`` at firing start). Unreadable config, bad
  snapshot, anything undecidable → exit 2 (fail closed).

**CLI mode** (explicit args, unchanged):

    python3 hooks/closure_gate.py --snapshot state/plan-snapshot.json \
        --ledger plan/tasks.json --events state/events.jsonl [--rounds N] ...

Exit 0 = closure holds (stopping is fine) or the gate is inert. Exit 2 =
block (with the reason on stderr). Enforcement gate: fails closed.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import closure, ledger as ledger_mod, loop as loop_mod  # noqa: E402


def _decide(result: dict) -> int:
    print(json.dumps(result, indent=2))
    if result["complete"] or result["status"] == "escalate":
        # escalate also releases the Stop: the loop must hand the operator
        # the decision instead of spinning further rounds
        return 0
    print(f"closure gate: {result['why']}", file=sys.stderr)
    return 2


def hook_main(stdin_text: str) -> int:
    try:
        try:
            doc = json.loads(stdin_text) if stdin_text.strip() else {}
        except json.JSONDecodeError:
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        project = (os.environ.get("CLAUDE_PROJECT_DIR")
                   or doc.get("cwd") or os.getcwd())
        marker = loop_mod.run_marker_live(
            os.path.join(project, "state", "run.marker"))
        if marker is None:
            return 0  # no live firing — inert
        cfg = closure.load_hook_config(
            os.path.join(project, "state", "closure-hook.json"), project)
        snap = closure.load_snapshot(cfg["snapshot"])
        ldg = ledger_mod.Ledger.load(cfg["ledger"])
        log = ledger_mod.EventLog(cfg["events"])
        result = closure.closure_check(
            snap, ldg, log,
            evidence_ts=cfg.get("evidence_ts"),
            last_remediation_ts=cfg.get("last_remediation_ts"),
            remediation_rounds=cfg.get("rounds", 0),
            max_rounds=cfg.get("max_rounds", 3),
            ratified_descopes=cfg.get("descoped", []))
        return _decide(result)
    except Exception as exc:  # gate: fail closed during a live firing
        print(f"closure gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return hook_main(sys.stdin.read())
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--snapshot", required=True)
        p.add_argument("--ledger", required=True)
        p.add_argument("--events", required=True)
        p.add_argument("--evidence-ts")
        p.add_argument("--last-remediation-ts")
        p.add_argument("--rounds", type=int, default=0)
        p.add_argument("--max-rounds", type=int, default=3)
        p.add_argument("--descoped", nargs="*", default=[])
        args = p.parse_args(argv)

        snap = closure.load_snapshot(args.snapshot)
        ldg = ledger_mod.Ledger.load(args.ledger)
        log = ledger_mod.EventLog(args.events)
        result = closure.closure_check(
            snap, ldg, log,
            evidence_ts=args.evidence_ts,
            last_remediation_ts=args.last_remediation_ts,
            remediation_rounds=args.rounds, max_rounds=args.max_rounds,
            ratified_descopes=args.descoped)
        return _decide(result)
    except Exception as exc:  # gate: fail closed
        print(f"closure gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
