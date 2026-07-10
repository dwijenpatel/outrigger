# Memory & lessons — storage, retrieval, and relevance filtering

**Date:** 2026-07-06
**Method:** 11 cloned popular repos mined by parallel analysts; file paths cite the clones at
`/Users/dwijen/repos/<name>`. Claims are tagged `[measured]` (code-backed or data-backed in the
repo), `[author-run]` (single-source measurement, unreplicated), or `[marketing]` (asserted,
unmeasured). "None" is reported as a finding, not an omission.
**Operator's questions:** how are people storing/collecting memories and lessons, and pulling from
them? How do they pull prior-work value into a current task without diluting the context window?
How do they decide what is worth storing for future related efforts?

---

## 1. Headline findings

1. **Every mature system converges on files-on-disk + explicit curation policy; none converges on
   a database-first design except ruflo** (SQLite+HNSW), and even ruflo's ADR-174 confesses its
   "consolidate" worker was a stub for 6,000+ commits — *everything recorded, nothing distilled*
   (`/Users/dwijen/repos/ruflo/v3/docs/adr/ADR-174-memory-distillation-self-optimization.md`).
   Capture-without-distillation is the ecosystem's documented failure mode.
2. **The dominant what-to-store primitive is promotion-by-recurrence with a confidence score**:
   everythingclaudecode promotes project→global only at 2+ projects with avg confidence ≥0.8;
   alirezarezvani/claude-skills promotes MEMORY.md entries recurring 2–3×; gstack quarantines
   per-site domain skills until 3 successful uses. Independent recurrence, not first sighting, is
   the storage trigger.
3. **Dilution control is overwhelmingly structural, not semantic.** Path-scoped rule files, hard
   shard caps, allowlists, and lazy per-mode loading appear everywhere; vector search appears in
   exactly one repo (ruflo). Nobody retrieves lessons by embedding similarity in a shipped,
   popular Claude Code workflow.
4. **Negative memory (what NOT to retry) is the sharpest under-exploited idea**, appearing in four
   independent forms: career-ops's retracted-claims hard gate, ruflo's anti-pattern archive of
   rejected mutations, everythingclaudecode's mandatory "What NOT to Retry" resume section, and
   no-mistakes's round-history of user-ignored findings.
5. **Nobody measures whether retrieved lessons improve outcomes.** All effectiveness claims about
   memory systems in these 11 repos are `[author-run]` at best, usually `[marketing]`. Ruflo's
   flywheel is the closest to closed-loop, but it benchmarks retrieval of its own memory
   subsystem, not end-to-end task outcomes.
6. **Only one repo engineers memory injection for prompt-cache stability** (planning-with-files:
   timestamp-free fixed-shape ledger summaries, pointer-not-payload injection). Everyone else's
   per-session/per-turn injection churns the prefix — invisible to them because none of the 11
   repos has any prompt-cache awareness in its cost model.

---

## 2. Per-repo inventory

Axes per repo: **stored** (what/when/format) → **retrieved** (always-loaded / searched / injected
per task) → **filtered** (relevance & curation) → **forgotten** (pruning).

### gstack (`/Users/dwijen/repos/gstack`) — the most complete layered design
- **Stored:** four stores. (1) Per-project `learnings.jsonl` — every skill's postamble logs
  durable quirks with confidence + source at completion. (2) `decisions.jsonl` — append-only
  event log (decide/supersede/redact) where "active" is *computed, never mutated*
  (`lib/gstack-decision.ts`); free text is injection-checked and secret-scanned on write.
  (3) gbrain digests (product/goals/user-profile/recent-decisions/salience) cached by a binary.
  (4) Question-preference distillation: `/plan-tune`'s "dream cycle" turns free-text interview
  answers into preference proposals the user approves one by one, 3 distills/day cap
  (`plan-tune/SKILL.md`).
- **Retrieved:** mixed-mode. Learnings are query/type/limit-searched (`gstack-learnings-search`),
  surfaced at skill start, and **injected into specialist reviewer prompts** — per-task curated
  injection. Recent decisions ride the always-loaded preamble with the rule "do not silently
  re-litigate; if reversing, say so." gbrain digests load at planning-skill start via cache
  binary instead of re-grepping (`office-hours/SKILL.md` lines 882–917).
- **Filtered:** explicit negative what-to-store policy — "do not log obvious facts or one-time
  transient errors" (`learn/SKILL.md`); per-repo read-write/read-only/deny trust tiers on gbrain;
  salience allowlist for privacy; domain skills quarantined until 3 successful uses
  (`docs/domain-skills.md`).
- **Forgotten:** `/learn` prunes on staleness (referenced file deleted) and contradiction (same
  key, opposite insight); dedup is key|type latest-wins; taste memory decays 5%/week (README).
- Evidence quality: mechanics are code-backed `[measured]`; no evidence the learnings improve
  outcomes.

### mattpocock/skills (`/Users/dwijen/repos/skills`) — curation doctrine, no automation
- **Stored:** (1) `CONTEXT.md` domain glossary + `docs/adr/` maintained inline by
  `/domain-modeling`, gated by a three-condition ADR test: hard to reverse AND surprising without
  context AND a real trade-off (`skills/engineering/domain-modeling/SKILL.md`). (2) `/teach`
  learning records — ADR-style, numbered, with the strictest what-to-store language in the
  corpus: *"Coverage is not learning. Wait for evidence"*; records are decision-grade insights,
  not journals (`skills/productivity/teach/LEARNING-RECORD-FORMAT.md`). (3) `/triage`'s
  `.out-of-scope/` KB of rejected requests, consulted for prior-rejection matching.
- **Retrieved:** by prose pointer only — no automated retrieval, no search, no injection. The
  wayfinder rule "map is an index, not a store" (one decision lives in exactly one ticket; the
  map gists and links; open work found by query) is the cleanest index/store separation shipped
  anywhere (`skills/in-progress/wayfinder/SKILL.md`).
- **Filtered/forgotten:** contradicted records get `Status: superseded` rather than deletion —
  "the evolution is signal." No cross-project memory at all.

### no-mistakes (`/Users/dwijen/repos/no-mistakes`) — within-run memory only
- **Stored/retrieved:** `internal/pipeline/steps/round_history.go` feeds each review/fix round a
  sanitized record of prior rounds **including findings the user deliberately left unselected**,
  so follow-up passes don't re-report ignored findings; `internal/intent/cache.go` caches
  per-session intent summaries. **No cross-run lessons store, no retrieval, no what-to-store
  policy — absence is the finding** in a heavily-engineered validation product.

### everythingclaudecode (`/Users/dwijen/repos/everythingclaudecode`) — the flagship pipeline
- **Stored:** continuous-learning-v2: PreToolUse/PostToolUse hooks log every tool call to
  per-project `observations.jsonl`; a background Haiku "observer" clusters them into atomic
  YAML "instincts" with confidence 0.3–0.9 under `~/.claude/homunculus/`
  (`skills/continuous-learning-v2/SKILL.md`). Load-bearing rationale: **hooks fire 100% of the
  time, skills fire probabilistically ~50–80%, so capture must be hook-side, never prompt-side.**
  Session memory: Stop hook persists a summary; `/save-session` format mandates "What worked
  (with evidence)", "What NOT to retry (with reasons)", exact next step
  (`commands/save-session.md`, `resume-session.md`).
- **Retrieved:** SessionStart hook auto-injects the latest ≤7-day session summary (fat-summary
  resume, not ledger-rebuilt); `/evolve` clusters instincts into generated skills/commands.
- **Filtered:** scope decision table (framework conventions = project; security/git practices =
  global); **promotion to global only when seen in 2+ projects at avg confidence ≥0.8** — an
  independent-confirmation rule, convergent with the operator's own memory policy.
- **Forgotten:** confidence decay on user correction or disuse.
- Evidence quality: architecture is real code (`scripts/hooks/`), effectiveness `[marketing]`.

### andrej-karpathy-skills (`/Users/dwijen/repos/andrej-karpathy-skills`) — **none.**
No memory, lessons, or retrieval of any kind. A 2.3KB advisory CLAUDE.md. Finding: the most
viral prompt packs carry zero memory machinery — memory is not what sells installs.

### caveman (`/Users/dwijen/repos/caveman`) — memory compression, not memory
- **Stored/retrieved:** none here (cross-session memory is the separate cavemem repo). What it
  ships is `/caveman-compress`: LLM-rewrites memory files (CLAUDE.md, todos, preferences) into
  compressed prose for **~46% input-token savings `[author-run]` on 5 real files**, gated by a
  deterministic validator (code fences byte-identical, headings/paths preserved) with
  cherry-pick-only repair and `.original.md` backups
  (`skills/caveman-compress/scripts/validate.py`). Relevant lesson: the *cost* of always-loaded
  memory files is real enough that a compression product for them went viral.

### planning-with-files (`/Users/dwijen/repos/planning-with-files`) — per-task memory, cache-safe
- **Stored:** per-task only: `findings.md` as the research store with a 2-Action Rule (flush
  after every 2 view/browser ops), an Errors Encountered table, a 3-Strike protocol, and a
  "Never Repeat Failures" rule (`skills/planning-with-files/SKILL.md`, `templates/task_plan.md`).
  README FAQ explicitly disclaims cross-session memory: *"planning continuity, not retrieval."*
- **Retrieved — the cache-hygiene standout:** injected content is engineered for KV-cache
  stability: timestamps sed-normalized to `T00:00:00Z` (`scripts/inject-plan.sh` lines 284–289);
  the v3 ledger summary is fixed-shape, zero timestamps, zero free text — "KV-cache stable by
  construction" (`scripts/ledger-summary.sh`); the Pi cache-safe mode replaces dynamic injection
  with a **byte-identical constant reminder telling the model to READ the files itself** —
  pointer-not-payload (`docs/cache-safe-diagram.md`). Also injection-hardening: progress.md is
  not attestation-covered, so the summary layer synthesizes from disk rather than quoting it.
- This is the only repo of 11 that arrived independently at the operator's
  cache-misses-are-the-real-spend insight and applied it to memory injection.

### alirezarezvani/claude-skills (`/Users/dwijen/repos/claude-skills`) — curation atop auto-memory
- **Stored:** the self-improving-agent plugin treats Claude Code auto-memory as
  **capture-not-curation** and layers a promotion lifecycle on top: `/si:review` flags MEMORY.md
  entries recurring 2–3× as promotion candidates; `/si:promote` graduates them to CLAUDE.md
  (enforced instructions) or **path-scoped `.claude/rules/*.md`** (loaded only when matching
  files open); `/si:extract` converts proven patterns into standalone skills; a PostToolUse
  error-capture hook appends structured failure entries (~30 tokens, only on error)
  (`engineering-team/self-improving-agent/skills/self-improving-agent/SKILL.md`,
  `hooks/error-capture.sh`, `reference/promotion-rules.md`).
- **Filtered:** relevance handled structurally — 200-line MEMORY.md head, topic files on demand,
  path-scoped rules with `paths:` globs = zero context overhead unless the matching file is open.
- Evidence quality: policy documents `[measured]` (they exist as shipped prompts); effect
  `[marketing]`.

### superpowers (`/Users/dwijen/repos/superpowers`) — memory removed from core
- **None in the current tree.** A full conversation-memory system (embeddings indexer,
  sessionEnd hook, search tool) existed and was **removed in commit 87f0422** to the satellite
  repo obra/superpowers-skills. Residue proves lessons-capture built the product: verification-
  before-completion cites "From 24 failure memories" as its evidence base, and the
  writing-skills methodology is itself a lessons loop — verbatim rationalizations from failed
  runs become rationalization-table rows (`skills/writing-skills/SKILL.md`). The per-run
  `.superpowers/sdd/progress.md` ledger is resumability, not cross-session memory. Finding: a
  methodology-first project with a 94% PR rejection bar decided embedded memory was not worth
  core residency — the lessons got baked into *prompt text* instead of a queryable store.

### career-ops (`/Users/dwijen/repos/career-ops`) — allowlisted memory + hard negative gate
- **Stored:** user-layer profile files (cv.md, `_profile.md`, voice-dna.md); accumulating
  interview memory — story-bank.md, question-bank.md, speaker-labelled session transcripts with
  per-answer competency tags; `scan-history.tsv`. Writing style is extracted once from samples,
  cached in `_profile.md`, with an explicit re-scan-only-on-new-samples invalidation rule
  (`modes/_shared.md`).
- **Retrieved:** modes read exactly the files their Inputs section names; `modes/patterns.md`
  re-mines transcripts on demand (clustering where fluent answers land vs where the user
  applies) — disk-is-the-memory applied to conversations.
- **Filtered — inverted relevance model:** `modes/_shared.md` declares an EXCLUSIVE
  source-of-truth allowlist and **bans auto-memory and cross-session inference** from
  user-facing content. Memory is allowlisted files, never accumulated context.
- **Negative memory as hard gate:** `interview-prep/retracted-claims.md` — claims the candidate
  conceded are indefensible are appended and **never reused, even if the user repeats them**
  (`modes/interview/practice.md`). Strongest anti-regression memory device in the corpus.

### ruflo (`/Users/dwijen/repos/ruflo`) — the deep end, with an honest confession
- **Stored:** AgentDB (SQLite) + HNSW vector index (`[author-run]` 1.9×–4.7× vs brute force,
  honest small-N caveats) + RVF snapshots (`v3/@claude-flow/memory/src/`).
- **Retrieved:** hybrid vector+FTS5; a rule-shard retriever that classifies task intent by regex
  and injects **at most 5 shards plus a constitution, filtered by risk class**
  (`v3/@claude-flow/guidance/src/retriever.ts`) — the only hard numeric retrieval cap in the 11.
- **Filtered — provenance tiers as code, not prose:** ADR-174: only execution-observed feedback
  (tier `oracle:test-exec`) can produce PROMOTED patterns; structural clusters stay
  searchable-but-unpromoted; co-occurrence edges carry "may rank retrieval, may NOT justify
  autonomous action" enforced in code. A memory write gate adds per-agent authority scopes,
  TTL, confidence decay, write rate limits, contradiction detection
  (`v3/@claude-flow/guidance/src/memory-gate.ts`).
- **Negative learning:** every REJECTED mutation archived as
  {mutation, stage_failed, evidence} so optimization never re-discovers identical failures
  (`harness-qualification.ts`).
- **Forgotten:** TTL + decay + rate limits. Caveat: headline "self-learning" claims rest on
  self-supervised retrieval benchmarks `[author-run]`, not coding outcomes; README numbers are
  `[marketing]` until traced to an ADR.

---

## 3. Comparison against the known patterns

| Pattern | Store | Index/retrieval | Curation | Dilution control |
|---|---|---|---|---|
| **Claude Code auto-memory** | one fact per file | always-loaded MEMORY.md index | none built-in (capture-only) | index head only; topic files on demand |
| **CLAUDE.md convention** | monolithic prose | always-loaded, every turn | manual | none — pays full context cost always (why caveman-compress exists) |
| **cc-agent-harness lessons corpus (design)** | orchestrator-owned file | curated injection per spawn | orchestrator-only writes; workers read-only | never resident in the prefix |
| gstack | 4 JSONL/digest stores | search + preamble + per-task injection | negative filter + trust tiers + quarantine | carve/lazy sections |
| everythingclaudecode | observations→instinct YAML | SessionStart injection + /evolve | recurrence≥2 projects @ ≥0.8 confidence | scope table |
| claude-skills self-improving | MEMORY.md → CLAUDE.md → rules/ | path-scoped auto-load | recurrence 2–3× promotion | `paths:` globs = zero idle cost |
| ruflo | SQLite+HNSW | vector+FTS, 5-shard cap | provenance tiers in code | hard cap + risk class |
| career-ops | allowlisted files + transcripts | per-mode Inputs list | allowlist; ban on auto-memory | exclusivity |
| planning-with-files | per-task findings/ledger | fixed-shape summary / pointer | n/a (disclaims memory) | cache-stable-by-construction |

Two ecosystem verdicts on the known patterns:
- **Auto-memory is treated as raw capture needing a curation layer** — claude-skills builds a
  promotion lifecycle on it precisely because MEMORY.md accumulates without judgment; career-ops
  goes further and bans it from outputs entirely.
- **Always-loaded CLAUDE.md is treated as a cost problem** — caveman-compress (46%
  `[author-run]` savings) and gstack's carve system (-42% to -59% `[measured]`, CI-pinned) both
  exist to shrink always-resident prose. The ecosystem monetized the dilution the operator is
  trying to avoid.

---

## 4. The design space, extracted

**What-to-store policies** (ordered weak→strong):
1. Capture everything, curate later (auto-memory; ECC observations) — proven to rot without a
   distiller (ruflo's 6,000-commit stub).
2. Negative filters at write time: "no obvious facts, no one-time transient errors" (gstack);
   "coverage is not learning, wait for evidence" (Pocock); ADR triple criterion (hard to
   reverse / surprising / real trade-off).
3. Recurrence thresholds before promotion: 2–3× (claude-skills), 2+ projects @ ≥0.8 (ECC),
   3 successful uses (gstack quarantine).
4. Provenance tiers enforced in code: only execution-observed evidence can drive action (ruflo
   ADR-174) — the strongest policy shipped anywhere.
5. Negative memory as first-class: retracted-claims hard gate (career-ops), rejected-mutation
   archive (ruflo), "What NOT to Retry" (ECC).

**Retrieval triggers:**
- Always-loaded index (MEMORY.md; gstack decision preamble) — cache-friendly, dilution-hostile.
- Searched-on-demand (gstack learnings-search; ruflo vector+FTS) — rare; only ruflo is semantic.
- Injected-per-task by a curator (gstack learnings → specialist prompts) — the closest shipped
  analog to the harness's per-spawn curated injection.
- Structurally scoped auto-load (claude-skills `paths:` globs; career-ops per-mode Inputs) —
  the cheapest relevance filter in the corpus: relevance decided by *file location/task type*,
  no model judgment needed.
- Pointer-not-payload (planning-with-files cache-safe mode; Pocock/claude-skills handoff
  reference-by-path) — moves volatile content out of the prefix onto the read path.

**Dilution controls:** hard caps (5 shards), path scoping, exclusive allowlists, lazy
sections behind read-when-applicable indexes, index/store separation ("map is an index, not a
store"), and — uniquely — byte-stable injection shapes for cache preservation.

**Forgetting:** staleness = referenced-file-deleted (gstack), contradiction detection (gstack,
ruflo), confidence decay on correction/disuse (ECC), TTL + write rate limits (ruflo), scheduled
decay (gstack taste 5%/week), and supersession-not-deletion (Pocock — keep the evolution as
signal). Negative memory is exempted from forgetting (career-ops retractions are permanent).

**Write-path discipline (cross-cutting):** deterministic capture must live in hooks, not prompts
(ECC: hooks fire 100%, skills ~50–80%); single-writer ownership prevents corruption (gstack
event-sourcing with computed "active"; planning-with-files single-writer + per-agent ledgers) —
both convergent with the harness's orchestrator-owns-the-file rule.

**The combination nobody ships** — each element exists somewhere; no repo has more than two:
1. **Task-scoped curated injection** (orchestrator picks lessons per spawn) — gstack only,
   partially.
2. **Provenance/confidence gating of what may be injected** (execution-observed > inferred) —
   ruflo only, and only for its own retrieval subsystem.
3. **Cache-safe placement** (lessons enter as a stable-shape suffix block or file pointer; the
   prefix stays byte-identical) — planning-with-files only.
4. **Closed-loop utility feedback** — did the injected lesson get used / did the task go better?
   Adjust confidence from outcomes at task boundaries. **Nobody ships this at all.** Every
   confidence score in the ecosystem is updated by recurrence or user correction, never by
   measured task outcome.

---

## 5. What the operator's project adds

Mapping cc-agent-harness assets onto the observed gaps:

- **Lessons-corpus design (orchestrator-owned, workers read-only, curated per-spawn injection,
  never prefix-resident)** already combines elements 1 and 3 above — a combination no surveyed
  repo ships. Ecosystem precedent to cite: gstack's learnings-into-specialist-prompts (per-task
  injection), planning-with-files' pointer-not-payload (cache safety), single-writer ledgers in
  both. The design is convergently validated, not idiosyncratic.
- **Cache economics findings (reads discounted; misses+output are the spend; ~5-min TTL)** are
  the missing rationale for *where* memory lives in context. 10 of 11 repos are cache-blind;
  the one that isn't (planning-with-files) arrived at prefix stability without the
  subscription-window measurement that explains why it matters. The harness can state the rule
  the ecosystem lacks: *an always-loaded lessons index is only cheap if byte-stable; a curated
  per-task lessons block is only cheap if appended after the stable prefix.*
- **Closed-loop control at task boundaries + the ~30x variance finding** supply element 4, the
  genuinely unshipped piece: score each stored lesson by whether firings that received it
  outperformed firings that didn't (the validator's pass/fail at the merge gate is a free,
  blind outcome label — no self-report). No surveyed system has an outcome-labeled lessons
  store; ruflo's receipts are the nearest shape and its bootstrap-CI significance gate
  (`harness-improvement-ledger.ts`) is the right statistical tool to borrow given 30x variance.
- **BLIND validation** gives the harness something no memory system here has: a trustworthy
  outcome signal. Everyone else's "did it work" is the implementer's own claim, which is exactly
  what their memory then learns from — reward-hacked outcomes can poison a lessons store.
- **Observations-ledger practices worth importing wholesale:** negative-memory ledger enforced
  as a hard gate (career-ops retracted-claims → a "retracted approaches" ledger firings must
  never re-attempt); "What NOT to Retry with reasons" as a mandatory resume section (ECC);
  supersession-not-deletion (Pocock); staleness = referenced-file-deleted (gstack); hook-side
  deterministic capture (ECC).

---

## 6. Verdict on the operator's hypothesis

The operator asked: *"how are people storing and collecting memories and lessons? And pulling
from those memories and lessons? We want to pull information from previous/other work that could
benefit a current task, but exclude irrelevant information that dilutes the context window. We
also want to be smart about what we store."*

**The instinct is sound and ecosystem-validated — with three honest corrections.**

1. **"Pull what benefits the current task, exclude the rest" — yes, and the winning mechanism is
   cheaper than it sounds.** The ecosystem's answer to relevance is overwhelmingly structural
   (path globs, task-type scoping, per-mode input lists, hard caps), not semantic search. Only
   ruflo does embedding retrieval, and its measured wins are for its own retrieval benchmarks,
   not task outcomes. At the harness's corpus scale (tens-to-hundreds of lessons), an
   orchestrator that already knows the task's files and type can select lessons by tags/paths
   deterministically. Do not build vector retrieval first; the evidence says it is the least
   adopted and least outcome-proven piece of the stack.
2. **"Be smart about what we store" — the ecosystem already converged on the policy, adopt it
   rather than invent it.** Write-time negative filters + recurrence-before-promotion +
   provenance tiers + first-class negative memory. One addition the harness is uniquely
   positioned to make: gate storage and confidence on the *blind validator's* outcome, not the
   implementer's self-report. That closes a poisoning channel every surveyed system leaves open.
3. **The uncomfortable finding: nobody has evidence that any of this helps.** Across 11 repos
   there is not one measurement that a lessons store improved task outcomes — every
   effectiveness claim is `[author-run]` or `[marketing]`, and the deepest system (ruflo)
   admits its distiller was dead code for months while marketing said "self-learning." So "is
   this a bad idea?" — storing lessons is not a bad idea, but *building a large memory
   subsystem before instrumenting utility would be.* The failure mode to fear is not dilution
   (solvable structurally) but rot: an ever-growing corpus nobody prunes and nothing validates.
   The harness's differentiated move is small: a curated, capped, outcome-labeled lessons file,
   injected per spawn after the stable prefix, with utility measured at the merge gate from
   day one. That exact combination — curation + provenance + cache-safe placement + closed-loop
   utility — is shipped by no one, and three of its four pieces already exist in the harness.
