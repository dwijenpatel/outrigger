# merge-gate — a blocking gate over the merged tree

**v2 artifact #2** ([design](../../docs/design/evidence-based-harness.md) D1/D5, built to
R5/D15). One thing well: **judge a candidate change by executing sound verifiers on the real
merge of base + candidate in a pristine throwaway worktree**, emit a stamped report, and exit
0 only on all-pass. Its `verify` subcommand re-checks a stamp against the repo's *current*
refs — the anti-merge-skew interlock.

Standalone by construction: pure stdlib Python 3 + git, no imports from anything else in this
repo, usable on any repository. It knows nothing about what the checks are — pytest, `tsc`,
`make lint`, anything with an exit code composes.

## Contract

```
python3 gate.py run --repo R --base main --ref CANDIDATE \
    --check "CMD" [--check "CMD" …] [--report FILE] [--timeout SECS]
python3 gate.py verify --report FILE [--repo R]
```

**Exit codes:** `0` pass / stamp fresh · `1` fail, merge conflict, or stamp stale · `2` usage
or environment error. There is **no advisory mode** (a gate that can be advised past is not a
gate — D5) and **no zero-check invocation** (a gate with nothing to check must error, never
vacuously pass — the v1 "skippable-by-omission" defect class).

**What `run` does, in order**

1. Resolves `--base` and `--ref` to SHAs; both go in the stamp.
2. Creates a detached **throwaway worktree at base** — clean-checkout reproduction; the
   caller's dirty working tree can never leak into the verdict.
3. Performs a real `merge --no-ff --no-commit` of the candidate **onto base-as-of-now** and
   judges *that* tree — a change is only ever proven green against what it will actually land
   on (the v1 **B-4** merge-skew lesson, made structural). Conflict ⇒ FAIL with the conflicted
   paths named; checks don't run.
4. Runs **every** `--check` via the shell in the merged worktree (run-all, not fail-fast, so
   the report names every failing verifier). All must exit 0. Each check has a hard
   **deadline** (`--timeout`, default 1800s) — a hung verifier is a FAIL, not a wait (the v1
   38-minute-hang lesson, P3v2-13).
5. Writes the stamped report (always, pass or fail), prints a compact summary to stdout,
   removes the worktree.

**The report** (`merge-gate-report.json` by default): `tool`, `ts`, `repo`,
`base{ref,sha}`, `source{ref,sha}`, `merge{performed, up_to_date, conflicts[]}`,
`checks[{cmd, exit, timed_out, duration_s, output_lines, output_tail}]` (tail capped at 100
lines), `ok`.

**What `verify` proves:** the report is a PASS **and** `base.ref` still resolves to the
stamped `base.sha` **and** `source.ref` still resolves to `source.sha`. If the base moved
after gating, the stamp is stale — the change was never proven against today's base. This is
the composable interlock:

```sh
python3 tools/merge-gate/gate.py verify --report gate.json && git merge task/foo
```

## Composition examples

```sh
# Gate a task branch with two verifier modalities, then merge only through it
python3 tools/merge-gate/gate.py run --repo . --base main --ref task/foo \
  --check "python3 -m pytest -q" --check "python3 -m mypy src/" --report gate.json \
  && python3 tools/merge-gate/gate.py verify --report gate.json \
  && git merge --ff-only task/foo

# Record the outcome in a run-ledger (composition, not coupling — neither tool knows the other)
python3 tools/run-ledger/ledger.py append v2-ledger.jsonl \
  --kind run --subject merge-gate/task-foo --data-file gate.json
```

## Boundaries the caller owns

The gate proves *the merged tree passes the given checks* — nothing more. It does not fetch
(refs are judged as they exist locally), does not choose the checks (weak checks ⇒ weak gate:
who authors the tests is the moderator, design D2), does not perform the merge, and does not
prevent a caller from merging without it — wiring it as the *only* path to merge is the
composition layer's job (D5).

## Measurement & deletion criterion (R2)

Judged by FAIL catches: every `run` whose report is recorded gives the count of candidate
changes that claimed readiness and failed the gate (v1 precedent: 3/3 worker "pass" claims
falsified before spend, P2-14). If real usage shows the gate catching nothing the checks'
plain invocation wouldn't have caught at equal cost, delete it; that deletion is a result.

## Tests · versioning

`python3 tools/merge-gate/test_gate.py` — 13 tests: merged-tree judging (a check that can only
pass on base-as-of-now **plus** the change), all-must-pass, conflict naming, timeout-as-FAIL,
dirty-tree non-leakage, worktree cleanup, zero-check refusal, and the **B-4 regression**
(stamp goes stale the moment base moves). Contract is **v1**; versioning discipline is
deliberately unsettled until the first real two-artifact integration
([design](../../docs/design/evidence-based-harness.md) **T11**).
