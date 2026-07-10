# Re-validation reuse & leakage — prior art behind the held-out vault's economics

The research behind the design's re-validation reuse decisions
([../design/token-time-optimized-harness.md](../../../design/token-time-optimized-harness.md) §5.5):
safe incremental re-validation, corpus persistence and freshness, and the leakage budget for
adaptive reuse of a hidden set. Load-bearing facts only — each theme lists the transferable
pattern and its named tradeoff. *How* the vault is kept unreadable is a separate question,
covered in [isolation-and-sandboxing.md](../isolation/isolation-and-sandboxing.md).

**Provenance:** prior-art digest, 2026-07-03. `[E]` = established in the cited primary source;
`[I]` = inference/synthesis. Fidelity note in the consolidated ledger ([README.md](../../README.md)).

---

## 1. The agentic-coding architecture (validates the design)

The published pattern is **a cheap, scoped self-check in the agent's inner loop + a full clean-room
gate with tests HIDDEN from the agent** — exactly the design's implementer-vs-blind-validator split.

- **SWE-bench** — per instance: clean base commit in a **sandboxed Docker image**, apply the model's
  patch, apply a **withheld test patch**, run it. Two hidden sets: `FAIL_TO_PASS` (proves the fix) +
  `PASS_TO_PASS` (**median 51** regression tests that must stay green). The agent never sees them. `[E]`
  — https://arxiv.org/abs/2310.06770
- **SWE-agent** — the agent's OWN verification is just re-running a **self-written reproduction script**,
  not the project suite; the trustworthy judgment is the hidden gate it can't scope or game. `[E]` —
  https://arxiv.org/abs/2405.15793
- **OpenHands/CodeAct** runs "tests after every change" in a per-task Docker sandbox (scope agent-chosen);
  **SapFix** (Meta) validates fixes by running **Sapienz-selected** tests, not the full suite, with human
  approval as the final gate; **Reflexion** verifies against self-written tests. `[E]` —
  https://engineering.fb.com/2018/09/13/developer-tools/finding-and-fixing-software-bugs-automatically-with-sapfix-and-sapienz/
  · https://arxiv.org/abs/2303.11366
- `[I]` **No published system combines *safe RTS on the inner loop* with a *full hidden gate*** — that is
  the novel, defensible spot the held-out-vault design occupies.

## 2. Safe incremental re-validation (Regression Test Selection / Test Impact Analysis)

The mature technique for "don't re-run unchanged work," with a precise safety property.

- **Ekstazi** — dynamic file-level RTS. **SAFE** RTS = "**never omits a test whose behavior may be affected
  by the change**"; a test is skipped only if none of its dynamically-tracked dependent files changed
  (~84% suite reduction reported). `[E]` — https://users.ece.utexas.edu/~gligoric/papers/GligoricETAL15Ekstazi.pdf
- **Microsoft TIA (Azure Pipelines)** — runs impacted + previously-failing + newly-added tests via an
  instrumented test→source map; **safe fallback runs ALL tests** for anything it can't reason about
  (non-managed code, etc.); recommends periodic full runs. `[E]` —
  https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis
- **Facebook Predictive Test Selection** (Machalica et al., ICSE-SEIP 2019) — ML picks tests per diff;
  in production **cuts test cost ~2× while still reporting >99.9% of faulty changes** (probabilistic, not
  provably safe). `[E]` — https://arxiv.org/abs/1810.05286
- **STARTS** — static class-level RTS; **can be unsafe** when the test→change path is only reachable via
  reflection (static deps ≠ runtime deps). `[E]` — https://www.cs.cornell.edu/~legunsen/pubs/LegunsenETAL17STARTS.pdf
- **Takeaway:** adopt the **safe** variant (Ekstazi/TIA property + full-run fallback) so escapes don't rise;
  predictive selection's 2× is the upper bound on savings if we ever accept a tiny miss rate.

## 3. Persisted adversarial corpora: persist → replay → grow → minimize

Every field persists the corpus separately and reuses it; the reuse trigger everyone converges on is
**"did the covering code/test change?"** — replay unchanged, re-derive changed.

- **libFuzzer / AFL(++)** — the corpus is a **directory**; a mutation hitting a **previously-uncovered path
  is saved back** to the first corpus dir; `-merge=1` / `afl-cmin` **minimize to a coverage-preserving
  subset**; `-reload`/`AFL_AUTORESUME` replay. `[E]` — https://llvm.org/docs/LibFuzzer.html ·
  https://aflplus.plus/docs/fuzzing_in_depth/
- **OSS-Fuzz/ClusterFuzz** — corpus persists in GCS, grows across runs, **pruned daily** (`CORPUS_PRUNE`);
  CIFuzz reuses the accumulated corpus for "regression testing for free." `[E]` —
  https://google.github.io/oss-fuzz/advanced-topics/corpora/ · https://google.github.io/clusterfuzz/reference/job-definition/
- **Mutation testing incremental** — StrykerJS (`--incremental`, `reports/stryker-incremental.json`), PIT
  (history files), mutmut v3 (`mutants/` dir). Rule: **a killed mutant whose covering test is unchanged
  stays killed; re-test only changed functions.** `[E]` — https://stryker-mutator.io/docs/stryker-js/incremental/
  · https://pitest.org/quickstart/incremental_analysis/ · https://mutmut.readthedocs.io/
- **Property-testing regression DBs** — Hypothesis **auto-persists** minimal failing examples to
  `.hypothesis/examples` and **replays them first** (`Phase.reuse` before `Phase.generate`); fast-check has
  **no auto DB** — manual `seed`/`path`/`examples`. `[E]` — https://hypothesis.readthedocs.io/en/latest/database.html
  · https://fast-check.dev/docs/advanced/fuzzing/
- **Build-system test caching** — Bazel/Go/Nx/Turbo/Gradle key a **content hash of declared inputs** and
  **replay stored output rather than re-run**. `[E]` — https://bazel.build/remote/caching · https://nx.dev/docs/concepts/how-caching-works

## 4. Freshness is load-bearing — a frozen corpus is a saturated corpus

Replay = regression floor; it CANNOT find a NEW hole. Find-power is in newly-generated cases.

- **Fuzzing** — find-power comes from **mutation + coverage feedback generating NEW inputs**; the stored
  corpus only **seeds** mutations; a campaign with **"no new path for a day/week → won't be fruitful"** is
  saturated. OSS-Fuzz's ever-growing 13k-vuln/50k-bug count is the anti-freeze evidence. `[E]` —
  https://llvm.org/docs/LibFuzzer.html · https://google.github.io/oss-fuzz/
- **Mutation validity** — a **fixed operator set misses real faults**: ~**27% of Defects4J real faults were
  not coupled** to any standard mutant (Just et al. FSE 2014); mutation-score↔real-fault-detection
  correlation is **weak once suite size is controlled** (Papadakis et al. ICSE 2018); most killable mutants
  aren't fault-revealing. `[E]` — https://homes.cs.washington.edu/~rjust/publ/mutants_real_faults_fse_2014.pdf
  · https://coinse.github.io/publications/pdfs/Papadakis2018hi.pdf
- **Dynamic benchmarks refresh continuously** — LiveCodeBench date-tags problems (evaluate only
  post-training-cutoff; caught DeepSeek's post-Sept-2023 cliff); LiveBench **replaces questions monthly**;
  Dynabench crafts model-fooling examples continuously. `[E]` — https://arxiv.org/abs/2403.07974 ·
  https://arxiv.org/abs/2406.19314
- **Takeaway:** the vault is a **regression floor, never a correctness proof**; always author FRESH
  adversarial tests on the CHANGED surface.

## 5. Reusing a fixed hidden set across adaptive iterations degrades it (and the fix)

The theory for "how many times can a held-out set be reused before it's gamed," and the mechanism.

- **The Ladder** (Blum & Hardt, ICML 2015) — a leaderboard that **only reveals a score beating the
  incumbent by > threshold η** has error growing only in **log k** (submissions); an un-thresholded oracle
  is **provably attackable** — k random submissions reach ~**√(k/n)** above chance from pure probing;
  Whitehill (2018) recovered all labels + rank #4/848 by probing a log-loss oracle. `[E]` —
  https://arxiv.org/abs/1502.04585 · https://arxiv.org/abs/1707.01825
- **Reusable Holdout / Thresholdout** (Dwork et al., *Science* 2015; STOC 2015) — a standard holdout's
  adaptive-reuse budget is ~**linear**; a **noise/threshold (differential-privacy) mechanism** extends it to
  **~quadratic-in-n overfitting events / exponential-in-n queries**. Demo: naive holdout reports 63% on a
  no-signal task (true 50%); Thresholdout stays at 50%. `[E]` — https://www.science.org/doi/10.1126/science.aaa9375
  · https://arxiv.org/abs/1411.2664
- **Adaptive-overfitting is milder than feared, but real** — fresh ImageNet/CIFAR test sets drop models
  11–14% / 3–15% (Recht et al. 2019, mostly distribution shift not adaptivity); GSM1k drops some LLMs up to
  ~13% with a memorization correlation (Scale AI 2024). `[E]` — https://arxiv.org/abs/1902.10811 ·
  https://arxiv.org/abs/2405.00332
- **Frozen-proxy failure is Goodhart / specification gaming** — optimizing hard against a fixed proxy
  satisfies its letter while missing intent (Manheim & Garrabrant taxonomy; DeepMind spec-gaming; Skalse
  et al. formal reward-hacking). `[E]` — https://arxiv.org/abs/1803.04585 ·
  https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/
- **Takeaways for the vault:** (a) **rate-limit reuse** as a leakage budget; (b) **rotate/refresh** the
  corpus; (c) for **security-critical surfaces keep FULL fresh re-derivation** — that's where a gamed
  frozen set is most dangerous.
