# t4-validations — human-readable render

> **GENERATED from `t4-validations.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T01:06:08Z
**Risk tier:** full

## Goal

Add execution of a mapping plan's output validations to eaitl as a new pure function `validate_output(ir, rows)` that checks the plan's `validations` entries (not_null, type_check) against already-produced output rows and returns a deterministic, row-major list of violation records {row_index, field, kind, reason} (empty = all pass). Structural malformation of the validations block raises the engine's existing MappingError; data-level failures never raise. type_check uses exactly the ratified four-type vocabulary (string/int/float/bool) with strict runtime-type matching (bool never passes int; int never passes float); null values skip type_check — nullability is not_null's jurisdiction alone — while a field absent from a row fails loudly with reason 'missing'. Done when the function is importable from eaitl, the pinned semantics hold with the exact examples in the task spec, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No new validation kinds — exactly the product draft's two (not_null, type_check); richer kinds (ranges, regex, uniqueness, and date/timestamp-format output assertions) are a post-experiment register item. Dates the engine produces via to_date are valid ISO strings by construction; only a hand-edited plan that bypasses to_date could route an unvalidated string into a date column, and no output-side shape check guards that path in this chain (named, accepted).
- Does not run the engine — it checks rows it is handed; composing apply_ir then validate_output is the caller's (later, job-pipeline task's) job.
- Does not re-validate the rest of the plan's structure — the ratified well-formedness validator is the full structural gate; this function only guards the block it reads.
- Report-only: never mutates, filters, or coerces rows.
- No source/target-schema awareness; no I/O; no LLM.

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the validate_output export to eaitl/__init__.py.
- MappingError is imported from eaitl and reused for structural failures — never redefined, never edited.
- type_check's expected vocabulary is exactly {string, int, float, bool}, identical to the ratified well-formedness validator's bad_expected_type set — the two specs must never drift.
- validate_output is a pure function: deterministic output ordering (row-major, validations order within a row); no I/O, clock, or randomness.
- No irreversible or externally-visible actions: pure computation only.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design T4 row: execute the IR validations 'deferred from T1'; next task in the ratified cascade order (T2, T3 done 2026-07-15).
- **Scope and non-goals (coverage item 2)**
  Sourced — chain-design T4 row (execute not_null + type_check against engine output) and the product draft's validations examples; exactly two kinds, report-only.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the job pipeline (T11) runs this as a stage after the engine; the CLI (T12) reports its findings.
- **Success in outcome terms (coverage item 4)**
  Sourced — chain-design: correct-or-stop machinery; violations reported exactly per pinned semantics, precise enough for a blind author to test from the spec alone.
- **Appetite (coverage item 5)**
  Sourced — chain-design size table classes T4 'small' (smallest tier); the experiment's measured ~$7/task budget precedent bounds it.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the task sequence; richer validation kinds go to the post-experiment register (the draft names only these two).
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure function, no side effects (constraints). Tier: full, per the chain-wide precedent ratified in the T2 plan.
- **Strict type matching**
  Derived (two-way door, from the project's silent-wrong-averse thesis): runtime types must match exactly — an int does not pass a float check, a bool never passes an int check. A lenient numeric check would let a wrong-op int slip a float assertion; strictness converts that to a loud violation the user fixes with an explicit cast. Cost: a semantically-fine int output flags and needs a cast added to the plan.
- **Are nulls allowed in output columns, and who asserts nullability?**
  Operator (2026-07-15, ledger challenge to the drafted semantics): nulls are allowed in general — a null output from a null input is legitimate data; nullability is asserted only and exactly via not_null, so omitting not_null IS the explicit nullable declaration. Consequence: type_check skips null values (type-when-present); a non-nullable typed column is declared as both checks together.
- **A field absent from a row, under type_check**
  Derived (two-way door, from loud-plan-defects): an absent key still fails type_check with reason 'missing' — engine output always carries every mapped field (failed values arrive as null), so an absent key means the validation names a field the plan never produces (typo'd or forgotten mapping); a pure skip would pass that plan defect silently with zero violations.
- **Structural errors raise; data failures report**
  Derived (two-way door, from engine precedent): validate_output is a runtime executor like apply_ir, so malformed validations raise the engine's existing MappingError (imported, reused — single source of truth for 'structural IR problem'); the ratified well-formedness validator reports the same defects as codes pre-flight, so composed callers never see the raise.
- **Interface shape and composition**
  Derived (two-way door, from precedent): validate_output(ir, rows) takes the full plan dict at the boundary (uniform with apply_ir/validate_ir) and the rows to check; it never runs the engine — single responsibility, the pipeline composes apply_ir | validate_output.
- **Violation record shape and ordering**
  Derived (two-way door, from the engine's error-record precedent): {row_index, field, kind, reason}, row-major, validations order within a row; duplicates run and report independently; unknown extra keys on entries ignored (lenient precedent).
- **type_check vocabulary = the ratified four, not introspection's six**
  Derived (two-way door, from cross-spec consistency): {string,int,float,bool} exactly matches the T2-ratified validator's expected-type set, and names the engine's runtime output types — dates are ISO strings at runtime (to_date returns a string), so a date column type-checks as string. Stated in the spec so the blind author does not expect date/timestamp support.

## Open questions

- none

## Task `output-validations` — Execute a plan's output validations (not_null, type_check)

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Depends on:** none · **Provides:** output-validations · **Requires:** eaitl-engine

---

# Execute a mapping plan's output validations (not_null, type_check)

## What and why
An eaitl mapping plan may carry **validations** — assertions on the *output* rows the engine
produces, e.g. `{"kind": "not_null", "field": "id"}` or
`{"kind": "type_check", "field": "amount_usd", "expected": "float"}`. The engine deliberately
ignores them (deferred out of the engine slice); the well-formedness validator checks only
their *structure*. This task makes them run: given a plan and a list of output rows, report
every violation. The job pipeline runs this as a stage after the engine; the CLI reports its
findings.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/validations.py`** exporting one function:
  - `validate_output(ir: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Add `validate_output` to `eaitl/__init__.py`. **That export line is the ONLY edit to
  existing files**; the engine and both prior tasks' files stay exactly as committed.
- **Input:** `ir` is the full mapping-plan dict (this function reads only its `validations`
  key); `rows` are the rows to check — normally `apply_ir`'s output rows, taken as given.
  **This function never runs the engine.**
- **Output:** a list of **violation records**, one per (row, validation) failure. Empty list =
  every validation passed on every row. Each record has exactly four keys:
  - `"row_index"`: int — the row's position in `rows`.
  - `"field"`: str — the validated field name.
  - `"kind"`: `"not_null"` | `"type_check"`.
  - `"reason"`: str — plain English, e.g. `"id is null"`, `"amount_usd expected float, got str"`.
- **Ordering:** row-major — all violations for `rows[0]` (in the plan's validations order),
  then `rows[1]`, … Deterministic: same inputs, same output, always.
- Pure function: no I/O, no clock, no randomness.

## Structural errors raise; data failures report
This is a runtime executor, so it follows the engine's split (`apply_ir` raises `MappingError`
for structural plan problems and captures data problems as records):

- **Raise `MappingError`** (imported from `eaitl` — reused, never redefined) when the
  validations block itself is malformed: `ir` not a dict; `validations` present but not a
  list; an entry not a dict; `kind` missing or not one of the two; `field` missing or not a
  string; for `type_check`, `expected` missing or not one of the four allowed types; a row in
  `rows` that is not a dict. Messages carry the location, parser-style:
  `"validations[1] missing field"`. (A caller that ran the well-formedness validator first
  never triggers these — it reports the same defects as problem codes. That is the intended
  composition; this function stays safe standalone.)
- **Never raise on data**: any value in any row is handled by the semantics below.

## Semantics (exact)
The `validations` key is optional; absent or `[]` → return `[]` (vacuous pass). Zero rows →
`[]`. Duplicate validations both run and can both report — no dedup.
Unknown extra keys on a validation entry are ignored (e.g. a stray `expected` on a
`not_null`), matching the engine's lenient treatment of unknown keys.

**`not_null`** fails for a row when the field's key is **absent** from the row OR its value
is **`None`**. (Engine output rows always carry every mapped field — `None` on a per-row
error — so an absent key normally means the validation names an unmapped field: it then
fails on every row, loudly. That is the intended behavior, not an error.)

**`type_check`** — `expected` is exactly one of **`string` · `int` · `float` · `bool`** (the
well-formedness validator's ratified vocabulary; note this is narrower than source
introspection's inference vocabulary, deliberately: these name the engine's *runtime output*
types, and the engine emits dates as ISO **strings** — `to_date` returns `"2026-07-10"`, so a
date column type-checks as `string`). A value passes iff its runtime type matches exactly:

- `string` ⇔ the value is a `str`.
- `int` ⇔ the value is an `int` **and not a `bool`** (in Python `isinstance(True, int)` is
  true; a bool must never pass an int check).
- `float` ⇔ the value is a `float` — **an `int` does not pass a float check** (strict; see
  the plan's decisions). `float('nan')` is a float and passes.
- `bool` ⇔ the value is a `bool`.
- A **null value is skipped by `type_check`** — it neither passes nor fails (operator ruling:
  nulls are legitimate data; nullability is asserted only and exactly by `not_null`, so
  omitting `not_null` IS the explicit declaration that a column may be null; declare both
  checks for a non-nullable float). A field **absent from the row still fails**, with reason
  `"amount_usd missing"`: engine output always carries every mapped field (failed values
  arrive as null), so an absent key is not data — it means the validation names a field the
  plan never produces (a typo'd or forgotten mapping), and that must stay loud.

## Worked examples (from the product draft's scenario)
Validations: `[{"kind": "not_null", "field": "id"},
{"kind": "type_check", "field": "amount_usd", "expected": "float"}]`

- Row `{"id": "A1001", "customer_name": "Ada Lovelace", "amount_usd": 25.99,
  "order_date": "2026-07-10", "is_paid": true}` → **no violations**.
- Row `{"id": null, "amount_usd": "25.99"}` → **two violations**:
  `{"row_index": 0, "field": "id", "kind": "not_null", "reason": "id is null"}` and
  `{"row_index": 0, "field": "amount_usd", "kind": "type_check",
    "reason": "amount_usd expected float, got str"}` (reason wording may vary; the four keys,
  their values, and the ordering are the contract — reasons must be non-empty plain English).
- Row `{"id": "A1003", "amount_usd": null}` → **no violations**: null skips `type_check`, and
  no `not_null` is declared on `amount_usd` — nullable by omission. Row `{"id": "A1004"}` (no
  `amount_usd` key at all) → **one violation**: `type_check` fails with reason
  `"amount_usd missing"` — the plan never produced the field.
- Row `{"id": "A1002", "amount_usd": 25}` (int) → **one violation** (strict float check).
- `type_check` on `order_date` with `expected: "string"` → passes (dates are ISO strings at
  runtime).
- `{"kind": "type_check", "field": "is_paid", "expected": "int"}` against `is_paid: true` →
  **violation** (bool is not int).
- Validations `[]` or key absent, any rows → `[]`.

## Conventions
- Python standard library only; `mypy --strict` clean across the `eaitl` package.
- Functional style; plain-dict public boundary.
- New tests under `tests/` using standard-library `unittest`.
