# Platform facts — the vendor substrate

**Scope.** Ground truth about the platform the harness runs on (Claude Code + the Max plan):
cache mechanics, rate-window structure, quota introspection surfaces, usage credits,
credentials, and the capacity/regime changelog. Not a design subtopic — the substrate every
subtopic's numbers are denominated in.

**Coverage: ● rich — and the most volatile folder in the corpus.** Everything here is
`vendor-build` or `vendor-policy` decay class: re-verify on build updates and plan changes,
never trust a stale read. This folder has produced three official-but-wrong catches
(see [../../distilled/README.md](../../distilled/README.md)).

## Holdings

- [claude-code-and-max-plan-facts.md](claude-code-and-max-plan-facts.md) — prompt-cache
  TTL/keys/invalidation, window mechanics (5-hour + weekly + Sonnet-only), the statusline
  feed, quota-surface absences, usage credits, the paused Agent-SDK regime change, the
  capacity changelog.

## Related material elsewhere

- [../../distilled/external.md](../../distilled/external.md) — the Tier-A subset (official
  *commitments* vs official *mechanism* claims).
- `tools/budget-governor/probe-spawn-portability*.md` — the re-run-per-build probes that
  keep mechanism claims honest.
- README recheck schedule ([../../README.md](../../README.md)) — dated triggers.

## Open questions

- The cache-read subscription-weight question (`[contested]`) — settled only by the written,
  unexecuted experiment in `tools/budget-governor/`.
- The paused Agent-SDK billing change — standing recheck; if it un-pauses, O1's denominator
  changes for headless runs.
