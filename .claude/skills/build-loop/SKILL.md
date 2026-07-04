---
name: build-loop
description: Operator-started build loop — grinds the ratified plan task-by-task through implementer/validator workers behind the merge gate. Invoke only when the operator starts a firing.
user-invocable: true
---

# Build loop — one firing

You are the orchestrator for one operator-started firing. Deterministic machinery does everything it can; you supply judgment only where scripts cannot. **Mandatory invocations below are phase-gated: run them at the stated point, every time — never rely on remembering.**

## 0. Start (mandatory, in order)

1. Acquire the run marker: `harness.loop.acquire_run_marker(state/run.marker, <firing-id>)`. A live-owner refusal means STOP — concurrent firings are operator-arbitrated. Immediately write `state/closure-hook.json` via `harness.loop.closure_hook_config(...)` — the registered Stop hook reads it, and a live firing without it blocks every stop (fail-closed).
2. Verify gates: `python3 -m harness.selftest` must pass. A gate that cannot prove itself does not guard this firing (fail closed: stop, report).
3. Check skill inventory: `harness.loop.skill_budget_check` — over budget means skills are silently vanishing; stop and report.
4. **Resume from artifacts only:** `harness.loop.resume_context(...)`. Act on the bundle (git facts, reconciled digest, pending events). Never resume from a prior session's summary — logs and notes are claims, not evidence. Drain `pending_events` before new work.

## Per tick (mandatory)

1. Governor between tasks: `python3 -m harness.governor ...` (statusline dump file → oauth doc → run-log estimate). `pause` → clean pause: write resume marker, release run marker, stop. `degrade` → profile-minimum panels, no new heavy admissions.
2. Scheduler: `harness.scheduler.tick(...)` with current occupancy, estimates, slots. Start what it says; record `held_unsafe`/`deferred` reasons in the ledger digest — never override its admission decisions to "just fit one more in". After an admitting tick, write the admission stamp: `harness.interlocks.write_admission_stamp(state/admission-stamp.json, {task_id, tick})` — the spawn interlock refuses worker spawns without a fresh one.
3. Per admitted task: spawn **test-author** (spec-only; move outputs to the vault, re-record the manifest), spawn **implementer** (scoped spec + `harness.loop.LessonsCorpus.select_for_task` injection, strict `harness.loop.worker_settings`), then the blind **validator panel** (fresh contexts, spec+diff only, one lens each).
4. Feed each worker step to `harness.liveness.Vitals`; on a park recommendation, park with a blocker record (schema `blocker.json`) and continue other work.
5. Merge only through the gate: `harness.gate.run_gate(...)` with verdict dir, floors config, vault path, evidence dir, and `stamp_dir=state/gate-stamps` — a PASS writes the stamp the merge interlock demands; without it `git merge` is hook-blocked during the firing. The gate's exit status decides — **check the real exit status, never a piped tail of it**.
6. Handle worker infrastructure errors via `harness.failures.classify` → continue / backoff / abort per the taxonomy. Agent-reported FAILs are escalation signals (effort before tier, at a fresh worker boundary), not errors.
7. Append every outcome to the run-log and ledger event log **before** advancing any cursor/marker (write-ahead).

## Pipelining (while validation runs)

Author task N+1's spec + contract tests while task N validates; pre-decompose the next phase into a provisional, planning-only ledger. Look-ahead is planning-only — never speculative implementation.

## Situational (invoke when the trigger fires, not by default)

- **Output diverges and you can't see why** → stop guess-and-patch; reproduce in isolation with a fresh worker.
- **Any surprise mismatch between a summary and an artifact** → trust the artifact; re-read state via `resume_context`.
- **key_learnings arrive** → `LessonsCorpus.add` (surprising-only contract; exact-dupe is dropped).
- **A machinery change seems needed** → never edit machinery; queue a decision card (E3) and continue.

## Close (mandatory)

Phase close: batch ratification cards; regenerate evidence roll-up. Firing end: reconcile worktrees, release the run marker, leave the ledger digest as the handoff — the next firing resumes from disk, not from your summary.
