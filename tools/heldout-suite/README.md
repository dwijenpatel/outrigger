# heldout-suite — the graded tests' lifecycle

**v2 artifact #4** ([design](../../docs/design/evidence-based-harness.md) D2/D11, built to
R5/D15 from the ratified [plan](../../plans/heldout-suite.plan.json) — the first artifact
planned through spec-interview + plan-preflight). One thing well: **manage the held-out test
suite's lifecycle** — materialize an authoring workspace *outside* the judged repo, validate
an authored suite has teeth against the pre-change code, seal it into a tamper-evident
manifest, and verify that seal before every use. The best-replicated finding in the corpus is
that an agent graded on tests it can see or edit games them (§3.1; 12/12 studied systems have
the hole); this artifact is the lifecycle half of closing it.

**Deliberately not here:** launching any agent. Who authors is composition — [ROLE.md](ROLE.md)
is the authoring contract any fresh-context agent can execute; the future execution loop wires
the spawn (plan decision 1: separation of concerns — launchers are the piece most likely to
change shape entirely). Standalone by construction: pure stdlib + git, no imports from
anything else in this repo.

## The four verbs

```
python3 heldout.py materialize --plan PLAN.json --task ID --repo REPO [--base main] --out DIR
python3 heldout.py validate    --workspace DIR/ID --repo REPO
python3 heldout.py seal        --workspace DIR/ID --repo REPO [--retire]
                               [--adjudicated-by NAME --adjudication-note TEXT]
python3 heldout.py verify      --workspace DIR/ID
```

Exit codes everywhere: **0** ok/fresh · **1** refusal, policy failure, or divergence ·
**2** usage or input error.

- **materialize** — builds `DIR/ID/` containing `authoring/task.json` (exactly the ratified
  input scope: this task's full entry + the plan-level goal/non-goals/constraints/decisions —
  **never sibling tasks**), an empty `suite/`, and a generated `AUTHORING.md` pointer.
  **Refuses an `--out` that resolves inside the repo** (realpath, symlinks covered): the v1
  in-repo vault measurably rode git history into every implementer worktree. Refuses existing
  workspaces — re-sealing is `--retire`'s job, never an overwrite.
- **validate** — runs the suite in a throwaway clean checkout of the recorded base commit
  (exact-count JSON runner, 600s deadline — a hung suite is a policy failure, not a wait).
  **The fails-on-base policy, verbatim from the ratified plan:** at least one test must fail
  against base; the failed/passed/errored split is recorded; base-passing tests are
  legitimate regression guards; ImportError on not-yet-existing modules counts as failing.
  Necessary, not sufficient — nothing mechanical can prove a test fails *for the right
  reason* without the implementation.
- **seal** — re-validates, then writes `manifest.json`: `{contract, task_id, spec_hash
  (sha256 of authoring/task.json), base_sha, run (the exact consumer invocation, with
  $CHECKOUT as the substitution point), files (per-file sha256s), fails_on_base, sealed_at
  [, adjudication{by, note, ts}]}` — and `deny-fragment.json` (deny-read of the whole
  realpathed workspace, ready to merge into an implementer-spawner's settings). Prints the
  **manifest's own sha256** — the out-of-band anchor value (see threat model). Re-sealing
  requires `--retire`, which archives the old manifest + validation + a suite snapshot to
  `retired/<ts>/` — evidence preserved, never overwritten. A human-edited suite re-seals
  with `--adjudicated-by/--adjudication-note`, putting the intervention on the record.
- **verify** — the tamper check consumers run **immediately before every use** of a sealed
  suite: recomputes every suite file's hash (missing, extra, and changed files all diverge)
  and the spec hash. Exit 0 fresh, 1 diverged.

## Threat model — three layers, stated honestly

A hash-manifest detects **divergence**, not authorship: it cannot alone stop an adversary
with full write access from rewriting tests *and* manifest into a self-consistent forgery.
The protection is layered:

1. **The tamper window shouldn't exist.** The implementer can never read or write the
   workspace (the deny wall — OS-enforced config, not politeness). The test-author's write
   access ends before sealing, and **the author never runs `seal`** (composer's verb, after
   the author's process ends). No live agent holds both motive and access post-seal.
2. **Divergence is actually checked.** `verify` runs before every use — partial tampering
   (files changed, manifest not, or vice versa) fails loudly. **Documented limit:** a
   full-write self-consistent forgery passes `verify`.
3. **Forgery is caught out-of-band.** `seal` prints the manifest's sha256; the composition
   records it in the git-committed run-ledger. Silently replacing a sealed suite then
   requires forging the files *and* rewriting pushed git history everywhere it exists —
   loud, multi-system surgery instead of a quiet file edit.

**Named escalation, deliberately not built (plan non-goal):** cryptographic signing with an
operator-held key no agent role can read — the right tool if the threat model ever includes
a repo-write-capable or host-level adversary. For a sandboxed-agent adversary, layers 1–3
suffice and key management isn't free (R2).

## Non-goals (verbatim from the ratified plan)

No agent spawning (composition's job — decision 1); no boundary-verification probe (declined
*here* to preserve that separation — buildable later as its own artifact); no replay/leakage
accounting (the composer's ledger concern — this artifact gives replays a stable identity to
account against); no in-repo suites, ever; no seal signing in v1 (above).

## Composition examples

```sh
# The full lifecycle, spawn supplied by you (or, later, by the execution loop):
python3 tools/heldout-suite/heldout.py materialize --plan plans/foo.plan.json \
  --task tags-add --repo ~/repos/app --out ~/repos/app-heldout
#   ... a fresh-context agent authors tests in the workspace per ROLE.md ...
python3 tools/heldout-suite/heldout.py seal --workspace ~/repos/app-heldout/tags-add --repo ~/repos/app

# Record the seal + its anchor in the ledger (composition, not coupling):
python3 tools/heldout-suite/heldout.py seal ... | python3 tools/run-ledger/ledger.py \
  append v2-ledger.jsonl --kind run --subject heldout-suite/tags-add/seal --data -

# Gate wiring — verify, then run the sealed suite against the merged tree:
python3 tools/merge-gate/gate.py run --repo ~/repos/app --ref task/tags-add \
  --check "python3 <this-dir>/heldout.py verify --workspace ~/repos/app-heldout/tags-add" \
  --check "PYTHONPATH=. python3 -m unittest discover -s ~/repos/app-heldout/tags-add/suite -t ~/repos/app-heldout/tags-add/suite"

# An adjudicated human edit, classified for the feedback loop (plan decision 8):
python3 tools/run-ledger/ledger.py append v2-ledger.jsonl --kind outcome \
  --subject heldout-suite/tags-add/adjudication \
  --data '{"lesson_target": "test-author-role", "generalizable": true, "note": "..."}'
```

## Measurement & deletion criterion (R2)

Judged by **escapes caught that the visible checks missed** — the P3v2-5 precedent: v1's
held-out suite caught a defect that visible tests *and* three independent reviewers all
passed. Every seal and every gate run against a sealed suite lands in the ledger; if real
usage shows the held-out layer never failing anything the implementer's own checks wouldn't
have caught, delete it — that deletion is a result (and T2 is the controlled version of this
question).

## Tests · versioning

`python3 tools/heldout-suite/test_heldout.py` — 17 tests across the lifecycle: workspace
scope (sibling exclusion), in-repo/symlink refusal, fails-on-base enforcement (all-pass
refused; ImportError counts), split recording, seal binding + anchor output, retire
preserving evidence, adjudication on the record, verify catching modified/extra/missing
files and spec drift, worktree cleanup. Manifest contract **v1**; drift between this README,
ROLE.md, and the code is **T11**'s subject matter.
