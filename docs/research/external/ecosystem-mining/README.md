# Ecosystem mining — index

**Produced:** 2026-07-06

**Purpose:** Mine the popular Claude Code agent-tooling ecosystem for (a) mechanisms worth
importing into cc-agent-harness and (b) PR-sized contribution opportunities where the
harness's assets fill verified gaps. **Method:** 11 popular repos cloned locally
(gstack, mattpocock/skills, no-mistakes, everythingclaudecode, andrej-karpathy-skills,
caveman, planning-with-files, alirezarezvani/claude-skills, superpowers, career-ops,
ruflo), analyzed by parallel per-repo analysts, then synthesized into five theme docs
and a ranked capstone. Claims are grounded in file-path citations to the clones;
measured vs marketing evidence is flagged throughout.

## Docs

**Start here → [contribution-opportunities.md](contribution-opportunities.md)** —
capstone: 8 moves ranked by value × asset leverage ÷ effort, weighted by demonstrated
PR-friendliness, plus quick hits, an explicit "not worth it" list, and a sequencing
plan where every PR is a slice of one of two standalone products.

- [landscape.md](landscape.md) — per-repo profiles (popularity, PR-friendliness,
  steal-worthy mechanisms, gotchas) plus a gap map placing each harness asset onto
  verified ecosystem absences with file-level insertion points.
- [verification-and-blind-gating.md](verification-and-blind-gating.md) — the
  reward-hacking hole is universal: in all 11 repos the implementer can see and edit
  the tests that judge it; blind validation is ecosystem-unique to the harness.
- [spec-elicitation-and-planning.md](spec-elicitation-and-planning.md) — the
  one-question-at-a-time interview is a commoditized category; the open slice is the
  exit side (machine-checkable determinacy bar, spec-to-test traceability).
- [parallelization-and-decomposition.md](parallelization-and-decomposition.md) —
  stub-and-seams gets a qualified yes: seams must be determinate enough that
  implementation is transcription, with a serial strong-model integrator.
- [limits-resume-and-wake.md](limits-resume-and-wake.md) — 0/11 repos have rate-window
  awareness or wake-on-reset; verdict is BUILD a wake daemon that wakes into a fresh
  session from disk state, not a cache-cold fat-transcript resume.
- [memory-and-lessons.md](memory-and-lessons.md) — ecosystem consensus is files-on-disk
  with recurrence-based promotion and structural filtering; nobody measures whether
  stored lessons improve outcomes.

## Top takeaways

1. **Routing matters more than idea quality.** PR-friendliness is bimodal: genuinely
   open (career-ops, no-mistakes, planning-with-files, ECC upstream, claude-skills,
   caveman, gstack) vs effectively closed (mattpocock/skills: zero external merges
   ever; superpowers: 94% rejection; ruflo: ~97% single-author; karpathy-skills:
   stale). Send issues, not PRs, to the closed set.
2. **Blind validation is the unique asset — but ship it in slices.** All 11 repos let
   the implementer author/edit its own judge. The plays: no-mistakes' modified-test
   tripwire (S), planning-with-files' documented-but-unimplemented AcceptanceCheck (M),
   and a standalone vault CLI — each preceded by a reproducible seeded demo of
   test-weakening plus guard catch-rate, which powers every PR body.
3. **Rate-window awareness is the clearest demand/supply gap** (0/11 repos, six open
   feature requests). The #1 ranked move overall is career-ops `--wait-for-reset` —
   its batch-runner already greps the reset timestamp and throws it away. The
   standalone verdict is a wake-on-reset daemon (parkfile + LaunchAgent waker +
   fresh-session-from-ledger wake), hedged against the paused plan change.
4. **Two hypothesis corrections from the landscape read:** the planning interview is a
   crowded category (five repos ship real interrogation loops) — the differentiated
   determinacy-probe/traceability slice is only buildable in-harness — and
   disk-is-the-memory resumability is now consensus (~5 independent convergences),
   not a moat.
5. **Cache economics is a 1-in-11 discipline with named bugs to fix:** only
   planning-with-files engineers for prompt-cache stability; ECC's cost-tracker and
   ruflo's gateway misprice cache token classes, and career-ops defeats its own prefix
   caching — all concrete S-sized PRs carrying the harness's cache finding.
6. **The evidence bar cuts both ways.** Ecosystem claims are mostly marketing-grade,
   and the honest-measurement repos (caveman, superpowers, planning-with-files) are
   the ones soliciting data — but the researcher's own cache/variance findings are
   single-source and must ship with methodology to clear the operator's own rule.
7. **Sequencing: every PR is a slice of a standalone product** (wake daemon or blind
   vault), so upstream credibility and the launches compound rather than compete.
   Mandatory pre-flight for all PRs: re-fetch upstream — several local clones are
   stale (ECC is ~4 months behind and its origin is a fork).
