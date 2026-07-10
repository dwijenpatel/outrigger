# Zenith & Meta-Zenith (Intelligent Internet) — the closest-neighbor harness

What Zenith is, what its RALPH-ablation experiment actually shows, what Meta-Zenith claims,
and a point-by-point comparison against this design
([../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md)).
Zenith is the nearest published neighbor to this project found to date — closer than anything
in [landscape-and-novelty.md](landscape-and-novelty.md) or
[ecosystem-mining/](ecosystem-mining/README.md) — and it ships as working code.

**Provenance:** 2026-07-09 study. Primary sources: the local clone at `~/repos/zenith`
(commit `feb1d62`, Apache-2.0) — README, the full technical report PDF (dated 2026-05-12),
the `zenith_harness` source and test suite, all role prompts and bundled skills — read
exhaustively by one deep-dive agent (Opus 4.8, 33 tool calls); plus an external-context agent
covering ii.inc blog posts, the FrontierSWE leaderboard, the GAIA leaderboard, and reception
searches. Mechanism claims below are tagged `[code]` (verified in source) vs `[report]`
(claimed in the PDF only); every performance number is `[author-benchmark, single-source]`
(II's own runs, ~n=1 per cell) per the standing independent-confirmation rule.

---

## 1. What Zenith is

An agent harness "for work that may run for days or weeks, where the dominant failure mode is
**premature completion** rather than inability to make progress" (README). A Python runtime
(`zenith-harness`) turns an ordinary Claude Code / Codex / Hermes session into a multi-agent
orchestrator:

- **Orchestrator = the interactive LLM session**, loaded with a 421-line system prompt,
  connected to Zenith's MCP server exposing exactly **7 tools**: `start_project · submit_plan ·
  advance_project · end_mission · decide_attention · inspect_project · abort_project`. `[code]`
- **Workers / validators / terminal-reviewer = separate ACP subprocesses**
  (`claude-agent-acp`, `codex-acp`, `hermes acp`) spawned by the runtime; each gets a tiny
  per-node MCP server exposing a *single* handoff tool (`end_node` /
  `submit_terminal_review`) that writes a JSON handoff to disk. Tool-surface isolation is
  structural: each role sees a disjoint tool set. `[code]`
- **Declarative control:** the orchestrator's five report-level decisions (spawn worker /
  spawn tester / register skill / replan / stop) are edits to a task graph + disk artifacts;
  a deterministic Python kernel (`MissionCoordinator.step()`) decides what dispatches. The
  coordinator is stateless — reconstructed per tool call, reloading `tasks.json` /
  `task-state.json` / `contract-state.json` from disk each step. `[code]`
- **Disk-as-memory:** all state lives in an out-of-workspace bucket
  (`~/.zenith/projects/<pid>/`) — durable tree (brief, contract, attempts as markdown,
  decisions, skills, `MEMORY.md`) + runtime cursors (JSON). Atomic writes
  (`tmp` + `os.replace`) + a per-project asyncio lock. Resume = re-reading `running` tasks'
  handoff files; a `running` task with no handoff synthesizes a *failed* handoff. **Not** an
  append-only event log — overwriting cursors, no generation stamps, no write-ahead
  ordering. `[code]`
- **Provider-agnostic by table:** a frozen `ProviderDefinition` table parameterizes skill
  dirs, config format, ACP command per backend; **each of the four roles can be a different
  provider** via env vars (this is how the report's Opus-4.6 + GPT-5.4 hybrid is built).
  Model/effort choice is environment-level and static — codex workers hardcode
  `model_reasoning_effort="xhigh"`. `[code]`

## 2. Stopping discipline — the actual fix to RALPH's missing stopping rule

The report's thesis (abstract): RALPH is the strongest simple baseline *because* each fresh
session re-opens the gap between current state and the original requirement — but RALPH "is
expensive and has no principled stopping rule." Zenith's replacement is four-layered:

1. **Prompt pressure** — "Do not close because the task list appears complete. A finished
   task list is only a signal to inspect evidence and request runtime closure." `[code-as-text]`
2. **Machinery refusal** — `end_mission` errors (`mission_not_ready_to_close`) while any gate
   is ready or any task runnable. `[code]`
3. **The independent terminal reviewer is the stopping rule** — a fresh ACP session charged:
   "Review the original user request against the current workspace **as if you had no mission
   history** … Do not read Zenith mission artifacts, contracts, attempts, validator reports,
   decisions … Independence matters: earlier workers and validators are not proof." Only its
   verdict seals `done`; the runtime refuses to fabricate a pass if the reviewer exits without
   verdict. Gaps → attention the orchestrator must `patch` or roll into a next mission
   (`done_with_acknowledged_gaps`), never silently stop. `[code]`
4. **Per-milestone gate checkpoints** — every gate, pass *or* fail, raises attention for
   orchestrator review. `[code]`

**Escape hatch caveat:** the orchestrator *can* `continue` past a failed gate or a
terminal-review gap — forbidden by prompt, not blocked by machinery. The gate is deterministic
up to orchestrator adjudication, then judgment. `[code]`

This converges with two independent lines already in the corpus: METR RE-Bench's measured
failure signature — agents "satisfice rather than optimize, often submitting before the time
limit" and can't "notice whether making progress" (see
[meta-harness-and-self-improving-harnesses.md §5](meta-harness-and-self-improving-harnesses.md))
— and this design's §7 closure gate. Three groups independently landed on "premature
completion is the dominant long-horizon failure; an independent end-gate is the fix."

**Difference worth noting:** Zenith's reviewer re-derives gaps from the **original request**
with fresh eyes; this design's closure gate judges against a **frozen plan snapshot** with a
fresh-evidence rule and a remediation cap. Zenith's form catches spec-drift-from-request that
a plan-snapshot gate can miss (the plan itself may have drifted); ours bounds re-litigation
and prevents goalpost-moving. They are composable, not competing — a candidate design
amendment (§6).

## 3. Verification model — fresh-context, spec-shared, prompt-blind, **no vault**

- Validators are **separate ACP sessions with fresh context**; they see the contract
  assertions (spec), their assignment, `AGENTS.md`/`MEMORY.md`, and the worker's *written
  handoff* (as a claim) — not the worker's reasoning. "Worker reports and previous validator
  reports are leads, **not proof**" — validators must gather fresh evidence. `[code]`
- **Gates are deterministic AND-semantics** in Python: every covering validator must report
  `passed=True` per target; any dissent or missing verdict blocks. `[code]`
- **But:** the only structural invariant at plan time is *one work-owner per assertion*;
  nothing forces an assertion to have a validator or gate — validation intensity is whatever
  the orchestrator LLM authors (prose-steered: "add testing layers based on the task's risk
  profile" `[report]`). The terminal review is the backstop for un-gated surface. `[code]`
- **No held-out tests anywhere.** Validators author adversarial artifacts *into the shared
  bucket* (`evidence/`, `regressions/`) — filesystem-reachable by later workers. "Holdout"
  appears in prompts only as "respect the *benchmark's* pre-existing hidden tests." `[code]`
- **No OS enforcement.** ACP sessions run with permissions fully bypassed
  (`bypassPermissions` / `danger-full-access`, approvals never); no sandbox, no denyRead, no
  egress control, no worktrees — parallel workers share the workspace cwd. Blindness and
  independence are **prompt promises**. `[code]`

Relative to this design: Zenith independently validates the *shape* (fresh-context
spec-shared validators, deterministic all-must-pass gates, evidence-not-claims) while lacking
the *enforcement layer* (six-layer vault isolation, held-out authoring, clean-checkout gate
reproduction, canaries/escapes calibration — see
[correctness-and-verification-evidence.md](correctness-and-verification-evidence.md) and
[isolation-and-sandboxing.md](isolation-and-sandboxing.md)). The ecosystem-mining finding
(reward-hacking hole universal at 11/11 repos) extends to 12/12: **Zenith's implementer-side
file access can reach validator-authored tests too.**

## 4. The RALPH→Zenith experiment — what it shows and what it can't

Five designs, each adding one control mechanism; eight long-horizon tasks (browser game,
desktop app, NL2Repo ydata-profiling, Git-in-Zig @ 20h cap, chess engine by Elo, AIRS-Bench
web-traffic forecasting, two PaperBench reproductions); scored by each task's own external
scorer, run by the authors; study backbones GPT-5.4 XHigh + Opus 4.6 Max Effort.
`[author-benchmark, single-source]`

| Method (adds…) | Mean rank ↓ | Mean $/task ↓ | Wins/8 |
|---|--:|--:|--:|
| One-session (nothing) | 5.00 | $22.21 | 0 |
| Plan-RALPH (fixed upfront plan) | 4.00 | $161.53 | 0 |
| Milestone-RALPH (JIT milestones + independent tester) | 2.88 | $209.47 | 0 |
| RALPH (repeated gap-finding) | 1.75 | $407.58 | 3 |
| **Zenith (adaptive orchestration + stopping)** | **1.38** | **$175.68** | **5** |

Readings that survive the caveats:

- **Control structure, not spend, drives rank.** RALPH spends most and ranks second;
  One-session is 18× cheaper and last. The authors themselves: winning runs cost $60–$500 —
  "not 'spend more and win,' but not 'cheap is enough'" `[report]`. This is the O1-relevant
  finding: Zenith beat RALPH's rank at 0.43× its cost by *replacing* undirected re-review
  with directed orchestration — i.e., **token efficiency came from control-flow design, not
  from budget machinery** (Zenith has none, §5).
- **RALPH's iteration curves are non-monotonic** (plateau/regress/jump) — "a rising or
  oscillating iteration curve does not tell us when the task is complete" `[report]` —
  independent support for gate/closure-based rather than score-trajectory-based stopping.
- **Fixed upfront plans are the worst of both** (Plan-RALPH: 4.00 at $161) — brittle when the
  list is wrong and "done" labels self-reported; supports this design's revisable-ledger +
  evidence-gated closure over frozen task lists.

Caveats before importing numbers: **n=1 per method×backbone cell**, no variance, "cleaned
runs" with the cleaning rule unstated; ranks average the two backbones per baseline while
Zenith is a single tuned hybrid — RALPH's cost mean is inflated by the expensive
RALPH-Claude runs ($1,354–$1,466 on two tasks) and **RALPH-Codex alone is cheaper than Zenith
on several tasks**; Zenith wins 5/8, RALPH 3/8 (Git-to-Zig, chess, PaperBench-Rice). Treat as
directional ablation evidence, not effect sizes.

## 5. What Zenith does NOT have (verified in code)

The two axes this design leads on have **no Zenith counterpart**:

- **No budget/token machinery at all.** No governor, token accounting, window/rate-limit
  model, tier/effort routing, cache discipline, degrade/pause thresholds, or
  backoff-on-rate-limit. The only resource knob is `ZENITH_MAX_PARALLEL_NODES` (static,
  default 4). "Budget" exists only as prompt guidance the orchestrator may reason about.
  Cost in the report is a measured *outcome*, never a governed *input*. `[code]`
- **No task-conditional harness configuration in machinery.** No risk profiles, no
  path→validator floors, no minimum panel sizes; validation intensity is orchestrator-LLM
  judgment steered by prose. The "adapt the harness to the task" idea lives one level up, in
  Meta-Zenith (§6) — not in this runtime. `[code]`
- **No self-modification of machinery, and no ratification gate on what does adapt.** The
  Python runtime is immutable to the loop; what improves continuously is the *plan, skills
  (`SKILL.md` files), decisions, and `MEMORY.md`* — curated autonomously by the orchestrator
  with no human gate in machinery (user plan-confirmation is prompt-only). `[code]`

## 6. Meta-Zenith — the harness that configures harnesses

From II's blog (2026-06-29, "Zenith: frontier performance without Fable") `[first-party
marketing]`:

- "Meta-Zenith automates this construction process": given a task spec + training feedback it
  "produces a fully configured Zenith harness" — system prompts, **Contract** (goals /
  acceptance criteria / constraints), **Milestone graph**, **Worker specs**, **Validator
  specs** (build gates + fidelity checks), and **stopping policies**. It operates "one level
  higher," executing "harness-design decisions against the task specification."
- Trained by "continuously collect[ing] our own daily engineering and research tasks and
  run[ning] the harness-construction loop over this internal task stream"; "the final
  Frontier SWE evaluation used finalized Zenith harnesses."
- **Configuration key is the task family, not risk.** "Each new task family requires
  different worker roles, validation strategies, milestone decompositions, acceptance checks,
  and stopping policies." **Nothing in II's public material describes risk-tiered
  slimming** (e.g. dropping validator overhead for low-risk tasks) — that extension is this
  project's own, not importable from II. Meta-Zenith's code is **not** in the public repo.
- Positioning within the field: Meta-Zenith is a productized instance of the "meta-harness"
  pattern (Lee et al. 2026, arXiv 2603.28052 — a coding agent searching over harness *code*,
  Pareto-frontier retention; see
  [meta-harness-and-self-improving-harnesses.md](meta-harness-and-self-improving-harnesses.md)),
  specialized to generating *configurations of a fixed runtime* rather than arbitrary
  harness code.

**The benchmark claims around it:**

- **FrontierSWE is real and independent** (Proximal Labs; 17 ultra-long-horizon tasks,
  ~20h/task; public leaderboard). The official leaderboard (native harnesses) reads:
  **Fable 5 first at 0.900**, Opus 4.8 at 0.750, GLM-5.2 at 0.740, GPT-5.5 fourth at 0.730.
  **Zenith does not appear on it.** `[independent]`
- II's "#1" is a **self-administered re-run**: "We ran the full suite with Zenith and scored
  it the same way Proximal scores the public leaderboard" — GPT-5.5 + Zenith at 2.06 average
  rank / 92% dominance, claimed ahead of Fable's native-harness entry. Disclosed method,
  unverified result. `[first-party marketing]`
- Same pattern on II-Agent's "75.57% GAIA": absent from the independent HAL leaderboard
  (top entry 74.55%). `[independent]`
- **Independent reception: none found** (2026-07-09) — no HN thread, no reproduction, no
  third-party evaluation. First-party amplification only (Mostaque: "taking models you can
  use today above Fable").

## 7. Side-by-side with this design

| Axis | Zenith (implemented) | This design |
|---|---|---|
| Objective | Implicit: complete the request, don't stop early; cost reported post-hoc | Explicit lexicographic O0 ≻ O1 (window-weighted tokens) ≻ O2, never scalarized |
| Planning | LLM-authored contract + adversarial `contract-review` passes; coverage invariant in code (one work-owner/assertion); user confirmation prompt-only | plan-build interview → **human-ratified** plan behind machinery gate; risk table; phased ledgers |
| Worker isolation | Fresh ACP process; permissions **bypassed**; shared cwd; no sandbox/worktrees | Six-layer OS-enforced vault stack + worktree-per-pipeline (see isolation-and-sandboxing.md) |
| Verification | Fresh-context spec-shared validators; deterministic AND gates; **no held-out corpus**; blindness by prompt | Blind validators + held-out vault (OS-enforced) + clean-checkout gate + canaries/escapes calibration |
| Stopping | Machinery-refused early close + **independent terminal reviewer vs original request** (hard gate) + milestone checkpoints; `continue` escape hatch | Closure gate vs frozen plan snapshot + fresh-evidence rule + bounded remediation; Stop hooks |
| Resume | Out-of-tree bucket, atomic overwriting cursors + attempt reconciliation; no event log/stamps | Append-only event log, derived-state reconciliation, generation stamps |
| Budget | None (static `max_parallel=4`) | The entire O1 layer (governor, admission, routing, cache discipline) |
| Self-modification | Runtime immutable; plan/skills/memory adapt autonomously, ungated | Machinery changes proposed → human-ratified; risk floors; headless runs can't edit own machinery |
| Portability | **Claude Code / Codex / Hermes (+GLM/Z.ai) via ACP; per-role provider mix** | Claude-Code-bound |

**What Zenith has that this design lacks:** shipped, tested, provider-agnostic runtime; the
terminal-reviewer as a distinct blinded *role* judging against the original request; the
adversarial contract-review planning loop; the code-enforced coverage invariant; ACP as a
portability hedge against single-vendor coupling (a §10.3-class volatility mitigation this
corpus has repeatedly flagged).

**What this design has that Zenith lacks:** everything O1 (window-aware budget governance —
which [ecosystem-mining](ecosystem-mining/README.md) found at 0/11 and Zenith makes 0/12);
OS-enforced blindness + held-out vault (reward-hacking hole now 12/12); calibration
(canaries, escapes log, clean-checkout reproduction); mechanized risk floors;
human ratification of self-modification; event-log resume.

## 8. Candidate imports (for design consideration, not yet adopted)

1. **Terminal-reviewer closure lens** — add an *original-request* re-derivation pass (fresh
   context, no mission artifacts) alongside the frozen-plan closure gate; catches
   plan-drift-from-request that snapshot comparison can't. Cheap: one extra fresh-context
   validator at mission end.
2. **Adversarial contract-review passes at plan time** — ≥2 fresh-context reviews of the
   contract *before* implementation spends tokens; complements the existing
   spec-ambiguity blockers (plan H9).
3. **Coverage invariant in machinery** — "every assertion has exactly one work-owner" is
   enforced in Zenith's `submit_plan`; this design's analog (every assertion has ≥1
   validator on risk-appropriate floors) is currently prose + gate-time; consider
   plan-submission-time enforcement.
4. **ACP as a portability hedge** — a medium-term option if Claude-Code coupling costs keep
   materializing; Zenith proves per-role provider mixing works.
5. **Do not import:** prompt-only blindness, bypassed permissions, post-hoc cost treatment,
   ungated autonomous skill/memory curation.

## 9. Open items

- **Independent replication of the RALPH-ablation and FrontierSWE claims** — nothing
  independent exists yet (2026-07-09); watch for third-party evaluations before any design
  decision leans on Zenith's effect sizes. (Ledgered in [README.md](README.md) open items.)
- **Meta-Zenith's implementation is closed** — if II open-sources it, re-study: it is the
  nearest productized instance of task-conditional harness generation, this project's §12
  interest.
- **Whether Zenith's terminal reviewer measurably reduces premature completion vs a
  frozen-snapshot closure gate** — an empirically testable question this project's pilot
  telemetry could answer (both gates can run on the same pilot).
