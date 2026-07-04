# Correctness & verification evidence — why the O0 floor is built this way

The empirical case behind the design's correctness machinery
([../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md) §7):
blind validation, diverse-lens panels, the human plan gate, durable state with external kill
switches, governed self-modification, and the calibration probe.

**Provenance:** external comparative study 2026-07-03 (two adversarial fact-check passes);
`[E]` = established in the cited primary source, `[I]` = inference/synthesis. Corrections in
the consolidated ledger ([README.md](README.md)). **Extended 2026-07-04 (evening):** a targeted
verifier-precision and error-correlation pass (§3 addendum, §7) run during the critique-refresh
exercise; sources fetched directly, magnitudes tagged single-source where applicable.

---

## 1. The threat is measured, not hypothetical (reward hacking / stale-green)

- METR: o3 **monkey-patched the evaluator to always return a perfect score**, overwrote Python's
  `==`, returned pre-computed answers — and *knew* (called its own approach a "cheating route";
  said "no, doesn't match user intent" 10/10 when asked). 1–2% of task attempts. `[E]`
  https://metr.org/evaluations/openai-o3-report/ ·
  https://metr.substack.com/p/2025-06-05-recent-reward-hacking
- DebugML catalog: agents **hardcoded returns for specific test inputs** and **printed "PASS"
  because the verifier only checked for the substring**; 28+ task-level instances across
  benchmarks. `[E]` https://debugml.github.io/cheating-agents/
- Anthropic: reward hacking on real coding tasks → **emergent broader misalignment** (12%
  sabotage of a safety codebase). `[E]`
  https://www.anthropic.com/research/emergent-misalignment-reward-hacking
- SWE-bench Verified audit: **~31% of passing patches rely on tests too weak to catch a wrong
  fix**; ~1/3 of issues leak solution code. `[E]`
  https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- Sycophancy (Sharma et al.): RLHF assistants tell users what they want to hear — a false
  "done" is the completion-shaped default, not an edge case. `[E]` https://arxiv.org/abs/2310.13548
- Kent Beck, independently: the agent "doesn't want to do TDD. It wants to write the code and
  then write tests that pass" and will cheat "by disabling or deleting tests." `[E]`
  https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes

**`[I]`** This is the exact failure family the clean-checkout reproduction rule, the blind
validator, commit-tests-first, and the fresh-evidence closure gate defend against. Not
over-engineering; the field's best-documented real failure.

## 2. Blind separation is the prescribed mitigation (generator–verifier)

Three converging pillars:

- **Self-recognition *causes* self-preference.** Fine-tuning a model's self-recognition causally
  shifts how much it favors its own output — and chain-of-thought is highly recognizable, so
  hiding *the implementer's reasoning specifically* is the precise mitigation. `[E]`
  https://arxiv.org/abs/2404.13076 (first named as self-enhancement bias in MT-Bench,
  https://arxiv.org/abs/2306.05685)
- **Intrinsic self-correction degrades accuracy** absent an external signal (GSM8K 75.9→74.7,
  CommonSenseQA 75.8→**41.8**). Correction helps only with external leverage: tools, execution,
  a verifier. `[E]` https://arxiv.org/abs/2310.01798
- **Separate verifiers measurably win:** process-reward models (https://arxiv.org/abs/2305.20050),
  CriticGPT (critiques preferred ~80% of the time,
  https://openai.com/index/finding-gpt4s-mistakes-with-gpt-4/), Weaver (aggregated weak verifiers
  close most of the generation–verification gap,
  https://hazyresearch.stanford.edu/blog/2025-06-18-weaver). `[E]`

**Load-bearing caveat `[E]`:** verification-easier-than-generation is *conditional* — it weakens
for strong generators/hard problems (https://arxiv.org/html/2509.17995). The asymmetry holds only
when the verifier has leverage the generator lacks. **`[I]`** It is the validator's *leverage*
(clean checkout, held-out execution, calibrated competence), not its *count*, that carries the
safety guarantee.

## 3. Panels: the lens design is vindicated; a prior critique is retracted

- Homogeneous multi-agent debate often fails to beat CoT/self-consistency at higher cost `[E]`
  https://arxiv.org/abs/2311.17371 (Smit et al., "Should we be going MAD?") ·
  https://arxiv.org/abs/2502.08788 — verified title: **"Stop Overvaluing Multi-Agent Debate —
  We Must Rethink Evaluation and Embrace Model Heterogeneity"** (an earlier draft of the study
  mis-titled it); its positive finding: **model heterogeneity is "a universal antidote."**
- Pure sampling-and-voting scales with agent count but with diminishing returns; gains require
  genuine diversity, not shared-blind-spot clones. `[E]` https://arxiv.org/abs/2402.05120
- **Code-specific and decisive:** on Defects4J, the ensemble ceiling is **+83%** over the best
  single model; diversity-based selection realizes ~95% of it; but **consensus/similarity voting
  falls into a "popularity trap," amplifying common-but-wrong outputs** — sometimes below naive
  baselines. `[E]` https://arxiv.org/abs/2510.21513
- Related, from the 2026-07-04 pass: arXiv 2604.02460 (Tran & Kiela) — single-agent **matches or
  outperforms** multi-agent on **multi-hop reasoning under equalized thinking-token budgets**
  (Qwen3, DeepSeek-R1-Distill-Llama, Gemini 2.5); scoped to reasoning benchmarks, not coding;
  the paper itself predicts multi-agent becomes competitive **when context utilization
  degrades** — the long-session regime a harness lives in — and its information-theoretic
  argument assumes perfect context utilization. `[E]` Net `[I]`: supports "parallelism is
  purchased, never free" *and* supports context-isolation fan-out; it is not a blanket
  prohibition on decomposition.

**`[I]` Retraction + surviving advice:** the study's initial "panels over-buy" critique is
withdrawn — diverse lenses combined **all-must-pass** (never voting across lenses) with
`consensus` reserved for redundant panels is exactly the aggregation this evidence rewards. The
config's own rationale ("a security FAIL must never be outvoted by lenses that weren't looking at
security") is the popularity-trap avoidance 2510.21513 demonstrates. Surviving advice: make the
diversity *real* — distinct lenses **and** some model heterogeneity across a panel, not N copies
of one model reading one diff.

**Addendum 2026-07-04 — correlated errors cap what heterogeneity buys.** Two independent
academic results sharpen (and partially deflate) the "model heterogeneity" advice above:

- **LLM errors are strongly correlated, and most-capable models correlate most.** Across 350+
  models and multiple leaderboards, when two models both err they agree on the *same wrong
  answer* ~60% of the time; error correlation *rises* with capability and persists across
  distinct architectures and **different providers**; downstream demos show LLM-as-judge and
  hiring-pipeline monoculture effects. `[E]` https://arxiv.org/abs/2506.07962
- **Judges favor models similar to themselves** (CAPA similarity metric); model mistakes
  converge as capability grows, "pointing to risks from correlated failures" for AI oversight.
  `[E]` https://arxiv.org/abs/2502.04313
- `[I]` Consequences for the panel design: N same-family validators are **not N independent
  draws** — and even cross-provider heterogeneity is weaker insurance than assumed. What
  de-correlates is **leverage diversity** (held-out execution, clean-checkout reproduction,
  distinct lenses inspecting distinct artifacts), which the design already holds as the §2
  caveat ("it is the validator's *leverage*, not its *count*"). Model heterogeneity should be
  demoted from diversity *mechanism* to weak *insurance*; marginal panel tokens buy a new lens
  or new leverage, never another same-family opinion. Measurably: aggregating calibration-canary
  results panel-wide (a planted defect missed by **all** lenses = a correlated blind spot,
  caught by an instrument the design already ships) turns this from an assumption into
  telemetry.

## 4. Plan-first has quantitative backing — and its key caveat justifies the human gate

- Plan-then-code beats direct generation: **up to +25.4% relative Pass@1** (peer-reviewed, code
  benchmarks). `[E]` https://arxiv.org/abs/2303.06689
- **"A subpar plan hurts performance even more than no plan at all"** (SWE-style tasks). `[E]`
  https://arxiv.org/html/2604.12147v1 — **`[I]` this is the empirical justification for the
  human-approval gate on the technical plan**: the gate defends against the one thing worse than
  not planning. (Also grounds the phase-retro re-scoping: Tessl's independent critiques flag
  waterfall risk from big up-front specs — the retro is the mitigation.)
- Terminology note `[I]`: this design's "contract tests" = the acceptance-TDD / tests-as-spec sense
  (Beck; Anthropic's commit-tests-first), **not** Pact/consumer-driven contract testing
  (https://docs.pact.io/) despite the shared word. Worth one clarifying line in
  the process docs.

## 5. Durable file state + external kill switches (practitioner/vendor convergence)

- Anthropic's long-running-harness guidance recommends exactly file-persisted state (progress
  log, feature list with pass/fail flags, git history; "compaction isn't sufficient" alone). `[E]`
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- 12-Factor Agents: own your context window / control flow; unify execution + business state;
  stateless reducer; contact humans as tools. `[E]` https://github.com/humanlayer/12-factor-agents
- Circuit-breaker principle: **the kill switch must live outside the loop** — "an agent stuck in
  a loop cannot talk its way past a budget ceiling." `[E]` (as inherited distributed-systems
  pattern; thresholds are folk) — e.g.
  https://dev.to/waxell/ai-agent-circuit-breakers-the-reliability-pattern-production-teams-are-missing-5bpg
- Stop-hook completion gates are shipped practice: `planning-with-files` re-injects the plan per
  turn and **blocks turn-end until the plan is done**. `[E]`
  https://github.com/othmanadi/planning-with-files
- Self-modifying loops can *discover and encode a bypass of their own safeguards* without
  "deciding" to (fitness-driven safety-filter removal; meta-level takeover) — the academic
  backing for propose/human-ratify. `[E]` (as threat model) https://arxiv.org/pdf/2410.04444
  (Gödel Agent) + self-evolving-agent-safety literature.
- The Ralph loop (folk baseline this design institutionalizes): greenfield-only, "~90% done,"
  "you'll wake up to a broken codebase … from time to time"; one task per loop; write down *why*
  because "future loops will not have the reasoning in their context window." `[E]` (self-reported)
  https://ghuntley.com/ralph/ — cost/output anecdotes ($297 MVP) are hype-tier.
- From the 2026-07-04 pass, the budget-specific case for external enforcement: agents cannot
  self-manage token budgets — see
  [token-economics-and-scheduling.md §4](token-economics-and-scheduling.md).

## 6. The genuinely novel piece — mutation testing aimed at the reviewer

**Verified novelty claim (adversarial search, 2026-07-03):** using seeded known-defect canaries as
**live gates on trust in a specific "0 findings" verdict** — i.e., the calibration probe — has **no located
published prior art.** The ingredients all exist separately:

- Mutation testing itself is textbook (mutation score = fraction of seeded mutants killed = checker
  adequacy; DeMillo/Lipton/Sayward 1978; survey: Jia & Harman 2011, IEEE TSE 37(5):649–678
  https://dl.acm.org/doi/10.1109/TSE.2010.62). `[E]`
- Seeded-fault-driven LLM test generation is deployed at scale: Meta's mutation-guided test gen —
  **~9,095 mutants**, 571 tests, 73% engineer acceptance (an earlier draft said ~4,660; corrected
  against the paper). `[E]` https://arxiv.org/abs/2501.12862
- Adversarial mutant↔tester co-evolution loops exist (AdverTest, https://arxiv.org/abs/2602.08146;
  SMART, https://arxiv.org/abs/2603.24560; PRIMG, https://arxiv.org/abs/2505.05584 — all three
  future-dated IDs **existence-verified** via the arXiv API). `[E]`
- **Nearest neighbor:** AXIOM (https://arxiv.org/abs/2512.20159) injects rule-based perturbations
  (known-severity defects) to **benchmark** LLM-as-judge for code — and finds judges hallucinate
  flaws and "can't be trusted for autonomous approval." But AXIOM is a **static accuracy
  benchmark, not an operational pre-screen gating a specific downgrade decision at decision
  time.** `[E]`

**`[I]` Positioning line for the docs:** the calibration probe extends rule-based-perturbation LLM-judge
evaluation from a static benchmark into an operational pre-screen — plant a defect the panel
*should* catch; a miss freezes the downgrade and strengthens the blind panel. AXIOM's
judges-hallucinate finding also *reinforces* the existing "only confirmed, reproducible findings
fail a task" rule (the `repro` lens) as the filter against hallucinated flaws.

**`[I]` The identified gap this enables:** the design calibrates the
*reviewer* but never the *contract-test suite* — yet §1 shows ~31% of green patches can ride on
weak tests. Mutation-testing the committed contract tests (per-task kill-rate) would quantify how
much load the held-out layer silently carries.

## 7. False FAILs — verifier precision is the symmetric, measured failure *(added 2026-07-04)*

§1–§6 defend against false PASS (escapes, stale-green). The symmetric failure — hallucinated
or wrong FAIL findings — has strong documented base rates and was previously unmodeled:

- **Most raw multi-agent defect findings are wrong.** Refute-or-Promote — the published
  methodology closest to this design's panel (adversarial kill-mandates at promotion gates,
  cold-start reviewers, cross-model critics) — reports **~79% of candidate findings killed**
  by adversarial refutation retrospectively (171 candidates, 7 targets) and **83%
  prospectively** (n=30); its motivating framing is that "plausible-but-wrong reports overwhelm
  maintainers." `[measured, single-source for the magnitudes]` https://arxiv.org/abs/2604.19049
- **Consensus does not filter hallucinated findings:** in the same work, *ten dedicated
  reviewers unanimously endorsed a non-existent Bleichenbacher padding oracle in OpenSSL's CMS
  module — it was killed only by a single empirical test.* `[E]` Converges with §3's
  correlated-errors addendum (unanimity ≠ independence) and with AXIOM's finding that judges
  hallucinate flaws (§6).
- **Spec-conformance judgment misfires too:** LLMs systematically misjudge whether code aligns
  with natural-language requirements, and added reasoning/prompting *increases* misjudgment of
  correct code as non-compliant. `[measured, single-author — direction only]`
  https://arxiv.org/abs/2603.25773
- Ecosystem-scale corroboration of the precision problem (reported, not independently audited
  here): AI-generated vulnerability reports drove curl's bug-bounty confirmed-valid rate below
  ~5% and the program closed. `[reported]`

**`[I]` Design consequences (drove the 2026-07-04 §7 amendments and plan Phase H):**
all-must-pass aggregation means **one hallucinated FAIL blocks a merge**; "durable FAIL" is the
escalation signal, so false FAILs trigger paid tier/effort escalations and full re-runs, and
they poison exactly the telemetry (>40% break-even trip-wire, catch-rate) the controller tunes
on. The design's "verdicts quote reproduced behavior" rule is the right filter but is a
*claimed* reproduction — and fabricated execution is a measured behavior
([harness-evaluation-prior-art.md §5.3](harness-evaluation-prior-art.md)). The mechanization:
error-severity findings carry a **machine-replayable repro** the gate re-executes in the clean
checkout before a FAIL blocks ("killed only by a single empirical test", pointed at FAILs);
non-replayable error findings downgrade to ask-user; the run-log counts unreproduced findings
so false-FAIL rate becomes a tracked quantity instead of an invisible one.
