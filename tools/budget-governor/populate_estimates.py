#!/usr/bin/env python3
"""Populate profile-tier-estimates.json's cost_estimate_by_profile block from a real run-log.

Read-modify-write, and deliberately narrow: this script only ever touches
`cost_estimate_by_profile`. It never invents a number where none exists, and it never
touches `risk_profiles` or `overshoot_variance_by_tier_effort` (those are hand-edited policy,
not derived stats). See profile-tier-estimates.json's `_meta.bootstrap_procedure`.

Input: a JSONL run-log where each line is one completed task:
    {"profile": "routine|elevated|high|critical", "total_tokens": 123456}
Extra fields are ignored, so this can be fed straight from the harness's run-log.
"""

import argparse
import json
import sys

PROFILES = ["routine", "elevated", "high", "critical"]


def _quantiles(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return {"p50": None, "p90": None, "p95": None, "sample_size": 0}

    def q(p):
        idx = min(n - 1, max(0, round(p * (n - 1))))
        return values[idx]

    return {"p50": q(0.50), "p90": q(0.90), "p95": q(0.95), "sample_size": n}


def compute(records):
    by_profile = {p: [] for p in PROFILES}
    unknown = set()
    for rec in records:
        profile = rec.get("profile")
        tokens = rec.get("total_tokens")
        if profile not in by_profile:
            unknown.add(profile)
            continue
        if tokens is not None:
            by_profile[profile].append(tokens)
    return {p: _quantiles(v) for p, v in by_profile.items()}, unknown


def _cli():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("run_log", nargs="?", default=None, help="JSONL run-log, or '-' for stdin")
    p.add_argument("--estimates-file", default=None,
                    help="Path to profile-tier-estimates.json (default: alongside this script)")
    p.add_argument("--write", action="store_true",
                    help="Write the recomputed cost_estimate_by_profile block back into the "
                    "estimates file. Without this flag, only prints what WOULD be written "
                    "(dry run -- the default, on purpose).")
    p.add_argument("--selftest", action="store_true",
                    help="Compute quantiles from a small synthetic run-log and print them. "
                    "No filesystem writes, ignores run_log/--write.")
    args = p.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.run_log:
        p.error("run_log is required unless --selftest is given")

    fh = sys.stdin if args.run_log == "-" else open(args.run_log)
    records = [json.loads(line) for line in fh if line.strip()]
    estimates, unknown = compute(records)

    if unknown:
        print(f"warning: ignored {len(unknown)} record(s) with unrecognized profile name(s): "
              f"{sorted(unknown)}", file=sys.stderr)

    print(json.dumps(estimates, indent=2))

    if not args.write:
        print("\n(dry run -- pass --write to update the estimates file)", file=sys.stderr)
        return

    estimates_path = args.estimates_file or (
        __file__.rsplit("/", 1)[0] + "/profile-tier-estimates.json"
    )
    with open(estimates_path) as f:
        doc = json.load(f)
    doc["cost_estimate_by_profile"] = estimates
    with open(estimates_path, "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print(f"wrote cost_estimate_by_profile to {estimates_path}", file=sys.stderr)


def _selftest():
    synthetic = (
        [{"profile": "routine", "total_tokens": 40000 + i * 500} for i in range(10)] +
        [{"profile": "elevated", "total_tokens": 95000 + i * 800} for i in range(10)] +
        [{"profile": "high", "total_tokens": 3} for i in range(0)]  # deliberately zero-sample
    )
    estimates, unknown = compute(synthetic)
    print(json.dumps(estimates, indent=2))
    assert estimates["routine"]["sample_size"] == 10
    assert estimates["high"]["sample_size"] == 0
    assert estimates["high"]["p50"] is None
    print("selftest OK: populated profiles show real quantiles; unsampled profiles stay null, "
          "never fabricated.", file=sys.stderr)


if __name__ == "__main__":
    _cli()
