# Dual-objective agent harness on Claude Code — technical design

> **Goal.** An agent harness that takes a thorough technical design spec and drives it to a
> *correctly implemented* codebase while explicitly optimizing two objectives: **(1) minimal
> token spend measured against the Claude Code Max plan's 5-hour and weekly rate windows**, and
> **(2) minimal wall-clock time to correct completion** — subject to a correctness floor that is
> never traded. The governing design principle: **bind every mechanism to a built-in Claude Code
> primitive first**; custom machinery is only the residue no built-in covers.
>
> Compiled 2026-07-03 from: the state-of-the-art survey
> ([agent-harness-state-of-the-art.md](../research/agent-harness-state-of-the-art.md)), the
> re-validation/scheduling prior-art digest
> ([revalidation-and-scheduling-prior-art.md](../research/revalidation-and-scheduling-prior-art.md)),
> the four pending META proposals of 2026-07-03/04 (`cc-agentloop-template/docs/META_PROPOSALS.md`),
> a fresh official-docs inventory of Claude Code built-ins, and fresh web research on Max-plan
> window mechanics (both 2026-07-03). Facts carry confidence tags: `[official]` Anthropic docs,
> `[measured]` community measurement with data, `[contested]` conflicting evidence,
> `[folklore]` practitioner consensus.

---

## 1. Scope and lineage

This is the consolidation design for the **next iteration of cc-agentloop-template**: the v1
plan/execute/reflect loop (blind validation, durable ledgers, governed self-modification —
independently assessed as ahead of the field on its verifier-calibration and governance layer,
survey §2) **plus** an explicit dual-objective optimization layer. It absorbs, as one coherent
system, the four proposals currently queued for ratification:

1. the explicit lexicographic **objective** (2026-07-04),
2. **global cross-phase DAG scheduling** (2026-07-04),
3. the **held-out test vault + safe incremental re-validation** (2026-07-04),
4. **per-profile effort at spawn** / effort as a cost lever (2026-07-03).

**Non-goals.** Portability off Claude Code (accepted coupling; see
`cc-agentloop-template/docs/PORTABILITY.md`). Multi-operator teams. Large brownfield codebases (the
phased-ledger model is greenfield-shaped, survey §7). Auto-scheduled firings (reintroduces the
concurrent-firing liveness problem v1 already solved by going manual).

## 2. The objective function

Lexicographic — never scalarized into one weighted score:

- **O0 — correctness floor (hard constraint).** Validation escapes ≈ 0, enforced by machinery,
  not model virtue. This is not over-engineering: evaluator-patching and hardcoded-pass reward
  hacking are measured behaviors (METR o3, DebugML's 28+ instances), ~31% of SWE-bench-Verified
  passes ride on tests too weak to catch a wrong fix, and a false "done" is the RLHF-default
  completion shape (survey §4a). **O0 is never traded for tokens or time.**
- **O1 — token spend against the Max windows.** The budget is not $/task; it is two rolling
  allowances — the 5-hour window and the weekly caps — shared account-wide. Consequences:
  - Spend that lands in a fresh window is *operationally cheaper* than spend near a wall:
    hitting the wall mid-panel wastes the whole in-flight panel.
  - The weekly cap makes *total build tokens* matter, not just burst rate: eliminating redundant
    re-reasoning (re-validation reuse §5.5, cache discipline §5.2) buys more build per week.
- **O2 — wall-clock to correct completion.** Includes human latency (ratification round-trips,
  parked-blocker waits), not just compute time.

Two rules from the objective proposal are load-bearing enough to restate:

- **Parallel lens breadth is not a wall-clock cost.** N diverse validator lenses run
  concurrently ≈ the slowest lens. Panel breadth is governed by O0 (risk) and O1 (tokens),
  and is **never** shrunk to save wall-clock.
- Controllers may economize on **token redundancy** (re-authoring, re-reasoning, prefix
  re-reads) and on **serialization idle** (empty concurrency slots). They may not economize on
  rigor where O0 applies (`protectedProfiles`, risk floors: strengthen-only).

**The one real O1↔O2 exchange:** concurrent task pipelines. All parallel sessions and subagents
drain **one shared account pool** `[official]` — parallelism buys wall-clock only, never budget.
And at equal token budget, single-agent beats multi-agent on quality (arXiv 2604.02460
`[measured]`) — so parallelism is purchased *only* out of window headroom (§6.2), never assumed
free.

## 3. Design principles

1. **Built-in before custom** (§4 is the map). If Claude Code ships it — subagents, worktrees,
   hooks, skills, caching, structured output, telemetry — the harness configures it rather than
   rebuilding it. Custom shell scripts are the residue, and each must justify itself in
   `cc-agentloop-template/docs/EVIDENCE.md` or be pruned.
2. **Zero-token enforcement.** Everything safety- or budget-load-bearing runs as a **hook or
   script** — deterministic, model-free, un-skippable, costs no context. Prose guards burn
   tokens every turn *and* get skipped exactly when the loop is degraded (survey §6.1). Command
   hooks cost 0 tokens; prompt/agent hooks cost tokens and are reserved for rare gates
   `[official]`.
3. **Context isolation is also compression.** Subagents exist for correctness (blind
   validation) *and* economy: a worker's exploration tokens die with its context; only the
   structured return crosses to the orchestrator. This is the token-efficient fan-out pattern
   Anthropic itself uses (multi-agent research system `[official]`).
4. **Disk is the memory.** Ledgers, STATUS, run-log, lessons live on disk; any context can die
   at any moment and the loop resumes from files alone. This makes fresh-context workers (and
   orchestrator compaction) free in *correctness* terms, so the token optimizer can use them
   aggressively.
5. **Measure, then move.** Every economy lever ships with its telemetry and a ground-truth
   check (escapes denominator, calibration canaries). No downgrade without a catch-proof; one
   lever at a time; sample floors respected. Limits themselves are volatile (§10.3) — ceilings
   are calibrated empirically, never hard-coded.

## 4. Leverage map — need → Claude Code built-in → custom residue

| Need | Built-in (how) | Residue we still build |
|---|---|---|
| Isolated worker contexts | **Subagents** (`.claude/agents/*.md`; per-agent `model`, `tools`; summary-only return) `[official]` | Spec-only shared-input discipline; verdict/handoff schemas |
| Parallel file edits, zero conflicts | **Git worktrees** (`claude --worktree`, subagent `isolation: worktree`, `.worktreeinclude`, auto-cleanup) `[official]` | Per-task naming + lifecycle policy (`scripts/worktree.sh`) |
| Un-skippable enforcement, 0 tokens | **Hooks** (PreToolUse / PostToolUse / Stop / SubagentStop / SessionStart; deny>ask>allow; matchers) `[official]` | The specific gate scripts hooks invoke (`gate.sh --check-*`) |
| Reusable procedures, cheap until used | **Skills** with progressive disclosure (names at start, body on invoke) `[official]` | Skill content (`/plan`, `/routine`, `/calibrate`, …) |
| Interactive planning w/o edits | **Plan mode** `[official]` | The plan template, risk-classification table, human gate |
| Completion gating | **Stop hooks** (script-based; `/goal`-style model-evaluated) `[official]` | Closure gate vs frozen snapshot + fresh-evidence rule |
| Structured worker returns | **`--json-schema` / structured outputs** (server-side validation) `[official]` | The verdict/AAR schemas themselves |
| Model routing | Per-subagent `model` param; session `/model`; aliases `[official]` | Tier indirection (`modelTiers`) + routing policy (`taskRouting`) |
| Effort routing | Session `/effort`; per-agent `effort` on the Workflow/Agent spawn path (probe-verified 2026-07-03) | Per-profile effort config + the spawn-path fallback ladder |
| Cost/usage telemetry | `/usage`, `/context`, `--output-format json` (`total_cost_usd`, per-model usage), OTEL enhanced telemetry, per-subagent token totals `[official]` | Run-log aggregation (`tokens_by_role`), `budget.sh` windows |
| Prompt-cache economy | **Automatic prompt caching** (5-min TTL; 1h TTL via env; auto breakpoints in CC/SDK) `[official]` | The *discipline* (§5.2): freeze-prefix rules, boundary edits |
| Tool-definition economy | **ToolSearch deferred loading** (names only at start; schema on use — default for MCP) `[official]` | Keep the MCP surface minimal; prefer CLI tools (`gh`) over MCP servers `[official]` |
| Long-lived instructions | CLAUDE.md (<200 lines guidance), path-scoped rules, `@imports`, auto-memory `[official]` | Lessons corpus + orchestrator-curated injection |
| Resume across deaths | Session persistence, `--resume`/`--continue`/`--fork-session` `[official]` | Ledgers/STATUS as the *canonical* resume state (disk > transcript — resuming a huge transcript reprocesses it at full cost `[measured]`) |
| Undo | `/rewind` checkpoints (session-local) `[official]` | Git remains canonical history; checkpoints are convenience only |
| Headless execution | `claude -p`, `--allowedTools`, `stream-json`, `--bare` `[official]` | The Routine (rendered skill) + advisory run marker |
| Background work | Background bash, background subagents, batched parallel tool calls `[official]` | Fan-out patterns (§6.1) |
| Output filtering | PostToolUse hooks pre-filtering tool output (10k-line log → the failures) `[official example]` | Which filters to apply per gate command |

**Deliberately not used:** auto-cron firing of the Routine (concurrent-firing liveness is
unsolvable from a tool-call shell — v1 decision stands); agent teams for implementation
(≈7× a standard session `[official]`, and Anthropic's own caveat: coding has few truly
parallelizable interdependent tasks `[official]` — the parallel-friendly part of this loop is
validation, which subagent fan-out already covers); `ANTHROPIC_API_KEY` in the environment
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
- No token quotas are published, and magnitudes changed ≥6 times in 12 months (§10.3) —
  **ceilings must be runtime-calibrated, never hard-coded**.

Governor (extends v1 `budget`): `scripts/budget.sh` computes window occupancy from the source
ladder — `estimate` (run-log rolling sums; the only unattended-capable source today) →
`quota-file` (operator-fed from `/usage`) → `quota-cmd`/OTEL when a programmatic quota API
ships (anthropics/claude-code#13585). Two thresholds, checked **between** tasks ("don't start
what you can't finish"):

- `degradeAtFraction` (0.8): panels shrink to profile minimums (never below a risk floor), no
  new tasks start, in-flight work commits.
- `pauseAtFraction` (0.95): clean pause — resume marker to STATUS, worktrees reconciled,
  marker released. The next firing after the window reset resumes from disk.

New in this design — **window-aware admission** (the scheduler input, §6.2): each candidate
task carries a cost forecast (its profile's panel size × tier + implementer tier; later the
`predict-duration` bucket). A heavy `critical`-profile task is admitted early in a fresh
window; near a wall only cheap `routine` tasks (or nothing) start. Escape valve: extra-usage
credits at API rates exist (`/usage-credits`, $2k/day cap `[official]`) — surfaced to the
operator as a *choice* at pause time, never auto-purchased.

### 5.2 Prompt-cache discipline (the #1 hidden lever)

Measured reality: a session carries a 20–30k-token prefix (system prompt + CLAUDE.md + memory
+ tool names) re-sent every turn `[measured]`; over 30 days of real use, cache-read volume ran
**1,310× fresh I/O tokens** and scaled with CLAUDE.md size, not workload `[measured]`. Whether
cache reads count against *subscription* limits at a discount or near-full weight is
**`[contested]`** (§10.2) — under either reading, the design conclusion is identical:
**cache-busting is the catastrophic spend event** (the v2.1.76 cache-bug era produced 10–20×
inflation `[measured]`), and the prefix must be small and immutable.

Rules (mechanized where possible):

1. **Frozen prefix per firing.** CLAUDE.md, CONSTRAINTS.md, hook set, MCP server set, model,
   and skill inventory do not change mid-firing — edits batch at clean-stop/boundary. Residue
   mechanization: a PreToolUse hook warns on mid-firing edits to prefix files (`Edit|Write`
   matcher on CLAUDE.md/CONSTRAINTS.md/settings).
2. **Small prefix.** CLAUDE.md stays under ~200 lines `[official guidance]`; reference material
   lives in skills (progressive disclosure) and path-scoped rules; lessons are injected
   per-spawn by the orchestrator, not resident in the prefix.
3. **TTL cadence.** The default cache TTL is 5 minutes `[official]`. The Routine's inner loop
   naturally turns over faster than that while working; a *planned* long gap (awaiting a human)
   is one cache miss, accepted. Long-idle sessions are ended cleanly rather than kept warm
   artificially. (`ENABLE_PROMPT_CACHING_1H` exists if measurement shows idle-gap misses
   matter `[official]`.)
4. **Never resume a huge transcript for a new task.** Fresh session + disk state beats
   `--resume` of a long history (full reprocess) `[measured]`. Ledgers are the resume state.
5. **Workers are short-lived by construction.** Implementers/validators are subagents (or
   headless `-p` one-shots): they pay their prefix once, do one task, die. No compaction debt
   accumulates anywhere except the orchestrator, whose context is structured-state-only.

### 5.3 Model + effort routing (two axes, start low, escalate on proof)

Unchanged v1 spine, now with both cost axes live:

- **Tier axis** (`taskRouting`, staged P1→P3): start the implementer as cheap as risk allows
  (`startTier` per profile; predictor + bucket matrix behind the measured
  `predictDuration` flag), let the escalation ladder walk it up on durable FAIL. Guardrails
  stand: `protectedNeverStartCheap` (safety is not a cost lever), `recencyOverride` (cheap
  tiers are a knowledge generation behind — nature beats difficulty), escalation-churn
  break-even (~40% failure rate flips the economics; the retro trips the start tier back up).
- **Effort axis** (META 2026-07-03): profiles already carry `effort`; the Workflow-based spawn
  path threads `profile.effort` per agent (probe-verified), with parallel `Agent`-call batches
  as the portable fallback (model-only). Effort joins the run-log (`tokens_by_role[].effort`)
  so the controller can segment cost/catch-rate by `(tier, model_id, effort)`. Downgrades
  require a fresh calibration PASS at the lower effort; protected profiles: raise-only.
- **Routing floor for grunt work:** mechanical fan-out (file moves, renames, log filtering,
  status sweeps) always runs `cheap` subagents — up to ~75% cost cut from deliberate routing
  is the practitioner consensus `[measured]`, and the gate catches any miss.
- **Weekly-pool awareness (new):** with the model-specific weekly cap now on **Sonnet** rather
  than Opus `[official]`, "route grunt work down-tier" is no longer automatically
  weekly-budget-safer. The controller tracks which pool each tier drains and re-checks the
  mapping after every Anthropic limit change (§10.3).

### 5.4 Context hygiene

- Orchestrator ingests **structured state only** (statuses, verdicts, decisions) — never raw
  file dumps; heavy reading is delegated and dies with the subagent.
- Workers receive **scoped specs** (the task's ledger entry + injected lessons), not the whole
  plan; specific file paths, not pasted file contents `[official guidance]`.
- MCP surface minimal; ToolSearch deferral on (default); prefer CLI tools over MCP servers
  `[official]`; `.claudeignore` tuned (measured up to ~85% context reduction `[measured]`).
- Compaction is a survivable event, not a stop (v1 rule) — but the *economical* pattern is to
  make it rare by keeping the orchestrator lean, and to prefer clean session boundaries
  (`/clear`-equivalent + disk resume) over repeated `/compact` (compaction is itself a model
  call over the history `[official]`).

### 5.5 Re-validation reuse — the vault (biggest O1 lever on retries)

Adopted from META 2026-07-04 (prior-art digest is the evidence base). On a durable-FAIL
re-validation today, the panel re-authors held-out tests and re-reviews a ~95%-unchanged diff —
pure token redundancy. Design:

1. **Implementer-blind held-out vault.** Panel-authored held-out tests persist where the
   implementer's context/worktree can never see them; isolation sandbox-enforced (hidden tests
   have been exfiltrated from autograders via submitted code — digest §5), proven by a hook,
   not by path convention.
2. **Safe incremental re-validation.** On re-validation, **replay** the vault against the
   unchanged surface (zero re-authoring tokens) under the Ekstazi/TIA **safe-RTS property** —
   never skip a test the change could affect; full-run fallback for anything unanalyzable
   (digest §2).
3. **Fresh authoring on the changed surface is mandatory.** A replayed corpus is a regression
   floor, structurally unable to find a new hole (frozen corpus = saturated corpus; ~27% of
   real faults uncoupled from standard mutants — digest §4). The vault shrinks re-authoring;
   it never eliminates it.
4. **Leakage budget.** Reuse of a fixed hidden set across adaptive fix-iterations degrades it
   (Ladder/Thresholdout, digest §6): rate-limit replays, rotate/refresh the corpus, and keep
   **full fresh re-derivation on risk-floored surfaces** — exactly where a gamed frozen set is
   most dangerous.

### 5.6 What the harness deliberately does not spend on

- No auto-cron; no idle-warm sessions; no speculative implementation of provisional ledgers
  (look-ahead is planning-only).
- No free-running reflection: reflection triggers on ground-truth events (an escape, a canary
  miss, a durable FAIL), never as open-ended synthesis (intrinsic self-correction *degrades*
  without external signal — survey §4b).
- Dormant opt-in controllers are pruned on evidence (`prune-advisor`); insurance controllers
  (risk floors, calibration, closure, budget) are exempt — there, silence is the desired state.
- `DISABLE_NON_ESSENTIAL_MODEL_CALLS=1` on headless firings `[official]`.

## 6. The wall-clock layer (O2)

### 6.1 Token-free accelerators first

These cut elapsed time without buying tokens; they are always on:

1. **Pipelining** (v1 `lookahead`): task N+1's spec + contract tests are authored while task N
   validates; the next phase pre-decomposes (provisional, planning-only) while the current
   phase's last task runs.
2. **Global cross-phase DAG scheduling** (META 2026-07-04): each tick, candidates = every
   not-started task whose hard deps are complete, **any phase**; fill idle slots prioritized by
   critical-path, then risk; gated by the `start-early-safe` predicate (`mayBeInvalidatedBy`
   soft edges) so pulled-forward work is never likely rework — wall-clock bought without
   wasted-token risk. Phase tags stay for human legibility; `doctor.sh`'s DAG check goes
   cross-phase.
3. **Panels are always batched-parallel.** One turn, N `Agent` calls (or one Workflow
   `parallel()`): wall-clock ≈ slowest lens. This is why lens breadth is O0/O1-governed only.
4. **Hooks over prose.** Every deterministic check that would otherwise be an orchestrator
   turn (merge gating, git-state checks, output filtering) runs as a hook — zero tokens *and*
   zero turn latency.
5. **Structured outputs everywhere** (`--json-schema` / schema-forced subagent returns):
   eliminates parse-repair round-trips `[official]`.

### 6.2 Paid parallelism — admission-controlled by window headroom

`maxConcurrentTasks > 1` (worktree-isolated implement→validate pipelines) is the one lever
that spends tokens to buy time. Admission rule, evaluated per tick:

> Admit a second/third concurrent pipeline **only if** (a) window occupancy is below the
> degrade threshold *and forecast to stay below it with the added burn*, (b) the runnable set
> contains genuinely independent tasks (hard deps + `mayBeInvalidatedBy` clear), and (c) the
> surface-contention cap (`maxConcurrentSurfaces`) is respected.

Rationale: bursting a fresh 5-hour window empty in <1h then stalling 4h is a *wall-clock loss*,
not a win — on subscriptions the binding constraint is often the window, not total tokens
`[folklore, consistent]`. Practitioner consensus caps useful concurrency at 2–4 pipelines
`[folklore]`; the run-log attributes rework/merge-conflict cost to concurrency so the retro can
tune the cap on evidence. Anthropic's own frontier datapoint — up to 90% time reduction at
~15× tokens for research fan-out `[official]` — is the reminder that the exchange rate is
steep: this harness buys parallelism for *validation* (independent lenses, cheap wall-clock)
structurally, and for *implementation* only under the admission rule.

**Window-phase scheduling:** heavy fan-out (big panels, multi-task bursts) schedules right
after a window reset; the tail of a window runs cheap serial work. The 5-hour anchor-at-first-
message behavior `[measured]` even allows deliberate window alignment to the operator's day
(the "warmup" pattern `[folklore]` — surfaced as an operator note, not automated).

### 6.3 Human latency

- **Park-and-continue** (v1 stance): a blocked task parks; the loop continues other runnable
  work — a human answer is never on the critical path of unrelated tasks.
- **Batch ratifications** at phase close: META proposals, consequential plan revisions, and
  efficiency tunings queue and are ratified in one sitting; push notification on queue-append.
- `assisted` autonomy = a merge *queue* (work continues on task branches), not stop-the-world.
- Blockers carry everything needed to decide (`repro`, options, recommendation) so one
  round-trip resolves them.

## 7. The correctness floor (O0) — retained v1 machinery

Unchanged, because the research says it is the differentiator (survey §2) and the optimizers
above are only safe on top of it:

- **Blind adversarial validation:** fresh-context validators; the spec is the only shared
  input; implementer reasoning never crosses (self-recognition causes self-preference —
  survey §4b); held-out tests; clean-checkout gate (`gate.sh --require-clean`).
- **Diverse-lens panels, all-must-pass;** `consensus` voting only for redundant panels
  (popularity-trap evidence, survey §4c); model heterogeneity across a panel where possible.
- **Mechanized risk floors** (`--check-riskfloor` on actual diff paths), machinery gate
  (`--check-machinery`), held-out-drop check, denylist, `block-dangerous-git` — all enforced
  by hooks at the merge point, all fail-open, all self-tested.
- **Self-measuring verifier loop:** `escapes.jsonl` ground truth + `/calibrate` canaries
  (freeze downgrades on a miss) + contract-test kill-rate calibration (weak visible oracle →
  raise rigor, never lower).
- **Closure gate** vs the frozen plan snapshot, fresh-evidence rule, bounded remediation.
- **Governed self-modification:** the loop proposes; a human ratifies machinery changes
  (META_PROPOSALS); headless runs cannot edit their own machinery (Gödel-agent threat model,
  survey §4e).

## 8. The controller — closing the loop on both objectives

The `efficiency` retro dimension remains the cost/quality controller, now optimizing the §2
objective explicitly:

- **Inputs:** `tokens_by_role` (+ `effort`), `modelCosts`, window telemetry from `budget.sh`,
  catch-rate vs `escapes.jsonl`, calibration results, concurrency-attributed rework, evidence
  roll-up.
- **Levers:** implementer/testAuthor start-tier, validator tier/count/lens-set, per-profile
  effort, `maxConcurrentTasks`, vault replay rate, window ceilings.
- **Discipline:** one lever at a time; `minSampleTasks` floors; model-id/effort changes reset
  samples; every downgrade needs a fresh calibration PASS; protected profiles strengthen-only;
  all tunings queue to META_PROPOSALS with a cost/benefit estimate — never auto-applied.
- **Justification surface:** `cc-agentloop-template/docs/EVIDENCE.md` (value / cost / features-fired)
  proves the harness earns its spend; `prune-advisor` retires dormant non-insurance machinery.

## 9. Failure modes and mitigations

| Failure mode | Mitigation |
|---|---|
| Stuck loop burning window budget | `liveness.sh` multi-signal park (git-delta authoritative; slow-grind vs predicted bucket) |
| Budget wall mid-panel (wasted panel) | Between-task `budget.sh` check; degrade→pause ladder; window-aware admission (§5.1, §6.2) |
| Cache thrash (the silent 10–20× event) | Frozen-prefix rules + prefix-edit warning hook; small CLAUDE.md; no huge-transcript resumes (§5.2) |
| Weak visible tests (green-but-wrong; the ~31% problem) | Held-out layer + contract-test kill-rate calibration + `check-heldout` at merge |
| Vault goes stale / gets gamed | Mandatory fresh authoring on changed surface; leakage budget; rotation; no replay on risk-floored surfaces (§5.5) |
| Pulled-forward task gets invalidated (wasted tokens) | `start-early-safe` predicate (`mayBeInvalidatedBy`); conservative default |
| Parallel burst empties the window, then stalls | Admission rule forecast; window-phase scheduling (§6.2) |
| Subpar plan (worse than no plan — survey §4d) | Human approval gate on TECHNICAL_PLAN.md; phase-close retro re-scopes remaining phases |
| Limits change under the harness (they did, 6+ times) | No hard-coded magnitudes; empirical ceiling calibration; §10.3 changelog discipline; re-check after 2026-07-13 promo expiry |
| Concurrent firings | Manual trigger + advisory marker + operator arbitration (v1 decision, retained) |
| Reward hacking / stale-green | The whole §7 floor; hooks un-skippable at merge/stop points |

## 10. Appendix — Max-window facts the design depends on

### 10.1 Established

- 5-hour window anchors at first message; usage bar + reset time visible in `/usage`
  `[measured; official docs deliberately don't specify mechanics]`.
- Weekly: one overall cap + one **Sonnet-only** cap since 2025-11-24 (Opus cap removed);
  fixed per-account weekly reset `[official]`.
- One shared pool across Claude app, all sessions, all subagents; subagent/skill/MCP usage is
  attributed in `/usage` `[official]`.
- Thinking tokens bill as output; effort level is an official depletion factor `[official]`.
- Extra usage at API rates via `/usage-credits`; `$2k/day` redemption cap `[official]`.
- Session prefix floor ≈ 20–30k tokens; multipliers: agents ~4× chat, multi-agent ~15×,
  agent teams ~7× `[official/measured]`.

### 10.2 Contested — design takes the conservative branch

**Do cache reads count against subscription limits?** API-side, cache reads are ~10% price and
exempt from ITPM `[official]`. Subscription-side: issue #24147 measured 1,310:1 cache-read:I/O
and argues near-full quota weight; other sources assume the ~10% discount `[contested]`.
Design assumption: **cache reads are cheap but not free; a cache-busted turn is catastrophic
either way** — so the discipline in §5.2 is unconditional, and `budget.sh`'s estimate mode
counts cache reads at a configurable weight (default conservative) until Anthropic documents
the truth.

### 10.3 Volatility log (why nothing is hard-coded)

| Date | Change |
|---|---|
| 2025-08-28 | Weekly caps introduced (overall + Opus) `[official]` |
| 2025-11-24 | Opus weekly cap removed; overall raised; Sonnet gets its own cap `[official]` |
| 2026-01 | Unannounced Opus tightening reported `[measured]` |
| ~2026-03 | Peak-hour throttling; v2.1.76 cache bug (10–20× inflation) `[measured]` |
| 2026-04-23 | Cache bug fixed + limit resets `[measured]` |
| 2026-05-06 | 5-hour limits doubled; peak throttling removed `[official]` |
| 2026-05-13 → **2026-07-13** | +50% weekly promo — **current headroom is inflated; recalibrate ceilings after expiry** `[measured]` |

## 11. Rollout — staged, measured flips

Mirrors the v1 `taskRouting` discipline: cheapest proven lever first, each flip gated on the
previous stage's telemetry.

- **Stage 0 (day one, no new machinery):** frozen-prefix cache discipline + prefix-edit
  warning hook; window-aware admission in its degenerate form (`budget.sh` estimate mode,
  serial execution); start-tier P1; pipelining + pre-decompose; structured outputs on all
  worker returns; `DISABLE_NON_ESSENTIAL_MODEL_CALLS` on headless firings.
- **Stage 1 (after `minSampleTasks` of telemetry):** per-profile effort via the Workflow spawn
  path (Part A), effort in the run-log (Part B); duration predictor (`predictDuration: true`)
  if P1 shows escapes ~0 and $/task down; cross-phase DAG scheduling behind a conservative
  `start-early-safe` predicate.
- **Stage 2 (needs Stage-1 evidence):** held-out vault + safe-RTS replay (non-floored surfaces
  first, replay rate-limited); `maxConcurrentTasks: 2` under the admission rule, run-log
  attributing rework to concurrency.
- **Stage 3 (optional, evidence-gated):** startTier matrix (P3); test-execution caching
  (bounded to non-security surfaces, mandatory cache-defeat on changed surface — explicitly
  down-weighted by the objective); `ENABLE_PROMPT_CACHING_1H` if idle-gap misses measurably
  matter.
- **Standing:** recalibrate window ceilings after 2026-07-13 (promo expiry) and after any
  entry lands in §10.3.

## 12. Open questions

1. **Programmatic quota API** (anthropics/claude-code#13585): until it ships, unattended runs
   budget on the token-proxy estimate; the source ladder upgrades in place when it lands.
2. **Cache-read quota weight** (§10.2): worth a controlled measurement (one firing with
   deliberate cache-busting vs one without, same work, compare `/usage` movement) before
   tuning `budget.sh`'s cache-read weight away from conservative.
3. **Vault sandbox enforcement:** the concrete mechanism proving the implementer *cannot* read
   the vault (separate repo + credential? OS-level sandbox rule? hook-verified path audit?) —
   design decision deferred to the vault proposal's ratification.
4. **Per-agent effort portability:** the Workflow spawn path is probe-verified on this build;
   the Agent-call fallback ladder must stay the default until the primitive is verified on the
   target environment (PORTABILITY.md note).
5. **Window-occupancy forecasting:** the admission rule needs a per-task burn forecast; start
   with profile×tier static estimates, upgrade to `predict-duration` buckets once P2 is live.
