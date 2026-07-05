# Harness repo — session notes

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
