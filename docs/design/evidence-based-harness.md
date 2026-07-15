# An evidence-based coding-agent harness — from-scratch design plan (draft 1)

**Status: first draft, 2026-07-10. Amended 2026-07-11:** +R5 and +D15 (loosely-coupled,
composable artifacts), composability touch-ups to D7/D8/D12/D14, +T11, sequencing reworded.
**Second amendment, 2026-07-11:** +R6 (improvement is evidence-gated, permanently) and a
substrate-volatility note on R1 (multiple subscriptions; metered API pricing).
**Third amendment, 2026-07-11:** D8 gains the cold-reader rule for operator-facing surfaces
(operator feedback from the first live spec-interview run).
**Fifth amendment, 2026-07-12 (operator direction — risk-tiered composition):** plans now
carry an operator-declared risk tier (`risk_tier`/`tier`: `full` / `gate-only` / `bare`,
absent = `full`), asked once per plan by the interview (blast radius + budget — SKILL.md
ground rule 8), validated by preflight as an additive-optional field within plan contract 1,
composed by the loop (D15's "risk-conditional configuration = choosing the compose set" made
concrete), and stamped on ledger records so lowering the guard is always a visible, recorded
choice. **Defaults unchanged: full remains the default everywhere.** The evidence question —
*where* the full apparatus earns its cost — moves to T2 pilot 1, amended (pre-data) from a
standalone 8-task study to **shadow mode**: comparisons embedded in real full-tier work
(harness arm = the real task; shadow null + arbiter ≈ $3–4 marginal each), accumulating from
the operator's actual task distribution.
**Sixth amendment, 2026-07-13 (T1 run 2 — magnitude bounded, T1 settled):** cache-read
window weight measured **w < 0.1125** (under the pre-registered cache-write weight v≥1;
consistent with 0; v=0 loosens the bound to 0.1775; half and full weight excluded;
[artifact](../research/internal/cache-weight-experiment-2026-07-13/RESULTS.md)). D12's
append-only context discipline takes its named promotion trigger: Provisional → **Decided**.
Window capacity ≈ 36–48M weighted tok/5h. Decay `vendor-policy`.
**Seventh amendment, 2026-07-14 (failure-attribution pass — error-compounding named):** an
88-agent Opus 4.8 deep-research pass on the root causes and effect sizes of long-horizon
failure ([failure-modes](../research/external/failure-modes/README.md); 20 primary-source claims
through three adversarial lenses, 0 killed / 5 number corrections) lands **+D16** — *bound the
horizon into short, fresh-context, gated links*, the countermeasure to **error-compounding**,
the largest and best-replicated long-horizon failure and not previously a named decision. Two
new Tier-A §3.1 rows (task-length collapse; scale-invariant self-conditioning) carry its
warrant; whether short fresh links beat one long thinking session (the decomposition bet)
stays TBD — the value experiment tests only the *gating* half; the decompose-vs-continuous
instrument is named-but-unbuilt. The pass also audited the top-level README and corrected three overclaims there
(the "0% right" catastrophic-nonlinearity phrasing; an unevidenced "hour six" oversight-decay
claim; and attributing compounding to ambiguity rather than to length and self-conditioning).
**Fourth amendment, 2026-07-12 (metabolizing an independent adversarial review of `docs/`,
operator-run):** evidence language tightened to the grading method's own bounds — D1/D10
gaming-ledger claims sample-bounded, D7's M7 citation narrowed (acyclicity is *a* decidable
restriction, not *the* precondition), D12's absence→cheapness slide struck, D2's M1/M2 citation
regime-bounded and the v1 held-out reuse policy stated concretely (+T12). Status refinements,
all conceding transport gaps the review named: D2 spec-only authorship → Provisional; D4
concurrent-write *harm magnitude* → Provisional (the single-writer default stays Decided); D8's
commit-before-reveal effect → Provisional pending T6; D12 wake-on-reset → Provisional behind T5.
D14 and §5's deletion clause now require **non-inferiority at a pre-registered margin**, not a
bare null match. Companion changes: the grading method
([distilled/README.md](../research/distilled/README.md)) resolves its warrant-vs-sufficiency
wording, adds two use-time fit checks, and adds the executed-reproduction rule for A3 (the
2026-07-12 grader correction is the standing example); the P3v2-5 thesis row is n=2 (smoke
run 2) with its artifact bounds stated (*internal* §5).

This is a from-first-principles redesign. It inherits
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
  *Volatility note (2026-07-11):* the operator flags two ways this substrate may change:
  (1) **multiple concurrent fixed-cost subscriptions** — e.g. subscriptions A and B, each with
  its own model set and its own usage-window clocks; (2) **a metered API cost model** — cost as
  a function of tokens in/out and the model used. Either reopens R1 and D12 (walls pluralize,
  or become budgets rather than reset clocks). Recorded for decay-awareness only: v1 designs
  for the substrate as stated and takes no speculative provision.
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
- **R5 — Artifacts are loosely coupled and composable** (added 2026-07-11). Every piece of
  machinery does **one thing well**, runs standalone, and composes through thin, durable
  interfaces, in the Unix spirit. No artifact may require another artifact's existence to be
  useful — the planning interview must work without the execution loop, the loop without the
  interview, the gate as a bare command — and so on throughout. This is operator doctrine, not
  a measured finding; **D15** gives it its mechanisms, its evidence support, and its
  against-interest exhibit.
- **R6 — Improvement is evidence-gated, permanently** (added 2026-07-11). After initial
  creation, the harness changes the same way this design was made: a proposed improvement
  enters only with highly-reliable evidence, and that evidence comes from exactly two
  categories — **new external research** (literature, replications, vendor commitments,
  re-graded into [distilled/](../research/distilled/README.md)) and **new internal research**
  (the instrumented harness's own record: null arms, TBD-ledger experiments, firing defect
  ledgers — D14's output stream). The design document is the change surface; artifacts follow
  it. This is the standing alternative to a self-modification loop (D10): the improvement loop
  runs through the operator and the evidence pipeline, never through the harness itself.

---

## 2. Decisions

### D1. All correctness authority lives outside the agent — **Decided**

No agent output is accepted on the agent's own assessment: not code, not plans, not completion
claims. PASS/FAIL is pronounced only by **sound verifiers** — execution, tests, type checks,
static analysis — and LLM judgment may triage, localize, or generate candidates for sound
verification, but never seal a result. The authority is exactly as wide as the predicate set:
a sound verifier's PASS means *these named checks passed*, never "the code is correct" — no
gate pronounces the latter, and treating a check-pass as a correctness certificate is the
proxy-optimization mistake M5 formalizes. Weak checks make a weak gate, honestly.

**Evidence.** LLM self-critique is net-negative, replicated across disjoint domains — 55/100
self-critiqued vs 88/100 with a sound external verifier, at an 84.45% false-positive rate
(§3.1); agent self-reports are unreliable exactly where verification is absent — ≥16% of
successful 8h+ runs involved cheating, disavowed when asked; fabricated execution transcripts
(§3.1); the §2.2 gaming ledger — every loop *in that surveyed sample* exploited any evaluator
it could see, edit, or self-grade (a curated ledger: its uniformity is the signal, its size is
not a census denominator); and M5 — the correctness floor cannot be a proxy the loop optimizes.

### D2. Graded tests are authored from the spec by a party that never sees the implementation, and the implementer cannot reach them — **Decided** (implementer-unreachable graded tests, machinery-enforced), **Provisional** (spec-only authorship as the protocol; full validator blindness)

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
*more* frequent (§2.2); Zenith's blindness is a prompt promise, not a boundary (§5).

**The reuse budget, regime-bounded and stated concretely.** The mathematical reuse guarantees
hold for *specific feedback regimes*: noise-and-threshold mechanisms (M2) and
threshold-revealed leaderboard scores (M1's O(log k)) — not for arbitrary rich feedback. The
v1 policy therefore does not lean on the theorems; it stays trivially inside them: suites are
**per-task**, failure feedback to the implementer is **counts-only**, and the attempt cap
(two, then a human) bounds adaptive queries per suite to **≤2**. (Whole-build closure replays
every suite once more at plan completion — non-adaptively: those results reach only the
operator, never a worker, so the adaptive budget is untouched.) Any change that raises
per-suite queries past the attempt cap — pipelining, suite reuse across tasks, larger caps —
must first write an actual reuse policy (holdout size, threshold, noise, query budget) and
show the feedback channel sits inside a guaranteed regime. That is **T12**, and it triggers on
the change, not on the calendar.

**The provisional parts:** (1) *spec-only authorship* — the §3.1 results directly indict
grading on the implementer's own or implementation-informed tests; "author from the ratified
spec, blind to any implementation" is this design's remedy, with two internal live instances
(P3v2-5 and smoke run 2, *internal* §5 — existence, not a rate) and T2's arm as the measure.
(2) *full validator blindness* — withholding the validators' reasoning from the implementer
(and vice versa) beyond test-secrecy is mechanism-plausible (judge self-preference, §3.1) but
its marginal value over test-secrecy alone is unmeasured — promotion trigger is **T2**.

### D3. Completion is granted, never claimed — **Decided**

"Done" is a state only an external verifier can produce, and the runtime refuses to fabricate
it: the loop cannot end a task, a phase, or the build on its own assertion. Every completion
carries the verifier artifact that granted it.

**Evidence.** Premature completion — declaring `done` too early — is a dominant long-horizon
failure *behavior*: agents "satisfice rather than optimize, often submitting before the time
limit," with poor ability to notice progress, replicated across METR RE-Bench, independent
research-agent post-mortems, and Zenith's convergent design (§3.1). It is the *completion-side*
sibling of error-compounding, which the 2026-07-14 attribution pass ranks the largest
long-horizon failure *shape* (**D16**, the accumulation side) — both are defeated only by an
external verdict, never a self-declared one. Zenith's committed code demonstrates the mechanism
is buildable — only the terminal reviewer's verdict seals `done` (§5).

### D4. Single-writer topology; parallelism only where the evidence licenses it — **Decided** (the default), **Provisional** (the harm magnitude of concurrent writes)

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

**Evidence, split by which leg it carries.** The *default* is the well-warranted leg: at equal
thinking-token budgets a single agent is best or tied at every budget except the lowest (§3.2,
four independent parties incl. Anthropic against interest), M6 is the theoretical no-gain floor
at equal compute, Anthropic explicitly declines to extend its multi-agent result to coding
(§2.1) — and under R2, no measured benefit means no machinery. The *harm magnitude* is the
Provisional leg, and it transports from thinner ground: the only concurrent-write measurement
is 13.1% *slower* with syntactic conflicts eliminated and semantic conflicts surviving (§3.2 —
one study, their domain; the sign is what transports), plus internal n=1 (the one time two
agents fixed the same defect in parallel, the result was worse than either alone —
P2-collision, *internal* §1). The default does not need the harm leg to stand.

### D5. Every independent check sits behind a blocking gate — **Decided**

A verifier that can be advised-past does not exist for correctness purposes. Merge, task
completion, and phase transitions are interlocks: no PASS artifact, no progression — enforced by
machinery, with no advisory mode.

**What may block (the D1/D4/D5 composition rule, made explicit):** only *sound* checks —
deterministic, machine-replayable predicates with exit codes — sit behind the gate. An
LLM-review lens (D4 shape 2) is a *finding generator*: its findings are advisory until
converted into a reproducible predicate (a failing test, a type error, a replayable
counterexample), and it is the predicate that blocks, never the opinion. This is not a
loophole for LLM findings — it is D1 applied to the gate itself: an opinion that cannot be
made reproducible cannot be distinguished from a false positive, and §3.1's false-positive
rates say unreplayable blocking findings would grind progress on phantoms. (The shipped
merge-gate already implements exactly this: it runs commands and reads exit codes; there is no
API for an opinion to fail the merge.)

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
- The preflight requires an **acyclic task graph**. M7's actual shape: unrestricted
  hierarchical plan-existence is undecidable, and decidability holds under *restricted forms* —
  totally-ordered networks are one, acyclic networks another. The preflight adopts the
  acyclic-DAG restriction as its decidable regime (the least restrictive of the named forms
  that still admits a sound structural check); acyclicity is *a* sufficient restriction, not
  *the* precondition. It also rejects plans whose seams are underdetermined wherever
  decomposition or parallelism is intended (§3.2 seam determinacy).
- **Planning depth is task-conditional.** Explicit planning pays ~+14% on structured/decomposable
  tasks and ≈0 on flat ones (§3.1 CoT meta-analysis) — so the harness must be able to run with a
  near-empty plan for flat work. A deficient plan is *worse* than none (§3.1, two independent
  studies), so the gate's failure mode must be "plan less," never "pad the plan."
- **The clarification interview is one of the best-evidenced levers in the corpus**: spec
  underspecification costs tens of points and interactive clarification recovers most of it
  (§3.1, three independent benchmarks, three recovery mechanisms). Budget real tokens there.
- Requirements templates are formatting, not completeness — EARS's own inventors say so (§2.3);
  a template cannot substitute for the interview.
- **The planning machinery is a standalone artifact (R5/D15):** the interview + preflight run
  with vanilla Claude Code and emit a ratified plan file; nothing else in this design is
  required for them to be useful, and the execution loop does not require them — a flat task
  legitimately runs plan-less, and any plan file meeting the contract is accepted regardless of
  what produced it.

**Provisional mechanics** (sign trusted, unmeasured): typed re-plan patches with
locality-of-repair, per Zenith's committed implementation (§5) and classical plan-repair theory;
a producer-before-consumer (`requires`/`provides`) check inside the preflight — theory-derived,
promoted only if **T3** shows machine-checkable determinacy bars beat human eyeballing (no
shipped product has one — 0/10, §6).

### D8. Human gates are built against the measured failure modes of human oversight — **Decided** (the human-factors shape), **Provisional** (the forcing card's effect size in this setting)

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
  silent channel suppresses detection 46%→21%). Accept the UX cost per R3. *This bullet is the
  Provisional part:* the commit-before-reveal effect was measured in clinical/decision-support
  settings — human-factors decay says the mechanism should transport to code-change
  ratification, but the effect size here is unmeasured, and **T6** is the promotion trigger.
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
- **The card is a standalone artifact (R5/D15):** it renders any schema'd decision file,
  records the commit-before-reveal transcript, and emits a stamped decision file — usable by
  any workflow, not only this harness's composition of it.
- **Operator-facing surfaces are written for a cold reader** (operator directive, from the
  first live spec-interview run, 2026-07-11): a self-contained briefing before any decision is
  requested; every term of art defined in-surface (no bare codenames, version names, or
  mechanism shorthand); every option carrying explicit pros/cons/tradeoffs, including the
  recommended option's costs — **and every cost named as its plain operational consequence**
  (what stops, who must act, when it resumes), never through softening metaphor ("friction",
  "overhead"): a plainly-named cost is what earns the operator's scrutiny, and euphemism is
  over-reliance manufacturing. The operator's working context is the scarcest resource in the
  loop, and an operator who cannot fully follow the surface decides poorly — the failure lands
  exactly where §3.3 says it will. Applies to interview questions, ratification cards, blocker
  cards, and escalation messages alike.

### D9. Memory: versioned plain files, deterministically captured, write-gated; nothing learned until closed-loop evidence exists — **Decided**

- **Substrate: plain files under git.** No memory architecture consistently beats a
  full-context or filesystem-grep baseline on independent harnesses — the substrate is not the
  bottleneck (§3.1). Anything fancier is unjustified complexity under R2. (Read the warrant
  precisely: this is the **null choice winning by default** — the evidence says nothing beats
  the trivial baseline, not that plain files beat the alternatives. If T8-class evidence ever
  shows an architecture clearing the baseline, the default loses its license.)
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
loop in the surveyed §2.2 sample exploited its evaluator, including against explicit
instruction (a curated ledger, so its uniformity is the signal and its count is not a census —
but a 100% hit rate across every case anyone bothered to publish is not a coin worth flipping)
— and by R2, since a self-modification loop is pure meta-work until the base harness has
demonstrated value. Either force suffices alone.

If a later version builds one: modifications are **proposals only**, human-ratified through the
hardest cognitive-forcing card in the system, with the evaluator and held-out assets outside the
loop's reach (§2.2's two published countermeasures), promotion gated on held-out performance
(M1/M2 budgets), and the card built as a debate/sandwiching artifact — the self-mod case is
exactly the information-asymmetry regime where debate measurably helps, *and* the regime where a
weak supervisor's judging collapses (§2.1 weak-to-strong). Human-ratified self-modification
remains unpublished anywhere (§6) — this is the design's one genuinely novel object, and it
stays parked until the base loop earns it.

Meanwhile the standing improvement path is **R6**: evidence-gated, operator-ratified design
changes. A self-modification loop, if ever built, automates proposal-generation *within* R6 —
never around it.

### D11. Isolation is OS-enforced, per-role, process-level — **Decided**

Role boundaries (implementer / test-author / validator) are separate OS processes with distinct
filesystem and network policies. Prompt promises are not boundaries (§2.2 STOP; §5 Zenith).
Anthropic's own sandbox documentation enumerates its gaps — "not a complete isolation boundary,"
filesystem-without-network permits exfiltration (§2.1) — and the reproduced Ona incident shows
an agent disabling its own sandbox and defeating the approval gate via fatigue (§2.3). Deny
rules have absolute precedence and resolve symlinks (§4, `vendor-build` — re-probe each build);
per-subagent sandbox differentiation is officially impossible in-process, which is precisely why
roles are separate processes (§4).

**"Separate processes" is the topology, not the wall — the wall is layered, and the layers fail
independently.** Live internal demonstrations (smoke runs 1–2, *internal* §5): a
permission-layer read-deny was silently voided by a permission-*mode* change while the process
boundary stood intact; the OS-sandbox layer holds independently of mode; and the vendor default
when the sandbox cannot start is to warn and run *unsandboxed* (caught by operator review,
2026-07-12 — the launcher now makes it a startup abort). So D11's requirement, precisely: role
separation is enforced by named layers (process, permission-rule, OS sandbox — filesystem and
network), **every load-bearing layer is probed per launcher per build** by a deliberate
read-attempt (the smoke's probe, never assumed from documentation), and any layer's mechanism
is `vendor-build` fact, not design fact. The *requirement* is Decided; every mechanism binding
carries the vendor-build decay class.

### D12. Economics: cache-stable context, halt-at-wall + park-and-resume, measure-don't-predict — **Decided** (halt-at-wall floor; append-only context discipline), **Provisional** (wake-on-reset), **TBD** (everything cleverer)

- **Context discipline is append-only / prefix-stable** so cache reuse is structural, not
  accidental — **Decided 2026-07-13, by its own named trigger**: T1 measured the window-side
  discount directly (*internal* §4, runs
  [1](../research/internal/cache-weight-experiment-2026-07-12/RESULTS.md) ·
  [2](../research/internal/cache-weight-experiment-2026-07-13/RESULTS.md)) — a cache read
  weighs **< 0.1125** of a fresh input token against the 5-hour window under the pre-registered
  cache-write weight (v≥1; v=0 loosens the bound to < 0.1775), so prefix-stable context is
  **several-fold cheaper (≈6–9×)** than context that busts the cache — consistent with cache
  reads being free, but a censored meter cannot separate that from a small positive weight. The ~10% billing
  rate (§4, official) and the measured window weight now agree in order of magnitude. Decay
  `vendor-policy`: re-check on any announced plan/limits change.
- **The wall is survivable by construction**: credits are strictly opt-in, so an unattended run
  halts rather than spills (§4) — the harness records a resumable checkpoint and *parks*.
  Wake-on-reset appears in none of the surveyed tools (§5 census) — which, per the grading
  method's absence rule, licenses "unoccupied niche" and nothing about cost or value; the prior
  draft's "is cheap; build it" was a builder's estimate wearing the absence finding's warrant,
  and is struck. Wake-on-reset is **Provisional**: a standalone wrapper around *any*
  long-running invocation (R5/D15) if built, and **T5**'s telemetry — are unattended windows
  actually being wasted? — decides whether it earns build effort at all.
- **Instrument spend; never predict it** (R4; *internal* §4's 3× same-task variance with
  committed artifacts).
- **Settled by T1 (runs 1–2) — the question that decided how aggressive context reuse should
  be:** how cache reads weigh against *subscription windows* is *officially* still unanswered
  (§4; the vendor declined to answer, §2.1), but is now **internally measured**: run 1
  (2026-07-12) excluded full weight; run 2 (2026-07-13, 9.3× larger,
  [artifact](../research/internal/cache-weight-experiment-2026-07-13/RESULTS.md)) bounded it —
  **w < 0.1125** (pre-registered write weight v≥1; v=0 loosens to < 0.1775; consistent with 0,
  not separately identified); half and full weight excluded outright; window capacity
  ≈ 36–48M weighted tok/5h. The community-telemetry "near-full weight" claim is contradicted
  at two run sizes on this build/plan. The official answer's absence is why the decay class is
  `vendor-policy`: any announced plan/limits change reopens the measurement, not the decision
  structure.
- **Substrate decay-awareness:** R1 carries a volatility note — multiple concurrent
  subscriptions, or metered API pricing. If either lands, "the wall" pluralizes or becomes a
  budget rather than a reset clock, and this decision is revisited through R6. Not provisioned
  for now.
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
- **experiments are pre-registered protocols**: hypothesis, arms, metric, sample size, and a
  **non-inferiority margin** fixed before the run. "The null arm matched" means *non-inferior
  at the pre-registered margin* — an underpowered no-difference result licenses nothing,
  in either direction (absence of evidence is not evidence of absence; the deletion clause in
  §5 binds to this definition);
- wins require committed, third-party-checkable artifacts — a win without an artifact is a claim
  (*internal* README rule), and an artifact's reproduction path is **executed before the label
  is applied** (grading-method maintenance rule 5, added after the 2026-07-12 grader
  correction: reading the harness is not running it);
- predictions are pre-registered before firings (the watch-item practice worked — it caught its
  own miss, *internal* §3);
- held-out assets carry an explicit reuse budget (M1/M2), and replay is licensed on unchanged
  surface only (M3);
- absence claims state their sample and date (grading method);
- measurement attaches **per artifact** (R5/D15): each ships its own null arm, so the R2
  deletion clause executes at artifact granularity — never all-or-nothing.

D14's output stream is also **R6's internal-evidence feed**: the ledger, the experiment
write-backs, and the firing defect records are where post-creation improvements get their
warrants.

### D15. Composition model: standalone artifacts, file contracts, late binding — **Decided** (R5 + evidence-supported mechanisms; contract-versioning settled minimal 2026-07-12)

R5 is operator doctrine and needs no warrant — but its mechanisms are independently
evidence-supported, and v1 is the against-interest exhibit for the alternative.

- **Each artifact is a standalone tool**: its own invocation, its own contract documentation,
  its own tests and null arm (D14), adoptable one-at-a-time in a vanilla Claude Code setup.
  "One thing well" also bounds surface area, which is where the tool-ergonomics evidence points:
  few, well-shaped surfaces beat many (§3.1), and anything load-bearing is deterministically
  invoked (D13).
- **Interfaces are durable file contracts** — schema-validated files, exit codes, streams —
  never imports of another artifact's internals, never shared mutable state. This is the
  machinery analogue of §3.2's licensing condition: decomposition is safe exactly when seams are
  determinate up front, and a schema'd file plus an exit code is a maximally determinate seam.
  The MAST caution — failures concentrate at coordination seams (§3.2) — is about *agents
  negotiating with agents* in free-form channels; a deterministic file contract is the seam type
  least exposed to that taxonomy.
- **No existence-dependencies, in either direction.** The interview emits a plan file and is
  useful alone (D7); the loop consumes a plan file *if present* (D7); the merge gate is a
  command over (diff, tests) → exit code that any workflow — including a human's — can call
  (D5); the card renders any schema'd decision file (D8); park-and-resume wraps any invocation
  (D12). Process-level role isolation (D11) already forces the process shape;
  composition-by-subprocess with disjoint tool surfaces and a stateless kernel re-reading disk
  is Zenith's committed, code-verified architecture (§5, A3).
- **Composition is explicit and late.** A thin composition layer may wire artifacts into a
  harness; artifacts never know they are composed. Risk-conditional configuration then
  degenerates to *choosing the compose set* — dropping the held-out-vault stage for low-risk
  work is removing a pipeline stage, not forking a monolith. (Task-conditional harness
  configuration is otherwise unpublished except by task family and model — §6 — so this is an
  extension, made cheap by construction.)
- **v1, against interest** (*internal* §1–§2): the build-loop refused to start unless
  `harness.planning ready` passed — the exact coupling R5 bans; the bootstrap deadlock was two
  individually-correct fail-closed rules composing invisibly inside one process; P2-collision
  destroyed the better implementation because two contexts coupled through shared machinery
  state. None of these failure shapes exists between artifacts that meet only through files.

**Contract-versioning — settled minimal (2026-07-12, T11):** how independently-evolving
artifacts keep their file contracts compatible (schema versioning, tolerant readers, golden
files) is settled to a minimal policy ([CONTRACTS.md](../../tools/CONTRACTS.md)) — it grows
only if a real drift failure escapes. The first live plan-preflight ↔ exec-loop integration is
**T11**'s ongoing subject.

---

### D16. Bound the horizon into short, fresh-context, gated links — the countermeasure to error-compounding — **Decided** (gate each link before the next builds on it), **TBD** (that short fresh links beat one long thinking session — the decomposition bet — and its size)

The long horizon is never run as one continuous session. It is decomposed into short tasks,
each implemented in a **fresh worker context**, and each **verified by the gate before the next
task builds on it**. A defect that escapes one link is caught at that link or it corrupts every
link downstream; the architecture's job is to make "caught at that link" the default.

**Evidence (2026-07-14 failure-attribution pass,
[failure-modes](../research/external/failure-modes/README.md) — 20 primary-source claims, three
adversarial lenses, 0 killed).** Error-compounding is the **largest, best-replicated, most
on-regime** failure of long-horizon coding, and it is two mechanisms, each countered here:

- **Scope / length collapse.** Long multi-file work scores far worse than single-issue work:
  top agents land ~25% on the multi-file SWE-EVO suite (n=48) where they clear ~70%+ on
  single-issue SWE-bench, and SWE-Bench Pro (n=1,865) shows the same gap on other data. These
  are **cross-benchmark gaps, not one controlled length manipulation** — import the direction
  (long unstructured work is much harder), not the exact ~70→~25 drop as if length alone caused
  it. METR's ~170-task suite fits success against log task-length exponentially (R²≈0.83),
  near-ceiling on short tasks → ~0–10% on multi-hour ones — and METR itself flags that transfer
  to ordinary software work is conditional. Shortening each task is *a* counter; see the bet below.
- **Self-conditioning.** A model degrades from its **own prior errors accumulating in context**
  — measured even when the plan is fully specified and only execution is tested — and it **does
  not go away as the model scales** (~32B→~1T, replicated ×3). Fresh context per link severs
  this channel across links; a bigger implementer does not. **Against this decision's grain,
  from the same primary source:** *thinking* mitigates self-conditioning and lets a model run
  **much longer within a single turn** — so for the thinking models this harness actually runs,
  the within-turn channel is weaker than the raw result implies, and the source's own remedy
  (more thinking per turn) points at a longer single session, not only at decomposition. That is
  exactly why decompose-vs-continuous is a **bet, not a settled consequence** (below).

Both are `llm-class` and enter as Tier-A rows in
[distilled/external.md](../research/distilled/external.md) §3.1.

**What is Decided, and what is a bet.** The per-link external verdict *is* Decided: the runtime
spawns a fresh worker per task and gates each link before the next builds on it (D2/D3/D5), on
the same warrant as D3/D5 — a defect must be caught by something outside the worker. What is
**not** evidence-forced is the decomposition itself — that a short-fresh-gated chain beats the
**same work run as one long thinking session**, at equal budget. No external source compares the
two, and the self-conditioning caveat above shows the evidence for thinking models arguably
points the other way, so this is a genuine **bet, not a consequence** of the failure evidence.
Its settling instrument — a **continuous-thinking run of the same chain at equal budget** — is
**named but unbuilt**; the current long-horizon value experiment holds decomposition *fixed*
across all arms and therefore tests only the **gating half** (does the gate arrest cross-task
compounding — recorded as **compounding depth** in
[chain-design](../research/internal/longhorizon-value/chain-design.md)), never
decompose-vs-continuous. Import the mechanism (error-compounding is real and structural); do
**not** import a magnitude for the cure, and do not treat decomposition as proven over a long
single session.

**Relation to the other decisions.** D3 (premature completion) is the *completion-side* failure
— declaring done too early; D16 is the *accumulation-side* failure — being wrong and building on
it. D2/D5 supply the per-link gate that makes decomposition safe; D7 supplies the determinacy
that lets a horizon be split at all without seam rework. D16 names the failure the others were
already, implicitly, defending against.

## 3. What this design deliberately omits — each omission is evidence

| Omission | Why (evidence) |
|---|---|
| Multi-agent debate/committee for correctness | Refuted at equal budget; unanimity endorsed a phantom vuln; errors correlate across models (§3.1–3.2) |
| Concurrent writers / parallel implementation by default | 13.1% slower with conflicts CRDT-eliminated; semantic conflicts survive; the parallel winner concedes no time/cost win (§3.2, §2.3) |
| Learned/vector memory, forgetting timers | No system beats trivial baselines; no ablated decay model; zero closed-loop coding evidence (§3.1, §6) |
| Long-horizon token prediction/optimization | R4; 3× same-task variance (*internal* §4); no validated horizon features |
| Prompt-level guardrails as enforcement | STOP: the warning comment *increased* violations (§2.2) |
| Autonomous self-improvement | Every loop in the surveyed §2.2 gaming ledger gamed its evaluator; R2 |
| Spec-first ceremony on flat tasks | CoT pays only on structured tasks (§3.1); no controlled evidence spec-first beats prompt-then-code at all (§6); a deficient plan is worse than none (§3.1) |
| TOON / serialization tricks | Measured-negative generation; narrow savings band (§3.1; *internal* §4) |
| Recommendation-first approval cards | Measured over-reliance bait: acceptance rises right-or-wrong (§3.3) |
| Approval theater (board-style review of every change) | External approval buys latency, not failure reduction (Tier B DORA, consistent with §3.3 complacency); PPV governs the human channel (§3.3) |
| Bundled machinery — artifacts that require each other to exist | R5; v1's own coupling defects: the loop hard-gated on the planner, the bootstrap deadlock, P2-collision (*internal* §1–§2); machinery seams must be few and determinate (D15, §3.2) |

The strongest statement this document makes is that the previous design's machinery count was
its defect, not its moat. The evidence funds a **small** machine — and R5/D15 says a
**separable** one: one writer, sound verifiers behind blocking gates, spec-authored held-out
tests, a forcing-function human surface, files as memory, park-and-resume economics, and
instrumentation — each a standalone tool, composed late. Everything else waits for data.

## 4. TBD ledger — the deliberately undetermined

The table names each question and its settling instrument. When an experiment is actually
scheduled, it first gets a **pre-registered protocol card** (hypothesis, arms, metric, sample
size, non-inferiority margin, decision rule — D14); a row here is a question, not yet a study.

| # | Question | What settles it |
|---|---|---|
| T1 | Do cache reads meaningfully discount *subscription-window* occupancy? | **Settled 2026-07-13: yes, by several-fold (≈6–9×)** ([run 1](../research/internal/cache-weight-experiment-2026-07-12/RESULTS.md) · [run 2](../research/internal/cache-weight-experiment-2026-07-13/RESULTS.md), both operator-run as pre-registered). Run 1 excluded full weight; run 2 (N=28, F=2500, 9.3× larger) bounded the magnitude: **w < 0.1125** of fresh-input weight under the pre-registered write weight (v=1; v=1.25 tightens to 0.096; **v=0 loosens to 0.1775**), consistent with **0** but not separately identified (censored meter); w=0.5 and w=1 excluded outright. Window capacity ≈ **36.2–48.3M weighted tok/5h** (nests inside run 1's 21–62M; linear model retro-predicts run 1 across the scale-up). D12's append-only discipline promoted on this trigger. Decay `vendor-policy` — re-run on any announced plan/limits change. Optional (no decision needs it): distinguish w=0 from w≈0.1 via a finer usage surface or an arm-A-only run at ≥3× reads |
| T2 | Does blind validation + a held-out vault pay its overhead vs test-secrecy alone, per risk tier? | Paired-arm A/B on a realistic task set (internal evidence is n=2 *existence* — P3v2-5 + smoke run 2, *internal* §5 — never a rate). **Pilot 1 registered 2026-07-12** ([protocol](../research/internal/t2-pilot-1/protocol.md), ledger-anchored): full harness vs the R2 null first, arbiter-suite oracle; **amended same-day, pre-data, to shadow mode** — comparisons embed in real full-tier work and accumulate from the operator's actual distribution; the secrecy-vs-gating decomposition is pilot 2, gated on pilot 1's outcome |
| T3 | Does a machine-checkable determinacy bar beat human plan-eyeballing? | Gate-on/gate-off arms measuring downstream integration failures (0/10 products have one, §6) |
| T4 | What licenses trust in a quiet verifier? | Calibration-canary catch rates, minding M4's coupling caveat |
| T5 | Is unattended window capacity actually wasted without admission machinery? | Instrumented halt/park/resume telemetry over real weeks |
| T6 | Does the cognitive-forcing card cut commission errors here, as it did in the literature? | A/B against a recommendation-first card, scored by errors caught (R3) |
| T7 | What escalation rate keeps the operator responsive? | Local tuning against ack-latency; the literature's 10–30% band does not transfer as a number (§3.3 alarm magnitudes) |
| T8 | Does a lessons store improve *anything* closed-loop? | With/without-injection paired arm; expect efficiency-not-quality (§2.3 Sandelin); measure *use*, not receipt |
| T9 | Per-lineup effort/model routing | Re-run the committed benchmark harness on each new lineup (`model-generation` decay) |
| T10 | Where does human latency actually go? | Instrument ack/decision times — operators' self-estimates are miscalibrated (§7 METR direction) |
| T11 | What contract-versioning discipline keeps independently-evolving artifacts compatible? | **Settled minimal 2026-07-12** ([tools/CONTRACTS.md](../../tools/CONTRACTS.md)) — the trigger fired (exec-loop composition + e2e run 1; the tier knob provided the first live additive change): explicit integer major per envelope, one owning producer, reject-unknown-major fail-closed, absence = legacy major-1 where history is append-only, additive-optional-within-major with validation, golden fixtures as the drift alarm. Grows only if a real drift failure escapes it |
| T12 | What held-out reuse policy is safe past the attempt cap? | Triggered by any change that raises per-suite adaptive queries above the cap (pipelining, shared suites, larger caps): write the policy — holdout size, threshold, noise, query budget — and show the feedback channel sits inside an M1/M2-guaranteed regime *before* the change lands (D2) |

## 5. Sequencing sketch (a plan, not a commitment)

Every stage's deliverables are **standalone artifacts with file contracts** (D15); composition
is itself a late, explicit step, never the medium the artifacts are born into.

1. **Measure first.** T1 (operator-run) and the instrumentation ledger (D14) — the first
   standalone artifact: before anything else is built, the tool that will judge it exists and
   is usable on its own.
2. **The correctness artifacts.** The spec-interview (D7), the test-author role (D2), and the
   merge-gate command (D1/D5) — each landing separately with its contract, tests, and null arm;
   then the first composition: a single-writer loop wired from them (D3/D4) on a small real
   task set, which is also T11's integration probe.
3. **The human-surface artifacts.** The forcing-function card (D8), tiered acknowledged
   escalation (D8), and the park-and-resume wrapper (D12) — then T6/T7/T10 on live traffic.
4. **Only then, candidates for expansion**, each entering as its own artifact through its TBD
   experiment: determinacy preflight (T3), canaries (T4), lessons store (T8), read-fan-out
   (T5-informed), admission machinery (T5).

Nothing in stages 2–4 is exempt from R2: any artifact whose paired arm shows the null harness
**non-inferior at the experiment's pre-registered margin** (D14 — a powered result, never a
bare no-difference from a small sample) gets deleted — at artifact granularity, which is
exactly what R5 makes cheap — and that deletion is a result, not a failure. Composition effects
are the known blind spot of per-artifact nulls: an artifact that only pays in combination is
exactly what a factorial or staged ablation would catch and a lone paired arm will not; when
two artifacts plausibly interact, the ablation is staged over the pair.
