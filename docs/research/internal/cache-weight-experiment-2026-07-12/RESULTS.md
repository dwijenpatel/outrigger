# T1 first run — 2026-07-12 (operator-executed per protocol)

> **Superseded on magnitude by [run 2](../cache-weight-experiment-2026-07-13/RESULTS.md)**
> (2026-07-13, 9.3× larger): w < 0.1125, point estimate 0 — T1 settled. Everything below
> stands as written; run 2 closed the "magnitude unidentified" gap.

**Protocol:** [cache-read-quota-weight-experiment.md](../../../../tools/budget-governor/cache-read-quota-weight-experiment.md),
run exactly as pre-registered (rehearsal in the prior window; arms + readings in a fresh
5-hour window). **Amendments: none.** Build 2.1.207; model pinned `claude-opus-4-8` both arms
(`T1_MODEL`); N=5 turns; F=6,003 words ≈ 13,273 tokens per filler block. Raw artifacts in
this directory: `arm-a/`, `arm-b/` (5 turn JSONs each, verbatim `claude -p --output-format
json` output), `readings.jsonl` (the status-line `rate_limits` dump, incl. rehearsal lines).

## The raw numbers

**Window meter** (`rate_limits.five_hour.used_percentage`, account-level, fresh window):

| Reading | epoch t | five_h |
|---|---|---|
| baseline | 1783912582 | **0** |
| after Arm A | 1783912729 | **0** |
| after Arm B | 1783912830 | **1** |

**Token totals** (summarize over each arm's 5 turns):

| | fresh input | cache read | cache creation | output | cost USD |
|---|--:|--:|--:|--:|--:|
| Arm A (cache-preserving) | 18 | 236,693 | 73,609 | 20 | $0.864 |
| Arm B (`DISABLE_PROMPT_CACHING=1`) | 310,320 | 0 | 0 | 20 | $1.552 |

Per-turn pattern, textbook: Arm A's cache reads grow linearly (14,997 → 75,333) with a
constant ≈13,273-token cache write per turn (the new filler block); Arm B's fresh input grows
linearly (35,518 → 88,610) with zero cache activity in any turn. Arm A turn 1 additionally
carries a 9,014-token `claude-haiku-4-5` subcall (Claude Code's internal title generation,
$0.009) absent from Arm B — an asymmetry that *adds* weight to Arm A, i.e. conservative for
every conclusion below. The pinned model is `claude-opus-4-8` in all 10 turns.

## What this run establishes (each claim at its actual strength)

1. **`DISABLE_PROMPT_CACHING=1` works as documented** — zero cache reads/writes across all
   five Arm B turns, perfect linear re-reading. The experiment's mechanism is real.
   (`vendor-build`.)
2. **The window meter is integer-quantized.** Every observed `used_percentage` value (13
   pre-reset; 0, 0, 1 in-window) is a whole number, and each interactive reading emits a null
   line before the populated one. Any future window telemetry (T5) inherits this ±0.5-point
   floor. (`vendor-build`.)
3. **Full-weight cache reads are excluded (w ≥ 1 rejected).** At w = 1 (and cache writes at
   weight ≥ 1), Arm A's weighted total (18 + 236,693 + 73,609 + 9,014·haiku ≈ **319k**) is
   *larger* than Arm B's (**310k**) — yet Arm A moved the meter by < 0.5 points while Arm B
   moved it by ≥ 0.5. If cache reads counted at full weight, Arm A had to move the meter at
   least as much as Arm B. It did not. Cache reads are discounted against the window.
4. **The magnitude of the discount is NOT identified by this run.** The protocol's ratio
   table degenerates under integer quantization (observed ratio 0/1; the pre-registered
   "delta too small → scale F up, not a conclusion" caveat fires). Depending on where Arm B's
   true delta sits inside its [0.5, 1.5) band, the data admit anything from w ≈ 0 (free) up
   to w ≈ 0.9. **No w value is reported.** (Don't-force-fit rule, §"The math" of the
   protocol.)
5. **First internal bound on window capacity:** Arm B's 310,320 fresh-weighted tokens moved
   the meter by [0.5, 1.5) points → the 5-hour window is **≈ 21M–62M weighted tokens** on
   this plan (Max), this day. (`vendor-policy` decay; sample-of-one window.)
6. **The billing-side discount showed up as dollars, incidentally:** Arm A did *more* total
   token-movement than Arm B for **56%** of the cost ($0.864 vs $1.552) — consistent with the
   ~10% cache-read billing rate, and a reminder that billing weight ≠ window weight is
   precisely the open question.

Weekly meter (`seven_d`) stayed 0 throughout — untouched at integer resolution.

## Honest summary for the T1 ledger

Directionally: cache reads are **cheaper than fresh input against the window** (full weight
excluded) — the operator's prior survives; the community-telemetry "near-full weight" claim
does not, at least on this build/plan. Magnitude: **unresolved at this run size.** The
instrument and mechanism are now verified, so the follow-up is purely a sizing decision.

## Named follow-up options (operator's call, any future clean window)

- **Rerun ~5–10× larger** so Arm B lands 5–15 points: N=10/F=12,000 ≈ ×4.7 (opus, ≈ $8);
  N=10/F=24,000 ≈ ×9.4 (≈ $15). Resolves w to roughly ±0.1.
- **Same experiment on Sonnet or Haiku** — cheaper per point of meter movement if window
  weighting is uniform across models; also tests whether it *is* uniform (unknown).
- **Look for a finer-grained usage surface** before spending again (the integer floor is the
  binding constraint, not token volume).
