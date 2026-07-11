# Landscape & novelty — the design vs. the field (2024–2026)

How the harness design (specified in
[../attic/token-time-optimized-harness.md](../../../attic/token-time-optimized-harness.md))
compares to 20+ contemporary coding agents, multi-agent frameworks, the spec-driven movement,
and the strongest framework prior art — and what in it is genuinely novel.

**Provenance:** external comparative study, 2026-07-03 — four parallel research clusters
(autonomous coding agents; multi-agent orchestration; spec-driven/plan-first/TDD-for-agents;
agent-reliability + practitioner "folk loop" practice), each grounded in fetched primary
sources, followed by two adversarial fact-checking passes that verified every load-bearing
citation. `[E]` = established in the cited primary source; `[I]` = inference/synthesis.
Corrections produced by the fact-check passes live in the consolidated ledger
([README.md](../../README.md)). Empirical evidence for *why* the core choices are right is in
[correctness-and-verification-evidence.md](../validation/correctness-and-verification-evidence.md).

---

## Verdict (one paragraph)

This design is best understood as **Anthropic's own recommended agentic-coding workflow,
hardened into a governed, self-measuring harness.** Its durable novelty is *not* plan-first or
separate-evaluator — both are now vendor territory (Kiro, Spec Kit, Claude Code plan mode /
`/goal` / Stop hooks) — but the **governance and verifier-calibration layer** almost nothing
else builds: (1) a **blind adversarial validator** (fresh context, never sees the implementer's
reasoning, authors held-out tests, reproduces the gate from a clean checkout), and (2) a
**self-measuring verifier loop** (the escapes log as labeled ground truth + calibration-probe
known-defect canaries — the latter verified as *ahead of the published literature*, see
[correctness-and-verification-evidence.md §6](../validation/correctness-and-verification-evidence.md)), plus
(3) **human-ratified self-modification** with mechanized, diff-inspecting risk floors. Durable
resumable state and structural context isolation are real strengths with mature prior art
(LangGraph ships both mechanisms — but no critic). The two fixable risks: load-bearing safety
logic living as orchestrator *prose* rather than scripts/Stop-hooks, and a conceptual apparatus
that has outrun its single-worker realized scale.

## 1. The comparison matrix

Every row checked against primary sources. Lens = the design's four load-bearing ideas.

| Effort | Plan/execute split | Blind impl↔verifier | Verification model | Durable/resumable state | Governed self-mod |
|---|---|---|---|---|---|
| **This design** | Explicit 2-mode, phased ledgers + risk table | **Yes** — separate context, held-out tests | Clean-checkout gate + adversarial panel + **frozen closure gate** | Disk ledgers = **spec-contract & resume state in one** | Propose → **human ratifies**; mechanized risk floors |
| Kiro (AWS) | Strong: requirements→design→tasks (EARS) + approval gates | No — author = executor | Hooks; **no doc'd closure gate** vs original goal | `.kiro/specs/*` files | Steering files |
| GitHub Spec Kit | Strong: spec→plan→tasks→implement + constitution | No | Checklists/analyze; **no automated final gate** | Spec files in repo | Constitution |
| Claude Code (Anthropic) | Plan mode + SPEC.md → fresh session | Two-Claude writer/reviewer *suggested*, not enforced | Stop hooks + `/goal` (separate evaluator per turn) | Progress/plan files + git | Auto-mode classifier (not human-ratified) |
| Devin (Cognition) | Plan-before-execute + approval | No separate verifier | Self-codes-and-tests | VM snapshots + Knowledge | Persists "learnings" |
| Aider | architect/editor = plan/diff, **not verify** | No — two authoring roles | Auto-lint + auto-test repair loop | Repo map | — |
| Cline / Roo Code | Plan/Act; Roo Boomerang isolates subtasks | Role-specialized, not blind-adversarial | Diagnostics/test-output reaction | Shadow-git checkpoints | — |
| OpenAI Codex CLI/cloud | Plan mode; sandbox + approval policy | No | Self-run tests in sandbox | Cloud sandbox per task | — |
| SWE-agent | No — ReAct loop | No | Agent self-runs tests + linter guard | Ephemeral history | — |
| OpenHands | Delegation, not plan-first | Behavioral QA agent (sees prior work) | Self-run tests + QA agent | Replayable event stream | — |
| MetaGPT / ChatDev | Waterfall SOP roles | Roles hand off distilled outputs, not blind repro | QA/reviewer role sees prior solution | MetaGPT: disk serialize/resume | — |
| AutoGen / AG2 | Conversation-driven | **Shared thread** — no isolation | Optional same-thread critic | v0.4 `save_state`/`load_state` | — |
| CrewAI | Task/flow graph | Isolated contexts wired by explicit `context` edges | User-defined QA task | `@persist` checkpoints | — |
| LangGraph | Graph author decides | Subgraph namespace isolation — **no built-in critic** | Hand-built evaluator node | **Best-in-class**: checkpointers, time-travel, resume | — |
| Tessl | Spec-as-source (code = regenerable artifact) | No | Tests-as-guardrails on regeneration | Spec is the durable artifact | — |

Key primary sources per row: Kiro `[E]` https://kiro.dev/docs/specs/ (three files, EARS, approval
gates, Quick Plan bypass, "Run all Tasks" dependency waves; **no first-party doc describes an
end-of-run closure check against the original requirements**). Spec Kit `[E]`
https://github.com/github/spec-kit + https://github.com/github/spec-kit/blob/main/spec-driven.md
("the spec … becomes the source of truth"; completion via checklists + human review, **no machine
verdict**). Claude Code `[E]` https://code.claude.com/docs/en/best-practices (explore→plan→code→
commit; "have one Claude write tests, then another write code to pass them"; commit-tests-first
because "Claude will sometimes change tests to make them pass"; Stop hooks + `/goal`). Devin `[E]`
https://cognition.com/blog/introducing-devin (plan-first; no separate verifier; confidence-score
gating is third-party-only, unconfirmed). Aider `[E]` https://aider.chat/docs/usage/modes.html
(architect/editor = planner-vs-diffwriter) + /docs/usage/lint-test.html. Cline `[E]`
https://docs.cline.bot/features/plan-and-act (+ checkpoints, auto-approve, YOLO mode). Roo `[E]`
https://docs.roocode.com/features/boomerang-tasks ("Each subtask operates in complete isolation
with its own conversation history … returns only the summary"). SWE-agent `[E]`
https://arxiv.org/abs/2405.15793 (ACI; self-verification only). OpenHands `[E]`
https://arxiv.org/abs/2407.16741 + https://docs.openhands.dev (event stream; QA agent "actually
running the software," not blind). MetaGPT `[E]` https://arxiv.org/abs/2308.00352 (SOP
assembly-line; shared message pool with pub-sub; breakpoint recovery is a v0.6 implementation
feature). ChatDev `[E]` https://arxiv.org/abs/2307.07924 (chat chain; long-term memory passes
"solutions … rather than the entire communication history"; replay ≠ resume). AutoGen `[E]`
https://microsoft.github.io/autogen/0.2/docs/tutorial/conversation-patterns/ (manager
**broadcasts** to all agents — one shared thread). CrewAI `[E]` https://docs.crewai.com/en/concepts/tasks
(explicit per-task `context` edges; `@persist`). LangGraph — see §3. Tessl `[E]`
https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry/ + independent critique
https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (regeneration engine closed-beta,
non-deterministic, JS-only; company pivoted to "Agent Enablement" ~2026-01).

## 2. Novelty, honestly sorted

**Distinctive (no mainstream analog found):**

- **Blind adversarial validation.** A verifier that (i) is a separate agent, (ii) has a fresh
  context, (iii) never sees the generator's reasoning, and (iv) withholds an adversarial test
  set — appears in **no surveyed tool**. The field's verifiers see everything (MetaGPT QA,
  ChatDev reviewer, OpenHands QA, same-thread AutoGen critics). Anthropic's evaluator-optimizer
  (https://www.anthropic.com/engineering/building-effective-agents) and the two-Claude
  writer/reviewer suggestion are the nearest endorsements — *suggested, not enforced*. `[E]`
- **Self-measuring verifier** — the escapes log (a committed, labeled set of defects the panel
  missed = exactly how you'd empirically calibrate a checker) + calibration canaries. `[E]`
  for the components; `[I]`+verified-absence for the composition
  ([correctness-and-verification-evidence.md §6](../validation/correctness-and-verification-evidence.md)).
- **Human-ratified self-modification + mechanized risk floors.** A propose/dispose ratification
  queue + merge-gate risk-floor and machinery checks inspecting the **actual diff paths**
  at the merge point. No framework provides this governance layer; Claude Code's auto-mode
  classifier is the closest and is not human-ratified. `[E]` (absence-of-feature confirmations)

**Real, but with mature prior art:**

- **Durable resumable state.** LangGraph checkpointers are best-in-class (§3). The twist that
  stays distinctive `[I]`: here the resume checkpoint and the validator's only-shared-context
  are the *same human-readable markdown ledger* — state and isolation artifact in one file.
- **Structural context isolation.** Now mainstream-endorsed: Claude Code subagents run "in its
  own fresh conversation … only its final message returns" `[E]`
  https://code.claude.com/docs/en/agent-sdk/subagents; Anthropic's multi-agent research system
  uses per-subagent windows for compression + decorrelation `[E]`
  https://www.anthropic.com/engineering/multi-agent-research-system; Roo Boomerang; LangGraph
  subgraph namespaces; CrewAI context edges. AutoGen's shared thread is the dated approach.

**Now mainstream (was distinctive in 2024, isn't in 2026):**

- **Plan-first with approval gates** — Kiro (requirements→design→tasks + "MUST NOT proceed"
  gates), Spec Kit, Claude Code plan mode, Devin, Cline Plan/Act.
- **A separate evaluator gating completion** — Claude Code `/goal` (separate evaluator re-checks
  each turn) + Stop hooks. What stays rare `[I]`: a **frozen-original-goal** closure gate with a
  fresh-evidence rule and a remediation cap — `/goal` re-checks a running goal; it is not a
  whole-build completion gate judged against a snapshot frozen at build start. Neither Kiro nor
  Spec Kit has any doc-confirmed final "did we build what we specified" check. `[E]` (absence)

**The most concise honest framing `[I]`:** this design is the disciplined, institutional version
of the folk "Ralph loop" (persisted plan, one task per iteration, subagent fan-out —
https://ghuntley.com/ralph/) plus the blind validator, mechanized gates, and governance that folk
loops lack — equivalently, Anthropic's reference workflow with every honor-system suggestion
turned into enforced machinery.

## 3. Strongest framework prior art, fact-checked

**LangGraph** — all claims verified against official docs (2026-07-03):

- **Time-travel/resume:** `get_state_history()` + `update_state()` fork-from-checkpoint on the
  compiled graph. `[E]` https://docs.langchain.com/oss/python/langgraph/use-time-travel
- **Checkpointers:** `InMemorySaver`/`SqliteSaver`/`PostgresSaver`, state keyed by `thread_id`;
  `interrupt()` requires a checkpointer, resumes via `Command(resume=...)`. `[E]`
  https://docs.langchain.com/oss/python/langgraph/persistence · /interrupts
- **Subgraph isolation:** "Each invocation gets its own checkpoint namespace"; parent does not
  automatically see child state. `[E]` https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- **No built-in critic:** reflection/evaluator-optimizer are hand-built StateGraph patterns
  (blog/community), not a shipped component. `[E]` (absence; confirmed by non-appearance in API docs)

**OpenAI Agents SDK**, same pass: guardrails exist (`tripwire_triggered`; a guardrail *can* be a
separate cheaper agent) but are **moderation/validation, not adversarial diff review** `[E]`
https://openai.github.io/openai-agents-python/guardrails/; `Agent.as_tool()` = bounded isolated
subtask vs. handoffs sharing full history `[E]` /tools/ · /handoffs/. Swarm is stateless and
superseded. `[E]` https://github.com/openai/swarm

**Consequence `[I]`:** two of the four axes originally claimed distinctive (durable state,
structural isolation) are mechanistically available off-the-shelf. The distinctive core narrows —
and sharpens — to the blind validator + the self-measurement loop + governance.

## 4. Design critique — updated 2026-07-04 (evening)

*Re-derived after Phases A–F landed (358 passing tests) plus a targeted verifier-precision /
error-correlation research pass. The 2026-07-03 critique is preserved in git history; this
section supersedes it. In-tree claims below were verified directly against the working tree
on 2026-07-04.*

### 4.1 The original four, re-statused

1. **Safety logic as prose — largely resolved; survives narrowed (high → med).** Everything the
   original critique named is now a tested script or hook: liveness counting (`harness/liveness.py`),
   budget math (`harness/governor.py`), held-out-drop detection (`hooks/heldout_drop_check.py` +
   gate step), the closure workflow (`harness/closure.py` + Stop-hook script), evidence appends
   (write-ahead event log + `harness/evidence.py`); "machinery-strip-and-retry" was dropped from
   the amended design entirely. What survives, verified in-tree `[E, in-tree 2026-07-04]`:
   **(a) no settings file registers any hook** — the scripts are deterministic *once invoked*,
   but nothing makes them un-skippable; the closure gate even lacked a Stop-hook stdin interface;
   **(b) the triggers are prose** — "merge only through the gate" and "governor between tasks"
   are skill sentences; nothing intercepts a merge to demand a PASS gate report, nothing makes a
   spawn refuse without an admission decision (the corpus already holds the fix pattern:
   firstmate's spawn-refuses-without-routing-decision,
   [unattended-operation-prior-art.md §8](../unattended-operation/unattended-operation-prior-art.md));
   **(c) the gate is skippable-by-omission** — every absent input (`test_cmd`, `vault_path`,
   `verdict_dir`, floors) yields a passing "caller's choice" step. Fixes = plan Phase H1–H3.
2. **Apparatus vs. realized scale (med, re-aimed).** The apparatus grew to ~20 modules / 358
   tests with **zero real firings, an empty escapes log, and no recorded real agent traces**
   (the A6 rig's fixtures are synthetic) — every telemetry-fed mechanism has no data, and
   confidence is generated by machinery passing its own tests. Mitigants: the operator's
   disposable-code scope rule and dormant/observe-only staging. The prescription changed: not a
   config split — **a small real pilot firing before further machinery** (now the Stage-0 exit
   criterion). Exhibit: the implementation plan's own "living ledger" drifted stale within a day
   (F1/F2 `not-started` while merged) — the claims-not-evidence rule, not the prose ledger, is
   what kept run 6 honest.
3. **Reflection can go ungrounded — resolved by design and code (med → watch item).** §5.6/§8
   mandate event-triggered reflection only; F2 implements one-lever/sample-floors/ratify-only.
   Residual risk is operational.
4. **Provider coupling (accepted, one new facet).** Volatility load is as predicted (promo
   expiry, paused Agent-SDK billing change — standing rechecks). New facet: coupling also
   **caps panel diversity** — see 4.2-N2.

### 4.2 New critiques (missing from the 2026-07-03 pass)

- **N1. False FAILs unmodeled (med-high).** The O0 apparatus points entirely at false PASS; the
  symmetric failure has measured high base rates (~79–83% of candidate findings killed by
  adversarial refutation; ten reviewers unanimously endorsing a non-existent OpenSSL vuln,
  killed only by one empirical test; judges misclassifying correct code —
  [correctness-and-verification-evidence.md §7](../validation/correctness-and-verification-evidence.md)).
  In this design one hallucinated FAIL blocks a merge, drives paid escalation, and poisons
  break-even telemetry; the repro-quoting rule is claimed-not-replayed. Fix: executable-repro
  findings replayed by the gate + a false-FAIL counter (plan H4).
- **N2. Panel independence overestimated (med).** Errors correlate strongly across models —
  ~60% same-wrong-answer agreement when two models err, correlation *rising* with capability
  and persisting across providers; judges favor similar models
  ([correctness-and-verification-evidence.md §3 addendum](../validation/correctness-and-verification-evidence.md)).
  A Claude-only panel is not N independent draws; model heterogeneity demotes to weak insurance.
  What de-correlates is leverage diversity. Fix: panel-wide canary aggregation as correlation
  telemetry + optional cross-provider validator card for critical profiles (plan H5).
- **N3. "Escapes ≈ 0" is unfalsifiable without a discovery channel (med).** Greenfield,
  solo-operator, pre-production: nothing discovers a merged-but-wrong change, so catch-rate
  reads optimistic exactly when discovery is weakest; canaries measure only the planted-defect
  distribution (~27% of real faults uncoupled from standard mutants,
  [revalidation-reuse-and-leakage.md §4](../validation/revalidation-reuse-and-leakage.md)). Fix: deterministic
  escape backfill + sampled escape-hunts + flip conditions requiring an *active* discovery
  channel (plan H6).
- **N4. Held-out content leaks around the vault via evidence artifacts (low-med).** The gate
  spills full test output to in-repo evidence dirs a retry implementer can read — an adaptive-
  reuse leak the §5.5 budget never governed. Fix: vault-side evidence store + manifest-based
  scrubbing of in-repo reports (plan H7).
- **N5. The spec is a shared single point of failure (low-med, accepted-with-eyes-open).**
  Blind validation cannot see spec↔intent divergence; the human plan gate is the mitigation.
  Cheap addition: test-author spec-ambiguity findings become blocking blocker-records on
  high/critical profiles *before* implementation spends tokens (plan H9).
- **N6. Unattended firings run on the weakest quota telemetry (low-med).** The best governor
  rung is interactive-only; the shim stales exactly overnight; the estimate rung is optimistic
  and blind to the operator's other usage — while agents measurably can't self-throttle. The
  governor had **no staleness handling** `[E, in-tree]`. Fix: age-aware readings + a preflight
  that starts conservative when no live rung is reachable (plan H8).

**Retracted (stands, reinforced):** "the validator panel over-buys" — the closest published
analogue (Refute-or-Promote) independently converged on adversarial kill-mandates + empirical
gates as the way to make panels precise; see
[correctness-and-verification-evidence.md §3, §7](../validation/correctness-and-verification-evidence.md).

### 4.3 Commoditization update (2026-07-04, observed in the dev environment)

Claude Code now ships one-command multi-agent cloud code review with adversarial verification
stages (`/code-review` at high effort / ultra), Workflow scripts (deterministic orchestration,
schema-forced agent returns, resume journal, token-budget accounting), and a native
custom-agent registry that this repo's `.claude/agents/` already plugs into. `[E, in-environment]`
None of it is blind-vs-implementer, none authors held-out tests, none gates merges — the
distinctive core (vault + calibration + governance) survives and sharpens — but the periphery
keeps becoming a vendor button. Consequence: the §4 leverage map needs a standing re-audit
cadence (first candidate: build-loop control flow as a Workflow script), and the "who benefits"
answer concentrates further on the blind-validation/self-measurement/governance core.

## 5. Who benefits

**Strong fit:** solo devs/small teams building **security-sensitive greenfield** (multi-tenant
SaaS, auth, billing, isolation) where a blind adversarial validator earns its cost; **people
building their own harness** (as a reference design/pattern library, the process spec may
be worth more than the runnable tool); any work where a false "done" is expensive.

**Poor fit:** exploratory/prototype "vibe coding" (plan-first ceremony is pure overhead — Aider/
Cline/Kiro-vibe); teams wanting off-the-shelf autonomy (single-worker, manual-trigger,
Claude-coupled, expects an operator who groks the ledger model); large brownfield codebases (the
phased-ledger model is built for greenfield, plan-decomposed work).
