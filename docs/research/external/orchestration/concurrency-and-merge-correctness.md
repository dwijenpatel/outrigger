# Concurrency & merge correctness — the theory under the machinery

The distributed-systems and software-engineering theory beneath the harness's concurrency
primitives (generation stamps, write-ahead log, merge interlock, worktree isolation), a
source-level audit against that theory, and the mapping of the pre-registered W1–W5 concurrency
watch items onto known hazards. The multi-agent-topology evidence is the companion,
[multi-agent-orchestration-evidence.md](multi-agent-orchestration-evidence.md).

**Provenance:** 2026-07-10 pass (orchestration cluster 4; Opus 4.8). Theory grounded in
textbook/peer-reviewed sources (OCC, ARIES, the Not-Rocket-Science Rule, Kafka idempotency, HiLo/
Snowflake). The machinery was **read from source** — `harness/ledger.py`, `harness/interlocks.py`,
design §§3/6.2/7, terminology §6, and the W1–W5 pre-registration in
`internal/pilot-2-artifacts/watch-items.json`. Four findings (B-1…B-4) are derived from reading
the code, not the design; one of them (B-4) is a genuine latent correctness gap. Tags per corpus
convention; `[in-tree, 2026-07-10]` marks audited working-tree facts.

**Epistemic frame:** all of W1–W5 are **pre-registered and UNOBSERVED** — no two tasks have ever
run in parallel in this harness. Everything here is *theory predicting where the first real
interleaving will break*, not a post-mortem.

The watch items, verbatim: **W1** stale-generation errors on the event log · **W2** write-ahead
ordering under interleaving · **W3** gate-stamp vs HEAD races at sequential merges of parallel
branches · **W4** admission warmup math · **W5** worktree conflicts.

---

## 1. The five theory areas

- **Optimistic concurrency control** (Kung & Robinson, ACM TODS 1981, `[peer-reviewed]`). Three
  phases: read a private snapshot (no locks), **validate** at commit that your read set wasn't
  invalidated, **write** only if validation passes. Guarantee: serializability without read-phase
  locking. **The load-bearing precondition everyone drops: validate+write must be a serial section
  (lock or atomic CAS).** Two transactions that validate concurrently against the same object can
  *both* pass and both install — the **lost-update anomaly**. Weaknesses: **starvation and wasted
  work under high contention** (OCC wins only when contention is low); a **monotonic version
  counter** is the right primitive and defeats the **ABA problem** (A→B→A read as v1→v2→v3), but it
  gives neither cross-object atomicity nor the serial validation section — it only *detects* a
  conflict the section is supposed to *prevent*.
- **Write-ahead logging / ARIES** (Mohan et al., ACM TODS 1992, `[peer-reviewed]`). The **WAL
  invariant**: the log record is durable *before* the data/effect it describes. Recovery = analysis
  → **redo "repeating history"** → undo, with **idempotent redo** via a per-page LSN check (apply a
  record only if `pageLSN < record.LSN`). **The classic subtle bug: the torn write** — a "durable"
  write split by the OS/device into sub-blocks, crashed mid-split, leaving a fragment whose bytes
  are internally inconsistent. **The fix is a per-record checksum (CRC): recovery stops at the first
  record whose checksum fails** — because a corrupt fragment can still contain a plausible boundary
  byte, so torn-tail detection must be checksum-based, not boundary-based.
- **Exactly-once / idempotency** (distributed-systems consensus). Exactly-once *delivery* is
  impossible over a lossy network; the achievable target is **effectively-once = at-least-once
  delivery + an idempotent consumer**. Mechanisms: idempotency keys + a dedup table (Stripe/Kafka);
  **reconstruct-from-effects** (the durable side effect *is* the dedup record — check whether the
  effect exists before re-performing it); a forward-only consumer cursor (Kafka offsets). The
  classic bug: treating at-least-once as exactly-once (a non-idempotent handler double-acts on the
  inevitable redelivery).
- **Merge queues / the Not-Rocket-Science Rule** (Hoare/bors; Zuul; GitHub; `[established
  practice]`). *"Never merge a commit before CI has proven that commit green, tested in the exact
  tree state it will occupy after merge."* This defeats **merge skew / semantic conflict** — two
  changes each green in isolation that break combined, which a textual git merge produces happily.
  **Speculative execution** tests trailing changes against the *projected* future state (B against
  main+A); **batching** groups N changes per CI run; **bisection eviction** ejects the culprit on a
  batch failure and **re-runs everything behind it because its base moved**; **adaptive window**
  (Zuul, literal TCP AIMD: +1 per success, ×½ per failure). The tradeoff: bigger batch = higher
  throughput but a single bad change false-evicts the whole batch — **optimal batch size tracks the
  pass rate.**
- **Distributed ID allocation** (HiLo / Snowflake / UUID, `[engineering-textbook]`). `SELECT MAX+1`
  races: two writers read the same max and collide. Fixes: **reserve a block atomically** (HiLo),
  **compose uniqueness into the ID** (Snowflake: `timestamp|machine|sequence`), or **UUIDs**.
  The lesson: *max+1 is a single-writer-only shortcut* — two writers must reserve or compose,
  never compute from the current max.

## 2. The machinery, audited against the theory

**Generation stamp = OCC backward-validation** (`ledger.py`). The event log is a single fsync'd
JSONL file; `generation()` = `len(events)`; an append with `expected_generation != generation`
raises `StaleGenerationError`. Correct *as* backward-validation, and **ABA-immune by append-only
monotonicity** (the counter is never reused — better than raw CAS on a mutable cell). But:

- **Finding B-1 — the OCC atomicity gap `[in-tree]`.** There is **no lock** spanning
  read→validate→write: grep finds no `flock`/`fcntl`/`O_APPEND`/`threading.Lock`/`multiprocessing`
  anywhere in `harness/`. Two processes that both read `generation=N` both pass validation and both
  `seek`+`write`+`truncate` at the same offset — the second **clobbers** the first (lost update).
  This is textbook OCC's dropped precondition. It is **safe only because the shared log is
  single-writer** — workers are headless one-shots in isolated worktrees that hand back structured
  returns and never touch the shared log; the sole appender is the orchestrator loop. **Correctness
  rests on an architectural single-writer invariant that no mechanism enforces** — a property of
  who-calls-what, one refactor from a live race.
- **Finding B-2 — `seq = len(events)+1` is `SELECT MAX+1` `[in-tree]`.** Same verdict: correct under
  single-writer, collides under two. The append-only structure is the redeeming strength (monotonic,
  never reused → ABA impossible).

**Torn-tail crash model = WAL torn-tail discipline** (`ledger.py`). A trailing line with no newline
is treated as an unacknowledged torn tail and ignored; the next append overwrites from the last
clean offset; interior problems (JSON-parse failure, non-object, broken `seq` chain, unknown kind)
**raise loudly.** A faithful ARIES/Postgres torn-tail discipline. But:

- **Finding B-3 — no per-record checksum `[in-tree]`.** Integrity is **boundary-based (newline) +
  structural (JSON-parse + monotonic seq chain)**, not checksum-based. This catches a *truncated*
  tail perfectly and most *corrupt* tails via parse-failure (fail-loud, safe direction). The
  residual ARIES gap: a torn write that lands **valid JSON with a plausible seq** would pass
  structural validation. **Severity is low** (single ~4KB fsync'd lines rarely block-split; the
  usual failure is a parse error, caught) — but it is the one nameable divergence from textbook WAL.

**Reconciliation = idempotent recovery / reconstruct-from-effects** (`ledger.py`). Current state is
*derived*, never stored: precedence **gate-verdict > run-liveness > event-claim**; contradictions
surface as `discrepancies` and are **never silently healed**; a dead run with an `in_progress`
claim reports `unknown` and blocks dependents. The consumer cursor refuses to rewind or pass the
generation — a **Kafka-style forward-only offset**. This is exactly the effectively-once pattern
(the log is a *claim*; gate/run/git artifacts are ground truth). One caveat: `reconcile` outranks
the log only when the caller supplies `artifacts`; the "reconstruct from artifacts before acting"
rule (design §7) is a **convention, not a type-enforced invariant.**

**Merge interlock = the Not-Rocket-Science Rule as machinery** (`interlocks.py`). A hook intercepts
`git merge`/`push` to protected refs and demands a fresh PASS gate stamp, written only on PASS,
recording `{branch, head, base, ok, ts}`. But:

- **Finding B-4 — the gate-stamp base-move race (W3), the one real correctness gap `[in-tree]`.**
  `_require_stamp` validates **only the source ref's HEAD** (`head != stamp["head"]` → re-gate). The
  stamp **stores `base` but nothing ever checks `base` against the current target HEAD.** So:
  branches A and B both gate against `base = main@X` in parallel; A merges (`main → Y`); B is
  presented — B's *source* HEAD is unchanged, so the interlock **allows the merge**, even though B
  was only ever proven green against `main@X`, not `main@Y`. This is precisely the **merge-skew /
  stale-base hazard the Not-Rocket-Science Rule forbids.** Exposure depends on merge strategy: a
  rebase/fast-forward *rewrites B's source HEAD* (the existing source-HEAD check *would* catch it);
  a true `git merge` leaves B's source HEAD intact and would **not** be caught. The primitive is
  correct for what it checks (source immutability — a clean CAS on the source) and **incomplete for
  the sequential-merge-of-parallel-branches case, which is the entire reason merge queues exist.**
  **Present at the minimum cap of 2**, and the `base` field the fix needs is *already recorded*.

## 3. W1–W5 → the literature

| Watch item | Maps to | Precondition | Audited status |
|---|---|---|---|
| **W1** stale-generation | OCC backward-validation; lost-update; `MAX+1`; ABA | atomic validation section **or** single-writer | **single-writer only** (B-1/B-2); ABA-immune by append-only; no lock → latent lost-update if a 2nd writer ever appends |
| **W2** write-ahead ordering | WAL invariant / repeating-history; idempotent redo; effectively-once | fsync barrier log-before-effect; replay checks the *effect* (reconcile) before repeating | sound *by construction* for ordering (single-writer, monotonic seq); risk is a code-discipline slip at one write site + the non-checksummed tail (B-3) |
| **W3** gate-stamp vs HEAD race | merge queue / Not-Rocket-Science-Rule; merge skew | serialize merges **and re-gate against the moved target** (or force-rebase so the source-HEAD CAS catches it) | **GAP (B-4).** checks source HEAD, never base; exposed under true-merge, masked under rebase/FF; **the one real correctness hole** |
| **W4** admission warmup math | speculative-execution economics; Zuul AIMD; OCC-under-contention; occupancy forecast | size concurrency to independence/pass rate; charge each pipeline its cold prefix; back off on rework | admission already forecasts P95 + per-pipeline warmup + a surface-contention cap; theory says **make the cap adaptive to measured false-eviction/rework**, not fixed 2–4 |
| **W5** worktree conflicts | MVCC private-workspace + integration; **semantic** merge conflict | disjoint write sets **and** re-test the *merged* tree | worktree isolation OS-clean; residual hazard is **semantic** and collapses into W3 (re-test the merged result) |

Distributed ID allocation is not a separate item — it is the *same coordination lesson as W1*,
surfacing as `seq = len(events)+1`; the reserve/compose migration path (HiLo/Snowflake/UUID)
applies only if the log ever goes multi-writer.

## 4. Verdict and the hardening backlog

**Are the primitives textbook-correct?** Four of five are sound **for the single-writer,
low-concurrency regime the harness actually runs in** — and their soundness is *contingent on that
regime rather than self-enforcing*:

- **Generation stamp / OCC:** correct as backward-validation, ABA-immune — but resting on an
  **unenforced single-writer invariant** (no lock behind the validation window). The low 2–4 cap
  defuses OCC's *performance* pathology (there is nothing to starve; the sole writer never
  contends) but **not its correctness precondition** — two writers at cap=2 would be enough to lose
  an update. *The cap doesn't save you; the writer count does.*
- **WAL / event log:** faithful torn-tail + idempotent-recovery discipline; the only ARIES
  divergence is **no per-record checksum** (B-3, low severity, fail-loud).
- **Merge interlock:** a real Not-Rocket-Science gate with a **genuine hole (B-4): validates source
  HEAD, never base**, so sequential merges of parallel branches can land green-against-stale-base
  under a true-merge strategy. **The single highest-value fix in the cluster**, present at cap=2.
- **Worktree isolation:** OS-clean; residual risk (W5) is semantic conflict, which reduces to W3.

**Hardening backlog, priority order** (research findings, not yet acted on — the harness is in
research-and-synthesis mode and machinery is upstream-owned):

1. **Close B-4 / W3 (highest value, mechanically simple).** Bind the gate stamp to `base` and
   invalidate on base-move — the `base` field is *already recorded in the stamp*, it just isn't
   checked in `_require_stamp`. This forces a re-gate of the trailing branch against the moved
   target, exactly as GitHub/Zuul re-run CI on the trailing PR. Alternative: mandate rebase-before-
   merge so the existing source-HEAD CAS catches it transitively. **Most likely to produce the
   harness's first *silent* wrong merge the day two tasks finally run in parallel.**
2. **Assert the single-writer invariant (B-1).** Either add an advisory `flock` around the append
   (cheap insurance; makes W1's precondition self-enforcing instead of architectural), or add a
   selftest that fails if any non-orchestrator path can reach `EventLog.append`. Pre-registering W1
   without a lock is trusting a property the code doesn't assert.
3. **Make the concurrency cap adaptive (W4).** The admission machinery already logs rework/merge
   cost; feed it into an AIMD-style cap (push toward 4 at high independence/pass rate; halve on
   observed false-eviction) instead of a fixed 2–4.
4. **Optional: per-record CRC on the event log (B-3).** Low severity given single-line fsync'd
   appends; closes the last ARIES divergence if the log ever grows multi-line records or lands on
   a filesystem that reorders block writes.
5. **Optional: elevate "reconstruct from artifacts before acting" from convention to invariant** —
   the `reconcile` outranks-the-log guarantee holds only when the caller passes `artifacts`.

**The framing to keep:** the concurrency machinery is *correct for a single-writer loop* and its
first real test is the day W1–W5 stop being unobserved. The cluster's contribution is turning five
pre-registered hunches into precise distributed-systems hazards with a named, code-verified bug
(B-4) at the front of the queue — before any of them has fired.
