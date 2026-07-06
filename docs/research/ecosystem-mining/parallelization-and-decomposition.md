# Parallel decomposition — stubs, seams, and weaker models

**Date:** 2026-07-06
**Method:** 11 cloned popular repos mined by parallel analysts; file paths cite the clones at `/Users/dwijen/repos/`.
**Question under evaluation (operator's hypothesis, quoted):** *"could we push the envelope on efficient parallelization by breaking tasks into parallelizable chunks? E.g. create stubs, then have 3 implementation authors work in parallel to implement the stubs at well-defined seams, then one task to combine and check their work? This may also allow us to use less powerful models that perform worse as task length increases."*

---

## TL;DR

The ecosystem parallelizes **reads** everywhere (review/research fan-out), parallelizes **independent artifacts** in two battle-tested places (career-ops batch, gstack Conductor sprints), and parallelizes **code implementation into one codebase** almost nowhere. Exactly one repo describes the operator's stub-and-seams pattern end to end (everythingclaudecode's Ralphinho pipeline — prescriptive markdown, unmeasured), and the repo with the most engineering rigor (superpowers) **explicitly forbids parallel implementers** while shipping the best interface-first decomposition format in the survey — which it then executes serially. The "weaker models" half of the hypothesis is directly contradicted for general tasks by superpowers' measured finding ("turn count beats token price": cheap models take 2-3x the turns and cost *more*) but directly supported for one narrow regime: **transcription-grade tasks where the plan already contains the complete code**. The honest synthesis: stub-and-seams is viable only if the stubs are so determinate that implementation approaches transcription — at which point the pattern works, cheap models work, and the harness's existing assets (determinacy interview, blind validation, cache hygiene, window awareness) are precisely the missing enablers nobody else has.

---

## 1. Map: parallelization topologies that actually exist

### 1a. Read-only fan-out (common, works, low risk)

Parallel subagents that produce *findings*, not code. No merge problem because outputs are additive.

- **gstack** `/review` dispatches up to 7 specialist subagents in a single message, dedupes findings by `path:line:category` fingerprint, boosts confidence on multi-specialist agreement, and fires a fresh-context red-team wave told what was already found (`/Users/dwijen/repos/gstack/review/SKILL.md` Steps 4.5-4.6, `review/specialists/*.md`). Specialists with 0 findings in 10+ dispatches are auto-gated off (`bin/gstack-specialist-stats`) — closed-loop control of review spend.
- **mattpocock/skills** two-axis review: Standards and Spec sub-agents run in parallel, never share context, and findings are *deliberately not merged* "so one axis cannot mask the other" (`/Users/dwijen/repos/skills/skills/engineering/code-review/SKILL.md`).
- **caveman** cavecrew "parallel scout": 2-3 investigator subagents spawned in one message, each with a strict grep-able output contract so compressed results aggregate cheaply in the main thread (`/Users/dwijen/repos/caveman/skills/cavecrew/SKILL.md`).
- **superpowers** `dispatching-parallel-agents`: one agent per *independent problem domain*, all dispatched in one response — used mainly for parallel test-failure investigations, not feature building (`/Users/dwijen/repos/superpowers/skills/dispatching-parallel-agents/SKILL.md`).
- **alirezarezvani/claude-skills** deep-research launches search subagents concurrently with model tiering; pulse documents parallel-across-sources / sequential-within-source with an explicit degradation ladder (`/Users/dwijen/repos/claude-skills/research/pulse/skills/pulse/references/parallel_execution_discipline.md`).

### 1b. Embarrassingly parallel write fan-out (works, but only for independent artifacts)

- **career-ops** conductor/worker batch: `batch-runner.sh --parallel N` hands each job to a headless `claude -p` worker with a clean context and self-contained prompt; sentinel-file atomic ID reservation prevents collisions (`reserve-report-num.mjs` — "never let workers compute max+1 themselves"); per-worker outputs are combined by an explicit merge step (`merge-tracker.mjs`); rate-limit exhaustion is a first-class `paused_rate_limit` state (`/Users/dwijen/repos/career-ops/batch/batch-runner.sh` lines 370-527, `modes/batch.md`). This is the most production-hardened fan-out in the survey — but each unit is one job posting producing its own report/PDF/tracker-line. **The analysts' explicit note: "no stubs/seams-style dependency decomposition like a code build needs."**
- **gstack** cross-session: designed for 10-15 parallel Conductor workspaces with per-workspace daemons and worktree isolation (`/Users/dwijen/repos/gstack/ARCHITECTURE.md`, `lib/worktree.ts`, `lib/conductor-env-shim.ts`). Parallelism at the *sprint* level — whole features per workspace, not intra-feature.

### 1c. DAG-parallel code implementation (rare; prose or shared-memory, never measured)

- **everythingclaudecode — Ralphinho RFC pipeline** is the only full statement of the operator's pattern in the survey: RFC decomposed into typed WorkUnits (deps, acceptance criteria, complexity tier) executed as a dependency DAG; each unit gets its own worktree and a tier-scaled pipeline; each stage runs in a separate context window so the reviewer never authored the code; then a **merge queue that rebases, tests, and EVICTS failures**, feeding captured conflict/test context back into the unit's next implement pass instead of blind retry (`/Users/dwijen/repos/everythingclaudecode/skills/autonomous-loops/SKILL.md`, Ralphinho section; `skills/ralphinho-rfc-pipeline/`). Caveat from the analysts: this is prescriptive prompt-markdown, not engineered machinery, and nothing in the repo measures whether it works — the genuinely engineered parts of that repo are its hooks, not its loops.
- **ruflo** is the only repo with real *code* for swarm orchestration: `task-orchestrator.ts` (decomposition, dependency resolution, parallel execution), `queen-coordinator.ts` (DelegationPlans with ParallelAssignment arrays), mesh/hierarchical/centralized topologies, Raft/Byzantine/Gossip consensus (`/Users/dwijen/repos/ruflo/v3/@claude-flow/swarm/src/`). But: "No stub/seam-based code-merge strategy — parallelism is at the task/agent level with shared memory; merge/combine is via consensus voting and shared AgentDB, not a combine step over diffs." Headline numbers (SPARC "2.8-4.4x speed") appear nowhere with methodology — marketing until traced. ~97% single-maintainer.

### 1d. Deliberate refusal (the strongest counter-signal)

- **superpowers** subagent-driven development dispatches a *fresh implementer per task* but **"explicitly FORBIDS parallel implementation subagents ('conflicts') — task execution is sequential with fresh contexts"** (`/Users/dwijen/repos/superpowers/skills/subagent-driven-development/SKILL.md`). This project has the best decomposition format in the survey (§2) and an eval-driven culture, and it still chose serial. That choice is evidence: the maintainers concluded the merge problem eats the parallel win at current tooling maturity.
- **no-mistakes** serializes concurrent pushes to the same branch by cancelling the in-flight run (`/Users/dwijen/repos/no-mistakes/internal/daemon/`); pipeline steps are strictly sequential (`internal/pipeline/executor.go`).

### 1e. Substrate (coordination primitives without orchestration)

- **planning-with-files**: single-writer rule (orchestrator alone writes the plan; workers append to their own `ledger-<agent>.jsonl`), shared monotonic tick computed as 1+max across all ledgers under flock, optional DependsOn/Owner phase fields (`/Users/dwijen/repos/planning-with-files/skills/planning-with-files/scripts/ledger-append.sh`, `templates/task_plan_autonomous.md`). "Substrate, not orchestration."
- **gstack** `lib/worktree.ts` isolated worktrees with change harvesting; `/spec --execute` worktrees pinned to explicit SHAs with `$$`-suffixed unique branches (`spec/SKILL.md` lines 1975-2050).
- **no-mistakes** patch-id fail-closed force-push guard — allow a rewrite only if every live remote commit is content-incorporated into the new head (`/Users/dwijen/repos/no-mistakes/internal/pipeline/steps/forcepush.go`). Directly reusable in any combine step where workers rebase.

### 1f. Absences (absence is a finding)

- **andrej-karpathy-skills**: parallelization — none. Pure prompt text.
- **caveman, no-mistakes, planning-with-files, mattpocock/skills, alirezarezvani/claude-skills**: analysts explicitly recorded "no task decomposition into stubs/seams," "no combine/merge machinery," or equivalent, per repo.
- **Nobody** in 11 repos measures parallel-implementation throughput or integration failure rates. Every parallel-code claim in the survey is unmeasured.

---

## 2. Interface-first decomposition: what already exists

The operator asked specifically what does interface-first decomposition today. Sightings, strongest first:

1. **superpowers `writing-plans`** — the real thing, executed serially: plans written for an engineer with "zero context and questionable taste"; every task carries exact file paths, **complete code in every step**, a **Consumes/Produces interface block**, 2-5 minute checkbox steps, a verbatim Global Constraints header, and a hard No Placeholders rule (no TBD, no "similar to Task N") (`/Users/dwijen/repos/superpowers/skills/writing-plans/SKILL.md`). Consumes/Produces *is* a seam declaration. The tasks are parallelizable by construction; superpowers just chooses not to.
2. **everythingclaudecode `blueprint`** — multi-PR plans where every step has a self-contained context brief and exit criteria so a fresh agent executes it cold, plus a dependency graph with **parallel-step detection** (`/Users/dwijen/repos/everythingclaudecode/skills/blueprint/SKILL.md`).
3. **Ralphinho WorkUnits** — deps + acceptance criteria + complexity tier per unit (`skills/autonomous-loops/SKILL.md`).
4. **mattpocock `/to-issues` + wayfinder** — slices with explicit Blocked-by edges; tickets sized to one ~100K-token session; claim-by-assignee for concurrent sessions (`/Users/dwijen/repos/skills/skills/in-progress/wayfinder/SKILL.md`). But note the doctrine: slices are **vertical tracer bullets**, and the tdd skill names *horizontal slicing* as an anti-pattern (`skills/engineering/tdd/SKILL.md`). Stub-and-seams is horizontal decomposition — this corner of the ecosystem argues against it on quality grounds.
5. **ruflo task-orchestrator** — dependency resolution in code, but seams are implicit in shared memory, not declared interfaces.

Convergent ecosystem consensus worth stating plainly: **short, fresh-context, self-contained tasks are the agreed unit of reliable agent work** (superpowers 2-5 min steps; wayfinder one-ticket-per-session; blueprint cold-executable steps; SDD fresh implementer per task). The ecosystem adopted the operator's "short task per agent" insight for *reliability, serially* — nobody has cashed it in for *throughput, in parallel* on shared code.

---

## 3. Combine-step failure modes (evidence-grounded)

The integration step is where the surveyed designs concentrate their scar tissue:

- **Conflicts are the stated reason superpowers bans parallel implementers** — one word ("conflicts") in `subagent-driven-development/SKILL.md`, from the project most willing to publish its failure evidence.
- **Eviction, not resolution.** Ralphinho's merge queue doesn't try to reconcile a failed unit at merge time; it rebases, tests, evicts, and recycles the conflict diff + test output into the unit's next implement pass (`everythingclaudecode/skills/autonomous-loops/SKILL.md`). Implication: the combine step degrades gracefully only by *re-serializing* failed work — worst case, parallelism collapses back to sequential with extra token spend.
- **The combine step is itself a long-horizon task.** It needs full-plan context, cross-unit consistency judgment, and conflict adjudication — exactly the work superpowers' measured cost decomposition says must not be cheapened: "cheapen mechanics, never judgment," with judgment points enumerated (BLOCKED diagnosis, severity calibration, false-positive adjudication) (`/Users/dwijen/repos/superpowers/docs/superpowers/specs/2026-06-10-strict-cost-sdd-design.md`). If weaker models degrade with task length, the integrator is the *last* role to hand them — the hypothesis pushes the hardest long task onto the one agent it can't cheapen.
- **Self-reported DONE multiplies.** planning-with-files' gate trusts the agent's own `Status: complete` lines (its AcceptanceCheck verification is documented but implemented in no shipped script — `templates/task_plan_autonomous.md` vs. grep of `scripts/`); no-mistakes' new-test-file tripwire misses *modified* existing tests (`internal/pipeline/steps/common_diff.go`). Three parallel implementers = three unverified completion claims arriving at once. Every surveyed verification story is same-context/self-reported; none has held-out tests.
- **Mechanical safety exists and is stealable:** patch-id incorporation checks (no-mistakes `forcepush.go`), recorded per-task BASE ranges instead of HEAD~1 ("which silently drops all but the last commit of a multi-commit task" — superpowers `scripts/review-package`), sentinel-file ID reservation (career-ops), single-writer + per-agent ledgers (planning-with-files). The *mechanics* of combining are solved; the *semantics* (cross-seam consistency, contract conformance) are not solved anywhere.

---

## 4. Weaker models vs. task length: what the evidence actually says

The operator's premise — model reliability degrades with task length, so shorter tasks admit weaker models — meets three relevant data points:

1. **Against, for general tasks:** superpowers' measured finding that "cheapest models take 2-3x the turns on multi-step work and cost more overall," plus the operational trap that an omitted subagent model silently inherits the session's most expensive one (`subagent-driven-development/SKILL.md`, Model Selection). Short wall-clock per task ≠ cheap: weak models convert saved capability into extra turns, and turns are output tokens — the researcher's own finding says output tokens are the real subscription spend.
2. **For, in one narrow regime:** the same section licenses cheap tier "only when the plan text contains the complete code (transcription)." This is the load-bearing sentence for the hypothesis: **if stubs + seams + briefs make the task transcription-adjacent, cheap-model fill-in is the documented working case.** writing-plans' complete-code-per-step format exists precisely to reach this regime.
3. **Precedent for tiering by determinacy, not just size:** everythingclaudecode's tier-scaled pipeline depth (trivial units get implement→test; large get the full 7-stage pipeline) and deep-research's cheap-models-for-broad-sweeps routing (`claude-skills/research/deep-research/skills/deep-research/SKILL.md`). Both unmeasured, but directionally consistent.

Reframe the insight accordingly: it is not "weaker models tolerate shorter tasks" but **"weaker models tolerate more-determinate tasks."** Length is a proxy; determinacy is the variable. A short-but-ambiguous stub is still a judgment task; a long-but-fully-specified one is transcription.

Cost interactions the ecosystem misses entirely (zero of 11 repos have prompt-cache awareness in their parallel designs — verified absent in gstack, superpowers, ruflo, everythingclaudecode, career-ops):

- **Fan-out multiplies cache misses unless briefs share a byte-identical prefix.** career-ops is the cautionary concrete case: `batch-prompt.md` interpolates per-job placeholders *before* ~400 lines of static rubric, defeating cross-worker prefix caching (`/Users/dwijen/repos/career-ops/batch/batch-prompt.md` lines 46-55). N parallel workers with distinct prefixes pay N full cache-miss establishments; N workers with a shared stable prefix + per-task suffix, scheduled densely within the ~5-min TTL, mostly pay discounted reads. Parallel fan-out is *more* cache-hygiene-sensitive than serial work, not less.
- **Parallelism burns the 5-hour window faster** and no surveyed orchestrator models it — career-ops at least has the `paused_rate_limit` vocabulary (reactive, manual resume); ruflo just shipped env vars to *hide* its misleading cost segment on subscription plans (`v3/@claude-flow/cli/src/init/statusline-generator.ts` ~line 58).
- **~30x same-task variance (researcher's measurement) compounds across a fan-out:** with 3 parallel units, the batch completes at the max of three heavy-tailed draws. Open-loop budgeting fails harder in parallel; ruflo's seeded-bootstrap significance gating (`harness-improvement-ledger.ts`) and gstack's hit-rate specialist gating are the only closed-loop spend controls sighted, neither applied to implementation fan-out.

---

## 5. What the operator's project adds

Mapping cc-agent-harness assets onto the verified gaps:

| Gap (verified across 11 repos) | Harness asset |
|---|---|
| Seam determinacy is asserted, never gated — superpowers interviews until the agent believes it understands; no machine-checkable readiness anywhere | **plan-build's determinacy interview + ratified plan ledger** (`python3 -m harness.planning ready` gate). Stub-and-seams lives or dies on interface determinacy; this is the only surveyed mechanism that *refuses to build* on an indeterminate spec. |
| Parallel completion claims are self-reported; zero implementer/validator context separation in any repo | **BLIND validation.** And it composes unusually well with stubs: seams are declared *before* implementation, so the validator can author held-out contract tests per seam from the interface spec alone, in the vault, before any implementer runs. The combine step then verifies on a clean checkout against tests no implementer ever saw. Reward-hacking surface shrinks as fan-out grows instead of multiplying. |
| No parallel design is cache-aware; career-ops actively defeats prefix caching in its fan-out | **Cache hygiene:** byte-identical shared brief prefix across the 3 implementers + dense dispatch within the TTL turns fan-out's biggest cost amplifier into a shared discount. Only planning-with-files shows convergent awareness (KV-cache-stable ledger summaries, pointer-not-payload — `scripts/ledger-summary.sh`, `docs/cache-safe-diagram.md`) and it isn't an orchestrator. |
| No orchestrator models subscription windows; fan-out accelerates window burn | **Rate-window awareness + closed-loop control at task boundaries:** schedule the fan-out as a unit against remaining window, park at `paused_rate_limit`-style boundaries, wake on reset. |
| Fat resumes / lost controllers; superpowers calls a lost progress ledger "the single most expensive failure observed" | **Disk-is-the-memory:** per-unit briefs and combine-step state as ledger files means an evicted or crashed unit re-dispatches from disk, thin. |

Also directly importable substrate, with sources: merge-queue-with-eviction + conflict-context recycling (everythingclaudecode), patch-id merge guard (no-mistakes), per-task BASE recording (superpowers `review-package`), sentinel ID reservation (career-ops), single-writer/per-agent-ledger discipline (planning-with-files), Consumes/Produces block format (superpowers `writing-plans`).

---

## 6. Verdict on the operator's hypothesis

**Qualified yes — but the qualification is most of the answer, and the naive version is a bad idea.**

The naive reading — "stub it, fan out 3 authors, combine" as a general acceleration for ordinary features — is contradicted by the strongest evidence in the survey: the most rigorous project (superpowers) built the exact decomposition format required and then *banned* parallel implementers over conflicts; the tracer-bullet doctrine (mattpocock) treats horizontal slicing as an anti-pattern; the only end-to-end statement of the pattern (Ralphinho) is unmeasured prose whose own design concedes the point by making eviction-and-reserialize its failure path; and the combine step concentrates precisely the long-horizon judgment work the cheap-model thesis cannot cover. Add the unmodeled costs — N× cache-miss amplification without prefix discipline, faster window burn, max-of-heavy-tails completion time under 30x variance — and naive stub-and-seams likely costs more tokens for modest wall-clock gain while multiplying unverified DONE claims.

The defensible version is narrower and genuinely open territory:

1. **Gate the fan-out on seam determinacy, not task size.** Only parallelize units whose Consumes/Produces contracts are ratified, compile-checkable, and specific enough that implementation is transcription-adjacent — the one regime where cheap-model fill-in has documented support (superpowers Model Selection). plan-build's ready-gate is the natural admission control; nothing in the ecosystem has one.
2. **Author held-out seam-contract tests blind, before dispatch.** Interfaces-first makes blind validation *cheaper*, not harder: the validator needs only the ratified interfaces, and the combine step becomes "clean checkout + vault tests + patch-id-guarded merge" rather than an LLM judgment call. This converts the survey's universal weakness (self-reported completion, ×N under fan-out) into the harness's differentiator.
3. **Keep the integrator expensive and serial.** One strong-model combine task, merge-queue-with-eviction semantics, conflict context recycled into the evicted unit's re-dispatch. Never cheapen judgment.
4. **Make the fan-out cache- and window-shaped.** Shared byte-identical brief prefix, dense dispatch inside the TTL, whole-fan-out scheduling against the remaining window, closed-loop cutoffs at unit boundaries.
5. **Expect modest N.** The evidence supports 2-3 genuinely independent units per feature at best (caveman scouts, the operator's own "3 authors" instinct); the serial fraction — determinacy interview plus integration — bounds the speedup, and for coupled features it will often round to 1, which is superpowers' answer.

The "weaker models" clause should be restated before it drives design: **determinacy, not brevity, is what licenses a weaker model.** Short-but-underspecified stubs given to cheap models will burn the saved capability as extra turns (= output tokens = real window spend) and hand the blind validator a queue of contract violations. If plan-build can reliably manufacture transcription-grade stubs, the hypothesis holds and nobody in the ecosystem is positioned to ship it; if it can't for a given feature, the evidence says run superpowers-style serial SDD and don't force it. Either way, the measurement itself — parallel vs. serial on the same ratified plan, N≥5 runs per arm given 30x variance — would be the first real data anyone in this ecosystem has produced on the question, and is publishable regardless of which way it comes out.
