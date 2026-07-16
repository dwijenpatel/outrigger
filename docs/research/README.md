# Research corpus — index

Primary-sourced research behind the harness design
([../attic/token-time-optimized-harness.md](../attic/token-time-optimized-harness.md)),
organized by topic. Each document is self-contained and cites primary sources inline with
confidence tags: `[official]` Anthropic docs, `[measured]` community/benchmark measurement with
data, `[contested]` conflicting evidence, `[folklore]` practitioner consensus; plus `[E]`
established-in-source / `[I]` inference-synthesis for research-study claims.

Unfamiliar term? [../terminology.md](../terminology.md) defines every acronym, coined term, and
evidence tag used across this corpus (and the full tag legend).

Compiled from four research efforts: a comparative state-of-the-art study and re-validation
prior-art digest (**2026-07-03**), a targeted gap-filling deep-research pass on routing
economics, burn forecasting, Claude Code/Max-plan mechanics, and vault isolation
(**2026-07-04**), a practitioner-stack survey + independent-confirmation pass
(**2026-07-04**): four-agent survey of the github.com/kunchenguid repos (AXI, gnhf, firstmate,
treehouse, no-mistakes, benchmark suite), three adversarial web-verification agents restricted
to independent sources, and a local zero-quota tokenizer measurement on this harness's own
data shapes — and a **critique-refresh pass (2026-07-04 evening)**: re-evaluation of the §4
design critique against the as-built system (in-tree verification of hooks/gate/governor/vault
state at 358 passing tests) plus targeted fetches on verifier precision (false FAILs) and
cross-model error correlation. The gap-filling pass used a fan-out → fetch → 3-vote adversarial
verification workflow (24 of 25 top claims confirmed, 1 refuted); its three most design-changing
facts were re-verified by direct fetch of the official pages. A **meta-harness + closest-neighbor
pass (2026-07-09)** added two documents: Lilian Weng's "Harness Engineering for
Self-Improvement" (2026-07-04) plus all ~40 of its cited references analyzed in four
identity-verified clusters (six load-bearing papers read in full text), and an exhaustive
code+report study of Intelligent Internet's Zenith harness (local clone) with an external
survey of its Meta-Zenith and benchmark claims. An **agent-memory pass (2026-07-10)**, seeded
by an operator-supplied landscape survey (verified, corrected, not committed), ran six Opus 4.8
clusters — foundations/surveys, production systems, an adversarial benchmark audit,
experiential/procedural memory, shipped coding-agent practice, and memory security — over ~30
verified papers and first-party docs, producing the two memory-and-context documents. A
**planning pass (2026-07-10)** ran six Opus 4.8 clusters — can-LLMs-plan (LLM-Modulo/PlanBench),
decomposition methods, classical planning + representations, requirements-engineering/spec-driven
development, shipped products, and a does-it-pay/brownfield/evaluation synthesis — over ~40
primary sources, producing the two planning documents. An **orchestration pass (2026-07-10)** ran
six Opus 4.8 clusters — the does-multi-agent-pay adjudication (Anthropic vs Cognition; the
equal-budget refutation), the MAST failure taxonomy, parallel code-generation, handoff/
communication, shipped frameworks, and distributed-systems concurrency theory (with a source-level
audit of the harness's own machinery that surfaced a latent merge-race bug) — producing the two
orchestration documents. A **human-in-the-loop pass (2026-07-10)** ran six Opus 4.8 clusters over
the mature adjacent fields — automation bias/complacency/alarm fatigue, mixed-initiative and
levels-of-automation, adjudication economics, scalable oversight and human-AI complementarity,
code-review HITL, and ratification governance — producing the two human-in-the-loop documents and
completing the 14-subtopic sweep. A **distillation refresh (2026-07-10)** then re-graded all four
passes into [distilled/](distilled/README.md) via four independent Opus 4.8 extraction agents —
adding ~30 Tier-A entries (two new mathematics rows, the human-factors cluster under a new
`human-factors` decay class, the equal-budget orchestration class-claims, the memory-benchmark
record, nine new absence rows) and the B-1..B-4 concurrency source-audit to
[distilled/internal.md](distilled/internal.md) as open defects. A **failure-attribution pass
(2026-07-14)** ran an 88-agent Opus 4.8 deep-research workflow — six search angles → 20
identity-checked primary sources → 74 extracted claims → 20 bucket-balanced claims through
three-lens adversarial verification (source-fidelity, methodology/regime-fit,
independent-replication; ≥2/3 refutes kill; 0 killed, 5 single-lens number corrections) —
adjudicating the root causes and effect sizes of long-horizon coding-agent failure against the
top-level README's claims, adding the fifteenth subtopic folder
([external/failure-modes/](external/failure-modes/README.md)) with a committed machine-readable
verification record. An **auto-research retrieval pass (2026-07-15)** — four Opus 4.8 agents
mirroring the primary artifacts of Karpathy's `autoresearch`, NVIDIA's ENPIRE, and AlphaEvolve's
2026 developments (product GA, the 67-problem math repo, the matmul-novelty dispute), plus a
landscape sweep, ahead of the 2026-07-18 AGI House auto-research summit — added
[external/self-improvement/auto-research-systems-2026-07.md](external/self-improvement/auto-research-systems-2026-07.md)
with three gaming-ledger additions; retrieval-grade verification only (no adversarial panel), so
nothing from it entered distilled/.

## Layout

The corpus is split by **who produced the evidence**, because provenance is the first thing that
determines how much weight a claim can carry:

| Directory | What's in it | How to weigh it |
|---|---|---|
| **[external/](external/)** | Vendor documentation, peer-reviewed and preprint literature, other people's systems and repos — **organized into 15 harness-design subtopic folders**, each with its own scoped README, holdings, and open questions. | We did not run these experiments. Strongest when independently replicated or when a source concedes something against its own interest; weakest when a party benchmarks its own product. |
| **[internal/](internal/)** | Our own pilot firings, our own zero-quota benchmarks, our own committed telemetry. | We ran these — exactly reproducible, and exactly as biased as we are. Our recorded **defects** are strong evidence; our recorded **wins** are not. |
| **[distilled/](distilled/README.md)** | The highly-reliable subset of both, and the grading method that decides what qualifies. | **Start here.** Everything in it is Tier A; everything else in the corpus is context. |

## The documents

### External — the world's evidence, by harness-design subtopic

`external/` is organized as a **map of the coding-agent-harness design space**, not of what we
happened to research first. Each folder's README states its scope, holdings, related material,
and open questions. Empty-handed folders are deliberate: they mark subproblems the corpus has
not yet covered, and they are the queue for the next research passes.

Coverage: **● rich · ◐ moderate · ○ thin (no dedicated document)** — as of 2026-07-14.

| Subtopic | Holdings | Coverage |
|---|---|---|
| [validation/](external/validation/README.md) — the correctness floor: blind validation, held-out testing, gates, verifier calibration, leakage theory | correctness-and-verification-evidence; revalidation-reuse-and-leakage | ● |
| [self-improvement/](external/self-improvement/README.md) — harnesses as the optimized object; the gaming ledger; governance of self-modification | meta-harness-and-self-improving-harnesses | ● |
| [economics/](external/economics/README.md) — token/quota budgeting, burn forecasting, admission control, parallelism's exchange rate | token-economics-and-scheduling | ● |
| [landscape/](external/landscape/README.md) — whole-system comparative studies (span every subtopic; the thin folders' best current material lives here) | landscape-and-novelty; zenith-and-meta-zenith; ecosystem-mining/ | ● |
| [platform-facts/](external/platform-facts/README.md) — the vendor substrate: cache, windows, quota surfaces, credits. **Most volatile; recheck on schedule** | claude-code-and-max-plan-facts | ● |
| [isolation/](external/isolation/README.md) — sandboxing, deny rules, egress, per-role boundaries, documented escapes | isolation-and-sandboxing | ◐ |
| [routing/](external/routing/README.md) — model/effort selection, task-horizon and difficulty prediction | task-horizon-prediction | ◐ |
| [unattended-operation/](external/unattended-operation/README.md) — durable state, resume, pause/wake, liveness, supervision | unattended-operation-prior-art | ◐ |
| [tool-surface/](external/tool-surface/README.md) — interface ergonomics, MCP-vs-CLI, deferred loading, serialization formats | tool-surface-and-format-economics | ◐ |
| [evaluation/](external/evaluation/README.md) — measuring the machinery itself: paired-arm methodology, variance-aware gates | harness-evaluation-prior-art | ◐ |
| [memory-and-context/](external/memory-and-context/README.md) — persistent memory, lessons, context engineering, staleness, memory security | memory-architectures-and-benchmarks; memory-for-coding-harnesses | ● |
| [planning/](external/planning/README.md) — spec elicitation, determinacy, decomposition quality, plan evaluation, re-planning, brownfield | planning-and-decomposition-evidence; spec-determinacy-and-practice; elicitation-protocol-evidence | ● |
| [orchestration/](external/orchestration/README.md) — topologies, parallel implementation, handoffs, concurrency correctness | multi-agent-orchestration-evidence; concurrency-and-merge-correctness | ● |
| [human-in-the-loop/](external/human-in-the-loop/README.md) — ratification UX, adjudication latency, approval fatigue, escalation policy, safe autonomy reduction | oversight-and-vigilance-evidence; ratification-and-escalation-design | ● |
| [failure-modes/](external/failure-modes/README.md) — root-cause attribution & effect sizes for long-horizon failure; the README-claims audit; per-claim verification record | root-causes-and-effect-sizes | ◐ |

**The sweep is complete.** As of 2026-07-10 all 14 original external subtopics carry a dedicated
document (five ● were long-standing; memory-and-context, planning, orchestration, and
human-in-the-loop went thin→rich across 2026-07-10; isolation, routing, unattended-operation,
tool-surface, and evaluation remain ◐ moderate). A fifteenth subtopic,
[failure-modes/](external/failure-modes/README.md), entered 2026-07-14 via the
failure-attribution pass. The corpus is now a mapped design space rather than a record of what
was researched first; the remaining ◐ folders are the natural depth targets, and each rich
folder's README carries its own measured open questions.

### Internal — evidence we generated ourselves

Our own runs. Reproducible, and motivated: we want this design to work. Weigh the **defects**
heavily (an admission against interest — existence-strength, per the grading method) and the
**wins** lightly.

- [pilot-1-observations.md](internal/pilot-1-observations.md) — live triage ledger of the first real
  firing's failures and friction (started 2026-07-04); the empirical feed for the
  pilot-#2 amendments.
- [pilot-2-observations.md](internal/pilot-2-observations.md) — the second firing on the frozen
  greenlane instrument: 16 ledger entries, 9 of which became machinery fixes; the P2-collision
  incident; the first live proof that the held-out corpus catches what visible tests and blind
  validators both miss. Terminated by design once the arm was confounded.
- [pilot-3-observations.md](internal/pilot-3-observations.md) — the floors×profiles halt, the
  headless-worker (I26) shakedown, and the quota-wall leg; source of I19–I30.
- [pilot-2-artifacts/](internal/pilot-2-artifacts/) — raw committed telemetry from pilot #2:
  `run-log.jsonl`, `ledger-events.jsonl`, `governor-log.jsonl`, verdicts, watch items. The
  artifacts that make the pilot ledgers checkable rather than merely asserted.
- [model-speed-effort-benchmark-2026-07/](internal/model-speed-effort-benchmark-2026-07/README.md) —
  `[measured, local]` benchmark (2026-07-05, 73 timed `claude -p` runs) of Fable 5 / Opus 4.8 /
  Sonnet 5 / Haiku 4.5: latency, throughput, token-spend variance, correctness, and relative
  cost per solved coding task at xhigh effort; raw per-run JSONs and reproduction harness
  included. Headline: correctness is saturated at prompt-scale coding; speed ranking inverts
  between thinking-heavy (Fable fastest) and tool-loop (Sonnet/Haiku fastest) regimes; token
  efficiency offsets most of the Fable/Opus per-token price premium.

Three external documents are **mixed-provenance** — they carry internally-generated claims
inside an external survey, tagged `[measured, local]`, `[in-tree]`, or `[operator-observed]`:
`landscape-and-novelty.md` §4 (in-tree verification of our own working tree),
`token-economics-and-scheduling.md` §2b/§2c (local supersessions; the Fable weekly-cap
observation), and `tool-surface-and-format-economics.md` §4.3 (local tokenizer measurements).
Those claims keep their tags in place, and are collected in
[distilled/internal.md](distilled/internal.md), so nothing is lost to the directory split.

### Distilled — the reliable subset

- [distilled/README.md](distilled/README.md) — **the grading method.** Why `[official]` is not a
  synonym for "true" (we have caught it wrong three times), why an admission against interest
  beats a benchmark, and the two axes — **warrant × decay** — every fact is scored on.
- [distilled/external.md](distilled/external.md) — Tier-A facts from the world: the mathematics,
  the gaming ledger, the independently replicated findings, the official commitments, and an
  explicit list of what to distrust.
- [distilled/internal.md](distilled/internal.md) — Tier-A facts from our own runs: every
  prediction our firings falsified, every defect we found in our own machinery, and an honest
  grading of our wins by whether a committed artifact backs them.

## How this maps to the design doc

**2026-07-10:** a from-scratch, evidence-first successor design-plan now exists at
[../design/evidence-based-harness.md](../design/evidence-based-harness.md) — every decision in it
cites [distilled/](distilled/README.md) directly, and it disregards all prior design decisions by
construction. The table below maps the corpus to the *previous* design
([token-time-optimized-harness.md](../attic/token-time-optimized-harness.md), kept as history).

| Design section | Backing research |
|---|---|
| §2 objective function; §7 correctness floor | correctness-and-verification-evidence; landscape-and-novelty |
| §5.1 budget governor; §6 wall-clock & parallelism | token-economics-and-scheduling; claude-code-and-max-plan-facts |
| §5.2 cache discipline; §10 Max-window facts | claude-code-and-max-plan-facts |
| §5.3 model/effort routing | token-economics-and-scheduling (incl. §2b local supersessions); model-speed-effort-benchmark-2026-07; task-horizon-prediction |
| §5.5 re-validation reuse / vault | revalidation-reuse-and-leakage (economics); isolation-and-sandboxing (secrecy) |
| §4 leverage map; §8 controller; whole-design novelty | landscape-and-novelty |
| §4 skills/ToolSearch rows; §5.4 context hygiene; §6.1 turn accelerators | tool-surface-and-format-economics |
| §3.4 disk-is-memory; §6.3 human latency; §9 failure modes | unattended-operation-prior-art |
| §5.6 no-spend list; §7 self-measuring loop; §8 lever discipline | harness-evaluation-prior-art |
| §8 self-modification governance; §7 hooks-over-prose; whole-design novelty (update) | meta-harness-and-self-improving-harnesses (gaming ledger, promotion rule, novelty re-assessment) |
| §7 closure/stopping; §11 staging vs shipped neighbors | zenith-and-meta-zenith (terminal-reviewer lens, RALPH ablation); meta-harness-and-self-improving-harnesses §5 (RE-Bench) |

## Consolidated corrections & confidence ledger

Corrections produced by the fact-check passes, kept so future readers don't re-import the errors:

- arXiv **2502.08788**'s real title is "Stop Overvaluing Multi-Agent Debate — We Must Rethink
  Evaluation and Embrace Model Heterogeneity" (not "If Multi-Agent Debate is the Answer…", a
  different paper).
- Meta's mutation paper (**2501.12862**) reports **~9,095 mutants**, not ~4,660.
- **R2-Reasoner**'s primary source is arXiv **2506.05901** (WWW 2026); the routing survey
  2603.04445 was the fetched intermediary that reported its figure.
- Devin's "confidence-score gate" / DAG re-planning: third-party only; **not confirmed** on
  Cognition's own sources.
- Kiro "runs tests and verifies between each sequential task": **not confirmed** on any primary
  kiro.dev page (hooks *can* fire before/after task execution; built-in inter-task verification
  is not documented).
- The original Claude Code best-practices post (Apr 2025) was rewritten; the verbatim
  "think/ultrathink" ladder, the numbered 5-step TDD block, and "markdown file or GitHub issue"
  line are original-post wording, corroborated via mirrors, not re-fetchable.
- **Corrected 2026-07-04:** the design's §5.2 cache-TTL model (5-min default + `ENABLE_PROMPT_CACHING_1H`
  opt-in) is **stale** — subscription auth gets the 1-hour TTL automatically and loses it on
  usage credits; the §11 Stage-3 `ENABLE_PROMPT_CACHING_1H` item is obsolete on-plan.
- **Reframed 2026-07-04:** the design's "~75% cost cut from routing" is best-case on
  knowledge/chat benchmarks; coding/correctness-graded work sits at ~30–56%.
- **Unfused 2026-07-04:** the "90% time reduction at ~15× tokens" citation combines two separate
  Anthropic measurements (parallelism time-cut; token multiplier vs chat baseline).
- **Corrected 2026-07-04 (live probe, Claude Code 2.1.45):** the design's §5.3 claim "invalid
  ids fail loud" for the Workflow spawn path's per-agent `model`/`effort` overrides does **not**
  hold as stated — an invalid `effort` string is silently accepted (no error), and an invalid
  `model` id fails only as an async `null` result + workflow-level log entry, not a catchable
  throw. See `tools/budget-governor/probe-spawn-portability-2026-07-04.md` for the full
  methodology and re-verification protocol; the harness's spawn code must validate `(model,
  effort)` itself rather than trusting the primitive to reject bad config.

- **Superseded 2026-07-05 (local benchmark, adaptive-thinking lineup only):** the §5.3
  effort guidance "always-high overthinks trivial inputs (+1,953%)" no longer binds on
  Fable 5 / Opus 4.8 / Sonnet 5 — adaptive thinking self-adjusts at fixed `xhigh` (easy
  tasks cost the same at every effort). "Always-low drops success" still holds. Uniform
  `xhigh` is the new default; `max` is the escalation rung. Haiku 4.5 has no effort
  control at all (API rejects; CLI silently ignores).
- **Refined 2026-07-05:** I12's "smaller models are faster" wall-clock rationale holds
  only in the tool-loop regime; on thinking-heavy tasks the ranking inverts (Fable
  fastest, Haiku slowest) and Opus costs ≈Sonnet per solved task. Routing is
  regime-aware from I18 onward.
- **Refined 2026-07-09 (meta-harness pass):** the landscape doc's "self-measuring verifier
  ahead of the published literature" claim is narrowed — **Self-Harness (arXiv 2606.09498,
  Jun 2026)** publishes a proposer-blind held-out promotion gate for harness
  self-modification, and its verifier-grounded weakness mining is a published analog of the
  escapes-log idea. Surviving distinctions, re-verified across ~40 additional sources:
  per-task blind held-out validation of *implementation* work, **calibration canaries**
  (still nowhere in the literature), and **human-ratified self-modification** (every
  published loop accepts autonomously; DGM's detection-marker hack — caught only by
  retrospective human lineage review — is the canonical argument for prospective
  ratification). See meta-harness-and-self-improving-harnesses.md §6.
- **Attribution (2026-07-09), so nobody re-imports the error:** *Autodata* = Kulikov et al.
  2606.25996 (agentic data-scientist, Meta/FAIR); *Self-Harness* = Zhang et al. 2606.09498;
  *Meta-Harness* = Lee et al. 2603.28052. An early working guess mapped Kulikov→Self-Harness;
  Weng's post labels them correctly.
- **Verified 2026-07-09:** Zenith's "#1 on Frontier SWE" and II-Agent's "75.57% GAIA" are
  **self-administered first-party runs absent from the independent leaderboards** (official
  FrontierSWE: Fable 5 first at 0.900, Zenith unlisted; HAL GAIA: top entry 74.55%,
  II-Agent unlisted). The RALPH-ablation numbers are author-run, ~n=1 per cell. Mechanisms
  are importable; effect sizes are not.
- **Corrected 2026-07-12 (found by independent critical review; against interest):** the local
  speed/effort benchmark's committed `grade.py` could never have produced its GEN "solved"
  column — it hardcoded a 17-test total against the 16-test hidden suite (`passed == total`
  unreachable) and globbed a results layout that doesn't exist in the tree; how the original
  36/36 was tallied is not recoverable. Corrected graders re-derive **GEN 12/12 (16/16 each)
  and HARD 12/12 (36/36 each)** from the committed JSONs — those rows keep A3 — but **FIX
  correctness (12 runs) is permanently unverifiable** (`ws_fix_*` workspaces never committed):
  demoted to a single-source run-day observation, which also weakens FIX's cost-per-solved
  column. Quote the headline as "24/24 re-verified; 12 FIX observed on run day, no longer
  checkable," never as "36/36." Latency/token/cost rows unaffected (CLI-emitted JSONs). Regrade
  transcript: `internal/model-speed-effort-benchmark-2026-07/results/regrade-2026-07-12.txt`.
- **Reframed 2026-07-12 (same review, phases 2–3), so nobody re-imports the overstatements:**
  (1) the grading method's summary line ("Tier A only if it scores well on all three") and its
  warrant table ("any one suffices") were contradictory — resolved: any one warrant letter
  suffices for provenance, decay must be in-date, and two new *fit checks* (measured-regime,
  setting-transport) govern use in design decisions; (2) "believe it completely" for
  admissions against interest is bounded to **existence strength** — A2 never carries rate,
  cause, or magnitude; (3) A3 now requires the reproduction path to have been **executed**, not
  read (maintenance rule 5 — the grader correction above is the standing example); (4) the
  absence rule gains the inference bound: absence licenses "unoccupied niche," never "cheap or
  valuable" (struck the design's wake-on-reset "is cheap; build it"); (5) design-doc claims
  sample-bounded or narrowed: the §2.2 gaming ledger is a curated sample not a census, M7's
  acyclicity is *a* decidable restriction not *the* precondition, M1/M2 reuse budgets hold for
  their feedback regimes only (the v1 policy stays inside them by the attempt cap; **T12**
  guards any change past it); (6) status refinements in the design doc's fourth amendment:
  D2 spec-only authorship, D4 concurrent-write harm magnitude, D8 commit-before-reveal effect
  size, D12 append-only-under-R1 and wake-on-reset — all → Provisional with named triggers;
  (7) the P3v2-5 thesis is **n=2 existence** (smoke run 2 fired it live on an isolation
  regression), neither instance with a complete preserved failure-side chain, still not a rate.

- **From the 2026-07-14 failure-attribution pass** (details in
  [external/failure-modes/root-causes-and-effect-sizes.md](external/failure-modes/root-causes-and-effect-sizes.md)
  §6), five widely-quotable numbers to not re-import: (1) **Ambig-SWE (2502.13069)**
  per-condition digits "17.0%/21.4%" appear nowhere in the paper — Full/Hidden values live
  only in the Fig.-3 bar chart; quote the band (~40%→~20%) or SWE-Bench Pro's replicated
  drops; (2) OpenAI's SWE-bench-Verified doubling (16%→33.2%) supports "the original
  benchmark understated resolve rate ~2×," **not** "half of apparent failures were
  artifacts" (only ~20% of the original failure mass reclassifies, and Verified skews
  easier); (3) **METR 2503.14499**: the success-vs-log-length aggregate fit is exponential
  **R²≈0.83** (not 0.80) — distinct from the R²≈0.98 exponential *horizon-vs-calendar-date*
  trend (and the pass's own draft briefly glossed the fit "logistic," wrong against the
  verbatim source — caught before import); (4) **self-conditioning (2509.09677) Fig. 5**
  has no 20% induced-error point (grid 0/.25/.5/.75/1.0), and ~90%-at-0% is Gemma-27B, not
  Qwen3-32B; (5) **MAST (2503.13657)** inter-agent misalignment is version-unstable across
  restatements (31.3/32.3/36.9/38.4; v2-text read 36.94%) — cite the ranking
  (second-largest), never a point value.

**Absence-of-feature findings** (strong, but inherently harder to prove than a positive): Kiro
closure gate; Spec Kit automated final gate; LangGraph built-in critic; any published
mutation-canary-calibration of an LLM review panel; a dedicated Claude Code quota CLI (issue
#13585 still open); an official statement on 5-hour-window anchoring or cache-read subscription
weighting.

**Refuted by the 2026-07-04 verify panel (1-2 vote):** "two-model cascades capture all the value
/ a many-rung tier ladder adds nothing" — evidence weak both ways; do not collapse the §5.3
ladder on this basis.

**From the 2026-07-04 independent-confirmation pass** (kunchenguid claims vs independent
sources; details in [tool-surface-and-format-economics.md](external/tool-surface/tool-surface-and-format-economics.md)
and [harness-evaluation-prior-art.md](external/evaluation/harness-evaluation-prior-art.md)):

- **TOON token savings on uniform tabular data:** replicated, but as a **20–40% band vs compact
  JSON**, tokenizer/shape-dependent (author's −37% is the optimistic end); loses to compact
  JSON off-uniform (replicated + reproduced locally on this harness's own shapes); CSV smaller
  than TOON (replicated).
- **TOON read-accuracy "neutral or better":** `[contested, leaning negative]` — zero
  independent confirmations, three independent contradictions (−5 to −9pp), all in the
  small-model regime where the author claimed the edge. Markdown-KV/Markdown-Table beat TOON
  on the accuracy/token Pareto frontier in the only 12-format test.
- **TOON generation reliability:** `[measured, negative]` — one-shot 50% vs JSON 75% across 21
  models; parallel tool calls collapse in non-JSON formats. Never for model-generated output.
- **MCP schema tax (tens of K tokens per large server):** upgraded to `[measured, replicated]`
  (4+ independent measurements incl. GitHub's own changelog and Anthropic's posts).
- **"Hand-crafted CLI beats MCP on success":** `[measured, single-source, contested]` — the
  only other controlled head-to-head (Smithery n=756) found native MCP winning vs an
  *auto-generated* CLI (91.7% vs 83.3%, CLI 2.9× tokens); the hand-crafted cell is measured
  only by axi. The replicated meta-finding: **interface ergonomics dominates transport choice**.
- **Deferred tool loading:** the axi "net negative" finding and Anthropic's Tool Search gains
  are **different regimes, both real** — defer when catalog ≫10K tokens and the hot set is a
  small fraction; eager/pin the hot set when a worker uses most of its tools (Anthropic's own
  docs state this boundary).
- **Claude Code skill under-invocation:** direction `[measured, corroborated]` (Anthropic's own
  trigger-quality admissions; ~15k-char silent skill-list budget; independent ~45–50%
  activation measurement); the exact recall figures are n=1. "Codex over-invokes" is contested
  (SkillsBench found the opposite).
- **Process-ceremony harm (mandated TDD −3.6pp at +55% cost):** existence claim
  `[measured, corroborated]` (independent analogue: null outcomes at higher cost; overfitting-
  to-self-authored-tests mechanism independently established, 21.8–33% visible-pass-hidden-fail),
  **not a universal law** — provided ground-truth tests/plans help weaker models on
  function-level tasks. Moderators: who authors the tests, hidden-vs-visible grading, task
  scale, model era. The harmful regime is exactly what the design's blind held-out vault removes.
- **Agent self-reports unreliable ("claims, not evidence"):** `[measured, replicated]` (METR
  ≥16% cheating on successful 8h+ runs; Transluce o3 fabrication elicitation).

**From the 2026-07-04 critique-refresh pass** (details in
[correctness-and-verification-evidence.md §3 addendum, §7](external/validation/correctness-and-verification-evidence.md)
and [landscape-and-novelty.md §4](external/landscape/landscape-and-novelty.md)):

- **Cross-model error correlation:** two independent academic sources (arXiv 2506.07962, 350+
  models, ~60% same-wrong-answer agreement when both err, correlation rises with capability and
  crosses providers; arXiv 2502.04313, judges favor similar models) — direction
  `[measured, replicated]`.
- **False-FAIL base rates:** Refute-or-Promote (arXiv 2604.19049) kill-rate magnitudes (~79–83%)
  are `[measured, single-source]` — methodology paper, self-reported; the
  unanimous-nonexistent-vuln incident is an existence claim `[E]`. Spec-alignment misjudgment
  (arXiv 2603.25773) is single-author, **direction only** — do not import its numbers. The curl
  bug-bounty closure is `[reported]`, cited for ecosystem framing only.
- **In-tree verification (2026-07-04, 358 tests passing):** no hook registration anywhere;
  closure gate lacked a Stop-hook stdin interface; `run_gate` passes absent inputs as "caller's
  choice"; governor has no reading-staleness handling; gate spills full held-out output to
  in-repo evidence dirs. These are working-tree facts, not external research — recorded here
  because the §4 critique and design amendments lean on them.

- **Corrected 2026-07-14 (independent repo critique):** several surfaces overstated their
  warrant; caught and fixed:
  - **Decomposition status.** The "bound the horizon" decision claimed the short-fresh-gated
    *shape* was evidence-forced. Corrected: the per-link gate is Decided; that short links beat
    one long thinking session is an **untested bet** — the long-horizon value experiment holds
    decomposition fixed and tests only the gating half. The self-conditioning source (2509.09677)
    also finds *thinking* mitigates the effect and enables longer single-turn runs — omitted
    before, now on the §3.1 row.
  - **Cache-weight bound.** `w < 0.1125` assumes the pre-registered cache-write weight **v ≥ 1**;
    at v=0 the same censored-meter logic gives **w < 0.1775 (≈5.6×)**. "Point estimate 0" is a
    censored-meter floor (`ΔA ∈ [0,1)`), consistent with any w in [0, bound), not a separately
    identified zero. The directional finding (reads far cheaper) is unchanged.
  - **M7 (HTN undecidability)** was cited as *the* precondition for plan preflight; it is a
    motivating analogy only — the preflight is finite-graph cycle detection (trivially decidable),
    and the acyclicity requirement rests on plain graph theory. (The 2026-07-12 design-doc
    narrowing had not reached `external.md`; now propagated.)
  - **"Permanent math" section.** M3's ~84% and M4's ~27% are empirical measurements with decay,
    not permanent theorems; flagged in place, in `external.md` and the grading method.
  - **"20 primary sources"** (failure-attribution pass) overstated the enumerated **15** — it is
    20 primary-source *claims* over 15 primaries fetched; corrected in the design doc.
  - **Stale status labels** corrected: README's "stamp over the plan's hash" (the stamp is
    `{by, ts}`; the content hash lives in the exec-loop at launch); the operator-walkthrough's
    "Decided, non-negotiable" spec-only authorship (Provisional) and "Decided and cheap"
    wake-on-reset ("cheap" struck); `terminology.md` naming the attic as the current authority;
    the `codex_p` smoke's "PENDING" header (certified end-to-end 2026-07-13).

**Hype-tier, cite for framing only:** Ralph-loop cost anecdotes ($297 MVP); the "100k sessions →
dumb zone" statistic; Palisade's o3-86% chess figure; vendor SWE-bench scaffold-jump percentages;
the TrueFoundry 10× caching case study (single unaudited vendor anecdote, gateway semantic caching
≠ Anthropic prompt caching).

## Open items still unresolved

- **Cache-read subscription-limit weighting** — officially unanswered (re-verified 2026-07-04
  evening: #24147 still has no maintainer response; new indirect signal — `/usage` limit
  attribution itemizes cache *misses*, implying hits are discounted, weight unstated); settle
  with the design's §12 controlled measurement (now the highest-value experiment).
- **Headless quota surface** — re-verified 2026-07-04 evening: #13585 open (zero maintainer
  responses through v2.1.201), OTEL consumption-only. Design §12 Q1 now tracks *which fallback
  to wire* (statusline-dump shim > OAuth endpoint > estimate), not whether a surface exists.
- **Agent-teams ~7× multiplier** — not re-verified in the 2026-07-04 pass; rests on the earlier
  official-docs inventory.
- **Official confirmation of 5-hour-window anchoring** — still only `[measured]`/practitioner.
- **`StopFailure` / `rate_limit` hook matcher** — single vendor-blog source; verify before
  relying.
- **Duration-bucket predictor features** — must be validated against measured burn before the
  §11 flag flips (human difficulty ratings only weakly track cost).
- **Independent replication of the 2026-07-09 pass's single-source results** — Zenith's
  RALPH-ablation + FrontierSWE self-run; Self-Harness and DGM headline numbers. Import the
  mechanisms (two-split promotion rule, terminal-reviewer lens, weakness mining), not the
  effect sizes, until replicated.
- **Meta-Zenith and Meta-Harness code** — both closed/unreleased as of 2026-07-09; if either
  ships, re-study as the base for any harness-variant search (task-family harness
  generation; Pareto retention + leakage audits).

## Recheck schedule (these facts rot)

- Recalibrate window ceilings after **2026-07-13** (+50% weekly promo expiry).
- Re-check the **paused Agent SDK plan change** (would move headless usage off rate windows onto
  a monthly dollar credit — see claude-code-and-max-plan-facts §6).
- Re-verify any capacity magnitude after each Anthropic limit change; nothing is hard-coded.
- Watch for third-party evaluations/reproductions of Zenith (none existed 2026-07-09) and for
  a Meta-Zenith or Meta-Harness code release — either changes the §12 task-conditional
  harness-configuration picture.
- **ENPIRE code release** (promised as of Jun 2026) — on arrival, audit reward-synthesis +
  Stage-2 logs; and re-pull AlphaEvolve's live `status.json` before citing any "current
  record" (both tracked in
  [external/self-improvement/auto-research-systems-2026-07.md](external/self-improvement/auto-research-systems-2026-07.md)).
