# Cache-read quota-weight experiment — protocol

Resolves design doc §10.2 / §12 open question #2, called out there as "the highest-value
experiment": does a cache-read token count against the Max-plan 5-hour/weekly windows at a
discount (API billing rate is ~10% of fresh input) or at near-full weight (what community
telemetry — `docs/research/claude-code-and-max-plan-facts.md` §4 — suggests)?

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
- **Identical filler content across arms**, generated once by `run_cache_weight_experiment.sh
  gen-filler` — determinism matters more than the content itself (verified: two invocations
  with the same word count produce byte-identical output).
- **Output held constant**: the "reply with exactly: OK" instruction keeps output tokens
  ~fixed per turn in both arms, so it isn't a confound.
- **Scale `F` up if the delta is too small to read.** Windows were doubled 2026-05-06 (design
  §10.3) and sizes aren't published, so a percentage-point delta that rounds to ~0 just means
  the filler was too small — rerun with a larger `F`, not a conclusion.
- **This measures the 5-hour window specifically**, via whatever surface you read
  `used_percentage` from (statusline JSON in an interactive session is the documented feed —
  `claude-code-and-max-plan-facts.md` §4 — but headless `claude -p`, which this script uses to
  make the workload scriptable, has no such surface itself). Two ways to close that gap:
  1. Run the arms via headless `claude -p` (this script does), and check the **weekly/5-hour
     `used_percentage` from an interactive session on the same account** immediately before and
     after each arm (open a second terminal, run `claude`, check the statusline or `/status`).
     Since the pool is shared account-wide, headless spend shows up there.
  2. Or skip headless entirely and paste the filler + instruction directly into an interactive
     session's turns, reading the statusline after each one — slower to script, but keeps
     everything in one surface.
- **Confirm the JSON schema before trusting the numbers.** `run_cache_weight_experiment.sh
  summarize`'s field paths are this tooling's best-effort guess at `claude -p --output-format
  json`'s per-turn usage schema (cross-referenced against the prompt-caching docs, not
  independently verified against a live call — that would itself cost quota). Run `dry-run`
  first and diff its raw JSON against the `summarize()` jq filter in the script; adjust the
  filter if the real keys differ before running the real arms.

## Procedure

1. **Dry run** (near-zero cost, sanity-checks the schema): `./run_cache_weight_experiment.sh
   dry-run`, then `jq . experiment-logs/<timestamp>-dry-run/turn-1.json` and confirm the fields
   `summarize()` expects are actually present at those paths; edit the script if not.
2. **Baseline.** In an interactive session on the same account, check `used_percentage` for the
   5-hour window. Note the timestamp.
3. **Arm A:** `./run_cache_weight_experiment.sh arm-a 5 6000` (5 turns, ~6,000-word filler per
   turn — scale up if step 1's dry run suggests the window is large enough that this would be
   too small to register). Immediately after, check `used_percentage` again (interactive
   session) and record the delta as `ΔA_window`. Also run
   `./run_cache_weight_experiment.sh summarize <arm-a logdir>` and record the token totals.
4. **Arm B:** `./run_cache_weight_experiment.sh arm-b 5 6000` (same N and F). Record
   `ΔB_window` and the token totals the same way.
5. **Compute** `ratio = ΔA_window / ΔB_window` and back out `w` from the table above.
6. **Write the result back** into design doc §10.2 (replace `[contested]` with the measured
   weight, or explicitly note the experiment was inconclusive and why) and into
   `docs/research/claude-code-and-max-plan-facts.md` §4, dated.
7. If `w` turns out non-trivial (> ~0.3), revisit the budget governor's default conservative
   cache-read weight (§5.1) — this experiment's whole purpose is to let you stop assuming and
   start calibrating it.

## Files

- [run_cache_weight_experiment.sh](run_cache_weight_experiment.sh) — the runner (`gen-filler` and
  `summarize` are free/local; `dry-run`/`arm-a`/`arm-b` call `claude -p` and spend real quota).
