# Token economics & scheduling — routing, effort, forecasting, budget governance

Evidence behind the design's O1 machinery
([../design/token-time-optimized-harness.md](../../design/token-time-optimized-harness.md)):
model/effort tier routing (§5.3), the budget governor and window-aware admission (§5.1, §6.2),
and the wall-clock/paid-parallelism tradeoffs (§6). Claude Code / Max-plan *mechanics* the
governor is built on are a separate document
([claude-code-and-max-plan-facts.md](claude-code-and-max-plan-facts.md)).

**Provenance:** deep-research workflow, 2026-07-04 — 5 search angles → 25 sources → 123 claims
→ top 25 through 3-vote adversarial verification (24 confirmed, 1 refuted). Findings below
carry their vote where verified; single-extraction claims from live primary sources are tagged.
Confidence: `[measured]` `[folklore]` `[E]`/`[I]`. Consolidated corrections and open items in
[README.md](../README.md).

> **Operational aside worth recording.** This research run itself hit the account's 5-hour
> session limit mid-verification, losing all 75 in-flight verifier votes — a live instance of
> the design's §9 "budget wall mid-panel" failure mode — and was recovered after the window
> reset by replaying the workflow journal (completed agents cached, only failed ones re-run):
> the disk-is-memory resume pattern (design §3.4) working exactly as prescribed.

---

## 1. Model routing & cascades — the §5.3 tier ladder now has literature (verified 3-0)

- **The "~75% cost cut" folklore is real but best-case and task-dependent.** Optimal
  two-model cascades at 90%-of-ceiling quality cut cost 73.7% (MMLU), 74.5% (TriviaQA),
  79.5% (MATH) — but only **56.1% on LiveCodeBench and 15.1% on SimpleQA** `[measured; arXiv
  2605.06350 "Is Escalation Worth It?", Table 2 verified verbatim]`. RouteLLM (ICLR 2025)
  achieves ~75% savings at 95% GPT-4 quality only in-distribution on MT-Bench; on MMLU/GSM8K
  the best routers save ~30% while giving up 8–13 quality points `[measured; arXiv 2406.18665]`.
  **Coding/correctness-graded workloads — the harness's actual domain under O0 — sit at the low
  end of the band; do not extrapolate the headline number to spec-to-code work.**
- **Start-cheap-escalate-on-proof is established prior art:** FrugalGPT (TMLR 2024) matched
  GPT-4 at up to 98% lower cost and at equal cost beat it by 4pts (arXiv 2305.05176, abstract
  verified); R2-Reasoner 84.46% savings via per-subtask routing (arXiv 2506.05901, WWW 2026);
  MixLLM 97.25% of GPT-4 quality at 24.18% of cost (NAACL 2025). All measured on
  query/reasoning benchmarks, **not long-horizon agentic coding**. A June-2026 replication
  (arXiv 2606.13241) found a FrugalGPT-style cascade *underperforming* always-best in a
  different regime — Pareto improvement is regime-dependent, not automatic. `[measured]`
- **Pre-generation routing beats pure escalate-on-failure on 4 of 5 benchmarks** — chiefly
  because a cascade pays the cheap model's full failed attempt (plus wall-clock) before any
  escalation decision `[measured; 2605.06350 abstract verbatim]`. Where pre-generation
  features were uninformative (TriviaQA, embedding AUROC ≈ 0.49) cascading stayed competitive.
  This supports the design's own >40%-failure break-even trip-wire (§5.3 guardrail 3) and its
  flagged duration-bucket predictor — **conditional on the predictor's features actually
  predicting**, which §3 says they mostly don't.
- **Router misclassification can erase all savings:** routers trained on mismatched
  distributions scored at or below the random-routing baseline (a BERT router at −21.8% APGR
  vs random on out-of-distribution tasks) `[measured; RouteLLM]`. Routing on an unfamiliar task
  distribution can be worse than a coin flip.
- **Escalation-signal taxonomy `[I]`:** FrugalGPT/RouteLLM escalate on a *learned scorer*; the
  design escalates on a *verified durable FAIL* at the gate. The design's signal is
  higher-precision but pays a full failed attempt per misroute — which is exactly why the
  break-even controller and (validated) upfront routing matter.
- **Many-rung ladders — no change forced.** The claim that >2-model chains add no meaningful
  benefit over a two-model envelope was **refuted 1-2** by the verification panel; evidence is
  weak in both directions. Do **not** collapse the tier ladder to two rungs on this basis.

## 2. Effort / thinking-budget control (verified 3-0)

- **Effort routing is literature-backed, not just an Anthropic knob:** ARES (arXiv 2603.07915,
  per-step effort router) cuts reasoning tokens **up to 52.7%** (SFT-only 35–45%) at 0–2pt
  success loss on TAU-Bench/BrowseComp-Plus/WebArena; AdaptThink (EMNLP 2025) −53% length at
  +2.4% accuracy; within-model compute control spans ~22–92% savings (Arora & Zanette, arXiv
  2502.04463; Chain-of-Draft, arXiv 2502.18600) `[measured]`. These are reasoning-token /
  within-model figures, not total-cost or model-routing figures, and none are on Claude coding
  agents — transfer is analogical.
- **Both uniform defaults measurably fail:** always-low drops agent success ~20pts (TAU-Bench
  54.8→35.0; WebArena −34.7pts); always-high overthinks trivial inputs (~1,953% extra tokens on
  "2+3=?", arXiv 2412.21187) `[measured]`. Effort must be *routed* with the escalation net
  intact — cheap-by-default is only safe with a difficulty signal or a verifier behind it. This
  confirms the §5.3 guardrails (protected profiles never start cheap; break-even escalation).
- **Thinking budgets are soft targets, not caps:** measured on Claude 3.7, observed thinking
  scales with the allocated budget but with a long overshoot tail; Anthropic docs call
  `budget_tokens` "a target rather than a strict limit" `[official + measured; arXiv 2507.02076
  Fig. 2]`. Governor forecasts need overshoot variance per (tier, effort) cell; degrade/pause
  thresholds must assume **soft** per-task ceilings.
- **Effort-vs-tier cache asymmetry (2-1 vote, medium confidence):** ARES argues intra-model
  effort switching preserves the KV cache while cross-model switching forces re-encoding. **In
  Claude Code specifically this is moot *mid-session* — model and effort are both part of the
  cache key** (see [claude-code-and-max-plan-facts.md §2](claude-code-and-max-plan-facts.md)),
  so any mid-session escalation of either busts the cache. The asymmetry survives only in the
  design's fresh-spawn-per-escalation path, where it is automatic. `[I]` Practical rule: prefer
  effort bumps before tier bumps, and always escalate at a worker respawn boundary.

## 2b. Local supersessions — the 2026 adaptive-thinking lineup (added 2026-07-05)

The [local benchmark](../internal/model-speed-effort-benchmark-2026-07/README.md)
(`[measured, local, n=3/cell]` — 73 timed `claude -p` runs on Fable 5 /
Opus 4.8 / Sonnet 5 / Haiku 4.5) changes three §2/§1-adjacent conclusions
**for this lineup specifically**:

- **"Always-high overthinks trivial inputs (+1,953%)" is superseded on
  adaptive-thinking models.** That figure (arXiv 2412.21187) predates
  adaptive thinking; measured now, easy tasks cost the same 3–10s at every
  effort — the dial self-adjusts, so **uniform `xhigh` is safe** (and is
  Claude Code's documented default for coding/agentic work). "Always-low
  drops success" **still holds** (Sonnet 5 wrong at low/medium on the hard
  reasoning task while Opus/Fable at low were right) — the asymmetry now
  points one way: don't route effort down; `max` buys deliberation time at
  diminishing returns and is best kept as an escalation rung.
- **Per-token speed ≠ task speed — the ranking inverts by regime.** On
  thinking-dominated coding, Fable is the *fastest model wall-clock*
  (Opus-class tok/s × 3–5× fewer tokens to a correct answer) and Haiku the
  slowest despite ~255 tok/s (it brute-forces reasoning as visible text).
  On tool-loop chores, Sonnet/Haiku win (~36s vs ~51s; TTFT + per-turn
  overhead dominate). Routing for wall-clock must be **regime-aware**, not
  "smaller = faster."
- **Token efficiency largely offsets the price ladder at the top.** Cost
  per solved thinking-heavy task: Opus ≈ Sonnet (5× price ÷ ~2.5× fewer
  tokens), Fable ≈ 1.6–1.8× Sonnet (not 10×). On no-thinking chores the
  ladder passes through (Haiku ~3.5× cheaper than Sonnet). Correctness was
  **saturated at prompt scale** (36/36) — separation lives at horizon
  scale, which is what makes horizon/regime the routing axis
  ([task-horizon-prediction.md](task-horizon-prediction.md)).

## 2c. Model-specific weekly caps (added 2026-07-05, `[operator-observed]`)

Fable 5 carries its **own weekly usage cap, significantly below the general
5h/7d windows** — hit twice on 2026-07-05: the operator's interactive session,
and a firing's critical test-author (`429 "out of usage credits … Fable 5"`,
first call, 0 tokens) while the general windows read 0.82 seven-day / 0.63
five-hour. Consequences adopted:

1. **Per-model caps are invisible to the general windows** — the statusline
   rung cannot see them coming; the governor's degrade hold happened to fire
   first here (correlated pressure), but that is luck, not coverage.
2. **Top-tier capacity is a separate, scarcer resource** shared with the
   operator's interactive work — machinery spend on it starves the operator.
   → **I28**: fable removed from the machinery (`max` aliases `capable`);
   reintroduction gated on the cap rising or interactive usage dropping.
3. Under an over-degrade *general* window, **opus workers stall in indefinite
   API backoff rather than 429ing** (P3v2-13: 38-min zero-progress hang) —
   window pressure degrades every model's workers, just with different
   failure shapes. Substitution does not dodge a window; parking does.

## 3. Burn forecasting — a hard published ceiling (verified 3-0)

`[measured; arXiv 2604.22750 "How Do AI Agents Spend Your Money?" — 8 frontier models incl.
Claude Sonnet 4.5, 500 SWE-bench-Verified instances; authors incl. OpenHands lead X. Wang,
Mihalcea, Brynjolfsson, Pentland]`

- **Same-task token spend is inherently stochastic — repeat runs differ up to 30×.** Point
  forecasts are unusable for tight packing against 5-hour/weekly windows; admission must use
  quantile/error-bar forecasts against the degrade (0.8) and pause (0.95) thresholds.
- **Models cannot self-predict their spend** (correlations ≤ 0.39, systematic
  *under*-estimation — the dangerous direction near a wall, since it over-admits; the
  self-prediction call itself cost 0.32–2× the task's own tokens for Claude models). This
  **confirms §5.3's "a script, not an LLM call"** predictor choice and rules out implementer
  self-estimates as an admission input.
- **Human-expert difficulty ratings only weakly track actual token cost** — so the duration
  predictor's human-legible features (spec size, file count, subsystem breadth, novelty) are
  *not proven* proxies for spend. The bucket×profile matrix must be validated against measured
  burn before it leaves its §11 feature flag. (Interpretive step: the paper tested human
  *ratings*, not the design's exact structural features — hence "validate before rollout," not
  "abandon.")

## 4. Budget-awareness & early-abort (verified 3-0)

`[measured; BAGEN "Are LLM Agents Budget-Aware?", arXiv 2606.00198 — 5 frontier agents incl.
Claude Opus 4.7 / Sonnet 4.6, 4 environments incl. SWE-bench]`

- **Agents cannot self-manage token budgets:** capability↔budget-awareness correlate only
  weakly (r = 0.35); frontier models are consistently over-optimistic, continuing to spend on
  doomed trajectories instead of alerting early. A stronger model does **not** buy
  self-throttling near a wall — window management must stay in the external, between-task
  governor script. Confirms §5.1's external-governor placement and the §9 "parallel burst
  empties the window" concern.
- **Intra-task early-abort is a quantified lever the design lacks:** terminating when the
  feasibility signal says "impossible" saves **28–64% of tokens on failed trajectories**
  (GPT-5.2 64.1% saved at 6.6% false-abort; Claude Sonnet 49.6%/3.3%; Claude Opus 28.2%/2.2%;
  overall success −1.6 to −4.2pp). The signal is trainable (SFT lifts feasibility accuracy
  25.5%→~90%, though demonstrated on Qwen-7B/Sokoban, and interval calibration stays poor at
  47% coverage). **Design action:** add an abort-on-predicted-failure check inside long-running
  tasks (extends §5.1's between-task-only governor); ship observe-only and count false-aborts
  against the O0 floor before enforcing.

## 5. Scheduling & admission-control theory / practice

- **Admission-control theory exists for LLM serving** (arXiv 2604.11001): a flow-control
  framework proves instability is unavoidable when expected workload exceeds capacity M, and
  that admission gating is provably *sufficient* for stability — output length is modeled as
  unknown at arrival (cost uncertainty). Server-side GPU/KV-cache setting; transfers to
  subscription quota windows **by structural analogy only** — supports building explicit
  admission control rather than relying on prioritization alone. `[E, analogy]`
- **Production burn-governor practice** `[folklore/vendor; TrueFoundry — unaudited but
  design-shaped]`:
  - **Forecast on tail percentiles, never means.** P95-of-rolling-7-day tracked monthly spend
    within 8–12%; trailing means fail because agent spend is heavy-tailed (P95 ≈ 4× mean).
    Feeds §5.1 per-task burn forecast and §12 open question 5.
  - **Graduated degradation converges with the design's ladder:** a four-threshold governor
    (75% soft alert / 90% "constrained mode" rerouting premium models to cheaper fallbacks /
    95% final warning / 100% hard cap → HTTP 429), checked every ~20 min against an attributed
    ledger — independent convergence on §5.1's degrade→pause shape, and it couples the degrade
    threshold to tier downgrade (§5.3), not only panel-shrink/no-new-tasks.
  - **Ship budget enforcement in audit mode first** (track/alert against simulated caps, tune,
    then enable hard blocking) — untuned hard caps cause fleet-wide failures. Matches §5.1's
    "never hard-coded" rule and argues for observe-only Stage-0 thresholds (§11).
  - **Per-run cost grows ~O(n²) in agent steps** (context re-appended each step), so step-count
    caps and retry breakers are first-order O1 controls, not niceties — a stuck loop becomes a
    multi-million-token run. Feeds the §9 liveness guard.
  - Case study (single unaudited anecdote): a review agent re-injecting a 50k-token manual into
    every PR was 92% of pipeline cost; caching it cut spend ~10×. Directional support for §5.2's
    "cache discipline is the #1 hidden lever," but it is gateway semantic caching, not Anthropic
    prompt caching, so the magnitude does not transfer to Max-plan window accounting.

## 6. Wall-clock & paid parallelism (§6) — the multi-agent exchange rate, fact-checked

- **The Anthropic "90% time reduction at ~15× tokens" citation fuses two separate
  measurements** `[E; anthropic.com/engineering/multi-agent-research-system]`. The real facts:
  a multi-agent system (Opus lead + Sonnet subagents) beat single-agent Opus by **90.2% on an
  internal research eval** at *unequal* (much larger) budget; the **time** reduction is
  attributed separately to parallel subagent spawning + parallel tool calls; the multipliers
  are **~4× tokens vs chat for single agents, ~15× vs chat for multi-agent**. Cite as two facts,
  not one exchange-rate pair.
- **Spending more tokens genuinely buys agentic performance:** on BrowseComp, token usage alone
  explained **80%** of performance variance (95% with tool-call count + model choice) `[E]`. This
  supports the §5.3 ladder's premise that escalation buys quality — and *raises* the cost of
  routing misclassification, since cheap-tier runs will systematically underperform.
- **Multi-agent fan-out is only economical for high-value, heavily-parallelizable, context-
  exceeding work** — Anthropic's own framing `[E]`. Confirms the design's decision to gate
  fan-out behind the budget governor (§6.2) rather than defaulting to it, and to buy parallelism
  for *validation* structurally but for *implementation* only under the admission rule.
- The single-agent-at-equal-budget result (arXiv 2604.02460) and its "MAS wins when context
  degrades" caveat are covered under
  [correctness-and-verification-evidence.md §3](correctness-and-verification-evidence.md).

## 7. Net design implications (summary)

| Design element | Verdict from this evidence |
|---|---|
| §5.3 tier ladder | Confirmed shape; **re-quote the savings band** (73–98% query / ~56% best-case code / ~30% OOD); keep multi-rung |
| §5.3 effort axis | Confirmed; both uniform defaults fail; treat budgets as soft with overshoot variance |
| §5.3 escalation ordering | New rule: effort-before-tier, always at respawn boundary (cache-key constraint) |
| §5.1 burn forecast | **Redesign to quantile/P95**; validate predictor features vs measured burn before flag-flip |
| §5.1 external governor | Strongly confirmed (agents can't self-throttle) |
| New lever | **Intra-task early-abort** (28–64% of failed-run tokens); observe-only first |
| §6.2 admission control | Confirmed; has formal + production analogues; forecast must include added burn at tail |
| §6.2 multi-agent framing | **Unfuse the 90%/15× citation**; add the 80%-variance datapoint |
| §9 liveness | Add step-count caps (O(n²) growth) |
| §11 rollout | Thresholds ship in audit/observe-only mode first |
