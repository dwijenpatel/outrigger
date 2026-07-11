# Pilot-3 artifacts — the P3v2-5 evidence set, salvaged

**Salvaged 2026-07-11** from the pilot-3 clone (`repos/cc-agent-harness-test1/`, HEAD `a638acf`)
and its external vault (`repos/cc-agent-harness-test1-vault/`) during the
[reincarnation](../../../reincarnation-plan.md), per its step 1. Until this salvage, the
design's central-thesis result was Tier C in this repo — "observed once, artifact not in tree"
([distilled/internal.md](../../distilled/internal.md) §5). These files are that artifact.

## What P3v2-5 claims, and which file backs each link

The claim ([pilot-3-observations.md](../pilot-3-observations.md) P3v2-5): *GL1-scaffold
attempt 1 passed visible tests, typecheck, and a full 3-lens Opus panel; the held-out corpus
failed 3 tests; attempt 2 (fresh worker, no leakage) fixed it and caught a latent
`dependency_overrides` closure bug.*

| Link in the chain | Artifact |
|---|---|
| Two attempts ran (two full spawn waves: worker + validators ×2) | [state/run-log.jsonl](state/run-log.jsonl) rows 0–9 |
| The 3-lens Opus panel, all PASS | [state/verdicts/GL1-scaffold/](state/verdicts/GL1-scaffold/) — `correctness` / `repro` / `security`, each `model: claude-opus-4-8` |
| The merge-gate stamp that sealed it | [state/gate-stamps/task__GL1-scaffold.json](state/gate-stamps/task__GL1-scaffold.json) (`base: main`, `head: 4b8653f`, `ts: 2026-07-05T21:29:24Z`) |
| The full 11-step gate run (incl. `heldout_drop`, `heldout_tests` "exit 0 over 7 held-out file(s)") | [state/evidence/GL1-scaffold/gate-report.json](state/evidence/GL1-scaffold/gate-report.json) |
| The held-out corpus itself — 7 test files the implementer never saw | [vault/GL1-scaffold/](vault/GL1-scaffold/) |
| **The 41/41 held-out pass** (final replay) | [vault/evidence/gate-heldout-task__GL1-scaffold.log](vault/evidence/gate-heldout-task__GL1-scaffold.log) — `41 passed in 0.58s` |
| The metered replay ledger — 4 replays, timestamps bracketing both attempts (M2 leakage accounting, live) | [vault/evidence/replays.jsonl](vault/evidence/replays.jsonl) |
| The test-author handoffs (spec-only authorship) | [vault/evidence/*.handoff.json](vault/evidence/) |

**Honest bound:** the vault-side log retains the *final* (passing) replay; the attempt-1
3-test failure survives as the replay-meter timestamps plus the two-wave run-log and the
ledger narrative, not as a preserved failing log. n remains 1. What this set upgrades is the
*warrant* — from clone-only assertion to committed, third-party-checkable artifacts (A3) — not
the sample size.

## Also salvaged

- [state/](state/) in full — governor log (the P3v2-12 degrade-hold reading), blocker cards
  (`GL2-fable5-credit-exhaustion` — the 429-at-0-tokens card; `GL2-governor-hold`;
  `GL2-window-pressure-5h`), scheduler log, lessons, ledger events, admission stamp,
  watch-items, plan snapshot, firing-close digest. Backs P3v2-12 (§5's "the governor was right
  and we disobeyed it") with the run-log `task_aborted` rows 10–16.
- [plan/](plan/) — the ratified instrument all three pilots ran byte-identically
  (`PLAN.md`, `ratification.json` content-bound stamp, `floors.json`, `tasks.json`, specs).
  Interpretive context for every GL-task and D/I-number in the ledgers.
- [vault/GL2-auth-tenancy/](vault/GL2-auth-tenancy/) — held-out tests authored for the task
  that never merged (P3v2-12/13): the instrument existed before the implementation attempt,
  which is the point.

**Not salvaged:** the clone's git history (the actual judged diffs live at
`repos/cc-agent-harness-test1`, branch `task/GL1-scaffold`, head `4b8653f`) and the worktree
sibling (`-wt/`). The clones may be deleted once this directory is judged sufficient; that
decision is the operator's.
