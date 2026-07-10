# Memory and context — what the agent knows between and within runs

**Scope.** Persistent agent memory (lessons, decisions, knowledge stores, negative memory),
context engineering (what enters the window, when, in what shape), compaction survival,
retrieval vs injection, promotion lifecycles, memory staleness/decay, and memory security.

**Coverage: ● rich** (2026-07-10 deep-research pass: ~30 papers across six verified clusters,
first-party product docs, and an adversarial benchmark audit — seeded by an operator-supplied
landscape survey whose load-bearing claims were verified or corrected). The remaining thinness
is deliberate and named: **task-utility evidence for coding work does not exist anywhere yet**
— it is this project's open lane, not a reading gap.

## Holdings

- [memory-architectures-and-benchmarks.md](memory-architectures-and-benchmarks.md) — the
  stable vocabulary (and where taxonomies conflict), six production systems' mechanisms and
  staleness stories in reimplementable detail, and **the benchmark audit**: LoCoMo's broken
  answer key (6.4%), LongMemEval-S fitting inside a context window, the Mem0⇄Zep dispute, the
  one independent 12-system evaluation, and why only *relative* findings survive.
- [memory-for-coding-harnesses.md](memory-for-coding-harnesses.md) — the harness-facing
  synthesis: the two opposing task-utility measurements (Copilot's +7pp vs the independent
  "efficiency-not-quality" result), shipped practice converging on version-controlled files,
  the three importable mechanics (cite-and-verify + disuse-TTL, capped
  summary-plus-detail-on-read, trigger-scoped retrieval), the experiential/procedural transfer
  table and abstraction rule, the memory-poisoning literature's write-path verdict, and the
  concrete design mapping for the lessons corpus and `SKILL.md` library.

## Related material elsewhere

- [../landscape/ecosystem-mining/memory-and-lessons.md](../landscape/ecosystem-mining/memory-and-lessons.md)
  — the 11-repo census these documents extend (closed-loop lesson utility 0/11; negative
  memory under-exploited; promotion lifecycles in the wild).
- [../self-improvement/meta-harness-and-self-improving-harnesses.md](../self-improvement/meta-harness-and-self-improving-harnesses.md)
  §2 — ACE/MCE, the strongest published context-engineering results.
- [../platform-facts/claude-code-and-max-plan-facts.md](../platform-facts/claude-code-and-max-plan-facts.md)
  — the cache mechanics that make context shape an economic decision (kept in economics, per
  the survey literature's own memory-vs-context-engineering boundary).
- Design §5.4 (lessons corpus rules); internal pilot ledgers (capture discipline, handoff
  `key_learnings`).

## Open questions — now the measured kind

The 2026-07-10 pass replaced this folder's seed questions with sharper, evidence-shaped ones
(full list: [memory-for-coding-harnesses.md §6](memory-for-coding-harnesses.md)):

- **The paired arm**: with/without-injection on our own pilots — expect efficiency-on-hard-tasks,
  null on quality, per the external evidence. The run-log already carries what this needs.
- **Injection-usage telemetry**: workers ignored injected workflows 81.5% of the time in the
  one study that measured it — did *our* worker use the lesson it was given?
- **Lesson-poisoning red-team** against the curation gate, using the published laundering
  taxonomy's attack classes.
- **The wiki-pattern trial**: compiled repo docs vs on-demand exploration, measured at the
  merge gate — asserted by every vendor, measured by none.
