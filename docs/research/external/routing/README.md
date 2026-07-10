# Routing — model, effort, and difficulty selection

**Scope.** Which model tier and reasoning effort each task gets, and whether task
difficulty/horizon can be predicted well enough to route on: cascades vs pre-generation
routers, effort dials, duration buckets, regime tags, escalation policy.

**Coverage: ◐ moderate** (2026-07-10). Good literature map; the load-bearing local facts live
in the internal benchmark; no validated horizon-router exists anywhere (absence finding).

## Holdings

- [task-horizon-prediction.md](task-horizon-prediction.md) — METR horizons, decades of
  software effort-estimation evidence (buckets work, points don't), the 2026 difficulty-router
  papers (single-source), and the bucket/asymmetric-loss scheme the harness adopts.

## Related material elsewhere

- [../economics/token-economics-and-scheduling.md](../economics/token-economics-and-scheduling.md)
  §1–2 — cascade/router savings bands and their regime dependence.
- Internal: [../../internal/model-speed-effort-benchmark-2026-07/](../../internal/model-speed-effort-benchmark-2026-07/README.md)
  — regime inversion, effort-down risk, adaptive-thinking supersessions; spawn-portability
  probes (acceptance ≠ application).

## Open questions

- Regime-tag calibration: do planner-assigned `chore|thinking|long_horizon` tags actually
  predict measured burn? (The run-log is the calibration set; unmeasured.)
- The >40% break-even trip-wire: real telemetry, per bucket.
- Cross-provider routing (the corpus is Claude-lineup-only).
- When does *effort* escalation beat *tier* escalation, measured end-to-end?
