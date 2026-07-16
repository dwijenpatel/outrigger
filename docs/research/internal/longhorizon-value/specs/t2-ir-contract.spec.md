# t2-ir-contract — human-readable render

> **GENERATED from `t2-ir-contract.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-15T08:39:38Z
**Risk tier:** full

## Goal

Add a standalone well-formedness validator for eaitl mapping plans as a new function `validate_ir` in the eaitl package, without changing the committed engine's behavior. `validate_ir` takes any object and returns a list of problems (an empty list means the plan is well-formed); each problem is a dict with a machine-readable `code`, a plain-English `message`, and a `location`. One call reports every problem at once (fundamentally-broken plans short-circuit), covering the executable core (mappings and filters), the output checks, and the light source/target identifiers, while ignoring proposer-only fields and never checking whether referenced columns exist. Done when `validate_ir` is importable from `eaitl`, the full rule set is enforced with the exact codes named in the task spec, the package type-checks under `mypy --strict`, and the existing engine tests still pass.

## Non-goals

- Does not modify the committed engine's behavior — new file `eaitl/validate.py` only, plus a single additive export line in `eaitl/__init__.py`.
- Does not check whether the source columns a mapping references actually exist (no schema is available; semantic/schema validation belongs to a later piece).
- Does not execute filters or output checks — it validates their structure only; running them belongs to the engine and a later piece.
- Does not include the automatic (LLM) mapping proposer or any code generation.
- Does not validate the proposer-only fields (`confidence`, `rationale`, `status`) — they are ignored pass-through.

## Constraints

- The engine's committed behavior at c646832 must not change: `apply_ir`, `MappingError`, and all engine/ops/parser/model/resolve code and their existing tests remain exactly as committed. The only edit to an existing file is adding the `validate_ir` export to `eaitl/__init__.py`.
- `validate_ir` must never raise on any input; it always returns a list (a non-object input is reported as a `not_an_object` problem, not an exception).
- Operation-name recognition reads the engine's live registry `eaitl.ops.OP_REGISTRY`, never a hardcoded copy of the names.
- A test must assert the validator's argument-count table has exactly the same keys as `OP_REGISTRY`, so a new engine operation without a count entry fails loudly.
- No irreversible or externally-visible actions: `validate_ir` is a pure function (no I/O, no network, no writes).

## Decisions

- **How wide is the contract the validator defines?**
  The deterministic-spine contract: mappings + filters + output checks (validations) + light source/target identifiers. Proposer-only fields (confidence, rationale, status) are ignored pass-through, as the engine already treats them.
- **When the validator finds problems, does it stop at the first or report them all?**
  Report them all: return a list of every problem (empty = well-formed); do not raise. Each entry has a code, a message, and a location.
- **Should one call catch everything, or only the new checks?**
  One complete standalone check: it reports every well-formedness problem including the ones the engine's parse already catches (may reuse parse_ir internally). Fundamentally-broken plans short-circuit.
- **Should each problem entry carry a machine-readable code?**
  Yes — a stable code alongside the message and location, so callers and hidden tests match on the code rather than fragile message text.
- **What is the public interface, and is the typed model exposed?**
  New file eaitl/validate.py with validate_ir(ir: object) -> list[dict[str,str]], exported from eaitl. The engine's internal typed representation stays internal; the public surface is just apply_ir and validate_ir; plans are passed as JSON dicts.
- **May this piece modify the engine, or only add alongside it?**
  Add-alongside-only; the committed engine is untouched (except the one export line). The validator keeps its own argument-count table mirroring the engine and syncs operation names live against OP_REGISTRY. A post-experiment follow-up task will refactor to a single source of truth for argument counts.
- **How strict is the validator about the edges?**
  source/target optional-but-checked (if present, an object with a string name); unknown/extra keys ignored (matching the engine); an output check's type_check `expected` must be one of string/int/float/bool; no column-existence checks.
- **Is the validator ever stricter than the engine?**
  Intentionally stricter on exactly three points that the engine tolerates at runtime but are almost always bugs: wrong argument counts, duplicate target columns, and non-predicate filters. It is NOT stricter on optional fields (never forces source/target, never flags unknown keys, never checks column existence).

## Open questions

- none

## Task `ir-contract` — Add a well-formedness validator for mapping plans

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Depends on:** none · **Provides:** ir-well-formedness-validator · **Requires:** eaitl-engine

---

# Well-formedness validator for eaitl mapping plans

## What and why
eaitl converts source rows into target rows using a **mapping plan** — a JSON object that lists,
per target column, which source column(s) feed it and what operation computes it, plus optional
row filters and output checks. The committed **engine** (commit `c646832`) applies a plan to rows.
This task adds a standalone **well-formedness validator**: a check that a plan is structurally
sound *before* anything downstream builds on it. It is the keystone contract every later piece
imports.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/validate.py`** exporting one function:
  - `validate_ir(ir: object) -> list[dict[str, str]]`
- Add `validate_ir` to `eaitl/__init__.py` so `from eaitl import validate_ir` works. **This export
  line is the ONLY edit to an existing file**; all existing exports and every engine/ops/parser/
  model/resolve line stay exactly as at `c646832`.
- **Input:** any object. Non-dicts are accepted on purpose (they are reported, not crashed on).
- **Output:** a list of **problems**. An **empty list means the plan is well-formed.** Each problem
  is a dict with exactly three string keys:
  - `code` — a stable machine-readable label from the fixed set below.
  - `message` — a plain-English description.
  - `location` — where in the plan, e.g. `"ir"`, `"mappings[2]"`, `"mappings[2].transform"`,
    `"filters[0]"`, `"validations[1]"`, `"source"`, `"target"`.
- `validate_ir` **never raises**: every problem, including "not an object", comes back in the list.

## Behavior
- **Reports every problem at once**, with one exception: **fatal problems short-circuit.** If the
  plan is not an object (`not_an_object`) or the `mappings` value is missing / not a list
  (`mappings_missing`), return just that one problem — nothing further can be examined. Otherwise,
  collect all problems across every mapping, filter, and output check.
- May **reuse the engine's parser internally** (`eaitl.parser.parse_ir`, catching its `MappingError`
  and re-expressing it as a problem) so structural checks are not rewritten — but the return shape
  is always the problem-list above, never a raised error.
- **Lenient on unknown keys:** extra top-level keys and extra per-mapping keys — including the
  proposer-only `confidence`, `rationale`, `status`, `sources`, `type` — are ignored, exactly as
  the engine ignores them.
- **No column-existence checks:** the validator has no source schema, so it does NOT check whether
  a column a mapping references exists. That belongs to a later piece.
- **Intentionally stricter than the engine on three points** (this is the validator's value — the
  engine tolerates all three at runtime, but they are almost always bugs): duplicate target
  columns, wrong argument counts, and non-predicate filters. It is NOT stricter on optional fields:
  it never *requires* `source`/`target`, never flags unknown keys, never checks column existence.

## Rules and codes

Whole-plan:
- `not_an_object` (`ir`, fatal): the plan is not a JSON object.
- `mappings_missing` (`ir`, fatal): no `mappings` key, or it is not a list.
- `filters_not_a_list` (`ir`): `filters` present but not a list.
- `validations_not_a_list` (`ir`): `validations` present but not a list.

Each mapping (location `mappings[i]`):
- `mapping_not_an_object`: the entry is not an object.
- `missing_target_field`: no `target_field`, or it is not a string.
- `duplicate_target_field`: another mapping has the same `target_field` (exact text match);
  report on the later occurrence(s).
- `transform_missing`: no `transform`, or it is not an object.
- `op_missing` (`mappings[i].transform`): the transform has no `op`, or it is not a string.
- `args_missing` (`mappings[i].transform`): the transform has no `args`, or it is not a list.
- `unknown_op` (`mappings[i].transform`): `op` is not in the engine registry
  (`eaitl.ops.OP_REGISTRY`).
- `wrong_argument_count` (`mappings[i].transform`): the number of `args` is outside the op's
  allowed range (table below).

Each filter (location `filters[i]`; a filter object is itself `{op, args}` — no `target_field`):
- `filter_not_an_object`: the entry is not an object.
- `op_missing`: no `op`, or it is not a string.
- `args_missing`: no `args`, or it is not a list.
- `unknown_op`: `op` is not in the registry.
- `wrong_argument_count`: args count outside the op's range.
- `non_predicate_filter`: `op` is not one of the six true/false operations `equals`,
  `not_equals`, `greater_than`, `less_than`, `greater_equal`, `less_equal`.

Each output check (location `validations[i]`):
- `validation_not_an_object`: the entry is not an object.
- `unknown_validation_kind`: `kind` missing or not one of `not_null`, `type_check`.
- `missing_validation_field`: `field` missing or not a string.
- `bad_expected_type`: for `kind == "type_check"`, `expected` missing or not one of `string`,
  `int`, `float`, `bool`.

Source / target (optional, but checked if present):
- `bad_source` (`source`): `source` is present but not an object with a string `name`.
- `bad_target` (`target`): `target` is present but not an object with a string `name`.
- Other keys (such as `format`) are ignored.

## Operation argument counts (the validator's own table, mirroring the engine)
Exact counts unless a range is given:

| operation | args |
|---|---|
| copy | 1 |
| rename | 1 |
| concat | 0 or more |
| substring | 2 or 3 |
| cast | 2 |
| add | 2 |
| subtract | 2 |
| multiply | 2 |
| divide | 2 |
| to_date | 1 |
| equals | 2 |
| not_equals | 2 |
| greater_than | 2 |
| less_than | 2 |
| greater_equal | 2 |
| less_equal | 2 |
| hash | 1 |

The validator recognizes operation *names* by reading the live `OP_REGISTRY`; the argument counts
above live in the validator itself. A test MUST assert that the count-table's keys exactly equal
the registry's keys, so a newly-added engine operation with no count entry fails loudly. (A
post-experiment follow-up task will unify these into a single source of truth.)

## Edge behaviors
- An empty `mappings` list is well-formed (the engine allows it).
- `validate_ir("not a dict")`, `validate_ir(None)`, `validate_ir(123)` each return exactly one
  `not_an_object` problem.
- A plan that is valid except for three wrong-argument-count mappings returns three problems.

## Conventions
- Python standard library only; no third-party dependencies.
- `mypy --strict` clean across the `eaitl` package.
- Functional style; typed internal helpers; the public boundary is plain JSON objects (dicts) in,
  a list of dicts out.
- New tests under `tests/` using the standard-library `unittest`.
