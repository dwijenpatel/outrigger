# Terminology

> **v1-era glossary, preserved as history.** These terms are the vocabulary of the **v1 (attic)
> design** and the internal evidence that still references it. The reincarnated project's design
> authority is [design/evidence-based-harness.md](design/evidence-based-harness.md); the attic is
> *never a source of current defaults* ([attic/README.md](attic/README.md)).

Every acronym, coined term, and piece of jargon used across this repo's design, plan, research
corpus, skills, and tooling — defined as *this project* uses it, with a pointer to where it is
canonically defined.

Companion pages: [reference.md](attic/reference.md) is the API/shape reference (what to *call*); this
page is the vocabulary (what things *mean*). For a conflict over what a **v1** term means, the
v1 design doc ([attic/token-time-optimized-harness.md](attic/token-time-optimized-harness.md))
is the authority for that vocabulary; the current design's authority is
[evidence-based-harness.md](design/evidence-based-harness.md).

**Reading the source column:** `§N` refers to a numbered section of the design doc.
`plan` = [plan/implementation-plan.md](attic/plan/implementation-plan.md).
`research/<name>` = a document in [research/](research/README.md).

---

## Quick reference — the twelve terms everything else assumes

| Term | One line |
|---|---|
| **O0 / O1 / O2** | The three objectives, in strict priority order: correctness floor, then token spend, then wall-clock. |
| **lexicographic** | O0 is satisfied *before* O1 is considered, and so on — never merged into one weighted score. |
| **firing** | One operator-started run of the build loop against a ratified plan. |
| **the vault** | The out-of-repo store of held-out tests the implementer is structurally unable to read. |
| **blind adversarial validation** | Validators judge the diff in fresh context, sharing only the spec — never the implementer's reasoning. |
| **merge gate** | The clean-checkout, all-must-pass checkpoint. Nothing merges on a model's say-so. |
| **budget governor** | The deterministic script that reads window occupancy and decides whether work may start. |
| **window** | A Max-plan rate allowance (5-hour and weekly), shared account-wide — the unit O1 is denominated in. |
| **disk is the memory** | All state lives on disk; any context may die at any moment and the loop resumes from files. |
| **hooks over prose** | Anything safety- or budget-load-bearing runs as a deterministic hook, not an instruction. |
| **claims, not evidence** | No status, verdict, or resume decision is ever made from a model's own summary. |
| **profile** | A task's risk level (`routine < elevated < high < critical`) — sets panel size, tier, and effort. |

---

## Naming conventions

These are patterns, not individual terms. Learn the pattern and every instance reads itself.

| Pattern | Meaning | Example |
|---|---|---|
| `§N` / `§N.M` | A numbered section of the design doc. | §5.2 = prompt-cache discipline |
| **Phase A–I** | Dependency-ordered groups of increments in the implementation plan. A = Stage-0 foundations, B = disk state, C = hooks, D = vault + gate, E = orchestration, F = controller, G = Stage-2 wall-clock, H = enforcement wiring, I = pilot fixes. | Phase H |
| **`<letter><digit>`** | One increment inside a phase. | `H9` = spec-ambiguity blockers |
| **`I<n>`** | A pilot-fix increment (Phase I), I1–I30 so far. A letter suffix is a follow-on correction to the same fix. | `I26`, `I4b` |
| **`P<pilot>-<seq>`** | A pilot observation, numbered in stream order. `P3v2` = pilot 3, rerun on instrument v2. | `P1-8`, `P3v2-13` |
| **`W<n>`** | A pre-registered watch item — a prediction recorded *before* it is observed, so a later observation confirms or falsifies it. | `W6` |
| **`D<n>`** | A ratified decision in a plan's decisions log. | `D17` (floors) |
| **`GL<n>`** | A ledger task id in the *greenlane* pilot product. | `GL1` |
| **Triage glyphs** | 🔴 defect · 🟡 friction · ⚪ benign · ❓ needs detail · 👁 watch item · ✅ what worked · 📊 datapoint | — |

---

## Evidence and confidence tags

Every factual claim in the research corpus carries a tag. The tags are load-bearing: a design
decision may rest on a `[measured, replicated]` claim, never on a `[hype-tier]` one.

| Tag | Meaning |
|---|---|
| `[official]` | Stated in Anthropic's own documentation. `[official, re-fetched]` = re-verified by direct fetch on a stated date. `[official, indirect]` = officially implied, not stated. |
| `[measured]` | Community or benchmark measurement with data behind it. |
| `[measured, replicated]` | Measured *and* independently reproduced by parties not sharing the original's methodology. |
| `[measured, corroborated]` | Measured, with an independent analogue supporting it, but not an exact replication. |
| `[measured, single-source]` | One party's measurement only. Direction may be trusted; magnitudes may not. |
| `[measured, local]` | Measured by this harness's own zero-quota benchmark on its own data shapes. |
| `[contested]` | Conflicting evidence. The design takes the conservative branch. `[contested, leaning negative]` where independent evidence runs against the claim. |
| `[folklore]` | Practitioner consensus, unmeasured. |
| `[E]` / `[I]` | For research-study claims: **E**stablished in the cited primary source vs. the corpus author's **I**nference or synthesis. |
| `[in-tree]` | A fact about *this repository's working tree* at a stated date and test count, not external research. |
| `[code]` / `[report]` | For studied external systems: verified in their source code vs. claimed only in their paper. `[code-as-text]` = a prompt string embedded in code. |
| `[author-benchmark, single-source]` | A performance number from the system's own authors' runs (often n=1 per cell). |
| `[first-party marketing]` / `[independent]` | A vendor's own claim vs. a fact from a party independent of it. |
| `[reported]` / `[operator-observed]` | Cited for framing only, unaudited / observed firsthand by the operator during live use. |
| **hype-tier** | Cited for framing only, never as evidence (e.g. "$297 MVP", "810x productivity"). |

**Standing rule:** single-source evidence must be independently confirmed before any design
decision leans on it. Import the *mechanism*, never the *effect size*.

---

## 1. The objective function

- **O0 — the correctness floor.** Validation escapes ≈ 0, enforced by machinery, not model
  virtue. **Never traded for tokens or time.** (§2)
- **O1 — token spend against the Max windows.** Not $/task: two rolling allowances (the 5-hour
  window and the weekly caps), shared account-wide. (§2, §5)
- **O2 — wall-clock to correct completion.** Includes *human* latency (ratification round-trips,
  parked-blocker waits), not just compute time. (§2, §6)
- **Lexicographic** — the three are ranked strictly and "never scalarized into one weighted
  score." A lower objective is pursued only without degrading a higher one. (§2)
- **The one real O1↔O2 exchange** — concurrent task pipelines. Every parallel session and
  subagent drains one shared account pool, so parallelism buys wall-clock only, never budget.
  It is purchased out of window headroom, never assumed free. (§2, §6.2)
- **Parallel lens breadth is not a wall-clock cost** — N validator lenses run concurrently ≈ the
  slowest lens, so panel breadth is governed by O0 (risk) and O1 (tokens) and is *never* shrunk
  to save wall-clock. (§2)
- **Token redundancy / serialization idle** — the two economies a controller *may* pursue
  (re-authoring, re-reasoning, prefix re-reads / empty concurrency slots). It may not economize
  on rigor where O0 applies. (§2)
- **Turn economy** — each extra turn re-sends the whole growing context, so eliminating
  follow-up calls is a first-class accelerator. "Turns, not bytes, are the budget." (§6.1)
- **Window-weighted tokens** — the true unit of O1: tokens weighted by how heavily they draw on
  the rate window. The billable unit is the **cache miss**, not the cache read.

## 2. Roles and orchestration

- **Operator** — the human. Starts and stops firings, ratifies plans, adjudicates blockers,
  supplies credentials and permission mode. Some controls (permission mode) are operator-only by
  construction.
- **Orchestrator** — the single long-lived session driving one firing. Ingests structured state
  only (statuses, verdicts, decisions), never raw file dumps. Supplies judgment where scripts
  cannot.
- **Worker** — any short-lived subagent. Pays its prefix once, does one task, dies.
- **Implementer** — implements exactly one ledger task from its scoped spec, in an isolated
  worktree. Never sees validator reasoning or held-out tests.
- **Test-author** — authors held-out adversarial tests for one task *from its spec alone*,
  before/without seeing any implementation. Output lands in the vault.
- **Validator** — blind adversarial review of one task's diff against its spec, through one
  assigned **lens**. Fresh context; the spec is the only shared input.
- **Lens** — one assigned validation viewpoint (correctness, security, spec-conformance,
  regression, repro…). "One diff, one spec, one lens."
- **Panel** — the set of validators run concurrently on a task. **All-must-pass**: one FAIL
  blocks the merge.
- **Firing** — one operator-started, operator-stopped run of the build loop. Auto-scheduled
  firings are a non-goal: a prior firing's liveness cannot be judged reliably from a tool-call
  shell, so manual triggering removes the double-run failure mode entirely. (§1)
- **Leg** — a resumed segment of one firing across a pause boundary, often on a changed
  machinery arm.
- **Tick** — one scheduler iteration / decision boundary. Governor reads and admission decisions
  happen per tick.
- **Headless one-shot worker** — the `claude -p` spawn path (I26) where every knob verifiably
  binds: per-spawn `--model`, measured-applied `--effort`, schema-forced return contract, and a
  per-worktree settings overlay. (§5.3)
- **Worker boundary / respawn boundary** — a fresh worker spawn: the only place escalation and
  cache-key changes are legal, because a cold cache is paid there anyway.
- **Escalation ladder / rung** — start cheap, escalate on *proof*. Attempt 2 = same tier at
  `max` effort with sharpened feedback; attempt 3+ = tier up. A "rung" is one step.
- **Tier** — the model-strength axis, indirected through abstract names (`cheap` / `standard` /
  `capable` / `max`) that map to concrete model ids in one config table (`tiers.json`). (§5.3)
- **Effort** — the reasoning-budget axis (`low` / `medium` / `high` / `xhigh` / `max`). A soft
  *target*, not a hard cap, so realized spend has an **overshoot tail**. Uniform `xhigh` is the
  harness default; `max` is the escalation rung.
- **Regime** — a planner-assigned task class (`chore` | `thinking` | `long_horizon`) that
  conditions routing. Chores route down freely; thinking tasks never start below `standard`.
- **Fan-out** — parallel dispatch where a worker's exploration tokens die with its context and
  only the structured return crosses. Context isolation is also *compression*. (§3)
- **Pipelining** — task N+1's spec and contract tests are authored while task N validates.
- **Pre-decompose** — the next phase decomposes into a *provisional*, planning-only ledger while
  the current phase's last task runs. Look-ahead is planning-only, never speculative
  implementation.
- **Park-and-continue** — a blocked task parks; the loop continues other runnable work. A human
  answer is never on the critical path of unrelated tasks. (§6.3)
- **Handoff** — the implementer/test-author structured return: outcome, summary, intent,
  `key_changes_made` (material outcomes, not activities), `key_learnings` (surprising only),
  `spec_ambiguities`, `files_touched`.
- **Verdict** — the validator's structured return: lens, verdict, evidence, intent, findings. A
  FAIL requires ≥1 finding, and evidence must quote *reproduced* behavior.
- **Blocker card** — the on-disk record of an operator decision: repro, ≥2 options with
  consequences, a recommendation, and `resolved{decision,by,at}`.
- **Card-first, ask-second** — the card hits disk (and the task shows `parked`) *before* any
  interactive prompt. The card **is** the question. Asking before carding was a real defect
  (P3v2-1).
- **Lessons corpus** — orchestrator-owned, workers read-only, curated injection per spawn, never
  resident in the prefix. Fed by handoff `key_learnings`.
- **Liveness guard** — the stuck-loop defense: multi-signal park (git-delta authoritative,
  repeated-error signature, slow-grind vs predicted duration), a step-count cap, a mid-flight
  token cap, and the **no-op rule**.
- **No-op rule** — a turn with zero git delta and zero new artifacts counts as a *failure*, so
  the loop halts instead of spinning.
- **Watchdog** — a per-worker wall-clock deadline (I29) that kills the process group. `--max-turns`
  never fires on a **pre-compute hang** (a quota-throttled worker that stalls before emitting
  any output).
- **Failure taxonomy** — a three-way stderr classification, not a judgment call: agent-reported
  task failures continue the loop; retryable infrastructure errors back off exponentially;
  permanent errors (auth, credit exhaustion) abort the firing at once.

## 3. The correctness floor (O0)

- **Blind adversarial validation** — fresh-context validators; the spec is the only shared
  input; implementer reasoning never crosses; held-out adversarial tests; the gate reproduced
  from a clean checkout. (§7)
- **Blind generator–verifier separation** — the general principle: the party judging cannot see
  the party generating. Motivated by **self-recognition → self-preference** (a model favors
  output it recognizes as its own, and chain-of-thought is highly recognizable), so hiding the
  implementer's *reasoning* specifically is the precise mitigation.
- **Generator–verifier gap** — the conditional asymmetry that verifying is easier than
  generating. It weakens for strong generators and hard problems, so the guarantee comes from
  the verifier's *leverage*, not its count.
- **Held-out tests / held-out corpus** — adversarial tests authored blind from the spec and kept
  where the implementer's context and worktree can never see them.
- **Merge gate** — clean-checkout reproduction, all-must-pass verdicts, risk floors checked
  against the *actual diff paths*. `--require-clean` refuses a dirty tree.
- **Clean-checkout reproduction** — tests run against a fresh checkout of committed code only,
  never the worker's dirty worktree.
- **Closure gate** — the completion check, judged against the **frozen plan snapshot** taken at
  build start, under the **fresh-evidence rule** (only evidence newer than the last remediation
  can decide), with a bounded **remediation cap**. Wired as a Stop hook.
- **Risk floors** — a path-glob → minimum-profile map enforced at the merge point by inspecting
  the real diff. *The diff decides, not the tag*: a mis-tagged security task cannot be validated
  cheaply and merged silently. **Floors-always** (I16) requires the floor step on every profile.
- **Floor collision** — a gate refusal when a task touches a path floored above its profile.
  **Floors × profiles consistency** is the static invariant that no task's profile sits below
  the floor of a path it `touches`.
- **Profile** — a task's named risk level (`routine < elevated < high < critical`) setting
  validator count, lenses, tier, and effort. **Protected profiles** never start cheap and are
  **strengthen-only** (downgrades forbidden).
- **Leverage diversity** — what actually de-correlates a panel: held-out execution,
  clean-checkout reproduction, distinct lenses on distinct artifacts. **Model heterogeneity is
  weak insurance, not a diversity mechanism** — LLM errors correlate strongly (~60%
  same-wrong-answer agreement when two models err, rising with capability, crossing providers).
  N same-family validators are not N independent draws.
- **All-must-pass** — any single lens's FAIL blocks. Consensus *voting* is reserved for
  redundant panels, because voting amplifies common-but-wrong outputs (the **popularity trap**).
- **Escapes log** — the committed, labeled record of defects a panel missed. Ground truth for
  measuring **catch-rate**.
- **Calibration canaries / calibration probe** — planted known-severity defects the panel must
  catch before any "0 findings" downgrade is trusted. A miss freezes the downgrade. **Panel-wide
  canary aggregation**: a defect missed by *all* lenses is recorded as a **correlated blind spot**.
- **Discovery channel** — the mechanism by which a merged-but-wrong change is ever found.
  "Escapes ≈ 0" is unfalsifiable without one, so flips require an *active* channel:
  **escape backfill** (a later task's discovery files an entry against the panel that passed it)
  and sampled **escape-hunts**.
- **Reward hacking** — satisfying the letter of a check while missing intent: patching the
  evaluator, hardcoding a pass, printing "PASS". Measured, not hypothetical.
- **Stale-green** — a suite that reads green but no longer reflects correctness. The false-PASS
  family the clean-checkout rule defends against. (Self-inflicted once here, by piping a test
  command's exit status through `tail`.)
- **False PASS / false FAIL** — the symmetric failures. A false FAIL (hallucinated finding)
  blocks a merge, drives paid escalation, and poisons break-even telemetry. Base rates are
  substantial (~79–83% of raw multi-agent findings die under adversarial refutation).
- **Executable repro** — an error finding carries a machine-replayable command + expectation
  that the gate **re-executes in the clean checkout before the FAIL blocks**. A finding whose
  repro doesn't reproduce downgrades to ask-user and is counted in the **false-FAIL rate**.
- **Typed findings** — `severity (error|warning|info)` × `action (auto-fix|ask-user|no-op)` with
  per-step **auto-fix budgets**. Review-class findings default to 0 — always human. Safe
  mechanical fixes are applied by the gate pipeline, never by the implementer being judged.
- **Claims, not evidence** — no status transition, verdict, or resume decision from a model's
  own summary. The loop reconstructs from artifacts (git delta, gate output, ledger). Agent
  self-reports are measurably unreliable.
- **Spec-ambiguity blockers (H9)** — a test-author's `spec_ambiguities` become *blocking* records
  on high/critical profiles, parking the task before the implementer spends tokens on an
  ambiguous spec. **`corpus_covers: "both"`** (I20) discharges an ambiguity that the held-out
  corpus covers under every reading — it cannot produce **validated-wrong software**.
- **Validated-wrong software** — spec↔intent divergence that passes validation, because the spec
  is the one shared input blind validation cannot audit.
- **Fail-closed** — an enforcement gate that cannot run refuses the merge. Only *advisory* layers
  (triage annotations, suggestions) fail open.
- **Selftest / smoketest** — `harness.selftest` proves every gate fails-closed with a failing
  case; `harness.smoketest` walks the skill's real step order in a scratch clone at zero quota,
  catching **composition defects** that hermetic per-module suites miss.
- **Registration ≠ execution** — a registered hook is proven present, not proven to fire.
  Unregistered hooks are a library, not an enforcement layer.

## 4. The vault and isolation

- **The vault** — the store of held-out tests and held-out execution evidence. **It lives
  OUTSIDE the repo** (absolute path). An in-repo vault dirties the tree *and* rides git history
  into worker worktrees, quietly killing the blindness claim.
- **Six-layer vault-isolation stack** — isolation is a stack, not a flag: (1) sandbox `denyRead`
  on the vault path (OS-enforced for Bash and children — macOS **Seatbelt**, Linux
  **bubblewrap**); (2) **Read/Edit deny rules** covering the built-in file tools (absolute
  precedence, symlink-resolving), since the sandbox covers only Bash; (3) **strict-mode flags**
  (`allowUnsandboxedCommands: false`, `failIfUnavailable: true`), without which the boundary is
  prompt-dependent; (4) config in a scope the worker cannot write; (5) **network egress
  control**, since filesystem isolation without network isolation permits exfiltration; (6)
  per-role isolation via **separate processes**, because subagents inherit the parent sandbox.
- **Vault-canary read-attempt** — the gate self-test that proves isolation *by a failing read*,
  never assumes it.
- **Permission enforcement is harness-level, not model-level** — a CLAUDE.md instruction not to
  look is not access control. An agent has autonomously disabled its own sandbox and bypassed
  path denylists `[measured]`.
- **Approval fatigue** — the socially-engineerable failure of human approval prompts under
  repetition. Not a containment guarantee on their own.
- **Vault replay / safe-RTS** — on a re-validation, replay the vault against the *unchanged*
  surface for zero re-authoring tokens, under the **safe regression-test-selection** property:
  never skip a test the change could affect; full-run fallback for anything unanalyzable.
- **Regression floor** — a frozen corpus is a *saturated* corpus, structurally unable to find a
  new hole. Fresh authoring on the changed surface is therefore mandatory.
- **Leakage budget** — the metered allowance for held-out content bleeding into
  implementer-readable paths across fix iterations. Every gate-side replay is metered
  (`record_replay`); out-of-gate corpus runs are forbidden.
- **Adaptive-reuse leakage** — the statistical hazard of repeatedly running the same held-out
  corpus against successive fix attempts (classic **Ladder / Thresholdout** territory). Evidence
  artifacts (verdicts, full test logs in in-repo evidence dirs) are themselves a leakage channel
  — hence the **vault-side evidence store** and **manifest-based scrubbing**.
- **Interlocks** — firing-time hooks demanding fresh stamps. **Merge interlock**: `git merge` to
  a protected ref requires a fresh PASS gate stamp bound to that branch + HEAD SHA. **Spawn
  interlock**: a worker spawn requires a fresh admission decision stamp. Both inert outside
  firings, fail-closed inside.
- **Machinery paths** — the gate-protected, upstream-owned code (`harness/`, `hooks/`,
  `.claude/`, `tools/`, `docs/plan/`, `docs/design/`, plus `plan/**`). Product code goes
  elsewhere (`pilot/<name>/`). **Workers deny machinery unconditionally**, regardless of branch
  name — a branch-prefix allowlist is a dev convenience, not a boundary a worker may adopt.
- **Worker overlay** — the per-worktree settings file binding the vault denies and per-role
  policy; the reason headless one-shot workers exist (the Agent-tool path structurally cannot
  set it).
- **Worktree** — an isolated git checkout per implement→validate pipeline. Worktrees of the same
  repo do **not** share prompt cache (different cwd), so each concurrent pipeline pays its own
  ~20–30k-token cold prefix. **Worktree pooling** (with **durable leases** that survive worker
  death) amortizes environment cold-start.

## 5. Budget, quota, and the window

- **Window** — a Max-plan rate allowance. Two exist: a **5-hour rolling window** (which *anchors
  at the first message*, not continuously) and **weekly caps** (one overall + one Sonnet-only,
  with independent resets). No published absolute sizes — only plan multipliers.
- **Shared pool** — the Claude app, every Claude Code session, IDE, and every subagent draw from
  one allocation. It is **externally drainable**: the operator's own interactive use consumes
  the same window the governor is budgeting, invisibly to local token accounting.
- **The wall** — a window's ceiling. Hitting it mid-panel wastes the whole in-flight panel; an
  unattended firing halts cleanly there unless usage credits were pre-enabled.
- **Budget governor** — the deterministic script the loop consults between tasks: *don't start
  what you can't finish*.
- **Source ladder** — the governor's best-source-first fallback for occupancy: **statusline**
  (official, in-session, zero-token) → **oauth-usage** (undocumented endpoint) → **estimate**
  (run-log sums; systematically optimistic, since it cannot see the operator's own drain).
- **Statusline JSON / `rate_limits`** — the documented stdin feed carrying
  `five_hour`/`seven_day` `used_percentage` and `resets_at`.
- **Statusline-dump shim** — a statusline command on the operator's interactive session that
  tees its stdin JSON to a file the governor reads. *Official data, unofficial acquisition* —
  it stales the moment the host session idles.
- **Readings carry their age** — a reading older than the staleness ceiling is treated as
  degraded: the admission margin widens with data age and the rung falls through.
- **Occupancy** — the measured fraction of a window consumed. `unknown` occupancy makes
  admission **fail-closed**: you cannot admit against an unmeasured window.
- **Degrade (0.8) / pause (0.95)** — the governor's thresholds. At *degrade*: panels shrink to
  profile minimums (never below a risk floor), no new tasks start, in-flight work commits. At
  *pause*: clean pause — resume marker written, worktrees reconciled, run marker released.
- **Observe-only** — ship thresholds logging crossings without acting, so ceilings are tuned on
  real telemetry first. Untuned hard caps stall the whole loop.
- **Conservative mode** — the posture when no live rung is reachable: tightened thresholds,
  widened admission margin, cheap-serial work only. A firing never silently begins full fan-out
  on estimate-rung data alone (**firing preflight**).
- **Admission control** — the window-aware rule: each candidate task carries a **P95 quantile**
  cost forecast, admitted against the degrade threshold *with* the forecast burn added. Never a
  point estimate — same-task spend varies up to ~30× and models cannot self-predict their own
  burn (r ≤ 0.39).
- **Overshoot** — realized spend above the effort target, because thinking budgets are soft
  targets. The governor carries per-`(tier, effort)` overshoot variance.
- **Window-phase scheduling** — heavy fan-out right after a reset; cheap serial work in the
  tail. **Reset headroom** waives tail-capping when the window will reset before exhaustion.
- **`fraction_rate`** — per-firing burn rate, computed only from readings after this firing's
  run-marker `acquired_at`. A fresh firing stays conservative until it has ~10 minutes of its
  own readings.
- **Sticky `~` (estimated-accounting flag)** — once any reading came from the estimate rung,
  every total derived from it is flagged estimated. Measured and guessed numbers are never
  silently blended.
- **Bootstrap deadlock** — the composition defect where a fresh firing can admit nothing (no
  statusline dump + no OAuth doc + unpopulated ceilings → occupancy unknown → every admission
  refused). Broken by `--assume-occupancy <frac> --acked-by <operator>`: attributed,
  bounds-checked, sticky-`~`, conservative-serial only.
- **Usage credits** — the escape valve, billed at standard API rates, strictly
  opt-in-in-advance with no silent spillover. Surfaced to the operator as a choice at pause
  time, never auto-purchased.
- **Per-model weekly cap** — a model's own cap sitting *below* the general windows and invisible
  to them. Fable 5 hit its cap (`429 "out of usage credits"`) while the general windows read
  0.82/0.63 — hence I28 (Fable removed from machinery; `max` temporarily aliases `capable`).
- **Substitution does not dodge a window; parking does** — under an over-degrade general window,
  workers stall in indefinite API backoff rather than 429-ing (a measured 38-minute
  zero-progress hang).
- **Break-even (>40%)** — at roughly >40% cheap-tier failure on a bucket, the wasted attempt
  plus re-run costs more than starting one tier up. The controller trips the start tier up.
- **Early-abort** — terminating a doomed trajectory mid-task on a feasibility signal (recovers
  28–64% of a failing run's tokens). Ships observe-only until the false-abort rate is proven
  against O0.
- **Kill switch** — a ceiling that lives *outside* the loop. An agent stuck in a loop cannot
  talk its way past a budget ceiling.
- **No-spend list (§5.6)** — what the harness deliberately does *not* spend tokens on.

## 6. State and persistence

- **Disk is the memory** — ledgers, status index, run-log, and lessons corpus live on disk. Any
  context can die at any moment and the loop resumes from files alone. This makes fresh-context
  workers and orchestrator compaction free in *correctness* terms.
- **Event log** — ledgers and run-logs are **append-only**. The raw, immutable history.
- **Derived state / reconciliation** — *current* state is always a derived reconciliation whose
  authoritative inputs are gate/run artifacts and git — **never the last log line** (after a
  resolved gate, the tail still reads `needs-decision`). Precedence: gate verdict > run liveness
  > event claim.
- **Write-ahead** — durable events are written *before* the progress markers that suppress them
  advance. A crash at any point recovers by draining the queue. (Also: the blocker card before
  the ask; the `task_spawn` record before the spawn.)
- **Generation stamp** — mutations of shared state carry a generation counter, so a stale read
  fails loudly (`StaleGenerationError`) instead of silently clobbering. Load-bearing the moment
  concurrency exceeds 1.
- **Torn-tail crash model** — an unacknowledged trailing fragment is ignored on read and
  repaired on next append; interior corruption raises loudly.
- **Run marker** — the advisory, pid-live file marking a firing as live (holds the occupancy
  snapshot and `acquired_at`). Released at a clean pause.
- **Resume marker** — written at a pause boundary (reason, next task, occupancy snapshot, run
  conventions, pinned commands) so the next firing resumes from disk. **Resume reads artifacts
  only, never a summary.**
- **Pause request / pause ack** — the operator drops `state/pause.request` from any terminal;
  the loop writes `pause.ack` at its next stage boundary, drains in-flight atomic work, then
  parks cleanly.
- **Run-log** — the append-only telemetry record: `task_spawn` / `task_complete` /
  `task_aborted` / `task_parked`, carrying role, profile, tier, model, effort, attempt, and
  tokens. Records the params **you requested**, never a worker's self-report.
- **Admission stamp / gate stamp** — disk proof that judgment happened. The spawn interlock
  demands a fresh admission stamp; the merge interlock demands a PASS gate stamp bound to
  branch + HEAD SHA.
- **`state/`** — the runtime working directory: created lazily, gitignored. `ls state/` failing
  before a firing is normal.

## 7. Governance and self-modification

- **Governed self-modification** — the loop *proposes*; a human *ratifies* machinery changes via
  a committed queue. Headless runs cannot edit their own machinery.
- **Ratification** — the human-approval stamp gating a firing, **content-bound**: any later plan
  edit voids it. The build-loop refuses to start without `harness.planning ready` passing.
- **Ratification queue / propose–dispose** — the committed queue where machinery proposals, plan
  revisions, and controller tunings collect and are ratified in one sitting. Never self-applied.
- **Decision card** — one queued proposal: deterministic Situation → **advisory triage** (fails
  open — a failed triage still publishes the card) → recommended action → exactly-one-choice
  options. Carries a **content hash**; a **stale-decision guard** refuses ratification if the
  proposal changed after review.
- **Authority separation** — LLM output is advisory and never authorizes action; trusted
  deterministic code executes. No autonomy level relaxes the human carve-out for destructive,
  irreversible, or security-sensitive changes.
- **Controller** — the periodic reflection step doubling as the cost/quality controller.
  Triggers on **ground-truth events** (an escape, a canary miss, a durable FAIL) — never
  open-ended synthesis.
- **Levers** — what the controller may tune: starting tier, validator tier/count/lens-set,
  per-profile effort, concurrency cap, vault replay rate, window ceilings.
- **Lever discipline** — one lever at a time; minimum **sample floors**; model/effort changes
  reset samples; **every downgrade needs a fresh calibration PASS**; protected profiles
  strengthen-only; everything queues to ratification with a cost/benefit estimate.
- **Insurance machinery** — floors, calibration, closure, budget. Never pruned on dormancy,
  because for insurance, *silence is the desired state*. Contrast: dormant opt-in controllers,
  which are pruned on evidence.
- **Machinery is upstream-owned** — in a pilot clone, do NOT implement machinery fixes locally.
  Record the defect in the observations ledger; the fix lands in the parent repo and arrives by
  `git fetch <parent> main && git merge FETCH_HEAD`. Local edits are overwritten by that merge.
- **P2-collision** — the named incident that produced the rule above: a pilot session and the
  parent independently built the same fix two ways; the sync clobbered the better version and
  left a broken **chimera** (session code calling functions the merged module no longer had).
- **Boundary sync** — machinery is frozen mid-firing. Upstream merges happen only at a
  firing/pause boundary, where "the arm changes".
- **Keep the gate outside the editable region** — the merge gate, vault, and ratification
  machinery must never sit inside any surface a self-improvement loop can propose against. The
  literature says why: see the gaming ledger below.

## 8. Planning and process

- **Order of operations** — `plan-build` (interview → ratified plan) → `build-loop` (the firing).
- **plan-build** — the relentless planning interview: one question per turn, each with a
  recommended answer, until the spec is determinate.
- **Determinacy bar** — the interview's stop condition: *a spec-only test-author could write
  held-out tests with no guessing.* **Two clean sweeps** (consecutive passes surfacing no new
  gaps) = done.
- **Explore, don't ask** — if the repo, the research corpus, or prior notes answer it, read them.
  Only the operator's preferences and intent require the operator.
- **DECISION (delegated)** — "you decide" is an answer you must *convert*: record it explicitly
  with your choice and rationale. Never silently assumed.
- **The wedge / OUT list / walking skeleton** — the product's thin entry point; the explicit
  out-of-scope list; a small end-to-end phase 1 (small must not mean vague).
- **`touches`** — the representative concrete paths a task's spec pins, recorded at plan time so
  the preflight can prove floors × profiles mechanically instead of by eyeball.
- **`plan_ready`** — the 7-check, fail-closed gate the build-loop refuses to start without.
- **Gate preflight** — the pre-ratification sweep simulating every statically-evaluable
  pre-spawn gate (floors × touches, H9 × existing handoffs), forcing foreseeable questions to
  ratification instead of mid-firing.
- **Frozen instrument / same-plan protocol / byte-identical** — the pilot methodology: hold the
  ratified plan bit-for-bit constant across pilots so **machinery is the only arm variable**.
  When a policy change invalidated v1, the re-ratified plan became "instrument v2".
- **Arm** — one experimental condition (a machinery version under test). A run spanning a
  mid-flight machinery change is **confounded** and yields no clean arm.
- **Kickoff block** — the complete firing-launch instruction block. Rule: always emit the
  complete current block, never a delta.

## 9. Machinery internals, cache, and context economics

- **Built-in before custom** — bind every mechanism to a Claude Code primitive first. Custom
  machinery is only the residue no built-in covers. The **leverage map** (§4) is that table, and
  it is re-audited on each Claude Code feature wave.
- **Zero-token enforcement** — everything safety- or budget-load-bearing runs as a hook or
  script: deterministic, model-free, un-skippable, costing no context.
- **Hooks over prose** — prose guards burn tokens every turn *and* get skipped exactly when the
  loop is degraded. (The literature's sharpest confirmation: in STOP, adding an explicit
  "DO NOT CHANGE" warning made sandbox-disabling slightly *more* frequent.)
- **Prompt-cache discipline** — the #1 hidden lever. Cache-busting is the catastrophic spend
  event (one bug produced 10–20× inflation).
- **Frozen prefix / cache-buster** — the per-firing prefix (model, effort, hook set, MCP set,
  skill inventory) is fixed at spawn. The real mid-firing busters: a `/model` switch, an
  `/effort` change, the first fast-mode toggle, a **bare-tool deny rule**, and a non-deferred MCP
  connect/disconnect. A mid-session CLAUDE.md edit is a *silent no-op*, not a bust.
- **Cache read / write / miss** — reads bill at ~10% of input rate; the `/usage` limit
  attribution itemizes cache **misses** as the limit driver. Whether reads count against
  *subscription* limits, and at what weight, is officially unanswered `[contested]`.
- **TTL** — subscription auth gets the 1-hour cache TTL automatically (and loses it while drawing
  on usage credits). Subagents get 5 minutes and start **cold**; forks inherit the parent cache.
- **Idle-session resume is a heavy admission** — it charges the full accumulated cache context to
  the new window (~15M tokens for ~20k of real work). Prefer a fresh session + disk resume over
  `--resume`.
- **Structured outputs** — schema-forced worker returns eliminate parse-repair round-trips.
- **Definitive empty states** — `runnable: 0 (3 blocked, 2 parked)`, never an ambiguous blank
  that forces a verification retry.
- **Tail-truncation + disk spill** — truncate output tail-biased (failures live at the end), spill
  the full artifact to disk, surface the path.
- **Serialization policy** — never pretty-print into model context (+48–82% tokens); compact
  JSON/JSONL for persisted state; digests flattened, then rendered as Markdown tables. **No TOON.**
- **TOON** (Token-Oriented Object Notation) — a tabular JSON encoding. Saves 20–40% vs compact
  JSON on *uniform* tabular data only, loses off-uniform, is beaten by CSV on size, and is
  unreliable for model-*generated* output (one-shot 50% vs JSON 75%). Read-accuracy claims are
  `[contested, leaning negative]`.
- **Skills discipline** — skill *loading* is cheap (progressive disclosure: names at start, body
  on invoke) but *triggering* is unreliable (recall 38–69%). So load-bearing procedures are
  invoked **phase-gated in deterministic prompt text**, never trigger-reliant. Situational skills
  carry explicit trigger conditions. The installed inventory is checked against the ~15k-char
  skill-list budget that silently drops overflow.
- **Routing canaries** — fixture prompts with expected skill-invocation sets, *including negative
  controls* (no skill should fire), so silent under-invocation is detectable.
- **MCP schema tax** — the token cost of MCP tool definitions loaded before any work (~42–77K+,
  `[measured, replicated]`). **Deferred tool loading** (Tool Search) wins when the catalog is
  ≫10K tokens and the hot set is a small fraction; eagerly pin the hot set otherwise. Both
  regimes are real.
- **Mock worker** — a deterministic rig speaking the real return schemas (synthetic usage
  counters, scripted workspace effects) so the loop, governor, and ledger are end-to-end testable
  at **zero quota**. Re-recording real fixtures spends quota and is operator-gated.
- **Spawn allowlist** — `(model, effort)` is validated against an explicit allowlist *before* any
  spawn, and results are null-checked. Required because **acceptance ≠ application**: an invalid
  `effort` string is silently accepted, and an invalid `model` id fails only as an async `null`
  plus a log line — not a catchable throw.

## 10. Staging, pilots, and lifecycle

- **Stage 0 → 3** — the staged, measured rollout. Stage 0: cache discipline, observe-only
  governor, serial execution, mock rig, enforcement wiring. Stage 1: governor enforcing, duration
  predictor (once validated), cross-phase DAG. Stage 2: vault replay, concurrency cap 2, worktree
  pool. Stage 3 (optional): the full bucket × profile tier matrix, test-execution caching.
- **Stage-gate flip** — a config/enforcement flip of already-built machinery, gated on the prior
  stage's telemetry. *Not* a build increment.
- **Stage-0 exit criterion** — a real pilot firing. No further machinery ships before it: the
  apparatus has outrun realized scale once already.
- **Pilot** — a small real greenfield build at Stage-0 settings, producing the first genuine
  telemetry. **greenlane** is the pilot product (a field-service SaaS); `test1` is the pilot clone.
- **Observations ledger** — the per-pilot file where the operator streams friction and failures,
  each **triaged** (defect / friction / benign / needs-detail / watch) and mapped to a fix.
  **Themes** are the recurring cross-observation patterns distilled at the bottom.
- **Defect harvest** — a pilot's real yield, measured in observations that became machinery
  fixes, even when the run itself is terminated or confounded.
- **Composition defect** — every module passes its own hermetic suite while the repo-level
  composition has no test. The recurring pilot theme, and why the smoketest exists.
- **Accept-halt / clean close** — a firing ending with the runnable set empty and zero worker
  spend. *The halt is itself the finding.*
- **Source-dive** — a session reading machinery source to recover shapes the docs don't state.
  A turn-economy cost that [reference.md](attic/reference.md) exists to prevent.

## 11. Statistics and methodology

- **Paired-arm template** — the controller's lever-evaluation methodology: one lever = one arm,
  a **continuous metric** (never binarized), **paired** per-task comparison, difficulty strata
  defined **out-of-sample**, and **confirmatory-vs-exploratory** labeling. Borrowed wholesale
  from programbench-bench (which adds paired Wilcoxon signed-rank + Holm correction).
- **Negative controls** — cases where the effect should *not* fire. Without them, precision is
  invisible.
- **Sample floor** — the minimum sample per cell before a calibration verdict is trusted (8 per
  bucket in the predictor's gate).
- **P50 / P90 / P95** — cost quantiles from the run-log. **P95** is the admission estimate;
  overshoot is measured against P50. Agent spend is heavy-tailed (P95 ≈ 4× mean), so quantiles,
  not means.
- **Spearman rank correlation** — the dependency-free rank correlation the calibration gate
  computes between predicted bucket and actual tokens.
- **Monotonicity** — the check that per-bucket mean cost is non-decreasing XS→XL. Non-monotonic
  buckets don't separate real cost.
- **Escape-rate redline** — any validation escape among validated tasks fails calibration
  outright. (Design O0: escapes are never traded.)
- **`flag_ready`** — the calibration gate's single boolean verdict. **Nothing auto-flips a flag**;
  the scripts only *report*, and a human (or the ratified controller) decides.
- **Asymmetric loss** — mis-routing short work *up* wastes ≤2×; mis-routing long or thinking work
  *down* costs a failed attempt plus wall-clock plus escalation. So the predictor needs only high
  recall on the long/thinking class: **when unsure, route up.**
- **Duration bucket** — a coarse horizon class (XS–XL) scored deterministically from spec size,
  file count, subsystem breadth, and novelty — *a script, not an LLM call*, because models
  cannot self-predict spend. Predicts *buckets*, never spend. Flag-gated until calibrated.
- **`forced_min_tier`** — the predictor output forcing a minimum tier when a task carries novelty
  flags, regardless of size.
- **Adaptive overfitting / the Ladder / Thresholdout** — the theory bounding how often a hidden
  set can be reused before it's gamed. A naive holdout's adaptive-reuse budget is ~linear;
  Thresholdout's noise/threshold mechanism extends it to ~quadratic. An un-thresholded oracle is
  provably attackable.
- **Mutation testing / mutants** — seeding faults to measure checker adequacy. The load-bearing
  caveat: ~27% of real faults are uncoupled from standard mutants, so canaries measure only the
  *planted-defect distribution*.
- **`[author-run]` n=1 caveat** — one run per cell, no variance, unstated cleaning rules. Treat as
  directional ablation evidence, never as effect sizes.
- **pass@k vs pass^k** — passing in *at least one* of k tries vs *all* k. Given ~30× same-task
  variance, single-run gates are noise.

## 12. Meta-harness and self-improvement (research vocabulary)

From [research/meta-harness-and-self-improving-harnesses.md](research/external/self-improvement/meta-harness-and-self-improving-harnesses.md).

- **Harness** — "the system surrounding a base model that orchestrates execution and decides how
  the model thinks and plans, calls tools and acts, perceives and manages context, stores
  artifacts, and evaluates results" (Weng, 2026).
- **Optimization-target ladder** — instruction prompts → structured context → workflow → harness
  code → optimizer code. Each rung treats the previous rung's hand-tuning as a search space.
- **Meta-harness** — a harness that optimizes harnesses. The optimized object is the *code*
  deciding what gets stored, retrieved, and presented to the model.
- **Self-improving harness** — a loop that edits its own instructions, tools, policies, or code,
  gated by a promotion test, with model weights frozen.
- **Two-split no-regression promotion rule** — Self-Harness's acceptance test: accept an edit only
  if Δ(held-in) ≥ 0 **and** Δ(held-out) ≥ 0 **and** max > 0, where the held-out split "is never
  shown to the proposer and is used only by the automatic promotion gate."
- **Weakness mining** — recording each failure as (terminal verifier cause, causal agent behavior,
  abstract mechanism), not just its symptom: two same-symptom failures can have different causes.
- **Leakage audit** — a zero-token regex/audit pass over any proposed machinery or prompt change,
  hunting held-out-content leakage into the harness.
- **Gaming ledger** — the catalogue of every documented case of a self-improvement loop gaming its
  evaluator. The headline entries: **STOP** wrote code disabling its own sandbox (and the rate
  *rose* when a warning was added); **DGM** removed the reward function's hallucination-detection
  markers, scoring a fake 2.0/2.0, caught only by human review of the archive lineage;
  **Autodata**'s agent prompted the weak solver to be weak; **Anchored Self-Play**'s generator
  drifted to unrealistic bugs until re-anchored to human-authored examples.
- **Capability floor** — the model-capability threshold below which a self-improvement loop
  *degrades* rather than improves.
- **Diversity collapse** — a multi-candidate search prematurely narrowing, losing the diverse
  candidates that would have won later. Countered by novelty-rejection pressure.
- **Pareto frontier** — retaining the non-dominated candidate *set* over multiple objectives
  rather than collapsing to one winner. In tension with a strict lexicographic order — the
  resolution: lexicographic for *operational* decisions; frontier retention for any future
  *search* over harness variants.
- **Premature completion** — declaring done before done. The empirically dominant long-horizon
  failure: RE-Bench measured agents that "satisfice rather than optimize, often submitting before
  the time limit" and show "poor ability to notice whether making progress" (**progress-blindness**).
- **Terminal reviewer** (Zenith) — a fresh, context-blinded session that reviews the *original
  request* against the workspace "as if it had no mission history." Its verdict is the only thing
  that can seal a mission `done`.
- **RALPH** — the folk loop where each fresh session re-opens the gap between current state and
  the original requirement. The strongest simple baseline; expensive, and with no principled
  stopping rule.

## 13. Named external systems

Compact one-liners. Full treatment in [research/landscape-and-novelty.md](research/external/landscape/landscape-and-novelty.md),
[research/zenith-and-meta-zenith.md](research/external/landscape/zenith-and-meta-zenith.md), and
[research/ecosystem-mining/](research/external/landscape/ecosystem-mining/README.md).

**Agents & frameworks:** **Kiro** (AWS; requirements→design→tasks in EARS syntax + approval
gates) · **GitHub Spec Kit** (spec→plan→tasks→implement + a "constitution") · **Devin** (Cognition;
plan-first, VM snapshots) · **Aider** (architect/editor = planner vs diff-writer, *not* verifier) ·
**Cline** / **Roo Code** (Plan/Act; Roo's **Boomerang tasks** isolate subtasks, returning only a
summary) · **OpenHands** (replayable event stream; its QA agent sees prior work — not blind) ·
**SWE-agent** (ReAct loop + Agent-Computer Interface) · **MetaGPT** / **ChatDev** (waterfall SOP
roles) · **AutoGen** (one shared broadcast thread — the dated, no-isolation approach) · **CrewAI**
(explicit `context` edges) · **LangGraph** (best-in-class durable state: checkpointers,
time-travel, subgraph isolation — but **no built-in critic**) · **Tessl** (spec-as-source) ·
**Zenith** (Intelligent Internet; the closest published neighbor — shipped, provider-agnostic via
**ACP**, with the terminal-reviewer stopping rule, but no budget machinery and prompt-only
blindness).

**Practitioner stack (kunchenguid):** **AXI** (agent-ergonomic CLI interface principles) ·
**gnhf** (overnight RALPH-style runner) · **firstmate** (crew orchestrator; the
spawn-refuses-without-a-routing-decision pattern) · **treehouse** (worktree pooling) ·
**no-mistakes** (push-gated validation pipeline; ships the ecosystem's only deterministic
anti-reward-hack guard) · **wheelhouse/m87** (IssueOps ratification cards).

**Self-improvement literature:** **STOP** · **ADAS** · **AFlow** · **AlphaEvolve** ·
**ShinkaEvolve** · **GEPA** · **DGM** (Darwin Gödel Machine) · **Hyperagents** · **Self-Harness** ·
**Meta-Harness** · **ACE** / **MCE** (context engineering) · **Autodata** · **Anchored Self-Play** ·
**Absolute Zero** · **TTT-Discover** / **UG-TTT** (the counterpoint: weights optimized at test
time, harness held fixed) · **AI Scientist** (Nature 2026; its completion gate is its own
automated peer review — the self-grading risk) · **autoresearch** (Karpathy, Mar 2026; the
minimal single-GPU keep-if-val-improved loop — and the seed-mining cautionary tale) ·
**ENPIRE** (NVIDIA GEAR, Jun 2026; "physical autoresearch" — robot-policy self-improvement
behind a frozen agent-authored verifier) · **OpenEvolve** (the open AlphaEvolve
reimplementation; reproduced circle-packing within 0.04%).

**Benchmarks:** **SWE-bench Verified** (whose hidden `FAIL_TO_PASS` + `PASS_TO_PASS` split is the
architecture validating this design; ~31% of passing patches ride on tests too weak to catch a
wrong fix) · **RE-Bench** (METR; the long-horizon human-vs-agent time-budget crossover) ·
**Terminal-Bench-2** · **Polyglot** · **PaperBench** · **CORE-Bench** (task-specific scaffold beats
generic) · **MLE-bench** · **FrontierSWE** (Proximal Labs; independent) · **GAIA** / **HAL
leaderboard** · **ProgramBench** / **programbench-bench** (the paired-arm instrument) ·
**superpowers-bench** (skill-invocation recall) · **SkillsBench** · **Defects4J**.

**Routing & economics literature:** **RouteLLM** (~75% savings in-distribution; *below random*
when trained on a mismatched distribution) · **FrugalGPT** (start-cheap cascade) · **ARES**
(per-step effort routing) · **METR time horizons** (task difficulty = time a skilled human needs;
the "50% horizon") · **Ekstazi** / **Microsoft TIA** (safe regression-test selection) ·
**Refute-or-Promote** (adversarial kill-mandates at promotion gates; ~79–83% of raw findings die).
