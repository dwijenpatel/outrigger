You are the IMPLEMENTER for task `ts-compiler`: Compile a mapping plan to a standalone typed TypeScript module

SPEC:
# Compile a mapping plan to standalone TypeScript — the engine's semantics, cross-language

## What and why
The product's wedge is one approved mapping plan compiling to multiple languages. This task
builds the **TypeScript backend** (operator decision 2026-07-16: TypeScript, not plain
JavaScript — the original JS-only scoping existed solely because the host lacked `tsc`, which
is now installed): `compile_ts(ir)` returns the source text of a standalone, typed,
node-runnable module whose `transform(rows)` reproduces the engine's behavior. Cross-language
parity has genuinely impossible corners (JavaScript/TypeScript has one number type; Python
two), so this spec defines an explicit **guaranteed parity domain** with named, accepted
exclusions. Everything inside the domain is exact; everything excluded is listed, not
discovered.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/compile_ts.py`** exporting one function:
  - `compile_ts(ir: dict[str, Any]) -> str`
- Add `compile_ts` to `eaitl/__init__.py`. **That export line is the ONLY edit to existing
  files.**
- **Structural errors:** plans the engine's parser rejects raise the reused **`MappingError`**
  at compile time (parser reuse allowed), exactly as the Python compiler does. Plans the
  engine tolerates at runtime (wrong arity, duplicate targets) **compile**, to code
  reproducing the engine's runtime behavior — the compiler never pre-rejects what the engine
  executes.
- **Deterministic generation:** identical plan → **byte-identical** TypeScript source.

## The generated module's contract
- **TypeScript, ES-module syntax, erasable types only** (no enums, no namespaces, no
  parameter properties) — so the file both type-checks under `tsc --strict` and runs
  **unmodified** under the host's node v24 native type stripping when saved as `.mts`.
- **Zero imports, zero dependencies** — not even node built-ins: the module embeds its own
  small SHA-256 and UTF-8 helpers (fixed template code). It runs in any modern JS runtime
  and type-checks with no `@types/*` packages, no package.json, no node_modules.
- **Exported surface** (all exported, exactly):
  - `type Row = Record<string, unknown>;`
  - `type TransformError = { row_index: number; target_field: string | null; reason: string };`
  - `type OutputRow = { ... };` — one property per mapping's `target_field`, in mappings
    order, typed by the op's return type, uniformly unioned with `null` (a failed mapping
    writes null): `copy`/`rename` → `unknown`; `concat`/`substring`/`to_date`/`hash` →
    `string | null`; `add`/`subtract`/`multiply`/`divide` → `number | null`;
    `equals`/`not_equals` and the four ordering comparisons → `boolean | null`; `cast` with a
    literal target type → that type (`"string"` → `string | null`, `"int"`/`"float"` →
    `number | null`), `cast` with a dynamic target → `unknown`. Duplicate targets take the
    last mapping's type.
  - `function transform(rows: Row[]): [OutputRow[], TransformError[]]`
- **Gates, pinned exactly** (both verified on this host, 2026-07-16 — tsc 7.0.2, node
  v24.13.1):
  - Type gate: `tsc --strict --noEmit --target es2022 --module es2022 --moduleResolution
    bundler <file>.mts` exits 0.
  - Runtime: `node <file>.mts` runs it directly (native type stripping; the erasable-only
    rule is what guarantees this).
- Pure: no I/O, no clock, no randomness, no `eval`. The test harness drives it via node
  (e.g. a driver importing the module, reading rows as JSON, printing
  `[output_rows, errors]` as JSON); the module contract is what is pinned.
- Output row keys appear in **mappings order**; later duplicate targets overwrite (last
  wins), each error-captured independently. Error objects have exactly the keys `row_index`,
  `target_field` (null for filter errors), `reason`.

## The parity requirement — guaranteed domain and named exclusions
**Behavioral parity is total**: for every plan that compiles and every JSON-representable row
list, the generated module and `eaitl.apply_ir` must agree on *which rows survive filtering,
which fields are null, and which error records exist at which (row_index, target_field)* —
no exclusions.

**Value parity** is compared at the JSON level with **numeric equality** (Python `2.0` and TS
`2` are equal; `-0` equals `0`), and is guaranteed **except** for these named, accepted
exclusions — each a language-level impossibility, not a quality bar:

1. **Number-to-text rendering** (wherever a number becomes a string: `concat`, `cast` to
   string, `hash` input, values embedded in reason strings) is guaranteed **only for safe
   integers** (|v| ≤ 2^53): Python renders `10.0` as `"10.0"` where TS cannot know it was a
   float. Non-integer or unsafe-range numbers rendered to text may differ between backends.
2. **Integer arithmetic beyond 2^53** may lose precision.
3. **Non-finite results**: inputs whose engine result is an infinity or NaN (e.g. Python's
   `float("inf")` via `cast`) are outside the domain — JSON cannot carry them anyway.
4. **Strings containing unpaired surrogates** (expressible via JSON escapes) are outside the
   domain — the two languages' UTF-8 handling of them differs irreconcilably.

Everything else — strings, booleans, nulls, safe integers, float *numeric* values, dates —
is **exact**.

## Python semantics the generated TypeScript must reproduce (each a tempting divergence)
- **equals / not_equals** use *Python* equality, not `===`: numbers and booleans compare
  numerically (`true` equals `1`; `1` equals `1.0`), strings compare to strings, `null`
  equals `null`, and any other cross-type pair is unequal (`"1"` never equals `1`). Never an
  error.
- **Ordering comparisons** (`greater_than`/`less_than`/`greater_equal`/`less_equal`) are
  defined *within* numbers-and-booleans (booleans as 1/0) and *within* strings
  (lexicographic by code unit — both languages agree); **any other pairing produces an error
  record** (`"greater_than: cannot compare 5 and 'a'"`) — JS's silent `5 < "a" → false` is
  the named wrong path.
- **divide** checks for zero **before** dividing → error record `"divide: division by
  zero"`; the generated code must never emit `NaN`/`Infinity` from division. True division on
  negatives: `divide(-7, 2) → -3.5`.
- **add/subtract/multiply/divide reject booleans and non-numbers** with an error record
  (`"add expects a numeric arg, got True"`) — even though `cast` accepts booleans; reproduce
  the asymmetry.
- **cast**: `"string"` renders per the same text rules as concat; `"int"`: a number
  truncates toward zero (`2.9 → 2`, `-2.9 → -2`), a boolean → 1/0, a string is accepted only
  in Python `int()` form — optional sign, ASCII digits, surrounding whitespace —
  **`"25.5"` is an error** (`parseInt`'s silent `25` is the named wrong path); `"float"`: a
  string in Python `float()` form (includes `"1e5"` → `100000`); anything unconvertible →
  error record `"cast: cannot cast 'abc' to int"`.
- **to_date** accepts date-only `YYYY-MM-DD` and datetimes `YYYY-MM-DD[T or space]HH:MM:SS`
  with optional `.fraction` and optional `Z` or `±HH:MM` offset (valid calendar moments),
  and returns the **date as written — never timezone-converted**:
  `"2026-07-10T23:22:11-05:00" → "2026-07-10"`, `"2026-07-10T14:22:11Z" → "2026-07-10"`;
  anything else in the domain → error record `"to_date: unparseable date 'x'"`. (Textual
  extraction is the sane implementation; the JS `Date` object's UTC conversion is the named
  wrong path.)
- **concat**: null parts render as the **empty string** (`concat("a", null, "b") → "ab"`),
  other values via the text rules; any number of args, zero → `""`; never errors.
- **hash**: SHA-256 hex digest of the UTF-8 bytes of the value's text rendering — via the
  **embedded** implementation, whose digests must equal Python `hashlib`'s for the same
  bytes (differential-tested; e.g. the digest of `"None"` — which is exactly what
  `hash(null)` produces, Python's rendering: the engine's concat/hash asymmetry, reproduced).
  Safe integers render as digits; float inputs fall under exclusion 1.
- **substring**: text-coerce, then Python slice semantics — `String.prototype.slice`
  matches for the pinned argument set: integer indices (negative allowed,
  `substring("hello", -3) → "llo"`), out-of-range → `""` without error; 2 or 3 args; a
  **boolean index is rejected** with an error record.
- **rename** behaves exactly as **copy**.
- **Argument resolution**: `{"lit": X}` (exactly that one key) → `X` always; a dynamic
  string that is a key of the row in scope → that row's value, otherwise **the string
  itself**; non-strings → themselves. Mappings resolve against the **source row**; **filters
  resolve against the mapped output row** — a filter naming a field the output lacks gets
  the literal string and silently drops every row (engine behavior, pinned).
- **Filters**: run in order after mapping; falsy → row dropped, **no error record**; an op
  failure inside a filter → row dropped **with** an error record (`target_field` null);
  remaining filters short-circuit.
- **Per-row error capture**: a failed mapping sets the field to null AND appends an error
  record; the row still emits unless filtered.
- **Reason strings** follow the engine's exact message templates; values embedded in reasons
  render Python-style within the guaranteed domain — strings single-quoted (`'abc'`),
  booleans as `True`/`False`, null as `None`, safe integers as digits; floats embedded in
  reasons fall under exclusion 1.
- **Degenerate plans**: `{"mappings": []}` compiles (OutputRow is `{}`); `transform([{a:1}])`
  → `[[{}], []]`; `transform([])` → `[[], []]`.

## Worked example (the product draft's scenario)
The draft's five-mapping plan (copy `order_id`→`id`, concat the names, divide
`amount_cents`/100, to_date `created_at`, equals `status`/"paid") compiles to a module whose
`OutputRow` is `{ id: unknown; customer_name: string | null; amount_usd: number | null;
order_date: string | null; is_paid: boolean | null }`, and running it under node over the
draft's sample row yields exactly
`[[{"id": "A1001", "customer_name": "Ada Lovelace", "amount_usd": 25.99,
"order_date": "2026-07-10", "is_paid": true}], []]` — JSON-equal to `apply_ir` on the same
inputs.

## Conventions
- Compiler side: Python standard library only; `mypy --strict` clean across the `eaitl`
  package. Generated side: the pinned tsc gate and node run above; erasable syntax only.
- New tests under `tests/` using standard-library `unittest`; the natural shape is
  differential — compile, write to a temp `.mts`, run the pinned `tsc` gate, execute under
  node via `subprocess`, JSON-compare against `apply_ir` on the same inputs, covering every
  named edge above (tsc 7.0.2 and node v24.13.1 are present on the host, verified).


PLAN GOAL: Add a TypeScript code generator to eaitl as `compile_ts(ir) -> str`, returning a standalone, zero-import, erasable-syntax ES-module TypeScript source (embedded SHA-256/UTF-8 helpers; no @types packages, no package.json) that type-checks under the pinned strict tsc invocation and runs unmodified under node v24's native type stripping, exporting Row/TransformError/OutputRow types and transform(rows) -> [output_rows, errors] whose behavior reproduces apply_ir within the pinned parity domain: behavioral parity total; value parity JSON-numeric-exact with four named exclusions (number-to-text beyond safe integers, >2^53 integer arithmetic, non-finite results, unpaired surrogates). Python semantics are reproduced where JS/TS natively diverge (Python equality incl. true==1, cross-type ordering errors, divide-by-zero as an error record never NaN, Python int()/float() string-cast acceptance, textual to_date with no timezone conversion, concat null -> empty string, hash of the Python text rendering with hashlib-equal digests). Structurally-invalid plans raise the reused MappingError at compile time; generation is deterministic (byte-identical). Done when compile_ts is importable from eaitl, the tsc gate and differential property hold with the exact examples in the task spec, mypy --strict passes, and the existing tests still pass.

PLAN CONSTRAINTS:
- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the compile_ts export to eaitl/__init__.py.
- MappingError is imported from eaitl and reused for compile-time structural failures; eaitl.parser.parse_ir may be reused internally (read-only import of frozen code).
- The generated module has zero imports and zero dependencies, uses erasable-syntax TypeScript only, performs no I/O, and reads no clock or randomness source; it must pass `tsc --strict --noEmit --target es2022 --module es2022 --moduleResolution bundler` and run unmodified as a `.mts` file under the host's node v24.
- compile_ts is deterministic: identical plan input yields byte-identical source text.
- The parity requirement is the pinned domain in the task spec: behavioral parity total; value parity JSON-numeric-exact outside the four named exclusions; reason strings per the engine's templates with the pinned value-rendering rules; the embedded SHA-256 must produce hashlib-equal digests.
- No irreversible or externally-visible actions: pure computation only.

DECISIONS (the why — do not re-decide these):
- Q: TypeScript or JavaScript?
  A: Operator (2026-07-16, redirect at the approval surface, pre-ratification): TypeScript. The chain's original JS-only scoping existed solely because tsc was absent from the host; the operator installed tsc 7.0.2, dissolving the constraint. Toolchain verified end-to-end the same day: strict tsc gate and node v24.13.1 native .mts execution both pass on the probe module; nothing else needs installing (npm present but unused).
- Q: Problem & who it's for; why now (coverage item 1)
  A: Sourced — chain-design T7 row: the second compiler backend sharing the Python compiler's op-semantic contract ('a T6 abstraction bug propagates'); next in the ratified cascade order (T2, T3, T4, T6 done).
- Q: Scope and non-goals (coverage item 2)
  A: Sourced — chain-design codegen scoping as amended 2026-07-16 (TypeScript backend; exec-gradeable behaviorally; Rust dropped). Non-goals recorded above.
- Q: Use-cases / consumers (coverage item 3)
  A: Sourced — chain-design: the job pipeline's compile stage and the CLI's code bundle emit both languages; the experiment's end-to-end oracle exec-grades generated code against apply_ir on held-out rows.
- Q: Success in outcome terms (coverage item 4)
  A: Sourced — chain-design names the oracle (generate -> execute -> compare to apply_ir); this task inherits the Python compiler's parity bar adapted to the cross-language domain pinned in the spec, plus the strict type gate.
- Q: Appetite (coverage item 5)
  A: Sourced — chain-design size/type table: rides the shared op contract (feature-size, smaller than the Python compiler); the experiment's measured per-task budget precedent bounds it.
- Q: Future-scope (coverage item 6)
  A: Sourced — the chain fixes the sequence; other backends, per-row ergonomics, and per-field input typing are post-experiment register items.
- Q: Irreversible/externally-visible actions + risk tier (coverage item 7)
  A: Sourced — pure computation, string out (constraints). Tier: full, per the chain-wide precedent.
- Q: Self-contained module: embedded SHA-256/UTF-8 instead of node:crypto
  A: Derived (two-way door, probe-verified): strict tsc rejects an inline ambient declaration for node:crypto (TS2664) without @types/node, and pulling npm/@types/node_modules into the frozen experiment repo would add unplanned infrastructure to every arm's foundation. Embedding fixed SHA-256 and UTF-8 template helpers keeps the repo npm-free, the oracle at two binaries (tsc + node), and makes the artifact runtime-agnostic. Cost: ~60-70 lines of fixed helper template per generated file, and a hand-rolled hash — mitigated by the pinned hashlib-equality differential requirement.
- Q: Typed exported surface incl. per-field OutputRow
  A: Derived (two-way door, from the product draft's own typed-codegen example): the output row type is deterministically op-derivable from the plan (each target field: the op's return type, uniformly | null since any failed mapping writes null; cast with a literal target maps to that type, dynamic to unknown). This is the payoff that makes the artifact TypeScript rather than JS-with-extensions. Cost: more template surface; the uniform | null is slightly loose for never-failing ops (concat) — accepted for one simple total rule.
- Q: ES-module .mts, erasable syntax only
  A: Derived (near-forced, probe-verified): export syntax is TS-native and type-checks dependency-free, node v24 runs .mts directly via native type stripping, and the erasable-only rule is exactly what guarantees stripping works; a CommonJS module.exports form would itself fail strict type-checking without @types/node. The tsc gate and node run commands are pinned verbatim in the spec (both verified on this host 2026-07-16).
- Q: Cross-language parity domain with named exclusions
  A: Derived (two-way door, from honesty-over-heroics): behavioral parity is total; value parity is JSON-numeric-exact except four named language-level impossibilities. An unqualified total-parity claim would be false on its face cross-language and would turn the blind suite into a lottery over undocumented corners. Cost: four documented soft spots the suite cannot grade.
- Q: Python equality and comparison semantics reproduced
  A: Derived (two-way door, from parity-over-native-idiom): equals is Python equality (true==1, 1==1.0, '1'!=1, null==null), not ===; ordering is defined within numbers-plus-booleans and within strings, erroring on any other pair — the silent cross-type comparisons are the canary-shaped wrong path. Cost: small comparison helpers in the template instead of native operators.
- Q: Reason-string parity level
  A: Derived (two-way door, one notch looser than the Python compiler, forced by the domain): the engine's message templates are exact; values embedded in reasons render Python-style per pinned rules within the guaranteed domain; floats in reasons fall under the rendering exclusion.
- Q: Standalone duplication, compile-what-the-engine-tolerates, determinism
  A: Settled by the Python compiler's ratified precedent (2026-07-16): deploy-anywhere is the product and differential suites pin the (now three) implementations together; MappingError reuse at compile time; runtime-tolerated defects compile to engine-identical behavior; byte-identical generation.

You are on the `main` branch of the repository (your cwd). Implement the spec, run the task's own checks (python3 -m mypy --strict eaitl; python3 -m unittest discover -s tests -t .), then COMMIT all changes (git add -A && git commit). Work not committed does not exist. Do not touch paths outside this repository.