# Orchestration — roles, topologies, and parallelism

**Scope.** How work is divided and coordinated: orchestrator/worker patterns, multi-agent
topologies, parallel implementation and integration (merge queues, worktrees, stub-and-seams),
handoff formats, concurrency control, and delegation depth.

**Coverage: ○ thin — no dedicated document.** Orchestration facts are scattered across the
landscape studies and the design doc; the *evidence* layer (what topology wins, when, at what
cost) is nearly empty everywhere, not just here.

## What exists today (scattered)

- [../landscape/ecosystem-mining/parallelization-and-decomposition.md](../landscape/ecosystem-mining/parallelization-and-decomposition.md)
  — parallel-implementation throughput measured by **0/11**; superpowers explicitly forbids
  parallel implementers; ECC's Ralphinho is the only end-to-end stub-and-seams statement
  (prose, unmeasured).
- [../economics/token-economics-and-scheduling.md](../economics/token-economics-and-scheduling.md)
  §6 — the multi-agent exchange rate, unfused (~4×/~15× token multipliers; Anthropic's 90.2%
  at unequal budget).
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) §1 — a
  shipped declarative orchestrator (7 tools, deterministic kernel, per-role providers via ACP).
- [../landscape/landscape-and-novelty.md](../landscape/landscape-and-novelty.md) §1–2 —
  isolation-vs-shared-thread across 20+ frameworks.
- Internal: W1–W5 (the entire concurrency watch-item family) — **pre-registered and still
  unobserved**; no two tasks have ever run in parallel here.

## Open questions — next research targets

- **Topology evidence.** Orchestrator-workers vs peer teams vs pipelines vs swarms: is there
  *any* controlled comparison anywhere, or only vendor demos?
- **Parallel implementers into one codebase.** The measured answer is missing field-wide.
  What integration discipline (seams, merge queue, integrator agent) makes it net-positive,
  and at what determinacy bar?
- **Handoff compression.** What information may cross a worker boundary, in what shape, and
  what is lost? (Structured returns vs transcripts vs artifacts.)
- **Concurrency correctness.** Our own generation-stamps/write-ahead machinery is untested
  under real interleaving (W1–W5) — as is everyone else's.
- **Delegation depth.** When does a sub-sub-agent pay? Nesting evidence is absent.
- **Failure containment.** One worker's death/poisoned output inside a fan-out: quarantine
  patterns.
