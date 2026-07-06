# Harness reference — one page

The shapes and one-liners a firing/planning session otherwise source-dives
for (I3, P1-6; pilot-3-v2's orchestrator spent mid-firing turns reading
module APIs). Every `harness.<module>.<name>` token below is asserted to
exist by `tests/test_reference.py` — if this page drifts from the code, the
suite goes red.

## Firing lifecycle (the build-loop's mandatory calls, in order)

| Phase | Invocation |
|---|---|
| Plan fireable? | `python3 -m harness.planning ready --plan-dir plan --snapshot state/plan-snapshot.json --vault-config harness/config/vault-isolation.json` (7 checks, fail-closed) |
| Gates prove themselves | `python3 -m harness.selftest` (30 checks) then `python3 -m harness.smoketest` (17-step composition walk, ~2s, zero quota) |
| Vault | `python3 -m harness.vault check` · configure ONLY via `python3 -m harness.vault configure --vault-path /abs/outside-repo` |
| Quota | `python3 -m harness.governor --preflight --statusline-json state/statusline-dump.json` (exit 3 = conservative) · bootstrap: `--assume-occupancy 0.3 --acked-by <operator>` |
| Marker + stop-gate | `harness.loop.acquire_run_marker` → `harness.loop.closure_hook_config` (immediately) · release via `harness.loop.release_run_marker` |
| Resume | `harness.loop.resume_context` — artifacts only, never a summary |
| Pause | operator: `harness.loop.request_pause` (any terminal) · loop: `harness.loop.pause_requested` at every stage boundary → `harness.loop.acknowledge_pause` → drain → clean pause → `harness.loop.clear_pause_request` |
| Permission mode | `harness.loop.permission_mode` (statusline dump; None = unknown on this build) vs `harness.loop.FIRING_PERMISSION_MODES` — wrong mode = stop before real work; launch with `claude --permission-mode auto` |

## Plan artifacts (`plan/`)

- `tasks.json` — `{"tasks": [{"id", "phase", "profile", "deps": [], "may_be_invalidated_by": [], "regime"?, "touches"?: [concrete paths]}]}` (`harness.ledger.validate_tasks`; profiles routine<elevated<high<critical; regimes chore|thinking|long_horizon)
- `specs/<task-id>.md` — scoped spec, ≥200 chars (pinned interfaces + acceptance criteria)
- `floors.json` — `{"floors": [{"glob", "min_profile"}]}` (`harness.hooks.validate_floor_map`)
- `conventions.json` (optional) — `{"heldout_cmd": "<project's held-out run command>"}` (P3v2-4)
- `ratification.json` — content-bound stamp; any edit voids it (`harness.planning.ratify`, `harness.planning.content_hash`)
- Pre-ratification sweep: `python3 -m harness.planning preflight` → `harness.planning.gate_preflight` (floors×touches + H9×existing-handoffs)

## State files (`state/`, gitignored, created at runtime)

`run.marker` (advisory, pid-live) · `closure-hook.json` · `plan-snapshot.json` (`harness.closure.freeze_snapshot`) · `ledger-events.jsonl` + `.cursor` (`harness.ledger.EventLog`: `record_status`, `set_resume_marker`, `pending`, `advance_cursor`) · `run-log.jsonl` (`harness.runlog.RunLog`) · `governor-log.jsonl` · `statusline-dump.json` · `admission-stamp.json` · `gate-stamps/` · `verdicts/<task>/` · `evidence/` · `blockers/*.json` · `pause.request` / `pause.ack` · `watch-items.json` · `lessons.jsonl`

## Workers (headless one-shot, I26)

```
harness.loop.write_worker_overlay(worktree, vault_path)   # layer-6 binding
harness.loop.headless_worker_cmd(prompt, model, effort=..., system_prompt=...,
    json_schema_path=..., max_turns=..., disallowed_tools=[...])  # schema inlined (P3v2-9)
harness.loop.run_headless_worker(argv, cwd, env=harness.loop.headless_env(...),
    timeout_s=...)  # wall-clock deadline; kills the process group (P3v2-13)
harness.loop.parse_worker_result(stdout)  # fence-tolerant (P3v2-10)
# deaths: harness.failures.classify(stderr, extra_patterns=
#         harness.failures.load_patterns(list(harness.loop.HEADLESS_FAILURE_PATTERNS)))
```

Spawn params: `harness.spawncheck.profile_spawn_params(profile, regime=...)` →
base `(model, effort)` for test-author/validators, `implementer` block for the
implementer; every pair through `harness.spawncheck.validate_spawn` (allowlist:
`harness/config/tiers.json`); results checked via `harness.spawncheck.require_result`.
Ladder: attempt 2 = same tier @ `max` + sharpened feedback; attempt 3+ = tier up.

## Worker return contracts (final message = JSON only)

- Handoff (implementer/test-author): `harness.schemas.validate_handoff` — outcome/summary/intent/key_changes_made/key_learnings (+`spec_ambiguities`: str or `{text, corpus_covers: "both"|"one-reading"}`; `files_touched`)
- Verdict (validator): `harness.schemas.validate_verdict` — lens/verdict/evidence[]/intent (+findings; FAIL needs ≥1 finding)
- Blocker card: `harness.schemas.validate_blocker` — task_id/repro/≥2 options/recommendation (+`kind`, `asked_at`, `resolved{decision,by,at}`)
- H9 pre-spawn: `harness.schemas.ambiguity_blockers(handoff, task_id, profile)` — blocking on `harness.schemas.BLOCKING_AMBIGUITY_PROFILES`; `corpus_covers:"both"` discharges

## Scheduling + quota

- `harness.admission.admit_task(profile, occupancy)` — forecast path needs calibrated estimates; unknown-cost fallback admits only under degrade−margin
- `harness.scheduler.tick` / `harness.scheduler.window_phase` — tail-cap waived only when `harness.governor.reset_headroom` clears
- `harness.governor.fraction_rate(decisions, window, since_ts=<marker acquired_at epoch>)` — per-firing burn rate (I25)
- Stamps: `harness.interlocks.write_admission_stamp` before spawns (spawn interlock: `harness.interlocks.check_spawn`, 900s freshness) · gate PASS writes via `harness.interlocks.write_gate_stamp`; merges checked by `harness.interlocks.check_merge`

## Gate (merge only through it)

```
harness.gate.run_gate(repo=<task worktree>, branch, base="main",
    test_cmd=..., verdict_dir=..., task_profile=...,
    floor_config_path="plan/floors.json",          # repo-relative: read from BASE ref
    vault_path=..., evidence_dir=...,
    stamp_dir="state/gate-stamps",
    required_steps_path="harness/config/gate-required-steps.json",
    heldout_cmd=<plan conventions / kickoff>)       # gate materializes the corpus itself
```
Report via `harness.gate.render_report`; false-FAIL telemetry via `harness.gate.false_fail_records`. Vault side: `harness.vault.materialize` (hash-verified), `harness.vault.build_manifest`, `harness.vault.load_manifest`, evidence in `harness.vault.heldout_evidence_dir`.

## Run-log records (`harness.runlog.validate_record`)

- `task_spawn`/`task_aborted`/`task_parked` via `harness.runlog.worker_event(event, task_id, role, resolved, attempt=...)`
- `task_complete`: requires `profile` + `total_tokens`; carry role/outcome/attempt/model/tier/effort (requested params, never worker self-report)

## Everything else

`harness.liveness.Vitals` + `harness.liveness.assess` (worker step budgets) ·
`harness.failures.next_action` (permanent→abort, retryable→backoff) ·
`harness.calibration.downgrade_allowed` / `harness.calibration.discovery_active` /
`harness.calibration.panel_correlation` (canaries/escapes) ·
`harness.loop.LessonsCorpus` (surprising-only; curated injection) ·
`harness.loop.skill_budget_check` · `harness.mockworker` (zero-quota rig) ·
`harness.hooks.check_destructive_git` / `harness.hooks.check_risk_floor` /
`harness.hooks.MACHINERY_GLOBS` (machinery + `plan/**` deny)
