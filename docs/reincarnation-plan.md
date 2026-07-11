# Reincarnation plan — continuity record for the from-scratch effort

**Status: EXECUTED 2026-07-11** (ratified in discussion 2026-07-10). Execution ran every step
in the §3 order, as the commit chain `c67768e` (salvage) → `89ef70c` (attic + machinery
deletion) → this commit (CLAUDE.md rewrite + close-out), with the pre-cleanup state anchored at
git tag **`v1-attic`** (placed on `c67768e`, i.e. *with* the salvage included). Findings and
deviations during execution:

- **Pilot clones located:** `repos/cc-agent-harness-test1/` (HEAD `a638acf`) plus siblings
  `-vault/` and `-wt/`. The full P3v2-5 evidence set was salvaged into
  [research/internal/pilot-3-artifacts/](research/internal/pilot-3-artifacts/README.md) —
  **including the vault** (amending §3's "no salvage needed" note: the held-out replay meter
  and the `41 passed` log turned out to live vault-side). internal.md §5 row 3 re-graded
  Tier C → **A3** (n stays 1). The clones were left on disk; deleting them is now safe and is
  the operator's call.
- **Tokenizer-study harness: confirmed lost** (no surviving session scratchpad holds it);
  internal.md marks that row permanently non-promotable.
- **One live catch:** the unanchored `state/` gitignore pattern silently swallowed the salvage
  — the tree-dirt failure family (P1-5/P1-9/P2-9) firing during the archival of its own
  evidence. Fixed by anchoring to `/state/`.
- **Scope additions found during execution:** `docs/reference.md` (the v1 API reference) went
  to the attic with the code it documents; `tests/test_reference.py` was repurposed into the
  corpus link guard (same invocation, new object of protection); the root `README.md` (a v1
  front page) was rewritten; `.claude/settings.json` was emptied in the same commit as the
  `hooks/` deletion so no registered hook points at a deleted script.
- The `harness-technical-plan` scheduled task was deleted.

This document remains the session-continuity anchor: if you are a new session picking this
effort up, read this file, [the design plan](design/evidence-based-harness.md), and
[distilled/](research/distilled/README.md) — in that order — and you have the full state.

## 1. Where the project is

The **research phase is complete**: all 14 external subtopics carry dedicated documents
(2026-07-09/10 passes: meta-harness, memory, planning, orchestration, human-in-the-loop), and
the distillation was refreshed 2026-07-10 to absorb them. The **current design surface** is
[design/evidence-based-harness.md](design/evidence-based-harness.md) (draft 1) — a from-scratch,
first-principles plan where every decision carries Decided/Provisional/TBD status and cites
Tier-A evidence. It disregards all prior design decisions by construction.

**The operator's governing decision:** the future harness will be built **from scratch**, not
from any existing harness work in this repo. The previous effort
([design/attic candidate: token-time-optimized-harness.md](attic/token-time-optimized-harness.md)
plus the `harness/` machinery) is an **evidence quarry, not a foundation**. The rule that
decides what survives: *our defeats are evidence; our decisions are not* — internal defects,
falsified predictions, and measurement artifacts are Tier-A material; the old design's choices
are self-generated conclusions.

## 2. Standing operator directives (issued in-session; recorded nowhere else)

- **Sub-agents use the `Opus 4.8` model, not `Fable 5`** — stated twice, applied to every
  research/extraction fan-out.
- **Git discipline: never commit directly to `main`.** Feature branch → commit → `--ff-only`
  merge → delete branch. Every commit this phase followed it.
- **Machinery defects are recorded, never fixed** while in research/design mode (e.g. the
  B-1..B-4 concurrency audit in [distilled/internal.md](research/distilled/internal.md) stays
  OPEN by policy).
- **The cache-weight experiment's quota-costing arms are operator-run only** — never execute
  `run_cache_weight_experiment.sh` `dry-run`/`arm-a`/`arm-b`; they spend real Max-plan quota
  (this is experiment **T1**, the highest-value single measurement pending).
- **Operator comfort is not a design goal** — gates are measured by errors caught (design R3).
- **Do not over-design**: a design decision enters only with a distilled Tier-A citation; "the
  old design did it" is explicitly not a warrant; TBD is the required honest state where
  evidence is weak.
- **Loosely-coupled, composable artifacts** (added 2026-07-11, post-execution): every machinery
  piece does one thing well, runs standalone, and composes through file contracts; no artifact
  may require another artifact's existence, in either direction — e.g. the planning interview
  must be fully decoupled from the execution loop, and vice versa (design R5/D15).

## 3. The reincarnation manifest (ratified, awaiting execution)

| Fate | What | Why |
|---|---|---|
| **Preserve** | `docs/research/` entire; `docs/terminology.md`; `docs/design/evidence-based-harness.md`; `docs/design/operator-walkthrough.md` | The product of this phase. terminology.md keeps internal evidence readable once old docs leave HEAD |
| **Preserve** | Measurement instruments + raw artifacts: the model/effort benchmark harness + 73 raw run JSONs, the spawn-portability probe, the cache-weight experiment (unexecuted) | Artifacts *are* the Tier-A warrant (internal §4); they measure the vendor, not our harness — zero design anchoring |
| **Archive to `docs/attic/`, don't delete** | `docs/attic/token-time-optimized-harness.md`, `docs/plan/` | Pilot ledgers cite their IDs constantly (I19, D17, GL1, §5.2); deleting them makes Tier-A internal evidence uninterpretable. Banner: *"Superseded 2026-07-10. Prior art to argue against — never a source of defaults."* |
| **Delete from HEAD** | `harness/`, `hooks/`, machinery-specific tests, the `plan-build`/`build-loop`/`build-pause` skills in `.claude/`, `state/` handling | The contamination vector — implementers copy patterns from code, not ledgers. Git history retains everything |
| **Rewrite** | `CLAUDE.md` | The auto-loaded file currently primes every session with old machinery. Worst contamination vector. New content spec in §4 |
| **Delete (outside repo)** | The `harness-technical-plan` scheduled task (`~/.claude/scheduled-tasks/harness-technical-plan/`) | It plans the OLD design; Manual-only, never fired |

**Execution order (each step gates the next):**

1. **Salvage P3v2-5 first.** Copy the pilot-3 clone's verdicts, held-out summary, and gate
   stamp into `docs/research/internal/pilot-3-artifacts/`. This is the design's central-thesis
   artifact (held-out corpus caught what three blind validators missed) and it exists **only in
   the pilot clone** — if clones are cleaned before salvage, the thesis proof is permanently
   hearsay (named in internal.md §5). ⚠ **Blocker: the pilot clones' exact paths are not
   recorded anywhere** — they are sibling directories outside this repo; ask the operator or
   scan before executing. Optional secondary salvage: the tokenizer study harness (Tier B,
   currently only in a dead session scratchpad — likely already lost; confirm and note).
2. **Tag the pre-reincarnation state**: `git tag v1-attic` — so "git history keeps it" has a
   named anchor.
3. Move the two referent docs to `docs/attic/` with the superseded banner; fix inbound links.
4. Delete machinery from HEAD. **Record the tombstone**: note in
   [distilled/internal.md](research/distilled/internal.md) the commit hash at which
   `harness/ledger.py` / `harness/interlocks.py` last exist, so the B-1..B-4 findings keep
   their A3 go-look path (`git show <hash>:harness/interlocks.py`).
5. Rewrite `CLAUDE.md` per §4.
6. Audit `tests/`: keep/replace the doc-drift test (`tests.test_reference`) so it guards the
   corpus, not the deleted design; keep the repo-wide relative-link checker practice (snippet
   in §6).
7. One reincarnation commit per step-group, branch → ff-merge, manifest in the message.

## 4. New CLAUDE.md content spec (for step 5)

Keep it short: (a) mode statement — evidence-first design phase, harness v2 built from scratch,
current surface `docs/design/evidence-based-harness.md`, evidence base `docs/research/distilled/`;
(b) the §2 standing directives (Opus 4.8 subagents; branch→ff-merge; T1 operator-run; no
decision without a Tier-A citation); (c) the environment truths that remain: shell is zsh
(never bare `=`-prefixed words; use `---` separators); (d) pointer to this file for the
manifest and external-assets inventory. Drop: vault paths, gate-protected globs,
upstream-ownership, pilot-clone rules — all old-machinery operational notes.

## 5. External assets a cold session cannot discover

- **Pilot clones** (P3v2-5 salvage source): **located and salvaged 2026-07-11** —
  `repos/cc-agent-harness-test1/` + `-vault/` + `-wt/`. Everything evidentiary is now in-tree
  ([pilot-3-artifacts/](research/internal/pilot-3-artifacts/README.md)); the clones' only
  remaining unique content is their git history (the judged diffs, branch `task/GL1-scaffold`
  head `4b8653f`). Safe to delete; operator's call.
- **The vault** (`repos/cc-agent-harness-test1-vault/`): **salvaged in full** into
  `pilot-3-artifacts/vault/` (the "no salvage needed" pre-judgment was wrong — the replay
  evidence lived there). The on-disk original is now redundant.
- **Zenith clone**: `repos/zenith`, pinned at commit `feb1d62` — the §5 code-read facts in
  distilled/external.md decay on any release past it. Keep.
- **Scheduled task**: `~/.claude/scheduled-tasks/harness-technical-plan/` — **deleted
  2026-07-11** per the manifest.
- **Assistant memory** (`~/.claude/projects/-Users-dwijen-repos-cc-agent-harness/memory/`)
  mirrors the scope rules but is machine/user-local — this repo file is canonical.

## 6. Corpus maintenance practice (session knowledge worth keeping)

After any doc change: run the repo-wide link check + drift test. The check used all session:

```python
# resolve every relative markdown link against its file's dir; report missing targets
import re, subprocess, pathlib
files = subprocess.run(['git','ls-files','*.md'],capture_output=True,text=True).stdout.split()
link = re.compile(r'\[[^\]]*\]\(([^)#\s]+?)(?:#[^)]*)?\)')
for f in files:
    p = pathlib.Path(f)
    for m in link.finditer(p.read_text()):
        t = m.group(1)
        if not t.startswith(('http','mailto:')) and not (p.parent/t).exists():
            print('BROKEN', f, '->', t)
```

plus `python3 -m unittest tests.test_reference -q`. (macOS `realpath -m` is unsupported — use
the Python path, and zsh for-loops need explicit arrays.)

## 7. Operator review queue for design draft 1

Flagged for the operator's judgment, in priority order:

1. **D4's three parallelism licenses** — evidence supports all three shapes, but fewer would
   also be defensible under R2.
2. **D10: no self-modification loop in v1** — the largest deliberate omission.
3. **The T1–T10 ledger ordering** — does it match the operator's priority? (T1 cache-weight is
   claimed highest-value and is operator-run.)
4. The Tier-B "load-bearing but unpromoted" layer was deliberately left in the pass documents
   rather than distilled — the design's Provisional entries are the curated subset; revisit if
   any Provisional needs promotion before build.

## 8. What was deliberately not carried from the prior sessions

- The four extraction agents' verbatim outputs (Tier-B curations with promotion triggers) —
  underlying findings all live in the pass documents; re-derivable.
- The "is this worth building vs `/goal` + Fable ultracode" debate — its conclusions are the
  design's R1–R4; the debate itself added nothing further.
- Old-design open-question work (§12 arms) beyond the preserved instruments.
