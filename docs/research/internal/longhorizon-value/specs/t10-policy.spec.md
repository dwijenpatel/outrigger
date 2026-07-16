# t10-policy — human-readable render

> **GENERATED from `t10-policy.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T02:22:54Z
**Risk tier:** full

## Goal

Add policy validation to eaitl as validate_mappings(ir, target_schema=None) -> list of advisory warnings ({code, message, location}, empty = nothing flagged, never raises for warnings): pii_unhashed (pinned 10-token name list, hash-op suppression), non_deterministic_op (pinned allowlist = the engine's current 17 ops, firing only if the registry ever grows past it), and unmapped_target (with the optional target_schema, one warning per uncovered field). Malformed plans or schemas raise MappingError (run the ratified validator first). Done when the worked example holds exactly, the allowlist live-syncs against the registry in tests, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No blocking, no gating — warnings are advisory; the human decides at confirmation.
- No semantic PII detection (types, values, ML) — the pinned token list only; false negatives are accepted and named. The LLM-driven successor (name synonyms + content-based detection) is recorded in the chain's post-experiment register.
- No duplicate-target or structural checks — the ratified well-formedness validator owns those; policy assumes a well-formed plan.
- No validations-execution (the output-validations task) and no schema inference.

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the new export(s) to eaitl/__init__.py.
- Pure function: deterministic, no I/O beyond arguments, no clock, no randomness, no LLM.
- No irreversible or externally-visible actions: pure computation only.
- Warning records use exactly the {code, message, location} shape of the ratified validator's problems.
- The PII token list and the deterministic-op allowlist are exactly as pinned in the task spec; a test must assert the allowlist's keys equal the live engine registry's keys.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design task table: policy validation ('validate_mappings(ir) -> warnings: PII fields (hash targets), unsupported / non-deterministic ops, ambiguous or unmapped-required targets'); next in the ratified cascade order (T2, T3, T4, T5, T6, T7 done).
- **Scope and non-goals (coverage item 2)**
  Sourced — the chain-design row and the product draft's API surface; non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the job pipeline's validate stage and the CLI's policy report; pairs with the matcher's ambiguity-omission (unmapped targets surface here).
- **Success in outcome terms (coverage item 4)**
  Sourced — the chain's correct-or-stop bar: behavior pinned exactly enough for the blind author to test from the spec alone, with the worked example as the anchor.
- **Appetite (coverage item 5)**
  Sourced — chain-design size/type table classes this task 'feature'; the experiment's measured per-task budget precedent bounds it.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the sequence; extensions go to the post-experiment register.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure function (constraints). Tier: full, per the chain-wide precedent.
- **Advisory warnings, never a gate**
  Derived (two-way door, from the product draft's approval flow): the human decides at confirmation; policy makes the questionable visible. The alternative (hard policy gate) belongs to a deployment layer, not the library. Cost: nothing stops a user confirming past every warning — by design.
- **Pinned 10-token PII list, exact token match**
  Derived (two-way door, from determinism-over-coverage): an exact, modest, spec-pinned list is blind-testable and has zero false positives on ordinary names; it will miss creative PII names — false negatives are accepted and named (semantic detection is the excluded-LLM path's territory). Cost: real-world coverage is thin; extending the list is a one-line, version-visible edit.
- **Deterministic-op allowlist that cannot fire today**
  Derived (two-way door, from the freeze-forward design): the allowlist equals the engine's 17 current ops, so the class is inert until the registry grows — at which point any new op warns until explicitly allowlisted (deterministic-by-default posture). The live-sync test mirrors the IR-contract task's ratified arity-table pattern.
- **target_schema as optional second parameter**
  Derived (two-way door, from the matcher's ratified precedent): unmapped-target detection is impossible from the plan alone; optional input enables it, absence skips it, recorded rather than silently divergent from the chain sketch's one-argument signature.

## Open questions

- none

## Task `policy-validation` — Advisory policy warnings over a well-formed plan

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Provides:** policy-validation · **Requires:** eaitl-engine, ir-well-formedness-validator

---

# Policy validation — advisory warnings on an approved-to-be plan

## What and why
Before a plan is confirmed, an enterprise gate wants to ask: is anything sensitive flowing
through unhashed? does the plan use anything non-deterministic? did the proposal leave
target fields unmapped? This task adds that check as **advisory warnings** — it blocks
nothing (the human decides at confirmation); it makes the questionable visible.

## Public interface (pin exactly)
- New file **`eaitl/policy.py`** exporting one function:
  - `validate_mappings(ir: dict[str, Any], target_schema: dict[str, Any] | None = None)
     -> list[dict[str, str]]`
- Add `validate_mappings` to `eaitl/__init__.py` (the only edit to existing files).
- **Returns a list of warnings** — same record shape as the well-formedness validator's
  problems (`{"code", "message", "location"}`), empty when nothing is flagged. **Warnings
  never raise**; but a plan the ratified validator finds problems in raises `MappingError`
  naming the first problem (policy analyzes well-formed plans; run the validator first).
- `target_schema`, when given, uses the introspection task's ratified shape
  (`{"fields": [{"name", "type"}]}`) and enables the unmapped-target class; without it that
  class is skipped (same optional-input precedent as the matcher). A malformed
  target_schema raises `MappingError`.

## The warning classes (pin exactly)
1. **`pii_unhashed`** — a mapping touches a PII-named field and its op is not `hash`.
   "PII-named": any name token (split on non-alphanumerics, lowercased) of the
   `target_field` OR of any dynamic string argument is in the **pinned token list**:
   `email · ssn · phone · address · dob · birthdate · password · passport · iban · salary`.
   `hash` as the mapping's op suppresses the warning for that mapping. Location
   `mappings[i]`. (The list is deliberately modest and exact — it will miss creative names;
   policy is advisory, and false-negatives are named as accepted.)
2. **`non_deterministic_op`** — a mapping's or filter's op is outside the **pinned
   deterministic allowlist**, which is exactly the engine's current 17 ops (`copy`,
   `rename`, `concat`, `substring`, `cast`, `add`, `subtract`, `multiply`, `divide`,
   `to_date`, `equals`, `not_equals`, `greater_than`, `less_than`, `greater_equal`,
   `less_equal`, `hash`). Today the registry equals the allowlist, so this class cannot
   fire — it exists so a future registry addition (a `now`, a `random`, a `lookup`) warns
   until explicitly allowlisted. Location `mappings[i].transform` / `filters[i]`.
3. **`unmapped_target`** — with `target_schema` given: a schema field no mapping's
   `target_field` covers. One warning per missing field, location `target_schema`, in
   schema order. (This is the matcher's ambiguity-omission surfacing to the human —
   the two tasks are designed as a pair.)

## Worked example
Plan: `copy(email_address) -> email` plus `copy(order_id) -> id`, target schema with fields
`email`, `id`, `region`. Warnings, exactly two:
`{"code": "pii_unhashed", "location": "mappings[0]", ...}` (token `email` on both sides,
op is copy) and `{"code": "unmapped_target", "location": "target_schema", ...}` for
`region`. Changing the first mapping's op to `hash` removes the first warning; omitting
`target_schema` removes the second. An IR whose every op is in the allowlist never yields
class 2 today — a test may assert the allowlist equals the engine registry's key set (the
same live-sync pattern the IR-contract task ratified for arities).

## Conventions
Python stdlib only; `mypy --strict` clean; new stdlib-`unittest` tests under `tests/`.
