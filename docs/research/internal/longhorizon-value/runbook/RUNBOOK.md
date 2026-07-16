# Long-horizon value experiment — operator runbook

Everything here is prepared so that starting the experiment is **one command per arm**.
Design authority: [../chain-design.md](../chain-design.md) (REGISTERED 2026-07-16; three
arms, pre-registered arm-F decision rules, canaries at T3/T6, compounding-depth metric).
All 11 specs are ratified and strict-preflight clean under [../specs/](../specs/).
**Every run script below spends real quota and is operator-run by design** (quota
discipline): each refuses to start without `--yes`, and nothing here is wired into any
loop, gate, test, or CI.

## The arms (one command each, independent repos — any order, any spacing)

| Arm | Command | What runs | Measured/estimated notional cost |
|---|---|---|---|
| **H** — gated harness | `./run-arm-H.sh --yes` | 11 × exec-loop full tier: blind Opus author → seal → confined Sonnet 5 implementer (≤3 same-model attempts, counts-only feedback) → hard gate → ff-merge; **stops honestly on blocker** | ~$7.10/task measured → **~$80** |
| **N** — diligent Sonnet | `./run-arm-N.sh --yes` | 11 × fresh Sonnet 5 session on `main`: same spec/context/checks as H's implementer, no gate, no stop channel | ~$2–3/task → **~$30** |
| **F** — frontier solo | `./run-arm-F.sh --yes` | same as N with Opus 4.8 (budget-neutral challenge to the gate) | ~$5–7.6/task → **~$60–85** |

Sessions run serially within an arm (~25 min/task measured on the pilot ⇒ roughly a
working day per arm, unattended). Arms are independent (separate clones, ledgers,
held-out roots) — run them in the same window or days apart; each is resumable
(completed work is skipped on re-run).

## Before first run (one-time, free)

```sh
./setup-arms.sh          # toolchain probe, 3 arm clones @ c646832, held-out roots, admission
./run-arm-N.sh --dry-run # free: builds all 11 bundles, launcher prints what WOULD spawn
./run-arm-F.sh --dry-run
```

## Recommended before arms: the second held-out slice (`./author-slice2.sh --yes`, ~$45)

The in-loop blind suites **gate arm H and then grade every arm** — that circularity is
named in the chain design; the pre-registered arm-F rules and the canaries survive it, but
head-to-head silent-wrong *rates* need an oracle no arm was optimized against. This script
authors that second slice (11 fresh blind Opus authors against base, sealed, grading-only).
Skipping it is legitimate — it just restricts head-to-head claims to canaries + arm-F rules.

## Registered operational rules (protocol details fixed before any run)

- **Arm N/F prompt parity**: the ungated sessions receive the exec-loop implementer's
  instruction body verbatim (title, spec, plan goal/constraints/decisions, the same
  checks, the same commit protocol) with exactly one delta — they work on `main` directly
  instead of a confined worktree. No blind suite, no gate, no retry, no stop channel.
- **Arm N/F no-stop-channel rule**: a session that ends without committing (or with
  failing self-checks) is recorded on the ledger (`head_before == head_after`) and the
  chain **proceeds to the next task** — downstream compounding is the phenomenon under
  measurement, not an error to prevent. Only launcher-level failures (refusal, spawn
  error) abort a run: those are environment problems, not arm outcomes.
- **Arm H stop rule**: any exec-loop blocker halts the arm (that IS the honest-stop
  channel). Adjudicate via the two doors (amend spec → re-ratify → rerun, or edit suite →
  `seal --retire --adjudicated-by …` → rerun), append the `lesson_target` ledger record,
  re-run the script; completed plans are skipped via `runs/arm-H/completed.txt`.
- **Timeout parity**: 3600 s per implementer session in every arm.
- **Outcome vs infrastructure (all arms, same classification)**: a session that
  *completes* is an arm outcome, committed or not. A session that ends abnormally is
  infrastructure until adjudicated: a detected usage-window wall halts consuming nothing
  (the task/attempt is redone after the reset); any other abnormal end halts for operator
  adjudication — in N/F, `--accept-failure TASK_ID` records it as the arm's real outcome
  and continues. Infrastructure halts are never graded as honest-stops.
- **No mid-run peeking**: grading artifacts (suite replays, overlap runs) are produced
  only after an arm finishes; no arm ever receives feedback from them.

## Quota walls mid-run (expected, not exceptional)

A full arm is a working day of serial sessions, so hitting a 5-hour window cap mid-run is
the NORMAL case, not a failure. All three arms halt cleanly and resume exactly:

- **Arm H**: the exec-loop detects wall-shaped session failures (`window-wall` blocker,
  vendor strings, fail-open) and halts **without consuming the attempt** — no gate verdict
  is recorded, so re-running `run-arm-H.sh --yes` after the reset redoes that same attempt;
  completed plans are skipped, sealed suites persist. A wall blocker needs no two-door
  adjudication — just re-run. (Unrecognized errors fall back to normal attempt handling —
  fail-open means a pattern miss costs a wasted attempt, never a stranded run.)
- **Arms N/F**: the runner uses the same wall heuristic — wall ⇒ halt (exit 3), nothing
  recorded, task redone on re-run. Weekly cap: identical, longer wait. Sessions are
  serial, so at most one session's partial work is lost at any wall.
- **author-slice2.sh**: fail-fast; sealed workspaces skip on re-run, an unsealed leftover
  is cleared and re-authored.
- **Grading and setup are quota-free** — walls cannot affect them.

## While an arm runs

- Arm H artifacts: `<heldout-root>/_runs/<plan>/` (bundles, gate reports, blocker.json);
  ledger `runs/arm-H/ledger.jsonl`.
- Arm N/F artifacts: `runs/arm-{N,F}/bundles/…` (instructions, params, result, transcript);
  ledger `runs/arm-{N,F}/ledger.jsonl` (per task: `committed`, heads, usage).
- Summaries: `python3 ../../../../../tools/run-ledger/ledger.py summarize runs/arm-H/ledger.jsonl`

## After the runs (free, post-hoc, non-adaptive)

```sh
# Replay every sealed suite (in-loop slice + slice 2 if authored) against each arm:
python3 grade_arm.py --arm-repo ~/repos/eaitl-arm-H \
    --workspaces ~/repos/eaitl-arm-H-heldout ~/repos/eaitl-heldout-slice2 \
    --out runs/arm-H/grade-report.json     # repeat for arm-N, arm-F
# Per-task self-tests-vs-blind-suite value readout (CPU-only mutation proxy):
python3 ../../../../../tools/test-overlap/…   # per its README, operator-run
```

Grading judgments made from the reports + ledgers (all pre-registered in chain-design):
three outcomes per task (correct-complete / honest-stop / silent-wrong), compounding
depth per landed silent-wrong, the arm-F decision rules, canary hits at T3/T6.

## Open decisions (none block starting)

1. **Second held-out slice** — recommended; one command above; skipping restricts
   head-to-head claims (chain-design "one circularity to control").
2. **Oracle granularity** (end-state-only vs per-step-accumulated + final) — a
   grading-time choice; the sealed suites support either; leaning per-step + final.
3. **Naive one-session floor** (`/goal` whole-plan) — optional cheap extra arm; subsumed
   by arm N per the settled decision; run only if wanted for the writeup.
4. **Continuous-thinking 4th arm** — named-but-unbuilt, default OFF (registered).
