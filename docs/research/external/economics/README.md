# Economics — token spend, quota, and scheduling

**Scope.** The O1/O2 layer: budgeting against subscription windows, burn forecasting, admission
control, cache economics, early-abort, parallelism's exchange rate, and scheduling theory that
transfers.

**Coverage: ● rich** (2026-07-10), with one decisive experiment still unexecuted.

## Holdings

- [token-economics-and-scheduling.md](token-economics-and-scheduling.md) — routing/cascade
  savings bands, burn stochasticity (~30× same-task variance; models can't self-predict),
  budget-awareness and early-abort, admission-control theory and production analogues, the
  multi-agent exchange rate (unfused), local supersessions (§2b) and operator-observed
  window events (§2c).

## Related material elsewhere

- [../platform-facts/claude-code-and-max-plan-facts.md](../platform-facts/claude-code-and-max-plan-facts.md)
  — the substrate facts economics runs on (windows, cache mechanics, credits).
- [../landscape/ecosystem-mining/limits-resume-and-wake.md](../landscape/ecosystem-mining/limits-resume-and-wake.md)
  — window awareness 0/11; wake-on-reset gap.
- Internal: [../../internal/model-speed-effort-benchmark-2026-07/](../../internal/model-speed-effort-benchmark-2026-07/README.md);
  pilot governor telemetry.
- `tools/budget-governor/` — the written-but-unexecuted cache-read quota-weight experiment
  (**still the single highest-value measurement in the corpus**).

## Open questions

- Execute the cache-read weight experiment; settle `[contested]` §10.2.
- Window-utilization telemetry over real weeks: does *our* workload ever bind?
- Multi-account / fleet economics (community practice is second accounts — unstudied).
- Batch/queue shaping against window phase, beyond the current tail-capping heuristics.
