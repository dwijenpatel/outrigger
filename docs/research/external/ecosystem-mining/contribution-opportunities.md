# Contribution opportunities — ranked shortlist (capstone)

> **Provenance.** Written 2026-07-06 as the capstone of the ecosystem-mining study.
> Inputs: the 11 per-repo analyses (gstack, mattpocock/skills, no-mistakes,
> everything-claude-code, andrej-karpathy-skills, caveman, planning-with-files,
> alirezarezvani/claude-skills, superpowers, career-ops, ruflo) and the five theme
> docs plus landscape in this directory (`landscape.md`,
> `verification-and-blind-gating.md`, `spec-elicitation-and-planning.md`,
> `parallelization-and-decomposition.md`, `limits-resume-and-wake.md`,
> `memory-and-lessons.md`). Star counts and activity data are as-of the analysis
> dates (2026-07-05/06); several local clones are stale (everything-claude-code is
> ~4 months behind upstream) — **re-fetch any target repo before scoping a PR**.
> Evidence caveat: the operator's own cache-discount and 30x-variance findings are
> single-source; per the standing confirmation rule, every submission that leans on
> them must ship the methodology and a reproducible measurement, not just the claim.

## The six hypotheses (legend)

Labels used throughout, matching the theme docs:

- **H1 — Blind validation:** implementer/validator context separation with
  vault-held tests and clean-checkout gating closes the reward-hacking hole
  (agents editing tests to pass). Verified unoccupied in 11/11 repos.
- **H2 — Determinate specs:** relentless spec elicitation to a machine-checkable
  determinacy bar cuts wall-clock time. Question-asking is commoditized; the
  *exit bar* and enforcement are not.
- **H3 — Stub-and-seams:** interface-first decomposition lets weaker models
  implement in parallel into pre-cut seams. Qualified support only; the measured
  experiment does not exist anywhere yet.
- **H4 — Wake-on-reset (parking):** long runs should park at task boundaries near
  window exhaustion and automatically resume at reset. 0/11 repos have any
  window awareness.
- **H5 — Wake shape (thin re-entry):** the correct wake is a fresh session
  rebuilt from disk ledgers, not a fat transcript resume (cache-cold economics).
- **H6 — Cache/window economics:** cache reads are heavily discounted against
  subscription windows; misses + output are the real spend; ~30x same-task
  variance means closed-loop control at task boundaries, not open-loop budgets.

## Ranking method

Score = (value to target community × leverage from existing assets) ÷ effort,
weighted by acceptance likelihood (activity + demonstrated PR-friendliness from
the per-repo analyses). Acceptance weighting matters more than idea quality:
the sample is bimodal between genuinely open repos (career-ops, no-mistakes,
planning-with-files, ECC upstream, claude-skills, caveman, gstack) and
effectively closed ones (mattpocock/skills: zero external merges ever;
superpowers: 94% stated rejection; ruflo: ~97% single-author; karpathy-skills:
stale). Ideas routed at closed repos are demoted or moved to the standalone
channel regardless of merit.

---

## Ranked shortlist

### 1. career-ops: `--wait-for-reset` auto-resume for batch runs — **PR** (serves H4, sets up H6)

The single best acceptance × leverage × value ratio in the study. career-ops's
`batch/batch-runner.sh` already detects Claude usage-limit pauses as a
first-class `paused_rate_limit` state and already greps the reset phrase
(`resets [0-9:]+[ap]m`, ~line 377) — then throws the timestamp away and makes
the human watch the clock (`--resume-paused`, documented in FAQ and
RUNNING_ON_A_BUDGET). The repo is the friendliest in the sample: community PRs
merge weekly, there is a contribution ladder, and the fix is in the repo's own
idiom (pure bash, TSV state, no new deps).

- **Minimal landable slice:** opt-in `--wait-for-reset` flag that parses the
  already-matched reset time (handle am/pm rollover to next day), sleeps until
  then, re-checks that the window actually freed (shared cross-surface pool —
  never trust the clock alone), then invokes the existing resume path. Preserve
  `paused_rate_limit` on disk for crash safety; add a bounded max-wait. Docs:
  `modes/batch.md` + FAQ. Open an issue first (feature-sized per CONTRIBUTING).
- **Where:** santifer/career-ops — `batch/batch-runner.sh`, `modes/batch.md`,
  `docs/FAQ.md`.
- **Expected pushback:** the runner is CLI-agnostic and the reset phrase is
  Claude-specific — frame as a Claude-focused opt-in that no-ops cleanly
  elsewhere; possible ask for a post-wake re-verification/backoff loop (have it
  in v1).
- **Effort:** M — 1-2 days including issue, tests, docs.
- **Follow-up in the same repo (after trust is established):** the
  cache-prefix fix to `batch/batch-prompt.md` (move `{{URL}}`/`{{ID}}`
  placeholders below the ~400-line static rubric so parallel workers share a
  byte-identical prefix) plus a budget-doc section on scheduling densely inside
  the cache TTL — serves H6 and is the concrete public demonstration of the
  cache-economics finding. Needs a small before/after measurement to clear
  their evidence bar.

### 2. no-mistakes: flag *modified* test files in fix rounds — **PR** (serves H1)

The cheapest way to plant the anti-reward-hacking flag in a shipping product.
`detectNewTestFiles` (`internal/pipeline/steps/common_diff.go`) forces human
approval when a fix-round agent writes NEW test files, but silently passes an
agent that *edits an existing test to make it pass* — the exact documented
failure mode. Extending a precedented tripwire in the same file respects the
maintainer's "fixed pipeline" constraint; ~10 external contributors have merged
PRs; velocity is high.

- **Minimal landable slice:** `detectModifiedTestFiles` (diff the test-path set
  between round-start ref and post-fix tree), emit an **ask-user** finding (not
  a block — kills the false-positive objection) wired into the test/lint fix
  paths, plus one unit test copying the existing pattern. PR body cites the
  reward-hacking evidence.
- **Where:** kunchenguid/no-mistakes — `internal/pipeline/steps/common_diff.go`,
  `test.go`. Note the dogfooding rule: the PR must itself be raised through
  no-mistakes (`no-mistakes init --fork-url`); budget setup time. Do not spoof
  the CI body marker.
- **Expected pushback:** "legit fixes sometimes must update tests" — answered by
  ask-user severity and scoping to fix mode only; hot-file churn — keep it
  small and rebase within days.
- **Effort:** S — half a day of code; ~1 day total with the dogfooding setup.

### 3. planning-with-files: implement the documented-but-missing AcceptanceCheck gate — **PR** (serves H1)

The most *sanctioned* H1 opening in the ecosystem: the maintainer already wrote
the full security design (per-phase `AcceptanceCheck` shell commands,
allowlist-at-attest-time, never run commands from unattested plans) in
`templates/task_plan_autonomous.md` — and no shipped script implements any of
it, so the completion gate today trusts the agent's self-reported
`Status: complete`. Community PRs land within days; releases are weekly.

- **Minimal landable slice:** wire AcceptanceCheck into
  `check-complete.sh --gate` for gated mode only: `attest-plan.sh` records the
  command allowlist at attest time; the gate executes only allowlisted commands
  from attested plans and treats a failing check as "phase not complete."
  ~10 tests mirroring `tests/test_gate.py`. sh-only for round one; sync the
  mirrored script locations (parity tests enforce this). Issue first, quoting
  the maintainer's own template text back at him.
- **Where:** OthmanAdi/planning-with-files —
  `skills/planning-with-files/scripts/{check-complete.sh,attest-plan.sh}` + tests.
- **Expected pushback:** security review of executing plan-declared commands
  (lean on the maintainer's written design verbatim); the ~13-variant
  duplication tax; a Windows-parity ask (offer the `.ps1` port as a follow-up —
  itself a named-gap PR in `docs/evals.md`).
- **Effort:** M — 2-4 days including variant syncing.

### 4. Standalone: wake-on-reset daemon for headless Claude runs — **BUILD** (serves H4 + H5 + H6)

The limits theme doc's explicit verdict, and the clearest demand/supply gap in
the study: six open native feature requests, zero window awareness in 11 repos,
and only one ~787-star community script in the niche. This is where three
operator assets compound: statusline `rate_limits` prior art, boundary-parking
design, and the cache-cold finding that makes fresh-from-ledger the correct
wake shape (a fat `--resume` reprocess burns the freshly reset window).

- **Minimal landable slice (v0.1):** one small CLI + LaunchAgent: (a) reader
  for the statusline rate_limits JSON dump; (b) a parkfile format written at a
  task boundary (what to run on wake, cwd, ledger paths); (c) a **user-level
  macOS LaunchAgent** waker (not cron/LaunchDaemon — keychain OAuth constraint)
  that re-checks `used_percentage` before waking; (d) wake = fresh `claude -p`
  seeded from disk state, with `--resume --fork-session` as the opt-in mode for
  irreplaceable context. Pre-ship verification tasks from the theme doc:
  confirm the limit-error exit text in `-p` mode and the `session_id` field
  name in the `-p` JSON result.
- **Distribution:** documented integrations rather than a bare repo —
  career-ops batch (natural cross-link once item 1 lands), planning-with-files
  community table, superpowers marketplace, later a ruflo plugin. Merged PRs
  from items 1-3 are the credibility trail.
- **Expected pushback/risk:** the announced-then-paused plan change that would
  move `claude -p`/SDK usage off subscription windows would dissolve the
  premise — hedge it in the README explicitly; Linux (systemd timer) can wait.
- **Effort:** M for v0.1 (~a week); L to polish multi-integration.

### 5. everything-claude-code (upstream): cost-tracker cache-token fix — **PR** (serves H6)

A clean, small correctness fix carrying the cache-economics finding into the
highest-traffic config collection: `scripts/hooks/cost-tracker.js` prices
`input_tokens`/`output_tokens` only and silently ignores
`cache_read_input_tokens`/`cache_creation_input_tokens`, so every estimate in
`~/.claude/metrics/costs.jsonl` is wrong in real sessions where cache reads
dominate.

- **Minimal landable slice:** price cache reads at 0.1x and cache writes at
  1.25x, add a cache-hit-rate field, extend `tests/hooks/` following existing
  patterns. Offer the cache-hygiene SKILL.md (stable prefixes, TTL scheduling,
  with measured numbers) as a separate follow-up PR, not bundled.
- **Where:** affaan-m/everything-claude-code — **upstream, not the marshall0524
  fork this clone tracks.** Mandatory recon first: the clone is ~4 months
  stale and the repo restructures aggressively; confirm the file still exists
  and check recent merged PRs for cross-harness mirror expectations.
- **Expected pushback:** mirror/translation scope inflation; possible pricing
  table bikeshed. Keep it dependency-free and per-type-checklist compliant.
- **Effort:** S — hours of code; half a day with recon.

### 6. caveman: issue-with-data — rate-limit-weighted savings + n≥3 eval variance — **ISSUE → 2 small PRs** (serves H6)

An 85k-star repo whose honesty docs *solicit exactly this contribution*.
`docs/HONEST-NUMBERS.md` closes with "Found a workload where our numbers are
wrong? Open an issue with the A/B", and `caveman-stats.js` carries a code-level
guard built on the assumption that input+cache tokens dominate limit accounting
— which the cache-read-discount finding inverts: output compression is worth
*more* against subscription windows than caveman currently claims. Separately,
`evals/README.md` self-declares single-run-per-arm as its weakest methodology —
the 30x-variance finding is the argument for n≥3 with confidence intervals.

- **Minimal landable slice:** one issue with a reproducible A/B measurement
  (their established pattern — data first, then PRs): PR (a) updates
  HONEST-NUMBERS.md + the `outputReductionPct()` guard commentary; PR (b) adds
  a repeat-count to `evals/llm_run.py` and per-arm CI reporting in
  `measure.py`, keeping CI offline/deterministic.
- **Where:** JuliusBrussee/caveman — `docs/HONEST-NUMBERS.md`,
  `src/hooks/caveman-stats.js`, `evals/`.
- **Expected pushback:** maintainer bandwidth (366 open issues) — lead with
  data to jump the queue; numbers must follow their "never invent or round"
  rule; touch only sources-of-truth, never the CI-rebuilt mirror dirs.
- **Effort:** M — the measurement writeup is the work (1-3 days); code is small.

### 7. Standalone: blind-validation vault — demo artifact first, then CLI + skill pack — **BUILD** (serves H1)

The ecosystem-unique asset, deliberately ranked below the small PRs because the
verification theme doc's conclusion stands: full blind validation as a PR is
the wrong shape for most targets, and the standalone needs a credibility trail
(items 2-3) plus a **precondition artifact** to clear both the targets' eval
bars and the operator's own single-source-evidence rule.

- **Minimal landable slice (build this first, week 1-2):** a small,
  reproducible, seeded demonstration of the test-weakening failure mode plus
  guard catch-rate. This one artifact powers the PR bodies for items 2 and 3,
  the standalone README, and any future gstack/superpowers submission.
- **Then v0.1:** de-harness the vault into a CLI — held-out tests stored
  outside the repo, validator brief authoring tests from the spec only,
  clean-checkout run, tamper detection — documented as a `commands.test`
  integration for no-mistakes (blind validation for its whole user base, zero
  upstream changes), then a superpowers-marketplace plugin
  (`superpowers-blind-review`) and a skills.sh pack for the Pocock audience,
  positioned as the adversarial complement to /tdd and /implement.
- **Expected pushback:** none structural (standalone), but adoption is earned —
  the demo artifact and merged tripwire PRs are the marketing.
- **Effort:** demo artifact M (2-4 days); CLI extraction M; full pack with
  integrations L.

### 8. ruflo: opt-in window-utilization statusline segment — **PR, capped investment** (serves H4/H6)

Ruflo just shipped env vars to *hide* its cost segment because it is
"misleading on subscription plans" — they named the problem and stopped short
of the answer. An opt-in segment (% used, reset countdown) fed by the
rate_limits statusline JSON replaces a misleading number with the one
subscription users need, in the operator's exact area of prior art.

- **Minimal landable slice:** one self-contained change to
  `v3/@claude-flow/cli/src/init/statusline-generator.ts` (plus the hooks
  statusline command). Leave daemon throttling to a follow-up; do not touch
  the mirrored `.claude/` trees unless docs demand it.
- **Where:** ruvnet/claude-flow (npm `ruflo`).
- **Expected pushback:** ~97% single-author history — the real risk is the
  maintainer reimplementing the idea in his own style rather than merging;
  branch rot at 464 commits/5 weeks. Keep it one file, rebase-ready, and treat
  a rewrite-with-credit as an acceptable outcome (the idea still lands, with
  attribution). Cap total investment at ~2 days.
- **Effort:** S-M.

### Quick hits (below the fold, do opportunistically)

- **claude-skills: determinacy-checklist reference for grill-me** (S, serves
  H2): one reference .md in `engineering/grill-me/references/` porting
  plan-build's determinacy tests; target the `dev` branch, follow the
  two-field frontmatter rule, expect post-merge rewrites. Trust-builder for
  the larger window-optimizer/blind-validation skills there later.
- **gstack: window gate in `bin/gstack-detach` + preamble WINDOW echo** (M,
  serves H4): verified absent despite fleet-scale workloads; follows existing
  preamble-echo + config-key conventions; note community PRs land in batched
  "waves", so expect latency. Optionally precede with the invited jargon-list
  starter PR to learn the .tmpl/regen pipeline.
- **career-ops: one zero-auth provider module** (S): explicitly fast-laned,
  no-issue-needed; pure ladder-building before or alongside item 1.
- **H3 note:** stub-and-seams has no external PR target — the right move is the
  in-harness measured parallel-vs-serial experiment (N≥5 per arm) the ecosystem
  lacks, published as data; import superpowers' Consumes/Produces block format
  and no-mistakes' patch-id merge guard as substrate while doing it.

---

## Not worth it (explicitly advised against)

1. **Any PR to mattpocock/skills.** 158k stars, 13.6k forks, and exactly zero
   externally-authored human PRs merged in the repo's entire history; no
   CONTRIBUTING.md; strict self-enforced sync conventions. Route ideas there as
   *issues* (he demonstrably implements good ideas himself — e.g. the
   evidence-gate proposal for code-review/triage) or as standalone skills.sh
   packs. Even the "small docs-drift README fix" is a lottery ticket; don't
   budget for it.
2. **gstack blind-validation specialist as an L-sized PR.** Requires .tmpl
   edits with 8-host regeneration, tier-1 tests, a catch-rate eval the
   maintainer will demand, and review lands in batched community waves. The
   same idea ships faster as the standalone pack (item 7) with gstack-specific
   integration docs; revisit as a PR only after the demo artifact exists and a
   smaller gstack PR has merged.
3. **Superpowers core PRs of any kind.** A stated 94% rejection rate, a ban on
   new core skills, and eval-evidence requirements for touching any skill
   prose. The sanctioned channel is a marketplace plugin
   (superpowers-blind-review, wake-on-reset pacing) — already folded into
   items 4 and 7. The one arguable exception (the `git clean -fdx` ledger
   hardening, grounded in their own release notes) is fine but low-leverage;
   only take it if a real session actually loses a ledger.
4. **A /grill spec-elicitation PR or standalone grill-me clone as a lead
   play.** The landscape verdict is blunt: the interview is a crowded,
   commoditized category (five independent implementations found). The
   operator's differentiated slice — executable determinacy probe, criterion-ID
   spec-to-test traceability — is only buildable where held-out tests exist,
   i.e. in the harness. Build it there first; export later if it proves out.
   The ECC `/grill` PR and a standalone grill plugin are both deprioritized.
5. **andrej-karpathy-skills contributions.** Stale since April, maintainer
   attention has moved to his commercial project, three hand-synced copies have
   already drifted, and the payoff is visibility only. The 3-line
   "never weaken a test" clause is the one defensible S-sized exception — do it
   only as leftover-time flag-planting, not as a planned item.
6. **Architectural contributions to ruflo** (blind-validation plugin into
   core, daemon-level window throttling, anything multi-file). ~97%
   single-author history at daily-release velocity means anything non-trivial
   gets rewritten or rots. Item 8 is the ceiling of sensible investment.
7. **Predictability/variance eval harness for Pocock's skills as a
   standalone.** L effort, no distribution channel (the natural venue is a
   closed repo), and the variance point lands cheaper via the caveman evals PR
   (item 6) and the harness's own published experiments.
8. **caveman lite/ultra/wenyan mode benchmarking.** Real API spend for a
   contribution with no asset leverage — leave it to the repo's own community.
9. **gstack preamble carve (the P3 token-reduction target).** High blast
   radius (52 skills × 8 hosts), it's the maintainer team's own core
   competency, and it exercises none of the operator's differentiated assets.

## Sequencing

- **Week 1:** item 2 (no-mistakes tripwire) + item 5 (ECC cost-tracker, after
  upstream recon) — two small merges on the board; start the item 7 demo
  artifact (it feeds every H1 PR body); open the item 6 caveman issue with data.
- **Weeks 2-3:** item 1 (career-ops --wait-for-reset, issue → PR) and item 3
  (planning-with-files AcceptanceCheck, issue → PR).
- **Weeks 3-5:** item 4 (wake-on-reset daemon v0.1) with career-ops and
  planning-with-files cross-listings; item 8 (ruflo statusline) as a capped
  side quest; career-ops cache-prefix follow-up PR with measurement.
- **After merges exist:** item 7 v0.1 CLI + marketplace/skills.sh packaging,
  citing the merged tripwire PRs and the demo artifact as evidence.

The through-line: every PR is a measured, small, convention-following slice of
one of the two standalone products (wake-on-reset daemon, blind-validation
vault), so upstream contributions and the launches compound instead of
competing for the same hours.
