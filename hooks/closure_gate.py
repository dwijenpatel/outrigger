#!/usr/bin/env python3
"""E5 — Stop-hook gate: block "done" while the closure gate says otherwise.

    python3 hooks/closure_gate.py --snapshot state/plan-snapshot.json \
        --ledger plan/tasks.json --events state/events.jsonl [--rounds N] ...

Exit 0 = closure holds (stopping is fine). Exit 2 = block (with the reason on
stderr). Enforcement gate: fails closed — an unreadable snapshot/ledger blocks.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import closure, ledger as ledger_mod  # noqa: E402


def main(argv=None) -> int:
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
        print(json.dumps(result, indent=2))
        if result["complete"] or result["status"] == "escalate":
            # escalate also releases the Stop: the loop must hand the operator
            # the decision instead of spinning further rounds
            return 0
        print(f"closure gate: {result['why']}", file=sys.stderr)
        return 2
    except Exception as exc:  # gate: fail closed
        print(f"closure gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
