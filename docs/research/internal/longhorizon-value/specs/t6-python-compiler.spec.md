# t6-python-compiler — human-readable render

> **GENERATED from `t6-python-compiler.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T01:36:58Z
**Risk tier:** full

## Goal

Add a Python code generator to eaitl as `compile_python(ir) -> str`, returning the source of a standalone stdlib-only module defining transform(rows) -> (output_rows, errors) whose observable behavior is exactly apply_ir's with the plan baked in — full differential equality including output rows, filtering decisions, and error records with the engine's exact reason strings, across the named edge set (true division on negatives, to_date Z/offset handling without timezone conversion, concat null -> empty string, cast/arithmetic bool asymmetry, comparison failures, hash of str(), substring slice semantics, literal-vs-dynamic argument resolution, filters over the mapped row, per-row error capture). Structurally-invalid plans raise the engine's MappingError at compile time; runtime-tolerated defects compile to engine-identical runtime behavior. Generation is deterministic (same plan -> byte-identical source). Done when compile_python is importable from eaitl, the differential property holds with the exact examples in the task spec, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No TypeScript or Rust backends — the JS compiler is the next task (sharing this op contract); Rust is dropped from the chain (no toolchain on the host); other languages are post-experiment register items.
- No single-row ergonomic wrapper (the product draft's transform(row) shape) — the gradeable rows-level parity function is the contract here; per-row ergonomics are a post-experiment register item.
- No compile-time validation beyond the engine parser's structural set — the ratified well-formedness validator is the gate for arity/duplicate-target defects; this compiler reproduces the engine's runtime behavior for them instead of pre-rejecting.
- No optimization, formatting polish, or configurability of the generated code beyond determinism and the pinned contract.
- No sandboxing of generated-code execution — tests exec what this compiler just produced from a trusted plan; running untrusted plans is out of scope.
- No CLI and no pipeline wiring (later tasks).

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the compile_python export to eaitl/__init__.py.
- MappingError is imported from eaitl and reused for compile-time structural failures — never redefined; eaitl.parser.parse_ir may be reused internally (read-only import of frozen code).
- The generated module never imports eaitl and uses only the Python standard library; it performs no I/O and reads no clock or randomness source.
- compile_python is deterministic: identical plan input yields byte-identical source text.
- The parity requirement is total differential equality against apply_ir, including error-record reason strings.
- No irreversible or externally-visible actions: pure computation only.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design T6 row: the Python compiler with engine-identical op semantics; the chain's largest task and a compounding hotspot; next in the ratified cascade order (T2, T3, T4 done).
- **Scope and non-goals (coverage item 2)**
  Sourced — chain-design ('compile_python(ir) -> str: standalone transform with engine-identical op semantics') + the chain's codegen scoping decision (Python + JS; Rust dropped, no toolchain). Non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design: the JS compiler (next task) shares the op-semantic contract; the job pipeline runs compile as a stage; the CLI emits the code bundle; the experiment's Canary B and end-to-end oracle consume the parity property.
- **Success in outcome terms (coverage item 4)**
  Sourced — chain-design names the oracle explicitly: exec(compiled) == apply_ir, with Canary B (op parity: divide rounding on negatives, to_date Z/timezone handling, concat null-rendering) as the seeded edge families.
- **Appetite (coverage item 5)**
  Sourced — chain-design size table classes T6 'large' (the chain's largest single task); still one worker session per arm under the experiment's measured budget precedent.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the sequence; TS/Rust backends and the per-row ergonomic wrapper go to the post-experiment register.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure computation, string out (constraints). Tier: full, per the chain-wide precedent ratified in the T2 plan.
- **Oracle strictness — do error reason strings count?**
  Derived (two-way door, from the chain's stated oracle + determinacy): full equality INCLUDING reason strings. The engine's message templates are in its committed, frozen source; requiring them makes the differential oracle a one-line total check with zero ambiguity for the blind author. Alternative (structural-only error parity) rejected: it opens a 'which differences count' judgment line the experiment's exact-match grading cannot adjudicate.
- **Generated interface: rows-level transform, not the draft's per-row function**
  Derived (two-way door, from gradeability-first): transform(rows) mirrors apply_ir's signature exactly, making the differential oracle trivial; the draft's per-row transform(row) cannot express filters or indexed error records without inventing extra contract. Per-row ergonomics deferred (non-goal).
- **Standalone generated code duplicates op semantics**
  Derived (two-way door, from the product requirement): the generated module is the deployable artifact and must not import eaitl, so op semantics exist twice (engine + generated templates). This is inherent to the product, not a shortcut — and the total differential requirement plus Canary B is precisely the machinery that keeps the two implementations pinned together. The single-source alternative (generated code importing eaitl) was rejected: it guts the product's deploy-anywhere property.
- **Compiler leniency — compile what the engine tolerates**
  Derived (two-way door, from parity-over-strictness): wrong arity and duplicate targets compile to engine-identical runtime behavior rather than being rejected at compile time. Pre-rejecting would make the compiler stricter than the runtime (breaking the differential property) and would duplicate the ratified validator's job. Cost: a defective-but-tolerated plan compiles silently — the validator, run first, is the named gate for that.
- **Structural errors at compile time**
  Derived (two-way door, from engine precedent, as in the validations task): plans the engine's parser rejects raise the reused MappingError at compile time; composed callers run the well-formedness validator first and never see the raise.
- **Deterministic generation**
  Derived (two-way door, from the freeze task ahead): identical plan -> byte-identical source, so the content-addressed freeze/versioning of approved plans extends cleanly to their compiled artifacts.

## Open questions

- none

## Task `python-compiler` — Compile a mapping plan to a standalone engine-identical Python module

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Provides:** python-compiler · **Requires:** eaitl-engine

---

# Compile a mapping plan to standalone Python — engine-identical semantics

## What and why
eaitl's product wedge is compiling one approved mapping plan into deterministic, deployable
code. This task builds the **Python backend**: `compile_python(ir)` returns the *source text*
of a standalone Python module whose behavior is **indistinguishable from the engine's**. That
parity is the whole game: generated code that quietly diverges from the engine on an edge
(rounding, timezones, null rendering) ships wrong data while every happy-path test passes.
The differential oracle — run the generated module and compare against `apply_ir` — is the
acceptance bar, and the edges below are explicit requirements, not implementation trivia.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/compile_python.py`** exporting one function:
  - `compile_python(ir: dict[str, Any]) -> str`
- Add `compile_python` to `eaitl/__init__.py`. **That export line is the ONLY edit to existing
  files**; the engine and all prior tasks' files stay exactly as committed.
- **Input:** the full mapping-plan dict (same shape `apply_ir` consumes).
- **Output:** Python source text (a complete module, as a string).
- **Structural errors:** a plan the engine's parser would reject (not a dict, missing/non-list
  mappings, mapping without `target_field`, transform without `op`/`args`, unknown op) raises
  the engine's existing **`MappingError`** at compile time — imported and reused, never
  redefined (may reuse `eaitl.parser.parse_ir` internally; a caller that ran the ratified
  well-formedness validator first never sees the raise).
- **No compile-time strictness beyond structure:** plans the engine *tolerates at runtime*
  (wrong arity, duplicate `target_field`) must **compile**, to code that reproduces the
  engine's runtime behavior for them (per-row arity error records; last-mapping-wins) —
  the compiler never pre-rejects what the engine executes. The well-formedness validator is
  the gate for those defects; the compiler's contract is parity.

## The generated module's contract
- Defines **`transform(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`**
  — the exact shape of `apply_ir(ir, rows)` with the plan baked in.
- **Standalone:** imports from the Python standard library only (`hashlib`, `datetime`,
  `typing` as needed) — it must **never import eaitl**; it is the deployable artifact.
- **Pure:** no I/O, no network, no clock reads, no randomness, no `eval`/`exec` inside.
- **Deterministic generation:** identical plan dict → **byte-identical** source text.

## The parity requirement (total, differential — this is Canary B's home)
For **every** plan that compiles and **every** list of rows:

```
module = exec(compile_python(ir))          # conceptually
module.transform(rows) == eaitl.apply_ir(ir, rows)   # full equality
```

Equality is **exact and complete**: same output rows (same keys, same values, same row
order), same error records (same `row_index`, `target_field`, **and `reason` strings** — the
engine's message templates are in its committed source and must be reproduced), same
filtering decisions. The property is total — it covers odd inputs, not only tidy ones.

**Named edge requirements** (each is a tempting divergence; all are engine behavior today):

- **divide** is true division, always: `divide(-7, 2) → -3.5` (never floor division's `-4`);
  `divide(5, 0)` → error record `"divide: division by zero"`, field set to null.
- **to_date** parses ISO strings, mapping a trailing `Z` to `+00:00`, and returns the date
  **as written in the value — never timezone-converted**:
  `"2026-07-10T23:22:11-05:00"` → `"2026-07-10"` (NOT the UTC date 2026-07-11);
  `"2026-07-10T14:22:11Z"` → `"2026-07-10"`; unparseable → error record.
- **concat** renders null parts as the **empty string** (`concat("a", null, "b") → "ab"`,
  never `"aNoneb"`), and non-strings via `str()`; it accepts **any number of args, including
  zero** (`→ ""`), and never errors.
- **cast**: targets exactly `string`/`int`/`float`; a failed conversion → error record
  (`cast: cannot cast 'abc' to int`); note the engine casts booleans numerically
  (`cast(true, "int") → 1`) and `float("1e5") → 100000.0` — engine semantics, not
  introspection's inference rules, govern here.
- **arithmetic** (`add`/`subtract`/`multiply`/`divide`) rejects **booleans and non-numerics**
  with an error record (`"add expects a numeric arg, got True"`) — even though `cast`
  accepts bools; parity means reproducing the asymmetry.
- **comparisons** (`greater_than`/`less_than`/`greater_equal`/`less_equal`): Python ordering;
  an incomparable pair → error record (`"greater_than: cannot compare 5 and 'a'"`).
  `equals`/`not_equals` compare anything and never error.
- **hash**: sha256 of `str(value)` UTF-8, hex digest — including `hash(null)` = the digest of
  the string `"None"` (yes: concat renders null as `""` while hash hashes `"None"` — the
  engine's asymmetry, reproduced, not fixed).
- **substring**: `str()`-coerces, then Python slice semantics — negative indices work
  (`substring("hello", -3) → "llo"`), out-of-range yields `""` without error; 2 or 3 args;
  index args must be ints and **a boolean index is rejected** (error record).
- **rename** behaves exactly as **copy** (one arg, passes the value through).
- **Argument resolution**: `{"lit": X}` (a dict with exactly that one key) always yields `X`;
  any other value is dynamic — a string that is a key **of the row in scope** yields that
  row's value, a string that is not a key yields **the string itself**, a non-string yields
  itself. Mappings resolve against the **source row**; **filters resolve against the mapped
  output row** — `equals("status", {"lit": "paid"})` as a filter reads the *output*'s
  `status` field, and if the output has no `status` key the arg is the literal string
  `"status"` (so the filter is false and the row silently drops — engine behavior, pinned).
- **Filters**: run in order after mapping; a falsy result drops the row **with no error
  record**; an op failure inside a filter drops the row **with** an error record
  (`target_field` null); remaining filters short-circuit.
- **Per-row error capture**: a failed mapping sets the target field to null AND appends an
  error record; the row still emits (unless filtered). Error dicts have exactly the engine's
  keys: `row_index`, `target_field`, `reason`.
- **Degenerate plans**: `{"mappings": []}` compiles; `transform([{"a": 1}])` →
  `([{}], [])` (one empty output row, engine-identical). `transform([])` → `([], [])`.

## Worked example (the product draft's scenario, end to end)
The draft's five-mapping plan (`copy order_id → id`, `concat` names, `divide amount_cents
100 → amount_usd`, `to_date created_at → order_date`, `equals status "paid" → is_paid`)
compiled and run over the draft's sample row must yield exactly
`{"id": "A1001", "customer_name": "Ada Lovelace", "amount_usd": 25.99,
"order_date": "2026-07-10", "is_paid": true}` with no errors — byte-for-byte what
`apply_ir` produces on the same inputs.

## Conventions
- Python standard library only; `mypy --strict` clean across the `eaitl` package (the
  *compiler*; generated text is exec'd by tests, not type-checked).
- Functional style; plain-dict public boundary.
- New tests under `tests/` using standard-library `unittest`. The natural test shape is
  differential: compile, exec, compare against `apply_ir` on the same inputs — including
  every named edge above.
