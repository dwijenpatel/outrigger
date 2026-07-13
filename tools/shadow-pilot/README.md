# shadow-pilot — one T2 shadow comparison per invocation

Runs the amended pilot-1 comparison
([protocol + Amendment 1](../../docs/research/internal/t2-pilot-1/protocol.md)) for **one
task the harness has already landed**: a third blind author writes an **arbiter suite** from
the ratified spec against the pre-task base state; the **plain-assistant shadow** attempts the
same spec in a throwaway clone (its work never lands); both landed states are graded by the
sealed arbiter suite, symmetrically; one comparison record is appended to `shadow-log.jsonl`.

**Spends real quota** (one author + one shadow session, ≈ $3–4): operator-run or
operator-directed, never wired into the loop, gates, or CI. Standing quota rule applies.

## Invocation

```sh
python3 tools/shadow-pilot/shadow.py \
  --plan <ratified plan.json> --task <task-id> \
  --repo <real repo> --base <sha> --merged <sha> \
  --out <shadow dir> --launcher tools/exec-loop/launchers/claude_p.py
```

`--base` and `--merged` come from the harness's own artifacts: the merged attempt's gate
report binds them (`base.sha`, and the landed commit is the ledger `merged` record's `sha`).
`--model` defaults to `claude-opus-4-8` (the protocol's N0 arm); `--effort xhigh`.

## What it writes (per comparison, under `--out`)

- `shadow-log.jsonl` — the accumulating comparison log (run-ledger envelope; one
  `measurement` record per comparison: both arms' arbiter verdicts, seal sha, usage/cost,
  paths).
- `<task>-<ts>/` — the artifacts: `arbiter/` (sealed suite), `base-clone/`, `shadow-clone/`,
  both worker bundles, both grade reports, and the **blinded review pair**: `diff-A.patch`,
  `diff-B.patch`, `SEALED-mapping.json` (open the mapping only *after* reviewing; record
  whether you could tell which arm was which).

## Contamination walls (enforced via launcher deny-read intent)

The arbiter author never sees either implementation (the live repo — which holds arm H's
landed code — is denied; it references a base-SHA clone instead). The shadow never sees the
arbiter suite or arm H. The arbiter is sealed before the shadow spawns. Grading uses the
self-judge gate (`--base X --ref X`), so PASS means exactly "these commands exited 0 against
that committed state."

## Composition (R5)

Standalone: composes with heldout-suite, merge-gate, and run-ledger strictly as subprocess
CLIs; workers only through the launcher file contract. Tested end-to-end with the mock
launcher (`test_shadow.py`, no quota). Ordering bias note (Amendment 1): the shadow always
runs *after* the real harness task, so same-account caching may cheapen it — direction favors
the null on spend, i.e. conservative against the harness's own case.
