# Pilot firing #2 (greenlane) — live observations ledger

Friction, failures, and defects observed during the greenlane firing
(single-trade field-service SaaS for small landscaping companies; plan
ratified 2026-07-05, stamp `03a4877bbfa52f91`). Same protocol as
[pilot-1-observations.md](pilot-1-observations.md): streamed in by the
operator, triaged against the machinery, fixes land in this repo.

**Status legend:** 🔴 defect (fix in this repo) · 🟡 friction (candidate
improvement, batch) · ⚪ benign (no action) · ❓ needs more detail ·
👁 watch item (pre-registered hypothesis, not yet observed)

---

## Pre-firing setup record (2026-07-05)

- Vault pinned via `python3 -m harness.vault pin` at
  `/Users/dwijen/repos/cc-agent-harness-test1-vault` (I4 live; `plan_ready`
  check 6 green).
- Ambient env pre-installed with GL1's pinned dependency set so the gate's
  clean-checkout `visible_tests` step doesn't fail on imports:
  Python 3.14.3 + fastapi 0.139.0, sqlalchemy 2.0.51, pydantic 2.13.4,
  uvicorn, jinja2, passlib[bcrypt], itsdangerous, python-multipart, pytest,
  httpx, mypy. Node v24.13.1 + npm 11.8.0 present for the tsc typecheck
  invariant (workers `npm install` typescript per-worktree from GL1's
  package.json).

## Triage ledger

### P2-1 👁 Can workers pip-install inside the sandbox? (untested territory)

Pre-registered before the firing: the implementer/test-author sandbox
(`worker_settings`: `allowUnsandboxedCommands: false`) has never run a
`pip install`/`npm install`. The ambient env is pre-installed (above), so
the *gate* path is covered — but a worker that decides it needs an extra
package, or the GL1 worker running `npm install` for typescript, exercises
network + site-packages writes from inside the sandbox for the first time.
If it fails: record the exact command + error HERE as the observation and
triage it — do not silently work around it in the worker prompt or by
weakening sandbox flags. If it succeeds, note that too (it means the
sandbox does not bound dependency drift, which is its own finding).

### P2-2 🔴 `governor --preflight --statusline-json <missing file>` dies with a raw traceback

Observed at firing start (2026-07-05): the skill's step 3b names
`--statusline-json state/statusline-dump.json`, but before any statusline
hook has produced the dump the CLI raises bare `FileNotFoundError` (exit 1,
stack trace) instead of the designed refusal/fall-through. The
*fail-closed decision layer* exists — calling `--preflight` with no source
args returns the proper conservative-mode document (exit 3) — the defect is
only in `_load_json_arg`: a missing/corrupt source file should degrade to
"source unavailable" (falling through to conservative mode with the reason
recorded), not crash. Workaround this firing: preflight invoked without
source args. Fix in this repo post-firing; machinery is frozen mid-firing
(E3 discipline).

### P2-3 👁 Preflight starts conservative on every fresh headless firing

Not a defect — a friction hypothesis. Neither live rung is reachable
non-interactively by design (statusline dump needs an interactive session's
hook; OAuth token is deliberately operator-supplied). Consequence: every
unattended firing begins in conservative mode (cheap-serial, no concurrency,
ack for heavy tasks) until the operator supplies a source. If pilot-2 spends
most of its wall-clock rate-limited by this, the batch improvement is an
operator-side pre-firing step (statusline dump export or
`CLAUDE_OAUTH_TOKEN=... tools/oauth_usage_fetch.sh > state/oauth-usage.json`)
documented in the build-loop skill's step 3b.

### P2-4 🔴 Bootstrap deadlock: a fresh firing can admit nothing

Hit at tick 1 (2026-07-05), firing paused cleanly on it. The chain: no
statusline dump (shim exists at `hooks/statusline_dump.py` but was never
registered as the interactive session's statusline command) → no OAuth doc
(token is operator-supplied by design) → estimate rung has no calibrated
ceilings (`profile-tier-estimates.json` is deliberately UNPOPULATED before
first telemetry; ceilings are never hard-coded) → governor occupancy
`unknown` → `scheduler.tick` refuses every admission ("cannot admit against
an unmeasured window", correct fail-closed) → zero tasks can start, ever,
on a first firing. Conservative mode's "cheap-serial work only" implies
work can proceed; the admission rule says nothing can. The two rules
compose into a deadlock exactly once — at first-ever startup — which is
why no test caught it (P1 theme 1 again: hermetic modules, untested
composition).

**Unblock (operator, either):** (a) register the shim: `"statusLine":
{"type": "command", "command": "python3 hooks/statusline_dump.py --out
state/statusline-dump.json"}` in this repo's Claude Code settings, let it
fire once, restart the firing; or (b) `CLAUDE_OAUTH_TOKEN=...
tools/oauth_usage_fetch.sh > state/oauth-usage.json` and restart with
`--oauth-json state/oauth-usage.json`.
**Candidate machinery fix (post-firing, E3):** a documented bootstrap path —
e.g. governor accepts an explicit operator-acked
`--assume-occupancy <frac>` recorded as `optimistic` + operator-attributed
in the run-log, valid only for conservative-mode serial admissions; plus
skill step 3b naming the shim registration as a pre-firing checklist item.

---

### P2-5 🔴 Parallel machinery evolution: the pilot session and the parent implemented I4 twice, and the sync clobbered one

While the parent repo built I4 (`configure`/`check_vault_config`), the
pilot session independently built its own (`pin`/`check` +, better, a
**`plan_ready` vault check**) — two correct, incompatible implementations
of the same fix, one review cycle apart. The parent-side sync then resolved
`harness/vault.py` "to the parent" and silently destroyed the session's
version, leaving the pilot repo a broken chimera (session `planning.py`
calling functions the merged `vault.py` no longer had; 17 test errors).
Root cause: no ownership rule said *where machinery evolves*.
**Fixed:** (a) machinery is upstream-owned — pilot clones record defects in
this ledger and receive fixes by merge (CLAUDE.md rule); (b) the session's
best idea is ported upstream: `plan_ready` now takes `--vault-config` and
refuses readiness against an unconfigured/drifted/absent vault (I4b), and
`configure` creates the vault dir + `check` verifies its existence.

## Fix log (parent repo)

- **P2-2 FIXED (I4b):** governor CLI treats missing/corrupt source files as
  skipped rungs (warning + fall-through), never a traceback.
- **P2-4 FIXED (I4b):** bootstrap path exists — skill step 3b documents the
  shim registration and OAuth fetch, and the governor accepts
  `--assume-occupancy <frac> --acked-by <operator>`: an attributed,
  bounds-checked, always-optimistic (sticky-`~`) assumption used only when
  no source yields a usable window; conservative-serial admissions only,
  never clears a preflight.
- **P2-3 FIXED (I9, operator-approved):** the statusline shim is registered
  as project machinery in `settings.json` — every interactive session
  auto-produces `state/statusline-dump.json`, so the live rung exists
  without an operator chore; H8 staleness handling covers idle dumps.
  Registration is selftest-checked.
- **P2-1:** unchanged — still the pre-registered sandbox watch item.

### P2-6 🔴 (blind run) The I9 statusline registration never fired — $CLAUDE_PROJECT_DIR is hooks-only

Blind-run pilot: step 0 all green, but no `state/statusline-dump.json`
existed at preflight → conservative mode → the session (correctly) stopped
at the step-3b bootstrap question. Root cause confirmed against the
official statusline docs: statusline commands receive only COLUMNS/LINES —
**`$CLAUDE_PROJECT_DIR` is not set** (it is a hooks-only variable), so the
I9 command's path expanded empty and the shim never ran. The project dir
IS available, but in the statusline's stdin JSON (`workspace.project_dir`).
**Fixed (I9b):** the shim's `--out` is now optional — omitted (or carrying
an unexpanded `$`), it resolves `<project>/state/statusline-dump.json` from
the input JSON itself; the settings command becomes
`cd "${CLAUDE_PROJECT_DIR:-.}" && python3 hooks/statusline_dump.py`.
Lesson for the ledger: I9 was registered but never *observed to fire*
before shipping — registration checks prove presence, not execution; the
I5 smoke test should exercise the statusline path with a synthetic stdin.

### P2-7 🟡 (blind run) Skill-budget call signature required source-diving

The skill said `harness.loop.skill_budget_check` without its required
argument; the session had to read the source to build the call (P1-6's
turn-economy lesson again, one function at a time). Fixed: the skill now
carries the exact one-liner.

### P2-8 🔴 The statusline rung can never fire in this operator's environment — sessions run in the desktop app

Third firing's bootstrap stalled on a missing statusline dump despite I9/I9b.
Full diagnostic chain: the registered command was proven correct by hand
(dump written, line printed); official docs confirmed project-scope
`statusLine` IS supported and settings hot-reload; `disableAllHooks` unset;
then the one observable only the operator could supply settled it — **the
sessions run in the Claude Code desktop app, which has no statusline
surface at all** (it is a terminal-TUI feature). I9/I9b were correct
machinery aimed at a surface that does not exist in this deployment's
workflow. Registration checks, hand-execution, even doc verification — none
of them test "does the environment actually invoke this?"
**Fixed (I13):** `tools/oauth_usage_refresh.sh` — an operator-started loop
(interval 300s, half the staleness ceiling) that keeps the OAuth rung
continuously fresh; token read once (macOS Keychain, OS prompt = the ack),
lives only in the operator's terminal process, never in files or the firing
session. Skill step 3b now routes by environment: terminal → statusline
shim; desktop → the refresher; one-shot fetch; acked assumption last.
The statusline machinery stays — it is the right rung for CLI workflows.

### P2-9 🔴 (caught at the pause boundary) Worker worktree homes dirty the judged tree

The paused GL1 implementer's worktree lives at `.claude/worktrees/` —
untracked, not gitignored: the next gate's `require_clean` would have
refused every merge (P1-5's exact family, fourth instance). The dir must
survive (durable-lease semantics — the parked worker's home) but never
count as tree dirt. **Fixed:** `.claude/worktrees/` gitignored.

### P2-10 🔴 The gate never runs the held-out corpus — the core O0 step is orchestrator prose

Surfaced at GL1's first gate approach: `run_gate` executes `test_cmd` on the
clean checkout and checks the manifest for *drops*, but **nothing
materializes the vault's held-out tests into the checkout** — there is no
`vault.materialize()`, and held-out execution exists only as "the
orchestrator supplies a test_cmd that wires it." The session had to invent
the wiring (copy corpus into a clean copy, pytest --tb=line, read pass/fail
names only). It did this *well* — but the single most load-bearing O0
mechanism is currently improvised per-task, per-session, with leakage
control resting on the orchestrator's manners, outside the gate's H7
scrubbing/evidence routing. **Fix (I14, post-firing):** vault.materialize +
a gate-native held-out step (corpus into checkout, output vault-side,
scrubbed tail in-repo).

### P2-11 🟡 Orchestrator ground-truth replays are uncounted adaptive reuse

Three held-out corpus runs against three fix attempts = classic adaptive
reuse (Ladder/Thresholdout territory), plus rework guidance derived from
failure output — bounded carefully this time (--tb=line, spec-anchored
guidance, no assertions leaked), but the D3 leakage budget counts none of
it (it ships disabled and only meters gate-side replays). Post-firing:
orchestrator-side replays must consume the same budget.

### P2-12 🟡 The write-ahead "spawn event" should be a schema, not an improvisation

The prior firing left a malformed task_complete (missing total_tokens —
written around the validated append). This session solved it correctly:
an open-schema spawn event at spawn time, full record with real tokens on
return. Mechanize as a validated `task_spawn` event type (I15) so routing
choices survive mid-task death by contract, not by orchestrator invention.

### P2-13 🔴 (design tension, needs a decision before pilot #3) Routine's step-manifest silently disables the mis-tag floor defense

GL1 (routine) creates `app/models.py` (floored high) and `app/routes/**`
(elevated) as scaffold stubs. The H3 default manifest omits `risk_floor`
for routine — so the gate never floor-checks exactly the profile where
mis-tagging is most likely, and C3's "the diff decides, not the tag"
defense is quietly off for cheap tasks. The deeper tension: scaffold tasks
legitimately *create* floored paths as stubs; had floors run, GL1 would
block and demand a high-profile panel for a skeleton. Candidate fix (I16):
require risk_floor in ALL profiles' manifests (it is nearly free), and
teach plan-build to reconcile at planning time — either profile
path-creating tasks at their floor, or write floors that exclude the
scaffold phase explicitly (ratified either way). For THIS firing, gating
GL1 under the committed manifest is consistent with the ratified config.

### P2-14 ✅ (what worked) Tick 1 exercised the whole floor, and it held

Statusline rung live end-to-end (preflight normal, 1.5s-old reading);
blocker-card resume into the parked worktree; write-ahead ordering and
generation stamps clean (7→10, no stale-gen); I12 ladder textbook —
haiku FAIL ×2 (effort rung between) → sonnet PASS 42/42, all three
self-reported "pass" claims falsified by ground truth BEFORE panel/gate
spend; window-phase tail correctly capped slots to 1 and the orchestrator
declined to force the operator's cap-3 against it; credential posture held
(checked env, never touched the Keychain).

## Fix log — tick-1 findings batch (2026-07-05, parent)

- **P2-10 FIXED (I14):** `vault.materialize` (manifest-driven, hash-verified)
  + gate step 6b runs the corpus itself — full log vault-side, scrubbed tail
  in-repo, fail-closed on missing vault/empty manifest/hash drift.
- **P2-11 FIXED (I14):** `vault.record_replay` meters every gate-side
  held-out execution; the skill forbids out-of-gate corpus runs.
- **P2-12 FIXED (I15):** validated `task_spawn`/`task_aborted`/`task_parked`
  events + `runlog.worker_event()` builder; `attempt` validated everywhere.
- **P2-13 FIXED (I16):** risk_floor + heldout_tests required on every
  profile's manifest; plan-build carries the floors↔profiles reconciliation
  rule (scaffold-task trap decided at planning time).
- **P2-15 (dissolved):** the suspected model-attribution bug was a misread —
  per-attempt records were exemplary (haiku fail ×2 → sonnet pass, correct
  models throughout; the "haiku pass" was the validator's own record).
- **P2-16 (observation, n=1):** GL1 break-even datapoint — floor-tier
  attempts cost 79k tokens/12min before the standard-tier 28.5k/4min
  success. First real input to the I12 >40% trip-wire; no action yet.
- **I17 (operator ask):** reset-time awareness — `resets_in_s` on every
  decision (live resets_at; operator `weekly_reset_anchor` fallback config,
  rolls +7d, live always wins), `fraction_rate` measured ceiling-free from
  the governor's own log, `reset_headroom` projection, and the scheduler
  waives tail-capping when the projection clears pause (degrade/pause still
  bind; anything unknown stays conservative).

## Themes so far

1. **Composition defects keep outrunning hermetic tests** (P2-4 joins
   P1-5/P1-9/P2-2): governor "unknown" × admission fail-closed = deadlock
   exactly once, at first boot. The I5 smoke test should include a
   cold-start scenario.
2. **Ownership must be explicit in a multi-agent workflow** (P2-5): two
   competent agents fixing the same defect independently produced a worse
   outcome than either alone.
