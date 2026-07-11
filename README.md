# cc-agent-harness

Research and design for a coding-agent harness on Claude Code, built **evidence-first**: a
primary-sourced research corpus covering the 14 subtopics of harness design, a graded
"highly-reliable subset" distillation, and a from-scratch design plan in which **every decision
cites the Tier-A evidence that licenses it** — and says TBD where none exists.

This repo was **reincarnated on 2026-07-11**: the v1 harness (design, implementation plan, ~27
Python modules, 8 enforcement hooks, worker roles, skills) was retired after its own post-mortem
— the machine cost tokens to save tokens — and the next harness will be built from scratch. What
survived is exactly what the evidence rules said should survive: *our defeats are evidence; our
decisions are not.* The pilot defect ledgers, falsified predictions, and measurement artifacts
stayed; the v1 conclusions moved to [docs/attic/](docs/attic/README.md); the v1 code lives at
git tag **`v1-attic`**.

## Start here

| Document | What it is |
|---|---|
| [docs/design/evidence-based-harness.md](docs/design/evidence-based-harness.md) | **The current design surface** (draft 1): 14 Decided/Provisional/TBD decisions, an evidence-backed omissions table, the T1–T10 experiment ledger, sequencing |
| [docs/design/operator-walkthrough.md](docs/design/operator-walkthrough.md) | The same design as a plain-language day-in-the-operator's-life, TBDs called out inline |
| [docs/research/distilled/](docs/research/distilled/README.md) | The Tier-A evidence base and the grading method (warrant × incentive × decay) that decides what qualifies |
| [docs/research/README.md](docs/research/README.md) | The full corpus index: 14 external subtopics, internal pilot evidence, corrections ledger, recheck schedule |
| [docs/reincarnation-plan.md](docs/reincarnation-plan.md) | The continuity record: standing operator directives, the executed cleanup manifest, external-assets inventory |
| [docs/terminology.md](docs/terminology.md) | Every acronym and coined term across the corpus |

## Repo layout

| Path | What |
|---|---|
| [docs/research/external/](docs/research/external/) | The world's evidence, organized into 14 harness-design subtopics — every claim tagged by how it was established |
| [docs/research/internal/](docs/research/internal/) | Our own evidence: pilot firing ledgers, the salvaged P3v2-5 artifact set ([pilot-3-artifacts/](docs/research/internal/pilot-3-artifacts/README.md)), the committed model/effort benchmark |
| [docs/research/distilled/](docs/research/distilled/README.md) | Tier-A only — external, internal, and the method |
| [docs/design/](docs/design/) | The evidence-based design plan and its operator walkthrough |
| [docs/attic/](docs/attic/README.md) | The superseded v1 design, plan, and API reference — *prior art to argue against, never a source of defaults* |
| [tools/run-ledger/](tools/run-ledger/README.md) | **v2 artifact #1** — append-only, schema-validated JSONL measurement ledger (D14): the home of every null arm, write-back, and pre-registered prediction |
| [tools/merge-gate/](tools/merge-gate/README.md) | **v2 artifact #2** — blocking gate judging the *merged* tree in a clean worktree (D1/D5), stamped reports, `verify` anti-merge-skew interlock |
| [tools/budget-governor/](tools/budget-governor/README.md) | Preserved measurement instruments: the spawn-portability probe and the **unexecuted cache-weight experiment (T1** — quota-costing, operator-run only**)** |
| `tests/` | The corpus link/reference guard (`python3 -m unittest tests.test_reference -q`) |

## Working in this repo

- Branch → commit → `--ff-only` merge to `main`; never commit to `main` directly.
- A design decision enters [the design plan](docs/design/evidence-based-harness.md) only with a
  [distilled](docs/research/distilled/README.md) Tier-A citation; otherwise it is Provisional
  (named promotion trigger) or TBD (named settling experiment).
- After editing docs, run the link guard: `python3 -m unittest tests.test_reference -q`.
- See [CLAUDE.md](CLAUDE.md) for session notes and standing directives.

## License

MIT — see [LICENSE](LICENSE).
