# Human oversight & vigilance — the evidence

What the mature literatures (safety-critical HCI, human factors, AI alignment, empirical
software engineering) establish about human oversight of automation: when it degrades, why, and
what keeps it meaningful. The harness-facing synthesis — decision-card redesign, escalation
policy, autonomy mapping — is the companion,
[ratification-and-escalation-design.md](ratification-and-escalation-design.md).

**Provenance:** 2026-07-10 deep-research pass. Six Opus 4.8 clusters, deliberately weighted
toward mature adjacent fields rather than the thin LLM-agent literature: automation
bias/complacency/alarm fatigue, mixed-initiative/levels-of-automation/interruption, scalable
oversight/deferral/complementarity, code-review HITL, adjudication economics, and ratification
governance. Extends the one worked example in
[../unattended-operation/unattended-operation-prior-art.md](../unattended-operation/unattended-operation-prior-art.md)
§6 and the approval-fatigue note in
[../isolation/isolation-and-sandboxing.md](../isolation/isolation-and-sandboxing.md). Evidence
tiers noted inline; `⚑` marks an against-interest finding (author's incentive ran opposite).
**This is not a novelty pass** — human oversight of automation is a decades-old field; the value
is the *measured* backbone for doing it well and knowing when it's safe to reduce.

---

## 1. Automation bias, complacency, and the omission channel

The foundational result: **a human watching a highly-but-imperfectly-reliable automation is a
worse detector than a human with no automation at all.** `[peer-reviewed]`

- **Commission errors** — following an automated directive *even when it contradicts other
  valid, available information*: mean **65%** of subjects, with **>20% erring on all six**
  contra-indicated events and **<1%** erring on none (Skitka, Mosier & Burdick 1999, IJHCS).
- **Omission errors** — failing to act on a problem the automation *didn't flag*: **~55%**. The
  aid's *silence* suppresses detection: breast-cancer CAD found in only **21%** of cases what
  unaided readers found in **46%**, when the CAD failed to mark it (Alberdi/Povyakalo et al.).
- **Meta-analytic weight:** decision-support systems giving bad advice raise the wrong-decision
  rate **RR 1.26 (95% CI 1.11–1.44)**; a CDSS that lifted correct answers 29%→50% still *flipped
  7% of already-correct answers to wrong* (Goddard et al. 2012, JAMIA, systematic review).
  Automation bias sets in above **~70% reliability**.

**Complacency is the substrate, and its driver is counter-intuitive.** When automation
reliability is held *constant*, failure-detection drops sharply versus *variable* reliability —
**consistency, not reliability level, breeds complacency** (Parasuraman, Molloy & Singh 1993).
It is an attention-allocation phenomenon under multi-task load, present in **both novices and
experts**, and **not overcome by practice** ⚑ (Parasuraman & Manzey 2010, Human Factors, review).
It is measured as *insufficient verification/cross-checking* — the operator samples too little
of the available confirming evidence (Bahner et al. 2008). Training on rare failures reduces
commission but ⚑ **not omission** (Goddard 2012).

**The ironies that make oversight fail exactly when it matters** (Bainbridge 1983, "Ironies of
Automation"; Endsley & Kiris 1995): the human is left the un-automatable *residue*; is a *poor
sustained monitor* of rare events; suffers *skill decay* through disuse; and must take over *at
the hardest moment* (the intervention paradox). Full automation degrades **situation awareness**
more than intermediate levels via a shift from active to passive processing — so the more the
human is a passive approver, the worse they adjudicate when a real failure finally arrives.

## 2. Alarm fatigue / cry-wolf — why false positives destroy a gate

The mechanism behind approval fatigue as an attack surface, with hard numbers. `[review/safety-board]`

- **Base rates:** 72–99% of clinical alarms are false/non-actionable (Cvach 2012); one ICU
  dataset logged **2,558,760 alarms in 461 patients over 31 days, 88.8% of arrhythmia alarms
  false positive** (Drew et al. 2014, PLoS ONE). The regulatory weight: **566 FDA-reported
  alarm-related deaths** (2005–08), a Joint Commission National Patient Safety Goal, ECRI's #1
  health-technology hazard (2014). Outside medicine: the 2009 Washington Metro collision (9
  dead) followed a fault generating **~8,000 alerts/week**, which the NTSB concluded "would have
  thoroughly desensitized" dispatchers.
- **The law:** operator response tracks **positive predictive value** — P(true | alarm) — not
  raw alarm count (Getty et al. 1995). False alarms destroy a warning's credibility "practically
  inevitabl[y]," and the more alarming the false positive, the greater the credibility loss
  (Breznitz 1984). The **base-rate trap**: a rare target guarantees low PPV even with a good
  detector, driving disuse (Parasuraman & Riley 1997).
- **The measured mitigations** (this is what the harness needs): **nuisance-rate reduction is the
  primary lever** — cutting non-actionable alarms restored response, with QI studies showing
  **43–88.5%** volume reductions (Graham & Cvach 2010; Sendelbach et al.). **Severity tiering**
  (IEC 60601-1-8: high/medium/low, distinct auditory signatures, explicit escalation, and
  **latching** so a transient *true* event persists until acknowledged). Prioritized ordering so
  the dangerous signal is met first, not buried.

## 3. Levels of automation & function allocation

The formal vocabulary for "how much to automate which stage," all `[peer-reviewed/canonical]`.

- **Sheridan & Verplank's 10 levels** — from L1 (human does all) through **L5 (computer executes
  if the human approves)**, **L6 (executes unless the human vetoes in a window)**, to L10
  (autonomous, ignores the human). L5 = an approval gate; L6 = a veto-window (the merge-queue
  shape); L7–10 = human-on/out-of-loop.
- **Parasuraman, Sheridan & Wickens' four-stage model** (2000): automation applies independently
  to information **acquisition**, information **analysis**, **decision/action selection**, and
  **action implementation** — each at any of the 10 levels.
- **The design rule, meta-analytically grounded:** Onnasch et al. 2014 (18 experiments) —
  the **"lumberjack effect"**: rising degree-of-automation raises routine performance and lowers
  workload but **sharply degrades failure-performance and situation awareness past a threshold**.
  Wickens 2018: **automate acquisition/analysis high, but cap *decision* and *action* at medium —
  keep the human in the decision loop.** Fitts-list static allocation is superseded (Dekker &
  Woods): automation *transforms* the human's task, it doesn't substitute a slice of it.

## 4. Mixed-initiative & the science of interruption

When to interrupt, and at what cost. `[peer-reviewed/controlled]`

- **Horvitz's expected-value rule** (CHI 1999): act autonomously only when EU(act) exceeds both
  EU(inaction) and EU(ask); *asking has a cost, guessing wrong has a cost scaled by
  reversibility, and timing is a first-class variable* (identical action, different value by the
  operator's attentional state). Minimize the cost of poor guesses; scope precision to
  uncertainty.
- **Coordination method** (McFarlane, controlled experiment): **negotiated interruption is best
  overall** (efficiency, accuracy, lowest disruption); ⚑ **immediate wins only when timeliness is
  critical** — so there is *no* absolute "boundaries only" rule.
- **The measured cost of ill-timed interruption** (Bailey & Konstan 2006, N=50): interrupting
  mid-task versus at a boundary costs **+3–27% time, ~2× errors, ~2× anxiety** with workload held
  constant — only the *timing* changed. **Breakpoints** (Iqbal & Bailey): deliver at coarse
  perceptual boundaries (lowest resumption lag); defer to the coarsest boundary the deadline
  allows.
- **Adjustable autonomy as decision theory** (Scerri, Pynadath & Tambe 2002): before ceding a
  decision, weigh cost-of-waiting + miscoordination against cost-of-erroneous-autonomous-action;
  **rigid one-shot transfers cause coordination failures** — a conditional strategy (act / defer /
  buy time) dominates, and "is the human even available?" is part of the calculus.

## 5. Scalable oversight, weak-to-strong, and human-AI complementarity

The deepest layer, for overseeing changes the human cannot directly evaluate — i.e.
self-modification of machinery.

- **Scalable oversight works in the information-asymmetry regime, and there specifically.** The
  one measured paradigm, sandwiching (Bowman et al. 2022, Anthropic `[preprint]` ⚑): a
  non-expert + unreliable model assistant beat *both* baselines (MMLU 57.2%→75.4%, QuALITY
  48.6%→76.8%) — but human+model teams still "give highly confident judgments that turn out to
  be wrong." Debate (Kenton et al. 2024, ICML, ~5M generations): debate beats direct QA **only
  under information asymmetry** (the judge can't see the source); on pure reasoning, **small-to-no
  benefit**. Ratifying a machinery change the human can't fully trace *is* the information-
  asymmetry case — the regime where assistance measurably helps.
- **But the human is a weak supervisor, and the judging analogue is where weak supervision
  collapses.** Weak-to-strong generalization (Burns et al. 2023, OpenAI `[ICML]` ⚑): a weak
  supervisor recovers 20–80% of a strong model's capability gap on knowledge tasks — but
  **reward modeling, the analogue of *judging* an action, generalizes worst (~10%)**, with strong
  students overfitting and imitating the weak supervisor's errors. Do not assume the weak human
  recovers the strong model's judgment.
- **Human+AI often loses to the better of the two — and ratification is the losing quadrant.**
  Vaccaro, Almaatouq & Malone 2024 (Nature Human Behaviour, 106 studies, pre-registered) ⚑:
  human+AI versus the better of human-or-AI-alone is **significantly worse on average (Hedges'
  g = −0.23)**; **decision tasks lose, content-creation gains**, and combos **lose precisely when
  the AI alone beats the human**. Ratification is a decision task with a strong AI.
- **Explanations induce over-reliance; forcing analytic work reduces it — at a UX cost.** Bansal
  et al. 2021 (CHI) ⚑: AI *explanations did not beat plain confidence*, and **raised acceptance
  of the AI whether it was right or wrong**. Buçinca et al. 2021 (CSCW) ⚑: **cognitive forcing**
  (make the human commit before the AI reveals its recommendation) cut over-reliance on
  AI-wrong cases **64%→48%** and quadrupled correct catches (8%→27%) — but ⚑ **the
  best-performing designs were the ones operators trusted and liked *least*.** Goddard's
  mitigators concur: confidence display ↓ bias; **display prominence ↑ bias**; **status/information
  displays cause less bias than command/recommendation displays**.
- **When it's safe to reduce the gate.** Green 2022 (41 oversight policies): a human gate the
  operator can't actually perform *legitimizes* the faulty system rather than checking it —
  **worse than no gate**. Graduated-autonomy frameworks converge: autonomy is earned per-skill by
  evidence, keyed to **risk × reversibility**, with tripwires that re-tighten on regression — but
  **irreversible/broad-impact actions stay human-in-the-loop regardless of demonstrated
  reliability**, because relaxation presumes a calibrated confidence signal, and Bowman
  (confident-wrong persists) + Burns (~10% judging-PGR) + Fisch 2022 (selective classifiers are
  *miscalibrated on the accepted set*) jointly show that signal is *least* trustworthy exactly
  where errors are unrecoverable.
- **Learned deferral beats fixed thresholds — but must model *who* it defers to.** Naive
  confidence-thresholding "strongly underperforms" because it ignores the expert's error
  (Narasimhan et al. 2022); defer where the *human is better*, not merely where the model is
  unsure (Madras et al. 2018); calibrate on the *accepted* set (Fisch); and models only
  "*mostly* know what they know" (Kadavath et al. 2022 — degrades off-format).

## 6. Does human code review catch AI bugs? — the software-specific ground truth

The coding-specific evidence beneath the abstract theory, and it is one-directional.
`[peer-reviewed/measured]`

- **Human diff-review is a leaky net even at its best:** formal inspection catches ~55–65% of
  defects, individual reviewers 25–50% (Capers Jones; Fagan), and effectiveness **collapses past
  ~400 changed lines** (SmartBear/Cisco) — the regime agents live in (600+ line diffs).
- **On AI PRs specifically** (arXiv 2605.02273): **61% received no recorded review**, 84% got no
  human review or agent-only review; human comments skew to *steering* the agent, not evaluating
  it.
- **Adversarial review still confidently endorses phantom bugs:** Refute-or-Promote (arXiv
  2604.19049) — five agents *unanimously* endorsed a **nonexistent** Bleichenbacher vulnerability;
  "adversarial review does not prevent confident false positives." This independently replicates
  this corpus's own ten-reviewer phantom-vuln finding: **unanimity is not evidence of correctness
  when reviewers pattern-match instead of execute.**
- **The verification tax is real and self-assessment is miscalibrated:** METR RCT (arXiv
  2507.09089) — 16 experienced devs were **19% slower with AI while forecasting −24% and still
  believing +20% afterward**; reviewing/cleaning AI output cost ~9% of their time. Self-assessment
  of AI-assisted work runs *toward over-crediting the AI*.
- **The shipped human-on-the-loop model is asserted, not validated:** Devin/Copilot gate intent
  (plan) and integration (PR), but **no vendor publishes measured evidence the checkpoint catches
  defects** — its honest value is scope/intent governance, not defect-catching.

**The one-directional conclusion:** every strand says human code review is an unreliable
*correctness* authority. A harness that made it the correctness gate would build on the weakest
link in the measured record — which is precisely why the harness routes correctness to blind
held-out tests + a merge gate (execution, not opinion) and reserves the human for scope/intent
and self-modification. The evidence doesn't merely permit that division; it argues against the
alternative. The design implications are the companion document.
