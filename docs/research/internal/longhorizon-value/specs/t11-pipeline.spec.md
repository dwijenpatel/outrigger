# t11-pipeline — human-readable render

> **GENERATED from `t11-pipeline.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T03:45:47Z
**Risk tier:** full

## Goal

Add the job pipeline to eaitl as run_job(text, fmt, target_schema, target_examples=None) -> job record: the six ratified stages (introspect, propose, validate, confirm, compile, preview) run in pinned order as one pure deterministic state machine, recording each completed stage's artifact and stopping at the first failing stage with {status, failed_stage, error, stages}. Compiles both languages; policy warnings (including unmapped_target against the given schema) are recorded, never fatal; per-row preview errors are data. Done when the pinned worked example holds end-to-end (including the real frozen version digest), the boundary examples hold, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No job ids, timestamps, persistence, or lineage beyond the frozen version — the product draft's job_id/GET-endpoint is a service layer; this slice returns the record (purity forbids uuid/clock anyway).
- No human-approval gate inside the library: when the confirm stage is reached it freezes unconditionally. The approval UX is the caller's obligation (the recorded edit -> validate -> confirm channel uses the pieces directly).
- No retries, partial resume, or caching across stages (introspection legitimately runs twice — both runs are pure).
- No language selection parameter — the compile stage always emits both; choosing one is the caller's filter.

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the new export(s) to eaitl/__init__.py.
- Pure function: deterministic, no I/O beyond arguments, no clock, no randomness, no LLM.
- No irreversible or externally-visible actions: pure computation only.
- Stage names, order, and per-stage artifact shapes are exactly as pinned in the task spec; the job record always carries status, failed_stage, error, stages.
- Only IntrospectError, MatchError, MappingError, and a non-empty validate_ir result may produce a failed record; any other exception propagates (it is a bug, not a job outcome).
- The failing stage contributes no partial artifact: stages holds exactly the completed prefix.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design task table: the job pipeline ('deterministic state machine: introspect -> propose -> validate -> confirm -> compile -> preview, with status + artifacts (GET /jobs/:id shape)'); next in the ratified cascade order (T2 through T10 done).
- **Scope and non-goals (coverage item 2)**
  Sourced — the chain-design row and the product draft's API surface; non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the end-to-end CLI is its only in-chain consumer (a thin veneer over run_job); post-chain, this is the function a service would wrap.
- **Success in outcome terms (coverage item 4)**
  Sourced — the chain's correct-or-stop bar: behavior pinned exactly enough for the blind author to test from the spec alone, with the worked example as the anchor.
- **Appetite (coverage item 5)**
  Sourced — chain-design size/type table classes this task 'integration'; the experiment's measured per-task budget precedent bounds it.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the sequence; extensions go to the post-experiment register.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Sourced — pure function (constraints). Tier: full, per the chain-wide precedent.
- **Compile stage emits BOTH languages; chain-table deps amended (+ the TypeScript compiler)**
  Derived (two-way door, recorded deviation from the chain sketch): the dependency row predated the operator's TypeScript redirect, and the CLI's ratified row emits both languages — compiling both in the pipeline keeps the CLI a veneer instead of side-calling a compiler. Cost: every job pays both compilations even when a caller wants one (cheap: pure string generation, no I/O).
- **Why does run_job exist at all, when the generated code is the user-facing artifact?**
  Operator question at review (2026-07-16): the code is the deliverable; run_job is the assembly line that produces it trustworthily, plus the paper trail. Three reasons it is a library function rather than CLI-inline logic: (1) orchestration in the library lets any frontend — CLI today; API service, notebook, tests tomorrow — run the same flow, keeping the CLI a veneer; (2) the job record is the audit/debug artifact (which proposal, which warnings, which frozen version, what the preview showed) — when generated code is wrong, the record shows what happened upstream; (3) the chain deliberately includes integration tasks because integration coverage is never a free byproduct of per-task tests. Cost: one more public surface to keep stable, and its one-shot shape is the no-gate happy path, not the interactive approval flow.
- **No job_id in the record despite the draft's sketch carrying one — why not just import uuid?**
  Derived; reasoning sharpened by operator challenge at review (2026-07-16). Not dogma about uuid in the system's own code — two concrete reasons: (1) an id's usefulness begins with persistence, and this slice stores nothing anywhere; ids and storage arrive together in the service layer that wraps run_job, where import uuid is exactly right. (2) A random id in the record would break equal-inputs-equal-record, which the experiment's blind exact-match oracles and differential tests lean on — every full-record assertion would special-case the field, for a value nothing in-chain consumes. Two-way door: a later layer adds ids without changing this record's meaning. Cost: two identical calls are indistinguishable — by design.
- **Failure = stage-prefix record, failing stage contributes nothing**
  Derived (two-way door, from determinism-over-diagnostics): the error field names the stage and message; keeping partial artifacts out of stages makes the record shape a function of where it stopped, nothing else. Cost: no partial evidence from the failing stage itself (its inputs are all reconstructible — every stage is pure).
- **Confirm stage freezes unconditionally (no approval hook parameter)**
  Derived (two-way door, from mechanism-not-policy): the library composes; gating belongs to callers (the CLI run command is the no-gate happy path; an interactive product inserts its approval between propose and confirm by calling the pieces directly). Cost, named plainly: nothing in this task stops code being generated from a never-reviewed proposal — the human gate is the caller's obligation.

## Open questions

- none

## Task `job-pipeline` — Compose the six ratified stages into one deterministic job

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Provides:** job-pipeline · **Requires:** eaitl-engine, source-introspection, deterministic-matcher, ir-well-formedness-validator, policy-validation, mapping-freeze, python-compiler, ts-compiler, preview-pipeline

---

# Job pipeline — the whole flow as one deterministic state machine

## What and why
Every piece of the product now exists as a ratified, standalone function: introspect,
propose, validate (well-formedness + policy), confirm/freeze, compile (both languages),
preview. This task composes them into the product's spine — one call that takes raw source
text and a target schema and runs the full flow, recording per-stage artifacts and where
(if anywhere) it stopped. It is the library form of the product draft's job record
(`GET /jobs/:id → status, artifacts`).

## Public interface (pin exactly)
- New file **`eaitl/pipeline.py`** exporting one function:
  - `run_job(text: str, fmt: str, target_schema: dict[str, Any],
     target_examples: list[dict[str, Any]] | None = None) -> dict[str, Any]`
- Add `run_job` to `eaitl/__init__.py` (the only edit to existing files).
- `text`/`fmt` use the ingestion task's ratified vocabulary (raw file content, `"csv"` or
  `"json"`); `target_schema` uses the ratified schema shape (`{"fields": [{"name",
  "type"}]}`); `target_examples` is the matcher's optional example-rows input.

## The stages (pin exactly — names, order, artifacts)
Run in this order, recording each completed stage's artifact under its name:
1. **`introspect`** — `introspect_source(text, fmt)`; artifact = its full return
   (`{"schema", "samples"}`).
2. **`propose`** — `propose_mappings(<stage-1 schema>, target_schema, <stage-1 samples>,
   target_examples)`; artifact = `{"ir": <the proposal>}`.
3. **`validate`** — `validate_ir(ir)` first: any problems fail the stage (error message
   must name the first problem's code and location; the matcher promises validator-clean
   output, so this firing means an internal contradiction — it still must be handled).
   Then `validate_mappings(ir, target_schema)` — **the same target_schema**, so the
   matcher's ambiguity-omissions surface here as `unmapped_target` warnings; artifact =
   `{"warnings": <the policy warnings>}`. Warnings never fail anything.
4. **`confirm`** — `confirm_mapping(ir)`; artifact = `{"version": <the 64-hex digest>}`
   (the plan itself is already recorded under `propose`).
5. **`compile`** — artifact = `{"python": compile_python(ir), "typescript":
   compile_ts(ir)}` — both languages, always.
6. **`preview`** — `run_preview(text, fmt, ir)`; artifact = its full return
   (`{"preview_rows", "errors"}`). Per-row errors here are **data, never failure**.

## The job record (pin exactly)
```json
{"status": "completed" | "failed",
 "failed_stage": null | "<stage name>",
 "error": null | "<message>",
 "stages": { <one key per COMPLETED stage, in stage order> }}
```
- All four keys always present; `failed_stage`/`error` are null on success.
- **Failure semantics**: the three expected exception types (`IntrospectError`,
  `MatchError`, `MappingError`) and a non-empty `validate_ir` result fail the job at their
  stage: `status` `"failed"`, `failed_stage` the stage name, `error` the exception's
  `str()` (or the code-and-location message for validator problems), and `stages` holding
  **only the stages that completed before it** — the failing stage contributes no partial
  artifact. Later stages do not run. Any other exception type is a bug and propagates.
- The record is JSON-serializable throughout, and `run_job` is pure: equal inputs produce
  equal records — no job id, no timestamps, no persistence (the draft's `job_id`/lineage
  belong to a service layer; the frozen `version` is this slice's lineage anchor).

## Composition honesty (the seams, named)
- Introspection runs **twice** — once as stage 1 and once inside `run_preview` (whose
  ratified contract takes raw text). Both are pure, so this is harmless; do not restructure
  the preview task's interface to share work.
- The ingestion contract keeps samples **raw and uncoerced**, so a `"csv"` source yields
  all-string sample values: example-driven numeric proposals generally will not arise, and
  arithmetic ops that do reach preview surface per-row errors there. That is faithful
  composition, not a pipeline defect; the worked example below uses `"json"`, where samples
  carry types.

## Worked example (pin end-to-end — the product draft's scenario, three rows)
`fmt` `"json"`, `text` exactly this array (the matcher task's samples, as JSON):
```json
[{"order_id": "A1001", "customer_first_name": "Ada", "customer_last_name": "Lovelace",
  "amount_cents": 2599, "created_at": "2026-07-10T14:22:11Z", "status": "paid"},
 {"order_id": "A1002", "customer_first_name": "Grace", "customer_last_name": "Hopper",
  "amount_cents": 1250, "created_at": "2026-07-11T09:00:00Z", "status": "refunded"},
 {"order_id": "A1003", "customer_first_name": "Alan", "customer_last_name": "Turing",
  "amount_cents": 999, "created_at": "2026-07-12T18:45:30Z", "status": "paid"}]
```
`target_schema`: fields `id string · customer_name string · amount_usd float · order_date
date · is_paid bool`. `target_examples`: `("A1001", "Ada Lovelace", 25.99, "2026-07-10",
true)`, `("A1002", "Grace Hopper", 12.5, "2026-07-11", false)`, `("A1003", "Alan Turing",
9.99, "2026-07-12", true)` (as row dicts).

The job completes with:
- `introspect`: six fields — `order_id string`, `customer_first_name string`,
  `customer_last_name string`, `amount_cents int`, `created_at timestamp`, `status
  string`; samples = the three rows unchanged.
- `propose`: **exactly the matcher task's pinned five-mapping proposal** (copy → `id`;
  concat with `{"lit": " "}` → `customer_name`; divide by `{"lit": 100}` → `amount_usd`;
  to_date → `order_date`; equals `{"lit": "paid"}` → `is_paid`; empty filters and
  validations).
- `validate`: `{"warnings": []}`.
- `confirm`: `{"version":
  "ec4a652a6db4123681215762326ce3c434a0448f0641b5119c3188d565beb417"}`
  (computed from the ratified canonical-form rule — the blind author can verify).
- `compile`: both keys present; each value byte-equal to the corresponding ratified
  compiler called on the proposal.
- `preview`: `preview_rows` **equal to the three target-example rows exactly**
  (`amount_usd` 25.99 / 12.5 / 9.99; `is_paid` true / false / true); `errors` `[]`.

Boundary examples to pin behavior (each must hold):
- Same inputs **without** `target_examples` → completed; `propose` = the matcher's pinned
  three-mapping fallback (copy → `id`, cast-to-float → `amount_usd`, to_date →
  `order_date`); `validate` warnings = exactly two `unmapped_target` records
  (`customer_name`, `is_paid`, in schema order); preview rows carry three keys each.
- Truncated JSON `text` → failed at `introspect`; `stages` is `{}`.
- `target_schema` malformed (e.g. `{"fields": "nope"}`) → failed at `propose`
  (`MatchError`); `stages` holds `introspect` only.
- A target schema the matcher can propose **nothing** for (e.g. a single bool field, no
  examples) → **completed**, not failed: the empty-mappings proposal is validator-clean,
  freezes to a version, compiles, and previews to empty row dicts — with the omissions
  visible as `unmapped_target` warnings. Silence-with-warnings is the designed behavior.

## Conventions
Python stdlib only; `mypy --strict` clean; new stdlib-`unittest` tests under `tests/`
(worked example end-to-end including the pinned version; the no-examples variant; each
failing stage with the stage-prefix rule; determinism as record equality across repeated
calls).
