# Implementation plan — token/time-optimized harness

Living progress ledger for turning
[../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md) into
working, tested code. **Every autonomous run reads this file first and resumes from the
"Next up" pointer — never restart from scratch.** This mirrors the design's own
"disk is the memory" resume philosophy (design §3.4, §9).

## How to use this file

- Statuses: `not-started` / `in-progress` / `done` / `deferred` (with a reason).
- Work one increment at a time: build → tests → tests pass → commit on a feature branch →
  merge → update this ledger. Never commit to `main` directly.
- Ordering below is dependency-aware; within a phase, top-to-bottom. Cross-phase pulls are
  fine when dependencies allow (the design's own §6.1 scheduling principle).
- When an increment closes a design decision differently than the doc states, log it under
  **Deviations & open items** — never silently.

## Ground rules (from the design, non-negotiable)

- **O0 floor:** no increment merges without passing tests (design §2).
- Pure stdlib Python 3 for harness modules (matches `tools/budget-governor/` — no deps,
  no network in library code). Tests are `unittest`, run via
  `python3 -m unittest discover -s tests -v`.
- Extend `tools/budget-governor/` artifacts; never reimplement them.
- Never run `run_cache_weight_experiment.sh dry-run|arm-a|arm-b` (spends real quota;
  operator-only). `gen-filler`/`summarize` are free.
- No hard-coded quota magnitudes anywhere — ceilings/estimates are config or runtime-calibrated
  (design §5.1, §10.3).

## Increment map

Layout: harness library modules in `harness/` (config in `harness/config/`), tests in
`tests/`, hooks in `hooks/` (Phase C), agent/skill definitions in `.claude/` (Phase E).

### Phase A — Stage-0 foundations (pure library code, no orchestration yet)

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| A1 | **Run-log module** (`harness/runlog.py`): canonical JSONL task-record schema (profile, tier, model_id, effort, token components, outcome, escaped, predicted_bucket, wall_secs, ts); append with validation, tolerant read, rolling-window filter, weighted token sum (configurable `cache_read_weight`, §10.2), adapter emitting `validate_predictor.py`'s record shape | §5.1 estimate rung, §8 inputs | — | done |
| A2 | **Tier table + spawn allowlist validation** (`harness/config/tiers.json`, `harness/spawncheck.py`): abstract tier → model-id table; explicit `(model, effort)` allowlist validation before any `agent()`/`Workflow` call; `require_result` null-check (invalid ids do NOT fail loud — probe-verified §5.3 correction); per-profile spawn params from `profile-tier-estimates.json` | §5.3, §12 Q3 | — | done |
| A3 | **Budget governor** (`harness/governor.py`): source ladder statusline → oauth-usage → run-log estimate (flagged optimistic); occupancy model per window (five_hour / seven_day / seven_day_sonnet); degrade(0.8)/pause(0.95) thresholds **observe-only by default**; JSONL decision log; CLI for between-task checks | §5.1, §11 Stage 0 | A1 | done |
| A4 | **Window-aware admission rule** (`harness/admission.py`): P95-quantile forecast from `profile-tier-estimates.json` (widened when sample < floor, never fabricated when null); admit/defer against degrade threshold with forecast added burn; conservative margin path when forecast or ceiling unknown | §5.1, §6.2 | A2, A3 | done |

### Phase B — Disk-is-the-memory state

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| B1 | **Task/ledger schema + status index** (`harness/ledger.py`): task records (id, phase, risk profile, hard deps, `mayBeInvalidatedBy` soft edges, status), validated status transitions, atomic (temp+rename) status-index writes, governor pause/resume marker, resume-from-disk view (`runnable`/`summary`) | §3.4, §9 | — | done |
| B2 | **Preflight DAG check + scheduler tick** (`harness/scheduler.py`): cross-phase DAG validation (cycle detection), runnable-set computation, `start-early-safe` predicate, critical-path-then-risk priority; concurrency admission calls A4 (incl. per-pipeline cold-prefix warmup cost, §6.2) | §6.1, §6.2 | B1, A4 | not-started |
| B3 | **Liveness guard (observe-only)** (`harness/liveness.py`): per-task step-count cap, repeated-error-signature detection, slow-grind vs predicted bucket; observe-only until false-abort rate proven (§5.6) | §9 | B1 | not-started |

### Phase C — Zero-token enforcement hooks

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| C1 | **Prefix-edit warning hook**: PreToolUse (Edit\|Write matcher) flags mid-firing edits to CLAUDE.md / settings / constraints (silent no-op + cache guard) | §5.2 rule 1 | — | not-started |
| C2 | **Destructive-git blocker + machinery-paths check**: task branches cannot edit loop machinery; block destructive git | §7 | — | not-started |
| C3 | **Risk-floor map**: path-glob → minimum-profile, enforced against *actual diff paths* at merge | §7 | B1 | not-started |
| C4 | **Held-out-test-drop check** at merge | §7 | D1 | not-started |
| C5 | **Hook self-test harness** (every gate proves itself with a failing case, incl. the vault canary once D1 lands) | §7 | C1–C4 | not-started |

### Phase D — Vault + merge gate

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| D1 | **Vault isolation config + canary**: six-layer stack config (sandbox denyRead, Read/Edit deny rules, strict-mode flags, out-of-scope config, egress notes, per-role processes) + canary read-attempt self-test | §5.5, §7 | — | not-started |
| D2 | **Merge gate script**: clean-checkout reproduction, `--require-clean`, all-must-pass panel verdicts | §7 | C-series | not-started |
| D3 | **Safe-RTS vault replay + leakage budget** (Stage 2 — gated on Stage-1 telemetry) | §5.5 | D1, D2 | not-started |

### Phase E — Orchestration surface

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| E1 | **Subagent definitions + verdict/handoff schemas** (`.claude/agents/*.md`, JSON schemas for structured returns) | §4, §6.1 | A2 | not-started |
| E2 | **Build-loop skill** + advisory run marker + headless flags (`DISABLE_NON_ESSENTIAL_MODEL_CALLS`, strict sandbox) | §4, §11 | A3, A4, B2 | not-started |
| E3 | **Park-and-continue + ratification queue** (`docs/PROPOSALS.md` format, blocker record format) | §6.3, §7 | B1 | not-started |

### Phase F — Controller / reflection

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| F1 | **Telemetry roll-up + `docs/EVIDENCE.md` generator** (per-role/tier/effort cost, catch-rate vs escapes log) | §8 | A1 | not-started |
| F2 | **Controller lever proposals** (one-lever-at-a-time, sample floors, strengthen-only for protected profiles, queue to ratification — never auto-applied) | §8 | F1, E3 | not-started |

## Next up

**B2 — preflight DAG check + scheduler tick** (`harness/scheduler.py`): cycle detection over
the cross-phase dep graph, `start-early-safe` predicate over `may_be_invalidated_by` soft
edges, critical-path-then-risk prioritization, concurrency admission via A4 (including the
per-pipeline cold-prefix warmup cost, §6.2). B1's `runnable()` is the candidate-set input.
C1/C2 (hooks) and D1 (vault config) are dependency-free alternatives if B2 stalls.

## Deviations & open items

- **Design §7 says the merge-point checks are "all fail-open"** — that reads as a typo for
  fail-closed (an enforcement gate that fails open is not a gate) or possibly "fail loud".
  Plan: implement merge/risk-floor gates fail-closed with loud diagnostics; flag for operator
  ratification when C-series lands. *(logged 2026-07-04)*
- **Estimate-rung window anchoring (A3):** the 5-hour window anchors at first message, but the
  run-log alone doesn't know the anchor. `estimate_from_runlog` uses a trailing window by
  default and accepts an explicit anchor; documented as an approximation, flagged
  `optimistic: true` per design §5.1. *(logged 2026-07-04)*
- **Admission without a calibrated ceiling (A4):** tokens→occupancy conversion needs a window
  ceiling that is deliberately never hard-coded. Until ceilings are calibrated from telemetry,
  the rule falls back to a conservative extra margin below the degrade threshold
  (configurable, default 0.15). Revisit when real telemetry exists. *(logged 2026-07-04)*
- **oauth-usage rung:** library parses the response document only; the actual authenticated
  fetch is a thin operator-side wrapper to be added with E2 (headless firing support). The
  endpoint is unstable/internal — parser is defensive by design. *(logged 2026-07-04)*
- Model ids in `harness/config/tiers.json` are **config, not code** — re-check after any
  §10.3 volatility event (next standing check: 2026-07-13 promo expiry).

## Session log

- **2026-07-04 (run 1):** Plan created. Implemented A1–A4 with test suites
  (`tests/test_runlog.py`, `tests/test_spawncheck.py`, `tests/test_governor.py`,
  `tests/test_admission.py`); all passing, plus existing `--selftest` scripts re-verified.
  Merged `feat/stage0-foundations`. Then implemented B1 (`harness/ledger.py` +
  `tests/test_ledger.py`) on `feat/b1-ledger-status-index`; 101 tests passing total.
  Ledger design notes: `done` is terminal (reopening is an operator file edit, never a
  silent loop action); a corrupt status index raises loudly instead of resetting statuses;
  cycle detection deliberately deferred to B2's preflight. Next run starts at B2.
