# Research corpus — index

Primary-sourced research behind the harness design
([../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md)),
organized by topic. Each document is self-contained and cites primary sources inline with
confidence tags: `[official]` Anthropic docs, `[measured]` community/benchmark measurement with
data, `[contested]` conflicting evidence, `[folklore]` practitioner consensus; plus `[E]`
established-in-source / `[I]` inference-synthesis for research-study claims.

Compiled from two research efforts: a comparative state-of-the-art study and re-validation
prior-art digest (**2026-07-03**), and a targeted gap-filling deep-research pass on routing
economics, burn forecasting, Claude Code/Max-plan mechanics, and vault isolation
(**2026-07-04**). The 2026-07-04 pass used a fan-out → fetch → 3-vote adversarial verification
workflow (24 of 25 top claims confirmed, 1 refuted); its three most design-changing facts were
re-verified by direct fetch of the official pages.

## The documents

**By objective:**

- [landscape-and-novelty.md](landscape-and-novelty.md) — the design vs. 20+ contemporary agents
  and frameworks; the comparison matrix; what is genuinely novel; the surviving design critique.
- [correctness-and-verification-evidence.md](correctness-and-verification-evidence.md) — the O0
  floor's evidence base: reward-hacking/stale-green threat, blind generator–verifier separation,
  panel-diversity, the human plan gate, external kill switches, and the calibration-probe
  novelty claim.
- [token-economics-and-scheduling.md](token-economics-and-scheduling.md) — the O1/O2 evidence:
  model/effort routing and cascades, burn forecasting, budget-awareness and early-abort,
  admission-control theory/practice, and the multi-agent wall-clock exchange rate.
- [revalidation-reuse-and-leakage.md](revalidation-reuse-and-leakage.md) — the held-out vault's
  economics: safe regression-test selection, corpus persistence/freshness, and adaptive-reuse
  leakage theory.

**Vendor-fact references (most volatile — recheck on schedule):**

- [claude-code-and-max-plan-facts.md](claude-code-and-max-plan-facts.md) — prompt-cache
  behavior, rate-window mechanics, quota introspection, usage credits, capacity/regime
  changelog.
- [isolation-and-sandboxing.md](isolation-and-sandboxing.md) — the six-layer stack proving the
  implementer cannot read the vault (design open question #3).

## How this maps to the design doc

| Design section | Backing research |
|---|---|
| §2 objective function; §7 correctness floor | correctness-and-verification-evidence; landscape-and-novelty |
| §5.1 budget governor; §6 wall-clock & parallelism | token-economics-and-scheduling; claude-code-and-max-plan-facts |
| §5.2 cache discipline; §10 Max-window facts | claude-code-and-max-plan-facts |
| §5.3 model/effort routing | token-economics-and-scheduling |
| §5.5 re-validation reuse / vault | revalidation-reuse-and-leakage (economics); isolation-and-sandboxing (secrecy) |
| §4 leverage map; §8 controller; whole-design novelty | landscape-and-novelty |

## Consolidated corrections & confidence ledger

Corrections produced by the fact-check passes, kept so future readers don't re-import the errors:

- arXiv **2502.08788**'s real title is "Stop Overvaluing Multi-Agent Debate — We Must Rethink
  Evaluation and Embrace Model Heterogeneity" (not "If Multi-Agent Debate is the Answer…", a
  different paper).
- Meta's mutation paper (**2501.12862**) reports **~9,095 mutants**, not ~4,660.
- **R2-Reasoner**'s primary source is arXiv **2506.05901** (WWW 2026); the routing survey
  2603.04445 was the fetched intermediary that reported its figure.
- Devin's "confidence-score gate" / DAG re-planning: third-party only; **not confirmed** on
  Cognition's own sources.
- Kiro "runs tests and verifies between each sequential task": **not confirmed** on any primary
  kiro.dev page (hooks *can* fire before/after task execution; built-in inter-task verification
  is not documented).
- The original Claude Code best-practices post (Apr 2025) was rewritten; the verbatim
  "think/ultrathink" ladder, the numbered 5-step TDD block, and "markdown file or GitHub issue"
  line are original-post wording, corroborated via mirrors, not re-fetchable.
- **Corrected 2026-07-04:** the design's §5.2 cache-TTL model (5-min default + `ENABLE_PROMPT_CACHING_1H`
  opt-in) is **stale** — subscription auth gets the 1-hour TTL automatically and loses it on
  usage credits; the §11 Stage-3 `ENABLE_PROMPT_CACHING_1H` item is obsolete on-plan.
- **Reframed 2026-07-04:** the design's "~75% cost cut from routing" is best-case on
  knowledge/chat benchmarks; coding/correctness-graded work sits at ~30–56%.
- **Unfused 2026-07-04:** the "90% time reduction at ~15× tokens" citation combines two separate
  Anthropic measurements (parallelism time-cut; token multiplier vs chat baseline).
- **Corrected 2026-07-04 (live probe, Claude Code 2.1.45):** the design's §5.3 claim "invalid
  ids fail loud" for the Workflow spawn path's per-agent `model`/`effort` overrides does **not**
  hold as stated — an invalid `effort` string is silently accepted (no error), and an invalid
  `model` id fails only as an async `null` result + workflow-level log entry, not a catchable
  throw. See `tools/budget-governor/probe-spawn-portability-2026-07-04.md` for the full
  methodology and re-verification protocol; the harness's spawn code must validate `(model,
  effort)` itself rather than trusting the primitive to reject bad config.

**Absence-of-feature findings** (strong, but inherently harder to prove than a positive): Kiro
closure gate; Spec Kit automated final gate; LangGraph built-in critic; any published
mutation-canary-calibration of an LLM review panel; a dedicated Claude Code quota CLI (issue
#13585 still open); an official statement on 5-hour-window anchoring or cache-read subscription
weighting.

**Refuted by the 2026-07-04 verify panel (1-2 vote):** "two-model cascades capture all the value
/ a many-rung tier ladder adds nothing" — evidence weak both ways; do not collapse the §5.3
ladder on this basis.

**Hype-tier, cite for framing only:** Ralph-loop cost anecdotes ($297 MVP); the "100k sessions →
dumb zone" statistic; Palisade's o3-86% chess figure; vendor SWE-bench scaffold-jump percentages;
the TrueFoundry 10× caching case study (single unaudited vendor anecdote, gateway semantic caching
≠ Anthropic prompt caching).

## Open items still unresolved

- **Cache-read subscription-limit weighting** — officially unanswered; settle with the design's
  §12 controlled measurement (now the highest-value experiment).
- **Agent-teams ~7× multiplier** — not re-verified in the 2026-07-04 pass; rests on the earlier
  official-docs inventory.
- **Official confirmation of 5-hour-window anchoring** — still only `[measured]`/practitioner.
- **`StopFailure` / `rate_limit` hook matcher** — single vendor-blog source; verify before
  relying.
- **Duration-bucket predictor features** — must be validated against measured burn before the
  §11 flag flips (human difficulty ratings only weakly track cost).

## Recheck schedule (these facts rot)

- Recalibrate window ceilings after **2026-07-13** (+50% weekly promo expiry).
- Re-check the **paused Agent SDK plan change** (would move headless usage off rate windows onto
  a monthly dollar credit — see claude-code-and-max-plan-facts §6).
- Re-verify any capacity magnitude after each Anthropic limit change; nothing is hard-coded.
