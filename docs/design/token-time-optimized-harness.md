# Dual-objective agent harness on Claude Code — technical design

> **Goal.** An agent harness that takes a thorough technical design spec and drives it to a
> *correctly implemented* codebase while explicitly optimizing two objectives: **(1) minimal
> token spend measured against the Claude Code Max plan's 5-hour and weekly rate windows**, and
> **(2) minimal wall-clock time to correct completion** — subject to a correctness floor that is
> never traded. The governing design principle: **bind every mechanism to a built-in Claude Code
> primitive first**; custom machinery is only the residue no built-in covers.
>
> Compiled from the research corpus in [../research/](../research/) (see its
> [README](../research/README.md) for the index and the design-section → research map): the
> landscape/novelty study, the correctness-and-verification evidence, the re-validation reuse and
> leakage prior-art, the token-economics and scheduling evidence, and the volatile Claude Code /
> Max-plan and vault-isolation fact references. Facts carry confidence tags: `[official]`
> Anthropic docs, `[measured]` community measurement with data, `[contested]` conflicting
> evidence, `[folklore]` practitioner consensus.

---

## 1. Scope

This document is the founding design for the harness this repository will implement. The system
in one paragraph: a human and the orchestrator produce an approved technical plan; a manual,
operator-started **build loop** then grinds the plan task-by-task through context-isolated
**implementer** and **validator** subagents (the spec is their only shared context), merging
only through an objective gate; durable state lives on disk so any context can die and the loop
resumes from files alone; a reflection layer tunes cost and quality from telemetry, proposing —
never self-applying — changes to its own machinery. On top of that spine sits the explicit
dual-objective optimization layer this document specifies.

**Non-goals.** Portability off Claude Code (accepted coupling; model/tier indirection is the
seam if a fork ever needs one). Multi-operator teams. Large brownfield codebases (the
phased-ledger model is greenfield-shaped,
[landscape-and-novelty.md §5](../research/landscape-and-novelty.md)). Auto-scheduled firings — whether a prior
firing is still alive cannot be judged reliably from a tool-call shell, so firings are
operator-started and operator-stopped, removing the double-run failure mode entirely.

## 2. The objective function

Lexicographic — never scalarized into one weighted score:

- **O0 — correctness floor (hard constraint).** Validation escapes ≈ 0, enforced by machinery,
  not model virtue. This is not over-engineering: evaluator-patching and hardcoded-pass reward
  hacking are measured behaviors (METR o3, DebugML's 28+ instances), ~31% of SWE-bench-Verified
  passes ride on tests too weak to catch a wrong fix, and a false "done" is the RLHF-default
  completion shape
  ([correctness-and-verification-evidence.md §1](../research/correctness-and-verification-evidence.md)).
  **O0 is never traded for tokens or time.**
- **O1 — token spend against the Max windows.** The budget is not $/task; it is two rolling
  allowances — the 5-hour window and the weekly caps — shared account-wide. Consequences:
  - Spend that lands in a fresh window is *operationally cheaper* than spend near a wall:
    hitting the wall mid-panel wastes the whole in-flight panel.
  - The weekly cap makes *total build tokens* matter, not just burst rate: eliminating redundant
    re-reasoning (re-validation reuse §5.5, cache discipline §5.2) buys more build per week.
- **O2 — wall-clock to correct completion.** Includes human latency (ratification round-trips,
  parked-blocker waits), not just compute time.

Two rules are load-bearing enough to state up front:

- **Parallel lens breadth is not a wall-clock cost.** N diverse validator lenses run
  concurrently ≈ the slowest lens. Panel breadth is governed by O0 (risk) and O1 (tokens),
  and is **never** shrunk to save wall-clock.
- Controllers may economize on **token redundancy** (re-authoring, re-reasoning, prefix
  re-reads) and on **serialization idle** (empty concurrency slots). They may not economize on
  rigor where O0 applies (protected risk profiles: strengthen-only).

**The one real O1↔O2 exchange:** concurrent task pipelines. All parallel sessions and subagents
drain **one shared account pool** `[official]` — parallelism buys wall-clock only, never budget.
And at equal thinking-token budget a single agent *matches or outperforms* multi-agent on
multi-hop reasoning (arXiv 2604.02460 `[measured]`; scoped to reasoning benchmarks, not coding) —
so parallelism is purchased *only* out of window headroom (§6.2), never assumed free. The same
result predicts multi-agent becomes competitive precisely when a single agent's context
utilization degrades — the long-session regime — which is why the harness still fans out for
*context isolation* (§3 principle 3) rather than treating the citation as a blanket ban on decomposition.

## 3. Design principles

1. **Built-in before custom** (§4 is the map). If Claude Code ships it — subagents, worktrees,
   hooks, skills, caching, structured output, telemetry — the harness configures it rather than
   rebuilding it. Custom shell scripts are the residue, and each must justify itself in the
   evidence trail (§8) or be pruned.
2. **Zero-token enforcement.** Everything safety- or budget-load-bearing runs as a **hook or
   script** — deterministic, model-free, un-skippable, costs no context. Prose guards burn
   tokens every turn *and* get skipped exactly when the loop is degraded
   ([landscape-and-novelty.md §4](../research/landscape-and-novelty.md)). Command
   hooks cost 0 tokens; prompt/agent hooks cost tokens and are reserved for rare gates
   `[official]`.
3. **Context isolation is also compression.** Subagents exist for correctness (blind
   validation) *and* economy: a worker's exploration tokens die with its context; only the
   structured return crosses to the orchestrator. This is the token-efficient fan-out pattern
   Anthropic itself uses (multi-agent research system `[official]`).
4. **Disk is the memory.** Phase ledgers, the status index, the run-log, and the lessons corpus
   live on disk; any context can die at any moment and the loop resumes from files alone. This
   makes fresh-context workers (and orchestrator compaction) free in *correctness* terms, so
   the token optimizer can use them aggressively.
5. **Measure, then move.** Every economy lever ships with its telemetry and a ground-truth
   check (the escapes log, calibration canaries). No downgrade without a catch-proof; one
   lever at a time; sample floors respected. Limits themselves are volatile (§10.3) — ceilings
   are calibrated empirically, never hard-coded.

## 4. Leverage map — need → Claude Code built-in → custom residue

| Need | Built-in (how) | Residue we still build |
|---|---|---|
| Isolated worker contexts | **Subagents** (`.claude/agents/*.md`; per-agent `model`, `tools`; summary-only return) `[official]` | Spec-only shared-input discipline; verdict/handoff schemas |
| Parallel file edits, zero conflicts | **Git worktrees** (`claude --worktree`, subagent `isolation: worktree`, `.worktreeinclude`, auto-cleanup) `[official]` | Per-task worktree naming + lifecycle policy (thin script) |
| Un-skippable enforcement, 0 tokens | **Hooks** (PreToolUse / PostToolUse / Stop / SubagentStop / SessionStart; deny>ask>allow; matchers) `[official]` | The merge-gate scripts the hooks invoke |
| Reusable procedures, cheap until used | **Skills** with progressive disclosure (names at start, body on invoke) `[official]` | The skill content itself (planning, build loop, calibration, status) |
| Interactive planning w/o edits | **Plan mode** `[official]` | The plan template, risk-classification table, human gate |
| Completion gating | **Stop hooks** (script-based; model-evaluated goal hooks) `[official]` | Closure gate vs frozen plan snapshot + fresh-evidence rule |
| Structured worker returns | **`--json-schema` / structured outputs** (server-side validation) `[official]` | The verdict/report schemas themselves |
| Model routing | Per-subagent `model` param; session `/model`; aliases `[official]` | Abstract tier indirection + per-task routing policy (§5.3) |
| Effort routing | Session `/effort`; per-agent `effort` on the Workflow/Agent spawn path (verified by direct probe) | Per-profile effort config + the spawn-path fallback ladder |
| Cost/usage telemetry | Statusline `rate_limits.{five_hour,seven_day}` + `resets_at` + `current_usage` (in-session, server-side utilization); `/usage`, `--output-format json` (per-turn tokens/cost), OTEL consumption metrics, per-subagent token totals `[official]` | Per-role run-log aggregation + the budget governor's source ladder (§5.1) |
| Prompt-cache economy | **Automatic prompt caching** (1h TTL auto on subscription, 5-min on credits/subagents; auto breakpoints; model+effort are cache-key components) `[official]` | The *discipline* (§5.2): freeze-prefix rules, escalate-at-boundary |
| Tool-definition economy | **ToolSearch deferred loading** (names only at start; schema on use — default for MCP) `[official]` | Keep the MCP surface minimal; prefer CLI tools (`gh`) over MCP servers `[official]` |
| Long-lived instructions | CLAUDE.md (<200 lines guidance), path-scoped rules, `@imports`, auto-memory `[official]` | Lessons corpus + orchestrator-curated injection at spawn |
| Resume across deaths | Session persistence, `--resume`/`--continue`/`--fork-session` `[official]` | Ledgers + status index as the *canonical* resume state (disk > transcript — resuming a huge transcript reprocesses it at full cost `[measured]`) |
| Undo | `/rewind` checkpoints (session-local) `[official]` | Git remains canonical history; checkpoints are convenience only |
| Headless execution | `claude -p`, `--allowedTools`, `stream-json`, `--bare` `[official]` | The build-loop skill + an advisory single-run marker |
| Background work | Background bash, background subagents, batched parallel tool calls `[official]` | Fan-out patterns (§6.1) |
| Output filtering | PostToolUse hooks pre-filtering tool output (10k-line log → the failures) `[official example]` | Which filters to apply per gate command |

**Deliberately not used:** auto-cron firing of the build loop (see Non-goals); agent teams for
implementation (≈7× a standard session `[official]`, and Anthropic's own caveat: coding has few
truly parallelizable interdependent tasks `[official]` — the parallel-friendly part of this loop
is validation, which subagent fan-out already covers); `ANTHROPIC_API_KEY` in the environment
(silently bills API instead of the subscription `[official]`).

## 5. The token-economy layer (O1)

### 5.1 Window model and budget governor

Facts the governor is built on (details + volatility log in §10):

- The 5-hour window **anchors at the first message**, not rolling continuously `[measured]`;
  weekly caps reset at a fixed per-account time `[official]`. Current caps: one overall weekly
  + one **Sonnet-specific** weekly (the Opus-specific cap was removed Nov 2025) `[official]`.
- **Everything shares one pool**: Claude app + every Claude Code session + every subagent
  `[official]`. Depletion factors: model, effort, thinking (billed as output), tools,
  attachments `[official]`.
- No token quotas are published, and limits/accounting rules changed ≥7 times in 12 months
  (§10.3) — **ceilings must be runtime-calibrated, never hard-coded**.

The **budget governor** is a small deterministic script the loop consults **between** tasks
("don't start what you can't finish"). It reads window occupancy from a source ladder,
best-source-first:

- `statusline` — the officially-documented statusline stdin JSON exposes
  `rate_limits.five_hour.used_percentage`, `rate_limits.seven_day.used_percentage`, and
  `resets_at` (Unix epoch), plus `context_window.current_usage` cache counters. This is
  **server-side utilization, machine-readable in-session, zero extra tokens** — the primary rung
  `[official]`.
- `oauth-usage` — for unattended/headless firings that lack a statusline surface, the
  undocumented `GET api.anthropic.com/api/oauth/usage` (Bearer token + `anthropic-beta:
  oauth-2025-04-20`) returns five_hour / seven_day / seven_day_sonnet utilization; an
  **unstable internal endpoint**, used only as a fallback `[measured]`.
- `estimate` — per-role token sums from the run-log over rolling windows; the last-resort
  fallback, and **systematically optimistic**: it cannot see quota the operator's own
  interactive Claude app / IDE use drains from the same shared pool `[official]`, so it
  under-counts true occupancy. Never the sole source when a live-utilization rung is available.

(The former `quota-file` rung — operator-fed from `/usage` — is dropped: the statusline feed
supersedes it. A dedicated quota CLI, anthropics/claude-code#13585, remains unshipped; the ladder
upgrades in place if it lands.) The occupancy reading drives two thresholds:

- **degrade** (default 0.8 of a window): panels shrink to profile minimums (never below a risk
  floor), no new tasks start, in-flight work commits; the implementer starting tier steps down
  where the profile allows (§5.3).
- **pause** (default 0.95): clean pause — resume marker to the status index, worktrees
  reconciled, run marker released. The next firing after the window reset resumes from disk.

Thresholds ship **observe-only** first (log the crossing, don't act) so ceilings are tuned on
real telemetry before they gate work — untuned hard caps stall the whole loop (§11).

**Window-aware admission** (the scheduler input, §6.2): each candidate task carries a **quantile**
cost forecast, never a point estimate — measured same-task token spend varies up to **30×** on
identical agentic-coding tasks, and neither model self-estimates (r ≤ 0.39, systematically low)
nor human difficulty ratings track burn well `[measured; arXiv 2604.22750]`. Forecast on a tail
percentile (P95-of-rolling-window, ≈ 4× the mean in practice `[folklore]`), carry per-(tier,
effort) overshoot variance since thinking budgets are soft targets not hard caps (§5.3), and
admit against the degrade threshold **with the forecast added burn**. A heavy critical-profile
task is admitted early in a fresh window; near a wall only cheap routine tasks (or nothing)
start. Escape valve: extra-usage credits at API rates exist (`/usage-credits`, $2k/day cap
`[official]`) — but they are **opt-in-in-advance with no silent spillover** `[official]`, so an
unattended run halts cleanly at the wall unless credits were pre-enabled; surfaced to the operator
as a *choice* at pause time, never auto-purchased.

### 5.2 Prompt-cache discipline (the #1 hidden lever)

Measured reality: a session carries a 20–30k-token prefix (system prompt + CLAUDE.md + memory
+ tool names) re-sent every turn `[measured]`; in one 30-day single-user measurement, cache-read
volume ran **1,310× fresh I/O tokens** and scaled with CLAUDE.md size, not workload
`[measured; one user, anthropics/claude-code#24147]`. Whether cache reads count against
*subscription* limits at a discount or near-full weight is **`[contested]`** (§10.2; community
telemetry points to near-full window weight, still officially unanswered) — under either reading,
the design conclusion is identical: **cache-busting is the catastrophic spend event** (one client
cache bug produced 10–20× inflation before it was fixed `[measured]`), and the prefix must be
small and immutable.

Rules (mechanized where possible):

1. **Frozen prefix per firing.** The actual mid-firing cache-busters `[official]` are: a
   `/model` switch, an `/effort` change, the first fast-mode toggle (all three are cache-key
   components), a bare-tool deny rule (`Bash`, `WebFetch` — tool defs live in the system-prompt
   layer), and a non-deferred MCP connect/disconnect. These do not change mid-firing — model,
   effort, hook set, MCP set, and skill inventory are fixed at spawn; escalation happens at a
   worker boundary, never mid-transcript (§5.3). Mechanization: a PreToolUse hook flags
   mid-firing edits to prefix files (`Edit|Write` matcher on CLAUDE.md / constraints / settings)
   — note that a mid-session CLAUDE.md edit does not actually bust the cache but **silently
   fails to apply** until the next `/clear` or restart `[official]`, so the hook guards against
   the silent no-op as much as the spend event.
2. **Small prefix.** CLAUDE.md stays under ~200 lines `[official guidance]`; reference material
   lives in skills (progressive disclosure) and path-scoped rules; lessons are injected
   per-spawn by the orchestrator, not resident in the prefix.
3. **TTL cadence.** On subscription auth Claude Code requests the **1-hour TTL automatically**
   (no `ENABLE_PROMPT_CACHING_1H` — that env var is API-key-only), but it **silently drops to 5
   minutes while drawing on usage credits** `[official]`. Subagents get the 5-minute TTL even on
   subscription and start cold; forks inherit the parent cache `[official]`. The build loop's
   inner cadence turns over faster than either TTL while working; a *planned* long gap (awaiting
   a human) is one cache miss, accepted. Long-idle sessions are ended cleanly rather than kept
   warm artificially.
4. **Never resume a huge transcript for a new task.** Fresh session + disk state beats
   `--resume` of a long history: resume reprocesses the full transcript **after a Claude Code
   upgrade or once the TTL lapses** (within-TTL resume hits the warm cache) `[official]`, and a
   resumed idle session attributes its whole accumulated cache context to the **new** rate
   window — measured 15M tokens charged for ~20k of real work `[measured]`. Ledgers are the
   resume state; treat any idle-session resume as a heavy admission (§9), not a free
   continuation.
5. **Workers are short-lived by construction.** Implementers/validators are subagents (or
   headless `-p` one-shots): they pay their prefix once, do one task, die. No compaction debt
   accumulates anywhere except the orchestrator, whose context is structured-state-only.

### 5.3 Model + effort routing (two axes, start low, escalate on proof)

Model selection is indirected through abstract tiers (cheap / standard / capable / max →
concrete model ids in one config table), and rigor is expressed as named **risk profiles**
(e.g. routine < elevated < high < critical), each specifying validator count, lenses, tier,
and effort. On top of that:

Start-cheap-escalate-on-proof is established prior art, not folklore: learned-scorer cascades
match a top model at up to 98% lower cost (FrugalGPT), and effort routing cuts reasoning tokens
35–53% at 0–2pt success loss (ARES) `[measured]`. But the savings band is task-dependent — ~73–98%
on knowledge/chat/math benchmarks, **~56% best-case on code generation, ~30% out-of-distribution**
`[measured]` — so the harness's coding domain sits at the low end, and a router trained on a
mismatched distribution can perform *worse than random* `[measured]`. Two consequences: the
design's escalation signal is a *verified durable FAIL* (higher-precision than a learned scorer,
but it pays a full failed attempt per misroute — which is what the break-even guardrail is for),
and a validated **upfront** router (the duration predictor) is worth more than a longer escalation
chain (pre-generation routing beats pure escalate-on-failure on 4 of 5 benchmarks by avoiding the
wasted cheap attempt `[measured]`).

- **Tier axis — per-task starting tier.** Start the implementer as cheap as the task's risk
  allows and let an escalation ladder (N durable FAILs → bump one tier) walk it up; the gate +
  validator panel remain the correctness net. Keep the ladder **multi-rung** — the claim that a
  two-tier cheap→capable pair captures all the value did not survive adversarial verification
  (refuted 1-2), so it is not adopted. Staged rollout: ship the simple per-profile starting-tier
  override first; a deterministic **duration-bucket predictor** (scored from spec size, file
  count, subsystem breadth, novelty — a script, not an LLM call, since models cannot self-predict
  their own token spend, r ≤ 0.39 `[measured]`) and the full bucket×profile starting-tier matrix
  stay behind a flag until (a) the simple lever's telemetry proves escapes ~0 and $/task down and
  (b) the predictor's features are validated against *measured* burn — human difficulty ratings
  track cost only weakly `[measured]`, so the features are not assumed-good. Guardrails,
  non-negotiable:
  1. *Safety is not a cost lever* — tasks on protected profiles or risk-floored surfaces never
     start cheap.
  2. *Nature beats difficulty* — recency-sensitive tasks (APIs newer than the cheap tier's
     training) route off cheap regardless of size.
  3. *Escalation churn has a break-even* — at roughly >40% cheap-tier failure on a bucket, the
     wasted attempt + re-run costs more than starting one tier up; the controller trips the
     start tier back up when telemetry crosses it. (This threshold is exactly the >40%-failure
     regime where published work says upfront routing should replace the cascade `[measured]`.)
- **Effort axis.** Profiles carry `effort` alongside `model`. The Workflow-based spawn path
  threads per-agent `model` *and* `effort` (re-verified by direct probe on Claude Code 2.1.45,
  2026-07-04: all five effort levels dispatch; both tested model overrides are honored — see
  [tools/budget-governor/probe-spawn-portability-2026-07-04.md](../../tools/budget-governor/probe-spawn-portability-2026-07-04.md)),
  with a batch of parallel `Agent` calls as the portable fallback (model-only; effort
  session-level). **Correction:** "invalid ids fail loud" does not hold as previously stated —
  an invalid `effort` string is **silently accepted** with no error, and an invalid `model` id
  fails only as an async `null` result + a workflow-level log entry, not a catchable throw.
  **The spawn code must therefore validate `(model, effort)` against an explicit allowlist
  before calling `agent()`/`Workflow`**, and must check results for `null` rather than relying on
  an exception. Effort lands in the run-log so the controller segments cost/catch-rate by
  `(tier, model_id, effort)`.
  **Neither uniform default is safe:** always-low drops agent success ~20pts, always-high
  overthinks trivial work (≈1,953% extra tokens on trivial inputs) `[measured]` — effort is
  *routed*, never a static default. Effort is a **soft** target with an overshoot tail, not a
  hard cap `[official]`, which is why the governor carries per-(tier, effort) variance (§5.1).
  Downgrades require a fresh calibration PASS at the lower effort; protected profiles: raise-only.
- **Escalation ordering — effort before tier, always at a worker boundary.** Both model and
  effort are cache-key components `[official]`: a mid-session bump of either busts the full
  cache (§5.2). So escalation never happens mid-transcript — it happens at the next fresh worker
  spawn, where a cold cache is paid anyway. Given that, prefer an *effort* bump before a *tier*
  bump: within one model, an escalated respawn can be cheaper to warm, and tier changes drain a
  different weekly pool (below).
- **Routing floor for grunt work:** mechanical fan-out (file moves, renames, log filtering,
  status sweeps) always runs cheap-tier subagents — deliberate routing cuts cost substantially
  (the published band above; the gate catches any miss).
- **Weekly-pool awareness:** with the model-specific weekly cap now on **Sonnet** rather than
  Opus `[official]`, "route grunt work down-tier" is no longer automatically
  weekly-budget-safer. The controller tracks which pool each tier drains and re-checks the
  mapping after every Anthropic limit change (§10.3).

### 5.4 Context hygiene

- Orchestrator ingests **structured state only** (statuses, verdicts, decisions) — never raw
  file dumps; heavy reading is delegated and dies with the subagent.
- Workers receive **scoped specs** (the task's ledger entry + injected lessons), not the whole
  plan; specific file paths, not pasted file contents `[official guidance]`.
- MCP surface minimal; ToolSearch deferral on (default); prefer CLI tools over MCP servers
  `[official]`; `.claudeignore` tuned (measured up to ~85% context reduction `[measured]`).
- Compaction is a survivable event, not a stop — but the *economical* pattern is to make it
  rare by keeping the orchestrator lean, and to prefer clean session boundaries
  (`/clear`-equivalent + disk resume) over repeated `/compact` (compaction is itself a model
  call over the history `[official]`).

### 5.5 Re-validation reuse — the vault (biggest O1 lever on retries)

On a durable-FAIL re-validation, a naive loop re-authors held-out tests and re-reviews a
~95%-unchanged diff — pure token redundancy. Design (evidence base:
[revalidation-reuse-and-leakage.md](../research/revalidation-reuse-and-leakage.md)):

1. **Implementer-blind held-out vault.** Panel-authored held-out tests persist where the
   implementer's context/worktree can never see them; isolation is the OS-enforced six-layer
   stack in §7 (sandbox `denyRead` + Read/Edit deny rules + strict-mode flags + out-of-scope
   config + egress control + separate-process roles), not path convention — hidden tests have
   been exfiltrated from autograders via submitted code, and a Claude Code agent has
   autonomously disabled its own sandbox
   ([isolation-and-sandboxing.md](../research/isolation-and-sandboxing.md)). Proven by a
   vault-canary read-attempt in the gate self-tests, not assumed.
2. **Safe incremental re-validation.** On re-validation, **replay** the vault against the
   unchanged surface (zero re-authoring tokens) under the Ekstazi/TIA **safe-RTS property** —
   never skip a test the change could affect; full-run fallback for anything unanalyzable
   ([revalidation-reuse-and-leakage.md §2](../research/revalidation-reuse-and-leakage.md)).
3. **Fresh authoring on the changed surface is mandatory.** A replayed corpus is a regression
   floor, structurally unable to find a new hole (frozen corpus = saturated corpus; ~27% of
   real faults uncoupled from standard mutants —
   [revalidation-reuse-and-leakage.md §4](../research/revalidation-reuse-and-leakage.md)). The
   vault shrinks re-authoring; it never eliminates it.
4. **Leakage budget.** Reuse of a fixed hidden set across adaptive fix-iterations degrades it
   (Ladder/Thresholdout,
   [revalidation-reuse-and-leakage.md §5](../research/revalidation-reuse-and-leakage.md)):
   rate-limit replays, rotate/refresh the corpus, and keep **full fresh re-derivation on
   risk-floored surfaces** — exactly where a gamed frozen set is most dangerous.

### 5.6 What the harness deliberately does not spend on

- No auto-cron; no idle-warm sessions; no speculative implementation of pre-decomposed
  (provisional) ledgers — look-ahead is planning-only.
- No free-running reflection: reflection triggers on ground-truth events (an escape, a canary
  miss, a durable FAIL), never as open-ended synthesis (intrinsic self-correction *degrades*
  without external signal —
  [correctness-and-verification-evidence.md §2](../research/correctness-and-verification-evidence.md)).
- **No spending-through a doomed trajectory.** Agents are measurably over-optimistic and keep
  spending on tasks unlikely to succeed rather than alerting early
  (r = 0.35 capability↔budget-awareness) `[measured]`; an external abort-on-predicted-failure
  check inside long-running tasks (§9 liveness guard) recovers 28–64% of the tokens a failing
  trajectory would otherwise burn `[measured]`. Ships observe-only, with false-aborts counted
  against the O0 floor before it gates.
- Dormant opt-in controllers are pruned on evidence (§8); insurance controllers (risk floors,
  calibration, closure, budget) are exempt — there, silence is the desired state.
- `DISABLE_NON_ESSENTIAL_MODEL_CALLS=1` on headless firings `[official]`.

## 6. The wall-clock layer (O2)

### 6.1 Token-free accelerators first

These cut elapsed time without buying tokens; they are always on:

1. **Pipelining:** task N+1's spec + contract tests are authored while task N validates; the
   next phase pre-decomposes into a provisional (planning-only, not runnable) ledger while the
   current phase's last task runs.
2. **Global cross-phase DAG scheduling:** each tick, candidates = every not-started task whose
   hard deps are complete, **any phase**; fill idle slots prioritized by critical-path, then
   risk; gated by a `start-early-safe` predicate (soft `mayBeInvalidatedBy` edges in the task
   schema) so pulled-forward work is never likely rework — wall-clock bought without
   wasted-token risk. Phase tags stay for human legibility; the read-only preflight check
   verifies the cross-phase dependency graph is a DAG.
3. **Panels are always batched-parallel.** One turn, N `Agent` calls (or one Workflow
   `parallel()`): wall-clock ≈ slowest lens. This is why lens breadth is O0/O1-governed only.
4. **Hooks over prose.** Every deterministic check that would otherwise be an orchestrator
   turn (merge gating, git-state checks, output filtering) runs as a hook — zero tokens *and*
   zero turn latency.
5. **Structured outputs everywhere** (`--json-schema` / schema-forced subagent returns):
   eliminates parse-repair round-trips `[official]`.

### 6.2 Paid parallelism — admission-controlled by window headroom

A concurrency cap >1 (worktree-isolated implement→validate pipelines) is the one lever that
spends tokens to buy time. Admission rule, evaluated per tick:

> Admit a second/third concurrent pipeline **only if** (a) window occupancy is below the
> degrade threshold *and forecast (on the P95 quantile, §5.1) to stay below it with the added
> burn*, (b) the runnable set contains genuinely independent tasks (hard deps +
> `mayBeInvalidatedBy` clear), and (c) a surface-contention cap (max concurrent surfaces) is
> respected.

The admission cost side must include a **per-pipeline cache warmup**: worktrees do *not* share
prefix cache (the cache is scoped per machine+directory, and each worktree is a distinct cwd
`[official]`), so every concurrent pipeline pays its own ~20–30k-token cold prefix; each commit
likewise cold-starts the next fresh session's prefix (the git snapshot is part of the system
prompt) `[official]`. Rationale: bursting a fresh 5-hour window empty in <1h then stalling 4h is a
*wall-clock loss*, not a win — on subscriptions the binding constraint is often the window, not
total tokens `[folklore, consistent]`. Practitioner consensus caps useful concurrency at 2–4
pipelines `[folklore]`; the run-log attributes rework/merge-conflict cost to concurrency so the
controller can tune the cap on evidence. Anthropic's frontier fan-out datapoints — a **90.2%**
quality gain over single-agent on an internal research eval (at *unequal*, much larger budget),
a separately-reported time reduction from parallelism, and a **~15× token multiplier vs a chat
baseline** (single agents ~4×) `[official]` — are *three distinct measurements*, not one exchange
rate; together they say the same thing: the exchange is steep, and token spend alone explains ~80%
of agentic-research performance variance `[official]` (so cheap-tier runs systematically
underperform, raising the cost of a routing miss, §5.3). This harness buys parallelism for
*validation* (independent lenses, cheap wall-clock) structurally, and for *implementation* only
under the admission rule.

**Window-phase scheduling:** heavy fan-out (big panels, multi-task bursts) schedules right
after a window reset; the tail of a window runs cheap serial work. The 5-hour anchor-at-first-
message behavior `[measured]` even allows deliberate window alignment to the operator's day
(the "warmup" pattern `[folklore]` — surfaced as an operator note, not automated).

### 6.3 Human latency

- **Park-and-continue:** a blocked task parks; the loop continues other runnable work — a
  human answer is never on the critical path of unrelated tasks.
- **Batch ratifications** at phase close: machinery proposals, consequential plan revisions,
  and efficiency tunings queue and are ratified in one sitting; push notification on
  queue-append.
- An `assisted` autonomy level = a merge *queue* (work continues on task branches), not
  stop-the-world.
- Blockers carry everything needed to decide (repro, options, recommendation) so one
  round-trip resolves them.

## 7. The correctness floor (O0)

The optimizers above are only safe on top of this floor, and the research says it is the
differentiator ([landscape-and-novelty.md §2](../research/landscape-and-novelty.md)):

- **Blind adversarial validation:** fresh-context validators; the spec is the only shared
  input; implementer reasoning never crosses (self-recognition causes self-preference —
  [correctness-and-verification-evidence.md §2](../research/correctness-and-verification-evidence.md));
  held-out adversarial tests; the merge gate reproduced from a clean checkout
  (a `--require-clean` mode refuses a dirty tree).
- **Vault isolation is a six-layer stack, not a flag** (design open question #3 closed;
  [isolation-and-sandboxing.md](../research/isolation-and-sandboxing.md)): (1) sandbox
  `denyRead` on the vault path (OS-enforced for Bash + children, macOS Seatbelt / Linux
  bubblewrap); (2) Read/Edit deny rules covering the built-in file tools (absolute precedence,
  symlink-resolving) — since the sandbox covers only Bash and the built-in tools bypass it;
  (3) strict-mode flags `allowUnsandboxedCommands: false` and `failIfUnavailable: true` on
  unattended runs, without which the boundary is prompt-dependent (a Claude Code agent has
  autonomously disabled its own sandbox and bypassed path denylists `[measured]`); (4) deny
  rules and sandbox config in a scope the worker cannot write; (5) network egress control so the
  vault is unreachable with any worker credential (no SSH-agent forwarding; proxy allowlist);
  (6) per-role isolation via separate processes (subagents inherit the parent sandbox, so the
  design's headless one-shot workers are what makes divergent implementer/validator policy
  possible). Permission enforcement is harness-level, not model-level — a CLAUDE.md instruction
  not to look is not access control `[official]`. Proven by a **vault-canary read-attempt** in
  the gate self-tests: the isolation is verified by a failing read, never assumed.
- **Diverse-lens panels, all-must-pass;** consensus voting only for redundant panels
  (popularity-trap evidence,
  [correctness-and-verification-evidence.md §3](../research/correctness-and-verification-evidence.md));
  model heterogeneity across a panel where possible.
- **Mechanized risk floors:** a path-glob → minimum-profile map enforced at the merge point by
  inspecting the *actual diff paths* (a mis-tagged security task cannot be validated cheaply
  and merged silently); a machinery-paths check (task branches cannot edit the loop's own
  machinery); a held-out-test-drop check; a destructive-git blocker — all enforced by hooks,
  all fail-open, all self-tested.
- **Self-measuring verifier loop:** a committed **escapes log** (defects a panel missed —
  labeled ground truth) + **calibration canaries** (plant a known defect the panel should
  catch before trusting any "0 findings" downgrade; a miss freezes the downgrade) +
  contract-test kill-rate calibration (a weak visible oracle raises rigor, never lowers it).
- **Closure gate** vs a plan snapshot frozen at build start, a fresh-evidence rule (only
  evidence newer than the last remediation can decide), bounded remediation rounds.
- **Governed self-modification:** the loop proposes; a human ratifies machinery changes via a
  committed ratification queue (`docs/PROPOSALS.md`); headless runs cannot edit their own
  machinery (self-modifying loops can encode a bypass of their own safeguards without
  "deciding" to —
  [correctness-and-verification-evidence.md §5](../research/correctness-and-verification-evidence.md)).

## 8. The controller — closing the loop on both objectives

A periodic reflection step doubles as the cost/quality controller, optimizing the §2 objective
explicitly:

- **Inputs:** per-role token telemetry (+ effort), a $/MTok cost table per model, window
  telemetry from the budget governor, catch-rate vs the escapes log, calibration results,
  concurrency-attributed rework, the evidence roll-up.
- **Levers:** implementer/test-author starting tier, validator tier/count/lens-set,
  per-profile effort, the concurrency cap, vault replay rate, window ceilings.
- **Discipline:** one lever at a time; minimum-sample floors; model-id/effort changes reset
  samples; every downgrade needs a fresh calibration PASS; protected profiles strengthen-only;
  all tunings queue to the ratification queue with a cost/benefit estimate — never
  auto-applied.
- **Justification surface:** a committed evidence trail (`docs/EVIDENCE.md`, regenerated from
  telemetry) answers *is it catching real defects, is the cost justified, which features
  actually fire* — and drives subtraction: dormant non-insurance machinery gets flagged for
  pruning; insurance machinery (floors, calibration, closure, budget) is never dropped on
  dormancy, since there silence is the desired state.

## 9. Failure modes and mitigations

| Failure mode | Mitigation |
|---|---|
| Stuck loop burning window budget | Liveness guard: multi-signal park (git-delta authoritative; repeated-error signature; slow-grind vs predicted duration bucket); a per-task step-count cap, since per-run token cost grows ~O(n²) in agent steps `[folklore]`, so a stuck retry loop is a multi-million-token event |
| Doomed trajectory keeps spending | Abort-on-predicted-failure check inside long-running tasks (recovers 28–64% of failing-run tokens `[measured]`; agents won't self-throttle, r=0.35); observe-only until false-abort rate is proven against O0 (§5.6) |
| Budget wall mid-panel (wasted panel) | Between-task budget-governor check; degrade→pause ladder; quantile window-aware admission (§5.1, §6.2) |
| Cache thrash (the silent 10–20× event) | Frozen-prefix rules (model/effort/fast-mode/bare-tool-deny are the real busters) + prefix-edit warning hook; small CLAUDE.md; no huge-transcript resumes (§5.2) |
| Idle-session resume pre-consumes a fresh window | Treat any idle resume as a heavy admission (charges full accumulated cache context to the new window — 15M tokens for ~20k real work `[measured]`); prefer fresh session + disk resume over `--resume` (§5.2 rule 4) |
| Weak visible tests (green-but-wrong; the ~31% problem) | Held-out layer + contract-test kill-rate calibration + held-out-drop check at merge |
| Vault goes stale / gets gamed | Mandatory fresh authoring on changed surface; leakage budget; rotation; no replay on risk-floored surfaces (§5.5) |
| Vault read by the implementer | Six-layer OS-enforced isolation stack + vault-canary read-attempt in gate self-tests (§7); strict-mode flags mandatory on unattended runs |
| Pulled-forward task gets invalidated (wasted tokens) | `start-early-safe` predicate (`mayBeInvalidatedBy`); conservative default |
| Parallel burst empties the window, then stalls | Admission rule forecast (P95 quantile, includes per-pipeline cache warmup); window-phase scheduling (§6.2) |
| Router misroutes (worse than random on unfamiliar distribution) | Verified-FAIL escalation signal (not a learned scorer); >40% break-even trip-up; validate predictor features vs measured burn before flag-flip (§5.3) |
| Subpar plan (worse than no plan) | Human approval gate on the plan document ([correctness-and-verification-evidence.md §4](../research/correctness-and-verification-evidence.md)); phase-close reflection re-scopes remaining phases |
| Limits change under the harness (they did, 7+ times) | No hard-coded magnitudes; empirical ceiling calibration; §10.3 changelog discipline; re-check after 2026-07-13 promo expiry and the paused Agent-SDK regime change |
| Concurrent firings | Manual trigger + advisory run marker + operator arbitration |
| Reward hacking / stale-green | The whole §7 floor; hooks un-skippable at merge/stop points |

## 10. Appendix — Max-window facts the design depends on

### 10.1 Established

- 5-hour window anchors at first message; usage bar + reset time visible in `/usage`
  `[measured; official docs deliberately don't specify mechanics]`.
- Weekly: one overall cap + one **Sonnet-only** cap since 2025-11-24 (Opus cap removed);
  fixed per-account weekly reset `[official]`.
- One shared pool across Claude app, all Claude Code sessions, IDE, and (currently) the Agent
  SDK / headless `-p`; the operator's own interactive use drains it too `[official, re-verified
  2026-07-04]`.
- **Live utilization is machine-readable in-session:** the statusline stdin JSON exposes
  `rate_limits.five_hour/seven_day.used_percentage` + `resets_at` and `context_window.current_usage`
  cache counters `[official]` — the governor's primary source (§5.1). No dedicated quota CLI yet
  (anthropics/claude-code#13585 open); headless firings have no official quota surface.
- **1-hour cache TTL is automatic on subscription auth** (drops to 5 min on usage credits);
  subagents get 5-min TTL and start cold; forks inherit the parent cache `[official]`.
- Thinking tokens bill as output; effort is a depletion factor and a **soft** budget (overshoot
  tail), not a hard cap `[official]`.
- Extra usage at API rates via `/usage-credits`; `$2k/day` redemption cap; **opt-in-in-advance,
  no silent spillover** `[official]`.
- Session prefix floor ≈ 20–30k tokens; multipliers vs a chat baseline: agents ~4×, multi-agent
  ~15× `[official/measured]`; agent-teams ~7× `[official/measured; not re-verified 2026-07-04]`.

### 10.2 Contested — design takes the conservative branch

**Do cache reads count against subscription limits?** API-side, cache reads bill at ~10% price
and are exempt from ITPM rate limits `[official]`. Subscription-side: still officially
**unanswered**, and community telemetry now points toward **near-full window weight** — one
report attributed ~70M tokens (>99% cache) in <2h and was closed "not planned" with no answer;
the 1,310:1 single-user ratio is the other datapoint `[contested]`. Design assumption:
**cache reads are cheap but not free; a cache-busted turn is catastrophic either way** — so the
discipline in §5.2 is unconditional, and the budget governor counts cache reads at a configurable
weight (default conservative) until Anthropic documents the truth. This is the single
highest-value controlled measurement to run — the protocol and runner are built, not yet
executed (§12 open question 2).

### 10.3 Volatility log (why nothing is hard-coded)

| Date | Change |
|---|---|
| 2025-08-28 | Weekly caps introduced (overall + Opus) `[official]` |
| 2025-11-24 | Opus weekly cap removed; overall raised; Sonnet gets its own cap `[official]` |
| 2026-01 | Unannounced Opus tightening reported `[measured]` |
| ~2026-03 | Peak-hour throttling; client cache bug (10–20× inflation) `[measured]` |
| 2026-04-23 | Cache bug fixed + limit resets `[measured]` |
| 2026-05-06 | 5-hour limits doubled; peak throttling removed `[official]` |
| 2026-05-13 → **2026-07-13** | +50% weekly promo — **current headroom is inflated; recalibrate ceilings after expiry** `[measured]` |
| 2026-06-15 announced → **PAUSED** | Agent SDK / `claude -p` / third-party usage would move **off** the rate windows onto a monthly dollar credit (Pro $20 / Max 5x $100 / Max 20x $200; interactive terminal/IDE carved out). Currently paused — all usage still draws the windows. **If un-paused, headless firings stop draining windows and O1 becomes dollar-budget management** — abstract "which pool does this spend drain" now `[official, re-verified 2026-07-04]` |

## 11. Rollout — staged, measured flips

Cheapest proven lever first; each flip gated on the previous stage's telemetry.

- **Stage 0 (day one):** frozen-prefix cache discipline + prefix-edit warning hook; budget
  governor reading the statusline `rate_limits` feed, thresholds **observe-only** (log crossings,
  don't act — untuned hard caps stall the loop `[folklore]`), serial execution; per-profile
  starting-tier override; the vault-isolation strict-mode flags on every unattended firing;
  pipelining + pre-decompose; step-count caps; structured outputs on all worker returns;
  `DISABLE_NON_ESSENTIAL_MODEL_CALLS` on headless firings.
- **Stage 1 (after the minimum task sample):** flip governor thresholds from observe-only to
  enforcing; per-profile effort via the Workflow spawn path, effort recorded in the run-log; the
  duration predictor, gated on (a) the simple starting-tier lever showing escapes ~0 and $/task
  down **and** (b) its features validated against measured burn; intra-task early-abort in
  observe-only; cross-phase DAG scheduling behind a conservative `start-early-safe` predicate.
- **Stage 2 (needs Stage-1 evidence):** held-out vault + safe-RTS replay (non-floored surfaces
  first, replay rate-limited); intra-task early-abort enforcing once the false-abort rate is
  proven against O0; concurrency cap 2 under the admission rule (including per-pipeline cache
  warmup in the cost side), with the run-log attributing rework to concurrency.
- **Stage 3 (optional, evidence-gated):** the full bucket×profile starting-tier matrix;
  test-execution caching (bounded to non-security surfaces, mandatory cache-defeat on the
  changed surface — explicitly down-weighted by the objective).
- **Standing:** recalibrate window ceilings after 2026-07-13 (promo expiry), re-check the paused
  Agent-SDK regime change (§10.3), and after any entry lands in §10.3.

## 12. Open questions

1. **Dedicated quota CLI** (anthropics/claude-code#13585, still open): the statusline
   `rate_limits` feed now covers in-session utilization (§5.1), but headless `-p` firings still
   have no official surface — they fall back to the unstable OAuth-usage endpoint or the
   optimistic local estimate until a headless-capable API ships.
2. **Cache-read quota weight** (§10.2) — *the highest-value experiment*: a matched-content
   cache-preserving vs cache-busting protocol is written and ready
   ([tools/budget-governor/cache-read-quota-weight-experiment.md](../../tools/budget-governor/cache-read-quota-weight-experiment.md)),
   with a working runner script, but **deliberately not yet executed** — it spends real Max-plan
   quota, so the operator decides when to run it (ideally right after a window reset).
3. **Per-agent effort portability:** re-probed on Claude Code 2.1.45 (2026-07-04) — dispatch of
   both axes is reconfirmed, but the probe also found the primitive does **not** reliably reject
   invalid `(model, effort)` ids (see §5.3 correction and
   [tools/budget-governor/probe-spawn-portability-2026-07-04.md](../../tools/budget-governor/probe-spawn-portability-2026-07-04.md)).
   Remaining open: whether this holds on other builds/environments the harness might run on —
   the parallel-`Agent`-calls fallback stays the default until re-probed there; re-run
   `tools/budget-governor/probe-spawn-portability.js` on any new build before trusting it.
4. **Window-occupancy forecasting:** the admission rule needs a per-task burn forecast; measured
   spend varies up to 30× same-task and models can't self-predict it (§5.1), so start with
   P95-quantile profile×tier estimates and only upgrade to duration buckets once the predictor's
   features are validated against measured burn. The predictor, its calibration gate, and the
   estimate table are built and self-tested (not yet fed real telemetry, since no tasks have run
   through the loop): [tools/budget-governor/](../../tools/budget-governor/) — see its README for
   how the two forecasts (admission vs tier-routing) share one bootstrap loop.
5. **Headless quota regime:** track whether the paused Agent-SDK change (§10.3) un-pauses; if it
   does, the governor's accounting swaps from window bin-packing to a monthly dollar budget for
   headless firings, so the "which pool does this spend drain" abstraction must already exist.

*Resolved since the founding draft:* **vault sandbox enforcement** (was open question #3) — the
six-layer OS-enforced isolation stack, proven by a vault-canary read-attempt in the gate
self-tests (§7; [isolation-and-sandboxing.md](../research/isolation-and-sandboxing.md)).
