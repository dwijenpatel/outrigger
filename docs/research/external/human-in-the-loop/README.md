# Human-in-the-loop — ratification, adjudication, and oversight

**Scope.** Where humans sit in an autonomous harness: ratification gates and decision-card UX,
blocker adjudication, notification/latency economics, approval fatigue, trust calibration of
advisory layers, and autonomy-level policy.

**Coverage: ○ thin — no dedicated document.** The corpus's strongest human-in-the-loop
material is embedded in other documents; the *design* leans heavily on human ratification
(it is the surviving novelty vs the self-improvement literature), which makes the thinness
here disproportionate to the concept's load.

## What exists today (scattered)

- [../unattended-operation/unattended-operation-prior-art.md](../unattended-operation/unattended-operation-prior-art.md)
  §6 — the one worked ratification-card UX (IssueOps cards: situation → advisory triage →
  exactly-one-choice; stale-decision guards; authority separation; fail-open advisory vs
  fail-closed enforcement).
- [../isolation/isolation-and-sandboxing.md](../isolation/isolation-and-sandboxing.md) —
  **approval fatigue** as a documented, socially-engineerable failure of human gates.
- [../self-improvement/meta-harness-and-self-improving-harnesses.md](../self-improvement/meta-harness-and-self-improving-harnesses.md)
  §4/§6 — why prospective human ratification is the field's missing safeguard (DGM caught
  only by retrospective lineage review); Weng's "humans move up the stack."
- Design §6.3/§7; internal: card-first discipline (I21), pause-channel starvation (P3v2-8),
  operator notification (`notify_operator.sh`), permission-mode is operator-only (I30).

## Open questions — next research targets

- **Adjudication latency economics.** O2 includes human latency; what does the
  park-and-continue pattern actually save, and where does batching decisions beat streaming
  them?
- **Decision-card design.** What card anatomy minimizes wrong approvals *and* round-trips?
  (One worked example exists; no comparisons.)
- **Approval fatigue engineering.** Fatigue is documented as an attack surface — what rate,
  batching, or risk-weighting keeps the human gate meaningful?
- **Trust calibration of advisory triage.** When the card's LLM triage is wrong, does the
  human catch it? (LLM-judge unreliability meets human rubber-stamping.)
- **Escalation policy.** What classes of event justify interrupting a human, on what channel,
  with what urgency? (We have one bell script and one starved pause request.)
- **The HCI/CSCW literature.** Mixed-initiative systems, alarm fatigue in ops, aviation
  automation policy — mature fields the corpus has not touched.
