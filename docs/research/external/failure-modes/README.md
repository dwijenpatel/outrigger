# Failure modes — why long-horizon runs fail

**Scope.** Root-cause attribution and effect sizes for long-horizon autonomous coding
failure: which causes (ambiguity, reward hacking, error compounding, context degradation,
weak graders, planning/coordination, oversight decay) carry how much measured weight, on
what provenance. This is the corpus's home for the *comparative attribution* question — the
mechanism-level evidence for each individual defense stays in its own folder:
verification design in [validation/](../validation/README.md), spec/plan evidence in
[planning/](../planning/README.md), human oversight in
[human-in-the-loop/](../human-in-the-loop/README.md), coordination in
[orchestration/](../orchestration/README.md).

**Coverage: ◐ moderate** — one verified pass (2026-07-14); depth targets below.

## Holdings

- [root-causes-and-effect-sizes.md](root-causes-and-effect-sizes.md) — the 2026-07-14
  failure-attribution pass: 20 primary-source claims through three-lens adversarial
  verification (0 killed, 5 number corrections), a root-cause × effect-size ranking, and
  verdicts on the top-level README's failure-mode claims. Headline: error-compounding /
  task-length collapse is the largest, best-replicated, on-regime effect — and it is not
  one of the README's three named modes; grader-visibility → reward hacking holds the
  cleanest *causal* evidence; ambiguity is co-equal, not dominant.
- [verification-record-2026-07-14.json](verification-record-2026-07-14.json) — the
  machine-readable audit trail: every search angle, fetched source, extracted claim, triage
  reason, and per-lens verdict with notes. The document is the synthesis; this is the
  evidence it stands on.

## Open questions

- **The decomposition bet is unmeasured.** No primary source compares one long run against
  the same effort decomposed into short, fresh-session, per-link-gated tasks at equal
  budget. Chain math says success ≈ (1−ε)^N once gates catch ordinary failures, with ε =
  the gate's false-pass rate — the design's central bet rides on it. The long-horizon value
  experiment measures the **gating** half (ε and cross-task compounding-arrest); it holds
  decomposition *fixed* across arms, so the head-to-head decompose-vs-continuous comparison
  still needs a continuous-run arm that experiment does not include (named, unbuilt).
- **Our own gate's false-pass rate ε.** SWE-ABS's ~20% P(wrong | pass) is specific to
  SWE-bench-style suites; nothing here measures ε for spec-authored held-out suites.
  Calibration canaries are the named probe.
- **R3's temporal claim.** Nothing anywhere measures oversight quality as a function of
  session hours ("fails at hour six" is unevidenced); nearest durable evidence is the
  automation-bias cluster in human-in-the-loop/.
- **Single-source magnitudes queue** (doc §5): MirrorCode's undisclosed denominator;
  SWE-EVO's LLM-judged >60% instruction-following share (needs human re-annotation); an
  independent re-annotation of the 38.3% underspecification fraction.
- **MAST's inter-agent share is version-unstable** (31.3/32.3/36.9/38.4 across
  restatements) — re-pin on the next MAST version bump; cite the ranking, not a point
  value, until then.
