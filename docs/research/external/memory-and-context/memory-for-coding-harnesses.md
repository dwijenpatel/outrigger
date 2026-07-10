# Memory for coding harnesses — task utility, shipped practice, security, and design mapping

The harness-facing half of the memory pass: does memory measurably help *work* (not dialogue
recall), what do shipped coding agents actually do, what does the poisoning literature say
about who may write memory, and what all of it implies for this design's lessons corpus and
skill files. Architectures, taxonomies, and the benchmark audit are in the companion,
[memory-architectures-and-benchmarks.md](memory-architectures-and-benchmarks.md).

**Provenance:** 2026-07-10 pass (same six Opus 4.8 clusters; see companion header). Extends
[../landscape/ecosystem-mining/memory-and-lessons.md](../landscape/ecosystem-mining/memory-and-lessons.md)
(the 11-repo census) with the paper literature, first-party product docs, and the security
corpus.

---

## 1. The task-utility question — the honest answer is "efficiency, maybe; quality, unproven"

**Direct measurements on coding agents exist exactly twice, and they disagree:**

- **GitHub Copilot's A/B** `[measured, vendor-run]`: coding-agent **PR merge rate 90% with
  memory vs 83% without** (review positive-feedback 77% vs 75%; both p < 0.00001). The
  strongest positive anywhere — and it is a vendor measuring its own feature on an
  operational metric the agent's behavior influences, not a blind held-out evaluation.
- **The one independent controlled test** (Sandelin 2026-03, N=9: 3 tasks × {memory, none,
  hand-written context file}, Opus 4.6) `[measured, against interest — the author builds a
  memory product]`: "**Persistent memory does not improve code quality**" — all conditions
  scored 84–96% on the same rubric. What memory bought was **efficiency that scales with
  difficulty**: 14–16% token savings overall, **22–32% cost and 28–40% fewer turns on complex
  tasks — and pure overhead on simple ones**.

**Adjacent evidence brackets the same conclusion.** SWE-ContextBench: *oracle-provided* task
summaries lift SWE resolution **+8pp** — so the ceiling is real, but the context was
"not accumulated by a memory system during operation" `[measured]`. The
experiential/procedural literature (§3) shows real transfer in Minecraft, web navigation, QA,
and enterprise workflows — and **contains no repo-scale software result at all**: no paper in
the learning-from-experience line evaluates on SWE-bench or any multi-file benchmark. The
famous Reflexion 91% HumanEval is same-task retry against self-generated tests, and the same
method **regressed on MBPP**.

**Standing conclusion for this design:** treat the lessons corpus and skill library as a
**plausible, adjacent-domain-validated bet whose coding payoff must be measured in our own
loop** — the run-log already carries what a paired with/without-injection arm needs. Expect
the measurable win to be *turns and tokens on hard tasks*, not first-attempt quality; expect
overhead on easy tasks (which argues for profile/regime-conditional injection, not
always-on).

## 2. Shipped practice — the market converged on files, and on three importable mechanics

Full product survey in the cluster notes; the load-bearing facts `[first-party-docs]` unless
tagged:

- **The convergence: version-controlled files beat opaque auto-memory.** Cursor shipped
  Memories (v1.0) and **removed them in v2.1** in favor of Rules `[practitioner-report]`.
  Windsurf/Cascade, verbatim: "For knowledge you want Cascade to reliably reuse, write it as
  a Rule or add it to `AGENTS.md`… rather than relying on auto-generated Memories." Codex:
  "AGENTS.md is static text… **not a memory system**" — yet it remains the durable layer.
  Factory's AutoWiki stores cloud-side; every agent-native auto-memory (Claude Code, Codex,
  Windsurf) is **machine-local with no sync**. The harness's file-first, curated stance is
  where shipped practice landed.
- **Mechanic 1 — summary-in-context, detail-on-read.** Claude Code injects only the **first
  200 lines / 25KB of MEMORY.md**, topic files read on demand; Codex reads
  `memory_summary.md` whole and greps the full store. Cheap, cache-friendly, matches this
  corpus's pointer-not-payload rule.
- **Mechanic 2 — cite-and-verify + disuse TTL (Copilot; the best shipped staleness design).**
  Every memory carries **citations to specific code locations**; "before applying any memory,
  the agent is prompted to verify its accuracy… by checking the cited code locations"; **any
  fact unused for 28 days is deleted**. This is re-validation at injection time plus
  utility-based expiry — importable wholesale into a lessons corpus (cite the commit/test
  that justified each lesson; re-verify at injection; expire the never-injected).
- **Mechanic 3 — trigger/path-scoped retrieval, not all-at-once.** Devin Knowledge retrieves
  "when relevant, not all at once"; Claude Code path-scoped rules load on matching-file
  access. Structural relevance beats semantic search at this scale.
- **The recurring shipped failure is capture reliability.** The `agentmemory` production
  walk-back `[practitioner-report, against interest]`: "BM25 reindex on every restart,
  5-second data-loss window, **wrong hook key on ~47% of Claude Code tool calls**" — author
  withdrew his own recommendation after a week. Copilot's `store_memory` tool "isn't being
  invoked reliably" `[practitioner-report]`. Echoes this corpus's skill under-invocation and
  hooks-vs-skills reliability findings: **capture must be deterministic (hooks), never
  model-initiative**.
- **The wiki pattern is real and unmeasured.** Karpathy's gist (2026-04-04) is an explicit
  idea-file; DeepWiki/AutoWiki/OpenWiki productize it; **no wiki product publishes any
  measurement that compiled docs improve agent outcomes** — the pitch is maintenance burden,
  the benefit asserted ("fewer avoidable mistakes"). The nearest measured signal is the
  oracle +8pp above.

## 3. Experiential and procedural memory — what transfers, at what abstraction, and what to forget

The learning-from-doing literature, interrogated for **transfer** (new tasks, not re-attempts):

| System | Domain | Transfer to new tasks? | Key number `[author-run]` |
|---|---|---|---|
| Reflexion (NeurIPS 2023) | code/QA/embodied | **No — same-task retry** | HumanEval 91% (vs 80) via self-tests; **MBPP regressed** 77.1 vs 80.1 |
| Voyager (2305.16291) | Minecraft | **Yes** — skill library solves 4/4 tasks in a *new world*; baselines 0/4 | 3.3× unique items; skills committed only after self-verification |
| ExpeL (AAAI 2024) | QA/web/embodied | **Yes** — cross-benchmark HotpotQA→FEVER 70% vs 63% | insights via ADD/EDIT/UPVOTE/DOWNVOTE |
| AWM (2409.07429) | web | **Yes** — grows with distribution gap (+8.9 cross-site, +14.0 cross-domain) | WebArena +51.1% relative; **agents ignored injected workflows 81.5% of the time** |
| MemP (2508.06433) | embodied/planning | Similar-task; weak→strong model transfer (+5%) | ALFWorld +35.7pp; **"scripts generalize; trajectories fit similar tasks; combining is optimal"** |
| Skill-Pro (2602.01869) | ALFWorld/games | Cross-difficulty + cross-agent | **102 tokens/skill vs 2,675/trajectory vs 4,568/insight** (~500× compression) |
| AFTER (2606.23127) | enterprise | **Skill-dependent** — some skills over-specialize and *lose* value under transfer | +3.7–6.7 pts/refinement round |
| ParamMem (2602.23320) | code (function-level) | Weak-to-strong (8B-trained lifts 80B) | LiveCodeBench 68 vs 62 — the only external-memory coding gain, single-source |

**The abstraction rule (convergent across MemP, AWM, Skill-Pro, AFTER):** parameterized,
abstracted procedures generalize and are radically cheaper in context; raw trajectories win
only on near-duplicate tasks; keep **both**, route by task similarity, and **tag each skill's
scope** (general vs project-specific) because over-specialized skills lose value when reused.
For this harness: Voyager's discipline maps directly onto `SKILL.md` files — **commit only
after verification passes, index by description, allow composition** — and AWM says write
skills with `{parameters}`, never transcripts.

**Forgetting:** the only explicit decay curve in the literature (MemoryBank's Ebbinghaus
model) was **never ablated**; every system that works uses **utility-gating and supersession**
(keep-what-works, up/down-vote, reflectively revise failures). A lessons corpus needs a
*used-and-useful* signal, not a timer — with one exception: vendor-fact-like lessons decay
with the platform, which is this corpus's evidence-decay insight applied inward.

**The 81.5% ignore-rate** (AWM) is the same pathology as this corpus's skill
under-invocation finding: injected guidance is unreliable unless phase-gated. Injection is
not application — measure whether workers *use* injected lessons, not whether they received
them.

## 4. Security — who may write memory is the whole game

The 2026 literature has named and measured the problem this design guessed at
(`[peer-reviewed]` where marked, else `[preprint]`):

- **Poisoning works at trivial cost.** AgentPoison (**NeurIPS 2024**): <0.1% poison rate →
  ≥80% attack success; a *single* poisoned instance with a one-token trigger ≥60%.
  PoisonedRAG (**USENIX Sec 2025**): 5 texts → ~90% success against million-document corpora;
  tested defenses "insufficient." MINJA (2503.03704): an attacker with **query-only access —
  never touching the store** — achieves 95–100% injection success via bridging-step prompts.
- **The laundering problem is now named and benchmarked**: *From Untrusted Input to Trusted
  Memory* (2606.04329) taxonomizes six attack classes with 34–67% average success, and finds
  prompt-injection filters miss weak-signal attacks by −40pts TPR; *Cross-Session Stored
  Prompt Injection* (2606.04425) measures 32–42% end-to-end success. Unit 42 demonstrated it
  against Bedrock Agents with **365-day persistence** `[practitioner-report]`. The convergent
  against-industry finding: "**defending against memory poisoning requires defenses that
  operate at the write path, not the input boundary.**"
- **Contradiction handling ≠ trust handling.** Zep's bi-temporal "newer information always
  wins" is itself a poisoning vector (a poisoned entry supersedes a true one); its provenance
  links are for citation, not trust. Hindsight's confidence scores encode epistemic
  uncertainty, not source trust. No production system does trust-weighted writes.
- **The verdict on this design's three pillars** (orchestrator-owned corpus, workers
  read-only; review-before-promotion; provenance/generation stamps): **(a) write-gating is
  supported** — it is exactly "Write Authorization" in the security survey (2604.16548) and
  the formally-verified origin-bound-authority defense (2606.24322); **(c) provenance stamps
  are supported and named the prerequisite primitive** ("remains rare in published
  architectures"); **(b) quarantine-before-promotion is ahead of published practice** — one
  validated analogue (VerificAgent's human-verified freezing) — a design bet, not a settled
  result. The surveys also warn the un-validated spots: multi-agent write concurrency has
  only engineering folklore behind it (Letta: last-writer-wins, "no atomic locking",
  designate an owner agent — which is this harness's topology anyway, named
  "orchestrator-based memory routing" in 2602.06052).

## 5. Design mapping — what this pass changes for the lessons corpus and skills

**Confirmed (adopt with confidence):** orchestrator-owned single-writer topology; per-spawn
curated injection (the surveys' mitigation for context bloat/goal drift — "active memory
perception" is a named frontier); disk ledgers as auditable token-level substrate (the
Trustworthy-Memory endpoint is "segmented, version-controlled, auditable" — plain git files
already are); negative memory as first-class (**contrastive success/failure induction is a
named abstraction mechanism**, not a hack); soft-supersession over deletion.

**Import (concrete, evidence-backed):**
1. **Cite-and-verify + disuse-TTL** on every lesson (Copilot): each entry carries the
   commit/test/observation that justified it; re-verify citations at injection; expire
   entries never injected. This composes staleness *and* trust.
2. **Summary-capped injection with detail-on-read** (Claude Code / Codex): the injected block
   stays small and cache-stable; the corpus behind it can grow.
3. **Voyager discipline for `SKILL.md`**: verified-before-commit, description-indexed,
   composable; **AWM parameterization**: `{placeholders}`, never transcripts; **AFTER scope
   tags**: general vs project-bound, gating cross-project reuse.
4. **Dual-store** (MemP): abstracted lessons/skills for novel tasks + a thin raw-exemplar
   side-store for near-duplicates; Skill-Pro's ~500× compression says the injected layer
   should be the abstracted one.
5. **Utility-gating, not timers** (ExpeL/MemP): track per-lesson use-and-outcome in the
   run-log; prune what stops earning; the Ebbinghaus curve has no evidence behind it.
6. **Mem0's ADD/UPDATE/DELETE/NOOP contract** as the orchestrator's consolidation decision —
   at this corpus's scale the orchestrator can read the whole corpus and decide; no vector
   DB, no embedding index (the independent eval's localized-maintenance finding says small
   and bounded is the *cost-winning* regime, and Letta's filesystem+grep result says the
   substrate is not the bottleneck).

**Divergences to hold, knowingly:** the research frontier points at parametric/latent
internalization and RL-learned memory policies; this harness stays token-level, external,
auditable — a trade the surveys themselves justify (parametric memory's interpretability and
catastrophic-forgetting costs are disqualifying where lessons must be inspectable and
revertible). And A-MEM-style in-place evolution of old entries is **rejected**: it is
anti-provenance and unforgeable-history is the point.

**What nothing in the literature provides — our open lane:** closed-loop measurement that a
memory system improves *coding task* outcomes (the 0/11 ecosystem absence now extends to the
entire paper literature); negative memory as a *measured* construct; maintenance-under-update
evaluation. A **blind-validator-gated, capped, cite-verified, outcome-labeled lessons file
measured at the merge gate** is a combination no shipped or published system offers — and
each ingredient is exactly one of the field's documented failure modes, inverted.

## 6. Open questions (supersedes the folder README's seed list where they overlap)

- Run the with/without-injection paired arm on our own pilots (the Sandelin design at firing
  scale, with the run-log as the ledger): does the lessons corpus buy turns/tokens on hard
  tasks here? Expect null on quality per the external evidence.
- Injection-usage telemetry: did the worker *use* the injected lesson (AWM's 81.5% problem)?
  Requires a use-attribution convention in handoffs.
- Lesson-poisoning red-team: can a worker's handoff smuggle an instruction that survives
  curation into the corpus? (The laundering taxonomy gives the attack classes to test.)
- Wiki-pattern trial for repo knowledge: compiled `openwiki/`-style docs vs on-demand
  exploration, measured at the merge gate — nobody has measured this; we can.
- Watch: BEAM-style maintenance-under-update benchmarks; any independent replication of
  Copilot's +7pp; Meta-Harness/Meta-Zenith releases touching memory config.
