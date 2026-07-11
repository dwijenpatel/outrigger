# plan-preflight — sound structural validation of a plan file

**v2 artifact #3a** ([design](../../docs/design/evidence-based-harness.md) D7, built to
R5/D15). One thing well: prove what a machine **can** prove about a `plan.json` — schema
validity, unique ids, resolvable dependencies, and an **acyclic task graph** (M7: only an
acyclic graph admits a sound structural check at all) — and *surface* what only the human
ratifier can judge as **warnings, never verdicts**.

The split is the design's D1 discipline applied to planning: hard failures are exclusively the
sound checks; determinacy signals (missing acceptance checks, unmatched `requires`, open
questions) inform ratification. The gate's failure mode is "plan less," never "pad the plan" —
nothing here rewards adding fake structure.

Standalone by construction: pure stdlib Python 3, no imports from anything else in this repo.
**Any plan file meeting the contract is accepted regardless of what produced it** — the
[spec-interview skill](../../.claude/skills/spec-interview/README.md) is one producer, not a
dependency.

## The plan contract (v1)

One JSON object. Unknown keys are errors at both levels (typos must die loudly).

| Key | Required | Meaning |
|---|---|---|
| `contract` | yes | integer `1` |
| `goal` | yes | one self-contained paragraph: what done looks like |
| `non_goals` | no | scope fence — what this plan deliberately does not do |
| `constraints` | no | operator-set invariants (incl. irreversible/externally-visible carve-outs) |
| `decisions` | no | the interview record: `[{"q": …, "a": …}]` — the *why* behind the spec |
| `open_questions` | no | explicitly unresolved items (warned; the ratifier accepts them knowingly) |
| `tasks` | yes | ≥1 task objects (below) |
| `external` | no | `requires` satisfied outside the plan |
| `ratified` | no | `{"by": …, "ts": …}` — present ⇔ a human ratified this exact content |

Task object: `id` (required, `[a-z0-9][a-z0-9-]*`, unique), `title` (required), `spec`
(required — self-contained enough for a fresh implementer; markdown welcome), `depends_on`
(ids; acyclic), `checks` (shell commands — sound verifiers; empty ⇒ warning), `provides` /
`requires` (free-form seam labels; unmatched `requires` ⇒ warning).

## Commands

```
python3 preflight.py check PLAN.json [--strict] [--require-ratified]
python3 preflight.py order PLAN.json
```

- `check` — JSON report `{ok, errors, warnings, ratified, stats}`. Exit **0** ok (warnings
  allowed) · **1** invalid (or warnings under `--strict`) · **2** usage/IO.
- `--strict` — promotes warnings to failure. **This is the T3 experiment knob** (does a
  machine determinacy bar beat human eyeballing? — unmeasured, 0/10 shipped products have
  one), not the default. Do not wire it into anything until T3 says so.
- `--require-ratified` — for consumers that must only accept ratified plans (an execution
  loop would pass this; a drafting workflow wouldn't).
- `order` — deterministic topological task order (lexicographic among ready tasks), refuses
  invalid plans. Exists so no consumer ever reimplements DAG logic against this contract.

## Composition examples

```sh
# Draft -> validate -> show the ratifier the warnings verbatim
python3 tools/plan-preflight/preflight.py check plan.json | jq -r '.warnings[]'

# An execution loop's admission line (blocking, D5-style):
python3 tools/plan-preflight/preflight.py check plan.json --require-ratified \
  && python3 tools/plan-preflight/preflight.py order plan.json
```

## Measurement & deletion criterion (R2)

Judged by errors caught before spend: v1's ratified plan shipped a floor inconsistency that a
structural preflight would have caught statically (P3-1/I19 precedent). If real usage shows
`check` never failing on anything a human wouldn't have caught in the same glance, delete it.
The warnings' value rides on **T3**; until then they are free information, not a gate.

## Tests · versioning

`python3 tools/plan-preflight/test_preflight.py` — 16 tests: sound-check hard failures
(contract, unknown keys, dup/malformed ids, dangling/self/cyclic deps, malformed
ratified/decisions), judgment-signal warnings (empty checks, unmatched requires, open
questions), `--strict` flip, `--require-ratified`, deterministic `order`. Contract is **v1**;
this file's schema table and the [spec-interview](../../.claude/skills/spec-interview/SKILL.md)
prose are two renderings of one contract — drift between them is exactly what **T11** exists
to learn from, and this pair is T11's first live integration.
