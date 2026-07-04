#!/usr/bin/env python3
"""Calibration gate for duration_predictor.py (design doc SS5.3 / SS12 open question #4).

The design doc is explicit that the duration-bucket predictor "stay[s] behind a flag until ...
the predictor's features are validated against measured burn" -- because published research
(docs/research/token-economics-and-scheduling.md SS3) shows human-legible difficulty features
only weakly track actual token cost. This script is that gate: it never flips the flag itself,
it only reports whether the evidence supports flipping it, matching design SS8's discipline
("every downgrade needs a fresh calibration PASS", "minimum-sample floors respected").

Input: a JSONL run-log where each line is one completed task:
    {"task_id": "...", "profile": "routine|elevated|high|critical",
     "predicted_bucket": "XS|S|M|L|XL", "actual_total_tokens": 123456,
     "escaped": false}
(`escaped` = whether a validation escape was later found for this task; optional, default
false. Extra fields are ignored, so this can be fed straight from the harness's run-log.)

Output: a verdict object with per-bucket stats, a monotonicity check, a rank-correlation
check, an escape-rate check, minimum-sample-floor enforcement, and a single `flag_ready`
boolean that is true only if every gate passes.
"""

import argparse
import json
import statistics
import sys

BUCKET_ORDER = ["XS", "S", "M", "L", "XL"]

MIN_SAMPLES_PER_BUCKET = 8  # sample floor (design SS8: "minimum-sample floors respected")
MIN_RANK_CORRELATION = 0.5  # bucket ordinal vs actual tokens must track at least this well
ESCAPE_RATE_REDLINE = 0.0   # design SS0/O0: escapes must stay ~0; any is a red flag here


def _spearman(xs, ys):
    """Dependency-free Spearman rank correlation (no numpy/scipy in the harness's toolchain)."""
    n = len(xs)
    if n < 2:
        return None

    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        r = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg_rank
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mean_rx, mean_ry = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    denom = (var_x * var_y) ** 0.5
    return cov / denom if denom else None


def _quantiles(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return {"p50": None, "p90": None, "p95": None}

    def q(p):
        idx = min(n - 1, max(0, round(p * (n - 1))))
        return values[idx]

    return {"p50": q(0.50), "p90": q(0.90), "p95": q(0.95)}


def validate(records):
    by_bucket = {b: [] for b in BUCKET_ORDER}
    escapes_by_bucket = {b: 0 for b in BUCKET_ORDER}
    unknown_buckets = set()

    for rec in records:
        bucket = rec.get("predicted_bucket")
        tokens = rec.get("actual_total_tokens")
        if bucket not in by_bucket:
            unknown_buckets.add(bucket)
            continue
        if tokens is None:
            continue
        by_bucket[bucket].append(tokens)
        if rec.get("escaped"):
            escapes_by_bucket[bucket] += 1

    sample_sizes = {b: len(v) for b, v in by_bucket.items()}
    present_buckets = [b for b in BUCKET_ORDER if sample_sizes[b] > 0]

    under_floor = {b: n for b, n in sample_sizes.items() if b in present_buckets and n < MIN_SAMPLES_PER_BUCKET}
    sample_floor_ok = len(under_floor) == 0 and len(present_buckets) == len(BUCKET_ORDER)

    means = {b: (statistics.mean(v) if v else None) for b, v in by_bucket.items()}
    ordered_means = [means[b] for b in present_buckets]
    monotonic = all(a <= b for a, b in zip(ordered_means, ordered_means[1:])) if len(ordered_means) >= 2 else False

    bucket_ordinals, tokens_flat = [], []
    for i, b in enumerate(BUCKET_ORDER):
        for t in by_bucket[b]:
            bucket_ordinals.append(i)
            tokens_flat.append(t)
    correlation = _spearman(bucket_ordinals, tokens_flat)
    correlation_ok = correlation is not None and correlation >= MIN_RANK_CORRELATION

    total_escapes = sum(escapes_by_bucket.values())
    escape_rate_ok = total_escapes <= ESCAPE_RATE_REDLINE * sum(sample_sizes.values()) if sample_sizes else False
    # With ESCAPE_RATE_REDLINE = 0.0 this literally means "zero escapes among validated tasks" --
    # deliberately strict, matching design O0 ("validation escapes ~= 0, never traded").

    flag_ready = bool(sample_floor_ok and monotonic and correlation_ok and total_escapes == 0)

    return {
        "flag_ready": flag_ready,
        "gates": {
            "sample_floor_ok": sample_floor_ok,
            "monotonic": monotonic,
            "correlation_ok": correlation_ok,
            "escape_rate_ok": total_escapes == 0,
        },
        "sample_sizes": sample_sizes,
        "under_sample_floor": under_floor,
        "unknown_buckets_seen": sorted(unknown_buckets),
        "actual_tokens_by_bucket": {b: _quantiles(v) for b, v in by_bucket.items()},
        "mean_tokens_by_bucket": means,
        "escapes_by_bucket": escapes_by_bucket,
        "rank_correlation": correlation,
        "min_samples_per_bucket_required": MIN_SAMPLES_PER_BUCKET,
        "min_rank_correlation_required": MIN_RANK_CORRELATION,
    }


def _cli():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("run_log", nargs="?", default=None,
                    help="Path to a JSONL run-log file, or '-' for stdin. Not needed with "
                    "--selftest.")
    p.add_argument("--selftest", action="store_true",
                   help="Validate a small synthetic run-log (four illustrative cases) and "
                   "exit, ignoring run_log. No filesystem writes.")
    args = p.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.run_log:
        p.error("run_log is required unless --selftest is given")

    fh = sys.stdin if args.run_log == "-" else open(args.run_log)
    records = [json.loads(line) for line in fh if line.strip()]
    print(json.dumps(validate(records), indent=2))


def _selftest():
    def make(bucket, base_tokens, n, escapes=0):
        out = []
        for i in range(n):
            out.append({
                "task_id": f"{bucket}-{i}",
                "predicted_bucket": bucket,
                "actual_total_tokens": base_tokens + (i * 137) % (base_tokens // 3 + 1),
                "escaped": i < escapes,
            })
        return out

    print("=== case 1: well-calibrated, enough samples, no escapes -> should be flag_ready=true ===")
    good = (make("XS", 40_000, 10) + make("S", 90_000, 10) +
            make("M", 180_000, 10) + make("L", 340_000, 10) + make("XL", 700_000, 10))
    print(json.dumps(validate(good), indent=2))

    print("\n=== case 2: too few samples in one bucket -> should be flag_ready=false ===")
    thin = (make("XS", 40_000, 10) + make("S", 90_000, 3) +
            make("M", 180_000, 10) + make("L", 340_000, 10) + make("XL", 700_000, 10))
    print(json.dumps(validate(thin), indent=2))

    print("\n=== case 3: buckets don't separate real cost (non-monotonic) -> should be flag_ready=false ===")
    flat = (make("XS", 200_000, 10) + make("S", 190_000, 10) +
            make("M", 210_000, 10) + make("L", 195_000, 10) + make("XL", 205_000, 10))
    print(json.dumps(validate(flat), indent=2))

    print("\n=== case 4: one escape present -> should be flag_ready=false regardless of calibration ===")
    escaped = (make("XS", 40_000, 10) + make("S", 90_000, 10, escapes=1) +
               make("M", 180_000, 10) + make("L", 340_000, 10) + make("XL", 700_000, 10))
    print(json.dumps(validate(escaped), indent=2))


if __name__ == "__main__":
    _cli()
