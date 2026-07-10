# Spec determinacy, shipped practice, and planning for the harness

The front-half of planning (eliciting and formalizing a determinate spec), what shipped
products actually do, the brownfield gap the corpus named as its biggest blind spot,
re-planning discipline, and the consolidated design mapping. The academic evidence base (can
LLMs plan, decomposition methods, classical planning, does-it-pay, plan evaluation) is the
companion, [planning-and-decomposition-evidence.md](planning-and-decomposition-evidence.md).

**Provenance:** 2026-07-10 pass (same six Opus 4.8 clusters; see companion header). Extends the
11-repo practitioner study in
[../landscape/ecosystem-mining/spec-elicitation-and-planning.md](../landscape/ecosystem-mining/spec-elicitation-and-planning.md)
with the requirements-engineering literature, first-party product docs, and the
brownfield/localization literature. Tags per corpus convention.

---

## 1. Requirements engineering — ambiguity is the wrong frame; underspecification is the right one

The reframe that reorganizes the harness's whole "typed ambiguity taxonomy" idea:

**There is a mature, adoptable RE ambiguity taxonomy** — Berry & Kamsties (2004) → Gervasi et
al. (2019): **lexical / syntactic / semantic / pragmatic-referential / vagueness / generality /
software-engineering** ambiguity, independently re-confirmed by Orchid's lexical/syntactic/
semantic/vagueness split (§2). `[PR]` But it is a **linguistic-mechanism axis** (does present
text admit multiple readings?), which is **orthogonal** to the harness's **behavioral-domain
axis** (boundary / permission / error-path / invariant / tenancy / environment / convention).

The load-bearing observation: **most of the harness's observed failure classes are OMISSION, not
ambiguity.** Boundary, error-path, invariant, tenancy, environment gaps are usually *silence* —
the spec says nothing — which is **ISO/IEC/IEEE 29148 set-level incompleteness**, not
multiple-readings ambiguity. So the harness's "typed ambiguity taxonomy" is more accurately a
**typed *underspecification* taxonomy**, and it should be pitched against the completeness /
underspecificity literature (Ambig-SWE, ISO-29148 set-completeness), not only the linguistic
ambiguity literature. The recommendation: type gaps on **two axes** — *linguistic mechanism*
(is present text multi-readable?) × *behavioral domain* (which behavior is undetermined?).
Convention and permission span both; the rest are predominantly omission.

Two RE ideas that are direct theoretical parents of the harness's approach:
- **Nocuous vs innocuous ambiguity** (Chantree et al., 2006–2008, `[PR]`): an ambiguity matters
  only if real readers **actually diverge** on interpretation. Dispatch an independent reader; if
  it diverges or asks, the ambiguity is *nocuous*. This is the theoretical parent of the
  determinacy probe (§2).
- **ISO 29148's per-requirement vs set-level split**: *unambiguous/singular* are per-requirement;
  ***complete*/consistent** are set-level. The harness's determinacy is a **set-level** property,
  systematically under-served by the ~41 sentence-level requirements-smell tools (Femmer's
  Smella etc.). `[PR/standard]`

**EARS** (Mavin et al., RE'09, `[PR]` but inventors on one internal Rolls-Royce corpus) is a
*syntactic constraint with temporal ordering* (built on Event-Condition-Action), **not** a
formal semantics. Its five templates + complex (ubiquitous / WHEN / WHILE / WHERE / IF-THEN)
force authors to name preconditions and triggers explicitly, and its own case study shows
per-requirement gains (avg 36.9→25.6 words; complexity/omission-instances/duplication/
untestability driven to zero on a log scale). **But the authors explicitly disclaim any effect
on omission/completeness** ("the claim that omissions have been eliminated needs to be treated
with caution… no evidence that other missing requirements have been captured"), and a 2024
RE-journal benchmark states there is "a lack of empirical evidence for [template systems']
effects." **EARS ⊂ determinacy:** it makes each sentence well-formed and testable and surfaces
missing preconditions, but does not touch set-level completeness — which is exactly the property
the harness cares about. Treat it as a formatting discipline, not a determinacy guarantee.

**LLMs are markedly better at *using* clarification than at *detecting* their own ambiguity** —
the finding that most shapes the design. Self-flagging precision is **~50%** with localization
<23% (Orchid); baseline detection is "only slightly above chance." This directly undercuts any
design that trusts the authoring model to mark its own gaps (Spec Kit's self-flagged
`[NEEDS CLARIFICATION]` markers are exactly this weak path) and argues *for* an **independent,
adversarial** reader. `[pre][M]`

## 2. Measuring determinacy — the probe's prior art and what is genuinely novel

Directly on-thesis measured evidence that under-determination *costs*, and that the harness's
probe composes validated pieces:

- **Orchid** (arXiv 2604.21505, `[pre][M]`, verified): 1,304 function tasks × 5,216 ambiguous
  variants. Injecting ambiguity drops pass@1 by **avg 7.22pp, up to ~29–32pp**; human
  interpretation-conflict rises **14%→28%**; and LLMs can't reliably self-detect it (~50%
  precision).
- **Ambig-SWE** (arXiv 2502.13069, `[pre][M]`) — **the closest measured analog to the harness's
  probe.** Underspecified SWE-bench-Verified issues drop resolve rate **~29pp** (Claude 3.5
  Sonnet 66%→38%); **interactive clarification recovers 80–89%** of the gap. It **counts
  clarifying questions** (avg 2.61–6.02/task) — but as a *task-recovery* mechanism, not as a
  determinacy score gating the build. Two underspecification types: informational vs
  navigational.
- **The Specification Gap** (arXiv 2603.24284, `[pre][M]`): coarse L0–L3 spec ladder (full
  docstrings → bare signatures); two-agent integration accuracy **58%→25%** across the ladder,
  single-agent 89%→56%; AST-based conflict detection 97% precision at the weakest level. *(⚠
  Correction: an intermediate summary confabulated a "specification entropy / determinacy index"
  for this paper — no such metric exists; cite only the verified L0–L3 numbers.)*
- **ClarifyGPT** (arXiv 2310.10996, `[pre][M]`): detects ambiguity via a **code-consistency
  check** — sample N solutions; if their *test behavior* diverges, the spec is ambiguous — then
  asks targeted questions (GPT-4 71%→81% on MBPP-sanitized). This is a near-relative of the
  determinacy probe: divergence among independent attempts reveals the gap.
- **TiCoder** (arXiv 2208.05950 / TSE'24, `[PR][M]`): test-driven intent formalization lifts
  pass@1 by **+45.73% avg** within 5 interactions — the strongest support for the harness's
  "spec-only test-author writes held-out tests" bar (caveat: function-level).

**Is "dispatch a spec-only agent, count its questions, require two clean sweeps" novel?**
**Yes in formulation.** No prior art uses an *independent spec-only agent's question-count as a
determinacy score/gate* for a specification before build, nor imposes a two-clean-sweep
acceptance criterion. The ingredients are all individually validated — nocuous-ambiguity-as-
reader-divergence (Chantree), consistency-probe (ClarifyGPT), question-counting under
underspecification (Ambig-SWE), forced unresolved-gap markers as a pre-build gate (Spec Kit) —
which is a *strength*: it is a novel composition of validated mechanisms, not a leap. The
strongest empirical justification is **Orchid's ~50% self-detection precision**, which says
self-flagging is inadequate and an **independent adversarial reader** is the right instrument.
The harness's use of a *separate, adversarial, spec-only* reader — whose confusion falsifies
determinacy — is the empirically-motivated improvement over every shipped self-flagging scheme.

## 3. Shipped product practice — ten products, one convergent design

Extends the 11-OSS-repo study with first-party **products**. The OSS study's two gaps (no
machine-checkable determinacy exit bar; no spec-to-test traceability) **hold across every shipped
product too.** `[FP]` unless tagged.

The market converged hard on **generate plan → human eyeballs it → execute**:

| Product | Interrogates? | Gates execution? | Determinacy criterion | Measured outcome |
|---|---|---|---|---|
| Claude Code plan mode | iterative, optional | human approve + extra confirm | none | none |
| Claude Code `/goal` | no (condition only) | **separate Haiku evaluator per turn** | measurable end-state (LLM-judged) | none |
| Devin | light ("implementation questions") | 30s then **auto-proceeds** | none | none |
| Cursor Plan Mode | yes (clarifying Qs) | human review | none | self-noted low adoption |
| Windsurf/Cascade | no (continuous) | human review | none | none |
| OpenAI Codex PLANS.md | **no** (autonomous) | human "Implement plan" | aspirational "self-contained" | 7-hr-run anecdote |
| Kiro (AWS) | yes, up front (EARS) | soft checkpoints (**Quick Plan skips**) | none (Fowler: non-blocking) | "4× on 4+ tasks" `[V]` |
| GitHub Spec Kit | `/clarify` optional | soft AI checklists (**"no 100% guarantee"**) | `[NEEDS CLARIFICATION]` + completeness checklist (self-checked) | ~10× slower `[PR]` |
| Google Antigravity | reviewable (inline comments) | **approval-gated** | none | none |
| Tessl | adaptive depth | none explicit | none (**pivoted away Jan 2026**) | none |

Not one has a machine-checkable determinacy bar, none blocks the build on a content-bound stamp,
none has preflight — the trio the OSS study found unique now reads as unique across products too.
A Thoughtworks/Fowler review calls the leading spec tools "merely suggestive… a false sense of
control," and its trials show agents **ignoring specs, generating unrequested duplicate
features, and non-determinism**, with a small bugfix ballooning to "4 user stories with 16
acceptance criteria" — *Verschlimmbesserung* (improving-into-worse). Against-evidence is real:
Spec Kit measured **~10× slower** than iterative with no quality edge (Scott Logic); Tessl
*pivoted away* from spec-as-source in Jan 2026 (its regeneration engine was closed-beta,
non-deterministic). **No controlled measurement that spec-first beats prompt-then-code on agent
outcomes was found** — the benefit is universally asserted; the indirect measured support is the
codegen-with-ground-truth-tests literature (§2) and the "incomplete plan worse than none" anchor
([companion §5](planning-and-decomposition-evidence.md)).

Two shipped ideas validate the harness's direction and are worth importing: Claude Code
`/goal`'s **worker/evaluator split** (a fresh model judges done — the harness already
generalizes this via blind validators; a cheap per-turn condition-check is a small addition),
and Kiro's **dependency-wave parallel execution** (the ledger already has a DAG; concurrent
independent-task firing is a latency win). Spec Kit's **constitution** (durable cross-task
principles read before every task) is the prose analog of the harness's conventions/floors —
gated, in the harness's case.

## 4. Brownfield — the corpus's biggest named gap

The design explicitly non-goals large brownfield codebases (§1: "the phased-ledger model is
greenfield-shaped"). The external literature is large, convergent, and it **reframes what
"planning" even means** when the code already exists.

**In brownfield, planning ≈ localization** ("where do I change") — the dominant sub-problem, and
genuinely unsolved at fine grain:
- **Agentless** (arXiv 2407.01489, FSE): a *fixed, non-agentic* localize→repair→validate
  pipeline with hierarchical localization (file → class/function via a skeleton → edit-line)
  beats autonomous agents on SWE-bench (Lite 32% at $0.70/issue; Verified 38.8%) — and its
  against-interest thesis is *"Do we really have to employ complex autonomous software agents?"*,
  flagging agent failure modes (30–40 turns, "lack of control in decision planning," can't filter
  misleading info). The brownfield state of the art says the planning that matters is a **fixed
  localization pipeline, not an LLM authoring a task DAG.** `[E]`
- **LocAgent** (arXiv 2503.09089, ACL 2025): graph-guided localization hits ~80/70/60% Acc@5 at
  file/class/function on SWE-bench but **35/28/22%** on harder repos — localization **degrades
  sharply with granularity**, and "success improves significantly with better localization." The
  fine-grained "where" is the bottleneck. `[measured]`
- **CodePlan** (arXiv 2309.12499, Microsoft, FSE 2024): repository-level coding *as* planning,
  where the plan is **synthesized from the code's own dependency graph** (incremental dependency
  analysis + change-may-impact + adaptive planning emitting change *obligations*; a plan-graph
  node = ⟨Block, Instruction, status⟩). 5/6 repos pass validity vs 0/6 baselines. The antithesis
  of the greenfield ledger: **you do not author a task list and then find the code — the existing
  dependency graph generates the task list, and the plan grows as may-impact discovers
  obligations** (a built-in re-planning loop). `[E]`
- Supporting: **aider's repo map** (tree-sitter symbol graph + PageRank + token budget) is the
  standard "index the repo so the planner can see structure" artifact — the harness has **no
  analog** (greenfield needs none); **blast-radius / change-impact** = BFS along *reverse*
  dependency edges (CodePlan's may-impact under its SE name); **constraint-from-existing-code** —
  LLMs "invent or hallucinate non-existent APIs," mitigated by retrieval grounding
  (De-Hallucinator +23–61% API-recall) since the design space is bounded by existing signatures
  and invariants. `[folklore/measured]`

**What greenfield-shaped machinery does and does NOT handle:**

| Harness mechanism | Greenfield | Brownfield failure |
|---|---|---|
| Walking skeleton / wedge | small end-to-end slice you *create* | no skeleton — the system runs; the "wedge" is *finding the seam in existing code* |
| Phased ledger + `deps` | build order over files-to-be-created | task DAG must be **derived from** the existing dependency graph, not authored |
| `touches` globs | trivial — you know what you'll create | **this IS the localization problem** — can't be authored without repo exploration; wrong `touches` → floors preflight checks the wrong surface |
| Risk floors × profiles | static, decidable at plan time | the *real* touched set is discovered mid-edit via blast-radius; floors must key off may-impact |
| Closure gate vs frozen snapshot | plan is ground truth | the *codebase* is ground truth; a snapshot can't encode "don't break the 200 existing call-sites" |

**Brownfield planning would need** (none exist in current machinery): a **localization-first
phase** that *produces* `touches` (Agentless/LocAgent-style); a **repo index** as a planning
input (aider-style); **blast-radius/may-impact as a first-class plan artifact** so floors and
validation key off discovered impact, not a plan-time guess; and **constraint-from-existing-code**
(existing API/signature/invariant capture) in specs. This is a coherent extension, not a patch —
brownfield is a *different planning problem*, not a moderator on the greenfield one.

## 5. Re-planning discipline

Classical warrant: **plan repair beats replan-from-scratch on stability** (Fox et al., ICAPS
2006, `[E]`) — fewer changes, competitive speed — because committed resources can't be undone,
downstream dependencies break under churn, and change has real cost that standard planning
metrics ignore. This maps 1:1 onto the harness's committed work (merged tasks, authored vault
tests, spent tokens) that a full re-plan would strand.

The shipped instance is Zenith's **`TaskListPatch`** (verified in the clone, `[code]`):
add / **supersede** (old→new, every downstream `depends_on` rewritten in place) / **cancel**
(downstream refs rewritten to remove); guardrail **"cleared/running tasks cannot be
superseded/cancelled"** (locality of repair as a hard invariant); every patch **re-runs
depends_on resolution + acyclicity + coverage** (a patch that orphans an assertion or introduces
a cycle is rejected *at patch time*).

The discipline the evidence + TaskListPatch jointly support:
1. **Locality of repair** — patch the minimal set; never touch cleared/running work.
2. **Coverage-preservation** — every patch re-runs the structural invariants.
3. **Anti-re-litigation** — superseded/decided items are recorded, not silently reopened (the
   closure gate's fresh-evidence rule + remediation cap already encode this on completion).
4. **Ground-truth triggers only** — re-plan on a durable FAIL / discovered blast-radius /
   impossibility (ADaPT-style execution signal), not scheduled reflection.
5. **Re-anchor to the original *request*, not just the plan snapshot** — long-horizon "goal
   fade" (the diminishing-influence-of-the-question result, arXiv 2410.12409) is why RALPH
   re-opens the gap to the original request each session and Zenith's terminal reviewer
   re-derives gaps from it; a frozen-snapshot closure gate can miss drift *of the plan itself
   from the request*.

**The harness's gap:** its current re-planning answer is the **content-bound stamp voiding on any
plan edit** — the *safety* property (no silent plan drift) but **not** the *locality* property. A
typed, coverage-preserving `TaskListPatch`-equivalent that re-runs full preflight on patch,
re-stamps only the changed subtree, and refuses to touch merged/in-flight work would give
locality without surrendering the content-bound guarantee. The pilot evidence demands it: P3-2
and P3v2-1 were **both re-ratification events**, and both re-simulated the gate that had already
fired but **not the gate the edit newly armed** — exactly the class a patch op with mandatory
full-preflight-on-patch prevents.

## 6. Design mapping — confirms, extends, challenges

**Confirmed (the literature strongly ratifies these choices):**
- **Don't let the plan-authoring LLM self-approve.** The single best-supported design choice in
  the corpus — self-critique is net-negative (55% vs 88%), 84.45% false-positive
  ([companion §1](planning-and-decomposition-evidence.md)).
- **External gate = static-sound preflight + human ratification.** This *is* LLM-Modulo. The
  held-out executable test is a genuinely sound verifier (VAL-analog).
- **Determinate skeleton upfront + provisional later phases + re-planning.** The ADaPT/survey-
  endorsed synthesis between brittle full-upfront decomposition and pure as-needed recursion.
- **Determinacy over mere plan-presence.** "Incomplete plan worse than none" (16,991 trajectories)
  makes the determinacy gate the load-bearing lever, not decoration.
- **An independent, adversarial, spec-only reader** as the determinacy instrument — Orchid's ~50%
  self-detection precision says self-flagging can't work.

**Extended (concrete, evidence-backed additions):**
1. **Per-task typed `requires`/`provides` interface model** → sound producer-before-consumer
   (open-precondition) checking; *two independent theory lenses (LLM-Modulo verification and
   classical POP) converge on this exact missing check.*
2. **Transcription-readiness lint**: cross-boundary connascence ⊆ {Name, Type} ∧ every volatile
   decision spec-fixed-or-hidden — statically checkable once the interface model exists.
3. **Modularity check over the `touches` dependency graph** as a mechanical decomposition-quality
   predictor (low-modularity cut = bad boundary = colliding parallel pipelines + non-per-task
   validation).
4. **Typed re-plan patch op** (TaskListPatch-shaped) with mandatory full-preflight-on-patch,
   subtree re-stamp, cleared/running immutability.
5. **Two-axis gap taxonomy** (linguistic mechanism × behavioral domain), pitched as
   *underspecification* (set-level completeness), not just ambiguity.
6. **Re-plan trigger at task level** (failure/uncertainty-driven), not merely phase-gated.

**Challenged / honest limits:**
- **Semantic plan correctness before the gate is exposed.** The sound preflight can't reach it;
  the human gate covers it only imperfectly (automation bias — 3/48 shipped incorrect suggestions
  in the CSCW study; our own P3-2). Highest-leverage hardening is to pull phase-2 properties below
  the gate as tier-1 static checks (extensions 1–3) and keep the human gate *adversarial*, not
  confirmatory.
- **Brownfield is out of scope by construction and non-trivially so** — it is a different
  planning problem (localization-first, plan-derived-from-code, blast-radius, existing-contract
  constraint), not a parameter tweak (§4).
- **The determinacy probe costs quota** (dispatch a real spec-only agent per ratification) — it
  is a semantic check, not a free static one; budget it against the wall-clock/rework it prevents.

## 7. Open questions — now measured, not folklore

- **The determinacy-payoff experiment** the corpus has wanted: N-run paired deltas attributing
  retries/parks/stalls to underspecification classes on our own pilots (the run-log is the
  ledger; the 30× variance finding says single-run before/after is noise). The one project
  positioned to turn "granular specs → wall-clock" from folklore into measurement.
- **Build the executable determinacy probe** and validate it against the two-clean-sweep bar:
  does spec-only-agent question-count predict downstream blockers? (Ambig-SWE shows question-count
  tracks recoverable gap; nobody has used it as a *gate*.)
- **The interface model + producer-before-consumer preflight** — the highest-consensus hardening;
  measure how many phase-2 defects (P3-2-class) it would have caught.
- **Brownfield pilot** — the corpus is greenfield-only; a localization-first phase over a real
  existing repo is entirely unstudied here.
- Watch: SANER'26 registered report on spec-driven codegen (arXiv 2601.03878, protocol-only now);
  any controlled spec-first-vs-prompt-then-code measurement (none exists yet).
