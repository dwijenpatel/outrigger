# File-contract versioning policy (T11, settled minimal — 2026-07-12)

Five artifacts exchange persistent, schema'd files (R5/D15: composition happens through these
files and exit codes, never through imports). This page is the whole policy; it exists so
compatibility knowledge lives in one place instead of embedded separately in each tool. T11's
settling condition — "the first real two-artifact integration" — fired with the exec-loop
composition and e2e run 1; the tier-knob addition then provided the first live
additive-change case. This policy generalizes what those two events already did.

## The envelopes and their owners

| Envelope | Major | One owning producer | Validating reader(s) |
|---|---|---|---|
| `plan.json` (contract v1) | `contract: 1` | spec-interview (or any human/tool honoring the schema) | plan-preflight (strict; unknown keys rejected) |
| held-out `manifest.json` | `contract: 1` | heldout-suite `seal` | heldout-suite `verify` |
| gate report | `contract: 1` | merge-gate `run` | merge-gate `verify`, exec-loop |
| ledger record | `contract: 1` | run-ledger `append` | run-ledger `check`, exec-loop (tolerant read) |
| launcher bundle (`params.json` / `result.json`) | `contract: 1` | exec-loop (params) / each launcher (result) | every launcher (params), exec-loop (result) |

## The five rules

1. **Every envelope carries an explicit integer major** (`contract`). One producer owns each
   schema; nothing else writes it.
2. **Readers reject an unknown major, fail-closed** — a refusal with the version named, never
   a guess. (Exit nonzero / refusal record, matching each tool's error convention.)
3. **Absence = legacy major-1, valid forever where history is append-only** (the ledger: old
   records are never rewritten, so `check` accepts missing `contract` as 1). For
   non-append-only envelopes (gate reports, bundles), producers stamp from now on and readers
   require the stamp — stale unstamped instances are already invalid for other reasons
   (freshness binding).
4. **Within a major, additions are optional keys, validated where enumerable.** The precedent
   is `risk_tier`/`tier` in plan contract 1: the validator learned the key and its enum;
   consumers that predate the key must behave correctly when it is absent (absence = the
   pre-addition default, and the default never weakens a guarantee — `risk_tier` absent means
   `full`). A change that cannot satisfy that sentence is a **major bump**.
5. **A major bump lands writer + every reader + a ledger note in one merge**, with the old
   major's reader kept only if history must stay readable (rule 3). No dual-writing, no
   flag-days spread across commits.

## Golden fixtures

[contracts-golden/](contracts-golden/) holds one canonical current-major instance per
envelope. `tests/test_contracts.py` parses each and asserts the required keys and the major.
**Rule: any commit that changes an envelope's shape updates its golden in the same commit** —
the golden diff *is* the reviewable contract change. (Plan and manifest goldens live where
their validators' test fixtures already are — preflight and heldout test suites — and are
listed here for completeness, not duplicated.)

## What this policy is not

Not a schema-registry, not semver, not tolerant-reader-everywhere. R2 applies: this is the
minimum that keeps five artifacts and a first foreign consumer (the Codex launcher, named
next) from embedding five private compatibility theories. If contract drift produces a real
failure this policy didn't prevent, that failure is T11 evidence and the policy grows only
then.
