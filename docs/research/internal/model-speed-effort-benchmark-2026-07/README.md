# Claude Code model speed / effort benchmark (July 2026)

Empirical benchmark of the four models offered in Claude Code — **Fable 5, Opus 4.8,
Sonnet 5, Haiku 4.5** — measuring latency, throughput, token spend, correctness, and
relative cost, with a focus on **coding tasks at `xhigh` effort** (Claude Code's
default/recommended effort level for coding and agentic work).

- **Date:** 2026-07-05
- **Harness:** headless `claude -p` (Claude Code CLI v2.1.201) on macOS (Darwin 25.5.0),
  billed through the operator's Claude Code account
- **Total spend:** ~$15 across 73 runs
- **Raw data:** `results/` (one JSON per run, as emitted by `--output-format json`:
  `duration_ms`, `duration_api_ms`, `ttft_stream_ms`, `usage`, `total_cost_usd`,
  `num_turns`, full response text)
- **Reproduction:** `harness/` (run scripts, task fixtures, graders)

## Purpose and context

Questions this was built to answer, in the order they were asked:

1. How fast are the four Claude Code models at each effort level? (round 1–2)
2. Narrowed by the operator: **latency / throughput / correctness for coding tasks at
   `xhigh` only** — per official guidance that `xhigh` is the right setting for
   coding/agentic work on Fable 5 / Opus 4.8 / Sonnet 5. (round 3)
3. Constraints the operator imposed on interpretation:
   - **Token-spend variance is real**: the same model + task + effort can spend very
     different token counts across attempts, so cells need repeated runs and
     single-run comparisons are suspect.
   - **Cost must be read as ratios, not dollars** (prices change regularly). Per-token
     price ladder at test time (output $/MTok: Fable 50, Opus 25, Sonnet 10 intro /
     15 from 2026-09-01, Haiku 5):

     | Haiku 4.5 | Sonnet 5 (intro) | Opus 4.8 | Fable 5 |
     |---|---|---|---|
     | 1× | 2× | 5× | 10× |

     Same ladder holds for input and cache rates. So "Fable is token-efficient" is
     only valuable if its efficiency beats its price multiple.

Background facts that shaped the design (from Anthropic docs/skill reference):

- Effort (`low`/`medium`/`high`/`xhigh`/`max`) is supported on Fable 5, Opus 4.6+,
  Sonnet 5/4.6. **Not supported on Haiku 4.5** (the API rejects it; the CLI silently
  tolerates `--effort` for haiku with no behavioral change — verified in round 1).
- All three big models use adaptive thinking: effort is a thinking-budget dial the
  model spends *only when the task warrants it*.
- Fable 5 / Opus 4.8 / Sonnet 5 use the newer tokenizer (~30% more tokens for the same
  text); Haiku 4.5 uses the older one. Cross-model token counts are therefore not
  directly comparable; billed cost is.
- Fast mode (`/fast`, Opus 4.8 at 2×/2× price for up to 2.5× output speed) was **not**
  benchmarked.

## Method

Each run: `claude -p "<prompt>" --model <m> [--effort <e>] --output-format json`
from a clean directory, with `--strict-mcp-config --mcp-config '{"mcpServers":{}}'`.
Generation-only tasks additionally used `--tools ""` (no tool schemas, single turn).
The agentic task allowed `Bash(python*/pytest*) Edit Read Write Glob Grep` via
`--allowedTools`. Runs executed 4–5 in parallel. Timing from the CLI's own
`duration_api_ms` / `ttft_stream_ms`; cost from `total_cost_usd`.

### Rounds

| Round | Question | Design |
|---|---|---|
| 1 (`run_bench.sh`) | Baseline speed + does effort matter on easy tasks? | Easy combinatorics Q + 300-word prose task; fable/opus/sonnet × all 5 efforts + haiku; 21 runs |
| 2 (`run_bench2.sh`) | Effort effect on a genuinely thinking-heavy task | Sum of Harshad numbers in (100,500), ground truth 26794; all 5 efforts; 16 runs |
| 3 (`run_bench3.sh` + `run_bench3b.sh`) | **Coding at xhigh: latency/throughput/correctness/cost, with variance** | 3 coding tasks × 4 models × 3 reps = 36 runs |

### Round-3 coding tasks (all graded mechanically; graders in `harness/`)

- **GEN** — write `evaluate(expr) -> float` (arith expression evaluator; unary minus vs
  right-assoc `**`, ValueError on malformed input; no eval/ast). Graded by hidden
  16-test pytest suite (`fixtures/test_eval_hidden.py`).
- **FIX** — agentic: isolated copy of `fixtures/fixws/` containing `wordwrap.py` with 4
  planted bugs (off-by-one in line-length check, missing long-word breaking, `['']`
  for empty input, missing width<1 ValueError) and a 10-test suite (5 failing at
  start). Model must run pytest and edit until green; grader re-runs pytest and
  checks the test file wasn't modified.
- **HARD** — write `match(pattern, text) -> bool`: a mini regex engine (`. * + ? | ()`
  char classes, negation, full-match semantics, real backtracking; no imports).
  Graded against `re.fullmatch` on a 36-case battery (in `grade_hard.py`), run in a
  subprocess with timeout to catch hangs.

## Results

### Round 1 — baseline speed (effort-independent)

| Model | TTFT | Steady-state generation (from long round-2 outputs) |
|---|---|---|
| Haiku 4.5 | ~1.0 s | ~255 tok/s |
| Sonnet 5 | ~1.0 s (0.9–1.2 s in every run, most consistent) | ~140–155 tok/s |
| Opus 4.8 | ~1.1–1.3 s (one 6.3 s outlier) | ~105–115 tok/s |
| Fable 5 | ~2.4–3.6 s (consistently slowest to first token) | ~100–118 tok/s |

On an **easy** reasoning task, effort made almost no difference (3–10 s at every
level, tiny thinking spend) — adaptive thinking declines to spend the budget.

### Round 2 — effort effect on a hard reasoning task (ground truth 26794)

| Effort | Sonnet 5 | Opus 4.8 | Fable 5 |
|---|---|---|---|
| low | 37 s / 5.2k tok / **wrong** | 45 s / 4.9k tok / ✓ | 43 s / 4.4k tok / ✓ |
| medium | 37 s / 5.5k tok / **wrong** | 67 s / 6.9k tok / ✓ | 56 s / 5.7k tok / ✓ |
| high | 130 s / 17.7k tok / ✓ | 64 s / 7.3k tok / ✓ | 65 s / 7.2k tok / ✓ |
| xhigh | 143 s / 22.1k tok / ✓ | 111 s / 11.7k tok / ✓ | 82 s / 9.1k tok / ✓ |
| max | 155 s / 22.7k tok / ✓ | 141 s / 15.9k tok / ✓ | 102 s / 12.0k tok / ✓ |

Haiku (no effort control): 61 s / 15.5k tok / ✓ / $0.09 — solved it by writing all
reasoning as visible text. Effort scaling low→max: Sonnet 4.2×, Opus 3.1×, Fable 2.4×.

### Round 3 — coding at xhigh (median [min–max] over 3 reps)

**Correctness: saturated.** All 4 models solved all 3 tasks in all 3 reps — 36/36
fully-correct runs, including Haiku on the regex engine. **Correction 2026-07-12** (see
bottom): 24 of these 36 (GEN + HARD) are re-derived from the committed artifacts by the
corrected graders; the 12 FIX runs are no longer checkable (workspaces not preserved).
Prompt-scale coding does not
discriminate the 2026 lineup; separation only appears at repo-scale / long-horizon
work (see published agentic benchmarks, e.g. SWE-bench-Verified, where Fable leads).

| Task | Metric | Haiku | Sonnet 5 | Opus 4.8 | Fable 5 |
|---|---|---|---|---|---|
| GEN | api_s | 171 [129–193] | 84 [68–92] | 74 [68–78] | **45** [40–75] |
| GEN | out tok | 21.8k | 9.6k | 6.6k | **4.1k** |
| GEN | cost $ | 0.123 | 0.182 | 0.197 | 0.289 |
| HARD | api_s | 86 [83–118] | 93 [91–113] | 74 [55–190] | **62** [54–69] |
| HARD | out tok | 14.6k | 10.5k | 6.2k | **5.3k** |
| HARD | cost $ | 0.087 | 0.196 | 0.186 | 0.356 |
| FIX | api_s | **35** [25–36] | 37 [31–37] | 50 [49–59] | 52 [50–59] |
| FIX | out tok | 3.2k | 2.6k | 3.5k | **2.2k** |
| FIX | cost $ | 0.057 | 0.199 | 0.279 | 0.497 |

**Cost per solved task, normalized to Sonnet = 1.0** (Sonnet at intro pricing):

| Task | Haiku (1× price) | Sonnet (2×) | Opus (5×) | Fable (10×) |
|---|---|---|---|---|
| GEN | 0.68 | 1.0 | 1.08 | 1.59 |
| HARD | 0.44 | 1.0 | **0.95** | 1.82 |
| FIX | **0.29** | 1.0 | 1.40 | 2.50 |

## Findings

1. **Speed ranking inverts by task regime.** Thinking-dominated coding (GEN, HARD):
   Fable is the *fastest model wall-clock* — Opus-class tok/s but 3–5× fewer tokens to
   a correct answer. Haiku is slowest there despite ~255 tok/s (it brute-forces in
   visible text). Tool-loop chores (FIX): Sonnet/Haiku win (~36 s vs ~51 s) — TTFT and
   per-turn overhead dominate when little thinking is needed.
2. **Token-spend variance is large and model-dependent** (confirming the operator's
   prior): up to 3× across identical reps. Worst: Opus on HARD, 5.0k–15.3k tok,
   55–190 s, $0.16–$0.42. Fable was the most consistent model. n=3 leaves wide error
   bars; treat medians as indicative.
3. **Token efficiency largely offsets the price ladder at the top.** Actual cost per
   solved thinking-heavy task: Fable ≈ 1.6–1.8× Sonnet (not 5×); Opus ≈ Sonnet
   (its 2.5× price ÷ ~2.5× fewer tokens ≈ 1). On no-thinking chores the ladder passes
   straight through (Fable 2.5× Sonnet; Haiku 3.5× cheaper than Sonnet). After
   Sonnet's Sept 2026 price rise (+50%), Fable's premium on thinking-heavy work
   shrinks to ~1.1–1.7× Sonnet.
4. **Effort is a thinking-budget dial that only costs time on hard tasks** (round 1
   vs 2). At fixed xhigh, the dial is effectively self-adjusting per task.
5. **Effort ≠ correctness insurance at the low end** (round 2): Sonnet was wrong at
   low/medium where Opus and Fable at *low* were both correct and cheap-in-tokens —
   consistent with Anthropic's claim that Fable at low often beats prior models at
   higher effort.
6. **Haiku has one speed.** No effort support; CLI `--effort` silently ignored.
   Fast + cheapest, and at prompt-scale coding it lost nothing on correctness.

### Practical routing implications (coding, xhigh)

- Hard self-contained problems → **Fable** (fastest, most consistent, ~1.6–1.8× Sonnet
  cost) or **Opus** as the value pick (≈Sonnet cost, near-Fable speed).
- Routine agentic chores (run tests, small fixes) → **Sonnet**; **Haiku** if cost
  dominates (same wall time, ~⅓ the cost, no correctness loss at this scale).
- Choose by task horizon, not "can it code" — use long-horizon benchmarks for
  correctness-critical routing decisions.

## Caveats

- n=3 per cell; 4–5 runs in parallel on one machine; single day; subscription path.
- Timing/cost include Claude Code's system prompt and its cache writes —
  representative of Claude Code usage, **not** raw API calls.
- Correctness saturation is a statement about *these* task sizes, not model parity.
- Sonnet costs reflect intro pricing ($2/$10) — CLI-reported `total_cost_usd`.
- TTFT figures include first-request cache-write behavior; treat as indicative.
- Fast mode and Sonnet 4.6/Opus 4.7 (still selectable in some setups) not covered.

## Reproduction

```sh
cd harness
bash run_bench.sh     # round 1  (21 runs, ~$1)
bash run_bench2.sh    # round 2  (16 runs, ~$5)
bash run_bench3.sh    # round 3  GEN+FIX (24 runs, ~$6)
bash run_bench3b.sh   # round 3b HARD    (12 runs, ~$3)
python3 grade.py      # grades GEN/FIX, prints aggregate
python3 grade_hard.py # grades HARD against re.fullmatch battery
```

Scripts expect `claude` at `~/.local/bin/claude` and `python3` + `pytest` on PATH.
Each script writes `result*_<task>_<model>_<effort|rep>.json` beside itself; graders
create `grading/` and `ws_fix_*` working dirs. The graders find round-3 results in
either layout (beside the script, or the committed `results/round3-coding-xhigh/`) and
derive test totals from the fixture files — both fixed 2026-07-12 (see Correction).
Note FIX is only gradeable in the same session as `run_bench3.sh`: grading reads the
`ws_fix_*` workspaces the run creates, and those are not preserved in this tree.

## Correction (2026-07-12)

An independent critical review of `docs/` flagged that `grade.py` as committed could not
have produced the headline correctness result. Re-verification confirmed three defects:

- **Off-by-one grader total:** `grade.py` hardcoded `total = 17` for GEN, but
  `fixtures/test_eval_hidden.py` has **16** tests (16 at first commit; never changed).
  `solved` requires `passed == total`, so a perfect 16/16 GEN run could never grade as
  solved. The committed grader therefore cannot print the GEN "solved" column of the
  36/36 claim; how that tally was originally produced is not recoverable from the tree.
- **Broken reproduction path:** both graders globbed `result3_*.json` beside the script
  (the original scratchpad layout), so against the committed layout they graded zero
  runs. Disclosed as a "known wart," but a broken A3 reproduction path all the same.
- **Latent crash:** `result3_hard_*.json` matches `grade.py`'s glob but not its regex —
  `m.groups()` on `None` raises `AttributeError` when hard results sit in the same dir.

All three are now fixed in `grade.py` / `grade_hard.py` (totals derived from fixtures,
both layouts searched, non-matching files skipped, FIX non-reproducibility stated
explicitly). Re-run of the corrected graders against this tree — full transcript in
`results/regrade-2026-07-12.txt`:

| Task | Re-derivable from committed artifacts? | Result |
|---|---|---|
| GEN (12 runs) | yes — solutions in result JSONs + hidden suite | **12/12 solved, 16/16 tests each** |
| HARD (12 runs) | yes — solutions in result JSONs + 36-case battery | **12/12 solved, 36/36 cases each** |
| FIX (12 runs) | **no** — `ws_fix_*` workspaces never committed | unverifiable; original run-day observation only |

The headline should be read as: **24/24 re-verified correct; 36/36 as originally
observed, of which the 12 FIX runs are no longer checkable.** Latency/token/cost numbers
are unaffected — they come directly from the CLI-emitted result JSONs. Evidence-grading
consequence: the correctness rows qualify as directly-reproducible (A3) only for GEN and
HARD; FIX correctness is a single-source run-day claim. Logged in
`docs/research/internal/v2-ledger.jsonl` (kind `correction`) and reflected in
[distilled/internal.md](../../distilled/internal.md).
