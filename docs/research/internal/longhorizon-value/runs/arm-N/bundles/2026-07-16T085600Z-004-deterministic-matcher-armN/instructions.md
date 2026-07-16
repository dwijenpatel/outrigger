You are the IMPLEMENTER for task `deterministic-matcher`: Propose mappings deterministically from schemas and examples

SPEC:
# Deterministic mapping matcher — propose a plan from schemas and examples, or propose nothing

## What and why
Given a source schema, a target schema, and sample data, eaitl proposes a **mapping plan** the
human then edits and approves. The full product uses an LLM for semantic proposals; this chain
deliberately excludes it — this task is the **deterministic matcher**: name normalization,
type compatibility, and example-driven inference, with **no model call and no randomness**.
Its governing principle is the project's own: **propose only what the evidence determines;
when a match is ambiguous, propose nothing** — an unmapped field is a loud, visible gap the
policy checker flags and the human fills by editing the plan JSON (the chain's recorded
human-modification channel), while a guessed mapping is a silent wrong that compounds through
the compilers into shipped data.

## Public interface (pin exactly — an independent author writes hidden tests against this)
- New file **`eaitl/match.py`** exporting:
  - `propose_mappings(source_schema: dict[str, Any], target_schema: dict[str, Any],
     samples: list[dict[str, Any]], target_examples: list[dict[str, Any]] | None = None)
     -> dict[str, Any]`
  - `class MatchError(Exception)` — raised only for the fatal input cases below.
- Add both to `eaitl/__init__.py`. **Those export lines are the ONLY edit to existing files.**
- **Schemas** (both source and target) use the introspection task's ratified shape:
  `{"fields": [{"name": <str>, "type": <str>}, ...]}` with type in
  `string · int · float · bool · date · timestamp`. `samples` are raw source rows (the
  introspection task's output, or any rows); `target_examples`, if given, are desired output
  rows **aligned by index with `samples`** (row i of each corresponds).
- **Returns an IR dict**: `{"mappings": [...], "filters": [], "validations": []}` — mappings
  in **target-schema field order** (unmapped targets simply omitted), filters and validations
  always present and empty (assertions are the human's to add). No `source`/`target` identity
  keys (the caller's to add), no proposer metadata (`confidence`/`rationale` are the LLM
  path's, excluded from this chain). The result must always pass the ratified well-formedness
  validator with zero problems.
- **Canonical argument emission**: column references are plain strings (`"order_id"`);
  every literal is `{"lit": X}` — never a bare value (a bare string literal like `" "`
  would be indistinguishable from a column reference).
- **Fatal (`MatchError`)**: a schema not of the shape above (missing/non-list `fields`,
  a field without a string `name` or with a `type` outside the six, **duplicate field
  names**); `samples` not a list of dicts; `target_examples` given but not a list of dicts
  of the same length as `samples`. Everything else never raises. Extra keys anywhere are
  ignored (lenient precedent).
- **Deterministic**: identical inputs → identical output, always. No I/O, no clock, no
  randomness, no LLM.

## The matching ladder (per target field, in target-schema order; first lane that yields a
## unique proposal wins; a tie or inconsistency at a lane means the ladder CONTINUES to the
## next lane; if no lane yields a unique proposal, the target is omitted)

**Name normalization** (used by lanes 1–2): lowercase, then drop every non-alphanumeric
character (`"Order_ID"` → `"orderid"`). **Tokens**: split the raw name on non-alphanumerics,
lowercase (`"customer_first_name"` → `{customer, first, name}`).

- **Lane 1 — exact name**: exactly one source field with the same normalized name → map it
  (op by the type rules below). Two or more → tie, continue.
- **Lane 2 — containment**: exactly one source field whose normalized name contains the
  target's normalized name, or is contained by it (`"id"` ⊂ `"orderid"`) → map it. Ties
  continue.
- **Lane 3 — example-driven** (only when `target_examples` is provided; uses index-aligned
  (sample, example) pairs where the target field's example value is present and non-null;
  requires **at least one usable pair**, and every rule below requires **consistency across
  all usable pairs** — one inconsistent pair kills the inference):
  - **Ratio (unit conversion)**: numeric target; exactly one numeric source field and one
    factor k from the fixed set **{10, 100, 1000}** with `source == round(example * k)`
    exactly on every pair → `divide(col, {"lit": k})`. (Fixed set by design: float-equality
    fishing beyond it is guess-shaped; an exotic ratio is the human's edit.)
  - **Concatenation**: string target; exactly one ordered pair of distinct string-typed
    source fields (candidates enumerated in source-schema order) and one constant separator
    string such that `str(a) + sep + str(b) == example` on every pair →
    `concat(colA, {"lit": sep}, colB)`.
  - **Equality (the bool lane)**: bool target; exactly one source field and one literal v
    (drawn from that field's sample values) with `(sample[field] == v) == example` on every
    pair, **and the examples must include at least one true and one false** (a single-truth
    pattern cannot distinguish candidates — see the worked example) → `equals(col, {"lit": v})`.
  - **Date extraction**: date target; exactly one source field whose sample values are
    strings the engine's `to_date` maps to the example on every pair → `to_date(col)`.
  - Two or more distinct inferences succeeding for the same target at this lane → tie,
    continue.
- **Lane 4 — unique type compatibility**: exactly one source field whose type is compatible
  with the target's (same type; or `timestamp` source → `date` target; or `int` ↔ `float`)
  **and** the target is the only target field of its type still unmapped → map it.

**Op selection by types** (lanes 1, 2, 4): same type → `copy`; `int`→`float` or
`float`→`int` → `cast(col, {"lit": "float"|"int"})`; `timestamp` (or `date`) source →
`date` target → `to_date(col)`; `string` source → `int`/`float` target →
`cast(col, {"lit": ...})`; **`bool` target from a non-bool source is never proposable
outside lane 3** — the engine has no bool cast; comparisons are how booleans are produced
(operator-recorded requirement, 2026-07-15) — so without examples such a target is omitted.
Any pairing not listed → not proposable at that lane.

## Worked example (pinned exactly — the product draft's scenario, extended to three samples)
A single sample row cannot make equality inference deterministic (with one all-true example,
`equals(order_id, {"lit": "A1001"})` and `equals(status, {"lit": "paid"})` are
indistinguishable — the spec's skip rule would omit `is_paid`). Three samples distinguish:

Source schema: `order_id string · customer_first_name string · customer_last_name string ·
amount_cents int · created_at timestamp · status string`. Target schema: `id string ·
customer_name string · amount_usd float · order_date date · is_paid bool`.
Samples: `("A1001", "Ada", "Lovelace", 2599, "2026-07-10T14:22:11Z", "paid")`,
`("A1002", "Grace", "Hopper", 1250, "2026-07-11T09:00:00Z", "refunded")`,
`("A1003", "Alan", "Turing", 999, "2026-07-12T18:45:30Z", "paid")` (as row dicts).
Target examples: `("A1001", "Ada Lovelace", 25.99, "2026-07-10", true)`,
`("A1002", "Grace Hopper", 12.50, "2026-07-11", false)`,
`("A1003", "Alan Turing", 9.99, "2026-07-12", true)`.

`propose_mappings` must return exactly:

```json
{"mappings": [
  {"target_field": "id", "transform": {"op": "copy", "args": ["order_id"]}},
  {"target_field": "customer_name", "transform": {"op": "concat",
     "args": ["customer_first_name", {"lit": " "}, "customer_last_name"]}},
  {"target_field": "amount_usd", "transform": {"op": "divide",
     "args": ["amount_cents", {"lit": 100}]}},
  {"target_field": "order_date", "transform": {"op": "to_date", "args": ["created_at"]}},
  {"target_field": "is_paid", "transform": {"op": "equals",
     "args": ["status", {"lit": "paid"}]}}
 ], "filters": [], "validations": []}
```

(`id` via lane 2; the other four via lane 3: concatenation with separator `" "`, ratio 100,
date extraction, equality on `status`/`"paid"` — note `equals(order_id, ...)` fails the
consistency rule on rows 2–3 and `equals(status, "paid")` is the unique survivor.)

Boundary examples to pin behavior (each must hold):
- Same inputs **without** `target_examples` → exactly three mappings:
  `id` → `copy(order_id)` (lane 2); `amount_usd` → `cast(amount_cents, {"lit": "float"})`
  (lane 4: the only numeric source, the only unmapped float target); `order_date` →
  `to_date(created_at)` (lane 4: the only timestamp source, the only unmapped date target).
  `customer_name` is **omitted** (lane 2 finds no containment; lane 4 sees four string
  sources — a tie) and `is_paid` is **omitted** (bool target without examples — never
  proposable).
- Two source fields normalizing identically (`"Order ID"` and `"order_id"`) → fatal
  duplicate? No — duplicates are *exact raw names*; these two normalize identically, so any
  target matching them at lanes 1–2 ties and falls through.
- Empty `samples` (`[]`) is legal: lane 3 is inert (and `target_examples`, if given, must
  also be `[]`); lanes 1, 2, 4 still operate.
- Zero-field target schema → `{"mappings": [], "filters": [], "validations": []}`.

## Conventions
- Python standard library only; `mypy --strict` clean across the `eaitl` package.
- Functional style; plain-dict public boundary.
- New tests under `tests/` using standard-library `unittest`. Natural shapes: the worked
  example exact-match; each lane in isolation; every skip rule (ties, inconsistent pairs,
  single-truth equality); the no-examples fallbacks; validator-cleanliness of every output;
  determinism (repeated calls byte-equal).


PLAN GOAL: Add the deterministic mapping matcher to eaitl as propose_mappings(source_schema, target_schema, samples, target_examples=None) -> IR dict, proposing mappings via a pinned four-lane ladder (exact normalized name; unique containment; example-driven inference — fixed-set ratio {10,100,1000}, two-field concatenation with constant separator, distinguishing equality for bool targets, to_date extraction; unique type compatibility) with the ambiguity rule: any tie or inconsistency yields NO proposal for that target (omitted, for the policy checker to flag) — never a guess. Output is always well-formed per the ratified validator, in target-schema order, with literals canonically as {lit: X}; bool targets are never proposable without examples (the engine has no bool cast — equality is how booleans are produced). Malformed inputs raise MatchError; the function is pure and deterministic, no LLM. Done when the pinned worked example returns exactly the specified IR, the boundary examples hold, mypy --strict passes, and the existing tests still pass.

PLAN CONSTRAINTS:
- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the propose_mappings and MatchError exports to eaitl/__init__.py.
- Every returned IR must pass the ratified well-formedness validator with zero problems, and must resolve on the engine exactly as proposed (canonical {lit: X} literals; plain-string column references).
- The ambiguity rule is absolute: a tie or an inconsistent example set at a lane never resolves by preference, order, or heuristic weight at that lane — it falls through, and a target no lane resolves uniquely is omitted.
- propose_mappings is a pure function: deterministic, no I/O, no clock, no randomness, no model calls.
- No irreversible or externally-visible actions: pure computation only.

DECISIONS (the why — do not re-decide these):
- Q: Problem & who it's for; why now (coverage item 1)
  A: Sourced — chain-design T5 row: the deterministic matcher (name-normalization + similarity + type-compat + example-driven op inference, no LLM); a compounding hotspot (wrong IR is wrong everywhere downstream); next in the ratified cascade order (T2, T3, T4, T6, T7 done).
- Q: Scope and non-goals (coverage item 2)
  A: Sourced — the chain's deterministic-spine scoping (LLM proposer excluded for gradeability) and the product draft's agent-loop step 1 ('deterministic matcher computes lexical/type candidates first'). Non-goals recorded above.
- Q: Use-cases / consumers (coverage item 3)
  A: Sourced — chain-design dependency table: the job pipeline's propose stage and the CLI consume the proposed IR; the human edits it (the operator-recorded edit-the-IR-JSON channel) and the freeze task stamps the approved version.
- Q: Success in outcome terms (coverage item 4)
  A: Sourced — the chain's correct-or-stop thesis applied to proposing: determinate proposals a blind author can test exactly (the pinned worked example), with ambiguity surfacing as omissions the policy task flags, never as guesses.
- Q: Appetite (coverage item 5)
  A: Sourced — chain-design size/type table classes T5 'feature'; the experiment's measured per-task budget precedent bounds it.
- Q: Future-scope (coverage item 6)
  A: Sourced — the chain fixes the sequence; the LLM proposer, fuzzy similarity, and richer ratio/inference lanes are post-experiment register items.
- Q: Irreversible/externally-visible actions + risk tier (coverage item 7)
  A: Sourced — pure function (constraints). Tier: full, per the chain-wide precedent.
- Q: Ambiguity policy
  A: Derived (two-way door, from the project's correct-or-stop thesis): a tie or inconsistency never resolves by guess — the target is omitted and the policy task flags it; the human fills the gap through the recorded IR-edit channel. The alternative (best-effort tie-breaking by source order or score) maximizes coverage but manufactures exactly the silent-wrong compounding the chain exists to measure. Cost, plainly: fewer auto-mapped fields — a human edits more plans.
- Q: target_examples as an explicit optional parameter
  A: Derived (two-way door, from the product draft's own API): the chain sketch's three-argument signature cannot support the example-driven lane it names — inferring divide-by-100 or equals('paid') requires desired output examples, which the draft's propose endpoint receives as example_output_rows. Added as an optional fourth parameter, index-aligned with samples; without it the example lane is inert and bool targets are unproposable (recorded consequence).
- Q: The bool lane (operator-recorded requirement)
  A: Sourced — operator note 2026-07-15 (chain-design T5 row): a bool-typed target over categorical string samples must be proposable as equals(col, lit); the engine has no bool cast — comparisons are how booleans are produced. Pinned with the distinguishing-examples rule (at least one true and one false), because a single-truth example set cannot separate candidates — the worked example demonstrates both the success and the necessity.
- Q: Fixed ratio set {10, 100, 1000} with exact integer verification
  A: Derived (two-way door, from determinism-over-cleverness): unit conversions are overwhelmingly decimal-shift (cents/dollars, milli/base); verifying source == round(example*k) exactly avoids float-equality fishing, and exotic ratios (x2.54, /12) are the human's one-line edit. Cost: genuinely linear non-decimal conversions are not auto-proposed.
- Q: Pinned lane ladder and canonical output form
  A: Derived (two-way door, from blind-gradeability): the four-lane precedence, per-lane uniqueness, target-schema-order output, omit-unmapped, always-empty filters/validations, and {lit: X}-always literal emission (a bare string literal is indistinguishable from a column reference — the draft's bare-100 sugar is rejected) make every output exactly predictable from the spec. Cost: a dumb-but-predictable matcher; cleverness is the excluded LLM's job.
- Q: Worked example extended to three samples
  A: Derived (forced by the skip rule, documented in the spec): the draft's single sample row makes equality inference inherently ambiguous (every field that distinguishes the row ties), so the pinned example uses three rows — which is itself the demonstration that the matcher needs distinguishing data or it honestly declines.
- Q: Fatal-input policy and error type
  A: Derived (two-way door, from the introspection task's precedent): a new MatchError in the new module for malformed schemas/samples (this function's inputs are not IR, so the engine's MappingError does not apply); duplicate raw field names in a schema are fatal (ambiguous by construction); identically-normalizing distinct names are legal and simply tie at lanes 1-2.

You are on the `main` branch of the repository (your cwd). Implement the spec, run the task's own checks (python3 -m mypy --strict eaitl; python3 -m unittest discover -s tests -t .), then COMMIT all changes (git add -A && git commit). Work not committed does not exist. Do not touch paths outside this repository.