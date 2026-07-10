# Orchestration — roles, topologies, and parallelism

**Scope.** How work is divided and coordinated: orchestrator/worker patterns, multi-agent
topologies, parallel implementation and integration (merge queues, worktrees, stub-and-seams),
handoff formats, concurrency correctness, and delegation depth.

**Coverage: ● rich** (2026-07-10 deep-research pass: ~45 sources across six verified clusters —
the does-multi-agent-pay adjudication, the MAST failure taxonomy, parallel code-generation,
handoff/communication, shipped frameworks, and distributed-systems concurrency theory *including
a source-level audit of the harness's own machinery*).

## Holdings

- [multi-agent-orchestration-evidence.md](multi-agent-orchestration-evidence.md) — the topology
  evidence: does multi-agent beat a single strong agent (the Anthropic-vs-Cognition adjudication
  and the equal-budget refutation — mostly a token-spend artifact), why multi-agent fails (the
  MAST 14-mode taxonomy mapped onto the harness; the cascade needs a *blocking gate*; faulty-not-
  Byzantine → an independent inspector recovers 96.4%), parallel code-generation (CodeCRDT's
  concurrent-write-is-slower, CAID's partition-then-serial-integrate is the one repo-level win,
  the Specification Gap's determinacy proof), the handoff/structured-return resolution (correct,
  and the strongest critic now agrees), and the shipped-framework topology survey.
- [concurrency-and-merge-correctness.md](concurrency-and-merge-correctness.md) — the
  distributed-systems theory under the harness's concurrency primitives (OCC, ARIES/WAL,
  effectively-once, the Not-Rocket-Science Rule, HiLo/Snowflake), a **source-level audit** mapping
  the pre-registered W1–W5 watch items onto known hazards, and **four code-verified findings** —
  including **B-4, a genuine latent merge-race bug** (the interlock validates the source HEAD but
  never the base, so sequential merges of parallel branches can land green-against-stale-base). A
  hardening backlog, B-4 first.

## Related material elsewhere

- [../landscape/ecosystem-mining/parallelization-and-decomposition.md](../landscape/ecosystem-mining/parallelization-and-decomposition.md)
  — the 11-repo stub-and-seams practitioner study these documents extend with academic evidence.
- [../landscape/landscape-and-novelty.md](../landscape/landscape-and-novelty.md) §1–2 — the
  20+-framework comparison matrix (isolation vs shared-thread).
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) — the shipped
  ACP orchestrator (terminal reviewer; §8 ACP-as-portability-hedge).
- [../economics/token-economics-and-scheduling.md](../economics/token-economics-and-scheduling.md)
  §6 — the multi-agent token exchange rate.
- [../planning/](../planning/README.md) — the spec-layer exposure (the top MAST residual) is the
  same blind spot the planning pass located; the Specification Gap appears in both passes.
- Internal: W1–W5 (`internal/pilot-2-artifacts/watch-items.json`) — pre-registered, still
  unobserved; the concurrency doc turns them into precise hazards.

## Open questions

- **Close B-4 / W3** — the code-verified merge-race, mechanically simple (the `base` field the fix
  needs is already recorded); most likely to produce the first silent wrong merge.
- The **repo-scale decomposition-quality → integration-success** curve with blind pre-dispatch
  seam contracts — the publishable gap nobody has filled.
- Add **committed-constraints** to the handoff schema and test whether it catches cross-worker
  conflict pre-merge.
- Right-size validation panels to the decorrelation saturation knee (~2–4); design **verdict
  reconciliation** as a first-class surface.
- Adaptive/task-conditional topology (AdaptOrch/Meta-Zenith) as the evidence base for the risk
  table; AgentCore-style microVM isolation as a vault substrate.
