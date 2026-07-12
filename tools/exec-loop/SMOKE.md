# The live smoke — operator-run, spends real quota

The mock-tested loop proves orchestration; **this run proves the vendor contract** — the
launcher's `claude -p` invocation, the effort mechanism, and whether the isolation wall
(deny rules + sandbox) actually holds. The previous harness hit three separate vendor-interface
breakages, every one found by a live probe and none by mocks or documentation. **The merge made
the loop code-complete; your smoke run is what makes it real.**

Standing rule: quota-costing operations are operator-run — this script is never wired into
automatic tests, gates, or CI. Expect roughly one author + one implementer worker (two Opus/
Sonnet sessions at xhigh) plus a possible retry.

## The per-launcher rule (plan decision 10)

Every launcher earns trust through **its own** smoke run — including the deliberate
read-attempt probe below — before any real plan uses it. When the Codex CLI launcher lands
(the named first extension), it gets its own smoke; a green Claude smoke says nothing about it.
Re-run the smoke after any Claude Code release (vendor-build decay).

## Before you run

1. Check window headroom (`/usage` in an interactive session) — don't burn a nearly-empty
   window on a probe.
2. `claude --version` — record it; the result is a fact about *this build*.

## Run

```sh
tools/exec-loop/smoke.sh --i-understand-this-spends-quota
```

The script builds a scratch target repo and a one-task ratified plan in a temp directory, then
runs the real loop with the real `claude_p` launcher. The smoke task's spec instructs the
implementer to (a) **attempt to read the held-out workspace path and write what happened to
`probe-result.txt`** — the wall is *probed*, never assumed — and (b) make a trivial committed
change so the full cycle (author → seal → implement → gate → merge) exercises live.

## What to check afterward (the script prints all paths)

- **Exit 0 and the merge landed** — the full chain worked against the live CLI.
- **`probe-result.txt` in the scratch repo** — must say the read was DENIED. If the worker
  could read the held-out path, the wall is not real on this build: file it as a
  vendor-build correction, fix `claude_p.py`'s translation, re-run.
- **The transcripts** (`_runs/<plan>/bundles/*/transcript.txt`) — sanity-read the author's
  and implementer's sessions.
- **`validation.json` / seal records** — fails-on-base held against a real authored suite.

## Record the outcome (the artifact is the warrant)

```sh
python3 tools/run-ledger/ledger.py append docs/research/internal/v2-ledger.jsonl \
  --kind measurement --subject exec-loop/smoke --source operator \
  --data '{"claude_code_version": "<version>", "exit": 0, "wall_probe": "denied|READABLE", "notes": "..."}'
```

A red smoke is a finding, not a failure: it caught a vendor-contract break at the cost of one
probe instead of mid-plan.
