# Multi-agent orchestration — the evidence

Does multi-agent orchestration beat a single strong agent, when, and why does it fail? The
distributed-systems theory under the harness's concurrency machinery (and a source-level audit
of it) is the companion, [concurrency-and-merge-correctness.md](concurrency-and-merge-correctness.md).

**Provenance:** 2026-07-10 deep-research pass. Six Opus 4.8 clusters over ~45 sources (most
full-text): the does-multi-agent-pay adjudication, the MAST failure taxonomy, parallel
code-generation, handoff/communication, shipped frameworks, and concurrency theory. Extends the
practitioner-repo studies in
[../landscape/ecosystem-mining/parallelization-and-decomposition.md](../landscape/ecosystem-mining/parallelization-and-decomposition.md)
(the stub-and-seams survey) and the framework matrix in
[../landscape/landscape-and-novelty.md](../landscape/landscape-and-novelty.md). Tags per corpus
convention; every headline number is author-run unless a tier says otherwise, single-source
magnitudes flagged.

---

## 1. Does multi-agent beat a single strong agent? — the adjudication

The frontier-lab "disagreement" is an illusion of task shape. The axis is **independence ×
read-vs-write**, and both labs concede the other's domain:

- **Anthropic** ("How we built our multi-agent research system"): orchestrator-workers beat
  single-agent Opus by **+90.2%** on an internal *research* eval — but at **~15× chat tokens**,
  with **token spend explaining 80% of the variance** (i.e. mostly paid for, not conferred), and
  the essay **explicitly declines to extend the result to coding**: "most coding tasks involve
  fewer truly parallelizable tasks than research." `[M, vendor-run, research, not budget-controlled]`
- **Cognition** ("Don't Build Multi-Agents," Jun 2025): "actions carry implicit decisions, and
  conflicting decisions carry bad results" — parallel writers make contradictory choices (the
  Flappy-Bird incoherence example); prescription is a **single-threaded writer + a context
  compression boundary**. `[vm, engineering-judgment, unmeasured]` **Reversed 22 Apr 2026**
  ("Multi-Agents: What's Actually Working"): multi-agent works *iff writes stay single-threaded* —
  one **writer** + many **reader/verifier** agents — and "clean context leads to a notable
  improvement in a generator-verifier loop" (removing shared context between coder and reviewer
  *improves* detection). `[M, vendor, coding]`

**The decisive independent result** — Tran & Kiela, "Single-Agent LLMs Outperform Multi-Agent
Systems... Under Equal Thinking Token Budgets" (arXiv 2604.02460), `[M, independent, the
equal-budget control is the whole point]`: with thinking tokens equalized, **single-agent is the
best or statistically tied at every budget except the lowest**. "Many reported advantages of
multi-agent systems are better explained by unaccounted computation and context effects rather
than inherent architectural benefits." Grounded in the **Data Processing Inequality**:
message-passing between agents is *lossy compression* versus one model's latent reasoning.
Multi-agent becomes competitive *only when the single agent's context degrades* (masking, noise,
overflow) — **it is a hedge against context corruption, not an inherent upgrade.**

Supporting shape:
- **Inverse scaling** (arXiv 2606.00655): performance is an **inverted-U**, peak at **n=2–4** then
  decline; reasoning tasks *collapse* post-peak (−27 to −33pp); a token-padding ablation shows
  the cause is **coordination overhead, not long-context failure**; small models (7–8B) degrade
  *monotonically* — only 70B+ sustain synergy.
- **Aggregation loss** (arXiv 2509.23537): four frontier models orchestrated vs the strongest
  single = **+0.7pp average, one benchmark negative**; on GPQA at-least-one-agent-correct was
  **95.5%** but the system delivered **87.4%** — ~8pp lost because selection "prioritized perceived
  reasoning quality over actual correctness." **Reconciliation, not lens count, is the failure surface.**
- **Decorrelation saturates** (More Agents Is All You Need, TMLR; MacNet, ICLR 2025): sampling-and-
  voting and networked collaboration both scale *logistically* — real gains, early knee, then
  plateau.
- **Self-report vs independent gap** (see §2): MetaGPT self-reports HumanEval 85.9%; MAST
  *independently* measures ChatDev at **25% correctness** on ProgramDev. Where re-measured, reality
  is far below the self-report.

**The four sub-cases, separated:**

| Sub-case | Verdict | Condition |
|---|---|---|
| Parallel **read/search** fan-out (decorrelation) | **wins** | independent subquestions, context exceeds one window, read-only |
| Role-specialized **pipelines** | modest win, from *structure + verification*, not agent count | serial SOP with a verification stage |
| **Debate / voting** | marginal, saturates, **can hurt** | corrupts confident single-agent reasoning via herding |
| Parallel **write into shared state** (coding) | **strictly worse** | dependencies + shared context → conflicting implicit decisions |

**Harness mapping.** The design sits on the endorsed shape: **free validation fan-out = the one
topology everyone endorses** (read-only, independent, decorrelated); **budget-gated implementation
fan-out = correctly gating the worst case** (parallel write); the single-orchestrator-spine +
short-lived-workers *is* Cognition's *accepted* architecture (a shared-context spine with
compression boundaries), not the peer-multi-agent pattern they warn against; and "context
isolation is also compression, only the structured return crosses" is *literally* the DPI result.
Two refinements the evidence forces:
1. **Validation-panel breadth saturates (~n=2–4).** The design governs breadth by O0/O1 and
   "never shrinks it for wall-clock" — not contradicted, but the marginal Nth lens buys little
   decorrelation, so profile panel sizes should reflect the saturation knee, and **verdict
   reconciliation deserves as much design attention as lens count.** One quiet strength: the
   harness uses **all-must-pass**, not quality-weighted voting, so it structurally avoids the
   "aggregation prioritized perceived quality over correctness" loss that sank the voting systems.
2. **Worker capability is a hard prerequisite** — small models can be *anti-synergistic* in fan-out
   (2606.00655), which qualifies "route grunt work to the cheap tier."

## 2. Why multi-agent systems fail — MAST and the cascade

**MAST** — "Why Do Multi-Agent LLM Systems Fail?" (Cemri et al., Berkeley, arXiv 2503.13657,
NeurIPS 2025; 1,600+ traces, 7 frameworks, κ=0.88), `[peer-reviewed]` — is the anchor. Failures
split **Specification & System-Design 41.8% / Inter-Agent Misalignment 36.9% / Task Verification
21.3%** — roughly balanced, and **predominantly coordination/specification/verification, not model
capability.** Targeted fixes (role-spec refinement + a verification step) added only ~+14–15% and
left success "insufficiently low" — the authors concede fixes need *structural redesign, not
prompt patches*. The single most decision-relevant number for handoff design: **Information-
Withholding is only 0.85% of failures** — the "share full context" camp's predicted culprit is
negligible; the real weight is **Reasoning-Action-Mismatch 13.2%**, Task-Derailment 7.4%,
Fail-to-Ask-Clarification 6.8%. MAST's own conclusion: "solutions focused on context or
communication protocols are often insufficient" — **verification fixes coordination failures.**

**Error cascade** (From Spark to Fire): a single injected error can reach **100% system infection**;
hub-injection in a star is **10.3× worse** than a leaf; and containment requires an *actual
blocking gate* — remove the blocking step and containment collapses from 0.94 to 3.1%. **Detection
without a gate does not contain a cascade.**

**Faulty vs Byzantine** — the tension resolves by *intent* (On the Resilience of LLM MAS, ICML
2025): our workers are **faulty-not-adversarial**, so the resilience regime applies. One faulty
agent drops accuracy **5.5% (hierarchical + review) vs 23.7% (worst topology)**, and a **downstream
inspector recovers up to 96.4%** of a faulty agent's errors. The measured prescription —
**hierarchical control + an independent downstream inspector** — is precisely a merge gate with
blind held-out tests.

**MAST's 14 modes × this harness** (fresh-context workers → structured-return-only → blind
validators with held-out spec-authored tests on a clean checkout → single merge gate):

- **Structurally prevented (7 modes + the cascade channel):** disobey-role-spec, lost-history
  (statelessness is intentional), unaware-of-termination (gate is the external stop),
  conversation-reset, ignored-agent-input, premature-termination/wrong-DONE (the central bet —
  self-declared completion has no authority), no/incomplete-verification (institutionalized,
  non-optional). Plus the cascade channel itself: **no raw artifact flows worker→worker; the
  clean-checkout gate is the quarantine the cascade literature says you need**, and the blind
  validator is the 96.4%-recovery inspector.
- **Detected but not prevented (costs a cycle):** disobey-task-spec, task-derailment,
  reasoning-action-mismatch (the validator judges the *diff*, not the narration).
- **Genuinely exposed (4):** **(i) spec-layer error** — the largest MAST category — because the
  gate verifies *conformance to* spec, not *correctness of* spec, and the validators share that
  spec (this is the same blind spot the planning pass located, and our own P3-2 was an instance);
  **(ii)** fail-to-ask-clarification, *traded away* by isolation and pushed upstream to the
  planning interview; **(iii)** verification-coverage gaps (bounded by held-out coverage);
  **(iv) hidden depth inside a worker** — if a worker spawns sub-sub-agents, cascade re-enters
  *below the gate's visibility*. **Containment composes only if every delegation level has its own
  verification boundary** — which is the theoretical case for the harness's deliberately *flat*
  topology (one level of fan-out).

## 3. Parallel code generation — the stub-and-seams question, measured

The ecosystem study said parallel-implementation-into-one-codebase is "measured by nobody." A
handful of 2025–26 papers now measure it, and they confirm the pessimism on throughput while
validating the harness's design on correctness. The sharp distinction first: **most "multi-agent
code" is serial role-play on one small function** (Self-Collaboration, AgentCoder, MapCoder,
MetaGPT are all serial single-writer); every *repo-level* "parallel" system achieves parallelism
by **partitioning to avoid concurrency** and integrating **serially**.

- **CodeCRDT** (arXiv 2510.18893, 600 trials) — the *only* true concurrent-write measurement.
  Even after **deleting the syntactic merge problem entirely** with CRDTs (0% character conflicts),
  concurrent implementation is **13.1% slower on average** (−21% to +39%; it emits 82–189% more
  code), and **semantic conflicts survive conflict-free merge: 5–10% baseline, rising to ~80% on
  complex tasks.** The decisive proof that the combine step is a *judgment* problem, not a
  mechanical one — and the empirical vindication of superpowers' ban on parallel implementers.
  `[preprint, single-source]`
- **CAID** (arXiv 2603.21489) — the one repo-level parallel system that *wins*, with **the harness's
  exact topology**: dependency-graph partition into non-overlapping tasks, isolated worktrees,
  **serial git-merge + test validation**. Claude Sonnet **57→63%**, weak model MiniMax **10.5→36.1%
  (+25.6pp)** — but the authors state plainly **wall-clock and cost are not reduced.** The win is
  *correctness*, and *weak models benefit most*. `[preprint, single-source]`
- **The Specification Gap** (arXiv 2603.24284) — the measured proof of the determinacy bet (and the
  same paper the planning pass cites). Two agents implement parts of one class in parallel across
  spec-completeness levels: full docstrings → **58%**, bare signatures → **25% — which loses to a
  single agent at 56%.** "Restoring the full specification alone recovers the single-agent ceiling;
  **providing conflict reports adds no measurable benefit**" — post-hoc conflict resolution buys
  nothing; the spec must be right up front. This is "gate fan-out on ratified seam determinacy,
  not size," measured causally. `[preprint, single-source]`
- **AgentCoder** (arXiv 2312.13010): its test designer generates tests **without seeing the code**,
  "because tests following the code in one conversation can be biased and lose objectivity" —
  independently arriving at the harness's **blind-test-author = correctness** argument (but
  per-function, serial, post-hoc, not a pre-dispatch held-out seam contract).
- **AgenticFlict** (arXiv 2604.03551): **27.67%** of agentic PRs conflict; Claude Code ~25.9%,
  Codex ~31.9% (≈2× Copilot's 15.2%); **small PRs 9.9% vs medium 30%** — churn drives conflicts,
  supporting small determinate units. `[preprint, observational]`
- **Strong-Weak** (arXiv 2505.20182): strong plans/localizes, weak implements → **40% cost cut at
  strong-model-equivalent performance** — but *only* with instance-level determinate guidance;
  repo-level generic context "consistently failed." The academic restatement of "determinacy, not
  brevity, licenses the weak model," and it says **keep the planner/integrator strong.**

**Direct answers.** *Does parallel-into-one-codebase beat serial?* On **throughput: no** (CodeCRDT
13.1% slower — no paper shows a throughput win from concurrent implementation). On **correctness:
yes once (CAID), but from partition-and-serially-integrate — the harness model — not concurrent
fan-out, which loses.** The whole harness stub-and-seams design is validated by this cluster:
determinacy gate (Specification Gap), blind held-out contract tests (AgentCoder), expensive serial
integrator (CAID + CodeCRDT proving the integrator's job is *semantic* and can't be cheapened),
determinacy-licenses-the-weak-model (Strong-Weak) — with one **sober correction the design must
internalize: the transferable win is correctness-per-dollar, not wall-clock speedup.** The open,
publishable gap is still ours: nobody has measured a repo-scale decomposition-quality →
integration-success curve with blind *pre-dispatch* seam contracts.

## 4. Handoff and communication — the structured-return rule, resolved

The harness's rule ("workers return only a structured result, never a raw transcript; the
orchestrator ingests structured state only") is **correct**, and the strongest critic now agrees.
Resolve it by task shape, because two jobs hide under one rule:

- **Blind validation** — compression is *not* economy here, it is a **correctness property**: the
  validator must not see the implementer's reasoning; decorrelation is the point. Cognition's
  capability argument is *inverted* here — Cognition itself now says the review agent's clean
  context lets it "go deeper," and MAST puts 21.3% of failures on verification (a validator that
  inherited the implementer's rationalizations would inherit its blind spots). **Structured-return-
  as-blindness is unambiguously right, and the strongest critic endorses it.**
- **Capability handoff** — Cognition's "actions carry implicit decisions" bites *only if the summary
  is the sole thing that crosses.* In the harness it isn't: the implementer's actions persist in
  the **git diff / worktree**, and the structured return *annotates* that durable artifact. The
  harness **serializes writes behind the merge gate** (one writer into main at a time) — which *is*
  Cognition's own "one writer, shared context" prescription, achieved through the repo rather than
  a shared transcript. The telephone game (5 hops at 95% → 77%) degrades only when each hop's *sole*
  input is the prior hop's summary; grounding every hop in the diff breaks the chain.

**Schema adequacy** — MAST names the fields that matter by what their absence causes:
`spec_ambiguities` → Fail-to-Ask-Clarification; `intent` → Task-Derailment; `key_changes_made` +
`files_touched` *grounded in the diff* → Reasoning-Action-Mismatch (the largest inter-agent mode);
`key_learnings` → repeated re-exploration. **No field gap.** The one high-leverage addition the
evidence points to (cluster 1 + Cognition P2 + DPI): carry the worker's **explicit committed
constraints/assumptions**, not just the artifact, so the orchestrator can detect cross-worker
conflict *before* integrating — otherwise a return that crosses only the diff re-creates
Flappy-Bird incoherence at merge. Keep `files_touched` mandatory and the summary strictly
subordinate to the diff (never the sole basis for a dependent write).

**Protocol direction** — in-process typed return is **sufficient and strictly richer**. A2A
(Agent Cards, Tasks, Artifacts-by-reference) solves cross-vendor, cross-process *federation* the
harness doesn't have, and even it carries structured Tasks + Artifacts-by-reference, corroborating
the shape; a network boundary would *weaken* the OS-enforced filesystem isolation the vault
depends on. **ACP** (Zed's Agent Client Protocol, Zenith's spawn layer) is the only protocol worth
tracking, and only as a **single-vendor-coupling hedge** — but ACP sessions run `bypassPermissions`,
so adopting it would still require re-wrapping in the vault/gate. Net: in-process now; ACP a filed
contingency; A2A out of scope (consistent with [zenith §8](../landscape/zenith-and-meta-zenith.md)).

## 5. Shipped orchestration — the topology landscape

Extends the framework matrix on the topology axis. Everyone ships the same menu (orchestrator-
workers + handoff/peer + group-chat + sequential/parallel workflow), and **every vendor's default
guidance is "start single-agent, escalate only when isolation/routing demands it."** `[fp]`

| Framework | Topology | Concurrency | Isolation | Merge gating | Coding-measured? |
|---|---|---|---|---|---|
| **Claude Code** (subagents + Workflow) | orchestrator-workers; peer (agent-teams, experimental) | 16 concurrent/run cap; `parallel()`/`pipeline()` | context-window only (worktree = experimental flag) | **none** (script phases) | no (research only) |
| OpenAI Agents SDK | peer handoff-graph + agents-as-tools; hand-wired | asyncio, turn-sequential | handoff=shared history; as_tool=bounded | none | no |
| LangGraph | supervisor + swarm prebuilts; graph substrate | Pregel/BSP super-steps; `Send` fan-out | subgraph namespace-isolated | state reducers (no validation) | no (retail τ-bench only) |
| CrewAI / AutoGen-AG2 / MS Agent Framework | crews-flows / group-chat / five patterns + Magentic | async / actor / workflow-graph | isolated / **shared thread** / per-pattern | manager-LLM / none / HITL approval | no (GAIA only) |
| Google ADK + A2A | hierarchy + Seq/Parallel/Loop; A2A = topology-agnostic transport | `ParallelAgent` concurrent fan-out | branch-isolated (manual state) | none | no |
| Amazon Bedrock MAC / AgentCore | supervisor + ≤10 collaborators | parallel invoke | **Firecracker microVM** (OS-level) | none (supervisor aggregates) | weak (simulated dev) |
| Zenith (ACP) | orchestrator-workers + terminal reviewer | static `max_parallel=4` | fresh ACP proc, **shared cwd, bypassPermissions** | deterministic AND-gate + reviewer (prompt-blind) | yes, n=1 |
| **This harness** | orchestrator-workers, single-writer | **budget-admission-gated** | **six-layer OS vault + worktree** | **blind-validation-gated + held-out** | (pilot pending) |

**Topology-utility evidence is scarce and leans against naive multi-agent for coding**: the
equal-budget refutation (§1); **SWE-EVO** (arXiv 2512.18470) — multi-agent *degrades* −2% to −15%
once single-agent baselines exceed ~45%; the one positive is **adaptive/task-conditional topology
selection** (AdaptOrch, +22.9%) — empirical backing for the harness's risk-profile table and
Meta-Zenith's task-family idea. No independently-replicated benchmark shows a coding topology
winning.

**What NONE of them ships — the harness's live differentiators:** (1) **blind-validation-gated
merge with held-out tests** — the field's gates are LLM-judgment (CrewAI), HITL approval (MAF), or
prompt-blind AND-gates (Zenith) over shared-filesystem artifacts (the reward-hacking hole is 12/12
across studied systems); Cognition's "clean context" reviewer is the nearest, still prompt-blind.
(2) **Budget-admission-gated concurrency** — everyone ships *static* caps (Claude 16, Bedrock 10,
Zenith 4) or advisory warnings; **none makes a spawn refuse until a governor admits the token
cost.** (3) **Generation-stamped durable state** — checkpointing resumes everywhere,
generation-stamping to detect racing writes nowhere. Two import candidates: **AgentCore-style
microVM isolation** as a stronger vault substrate than worktrees, and **adaptive topology
selection** as backing for the risk table.

## 6. Design mapping — confirms, refines, exposes

**Confirmed (strongly, and often independently converged):** free validation fan-out is the
one endorsed topology; budget-gated implementation fan-out correctly gates the worst case; the
single-orchestrator-spine is Cognition's *accepted* architecture; structured-return-as-compression
is the DPI result; blind-validation-gated merge = the measured 96.4%-recovery inspector +
Cognition's clean-context reviewer; flat topology is the cascade-containment prescription;
the harness's exact partition-then-serial-integrate topology is the one that *wins* on coding
(CAID); the determinacy gate is measured (Specification Gap); all-must-pass structurally dodges the
voting-aggregation loss.

**Refined:** validation panel breadth saturates (~2–4) — size profile panels to the knee and
invest in *reconciliation*; worker capability is a hard floor for cheap-tier fan-out; the
transferable parallel win is **correctness-per-dollar, not wall-clock** — pitch it that way.

**Exposed (the honest gaps):** spec-layer error is the top residual (gate verifies conformance,
not correctness — same blind spot as the planning pass, and P3-2 was an instance); hidden
sub-agent depth below the gate re-opens the cascade; and the highest-leverage schema addition is
**explicit committed-constraints in the return** to catch cross-worker conflict before merge. The
concurrency-machinery exposures (including a real latent merge-race bug) are audited in the
[companion document](concurrency-and-merge-correctness.md).

## Open questions

- Measure the repo-scale decomposition-quality → integration-success curve with blind pre-dispatch
  seam contracts — the publishable gap nobody has filled.
- Add **committed-constraints/assumptions** to the handoff schema; test whether it catches
  cross-worker conflict pre-merge on a real parallel pilot.
- Right-size validation panels to the saturation knee per profile, and design verdict
  reconciliation as a first-class surface (it lost 8pp in the one study that measured it).
- Adaptive/task-conditional topology (AdaptOrch/Meta-Zenith) as the evidence base for the risk
  table — is topology-by-profile measurably better than a fixed topology?
- Watch: any independently-replicated coding-topology benchmark (none exists); AgentCore microVM
  isolation as a vault substrate.
