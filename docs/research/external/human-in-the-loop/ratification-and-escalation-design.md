# Ratification & escalation — design implications for the harness

The harness-facing half of the human-in-the-loop pass: what the oversight evidence says the
harness must change, keep, and never do. The measured evidence base is the companion,
[oversight-and-vigilance-evidence.md](oversight-and-vigilance-evidence.md).

**Provenance:** 2026-07-10 pass (same six Opus 4.8 clusters; see companion header). Tags per
corpus convention; `⚑` marks against-interest findings.

---

## 1. First, the framing correction

An earlier wrap-up called human ratification "the design's surviving novelty." That was
imprecise, and it matters. The harness has **three human touchpoints at different phases**, and
only one carries a novelty claim:

| # | Phase | Touchpoint | Novel? | Prior art |
|---|---|---|---|---|
| 1 | Design/planning | **Plan ratification** — interview → approve → content-bound stamp gates the build | **No** | `/grill-me`, Kiro, Spec Kit, Claude Code plan mode, Devin (all: generate→approve) |
| 2 | Implementation | **Blocker adjudication** — task parks, decision card, operator decides | **No** | Standard HITL approval |
| 3 | Governance/meta | **Self-modification ratification** — the loop proposes changes to its *own machinery*, a human ratifies; headless runs can't self-modify | **Yes — and narrowly** | None found in the self-improving-harness literature |

Pocock's `/grill-me` is squarely prior art for **#1** (interrogate → confirm shared understanding
→ proceed; the ecosystem study already found the interview mechanics commoditized at 5/11 repos).
What plan-build adds over it is the **machine-checkable determinacy gate that refuses to build** —
a *gate* property, documented in the planning pass, not a human-ratification novelty. The corpus's
actual, re-verified novelty claim (landscape §2; meta-harness §6, across ~40 papers) is narrow:
**human-ratified self-modification** — every self-improving-agent loop in the literature accepts
autonomously; DGM's reward-hack was caught only by *retrospective* review, which is the empirical
argument *for* prospective ratification. And even here the *mechanism* (a human approving a
machine-proposed diff) is ancient (code review, change-advisory boards, IaC review); what is
unpublished is **applying it as the gate on an autonomous self-improvement loop.** So: import the
mature HITL evidence for #1 and #2; the distinctiveness is #3, and it is about the *object*, not
the mechanism.

## 2. The decision card is measured over-reliance bait — redesign it

The sharpest finding of the pass. The harness's card is "situation → advisory LLM triage →
**recommended action** → exactly-one-choice." Three independent literatures converge that this
shape *produces* the rubber-stamping it means to prevent:

- **Command/recommendation displays cause more automation bias than status displays**, and
  **display prominence increases bias** — a prominent recommendation is a commission-error
  generator (Goddard 2012, systematic review; Skitka's 65% commission rate arose exactly when a
  salient directive contradicted valid data).
- **Explanations raise acceptance of the AI whether it is right or wrong** and add nothing over
  plain confidence (Bansal 2021 ⚑). Human+AI on decision tasks nets **g = −0.23**, losing
  precisely when the AI beats the human (Vaccaro 2024 ⚑) — ratification's quadrant.
- This project already *observed* the failure: the planning pass's CSCW study found **3/48
  operators accepted incorrect LLM suggestions and shipped them** — a textbook commission error.

**The redesign, from the one intervention that measurably works** (Buçinca 2021 cognitive
forcing: over-reliance 64%→48%, correct catches 8%→27% ⚑):

1. **Commit-before-reveal.** The card elicits the operator's own read / red-flags on the
   decomposed diff *first*, then reveals the advisory triage and recommendation. A card that leads
   with the recommendation has already lost the intervention.
2. **Never pre-select or highlight the recommended answer.** Default state unselected; show the
   recommendation as *one option in the full choice set with its calibrated confidence*, not as
   "the answer."
3. **Make agreement not-free.** "Make disagreement cheap" (the design's own phrasing)
   operationally means *no one-click accept-the-recommendation* — accepting must cost at least as
   much interaction as rejecting. This is what converts a rubber stamp into an inspection.
4. **Show the strongest counter-argument to its own recommendation** (debate — measurably helps
   in the information-asymmetry regime that self-mod *is*: Kenton 2024). The advisory must argue
   both sides, not advocate one.
5. **Require a short written rationale on high-tier cards.** External accountability framing
   failed on professionals; only *internalized* accountability worked ⚑ (Skitka 2000) — and the
   act of writing *is* the verification behavior complacency suppresses (Bahner 2008).
6. **Prompt for omissions explicitly.** The aid's *silence* is the dangerous channel (CAD
   46%→21%; 55% omission rate). The card must ask "**what did the triage NOT flag that you'd
   expect?**" — otherwise ratification inspects only commission, never omission.

The `exactly-one-choice` forcing itself is *good* (no silent pass-through — keep it). The fix is
to defuse the default, not remove the choice. And accept the UX cost with eyes open: ⚑ the
designs that most reduce over-reliance are the ones operators *like least* — **measure the gate
by errors caught, not by operator satisfaction.** A ratification card that feels frictionless is,
by this evidence, a rubber stamp; and per Green 2022, a gate the human can't really operate
*legitimizes* the change rather than checking it — worse than no gate.

## 3. Escalation: two tiers + a dead-man's-switch

The current escalation surface — a terminal bell plus a polled `state/pause.request` flag — is,
per the evidence, the textbook **bystander/broadcast anti-pattern with no acknowledgement and no
timeout**. The unnoticed-pause incident (P3v2-8, an operator prompt that sat unbounded "by
construction") was therefore *structurally guaranteed*, not bad luck.

The policy the evidence prescribes (Horvitz expected-value + McFarlane coordination + PagerDuty/
incident.io tiers):

- **Immediate, out-of-band, named target** — *only* where cost-of-waiting dominates **and** the
  act is irreversible/blocking: budget-wall pause, self-modification proposal, destructive/security
  gate. (McFarlane: immediate beats negotiated only when timeliness is critical; Horvitz principle
  7: minimize the cost of poor guesses.) *Out-of-band* because the absent operator isn't watching
  the terminal; *named* because a broadcast to a channel triggers the bystander effect ("50 see
  it, 49 assume it's handled").
- **Batch to the ratification boundary** — routine parked ambiguity and most failed-gate
  decisions: park-and-continue, present as a decision card at the next guaranteed-present moment.
  (Negotiated interruption; the ratification boundary is the ideal coarse breakpoint because the
  human is guaranteed present there.)
- **Never interrupt** for anything decidable reversibly under the autonomy level (auto-retry,
  re-route).
- **Acknowledgement tracking + ack-timeout re-trigger.** Add a "seen" state to `pause.request`
  (published ≠ operator-saw); re-fire an acked-but-unactioned card (PagerDuty pattern). MTTA
  rising is the earliest fatigue signal; an escalation-rate outside **10–30%** means the
  policy is mis-tuned.
- **Dead-man's-switch — fail safe, never fail-forward.** On escalation timeout, treat the operator
  as absent and **pause the firing** (stop burning budget/quota on a possibly-wrong branch),
  mirroring GitHub's 30-day auto-fail and Temporal's durable-timer auto-reject. The carve-out
  binds absolutely: a timeout may default to *pause/reject*, **never** to approving a
  self-modification or a destructive action. Latching (IEC 60601-1-8): a high-severity card
  persists until explicitly acknowledged and must never be swept through in a batch pass or
  silently defaulted by park-and-continue.

## 4. Adjudication economics: batch the auto-approved, decompose the human-ratified

Clusters 3 and 6 appeared to conflict — "batch for latency" vs "keep small for review quality" —
but they are **different axes, not a contradiction**, and the resolution is a design rule:

- The human is a slow, expensive, batchable server; each interruption costs the operator a
  context-switch (~23 min to refocus). Batching amortizes that tax; **park-and-continue takes the
  human off the critical path** so wall-clock stops being Σ(human-latency) — the right call.
- But **review quality is inversely coupled to the size of what the human ratifies**: defect-
  finding collapses past ~400 LOC, Google runs one lightweight reviewer *because* changes are
  small, and large diffs get "LGTM" (clusters 5, 6). So:

> **Batch the auto-approved (mechanically-gated, reversible, low-risk) to save latency;
> decompose the human-ratified (intent/scope, self-modifications) to preserve review quality.
> The risk tier decides which axis an item is on.**

Batching hurts on three fronts the design must counter: **stale decisions** (keep the
content-hash recheck — §6); **out-of-the-loop SA loss** (front-load full context on each card to
rebuild situation awareness, and force the commit-before-reveal step — §2); and **volume
desensitization** (cap batch size; never sweep a high-severity card through the same rapid pass —
tier and latch). And the DORA null result ⚑ (external approval boards buy latency and *no* change-
fail-rate reduction) is not a strike against the harness — it is a strike against *board-reviewing
every change*, and it endorses the harness's split: mechanically dispose of the checkable
majority, reserve the human for genuine intent/scope judgment.

## 5. Autonomy levels and the carve-out — a textbook function-allocation design

The corpus's autonomy levels and hard carve-out map cleanly onto Parasuraman-Sheridan-Wickens'
types×levels model (cluster 2), and the mapping is *endorsed* by the evidence:

| Stage | Automate to | Warrant |
|---|---|---|
| Acquisition (gather diffs, logs, gate output) | high (L7–10) | Onnasch: acquisition/analysis automation is low-risk |
| Analysis (triage, advisory) | high but **advisory-only** | LLM-judge unreliability → must not decide |
| **Decision** (merge / accept self-mod / spend) | **low for high-risk (L4–5)**; **medium (L6 veto-window)** for routine merges under "assisted" | Wickens: cap decision automation at medium — the lumberjack effect |
| **Action** (destructive/irreversible/security) | **L1–5, always human** | irreversibility × security = the carve-out |

This *is* "make the decision stage human while automating acquisition/analysis" — the
literature's own prescription. "Assisted = merge queue" ≈ **L6 veto-window**; "stop-the-world" ≈
**L5 explicit approval**.

**When is it safe to reduce a human gate?** The evidence supports a **hybrid, partitioned**
answer:
- **Risk-tiered relaxation** for reversible/verifiable/low-impact classes, earned by evidence
  (sustained low override rate, calibrated confidence validated against held-out outcomes on the
  *accepted* set, advisory↔operator error-correlation below the complementarity threshold), with
  **tripwires that re-tighten on regression.**
- **A hard floor** for destructive/irreversible/security — *not merely conventional.* Relaxation
  presumes a calibrated confidence signal, and Bowman (confident-wrong persists) + Burns (~10%
  judging-PGR) + Fisch (miscalibrated on the accepted set) show that signal is least trustworthy
  exactly where errors are unrecoverable. O0/correctness stays non-tradeable.
- **Learned deferral as a one-way ratchet.** The harness *may* learn to add human touchpoints
  (defer more when self-estimated uncertainty is high) — learned deferral beats fixed thresholds
  *if* it models whether the human adds value on this class (Narasimhan/Madras) — but it must
  **never remove the fixed carve-out**, because self-assessment is demonstrably gameable (DGM).
  Keep the carve-out a hard-coded rule, never a learned-confidence output.

And preserve enough operator visibility (the decision-card log, full context per card) that
re-entry after a park doesn't hit the out-of-the-loop SA decrement.

## 6. Ratification governance — the content-bound stamp is right; three adoptable extras

Mature governance practice (cluster 6) confirms the harness's ratification mechanics and offers
precise upgrades:

- **The content-bound stamp (voids on any post-review edit) IS attestation's "approve exactly
  these bytes."** A signature over a SHA-256 subject (in-toto/SLSA/Sigstore) breaks on any content
  change — the same guarantee, and load-bearing for self-mod ratification: without it, "the thing
  ratified ≠ the thing run" and the evaluation is void. **Adopt three extras:** bind the stamp to
  the **signer's identity** (Sigstore/Fulcio: *who* ratified, non-forgeably), get cryptographic
  **non-repudiation** (not a claimable flag), and make the **decisions log an append-only
  transparency log** (Rekor) — which the ADR "supersede, don't rewrite" rule already points at.
- **Policy-as-code (OPA/Gatekeeper) is "mechanized risk floors + hooks over prose" in the
  governance domain** — machine disposes the checkable uniformly, escalates only genuine
  exceptions to a human. Confirms the harness's preflight/floors-mechanical vs. human-does-intent
  split is the established pattern, not an idiosyncrasy.
- **ITIL risk-tiering** (standard→auto, normal→human-by-risk, emergency→expedited) backs the
  "some classes always need a human, some are mechanically gated" design; the hard carve-out = the
  class that can never be a "standard change." Separation of duties (submitter ≠ approver) is
  already honored (headless runs can't self-modify).

## 7. Design mapping — confirms, refines, exposes

**Confirmed by mature evidence:**
- Not relying on human code review for correctness (§6 of the evidence doc: review catches
  25–65%, collapses past 400 LOC, endorses phantom vulns) — the machine-catches-defects /
  human-governs-intent split is the evidence-endorsed division.
- The autonomy-levels design and the hard carve-out are textbook function allocation, and the
  carve-out is an evidence-backed *floor*, not a convention.
- The content-bound stamp is attestation; policy-as-code and ITIL tiering confirm the mechanical/
  judgment split; DORA endorses "don't board-review every change."
- park-and-continue (keep the human off the critical path) is the right call for vigilance and
  load.

**Refined:**
- The decision card must be rebuilt as a **cognitive-forcing artifact** (commit-before-reveal,
  no pre-selected default, counter-argument, written rationale, omission prompt) — as shaped, it
  is measured over-reliance bait.
- Escalation must become **two tiers + acknowledgement + a fail-safe dead-man's-switch** — the
  bell-and-polled-flag is the bystander anti-pattern.
- Batch the auto-approved, **decompose the human-ratified**; cap batch size; front-load context.
- Right-size to the alarm-fatigue law: **suppress nuisance prompts aggressively** (response tracks
  PPV; never ask what the harness can verify itself), tier by blast radius, latch the irreversible.

**Exposed (honest limits):**
- The **omission channel** is under-instrumented — ratification inspects what triage surfaced, not
  what it missed; the "what wasn't flagged?" prompt is a partial fix, not a solution.
- **Self-assessment is untrustworthy** (METR: 19% slower, felt +20%) — the harness should measure
  human-latency and the ratification override-rate *empirically*, not infer them from operator
  impression.
- The novelty (#3) is real but **unproven at realized scale** — no pilot has exercised a
  self-modification ratification, so the cognitive-forcing card and the "weak supervisor judging a
  strong change" dynamics are untested here.

## 8. Open questions

- **Rebuild the decision card as a cognitive-forcing artifact** and A/B it (commit-before-reveal
  vs recommendation-first) on real adjudications — does it cut the commission-error rate the CSCW
  study measured?
- **Instrument human-latency and override-rate empirically** — the METR result says don't trust
  the operator's sense of either; the run-log can carry both.
- **Escalation-rate as a tuning meter** (target 10–30%): does it detect a mis-tuned autonomy/gate
  balance in a real firing?
- **The self-mod ratification, exercised** — the corpus's one distinctive safeguard has never
  fired; design the first self-modification card as a debate/sandwiching artifact and observe
  whether the weak-supervisor dynamics (Burns ~10% judging-PGR) bite.
- Watch: any measured evidence that a human checkpoint catches agent defects (none exists); the
  graduated-autonomy / earned-trust tripwire literature as it matures.
