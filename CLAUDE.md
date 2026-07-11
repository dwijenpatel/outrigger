# Session notes — evidence-first harness design

**Mode:** research-and-design. The v2 harness will be built **from scratch**; nothing is
implemented here yet. The current design surface is
[docs/design/evidence-based-harness.md](docs/design/evidence-based-harness.md); the evidence
base is [docs/research/distilled/](docs/research/distilled/README.md). The repo was
**reincarnated 2026-07-11** — v1's conclusions live in [docs/attic/](docs/attic/README.md)
(*prior art to argue against, never a source of defaults*), v1's code at git tag `v1-attic`.
Continuity record + executed manifest: [docs/reincarnation-plan.md](docs/reincarnation-plan.md).

## Standing operator directives

- **A design decision enters only with a distilled Tier-A citation** — otherwise it is
  Provisional (named promotion trigger) or TBD (named settling experiment). "The old design
  did it" is not a warrant. Do not over-design.
- **Loosely-coupled, composable artifacts** (design R5/D15): every machinery piece does one
  thing well, runs standalone, and composes via schema'd file contracts + exit codes; no
  artifact may require another artifact's existence, in either direction. No bundling.
- **Improvements are evidence-gated, permanently** (design R6): post-creation harness changes
  enter exactly like design decisions — new external or internal highly-reliable evidence →
  design doc → artifacts. No other channel.
- **Sub-agents use the `Opus 4.8` model, not `Fable 5`.**
- **Git discipline:** never commit directly to `main` — feature branch → commit → `--ff-only`
  merge → delete branch.
- **Never run** `tools/budget-governor/run_cache_weight_experiment.sh` `dry-run`/`arm-a`/`arm-b`
  — it spends real Max-plan quota. That measurement (T1) is operator-run only.
- Operator comfort is not a goal; gates are judged by errors caught (design R3).

## Environment

- **Shell is zsh.** Never use bare `=`-prefixed words (`echo ===` dies: zsh expands `=cmd` to a
  command path). Use `---` separators. zsh for-loops need explicit arrays; macOS lacks
  `realpath -m`.
- After editing docs, run the corpus guard: `python3 -m unittest tests.test_reference -q`
  (every relative markdown link must resolve).
