# run-ledger — the measurement substrate

**v2 artifact #1** ([design](../../docs/design/evidence-based-harness.md) D14, built to the
composition rules of R5/D15). One thing well: **durable, schema-validated, append-only JSONL
records of measurements and runs** — so that every later artifact's null arm, every experiment
write-back, and every pre-registered prediction has a committed, third-party-checkable home.
The rule it exists to serve: *a win without an artifact is a claim.*

Standalone by construction: pure stdlib Python 3, no imports from anything else in this repo,
usable in any project. Query with `jq`/`grep`, rotate with `mv`, version with git — this tool
deliberately does not reimplement them.

## Contract

**Record envelope** (one JSON object per line; strict — unknown top-level keys are invalid):

| Key | Required | Meaning |
|---|---|---|
| `ts` | yes | RFC3339 timestamp (append stamps now-UTC; `--ts` overrides for backfill) |
| `kind` | yes | free string — conventions: `measurement`, `run`, `prediction`, `outcome`, `note` |
| `subject` | yes | free string — what it's about, e.g. `t1/arm-a`, `merge-gate/null-arm` |
| `data` | yes | arbitrary JSON **object** (the payload; the envelope has no opinions about it) |
| `source` | no | who/what produced it |

**Commands**

```
python3 ledger.py append LEDGER --kind K --subject S [--data '{"…":…}' | --data - | --data-file F] [--source SRC] [--ts ISO]
python3 ledger.py check LEDGER [LEDGER…]        # strict: exit 1 on ANY invalid line
python3 ledger.py summarize LEDGER [LEDGER…]    # tolerant: counts by kind/subject, time range, invalid-line count
```

`append` echoes the appended record to stdout (pipe-friendly). Exit codes everywhere:
**0** ok · **1** invalid records found (`check`/`summarize`) · **2** usage or input error
(`append` never writes an invalid record — validation precedes the write).

**Guarantees**

- Append is a single line written in one call under an advisory `flock`, then fsync'd —
  concurrent appenders on POSIX do not interleave or lose lines (the v1 B-1/B-2 lesson:
  single-writer invariants need a mechanism, not an architecture note).
- `check` is strict and reports **torn tails** distinctly (a final partial line without a
  trailing newline — the v1 B-3 lesson); `summarize` is tolerant and counts invalid lines
  instead of dying.
- Deterministic serialization (sorted keys, compact separators) — byte-stable for git diffs.

**Non-goals** (use the composing tool instead): querying (`jq`), rotation (`mv` + a fresh
file), multi-host coordination, dashboards, opinions about `data`'s shape. Pre-registration is
a *convention*, not machinery: append `kind=prediction` before the run and `kind=outcome`
after, and let the timestamps prove the order.

## Composition examples

```sh
# T1 write-back: the experiment's summarize output becomes a ledger record
./tools/budget-governor/run_cache_weight_experiment.sh summarize LOGDIR \
  | python3 tools/run-ledger/ledger.py append v2-ledger.jsonl \
      --kind measurement --subject t1/arm-a --data - --source cache-weight-experiment

# A merge-gate report becomes a run record (composition, not coupling — neither tool knows the other)
python3 tools/run-ledger/ledger.py append v2-ledger.jsonl \
  --kind run --subject merge-gate/task-foo --data-file gate-report.json
```

## Measurement & deletion criterion (R2)

The ledger is judged by whether decisions cite its records. If entries accumulate that nothing
reads — no write-back, no null-arm comparison, no design citation — delete the tool and the
habit; that deletion is a result, not a failure.

## Tests · versioning

`python3 tools/run-ledger/test_ledger.py` — covers envelope validation, torn-tail detection,
tolerant-vs-strict reads, and a 10-way concurrent-append race. Contract is **v1, unversioned
in-band**; the versioning discipline is deliberately unsettled until the first real
two-artifact integration ([design](../../docs/design/evidence-based-harness.md) **T11**).
