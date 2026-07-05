# Pilot firing #3 (greenlane, same-plan protocol) — observations

Fired 2026-07-05 on I14–I18 machinery with the byte-identical pilot-2 plan
(ratification `03a4877bbfa52f91`). **Outcome: parked at the root task, zero
worker spawns, zero tokens of worker spend, clean close** — and the halt is
itself the finding.

## P3-1 ✅ (what worked) The floor collision was caught statically, pre-spawn, and handled by the book

The session simulated the risk-floor gate against GL1's *pinned layout*
before spawning anything: `check_risk_floor("routine", GL1_paths, floors)`
→ mis-tag bounce (models.py floored high, services/** high). It parked GL1
on a complete blocker card (simulated-gate repro, three options with
consequences, recommendation deferring to operator authority), explicitly
noted the collision was NOT among the operator's pre-registered bounces,
refused to edit plan/ or weaken any gate input without ratification, and
closed the firing cleanly when the root block emptied the runnable set.
I16 did its job at the cheapest possible point; the card discipline (E3)
and protocol adherence were exemplary. Statusline rung was live (preflight
normal); I17/cap-3 never engaged — nothing was ever admitted.

## P3-2 🔴 The ratified plan is internally floor-inconsistent — and plan_ready cannot see it

The contradiction was RATIFIED: D17 sets models.py=high floors AND
GL1=routine-touching-models in the same plan. It is systemic, not a GL1
quirk — GL4/GL6/GL7 (elevated) all add models to the shared `models.py`
(floored high) and would bounce at their turn; GL10 (routine) touches
`routes/**` (elevated). `plan_ready` validates artifacts, ratification,
and vault — **not** floors×profiles consistency, because predicted diff
paths live in spec prose. Fix direction (I19 candidate): plan-build
records each task's predicted `touches` globs in tasks.json; plan_ready
cross-checks touches × floors × profile deterministically at ratification
time. The gate stays the enforcement point; planning gains the static
pre-check the session had to improvise.

## P3-3 🟡 (process, operator-side) A frozen instrument must be re-validated when gate policy changes

The same-plan protocol froze a plan ratified BEFORE I16 (floors-always);
nothing re-checked the instrument against the new manifest, and the
pre-registration named GL10 as the expected bounce when pilot-2's own
tick-1 analysis had already documented GL1 creating floored paths — the
evidence was in the ledger and did not get propagated. Protocol amendment:
a plan is versioned against the machinery that ratified it; any
manifest/floor/profile-policy change requires re-running the (I19) static
consistency check and, if it fails, a re-ratified instrument v2 — which
then becomes the new constant across pilots.

## Decision — RESOLVED 2026-07-05: Package A ratified

Operator ratified the profile-raising amendment: GL1/GL4/GL6/GL7 → high,
GL10 → elevated; specs/scope byte-identical to v1. Re-ratified as
**instrument v2** (`fb51fce3346daa04`), snapshot unchanged (`d71eba21`,
same task ids). GL1's blocker card carries the resolution; the next firing
resumes it parked→in_progress. v2 is the fixed constant for pilot
#3-rerun and #4; the added validation cost on 5 tasks is telemetry, not
overhead. I19 (planning-time floors×profiles static check) remains the
machinery fix so no future instrument ratifies this contradiction.

## The original options (for the record)

The blocker card's options, augmented by the systemic view:
- **Package A (minimal, recommended for pilot discipline):** raise profiles
  to match floors — GL1/GL4/GL6/GL7 → high, GL10 → elevated; specs and
  scope untouched; one tasks.json edit → re-ratify as **instrument v2**;
  rerun pilot #3. Validation cost rises on 5 of 10 tasks — that cost is
  itself telemetry (the true price of floors-always on this plan).
- **Package B (architectural):** floored-surface ownership — GL1 sheds the
  models.py/services placeholders (their creating owners take them:
  GL2-critical creates models.py Base; the services package lands with its
  first high-profile user), optionally models.py floor high→elevated.
  Truer product structure, more plan surgery, weaker cross-pilot
  comparability.
- **Accept-halt** (characterize only) remains the no-edit option; it ends
  greenlane building under this protocol.
