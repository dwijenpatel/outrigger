# Authoring workspace — held-out suite for task `eaitl-preview-engine`

You are the TEST-AUTHOR for exactly one task. Full role instructions:
`ROLE.md` in the heldout-suite artifact directory of the orchestrating repo
(tools/heldout-suite/ROLE.md). The short version:

- **Your inputs are `task.json` (in this directory) and the base checkout of
  the target repository — nothing else.** task.json holds the task's spec and
  the plan-level goal/non-goals/constraints/decisions (the why). There is no
  implementation yet; you write tests from the SPEC.
- **Write stdlib-unittest tests as `test_*.py` files into `../suite/`.**
- Your suite will be judged by `heldout.py validate` against a clean checkout
  of base commit `e64604deb3851c6fd1f082df414d9553a847cdcd`: the runner must complete, and **at least one
  test must fail on base** (a suite that fully passes before the change proves
  nothing). Base-passing regression guards are allowed and welcome.
- You may run `validate` yourself, iteratively. You never run `seal`.
- You never assert your suite is good — validate and the seal decide.
