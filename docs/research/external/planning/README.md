# Planning — spec elicitation and technical planning

**Scope.** Getting from intent to a buildable, determinate specification and an executable plan:
elicitation interviews, requirements formats, plan representations (task DAGs, milestone graphs,
ledgers, contracts), decomposition quality, plan evaluation, re-planning and drift, and
brownfield planning.

**Coverage: ● rich** (2026-07-10 deep-research pass: ~40 primary sources across six verified
clusters — the academic planning literature, classical planning + representations,
requirements-engineering, shipped products, and a does-it-pay/brownfield/evaluation synthesis).
The remaining thinness is specific and named: **brownfield/repo-scale planning** is covered as a
*gap analysis* (what greenfield machinery can't do), not yet as adopted design — see below.

## Holdings

- [planning-and-decomposition-evidence.md](planning-and-decomposition-evidence.md) — the evidence
  base: can an LLM plan (self-critique net-negative; LLM-Modulo; the generation/validity/
  verification split), decomposition methods (ADaPT's fixed-plan-worse-than-none; DAG/list/tree),
  classical planning + the sound-checker pattern (LLM+P, HTN/ChatHTN, POP, VAL, plan repair),
  **the transcription-readiness predicate** (connascence + Parnas + seams + modularity — the
  corpus's "is a good boundary formalizable?" question, answered), the moderated does-planning-pay
  rule, and why an LLM-as-plan-judge gate is unsound.
- [spec-determinacy-and-practice.md](spec-determinacy-and-practice.md) — the front-half and the
  practice: the **ambiguity-vs-underspecification reframe** (most harness gap classes are
  omission, not ambiguity), EARS and the RE taxonomy, **determinacy measurement** (the probe's
  prior art and genuine novelty), the ten-product shipped survey (all converged on
  generate→eyeball→execute; none has a determinacy gate), the **brownfield gap** (planning ≈
  localization; Agentless/CodePlan), re-planning discipline (repair over replan; TaskListPatch),
  and the consolidated design mapping + hardening backlog.

## Related material elsewhere

- [../landscape/ecosystem-mining/spec-elicitation-and-planning.md](../landscape/ecosystem-mining/spec-elicitation-and-planning.md)
  — the 11-repo practitioner study these documents extend (asking mechanics commoditized; the
  exit side empty; `harness.planning ready` unique).
- [../validation/correctness-and-verification-evidence.md](../validation/correctness-and-verification-evidence.md)
  §4 — plan-first +25.4% and the human plan gate (evidence these documents reconcile).
- [../evaluation/harness-evaluation-prior-art.md](../evaluation/harness-evaluation-prior-art.md)
  — mandated-TDD net-negative (the other pole of the does-planning-pay reconciliation).
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) — Zenith's
  Contract, adversarial contract-review, coverage invariant, and `TaskListPatch` re-planning.

## Open questions — now measured, not folklore

Full list in [spec-determinacy-and-practice.md §7](spec-determinacy-and-practice.md); the
highest-leverage:

- **The determinacy-payoff experiment** — N-run paired deltas attributing retries/parks/stalls
  to underspecification classes on our own pilots; the one project positioned to turn "granular
  specs → wall-clock" from folklore into measurement.
- **The interface model + producer-before-consumer preflight** — the highest-consensus hardening
  (two theory lenses converge on it); measure how many P3-2-class phase-2 defects it would catch.
- **The executable determinacy probe** — validate spec-only-agent question-count against the
  two-clean-sweep bar as a *gate*, which no prior art does.
- **A brownfield pilot** — the corpus is greenfield-only; localization-first planning over a real
  existing repo is entirely unstudied here.
