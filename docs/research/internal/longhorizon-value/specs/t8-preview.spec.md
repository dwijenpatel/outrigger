# t8-preview — human-readable render

> **GENERATED from `t8-preview.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T02:22:54Z
**Risk tier:** full

## Goal

Add the preview pipeline to eaitl as run_preview(text, fmt, ir) -> {preview_rows, errors}: introspect the raw source text, apply the plan to the introspection samples (<=10 rows by construction), and return the engine's output rows and error records under exactly those two keys, passing fatal errors through unchanged (IntrospectError for bad input, MappingError for structurally-invalid plans) and adding no error vocabulary of its own. Done when the worked example holds, the composition is differential-equal to calling the two ratified pieces by hand, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No full-file transformation — preview is bounded to introspection's sample cap by design; transforming everything is the generated code's job in deployment.
- No schema in the return — callers wanting it call introspection directly.
- No new error types, no warning layer, no policy checks (the policy task's job).
- No CLI or pipeline wiring (later tasks).

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the new export(s) to eaitl/__init__.py.
- Pure function: deterministic, no I/O beyond arguments, no clock, no randomness, no LLM.
- No irreversible or externally-visible actions: pure computation only.
- Composition only: run_preview must behave exactly as introspect_source then apply_ir — it may not re-implement, filter, or augment either component's behavior.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design task table: the preview pipeline ('run_preview(source_data, ir) -> {preview_rows, errors}: introspect -> apply_ir'), the chain's first integration task; next in the ratified cascade order (T2, T3, T4, T5, T6, T7 done).
- **Scope and non-goals (coverage item 2)**
  Sourced — the chain-design row and the product draft's API surface; non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the job pipeline's preview stage and the CLI's preview output.
- **Success in outcome terms (coverage item 4)**
  Sourced — the chain's correct-or-stop bar: behavior pinned exactly enough for the blind author to test from the spec alone, with the worked example as the anchor.
- **Appetite (coverage item 5)**
  Sourced — chain-design size/type table classes this task 'integration'; the experiment's measured per-task budget precedent bounds it.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the sequence; extensions go to the post-experiment register.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure function (constraints). Tier: full, per the chain-wide precedent.
- **Three-argument signature vs the chain sketch's two**
  Derived (two-way door, from the ratified introspection contract): introspection requires (text, fmt), so the sketch's 'source_data' becomes two explicit parameters — the same signature-precision move the matcher's plan made, recorded rather than silently diverging.
- **Preview applies the plan to the samples only**
  Derived (two-way door, from the product draft: 'execute transform on sample rows only'): bounded cost by construction; full-run transformation is the deployed generated code's job, not the preview's.
- **Pure pass-through error contract**
  Derived (two-way door, from composition-over-invention): fatal errors propagate unchanged and per-row errors return verbatim, so the preview adds zero new vocabulary — a caller that understands the two ratified pieces understands the preview. Cost: no preview-specific error niceties.

## Open questions

- none

## Task `preview-pipeline` — Compose introspection and the engine into a bounded preview

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Provides:** preview-pipeline · **Requires:** eaitl-engine, source-introspection

---

# Preview pipeline — introspect the source, apply the plan to its samples

## What and why
The product's preview step answers "what would this plan actually produce?" before anything
is approved: run the transform **on sample rows only**. This task is the chain's first
integration piece — it composes two ratified components (source introspection and the
engine) behind one call, and its value is the seam: raw source text in, previewed output
rows out.

## Public interface (pin exactly)
- New file **`eaitl/preview.py`** exporting one function:
  - `run_preview(text: str, fmt: str, ir: dict[str, Any]) -> dict[str, Any]`
- Add `run_preview` to `eaitl/__init__.py` (the only edit to existing files).
- **Behavior, exactly**: `introspect_source(text, fmt)` → take its `samples` (the first ≤10
  raw rows) → `apply_ir(ir, samples)` → return
  `{"preview_rows": <output_rows>, "errors": <errors>}` — the engine's two results under
  those two keys, nothing else (no schema key; introspection's schema is available by
  calling introspection directly).
- **Error behavior — pass-through, add nothing**: a fatal introspection input raises
  `IntrospectError` (unchanged, from the introspection task); a structurally-invalid plan
  raises `MappingError` (unchanged, from the engine); per-row transform errors come back in
  `"errors"` exactly as `apply_ir` produced them. This function adds no error vocabulary of
  its own.
- Preview is **bounded by construction**: it never transforms more than introspection's
  sample cap (10 rows) — previewing a million-row file costs the same as previewing eleven.

## Worked example
With the product draft's raw_orders JSON (one row) as `text`, `fmt="json"`, and the draft's
five-mapping plan: `run_preview` returns
`{"preview_rows": [{"id": "A1001", "customer_name": "Ada Lovelace", "amount_usd": 25.99,
"order_date": "2026-07-10", "is_paid": true}], "errors": []}` — exactly
`apply_ir(ir, samples)` re-keyed. A plan whose `divide` hits a zero in a sample row returns
that row with the field null and the engine's error record in `"errors"` — previews show
failures, they don't hide them.

## Conventions
Python stdlib only; `mypy --strict` clean; new stdlib-`unittest` tests under `tests/`
(natural shape: differential against composing the two ratified pieces by hand, plus the
error pass-through cases).
