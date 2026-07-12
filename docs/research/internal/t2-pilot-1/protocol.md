# T2 Pilot 1 — harness vs. null: pre-registered protocol

**Status: REGISTERED, not yet scheduled.** Registered 2026-07-12; the registration is anchored
in [v2-ledger.jsonl](../v2-ledger.jsonl) (`kind=note`, `subject=t2/pilot-1/protocol-registered`)
with this file's sha256, per D14's pre-registration discipline
([design](../../../design/evidence-based-harness.md) — experiments fix hypothesis, arms,
metrics, and decision rules *before* running). Any post-registration change is an **amendment**:
recorded in the ledger, dated, and listed in the results write-up. Results reported without
their amendments list are invalid.

## 1. The question

**R2's founding obligation, put to the test:** does the harness — blind spec-authored held-out
suites, counts-only feedback, blocking gates, whole-build closure — produce better *accepted
work* than plain Claude Code with a good prompt, on realistic tasks, and at what cost?

Relationship to the design's ledger: this is **pilot 1 of T2**, aimed at the R2 null (the
biggest question first). T2's full decomposition — test-secrecy alone vs. secrecy + full
gating ("N1") — is **pilot 2**, warranted only if pilot 1 shows the apparatus earning keep at
all.

## 2. Hypotheses (fixed before any run)

- **H1 (mechanism):** on ≥1 pilot task, the harness's held-out suite will block or force the
  repair of a defect that the null arm lands — and the reverse (a defect class the null avoids
  *because* it lacks the harness) will not occur.
- **H2 (false friction):** the harness will produce ≥1 false blocker (correct work stopped) —
  the cost side of D5's blocking-gate design. We predict this openly; counting it is the point.
- **H3 (spend):** harness cost per accepted task will be 2–5× the null's (author + gate +
  possible escalation overhead). Recorded, not optimized (R4).

## 3. Arms

**Arm H — the harness as shipped.** `exec-loop` with the `claude_p` launcher, default worker
config (author Opus 4.8 @ xhigh; implementer Sonnet 5 @ xhigh, escalation to Opus; cap 2),
per-task blind suites, counts-only feedback, gates, ff-only landing, whole-build closure.

**Arm N0 — the realistic null.** One strong session per task (`claude -p`, Opus 4.8 @ xhigh —
the *strong* single agent, matching the harness's escalation ceiling): prompt = the identical
ratified task spec + plan context, repo access, instruction to implement, run the task's stated
checks and the repo's existing tests, fix what fails, and commit when it judges the work done.
No held-out anything, no external gate, no machinery retries: acceptance is the null's own
completion claim plus whatever verification it chose to run — exactly what a solo operator
without the harness would get. Its landed state is whatever it committed.

Fairness posture, stated plainly: the arms are **not budget-matched** — the harness inherently
spends more (extra author, gates, possible second attempt). That asymmetry *is the mechanism
under test*; spend is a recorded outcome (§7), and cost-per-accepted-correct-task is the
pre-named efficiency lens. The null is not handicapped: it gets the same spec, the same repo,
the strongest model, and freedom to verify however it likes.

## 4. Task set

**Size:** 6–12 tasks across 2–3 repositories. **Frozen before any arm runs:** the exact task
list, specs (ratified plan.json files), base SHAs, and repo clones are recorded in
[tasks-manifest.json](tasks-manifest.json) *before the first worker spawns*; the manifest's
sha256 goes into the ledger at freeze time. Tasks added or dropped after freeze = amendment.

**Composition (per the external review, adopted):** at least one each of —
1. a normal bug fix;
2. a multi-file feature;
3. an integration or dependency change;
4. an ambiguous-requirement task (realistic under-specification; the interview pins what it
   pins, and post-ratification ambiguity discoveries land in the escapes log);
5. a task where the repo's visible tests are plausibly insufficient to catch a wrong
   implementation;
6. **1–2 seeded-defect canary tasks** — tasks with a planted, documented wrong-path that a
   correct implementation must avoid (the plant is recorded sealed in the manifest, revealed
   only at grading). These calibrate the oracle (§5), with M4's caveat stated: they measure
   sensitivity to *planted* defects, not the real distribution.

**Sourcing:** real repositories the operator names (scheduling blocks on this — §10), sized so
each task is a reviewable diff (a few hundred lines max). Specs come from the standard
spec-interview, once per task, shared verbatim by both arms.

## 5. The defect oracle (the heart of the design)

"Defects escaping acceptance" needs an arbiter neither arm optimized against:

- **Primary — the arbiter suite.** For every task, a *third* blind author (the existing
  heldout-suite machinery, separate spawn, Opus 4.8 @ xhigh) writes an **arbiter suite** from
  the ratified spec alone, sealed **before either arm runs the task**. It is never executed by
  either arm's process, never feeds back into any attempt, and grades both arms' *landed*
  states identically after both finish. Symmetry is the load-bearing property: the arbiter's
  imperfect coverage biases neither arm.
- **Secondary — blinded operator review.** The operator reviews each task's two landed diffs
  with arm identity stripped (prepared by the session, order shuffled per task, labels A/B),
  marking defects and scope violations. Blinding note, honestly: perfect blinding is unlikely —
  harness diffs may be recognizable (style, commit shape) — so this channel is *secondary*, and
  the review sheet records a "could you tell which arm?" field per task.
- **Calibration — the canaries.** The seeded tasks' plants must be caught by the arbiter suite
  when present in a landed change; an arbiter that misses its canary is recorded as an oracle
  miss and that task's arbiter verdicts are downgraded to the blinded-review channel alone.

Oracle contamination rules: the arbiter author never sees either implementation; arbiter
suites are sealed (manifest sha in ledger) before first spawn on that task; arbiter results
are computed only after both arms complete the task.

## 6. Procedure (per task)

1. Interview → ratified plan.json (one task's spec; both arms will consume it verbatim).
2. Arbiter suite authored + sealed (ledger record).
3. Two clones of the repo at the manifest base SHA: `clone-H`, `clone-N0`.
4. Run the arms, **alternating which goes first by task index** (odd: H first; even: N0
   first); record start/end timestamps and window identity for both. (Same-account prefix
   caching may cheapen whichever arm runs second — alternation plus recorded order is the
   mitigation; spend comparisons carry this caveat.)
5. After both arms finish: run the task's stated checks + the arbiter suite against each
   arm's landed state, mechanically; record per-arm results.
6. Blinded review sheet for the task's two diffs.
7. Ledger everything (spawns, seals, gates, closure, arbiter verdicts — the run-ledger is the
   raw data; the manifest + reports are the artifact).

No mid-pilot fixes to harness machinery: if a harness defect surfaces mid-pilot, it is
recorded, the task pair completes as-is, and the fix waits for the pilot to end (amendment
rule otherwise).

## 7. Outcomes (all pre-named; nothing else gets promoted to a "finding")

**Primary:**
- **Defects escaping acceptance**, per arm: arbiter-suite failures (and blinded-review
  confirmed defects) in *landed* work.
- **Unique catches**: defects present in one arm's landed work that the other arm's process
  demonstrably caught (harness: a gate rejection whose failing held-out test matches the
  null's landed defect; null: any symmetric case).
- **False blockers** (harness only, by construction): blockers/rejections on work the arbiter
  judges correct.

**Secondary:** per task and arm — attempts and escalations; operator interventions (count,
minutes); wall clock; tokens and cost (auto-captured per worker since run 4); churn; suite
sizes; blockers by reason.

**Qualitative (mechanism traces):** for every rejection, block, or catch: *which* information
caused it (which test, which channel, which feedback line) — the "what actually worked" record
that decides what pilot 2 isolates.

## 8. Decision rules (small-n honesty, fixed now)

n ≤ 12 yields **existence and direction, never rates**. No percentage claim survives this
pilot; anything phrased as a rate in the write-up is a protocol violation.

- **Mechanism demonstrated:** ≥1 clean unique catch by the harness (H1 pattern) and zero
  symmetric opposites → the vault mechanism has a live, oracle-confirmed instance at realistic
  scale. Consequence: proceed to pilot 2 (N1 decomposition: secrecy-alone vs. full gating),
  and the design's D2 evidence line gains this pilot as internal existence evidence.
- **R2 pressure:** the null lands ≥ as many arbiter-clean tasks, at ≤ cost, and the harness
  records zero unique catches → the apparatus is not earning keep at this task scale.
  Consequence (pre-named): D2/D5 stay Decided as *mechanisms* but their **default-on scope**
  is demoted to Provisional pending risk-tiered configuration (D15's compose-set lever) — the
  harness becomes something you turn on for high-stakes work, not everything.
- **Mixed** (catches both ways, or catches offset by false-blocker cost): enumerate, publish
  the traces, and let pilot 2's design target the live uncertainty. No status changes.
- **Oracle failure** (arbiter misses ≥half the canaries): the pilot reports *operational*
  outcomes only (cost, friction, attempts) and defers correctness claims — an honest partial
  result, not a forced conclusion.

## 9. Threats to validity (named now, so nobody discovers them post-hoc)

- **Arbiter is LLM-authored:** imperfect, possibly correlated with the harness author's blind
  spots (same model family — §3.1 error correlation). Symmetric across arms; canaries bound
  its sensitivity; blinded review is the second channel.
- **Operator unblinding** (recognizable arm styles): recorded per task; review channel is
  secondary.
- **Cache-order spend contamination:** alternation + recorded order; spend read directionally.
- **Task selection bias:** tasks chosen by the same people who built the harness — the
  composition list (§4) forces variety, and the manifest freezes it before any result exists.
- **One operator, one account, one machine:** as everywhere in internal evidence — stated,
  not fixable at this scale.

## 10. Budget and scheduling (operator-gated)

Rough per task: arbiter author ~$2 + Arm H ~$3–5 (author + implementer + possible escalation +
gates) + Arm N0 ~$1–2 ≈ **$6–9/task** → 8 tasks ≈ **$50–70**, several 5-hour windows,
operator-kicked per the standing quota rule. Needs from the operator before freeze: named
target repositories, and window reservations. T1 remains independent and can run in any clean
window before or during.

## 11. Write-back (where results go)

Raw artifacts under `docs/research/internal/t2-pilot-1/` (manifest, ledger, arbiter seals,
review sheets, per-task reports — committed before any narrative). Results write-up updates:
the design doc's T2 row and D2 evidence line; `distilled/internal.md` (graded by its actual
warrant: existence-level, artifact-backed); the corrections ledger if any harness defect
surfaced mid-pilot. Every claim carries its amendment list.
