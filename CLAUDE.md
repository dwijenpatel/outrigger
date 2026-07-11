# Harness repo — session notes

> **⚠ Phase change (2026-07-10) — read [docs/reincarnation-plan.md](docs/reincarnation-plan.md)
> first.** The project pivoted to an evidence-first, from-scratch redesign: current design
> surface is [docs/design/evidence-based-harness.md](docs/design/evidence-based-harness.md),
> evidence base is [docs/research/distilled/](docs/research/distilled/README.md). The
> reincarnation plan holds the ratified repo-cleanup manifest (NOT yet executed), the standing
> operator directives (Opus 4.8 for subagents; branch→ff-merge only; T1 experiment is
> operator-run; record-don't-fix machinery defects), and the external-assets inventory. The
> notes below describe the OLD machinery and remain valid only until the manifest executes.

- **Order of operations:** `plan-build` skill (interview → ratified plan) →
  `build-loop` skill (the firing). The build-loop refuses to start without
  `python3 -m harness.planning ready` passing.
- **Shell is zsh.** Never use bare `=`-prefixed words (`echo ===` dies:
  zsh expands `=cmd` to a command path). Use `---` separators.
- `state/` is created lazily at runtime and is gitignored — `ls state/`
  failing before a firing is normal.
- **The vault lives OUTSIDE this repo** (absolute path, e.g. a sibling
  directory). An in-repo vault dirties the tree and rides git history into
  worker worktrees.
- Machinery paths (`harness/`, `hooks/`, `.claude/`, `tools/`, `docs/plan/`,
  `docs/design/`) are gate-protected; product code goes elsewhere
  (e.g. `pilot/<name>/`).
- **Machinery is upstream-owned.** In a pilot clone, do NOT implement
  machinery fixes locally — two parallel implementations collided once
  already (P2-collision). Record the defect in the pilot's observations
  ledger; the fix lands in the parent repo and arrives by
  `git fetch <parent> main && git merge FETCH_HEAD`. Local machinery edits
  will be overwritten by that merge.
