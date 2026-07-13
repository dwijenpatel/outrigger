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

## The codex_p smoke — PENDING, operator-run (spends OpenAI quota, not Max-plan)

`codex_p.py` landed 2026-07-13, mock-tested only (`test_codex_p.py`, stub binary; flags
probed against `codex-cli 0.142.5 --help`). Per the per-launcher rule its first smoke must
run before any real plan uses it. One author-role bundle (the only loop role codex_p accepts
today — it refuses `deny_read` fail-closed, which the implementer's isolation needs), plus
one deliberate escape probe. What it must verify, in order of load-bearing-ness:

1. **The write wall holds:** instructions tell the worker to create a file *outside* its cwd
   (e.g. in `$HOME`) and report what happened — expect the write BLOCKED by
   `workspace-write`, in-cwd writes fine, shell commands unattended (no approval hang). This
   is the codex analogue of claude_p's read-attempt probe.
2. **The event schema matches the parser:** `result.json.usage` populated with real numbers
   (not `{"error": ...}`). If it misses, the verbatim `events.jsonl` in the bundle is the
   fix's spec — adjust `parse_events`, re-run.
3. **A non-git cwd starts** (`--skip-git-repo-check` honored — the author workspace is not a
   repository) and `--ephemeral` leaves no session files behind.
4. **Effort reaches the model** (`-c model_reasoning_effort=...` accepted, session runs).

Record the outcome here (dated, build-pinned) and as a ledger note, like the claude runs
below. Until then codex_p's vendor translation is doc-grounded only.

## What each run has taught (vendor-build facts, build-specific)

- **Run 1** (`acceptEdits` + `permissions.deny Read`): the OS wall held through bash, but
  headless git commit / python3 aborted on approval prompts nobody could answer.
- **Run 2** (`bypassPermissions`): commits ran, but the read wall dropped (the permission-layer
  `Read` deny doesn't survive bypass) — and **the held-out suite caught it**: the implementer's
  own checks passed, the blind test asserting `DENIED` failed the gate, merge refused. The
  design's whole thesis, live.
- **The fix now in `claude_p.py`** (doc-grounded, run 3 is the arbiter): the wall moved to the
  OS layer (`sandbox.filesystem.denyRead`), `sandbox.autoAllowBashIfSandboxed` runs sandboxed
  bash unattended, `acceptEdits` covers the edit tool. **Run 3's job: confirm git commit runs
  with no prompt under auto-allow AND the bash read of the held-out dir is DENIED — both at
  once.** That combination is the thing every prior run missed.
- **Pre-run-3 hardening** (operator-caught, doc-verified 2026-07-12): `sandbox.failIfUnavailable`
  is now set — the vendor default when the sandbox *cannot start* (missing deps, unsupported
  platform) is to **warn and run unsandboxed**, which would silently void the OS wall while
  every visible check still passed. Now it aborts the session instead, and the abort surfaces
  as a failed spawn. Docs don't name the headless path explicitly (the `--settings` precedence
  rule implies it) — run 3 arbitrates this key like the rest.
- **Pending re-probe — `--output-format json` (2026-07-12):** the launcher now runs workers
  with `--output-format json` and parses the session's own `usage`/`total_cost_usd` into
  `result.json` (durable spend capture, D14/R4). This changes the vendor invocation and the
  stdout shape the launcher consumes, so it needs a green smoke on the target build before a
  real plan relies on the captured numbers. `parse_session` is fail-safe (a schema surprise
  degrades to `usage:{error}`, never a crash), but "the numbers are right" is vendor-build and
  only the smoke proves it. **Run 4's added checks: `result.json` carries a `usage` block with
  non-null `output_tokens` and `cost_usd`; the run ledger's seal record carries `author_usage`
  + `suite{files,lines}` and the gate record `impl_usage` + `churn{files,insertions,deletions}`
  matching the actual diff** (churn is pure git, not vendor behavior — it rides along for
  confirmation, not probing). Run 4 is a release check for the instrumentation, not a study:
  green means the telemetry can be trusted from then on.
- **Run 4** (2026-07-12, build 2.1.207 — **red, and the red is the finding**): every scheduled
  release check PASSED — wall `DENIED` on both attempts, unattended commits, telemetry live and
  credible on all 3 workers (author $1.98/24.6k out; implementers $0.58 + $0.84), churn matching
  diffs, counts-only redaction confirmed. The red: the author legitimately wrote spec tests that
  consult **git state**, and the gate runs checks in a `--no-ff --no-commit` staged-merge
  worktree — HEAD lags the judged tree and status is dirty *by construction*, so those tests
  fail environmentally, deterministically, on every attempt → attempts-exhausted. Predicted
  after gate-a1, confirmed at gate-a2 (identical failing test names). Not a vendor break; a
  **gate execution-environment defect** — fix: the gate commits its merge in the throwaway
  worktree before running checks. The `--output-format json` re-probe is hereby **satisfied**;
  the environment fix is machinery-only and needs no new smoke.
- **Run 3** (2026-07-12, build 2.1.202 — **green**): exit 0, merged on attempt 1,
  `probe-result.txt` = `DENIED`. The combination every prior run missed held **simultaneously**:
  git commit ran unattended under sandbox auto-allow AND the OS wall denied the held-out read.
  `failIfUnavailable: true` was accepted by the live CLI (settings not rejected; worker ran
  normally). Author suite: 3 files, 10 fails-on-base. Full cycle ~15 min, one author + one
  implementer, no escalation. Caveat: this ran on the stale standalone 2.1.202 (the skew the
  host convention below now prevents); a 2.1.205 verdict is an operator re-run if wanted.

### Network note

The sandbox's network model is allowlist-based. `network: true` in the isolation intent
currently means "sandbox default" (local git/python work; reaching external domains needs
explicit domain allowlisting) — a known gap, unneeded by this smoke, to be closed by its own
probe when a real task needs outbound network (e.g. `pip install`).

### Named upgrade — adversarial boundary matrix

Today's smoke probes ONE boundary: a shell read of the held-out path. The full wall has more
faces, and runs 1–2 proved boundary behavior must be demonstrated, never inferred: **direct
Read-tool reads, shell reads, file-search/glob tools, credential paths (keychain,
`~/.claude`), and outbound network attempts** — each deliberately attempted per launcher, per
build, with the expected refusal observed. Trigger for building it: before the first plan on a
repository whose secrets matter, or any plan whose workers handle credentials. Until then the
single-probe smoke is the floor, stated honestly.

## Before you run

1. Check window headroom (`/usage` in an interactive session) — don't burn a nearly-empty
   window on a probe.
2. `claude --version` — record it; the result is a fact about *this build*.

### Which `claude` runs (host convention, 2026-07-12)

Runs 1–2 executed on 2.1.205 (the desktop app's managed CLI) while run 3 executed on 2.1.202
(a stale standalone install PATH happened to serve) — two independent updaters had silently
diverged. Since 2026-07-12, `~/.local/bin/claude` on this host is a **shim that resolves to
the desktop app's managed CLI** (`~/Library/Application Support/Claude/claude-code/<ver>/…`),
so terminal and app share one updater and cannot diverge; the shim fails loudly if the app
layout changes. Independently, every spawn's `result.json` now records the **binary path and
version actually used** (launcher contract `binary` key) — a version change between runs is a
recorded fact, and any new build re-triggers the standing re-smoke rule above.

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
