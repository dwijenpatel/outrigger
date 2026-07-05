# Task-horizon prediction — can we route models by predicted task length?

Evidence behind the design's duration-bucket predictor (§5.3, flagged behind
Stage-1 validation) and the I18 regime-routing rework. Compiled 2026-07-05
from an operator-run research pass; sources fetched by that session, not yet
independently re-verified here — 2026 arXiv items are tagged accordingly.
Companion: [model-speed-effort-benchmark-2026-07/](model-speed-effort-benchmark-2026-07/README.md)
(the local measurement that makes horizon/regime the routing axis).

---

## 1. Horizon as difficulty — established (METR)

- **Task difficulty = time a skilled human needs**; per model, fit
  P(success) vs log(human-time); the "50% horizon" is where it crosses 0.5.
  `[measured]` https://arxiv.org/abs/2503.14499 ·
  https://metr.org/time-horizons/ (live tracking; Epoch mirrors a dashboard)
  · domain variation: metr.org/blog/2025-07-14-how-does-time-horizon-vary-across-domains/
- This supplies the **routing-table half**: given a horizon bucket, each
  model has a calibrated success probability. Labeled data exists —
  SWE-bench Verified ships human-annotated fix-time buckets
  (<15m / 15m–1h / 1–4h / >4h). `[E]`
- METR does **not** supply the prediction half (humans measure horizons;
  nothing infers them from task text). BRIDGE (arXiv 2602.07267) inverts the
  wrong way (model performance → human time). `[E, single-source]`

## 2. Predicting effort from task text — old field, honest record

Classical software effort estimation (COCOMO → story points → Deep-SE/GPT2SP
lineage): **bucket-level prediction works; point estimation does not** —
consistent optimism bias, large error bars. `[measured, literature-long]`
The LLM twist ("Can LLMs Perceive Time?", arXiv 2604.00010) matches the
corpus's burn-forecasting ceiling: models cannot self-predict their own
spend (r ≤ 0.39, systematic under-estimation, and the estimate call itself
costs 0.32–2× the task —
[token-economics-and-scheduling.md §3](token-economics-and-scheduling.md)).

## 3. Difficulty-aware routing for coding agents — the 2026 frontier

All `[E, single-source, not yet independently verified — do not import
magnitudes]`:

- **Agent Psychometrics** (arXiv 2604.00594) — IRT + task features to
  predict per-task success for unseen agent×task pairs on agentic coding
  benchmarks; closest published "difficulty predictor for coding agents."
- **Agent-as-a-Router** (arXiv 2606.22902) — routes coding tasks between
  models on task features in an agentic setting; beats static baselines.
- **Difficulty-Aware Agent Orchestration** (arXiv 2509.11079) — learned
  difficulty estimator sets workflow depth/operators.
- Already-verified corpus anchor: **pre-generation routing beat
  escalate-on-failure on 4 of 5 benchmarks** (arXiv 2605.06350, 3-0) —
  conditional on features actually predicting.

## 4. What the harness adopts (design consequences)

1. **Predict horizon *buckets*, never spend.** Spend varies 30× across
   identical repeats (§3 ceiling) — unpredictable in principle; horizon
   class (minutes / hour / multi-hour) is a property of the task and is
   bucket-learnable per decades of estimation literature.
2. **Asymmetric loss.** The local benchmark shows short tasks are solved by
   every model — mis-routing short work up wastes ≤2× cost; mis-routing
   long/thinking work down costs a full failed attempt + wall-clock +
   escalation (pilot-2's GL1: two floor-tier failures, 79k tokens/12min,
   before a standard-tier 28.5k/4min success). The predictor therefore only
   needs **high recall on the long/thinking class**: when unsure, route up.
3. **A script/classifier, not an LLM self-estimate** (r ≤ 0.39 stands).
4. **Zero-ML v1 = planner-assigned regime tags.** The plan-build interview
   already knows each task's shape; tagging `regime` (chore | thinking |
   long_horizon) at planning time beats inferring it from text, and the
   run-log (wall_secs, outcome, model, attempt) is the calibration set that
   later validates or retires the tags — same Stage-1 gate as the §5.3
   predictor flag (features must predict before anything trusts them).
5. Nobody has shipped a validated horizon-router for coding agents; the
   2026 papers are first attempts. The design's flagged duration-bucket
   predictor is aimed at exactly the version the evidence supports —
   coarse buckets, asymmetric loss, escalate-on-verified-FAIL kept as the
   net regardless.
