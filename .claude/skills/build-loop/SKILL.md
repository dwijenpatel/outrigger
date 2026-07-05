---
name: build-loop
description: Operator-started build loop — grinds the ratified plan task-by-task through implementer/validator workers behind the merge gate. Invoke only when the operator starts a firing.
user-invocable: true
---

# Build loop — one firing

You are the orchestrator for one operator-started firing. Deterministic machinery does everything it can; you supply judgment only where scripts cannot. **Mandatory invocations below are phase-gated: run them at the stated point, every time — never rely on remembering.**

## 0. Start (mandatory, in order)

0. Plan readiness: `python3 -m harness.planning ready --plan-dir plan --snapshot state/plan-snapshot.json --vault-config harness/config/vault-isolation.json`. Exit != 0 means **no firing** — no ratified plan (run `plan-build`) or no configured vault (`python3 -m harness.vault configure --vault-path /abs/path-outside-repo`). Never author or patch a plan from inside a firing.
1. Acquire the run marker: `harness.loop.acquire_run_marker(state/run.marker, <firing-id>)`. A live-owner refusal means STOP — concurrent firings are operator-arbitrated. Immediately write `state/closure-hook.json` via `harness.loop.closure_hook_config(...)` — the registered Stop hook reads it, and a live firing without it blocks every stop (fail-closed).
2. Verify gates: `python3 -m harness.selftest` must pass. A gate that cannot prove itself does not guard this firing (fail closed: stop, report).
2b. Vault config: `python3 -m harness.vault check` must exit 0. Exit 2 = unconfigured or drifted — STOP; the operator sets it with `python3 -m harness.vault configure --vault-path /abs/path-outside-repo` (never hand-edit the config). Use the checked config's `vault_path` for every `worker_settings`/gate call below.
3. Check skill inventory: `python3 -c "from harness import loop; r = loop.skill_budget_check(['.claude/skills']); print(r['why']); raise SystemExit(0 if r['ok'] else 1)"` — over budget means skills are silently vanishing; stop and report.
3b. Preflight quota sources: `python3 -m harness.governor --preflight --statusline-json state/statusline-dump.json [--oauth-json ...]` (missing source files are skipped rungs, not errors). Exit 3 = **conservative mode**: tightened thresholds, cheap-serial only, no concurrency admissions — or stop for operator ack. Estimate-rung data alone never clears a preflight. **First-ever firing (P2-4 bootstrap):** with no live rung and no calibrated ceilings, occupancy is `unknown` and admission refuses everything. Options, in preference order: (a) operator registers the statusline shim (`"statusLine": {"type": "command", "command": "python3 hooks/statusline_dump.py --out state/statusline-dump.json"}`) in an interactive session; (b) `CLAUDE_OAUTH_TOKEN=... tools/oauth_usage_fetch.sh > state/oauth-usage.json`; (c) explicit operator-acked assumption for conservative-serial admissions only: `--assume-occupancy 0.3 --acked-by <operator>` — attributed and sticky-`~`, never a silent default.
4. **Resume from artifacts only:** `harness.loop.resume_context(...)`. Act on the bundle (git facts, reconciled digest, pending events). Never resume from a prior session's summary — logs and notes are claims, not evidence. Drain `pending_events` before new work.

## Per tick (mandatory)

0. Pause request: `harness.loop.pause_requested(state/pause.request)` non-None → **clean pause now** (the `build-pause` skill's orchestrator sequence: park in-flight, write-ahead records, resume marker, release run marker, clear the request *after* pausing). The operator can flag this from any terminal — honoring it at the boundary is what makes the flag graceful.
1. Governor between tasks: `python3 -m harness.governor ...` (statusline dump file → oauth doc → run-log estimate). `pause` → clean pause (same sequence). `degrade` → profile-minimum panels, no new heavy admissions.
2. Scheduler: `harness.scheduler.tick(...)` with current occupancy, estimates, slots. Start what it says; record `held_unsafe`/`deferred` reasons in the ledger digest — never override its admission decisions to "just fit one more in". After an admitting tick, write the admission stamp: `harness.interlocks.write_admission_stamp(state/admission-stamp.json, {task_id, tick})` — the spawn interlock refuses worker spawns without a fresh one.
3. Per admitted task: spawn **test-author** (spec-only; move outputs to the vault, re-record the manifest). On its return run `harness.schemas.ambiguity_blockers(handoff, task_id, profile)` — non-empty on high/critical means **park the task on those blockers now**, before the implementer spawns (E3 cards; one round-trip each). Then spawn **implementer** (scoped spec + `harness.loop.LessonsCorpus.select_for_task` injection, strict `harness.loop.worker_settings`), then the blind **validator panel** (fresh contexts, spec+diff only, one lens each).
4. Feed each worker step to `harness.liveness.Vitals`; on a park recommendation, park with a blocker record (schema `blocker.json`) and continue other work.
5. Merge only through the gate: `harness.gate.run_gate(...)` with verdict dir, floors config, vault path, evidence dir, `stamp_dir=state/gate-stamps` (a PASS writes the stamp the merge interlock demands; without it `git merge` is hook-blocked during the firing), and `required_steps_path=harness/config/gate-required-steps.json` (the manifest turns omitted inputs into fail-closed refusals for the task's profile). The gate's exit status decides — **check the real exit status, never a piped tail of it**.
6. Handle worker infrastructure errors via `harness.failures.classify` → continue / backoff / abort per the taxonomy. Agent-reported FAILs are escalation signals (effort before tier, at a fresh worker boundary), not errors.
7. Append every outcome to the run-log and ledger event log **before** advancing any cursor/marker (write-ahead). Each run-log record carries the **spawn params you requested** — `role`, `tier`, **`model` (the concrete id from `spawncheck`'s resolved params)**, `effort`, `profile` — never a worker's self-report. A worker that dies or parks mid-task still gets its record (`outcome: "aborted"`/`"parked"`) so the routing choice is never lost.

## Pipelining (while validation runs)

Author task N+1's spec + contract tests while task N validates; pre-decompose the next phase into a provisional, planning-only ledger. Look-ahead is planning-only — never speculative implementation.

## Situational (invoke when the trigger fires, not by default)

- **Output diverges and you can't see why** → stop guess-and-patch; reproduce in isolation with a fresh worker.
- **Any surprise mismatch between a summary and an artifact** → trust the artifact; re-read state via `resume_context`.
- **key_learnings arrive** → `LessonsCorpus.add` (surprising-only contract; exact-dupe is dropped).
- **A machinery change seems needed** → never edit machinery; queue a decision card (E3) and continue.

## Close (mandatory)

Phase close: batch ratification cards; regenerate evidence roll-up. Firing end: reconcile worktrees, release the run marker, leave the ledger digest as the handoff — the next firing resumes from disk, not from your summary.
