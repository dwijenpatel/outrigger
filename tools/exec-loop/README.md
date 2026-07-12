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
`author`, `implementer_a1`, `implementer_a2`; `protect_paths`; `author_timeout_s` /
`implementer_timeout_s`; `max_attempts` (default 2); `launcher`; `ledger` (default:
`<workdir>/ledger.jsonl`, so the artifact is standalone; point it at a repo ledger for real
runs).

## Guarantees

- **Admission**: refuses any plan that fails `plan-preflight check --require-ratified`; task
  order comes from `plan-preflight order` — DAG logic is never reimplemented.
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
  down and redone; sealed workspaces are never auto-removed. One `flock` per plan directory —
  two loops cannot walk the same plan.

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
anchor, your review) rather than prevented. The enforcement mechanisms themselves are
vendor-build behavior: **probed by [the smoke](SMOKE.md), re-probed every release, never
trusted from documentation.**

## Non-goals (each names its upgrade path)

No pipelining (named upgrade; inherits staleness-check, depth-1, waste-metric requirements).
No continue-past-blocker (v1.1, gated on measured adjudication data). No park-at-wall (the
separate D12 artifact). No notifications (stage 3). No boundary probe (its own artifact). No
mid-run re-planning (blockers, always). No Codex launcher yet (first post-confidence
extension).

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
