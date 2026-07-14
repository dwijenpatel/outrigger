# test-overlap — what a blind held-out suite catches that self-tests miss

Standalone tool (Python stdlib + git only). **One thing well:** measure how much
two test suites over the same code differ in *what they actually catch* — so you
can see the marginal value a blind held-out suite adds on top of an implementer's
own self-tests, and where **both** are blind.

**Terminal telemetry, not a gate.** Nothing composes on its output; a person
reads it. It changes nothing about how the harness runs — it only observes — so
it needs no design change to exist. It operationalizes the held-out-suite tool's
own keep-or-delete test ("escapes caught that the visible checks missed" —
[../heldout-suite/README.md](../heldout-suite/README.md)) at finer grain, on a
single task.

## The two lenses

- **line-reach** — which source lines each suite runs. Cheap, and it **undercounts**:
  a wrong-rounding bug runs the *same source line* as correct rounding, so line
  coverage cannot tell a rigorous suite from a shallow one. Read it as a sanity
  check, never as the measure of value.
- **mutation** — generate many small **wrong-versions** of the source (flip `<`
  to `<=`, `+` to `-`, an argument index `0` to `1`, `True` to `False`, drop a
  `not`, tweak a constant). For each, does suite A notice (some test fails)? does
  suite B notice? The **differential cells** — caught by *exactly one* suite — are
  the signal: they are the wrong-versions one suite would let ship silently and
  the other would stop.

## Run

```sh
python3 tools/test-overlap/overlap.py \
  --repo /path/to/repo-under-test \
  --source-pkg eaitl \
  --suite-a self=tests \
  --suite-b held=/abs/path/to/sealed/suite \
  --mutate ops.py,engine.py,resolve.py,parser.py \
  --out overlap-report.json
```

- The repo is copied to a throwaway checkout; `--source-pkg`'s files are the ones
  traced and mutated. A suite path **under** `--repo` is *internal* (it moves with
  the mutated checkout); a path **outside** the repo is *external* (a sealed
  held-out suite that imports the mutated code with the repo on `PYTHONPATH` — the
  same run contract [heldout-suite](../heldout-suite/README.md) seals).
- Assumes stdlib-`unittest`-discoverable suites and the repo-on-`PYTHONPATH`
  import convention every task in this project follows.
- `--mutate` defaults to every `*.py` under the package except `__init__.py`;
  narrow it to the behaviour-bearing files to cut equivalent-mutant noise.
- `--stage lens1` runs only the cheap line-reach pass.

Exit codes: **0** measured · **1** a suite is not green on the pristine tree
(precondition failed, nothing measured) · **2** usage/input error.

## Output

`overlap-report.json` carries an explicit integer major (`contract: 1`) for
consistency, but it is **terminal telemetry — not one of the composed envelopes**
in [../CONTRACTS.md](../CONTRACTS.md) (nothing downstream reads it). Shape:
`pristine`, `line_reach`, and `mutation` with `caught_by_both`,
`caught_only_by_<label>` for each suite, `caught_by_neither`,
`mutation_score_<label>`, and an `examples` block listing the exact mutants in
each differential bucket.

## Reading the numbers honestly

- **The differential cells are the signal.** Equal totals hide everything.
- **"caught by neither" mixes two things** — genuine shared blind spots *and*
  equivalent mutants (wrong-versions that are behaviourally identical to the
  original). Read that list by hand; the tool cannot tell them apart.
- **Mutation testing is a proxy** for "plausible wrong implementations," not a
  census of real bugs.
- **The mutation operators are a fixed set** — comparison/arithmetic/boolean-operator
  swaps, `not`-removal, and numeric/boolean constant tweaks. Strings, slice
  bounds, and control-flow shape are not mutated; the scores are over that class.
- **It is one task at a time.** Existence-and-magnitude on a single task, never a
  rate.

## First run — eaitl engine slice (2026-07-14)

Implementer self-tests (35) vs the blind held-out suite (126), both green on the
landed engine (`eaitl` `c646832`). Of 157 valid wrong-versions: **99** caught by
both, **13** by the blind suite only, **0** by the self-tests only, **45** by
neither. The 13 the blind suite alone caught cluster on comparison boundaries and
operand order, filter error-handling (an errored filter row must be dropped),
cast dispatch, and the `{"lit": …}` literal-argument escape. Committed report:
[../../docs/research/internal/t2-pilot-1/pilot-eaitl-preview/overlap-report.json](../../docs/research/internal/t2-pilot-1/pilot-eaitl-preview/overlap-report.json).

## Tests

`python3 tools/test-overlap/test_overlap.py` — mutation generation (each operator,
no-op-free, single-point), suite resolution (internal vs external), and an
end-to-end differential case: a `<=` that a boundary-testing held suite catches
and a self suite that never tests the boundary lets pass.
