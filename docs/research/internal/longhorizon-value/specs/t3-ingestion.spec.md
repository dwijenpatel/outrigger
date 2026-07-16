# t3-ingestion — human-readable render

> **GENERATED from `t3-ingestion.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-15T23:59:14Z
**Risk tier:** full

## Goal

Add source introspection to eaitl as a new pure function `introspect_source(text, fmt)` that parses raw CSV or JSON content and returns {schema, samples}: an ordered field list with one inferred type per field (vocabulary: string/int/float/bool/date/timestamp, under exact classification rules including the leading-zero, bool-token, int-vs-float, and date/timestamp edges) plus up to 10 raw, uncoerced sample rows. Malformed input (unparseable, zero rows, duplicate/empty CSV header, ragged CSV row, non-array JSON) raises IntrospectError; value-level oddities never raise. Done when the interface is importable from eaitl, the classification rules hold with the exact examples in the task spec, the package passes mypy --strict, and the existing engine tests still pass.

## Non-goals

- No Parquet, database, or connector ingestion — CSV and JSON text only (product draft MVP boundary; chain scope).
- No statistics beyond the schema and sample rows (the draft's 'stats' are out of the chain's scope for this task).
- No target-schema handling: the matcher consumes a user-supplied target schema directly; this task introspects SOURCE data only (chain task table).
- No type coercion of values — samples are raw; casting is the engine's job via the mapping plan.
- No file I/O — the function takes text content, never a path; no streaming (whole text in memory).
- No LLM involvement; fully deterministic.

## Constraints

- The committed engine at c646832 must not change: the only edit to existing files is adding the introspect_source and IntrospectError exports to eaitl/__init__.py.
- introspect_source is a pure function: no filesystem, network, clock, randomness, or locale dependence; identical (text, fmt) always yields identical output.
- IntrospectError is raised for exactly the fatal cases enumerated in the spec; no other input may raise.
- The type vocabulary is exactly {string, int, float, bool, date, timestamp}; the classification rules in the spec are exhaustive and first-match-wins.
- No irreversible or externally-visible actions: pure computation only.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design.md task table: T3 is the ingestion step feeding the deterministic matcher, preview pipeline, and CLI; next task in the ratified cascade order (T2 done 2026-07-15).
- **Scope and non-goals (coverage item 2)**
  Sourced — chain-design T3 row ('parse CSV/JSON source data, infer field types, extract sample rows -> {schema, samples}') + the product draft's MVP boundaries (single-table, batch, no connectors). Non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the deterministic matcher (T5) consumes {schema, samples} to propose mappings; the preview pipeline (T8) and job pipeline/CLI (T11/T12) consume it downstream.
- **Success in outcome terms (coverage item 4)**
  Sourced — chain-design Canary A: correct type inference on the named edge families (leading-zero numeric strings, bool-like tokens, int-vs-float), precise enough that a blind author can write acceptance tests from this spec alone.
- **Appetite (coverage item 5)**
  Sourced — the experiment's per-task budget precedent (~$7/task measured on the engine slice; feature-size task, one worker session per arm).
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the full task sequence T2-T12 in advance; no expansion of this task is planned inside the experiment. Post-experiment additions go to the recorded follow-ups register in chain-design.md.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure function, no side effects (constraints). Tier: full, per the chain-wide precedent ratified in the T2 plan (every chain task runs full-tier: blind suite + gate).
- **Public interface shape**
  Derived (two-way door, from precedent): one public entry introspect_source(text, fmt) -> dict plus IntrospectError, exported from eaitl — mirrors the engine's apply_ir and T2's validate_ir single-function pattern; text-content input (not a path) keeps it pure and trivially testable.
- **Type vocabulary**
  Derived (two-way door until the experiment starts, from principle single-source-of-naming): {string,int,float,bool,date,timestamp} — reuses the engine's cast target names verbatim (string/int/float) and adds the three the draft's examples need; the draft's 'integer' normalizes to 'int'. Freezes when the runs begin.
- **Numeric-string recognition**
  Derived (two-way door, from principle determinism-over-convenience): pinned ASCII-only rules with the leading-zero exclusion, no '+' form, no scientific notation, no underscores — NOT Python's int()/float() parse, whose surprising acceptances (unicode digits, '1_000', ' 25 ', 'nan') are exactly the silent-wrong shapes Canary A exists to catch.
- **Bool-like tokens**
  Derived (two-way door, from the chain's canary design): case-insensitive true/false only; '0'/'1' classify int and 'yes'/'no' classify string — treating 0/1 as bool is the documented tempting-wrong-path.
- **Heterogeneous column fallback**
  Derived (two-way door, from principle safe-defaults): any mix other than int+float -> string, uniformly — a column the rules cannot type consistently gets no cast proposed downstream; int+float promotes to float.
- **Malformed-input strictness**
  Derived (two-way door, from the project's correct-or-stop thesis + engine precedent MappingError): structural defects (unparseable, zero rows, duplicate/empty header, ragged row, non-array JSON) are fatal IntrospectError — a silently-garbage schema must not enter the chain; value-level oddities never raise.
- **Samples policy**
  Derived (two-way door, from principle evidence-not-fabrication): first min(10, rows) rows, raw and uncoerced (classification strips whitespace for testing; samples keep the original), in input order.
- **JSON parsing edge policy**
  Derived (two-way door, from stdlib-behavior-as-documented): json.loads defaults — NaN/Infinity accepted and classify float; duplicate keys in one object keep the last value; a single leading BOM stripped for CSV.
- **Where the new exception lives**
  Derived (two-way door, from the T2 frozen-engine precedent): IntrospectError is defined in the new eaitl/introspect.py, not in the engine's errors.py — the engine files stay untouched; only __init__.py gains export lines.

## Open questions

- none

## Task `source-introspect` — Add CSV/JSON source introspection with pinned type inference

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Depends on:** none · **Provides:** source-introspection · **Requires:** none

---

# Source introspection for eaitl — parse CSV/JSON, infer field types, extract samples

## What and why
eaitl converts source rows into target rows using an approved mapping plan. Before any mapping
can be proposed, the tool must look at the raw source data and answer: what fields exist, what
type is each, and what do example rows look like? This task builds that step — **source
introspection**: raw CSV or JSON text in, `{schema, samples}` out. The deterministic matcher
(a later task) consumes this output to propose mappings; the preview pipeline and CLI consume
it downstream. Wrong type inference here propagates through every later stage (matcher proposes
a wrong cast, engine executes it, compilers bake it in), so the inference rules below are exact
correctness requirements, not suggestions.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/introspect.py`** exporting:
  - `introspect_source(text: str, fmt: str) -> dict[str, Any]`
  - `class IntrospectError(Exception)` — raised only for the fatal cases named below.
- Add both to `eaitl/__init__.py` so `from eaitl import introspect_source, IntrospectError`
  works. **Those export lines are the ONLY edit to existing files**; every engine file stays
  exactly as committed at `c646832`.
- **Input:** `text` is the raw file *content* (never a path — the function does no I/O);
  `fmt` is `"csv"` or `"json"`. Any other `fmt` → `IntrospectError`.
- **Output:**
  ```
  {
    "schema": {"fields": [{"name": <str>, "type": <str>}, ...]},
    "samples": [<row dict>, ...]
  }
  ```
- Pure function: no filesystem, no network, no clock, no randomness, no locale dependence.
  Same `(text, fmt)` → same result, always.

## The type vocabulary
`"type"` is exactly one of: **`string` · `int` · `float` · `bool` · `date` · `timestamp`**.
(Aligned with the engine's `cast` targets `string`/`int`/`float`; `bool`, `date`, `timestamp`
extend them. The product draft's `integer` maps to `int`; its source-schema `timestamp` and
target-schema `date` are both kept, distinguished by value shape.)

## Parsing
**CSV** (`fmt="csv"`): standard-library `csv` defaults (comma-delimited). A single leading
Unicode BOM (`﻿`) is stripped before parsing. The **first row is the header** and defines
the field names and their order. Every value is a string. Fatal (`IntrospectError`):
- a duplicate header name, or an empty header name ("", after the row is parsed);
- a **ragged row** — any data row with more or fewer cells than the header;
- zero data rows (header-only or empty input).

**JSON** (`fmt="json"`): `json.loads` with default settings (so the non-standard `NaN` /
`Infinity` literals parse, and classify as `float`; a duplicate key within one object keeps the
last value — both are documented `json`-module behavior). The document must be an **array of
objects**; anything else — a bare object, an array containing a non-object, unparseable text —
is fatal. An empty array (zero rows) is fatal. Field names are the **union of keys across all
rows, in first-seen order** (scanning rows in order, keys in each row's order).

## Value classification (per value)
"Missing" values are excluded from inference and never veto a type: JSON `null`, an absent key
(JSON), and — in both formats — a value that is an empty string or only whitespace.

JSON-native values classify directly: `true`/`false` → `bool` (**checked before any numeric
test** — in Python `isinstance(True, int)` is `True`; a `bool` must never classify as `int`);
int → `int`; float → `float` (`25.0` stays `float`; `NaN`/`Infinity` → `float`); a nested
object or array → `string` (opaque; kept raw in samples). JSON *strings* fall through to the
string rules below, exactly like CSV values.

**String content rules** — applied to a copy stripped of leading/trailing whitespace (samples
keep the raw value; `" 25 "` classifies as `int`, the sample still shows `" 25 "`). First match
wins:
1. Case-insensitive `true` / `false` → `bool`. **Nothing else is bool-like**: `yes`, `no`,
   `t`, `f`, `0`, `1` are NOT bool (`"0"`/`"1"` → `int`; `"yes"` → `string`).
2. Integer string: an optional leading `-`, then **ASCII digits `0-9` only** — with the
   **leading-zero rule**: two or more digits starting with `0` is NOT numeric.
   `"0"` → `int` · `"25"` → `int` · `"-3"` → `int` · **`"007"` → `string`** ·
   **`"02115"` → `string`** · `"-007"` → `string` · `"+5"` → `string` (no `+` form) ·
   `"١٢٣"` (non-ASCII digits) → `string` · `"1_000"` → `string`.
3. Float string: the integer-string form (same sign and leading-zero rules on the integer
   part, except a bare `0` integer part is fine), then `.`, then one or more ASCII digits.
   `"25.99"` → `float` · `"-0.5"` → `float` · `"0.5"` → `float` · `".5"` → `string` ·
   `"5."` → `string` · `"007.5"` → `string` · **`"1e5"` → `string`** (no scientific
   notation) · `"NaN"` → `string` (the string; JSON-native NaN is `float`).
4. Date: exactly the 10-character zero-padded form `YYYY-MM-DD`, a valid calendar date.
   `"2026-07-10"` → `date` · `"2026-7-1"` → `string` (not zero-padded) · `"2026-13-45"` →
   `string` (invalid date).
5. Timestamp: the zero-padded form `YYYY-MM-DDTHH:MM:SS`, optionally `.ffffff` fractional
   seconds, optionally a `Z` or `±HH:MM` offset, and the whole thing must be a valid moment.
   `"2026-07-10T14:22:11Z"` → `timestamp` · `"2026-07-10T14:22:11"` → `timestamp` ·
   `"2026-07-10T14:22:11+05:30"` → `timestamp` · `"14:22:11"` → `string` (no date part).
6. Anything else → `string`.

## Column type (fold over the column's non-missing values)
- Zero rows is already fatal; a column whose values are ALL missing → `string`.
- All values the same type → that type.
- A mix of exactly `int` and `float` → `float` (`[1, 2.5]` → `float`; `["25", "25.0"]` →
  `float`).
- **Any other mix → `string`** — the uniform safe fallback: a column the rules cannot type
  consistently gets no cast proposed downstream. `["true", "0"]` → `string` ·
  `["2026-07-10", "2026-07-10T14:22:11Z"]` (date + timestamp) → `string`.

## Samples
`samples` = the **first `min(10, row_count)` rows, in input order, values raw and uncoerced**
(introspection reports evidence; coercion is the engine's job). CSV sample rows carry every
header key, empty cell = `""`. JSON sample rows carry exactly the keys that row actually had,
values as `json.loads` produced them.

## Worked example (the product draft's raw_orders row)
Input (JSON, one row):
```json
[{"order_id": "A1001", "customer_first_name": "Ada", "customer_last_name": "Lovelace",
  "amount_cents": 2599, "created_at": "2026-07-10T14:22:11Z", "status": "paid"}]
```
Output:
```json
{"schema": {"fields": [
   {"name": "order_id", "type": "string"},
   {"name": "customer_first_name", "type": "string"},
   {"name": "customer_last_name", "type": "string"},
   {"name": "amount_cents", "type": "int"},
   {"name": "created_at", "type": "timestamp"},
   {"name": "status", "type": "string"}]},
 "samples": [{"order_id": "A1001", "customer_first_name": "Ada",
   "customer_last_name": "Lovelace", "amount_cents": 2599,
   "created_at": "2026-07-10T14:22:11Z", "status": "paid"}]}
```

## Error behavior summary
`IntrospectError` for exactly: unknown `fmt`; undecodable/unparseable input; JSON that is not
an array of objects; zero data rows; duplicate or empty CSV header name; ragged CSV row.
Everything value-level (weird strings, nulls, nested values, mixed types) is handled by the
classification rules and **never raises**.

## Conventions
- Python standard library only; no third-party dependencies.
- `mypy --strict` clean across the `eaitl` package.
- Functional style; typed internal helpers; plain-dict public boundary.
- New tests under `tests/` using standard-library `unittest`.
