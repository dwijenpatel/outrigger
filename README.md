# outrigger

**Long-horizon coding agents, stabilized.** Agents do the work; outrigger decides whether
it counts.

Polynesian navigators crossed thousands of miles of open ocean in small canoes — not by
building bigger hulls, but by lashing a stabilizing float alongside. The hull does the
work. The outrigger keeps it upright, far from shore, when nobody can reach you.

Same idea here. The coding agent is the hull — Claude Code, Codex CLI, whatever comes next.
**outrigger is the structure lashed alongside it**: the interrogated spec, the isolation
walls, the blind examiner, and the evidence discipline that together make hours of
unattended work land as *verified, to-spec, merge-worthy* commits instead of confident
wreckage.

```
      ┌──────────────────────────────────┐
      │   your coding agent    ~ hull ~  │   does the work
      └───────┬──────────┬──────────┬────┘   (any vendor; replaceable)
              │          │          │        ← lashings: schema'd file
      ┌───────┴──────────┴──────────┴────┐     contracts + exit codes,
      │   outrigger            ~ float ~ │     never shared memory
      │   spec · walls · blind grading   │
      │   · evidence ledger              │   keeps it upright when
      └──────────────────────────────────┘   no one is watching
```

## The problem

Coding agents are brilliant for twenty minutes and untrustworthy for eight hours. Three
failure modes dominate long runs, and none of them is fixed by a better model:

1. **Ambiguity compounds.** A spec that's 95% clear produces work that's 0% right when the
   missing 5% was the point. In our own pilot records, a single unstated convention cost an
   **8-hour-25-minute mid-run stall** — the agent wasn't weak, the spec was.
2. **The agent grades its own homework.** When the implementer writes (or can even *read*)
   its own acceptance tests, "all tests pass" is the agent's opinion of itself. Long runs
   give optimization pressure time to find the grader — Goodhart's law, industrialized.
3. **The human is the weakest wall.** Tired operators rubber-stamp, treat silence as
   approval, and relax the rules mid-run "just this once." Any harness that relies on
   sustained human vigilance is designed to fail at hour six.

And a fourth, quieter one: **harnesses accrete ritual.** Checks nobody measured, guardrails
nobody costed. We learned this the expensive way — our v1's post-mortem verdict was *"the
machine cost tokens to save tokens."* The cure isn't more machinery; it's machinery that
has to earn its keep.

## The levers that actually move the needle

If you want an agent to run longer *and* be more trustworthy at the end, our research and
pilot evidence keep pointing at the same five levers:

1. **Spec quality before any code.** Ambiguity is the compounding error source; it's
   cheapest to kill at hour zero.
2. **Verification the worker cannot touch.** Not "more tests" — tests the implementer
   cannot read, influence, or overfit.
3. **Externally granted completion.** The agent never declares itself done; an independent
   mechanism does, against the whole build.
4. **Surviving the economics.** Subscription windows close mid-run; context reuse is ~9×
   cheaper than fresh tokens (we measured it). A long-horizon harness must halt, park, and
   resume — never overspend or lose the run.
5. **Subtracting machinery.** Every mechanism measured; anything that doesn't pay for
   itself gets dialed down or deleted, on evidence.

outrigger is those five levers, built as composable tools.

## How it works

```
 ratified spec ─────► blind TEST-AUTHOR ────► sealed held-out suite ✦
      │                (fresh worker,          (proven to fail on base,
      │                 sees spec only)         tamper-evident manifest)
      │                                              ║
      │               ═══ OS-enforced wall ══════════╣
      │               implementer CANNOT read ═══════╣
      ▼                                              ║
  IMPLEMENTER ──► commits in a walled worktree       ║
  (own tests,     │                                  ║
   own judgment)  ▼                                  ▼
              MERGE-GATE: judges the MERGED tree — task checks + sealed suite
                  │  feedback is counts-only; ≤2 attempts, then a human
                  ▼
              fast-forward landing, pinned to the judged SHA
                  ▼
              WHOLE-BUILD CLOSURE: every check + every sealed suite,
              re-run against final main → completion GRANTED and stamped
```

**The interrogation.** Work enters through a pedantic, one-question-at-a-time spec
interview that converts a goal into a machine-checkable plan — decisions recorded with
rationale, constraints pinned, and a determinacy bar: *could a stranger write acceptance
tests from this spec alone, without guessing?* Ratification is explicit and content-bound
(a stamp over the plan's hash — no silence-as-approval, no drift after sign-off), and a
structural preflight refuses malformed or unratified plans before any tokens burn.

**The blind examiner.** A *separate* fresh worker authors the acceptance suite from the
ratified spec — it never sees the implementation. The suite is validated (it must fail on
the pre-change codebase), then sealed with a tamper-evident manifest. The implementer works
in an isolated worktree and is **denied read access to the suite at the OS level** — not by
prompt, by sandbox. Failures come back as counts only, so there's nothing to overfit.
Attempts are bounded; exhaustion escalates to a human instead of grinding against the
grader.

**The evidence regime.** Every design decision cites graded evidence (each claim scored on
warrant, incentive, and decay — vendor docs expire, benchmarks age) or is explicitly marked
Provisional/TBD with a named promotion trigger or settling experiment. Changes to the
machinery itself enter the same way: pre-registered predictions, null arms where feasible,
an append-only measurement ledger, and **deletion criteria** — a check that catches no
errors gets removed, on the record. Rigor is also *dialable per plan*: `full`, `gate-only`,
or `bare`, chosen by the operator at spec time, and every reduction is stamped in the
ledger so lowering the guard is always a visible, recorded choice.

```
 research corpus ──► Tier-A distillation ──► design decision ──► artifact
 (14 subtopics,      (warrant × incentive     Decided /           (standalone
  primary sources)     × decay grading)       Provisional / TBD    tool)
                                                                     │
        ┌────────────────────────────────────────────────────────────┘
        ▼
  measurement · null arms · pre-registered predictions ──► append-only ledger
        │
        ▼
  dial up · dial down · DELETE — no ritual survives without evidence
```

## Receipts

Claims like these deserve evidence; the repo carries its own:

- **The blind suite caught a dropped wall, live.** During launcher hardening, a config
  change silently disabled the read-isolation. The implementer's own checks passed; the
  held-out suite's probe failed; the merge was refused. The design's whole thesis,
  demonstrated by accident, on the record.
- **The machinery defended the spec against its own operator.** In a live probe, workers
  truthfully reported ambient context leaking into their sessions — and the blind gate
  refused the run, twice, exactly as specified. Exit 1 was the system working.
- **Vendor-undocumented economics, settled for $17.** Whether cached tokens count against
  subscription rate-limit windows was officially unanswered; a pre-registered two-arm
  experiment bounded it (cache reads weigh **< 0.1125** of fresh input) and promoted a
  design decision on the result.
- **Two vendors, one contract, fail-closed.** The same tool-neutral launcher contract runs
  Claude Code and Codex workers — each earned trust through its own live smoke, including
  deliberate read-attempts against the wall. Three of the five Codex smoke attempts cost
  $0: they aborted loudly at config parse rather than ever running unwalled. That's the
  contract's core clause: *never launch unwalled and hope.*

Everything above is reproducible from the committed artifacts: raw turn logs, gate reports,
sealed-suite manifests, and the measurement ledger.

## Architecture, in one breath

Unix-style composition: every piece is a standalone CLI that does one thing, connected only
by schema-validated files and exit codes — no artifact requires another's existence, and
workers attach through a [tool-neutral launcher contract](tools/exec-loop/launchers/CONTRACT.md)
(new vendor = one launcher file + one smoke run, never surgery on the loop).

| Tool | One thing, done well |
|---|---|
| [spec-interview](.claude/skills/spec-interview/README.md) | The interrogation: goal → ratified, machine-checkable plan |
| [plan-preflight](tools/plan-preflight/README.md) | Refuses malformed/unratified plans; determinacy warnings for the ratifier |
| [heldout-suite](tools/heldout-suite/README.md) | Blind suite lifecycle: materialize outside the repo, fails-on-base proof, tamper-evident seal |
| [merge-gate](tools/merge-gate/README.md) | Judges the *merged* tree in a clean worktree; stamped, staleness-proof reports |
| [exec-loop](tools/exec-loop/README.md) | The composition: walks a ratified plan unattended through author → seal → implement → gate → land → closure |
| [run-ledger](tools/run-ledger/README.md) | Append-only, schema-validated measurement ledger — the home of every prediction and null arm |
| [shadow-pilot](tools/shadow-pilot/README.md) | Turns real tasks into harness-vs-null comparisons with a blind arbiter — the harness proves its own value or doesn't |

Deeper reading: the [evidence-based design](docs/design/evidence-based-harness.md) (every
decision with its warrant and status), the [operator walkthrough](docs/design/operator-walkthrough.md)
(the same design as a day-in-the-life), the [graded evidence base](docs/research/distilled/README.md),
and the [full research corpus](docs/research/README.md).

## Working in this repo

- Branch → commit → `--ff-only` merge to `main`; never commit to `main` directly.
- A design decision enters [the design](docs/design/evidence-based-harness.md) only with a
  [distilled](docs/research/distilled/README.md) Tier-A citation; otherwise it is Provisional
  (named promotion trigger) or TBD (named settling experiment).
- After editing docs, run the link guard: `python3 -m unittest tests.test_reference -q`.
- See [AGENTS.md](AGENTS.md) for standing directives (Claude Code additionally reads
  [CLAUDE.md](CLAUDE.md)).

## History

This project has shed a skin once and a name twice; the records are kept, not rewritten:
the [reincarnation record](docs/reincarnation-plan.md) (v1 retired by its own post-mortem,
2026-07-11; its code at git tag `v1-attic`, its conclusions in [the attic](docs/attic/README.md)
as prior art to argue against) and the rename (`cc-agent-harness` → `outrigger`,
2026-07-13 — historical documents and artifacts keep the old name where they are records).

## License

MIT — see [LICENSE](LICENSE).
