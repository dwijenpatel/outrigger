# Rate-window handling — monitors, resume, and wake-on-reset

**Date:** 2026-07-06
**Method:** 11 cloned popular repos mined by parallel analysts; file paths cite the clones at `/Users/dwijen/repos/`. Primary feasibility evidence: a CLI probe of `claude --help` (v2.1.201) plus disk inspection of `~/.claude/projects/` — zero model invocations, so runtime behavior (exit codes on limit errors, truncated-transcript resume) is flagged as unverified where relevant. Prior-art star counts come from an earlier verified sweep, noted as such.

---

## 1. The question

Two operator hypotheses under test:

1. *"Could we build something simple that lives outside the Claude CLI, monitors 5-hour limit usage, and automatically wakes up a conversation after the limit resets with a simple message like 'the limit has been reset. please continue.'"*
2. *"Throttling when close to a limit doesn't make sense — what matters is efficient token usage and minimizing wall-clock to completion. We should be able to wake a limited session with something like `claude -p --resume $SESSION_ID --output-format json 'please continue'`. Does anything like this exist? If not, can we build it?"*

Short answers, argued below: (1) yes, mechanically feasible today, and nothing in the popular ecosystem does it — but the naive "wake the old conversation" form is economically wrong; (2) the resume invocation is a documented, supported shape, the anti-throttling instinct is mostly right, and the closest existing tool is a ~787-star niche script, not any of the 11 major repos.

## 2. What the 11 popular repos actually do

The headline finding: **zero of 11 repos have subscription rate-window awareness, and zero have wake-on-reset.** One (career-ops) even greps the reset time out of worker logs — and throws it away. Meanwhile 9 of 11 have serious *resume* machinery, all of it disk/file-based rather than transcript-resume-based. The ecosystem has independently converged on "fresh session + disk state" and independently failed to touch the window problem.

| Repo | 5h/weekly window awareness | Wake-on-reset | Resume mechanism |
|---|---|---|---|
| gstack | **None** (grep hits only GitHub-API/HTTP caps) | No | `/context-save`, `/context-restore`, structured `[gstack-context]` WIP commits (`/Users/dwijen/repos/gstack/context-save/SKILL.md`) |
| mattpocock/skills | **None** | No | `/handoff` doc outside workspace; `/claude-handoff` pipes it into `claude --bg` (`skills/productivity/handoff/`, `skills/in-progress/claude-handoff/`); wayfinder makes the issue tracker the durable state |
| no-mistakes | Retry-only: `rate_limit_error`/429/503/529 → exp backoff maxing ~21s, then the run **fails** (`/Users/dwijen/repos/no-mistakes/internal/agent/retry.go`) | No | Daemon + SQLite run state, `attach`/`rerun`, crash recovery |
| everything-claude-code | **None** (loop commands will burn a window mid-loop) | No | Fat-summary resume: `~/.claude/sessions/*-session.tmp` re-injected by SessionStart hook (`scripts/hooks/session-start.js`, `commands/resume-session.md`) |
| karpathy-skills | **None** (repo is 2.3KB of prose) | No | None |
| caveman | Partial and *inverted*: `caveman-stats.js` refuses to print limit relief, assuming input+cache dominate limit accounting (`src/hooks/caveman-stats.js` lines 286-293) | No | Flag files re-armed by SessionStart hook — small disk-is-the-state pattern |
| planning-with-files | **None** | No | Strongest disk-first resume: hook-injected plan/ledger, `session-catchup.py` transcript replay, attestation-gated injection (`skills/planning-with-files/scripts/`) |
| alirezarezvani/claude-skills | External-HTTP only (pulse honors `X-Ratelimit-*`) | No | handoff skill: reference-by-path, never inline (`engineering/handoff/`) |
| superpowers | **None** (grep across skills/hooks/docs: empty) | No | Append-only `.superpowers/sdd/progress.md` ledger; "trust the ledger and git log over your own recollection" (`skills/subagent-driven-development/SKILL.md`) |
| career-ops | **Closest**: `batch-runner.sh` greps worker logs for `session limit|resets [0-9:]+[ap]m`, enters first-class `paused_rate_limit` state (lines 370-527) — then **discards the timestamp**; resume is manual `--resume-paused` after the human watches the clock (`docs/FAQ.md`) | No | `batch-state.tsv` + PID lockfile crash-resume; `data/agent-inbox.md` durable cross-session queue |
| ruflo | API-key-only: `rateLimitRemaining/rateLimitReset` header tracking + circuit breaker (`v3/@claude-flow/providers/src/base-provider.ts`); statusline just added env vars to **hide** the cost segment because it is "misleading on subscription plans" (`v3/@claude-flow/cli/src/init/statusline-generator.ts` ~line 58) — problem identified, answer absent | No | MCP session snapshot tools; ContinueGate forced checkpoints |

Absence readings worth naming:

- **gstack** ships detached eval runs, caffeinate wrappers, and 10-15-parallel-sprint Conductor fleets — exactly the workloads that slam a Max window — with no window gate anywhere (`/Users/dwijen/repos/gstack/CONTRIBUTING.md`, Detached runs).
- **superpowers** advertises agents "working autonomously for a couple hours at a time" (README) on the exact plan whose window is 5 hours.
- **career-ops** proves users hit this constantly: pause states, `--resume-paused` flags, and FAQ entries exist *because* subscription limits bite mid-batch. The fix (parse the timestamp it already matched, sleep until then) is one script away and nobody has landed it.
- **ruflo** and **caveman** both stumbled into the accounting question — ruflo by hiding a misleading dollar figure, caveman by refusing to claim limit relief — and both got the subscription economics wrong or incomplete relative to the measured finding that cache READS are heavily discounted against windows.

The one *conceptually* adjacent pattern: career-ops' `paused_rate_limit` as a first-class scheduler state distinct from failure, which pauses without consuming retry budget. That is the right vocabulary; it just lacks the alarm clock.

## 3. Prior art outside the 11 (earlier verified sweep)

- **terryso/claude-auto-resume** (~787 stars): the closest existing thing to hypothesis 2 — waits out the limit and continues. Niche adoption, single-purpose.
- **aniketkarne/ClaudeNightsWatch** (~367 stars, stale since Jan 2026): scheduled unattended runs; effectively abandoned.
- **Statusline/usage monitors** (ohugonnot/claude-code-statusline, Usage4Claude): display-only — they read the windows, they don't act on them.
- **Six open Claude Code feature requests for native auto-resume** (#18980, #26775, #35744, #36320, #38263, #47276).

Read together with §2: strong, repeatedly-expressed demand; supply is one ~787-star script and a dead project. None of the high-star ecosystem repos (52k-158k stars) touch it. This is the clearest demand/supply gap found in the entire mining exercise.

## 4. CLI feasibility (probe results, v2.1.201)

**The hypothesis-2 invocation is supported.** `-r, --resume [value]` combines with `-p, --print` and `--output-format json` (print-mode only); nothing in the help restricts `--resume` to interactive mode, and `--no-session-persistence` ("only works with --print") confirms by inversion that print-mode sessions persist and are resumable. `--fork-session` lets a wake preserve the original transcript. `-c, --continue` is the id-free variant (racy if other sessions ran in the cwd).

**Session-id discovery — four routes:**
1. **Pin it up front** (cleanest for a harness): launch the workload with `--session-id <uuid>` (must be a valid UUID); the waker knows the id a priori.
2. **Disk:** `~/.claude/projects/<munged-cwd>/<session-uuid>.jsonl` where munged-cwd replaces `/` and `.` with `-`; the filename stem IS the session id (verified against a real session's records). Most recent: `ls -t .../*.jsonl | head -1`.
3. **The original `-p --output-format json` result object** carries the session id (`session_id` — verify field name before relying; not in --help).
4. `claude agents --json` for `--bg` sessions.

**Reset detection without an API call:** the statusline stdin JSON officially carries `rate_limits.five_hour.resets_at` / `rate_limits.seven_day.resets_at` (Unix epoch) plus `used_percentage` (docs/research/claude-code-and-max-plan-facts.md §4, official). This repo's `hooks/statusline_dump.py` already tees that JSON atomically to `state/statusline-dump.json` with `_captured_at`. A session that hit the limit had received API responses, so its last statusline refresh should have persisted a valid `resets_at` before stalling. Read defensively: `rate_limits` appears only for Pro/Max, only after the first API response, and `five_hour`/`seven_day` may each be independently absent.

**Fallback detection:** parse the limit error text — career-ops' production grep (`resets [0-9:]+[ap]m`, `batch/batch-runner.sh` line 377) proves the string shape is stable enough to match in the wild. Last resort: the undocumented OAuth endpoint `GET api.anthropic.com/api/oauth/usage` (measured, community) — but token acquisition is non-interactive-hostile here. OTEL is after-the-fact only; `anthropic-ratelimit-*` headers are API-key-only.

**Unattended-run caveats (all load-bearing):**
- **Auth:** subscription OAuth lives in the macOS Keychain (no `~/.claude/.credentials.json` on this machine, probed 2026-07-04). A bare cron/LaunchDaemon may fail keychain access — run the waker as a **user LaunchAgent in a logged-in session**, or mint a token via `claude setup-token`. Do NOT use `--bare`: it strictly reads `ANTHROPIC_API_KEY`/apiKeyHelper and would **silently bill API dollars instead of the reset subscription window**.
- **Permissions:** a `-p` run cannot answer interactive prompts; without `--permission-mode auto|dontAsk|bypassPermissions` or a pre-baked allowlist the woken turn stalls on its first tool call. Also: settings files that fail validation are **silently ignored in print mode** — a broken settings.json silently drops the allowlist.
- **Empty-var guard:** `--resume [value]` takes an *optional* value; `$SESSION_ID` expanding empty opens the interactive picker, which in `-p`/no-TTY hangs or fails. Quote and guard it.
- **Died-mid-turn:** a clean limit error leaves a complete transcript; a killed process may leave a `.jsonl` ending mid tool-use with unreconciled side effects (half-written files). The wake prompt must instruct re-verification of working-tree state, not trust of last memory. Resume-after-truncation behavior is undocumented — verify empirically.
- **Shared pool:** the 5h window anchors at first message ([measured], not official) and is shared across app/web/IDE/terminal/SDK — a "reset" window can be partially re-drained by the operator before the wake fires. **Re-check `used_percentage` at wake time, not just the clock.**
- **Regime risk:** the announced-then-PAUSED plan change would move `claude -p`/SDK usage off subscription windows onto monthly dollar credits (official, support 15036540). If un-paused, headless wakes stop draining windows and this whole premise dissolves into dollar-budget management. Any tool built here needs that hedge documented.

## 5. The cache-cold correction: why "please continue" on the old session is the wrong wake

Hypothesis 2's premise needs one repair. Subscription main-session prompt-cache TTL is **1 hour** (5 minutes applies to API-key auth, usage-credit draw, and subagents — official, re-fetched). Either way, a multi-hour limit wait **guarantees a cold cache**: `--resume` on a long transcript reprocesses the entire conversation at full cache-write cost, and community telemetry shows the resumed session attributes its whole accumulated context to the **new** window — ~15M tokens attributed for ~20k of real work; 192k cache-reads to produce a 1-token response. Waking a fat session at reset can immediately re-burn a large slice of the window you just waited five hours for.

The ecosystem's own convergent behavior corroborates the alternative: every serious resume mechanism in §2 — gstack checkpoints, superpowers' progress ledger, planning-with-files' plan injection, Pocock's handoff, everything-claude-code's blueprint "cold-executable step briefs" — rebuilds a **fresh, thin context from disk artifacts** instead of resuming transcripts. superpowers states the principle outright: after compaction, "trust the ledger and git log over your own recollection"; losing the ledger was "the single most expensive failure observed" (`skills/subagent-driven-development/SKILL.md`).

So the wake decision tree is:

1. **Default: fresh `claude -p` seeded from disk state** (plan ledger, progress file, observations) — cheap, window-friendly, and exactly what a disk-is-the-memory harness already supports. The prompt is not "please continue"; it is "read `<ledger paths>`, re-verify working-tree state, resume at the recorded boundary."
2. **Exception: `--resume` (with `--fork-session`) only when in-conversation context is genuinely irreplaceable** — a long interactive design discussion, un-persisted reasoning. Accept the full-transcript re-burn as a priced choice.
3. **Never:** blind `-c`/`--resume` of the fattest available transcript with a bare "continue" — the naive hypothesis-1 shape.

On throttling, the operator is essentially right, with one refinement. Slowing down near a hard window wall doesn't buy anything — the wall arrives regardless, and the evidence (same-task token spend varying ~30x between identical runs) says open-loop pacing can't even predict when. What the ecosystem's best analogues do instead is **park at a clean boundary**: career-ops' `paused_rate_limit` stops *scheduling* new jobs rather than slowing in-flight ones; ruflo's ContinueGate decides continue/checkpoint/pause at step boundaries. The correct policy is: run at full speed, check the window at task boundaries (closed-loop), park cleanly when the next task won't fit, wake at reset. That is throttling-free but not window-blind.

## 6. Minimal viable wake-on-reset design

Smallest thing that works, composed almost entirely of already-verified parts:

1. **Instrument:** statusline hook tees `rate_limits` JSON to a state file with `_captured_at` (exists: `hooks/statusline_dump.py` → `state/statusline-dump.json`).
2. **Launch discipline:** harness/batch runs start workers with `--session-id <uuid>` and record `{session_id, cwd, ledger_paths, boundary}` in a parkfile when a limit error is detected (error-text grep per career-ops, or statusline `used_percentage` ≥ threshold at a task boundary).
3. **Waker:** a user LaunchAgent (not a LaunchDaemon — keychain) reads the parkfile + dump, sleeps until `resets_at` + jitter, then **re-checks `used_percentage`** from a fresh probe before spending anything.
4. **Wake:** default `claude -p --output-format json --permission-mode <configured> "<re-entry prompt pointing at ledger paths, instructing working-tree re-verification>"` in the recorded cwd; optional `--resume "$SESSION_ID" --fork-session` mode behind an explicit flag, with the empty-var guard.
5. **Loop:** parse the JSON result, update the parkfile/ledger, repeat until the run ledger says done or the window re-exhausts (park again — the state machine is park ⇄ wake, not fail).

Everything above is help-text-supported or already prototyped in this repo; the two things needing empirical verification before shipping are the limit-error exit code/text in `-p` mode and the `session_id` field name in the JSON result.

## 7. What the operator's project adds

Mapping cc-agent-harness assets onto the measured gaps:

- **Asset #4 (rate-window awareness, statusline `rate_limits` feed):** the only party in this survey that both reads the official reset feed and knows its failure modes (staleness, per-window absence, Pro/Max-only). Fills the literal hole in career-ops (`--wait-for-reset`, PR-sized: parse the timestamp `batch-runner.sh` already greps), ruflo (window segment replacing the hidden cost segment — they documented the need in their own CHANGELOG), gstack (`gstack-detach` window gate), and everything-claude-code (`/loop-start` safety checks).
- **Asset #5 (cache economics):** corrects caveman's inverted assumption (its stats code refuses to claim limit relief because it believes cache reads dominate limit accounting — the measured finding says reads are discounted and misses+output are the spend), and supplies the §5 argument that makes a wake tool *cheap* rather than merely automatic. No repo in the survey has any prompt-cache awareness in its cost logic (everything-claude-code's `cost-tracker.js` ignores cache token classes entirely; ruflo uses a flat $/token heuristic).
- **Asset #3 (disk-is-the-memory resumability):** the fresh-session wake in §6 step 4 is only viable because thin contexts rebuild from ledger files. Repos with fat-summary resume (everything-claude-code) or transcript replay (planning-with-files' session-catchup) get strictly worse wake economics. The harness's ledger + resume-marker design (build-pause already writes one) is the natural parkfile.
- **Asset #5b (30x variance → closed-loop control):** justifies the park-at-boundary policy over any predictive throttling, and matches the ecosystem's independently-derived best practice (career-ops pause state, ruflo ContinueGate, superpowers N=5-runs methodology note).

## 8. Verdict on the operator's hypotheses

**Hypothesis 1 (external monitor + "the limit has been reset. please continue."): build the mechanism, not the message.** The monitor-sleep-wake loop is feasible today with documented flags and an official reset feed, nothing popular does it, and six open feature requests plus career-ops' manual `--resume-paused` dance prove people want it. But the literal design — waking the *old conversation* with a bare "please continue" — is a bad idea on the evidence: the cache is guaranteed cold after a multi-hour wait, the resume re-processes the whole transcript against the freshly reset window (community telemetry: ~15M tokens attributed for ~20k of real work), and a bare "continue" trusts a memory that may predate un-reconciled side effects. The wake message must point at disk state and demand re-verification; the wake session should usually be fresh.

**Hypothesis 2 (`claude -p --resume $SESSION_ID --output-format json 'please continue'` — does it exist? can we build it?):** The invocation shape is real and supported per `claude --help` v2.1.201. Nothing like the full tool exists in the popular ecosystem — the closest is terryso/claude-auto-resume (~787 stars) and the stale ClaudeNightsWatch; the 11 surveyed repos (52k-158k stars among them) score 0/11 on wake-on-reset. Yes, we can build it — with `--resume` demoted to an explicit opt-in for irreplaceable-context cases and fresh-session-from-ledger as the default, per §5. The anti-throttling instinct is correct as stated: don't slow down, but do park at task boundaries and re-check the window at wake, because the pool is shared and open-loop prediction fails at 30x variance.

**Build/don't-build: BUILD**, as a small standalone tool ("wake-on-reset daemon" / window-aware parking for headless Claude runs), with these popularity levers:

1. **One-command install, zero config in the common case** — auto-discover the newest session in the cwd, auto-read the statusline dump, sensible `--permission-mode` default. The prior art's weakness is setup friction.
2. **Ship the honest economics** — a README section on why fresh-session wakes beat `--resume` (with the telemetry numbers) is differentiated content nobody else has and doubles as marketing.
3. **Integrations as distribution:** a career-ops `--wait-for-reset` PR, a planning-with-files community-table listing, a superpowers-marketplace plugin, a ruflo statusline segment — four communities whose own files show the wound this dresses.
4. **Hedge the regime risk in writing:** if the paused plan change un-pauses, headless runs leave subscription windows entirely; the tool's park/wake state machine survives (it becomes budget-parking), but the pitch must not over-commit to the 5-hour window as a permanent fact.
5. **Expect native competition:** six open feature requests also signal Anthropic may ship native auto-resume. The durable moat is not the sleep-until-reset loop (trivially copied) but the wake *policy* — thin-context re-entry, boundary parking, used_percentage re-check — which is where the harness's assets live.

Don't-build variant rejected: doing nothing and waiting for native support forfeits a clear first-mover slot that the demand signal says has been open for months; building only the naive hypothesis-1 version was rejected because it wakes sessions into the most expensive possible first turn.
