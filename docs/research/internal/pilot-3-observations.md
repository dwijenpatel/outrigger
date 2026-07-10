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

## P3v2-1 🔴 (machinery + protocol) A profile raise silently armed H9; the ask stalled the firing (8h25m as stamped; ≲85 min clock-corrected — see P3v2-3)

**Chain:** Package A raised GL1 routine→high to clear the floor collision →
`BLOCKING_AMBIGUITY_PROFILES=("high","critical")` now includes GL1 → its
**carried-over** test-author handoff records 10 `spec_ambiguities` (advisory
under v1/routine) → H9 fires pre-spawn. The session asked interactively
(stamped 12:15:12Z); the operator answered 20:40Z. First measured as **8h25m
of firing wall-clock on an unnoticed terminal prompt** — the P3v2-3 host-clock
correction (~+8h mid-firing) revises the true wait to **≲85 min**, and the
"5-hour window reset unused mid-stall" reading (five_hour 0.43 → 0.0) was an
artifact of the same skew. The protocol failures below are magnitude-
independent: an unnoticed prompt is unbounded by construction.

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
   only WITH the answer (20:40Z), not at ask time — for the whole wait the
   question existed nowhere but the session's context, and the ledger claimed
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

## Status (mid-firing, ~14:11 local — superseded by the firing close below)

I19/I20/I21/I22 merged upstream 2026-07-05 (542 tests). **Not synced to the
pilot clone mid-firing** (machinery frozen); sync at the next firing
boundary. Note for this firing's remainder: the frozen clone still has
pre-I20/I21 machinery, so GL2/GL3/GL5/GL8/GL9 (high/critical) test-authors
that record ambiguities will park again — expected, card-per-decision, and
now it is the known cost of the frozen arm rather than a surprise.

---

# Firing close (21:37:30Z) — GL1 done; session findings folded; boundary sync

The firing session ran GL1 end-to-end after the adjudication and **paused
cleanly on the operator's request** (resume marker seq 7: next task GL2,
occupancy snapshot, run conventions; run marker released; nothing in flight).
It kept its own in-clone ledger numbered P3v2-0..7; that file is folded here
(upstream numbering below; mapping: session 0 → close summary, 1 → P3v2-1
✅ confirmed, 2 → **P3v2-3**, 3 → P3v2-2 ✅ fixed I22, 4 → **P3v2-4**,
5 → **P3v2-5**, 6 → **P3v2-6**, 7 → **P3v2-7**) and superseded — the local
copy was moved aside at the boundary sync (it was untracked and tripped the
gate's `require_clean` on main; the session's `repo=<task worktree>` hint
worked around that).

## P3v2-3 🔴→I25 Host clock corrected ~+8h mid-firing; `fraction_rate`'s cross-firing lookback (W7)

Early stamps were local-time-labeled-Z; the correction landed mid-firing.
Every module's `_utcnow_iso()` is internally consistent at any instant — not
a machinery bug — but tick 1's `fraction_rate` resolved from the *prior*
firing's reading (inside the 6h lookback), engaging reset-headroom
immediately; after the correction those readings retro-aged past the window
and I17 correctly reverted to conservative. Also corrects P3v2-1's
magnitude (8h25m → ≲85 min). → **I25**: `fraction_rate(since_ts=run-marker
acquired_at)` — burn rate is per-firing; fresh firings stay conservative
until ~10 min of their own readings (the pre-registered expectation).

## P3v2-4 🟡 Held-out run convention: the corpus consumes spec-mandated fixtures (W6)

Naive `pytest .heldout` → 14 `fixture 'app'/'client' not found` errors: GL1's
held-out tests deliberately consume the `app`/`client` fixtures the spec
mandates `tests/conftest.py` provide. Project convention (pinned in the
resume marker): `env PYTHONPATH=pilot/greenlane:pilot/greenlane/tests
python3 -m pytest .heldout -q -p conftest`. Not a defect; the general rule —
**the plan pins each project's `heldout_cmd`** — rides the kickoff and the
next plan-build interview.

## P3v2-5 ✅ The held-out corpus caught a defect visible tests + 3 blind validators all missed (W6 — the design thesis, first live proof)

Attempt 1's `get_db(request)` passed visible tests, typecheck, and the full
3-lens opus panel; the held-out corpus failed 3 tests (`get_db()` must be a
zero-arg generator dependency — exactly the reading the operator's
proceed-as-read endorsed). Attempt 2 (fresh worker, same tier, sharpened
spec-grounded feedback — no test leakage) fixed it and caught a latent
`dependency_overrides` closure bug that would have silently broken later
DB-backed tasks. Gate: 41/41 held-out, 3/3 verdicts, floors OK, merged
`--no-ff` with stamp. **Blind validation + held-out vault earned its cost on
the first real merge.**

## P3v2-6 🔴→I24 The escalation ladder's effort rung is not actuatable via `Agent` (P3v2-6)

`Agent`/`Task` expose `model`, no per-spawn `effort` (session-inherited).
The session substituted "more effort, same tier" = fresh worker + sharp
feedback, reserving tier-up for attempt 3 (not needed). → **I24**: ladder
restated in actuatable terms (feedback → tier); recorded effort = requested
param; `max`-effort rung reserved for Workflow-path spawns.

## P3v2-7 📊 v2 validation cost (W9 — the floors-always price, first datapoint)

GL1 (high, 3-lens opus panel), per-attempt subagent tokens: panels 83,470 +
79,743; implementers 60,137 + 37,309; **task total ≈ 260,659 across 2
attempts** — panel spend ≈ 63%. Run-log carries per-attempt `task_complete`
with model/tier/effort/attempt + `panel_tokens` (W8 ✓). 8/10 v2 tasks run
high/critical panels; the accumulating run-log is the measure.

## P3v2-8 🔴→I23 Pause channel: an in-session request starves behind a foreground worker (operator-side)

The operator typed `/build-pause` INTO the live firing session; it sat in
the message queue ~17 min until the turn yielded at the GL1 merge — the
GL1 implementer had been spawned **foreground**, so the orchestrator was
deaf the whole attempt, and no `state/pause.request` flag existed for the
tick-boundary check to see. The clean pause it then ran was exemplary
(ack-worthy resume marker, no in-flight loss). → **I23**: acknowledge
(`state/pause.ack`) → drain (attempts are atomic; kill = redo) → park;
flag checked at every stage boundary; workers spawn in background with
polling; build-pause now sets the operator expectation (ack ≤ one poll
interval; full pause ≤ longest in-flight attempt) and directs live-firing
pauses to the flag from a second terminal.

## Close status

- **Ledger:** GL1 done+merged (`745b8fb`), 1/10; 9 not_started; next
  GL2-auth-tenancy (critical — fresh test-author, no carried corpus).
- **Quota at pause:** five_hour 0.15, seven_day 0.73 (weekly reset ~01:00Z
  = ~18:00 local 2026-07-05).
- **Machinery:** I19–I25 merged upstream (545 tests); **test1 synced at this
  pause boundary** — the arm changes here; run-log records after resume are
  the new arm. Same-plan instrument v2 unchanged (byte-identical preserved).
- **Watch items open:** W1–W5 (concurrency family — first opportunity
  GL3∥GL4 after GL2), plus new: preflight-at-firing-start first live run
  (I19 check 7), pause-ack live use (I23), fresh test-author handoffs under
  I20 (do they mark `corpus_covers`?).

---

# Leg 2 — GL2-only, new (headless I26) arm shakedown — 2026-07-05T23:03Z→06T00:17Z (operator attending)

Resumed `greenlane-pilot3-v2` from the seq-7 marker on the **new machinery
arm** (I19–I26 + `harness.smoketest` synced at the GL1 pause boundary). Start
gates all green: plan-ready **7/7** (I19 preflight green — GL1's resolved cards
adjudicate the carried blockers), selftest **30/30**, **smoketest 17/17** (I5
composition proof, first live use), vault valid, skill budget 762/15000,
preflight NORMAL (live statusline rung 1s old). GL2 was the sole runnable.

**The arm never completed a single productive worker** — the window was over
budget and the governor was right at every turn. Five findings:

## P3v2-9 🔴 `headless_worker_cmd` emits `--json-schema <PATH>`; CLI 2.1.201 wants inline JSON

`loop.headless_worker_cmd(json_schema_path=...)` builds `--json-schema
harness/config/schemas/handoff.json`; `claude` 2.1.201 parses the flag value as
inline JSON → `Error: --json-schema is not valid JSON: Unrecognized token '/'`,
exit 1, empty stdout. Orchestrator workaround (no machinery edit): pass
`--json-schema "$(cat <schema>)"`. **Upstream fix:** `headless_worker_cmd`
should inline the file's contents (or the CLI should accept a path).

## P3v2-10 🔴 `parse_worker_result` → `parsed=None` on a *compliant* worker (fenced result + null structured_output)

Real CLI (2.1.201) leaves `structured_output=null` (the `--json-schema` flag did
not tee a validated object) **and** the model returns its handoff JSON fenced in
```` ```json … ``` ```` inside `result`, so `json.loads(result)` fails →
`parsed=None`. Per the skill, `parsed=None` == contract violation → ladder, so
**every honoring worker would spuriously escalate**. Workaround: prompt for raw
JSON (no fences) **and** fence-strip `result` before concluding a violation.
**Upstream fix:** strip code fences in `parse_worker_result` before `json.loads`.

## P3v2-11 🔴 `failures.load_patterns(loop.HEADLESS_FAILURE_PATTERNS)` raises (tuple vs list)

The skill's documented death-classify incantation raises
`FailureConfigError('pattern table must be a JSON list')`:
`HEADLESS_FAILURE_PATTERNS` is a **tuple**, `load_patterns` requires a **list**.
Workaround: `load_patterns(list(...))`. **Upstream fix:** make the constant a
list, or accept any sequence.

## P3v2-12 ✅→🔴 The governor was RIGHT: proceed-under-degrade hit a hard Fable-5 429 on the first call

The between-task governor read the live rung as **seven_day 0.82 / five_hour
0.63 → degrade**; `scheduler.tick` **deferred** GL2 (`admission.admit`
hard-gates `occupancy≥degrade`, independent of reset_headroom/phase; I17 was
conservative anyway per I25 — only one governor reading since this firing's
marker). Card-first adjudication (I21): card + parked-truth + notify **before**
the ask. Operator overrode → proceed. The fresh test-author (**fable-5**, the
critical base + the 4-lens panel model) died on its **first call**:
`api_error_status=429`, *"You're out of usage credits … Fable 5"*, num_turns=1,
**0 tokens**, cost 0. `classify` → retryable, but it is **credit exhaustion**,
not transient overload. **The governor's degrade hold was vindicated
end-to-end.**

## P3v2-13 🔴 The Opus substitute HUNG 38 min with no watchdog and no liveness signal

Operator then authorized substituting **opus-4-8** for the fable roles
(shakedown-only, no-merge). The opus test-author **hung ~38 min**: 7.35s
cumulative CPU, 0% CPU in `sleep`, open-but-idle TCP to `api:443`, **0 bytes
out, `.gl2_heldout` never created**. Diagnosed by `ps` (CPU flat) + `lsof`
(idle API sockets); killed via `TaskStop`. The *"opus is unaffected"* premise
was **false** — under the same over-degrade window that 429'd fable-5, opus was
throttled into an indefinite backoff **stall**. Two machinery gaps: **(a)** the
only worker time-bound is `--max-turns`, which never fires on a **pre-compute
hang** — no client-side wall-clock watchdog on the spawn path, so a
quota-stalled worker burns unbounded wall-clock silently; **(b)** no
heartbeat/liveness from a headless worker (`Vitals` sees no steps because none
arrive) — detection took manual `ps`/`lsof` forensics. **Upstream fix:** a
per-worker wall-clock deadline + a no-progress kill; optionally surface a
periodic liveness ping.

## Leg-2 close status

- **Ledger:** GL1 done+merged (`745b8fb`), 1/10; GL2 **parked** on the
  Fable-5 credit wall (card `state/blockers/GL2-fable5-credit-exhaustion.json`,
  with `substitution_outcome`); 8 not_started. No new merge this leg.
- **Records:** run-log carries the full honest trail — `task_spawn`×3
  (fable-5 test-author, opus-substitute test-author) + `task_aborted`×2
  (429, then hang) with requested params + attempt; ledger events seq 8–11
  (admit-by-override → park → resume-under-substitute → re-park); governor-log
  + scheduler-log (deferral tick 2 + operator_override_admission).
- **Quota:** seven_day 0.82 (over the 0.80 degrade line), five_hour 0.63;
  weekly reset ~2026-07-06T00:59:59Z. **Fable-5 credits exhausted.**
- **Decision (operator, attending):** clean-pause + re-fire after the window
  resets and fable-5 credits return.
- **Arm verdict:** the headless spawn/harvest **mechanism** works (proven on a
  haiku probe: exit 0, usage + `total_cost_usd` harvested, spawn interlock
  correctly gated on the admission stamp), but the arm needs three integration
  fixes (P3v2-9/-10/-11) and a worker watchdog (P3v2-13) before it is
  production-trustworthy — and it cannot be exercised end-to-end until the
  quota window has headroom.

## Upstream resolution (same night, merged before the re-fire)

- **P3v2-9** → **I29**: `headless_worker_cmd` inlines the schema file's
  contents for `--json-schema` (loud when unreadable).
- **P3v2-10** → **I29**: `parse_worker_result` strips one outer code fence
  before parsing `result`; `structured_output`-null-on-2.1.201 documented.
- **P3v2-11** → **I29**: `failures.load_patterns` accepts tuples.
- **P3v2-12** → **I28**: **Fable 5 removed from the machinery** (operator
  decision — the model-specific weekly cap is far below the general windows
  AND fable is the operator's primary interactive model, so machinery spend
  starves interactive work). `max` temporarily aliases `capable` (opus);
  fable is off the allowlist entirely; tier-up saturates at opus (attempt-3
  from capable parks instead). Reintroduction = one tiers.json line, gated
  on the cap rising or interactive usage reliably dropping. Plus a
  PERMANENT classify pattern for `out of usage credits` ("park until the
  window resets; substitution does not dodge the window"). Economics
  recorded in token-economics §2c.
- **P3v2-13** → **I29**: `run_headless_worker` — every worker runs under a
  client wall-clock deadline (default 45 min; 3× profile P95 when
  calibrated) that kills the process group and returns the death
  structured. Heartbeat/liveness pings from headless workers remain future
  work (the deadline covers the observed failure mode).
- The GL2 leg's operator constraint ("shakedown-substitute, no-merge")
  dissolves under I28: opus IS the critical routing now — the re-fire runs
  GL2 real and merges through the gate.

## P3v2-14 🟡 (operator-side) Default-mode firings flood the operator with permission prompts

A firing is arbitrary-Bash heavy; launched in `default`/`manual` mode it
prompts almost immediately and frequently — the operator had to remember
"Auto mode on" before every kickoff. Facts established: the mode is
**operator-only** (no tool/slash/hook lets a session change it); project- and
local-scope `permissions.defaultMode: "auto"` is deliberately **ignored**
(v2.1.142+ — repos must not grant themselves auto); official docs (2.1.200+)
list a `permission_mode` field in the statusline stdin, but the 2.1.201 dump
**measurably lacks it** (docs-vs-build conflict; measured wins, re-check on
version moves). → **I30**: kickoff blocks pin the launch line
(`claude --model <m> --permission-mode auto`) and build-loop step 0 checks
`loop.permission_mode(dump)` — fail-closed STOP on a wrong mode, advisory on
None — live the moment the CLI ships the field.

## P3v2-15 🟡 The reference page existed and the orchestrator source-dived anyway (discoverability)

The GL2 re-fire session (leg 3) opened with exemplary resume judgment — it
correctly dissolved the leg-2 workarounds (upstream fixes in its arm) and the
fable half of the resume precondition (I28), and refused to act on a stale
pre-reset degrade log, demanding a fresh live governor read. Then it spent
minutes reading `harness/*.py` sources to re-derive API signatures — while
`docs/reference.md` (I3, built for exactly this, honesty-tested) sat unread
in its repo. Nothing pointed at it: the skill never mentioned the page.
Docs that are not discoverable at the point of need save nothing.
→ build-loop skill preamble now sends the orchestrator to the reference
page FIRST, source-diving only for what the page lacks.
