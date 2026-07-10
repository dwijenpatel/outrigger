# cc-agent-harness

An agent harness on Claude Code that drives an approved technical design to a *correctly
implemented* codebase while explicitly optimizing two objectives: minimal token spend against
the Max plan's 5-hour and weekly rate windows, and minimal wall-clock time to correct
completion — subject to a correctness floor that is never traded away. The governing principle:
bind every mechanism to a built-in Claude Code primitive first (subagents, worktrees, hooks,
skills, caching); custom code is only the residue no built-in covers.

Full design: [docs/design/token-time-optimized-harness.md](docs/design/token-time-optimized-harness.md).

## Status

The design is not yet finalized. Until it is, **only [docs/research/](docs/research/) and
[docs/design/](docs/design/) are durable** — [docs/plan/implementation-plan.md](docs/plan/implementation-plan.md)
and all code (`harness/`, `tests/`, `tools/`) are disposable and get thrown away or redone as
the design moves. The harness does not ship agent-facing CLIs; the library modules below are
consumed by hooks and the build-loop skill, not exposed as standalone commands.

That said, Phases A–E of the implementation plan are built and passing: 27 library modules in
`harness/`, 8 enforcement hooks, 561 tests. See
[docs/plan/implementation-plan.md](docs/plan/implementation-plan.md) for the increment-by-increment
ledger and current "next up" pointer.

## How it works

1. **`plan-build`** ([.claude/skills/plan-build](.claude/skills/plan-build/SKILL.md)) — an
   interview that grills the operator one question at a time until the spec is determinate,
   then writes the ratified plan (`plan/tasks.json`, `plan/specs/*.md`, `plan/floors.json`,
   `plan/conventions.json`) a held-out test-author could work from with no guessing.
2. **`build-loop`** ([.claude/skills/build-loop](.claude/skills/build-loop/SKILL.md)) — the
   operator-started firing. Grinds the ratified plan task-by-task through context-isolated
   **implementer** and **validator** subagents (the spec is their only shared context),
   merging only through an objective gate. Durable state lives on disk (`state/`, gitignored)
   so any context can die and the loop resumes from files alone.
3. **The gate** (`harness/gate.py`) — clean-checkout reproduction, all-must-pass panel
   verdicts, risk floors checked against the actual diff. Nothing merges on a model's say-so.

The objective function is lexicographic, never scalarized:

| | Objective | Rule |
|---|---|---|
| **O0** | Correctness floor (hard constraint) | Validation escapes ≈ 0, enforced by machinery, not model virtue. Never traded for tokens or time. |
| **O1** | Token spend vs. the Max windows | Two rolling allowances (5-hour, weekly), shared account-wide — not $/task. |
| **O2** | Wall-clock to correct completion | Includes human latency (ratification round-trips, parked-blocker waits), not just compute. |

Design §2 has the full statement, including the one real O1↔O2 exchange (concurrent task
pipelines) and the two load-bearing rules on panel breadth and token-redundancy economizing.

## Repo layout

| Path | What |
|---|---|
| [docs/design/](docs/design/) | The founding design doc — durable. |
| [docs/research/](docs/research/) | Primary-sourced research backing every design decision, with a confidence-tagged corpus and [an index](docs/research/README.md) — durable. |
| [docs/plan/](docs/plan/) | The living implementation ledger tracking the design into code — disposable. |
| [docs/reference.md](docs/reference.md) | One-page API reference for the firing lifecycle (asserted against the code by `tests/test_reference.py` — it fails if this page drifts). |
| [docs/terminology.md](docs/terminology.md) | Every acronym and coined term across the design, plan, and research corpus — O0/O1/O2, the vault, blind validation, evidence tags, ID conventions. |
| `harness/` | Pure-stdlib Python 3 library: ledger, scheduler, governor, admission, gate, vault, liveness, failures, calibration, and more — one module per increment in the plan. |
| `harness/config/` | Tier tables, spawn allowlists, risk floors, vault-isolation config, gate-required-steps. |
| `hooks/` | Zero-token enforcement scripts wired into `.claude/settings.json` (PreToolUse/Stop) — destructive-git blocking, merge/spawn interlocks, risk-floor checks, closure gate. |
| `.claude/skills/` | The `plan-build`, `build-loop`, and `build-pause` procedures. |
| `.claude/agents/` | Subagent definitions (implementer, test-author, validator). |
| `tests/` | `unittest` suite, one file per `harness/` module plus integration tests. |
| `tools/budget-governor/` | Working artifacts resolving open design questions — spawn-portability probes, duration prediction, cache-weight experiments. See [its README](tools/budget-governor/README.md). |

## Running the tests

Pure stdlib, no dependencies to install:

```
python3 -m unittest discover -s tests -v
```

Before a real firing, the loop also proves the gates against themselves:

```
python3 -m harness.selftest    # every gate demonstrates it can fail
python3 -m harness.smoketest   # zero-quota walk of the whole step sequence
```

## Documentation map

- [docs/design/token-time-optimized-harness.md](docs/design/token-time-optimized-harness.md) — the design, start to end.
- [docs/research/README.md](docs/research/README.md) — research corpus index, confidence ledger, and open items.
- [docs/plan/implementation-plan.md](docs/plan/implementation-plan.md) — what's built, what's next.
- [docs/reference.md](docs/reference.md) — firing lifecycle, plan/state file shapes, worker return contracts.
- [docs/terminology.md](docs/terminology.md) — the vocabulary. Start here if a term in any other doc is unfamiliar.
- [CLAUDE.md](CLAUDE.md) — session notes for anyone (human or agent) working in this repo.

## License

MIT — see [LICENSE](LICENSE).
