---
name: plan-review
description: "Adversarial review of plan/spec PROSE before implementation — find → verify → filter-hard, aimed at spec defects: sentences admitting divergent readings, cross-spec seam contradictions, unpinned observable behavior, checks that cannot adjudicate their contracts, silently broken local conventions, and substrate claims about external systems that are simply false (probed by execution, since a false sentence has only one reading and no ambiguity instrument can see it). Writes plan-review-report.md with divergence pairs, probe transcripts, and proposed rewrites; --fix applies confirmed rewrites to the spec files. Use before ratifying or implementing a plan, after any amendment round that changes mechanism prose, or when invoked as /plan-review [--fix] [lean] [paths]."
---

# plan-review — adversarial spec reading, pre-implementation

`/plan-review [--fix] [lean] [plan artifacts…]`

**Tiers.** Default is the full shape below (3 translators + 5 angle finders +
grouped verification). With `lean` in the arguments, run a reduced shape: **2
translators + 2 merged finders** (seams+conventions as one agent, oracle-fitness+
under-determination as the other) + grouped verification. Lean costs roughly half
and is blunter — the 2-way translator diff exposes an 80/20 trap on ~32% of pair
readings vs ~48% for 3-way. Use lean for small plans (≲8 specs), cheap early passes,
or re-review after amendments; use the default when the plan gates real build spend.
**The substrate-truth finder runs in both tiers** — it is the cheapest agent here and the
only one that can see a false-but-unambiguous sentence, so it is never the one you drop.

You are reviewing **plan prose, not code** — nothing under review executes. The target
defect class: a spec sentence that admits two defensible readings. Whichever implementer
takes the minority reading ships a defect; a test author misreading the same sentence
ships a defective oracle; end-state code review catches neither, because code that is
consistent with its author's reading looks correct. The cheapest interception point is
before anyone implements — that is where you sit.

**The finding contract (load-bearing).** Every finding MUST carry a **concrete
divergence pair**: two readings of one location, each stated as executable-style
behavior — input → exact output (exact shapes, nesting, names) — both defensible, with
no sentence anywhere in the plan or its source design doc resolving them. A claim
without a divergence pair is not a finding; drop it. This rule is what separates
adversarial reading from style critique. False positives are this tool's #1 product
risk: every surfaced finding spends ratifier attention or (in `--fix` mode) rewrites
someone's spec.

**Exactly one exception: the falsified substrate claim.** A sentence asserting how an
external system behaves — a framework default, middleware ordering, a tool's pattern
syntax — can be simply *false*, and a false sentence has only one reading. It therefore
passes every ambiguity instrument in this skill by construction, which is precisely why it
is the class that survives to production. Its finding contract is **a probe transcript
instead of a divergence pair**: the command, the trimmed output, the version, and the plan
sentence it contradicts. Nothing else is admitted without a divergence pair — do not use
this exception to smuggle in style critique about wording you dislike.

## Phase 0 — Gather scope

Arguments name the plan artifacts; otherwise discover them: `plan.json` or
`tasks.json`, the spec files they reference (e.g. `specs/`), the design doc the plan
was derived from, and the repo's `AGENTS.md` conventions file. Read all of it fully.
The review unit is the whole plan — divergences live *between* files as often as
within one.

## Phase 1 — Finders (parallel subagents, one message)

Launch all finders concurrently via the Agent tool. Every finder returns findings as:
`file`, `section-or-line`, `angle`, a one-line `summary`, the `divergence pair`, and
`unresolved_by` (which sentences it checked for a resolution, and why they do not pin
it). Drop findings without divergence pairs at collection.

**Independent translators (×3) — the divergent-readings instrument.** Three agents,
identical prompt, no shared context: *translate the plan's **contract surfaces** into
concrete assertions (input → exact expected output), section by section, keyed by
(file, contract point). Contract surfaces are: public APIs and signatures, algorithms
and their worked examples/goldens, wire/IR shapes, error models, and acceptance
checks. Skip narrative, motivation, and background prose — translating it is the
dominant token cost and (measured on the first live firing) produced zero findings.
Choose the reading you would implement. Do not flag ambiguity; just translate
honestly.* Then diff the three translations key by key: any contract point where they
disagree structurally (different shape, nesting, value, or behavior) is a candidate
finding, and the disagreeing translations ARE its divergence pair. This catches what a
single hunt-for-ambiguity pass misses: readers who misread a trap sentence each
believe their reading is *the* reading — divergence is detected by comparing honest
readings, never by asking one reader to doubt. Three translators, not two, is
deliberate: the third reader buys recall, not just tie-breaks (measured rates: the
Tiers note above).

**Cross-spec seam finder (×1).** For every interface one task provides and another
consumes: does the consumer restate the interface (module path, signature, exact
shape), and does the restatement match the producer exactly? Flag mismatches AND
absences — a consumer that never restates forces the implementer to guess. Also sweep
scenario prose in each spec against the surfaces other specs define: a scenario one
spec describes (growth, future ops, error flows) that another spec's surface cannot
support is a seam defect even when each spec reads clean alone.

**Oracle-fitness finder (×1).** For each task's acceptance checks and each testable
contract sentence: could a test written from this sentence alone (a) reject a correct
implementation — over-pins: exact-message asserts, string-absence asserts, incidental
structure the sentence never promises — or (b) accept a wrong one — the sentence
forces the test author to invent details the spec does not pin? Spec prose is the
oracle's source; a sentence only a lucky test author survives is a defect.

**Under-determination finder (×1).** Enumerate decisions an implementer MUST make that
are observable in outputs or checks yet pinned by no sentence: error paths, empty/null
inputs, ordering, boundary types, and placeholder examples that cannot disambiguate
(a placeholder like `<the digest>` that matches two structurally different candidate
values). Only observable decisions count — unobservable internal choices are
implementation freedom, and flagging them is exactly the false-positive failure mode.

**Convention-break finder (×1).** Find local production rules the plan itself
establishes — a pattern repeated across bullets, stages, or tasks — and any place one
instance silently breaks the pattern. A break is either called out explicitly in the
prose ("unlike the other stages…") or it is a probable drafting error whose two
readings are "the pattern holds" vs "the break is intended". Also flag quiet
deviations from the repo's AGENTS.md conventions.

**Substrate-truth finder (×1) — runs in BOTH tiers, and is not optional.** Enumerate every
sentence asserting external behavior: framework defaults, middleware or hook ordering,
what a library call returns, a tool's pattern syntax and exit codes, path resolution,
which attribute or setting a framework actually reads. For each, **execute a minimal probe
against the installed version** — install it in a scratch directory if absent; read the
source; run the command. Report a claim the probe contradicts as a *falsified claim* with
its transcript. Also probe the plan's own acceptance checks: run each against a
deliberately-wrong implementation and against the artifact the plan itself ships verbatim,
because a check that rejects its own spec's code, or accepts the violation it names, is
the same defect wearing different clothes.

Aim this hardest at four places, all measured to be where it pays: **(a) settings and
constants presented as pinned values** — they interact, so probe the shipped combination
rather than each alone; **(b) any prose added by an amendment**, which is the least-reviewed
text in the plan and reads as authoritative because it reads as a correction; **(c)
fixes**, since a fix asserting "setting this makes the framework do X" is exactly as likely
to be wrong as what it replaced; and **(d) anything the plan says about the test
environment**, where local servers and temp directories differ from production in ways the
plan's own examples quietly assume away.

This finder exists because the divergence-pair contract, by design, cannot see falsehood —
across two measured rounds on one plan, every blocker was an unambiguous sentence about
someone else's system, and each was caught only by running it.

## Phase 2 — Adversarial verify (parallel, one verifier per location group)

Group candidates by (file, section) and launch one verifier per **group**, not per
candidate — verifiers re-read the whole plan, so per-candidate fan-out pays that cost
repeatedly for candidates that sit in the same section (measured: candidates cluster;
grouping roughly halves this phase). Each verifier is instructed to **refute** its
group's findings one by one: search the full plan and design doc for any sentence that
pins one reading.

- **REFUTED** — a sentence pins it; the verifier must QUOTE the pinning sentence.
  Anti-over-confirm: if a quoted sentence genuinely resolves the divergence, refute
  even if the prose could be clearer — "could be clearer" is not a finding.
- **CONFIRMED** — both readings remain defensible, nothing in the plan resolves them,
  and the divergence is observable in outputs or checks.
- **PLAUSIBLE** — not refutable, but the divergence is marginal or arguably
  unobservable.

Anti-over-refute rules: "the obvious reading" is NOT a refutation — the measured base
rate for a careful reader taking the minority reading of a trap sentence is roughly 1
in 5, and that fraction ships as defective implementations and defective tests alike.
A general-engineering default does not refute when the plan's own local pattern
suggests the other reading. A refutation without a quoted sentence is invalid.

**Verifiers must execute, not only read.** Where a candidate rests on external behavior or
on a check's exit code, re-probe it independently rather than trusting the finder's
transcript — finders overstate, and a verifier that only reads prose cannot tell an
overstatement from a defect. Two things this catches, both measured: a finder's premise
that misread the framework (refute it, with the correcting transcript), and a real defect
whose stated consequence was wrong (confirm it, with the consequence fixed). A **falsified
substrate claim** is refuted only by a probe showing the plan is right — never by a
sentence, since no sentence can make a false claim true.

## Phase 3 — Filter hard, then report

- Keep CONFIRMED. Keep PLAUSIBLE only when the divergence would flip an acceptance
  check's outcome. Dedupe by (file, section), keeping the sharpest divergence pair.
  **Report every kept finding in full — there is no cap.** An earlier revision capped the
  report at 10 findings: the cap bound in 100% of the rounds it applied to (26 and 21
  confirmed), so it truncated rather than tracked, and what it compressed is exactly the
  material the amendment author needs — the report file is the handoff artifact for a
  fresh fixing session, and a below-cap row without its probe transcript and rewrite
  starves that session. Quality control is the finding contract plus adversarial
  verification, never a count limit.
- **Open the report with a ranked executive tier** — the operator's scarce resource is
  decision points, not report length. The tier is: the one-sentence headline; then at
  most ~10 one-line entries, most severe first; and an explicit flag on every finding
  that needs an **OPERATOR DECISION** (a product judgment, a stated exception to a
  repo rule, a schema or scope change) rather than an editor. Those flagged findings
  are the only ones the human must read before saying "fix the rest" — measured: a
  21-finding round contained exactly one. Group the full findings beneath the tier by
  kind: operator-decision first, then blockers, then mechanical.
- **Do-not-flag** (false-positive suppression): unobservable implementation freedoms;
  wording or style that changes no observable output; requirements the design doc
  never stated (scope invention); anything outside the artifacts under review; "the
  spec could say more" without a concrete divergence pair.
- Write the report to **`plan-review-report.md` in the repo root** — always write the
  file, even for zero findings (headless callers read files, not stdout). When you hand
  the report to a human, **ship the command that reads it**, not just the path — a
  findings count alone forces them to go hunting for the material you already know the
  location of:
  ```
  sed -n '/^## F1/,/^# Negative space/p' plan-review-report.md   # the findings
  sed -n '/^# Negative space/,$p'        plan-review-report.md   # what was refuted, and why
  ```
  The second command is not optional courtesy. A findings list without the refutations
  reads as "the reviewer found seven problems"; with them it reads as "the reviewer tested
  fifteen and seven survived", which is the only version that supports a decision. Per finding:
  location; both readings as concrete behavior; what was checked and why it does not
  resolve them; and a **proposed rewrite** that (a) pins the intended reading with an
  executable-style example — exact input → exact output, (b) adds a negative example
  naming the rejected reading ("this does NOT mean …"), and (c) if a local pattern was
  broken, an explicit callout of the break. Rewrites are minimal — never restyle
  healthy prose. End the report with the negative space: how many candidates were
  REFUTED or dropped, and by which angle — a zero-findings verdict must show what was
  checked to earn trust.

Findings from the substrate-truth finder carry **the probe transcript in place of the two
readings** — command, trimmed output, version, and the sentence contradicted — plus a
rewrite that states the true behavior and cites the probe. Report the version the probes
ran against: they are true of one version at one moment, and a dependency bump silently
invalidates the report's whole substrate section.

When the reviewed plan has been **amended since its last review**, say so in the report and
report the split — how many findings landed in amendment prose versus original prose. That
ratio is the operator's evidence for whether amendments need their own review gate; it read
as *nearly all* on the one plan where it has been measured.

**Default mode is report-only** — plan prose belongs to its author and ratifier;
propose, don't touch. With **`--fix`**: apply the confirmed rewrites directly to the
spec files (and still write the report). Choosing which reading to pin, in order of
precedence: the plan's own local pattern → the design doc's statement → the majority
translator reading; record in the report which rule chose each pin. Rationale: for
build coherence, any *pinned* reading beats a divergent one — a pin that turns out to
contradict design intent fails visibly and consistently downstream, instead of
shipping as a silent split between implementation and oracle. Do not commit; the
caller owns git.
