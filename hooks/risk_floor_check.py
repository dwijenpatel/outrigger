#!/usr/bin/env python3
"""C3 — merge-point gate: risk floor vs the actual diff paths.

Usage (called by the merge gate, D2):

    python3 hooks/risk_floor_check.py --profile routine \
        --floor-config harness/config/risk-floors.json --ref main \
        --repo . path1 path2 ...

The floor config is loaded from the **ratified ref's committed state** — never
the working tree under judgment. Enforcement gate: fails closed (unloadable
config, bad input, or a floor violation all exit 2).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks  # noqa: E402


def main(argv=None) -> int:
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--profile", required=True)
        p.add_argument("--floor-config", required=True,
                       help="repo-relative path to the floor map JSON")
        p.add_argument("--ref", default="main")
        p.add_argument("--repo", default=".")
        p.add_argument("paths", nargs="*")
        args = p.parse_args(argv)

        doc = hooks.load_ratified_config(args.repo, args.floor_config,
                                         ref=args.ref)
        if doc is None:
            print(f"risk-floor gate: cannot load {args.floor_config} from "
                  f"{args.ref} — blocking (fail-closed; config must live on the "
                  f"ratified branch)", file=sys.stderr)
            return 2
        floor_map = hooks.validate_floor_map(doc.get("floors", []))
        result = hooks.check_risk_floor(args.profile, args.paths, floor_map)
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            print(f"risk floor violated: {result['why']}", file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # gate: fail closed
        print(f"risk-floor gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
