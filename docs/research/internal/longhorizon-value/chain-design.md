# eaitl long-horizon chain — task-sequence design (REGISTERED)

Substrate for the long-horizon value experiment (thesis: outrigger gives reliable
correct-or-stop over a dozen dependent tasks where ungated alternatives ship silent-wrong).
**Three arms** — the gated Sonnet harness, a diligent-ungated Sonnet control, and a
diligent-ungated Opus frontier control — all build the same chain from the same ratified
specs (see "The three arms" below). This file designs the chain and the arms.
**Registered 2026-07-16** on the operator's commit order, with all eleven specs (T2–T12)
ratified: the chain, the arms, and the pre-registered arm-F decision rules are fixed; the
named open items (oracle granularity — a grading-time choice; the optional naive one-session
floor; the recommended second held-out slice) are the only pre-run decisions left, each
recorded where it lives.

## Two scoping decisions (load-bearing)

1. **Deterministic spine only — exclude the LLM semantic proposer.** eaitl's draft has an
   LLM propose mappings; that is non-deterministic and cannot be blind-graded (the oracle is
   exact-match on held-out cases). So the "mapping engine" here is the **deterministic
   matcher** (lexical + type-compat + example-driven heuristics, no model call). The
   deterministic spine is the real engineering core anyway; the LLM proposer can be a later,
   non-experiment slice. **Required for gradeability.**
2. **Codegen = Python + TypeScript; Rust dropped.** (Amended 2026-07-16, operator decision:
   TypeScript, not plain JavaScript — the original JS-only choice existed solely because
   `tsc` was missing; the operator installed **tsc 7.0.2**, dissolving the constraint.
   Toolchain probe-verified same day: strict tsc gate + `node` v24.13.1 native `.mts`
   type-stripping both pass; npm present but unused — the generated module is zero-dependency
   by design.) Both compilers are graded *behaviorally* (generate → type-gate → execute →
   compare to `apply_ir` on held-out rows); Rust cannot be exec-graded (no toolchain) → out.

## The chain (T1 done; T2–T12 the sequence)

| # | Task | What (all deterministic) | Deps | Role |
|---|------|--------------------------|------|------|
| 1 ✅ | transform/preview engine | `apply_ir(ir,rows)->(rows,errors)`, op library, filters, per-row errors | — | DONE (eaitl `c646832`) |
| 2 | IR contract | typed IR model + well-formedness check (op names synced to the engine registry, arg arities, unique `target_field`, filter shape) | 1 | foundation; malformed-IR gate everything downstream trusts |
| 3 | ingestion / introspect | parse CSV/JSON source data, infer field types, extract sample rows → `{schema, samples}` | — | **compounding hotspot · CANARY A (type inference)** |
| 4 | output validations | execute IR `validations` (not_null, type_check) against engine output (deferred from T1) | 1,2 | small |
| 5 | deterministic matcher | `propose_mappings(source_schema, target_schema, samples) -> IR` via name-normalization + similarity + type-compat + example-driven op inference (e.g. amount_cents→amount_usd ⇒ divide/100). No LLM. **T5-spec note (operator Q, 2026-07-15):** the human-modification channel is edit-the-IR-JSON → validate → confirm/freeze (no UI in-chain); a bool-typed target column over yes/no-like string samples must be proposable as `equals(col, lit)` — the engine has no bool `cast`; comparisons are how booleans are produced. | 2,3 | compounding (wrong IR → wrong everywhere downstream) |
| 6 | Python compiler | `compile_python(ir) -> str`: standalone `transform(row)` with **engine-identical op semantics** | 1,2 | **compounding hotspot · CANARY B (op parity) · oracle: exec(compiled)==apply_ir** |
| 7 | TS compiler | `compile_ts(ir) -> str`: standalone typed TypeScript `transform` (zero-dep, erasable-syntax `.mts`; strict-tsc gate + node-stripping run); same op contract | 6 | shares the op-semantic contract; a T6 abstraction bug propagates |
| 8 | preview pipeline | `run_preview(source_data, ir) -> {preview_rows, errors}`: introspect → apply_ir | 1,3 | integration |
| 9 | mapping freeze | `confirm_mapping(ir) -> frozen_version`: content-addressed, versioned approved IR (deterministic hash) | 2 | small |
| 10 | policy validation | `validate_mappings(ir) -> warnings`: PII fields (hash targets), unsupported / non-deterministic ops, ambiguous or unmapped-required targets | 1,2 | feature |
| 11 | job pipeline | deterministic state machine: introspect → propose → validate → confirm → compile (both languages) → preview, with status + artifacts (GET /jobs/:id shape) | 3,5,6,7,8,9,10 | integration |
| 12 | end-to-end CLI | `eaitl run <source> <target> <samples>` → proposed IR → preview → generated Python/TypeScript + validation & policy reports | all | integration; **end-state acceptance** |

Total: 12 tasks (1 done, 11 to run). Topologically ordered; the preflight `order` will confirm.

## Canary design (hybrid: natural compounding + 2 seeded)

Both are **spec-level** — the spec states the correctness requirement; the documented
tempting-wrong-path is sealed and a correct implementation must avoid it. The blind suite tests
the edge; a diligent-ungated arm's own visible tests plausibly miss it, so it ships and the
error compounds downstream.

- **Canary A — T3 type inference.** A subtle inference edge: leading-zero numeric strings
  (`"007"`, zip codes), bool-like tokens, or int-vs-float ambiguity. Wrong inference passes T3's
  happy-path tests but propagates: matcher (T5) proposes a wrong cast → engine (T1) casts wrong
  → compiler (T6/7) bakes it in → end-to-end wrong output. High propagation (earliest hotspot).
- **Canary B — T6 Python compiler op parity.** A subtle op-semantic divergence between generated
  code and the engine: `divide` rounding on negatives, `to_date` `Z`/timezone handling, or
  `concat` null-rendering. Passes the compiler's worked-example test; a blind differential edge
  test reveals compiled ≠ `apply_ir`. The canonical "visible tests plausibly insufficient" case.

## The three arms

All arms build the same eleven tasks (T2–T12) from the same ratified specs, starting from the
same landed-engine commit (`c646832`), with a fresh session per task. After the runs, every
arm's landed code is graded against the same sealed held-out suites (plus the canaries and the
[test-overlap tool](../../../../tools/test-overlap/README.md)) — grading is post-hoc and
non-adaptive: no arm ever receives feedback from it, so the suites stay independent, and the
harness arm's blind suites double as the free oracle for both ungated arms.

**One circularity to control.** Arm H is *gated* by the blind suite during its build (up to
three retries against its counts-only feedback), and that same suite then *grades* every arm.
So any head-to-head "H shipped less silent-wrong than N/F" is confounded — H was optimized
against the very instrument that scores everyone; N and F never saw it. Two clean readings
survive this: (1) the pre-registered **arm-F decision rules** below (Opus never saw the suite,
so the suite grades it fairly), and (2) the **canaries** (T3, T6), planted independent of the
suite. Treat the suite-graded H-vs-N/F silent-wrong *rate* as suggestive only unless a
**second, independently authored held-out slice** — one no arm was gated on — is added as the
head-to-head oracle. Recommended: add that second slice, or restrict head-to-head claims to the
canaries + the arm-F rules.

| Arm | Implementer | Verification while building | Question it answers |
|---|---|---|---|
| **H — gated harness** | Sonnet 5 (xhigh); up to 3 fresh attempts on gate failure (the gate reports only how many hidden tests failed, never which); exhaustion = honest stop | sealed blind suite + hard merge gate, plus its own visible tests | Does the machinery produce correct-or-stop? |
| **N — diligent Sonnet control** | Sonnet 5 (xhigh), one fresh session per task | its own visible tests + repo tests; no gate, no stop channel | Does the machinery beat plain diligence, model held fixed? |
| **F — frontier-solo control** | Opus 4.8 (xhigh), one fresh session per task | its own visible tests + repo tests; no gate, no stop channel | Is the gate worth more than spending the same money on a better implementer? |

**Why arm F exists (added 2026-07-14).** The strongest challenge to the harness: the blind
author's token spend might be better spent upgrading the implementer. Current list prices
(Sonnet 5 $3/$15 per Mtok in/out, intro $2/$10 through 2026-08-31; Opus 4.8 $5/$25; Fable 5
$10/$50) make Opus-solo cost about the same as the whole gated-Sonnet arm (~$5.0–7.6 vs the
measured $7.10/task on the engine slice) — so arm F is the budget-neutral form of the
challenge: same spend, no gate, stronger model. Fable-solo would cost 1.4–2× the gated arm
and is held back as an optional escalation (only if Opus stumbles, or to probe the ceiling).

**The crossover arm F measures.** An ungated arm ships silent-wrong whenever its code is
wrong and its own tests pass. The gated arm ships silent-wrong only when, additionally, the
blind suite misses the defect. The test-overlap tool's first run put the blind suite's miss
rate at roughly a quarter of wrong-versions
([report](../t2-pilot-1/pilot-eaitl-preview/overlap-report.json); one task, one-line-mutation
proxy — **illustrative arithmetic, not a measured rate**) — so *if that ¼ miss-rate held*,
going gateless would ship less silent-wrong only where the frontier model's
wrong-but-own-tests-pass rate is at least ~4× lower than Sonnet's. Both the ¼ and the ~4× are
single-task back-of-envelope; the real ratio is unknown and is what this experiment measures. Two asymmetries the ratio doesn't capture: the gated arm's
failures skew loud (retry or honest stop; the solo arms' only failure mode is silent), which
matters on a dependent chain where one early silent-wrong corrupts everything downstream —
and, against that, if the frontier model genuinely one-shots this difficulty tier, stops are
worth nothing and the gate is pure overhead.

**Pre-registered decision rules for arm F:**

- Arm F ships **≥1 silent-wrong that the sealed suite catches** → the gate has demonstrated
  value against the best available implementer, on real work.
- Arm F goes **11-for-11 clean** → at this task difficulty the gate buys nothing over a
  frontier implementer. Bounded conclusion: one clean 11-run is weak statistics, so it
  licenses "don't pay for the gate on chains of this difficulty," not "the gate is worthless
  everywhere."

**Fairness invariants:** same ratified plan, same base commit, fresh session per task, every
arm runs its own visible tests. The only deltas: arm H adds the walled blind suite + gate +
stop; arm F swaps the implementer tier. Per-task costs recorded from Claude Code's own
`total_cost_usd` (notional on a subscription plan, ≈ API list price).

## Error-compounding — an explicit measured outcome (2026-07-14)

The 2026-07-14 failure-attribution pass ([failure-modes](../../external/failure-modes/README.md))
ranks error-compounding the **largest, best-replicated** long-horizon failure, and flags the
**decomposition bet** — that short, fresh-context, per-link-gated tasks beat the same effort run
long — as measured by *no external source*. This chain is the in-house instrument for the gating
half of that bet, so compounding is a first-class recorded outcome, not a side effect.

**Controlled by design vs. measured here.** All three arms already run a **fresh worker context
per task**, which severs the within-context *self-conditioning* channel equally — so this
experiment does **not** measure self-conditioning (it holds it fixed across arms). What it
measures is **cross-task dependency compounding**: whether a wrong-but-shipped output at link N
corrupts links N+1…12. The gated arm (H) can arrest it at each link (stop-on-fail); the ungated
arms (N, F) ship silent-wrong and build on the corrupted foundation.

**What this does NOT test — and the honest gap.** Holding decomposition fixed across all arms
means the experiment cannot compare **decomposed-fresh-gated vs. one long continuous session** —
the actual shape-question behind the "bound the horizon" decision. That question needs a
**fourth arm: a continuous-thinking run** of the whole chain in one session at equal budget (no
per-task fresh context). It is deliberately **not** included here — it roughly doubles the most
expensive arm, and this experiment's founding question is the *gate's* value, not the
*decomposition's*. The competing lever is real, not a strawman: the self-conditioning source
(2509.09677) finds *thinking* mitigates within-turn rot and enables much longer single turns, so
a continuous-thinking run is a live rival to decomposition. Recorded as the named, unbuilt
instrument for the decomposition half of the bet; the design doc's "bound the horizon" decision
is marked TBD on exactly this comparison.

**The metric — compounding depth.** For every silent-wrong that lands, record how many downstream
tasks inherit and build on the defect before the sealed end-to-end oracle (or a canary) flags it:
depth 0 = caught at its own link; depth k = k downstream links corrupted. Per arm, report the
distribution of compounding depths and the max. The thesis predicts arm H pins at depth 0 (caught
at the link), while the ungated arms show a heavy tail — one early miss (the T3 or T6 canary is
the seeded case) dragging a run of downstream links wrong. **This per-arm depth distribution is
the experiment's direct read on the decomposition bet** the external corpus leaves open.

## Properties this buys the experiment

- Fully deterministic → clean blind exact-match oracle at every step and end-to-end.
- Real dependencies where early defects compound (op semantics, IR contract, type inference all
  flow downstream) — the phenomenon under test can actually occur.
- Three integration tasks (8, 11, 12) — integration coverage is never a free byproduct of
  per-task tests.
- Size/type variety (small: 4, 9; feature: 2, 5, 10; large: 6; integration: 8, 11, 12) — matches
  the protocol's composition-variety requirement.
- The harness arm builds a genuinely useful deterministic ETL compiler → real work → free under
  shadow mode.

## Settled / open

- ✓ Deterministic-spine scoping (exclude LLM proposer).
- ✓ All 12 tasks (T1 done; T2–T12 the sequence).
- ✓ Canaries at T3 (type inference) and T6 (op parity).
- ✓ **Three arms incl. the frontier-solo control** (2026-07-14; see "The three arms").
- ✓ **No promotion of held-out tests into the repo during the chain** (2026-07-14): adding
  the blind suite's tests to shared repo state would leak the canary edges to the ungated
  arms (or break arm symmetry if added one-sidedly). Tabled as a possible post-experiment
  feature.
- **Experiment base:** all arms start from the landed engine `c646832` (shared, correct
  foundation) and build **T2–T12 (11 dependent tasks)**. Symmetric → fair; reuses real work;
  T2–T12 is plenty of horizon for compounding. Alternative rejected: start from empty
  `e64604d` and rebuild T1 twice for a literal 12-task horizon (more cost, discards landed work).
- Open: **oracle granularity** (end-state-only vs per-step-accumulated + final).
- Open: whether to also run the naive one-session floor (a single session handed the whole
  plan) — subsumed by the diligent controls, at most a cheap add-on.
- Open (**default: no**): add a **fourth continuous-thinking arm** to test decompose-vs-continuous
  directly (see "What this does NOT test"). Defaulted off to hold quota fixed — the decomposition
  premise stays *marked untested*, with this arm named as its instrument. Flip to yes only on an
  explicit decision to spend the extra run.
- Open (**recommended: yes**): add a **second, independently authored held-out slice** as the
  head-to-head oracle, so the H-vs-N/F silent-wrong comparison isn't graded on the suite H was
  gated against (see "One circularity to control").

## The spec cascade (in progress)

Draft T2–T12 as pinned, ratifiable specs, **foundation-first** (a dependent chain must be
specced from the keystone out, or an early interface change forces downstream rework):
T2 (IR contract, the keystone) → T3 + Canary A → T4 → T6 + Canary B → T7 → T5 → T8/9/10 →
T11/12. Reuse slice-1's locked conventions: Python-stdlib runtime, `mypy --strict`, functional
style + typed internal model with a dict/JSON public boundary, per-row error capture where
applicable, stdlib-unittest checks. Each spec pins the public interface AND the consumed
interfaces from its deps (compounding requires those pinned). The same ratified specs feed
all three arms — spec quality is shared infrastructure, never a per-arm variable.

**Progress:** ✓ **T2 (IR contract) ratified 2026-07-15** — `specs/t2-ir-contract.plan.json`
(a standalone `validate_ir` well-formedness check layered additively over the landed engine;
full-tier; preflight clean, 0 warnings). ✓ **T3 (ingestion/introspect + Canary A) ratified
2026-07-15** — `specs/t3-ingestion.plan.json` (`introspect_source(text, fmt)` → `{schema,
samples}`; pinned type-inference rules carry the canary edges: leading-zero → string,
true/false-only bool tokens, int+float→float else string-fallback; strict-or-stop file
handling; preflight clean, 0 warnings). **First interview under the compressed protocol: 0
questions (all seven coverage items sourced), 2 operator turns (vs baselines 14/10), 0 ledger
challenges; the omission sweep surfaced the IR-edit-model question → the T5-spec note above.**
✓ **T4 (output validations) ratified 2026-07-16** — `specs/t4-validations.plan.json`
(`validate_output(ir, rows)` → violation records `{row_index, field, kind, reason}`; strict
runtime-type matching, bool≠int, int≠float; **operator ruling via the first accepted ledger
challenge: nulls are legitimate data — `type_check` skips nulls, nullability is `not_null`'s
jurisdiction alone, omission of `not_null` = nullable-by-default; absent field still fails
loudly**; structural malformation raises the engine's `MappingError`, reused). Second
compressed-protocol trial: 0 questions, 2 operator turns, **1 of 5 ledger entries challenged
and accepted (the artifact changed pre-ratification — the challenge channel works)**, plus a
recorded seam answer (date validity: `to_date` output valid-by-construction; no output-side
date-shape assertion in-chain, post-experiment register). **Human-readable `.spec.md` renders**
now generated alongside each ratified plan (plan JSON stays the authority; renders marked
generated). ✓ **T6 (Python compiler + Canary B) ratified 2026-07-16** —
`specs/t6-python-compiler.plan.json` (`compile_python(ir) -> str`: standalone stdlib-only
module, `transform(rows)` with **total differential equality vs `apply_ir` including error
reason strings**; canary edges pinned as named requirements — true division on negatives,
`to_date` never timezone-converts, `concat` null→"", the engine's cast/arithmetic bool
asymmetry and concat/hash null asymmetry reproduced-not-fixed; compiler compiles what the
engine tolerates; byte-identical generation). Trial 3: 0 questions, 2 operator turns, 0
challenges. **T7 redirected pre-ratification (2026-07-16): TypeScript, not JavaScript** —
operator decision at the approval surface (the JS plan reached review, was never ratified,
and was superseded; scoping decision 2 amended; toolchain probe-verified). ✓ **T7 (TypeScript
compiler) ratified 2026-07-16** — `specs/t7-ts-compiler.plan.json` (`compile_ts(ir) -> str`:
zero-dependency, erasable-syntax `.mts` ES module with embedded SHA-256/UTF-8 helpers, typed
exports incl. per-field OutputRow; pinned gates: strict-tsc invocation + node v24 native
type-stripping, both probe-verified; behavioral parity total, value parity JSON-numeric with
four named cross-language exclusions; Python equality/comparison semantics reproduced).
✓ **T5 (deterministic matcher) ratified 2026-07-16** — `specs/t5-matcher.plan.json`
(`propose_mappings(source_schema, target_schema, samples, target_examples=None) -> IR`;
four-lane ladder — exact normalized name → unique containment → example-driven → unique type
compatibility; ambiguity → omit, never guess; output always validator-clean; worked example
extended to 3 samples after a hand-trace found single-sample equality inherently ambiguous;
bool targets never proposable without examples). Trial: 0 questions, 2 operator turns, 0
challenges. ✓ **T8 (preview pipeline) + T9 (mapping freeze) + T10 (policy validation)
ratified 2026-07-16** — first **consolidated exchange** (three plans, one approval surface,
per the consolidation principle): `specs/t8-preview.plan.json` (`run_preview(text, fmt, ir)`
composing introspect → apply on the ≤10 samples, pure pass-through errors, zero new
vocabulary), `specs/t9-freeze.plan.json` (`confirm_mapping(ir)` → SHA-256 of canonical JSON;
key order identity-irrelevant, array order identity-relevant; refuses malformed; pinned real
worked-example digest), `specs/t10-policy.plan.json` (`validate_mappings(ir,
target_schema=None)` advisory warnings: pinned 10-token PII list with hash-suppression,
live-synced deterministic-op allowlist, unmapped-target with optional schema). Trial: 0
interview questions, 2 operator turns for all three; **2 operator review questions, both
real omission catches that changed artifacts pre-ratification** (freeze iteration story —
edit → re-validate → re-confirm mints a new version, recorded as a spec section + decision;
LLM-PII follow-up recorded to the post-experiment register, which also gained the
date-shape bullet promised at T4 but never added).
✓ **T11 (job pipeline) + T12 (end-to-end CLI) ratified 2026-07-16 — SPEC CASCADE COMPLETE**
— second consolidated exchange: `specs/t11-pipeline.plan.json` (`run_job(text, fmt,
target_schema, target_examples=None)` → job record; six ratified stages in pinned order,
stage-prefix failure records, compiles both languages — chain-table row 11 deps amended +T7
post-TypeScript-redirect; no job_id: ids arrive with persistence at the service layer;
worked example pins the real frozen-version digest `ec4a652a…beb417`, cross-checked against
the ratified matcher text) and `specs/t12-cli.plan.json` (`python3 -m eaitl run <source>
<target_schema> [<target_examples>] --out <dir>`, a thin veneer over run_job; exit 0/1/2
with pinned stdout; job.json always written; the chain's only externally-visible task —
writes carved out to --out only; end-state acceptance). Trial: 0 interview questions, 2
operator turns for both; **3 operator review questions, all recorded as ledger entries —
one rewrote a weak recorded rationale** (run_job purpose; no-job_id reasoning sharpened
from "purity forbids" to ids-arrive-with-persistence + equal-inputs-equal-record; CLI
purpose = end-state acceptance now, smallest user surface later).
**All eleven specs (T2–T12) are ratified.** Compressed-protocol final tally across 8
interview exchanges: 0 interview questions (every coverage item asked-or-sourced), 2
operator turns per exchange vs 14/10 baselines, and every operator intervention arriving
through the designed channels — 1 accepted ledger challenge (T4 nulls), 1 pre-ratification
redirect (T7 TypeScript), 5 review questions that changed artifacts (T8/9/10: freeze
iteration story + LLM-PII register; T11/12: the three above).
Next: **held-out suite authorship** (blind, from the ratified specs alone, per task +
end-to-end; second slice recommended per the oracle-circularity control), then the
**arm runs** (operator-run, quota-gated; open pre-run decisions: oracle granularity,
naive one-session floor arm).

## Post-experiment follow-ups (deferred — do NOT touch during the chain)

- **Single source of truth for operation argument-counts.** T2's validator mirrors the engine's
  per-operation argument counts in its own table, because the engine is frozen as the shared
  experiment foundation and T2 must not modify it (a test guards against a *missing* entry, but a
  *changed* count would not be auto-detected). After the experiment, refactor the engine to
  publish its argument counts declaratively and have the validator read from them. (Recorded in
  the ratified T2 spec's decisions; 2026-07-15.)
- **LLM-driven semantic PII detection.** T10's policy checker pins an exact 10-token PII name
  list — deterministic and blind-testable, but it misses anything not literally so named
  (`customer_contact`, `national_id`, PII values in innocuously-named columns). Real coverage
  needs semantic detection — column-name synonyms and/or value-content classification — which is
  LLM territory, excluded from the whole chain by the deterministic-spine scoping decision.
  Successor to the pinned list, not a replacement of the advisory posture. (Operator-confirmed
  follow-up at T10 review; recorded in the T10 plan's non-goals; 2026-07-16.)
- **Output-side date-shape assertion.** T4's seam answer: `to_date` output is
  valid-by-construction, so the chain ships no output-side date/timestamp validation kind; a
  richer `validations` vocabulary (date-shape assertions and similar) is deferred here.
  (Recorded at T4 ratification; 2026-07-16 — this bullet closes a prose promise that predated
  the register entry.)
