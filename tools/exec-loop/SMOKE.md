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

`codex_p.py` landed 2026-07-13 and was reworked the same day from `--sandbox
workspace-write` to a **generated permission profile** (`extends = ":workspace"` + per-path
`"deny"` carve-outs + per-profile network policy, activated via `-c
default_permissions=...`) after the mechanism was verified against
learn.chatgpt.com/docs/permissions — profiles CAN deny reads, which makes `deny_read`
expressible and every loop role codex-eligible. Mock-tested only (`test_codex_p.py`, stub
binary). Three vendor-arbitrated unknowns make this smoke mandatory before any real plan:
permission profiles are officially **beta**; the `-c` dotted-path parser's handling of
quoted path-segment keys is undocumented (failure mode is a loud `--strict-config` abort —
safe, but must be confirmed); and the event schema for usage is unprobed live. What it must
verify, in order of load-bearing-ness:

1. **The read wall holds (THE probe):** a bundle with `deny_read: [<scratch dir with a
   sentinel file>]`; instructions tell the worker to read that file via its file tool AND
   via shell (`cat`), report both, then do a trivial in-cwd task. Expect: both reads DENIED,
   in-cwd writes fine, shell unattended (no approval hang). If the profile silently failed
   to apply, the worker reads the sentinel — that exact transcript is the falsification.
2. **The write wall holds:** same bundle, also attempt a write outside cwd (e.g. `$HOME`) —
   expect BLOCKED (`:workspace` base behavior).
3. **The config actually parses:** the spawn starts at all under `--strict-config` with the
   quoted filesystem keys (unknown-parser risk above); a startup abort here means switching
   the profile delivery from `-c` overrides to a generated `$CODEX_HOME/<name>.config.toml`
   + `--profile` (documented fallback, one function).
4. **The event schema matches the parser:** `result.json.usage` populated with real numbers
   (not `{"error": ...}`). If it misses, the verbatim `events.jsonl` in the bundle is the
   fix's spec — adjust `parse_events`, re-run.
5. **A non-git cwd starts** (`--skip-git-repo-check` honored) and `--ephemeral` leaves no
   session files behind; `--ignore-user-config` really keeps a user-config `sandbox_mode`
   from conflicting with the profile (plant one temporarily, expect no effect).
6. **Effort reaches the model** (`-c model_reasoning_effort=...` accepted, session runs).

Record the outcome here (dated, build-pinned) and as a ledger note, like the claude runs
below. Until then codex_p's vendor translation is doc-grounded only.
**Status 2026-07-13:** `--rehearse` executed by the operator (argv verified against
codex-cli 0.142.5, nothing spent); **the real run has not happened yet.**

## Claude run 5 — EXECUTED 2026-07-13, build 2.1.207: hardening holds; one residual found

`claude_p.py` passes `--setting-sources ""`, `--strict-mcp-config`,
`--disable-slash-commands`, `--no-session-persistence` and sets
`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Run 5 probed the delta vs runs 3–4. **Exit 1
(attempts-exhausted) was the probe working**: both implementers truthfully reported the
ambient finding below, and the blind suite — which correctly codified the spec's
"MEMORY: NONE expected" — refused the merge twice. Every pre-registered question got its
answer. Cost $2.25 (author $1.12, implementers $0.40 + $0.73); artifacts:
[smoke-run5-2026-07-13](../../docs/research/internal/smoke-run5-2026-07-13/).

1. **Auth works** under `--setting-sources ""` — three OAuth sessions ran normally. ✓
2. **The wall held and commits ran**: `WALL: DENIED` (OS wall probed via ls/read —
   `Operation not permitted`), farewell implemented, committed, own checks green. The
   generated `--settings` file survives `--setting-sources ""` — pre-registered risk
   cleared. ✓
3. **Ambient isolation held where mechanisms exist**: canary `SessionStart` hook did not
   fire (marker absent; operator restored settings immediately after — verified
   post-cleanup, consistent though not independently timestamped); `MCP: NONE` with real
   user-scope MCP servers configured — `--strict-mcp-config` proven against a live
   counterfactual. ✓
4. **Residual, both attempts, deterministic:** the **logged-in account's identity
   (userEmail) is injected via a system-reminder regardless of the hardening set** —
   `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` does not govern it (account-scope, not
   settings-scope; only `--bare` suppresses it, and `--bare` kills OAuth). No memory-file
   CONTENT leaked — though worker cwds are fresh scratch paths whose project memory is
   structurally empty, so that channel is closed by construction for loop workers, not by
   the env var. **Accepted residual**: the operator's own email visible to the operator's
   own workers; revisit per build. The probe spec now splits identity (line 4, recorded)
   from memory content (line 3, judged) so future runs grade cleanly.
5. **Vendor nuance (attempt 2):** `python3 -c` is approval-gated even under
   `autoAllowBashIfSandboxed` on 2.1.207; a script file runs fine. Workers route around it;
   plans should prefer script-file checks over `-c` one-liners.

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

## Cross-vendor verification matrix (status as of 2026-07-13)

The repo is "Claude + Codex compatible" only when every row passes **per vendor,
independently**. `mock` = proven by the zero-quota suites (`test_exec_loop.py`,
`test_codex_p.py`, `tests/test_agent_surfaces.py`); `live-pending` = needs that vendor's
operator-run smoke; a dash = not applicable.

| Check | Claude Code | Codex |
|---|---|---|
| Shared instructions loaded | CLAUDE.md imports AGENTS.md (live-pending: eyeball one session) | native AGENTS.md (live-pending) |
| Skill discovered | `.claude/skills` (proven in use) | `.agents/skills` symlink (live-pending) |
| Dry-run argv/config | mock ✓ | mock ✓ |
| Wrong-tool refusal | mock ✓ | mock ✓ |
| Unknown-tool halts before spawn | mock ✓ (loop registry) | mock ✓ (loop registry) |
| File tool cannot read held-out path | live ✓ (runs 3–5) | live-pending (probe 1) |
| Shell cannot read held-out path | live ✓ (runs 3–5) | live-pending (probe 1) |
| Worker edits + commits in worktree | live ✓ (runs 3–5) | live-pending (probe 2) |
| Requested network policy holds | live ✓ (run 3 note) | live-pending |
| Sandbox/profile unavailable ⇒ refusal | `failIfUnavailable` live ✓ (run 4) | `--strict-config` live-pending (probe 3) |
| Timeout kills process group | mock ✓ | mock ✓ |
| Ambient config cannot weaken wall | live ✓ (run 5: canary hook silent, MCP excluded vs live counterfactual) — residual: account userEmail injection, documented | live-pending (probe 5) |
| Usage telemetry parses | live ✓ (runs 4–5) | live-pending (probe 4) |
| Full mocked exec-loop | mock ✓ (46 tests) | mock ✓ (registry + wrapper) |
| One live task through the real CLI | live ✓ (e2e run 1) | live-pending |
