---
name: plan-build
description: Relentless planning interview before any firing — grills the operator one question at a time until the spec is determinate, then produces the ratified plan artifacts the build-loop requires. Run BEFORE build-loop; a firing without its outputs is refused.
user-invocable: true
---

# Plan a build — the interview before the firing

You produce the **ratified plan** the build-loop grinds. The whole correctness floor downstream trusts the spec — it is the panel's only shared context and the test-author's only input — so your job is to make it *determinate*, and the operator's approval *explicit*. **Do not write code. Do not start the firing. Do not author the ledger until the interview is complete.**

## The interview (modeled on the "grilling" method)

1. **Interview relentlessly, one question at a time.** Ask exactly one question per turn and wait for the answer — batching is bewildering. Walk the design tree branch by branch, resolving decisions in dependency order (an answer about tenancy changes the questions about auth; ask tenancy first):
   product goal & the wedge → users & roles → tenancy/auth model → domain model → core workflows (walk each one end-to-end) → the security/trust-critical behaviors in detail → integrations & the explicit OUT list → tech stack & storage → non-functional constraints → risk classification.
2. **Every question carries your recommended answer** and why — the operator should mostly be confirming or correcting, not generating from scratch. Use the option-question tool where choices are enumerable; put the recommendation first.
3. **Explore, don't ask.** If the repo, the research corpus, or prior notes already answer it, read them instead of asking. Only the operator's *preferences and intent* need the operator.
4. **"You decide" is an answer you must convert.** Record it as an explicit `DECISION (delegated)` with your choice and rationale in the plan — it gets ratified with everything else, never silently assumed.
5. **The determinacy bar:** keep going until a spec-only test-author could write held-out tests with **no guessing** — every boundary, permission, error path, and invariant in scope has a determinate answer. Then do one final sweep of the whole tree; if the sweep surfaces a new material unknown, keep interviewing. Two clean sweeps = done.
6. **Push back.** If two answers conflict, or an answer implies scope the operator earlier excluded, say so immediately and resolve it — do not paper over inconsistencies.

## The artifacts (only after the interview completes)

Write the plan dir (default `plan/`):

- `plan/PLAN.md` — goal, the wedge, decisions log (including delegated ones), the explicit OUT list, tech stack, phase map (later phases marked **provisional, planning-only**).
- `plan/tasks.json` — the ledger (schema: `harness/ledger.py` `validate_tasks`; fields: `id`, `phase`, `profile`, `deps`, optional `may_be_invalidated_by`). Phase 1 = a small walking skeleton (4–6 tasks is fine); **small must not mean vague**.
- `plan/specs/<task-id>.md` — one scoped spec per task: pinned interfaces (names, routes, schemas), behavior, **acceptance criteria a held-out test can execute**, explicit non-goals. This file is the worker's whole world — write it for a reader with zero context.
- `plan/floors.json` — path-glob → minimum profile (`{"floors": [{"glob": "...", "min_profile": "..."}]}`). Tenancy/auth/billing surfaces floor at `critical`.

## Ratification (hard stop)

1. Present the plan: a digest of decisions, the task table with profiles, and where each risk lives. **STOP and wait for explicit approval.** Silence, partial answers, or "looks fine so far" are not approval.
2. Only after the operator explicitly approves: `python3 -m harness.planning ratify --plan-dir plan --approved-by <operator>` — the stamp is content-bound; any later plan edit voids it and forces re-presentation.
3. Freeze the snapshot: `harness.closure.freeze_snapshot(ledger, state/plan-snapshot.json)`.
4. Verify: `python3 -m harness.planning ready --plan-dir plan --snapshot state/plan-snapshot.json` must exit 0. Hand off — the operator starts the firing with the build-loop skill.
