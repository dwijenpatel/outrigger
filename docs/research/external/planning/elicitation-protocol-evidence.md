# Elicitation-protocol evidence — who answers which questions, and how few

**Pass of 2026-07-15** (operator-directed): four parallel Opus 4.8 deep-research agents, one per
branch below, each returning primary-sourced, evidence-graded claims. Purpose: ground the
compression of the spec-interview skill after the first two live interviews measured its cost —
**T1 = 14 operator questions, T2 = 10 operator turns**, against a **25-minute, ~$7, fully
unattended execution** (author → implement → gate → land; pilot ledger, 2026-07-14). A post-hoc
autopsy scored **~0 of T2's 7 questions** as genuinely needing the operator: the near-real one
was the *scope* question; the rest were engineering-craft calls whose recommended answer was
accepted verbatim every time, with operator answers shrinking to single letters by question 3.

This document extends [spec-determinacy-and-practice.md](spec-determinacy-and-practice.md)'s
ambiguity-vs-underspecification reframe (most gap classes are omission, not ambiguity) with the
external evidence on *interview protocol*: which questions earn a human, and what happens to the
rest. **No claim here enters the Tier-A distilled set** — the strongest rows are systematic
reviews with shared authors or large single studies; the protocol change they license enters the
design as **Provisional** with named metrics (see §5).

Grades as used by the corpus: **[replicated]** independent parties · **[single-study]** ·
**[survey]** · **[benchmark-only]** (LLM benchmark, un-replicated) · **[case-study]**
self-reported · **[lore]** practitioner belief without empirical support.

---

## 1. Empirical requirements engineering

| Claim | Source | Grade |
|---|---|---|
| Interviews — preferentially **structured** — are among the most effective elicitation techniques; card-sorting/ranking/think-aloud are *less* effective; value lies in structure, not interviewer skill | Davis/Dieste/Hickey/Juristo/Moreno RE'06; Dieste & Juristo IEEE TSE 2011 (564 pubs → 30 studies, qualitative aggregation — meta-analysis impossible) | [replicated]* shared authors across the two reviews |
| Analyst **experience does not reliably improve** elicitation (domain-dependent; professional experience sometimes *negative*) | Davis 2006; analyst-experience quasi-experiment family, arXiv 2408.12538 | [replicated] |
| The dominant real-defect class is **omitted/unidentified requirements and scope/interface boundaries**, not ambiguity — "the most common cause is requirements which have not been identified" | Lutz RE'93 (209 safety-critical errors, Voyager/Galileo) | [single-study, high-influence; aerospace regime] |
| Requirements **ambiguity does not correlate** with project failure / downstream defects (normal inspection resolves it) | Philippo et al.; Sci. Comput. Program. 2020 | [single-study] |
| **The 10–100× late-fix cost multiplier is folklore**: Boehm's own account says ~5:1 for small/informal systems; the sourcing fails inspection (Bossavit); the largest modern test — **171 projects, 2006–2014 — finds no consistent delayed-issue effect** | Boehm & Basili IEEE Computer 2001; Bossavit *Leprechauns* 2015; Menzies/Nichols/Shull/Layman EMSE 2017 (arXiv 1609.04886) | [lore] (multiplier) / [large single-study] (refutation) |
| **Question omission is the #1 least-trainable interviewing mistake** (34 mistakes, 7 themes; no improvement across three interviews on omission/formulation/order) | Bano/Zowghi/Ferrari/Spoletini/Donati, Req. Eng. 2019 (~250 students) | [single-study] |
| **Domain-expert interviewers skip "obvious" questions → tacit assumptions → incomplete requirements** — expertise is double-edged | Hadar/Soffer/Kenzi, Req. Eng. 2013 | [single-study] |
| Asking stakeholders for **solutions instead of requirements** is a documented interviewing mistake | Bano 2019; Donati REFSQ 2017 | [single-study] |
| **Playback/review catches what live questioning misses: 68% of ambiguities found on later review vs 32% live** | Ferrari & Spoletini RE'17/REFSQ'18 (controlled, n=42) | [single-study] |
| A single elicitation pass is lossy — only **30–38%** of final requirements trace to the customer's initial ideas; requirements are co-created | Ferrari et al., Req. Eng. 2022 (arXiv 2208.00825) | [single-study] |
| No RE evidence exists on optimal **question count / fatigue within one session** (saturation research counts interviewees, not questions) | RQ sweep, this pass | honest gap |

**What this branch licenses:** a *designed, structured* question set (not interviewer cleverness);
no mandate for exhaustive up-front interrogation (the cost-curve folklore is refuted — effort
scales to appetite); the question budget belongs on **scope/boundary/use-case coverage and
omission-hunting**, not disambiguation. **What it warns:** "derive instead of ask" is the exact
expert behavior shown to *cause* the dominant defect class — so derivation is safe only under a
reliability condition, the taxonomy must run as a **coverage checklist** (each item asked *or*
its answer's source named — never silently skipped), and a **playback step** (the approval
ledger) is the cheap, evidenced catch for wrong derivations.

## 2. Practice at scale — the PM/tech-lead boundary

| Claim | Source | Grade |
|---|---|---|
| Google design docs: **Goals / Non-Goals** ("things that could reasonably be goals but are explicitly chosen not to be") are the product inputs; **Alternatives Considered** is "one of the most important" sections — it converts silent engineering decisions into auditable ones | Ubl, "Design Docs at Google" (industrialempathy.com) | [primary practice] |
| Amazon: the **PR-FAQ answers customer/problem/success before any technical design**; "if the press release does not excite a customer, the idea is reworked or killed before a single engineer is assigned" | Bryar & Carr, workingbackwards.com | [primary practice] |
| **Reversibility governs who decides and with how much scrutiny**: "Type 2 [two-way door] decisions can and should be made quickly by high judgment individuals or small groups"; applying heavyweight process to reversible decisions is the named org failure | Bezos 2015 shareholder letter (read in full) | [primary practice] |
| **Appetite is a business decision, not an estimate**: "Appetites start with a number and end with a design. Estimates start with a design and end with a number" — fixed time, variable scope | Singer, *Shape Up* ch. 1.2 (basecamp.com/shapeup) | [primary practice] |
| The right spec abstraction is **rough / solved / bounded** — "work that's too fine, too early commits everyone to the wrong details"; no-gos recorded explicitly | *Shape Up* chs. 1.1, 1.5 | [primary practice] |
| RFC cultures split **decided-and-defended** (rationale-and-alternatives) from **unresolved questions** (an explicit register: resolve-before-merge / resolve-in-implementation / out-of-scope) | Rust RFC template; Oxide RFD-1 (options + drawbacks + determination); Uber approver fields (Orosz, second-hand) | [primary practice] |
| **ADR format** = context / decision / consequences ("all consequences, not just the positive ones") / status incl. **superseded** — the per-decision record with a repayment trail | Nygard 2011; Fowler, ArchitectureDecisionRecord | [primary practice] |
| **Deliberate-prudent technical debt** ("we must ship now and deal with the consequences") is legitimate exactly when documented, tracked, and scheduled for payback | Fowler, TechnicalDebtQuadrant | [primary practice] |
| **Caution:** "PM decides what, engineers decide how" as a wall is a *weak-team* pattern; the split is by **risk accountability** (PM: value+viability; lead engineer: feasibility), with scope and acceptance criteria **negotiated at the boundary** | Cagan, SVPG "Four Big Risks" / "Value and Viability" | [primary practice] |

**What this branch supplies:** the composite PM-owned question set (problem/customer, why-now,
success, use-cases, appetite, non-goals, viability constraints, irreversibility tolerance,
cut-priority) — and the derived-decision record's exact shape (alternatives-considered + ADR +
unresolved-questions register + reversibility tags + debt packages). All practitioner-warrant:
authoritative, unreplicated by experiment, labeled as such.

## 3. Structured lightweight elicitation (the BDD tradition)

| Claim | Source | Grade |
|---|---|---|
| **Example Mapping**: story → rules (acceptance criteria) → concrete examples per rule → **red Question cards = "anything nobody in the room can answer"**; 25-minute timebox; readiness heuristics: **many questions = not ready; many rules = too big, slice** | Wynne, Cucumber 2015 | [lore] |
| The **tester perspective** uniquely yields edges, negative paths, boundaries, "what about X?" gaps — the adversarial completeness check the other roles miss | Dinwiddie (Three Amigos); Automation Panda 2017 | [lore] |
| A rule with **no concrete example is untestable**; key examples must *fence boundaries*, not illustrate the happy path — one example makes a rule checkable, not complete | Adzic, *Specification by Example* 2011 (50+ case studies) | [case-study] |
| SBE 10-years survey (n=514): example-using teams report "great" quality 22% vs 8%; **~1/3 never automate**; author's own verdict: "specifications and tests in a single document didn't really work out"; ranking: conversations > capture > automation | Adzic 2020 | [survey, self-selected] |
| **INVEST-Testable** = "I understand what I want well enough that I could write a test for it" (the blind-author bar in one line); INVEST itself never empirically validated | Wake, XP123 2003 | [lore] |
| **Given/When/Then shows no measured comprehension edge over checklist formats** (only faster writing) — scenario ceremony is not evidence-backed | Oliveira et al. 2018 (controlled, students) | [single-study] |
| **Prospective hindsight** ("assume it already failed, write the history") increased *reasons generated* ~30% — **quantity, not verified quality**; Klein's 2007 restatement overstates the 1989 source; strongest replication measured reduced overconfidence, not better decisions | Mitchell/Russo/Pennington JBDM 1989; Klein HBR 2007; Veinott/Klein/Wiggins ISCRAM 2010 (n=178) | [single-study] + measured-critique |
| Verified correction en route: the QUS/AQUSA story-lint tool's real accuracy is **recall 92.1% / precision 77.4%** (Table 4; a search-summary's "97.9/84.8" is wrong); 56% of 1,023 real user stories carry ≥1 detectable structural defect; only 5 of 13 quality criteria are automatable | Lucassen et al., Req. Eng. 2016 | [measured] |

**What this branch supplies:** the escalation criterion in one sentence (a question reaches the
operator iff *nobody in the room can answer it* — and the AI plays the developer and tester
roles internally); the readiness heuristics; the example-per-rule testability bar; and the
evidence-tuned omission-sweep phrasing — graded honestly as a candidate-generator.

## 4. LLM-era clarification research (2023–2026)

| Claim | Source | Grade |
|---|---|---|
| Information-gain ask-policies beat no-ask **while asking 1.3 vs 4.2 turns**; success **peaks at intermediate question budgets and plateaus/declines** beyond | arXiv 2606.03135 (5 backbones) | [benchmark-only] |
| Calibrated ask-vs-refrain wins on underspecified SWE-bench (500): **69.4% vs 61.2%** resolve; the system resolved **76.9% on tasks it correctly chose *not* to ask about**; ~3 questions/queried task | arXiv 2603.26233 | [benchmark-only] |
| **Fragmentary serial questioning and generic querying are the measured failure modes**; the best agent consolidates needs into **one structured turn** (~1.5 turns avg); the ambiguity gap itself is huge (~80pp Pass@1) | ClarEval, arXiv 2603.00187 (2,250 tasks, 11 agents) | [benchmark-only] |
| **Forcing an ask lowers accuracy 1.7–28.6 points**; matching SOTA resolve with **41% fewer questions** is achievable by relevance×answerability targeting | arXiv 2605.28108; CLARITI arXiv 2604.14624 | [benchmark-only] |
| **Asking too late is worse than never**: goal-clarification value collapses after ~10% of execution; 52% of sessions over-asked | arXiv 2605.07937 (6,000+ runs) | [benchmark-only] |
| Over-asking is **misdirected**: 88% of one frontier model's asks were style-preference; 85% of another's were out-of-scope — models over-ask about exactly the craft layer | Ambig-DS, arXiv 2605.09698 | [benchmark-only] |
| AI interviewers ≈ human-parity on explicit requirements and error count (~74% elicited) but **reliably miss implicit/product intent** (best implicit-elicitation ratio 0.32; style ≈ 0); the model that asked the most (~20 turns) extracted the **least** | LLMREI, RE 2025 (arXiv 2507.02564); ReqElicitGym (arXiv 2602.18306) | [single-study] / [benchmark-only] |
| **74% of 448 surveyed developers want approve-before-effect** (AI acts only after explicit approval); only 26% accept act-unless-vetoed | arXiv 2607.00533, IUI 2026 (Microsoft) | [single-study] |
| **Each additional alert cuts acceptance ~30%** (1.26M alerts, 112 clinicians); repeated low-stakes confirmations train assent; forcing engagement with *reasoning* (not just the recommendation) reduces blind acceptance | Ancker et al. BMC MIDM 2017; arXiv 2401.05612 | [single-study] (phenomenon [replicated]) |
| Proactive drafting beats reactive help (+12–18% subtasks, 80–90% preference) **until too frequent** (preference collapses to 47%); review moments land at task boundaries (52% engage) not mid-task (62% dismissed) | CHI 2025 arXiv 2410.04596; IUI 2026 arXiv 2601.10253 | [single-study] |
| **Users mispredict their own interaction preferences** (stated < revealed, p<.05) — don't ask meta-preference questions; high-value follow-ups can *raise* satisfaction (fewer *low-value*, not fewer absolutely) | arXiv 2601.04461; CHI EA 2024 arXiv 2404.17025 | [single-study] |
| **The exact fork — draft-then-approve vs ask-then-draft — has no head-to-head study** in any domain surveyed | RQ6 sweep, this pass | honest gap |

**What this branch supplies:** direct convergent support for *few, early, consolidated,
calibrated* questions; indirect support for cutting exactly the craft-layer asks; and two
design corrections adopted below — **approve-before-effect framing** (never post-hoc veto) and
**rubber-stamp engineering** (short, stakes-flagged, reasoning-forcing ledger, placed at the
ratification boundary).

---

## 5. Synthesis — the protocol this licenses (Provisional)

Four independent literatures converge on one shape: **the human answers the product-boundary
questions; the interviewer derives the rest, records every derivation with its rejected
alternative, and presents the record for approval before anything proceeds.**

1. **PM-boundary taxonomy as a coverage checklist** — problem/why-now, scope + non-goals,
   use-cases/consumers, success, appetite, future-scope (forced concrete), irreversibles + risk
   tier. Each item **asked or its answer's source named** — the omission-guard the RE branch
   demands (Lutz/Bano/Hadar).
2. **Derivation license, three layers** — recorded conventions → ratified precedent → general
   engineering principles. Test: *would two competent tech leads land on the same answer?*
   Underdetermined + product-relevant → question. Underdetermined + craft → decide, flag first.
3. **Reversibility tags** (Bezos) — two-way doors decided and recorded; one-way doors escalate
   regardless of derivability.
4. **Deviation packages** (Fowler) — principle, forcing constraint, interest, repayment task;
   repaid via superseding entry.
5. **Consolidation** — the few real questions in one structured exchange, early, before any
   draft (commit-before-reveal attaches there); **>3 genuine questions = not-ready signal**
   (Example Mapping).
6. **Approval ledger** — before ratification, capped ~5–7 surfaced entries (one-way doors,
   contestable calls, deviations, example-less rules), each *decision · rejected alternative ·
   why · cost of changing*; everything else in the plan file as audit trail. Approve-before-
   effect; silence never proceeds.
7. **Omission sweep** — prospective-hindsight phrasing, interviewer answers first as the
   tester-amigo; graded as a candidate-generator.

**Status and instruments.** The protocol is **Provisional**: its central bet —
derive-and-approve equals interrogation on spec quality — is measured by *no* source (the RQ6
gap; this project may be the first to A/B it). Metrics, all recorded by the spec cascade:
**operator turns per spec** (baselines: T1 = 14, T2 = 10; target ≤ 3–4), **interview escapes
per spec** (post-ratification amendments), **blind-author failures-to-author**, and the
**ledger challenge rate** (an operator who never challenges any surfaced entry across many
specs means the ledger is decoration — redesign trigger). Demotion trigger: escapes or
author-failures rise under the compressed protocol.

## 6. Honest gaps

- Draft-then-approve vs ask-then-draft: **unmeasured anywhere** — our cascade is the instrument.
- Options-with-recommendation vs open questions in AI elicitation: no primary study (only
  form-design defaults, which also carry the anchoring caveat).
- Question ordering: no evidence either way.
- Appetite/irreversibility as question types: practitioner-warrant only.
- Rubber-stamping from repeated *spec*-confirmations specifically: inferred from alert/consent
  fatigue, never measured on spec review — the ledger challenge-rate metric watches it.
- The sharpest 2026 numbers are single, benchmark-only, on brand-new models: directional.

## 7. Source index

Branch 1: Dieste & Juristo IEEE TSE 2011 (ieeexplore.ieee.org/document/5416730); Davis et al.
RE'06; arXiv 2408.12538; Lutz RE'93 (ieeexplore.ieee.org/document/324825); Boehm & Basili 2001
(cs.umd.edu/projects/SoftEng/ESEG/papers/82.78.pdf); Bossavit, *Leprechauns* (leanpub.com);
Menzies et al. arXiv 1609.04886; Bano et al. Req.Eng. 2019 (springer 10.1007/s00766-019-00313-0);
Hadar et al. 2013 (10.1007/s00766-012-0163-2); Ferrari/Spoletini RE'17; arXiv 2208.00825;
Guest/Bunce/Johnson Field Methods 2006; Zaremba & Liaskos RE'21.
Branch 2: industrialempathy.com/posts/design-docs-at-google; workingbackwards.com; Bezos 2015
letter (s2.q4cdn.com …2015-Letter-to-Shareholders.PDF); basecamp.com/shapeup;
github.com/rust-lang/rfcs 0000-template; rfd.shared.oxide.computer/rfd/0001;
blog.pragmaticengineer.com (Orosz); svpg.com/four-big-risks; cognitect.com (Nygard ADR);
martinfowler.com/bliki/{ArchitectureDecisionRecord,TechnicalDebtQuadrant}.
Branch 3: manning.com/books/specification-by-example; gojko.net/2020/03/17/sbe-10-years;
cucumber.io/blog/bdd/example-mapping-introduction; agilealliance.org (Three Amigos, INVEST);
springer 10.1007/s00766-016-0250-x (QUS/AQUSA); xp123.com (Wake); Oliveira 2018 (LNBIP);
Mitchell/Russo/Pennington JBDM 1989; Klein HBR 2007; Veinott ISCRAM 2010.
Branch 4: arXiv 2606.03135, 2603.26233, 2502.04485 (ICLR'25), 2406.12639, 2507.21285,
2603.00187, 2605.28108, 2604.14624, 2605.07937, 2605.09698, 2607.00711, 2212.09885 (ACL'23),
2310.10996 (FSE'24), 2507.02564 (RE'25), 2602.18306, 2507.02858, 2607.00533 (IUI'26),
2602.01481 (IUI'26), 2410.04596 (CHI'25), 2601.10253 (IUI'26), 2601.04461, 2404.17025 (CHI
EA'24); Ancker PMC5387195; arXiv 2401.05612; aclanthology.org/P18-1255 (Rao & Daumé).
