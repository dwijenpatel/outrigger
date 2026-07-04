#!/usr/bin/env python3
"""Deterministic duration-bucket predictor (design doc SS5.3 / SS12 open question #4).

NOT an LLM call, by design: research evidence (docs/research/token-economics-and-scheduling.md
SS3) shows frontier models cannot self-predict their own token spend (r <= 0.39, systematically
low) and that the same-task spend they'd be predicting varies up to 30x run to run. A cheap,
transparent, auditable script is the only sound source for this signal.

STATUS: behind a flag. Per the design doc, this predictor's *bucket assignments* must be
validated against measured burn (validate_predictor.py) before any admission or tier-routing
decision is allowed to depend on them. Until validated, use profile-tier-estimates.json's
per-profile P95 estimates instead (the Stage-0/1 lever).

The scoring thresholds below are an initial, clearly-adjustable heuristic -- NOT measured
fact. They exist so the pipeline (predict -> log -> validate -> calibrate) is exercisable from
day one instead of blocked on a chicken-and-egg "no data yet" problem. Adjust them only in
response to validate_predictor.py's calibration output, one change at a time (design SS8
discipline: "one lever at a time").
"""

import argparse
import json
import sys

# --- Adjustable scoring thresholds (see module docstring) ---------------------------------

SPEC_TOKEN_BANDS = [500, 2000, 6000, 15000]  # score 0..4, index = how many bands exceeded
FILE_COUNT_BANDS = [1, 3, 8, 20]
SUBSYSTEM_COUNT_BANDS = [1, 2, 4, 7]
NOVELTY_BANDS = [0, 1, 3]  # len(novelty_flags) compared against these; scored 0/2/3/4 (weighted)
NOVELTY_SCORES = [0, 2, 3, 4]

BUCKET_THRESHOLDS = [
    (2, "XS"),
    (5, "S"),
    (9, "M"),
    (13, "L"),
]
BUCKET_MAX = "XL"


def _band_score(value, bands):
    """How many band ceilings `value` exceeds, capped at len(bands)."""
    score = 0
    for ceiling in bands:
        if value > ceiling:
            score += 1
    return score


def _novelty_score(novelty_flags):
    n = len(novelty_flags)
    score = 0
    for i, ceiling in enumerate(NOVELTY_BANDS):
        if n > ceiling:
            score = NOVELTY_SCORES[i + 1]
    return score


def predict(spec_tokens, file_count, subsystem_count, novelty_flags=None):
    """Score a task's features into a duration bucket.

    Returns a dict: {bucket, raw_score, feature_breakdown, forced_min_tier}.
    `forced_min_tier` is "standard" when novelty_flags is non-empty, per design SS5.3
    guardrail 2 ("nature beats difficulty" -- recency-sensitive tasks route off cheap
    regardless of size), independent of the bucket the size features alone would suggest.
    """
    novelty_flags = novelty_flags or []

    breakdown = {
        "spec_tokens": _band_score(spec_tokens, SPEC_TOKEN_BANDS),
        "file_count": _band_score(file_count, FILE_COUNT_BANDS),
        "subsystem_count": _band_score(subsystem_count, SUBSYSTEM_COUNT_BANDS),
        "novelty": _novelty_score(novelty_flags),
    }
    raw_score = sum(breakdown.values())

    bucket = BUCKET_MAX
    for ceiling, name in BUCKET_THRESHOLDS:
        if raw_score <= ceiling:
            bucket = name
            break

    return {
        "bucket": bucket,
        "raw_score": raw_score,
        "feature_breakdown": breakdown,
        "forced_min_tier": "standard" if novelty_flags else None,
        "inputs": {
            "spec_tokens": spec_tokens,
            "file_count": file_count,
            "subsystem_count": subsystem_count,
            "novelty_flags": novelty_flags,
        },
    }


def _cli():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--spec-tokens", type=int)
    p.add_argument("--file-count", type=int)
    p.add_argument("--subsystem-count", type=int)
    p.add_argument("--novelty-flag", action="append", default=[], dest="novelty_flags",
                    help="Repeatable. E.g. --novelty-flag 'sdk-v3-newer-than-training-cutoff'")
    p.add_argument("--json", metavar="FILE", help="Read a single task's features from a JSON "
                   "file instead of flags: {spec_tokens, file_count, subsystem_count, "
                   "novelty_flags}. Use '-' for stdin.")
    p.add_argument("--selftest", action="store_true",
                    help="Run a small set of illustrative example tasks and print their "
                    "predicted buckets, then exit. No network, no filesystem writes.")
    args = p.parse_args()

    if args.selftest:
        _selftest()
        return

    if args.json:
        raw = sys.stdin.read() if args.json == "-" else open(args.json).read()
        task = json.loads(raw)
        result = predict(
            task["spec_tokens"], task["file_count"], task["subsystem_count"],
            task.get("novelty_flags", []),
        )
    else:
        missing = [n for n in ("spec_tokens", "file_count", "subsystem_count")
                   if getattr(args, n.replace("-", "_")) is None]
        if missing:
            p.error(f"missing required: {', '.join('--' + m.replace('_', '-') for m in missing)}"
                    " (or use --json / --selftest)")
        result = predict(args.spec_tokens, args.file_count, args.subsystem_count,
                          args.novelty_flags)

    print(json.dumps(result, indent=2))


def _selftest():
    examples = [
        ("tiny routine fix", dict(spec_tokens=300, file_count=1, subsystem_count=1)),
        ("small feature, few files", dict(spec_tokens=1800, file_count=3, subsystem_count=1)),
        ("medium cross-cutting change", dict(spec_tokens=5000, file_count=6, subsystem_count=3)),
        ("large multi-subsystem feature", dict(spec_tokens=12000, file_count=15, subsystem_count=5)),
        ("sprawling rewrite", dict(spec_tokens=20000, file_count=30, subsystem_count=9)),
        ("small task, but uses a brand-new API", dict(
            spec_tokens=800, file_count=2, subsystem_count=1,
            novelty_flags=["vendor-sdk-v4-post-training-cutoff"],
        )),
    ]
    print(f"{'label':<38} {'bucket':<4} {'score':<6} forced_min_tier")
    for label, features in examples:
        r = predict(**features)
        print(f"{label:<38} {r['bucket']:<4} {r['raw_score']:<6} {r['forced_min_tier']}")


if __name__ == "__main__":
    _cli()
