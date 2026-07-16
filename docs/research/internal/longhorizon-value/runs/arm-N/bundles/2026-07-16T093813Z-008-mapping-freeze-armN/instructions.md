You are the IMPLEMENTER for task `mapping-freeze`: Content-address an approved plan with a deterministic version

SPEC:
# Mapping freeze — a content-addressed version stamp for an approved plan

## What and why
Approval must bind to exact content (the harness's own ratification lesson): "the plan we
approved" has to mean one specific document, not whatever the file later says. This task
gives eaitl that primitive: `confirm_mapping(ir)` computes a **deterministic,
content-addressed version** of a well-formed plan — the identity the pipeline records and
everything downstream cites.

## Public interface (pin exactly)
- New file **`eaitl/freeze.py`** exporting one function:
  - `confirm_mapping(ir: dict[str, Any]) -> dict[str, Any]`
- Add `confirm_mapping` to `eaitl/__init__.py` (the only edit to existing files).
- **Returns** `{"version": <64-char lowercase hex>, "ir": <the input plan, unchanged>}`.
- **Refuses to freeze a malformed plan**: if the ratified well-formedness validator
  (`validate_ir`) returns any problems, raise the engine's `MappingError` with a message
  naming the first problem's code and location — freezing garbage would defeat the point.
  (A caller that validated first never sees the raise.)

## The canonical form (pin exactly)
`version` = SHA-256 hex digest of the plan serialized as **canonical JSON**:
`json.dumps(ir, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded UTF-8.

Consequences, all intended and testable:
- **Object key order is identity-irrelevant** (sort_keys): two plans differing only in dict
  key order freeze to the same version.
- **Array order is identity-relevant**: mapping order is semantics (output-row key order,
  duplicate-target last-wins), so reordering `mappings` produces a different version.
- **Idempotent and pure**: same plan → same version, every time, on any machine.
- Unknown/extra keys (e.g. proposer metadata) **are part of the content** and change the
  version — the frozen identity covers the whole document, not a projection.

## Worked example (digest computed from this exact rule — the blind author can verify)
For the plan
```json
{
  "mappings": [
    {
      "target_field": "id",
      "transform": {
        "op": "copy",
        "args": [
          "order_id"
        ]
      }
    },
    {
      "target_field": "amount_usd",
      "transform": {
        "op": "divide",
        "args": [
          "amount_cents",
          {
            "lit": 100
          }
        ]
      }
    }
  ],
  "filters": [],
  "validations": [
    {
      "kind": "not_null",
      "field": "id"
    }
  ]
}
```
`confirm_mapping` returns `version` exactly:
`a4ae8a152df23d2b743a70fa8e91daae4699d6e9fe808c965274f8b0f0ad90fb`

## Non-storage
The freeze computes identity; it does **not** persist anything (no registry, no files) —
storage is the caller's concern, which keeps this a pure function and lets any workflow
(pipeline, CLI, a human at a REPL) use it.

## Iteration — fixing an approved plan later
Freezing locks nothing. To fix an oversight the human edits the plan (the product's
recorded modification channel), re-validates, and confirms again: the edited plan freezes
to a **new** version, and the deterministic compilers regenerate code from it — the same
pipeline re-entered, not new machinery. `confirm_mapping` keeps no memory: it never
refuses a re-confirmation, and "which version is current" is the caller's record. Version
history, diffing, and rollback are out of scope (non-goals).

## Conventions
Python stdlib only; `mypy --strict` clean; new stdlib-`unittest` tests under `tests/`
(the pinned digest above; key-order insensitivity; array-order sensitivity; the
refuses-malformed raise; idempotence).


PLAN GOAL: Add the mapping freeze to eaitl as confirm_mapping(ir) -> {version, ir}: the SHA-256 hex digest of the plan's canonical JSON form (sort_keys, compact separators, ensure_ascii=False, UTF-8), refusing malformed plans by raising MappingError when the ratified validator reports any problem. Object key order is identity-irrelevant, array order is identity-relevant, the function is pure and persists nothing. Done when the pinned worked-example digest matches exactly, the canonical-form properties hold, mypy --strict passes, and the existing tests still pass.

PLAN CONSTRAINTS:
- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the new export(s) to eaitl/__init__.py.
- Pure function: deterministic, no I/O beyond arguments, no clock, no randomness, no LLM.
- No irreversible or externally-visible actions: pure computation only.
- The canonical form is exactly the pinned serialization — any deviation changes every digest and is a contract break.
- confirm_mapping must refuse (MappingError) any plan the ratified validator finds problems in, and must return the input plan unchanged (same object content) on success.

DECISIONS (the why — do not re-decide these):
- Q: Problem & who it's for; why now (coverage item 1)
  A: Sourced — chain-design task table: the mapping freeze ('confirm_mapping(ir) -> frozen_version: content-addressed, versioned approved IR (deterministic hash)'); next in the ratified cascade order (T2, T3, T4, T5, T6, T7 done).
- Q: Scope and non-goals (coverage item 2)
  A: Sourced — the chain-design row and the product draft's API surface; non-goals recorded above.
- Q: Use-cases / consumers (coverage item 3)
  A: Sourced — chain-design dependency table: the job pipeline's confirm stage records the version; the CLI reports it; the operator-recorded human-modification channel ends here (edit -> validate -> confirm/freeze).
- Q: Success in outcome terms (coverage item 4)
  A: Sourced — the chain's correct-or-stop bar: behavior pinned exactly enough for the blind author to test from the spec alone, with the worked example as the anchor.
- Q: Appetite (coverage item 5)
  A: Sourced — chain-design size/type table classes this task 'small'; the experiment's measured per-task budget precedent bounds it.
- Q: Future-scope (coverage item 6)
  A: Sourced — the chain fixes the sequence; extensions go to the post-experiment register.
- Q: Irreversible/externally-visible actions + risk tier (coverage item 7)
  A: Sourced — pure function (constraints). Tier: full, per the chain-wide precedent.
- Q: Canonical form: sorted-keys compact JSON, arrays order-preserving
  A: Derived (two-way door, from semantics: key order is presentation, array order is meaning): sort_keys makes cosmetic dict-order differences identity-irrelevant while mapping order (which IS semantics — output key order, last-wins) stays identity-relevant. Alternative (hash the raw file bytes) rejected: whitespace and key order would mint spurious versions. Cost: semantically-equivalent-but-differently-written plans ({lit: 100} vs bare 100) still differ — canonicalizing semantics is out of scope, named.
- Q: Refuse to freeze malformed plans
  A: Derived (two-way door, from approve-before-effect): a frozen version of garbage is worse than no version; composing the ratified validator makes freeze the natural end of the edit -> validate -> confirm channel. Cost: freeze depends on the validator (an intended, recorded composition seam).
- Q: Identity only, no persistence
  A: Derived (two-way door, from one-thing-well): a pure identity function composes anywhere; storage policy belongs to the pipeline task. Cost: callers must record versions themselves.
- Q: Can a user fix oversights in an approved mapping later, or is the freeze final?
  A: Operator question at review (2026-07-16): the freeze is identity, not a lock — edit the plan, re-validate, confirm again; the edit freezes to a new version and the deterministic compilers regenerate code from it (the same loop re-entered, not new product machinery; the job-pipeline task composes it end to end). Cost, named: this slice keeps no version history — current-version bookkeeping is the caller's, and history/diff/rollback are future-product territory.

You are on the `main` branch of the repository (your cwd). Implement the spec, run the task's own checks (python3 -m mypy --strict eaitl; python3 -m unittest discover -s tests -t .), then COMMIT all changes (git add -A && git commit). Work not committed does not exist. Do not touch paths outside this repository.