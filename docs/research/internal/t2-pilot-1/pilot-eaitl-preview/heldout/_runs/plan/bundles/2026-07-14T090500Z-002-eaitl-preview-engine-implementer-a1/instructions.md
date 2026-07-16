You are the IMPLEMENTER for task `eaitl-preview-engine`: Implement the deterministic IR transform/preview engine

SPEC:
Create a pure-Python-stdlib package `eaitl` in the repo root implementing the transform/preview engine described in design-draft.md.

PUBLIC CONTRACT (import-stable — a third party will test against exactly these):
- `from eaitl import apply_ir, MappingError`
- `apply_ir(ir: dict, rows: list[dict]) -> tuple[list[dict], list[dict]]` returns `(output_rows, errors)`.
  - `output_rows`: one dict per input row that passes all filters, each holding every mapping's `target_field`. A field whose transform failed is set to `None` and an error is recorded.
  - `errors`: list of `{"row_index": int, "target_field": str | None, "reason": str}` — `row_index` indexes the INPUT `rows`; `target_field` is null for row-level/filter errors.
- `MappingError(Exception)` is raised only for STRUCTURAL IR problems (see error model), never for per-row data problems.

IR SHAPE CONSUMED (per design-draft.md): `ir['mappings']` is a list of `{ 'target_field': str, 'transform': { 'op': str, 'args': list }, ... }` (other mapping keys ignored). `ir['filters']` (optional, default []) is a list of `{ 'op': str, 'args': list }` predicates. Other top-level IR keys are ignored.

ARG RESOLUTION: each entry in `transform.args` (and filter args) resolves against the input row — a STRING equal to a key in the row becomes that row's value; any other value (non-matching string, number, bool) is a literal; and `{"lit": v}` is always the literal `v` even if it matches a field key.

OP SET (implement all): copy(x)->x; rename == copy; concat(*parts)-> parts joined as strings, None rendered as ''; substring(s, start[, end])-> str(s)[start:end]; cast(x, target_type) for target_type in {'string','int','float'} via str/int/float; add|subtract|multiply|divide(a, b) numeric (divide-by-zero -> captured error); to_date(x)-> parse ISO-8601 (accept trailing 'Z'), return 'YYYY-MM-DD' (unparseable -> captured error); equals|not_equals|greater_than|less_than|greater_equal|less_equal(a, b)-> bool; hash(x)-> sha256 hexdigest of str(x) UTF-8 (unsalted).

ORDER OF OPERATIONS: apply mappings to every input row (capturing per-field errors by input row_index); then evaluate `filters` (AND-ed) against each mapped output row and include only rows where all filters are truthy; `errors` covers all input rows regardless of filtering.

ERROR MODEL:
- FATAL (raise MappingError): IR not a dict; `mappings` missing or not a list; a mapping missing `target_field`; a transform missing `op` or `args`; an unknown op name.
- CAPTURED (append to errors, set field to None, continue): a referenced source field missing from the row; a runtime op error on a value (divide-by-zero, unparseable date, failed cast); a filter evaluation error (target_field null).

WORKED-EXAMPLE ORACLE (must pass): using the `proposed_mappings` from design-draft.md (ops copy on order_id -> id; concat first+last -> customer_name; divide amount_cents by 100 -> amount_usd; to_date created_at -> order_date; equals status 'paid' -> is_paid), `apply_ir(ir, [sample_row])` must return `output_rows == [{'id': 'A1001', 'customer_name': 'Ada Lovelace', 'amount_usd': 25.99, 'order_date': '2026-07-10', 'is_paid': True}]` and `errors == []`. Include the example IR/rows as a fixture under examples/ and assert this in tests.

LAYOUT: `eaitl/__init__.py` (exports apply_ir, MappingError), plus internal modules of your choosing (e.g. eaitl/engine.py, eaitl/ops.py). Tests under tests/ using stdlib unittest, covering the worked example and edge cases (missing field, null value, divide-by-zero, unparseable date, the {lit} escape, and a filter dropping a row).

STYLE: fully type-annotated — `mypy --strict eaitl` must pass. Functional patterns: pure functions, immutable typed structures (e.g. frozen dataclasses) for the internal IR/op/error model, function composition, no mutable global state. The public boundary (apply_ir's signature) stays dict/JSON-shaped; strong typing applies to the internal model. Module split and dispatch style are your choice.

PLAN GOAL: Build the deterministic transform/preview engine for the eaitl ETL compiler (repo /Users/dwijen/repos/eaitl, currently greenfield) as a pure-Python-stdlib package `eaitl`. It consumes an approved IR (the typed JSON mapping plan from design-draft.md) plus sample rows and produces output rows, capturing per-row transform errors rather than raising on them. Done = the public function `eaitl.apply_ir(ir, rows)` exists with the exact signature and semantics pinned below, the full op set is implemented, the draft's worked example (raw_orders -> analytics_orders) reproduces its expected output row exactly, and a stdlib-unittest suite under tests/ passes.

PLAN CONSTRAINTS:
- eaitl's RUNTIME imports use the Python 3 standard library only — no third-party runtime dependency; the base repo needs no install step for the code to run.
- Static typing is enforced: the package is fully type-annotated and `mypy --strict eaitl` must pass (mypy is a dev/check tool, installed 2.1.0 — not a runtime import).
- Functional style: pure functions, immutable data (frozen dataclasses / tuples), minimal side-effects, function composition, no mutable global state.
- Strong internal data modeling: the IR, mappings, transforms, and error records are modeled as typed immutable structures internally; the PUBLIC boundary (apply_ir) stays JSON-shaped dicts so the blind arbiter and the draft's example IR remain valid inputs, with dict->typed parsing done inside.
- Pure and deterministic: no I/O, no network, no filesystem, no time/randomness in results; identical input always yields identical output. `hash` uses a fixed algorithm (sha256).
- The package is side-effect-free — no irreversible or externally-visible actions exist in this slice.

DECISIONS (the why — do not re-decide these):
- Q: Risk tier / how is it guarded and graded?
  A: full — a blind worker authors hidden acceptance tests from the spec and merge is behind the gate. Required because this is the harness arm of the T2 shadow-pilot (a non-full task is not a valid comparison arm), and a transform library is where hidden edge tests earn their keep.
- Q: Which ops and how much of the IR does this slice cover?
  A: The deterministic op set (copy, rename, concat, substring, cast, arithmetic, date-parse, comparison, hash) plus the IR `filters` section (row-drop). `encrypt` and `validations` execution are deferred.
- Q: How does the engine tell a field reference from a literal in transform.args?
  A: Row-key match with an explicit-literal escape hatch: a STRING arg equal to a key in the input row resolves to that row's value; any other arg (non-matching string, number, bool) is a literal; and an arg written as {"lit": value} is ALWAYS a literal even if it matches a field. This matches the draft's worked-example IR verbatim (bare-string refs) so the example stays the oracle.
- Q: What happens when a row can't be cleanly transformed?
  A: Per-row error capture: apply_ir returns (output_rows, errors); a failing target field yields null in its output row and an entry is appended to errors; the batch is not aborted.
- Q: Which errors are fatal (raise) vs captured (per-row)?
  A: STRUCTURAL IR problems raise MappingError before/independent of row data: IR not a dict, missing/!list `mappings`, a mapping missing `target_field`, a transform missing `op`/`args`, or an unknown op name. Per-row DATA problems are captured: a referenced source field missing from the row, a runtime op error on a value (divide-by-zero, unparseable date, failed cast), or a filter evaluation error.
- Q: What is the exact public interface the blind arbiter imports?
  A: Package `eaitl` exports two names: `apply_ir(ir: dict, rows: list[dict]) -> tuple[list[dict], list[dict]]` and the exception class `MappingError`. Internal modules (ops registry, engine) are not part of the contract.
- Q: Which IR fields does the engine read?
  A: Per mapping it reads `target_field` and `transform` ({op, args}); `sources`, `type`, `confidence`, `rationale`, `status` are proposal metadata and ignored (forward-compatible). Top-level it reads `mappings` and `filters`; `job_id`, `source`, `target`, `validations` are ignored.
- Q: Per-op semantics (pinned).
  A: copy(x)->x; rename(x)->x (alias of copy; the rename is expressed by target_field); concat(*parts)->parts joined as strings with None rendered as ''; substring(s,start[,end])->str(s)[start:end] (Python slice, end optional); cast(x,target_type)-> string|int|float via str/int/float (boolean cast is out of scope — use comparison ops); add|subtract|multiply|divide(a,b)-> numeric (divide-by-zero is a captured error); to_date(x)-> parse ISO-8601 (accept trailing 'Z') and return 'YYYY-MM-DD' (non-ISO input is a captured error); equals|not_equals|greater_than|less_than|greater_equal|less_equal(a,b)->bool; hash(x)-> sha256 hexdigest of str(x) UTF-8 encoded (unsalted).
- Q: Filter shape and order of operations (the draft leaves filters[] empty, so this is defined here).
  A: Each entry in `filters` is a predicate {op, args} using the same op/arg grammar, evaluated against the mapped OUTPUT row; all filters are AND-ed; a row is included in output_rows only if every filter is truthy. Mappings are applied to every input row first (errors captured by input row_index), then filters gate output inclusion; the errors list covers all input rows regardless of filtering.
- Q: Error record shape.
  A: Each errors entry is {"row_index": int (index into the input rows), "target_field": str or null (null for a row-level/filter error not tied to one field), "reason": str}.
- Q: Test framework and visible checks.
  A: Stdlib unittest only (no pytest dependency; matches the arbiter's stdlib-unittest suites). Tests live under tests/ and the visible check runs `python3 -m unittest discover -s tests -q`.
- Q: Backend/implementation language?
  A: Python 3, standard library only. The draft's examples lead with Python and the slice needs only stdlib (hashlib, datetime); the language must be pinned regardless because both comparison arms and the blind arbiter import `eaitl`. The draft's TypeScript/Rust are codegen TARGETS for the later compiler slice, not this engine's language.
- Q: How much internal design does the spec pin?
  A: Only the public contract (apply_ir/MappingError, op behaviors, error + IR shapes). Module split, op-dispatch style, and internal structure are the implementer's choice — deliberately open, because the internal design is precisely what the T2 harness-vs-null comparison measures; pinning it would contaminate the comparison and over-design a first slice ahead of the later compiler/matcher/validator slices, which get their own specs.
- Q: Coding style and type checking?
  A: Enforced strict static typing — `mypy --strict eaitl` is a check — plus functional style: pure functions, immutable typed data (frozen dataclasses/tuples), minimal side-effects, function composition, no mutable global state. This constrains STYLE, not structure (module split and dispatch stay the implementer's choice per the prior decision). Runtime stays stdlib-only; mypy is a dev/check tool. The public API boundary stays dict/JSON so the arbiter and the draft's example IR remain valid inputs; strong typing applies to the internal model. Caveat: mypy --strict is a hard mechanical gate, but functional style beyond what mypy enforces is judged in the blinded review, not by a shell check (no FP-linter added — over-tooling for slice 1).

You are on a dedicated branch in a dedicated worktree (your cwd). Implement the spec, run the task's own checks (python3 -c "import eaitl; assert hasattr(eaitl, 'apply_ir') and hasattr(eaitl, 'MappingError')"; mypy --strict eaitl; python3 -m unittest discover -s tests -q), then COMMIT all changes (git add -A && git commit). Work not committed does not exist. Do not touch paths outside this repository.