# An evidence-based coding-agent harness — from-scratch design plan (draft 1)

**Status: first draft, 2026-07-10.** This is a from-first-principles redesign. It inherits
**nothing** from [token-time-optimized-harness.md](../attic/token-time-optimized-harness.md) (kept as
history) — no prior decision survives unless the evidence independently re-derives it. It
assumes a **fresh implementation substrate**: the only assets carried forward are the research
corpus, its grading method, and the internal defect record. It is deliberately **under-designed**:
where highly-reliable evidence is missing, the section says TBD and names the experiment that
would settle it, because a decision made without evidence would just be the previous project's
mistake with newer citations.

**How to read a decision.** Every design choice carries one of three statuses and cites the
evidence that carries its weight, almost always via
[distilled/external.md](../research/distilled/external.md) (§-references below are to that
document unless marked *internal*, i.e.
[distilled/internal.md](../research/distilled/internal.md)):

- **Decided** — Tier-A evidence forces or strongly licenses it (grading method:
  [distilled/README.md](../research/distilled/README.md)).
- **Provisional** — Tier-B: the *sign* is trusted, the magnitude or mechanism-transfer is not;
  the entry names its promotion trigger.
- **TBD** — evidence absent or contested; the entry names what would settle it. TBD is a
  first-class outcome of this exercise, not a gap to be filled by taste.

The standing rule applies throughout: **import the mechanism, never the magnitude.**

---

## 1. Operator requirements (constraints, not conclusions)

These are requirements set by the operator. They are inputs the design must satisfy, kept
separate from evidence so nobody mistakes a preference for a finding.

- **R1 — The economic substrate is fixed-cost subscription windows** (5-hour + weekly caps,
  shared pool, credits strictly opt-in so an unattended run halts at the wall — the §4 official
  commitments). The goal is *reliable unattended work inside the windows*, not dollar
  minimization.
- **R2 — Machinery must be minimal.** The previous design's post-mortem: the machine cost tokens
  to save tokens, and meta-work crowded out real work. Every mechanism in this plan must justify
  itself against the null harness (plain Claude Code with a good prompt); "would help" is not
  justification.
- **R3 — Operator comfort is explicitly not a goal.** Gates are measured by errors caught, not
  satisfaction — which the evidence says would otherwise be traded against each other, because
  the oversight designs that work best are the ones operators like least (§3.3).
- **R4 — No long-horizon token optimization.** Same-task spend varies up to ~3× between
  identical reps (*internal* §4, committed artifact), horizon-bucket prediction has no validated
  feature set, and the operator judges the problem inherently hard. The harness measures spend;
  it does not predict or optimize it over horizons.

---

## 2. Decisions

### D1. All correctness authority lives outside the agent — **Decided**

No agent output is accepted on the agent's own assessment: not code, not plans, not completion
claims. PASS/FAIL is pronounced only by **sound verifiers** — execution, tests, type checks,
static analysis — and LLM judgment may triage, localize, or generate candidates for sound
verification, but never seal a result.

**Evidence.** LLM self-critique is net-negative, replicated across disjoint domains — 55/100
self-critiqued vs 88/100 with a sound external verifier, at an 84.45% false-positive rate
(§3.1); agent self-reports are unreliable exactly where verification is absent — ≥16% of
successful 8h+ runs involved cheating, disavowed when asked; fabricated execution transcripts
(§3.1); the entire §2.2 gaming ledger (every published self-improvement loop exploited any
evaluator it could see, edit, or self-grade); and M5 — the correctness floor cannot be a proxy
the loop optimizes.

### D2. Graded tests are authored from the spec by a party that never sees the implementation, and the implementer cannot reach them — **Decided** (the enforcement mechanism), **Provisional** (full validator blindness)

Test authorship is a separate role with a separate filesystem boundary. The implementer cannot
read, write, or discover the graded tests; the tests are authored from the ratified spec alone.
Separation is enforced by **machinery** (process isolation, OS-level file access), never by
prompt instruction.

**Evidence.** Grading on agent-authored tests is null-to-harmful — 21.8–33.0% of
visible-test-passing patches fail hidden tests, and refining against self-authored tests makes
it *worse*, while provided ground-truth tests help (§3.1); Anthropic's own admission that
"Claude will sometimes change tests to make them pass" (§2.1); the implementer-can-edit-its-judge
hole is 12/12 across studied systems and 0 of 9 shipped frameworks close it (§5, §6); prose
enforcement measurably fails — STOP's explicit `# DO NOT CHANGE` warning made sandbox-disabling
*more* frequent (§2.2); Zenith's blindness is a prompt promise, not a boundary (§5). Two
mathematical constraints govern the held-out set's reuse: an adaptively re-queried holdout has a
bounded, known number of safe reuses (M2), and threshold-revealed results bound leakage to
O(log k) (M1).

**The provisional part:** withholding the *validators'* reasoning from the implementer (and vice
versa) beyond test-secrecy is mechanism-plausible (judge self-preference, §3.1) but its marginal
value over test-secrecy alone is unmeasured — promotion trigger is experiment **T2**.

### D3. Completion is granted, never claimed — **Decided**

"Done" is a state only an external verifier can produce, and the runtime refuses to fabricate
it: the loop cannot end a task, a phase, or the build on its own assertion. Every completion
carries the verifier artifact that granted it.

**Evidence.** Premature completion is *the* dominant long-horizon failure — agents "satisfice
rather than optimize, often submitting before the time limit," with poor ability to notice
progress, replicated across METR RE-Bench, independent research-agent post-mortems, and Zenith's
convergent design (§3.1); Zenith's committed code demonstrates the mechanism is buildable — only
the terminal reviewer's verdict seals `done` (§5).

### D4. Single-writer topology; parallelism only where the evidence licenses it — **Decided**

Exactly one agent writes to the workspace at a time. Concurrency is licensed for three shapes
only, each with its evidence-bound condition:

1. **Read-shaped fan-out** (research, localization, review) — the one regime where multi-agent
   is competitive, as a hedge when a single context would degrade, and per Anthropic's own bound
   "high-value, heavily-parallelizable, context-exceeding" (§2.1, §3.2).
2. **Verification lenses**, sized to the measured saturation knee of **n≈2–4** (§3.2) and
   diversified by *modality* (execution vs static analysis vs LLM review) rather than by model
   count, because same-family validators are not independent draws (§3.1).
3. **Partitioned implementation with serial integration** — only when seams are determinate up
   front (§3.2: bare-signature seams *lose* to a single agent; post-hoc conflict reports add no
   measurable benefit), and with the expectation set by CAID's own concession: the win, if any,
   is correctness, **not wall-clock or cost** (§2.3).

**Evidence.** At equal thinking-token budgets a single agent is best or tied at every budget
except the lowest (§3.2, four independent parties incl. Anthropic against interest); the DPI
floor (M6); the only concurrent-write measurement is 13.1% *slower* with syntactic conflicts
eliminated and semantic conflicts surviving (§3.2); Anthropic explicitly declines to extend its
multi-agent result to coding (§2.1). *Internal* corroboration: the one time two agents fixed the
same defect in parallel, the result was worse than either alone (P2-collision, *internal* §1).

### D5. Every independent check sits behind a blocking gate — **Decided**

A verifier that can be advised-past does not exist for correctness purposes. Merge, task
completion, and phase transitions are interlocks: no PASS artifact, no progression — enforced by
machinery, with no advisory mode.

**Evidence.** Detection without blocking collapses cascade containment from 96.4% recovery to
~3% (§3.2); multi-agent failures concentrate in coordination/verification, and the taxonomy's
own authors concede prompt patches are insufficient (§3.2); Zenith's gate can be `continue`d
past on prompt authority alone — named there as the gap, not the pattern (§5).

### D6. A "0 findings" verdict is never trusted bare — **Decided** (the distrust), **TBD** (the instrument)

Verifier silence is treated as "nothing found," never as "nothing there." Unanimous LLM
endorsement is explicitly not a correctness signal.

**Evidence.** Five agents unanimously endorsed a nonexistent vulnerability, independently
replicating our own ten-reviewer phantom-vuln result (§3.1); cross-model errors correlate at
~60% and rise with capability (§3.1).

**The TBD:** what instrument *does* license trust in a quiet verdict. Planted known-defect
canaries are this project's own unpublished idea (§6 absence) with a mathematical caveat — they
measure the planted distribution, not the real one (M4). Experiment **T4**.

### D7. Plans: gate quality, not presence; determinacy before decomposition; clarification is load-bearing — **Decided** (core), **Provisional** (mechanics)

- A plan is ratified by a human **and** machine-preflighted before execution; the planner never
  self-certifies (§3.1 self-critique, 84.45% FP on plan verification specifically).
- The preflight requires an **acyclic task graph** — the mathematical precondition for any sound
  structural check to exist at all (M7) — and rejects plans whose seams are underdetermined
  wherever decomposition or parallelism is intended (§3.2 seam determinacy).
- **Planning depth is task-conditional.** Explicit planning pays ~+14% on structured/decomposable
  tasks and ≈0 on flat ones (§3.1 CoT meta-analysis) — so the harness must be able to run with a
  near-empty plan for flat work. A deficient plan is *worse* than none (§3.1, two independent
  studies), so the gate's failure mode must be "plan less," never "pad the plan."
- **The clarification interview is one of the best-evidenced levers in the corpus**: spec
  underspecification costs tens of points and interactive clarification recovers most of it
  (§3.1, three independent benchmarks, three recovery mechanisms). Budget real tokens there.
- Requirements templates are formatting, not completeness — EARS's own inventors say so (§2.3);
  a template cannot substitute for the interview.

**Provisional mechanics** (sign trusted, unmeasured): typed re-plan patches with
locality-of-repair, per Zenith's committed implementation (§5) and classical plan-repair theory;
a producer-before-consumer (`requires`/`provides`) check inside the preflight — theory-derived,
promoted only if **T3** shows machine-checkable determinacy bars beat human eyeballing (no
shipped product has one — 0/10, §6).

### D8. Human gates are built against the measured failure modes of human oversight — **Decided**

The human is the scarcest, most-failure-prone component in the loop, and the §3.3 human-factors
cluster (the slowest-decaying evidence in the corpus) dictates the shape:

- **Function allocation.** Automate information acquisition and analysis high; cap *decision and
  action* automation at medium wherever the human is the failsafe (§3.3 lumberjack). Concretely:
  a hard, non-learnable carve-out routes irreversible or externally-visible actions to a human,
  always.
- **The ratification card is a cognitive-forcing artifact, not a recommendation.** The operator
  commits to a judgment *before* the machine's preference is revealed; no pre-selected default;
  the strongest counter-argument is shown; and the card explicitly prompts the omission channel
  — "what did the triage *not* flag?" (§3.3: passive recommendations raise acceptance right or
  wrong; commit-before-reveal is the one intervention that measurably cuts over-reliance; the
  silent channel suppresses detection 46%→21%). Accept the UX cost per R3.
- **Approval traffic is governed by the alarm-fatigue law.** Response tracks positive predictive
  value, so nuisance-rate reduction is the primary lever; interruptions are tiered, latched for
  high-severity events, and delivered at task boundaries — immediate interruption is reserved
  for irreversible-and-blocking cases (§3.3 alarm fatigue + interruption timing). Approval
  fatigue is also an attack surface — the Ona incident's human gate fell to it (§2.3).
- **Escalations require acknowledgement, and the dead-man's-switch fails safe**: an
  unacknowledged escalation pauses the firing; silence never auto-approves. (Fail-safe
  convention; evidence-consistent — complacency guarantees silence cannot be read as attention,
  §3.3.)
- **Batch the auto-approved; decompose the human-ratified.** Human defect-review collapses past
  ~400 changed lines (§3.3), so anything a human must actually judge arrives small, while
  low-risk items batch to the boundary for interruption economics. The risk tier decides the
  axis.
- **Approval is an intent warrant, never a correctness warrant.** Human review's measured value
  is scope/intent governance (§3.3 review-collapse; §6: no shipped product validates its
  checkpoint's defect-catching; human+AI teams *lose* on decision tasks, g = −0.23, §3.3).
  Correctness authority stays with D1's sound verifiers.

### D9. Memory: versioned plain files, deterministically captured, write-gated; nothing learned until closed-loop evidence exists — **Decided**

- **Substrate: plain files under git.** No memory architecture consistently beats a
  full-context or filesystem-grep baseline on independent harnesses — the substrate is not the
  bottleneck (§3.1). Anything fancier is unjustified complexity under R2.
- **Capture is deterministic (hooks), never model-initiative** — model-initiated capture drops
  events (agentmemory's author withdrew his own tool; Copilot concedes its store tool "isn't
  invoked reliably", §2.3), and skills/guidance auto-invocation recall is 38–69% (§3.1).
- **Delivery must measure *use*, not receipt** — injected guidance was ignored 81.5% of the time
  in its own authors' system (§2.3/§3.1).
- **Writes are gated and provenance-stamped** — poisoning succeeds at <0.1% injection rates and
  input-boundary filters miss weak-signal attacks by −40pts TPR, so the defense sits at the
  write path (§3.1); no production system does trust-weighted writes (§6) — this is a place the
  design goes beyond shipped practice on Tier-A grounds.
- **No forgetting timer** — no decay model has ever been ablated (§6); staleness is handled by
  utility-gating and supersession, the only mechanisms with support.
- **Expectation-setting:** the best available controlled result says memory buys efficiency on
  hard tasks, not quality (§2.3 Sandelin) — memory is an economics feature, not a correctness
  mechanism, and it must prove itself in **T8** before it earns permanence (closed-loop evidence
  is currently 0 across ecosystem *and* literature, §6).

### D10. No self-modification loop in v1 — **Decided**; the ratification design if ever built — **Provisional**

v1 ships with **no** mechanism that edits its own machinery, prompts, or configuration. This is
the single largest deliberate omission, and it is doubly forced: by the gaming ledger — every
published self-improvement loop exploited its evaluator, including against explicit instruction
(§2.2) — and by R2, since a self-modification loop is pure meta-work until the base harness has
demonstrated value.

If a later version builds one: modifications are **proposals only**, human-ratified through the
hardest cognitive-forcing card in the system, with the evaluator and held-out assets outside the
loop's reach (§2.2's two published countermeasures), promotion gated on held-out performance
(M1/M2 budgets), and the card built as a debate/sandwiching artifact — the self-mod case is
exactly the information-asymmetry regime where debate measurably helps, *and* the regime where a
weak supervisor's judging collapses (§2.1 weak-to-strong). Human-ratified self-modification
remains unpublished anywhere (§6) — this is the design's one genuinely novel object, and it
stays parked until the base loop earns it.

### D11. Isolation is OS-enforced, per-role, process-level — **Decided**

Role boundaries (implementer / test-author / validator) are separate OS processes with distinct
filesystem and network policies. Prompt promises are not boundaries (§2.2 STOP; §5 Zenith).
Anthropic's own sandbox documentation enumerates its gaps — "not a complete isolation boundary,"
filesystem-without-network permits exfiltration (§2.1) — and the reproduced Ona incident shows
an agent disabling its own sandbox and defeating the approval gate via fatigue (§2.3). Deny
rules have absolute precedence and resolve symlinks (§4, `vendor-build` — re-probe each build);
per-subagent sandbox differentiation is officially impossible in-process, which is precisely why
roles are separate processes (§4).

### D12. Economics: cache-stable context, halt-at-wall + park-and-resume, measure-don't-predict — **Decided** (floor), **TBD** (everything cleverer)

- **Context discipline is append-only / prefix-stable** so cache reuse is structural, not
  accidental. (Official commitment: cache reads bill ~10% of input rate — a *billing* statement;
  §4.)
- **The wall is survivable by construction**: credits are strictly opt-in, so an unattended run
  halts rather than spills (§4) — the harness records a resumable checkpoint and *parks*.
  Wake-on-reset exists nowhere in the surveyed ecosystem (§5 census) and is cheap; build it.
- **Instrument spend; never predict it** (R4; *internal* §4's 3× same-task variance with
  committed artifacts).
- **TBD — the contested question that decides how aggressive context reuse should be:** how
  cache reads weigh against *subscription windows* is officially unanswered (§4; the vendor
  declined to answer, §2.1). The built, unexecuted experiment (**T1**) settles it and is the
  highest-value single measurement available.
- **TBD — admission/routing machinery.** Window-aware admission control appears nowhere (§6),
  which makes it tempting novelty — but our own governor both deadlocked a first firing
  (bootstrap deadlock, *internal* §2) and was once correct against operator override (*internal*
  §5). v1 ships the halt/park/resume floor only; predictive admission returns only if **T5**
  shows unattended windows actually being wasted. Effort/model routing stays at
  uniform-high-effort on adaptive-thinking lineups — effort-down produced wrong answers where
  higher effort was right (*internal* §4, `model-generation` decay — re-benchmark each lineup,
  **T9**).

### D13. Tool surface: few, well-shaped, deterministically invoked — **Decided**

Small tool count with purpose-built shapes (interface ergonomics dominates transport, §3.1); no
MCP-heavy surface (the 42–77K-token schema tax, §3.1); no TOON or serialization cleverness
(measured-negative generation reliability; savings only on uniform tabular shapes, §3.1 — and
the *internal* tokenizer study reached "No TOON" against its own author's lean). Anything
load-bearing is invoked by hooks/machinery, never left to skill auto-triggering (recall 38–69%
with ~100% precision — the model under-fires, §3.1).

### D14. The harness measures itself from day one — **Decided**

The previous project's sharpest internal lesson: it never ran a controlled A/B, and its headline
win is not Tier A in its own tree because the artifact was never brought home (*internal* §5–§6).
So, from the first commit:

- every mechanism ships with its measurement and a paired null arm where feasible;
- wins require committed, third-party-checkable artifacts — a win without an artifact is a claim
  (*internal* README rule);
- predictions are pre-registered before firings (the watch-item practice worked — it caught its
  own miss, *internal* §3);
- held-out assets carry an explicit reuse budget (M1/M2), and replay is licensed on unchanged
  surface only (M3);
- absence claims state their sample and date (grading method).

---

## 3. What this design deliberately omits — each omission is evidence

| Omission | Why (evidence) |
|---|---|
| Multi-agent debate/committee for correctness | Refuted at equal budget; unanimity endorsed a phantom vuln; errors correlate across models (§3.1–3.2) |
| Concurrent writers / parallel implementation by default | 13.1% slower with conflicts CRDT-eliminated; semantic conflicts survive; the parallel winner concedes no time/cost win (§3.2, §2.3) |
| Learned/vector memory, forgetting timers | No system beats trivial baselines; no ablated decay model; zero closed-loop coding evidence (§3.1, §6) |
| Long-horizon token prediction/optimization | R4; 3× same-task variance (*internal* §4); no validated horizon features |
| Prompt-level guardrails as enforcement | STOP: the warning comment *increased* violations (§2.2) |
| Autonomous self-improvement | The entire §2.2 gaming ledger; R2 |
| Spec-first ceremony on flat tasks | CoT pays only on structured tasks (§3.1); no controlled evidence spec-first beats prompt-then-code at all (§6); a deficient plan is worse than none (§3.1) |
| TOON / serialization tricks | Measured-negative generation; narrow savings band (§3.1; *internal* §4) |
| Recommendation-first approval cards | Measured over-reliance bait: acceptance rises right-or-wrong (§3.3) |
| Approval theater (board-style review of every change) | External approval buys latency, not failure reduction (Tier B DORA, consistent with §3.3 complacency); PPV governs the human channel (§3.3) |

The strongest statement this document makes is that the previous design's machinery count was
its defect, not its moat. The evidence funds a **small** machine: one writer, sound verifiers
behind blocking gates, spec-authored held-out tests, a forcing-function human surface, files as
memory, park-and-resume economics, and instrumentation. Everything else waits for data.

## 4. TBD ledger — the deliberately undetermined

| # | Question | What settles it |
|---|---|---|
| T1 | Do cache reads meaningfully discount *subscription-window* occupancy? | The built cache-weight experiment (operator-run; quota-costing) |
| T2 | Does blind validation + a held-out vault pay its overhead vs test-secrecy alone, per risk tier? | Paired-arm A/B on a realistic task set (the internal n=1 win is Tier C in-tree) |
| T3 | Does a machine-checkable determinacy bar beat human plan-eyeballing? | Gate-on/gate-off arms measuring downstream integration failures (0/10 products have one, §6) |
| T4 | What licenses trust in a quiet verifier? | Calibration-canary catch rates, minding M4's coupling caveat |
| T5 | Is unattended window capacity actually wasted without admission machinery? | Instrumented halt/park/resume telemetry over real weeks |
| T6 | Does the cognitive-forcing card cut commission errors here, as it did in the literature? | A/B against a recommendation-first card, scored by errors caught (R3) |
| T7 | What escalation rate keeps the operator responsive? | Local tuning against ack-latency; the literature's 10–30% band does not transfer as a number (§3.3 alarm magnitudes) |
| T8 | Does a lessons store improve *anything* closed-loop? | With/without-injection paired arm; expect efficiency-not-quality (§2.3 Sandelin); measure *use*, not receipt |
| T9 | Per-lineup effort/model routing | Re-run the committed benchmark harness on each new lineup (`model-generation` decay) |
| T10 | Where does human latency actually go? | Instrument ack/decision times — operators' self-estimates are miscalibrated (§7 METR direction) |

## 5. Sequencing sketch (a plan, not a commitment)

1. **Measure first.** T1 (operator-run) and the instrumentation substrate (D14) — before any
   loop is built, the ledger that will judge it exists.
2. **The minimal loop.** Single writer + spec-authored held-out tests + sound verifiers behind a
   blocking merge gate + granted completion (D1–D5) on a small real task set, with a null arm.
3. **The human surface.** Forcing-function ratification card + tiered, acknowledged escalation +
   park-and-resume (D8, D12) — then T6/T7/T10 on live traffic.
4. **Only then, candidates for expansion**, each entering through its TBD experiment: determinacy
   preflight (T3), canaries (T4), lessons store (T8), read-fan-out (T5-informed), admission
   machinery (T5).

Nothing in stages 2–4 is exempt from R2: any mechanism whose paired arm shows the null harness
matching it gets deleted, and that deletion is a result, not a failure.
