# T1 run 2 — 2026-07-13 (operator-executed per pre-registered sizing)

**Protocol:** [cache-read-quota-weight-experiment.md](../../../../tools/budget-governor/cache-read-quota-weight-experiment.md),
"Run 2 — pre-registered sizing" section (registered 2026-07-12, before execution). Build
2.1.207 (same verified build as run 1 — the build rule's dry-run trigger did not fire); model
pinned `claude-opus-4-8` both arms (`T1_MODEL`); **N=28 turns, F=2,500 words ≈ 5,593 tokens
per filler block** (steady-state cache write, turn 28). Raw artifacts in this directory:
`arm-a/`, `arm-b/` (28 verbatim `claude -p --output-format json` turn JSONs each),
`readings.jsonl` (the status-line `rate_limits` lines for the three readings).

**One deviation, covered by the protocol:** the window was not fresh — baseline read **3**,
not 0 (earlier same-window activity, disclosed by the operator before analysis). The
protocol's Controls section pre-registers exactly this contingency: *"record the window's
`used_percentage` immediately before each arm and treat the delta, not the absolute value, as
the measurement."* All analysis below is on deltas. Headroom was never in question (peak: 10
of 100). No other amendments.

## The raw numbers

**Window meter** (`rate_limits.five_hour.used_percentage`, account-level; `resets_at`
identical at all three readings → no mid-run window reset):

| Reading | epoch t | local (2026-07-13) | five_h | seven_d |
|---|---|---|---|---|
| R0 baseline | 1783932666 | 01:51:06 | **3** | 7 |
| R1 after Arm A | 1783932811 | 01:53:31 | **3** | 7 |
| R2 after Arm B | 1783932916 | 01:55:16 | **10** | 8 |

**Bracketing verified from turn-file mtimes** — every turn falls strictly inside its
reading pair: Arm A ran 01:51:52–01:53:06 (74 s, inside R0–R1); Arm B ran 01:53:53–01:55:11
(78 s, inside R1–R2). The arms are prefill-bound with 4-token outputs, hence far faster than
the prereg's 10–20 min guess — the guess was wrong, the brackets are what matter.

**Token totals** (sum of `.usage` over each arm's 28 turns):

| | fresh input | cache write | cache read | output | cost USD |
|---|--:|--:|--:|--:|--:|
| Arm A (cache-preserving) | 104 | 176,983 | 2,720,679 | 112 | $3.14 |
| Arm B (`DISABLE_PROMPT_CACHING=1`) | 2,898,461 | 0 | 0 | 112 | $14.50 |

Textbook per-turn pattern again: Arm A's reads grow linearly (14,997 → 173,538) with a
constant ≈5.6k-token write per turn; Arm B's fresh input grows linearly to **179,160 on turn
28** (prereg predicted ~177.7k — 0.8% off) with zero cache activity in all 28 turns. Arm A
turn 1 additionally carries a 4,094-token `claude-haiku-4-5` title-generation subcall absent
from Arm B — adds unmodeled weight to Arm A only, i.e. **conservative** for the bound below.
Writes are 1-hour-ephemeral; a 74 s arm has no TTL expiry. Zero errors, zero permission
denials, `claude-opus-4-8` in all 56 turns. Combined cost **$17.63** (estimate was ~$17).

## The pre-registered solve

Displayed meter values are integer-quantized. The true-delta intervals are **identical under
floor- or round-display**: `ΔA ∈ [0, 1)` points (meter is monotone within a window),
`ΔB ∈ (6, 8)` points — inside the prereg's predicted 4.6–13.9 band.

With `fresh = input + cache_creation`, `reads = cache_read`, cache-write window-weight v=1
(prereg): `fresh_A = 177,087`, `reads_A = 2,720,679`, `fresh_B = 2,898,461`, and

```
w = (ΔA/ΔB · fresh_B − fresh_A) / reads_A
```

- **Upper bound** (ΔA→1, ΔB→6): **w < 0.1125**.
- **Point estimate** (displayed ΔA=0): the solve goes negative (−0.065), i.e. **pins to
  w = 0** — even free cache reads predict Arm A moved ~0.4 pt, which displayed-0 absorbs.
- **Write-weight sensitivity:** under v=1.25 (the API billing rate for writes) the bound
  *tightens* to **w < 0.096**. **Correction (2026-07-14):** v=1 is the loosest choice only
  within v ∈ [1, 1.25]; the pre-registration fixed v=1 but did not measure it, and over the full
  plausible range v ∈ [0, 1.25] the loosest is **v=0** (cache writes free against the window),
  giving **w < 0.1775**. So the headline 0.1125 assumes **v ≥ 1**; the assumption-light bound is
  **w < 0.1775 (≈5.6×)**. And "point estimate 0" is a **censored-meter floor** (`ΔA ∈ [0,1)`
  displayed as 0): the data are consistent with any w in [0, bound), so read it as *consistent
  with 0*, not a separately identified zero. Neither shifts a design decision.

Same result as an exclusion table — what Arm A's delta *had to be* if w were:

| hypothesis | predicted ΔA (pts) | verdict vs observed ΔA < 1 |
|---|---|---|
| w = 0 (free) | 0.37–0.49 | consistent |
| w = 0.1 (≈ billing rate) | 0.93–1.24 | boundary — not excludable |
| w = 0.5 | 3.18–4.24 | **excluded** |
| w = 1.0 (community lean) | 6.00–8.00 | **excluded** |

## Window capacity, refined

Arm B's 2,898,461 fresh tokens moved the meter 6–8 points → **1 point = 362–483k weighted
tokens; the 5-hour window ≈ 36.2–48.3M weighted tokens** (Max plan, this build/day). This
**nests inside run 1's 21–62M** bound, and the linear model cross-checks both ways across the
9.3× scale-up: at run-2 capacity, run 1's Arm B (310,320 weighted) retro-predicts 0.64–0.86
pts (observed: the 0→1 transition ✓) and run 1's Arm A at w ≤ 0.1125 retro-predicts ≤ 0.30
pts (observed: 0→0 ✓).

## What this run establishes (each claim at its actual strength)

1. **Magnitude bounded: a cache-read token weighs < 0.1125 of a fresh input token against
   the 5-hour window** (under the pre-registered write weight v≥1; v=0 → < 0.1775) — a
   several-fold discount (≈6–9×), consistent with 0 (free) but not separately identified. Half
   weight and full weight are excluded outright, run 1's direction finding confirmed at 9.3×
   scale. (A3 — the artifact carries it; `vendor-policy` decay: re-run on any announced
   plan/limits change.)
2. **T1 is settled.** The design question — "do cache reads meaningfully discount
   subscription-window occupancy?" — is answered *yes, by several-fold (≈6–9×; see the write-weight correction above)*. The remaining unknown
   (where in [0, 0.11) w sits) changes no current design decision. Distinguishing w=0 from
   w≈0.1 would need a finer usage surface or an arm-A-only run at ≥3× the reads — named,
   optional, not a settling step.
3. **Window capacity ≈ 36.2–48.3M weighted tokens / 5h** on Max, 1.7× tighter than run 1 and
   consistent with it. (A3; `vendor-policy`; n=2 windows, consecutive days.)
4. **Billing and window accounting are now separately measured and mutually consistent:**
   Arm A cost 21.7% of Arm B's dollars ($3.14 vs $14.50) while causing <14% of its window
   movement — the billing discount (~10% official) and the window discount (<11.25% measured)
   are the same order. (A3.)
5. The weekly meter moved 7→8 exactly at R2 — coherent with Arm B being the only large
   spend in the bracket. (Incidental.)

## Threats, each with its direction

- **Baseline 3, not 0** — covered by the pre-registered delta contingency (above). R0=R1=3
  across 145 s shows no trailing drain contaminated Arm A's bracket.
- **Attested account silence** is load-bearing for Arm B's bracket: outside spend inside
  R1–R2 would fake meter movement Arm B didn't cause, *loosening* the true bound. Mitigation:
  operator-attested silence, a 105 s bracket at ~01:54 local, and the seven_d coherence in
  claim 5. Residual risk accepted and disclosed.
- **R2 taken 5 s after Arm B's last turn** — any lagging server-side accounting undercounts
  ΔB, which *loosens* (never tightens) the computed bound. Safe direction.
- **Haiku title subcall in Arm A only** (4,094 tok) — inflates Arm A's unmodeled spend,
  conservative for the bound. The reading sessions themselves spend ~10⁻³ pt each (one Haiku
  turn) — negligible.
- **Quantization scheme unknown (floor vs round)** — the delta intervals coincide under
  both, so nothing rests on it.

## Honest summary for the T1 ledger

**Settled.** Cache reads are discounted against the 5-hour window by at least ~9× (w <
0.1125, point estimate 0); full and half weight excluded; the community-telemetry "near-full
weight" lean is contradicted on this build/plan at two run sizes. Window capacity ≈ 36–48M
weighted tokens/5h. D12's append-only context discipline gets its promotion trigger. The
*official* answer remains unpublished — decay class `vendor-policy`, re-run on any announced
plan or limits change.
