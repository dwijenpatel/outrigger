# Agent memory — architectures, taxonomies, and the benchmark problem

What the memory literature actually establishes: the stable vocabulary, the production-system
mechanisms (in reimplementable detail), what every system's staleness story is, and — the
load-bearing section — why almost none of the published benchmark numbers survive
incentive-aware scrutiny. The harness-facing synthesis (task utility, shipped practice,
security, design mapping) is the companion document,
[memory-for-coding-harnesses.md](memory-for-coding-harnesses.md).

**Provenance:** 2026-07-10 deep-research pass. Seed: an operator-supplied AI-generated
landscape survey (not committed — treated as unverified orientation; its load-bearing claims
are corrected below). Six Opus 4.8 clusters: foundations/surveys (6 papers, identities and
venues verified, 3 read via PDF extraction), production systems (6 papers, full text),
benchmark verification (adversarial, web + papers), experiential/procedural (10 papers),
shipped practice (first-party docs), security/multi-agent (papers + advisories). Tags per
corpus convention; every number carries who-measured-it.

---

## 1. Vocabulary — what is stable and what is contested

Six framework/survey papers were verified: CoALA (arXiv 2309.02427, **TMLR — peer-reviewed**),
Zhang et al. (2404.13501, preprint), *Memory in the Age of AI Agents* (2512.13564, preprint,
129 pp.), *Rethinking Memory Mechanisms of Foundation Agents in the Second Half* (2602.06052,
preprint), *From Storage to Experience* (2605.06716, **ACL 2026 Findings**), *Lifelong
Learning of LLM-based Agents* (2501.07278, **IEEE TPAMI**). None runs its own benchmarks —
peer-review attaches to framing, not to any system's numbers. `[E]`

**Universal across all six (safe to adopt):**

- **Working / episodic / semantic** as functional memory types — the current decision cycle's
  scratchpad; past trajectories; world facts/knowledge.
- **The operation lifecycle: write → maintain → retrieve** (under varying names — CoALA's
  retrieval/reasoning/learning; formation/evolution/retrieval; storage/updates/retrieval).
- **The substrate split: external-token vs internal-parametric** — text a system can inspect
  and edit, vs knowledge in weights.

**Contested (do not treat as settled):**

- **The fourth type.** CoALA says *procedural* (skills/code/weights, with the warning that
  writing it is "significantly riskier" than episodic/semantic writes); the
  Lifelong/Zhang/Mem-Age line says *parametric* (a substrate, not a function); Rethinking adds
  *sensory*. No consensus.
- **Top-level cut.** *Memory in the Age of AI Agents* deliberately rejects the long/short-term
  dichotomy for a Forms × Functions × Dynamics lens (token/parametric/latent ×
  factual/experiential/working × formation/evolution/retrieval); others keep cognitive types
  primary. *From Storage to Experience* is orthogonal to both: a **maturity axis** — Storage
  (raw trajectories) → Reflection (refined) → Experience (cross-trajectory abstraction under a
  minimum-description-length view).
- **Scope boundaries.** RAG = static sources, single invocation; agent memory = persistent,
  self-evolving, cross-task. Context engineering manages the window as a resource; agent
  memory models a persistent entity — and the boundary "effectively dissolves" for short-term
  memory `[E, 2512.13564]`. This corpus keeps cache/context economics in
  [../economics/](../economics/README.md) and treats memory as the durable layer, matching
  that split.

## 2. Production systems — mechanisms and staleness stories

Six systems read in full (`[author-run]` applies to every number; see §3 before comparing any
of them). Mechanisms, condensed to the reimplementable core:

| System (paper) | Substrate | Update model | Staleness / contradiction |
|---|---|---|---|
| **MemGPT** (2310.08560) | Paged context + external archival/recall stores | Self-editing function calls; FIFO warning at 70% of window, flush at 100% evicts 50% into a recursive summary | **None** — lossy summarization, no versioning or conflict handling |
| **Zep/Graphiti** (2501.13956) | Neo4j temporal knowledge graph (episode → entity → community tiers) | LLM entity/edge extraction; hybrid cosine+BM25+graph retrieval, reranked | **Bi-temporal** (`t_valid/t_invalid` event time; `t_created/t_expired` transaction time); contradiction → non-destructive invalidation, "newer wins" |
| **Mem0** (2504.19413, ECAI 2025) | Vector store (+Neo4j graph variant) | Extract facts from message pairs; per-fact LLM tool call chooses **ADD / UPDATE / DELETE / NOOP** against top-10 similar | UPDATE on higher information content; DELETE on contradiction; graph soft-invalidates edges; no decay |
| **A-MEM** (2502.12110) | Vector store of Zettelkasten notes | Auto-link top-k neighbors; **"evolution" rewrites existing neighbors in place** when new notes arrive | **None** — no delete, no decay, no conflict detection; destructive mutation without provenance |
| **MemoryOS** (2506.06326, **EMNLP 2025 Oral**) | Tiered short/mid/long stores | FIFO short→mid; **heat-based promotion** mid→long: `Heat = α·visits + β·interactions + γ·exp(−Δt/μ)` (μ ≈ 115 days; α=β=γ=1, admittedly arbitrary) | Recency decay + lowest-heat eviction; no active contradiction resolution |
| **Hindsight** (ACL 2026 **demo track**) | PostgreSQL+pgvector, four networks (world / experience / observation / **opinion**) | Retain (2–5 narrative facts/conversation) → 4-channel recall (vector, BM25, graph spreading-activation, temporal) → RRF + cross-encoder, token-budgeted → Reflect | Best-designed: **confidence-scored opinions** reinforced up/down by evidence; observations carry a freshness trend {new, strengthening, stable, weakening, stale}; non-destructive refinement |

Recurring mechanisms: extraction → consolidation → tool-based update (everyone but MemGPT);
temporal validity (Zep the reference, Hindsight and Mem0-graph partial); hierarchical
promotion (MemGPT, MemoryOS, Hindsight, Zep); hybrid retrieval with fusion (Zep, Hindsight,
Mem0ᵍ); confidence-scored beliefs (**only Hindsight**).

**Admissions against interest worth keeping** `[E]`: MemGPT — "significantly degraded
performance using GPT-3.5" (0% at one nesting level; the pattern needs frontier function
calling). Zep — its own headline benchmark (DMR) is "inadequa[te] for evaluating memory
systems"; a whole LongMemEval category **regressed** (−17.7% single-session-assistant). Mem0 —
**full-context beats it on accuracy** (72.90 vs 68.44 LLM-judge; it trades ~5 points for 91%
lower p95 latency), and its graph variant *hurts* single- and multi-hop. Hindsight — its own
table shows Backboard above it on LoCoMo (90.0 vs 89.6); its "independent reproduction" credits
are co-author institutions; benchmark numbers live in an unpublished companion paper.

## 3. The benchmark problem — why the published numbers don't rank systems

This section exists because the seed document (like most secondary coverage) presented
vendor numbers as a leaderboard. They are not one. `[adversarially verified, 2026-07-10]`

**The instruments are weak, and they measure dialogue, not work:**

- **LoCoMo** (2402.17753, ACL 2024) is measurably broken: an independent audit found **99
  score-corrupting errors in 1,540 questions (6.4% of the answer key)** — hallucinated gold
  facts, wrong speaker attribution — putting the ceiling for a perfect system at **~93.6%**;
  and the standard LLM judge **accepts 62.8% of intentionally-wrong-but-topical answers**
  (a repaired judge reaches 86.3% human agreement vs 43.7% for the original). Any LoCoMo
  score above ~85% is inside the noise band. `[independent]`
- **LongMemEval** (2410.10813, ICLR 2025) is real, but the **-S variant every vendor quotes
  is ~115k tokens — it fits inside a modern context window**, so it tests retrieval/context
  management, not durable memory. Optimized plain RAG scores **86%** on it `[independent]`;
  the -M variant (~1.5M tokens) is rarely quoted.
- **BEAM** (2510.27246, ICLR 2026) is the honest instrument — academic, up to 10M tokens,
  deliberately unsaturated. (Mem0 markets its BEAM scores; it did not create BEAM.)
- **All three are multi-session personal-assistant dialogue-recall benchmarks.** None
  measures coding-task or build-loop utility.

**The claims are self-administered and non-comparable:**

- The seed's contradiction ("Zep #1 at 63.8%" vs "Mem0 94.4%") resolves as **different
  instruments a year apart**: Zep's 63.8/71.2% (Jan 2025 paper, GPT-4o readers, original
  algorithm) vs Mem0's 94.4% (2026 marketing blog, revised algorithm, undisclosed judge).
  The ~30-point spread is reader-model strength and time, not architecture. Hindsight's 91.4%
  rides a **Gemini-3 Pro reader** (it measures the model plus retrieval); its 83.6% with a
  20B reader is the defensible config. MemoryOS's "+49.11% F1" is a *relative* delta on
  *word-overlap* metrics — a different axis entirely. agentmemory's "95.2%" is retrieval
  recall, not QA accuracy (the vendor itself says so).
- **Reimplemented baselines diverge wildly:** A-MEM's LoCoMo temporal F1 is **45.85 in its own
  paper, 35.40 as reimplemented by Mem0, and 8.04 as reimplemented by MemoryOS** — a 5.7×
  spread on one cell. Cross-paper tables are meaningless.
- **The Mem0 ⇄ Zep dispute** is documented on both sides: Mem0 caught Zep's LoCoMo score
  counting excluded-category answers in the numerator (Zep self-corrected **84% → 75.14%**, a
  ~9-point concession); Zep caught Mem0 misconfiguring its user model, timestamps, and search
  parallelism when scoring Zep at 65.99%. Along the way, **both sides' own full-context
  baselines beat the memory systems** in places — the "no-memory-system" condition winning is
  the quiet headline. A third vendor's "100% LoCoMo" was exposed as outright gamed (patched
  dev questions, top_k above the session count). `[independent + both parties]`

**The one incentive-neutral evaluation** — *Are We Ready For An Agent-Native Memory System?*
(2606.24775, Shanghai Jiao Tong data-management group, no memory product; ~12 systems + 2
baselines, 5 workloads, 11 datasets) `[independent, preprint]`:

- **"No single memory system dominates all workloads."** Verified verbatim.
- Absolute scores collapse under a standardized harness: the LongMemEval *leader* is Zep at
  **48.0** (vs its own 63.8, vs Mem0's marketed 94.4); the LoCoMo leader scores **11.5
  exact-match**. Read orderings, never absolutes.
- **Maintenance economics is where systems separate:** "the most cost-efficient memory
  mechanisms localize maintenance to a bounded subset… mechanisms that repeatedly reorganize
  a large global state are the least efficient" — LightMem 48.3 utility at 3.67s vs Zep at
  155.1s and Cognee at 116.5s per maintenance cycle. Graph structure genuinely leads
  knowledge-*update* workloads (Zep best at 44.4 substring-EM); flat text collapses as the
  evidence gap widens.
- Corroborating independents: MemoryBench — "none of the advanced memory-based LLM systems
  can consistently outperform RAG baselines that simply use all task context"; AMemGym —
  static leaderboards misrank vs on-policy evaluation by up to 3 positions; **Letta's
  against-interest result: filesystem + grep + gpt-4o-mini scores 74.0% on LoCoMo**, beating
  Mem0-graph and ~tying corrected Zep — "memory is more about how agents manage context than
  the exact retrieval mechanism."

**What survives, and the protocol:** only *relative* findings — Zep/graph structure leads
recall-and-update workloads (independently corroborated) at the highest maintenance cost;
localized maintenance wins the cost frontier; every absolute ≥90% figure is an artifact of
variant choice, reader strength, judge leniency, metric substitution, or a broken key. For
any harness-side test: run **full-context and filesystem-grep baselines**, audit the ground
truth first, publish the judge prompt, use multi-seed runs, and prefer on-policy evaluation
in the real loop — and if a dialogue benchmark must be used, use LongMemEval-M or BEAM-10M
where context-stuffing is impossible.

## 4. What the literature converges on

- **Maintenance is the bottleneck — 5 of 6 surveys, plus the independent eval.** Ingestion
  and retrieval are mature; update/conflict-resolution/consolidation/forgetting is where
  systems fail and where cost lives. The documented update-maturity ladder: rule-based
  replace → **temporal soft-deletion** (invalidate, keep history) → dual-phase (online
  soft-update + offline reflective consolidation) → RL-learned update policies. `[E]`
- **Memory measurably hurts when unmanaged** — convergent failure modes across ≥3 surveys
  each: retrieval of irrelevant/obsolete entries disrupts reasoning; accumulation "saturates
  attention budgets, increases latency, and induces goal drift"; incorrect updates overwrite
  critical information; errors propagate and "contaminate the efficacy of learning";
  consolidation causes "information smoothing, where outlier events or unique exceptions are
  lost." Unbounded accumulation is named detrimental in so many words. `[E]`
- **Forgetting: implemented rarely, validated never.** The one explicit decay model
  (MemoryBank's Ebbinghaus `R = exp(−t/S)`) was **never ablated**; Generative Agents' recency
  decay is a retrieval-ranking term validated only on believability. What has support is
  **utility-gating and supersession** — keep-what-works, soft-invalidate the rest (see the
  experiential evidence in the companion doc §3).
- **Evaluation itself is the recurring open problem** (5 of 6 surveys): static, short-horizon,
  conversational QA that never tests maintenance-under-update — exactly the gap §3
  demonstrates empirically.

## 5. Corrections to the seed document

Recorded so nobody re-imports the errors: `2602.01869` is **Skill-Pro**, not "ProcMEM";
`2602.23320` is **ParamMem**; *Rethinking Memory Mechanisms*' full title ends "…in the Second
Half"; CoALA, *From Storage to Experience*, and the Lifelong roadmap are peer-reviewed (TMLR /
ACL Findings / TPAMI), which the seed understated. The seed's Reflexion account omits that the
method **regressed on MBPP** (77.1 vs 80.1) and that its HumanEval 91% is same-task retry
against self-generated tests. Karpathy's LLM Wiki is a gist dated **2026-04-04**, explicitly
"an idea file… designed to be copy pasted," with no outcome claims; OpenWiki released
**2026-07-01** (not 06-30) with a GitHub Action that runs "on schedule" (not confirmed daily).
Mem0's 92.5/94.4 figures are **marketing-blog numbers absent from its peer-reviewed paper**,
whose real result is LoCoMo J = 66.88/68.44 — below its own full-context baseline. Zep's
"#1 with 63.8%" was true at paper time (Jan 2025) and is not comparable to any 2026 number.
