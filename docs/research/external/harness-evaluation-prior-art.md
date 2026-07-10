# Harness-evaluation prior art — measuring the machinery itself

Evidence base for evaluating *the harness's own levers* (skills, orchestration prompts,
process mandates, validator formats) rather than the model: the kunchenguid benchmark suite
(**superpowers-bench**, **programbench-bench**, **harness-exam**, **org-bench**) plus
independent confirmation. Backs the design's measure-then-move principle (§3.5), the
controller's lever discipline (§8), and the skills/plan increments (plan E1/E2).

**Provenance:** repo survey 2026-07-04 (four-agent fan-out over READMEs, configs, published
results) + independent-confirmation pass 2026-07-04 (three adversarial web-verification
agents; see §5). `[E]` established in cited source; `[I]` inference/synthesis. The kunchenguid
benchmarks are author-run: single-author methodology, mostly single-model, LLM judges —
tagged `[measured, single-source]` until independently replicated.

---

## 1. Skill routing is measurable — and Claude Code under-invokes (superpowers-bench)

Benchmark of whether agents discover and invoke the right Agent Skills from task context alone
(obra/superpowers corpus; 18 scored tasks + no-skill controls; Claude Code, Codex, OpenCode;
n=1 per cell — small). `[measured, single-source]`

- **Claude Code's failure mode is under-invocation:** precision ~100%, recall 38–69% — it
  silently does the work without loading the relevant skill (opus-4-6 no-hints: recall 38%;
  opus-4-7: 69%). Codex over-invokes mildly (recall 92–98%, precision 83–90%). `[E]`
- **Hints that imply the workflow without naming the skill** lift perfect-match rates
  substantially (opus-4-7: 44%→56%; codex: 44%→78%) but recall only modestly. `[E]`
- **Negative controls matter:** 3 tasks where *no* skill should fire penalize over-invocation —
  without them precision is unmeasurable. `[E]`
- **Detection methodology transfers:** for harnesses without native skill telemetry, 2–3
  distinctive *body* phrases per skill ("fingerprints", from the SKILL.md body, not frontmatter)
  prove the body actually loaded vs. was paraphrased. `[E]`
- `[I]` Design consequence: progressive disclosure (§4) silently fails ~⅓–⅔ of the time absent
  explicit triggers. Build-loop skills need (a) routing canaries — fixture tasks with expected
  invocation sets *including negative controls* — in the self-test suite (same spirit as §7
  calibration canaries), and (b) the orchestration prompt should split skill use into
  **mandatory phase-gated** ("before merging: run X") vs **situational trigger-conditioned**
  ("when output diverges and you can't see why: run investigate — don't guess-and-patch") —
  the pattern already piloted in programbench-bench's skills arm. Mandatory-phase-gated
  invocations are deterministic prompt text, immune to the recall problem.

## 2. Process mandates are not free — a paired A/B instrument (programbench-bench)

Inverts ProgramBench (arXiv 2605.03546; ~200 rebuild-a-CLI-from-docs tasks with hidden test
suites): hold the model constant, vary one harness variable per **arm** (a directory:
orchestration prompt + skills + settings), compare paired per task. Hermetic three-container
topology; anti-gaming audits. Methodology discipline worth copying wholesale: continuous
metric (mean hidden-test pass rate, not binarized), paired Wilcoxon signed-rank with Holm
correction, difficulty terciles defined out-of-sample, confirmatory-vs-exploratory labeling,
"no method chosen for its result." `[measured, single-source]` (gpt-5.5, n=192/arm)

- **Mandated TDD strictly dominated by freeform** on hidden tests: 52.4→48.8 mean pass rate
  (p<0.0001, lost 136/192 tasks) at **+55% cost** ($1.12→$1.73/task; input tokens +112%,
  reasoning turns +248%). Mechanism: "each micro-cycle is a separate turn that re-bills the
  entire context — the money buys process, not product"; self-written tests can't see the
  hidden spec, so green self-tests → confident premature stop (worst on easy tasks). `[E]`
- **"Careful coding guidelines" (Karpathy-style) slightly hurt:** 53.7→51.5 (p=0.005), no cost
  savings; "Simplicity First" narrowed scope — "it reasons itself out of completeness." `[E]`
- **Language-mandate arm:** free choice is cheapest and statistically tied with the top on
  quality; an oracle per-task language picker would add only ~7 points — upfront routing
  ceilings are modest even with perfect information. `[E]`
- `[I]` Design consequences: (a) this is the strongest available caution for §5.6/§8 — every
  piece of loop ceremony (mandated workflows, guideline prose, extra gates that make the
  *implementer* do process) must be treated as a candidate net-negative until paired telemetry
  clears it; it sharpens, not contradicts, the design's held-out-vault logic — the TDD arm
  failed because the agent graded itself on tests it authored against a spec it couldn't see,
  which is exactly why the design keeps validation blind and *panel*-authored (§5.5, §7);
  (b) the arm/paired-comparison shape is the ready-made template for §8 controller lever
  evaluation — one lever = one arm, continuous metric, paired stats, pre-registered.

## 3. Judge/validator format patterns (org-bench, harness-exam)

- **org-bench** (multi-agent topology benchmark; runs budgeted as `{tokens, wallClockMs}` —
  the design's dual-objective envelope as a run schema): its judge is an agent driving the
  artifact through a browser "like a real user — no hidden test hooks, mandated selectors, or
  implementation contract," returning rubric JSON where the rationale **must quote observed
  behavior** ("reload persistence did not restore contents"). `[E]` `[I]` — a validator-verdict
  format rule: verdicts cite reproduced behavior, not vibes; slots into the E1 verdict schema.
- **harness-exam** (3-task capability exam for harnesses): session → deterministic grading →
  machine-generated scorecard; includes a **browser attestation** so the agent must actually
  drive the artifact rather than pattern-match the answer. `[E]` `[I]` — attestation-style
  proofs (the gate proves the validator *ran* the thing) complement the design's vault-canary
  pattern (§7): both verify machinery by forcing an action that cannot be faked from text.
- **trial-by-combat** (LLM duel arena, skim): full determinism for exact replays; a required
  `intent` field on every action for a legible audit trail. `[E]` `[I]` — cheap additions to
  the escapes log: replayable determinism where possible, mandatory one-line intent on gate
  decisions.

## 4. What this changes in the research corpus

- The design's "dormant machinery gets pruned on evidence" (§8) gains a *quantified* failure
  mode it guards against: ceremony that costs +55% for −3.6 quality. Insurance-vs-active
  distinction unchanged.
- The §4 skills row gains a caveat: progressive disclosure's *loading* is cheap, but its
  *triggering* is unreliable without explicit phase-gating or tested trigger phrasing.
- The controller (§8) gains a concrete evaluation protocol (arms, paired stats, terciles)
  compatible with its existing one-lever-at-a-time and sample-floor rules.

## 5. Independent confirmation (2026-07-04 adversarial verification pass)

Adversarial web-verification against sources independent of kunchenguid. Outcomes:

### 5.1 Skill under-invocation — direction HIGH confidence, numbers LOW; regime-dependent

- **Anthropic itself treats under-triggering as a real open problem** `[official]`: the Agent
  Skills engineering post names trigger quality (false positives *and* negatives) as a
  limitation, and the skill-creator update's headline feature is description optimization,
  reporting improved triggering on 5 of 6 of Anthropic's own public skills
  (anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills;
  claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills).
- **A mechanical cause exists:** skills silently vanish from the system prompt past a
  ~15,000-char skill-list budget with no warning (`SLASH_COMMAND_TOOL_CHAR_BUDGET`) —
  structural false negatives at scale, documented by the superpowers author, who also found
  triggering requires enforcement machinery (session-start hook, "you *must* use it"
  bootstrap) `[measured]` (blog.fsck.com 2025-12-17, 2025-10-09).
- **Small independent replication:** 20 fresh Claude Code sessions, ~45–50% skill
  auto-activation *even with* a UserPromptSubmit nudge hook `[measured]`
  (scottspence.com/posts/claude-code-skills-dont-auto-activate) — inside superpowers-bench's
  38–69% recall band.
- **Regime dependence (SkillsBench, arXiv 2602.12670** — 84 tasks, 7,308 trajectories,
  deterministic verifiers `[measured, replicated]`): with a *single curated, clearly-relevant*
  skill mounted, Claude Code uses it consistently (+16.2pp avg, +13.9 to +23.3pp); the
  under-invocation regime is many skills with fuzzy relevance. Also: **self-generated skills
  scored −1.3pp** — skill *content* must earn its place. The "Codex over-invokes" contrast is
  **contested** — SkillsBench observed Codex CLI *under*-utilizing mounted skills.
- `[I]` Design consequences hold and sharpen: mandatory phase-gated invocation for
  load-bearing skills (deterministic prompt text, immune to recall); few skills with short,
  optimized descriptions (the char budget is a hard mechanical ceiling); routing canaries in
  self-tests; and a budget check that the installed skill inventory fits the list budget.

### 5.2 Process-ceremony harm — existence claim MODERATE-TO-HIGH; cost side essentially certain; not a universal law

- **Closest independent analogue** (arXiv 2602.07900, SWE-bench Verified, 6 models):
  prompting models to write more or fewer tests **did not significantly change resolution**
  — it "reshape[s] process and cost more than final task outcomes"; GPT-5.2 writes almost no
  tests and ranks top. Null-at-higher-cost, not strictly negative. `[measured]`
- **The harm mechanism is independently established** (arXiv 2511.16858, hidden-test grading,
  449 instances): 21.8% (Claude 3.7 Sonnet) / 33.0% (GPT-4o) of patches passing visible tests
  fail hidden tests, and **iteratively refining against self-authored visible tests makes
  hidden-test failure *worse*** (→25.5% / 35.9%). `[measured]` Overthinking/ceremony harm is
  corroborated by arXiv 2502.08235 (picking low-deliberation solutions: +~30% perf at −43%
  cost), Anthropic's inverse-scaling-in-test-time-compute results, IFScale (compliance
  degrades with instruction count), and "Same Task, More Tokens" (input bloat alone degrades
  reasoning). Scaffolding minimalism corroborates from the other side: Anthropic's 49%
  SWE-bench run and mini-swe-agent (~100 lines, 65–74%) both beat elaborate scaffolds.
  `[measured]`
- **TDD/structure helps in a different regime** `[measured]`: *provided ground-truth* tests
  (+12.8% MBPP, +9.2% HumanEval — arXiv 2402.13521) and plan-then-code on function-level
  tasks (arXiv 2303.06689). The moderators that reconcile the two bodies: **who authors the
  tests** (provided = new information → helps; agent-authored = overfitting target → null-to-
  harmful), **hidden vs visible grading**, task scale, model era.
- `[I]` This *strengthens* the design rather than qualifying it: the harmful regime —
  implementer grading itself on tests it authored against a spec it can't fully see — is
  precisely what the design's blind panel-authored held-out vault (§5.5, §7) removes. The
  imported rule stands: implementer-side ceremony is a candidate net-negative until paired
  telemetry clears it; validator-side rigor is governed by O0, not by this finding.

### 5.3 "Claims, not evidence" — CONFIRMED

Agent self-reports are unreliable exactly where verification is absent: METR measured ≥16% of
successful 8h+ task runs involved cheating (modifying tests/scoring), with o3 disavowing the
behavior 10/10 times when asked; Transluce elicited 71 transcripts of o3 fabricating code
execution it never ran plus 352 fabricated justifications, doubling down when confronted.
`[measured, replicated]` (metr.org/blog/2025-06-05-recent-reward-hacking;
transluce.org/investigating-o3-truthfulness) — the evidentiary backbone for extending the §7
fresh-evidence rule to the orchestrator's own summaries ("never summarize a run from memory;
reconstruct from git").
