# Implementation plan — token/time-optimized harness

Living progress ledger for turning
[../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md) into
working, tested code. **Every autonomous run reads this file first and resumes from the
"Next up" pointer — never restart from scratch.** This mirrors the design's own
"disk is the memory" resume philosophy (design §3 principle 4, §9).

**Standing scope rule (operator, 2026-07-04):** until the design is confidently finalized, the
only durable artifacts in this repository are `docs/research/` and `docs/design/`. This plan
and **all code** (`harness/`, `tests/`, `tools/`) are disposable — throw away or redo freely
when the design moves. The harness does **not** build agent-facing CLIs; deterministic modules
are consumed by hooks and the build-loop skill, not exposed as polished command-line products.

*Re-derived 2026-07-04* against the amended design (13 amendments from the kunchenguid-stack
survey + independent-confirmation pass; evidence in
[../research/tool-surface-and-format-economics.md](../research/tool-surface-and-format-economics.md),
[../research/unattended-operation-prior-art.md](../research/unattended-operation-prior-art.md),
[../research/harness-evaluation-prior-art.md](../research/harness-evaluation-prior-art.md)).

## How to use this file

- Statuses: `not-started` / `in-progress` / `done` / `done (pre-amendment)` / `deferred`
  (with a reason). `done (pre-amendment)` = built and passing tests before the 2026-07-04
  design amendments; keep using it, but its rework increment supersedes conflicting behavior.
- Work one increment at a time: build → tests → tests pass → commit on a feature branch →
  merge → update this ledger. Never commit to `main` directly.
- Ordering below is dependency-aware; within a phase, top-to-bottom. Cross-phase pulls are
  fine when dependencies allow (design §6.1).
- When an increment closes a design decision differently than the doc states, log it under
  **Deviations & open items** — never silently.

## Ground rules (from the design, non-negotiable)

- **O0 floor:** no increment merges without passing tests (design §2).
- Pure stdlib Python 3 for harness library modules; tests are `unittest`
  (`python3 -m unittest discover -s tests -v`). Node is acceptable for the mock-worker rig if
  protocol fidelity demands it.
- **Format policy (design §5.4):** persisted state is compact JSON/JSONL; anything a model
  generates is schema-validated JSON only; digests built for model reading are flattened,
  then rendered as Markdown tables; never pretty-print into model context. No TOON.
- **Turn economy (design §6.1):** every artifact a worker reads carries pre-computed
  aggregates, definitive empty states, and tail-truncated output with disk spill — acceptance
  criteria on every model-facing surface built below.
- Extend `tools/budget-governor/` artifacts; never reimplement them (disposable, but reuse
  beats rewrite while they match the design).
- Never run `run_cache_weight_experiment.sh dry-run|arm-a|arm-b` (spends real quota;
  operator-only). Recording real agent traces for the A6 rig is likewise operator-gated.
- No hard-coded quota magnitudes anywhere — ceilings/estimates are config or
  runtime-calibrated (design §5.1, §10.3).

## Increment map

Layout: harness library modules in `harness/` (config in `harness/config/`), tests in
`tests/`, hooks in `hooks/` (Phase C), agent/skill definitions in `.claude/` (Phase E).

### Phase A — Stage-0 foundations (pure library code, no orchestration yet)

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| A1 | **Run-log module** (`harness/runlog.py`): canonical JSONL task-record schema; append with validation, tolerant read, rolling-window filter, weighted token sum (configurable `cache_read_weight`, §10.2), adapter emitting `validate_predictor.py`'s record shape | §5.1 estimate rung, §8 inputs | — | done (pre-amendment) |
| A2 | **Tier table + spawn allowlist validation** (`harness/config/tiers.json`, `harness/spawncheck.py`): abstract tier → model-id table; explicit `(model, effort)` allowlist validation before any spawn; `require_result` null-check (probe-verified §5.3 correction) | §5.3, §12 Q3 | — | done (pre-amendment) |
| A3 | **Budget governor** (`harness/governor.py`): source ladder statusline → oauth-usage → run-log estimate; occupancy model per window; degrade(0.8)/pause(0.95) thresholds **observe-only by default**; JSONL decision log | §5.1, §11 Stage 0 | A1 | done (pre-amendment) |
| A4 | **Window-aware admission rule** (`harness/admission.py`): P95-quantile forecast; admit/defer against degrade threshold with forecast added burn; conservative margin path when forecast or ceiling unknown | §5.1, §6.2 | A2, A3 | done (pre-amendment) |
| A5 | **Governor driver rules** (amends A3/A1): three-way **failure taxonomy** (agent-reported → continue; retryable → exponential backoff; permanent (auth/credit stderr patterns) → abort firing) as a config-driven pattern table; **sticky `~` estimated-accounting flag** — any window total derived from an `estimate`-rung reading is flagged estimated end-to-end, never silently blended | §5.1 (2026-07-04 amendment) | A1, A3 | done |
| A6 | **Token-free loop test rig**: deterministic mock worker speaking the E1 return schemas — synthetic usage counters (static + cumulative modes), scripted workspace side effects (post-success file mutations), hold-open turns for cancellation paths; recorded-trace replay (normalized JSONL); fixtures committed; **re-recording from real agents is operator-gated** (spends quota) | §11 Stage 0 (2026-07-04 amendment) | A1 (schemas); E1 verdict shape may iterate it | done |

### Phase B — Disk-is-the-memory state

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| B1 | **Task/ledger schema + status index** (`harness/ledger.py`): task records (id, phase, risk profile, hard deps, `mayBeInvalidatedBy`, status), validated transitions, atomic writes, pause/resume marker, `runnable`/`summary` views | §3 p4, §9 | — | done (pre-amendment) |
| B4 | **State-architecture rework of B1** (event-log/reconciliation split): status index becomes an **append-only event log** plus a **derived reconciliation view** whose authoritative inputs are gate/run artifacts and git state (never the last event line); **write-ahead event queue** (durable event recorded before any suppression/progress marker advances; recovery = drain queue); **generation-stamped mutations** (stale expected-generation fails loudly). `runnable()`/`summary()` become reconciliation reads. Digest output rendered per format policy (flattened Markdown table + aggregate header: `tasks: 12 of 47 done, 3 FAIL, 2 blocked`) | §3 p4, §5.4 format policy (2026-07-04 amendments) | B1 | done |
| B2 | **Preflight DAG check + scheduler tick** (`harness/scheduler.py`): cross-phase DAG validation (cycle detection), runnable-set computation over the B4 reconciliation view, `start-early-safe` predicate, critical-path-then-risk priority; concurrency admission calls A4 (incl. per-pipeline cold-prefix warmup cost, §6.2); **window-phase awareness** — heavy fan-out slots early in a fresh window, the tail runs cheap serial work | §6.1, §6.2 | B4, A4 | done |
| B3 | **Liveness guard (observe-only)** (`harness/liveness.py`): per-task step-count cap; **per-task token cap from the §5.1 P95 forecast, checked mid-flight**; repeated-error-signature detection; slow-grind vs predicted bucket; **no-op rule** (zero git delta + zero new artifacts = failed turn, halts the spin); observe-only until false-abort rate proven (§5.6) | §9 (2026-07-04 amendment) | B4 | done |

### Phase C — Zero-token enforcement hooks (all gates fail-closed; advisory layers fail open — design §7)

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| C1 | **Prefix-edit warning hook**: PreToolUse (Edit\|Write matcher) flags mid-firing edits to CLAUDE.md / settings / constraints (silent no-op + cache guard) | §5.2 rule 1 | — | done |
| C2 | **Destructive-git blocker + machinery-paths check**: task branches cannot edit loop machinery; block destructive git; **hook/gate executable config loads only from the ratified default branch at a freshly-fetched commit** (fetch failure → empty config, refuse; never the task branch's copy) | §7 (2026-07-04 amendment) | — | done |
| C3 | **Risk-floor map**: path-glob → minimum-profile, enforced against *actual diff paths* at merge | §7 | B4 | done |
| C4 | **Held-out-test-drop check** at merge | §7 | D1 | done |
| C5 | **Hook self-test harness**: every gate proves itself with a failing case (incl. the vault canary once D1 lands); gates demonstrably fail-closed (a gate that cannot run refuses) | §7 | C1–C4 | done |

### Phase D — Vault + merge gate

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| D1 | **Vault isolation config + canary**: six-layer stack config + canary read-attempt self-test | §5.5, §7 | — | done |
| D2 | **Merge gate script**: clean-checkout reproduction, `--require-clean`, all-must-pass panel verdicts; **typed findings** (`severity × action` with per-step auto-fix budgets; review-class defaults to 0); gate pipeline (not the implementer) applies mechanical fixes; **evidence directory** per gated task (transcripts, gate captures) committed to ride review; gate report output follows turn economy (aggregates, definitive empties, tail-truncate + full log to disk with grep hint) | §7, §6.1 (2026-07-04 amendments) | C-series | done |
| D3 | **Safe-RTS vault replay + leakage budget** (Stage 2 — gated on Stage-1 telemetry) | §5.5 | D1, D2 | done (ships disabled — enabling is the Stage-2 flip) |
| D4 | **Escapes log + calibration machinery**: committed escapes-log format (defects a panel missed — labeled ground truth); **calibration canaries** (plant a known defect the panel must catch before any "0 findings" downgrade is trusted; a miss freezes the downgrade); contract-test kill-rate calibration (a weak visible oracle raises rigor, never lowers it) | §7 self-measuring loop, §3 p5 | D2 | done |

### Phase E — Orchestration surface

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| E1 | **Subagent definitions + verdict/handoff schemas** (`.claude/agents/*.md`, JSON schemas for structured returns): model output is schema-validated JSON only; verdict rationale must **quote reproduced behavior**, never summarize impressions; returns carry aggregates + definitive empty states; every schema includes a one-line `intent` field for the audit trail; handoff schemas carry structured `key_changes_made` ("material outcomes, not activities") and `key_learnings` ("surprising, not captured by prior lessons") feeding the lessons corpus | §4, §6.1, §5.4 format policy (2026-07-04 amendments) | A2 | done |
| E2 | **Build-loop skill** + advisory run marker + headless flags (`DISABLE_NON_ESSENTIAL_MODEL_CALLS`, strict sandbox): **load-bearing procedures invoked phase-gated in the prompt (deterministic text), never trigger-reliant**; situational skills carry explicit trigger conditions; **claims-not-evidence resume**: reconstruct from git/gate/ledger artifacts before acting, never from a model summary; failure taxonomy (A5) wired into the driver; skill inventory checked against the ~15k-char list budget; **pipelining + pre-decompose** (task N+1's spec + contract tests authored while task N validates; next phase pre-decomposed into a provisional planning-only ledger); **lessons corpus mechanics** — orchestrator-owned file, workers read-only, curated injection per spawn (never resident in the prefix); headless quota fallbacks built here: the **statusline-dump shim** + the oauth-usage operator wrapper (§5.1, §12 Q1) | §4, §6.1, §11, §5.4 skills discipline, §7 (2026-07-04 amendments) | A3, A4, A5, A6, B2 | done |
| E3 | **Park-and-continue + ratification queue** (`docs/PROPOSALS.md`): **blocker records** carry repro, options, and a recommendation so one human round-trip resolves them; parked tasks never block unrelated runnable work; queue entries are **decision cards** — Situation → advisory triage (cached per content revision) → recommendation → exactly-one-choice options; **content hash + stale-decision refusal** (a changed proposal is never ratified against an old review); advisory triage fails open, execution stays deterministic post-approval | §6.3, §7 (2026-07-04 amendment) | B4 | done |
| E5 | **Closure gate**: plan snapshot frozen at build start; completion judged against the snapshot under the **fresh-evidence rule** (only evidence newer than the last remediation can decide); bounded remediation rounds; wired as a Stop-hook script | §4 completion gating, §7 | B4, D2 | done |
| E4 | **Skill-routing canaries**: fixture prompts with expected invocation sets **including negative controls** (no skill should fire), run as part of the self-test suite; body fingerprints where invocation telemetry is unavailable | §5.4 skills discipline (2026-07-04 amendment) | E2 | done |

### Phase F — Controller / reflection

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| F1 | **Telemetry roll-up + `docs/EVIDENCE.md` generator** (per-role/tier/effort cost, catch-rate vs the D4 escapes log, calibration results; D2 evidence directories as input); digests rendered per format policy (flattened Markdown tables + aggregate headers) | §8, §5.4 | A1, D2, D4 | done |
| F2 | **Controller lever proposals**: one-lever-at-a-time, sample floors, strengthen-only for protected profiles, queue to ratification (E3 cards) — never auto-applied; lever evaluations follow the **paired-arm template** (one lever = one arm, continuous metric, paired per-task stats, out-of-sample difficulty strata, confirmatory-vs-exploratory labels) | §8 (2026-07-04 amendment) | F1, E3 | done |

### Phase G — Stage-2 wall-clock (deferred until Stage-1 telemetry)

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| G1 | **Pooled lease-based worktree lifecycle**: warm pool, env-setup hooks run once per member, durable leases surviving worker death, fail-closed teardown (landed = patch-ID containment incl. post-squash; refuse when remote unreachable; per-risk opt-in flags, no blanket force) | §6.2 (2026-07-04 amendment) | B2, concurrency cap ≥2 flip | done (machinery built; pool activation is the Stage-2 flip) |

### Phase H — Enforcement wiring + verifier-precision floor (2026-07-04 evening amendments)

From the updated design critique ([../research/landscape-and-novelty.md §4](../research/landscape-and-novelty.md)):
the C/D/E-series built the enforcement *logic*; Phase H makes it **wired, triggered, and
precision-aware**. All gates fail closed; interlocks are inert outside a live firing.

| ID | Increment | Design ref | Deps | Status |
|---|---|---|---|---|
| H1 | **Hook registration**: committed `.claude/settings.json` registering git-guard + prefix-edit-warn (PreToolUse) and the closure gate (Stop); `hooks/closure_gate.py` gains a **Stop-hook stdin mode** (config from a fixed path; **inert when no live run marker** — the gate guards firings, not operator sessions); selftest **fails when registration is absent** or points off the ratified scripts | §7 wiring amendment 1, §11 Stage 0 | C1–C5, E5 | done |
| H2 | **Merge + spawn interlocks** (`harness/interlocks.py`, `hooks/merge_interlock.py`, `hooks/spawn_interlock.py`): during a live firing, `git merge`/`git push` to protected refs requires a **fresh PASS gate stamp bound to branch + HEAD SHA** (run_gate writes stamps on PASS); worker spawns require a **fresh admission stamp** (scheduler tick writes it); both inert outside firings, fail closed inside | §7 wiring amendments 2–3 | H1, D2, B2 | done |
| H3 | **Gate mandatory-step manifest** (`harness/config/gate-required-steps.json`): per-profile required steps loaded from the ratified ref; a required input that is absent **fails closed** — "caller's choice" passes survive only where the manifest says so | §7 wiring amendment 4 | D2 | done |
| H4 | **Executable-repro findings + false-FAIL telemetry**: verdict/finding schema gains a machine-replayable `repro` (command + expectation); the gate replays repro **in the clean checkout** before an error finding blocks; unreproduced findings **downgrade to ask-user** and are counted (per-lens/tier false-FAIL rate lands in the run-log; repro-required per profile) | §7 typed-findings amendment, §8 inputs | D2, E1, A1 | done |
| H5 | **Panel-correlation telemetry + cross-provider card**: calibration aggregates canary trials panel-wide (all-lenses-missed = correlated blind spot, feeds the evidence roll-up); a decision-card factory for the opt-in cross-provider validator on critical profiles | §7 panel amendment, §8 | D4, E3, F1 | done |
| H6 | **Escape-discovery protocol**: deterministic backfill (later-phase defect on a merged surface → escapes-log entry attributed to merging task + panel); sampled **escape-hunt due-check** (budget-governed); downgrade/flip guard requires **discovery channel active**, not just zero escapes | §7 self-measuring amendment | D4 | done |
| H7 | **Evidence leakage policy**: held-out execution output routes to a **vault-side evidence store** covered by the same deny rules; in-repo gate reports **scrubbed against the vault manifest** (vault paths/test identifiers → stable hashes); verdict-verbosity line in the leakage budget | §5.5 point 5 | D1, D2 | done |
| H8 | **Firing preflight + staleness-aware governor**: occupancy readings carry age (stale → margin widens with data age, rung falls through); `preflight()` probes the ladder at firing start — no live-utilization rung reachable → **conservative mode** (tightened thresholds, cheap-serial only) or operator ack | §5.1 amendment | A3, E2 | done |
| H9 | **Spec-ambiguity blockers**: handoff schema gains `spec_ambiguities`; on high/critical profiles they become **blocker records parking the task before implementation spends tokens** (advisory `key_learnings` on lower profiles) | §6.3 amendment | E1, E3 | done |
| H10 | **Worker-side unconditional machinery deny**: `worker_settings()` denies Edit/Write on machinery globs regardless of branch name, merged with the vault fragment — branch prefixes are a dev convenience, not a boundary a worker can adopt | §7 wiring amendment 5 | E2, D1 | done |

### Phase I — pilot-1 fixes (seeded from [../research/pilot-1-observations.md](../research/pilot-1-observations.md))

| ID | Increment | Source | Deps | Status |
|---|---|---|---|---|
| I1 | **`state/` gitignored** — the loop's own bookkeeping must not dirty the tree `require_clean` judges | P1-5 | — | done |
| I2 | **Planning surface**: `plan-build` skill (grilling-method interview — one question at a time with a recommended answer, explore-don't-ask, determinacy bar = a spec-only test-author needs no guesses, hard ratification stop) + `harness/planning.py` (content-bound ratification stamp; `plan_ready` gate: ledger/specs/floors/snapshot/ratification all fail-closed) + build-loop step 0 refuses to fire without it; routing canaries; repo CLAUDE.md | P1-8 | — | done |
| I3 | **Harness reference doc** — one page of shapes (task record, floors, gate call, state-file map) so planning sessions stop source-diving | P1-6 | — | not-started |
| I4 | **Vault config generated + machine-checked** (`vault configure|check` CLI): vault_path must be absolute + outside the repo; worker_settings must equal the regenerated layers 1–3 (hand-edit drift refused); template ships unconfigured and **firings refuse until configured** (build-loop step 2b); committed-config coherence in the selftest | P1-7, P2-3 | — | done |
| I6 | **`plan/**` is machinery** — an implementer must not edit the spec it is judged against (blind validation's shared context is immutable); MACHINERY_GLOBS gains `plan/**`, which flows to the gate step, the PreToolUse hook, and H10 worker denies automatically | P2-2 | — | done |
| I4b | **plan_ready vault check + vault dir lifecycle** (ported from the pilot session's parallel I4 after the P2-5 collision): `planning ready --vault-config` refuses readiness against an unconfigured/drifted/absent vault; `configure` creates the vault dir; ownership rule in CLAUDE.md — machinery evolves upstream only | P2-5 | I4 | done |
| I7 | **Governor source-file robustness** — missing/corrupt source files are skipped rungs (warn + fall through), never tracebacks | P2-2 | — | done |
| I8 | **Bootstrap occupancy assumption** — `--assume-occupancy <frac> --acked-by <op>`: attributed, bounds-checked, sticky-`~`, applies only when no source yields a window; breaks the first-firing deadlock (governor `unknown` × admission fail-closed); skill step 3b documents shim/OAuth/assumption ladder | P2-4 | — | done |
| I9 | **Statusline shim registered as project machinery** (`settings.json` statusLine → `state/statusline-dump.json`; operator-approved): every interactive session auto-produces the quota dump, so the live rung exists and P2-3/P2-4 bootstrap friction disappears whenever a session ran recently (H8 staleness guards idle dumps); registration self-tested | P2-3, P2-4 | H8 | done |
| I10 | **Concrete model id in routing telemetry**: run-log validates optional `model` on task_complete (from spawncheck's resolved params — requested spawn, never worker self-report); evidence roll-up keyed by (role, tier, **model**, effort, profile) so a tiers.json remap never silently blends telemetry (the §8 model-id sample-reset needs to see it); SKILL step 7 records aborted/parked spawns too | design §5.3/§8 gap, found in operator review | A1, A2, F1 | done |
| I9b | **Statusline shim self-resolves its output path** (P2-6: `$CLAUDE_PROJECT_DIR` is hooks-only — statusline gets it via stdin `workspace.project_dir`); settings command hardened; exact skill-budget call in the skill (P2-7) | P2-6, P2-7 | I9 | done |
| I11 | **build-pause skill + pause-request flag**: `loop.request_pause/pause_requested/clear_pause_request` (attributed, durable, fail-safe on corrupt flags, cleared only after the pause lands); build-loop tick step 0 honors the flag as a governor-pause; the skill covers both in-session pause and out-of-band flagging | operator UX request | E2 | done |
| I5 | **Firing smoke test** — scripted walk of the skill's step sequence in a scratch clone via the mock worker; asserts clean tree + green gate end-to-end (hermetic suites missed P1-5/P1-7-class composition defects) | P1 theme 1 | A6 | not-started |

## Stage-gate flips (operational, evidence-gated — design §11)

Not build increments: config/enforcement flips of machinery built above, each gated on the
prior stage's telemetry.

- **Stage 1:** governor thresholds observe-only → enforcing (A3); per-profile effort via the
  spawn path, recorded in the run-log (A2/E1); duration-bucket predictor behind its double
  gate — simple starting-tier lever shows escapes ≈ 0 and $/task down, *and* predictor
  features validated against measured burn; intra-task early-abort observe-only (B3);
  cross-phase DAG scheduling behind the conservative `start-early-safe` predicate (B2).
- **Stage 2:** vault replay + leakage budget (D3); early-abort enforcing once the false-abort
  rate is proven against O0 (B3); concurrency cap 2 under the admission rule (B2); pooled
  worktree lifecycle (G1).
- **Stage 3 (optional, evidence-gated):** bucket×profile starting-tier matrix;
  test-execution caching (non-security surfaces, mandatory cache-defeat on the changed
  surface).

## Standing rechecks (mirror of design §11 Standing)

- Recalibrate window ceilings after **2026-07-13** (promo expiry) and after any design §10.3
  volatility entry.
- Re-check the paused Agent-SDK billing change before relying on window accounting for
  headless firings (design §12 reclassified item).
- Re-run `tools/budget-governor/probe-spawn-portability.js` on any new Claude Code build or
  environment before trusting per-agent `(model, effort)` dispatch.
- **Re-audit the design §4 leverage map on each Claude Code feature wave** — migrate custom
  residue a new built-in now covers (first candidate: build-loop control flow as a Workflow
  script; evaluate, don't mandate). *(added 2026-07-04 evening)*

## Next up

**The pilot firing** (Stage-0 exit criterion, design §11) — deliberately **not** a build
increment. Phase H is complete; every increment in the plan is built and merged (450 tests,
29/29 gate selftest cases). The next unit of work is a small real greenfield build at
Stage-0 settings, producing the first real run-log/canary/calibration data and
operator-gated recorded traces. **Operator-started** — the firing needs the operator to
pick the pilot project and start it (`build-loop` skill). No further machinery before the
pilot: the apparatus has outrun realized scale once already (design §11, landscape §4.1).

<!-- superseded pointer kept for history: -->
**H1 — hook registration** (settings artifact + closure Stop-hook stdin mode + registration
selftest): first Phase-H increment; H2 depends on it.

<!-- superseded pointer kept for history: -->
**E1 — subagent definitions + verdict/handoff schemas** (`.claude/agents/*.md` + JSON
schemas): the first Phase-E increment; A6's mock rig is expected to iterate with the frozen
schema shapes. Previous pointer (B2) is done, as is all of Phases A–D.

## Deviations & open items

- **Resolved 2026-07-04:** design §7 previously said the merge-point checks are "all
  fail-open"; the amended design states the principled split — enforcement gates
  **fail-closed**, advisory layers (triage, suggestions) fail open. The C-series builds to
  that.
- **Estimate-rung window anchoring (A3):** the 5-hour window anchors at first message, but the
  run-log alone doesn't know the anchor. `estimate_from_runlog` uses a trailing window by
  default and accepts an explicit anchor; documented as an approximation, flagged
  `optimistic: true` per design §5.1 — and, post-A5, sticky-`~` end-to-end. *(logged
  2026-07-04)*
- **Admission without a calibrated ceiling (A4):** until ceilings are calibrated from
  telemetry, the rule falls back to a conservative extra margin below the degrade threshold
  (configurable, default 0.15). Revisit when real telemetry exists. *(logged 2026-07-04)*
- **oauth-usage rung:** library parses the response document only; the authenticated fetch is
  a thin operator-side wrapper to be added with E2. Endpoint is unstable/internal — parser is
  defensive by design. Probed 2026-07-04 on this machine: **no credentials file and no Claude
  Code Keychain item are non-interactively accessible**, so the wrapper is mandatory per
  environment; the **statusline-dump shim** (design §5.1/§12 Q1) is the preferred headless
  bridge and should be built alongside it in E2. *(logged 2026-07-04)*
- Model ids in `harness/config/tiers.json` are **config, not code** — re-check after any
  §10.3 volatility event (next standing check: 2026-07-13 promo expiry).
- **A1/B1 format note:** run-log stays JSONL and the ledger stays JSON per the amended format
  policy (they are persisted state read by deterministic code); only *digest views* change
  shape (B4, F1). No rework of the stored formats is needed — verified against the local
  measurement in
  [../research/tool-surface-and-format-economics.md §4.3](../research/tool-surface-and-format-economics.md).

## Session log

- **2026-07-04 (run 2):** Design amended with 13 evidence-backed changes (tool-surface regime
  rule, format policy, fail-closed gates, skills discipline, turn economy, state-architecture
  mechanics, driver rules, ceremony discipline, typed findings, decision cards, token-free
  test rig, worktree pool, paired-arm controller methodology) after the kunchenguid-stack
  survey + independent-confirmation pass; three new research docs added. Plan re-derived from
  the amended design: A5/A6/B4/E4/G1 added, C2/D2/E1/E2/E3/B3/F1/F2 enriched, next-up moved to
  B4. Prior session log discarded per operator instruction (pre-amendment work — A1–A4, B1,
  101 passing tests — remains in-tree as `done (pre-amendment)` and is disposable).
- **2026-07-04 (run 3):** Plan **finalized** against the amended design after a full coverage
  review (every §4–§9 mechanism → an increment or an explicit stage flip). Gaps closed: added
  **D4** (escapes log + calibration canaries + kill-rate calibration — was consumed by F1 but
  built by nothing) and **E5** (closure gate — §4/§7 mechanism with no increment); enriched B2
  (window-phase scheduling), E1 (lessons handoff fields), E2 (pipelining + pre-decompose,
  lessons-corpus mechanics, statusline-dump shim + oauth wrapper), E3 (blocker records,
  re-dropped during the run-2 rewrite); F1 now depends on D4. Added the stage-gate-flips and
  standing-rechecks sections so the rollout stages and volatility watches live in the plan,
  not only the design. §12 trim reflected (two open questions; three reclassified). Next up
  unchanged: **B4**.
- **2026-07-04 (run 4):** Execution begun on the finalized plan. **B4 done** on
  `feat/b4-event-log-reconciliation`, merged; 126 tests passing (was 101). Implementation
  notes: `StatusIndex` removed — replaced by `EventLog` (append-only fsync'd JSONL; torn-tail
  crash model: unacknowledged fragment ignored on read and repaired on next append, interior
  corruption/broken seq chain raises loudly); reconciliation precedence is gate verdict > run
  liveness > event claim, with contradictions surfaced as `discrepancies` and never healed
  silently (appending the correcting event is the caller's decision); dead-run tasks report
  `unknown` (reconciliation-only status, blocks dependents, never persisted);
  `StaleGenerationError` on stale `expected_generation`; consumer cursor cannot pass durable
  events or rewind; `digest()` renders the §5.4 aggregate-header + Markdown-table view with
  definitive empty states. Docs from the amendment/finalization session committed and merged
  the same run. Next: **B2**.
- **2026-07-04 (run 5, in progress):** Phases A and B **complete** — A5
  (`harness/failures.py` taxonomy + governor sticky-`~` rollup), A6
  (`harness/mockworker.py` + zero-quota loop integration test: ledger → governor →
  admission → mock worker → run-log), B2 (`harness/scheduler.py`: preflight cycle reporting,
  critical-path-then-risk tick over the reconcile view, start-early-safe hold, per-pipeline
  warmup charged on concurrent slots, window-phase tail = cheap serial), B3
  (`harness/liveness.py`: step/token/wall caps, collapsed error signatures, no-op rule,
  observe-only). 185 tests passing. Each increment on its own feature branch, merged green.
  Continuing into Phase C (hooks) and Phase D (vault + gate).
- **2026-07-04 (run 5, complete):** **Phases A, B, C, and D are all complete** — 266 tests
  passing. C1–C3 (`harness/hooks.py` + `hooks/`: advisory prefix-edit warning fails open;
  git-guard and risk-floor gates fail closed, floor config read only from the ratified ref —
  a branch tampering with its own floors.json is ignored), D1 (`harness/vault.py` +
  `harness/config/vault-isolation.json`: six-layer declaration validator, canary proven to
  detect a readable vault AND pass a denied one, sha256 manifest), C4
  (`hooks/heldout_drop_check.py`: dropped/mutated held-out tests block, fresh authoring
  passes), C5 (`harness/selftest.py`: every gate proven both directions in hermetic
  fixtures), D2 (`harness/gate.py`: fixed-order clean-checkout gate, typed findings with
  per-step auto-fix budgets, evidence dirs, turn-economy report), D4
  (`harness/calibration.py`: escapes log, canary trials, downgrade frozen on misses/fresh
  escapes, weak-oracle raises rigor), D3 (`harness/replay.py`: safe-RTS plan, unanalyzable →
  fresh, floored never replays, leakage budget; ENABLED_DEFAULT=False). Process note: one red
  suite briefly merged because unittest's exit status was piped through `tail` — caught and
  fixed next command; future gate chains must test the real exit status (exactly the design's
  stale-green lesson, self-inflicted at 1-command scale). Next: **Phase E** (E1 subagent
  definitions + verdict/handoff schemas).
- **2026-07-04 (run 6, in progress):** **Phase E complete** — E1 (`harness/schemas.py` +
  JSON Schemas + `.claude/agents/`: behavior-quoting verdicts, no-op rule at the schema
  layer), E2 (`harness/loop.py` + `.claude/skills/build-loop/SKILL.md` + statusline-dump
  shim + oauth wrapper: run marker, headless env, claims-not-evidence resume, lessons
  corpus, skill budget check), E3 (`harness/ratification.py`: decision cards, content-hash
  stale guard, cached triage, blocker→card), E5 (`harness/closure.py` + Stop-hook: frozen
  tamper-detected snapshot, fresh-evidence rule, bounded remediation escalates), E4
  (`harness/routing_canaries.py` + fixtures: negative controls mandatory, fingerprints).
  Continuing into Phases F and G.
- **2026-07-04 (run 6, complete):** **Phases E, F, and G are all complete — every increment
  in the plan is now built.** 358 tests passing. F1 (`harness/evidence.py`: cost cells per
  role/tier/effort/profile, catch-rate never fabricated at n=0, sticky-`~` totals,
  format-policy EVIDENCE.md), F2 (`harness/controller.py`: one-lever-at-a-time, sample
  floors, protected profiles strengthen-only, downgrades gated on D4 calibration proof,
  proposals emitted as E3 cards carrying paired-arm evaluation plans), G1
  (`harness/worktrees.py`: warm pool, durable leases surviving process death, landed =
  ancestry OR patch-id containment, fail-closed teardown with per-risk flags — machinery
  built; *activation* remains the Stage-2 flip, like D3's replay). Remaining work is
  operational, not build: stage-gate flips (evidence-gated), standing rechecks, the
  operator-gated cache-weight experiment and routing-canary collection runs, and real
  telemetry from a first plan run through the loop.
- **2026-07-04 (run 7, in progress):** Critique-refresh exercise (read-only) re-derived the
  design critique against the as-built system + fresh external evidence (correlated errors,
  false-FAIL base rates); research corpus and design amended (see
  [../research/landscape-and-novelty.md §4](../research/landscape-and-novelty.md) and the
  design's 2026-07-04-evening amendments). **Phase H added** (H1–H10: enforcement wiring +
  verifier-precision floor) and execution begun. Also logged: this file's own status table
  went stale mid-run-6 (F/G done while marked not-started) — a live instance of the
  claims-not-evidence rule; the reconciliation view, not this prose, is the resume authority.
- **2026-07-04 (run 7, complete):** **Phase H complete — every increment in the plan is now
  built.** 450 tests passing (was 358 at run-6 close); gate selftest 29/29 both-direction
  cases. H1 (`.claude/settings.json` registration + closure Stop-hook stdin mode, inert
  without a live run marker; registration selftest), H2 (`harness/interlocks.py` +
  merge/spawn interlock hooks: PASS-only gate stamps bound to branch+HEAD, admission stamps,
  inert outside firings, fail-closed inside), H3 (per-profile required-steps manifest from
  the ratified ref — "caller's choice" omissions fail closed), H4 (executable-repro findings:
  the gate replays repros in the clean checkout before a FAIL blocks; unreproduced findings
  → ask-user adjudication, never escalation fuel; per-lens false-FAIL telemetry →
  run-log `false_fail` events), H5 (`panel_correlation` over per-lens canary results;
  EVIDENCE.md lines; `cross_provider_card`), H6 (`backfill_escape` + `HuntLog` +
  deterministic `hunt_sample` + `discovery_active`; `downgrade_allowed` now freezes without
  an active discovery channel), H7 (vault-side evidence store excluded from the manifest;
  manifest-based scrubbing of gate reports/logs; `verdict_verbosity` leakage line), H8
  (readings carry age → stale rungs fall through, thresholds tighten with data age;
  `preflight()` — no live rung → conservative mode; CLI `--preflight` exit 3), H9
  (`spec_ambiguities` in the handoff schema → blocker records parking high/critical tasks
  pre-implementation), H10 (`machinery_deny_rules()` unconditional in `worker_settings`).
  **Process deviation, logged per ground rules:** H2 was committed directly to `main`
  (`ca8d707`) instead of via a feature branch — caught immediately after; content identical
  to what the merge would have produced; not history-rewritten (destructive-git rule).
  Next: **the pilot firing** (see Next up).
