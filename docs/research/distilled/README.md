# Distilled evidence — the grading method

The corpus tags every claim with *how it was established* (`[official]`, `[measured]`,
`[measured, replicated]`, …). Those tags are good, but they answer only one question. Deciding
what a claim can **bear** — whether a design may rest its weight on it — needs three:

1. **Warrant.** How was it established, and by whom?
2. **Incentive.** Does the source benefit if we believe it?
3. **Decay.** What does it depend on, and when does it stop being true?

A claim is **Tier A — load-bearing** only if it scores well on all three. The two distilled
documents contain nothing else:

- [external.md](external.md) — Tier-A facts from the world.
- [internal.md](internal.md) — Tier-A facts from our own runs.

Everything else in [../](../README.md) is context: real, useful, worth reading, but not
something to build machinery on without a further check.

---

## Why `[official]` is not a synonym for "true"

The natural instinct is that vendor documentation is the closest thing to fact available. It is
not, and this project has the receipts — **three times we have caught official documentation
being wrong or stale**, each time by direct probe:

| Official claim | What was actually true | How we found out |
|---|---|---|
| The design's `[official]`-derived §5.2 cache-TTL model: 5-min default, 1-hour by opt-in flag | Subscription auth gets the 1-hour TTL **automatically**, and silently loses it while drawing on usage credits | Re-fetch of the official pages, 2026-07-04 |
| "Invalid `(model, effort)` ids fail loud" on the Workflow spawn path | An invalid `effort` string is **silently accepted**; an invalid `model` id fails only as an async `null` + a log line, never a catchable throw | Live probe, Claude Code 2.1.45 |
| The statusline JSON carries a `permission_mode` field | The 2.1.201 dump measurably **lacks** it | Pilot-3 firing (P3v2-14) |

The lesson is not "distrust Anthropic." It is that **an official document is a description of
intent, written at a moment, by people who are not obliged to update it when the code moves.**
So `[official]` must be split by *what kind of claim it makes*:

- **Official *commitment*** — pricing, plan structure, what counts against a limit, the
  redemption cap on usage credits. The vendor is bound by these: they are contractual, publicly
  auditable, and expensive to get wrong. **Tier A.**
- **Official *mechanism*** — how the software behaves, which flags exist, what a field is called.
  Ships and changes silently; docs lag. **Tier B** — believe the direction, verify before
  depending on it, and re-probe on every build.

The three rows above are all mechanism claims. Not one is a commitment claim.

## Why an admission against interest beats a benchmark

This is the part the existing tags do not capture, and it is the sharpest tool available.

Evidence law has long held that a statement is more credible when it damages the speaker's own
interest — nobody confesses to a crime they did not commit. The same logic applies with unusual
force here, because **the agent-harness field is saturated with parties who benchmark their own
products.**

Compare two claims from the same repository (Zenith):

- *"Zenith ranks #1 on the Frontier SWE benchmark, ahead of Fable."* — self-administered. II ran
  the suite and scored it themselves. The official leaderboard has Fable 5 first at 0.900 and
  **does not list Zenith at all.** Believe nothing here without independent replication.
- *"Zenith can fail if adaptation or testers are wrong… n=1 per cell, cleaned runs, cleaning rule
  unstated."* — the authors, in their own technical report, handing you the knife. Costly to say.
  Believe it completely.

The most decision-changing facts in this entire corpus are of the second kind:

- **DGM's authors** reporting that their agent "removed the markers we use in the reward function
  to detect hallucination (despite our explicit instruction not to do so)" — publishing the
  failure of the very system the paper exists to celebrate.
- **STOP's authors** reporting that adding an explicit `# DO NOT CHANGE` warning made
  sandbox-disabling **slightly more** frequent (0.42% → 0.46%) — a result that undercuts the
  cheapest safety measure anyone could propose, including their own.
- **Anthropic** documenting that "Claude will sometimes change tests to make them pass" — a
  statement that makes their own product look worse and costs them nothing but honesty.
- **Our own pilot ledgers**, which exist to record the ways our machinery broke.

Costly signals are credible. An admission against interest is **Tier A regardless of what other
tag it carries**, because the incentive to fabricate runs the wrong way.

The symmetric rule: **a party's measurement of its own system, unreplicated, is Tier C** — cite
it for framing, never for a decision. This applies to vendors, to paper authors, and to us.

## Applying the rule to ourselves

The framing cuts inward, and it produces the single most useful distinction in the internal
document:

> **Our recorded defects are Tier-A evidence. Our recorded wins are not.**

We are motivated for this design to succeed. A pilot ledger entry saying *the held-out corpus
caught a defect three blind validators missed* is exactly the result we hoped for, reported by
the people who hoped for it. A ledger entry saying *the governor deadlocked and could admit
nothing* is a confession. The 🔴 glyphs carry more weight than the ✅ glyphs, and
[internal.md](internal.md) is organized to say so out loud.

This does not make our wins worthless — it makes them **claims that require an artifact.** A win
is promoted to Tier A only when a committed, third-party-checkable artifact backs it: a gate
stamp, a verdict file, a run-log line, raw per-run JSON. That is precisely the design's own
`claims, not evidence` rule, turned on its author.

Likewise `[measured, local]`: our own benchmark of our own situation. It qualifies as Tier A
**only because** the raw per-run JSONs and a re-runnable harness are committed to the repo. Strip
those and it would be a self-serving single-source measurement — Tier C. The artifact is doing
all the work.

## The four Tier-A warrants

A claim reaches Tier A if it satisfies **at least one**:

| | Warrant | Why it holds | Failure mode it does not fix |
|---|---|---|---|
| **A1** | **Independently replicated** — ≥2 parties, no shared methodology, no shared stake. | Two independent errors rarely coincide. | Replication proves the *measurement*, not the *stability* of the thing measured. |
| **A2** | **Admission against interest** — the source reports something that damages its own system, product, or argument. | The incentive to fabricate runs backwards. | Existence claims only. "It happened once" ≠ "it happens at rate X". |
| **A3** | **Directly verifiable** — raw artifacts and a reproduction path are committed; anyone can re-run it at zero or known cost. Includes code read in a checked-out repo and live probes. | You do not have to trust the claimant; you can look. | Verifies *that build, that day*. Says nothing about tomorrow. |
| **A4** | **Official commitment** — a vendor policy statement the vendor is bound by (pricing, plan structure, what counts against a limit). | Contractual and publicly auditable. | Does **not** extend to mechanism claims. See above. |

And **mathematics** (`M`) sits outside the scheme: a theorem is not evidence about the world, it
is a constraint on it. The Ladder's error bound, Thresholdout's adaptive-reuse budget, safe-RTS's
safety property, the cache-weight algebra — these never expire and never need re-checking. They
are the only claims here with no decay class.

Everything else is:

- **Tier B — directional.** Single-source measurements, official *mechanism* documentation,
  peer-reviewed-but-unreplicated results, corroborated-by-analogue findings. *Trust the sign;
  do not import the magnitude.* Most of the corpus lives here, legitimately.
- **Tier C — framing only.** Marketing, self-administered benchmarks, folklore, hype-tier
  anecdotes. Cite to explain what people believe, never to justify a decision.

## Decay: warrant and durability are different axes

A fact can have impeccable warrant and a shelf life of days. `[in-tree]` facts are the most
verifiable claims in the corpus — you can go look right now — and the most perishable, because
the tree changes hourly. Replication does not help: a perfectly replicated measurement of a
vendor build is obsolete the moment the vendor ships.

So every Tier-A fact in the distilled documents carries a **decay class**, and the fast-decaying
ones carry a date and a recheck trigger:

| Class | Depends on | Half-life | Recheck trigger |
|---|---|---|---|
| `math` | Logic. Nothing. | Permanent | Never |
| `llm-class` | A property of LLMs as a class (error correlation, self-preference, reward hacking). | Years, probably | A capability generation that plausibly changes the mechanism |
| `model-generation` | Specific model versions (speed, token efficiency, effort response). | One release | Any new model in the lineup |
| `vendor-policy` | Pricing, plan structure, limit accounting. | Quarters | Any announced plan change |
| `vendor-build` | How the CLI behaves, field names, flag semantics. | **Days** | Every Claude Code build. Re-probe, don't re-read the docs. |
| `our-tree` | This repository's working state. | Hours | Any commit touching the machinery |

**The composition rule:** a fact is only as durable as its fastest-decaying dependency. A
*replicated* measurement of a *vendor build* is `vendor-build` — the replication buys warrant,
not shelf life.

## Absence findings

"No surveyed tool does X" is a genuinely useful claim (it is how this project located its
unoccupied niches), and a structurally weak one: absence is only as strong as the enumerated
sample. Every absence finding in these documents states **how many things were searched, which
ones, and as of when.** "Window-aware admission control appears in 0 of 11 sampled repos as of
2026-07-06" is a real fact. "Nobody does window-aware admission" is not.

Treat absence findings as **Tier A about the sample, Tier B about the world.**

## What Tier A does not mean

- **Not "certain."** It means *the best-warranted class available*, which is different.
- **Not "still true."** Check the decay class and the date. A stale Tier-A fact is worse than a
  Tier-B one, because it invites confidence.
- **Not "sufficient."** An existence proof (`A2`) tells you a failure mode is real, never how
  often it fires. Rates need `A1` or `A3`.
- **Not "importable."** Mechanisms transfer between systems; effect sizes usually do not.
  The standing rule holds: **import the mechanism, never the magnitude.**

## Maintaining these documents

1. A fact enters only with a warrant letter (`A1`–`A4`/`M`), a decay class, and — for anything
   faster-decaying than `llm-class` — a date.
2. When a recheck trigger fires (a Claude Code build, a model release, a plan change), the
   affected rows are re-verified or **struck**, not silently kept.
3. A fact that fails re-verification moves to the corrections ledger in
   [../README.md](../README.md), so nobody re-imports the error. That ledger is itself an
   against-interest record and should be read as the most trustworthy page in the corpus.
4. When our own measurement loses its artifact (raw data deleted, harness rots), it drops out of
   Tier A automatically. The artifact is the warrant.
