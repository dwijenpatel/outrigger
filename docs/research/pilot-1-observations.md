# Pilot firing #1 — live observations ledger

Friction, failures, and defects observed during the first real firing
(`cc-agent-harness-test1`, single-trade field-service pilot, started
2026-07-04). Streamed in by the operator as they occur; triaged here against
the machinery; fixes land in this repo and roll into the pilot-#2 clone.
This is the "first real telemetry" the Stage-0 exit criterion exists to
produce ([../plan/implementation-plan.md](../plan/implementation-plan.md)
Next up; design §11).

**Status legend:** 🔴 defect (fix in this repo) · 🟡 friction (candidate
improvement, batch) · ⚪ benign (no action) · ❓ needs more detail

---

## Triage ledger

### P1-1 ⚪ `ls state/` exits 1 before any firing

The probe `ls .../state 2>/dev/null` fails because `state/` does not exist
until the loop creates it (every writer `makedirs` lazily). Benign — but see
P1-5, which the same probe surfaced.

### P1-2 🟡 zsh eats `===` separators — "(eval):1: == not found"

The pilot orchestrator generated `sed ...; echo ===; grep ...` as a compound
probe; zsh's `=`-prefix expansion (a bare word starting with `=` expands to
a command path) turns `===` into "path of command `==`" → hard failure of
the whole compound command. Model-behavior friction, not machinery. Two
cheap mitigations for pilot #2: a CLAUDE.md line in the pilot repo ("shell
is zsh — never use bare `=`-prefixed words like `===` as separators"), and
it is exactly the shape the lessons corpus exists for once a firing is live.

### P1-3 ❓ "Failed to read ledger task schema and module APIs"

No command/output captured yet. Theme is clear though — see P1-6.

### P1-4 ❓ "Failed to read gate signature, config dir, gitignore"

No command/output captured yet; the gitignore probe is what led to P1-5.

### P1-5 🔴 `state/` is not gitignored → the loop's own state dirties the tree → `require_clean` refuses every merge

Confirmed in-tree: the build-loop skill mandates `state/run.marker`,
`state/closure-hook.json`, `state/admission-stamp.json`,
`state/gate-stamps/` — all inside the repo — while `.gitignore` covered only
`__pycache__/`, `*.pyc`, `.DS_Store`. `run_gate` step 1 reads
`git status --porcelain`, which includes untracked files: the first gated
task of the pilot would have been refused with "source tree dirty" *by the
harness's own bookkeeping*. Classic integration defect no unit test caught —
each module was hermetic; the composition wasn't.

**Fix (this repo, this commit):** `state/` added to `.gitignore`.
**Fix (live pilot repo, operator one-liner):** `echo "state/" >> .gitignore`
(commit it) before the first gated merge.

### P1-6 🟡 The planning session has to source-dive for shapes (ledger schema, gate signature, config locations)

The pilot session's probes are API archaeology: what fields a task record
needs, what `run_gate` takes, where configs live. The SKILL.md names
functions but never shapes — a violation of our own §6.1 turn economy, paid
in exploration turns at planning time. Batch improvement for pilot #2: a
one-page operator/orchestrator reference (task-record fields, floors.json,
gate-required-steps.json, closure-hook config, state-file map, the
`run_gate` call the skill expects) — either `docs/HARNESS-REFERENCE.md` or
a `references/` file progressive-disclosed from the build-loop skill.

### P1-7 🟡 (predicted, not yet hit) Vault location is unpinned — an in-repo vault breaks two ways

The skill says "move outputs to the vault" without pinning *where*. If the
pilot places the vault inside the repo: (a) untracked vault files dirty the
tree (same failure as P1-5); (b) committed vault files ride the git history
into the implementer's worktree — the deny rules guard the *path*, but a
worktree checkout resurrects the content at a different path and the
isolation claim quietly dies. The vault must be an **absolute path outside
the repo** (sibling dir, e.g. `../cc-agent-harness-test1-vault/`). Batch
fix: pin this in the SKILL.md and in `vault.isolation_settings` docs;
consider a loud check (vault path inside the repo root → refuse).

### P1-8 🔴 There is no planning surface — the loop improvises the plan and asks almost nothing

Observed: given a one-line project description, the pilot session asked one
project question (with "~4–6 ledger tasks" pre-baked into it), accepted a
one-line answer, and moved straight to authoring the ledger — no
requirements elicitation (trade specifics, roles, tenancy/auth model, the
billing-wedge behaviors, in/out list, tech stack), no per-task spec review,
no explicit plan-ratification step beyond the initial question. The operator
expected "a lot more clarifying questions."

Root cause is in-tree: the design's plan-first half ("the plan template,
risk-classification table, human gate" — §4 residue) **was never an
increment**; the plan has no planning skill anywhere in Phases A–H. The
build-loop skill's first line assumes "the ratified plan" exists. Everything
downstream leans on spec quality — the spec is the panel's *only shared
context*, the test-author writes held-out tests *from the spec alone*, and
H9's ambiguity blockers only bite where profiles are set right — so a thin
improvised spec quietly weakens the entire O0 chain ("a subpar plan hurts
more than no plan" is the measured result the human gate exists for).

**Live-pilot mitigation:** operator stopped the session; pilot restarts
from scratch after the fix.
**FIXED (I2, 2026-07-04):** `plan-build` skill (interview modeled on
mattpocock/skills "grilling": one question at a time with a recommended
answer, walk the design tree in dependency order, explore-don't-ask, no
enactment until explicit shared understanding) + our additions (the
determinacy bar — a spec-only test-author needs no guesses; "you decide" →
recorded delegated DECISION; two clean sweeps to finish) +
`harness/planning.py`: content-bound ratification stamp (any post-approval
edit voids it), `plan_ready` fail-closed gate, and **build-loop step 0 now
refuses to fire without it**. Sizing guidance included: phase 1 = small
walking skeleton, later phases provisional — small must not mean vague.

---

## Themes so far

1. **Hermetic tests missed composition defects** (P1-5, P1-7): every module
   passed its suite; the repo-level interaction (state files × require_clean;
   vault × git history) had no test. Pilot #2 prep should add a
   "firing smoke test": scripted walk of the skill's step sequence in a
   scratch clone via the mock worker, asserting the tree stays clean and the
   gate stays green end-to-end.
2. **Turn economy applies to the harness's own surfaces** (P1-6): the
   machinery is legible to its authors, not yet to a fresh orchestrator.
3. **The enforcement half was built; the elicitation half wasn't** (P1-8):
   every guard downstream of the spec is mechanized, but nothing mechanizes
   *producing a good spec* — the single input the whole O0 chain trusts.
