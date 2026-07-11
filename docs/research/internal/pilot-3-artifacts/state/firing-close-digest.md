# greenlane-pilot3-v2 — firing digest (Leg 2: GL2-only, PAUSED at operator direction)

Clean-paused 2026-07-06T00:17Z at a task boundary (operator chose "clean-pause +
re-fire after reset"). Firing is RESUMABLE from disk — the next build-loop
`resume_context` reconstructs state; do not resume from this prose.

## Arm change (recorded per operator direction)
The machinery arm changed at the GL1 pause boundary: **I19–I26 + `harness.smoketest`**
arrived by sync. PRIOR arm (GL1 leg) = **Agent-tool fallback**. THIS leg = the
**headless one-shot path (I26, first live use)**. Run-log records from seq/ts
this leg forward are the new arm.

## Ledger
tasks: **1 of 10 done** · 0 in-flight · **1 parked (GL2)** · 0 failed
runnable-when-unblocked: **GL2-auth-tenancy** (critical; parked on a quota wall)

| id | phase | profile | status | note |
|---|---|---|---|---|
| GL1-scaffold | 1 | high | **done** | merged `745b8fb` (prior leg) |
| GL2-auth-tenancy | 1 | critical | **parked** | Fable-5 429 credit wall; opus-substitute hung. Card `state/blockers/GL2-fable5-credit-exhaustion.json` |
| GL3–GL10 | 1–2 | — | not_started | dep chain unchanged; not admitted |

## What happened this leg (headless-arm shakedown)
- Start gates all green (plan-ready 7/7 incl. I19 preflight; selftest 30/30;
  **smoketest 17/17**, I5 first live use; vault valid; skill budget ok;
  preflight NORMAL, live statusline rung 1s old).
- Governor between-tasks read **degrade** (seven_day **0.82** ≥ 0.80). Scheduler
  **deferred** GL2 (sole runnable). Card-first adjudication (I21). Operator
  overrode → proceed under degrade (one-off attributed exception, GL2 only).
- Headless mechanism **proven** on a haiku probe (exit 0, usage + cost harvested,
  spawn interlock gated correctly on the admission stamp). But:
  - **P3v2-9** `--json-schema <path>` rejected by CLI 2.1.201 (wants inline) →
    workaround `--json-schema "$(cat …)"`.
  - **P3v2-10** `parse_worker_result`→`parsed=None` on a compliant worker
    (fenced `result`, null `structured_output`) → workaround: raw-JSON prompt +
    fence-strip.
  - **P3v2-11** `load_patterns(HEADLESS_FAILURE_PATTERNS)` raises (tuple vs list)
    → workaround `list(...)`.
- **P3v2-12** Fable-5 test-author died first call: **429 out-of-usage-credits**
  (0 tokens). Governor's degrade hold **vindicated**.
- Operator authorized **opus substitute (shakedown-only, no-merge)**. Opus
  test-author **HUNG 38 min** (7.35s CPU, idle API sockets, 0 output); killed via
  TaskStop. **P3v2-13**: no worker wall-clock watchdog / liveness signal; the
  "opus unaffected" premise was false (opus throttled too).
- Three hard quota signals → GL2 unrunnable now. Operator: clean-pause + re-fire.

## To RESUME (operator: re-run build-loop AFTER the window resets)
1. **Gate on quota first:** re-fire only once seven_day is back under 0.80 AND
   **Fable-5 credits have returned** (check `/usage-credits`). Weekly reset
   ~2026-07-06T00:59:59Z. If seven_day is still ≥ 0.80 the scheduler will
   correctly defer GL2 again.
2. Same start sequence; `resume_context` shows GL1 done, GL2 **parked** on the
   resolved-but-quota-blocked card. GL2 needs a **fresh test-author** (no carried
   corpus) — the worktree from this leg was reconciled (removed clean; 0 work
   landed), so start GL2's pipeline from scratch.
3. **Do NOT re-use the shakedown substitution.** GL2 is critical; run it on the
   real critical routing (fable-5 test-author + 4-lens fable-5 panel) so the
   merge is validation-worthy. The opus substitution was shakedown-only.
4. Apply the P3v2-9/-10/-11 workarounds until the upstream machinery fixes land
   by `git fetch <parent> main && git merge FETCH_HEAD` (machinery is
   upstream-owned; do NOT patch locally).
5. Held-out run convention (pinned prior leg): gate `heldout_cmd` =
   `env PYTHONPATH=pilot/greenlane:pilot/greenlane/tests python3 -m pytest .heldout -q -p conftest`;
   run the gate with `repo=<task worktree>`.

## Records (all on disk)
- run-log `state/run-log.jsonl`: task_spawn ×3 + task_aborted ×2 (429, hang),
  requested params + attempt (new arm).
- ledger events `state/ledger-events.jsonl`: seq 8–11 (admit-by-override → park →
  resume-under-substitute → re-park); cursor + resume marker current.
- governor-log (degrade decision) + scheduler-log (deferral tick 2 +
  operator_override_admission + firing_pause).
- blocker cards: `state/blockers/GL2-governor-hold.json` (resolved:
  operator-ack-proceed), `state/blockers/GL2-fable5-credit-exhaustion.json`
  (resolved: shakedown-substitute; substitution_outcome: FAILED/hung).
- watch-items `state/watch-items.json` (W10/W12/W14/W16 updated; W14 carries
  P3v2-9..13 findings).
- observations ledger `docs/research/pilot-3-observations.md` — "Leg 2" section
  (P3v2-9..13). **Uncommitted working change on main** — operator to commit or
  the next firing merges it.
