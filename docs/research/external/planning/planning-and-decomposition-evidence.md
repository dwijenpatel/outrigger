# Planning & decomposition — the evidence base

What the research establishes about whether an LLM can plan, how to decompose work, what plan
representation to use, when planning ceremony pays, and whether a plan can be evaluated before
execution. The spec-elicitation front-half, shipped-product survey, brownfield gap, and the
consolidated harness design mapping are the companion document,
[spec-determinacy-and-practice.md](spec-determinacy-and-practice.md).

**Provenance:** 2026-07-10 deep-research pass. Six Opus 4.8 clusters over ~40 primary sources
(most read full-text): can-LLMs-plan (Kambhampati/ASU line), decomposition methods, classical
planning + representations, spec-driven/requirements-engineering, shipped products, and a
does-it-pay/brownfield/evaluation synthesis. Extends the practitioner-repo view in
[../landscape/ecosystem-mining/spec-elicitation-and-planning.md](../landscape/ecosystem-mining/spec-elicitation-and-planning.md),
which already found the *asking* mechanics commoditized and the *exit* side (determinacy,
traceability) empty. Tags per corpus convention; every headline number is author-run unless a
tier says otherwise, and single-source magnitudes are flagged.

---

## 1. Can an LLM be trusted to plan? — generation vs validity vs verification

The most-replicated result in the planning literature, and the strongest theoretical
ratification the harness has received: **an LLM is no better at verifying a plan than at
generating one, and self-critique of a plan is net-negative.** Separate the three capabilities:

- **(a) Generate a *plausible* plan** — solved and improving fast. Frontier reasoning models
  produce fluent, reasonable-looking plans; o1 hits 97.8% on plain Blocksworld. `[E]`
- **(b) Generate a *correct/valid* plan with a guarantee** — **not** solved. Autonomous validity
  was ~12–35% in the GPT-4 era (PlanBench, arXiv 2206.10498, NeurIPS 2023); even o1 is
  non-robust (collapses to 23.6% on 20–40-step plans, 37–53% on obfuscated "Mystery
  Blocksworld") and offers **no guarantee**, while classical Fast Downward solves 100% cheaply
  (arXiv 2409.13373). The obfuscation cliff — GPT-4 solved 210/600 plain Blocksworld but
  **1/600** renamed — is the reasoning-vs-retrieval smoking gun: apparent planning is largely
  pattern-matching. `[E]`
- **(c) Verify/critique a plan** — the weakest, and the decisive finding. GPT-4 self-critiquing
  its own Blocksworld plans scored **55/100 vs 88/100 with a sound external verifier (VAL)**,
  with an **84.45% false-positive rate** — the LLM-verifier waves invalid plans through as valid
  (arXiv 2310.08118). On graph coloring, critique *content* was "largely irrelevant" to
  improvement — gains came from resampling and an external check, not from the critique (arXiv
  2310.12397). Self-verification limitations replicate across Game-of-24, graph coloring, and
  STRIPS (arXiv 2402.08115). `[E]`

**LLM-Modulo** (Kambhampati et al., arXiv 2402.01817, ICML 2024 position) is the prescription:
a **Generate–Test–Critique** loop where the LLM *generates* candidates and *reformulates* them
into critic syntax, a **bank of sound external critics** (VAL, compilers, simulators) is the
gate, LLM "soft critics" cover only non-verifiable style, and the human is consulted **once per
domain/problem, never in an iterative prompt loop**. Verbatim: *"LLMs cannot verify plans and
thus cannot improve by self-critiquing."*

**Harness mapping — this is the single best-supported design choice in the corpus.** The refusal
to let the plan-authoring LLM self-approve, and the requirement of an external gate
(static-sound preflight + human ratification), is exactly LLM-Modulo. The blind
generator/verifier separation (test-author and validators get spec-only, never the implementer's
reasoning) is the "don't let the generator be the verifier" split; the held-out executable test
is a genuinely *sound* verifier of "code satisfies this test" — the software analog of VAL.

**The residual risk, precisely located.** The preflight is sound **only over the decidable
structural predicates it encodes** (DAG acyclicity, floors×touches, coverage) — it is
VAL-for-plan-*structure*, not VAL-for-plan-*semantics*. It cannot decide: does the decomposition
*cover* the goal? are the dependency edges the *right* edges? are there cross-task
subgoal/resource interactions (task B assumes an interface task A was meant to create but A's
spec doesn't require it)? That last is "phase-2" reasoning — the combinatorial
subgoal-interaction sequencing where every paper says LLMs are weakest — **and no static check
fires there.** The only semantic verifier left is the human gate, and a CSCW study warns it is
not sound: 3/48 assisted planners accepted incorrect LLM suggestions, 2 shipped them
(automation bias); assisted and unassisted groups were statistically indistinguishable (arXiv
2305.15771). **This is exactly our own P3-2** — a ratified plan that was internally
floor-inconsistent, waved through by both the artifact-validator and the human. The literature
explains why the human gate alone can't be relied on to catch it. *Bias flag:* the six
can-LLMs-plan papers are all from one lab (ASU/Kambhampati); the self-verification result is
independently corroborated on a distinct domain (graph coloring), the framing is that group's
thesis.

## 2. Decomposition methods — upfront vs as-needed, and the representation

Central result (**ADaPT**, arXiv 2311.05772, NAACL 2024 Findings): a **fixed upfront plan can be
worse than no plan.** "Plan-and-Execute" scored **17% vs a reactive ReAct baseline's 32%** on
WebShop — a frozen plan *halved* success; upfront decomposition delivered zero or negative value
on two of three agentic benchmarks, and all the wins came from **as-needed recursion on
executor failure** (ALFWorld 43→72, TextCraft 19→52). The depth of decomposition actually used
scales with local task complexity (k_max 1.9→2.8 as recipe depth 2→4). `[E]`

The planning survey (arXiv 2402.02716) states the tradeoff cleanly:
- **Decomposition-first** (HuggingGPT, Plan-and-Solve): stronger sub-task↔goal correlation, less
  task-forgetting — *but* "since the sub-tasks are predetermined… **one error in some step will
  result in failure**" unless an adjustment mechanism exists.
- **Interleaved** (ReAct, ADaPT): dynamically adjusts on feedback, fault-tolerant — *but* long
  trajectories drift and hallucinate, "deviating from the original goals."

**Representation** (from decomposition methods + classical planning, §3):
- **Linear list** (Plan-and-Solve, Least-to-Most): cheapest; encodes ordering so earlier results
  feed later; buys compositional generalization (Least-to-Most: 99.7% on SCAN vs ~16% CoT); no
  parallelism, no dependency semantics, no failure branching.
- **Task DAG** (HuggingGPT): explicit dependency edges + resource passing → parallelism and
  correct data flow; the natural structure for build work. **Cost:** upfront DAG accuracy is the
  ceiling — GPT-4 tops out at **~67% F1 on graph-structured plans**, and the authors warn edge
  errors cascade into loops.
- **Tree** (Tree of Thoughts, RAP): edges are *alternatives to search over*, not dependencies to
  satisfy; a value function/world model prunes and backtracks (ToT: 74% vs 4% CoT on Game-of-24;
  RAP: 0.88 vs 0.02 CoT on Blocksworld). Expensive (b×depth calls) and needs a cheap
  verifier/simulator — a *plan-selection* mechanism for a hard task, **not** a whole-project
  decomposer (the survey files ToT/RAP under "Multi-Plan Selection," a different axis).

**Harness mapping.** The DAG is the right representation, and tree-search is an orthogonal
technique to apply *within* a hard, verifiable task — they are complementary. On upfront vs
as-needed, the harness already sits on the literature-endorsed synthesis: a **determinate
walking-skeleton phase 1** (decomposition-first applied only where it is safe — the
well-specified regime where it demonstrably helps) + **provisional later phases refined
just-in-time** (honoring ADaPT's "don't freeze the far horizon") + **re-planning patches** (the
survey's mandatory "adjustment mechanism"). The one refinement the evidence prescribes: ADaPT
shows the depth needed **varies per task within a phase**, so the re-plan trigger should be
**task-level failure/uncertainty-driven, not merely phase-gated**.

## 3. Classical planning & the sound-checker pattern

The formal-methods lineage supplies both the pattern the harness already follows and the checks
it is missing.

- **LLM+P** (arXiv 2304.11477): LLM translates NL→PDDL, a **sound & complete** classical planner
  solves, LLM renders back. The LLM never plans — it emits a formal artifact a sound tool
  validates. Representative: Blocksworld 20%→90%, raw LLM mostly infeasible (no precondition
  reasoning). This is the harness's exact shape — with one asymmetry: **LLM+P's checker *solves*
  (proves a valid plan exists in the model); the preflight only *checks structural invariants*.
  The harness splits VAL across ratification-time (static structure) and build-time (the blind
  validators verify goal-achievement per task)** rather than proving validity up front. `[E, T2]`
- **World-model authoring** (arXiv 2305.14909, NeurIPS 2023): use the LLM to author the *domain
  model* (reviewed and corrected by humans up front), then plan soundly — "make the volatile
  artifact the reviewable model, keep the executor sound." The philosophical match to
  fix-the-plan-at-ratification. `[E]`
- **HTN** (Erol-Hendler-Nau 1994; SHOP2, JAIR 2003): hierarchical decomposition of compound
  tasks into subtask networks via a method library. Sound & complete procedures exist (UMCP),
  but **general HTN plan-existence is undecidable** — only restricted forms (totally-ordered,
  acyclic) are decidable, which is why practical systems restrict form. **ChatHTN** (arXiv
  2505.11814, 2025) is the closest analog to our checker: symbolic HTN runs normally, queries an
  LLM only when no method matches, and stays **provably sound** by inserting a **verifier task** —
  a synthetic primitive whose preconditions equal the compound task's declared effects, executed
  after every decomposition; if the effects don't hold, it backtracks. That is precisely our
  blind validators (runtime) + coverage invariant (static). `[E/T1 theory, T2 ChatHTN]`
- **Partial-order planning & plan stability.** A task DAG *is* a partial-order plan: unordered
  tasks are provably parallel, and each ordering edge should be **justified by a causal link**
  (producer→consumer), which `touches` file-globs only proxy. Fox et al. (ICAPS 2006) established
  **plan repair beats replan-from-scratch on stability** (fewer changes, competitive speed) —
  the academic warrant for locality-of-repair and for the harness's soft `may-be-invalidated-by`
  edges as a declared blast-radius graph. **VAL** (Howey et al., ICTAI 2004) defines validity as
  executability (preconditions hold at each step) + goal-achievement, binary, naming the first
  failing action — the model for structured preflight feedback. `[E/T1]`

**The hardening this cluster prescribes** (priority order), all decidable and sound:
1. **Per-task `requires`/`provides` interface symbols.** Today `touches` globs are a file-level
   proxy. Declared interface symbols let the preflight verify **dependency-order executability**
   (every task's `requires` is `provides`-d by a hard-edge ancestor — no open preconditions).
   This is POP causal-link checking / STRIPS reachability, fully decidable, and upgrades the DAG
   from "asserted edges" to "edges justified by producer→consumer links." **Cluster 1 reached
   the identical recommendation from LLM-Modulo verification theory** — two lenses converging on
   the same missing check is strong signal.
2. **Type the coverage check** (every assertion's owner *provides* the interface the assertion
   ranges over — the static half of ChatHTN's verifier task).
3. **A dry-run symbolic executor** over declared effects (mini-VAL): topologically execute tasks
   over symbolic state, confirm the goal (full assertion set) is reached. This is what would make
   the preflight solver-grade rather than well-formedness-grade.
4. **Structured, category-tagged preflight feedback** so ratification failures are LLM-actionable
   (arXiv 2305.11014's debugging-loop lesson: automated structured feedback is the largest lever).

## 4. Decomposition quality, formalized — the "transcription" predicate

The corpus's standing open question ("is 'determinate enough that implementation is
transcription' formalizable?") gets a concrete, mechanical answer.

The theory: **information hiding** (Parnas 1972 — each module hides one likely-to-change design
decision behind a stable interface), **coupling & cohesion** (Constantine — good boundaries
expose only data/message coupling and are functionally cohesive), **connascence** (Page-Jones
1992 — the most formalizable coupling model: keep strong/dynamic connascence *inside* a
boundary, let only weak/static Name/Type connascence *cross* it), and **seams** (Feathers 2004 —
a boundary is independently testable iff it is a seam with a determinate enabling point; **this
is a necessary precondition for blind validation**). All T1/T3 (established design theory, not
empirically validated as predictive metrics).

The synthesis — **transcription-readiness as a checkable predicate:**

> A task is transcription-ready ≡ (cross-boundary connascence ⊆ {Name, Type}) ∧ (every volatile
> decision is spec-fixed or task-internal).

Implementation is *design*, not transcription, exactly when a decision is **neither fixed in the
spec nor hidden inside the task** — it leaks across the boundary as strong/dynamic connascence,
forcing the implementer to make a cross-cutting choice others depend on. Both conjuncts are
**statically checkable given the §3 interface model** (typed `requires`/`provides` + typed
assertions), turning a judgment call into a preflight lint.

And a **mechanical decomposition-quality predictor** with a quantitative bridge: cohesion-aware
partitioning (arXiv 2606.00953, `[measured, single-source]` — direction usable, numbers
unverified) partitions the code-dependency graph by **Louvain modularity**; modularity >0.6 →
~2–3× parallel speedup, <0.4 → 1.2–1.5× *slowdown* from coordination overhead. A task boundary
is good iff it cuts a **low-coupling seam** — the graph-theoretic restatement of Parnas. A
plan-time **modularity check over the `touches` dependency graph** is the decomposition-quality
analog of the floors×touches preflight, and unlike an LLM plan-judge (§6) it is mechanical and
sound: two tasks whose `touches` sets are dependency-entangled are a bad boundary regardless of
how the ledger is drawn.

## 5. Does planning ceremony pay? — the moderated rule

The corpus's apparent contradiction — plan-then-code **+25.4% relative Pass@1** ("Self-planning
Code Generation with LLMs," Jiang et al., arXiv 2303.06689, ASE 2024; peer-reviewed) vs mandated
self-authored TDD **−3.6pp at +55% cost** (programbench-bench) — dissolves into moderator axes,
each pinned by external evidence:

| Moderator | Pays when… | Hurts when… | Evidence |
|---|---|---|---|
| **Task structure** | symbolic / sequential / decomposable | flat, commonsense, single-step | "To-CoT-or-not," arXiv 2409.12183, ICLR 2025: CoT gives +14% symbolic, ~0 non-symbolic (100+ papers) |
| **Horizon** | multi-step / long | short (overhead > benefit) | ADaPT; overthinking-on-simple |
| **Authorship / info asymmetry** | plan carries info the executor lacks (**human-ratified, provided ground-truth**) | **self-authored + self-graded** (overfits) | provided-tests +12.8% MBPP vs mandated-TDD −3.6pp |
| **Strategy alignment** | plan matches the model's grain | extra "reasonable" phases fight it | plan-compliance study (16,991 trajectories): extra early phases *degrade* success |
| **Model strength** | weaker model (needs scaffold) | strong LRM in-distribution | o1 on PlanBench |
| **Cost structure** | plan authored once, executed cheaply | ceremony re-bills full context per micro-step | programbench-bench (+112% input tokens) |

**One-sentence rule:** *plan first when the task is structured and non-trivial-horizon and the
plan is authored/verified by a source with more information than the executor and aligned to the
executor's strategy; skip or minimize planning when the task is short/flat, or when the "plan"
is self-authored, self-graded, misaligned, or paid for by re-billing context each step.* The
harness sits in the paying cell by construction (human-ratified = asymmetric info; structural
tasks; decompose-conditioned-on-regime) **provided** it does not slide into the harmful cell by
mandating implementer-side ceremony — which the no-spend-list / lever-discipline guards.

**The empirical anchor the whole subtopic turns on** (arXiv 2604.12147, 16,991 trajectories,
SWE-bench Verified+Pro): removing the plan hurts, but **following a bad/incomplete plan hurts
more than no plan at all.** Plan *presence* is table stakes; plan *determinacy* is the lever.
That reframes the harness's determinacy gate from "nice rigor" to "the thing that prevents
active harm."

## 6. Plan evaluation — mechanical yes, semantic mostly no

Can a plan's quality be gated *before* execution? Only in two sound forms:

1. **Mechanical structural checks** — the VAL-analog for a domain with no formal action model:
   `plan_ready`, acyclicity, coverage, floors×touches, and the proposed interface/modularity
   checks (§3–4). Zenith enforces the same class (depends_on resolution + acyclicity + coverage)
   `[code]`. Necessary, not sufficient — they certify well-formedness, not goal-achievement.
2. **A sound external semantic signal** — the **human ratification gate** (the only source with
   information the plan-authoring LLM lacks: true intent), optionally fed by **fresh-context
   adversarial review** (Zenith's contract-review; better than self-critique because the reviewer
   never saw the authoring reasoning) whose findings are **advisory into the human gate, never an
   autonomous pass**.

An **LLM-as-plan-judge autonomous gate is not sound** — it imports exactly the
self-verification-collapse / false-FAIL / self-preference pathologies O0 spends heavy machinery
to remove (§1; arXiv 2402.08115, 2402.01817; the corpus's existing false-FAIL ledger). The
determinacy bar ("a spec-only test-author could write held-out tests with no guessing") is the
right *target*; the **executable determinacy probe** (dispatch a spec-only agent, count its
questions) is the closest thing to a *sound* semantic check because it measures a **downstream
consumer's confusion** rather than asking a model to grade itself — see
[spec-determinacy-and-practice.md §2](spec-determinacy-and-practice.md) for its prior art and
novelty.

## Corrections & evidence flags

- **arXiv 2303.06689** is titled *"Self-planning Code Generation with Large Language Models"*
  (Jiang et al., ASE 2024 / ACM TOSEM); the corpus cites it by ID only, so no committed title
  error — the correct title is now attached. The **+25.4% relative Pass@1** (vs direct
  generation; +11.9% vs CoT) stands; it is function-level (HumanEval/MBPP), not repo-scale.
- **Single-source magnitudes to import as direction only:** modularity thresholds and
  speedup/slowdown (2606.00953, also summarizer-read); all LLM+P/HTN/Plansformer benchmark
  numbers (author-run); ADaPT/ToT/RAP deltas (author-run, re-implemented baselines).
- **Model-generation scoping:** the can-LLMs-plan numbers are GPT-3.5/4/o1-era on formal PDDL;
  the *self-verification-is-unreliable* finding is domain-general and survives the
  reasoning-model transition, but raw generation-accuracy numbers do not transfer to software and
  are a caution, not a prediction. Retest on any new frontier model before leaning on a
  percentage.
