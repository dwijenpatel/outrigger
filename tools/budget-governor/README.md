# Budget governor tools

Working artifacts resolving three of the design doc's
([../../docs/attic/token-time-optimized-harness.md](../../docs/attic/token-time-optimized-harness.md))
§12 open questions: per-agent effort/model spawn portability (#3), window-occupancy
forecasting (#4), and the cache-read quota-weight experiment protocol (#2). This is the first
real implementation code in the repo — everything else so far is docs.

## What's here

| File | Resolves | What it does |
|---|---|---|
| [probe-spawn-portability.js](probe-spawn-portability.js) + [probe-spawn-portability-2026-07-04.md](probe-spawn-portability-2026-07-04.md) | Open Q#3 | A `Workflow` script that live-probes whether the current Claude Code build honors per-agent `effort`/`model` overrides, and whether it rejects invalid ones. Re-run on any new build/environment — portability, not a one-time fact, was the open question. |
| [duration_predictor.py](duration_predictor.py) | Open Q#4 (design §5.3) | A deterministic, non-LLM scorer: task features (spec size, file count, subsystem breadth, novelty) → a duration bucket (XS–XL). **Behind a flag** until `validate_predictor.py` says it's calibrated. |
| [validate_predictor.py](validate_predictor.py) | Open Q#4 (design §5.3/§12/§8) | The calibration gate. Reads a run-log of `{predicted_bucket, actual_total_tokens, escaped}` records and reports whether the predictor's buckets actually track measured cost — sample floors, monotonicity, rank correlation, and a zero-escape gate, matching design §8's "one lever at a time, minimum-sample floors, every downgrade needs a fresh calibration PASS" discipline. |
| [profile-tier-estimates.json](profile-tier-estimates.json) + [populate_estimates.py](populate_estimates.py) | Open Q#4 (design §5.1 admission forecast) | The Stage-0/1 lever: static P95 estimates per **risk profile** (not yet per duration bucket), used by the admission rule before the predictor is trusted. Starts genuinely empty (no fabricated numbers) and self-populates from a real run-log. |
| [cache-read-quota-weight-experiment.md](cache-read-quota-weight-experiment.md) + [run_cache_weight_experiment.sh](run_cache_weight_experiment.sh) | Open Q#2 | The controlled-experiment protocol (with the math for turning a measured delta into an implied cache-read weight) and its runner for settling whether cache reads count against subscription limits at a discount or near-full weight. The `gen-filler`/`summarize` subcommands are free and tested; `dry-run`/`arm-a`/`arm-b` call `claude -p` and **spend real Max-plan quota — deliberately not yet executed**; run them only when you decide to. |

## How the pieces fit into the design (§5.1 / §5.3)

Two related but distinct forecasts, both fed by the same underlying signal:

1. **§5.1 admission forecast** — "does this candidate task fit in the remaining window?" Today:
   look up the task's risk profile in `profile-tier-estimates.json`'s `cost_estimate_by_profile`
   (a P95 token figure). Once `duration_predictor.py` is validated, its bucket's *measured*
   quantile (from the same run-log, sliced by bucket instead of by profile) can replace or refine
   the profile-level estimate — same admission rule, sharper input.
2. **§5.3 tier-routing matrix** — "which starting tier should this task use?" Stage 0/1 uses a
   single starting tier per profile (already in `risk_profiles` below). Stage 3's full
   bucket×profile matrix needs `duration_predictor.py`'s bucket assignment **and**
   `validate_predictor.py`'s sign-off before it drives any real routing decision.

Both consumers are deliberately **out of scope here** — this directory ships the predictor, the
gate, and the estimate table; the admission rule and tier router that *read* them are harness
code that doesn't exist yet.

## Day-one bootstrap loop

```
task runs  →  append {profile, total_tokens} to a run-log
                          │
                          ├─→ populate_estimates.py --write   (Stage-0/1 estimates sharpen)
                          │
task also scored by  →  duration_predictor.py  →  predicted_bucket
                          │                              │
                          └─→ append {predicted_bucket, actual_total_tokens, escaped}
                                        to a second run-log
                                        │
                                        └─→ validate_predictor.py  →  flag_ready: true/false
```

Nothing here auto-flips a flag. Both scripts only *report*; a human (or the §8 controller, once
it exists) reads the verdict and decides, per design §8's "never auto-applied" rule.

## Try it now (no real telemetry needed)

```bash
python3 duration_predictor.py --selftest        # six illustrative example tasks
python3 validate_predictor.py --selftest        # four calibration scenarios (pass/3 fail modes)
python3 populate_estimates.py --selftest        # quantile computation on synthetic data
```

All three are pure stdlib Python 3, no dependencies, no network, no writes unless you pass
`--write` (and even then only to the file you name with `--estimates-file`).
