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

---

# Pilot #3-v2 (rerun on instrument v2) — observations

Rerun started 2026-07-05 12:01Z (`greenlane-pilot3-v2`, ratification
`fb51fce3346daa04`). Reviewed live at ~20:50Z from artifacts + the session
transcript while the firing continues (GL1 implementer spawned 20:49Z).

## P3v2-0 ✅ (what worked)

- **Resume discipline exact:** GL1 `parked→in_progress` off the resolved
  blocker card, no re-adjudication (ledger seq 3, 12:05Z) — precisely the
  kickoff contract.
- **I17 first live engagement, both directions:** tick 1 (12:13Z) resolved a
  real `fraction_rate` from two governor readings, `reset_headroom_clears:
  true` flipped `window_phase` tail→mid; at 20:43Z the same machinery
  correctly **reverted to conservative** on >6h-stale readings before
  re-reading fresh. Statusline rung live throughout.
- **Records discipline post-resume:** worktree + branch per convention;
  `task_spawn` write-ahead with resolved spawn params before the implementer
  spawn (W8), including the I12 split (high profile → standard-tier/sonnet
  implementer, xhigh, attempt 1).
- **By-the-book machinery workaround:** hitting P3v2-2 (below), the session
  diagnosed the false positive empirically, logged it as a finding, and
  rephrased its command — no local machinery edit (P2-collision rule held).
- Append-only logs carried the v1→v2 transition in one file cleanly
  (scheduler-log holds the v1 close and the v2 tick-1 side by side).

## P3v2-1 🔴 (machinery + protocol) A profile raise silently armed H9; the ask stalled the firing 8h25m

**Chain:** Package A raised GL1 routine→high to clear the floor collision →
`BLOCKING_AMBIGUITY_PROFILES=("high","critical")` now includes GL1 → its
**carried-over** test-author handoff records 10 `spec_ambiguities` (advisory
under v1/routine) → H9 fires pre-spawn. The session asked interactively
(12:15:12Z); the operator answered 20:40Z. **8h25m of firing wall-clock on an
unnoticed terminal prompt; a full 5-hour quota window reset unused
mid-stall** (five_hour 0.43 → 0.0 across the gap).

Four layered causes, each fixed upstream:

1. **False positive at the source.** All 10 ambiguities were dual-covered in
   prose ("tests accept both readings") — the schema had no machine-readable
   discharge, so H9 counted them anyway. → **I20**: `corpus_covers: "both"`
   discharges an entry (advisory everywhere); test-author contract updated.
2. **Foreseeable at re-ratification, discovered mid-firing.** The Package-A
   analysis re-simulated the gate that had fired (floors) but not the gates
   the raise would newly arm (H9) — same miss family as P3-3, and it proves
   the sweep must be mechanical, not memory. → **I19**: `gate_preflight`
   (floors×touches + H9×existing-handoffs) as `plan_ready` check 7 + a
   pre-ratification CLI. Verified against this pilot's live state: it
   reproduces this whole event as a non-fatal, already-adjudicated finding.
3. **Ask-before-card (write-ahead violation).** The blocker card hit disk
   only WITH the answer (20:40Z), not at ask time — for 8h25m the question
   existed nowhere but the session's context, and the ledger claimed
   `in_progress` with no live worker (claims-vs-evidence). The v1 halt got
   this right; the interactive path had no card-first discipline. → **I21**:
   card + `parked` status + notification BEFORE any ask; ask only when
   nothing else is admissible; `resolved{decision,by,at}` on the card;
   operator-wait now disk-derivable (parked→resumed).
4. **No operator signal.** Nothing pinged a human; the prompt sat in a
   backgrounded terminal. → **I21**: `tools/notify_operator.sh` (best-effort
   bell + macOS notification) on every operator-blocking event.

Judgment note: the ask itself was high quality (three options with
consequences + recommendation, mirroring the card schema) and GL1 being the
serial root meant park-and-continue had nothing to continue — the defect was
protocol and timing, not the session's judgment.

## P3v2-2 🔴 git_guard destructive-pattern false positive across command lines

The session's worktree-setup compound (safe: `git worktree add …`, an
`echo "--- clean check ---"`, `git … rev-parse --abbrev-ref HEAD`) was
blocked: `clean\s+[^|;&]*-[a-z]*f` matched from the echo's "clean" across a
newline to `-ref`. Gap classes didn't exclude `\n`, so patterns spanned
lines of a compound. Session diagnosed it empirically and worked around it
(word removed), correctly refusing to patch machinery locally. → **I22**:
all gap classes now `[^|;&\n]*` (a newline separates commands exactly like
`;`); regression test is the live repro; destructive lines inside compounds
still match.

## Status

I19/I20/I21/I22 merged upstream 2026-07-05 (542 tests). **Not synced to the
pilot clone mid-firing** (machinery frozen); sync at the next firing
boundary. Note for this firing's remainder: the frozen clone still has
pre-I20/I21 machinery, so GL2/GL3/GL5/GL8/GL9 (high/critical) test-authors
that record ambiguities will park again — expected, card-per-decision, and
now it is the known cost of the frozen arm rather than a surprise.
