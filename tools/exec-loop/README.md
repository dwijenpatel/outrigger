# exec-loop — the first composition

**v2 artifact #5** ([design](../../docs/design/evidence-based-harness.md) D3/D4/D5, built to
R5/D15 from the ratified [plan](../../plans/exec-loop.plan.json)). One thing well: **walk a
ratified plan task-by-task, unattended** — composing the four existing artifacts and a
swappable worker launcher into the full correctness chain:

```
for each task, serially:
  materialize authoring workspace   (heldout-suite CLI, outside the repo)
  launch fresh TEST-AUTHOR          (launcher contract; Opus @ xhigh)
  seal the held-out suite           (fails-on-base policy; ledger anchor)
  launch fresh IMPLEMENTER          (confined worktree; Sonnet @ xhigh)
  protected-paths check             (machinery-touching diff -> blocker, never gated)
  gate the MERGED tree              (task checks + verify + sealed suite)
  merge on pass                     (gate verify first)          [retry once: Opus @ xhigh]
  record everything                 (run-ledger CLI)
```

Composition rule (R5): sibling artifacts are invoked **only as subprocess CLIs**; workers only
through the [launcher file contract](launchers/CONTRACT.md) — tool-neutral by decision 10, so
the named first extension (Codex CLI) is one launcher file plus one smoke probe, never loop
surgery. Pure stdlib.

## CLI

```
python3 loop.py run --plan PLAN.json --repo REPO --heldout-out DIR
                    [--config CONFIG.json] [--launcher PATH] [--ledger PATH]
```

Exit codes: **0** plan complete · **1** blocker (`blocker.json` in the run dir; all automated
progress stopped, operator adjudication required) · **2** usage/config/admission error.

**Config** (JSON overriding `DEFAULT_CONFIG`): `workers` — `(tool, model, effort)` triples for
`author`, `implementer_a1`, `implementer_a2`; `launchers` — the per-tool registry
(`{"claude": …/claude_p.py, "codex": …/codex_p.py}`) selected by each worker's `tool`, so a
mixed-tool plan is a config edit; `launcher` — a global override that wins for every tool
(the CLI `--launcher` flag sets it; tests and single-tool runs). An unconfigured tool is an
`unknown-worker-tool` blocker raised before the first spawn. Also: `protect_paths` (defaults
include the instruction surfaces — `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.agents/`,
`.codex/` — since a worker that edits them steers every later spawn); `author_timeout_s` /
`implementer_timeout_s`; `max_attempts` (default 2); `ledger` (default:
`<workdir>/ledger.jsonl`, so the artifact is standalone; point it at a repo ledger for real
runs).

## Guarantees

- **Admission**: refuses any plan that fails `plan-preflight check --require-ratified`; task
  order comes from `plan-preflight order` — DAG logic is never reimplemented.
- **Risk tiers (operator-declared, 2026-07-12)**: `plan.risk_tier` / per-task `tier` ∈
  `full | gate-only | bare`, absent = **full**. `full` = the whole pipeline as below.
  `gate-only` = the task's stated checks behind the gate, no held-out suite (a gate-only task
  with zero checks is refused — a gate with nothing to run is a rubber stamp). `bare` = one
  strong session (config `workers.bare`), single attempt, no gate. At **every** tier:
  protected paths never auto-merge, landing is ff-only-or-refuse, and the tier is stamped on
  spawn/gate/merged ledger records — lowering the guard is always visible in the record.
  Closure replays suites only where suites exist and records an all-bare composition honestly
  (`checks: 0`).
- **Blindness by ordering**: the suite is sealed before the implementer's first token; the
  seal's timestamp precedes the implementation branch — provable from artifacts.
- **Confinement intent per spawn**: the implementer's launcher receives
  `{deny_read: [workspace], sandbox: true, network: true}`; launchers translate or **refuse**
  (fail-closed). Deny rules are monotonic across scopes (vendor commitment) — a worktree
  settings file cannot remove them.
- **Counts-only held-out feedback** (decision 5): a retry sees its own checks' output in full
  and only `exit + counts (contents withheld)` for the held-out suite. The redaction has its
  own test — a redaction bug is a silent leak.
- **Halt-all** (decision 6): cap 2 attempts (Sonnet → Opus), then `blocker.json`, ledger
  record, exit 1. Nothing auto-approves, nothing skips.
- **No state file** (decision 7): progress derives from git ancestry + seals + the append-only
  ledger on every start; interrupted work (unsealed workspaces, uncommitted worktrees) is torn
  down and redone; sealed workspaces are never auto-removed.
- **Single-writer is repo-scoped** (D4; hardened 2026-07-12): a `flock` in the target repo's
  git common dir — two loops cannot write one repository, regardless of plan names or heldout
  dirs. A second per-plan-workdir `flock` additionally keeps two runs of one plan from sharing
  bundles/reports.
- **The judged tree is what lands, or nothing does** (hardened 2026-07-12): after gate verify,
  the merge is `--ff-only` against the report's pinned source SHA — if main moved mid-flight
  or the worker rewrote history, the land refuses (`merge-not-fast-forward` blocker) instead
  of landing a tree no gate ever judged.
- **Whole-build closure grants completion** (D3; hardened 2026-07-12): per-task gates only run
  the current task's verifiers, so a later merge can silently regress an earlier task. After
  the last task, closure re-runs **every task's checks and every sealed suite** against final
  main via the merge-gate, stamped with the plan-snapshot hash + main SHA and recorded in the
  ledger; exit 0 exists only behind that report (`closure-failed` blocker otherwise; restart
  skips only on an exact main+plan match). Closure results reach only the operator — the D2
  reuse budget is untouched.

## Threat model

The workers are the in-model adversaries. **The worker-diff channel** — an implementer
shipping an edit to the gate, the plan, the ledger, or the tools inside its task diff (the
published evaluator-edit move, arriving through the merge) — is closed by the
**protected-paths interlock**: touched paths are checked against the protect list *before*
gating, and any hit is an automatic blocker for operator hand-review; the plan itself is
snapshotted at loop start; the loop's code runs from the main checkout, out of worker reach
mid-run. **Stated honestly, this does not stop**: malicious *product* code that passes every
check (the gate proves checks pass, nothing more — weak checks, weak gate), or vendor sandbox
escapes — those are *noticed* (seal `verify` before every suite run, the ledger's manifest
anchor, your review) rather than prevented. A sandbox that cannot *start* is a separate axis:
the vendor default silently runs unsandboxed; the launcher sets `sandbox.failIfUnavailable`
so that case aborts the spawn instead (fail-closed, operator-caught 2026-07-12). The
enforcement mechanisms themselves are
vendor-build behavior: **probed by [the smoke](SMOKE.md), re-probed every release, never
trusted from documentation.**

## Non-goals (each names its upgrade path)

No pipelining (named upgrade; inherits staleness-check, depth-1, waste-metric requirements).
No continue-past-blocker (v1.1, gated on measured adjudication data). No park-at-wall (the
separate D12 artifact). No notifications (stage 3). No boundary probe (its own artifact). No
mid-run re-planning (blockers, always). Codex launcher: landed 2026-07-13
(`launchers/codex_p.py`), smoke-pending — no real plan uses it until its operator-run smoke
passes (SMOKE.md).

## Composition examples

```sh
# A real run (repo ledger, real launcher):
python3 tools/exec-loop/loop.py run --plan plans/foo.plan.json --repo ~/repos/app \
  --heldout-out ~/repos/app-heldout --ledger docs/research/internal/v2-ledger.jsonl

# Afterward — the run is fully reconstructable from the ledger:
python3 tools/run-ledger/ledger.py summarize docs/research/internal/v2-ledger.jsonl

# Blocker adjudication: read blocker.json, resolve through the two doors
# (amend the spec -> re-ratify -> rerun; or edit the suite -> seal --retire
# --adjudicated-by ... -> rerun), then append the lesson_target record:
python3 tools/run-ledger/ledger.py append docs/research/internal/v2-ledger.jsonl \
  --kind outcome --subject exec-loop/<plan>/<task>/adjudication \
  --data '{"lesson_target": "interview|test-author-role|neither", "generalizable": false}'
```

## Measurement & deletion criterion (R2)

The loop is judged by **unattended tasks landed per operator intervention** — every spawn,
gate, merge, and blocker is on the ledger, so the ratio is computable per run. If real usage
shows the operator babysitting every run, the composition has failed its point: measure, then
simplify or delete. The escalation rate (gate-a2 records / gate-a1 records) is decision 3's
revisit metric.

## Tests · versioning · the smoke

`python3 tools/exec-loop/test_exec_loop.py` — 25 tests: the launcher contract (fail-closed ×4,
timeout kill, dry-run), the task cycle (redaction silent-leak test, escalation params,
protected-path block-before-gate, suite reuse/staleness), the walker (admission, lock,
derive-state restart), and the five ratified e2e scenarios through the real CLI. **The vendor
contract is deliberately unproven by these tests** — that is [SMOKE.md](SMOKE.md)'s job,
operator-run because it spends quota. Contracts **v1**; cross-artifact drift is **T11**'s
subject, and this artifact is its largest live integration (four CLIs + one launcher seam).
