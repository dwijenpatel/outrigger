# spec-interview — artifact notes

**v2 artifact #3b** ([design](../../../docs/design/evidence-based-harness.md) D7, built to
R5/D15). One thing well: the **clarification interview** — the interviewer acts as tech lead,
asks the operator only the product-boundary questions (a coverage checklist), derives the
craft decisions on the record, and presents a capped approval ledger before ratification —
emitting a `plan.json` (contract v1) the operator ratifies. The skill body is
[SKILL.md](SKILL.md); the machine-normative side of the contract is
[tools/plan-preflight](../../../tools/plan-preflight/README.md).

## Evidence shape (why the skill reads the way it does)

- **The interview is the lever**: spec underspecification costs tens of points; interactive
  clarification recovers most (distilled §3.1 — three independent benchmarks). Real token
  budget here.
- **But questions route by owner** (2026-07-15, Provisional —
  [elicitation-protocol-evidence](../../../docs/research/external/planning/elicitation-protocol-evidence.md)):
  the winning ask-policies are few/early/consolidated/calibrated; omission (not ambiguity) is
  the dominant requirements-defect class, so the product-boundary taxonomy runs as a coverage
  checklist (asked or sourced, never skipped); craft decisions are derived
  (conventions → precedent → general engineering principles), reversibility-tagged (one-way
  doors escalate), deviations recorded as repayment-bearing debt; the approval ledger is the
  playback pass (68% of misses surface on review), capped and reasoning-forcing against
  rubber-stamping; approve-before-effect, never post-hoc veto.
- **Plan less, never pad**: a deficient plan is net-negative vs none; planning pays on
  structured tasks and ≈0 on flat ones (§3.1) — hence task-conditional depth and the early
  stop condition.
- **Determinate seams only where work splits** (§3.2); **carve-outs surfaced explicitly**
  (D8's hard floor); **the omission sweep** before ratification, in prospective-hindsight
  framing (§3.3 silent channel; the measured premortem effect attaches to that framing —
  candidate-generator, not completeness guarantee); **no self-certification** (§3.1 — D1).

## Standalone-ness (R5/D15)

Adoption is copying this directory into any repo's `.claude/skills/`. It requires nothing
else from this repo: if `plan-preflight` is present it is run opportunistically and its
warnings shown verbatim; if absent, the skill says so and the plan is still valid output.
The execution loop (when it exists) will consume plan files via `--require-ratified` — it
will not know or care whether this skill produced them.

Deterministic invocation (`/spec-interview`) is the reliable path — skills auto-trigger with
38–69% recall (§3.1), so anything load-bearing should invoke it explicitly.

## Measurement & deletion criterion (R2)

The null arm is prompt-only planning: same goals, no interview, measure downstream rework and
integration failures (this is adjacent to design **T3**, which separately measures the
machine bar). v1 precedent: the interview surfaced ~20 decisions on its first outing and its
absence was a recorded pilot defect (P1-8). If measured usage shows interview-produced plans
doing no better than prompt-only, delete the ceremony; that deletion is a result.

**The compressed protocol's own instruments** (2026-07-15, Provisional): operator turns per
spec (pedantic baselines: 14 on the engine slice, 10 on the validator; target ≤3–4),
interview escapes per spec, blind-author failures-to-author, and the ledger challenge rate
(never-challenged across many specs ⇒ the ledger is decoration — redesign trigger). Demotion
trigger: escapes or author-failures rise under compression.

**First live run (2026-07-11, planning the held-out-suite artifact):** coverage judged right
by the operator; presentation produced three recorded defects — no self-contained briefing
before question 1, undefined shorthand throughout ("v1", "#5", "seal", "vault"), and options
lacking explicit pros/cons/tradeoffs. Fixed same-day (the briefing section, the cold-reader
standalone-readability rule, the tradeoffs requirement); recorded in the v2 ledger
(`spec-interview/live-run-1`) and as the design's D8 cold-reader rule.

**Live runs 2–3 (2026-07-14/15, the eaitl engine slice and the IR-contract validator):**
14 questions and 10 operator turns respectively, against a 25-minute unattended execution —
and a post-hoc autopsy scored ~0 of the validator interview's 7 questions as genuinely
needing the operator (the near-real one was the scope question; every craft recommendation
was accepted verbatim, answers shrinking to single letters). Operator directive + a
four-branch research pass produced the 2026-07-15 compression (the tech-lead/PM split above).

**Live run 4 (2026-07-15, the eaitl source-introspection task — first trial of the
compressed protocol):** **0 questions** (all seven coverage-checklist items sourced from the
chain design, the product draft, and ratified precedent), **2 operator turns** (vs baselines
14/10; target ≤3–4), 6-entry approval ledger, 0 entries challenged. The omission sweep did
real work: it surfaced the operator's IR-edit-model question (how humans modify a proposed
mapping plan), which produced a recorded cross-task requirement for the matcher's future spec
— the engagement channel the ledger-challenge-rate metric watches was exercised, not silent.
Operator's verdict, verbatim: "MUCH easier and less cognitively demanding than the previous
interview." Escapes and blind-author-failure counts pend the task's execution.

**Live runs 5–10 (2026-07-16, the remaining eight eaitl cascade specs — the compressed
protocol's full trial):** eight specs across six exchanges (validations, Python compiler,
TypeScript compiler, matcher singly; preview+freeze+policy and pipeline+CLI as consolidated
multi-plan exchanges). Every exchange: **0 interview questions** (all seven coverage items
asked-or-sourced) and **2 operator turns** (vs baselines 14/10). The metric that mattered:
the operator's engagement channels were exercised, not silent — run 5 produced the first
**accepted ledger challenge** (the null-semantics ruling; artifact changed
pre-ratification), run 7 a full **pre-ratification redirect** (JavaScript → TypeScript,
caught at the approval surface — the wrongly-aimed plan was superseded before any
implementation existed), and the two consolidated exchanges drew **five review questions,
every one an artifact change**: two real omission catches (the freeze's
fixing-an-approved-plan-later story; an LLM-PII follow-up that was named but recorded
nowhere) and one **rewrite of a weak recorded rationale** (no-job_id: "purity forbids" →
ids-arrive-with-persistence + equal-inputs-equal-record). Verdict so far: turns collapsed
7×, and the saved attention visibly moved to the approval surface — challenges, redirects,
and omission catches replaced clarification volleys. Escapes and blind-author-failure
counts still pend chain execution.

## Versioning

Contract **v1**, shared with plan-preflight. SKILL.md's example and preflight's schema table
are two renderings of one contract — drift is what **T11** studies; this pair is T11's first
live integration.
