# Memory and context — what the agent knows between and within runs

**Scope.** Persistent agent memory (lessons, decisions, knowledge stores, negative memory),
context engineering (what enters the window, when, in what shape), compaction survival,
retrieval vs injection, promotion lifecycles, and memory staleness/decay.

**Coverage: ○ thin — no dedicated document.** The corpus touches memory only through cache
economics (a cost lens) and the lessons-corpus design sketch (§5.4). **Priority target for the
next research passes** — named explicitly by the operator.

## What exists today (scattered)

- [../landscape/ecosystem-mining/memory-and-lessons.md](../landscape/ecosystem-mining/memory-and-lessons.md)
  — the 11-repo view: closed-loop utility feedback on stored lessons is **0/11** (nobody
  measures whether memory helps), negative memory under-exploited, ECC's promotion lifecycle
  (instincts → global at 2+ projects ≥0.8 confidence), ruflo's database-first outlier,
  planning-with-files' KV-stable injection.
- [../self-improvement/meta-harness-and-self-improving-harnesses.md](../self-improvement/meta-harness-and-self-improving-harnesses.md)
  §2 — ACE (evolving playbooks; context collapse documented) and MCE (bi-level skill
  evolution): the strongest published context-engineering results.
- [../platform-facts/claude-code-and-max-plan-facts.md](../platform-facts/claude-code-and-max-plan-facts.md)
  — the cache mechanics that make context shape an economic decision.
- Design §5.4 — the lessons-corpus rules (orchestrator-owned, injected per spawn, never
  resident); Weng's challenge #2 ("context engineering will become a core part of
  intelligence") and #3 (negative-results preservation).

## Open questions — next research targets

- **Does any memory measurably help?** The 0/11 closed-loop-feedback absence is the field's
  biggest hole. What would utility-measured lessons look like (paired-arm: with/without
  injection)?
- **Negative memory.** "What NOT to retry" stores (career-ops retracted-claims, ruflo's
  rejected-mutation archive) — design and evidence for search-space pruning.
- **Promotion lifecycles.** Observation → instinct → project rule → global rule: thresholds,
  independent-confirmation gates, demotion/expiry. (Parallel to our evidence-decay classes.)
- **Retrieval vs curated injection.** Semantic retrieval (ruflo's HNSW) vs
  orchestrator-curated per-spawn injection vs resident context: costs, staleness, failure
  modes.
- **Memory staleness.** Lessons rot like vendor facts do — what's the recheck/expiry model?
- **Compaction-safe design.** What must survive `/compact`, and how do the survivors stay
  KV-cache-stable?
- **The academic memory literature.** MemGPT-lineage, episodic/semantic splits,
  reflection-based consolidation — unmined for harness-shaped conclusions.
- **Cross-project boundaries.** What may memory carry between projects (privacy, leakage,
  relevance)?
