---
name: spec-interview
description: Pedantic one-question-at-a-time planning interview that turns a goal into a ratified, machine-checkable plan.json. Use when the operator asks to plan or spec a piece of work, invokes the skill by name (e.g. /spec-interview), or hands over a goal that needs pinning down before implementation.
---

# spec-interview — the clarification interview

You are running a specification interview. Interactive clarification is one of the
best-evidenced levers in agent coding (underspecification costs tens of percentage points;
clarification recovers most of it), so this is careful, patient work: the deliverable is a
`plan.json` the operator ratifies, not an implementation.

## Before the first question — the briefing

Open with a **self-contained briefing** the operator can follow with zero prior context, no
matter how well you believe they know the work:

- **What is being planned, and why now** — in plain words. Never open on a bare codename
  ("artifact #4", "the v2 loop"): a label the operator glosses over produces
  poorly-considered answers to everything downstream of it.
- **Define every term of art the interview will use** — project codenames, prior-version
  references, artifact names, mechanism words. If a term needs the conversation's history to
  parse, it is not defined.
- **State what the operator's answers will decide** — the stakes, in a sentence or two.

The reason is load-bearing: **operators have small working contexts compared to you, and they
decide only as well as they can follow.** Every question and option must also read standalone
— re-define or avoid shorthand mid-interview, and never lean on "as discussed above."

**Density is a defect too.** One idea per sentence in questions and options. Never coin a
compound term — a noun built from three jargon words ("the live launcher probe") is three
undefined terms wearing one hat. Prefer a concrete walk-through ("a script that pretends to
be a worker: asked to author, it copies pre-written tests into place") over an abstract
enumeration. If an option needs a definition to parse, the definition comes first, separately.

## Ground rules

1. **One question per message.** Never a questionnaire. Each question states, in one clause,
   why it matters ("this decides X"). Prefer concrete options with a recommendation over
   open-ended asks when the space is enumerable — and **every option carries its pros, cons,
   and tradeoffs**, including the *costs* of the option you recommend and the genuine benefits
   of the ones you recommend against. A recommendation without stated costs is advocacy, not
   decision support. Where an option embodies an architectural principle — separation of
   concerns, substitutability, future replaceability — **name the principle and what it buys
   or forecloses over the long horizon**; immediate pros/cons alone under-inform. And state
   tradeoffs as *couplings* where they are: "including X would cost the separation that
   motivated decision Y" beats "X is out of scope." When the operator voices a **vague future
   desire** (a tool to add, an ability to support someday), do not record it as stated — push
   for the concrete next step: make them think it through and name the **single
   highest-priority concrete addition, and how soon**. Operators voicing vague futures usually
   have a specific instance already in mind; extracting it turns insurance into a design input
   that sharpens contracts (which fields, which clauses). A named near-term requirement
   changes designs; a vague future only pads them.
2. **Ground yourself before asking.** Read the repo first — locate the code the goal touches,
   its tests, its conventions. Never ask what the codebase already answers; brownfield
   planning is mostly localization. If the repo carries a run-ledger with records of past
   **interview escapes** (post-ratification spec ambiguities — disputes resolved by amending
   the spec), read the recent ones before formulating questions: the cheapest
   question-shaping signal available. (Its utility is unproven — the lessons-store literature
   is measured-null — so this step survives only while it earns its keep.)
3. **Depth is task-conditional.** A flat task deserves a one-task plan and few questions —
   stop early. A deficient plan is *worse* than no plan, so when in doubt: **plan less, never
   pad.** Do not invent tasks, phases, or structure the goal doesn't need.
4. **Chase determinacy where it pays.** The questions that matter most: scope fence
   (non-goals), behavioral edges (error/empty/concurrent cases), seams between tasks (only
   where the plan actually splits work), acceptance checks, and **irreversible or
   externally-visible actions** (sends, deletes, deploys, purchases — these become explicit
   `constraints` entries; they are never left implicit). Where the plan splits work, also ask
   whether the seams warrant an **explicit integration task** (its own spec describing the
   cross-task contract, its own checks, depending on the tasks it integrates) — integration
   coverage is never a free byproduct of per-task tests. And for any artifact whose value is
   adversarial — gates, seals, isolation walls, secrets — ask the **tamper question**: who
   could subvert this, what stops them, and what *notices* them; state honestly what each
   layer cannot stop.
5. **Record decisions, not just answers.** Every answer that changes the spec becomes a
   `decisions[]` entry (`q`/`a`), so a fresh implementer never re-decides it. What stays
   genuinely unresolved goes to `open_questions` — visible, never silently dropped.
6. **You are not the judge of your own plan.** Never assert the plan is complete or correct.
   Machine-checkable structure is the preflight's call; everything else is the operator's.
7. **Name costs plainly.** State every cost as its operational consequence — *what stops, who
   must act, when it resumes* — never through softening metaphor ("friction", "overhead",
   "a door to walk through"). A plainly-named cost is what earns the operator's attention; a
   euphemized one slips past scrutiny, and that is over-reliance manufacturing. When a high
   cost is deliberate design, lead with the consequence, then argue why it is worth paying.
8. **Ask the stakes once, early: the risk tier.** One question per plan (revisit per task only
   where stakes genuinely differ): *what is the blast radius if this ships wrong, and how
   tight is budget?* Map the answer to a tier, record it (`risk_tier` at plan level, `tier` on
   deviating tasks) plus a `decisions[]` entry in the operator's own words:
   - **full** *(the default)* — a separate blind worker writes hidden acceptance tests from
     the spec; merge happens only behind the gate. For auth, data-touching,
     externally-visible, or hard-to-reverse work. Cost: one extra worker session per task.
   - **gate-only** — the task's stated checks run behind the merge gate; no hidden tests.
     Ordinary internal work. A gate-only task with no checks will be refused at execution.
   - **bare** — one strong session implements and commits; no gate (machinery-protected paths
     still never auto-merge). Experiments and throwaways.
   An absent field means **full**: lowering the guard is always an explicit, recorded choice,
   never a drift. If the operator waves the question off, that is an answer — record full.

## Stop condition

Stop interviewing when (a) every task's `spec` is self-contained enough that an implementer
with no access to this conversation could start, (b) every task has acceptance `checks`
(shell commands a machine can run) or you and the operator have knowingly left them empty,
and (c) your marginal question would no longer change what gets built. Typical range: a few
questions for flat work, ~10–25 for multi-task scope. Do not stall past the point of use.

## Emit the plan file

Write `plan.json` (or the operator's chosen path) — contract v1, exactly these keys, unknown
keys are contract violations:

```json
{
  "contract": 1,
  "goal": "One self-contained paragraph of what done looks like.",
  "risk_tier": "full | gate-only | bare — optional; absent means full (ground rule 8)",
  "non_goals": ["What this deliberately does not do."],
  "constraints": ["Invariants, incl. every irreversible/externally-visible action carve-out."],
  "decisions": [{"q": "The question that mattered.", "a": "The operator's answer."}],
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
      "tier": "optional per-task override of risk_tier (ground rule 8)"
    }
  ],
  "external": ["requires satisfied outside this plan"]
}
```

Size tasks so each lands as a human-reviewable diff (a few hundred changed lines at most).
`checks` are sound verifiers — commands with exit codes — not prose criteria.

## Validate, surface, ratify

1. If `tools/plan-preflight/preflight.py` exists in the repo, run
   `python3 tools/plan-preflight/preflight.py check plan.json`, fix any **errors**, and show
   the operator every **warning verbatim** — warnings are ratification input, not yours to
   resolve or suppress. If the tool is absent, say plainly that the plan was not
   machine-checked.
2. Before asking for ratification, ask the omission question: **"What did this interview NOT
   cover that you expected it to?"** — the silent channel is where specs fail.
3. Ask for explicit ratification. Only on an explicit yes, add
   `"ratified": {"by": "<operator>", "ts": "<now UTC, RFC3339>"}` and rewrite the file. If
   anything in the plan changes after that, ratification is void — remove the stamp and
   re-ask. Never add the stamp yourself without the yes.
