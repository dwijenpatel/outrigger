# Human-in-the-loop — ratification, adjudication, and oversight

**Scope.** Where humans sit in an autonomous harness: ratification gates and decision-card UX,
blocker adjudication, notification/latency economics, approval fatigue, trust calibration of
advisory layers, autonomy-level policy, and when it is *safe* to reduce a human gate.

**Coverage: ● rich** (2026-07-10 deep-research pass: six Opus 4.8 clusters weighted toward the
mature adjacent fields — safety-critical HCI, human factors, AI alignment, empirical software
engineering — that carry the measured evidence the LLM-agent literature lacks).

**Not a novelty pass.** Human oversight of automation is a decades-old field, and the harness's
plan-ratification (#1) and blocker-adjudication (#2) touchpoints are commoditized. Only
**self-modification ratification** (#3 — the loop needing human approval to change its *own
machinery*) is distinctive, and its novelty is about the *object*, not the mechanism (a human
approving a machine-proposed diff is ancient). The value of this pass is the *measured* backbone
for doing human-in-the-loop *well*, and knowing when to reduce it —
[ratification-and-escalation-design.md §1](ratification-and-escalation-design.md) states the
three-touchpoint framing precisely.

## Holdings

- [oversight-and-vigilance-evidence.md](oversight-and-vigilance-evidence.md) — the measured
  evidence: automation bias (65% commission, 55% omission; automation makes monitors *worse*),
  complacency (driven by *consistency*, not reliability; unfixed by practice), alarm fatigue
  (72–99% false; response tracks PPV, not count; the nuisance-reduction + severity-tiering +
  latching mitigations), the ironies of automation and out-of-the-loop SA loss, levels-of-
  automation function allocation (cap decision/action at *medium* — the lumberjack effect),
  mixed-initiative and interruption cost, scalable oversight / weak-to-strong / human-AI
  complementarity (g = −0.23; explanations induce over-reliance; cognitive forcing is the one
  intervention that works, at a UX cost), and the software-specific ground truth that human code
  review is an unreliable correctness authority.
- [ratification-and-escalation-design.md](ratification-and-escalation-design.md) — the design
  synthesis: the framing correction (three touchpoints; `/grill-me` is prior art for #1), **the
  decision card is measured over-reliance bait and how to rebuild it** (commit-before-reveal, no
  pre-selected default, counter-argument, written rationale, omission prompt), the two-tier
  escalation policy + fail-safe dead-man's-switch, the batch-the-auto-approved/decompose-the-
  human-ratified rule, the autonomy-levels function-allocation mapping and when it's safe to
  reduce a gate (hybrid: risk-tiered relaxation + a hard, evidence-backed floor; learned deferral
  as a one-way ratchet), and the content-bound-stamp-is-attestation governance mapping.

## Related material elsewhere

- [../unattended-operation/unattended-operation-prior-art.md](../unattended-operation/unattended-operation-prior-art.md)
  §6 — the one worked ratification-card UX (IssueOps cards) these documents extend with SLA/
  timeout, escalation tiers, and acknowledgement.
- [../isolation/isolation-and-sandboxing.md](../isolation/isolation-and-sandboxing.md) — approval
  fatigue as a socially-engineerable attack surface (now grounded in the alarm-fatigue literature).
- [../self-improvement/meta-harness-and-self-improving-harnesses.md](../self-improvement/meta-harness-and-self-improving-harnesses.md)
  §6 — human-ratified self-modification as the field's missing safeguard (DGM caught only by
  retrospective review); the scalable-oversight cluster resolves *how* to make it real.
- [../planning/spec-determinacy-and-practice.md](../planning/spec-determinacy-and-practice.md) —
  plan ratification (#1) and the CSCW automation-bias finding (3/48 shipped incorrect suggestions).
- [../landscape/ecosystem-mining/spec-elicitation-and-planning.md](../landscape/ecosystem-mining/spec-elicitation-and-planning.md)
  — `/grill-me` and the commoditized interview mechanics (prior art for touchpoint #1).

## Open questions

Full list in [ratification-and-escalation-design.md §8](ratification-and-escalation-design.md);
the highest-leverage:

- **Rebuild the decision card as a cognitive-forcing artifact** and A/B it against the current
  recommendation-first shape — does it cut the measured commission-error rate?
- **Instrument human-latency and ratification override-rate empirically** — METR says don't trust
  the operator's sense of either.
- **Exercise the self-modification ratification** (never fired at realized scale) as a
  debate/sandwiching card, and observe whether the weak-supervisor-judging-a-strong-change
  dynamics bite.
- **Escalation-rate as a tuning meter** (target 10–30%) — does it detect a mis-tuned autonomy/gate
  balance in a real firing?
