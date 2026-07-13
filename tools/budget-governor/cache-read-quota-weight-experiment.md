# Cache-read quota-weight experiment — protocol

Resolves **T1** in the current design plan
([../../docs/design/evidence-based-harness.md](../../docs/design/evidence-based-harness.md) §4,
D12) — the highest-value single measurement available *(originally design-v1 §10.2/§12 open
question #2; that document is now in [the attic](../../docs/attic/token-time-optimized-harness.md))*:
does a cache-read token count against the Max-plan 5-hour/weekly windows at a discount (API
billing rate is ~10% of fresh input) or at near-full weight (what community telemetry —
[claude-code-and-max-plan-facts.md](../../docs/research/external/platform-facts/claude-code-and-max-plan-facts.md)
§4 — suggests)?

**This experiment spends real Max-plan quota.** It is written but **not executed**. Read this
whole document, then decide when to run it — right after a window reset gives the cleanest
baseline, since the two arms should ideally run back-to-back in the same fresh 5-hour window so
neither carries stale occupancy from unrelated work.

## Hypothesis and design

Two arms process **the same total amount of "read" content**, but one reads most of it via the
prompt cache and the other reads all of it fresh. If the window only bills fresh tokens, the
cache-preserving arm should barely move `used_percentage`; if it bills cache reads too, both arms
should move it by roughly the same amount.

**Arm A (cache-preserving):** one growing session, `N` turns. Each turn appends the same
filler block (~`F` words) plus a trivial instruction. Turn 1 is a full cache miss (writes the
first filler block fresh). Turns 2..N each read all *prior* filler blocks from cache and only
the current turn's filler block fresh.

- Total fresh input ≈ `N × F` (word-equivalent; F stands for "one filler block's token count")
- Total cache-read ≈ `(0 + 1 + 2 + ... + (N-1)) × F = (N(N-1)/2) × F`

**Arm B (cache-busting):** the identical `N`-turn conversation, but with
`DISABLE_PROMPT_CACHING=1` set for the whole session, so every turn re-reads the entire prior
conversation fresh (no cache hits at all).

- Total fresh input ≈ `(1 + 2 + ... + N) × F = (N(N+1)/2) × F`
- Total cache-read ≈ 0

With `N = 5`: Arm A ≈ `5F` fresh + `10F` cache-read; Arm B ≈ `15F` fresh + `0` cache-read. Output
is held ~constant across every turn in both arms (the instruction is "reply with exactly: OK"),
so it's a control, not a variable.

## The math: reading the result

Let `w` be the effective weight of a cache-read token against the window (0 = free, 1 = full
weight). If the window's occupancy delta scales linearly with `fresh + w × cache_read`:

```
ΔA ∝ 5F + 10Fw
ΔB ∝ 15F
ratio = ΔA / ΔB = (5 + 10w) / 15
```

Solve for `w` from the observed ratio:

```
w = (15 × ratio − 5) / 10
```

| Observed ratio (ΔA / ΔB) | Implied `w` | Reading |
|---|---|---|
| ≈ 0.33 | ≈ 0.0 | Cache reads are free against the window — §10.2's conservative assumption is overly cautious |
| ≈ 0.40 | ≈ 0.1 | Cache reads count at roughly the ~10% billing discount |
| ≈ 0.67 | ≈ 0.5 | Partial weighting, closer to full than to the billing discount |
| ≈ 1.0 | ≈ 1.0 | Cache reads count at full weight — matches the community telemetry in `claude-code-and-max-plan-facts.md` §4 |

`ratio > 1` is possible (e.g. cache *writes* also cost something the window bills, or per-turn
overhead is nonlinear) — if you see it, don't force-fit `w`; report the raw numbers and treat it
as a sign the linear model is too simple for a second pass.

## Controls and threats to validity

- **Run both arms in the same fresh 5-hour window**, back-to-back, so neither carries stale
  occupancy from unrelated prior use. If you can't, record the window's `used_percentage`
  immediately before each arm and treat the *delta*, not the absolute value, as the measurement.
- **No concurrent interactive use of the same account** during the experiment — the window is a
  shared pool (design §5.1); any other Claude app/Claude Code activity on the account during the
  run confounds the delta.
- **One model, pinned explicitly, both arms** (added 2026-07-12): bare `claude -p` inherits a
  config default, and some plan configurations auto-switch models under window pressure —
  which would make the arms incomparable. The runner now requires `T1_MODEL=<model>` for
  `arm-a`/`arm-b` and passes `--model` on every turn; it refuses to run without it rather
  than silently picking a default (the model choice is part of the pre-registration — record
  it with the results).
- **Identical filler content across arms**, generated once by `run_cache_weight_experiment.sh
  gen-filler` — determinism matters more than the content itself (verified: two invocations
  with the same word count produce byte-identical output).
- **Output held constant**: the "reply with exactly: OK" instruction keeps output tokens
  ~fixed per turn in both arms, so it isn't a confound.
- **Scale `F` up if the delta is too small to read.** Windows were doubled 2026-05-06 (design
  §10.3) and sizes aren't published, so a percentage-point delta that rounds to ~0 just means
  the filler was too small — rerun with a larger `F`, not a conclusion.
- **This measures the 5-hour window specifically, and the readout must be account-level.**
  The only documented machine-readable source for the account's window occupancy is the
  **status-line JSON**: `rate_limits.five_hour.used_percentage` and
  `rate_limits.seven_day.used_percentage` (plus `resets_at`), populated from the most recent
  API response — the server's account-wide view (verified 2026-07-12 vs
  code.claude.com/docs/statusline; `vendor-build`, re-probe each build). It beats the `/usage`
  panel on two axes that matter here: it is **account-level** (the `/usage` panel is a
  *local-machine estimate* that excludes other devices and claude.ai), and it is **loggable
  with a timestamp** rather than hand-copied. Three constraints, all real and all load-bearing:
  1. The status line runs only in an **interactive terminal** `claude` session — **not** in
     headless `claude -p` (which the arms use), and **not** in the **desktop app** (no
     status-line surface — pilot-2 P2-8). So the readings come from a *separate terminal
     session* that brackets each arm, never from the arm process itself.
  2. `rate_limits` populates only **after one API round-trip**, so that bracketing session must
     send one message before the fields appear.
  3. `used_percentage` is coarse (0–100). If a delta rounds to ~0, scale `F` up (rule above) —
     now with a machine-readable readout instead of a squinted bar.
  **Fallback (desktop-app path):** read the 5-hour bar from the `/usage` panel manually before
  and after each arm. Simpler and app-native, but a local estimate and hand-transcribed. Either
  way, record the value **and** its timestamp. (`/usage` is interactive-only — it cannot be
  scripted via `claude -p`; verified 2026-07-12.)
- **Confirm the JSON schema before trusting the numbers.** ~~`summarize`'s field paths are a
  best-effort guess~~ — **validated 2026-07-11, zero quota**: the jq filter was run against real
  committed `claude -p --output-format json` outputs (build 2.1.201) from
  [the benchmark artifacts](../../docs/research/internal/model-speed-effort-benchmark-2026-07/README.md),
  and every field path (`.usage.input_tokens` / `.usage.output_tokens` /
  `.usage.cache_read_input_tokens` / `.usage.cache_creation_input_tokens` / `.total_cost_usd`)
  matched and summed correctly across multi-file input. The `dry-run` step is therefore a
  *confirmation* against the current build (schema decay is `vendor-build`), not a discovery —
  still eyeball its output once before the real arms.

## Procedure

1. **Dry run — schema *and* readout** (near-zero cost, and it must happen *before* the real
   window, never during it):
   - **(a) Token schema:** `./run_cache_weight_experiment.sh dry-run`, then
     `jq . experiment-logs/<timestamp>-dry-run/turn-1.json` and confirm the fields
     `summarize()` expects are present; edit the script if not.
   - **(b) Window readout, if using the status-line path:** add the `statusLine` command below
     to your settings, open an **interactive terminal** `claude`, send one message, and confirm
     a line with a real `five_h` number landed in the log. A status-line command that silently
     fails to log is caught here, for free — not mid-experiment. Remove it (or keep it) for the
     real run; it is harmless either way.

     ```json
     { "statusLine": { "type": "command",
       "command": "jq -c '{t: now, five_h: .rate_limits.five_hour.used_percentage, seven_d: .rate_limits.seven_day.used_percentage, resets: .rate_limits.five_hour.resets_at}' >> ~/t1-rl.log" } }
     ```
2. **Baseline.** Take a window reading and record value + timestamp.
   *Status-line path:* in the bracketing terminal `claude` session send one message, then read
   the last line of `~/t1-rl.log`. *Fallback:* open `/usage` in the desktop app and read the
   5-hour bar. Confirm the 5-hour bar is at/near baseline (this is why the run wants a fresh
   window) and no other account activity is in flight.
3. **Arm A:** `T1_MODEL=<model> ./run_cache_weight_experiment.sh arm-a 5 6000` (5 turns,
   ~6,000-word filler per turn — scale up if step 1's dry run suggests the window is large
   enough that this would be too small to register). Immediately after, take another reading
   the same way and record the delta as `ΔA_window`. Also run
   `./run_cache_weight_experiment.sh summarize <arm-a logdir>` and record the token totals.
4. **Arm B:** `T1_MODEL=<model> ./run_cache_weight_experiment.sh arm-b 5 6000` (same N, F,
   **and model**). Record `ΔB_window` and the token totals the same way.
5. **Compute** `ratio = ΔA_window / ΔB_window` and back out `w` from the table above.
6. **Commit the artifact first** — the raw `experiment-logs/` turn JSONs, both `summarize`
   outputs, and the four window readings with timestamps (the `~/t1-rl.log` lines, or the
   hand-recorded `/usage` values), under
   `docs/research/internal/cache-weight-experiment-<date>/`. The artifact is the warrant
   (distilled method): without it the result is a claim, not a measurement.
7. **Write the result back** into its current homes, dated:
   - [docs/design/evidence-based-harness.md](../../docs/design/evidence-based-harness.md) —
     settle **T1** in the §4 ledger and update D12's contested-question bullet with the measured
     `w` (or record "inconclusive" and why — that too settles how aggressive context reuse
     should be, conservatively);
   - [docs/research/distilled/internal.md](../../docs/research/distilled/internal.md) §4 — the
     measurement as A3 (decay `vendor-policy`: re-check on any announced plan change);
   - [claude-code-and-max-plan-facts.md](../../docs/research/external/platform-facts/claude-code-and-max-plan-facts.md)
     §4 and [distilled/external.md](../../docs/research/distilled/external.md) §4's "still
     officially unanswered" note — cross-reference the internal measurement (the *official*
     question stays open; we now have our own answer).

## Run 2 — pre-registered sizing (2026-07-12, before execution)

Run 1 (artifact:
[cache-weight-experiment-2026-07-12](../../docs/research/internal/cache-weight-experiment-2026-07-12/RESULTS.md))
settled direction (full weight excluded) but not magnitude: the meter is integer-quantized and
both arms landed inside ~1 point. Run 2 is the same design, sized from run 1's measured
constants (2.211 tok/word; ~22.2k fresh overhead per turn; 1 meter point ≈ 207–621k weighted
tokens):

- **Parameters: `N=28`, `F=2500`, model pinned `claude-opus-4-8`, both arms.** Arm B expected
  fresh ≈ 2.88M tokens (9.3× run 1) → **ΔB ≈ 4.6–13.9 points**; final-turn context 177.7k
  (22k margin under the 200k limit — the binding constraint that rules out larger F at this N).
  Estimated cost ≈ $17; ≈ 10–20 min per arm (the runner prints `wrote …turn-N.json` per turn).
- **Solve with ACTUAL token counts** (run 1's lesson: overhead matters; the idealized 5F/15F
  form is retired): with `fresh = input + cache_creation` and `reads = cache_read` from
  `summarize`, under cache-write window-weight v=1,
  `w = (ΔA/ΔB · fresh_B − fresh_A) / reads_A`.
  Sensitivity: writes are ~6% of arm A's mix, so the untested v ∈ [1, 1.25] shifts w by ≤0.02.
  Quantization propagates to roughly **±0.06–0.16 on w** depending on where ΔB lands.
- **Build rule:** record `claude --version` at run time; if it differs from the last verified
  build, run the one-turn `dry-run` in the *prior* window first (schema decay is
  vendor-build).
- Three readings as in run 1 (baseline / between arms / final), Haiku for the reading
  sessions, total account silence during the arms.

## Run 2 — result (2026-07-13, executed as pre-registered; T1 settled)

Artifact: [cache-weight-experiment-2026-07-13](../../docs/research/internal/cache-weight-experiment-2026-07-13/RESULTS.md).
One deviation, covered by the Controls section's own contingency: baseline was **3**, not a
fresh window — analysis on deltas. Readings 3 → 3 → 10; token totals as sized (arm B
2,898,461 fresh; arm A 2,720,679 reads + 177,087 fresh). Solve: **w < 0.1125** (v=1; v=1.25
*tightens* it to 0.096), point estimate pins to **0**; w = 0.5 and w = 1 excluded outright.
Window capacity ≈ **36.2–48.3M weighted tokens / 5h** (nests inside run 1's 21–62M; the
linear model retro-predicts run 1's deltas correctly across the 9.3× scale-up). Both runs on
build 2.1.207, `claude-opus-4-8`, $17.63 combined for run 2. The question this document was
written to answer is answered: **cache reads are discounted against the window by ≥ ~9×.**
Re-run trigger: `vendor-policy` decay — any announced plan/limits change.

## Files

- [run_cache_weight_experiment.sh](run_cache_weight_experiment.sh) — the runner (`gen-filler` and
  `summarize` are free/local; `dry-run`/`arm-a`/`arm-b` call `claude -p` and spend real quota).
