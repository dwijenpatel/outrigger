# spec-interview — artifact notes

**v2 artifact #3b** ([design](../../../docs/design/evidence-based-harness.md) D7, built to
R5/D15). One thing well: the **clarification interview** — one question at a time, grounded
in the repo, task-conditional depth — emitting a `plan.json` (contract v1) the operator
ratifies. The skill body is [SKILL.md](SKILL.md); the machine-normative side of the contract
is [tools/plan-preflight](../../../tools/plan-preflight/README.md).

## Evidence shape (why the skill reads the way it does)

- **The interview is the lever**: spec underspecification costs tens of points; interactive
  clarification recovers most (distilled §3.1 — three independent benchmarks). Hence
  one-question-at-a-time patience and real token budget here.
- **Plan less, never pad**: a deficient plan is net-negative vs none; planning pays on
  structured tasks and ≈0 on flat ones (§3.1) — hence task-conditional depth and the early
  stop condition.
- **Determinate seams only where work splits** (§3.2); **carve-outs surfaced explicitly**
  (D8's hard floor); **the omission prompt** before ratification (§3.3 — the silent channel
  suppresses detection); **no self-certification** (§3.1 — D1).

## Standalone-ness (R5/D15)

Adoption is copying this directory into any repo's `.claude/skills/`. It requires nothing
else from this repo: if `plan-preflight` is present it is run opportunistically and its
warnings shown verbatim; if absent, the skill says so and the plan is still valid output.
The execution loop (when it exists) will consume plan files via `--require-ratified` — it
will not know or care whether this skill produced them.

Deterministic invocation (`/spec-interview`) is the reliable path — skills auto-trigger with
38–69% recall (§3.1), so anything load-bearing should invoke it explicitly.

## Measurement & deletion criterion (R2)

The null arm is prompt-only planning: same goals, no interview, measure downstream rework and
integration failures (this is adjacent to design **T3**, which separately measures the
machine bar). v1 precedent: the interview surfaced ~20 decisions on its first outing and its
absence was a recorded pilot defect (P1-8). If measured usage shows interview-produced plans
doing no better than prompt-only, delete the ceremony; that deletion is a result.

## Versioning

Contract **v1**, shared with plan-preflight. SKILL.md's example and preflight's schema table
are two renderings of one contract — drift is what **T11** studies; this pair is T11's first
live integration.
