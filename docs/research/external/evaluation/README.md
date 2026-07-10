# Evaluation — measuring the machinery itself

**Scope.** How to know whether a harness (or one of its levers) works: paired-arm methodology,
benchmark design for harnesses, skill-routing reliability, judge/validator formats, run-to-run
variance handling, and escape-rate estimation.

**Coverage: ◐ moderate** (2026-07-10). One methodology-dense document plus the internal
benchmark's worked example; firing-level A/B methodology remains unbuilt everywhere.

## Holdings

- [harness-evaluation-prior-art.md](harness-evaluation-prior-art.md) — skill-routing
  reliability (under-invocation, replicated), process-ceremony cost/benefit (paired-arm:
  mandated TDD net-negative), validator/judge format patterns, with independent confirmation
  passes.

## Related material elsewhere

- Internal: [../../internal/model-speed-effort-benchmark-2026-07/](../../internal/model-speed-effort-benchmark-2026-07/README.md)
  — the corpus's one committed, re-runnable measurement harness.
- [../../distilled/README.md](../../distilled/README.md) — the evidence-grading method
  (warrant × incentive × decay) this corpus applies to *itself*.
- [../landscape/ecosystem-mining/](../landscape/ecosystem-mining/README.md) — N=5-runs
  methodology confessions; seeded-bootstrap-CI gating (ruflo).

## Open questions

- **Firing-level A/B.** No clean arm has ever been run (pilots confounded by mid-flight
  machinery evolution). What does a controlled harness experiment look like at firing scale?
- **Escape-rate estimation under weak discovery.** Catch-rate reads optimistic exactly when
  discovery is weakest — estimator design is open.
- **Variance-aware gates.** pass@k vs pass^k for machinery decisions; how many runs does a
  lever verdict need at ~30× spend variance?
