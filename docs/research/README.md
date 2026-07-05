# Research corpus — index

Primary-sourced research behind the harness design
([../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md)),
organized by topic. Each document is self-contained and cites primary sources inline with
confidence tags: `[official]` Anthropic docs, `[measured]` community/benchmark measurement with
data, `[contested]` conflicting evidence, `[folklore]` practitioner consensus; plus `[E]`
established-in-source / `[I]` inference-synthesis for research-study claims.

Compiled from four research efforts: a comparative state-of-the-art study and re-validation
prior-art digest (**2026-07-03**), a targeted gap-filling deep-research pass on routing
economics, burn forecasting, Claude Code/Max-plan mechanics, and vault isolation
(**2026-07-04**), a practitioner-stack survey + independent-confirmation pass
(**2026-07-04**): four-agent survey of the github.com/kunchenguid repos (AXI, gnhf, firstmate,
treehouse, no-mistakes, benchmark suite), three adversarial web-verification agents restricted
to independent sources, and a local zero-quota tokenizer measurement on this harness's own
data shapes — and a **critique-refresh pass (2026-07-04 evening)**: re-evaluation of the §4
design critique against the as-built system (in-tree verification of hooks/gate/governor/vault
state at 358 passing tests) plus targeted fetches on verifier precision (false FAILs) and
cross-model error correlation. The gap-filling pass used a fan-out → fetch → 3-vote adversarial
verification workflow (24 of 25 top claims confirmed, 1 refuted); its three most design-changing
facts were re-verified by direct fetch of the official pages.

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
- [tool-surface-and-format-economics.md](tool-surface-and-format-economics.md) — how workers
  touch tools and data: AXI interface principles, MCP-vs-CLI and deferred-tool-loading
  evidence (regime-split), TOON/serialization-format verification incl. local measurements on
  this harness's own shapes.
- [unattended-operation-prior-art.md](unattended-operation-prior-art.md) — one practitioner's
  production stack for unattended agent operation: event-log/reconciled-state split,
  zero-token supervision, worktree pooling, gate findings taxonomy, ratification-card UX,
  token-free loop testing.
- [harness-evaluation-prior-art.md](harness-evaluation-prior-art.md) — measuring the
  machinery itself: skill-routing reliability, process-ceremony cost/benefit (paired-arm
  methodology), validator/judge format patterns; with independent confirmation.
- [pilot-1-observations.md](pilot-1-observations.md) — live triage ledger of the first real
  firing's failures and friction (started 2026-07-04); the empirical feed for the
  pilot-#2 amendments.

**Vendor-fact references (most volatile — recheck on schedule):**

- [claude-code-and-max-plan-facts.md](claude-code-and-max-plan-facts.md) — prompt-cache
  behavior, rate-window mechanics, quota introspection, usage credits, capacity/regime
  changelog.
- [isolation-and-sandboxing.md](isolation-and-sandboxing.md) — the six-layer stack proving the
  implementer cannot read the vault (design open question #3).
- [model-speed-effort-benchmark-2026-07/](model-speed-effort-benchmark-2026-07/README.md) —
  `[measured]` local benchmark (2026-07-05, 73 timed `claude -p` runs) of Fable 5 / Opus 4.8 /
  Sonnet 5 / Haiku 4.5: latency, throughput, token-spend variance, correctness, and relative
  cost per solved coding task at xhigh effort; raw per-run JSONs and reproduction harness
  included. Headline: correctness is saturated at prompt-scale coding; speed ranking inverts
  between thinking-heavy (Fable fastest) and tool-loop (Sonnet/Haiku fastest) regimes; token
  efficiency offsets most of the Fable/Opus per-token price premium.

## How this maps to the design doc

| Design section | Backing research |
|---|---|
| §2 objective function; §7 correctness floor | correctness-and-verification-evidence; landscape-and-novelty |
| §5.1 budget governor; §6 wall-clock & parallelism | token-economics-and-scheduling; claude-code-and-max-plan-facts |
| §5.2 cache discipline; §10 Max-window facts | claude-code-and-max-plan-facts |
| §5.3 model/effort routing | token-economics-and-scheduling; model-speed-effort-benchmark-2026-07 |
| §5.5 re-validation reuse / vault | revalidation-reuse-and-leakage (economics); isolation-and-sandboxing (secrecy) |
| §4 leverage map; §8 controller; whole-design novelty | landscape-and-novelty |
| §4 skills/ToolSearch rows; §5.4 context hygiene; §6.1 turn accelerators | tool-surface-and-format-economics |
| §3.4 disk-is-memory; §6.3 human latency; §9 failure modes | unattended-operation-prior-art |
| §5.6 no-spend list; §7 self-measuring loop; §8 lever discipline | harness-evaluation-prior-art |

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

**From the 2026-07-04 independent-confirmation pass** (kunchenguid claims vs independent
sources; details in [tool-surface-and-format-economics.md](tool-surface-and-format-economics.md)
and [harness-evaluation-prior-art.md](harness-evaluation-prior-art.md)):

- **TOON token savings on uniform tabular data:** replicated, but as a **20–40% band vs compact
  JSON**, tokenizer/shape-dependent (author's −37% is the optimistic end); loses to compact
  JSON off-uniform (replicated + reproduced locally on this harness's own shapes); CSV smaller
  than TOON (replicated).
- **TOON read-accuracy "neutral or better":** `[contested, leaning negative]` — zero
  independent confirmations, three independent contradictions (−5 to −9pp), all in the
  small-model regime where the author claimed the edge. Markdown-KV/Markdown-Table beat TOON
  on the accuracy/token Pareto frontier in the only 12-format test.
- **TOON generation reliability:** `[measured, negative]` — one-shot 50% vs JSON 75% across 21
  models; parallel tool calls collapse in non-JSON formats. Never for model-generated output.
- **MCP schema tax (tens of K tokens per large server):** upgraded to `[measured, replicated]`
  (4+ independent measurements incl. GitHub's own changelog and Anthropic's posts).
- **"Hand-crafted CLI beats MCP on success":** `[measured, single-source, contested]` — the
  only other controlled head-to-head (Smithery n=756) found native MCP winning vs an
  *auto-generated* CLI (91.7% vs 83.3%, CLI 2.9× tokens); the hand-crafted cell is measured
  only by axi. The replicated meta-finding: **interface ergonomics dominates transport choice**.
- **Deferred tool loading:** the axi "net negative" finding and Anthropic's Tool Search gains
  are **different regimes, both real** — defer when catalog ≫10K tokens and the hot set is a
  small fraction; eager/pin the hot set when a worker uses most of its tools (Anthropic's own
  docs state this boundary).
- **Claude Code skill under-invocation:** direction `[measured, corroborated]` (Anthropic's own
  trigger-quality admissions; ~15k-char silent skill-list budget; independent ~45–50%
  activation measurement); the exact recall figures are n=1. "Codex over-invokes" is contested
  (SkillsBench found the opposite).
- **Process-ceremony harm (mandated TDD −3.6pp at +55% cost):** existence claim
  `[measured, corroborated]` (independent analogue: null outcomes at higher cost; overfitting-
  to-self-authored-tests mechanism independently established, 21.8–33% visible-pass-hidden-fail),
  **not a universal law** — provided ground-truth tests/plans help weaker models on
  function-level tasks. Moderators: who authors the tests, hidden-vs-visible grading, task
  scale, model era. The harmful regime is exactly what the design's blind held-out vault removes.
- **Agent self-reports unreliable ("claims, not evidence"):** `[measured, replicated]` (METR
  ≥16% cheating on successful 8h+ runs; Transluce o3 fabrication elicitation).

**From the 2026-07-04 critique-refresh pass** (details in
[correctness-and-verification-evidence.md §3 addendum, §7](correctness-and-verification-evidence.md)
and [landscape-and-novelty.md §4](landscape-and-novelty.md)):

- **Cross-model error correlation:** two independent academic sources (arXiv 2506.07962, 350+
  models, ~60% same-wrong-answer agreement when both err, correlation rises with capability and
  crosses providers; arXiv 2502.04313, judges favor similar models) — direction
  `[measured, replicated]`.
- **False-FAIL base rates:** Refute-or-Promote (arXiv 2604.19049) kill-rate magnitudes (~79–83%)
  are `[measured, single-source]` — methodology paper, self-reported; the
  unanimous-nonexistent-vuln incident is an existence claim `[E]`. Spec-alignment misjudgment
  (arXiv 2603.25773) is single-author, **direction only** — do not import its numbers. The curl
  bug-bounty closure is `[reported]`, cited for ecosystem framing only.
- **In-tree verification (2026-07-04, 358 tests passing):** no hook registration anywhere;
  closure gate lacked a Stop-hook stdin interface; `run_gate` passes absent inputs as "caller's
  choice"; governor has no reading-staleness handling; gate spills full held-out output to
  in-repo evidence dirs. These are working-tree facts, not external research — recorded here
  because the §4 critique and design amendments lean on them.

**Hype-tier, cite for framing only:** Ralph-loop cost anecdotes ($297 MVP); the "100k sessions →
dumb zone" statistic; Palisade's o3-86% chess figure; vendor SWE-bench scaffold-jump percentages;
the TrueFoundry 10× caching case study (single unaudited vendor anecdote, gateway semantic caching
≠ Anthropic prompt caching).

## Open items still unresolved

- **Cache-read subscription-limit weighting** — officially unanswered (re-verified 2026-07-04
  evening: #24147 still has no maintainer response; new indirect signal — `/usage` limit
  attribution itemizes cache *misses*, implying hits are discounted, weight unstated); settle
  with the design's §12 controlled measurement (now the highest-value experiment).
- **Headless quota surface** — re-verified 2026-07-04 evening: #13585 open (zero maintainer
  responses through v2.1.201), OTEL consumption-only. Design §12 Q1 now tracks *which fallback
  to wire* (statusline-dump shim > OAuth endpoint > estimate), not whether a surface exists.
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
