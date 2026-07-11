# Unattended-operation prior art — the kunchenguid orchestration stack

Prior-art survey of one practitioner's production stack for unattended / semi-attended agent
operation (github.com/kunchenguid: **gnhf**, **firstmate**, **treehouse**, **no-mistakes**,
**acpx**, **acp-mock**, **wheelhouse**, **m87**), read against the harness design
([../attic/token-time-optimized-harness.md](../../../attic/token-time-optimized-harness.md) §3.4
disk-is-memory, §5.1 governor, §6.3 human latency, §7 floor, §9 failure modes). The repos form a
deliberate, dogfooded stack: treehouse (worktree pool) → no-mistakes (merge gate) → gnhf
(overnight loop) / firstmate (crew orchestrator) → acpx/acp-mock (agent transport + token-free
testing); each repo ships through its own gate.

**Provenance:** repo survey 2026-07-04 (READMEs, design docs, and source read via shallow
clones; four-agent fan-out). `[E]` = established in the cited repo's docs/source; `[I]` =
inference/synthesis. These are *design patterns from one practitioner's working system* — prior
art, not controlled measurements; where a pattern references a lived failure ("incident"), that
is anecdotal evidence it was load-bearing, not proof of magnitude.

---

## 1. State architecture: event logs vs. reconciled current state

The single most design-relevant pattern, hardened by a referenced incident (firstmate):

- **Status files are append-only wake-event logs, explicitly "not current-state truth."**
  Current state is a *reconciliation read*: the branch-matched pipeline run-step is
  authoritative, then live pane/process signature, then the log; a dead worker with no run
  reports `unknown` rather than trusting a stale log tail. Rationale: after a resolved gate the
  last log line still reads `needs-decision` while the run has moved on — "never infer current
  state from a `tail` of that log." `[E]`
- **Write-ahead ordering for durability:** actionable wake events are appended to a durable
  queue (`state/.wake-queue`) *before* detector suppression markers advance, so a crash between
  the two loses nothing — recovery = drain the queue from disk. Leases persist in state files
  independent of any live process. "A restart must be a non-event; conversation memory is a
  cache." `[E]`
- **Stale-read detection by generation counter** (chrome-devtools-axi, same author): snapshot
  refs carry a `g<N>:` generation prefix; acting on a stale ref fails loudly (`STALE_REF`)
  instead of silently no-op'ing. `[E]`
- `[I]` Mapping to the design: the phase ledger is the event-log half; the status index should
  be an explicitly *derived* reconciliation (authoritative inputs: gate/run state, git), never
  the last-transition record; a generation stamp on the status index gives concurrent pipelines
  (§6.2 cap ≥ 2) optimistic-concurrency protection that atomic writes alone do not.

## 2. Zero-token supervision (extends the design's zero-token *enforcement*)

The design's principle 2 makes enforcement model-free; this stack makes *supervision*
model-free too — "every LLM turn in the driver is a defect to engineer away" `[I]`:

- A bash watcher classifies every worker wake; benign wakes (a `working:` note while the
  worker's pipeline run is provably alive) are absorbed with **no LLM turn**; only actionable
  events (`done:|needs-decision:|blocked:|failed:|PR ready|...` — a regex, not a model call)
  reach the orchestrator. Heartbeats back off exponentially (600s doubling to a 2h cap); any
  real signal resets cadence. `[E]` (firstmate `fm-watch.sh` / `fm-classify-lib.sh`)
- **Pull-based liveness guard that rides existing output:** every supervision script first
  calls a guard that prints a bordered alarm *through tool output the orchestrator already
  reads* when tasks are in flight but the watcher beacon is stale or wakes are queued —
  harness-portable (no hook surface needed), and complements hook-based gates. Arm/disarm
  wrappers are self-verifying (`started`/`healthy`/`FAILED`, never a false "already running"
  from a dying pid). `[E]`
- **Machine-vs-human message discrimination:** daemon-injected digests carry an in-band
  sentinel (ASCII 0x1f) so the orchestrator can distinguish automation from the operator; any
  unmarked message exits away-mode — "a present captain beats token savings and a false exit is
  self-correcting." `[E]`
- Worker status protocols are *sparse by contract*: crewmates append status only for
  supervisor-actionable phase changes, "because every append wakes firstmate." `[E]` `[I]` —
  the same economy the design wants from subagent structured returns, stated as an interface
  rule.

## 3. Overnight-loop mechanics (gnhf)

A ralph-style outer loop (fresh agent invocation per iteration until cap/stop), with the
sharp edges filed down:

- **One small, individually-verifiable, committed change per iteration**; commit on success,
  `git reset --hard` on failure — *except* git-commit failures, which preserve work and ask the
  next iteration to repair. `[E]`
- **Error taxonomy drives the retry policy:** agent-*reported* failures → continue immediately;
  retryable hard errors → exponential backoff; permanent errors (credit exhausted, auth) →
  abort at once (stderr regex → `PermanentAgentError`). `[E]` `[I]` — maps onto the governor's
  source ladder and the build-loop driver's failure handling (§5.1, §9).
- **A complete no-op iteration counts as a failure** so the loop halts instead of spinning —
  a ready-made anti-spin rule for the §9 liveness guard. `[E]`
- **Mid-iteration token abort:** `--max-tokens` aborts *inside* an iteration once reported
  usage crosses the cap — finer-grained than the design's between-task governor check; a
  per-task token cap (fed by the P95 forecast) is the natural §9 sibling to the step-count cap.
  `[E]` `[I]`
- **Sticky "estimated" accounting flag:** if any usage source in a run was an estimate, every
  downstream total renders with `~` — honesty about accounting quality propagates instead of
  silently blending measured and guessed numbers. `[E]` — directly applicable to the governor's
  `estimate` rung (§5.1, already flagged `optimistic`; the stickiness is the addition).
- **Cross-iteration memory is orchestrator-owned:** the loop maintains `notes.md`; the agent
  reads it but is forbidden to write it; each iteration must return structured
  `key_changes_made` ("material outcomes, not activities") and `key_learnings` ("surprising,
  not captured by previous notes"). `[E]` — a concrete mechanization of the design's
  lessons-corpus injection (§4).
- **Supervision skill rules** (verbatim-worth): "Read notes/logs as **claims, not evidence**";
  "Never summarize an overnight run from memory" — a morning review reconstructs state from
  `git status/log` + process checks before saying anything. `[E]` — the design's fresh-evidence
  rule (§7) extended to the orchestrator's own self-reports. Independent support for
  agent-self-report unreliability is in
  [correctness-and-verification-evidence.md](../validation/correctness-and-verification-evidence.md) (METR
  reward-hacking observations; false "done" as RLHF-default shape).

## 4. Worktree pool (treehouse)

- **Pool of reusable, detached-HEAD worktrees** per repo: acquire = fetch + reset an idle pool
  member to the fresher of local/remote default; release = kill lingering processes (live
  process scan of the worktree path), reset, return to pool — **dependencies and build caches
  intact for the next task**. Detached HEAD avoids branch-name conflicts entirely. `[E]`
- **Durable leases** survive process death: a leased worktree with zero live processes is never
  handed out or pruned until explicitly returned — the right primitive for a pipeline that dies
  mid-run and resumes from disk. Owner reservations self-heal when the owner PID dies. `[E]`
- **Fail-closed teardown with precise "landed" semantics:** prune is dry-run by default,
  deletes only merged+clean+idle, proves HEAD against a *freshly fetched* remote default, and
  **refuses when origin is unreachable** ("cannot verify"). Blanket `--force` was deliberately
  removed, replaced with per-risk opt-ins (`--include-unlanded`, `--include-leased`, exact-path
  only) and a risk-labeled preview. firstmate's teardown extends "landed" to **patch-ID
  containment after the pipeline replayed the branch** — handles squash-merge-then-delete
  without false refusals. `[E]`
- **Supply-chain posture:** `post_create`/`pre_destroy` hooks load from *user-level config
  only*; "hooks in repo-level treehouse.toml are ignored for safety." `[E]`
- `[I]` Design fit: the pool kills per-task environment cold-start — the environment analog of
  prompt-cache discipline — and is the natural implementation of the §4 worktree-lifecycle
  residue at Stage 2. Cache interaction stated precisely: a stable pool-slot cwd stabilizes the
  cache key (cache is per machine+directory), but commits still cold-start the next session's
  prefix (git snapshot is in the system prompt,
  [claude-code-and-max-plan-facts.md](../platform-facts/claude-code-and-max-plan-facts.md)) — so the pool's win
  is environment setup and worktree churn (O2), *not* the §6.2 per-pipeline cache-warmup cost,
  which stays in the admission calculation.

## 5. Merge/push gate (no-mistakes)

A local bare repo as gate remote: `git push no-mistakes` triggers a daemon that replays the
branch in a disposable worktree through a **fixed, non-reorderable pipeline**
(`intent → rebase → review → test → document → lint → push → pr → ci`); only all-green reaches
the real target. Load-bearing specifics:

- **Findings taxonomy richer than pass/fail:** every step emits findings with
  `severity (error|warning|info)` × `action (auto-fix|ask-user|no-op)`, plus **per-step
  auto-fix budgets** (review defaults to 0 = always human). "The pipeline, not the crewmate,
  applies validation fixes." Step order is justified step-by-step (review before test "so the
  agent reads fresh code, not code it may have touched during fixes"). `[E]` — a ready schema
  for the design's gate/verdict interface (§7), encoding *who may fix what*.
- **Trust boundary for executable config:** commands/agent config are **always read from the
  default branch at a freshly-fetched commit, never from the pushed SHA**; fetch failure forces
  those fields empty rather than falling back to a stale copy. `[E]` — the ratification-queue
  trust model (§7 governed self-modification) extended to config that *executes*; closes a gap
  the design's six-layer stack does not explicitly name (a task branch editing hook *config*
  rather than machinery code).
- **Committed evidence directories:** validation evidence (transcripts, structured captures,
  probe outputs) rides the PR in-repo (`.no-mistakes/evidence/<task>/`), reviewable and
  durable. `[E]` — a concrete home for the design's escapes log / EVIDENCE.md inputs (§8).
- **Data-loss guard on push** (refuses updates that would discard unincorporated target
  commits); daemon startup recovery marks stuck runs failed, reaps orphans; a new push to the
  same branch cancels the in-flight run. Agent fallback ladder retries *process-level*
  failures with the next agent but never structured-finding failures. `[E]`
- Parked runs surface `awaiting_agent: parked <duration>` so a supervisor distinguishes waiting
  from working in one read. `[E]`

## 6. Human ratification UX (wheelhouse, m87)

IssueOps decision cards — every open card is one pending human decision; a checkbox tick, a
slash command, or plain English executes it. The parts that transfer to the design's
ratification queue (§6.3, §7, plan E3):

- **Card anatomy:** Situation (deterministic facts) → advisory LLM triage (**cached per
  head-SHA — one triage per revision, ever**: spend control) → Recommended action → exactly-one
  checkbox with machine-parseable `<!-- opt:key -->` markers → hidden HTML comment carrying
  machine state including a **material-change signature**. `[E]`
- **Stale-decision guard:** acting re-checks the target's head SHA; a moved head refuses with a
  note — a ratification is never applied to something other than what was reviewed. `[E]`
- **Authority separation:** LLM output is advisory-only and never authorizes actions; trusted
  deterministic code executes; every acting path checks the sender is the owner. Automation
  levels (away-mode, yolo) *never* relax the human-approval carve-out for destructive/
  irreversible/security-sensitive actions. `[E]`
- **Fail-open holds for advisory machinery:** a new card shows no checkboxes until first triage
  completes, but triage *failure* also publishes (never a permanent wait) — advisory layers
  fail open, enforcement layers fail closed. `[E]` `[I]` — resolves cleanly the design's §7
  "fail-open" wording question logged in the implementation plan: *advisory* = fail-open,
  *gates* = fail-closed.

## 7. Token-free harness testing (acp-mock, no-mistakes fakeagent, gnhf e2e)

The stack's answer to "how do you test an agent loop without spending quota" — a gap the
harness plan currently covers only with unit tests:

- **A deterministic mock agent process** speaking the real wire protocol: emits fixed message
  chunks or JSON, synthetic `usage_update`s (`static` or `cumulative` — cumulative multiplies
  by successful prompt count; cancelled prompts don't increment: exercises multi-turn
  accounting), N tool-call events, **turn-level workspace side effects** (append to a file only
  after a successful turn), and a hold-open flag to test cancellation deterministically. `[E]`
- **Record-once, replay-forever traces:** normalized runtime JSONL recorded from real agents,
  replayed as protocol events for free; **re-recording "spends real API quota, and should be
  reviewed before committing."** `[E]` — quota-spending test fixtures treated with the same
  operator-gating discipline as the design's cache-weight experiment.
- stdout is protocol-only; lifecycle logs are opt-in JSONL. `[E]`
- `[I]` Design fit: a mock implementer/validator emitting deterministic usage numbers +
  scripted workspace mutations lets the build loop, governor thresholds, window-aware
  admission, ledger accounting, and gate logic be e2e-tested at zero quota — proposed as its
  own plan increment before the build-loop skill.

## 8. Policy-vs-mechanism split for routing config (firstmate crew-dispatch)

- Routing rules live as **natural-language policy the LLM matches by judgment**
  (`{"when": "trivial mechanical edit...", "use": {"harness": "claude", "model": "haiku",
  "effort": "low"}}` ... `"default": {...}`); shell never parses the NL — but **enforces that
  judgment happened** (when the policy file exists, spawn refuses launches without an explicit
  routing decision). Unsupported effort values are recorded for audit; the launch flag is
  omitted rather than guessed. `[E]`
- `[I]` Design fit: the §5.3 tier/effort routing table gains a clean two-layer shape —
  deterministic allowlist validation (already built, A2) *plus* an enforce-that-routing-was-
  consulted backstop in the spawn path.

## 9. Cross-cutting: how this practitioner designs for unattended operation

1. Bash-first, tokens-last — deterministic code for polling/classification, LLM only for
   judgment. 2. Append-only event logs; derived, reconciled current state. 3. Write the durable
queue before advancing state. 4. Guards over discipline — invariants checked at every
touchpoint, alarms ride outputs the agent already reads. 5. Fail-closed teardown with precise
"landed" semantics; per-risk opt-ins instead of `--force`. 6. NL policy, mechanical backstop.
7. Executable config only from the ratified branch. 8. Structured, self-documenting contracts
at every agent boundary. 9. Success requires evidence; recording quota-spending fixtures is an
operator-gated act. 10. No automation level relaxes human authority over destructive actions.
`[E]` (each grounded in the sections above) `[I]` (the enumeration as design guidance)
