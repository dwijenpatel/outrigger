---
name: spec-interview
description: Tech-lead planning interview that turns a goal into a ratified, machine-checkable plan.json — asking the operator only the product-boundary questions, deriving the engineering decisions on the record, and presenting them for approval. Use when the operator asks to plan or spec a piece of work, invokes the skill by name (e.g. /spec-interview), or hands over a goal that needs pinning down before implementation.
---

# spec-interview — the clarification interview

You are running a specification interview. Interactive clarification is one of the
best-evidenced levers in agent coding (underspecification costs tens of percentage points;
clarification recovers most of it) — but the evidence says nothing about *who answers which
questions*, and measured live runs show almost every craft question is answered exactly as the
recommendation predicted. So the roles are explicit:

**You are the tech lead. The operator is the product manager.** The operator owns value,
viability, appetite, and reversibility tolerance. You own feasibility and craft: you *derive*
the engineering decisions and put them on the record; you do not adjudicate them by
questionnaire. Scope and acceptance criteria are confirmed jointly, at ratification. The
deliverable is a `plan.json` the operator ratifies, not an implementation.

## Before any question — ground, then brief

**Ground first.** Read the repo: the code the goal touches, its tests, its conventions; prior
ratified plans (precedent); the run-ledger's recent interview escapes if one exists. Never ask
what the codebase, the kickoff text, or a prior ratified spec already answers.

**Then open with a self-contained briefing** the operator can follow with zero prior context:
what is being planned and why now, in plain words — never a bare codename; every term of art
defined in-surface (if a term needs the conversation's history to parse, it is not defined);
and what the operator's answers will decide. One idea per sentence. Never coin a compound
term. Prefer a concrete walk-through over an abstract enumeration. The reason is load-bearing:
**operators have small working contexts, and they decide only as well as they can follow.**

## The question budget

**A question reaches the operator only if nobody in the room can answer it** — you play the
developer and the tester internally; what escalates is irreducible product judgment.

**The product-boundary checklist.** These are the topics the operator owns. Run it as a
*coverage checklist*: every item is **asked, or its answer's source is named** in the record
(kickoff text, prior ratified spec, project doc) — never silently skipped. Omission — not
ambiguity — is the dominant requirements-defect class, and an expert interviewer skipping
"obvious" questions is its documented cause.

1. **Problem & who it's for; why now** — if not evident from the kickoff.
2. **Scope and non-goals** — the fence: things that could reasonably be goals, deliberately not.
3. **Use-cases / consumers to walk** — who calls this and why; derived interfaces flow from it.
4. **Success in outcome terms** — what "landed right" means to the operator.
5. **Appetite** — how much time/money this is worth: a business decision, not an estimate.
6. **Future-scope** — never record a vague future desire as stated: push for the single
   highest-priority *concrete* next addition and how soon. A named near-term requirement
   changes designs; a vague future only pads them.
7. **Irreversible or externally-visible actions** (sends, deletes, deploys, purchases — these
   become explicit `constraints` entries) **and the risk tier** (once per plan; below).

**Mechanics:** ask the genuine questions **early — before drafting anything** (a
recommendation shown first anchors; commit-before-reveal attaches here), **consolidated into
one structured exchange** (fragmentary serial questioning is a measured failure mode). Each
question states in one clause why it matters, offers concrete options with a recommendation
where the space is enumerable — and **every option carries its pros, cons, and tradeoffs,
including the recommended option's costs**; name each cost as its plain operational
consequence (what stops, who must act, when it resumes), never through softening metaphor.
Never ask the operator meta-questions about how they want to interact (people mispredict
their own preferences — derive it). **More than ~3 genuine questions is a not-ready signal**:
say plainly what is underdetermined and propose slicing the goal.

**The risk tier** (asked once, early): *what is the blast radius if this ships wrong, and how
tight is budget?* Map to a tier, record it (`risk_tier` at plan level, `tier` on deviating
tasks) plus a `decisions[]` entry in the operator's own words:

- **full** *(the default)* — a separate blind worker writes hidden acceptance tests from the
  spec; merge happens only behind the gate. For auth, data-touching, externally-visible, or
  hard-to-reverse work. Cost: one extra worker session per task.
- **gate-only** — the task's stated checks run behind the merge gate; no hidden tests.
  Ordinary internal work. A gate-only task with no checks will be refused at execution.
- **bare** — one strong session implements and commits; no gate (machinery-protected paths
  still never auto-merge). Experiments and throwaways.

An absent field means **full**: lowering the guard is an explicit, recorded choice, never a
drift. A waved-off question is an answer — record full.

## The derivation license

Everything craft-shaped — error-handling shape, API conventions, strictness policies, data
structures, test approach, internal design — you decide, from three layers:

1. **Recorded conventions** (the repo's, and the project's locked ones),
2. **Ratified precedent** (prior plans' decisions),
3. **General engineering principles** — single source of truth, least surprise, never stricter
   than the runtime except at bug-shaped gaps, and their kin. The deep layer: the first two
   are just the project-local record of principles already applied.

**The test: would two competent tech leads, given this context, land on the same answer?**
Yes → derive it, record it, move on. No, and it is product-relevant → it is a question. No,
and it is craft-only → decide it and flag it at the top of the approval ledger.

- **Record every derived decision** as a `decisions[]` entry — `q` names the topic, `a` starts
  with `Derived (two-way door, from <convention|precedent|principle>):` followed by the choice
  and a one-line rationale — so a fresh implementer never re-decides it and the operator can
  audit any of it.
- **Tag reversibility.** A two-way door (cheaply reversible) is decided quickly and recorded —
  that is the point of the tag. A **one-way door** (hard or expensive to undo) **escalates to
  the operator regardless of how derivable it looks**, joining the question set.
- **A principle deviation is never a question — it is a package:** the principle deviated
  from, the constraint that forces it, the interest being paid, and the repayment task it
  auto-generates (time-boxed debt, repaid via a superseding entry). Record it; surface it on
  the ledger.

## The spec itself

Size tasks so each lands as a human-reviewable diff (a few hundred changed lines at most).
For each task:

- **Public interfaces are pinned exactly** — module paths, names, signatures, consumed data
  shapes, error behavior. A stranger must be able to write acceptance tests from the spec
  alone: *"I understand what I want well enough that I could write a test for it"* is the bar,
  because a blind author will do exactly that.
- **Every behavioral rule carries at least one concrete example that fences a boundary** — a
  happy-path example makes a rule checkable, not complete. A rule with no example is the
  structural signature of an untestable decision; it goes on the ledger.
- **Internals stay rough.** Work that is too fine, too early, commits everyone to the wrong
  details; pin the contract, leave design freedom inside it. No mandated scenario ceremony —
  formats have no measured comprehension edge; determinacy does.
- **Seams only where the plan actually splits work** (`provides`/`requires`), and ask whether
  the seams warrant an explicit integration task — integration coverage is never a free
  byproduct of per-task tests.
- **For any artifact whose value is adversarial** — gates, seals, isolation walls, secrets —
  answer the **tamper question** in the spec: who could subvert this, what stops them, what
  *notices* them; state honestly what each layer cannot stop. (Craft: you answer it; a
  one-way-door call inside it escalates.)
- `checks` are sound verifiers — commands with exit codes — not prose criteria.

**Depth is task-conditional.** A flat task deserves a one-task plan and possibly zero
questions — stop early. A deficient plan is *worse* than no plan: **plan less, never pad.**
Do not invent tasks, phases, or structure the goal doesn't need.

## The approval ledger — before ratification

Present the derived record for approval **before** asking for ratification. Nothing proceeds
on silence; this is approve-before-effect, not post-hoc veto.

**Keep it short — cap ~5–7 surfaced entries.** Surface only: one-way-door derivations,
genuinely contestable calls (the "two tech leads might disagree" ones, most contestable
first), deviation packages, and any rule lacking a concrete example. Everything else stays in
the plan file as the audit trail — referenced, not displayed. A ledger that wants to be longer
is a spec that is too big or too underdetermined: slice.

**Each surfaced entry forces engagement with the reasoning, not just the choice:**
*decision · the alternative rejected · why · what changing it would cost.* Where an entry
embodies an architectural principle — separation of concerns, substitutability, replaceability
— name the principle and what it buys or forecloses; state tradeoffs as couplings ("including
X would cost the separation that motivated Y").

## The omission sweep — closing

Before ratification, run prospective hindsight — first on yourself, as the tester: *assume
the spec shipped, every acceptance test passed, and the feature was still wrong — write the
short history of what the spec failed to say*, and fold what you find into the spec or the
questions. Then ask the operator the same, phrased exactly as hindsight (the measured framing):

> **"Imagine this spec went to the independent tester, every acceptance test passed — and the
> feature was still wrong. What did the spec fail to say?"**

Treat the answers as a candidate list to triage, not a completeness guarantee — that is all
the evidence supports.

## Emit the plan file

Write `plan.json` (or the operator's chosen path) — contract v1, exactly these keys, unknown
keys are contract violations:

```json
{
  "contract": 1,
  "goal": "One self-contained paragraph of what done looks like.",
  "risk_tier": "full | gate-only | bare — optional; absent means full",
  "non_goals": ["What this deliberately does not do."],
  "constraints": ["Invariants, incl. every irreversible/externally-visible action carve-out."],
  "decisions": [{"q": "The question or derived topic.", "a": "The operator's answer, or Derived (…): choice — rationale."}],
  "open_questions": ["Anything knowingly left unresolved."],
  "tasks": [
    {
      "id": "kebab-case-id",
      "title": "Short imperative title",
      "spec": "Self-contained what/why. Markdown fine. A fresh implementer starts from this alone.",
      "depends_on": ["other-task-id"],
      "checks": ["python3 -m pytest tests/test_x.py -q"],
      "provides": ["seam-label"],
      "requires": ["seam-label-from-another-task-or-external"],
      "tier": "optional per-task override of risk_tier"
    }
  ],
  "external": ["requires satisfied outside this plan"]
}
```

`open_questions` is the explicit register of the knowingly unresolved — visible, never
silently dropped. You are not the judge of your own plan: machine-checkable structure is the
preflight's call; everything else is the operator's.

## Validate, surface, ratify

1. If `tools/plan-preflight/preflight.py` exists in the repo, run
   `python3 tools/plan-preflight/preflight.py check plan.json`, fix any **errors**, and show
   the operator every **warning verbatim** — warnings are ratification input, not yours to
   resolve or suppress. If the tool is absent, say plainly that the plan was not
   machine-checked.
2. Present the **approval ledger**, then the **omission sweep**.
3. Ask for explicit ratification. Only on an explicit yes, add
   `"ratified": {"by": "<operator>", "ts": "<now UTC, RFC3339>"}` and rewrite the file. If
   anything in the plan changes after that, ratification is void — remove the stamp and
   re-ask. Never add the stamp yourself without the yes.

## Measurement

This protocol is **Provisional** (design doc D7; evidence:
`docs/research/external/planning/elicitation-protocol-evidence.md`). Its instruments, recorded
by normal operation: operator turns per spec (pedantic baselines: 14 and 10; target ≤3–4),
interview escapes per spec (post-ratification amendments), blind-author failures-to-author,
and the ledger challenge rate — an operator who never challenges any surfaced entry across
many specs means the ledger is decoration, and it gets redesigned on the record.
