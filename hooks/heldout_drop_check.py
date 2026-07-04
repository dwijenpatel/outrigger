#!/usr/bin/env python3
"""C4 — merge-point gate: held-out-test-drop check.

Compares the vault's recorded manifest against its current contents; a merge
that dropped or mutated held-out tests is blocked. Enforcement gate: fails
closed (missing/corrupt manifest, missing vault, internal error all exit 2).

    python3 hooks/heldout_drop_check.py --vault .vault
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import vault  # noqa: E402


def main(argv=None) -> int:
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--vault", required=True)
        args = p.parse_args(argv)
        recorded = vault.load_manifest(args.vault)
        current = vault.build_manifest(args.vault)
        result = vault.check_heldout_drop(recorded, current)
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            print(f"held-out-drop gate: {result['why']} "
                  f"(dropped={result['dropped']}, mutated={result['mutated']})",
                  file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # gate: fail closed
        print(f"held-out-drop gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
