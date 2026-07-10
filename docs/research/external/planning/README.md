# Planning — spec elicitation and technical planning

**Scope.** Getting from intent to a buildable, determinate specification: elicitation
interviews, requirements formats, plan representations (task DAGs, milestone graphs, ledgers,
contracts), decomposition quality, re-planning and drift, plan verification, and
brownfield planning.

**Coverage: ○ thin — no dedicated document.** This folder is a deliberate placeholder: the
corpus has treated planning as an input to validation rather than as a design subproblem in
its own right. **Priority target for the next research passes.**

## What exists today (scattered)

- [../landscape/ecosystem-mining/spec-elicitation-and-planning.md](../landscape/ecosystem-mining/spec-elicitation-and-planning.md)
  — the 11-repo view: the interview is commoditized (5/11, grill-me lineage), a
  machine-checkable determinacy exit bar is 0/11, the `devis` fork as documented unmet demand.
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) — Zenith's
  Contract + adversarial contract-review passes + code-enforced coverage invariant.
- [../landscape/landscape-and-novelty.md](../landscape/landscape-and-novelty.md) §1 — Kiro's
  EARS requirements flow, Spec Kit, plan-first now being vendor territory.
- Internal, substantial but unsynthesized: the `plan-build` interview design (I2), the
  determinacy bar, `touches`/floors×profiles preflight (I19), spec-ambiguity blockers
  (H9/I20), and pilot evidence that ratified plans can still be internally inconsistent (P3-2).

## Open questions — next research targets

- **Executable determinacy probes.** "A spec-only test-author could write held-out tests with
  no guessing" is our bar — can it be *measured* (dispatch a spec-only agent, count its
  questions) rather than judged? Proposed in ecosystem-mining; nobody has built it.
- **Does elicitation pay?** The interview's cost is real; its benefit (fewer mid-firing
  blockers, less rework) is anecdotal (H9/P3v2-1). What would a paired-arm test look like?
- **Plan representations.** Task DAG vs milestone graph vs phased ledger vs spec-as-source
  (Tessl): what do the alternatives buy, and what evidence exists beyond vendor docs?
- **Decomposition quality.** What predicts a good task boundary/seam? Stub-and-seams'
  "determinate enough that implementation is transcription" bar — formalizable?
- **Spec-to-test traceability.** Criterion IDs mapped from acceptance criteria to vault tests,
  reported at the gate — 0/11 in the ecosystem; uniquely buildable here.
- **Re-planning discipline.** When to patch vs re-ratify; what Zenith's `TaskListPatch`
  guardrails and our content-bound stamps each get right.
- **Brownfield planning.** The entire corpus is greenfield-shaped; planning against a large
  existing codebase is unstudied here.
- **LLM-native requirements literature.** EARS and classical RE meet agent harnesses — is
  there an academic literature we haven't mined?
