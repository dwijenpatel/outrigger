# Ecosystem landscape — 11 popular repos profiled

**Date:** 2026-07-06
**Method:** 11 cloned popular repos mined by parallel analysts; file paths cite the clones at `/Users/dwijen/repos/`. Star counts and claims are labeled measured (verified in code/API) vs marketing (author-asserted). Clone staleness is noted where it changes the calculus.

---

## 1. gstack (garrytan/gstack)

**What/why popular:** Garry Tan's MIT "software factory" — ~52 template-generated SKILL.md skills simulating a startup team (YC-interview planner, review army, QA, release eng) plus a persistent Chromium daemon with layered injection defense. Popular via a prominent author and a concrete answer to "ship like a team of twenty."
**Activity/PRs:** Intense — near-daily releases (v1.57→v1.58.5 in ~2 weeks of June), PR #s to #2078, 548-line CONTRIBUTING.md, community PRs land in batched "waves." Clone 11 days stale.
**Distinctive mechanisms:**
- Token-budget engineering as CI regression gates: carve system (skeleton + on-demand `sections/`, measured −42%..−59% per skill in `TODOS.md`) pinned by `test/skill-size-budget.test.ts` + frozen `test/fixtures/parity-baseline-*.json` (>1.05x growth fails CI).
- Review Army with adaptive hit-rate gating: parallel specialist subagents, fingerprint dedup + agreement confidence boost, specialists auto-gated off after 0 findings in 10+ dispatches except NEVER_GATE security/data-migration (`review/SKILL.md` Steps 4.5–4.6, `bin/gstack-specialist-stats`) — closed-loop control of validation spend.
- Three-tier hermetic eval system for its own prompts, incl. LLM-judge regression vs the main-branch baseline (`test/helpers/hermetic-env.ts`, `test/helpers/session-runner.ts`, CONTRIBUTING.md).
**Steal:** skill-size CI baselines; event-sourced decision memory where "active" is computed not mutated (`lib/gstack-decision.ts`); question-preference learning to cheapen repeat interviews (`plan-tune/SKILL.md`); structured WIP commits as checkpoint store; detach wrapper with guaranteed EXIT sentinel.
**Gotchas:** SKILL.md files are generated — edit `.tmpl` + regen 8 hosts or the PR dies; headline productivity numbers (810x, ETHOS.md compression table) are author-run marketing, while carve/eval numbers are test-pinned and measured; ARCHITECTURE.md and TODOS.md contradict each other on eval heartbeats — verify against code first.
**Gap findings:** No implementer/validator separation, no held-out tests, no rate-window awareness (grep verified: only GitHub-API/HTTP rate caps), no prompt-cache awareness.

## 2. mattpocock/skills ("Skills For Real Engineers")

**What/why popular:** ~25 prompt-only skills; centerpiece is the grilling family (relentless one-question-at-a-time spec interviews). 158,506 stars / 13,624 forks (GitHub API, 2026-07-06) in five months, riding Pocock's educator reach.
**Activity/PRs:** Pushed day-of-analysis, 178 commits since May — but **zero merged external human PRs in the repo's history** (only 2 version bots); no CONTRIBUTING.md. A personal toolbox published for adoption, not a community project.
**Distinctive mechanisms:**
- Grilling primitive: 13-line model-invoked interview engine with explicit do-not-enact-until-confirmed gate (`skills/productivity/grilling/SKILL.md`), thin `/grill-me`/`/grill-with-docs` wrappers.
- writing-great-skills meta-discipline: "predictability" as root virtue, the sentence-level no-op test, "leading words" (pretrained concepts as token-cheap behavior anchors) (`skills/productivity/writing-great-skills/SKILL.md`).
- Wayfinder: issue tracker as multi-session planning memory — map-is-an-index-not-a-store, fog-of-war unspecified work, claim-by-assignee, one ticket per session (`skills/in-progress/wayfinder/SKILL.md`; churning heavily, ~15 of last 20 PRs).
**Steal:** leading words + no-op test for kickoff blocks; the tautological-test anti-pattern wording in `skills/engineering/tdd/SKILL.md` (names exactly the failure blind validation prevents); diagnosing-bugs' paste-the-output proof gate; loop-me's determinacy one-liner: "done when an implementer agent could build it without asking a single question" (`skills/in-progress/loop-me/SKILL.md`).
**Gotchas:** All effectiveness claims are experiential ("Try it, and see") — never measured. Route ideas here as issues (he implements them himself) or ship standalone on the same `npx skills add` installer; direct PRs are near-zero probability.
**Gap findings:** Same agent writes tests and code — no adversarial verification of any kind; no rate-limit or cache awareness anywhere (grep verified).

## 3. kunchenguid/no-mistakes

**What/why popular:** Go daemon that gates `git push` behind a fixed 9-step AI validation pipeline (intent→rebase→review→test→…→PR→CI babysit) in disposable worktrees, agent-agnostic across 7 CLI backends. "Clean PRs by default"; Trendshift badge, Discord, bilingual README.
**Activity/PRs:** 392 commits in ~3 months (~4/day), released weekly via release-please, ~10 merged external contributors. CONTRIBUTING.md requires every PR to be raised *through no-mistakes itself* (CI-enforced by a PR-body grep).
**Distinctive mechanisms:**
- New-test-file tripwire: if the fixing agent writes NEW test files, human approval is forced even when tests pass (`internal/pipeline/steps/common_diff.go` detectNewTestFiles) — a deterministic anti-reward-hack guard. But it ignores MODIFIED tests: an agent editing an existing test to pass sails through.
- Fail-closed force-push guard via git patch-id incorporation checks (`internal/pipeline/steps/forcepush.go`).
- Deterministic e2e via a single `fakeagent` binary symlinked under each agent name, dispatching wire protocol on argv[0], logging every prompt issued (`cmd/fakeagent/main.go`); plus meta-tests that pin the CI workflow YAML itself (`workflow_no_mistakes_required_test.go`).
**Steal:** the tripwire pattern; ask-user/auto-fix/no-op finding taxonomy keyed to "does this challenge deliberate intent?" (`internal/pipeline/steps/review.go`); generated-SKILL.md drift lint (`cmd/genskill/`); fakeagent for token-free build-loop testing.
**Gotchas:** The fixed pipeline is doctrine — "add a blind validation step" PRs will be rejected on design grounds; strengthen existing steps instead. Hot files churn fast. Review runs once BEFORE test, so later fix commits are never re-reviewed; an auto-fix whose re-check passes completes with no human look (executor.go:343). Mechanism claims are code-verified; efficacy ("Kill all the slop") is unmeasured.
**Gap findings:** Reviewer and fixer share one agent identity/config; rate_limit errors burn ~21s of retries then fail — no window parking despite the daemon+SQLite plumbing existing to support it.

## 4. everything-claude-code (affaan-m; clone is the marshall0524 fork — beware)

**What/why popular:** Mega-collection ("50K+ stars" README claim, marketing-adjacent): 17 agents, 43 commands, ~80 skills, ~25 hook scripts; the code companion to two viral X guides.
**Activity/PRs:** Genuinely community-friendly — per-type CONTRIBUTING templates, many merged external PRs, `origin: community` frontmatter is first-class. **This clone's last upstream commit is 2026-03-11; newer commits are fork-local noise** — re-check upstream before scoping anything.
**Distinctive mechanisms:**
- Instinct-based continuous learning: hooks (fire 100%) log observations; a Haiku observer clusters them into confidence-scored instincts; promotion to global requires 2+ projects at ≥0.8 confidence (`skills/continuous-learning-v2/SKILL.md`) — an independent-confirmation policy in the wild.
- Session-memory hook triad + resume protocol with mandatory "What NOT to retry (with reasons)" and no-work-until-operator-confirms (`commands/resume-session.md`, `scripts/hooks/session-start.js`).
- Ralphinho RFC→WorkUnit DAG: per-unit worktrees, tier-scaled pipeline depth, per-stage context isolation (reviewer never authored the code), merge queue that evicts failures and recycles conflict context into the next implement pass (`skills/autonomous-loops/SKILL.md`).
**Steal:** "hooks, not skills, for observation" (skills fire ~50-80%, hooks 100%); de-sloppify ("two focused agents outperform one constrained agent"); pass@k vs pass^k gating framing (`skills/eval-harness/SKILL.md`) — dovetails with the 30x-variance finding.
**Gotchas:** Most "systems" are prescriptive markdown, not machinery; "997 internal tests" are structural hook tests, not behavior evals; cross-harness mirrors may inflate PR scope. `scripts/hooks/cost-tracker.js` ignores cache token classes entirely — every logged cost estimate is wrong (a clean bugfix opening).
**Gap findings:** No test-integrity guard, no grill-style elicitation (grep verified), no rate-window handling, zero prompt-cache awareness.

## 5. andrej-karpathy-skills (forrestchang → multica-ai)

**What/why popular:** A single ~2.3KB CLAUDE.md restating Karpathy's Jan-2026 tweet as four principles, packaged as plugin + Cursor rule. Popularity is 100% borrowed virality; PR/issue #s to #95 against 9 files.
**Activity/PRs:** Stale since 2026-04-20; maintainer attention has moved to his Multica project (README is now a funnel). Merges small safe PRs.
**Distinctive mechanisms (all advisory prose):**
- Imperative→verifiable transformation table ("Fix the bug" → "Write a test that reproduces it, then make it pass") + `1. [Step] -> verify: [check]` micro-plan format (`CLAUDE.md` lines 45–61).
- Multi-surface packaging of one text (CLAUDE.md + plugin skill + `.cursor/rules/*.mdc`) — manually synced and **already drifted** (SKILL.md verifiably missing the closing section the other two copies have).
**Steal:** the transformation table as the canonical line format for plan-ledger tasks; contrastive wrong/right diffs as documentation (`EXAMPLES.md`) — e.g. show a real reward-hacked test-edit diff next to the blind flow; the distribution lesson: a 2KB fast package around a high-attention artifact captured a whole niche.
**Gotchas:** Zero enforcement, zero measurement; value is distribution study, not technique. Themes verified "none" for parallelization, limits/resume, memory, token efficiency — this repo is the demand signal for elicitation/verification tooling, not the supply.

## 6. JuliusBrussee/caveman

**What/why popular:** Compressed "caveman-speak" output skill (measured claim: 65% fewer output tokens vs verbose baseline; analyst re-check: ~50-53% vs the repo's own terse control). 85,596 stars / 4,763 forks in 3 months (GitHub API). Meme + a surprisingly serious support stack; funneling toward a commercial "Caveman 2."
**Activity/PRs:** 252 commits/3 months, dozen external contributors merged, per-PR CI, issue-driven fixes (fix(#601)). Lead with a data-backed issue — that's the house pattern.
**Distinctive mechanisms:**
- Three-arm eval with a terse control + committed snapshots so CI re-measures deterministically and any metric change is a reviewable diff (`evals/README.md`, `evals/snapshots/results.json`); README admits the earlier baseline-only comparison inflated numbers.
- Deterministic-validator-gated LLM rewrites: compress memory files, validate structure offline (code fences byte-identical), cherry-pick repairs only, bounded retries, untouched-original fallback (`skills/caveman-compress/scripts/validate.py`).
- HONEST-NUMBERS.md as a genre: a when-this-tool-LOSES page quantifying the ~1-1.5k token/turn overhead and naming break-even; honesty guards baked into code comments (`src/hooks/caveman-stats.js` lines 286–293 forbid mislabeling the ratio).
**Steal:** tokenizer-aware style rules (invented abbreviations save zero BPE tokens); compressed subagent output contracts with terminal first tokens (`skills/cavecrew/SKILL.md`); runtime single-source-of-truth prompt injection re-anchored each session because compaction erodes style rules (`src/hooks/caveman-activate.js`).
**Gotchas:** The 65% headline cherry-picks the favorable baseline and `benchmarks/results/` is actually empty (.gitkeep) despite "committed and reproducible" wording; grill-me lives in the sibling JuliusBrussee/skills repo, not here; CI force-rebuilds mirror dirs — edit sources-of-truth only.
**Gap findings:** caveman-stats deliberately understates limit relief on the assumption input+cache dominate window accounting — the researcher's cache-read-discount data says the opposite, a documented open question the repo itself solicits A/B evidence for.

## 7. OthmanAdi/planning-with-files

**What/why popular:** File-based planning memory (task_plan.md / findings.md / progress.md) re-injected via hooks so work survives /clear and compaction; rides the Manus meme; installable on 60+ agents. Author claims 15.3k stars / 5k weekly installs (unverifiable from clone).
**Activity/PRs:** Last commit day-of-analysis, four releases in a month, community PRs land within days (CHANGELOG credits them by number). Single maintainer ~80% of commits.
**Distinctive mechanisms:**
- Completion gate with 5-guard decision table incl. semantic stall detection (allow stop when the JSONL ledger hasn't advanced) and a hard block cap (`scripts/check-complete.sh`, `scripts/gate-stop.sh`); block reasons carry the phase NAME only because imperative text in a reason field becomes a continuation command (PR #180 lesson).
- Attestation-gated injection: plan SHA-256 locked at ratification; hooks refuse tampered or unattested plan bodies (`scripts/inject-plan.sh`, `scripts/attest-plan.sh`).
- **Engineered KV-cache hygiene** — the only repo in the sample with it: timestamp normalization of injected content, a "KV-cache stable by construction" fixed-shape ledger summary (`scripts/ledger-summary.sh`), and the Pi cache-safe mode's pointer-not-payload constant reminder (`docs/cache-safe-diagram.md`). Independent convergence with the researcher's cache findings.
**Steal:** all three cache patterns; single-writer rule + per-agent JSONL ledgers with flock'd monotonic tick; Run Contract stated in the artifact "not in chat history that gets compacted away" (`templates/task_plan_autonomous.md`); the verify-by-running audit that found 2 of 6 mechanisms silently broken while tests stayed green (`docs/evals.md` Test 4).
**Gotchas:** Headline 96.7% benchmark measures file-pattern fidelity, not outcomes (author-honest about it); their own eval shows the skill *costs* +68% tokens; every "one-file" PR touches ~13 mirrored variants (parity tests enforce). **AcceptanceCheck is documented with a full security model but implemented in no shipped script** — "done" is still agent self-report, i.e. gameable; that doc/code gap is the best PR opening. Set PLANNING_DISABLED=1 in harness worker envs — its cwd-triggered activation has hijacked one-shot sessions before (v3.4.0 fix).

## 8. alirezarezvani/claude-skills

**What/why popular:** 354 skills across 18 domains for 13 platforms; breadth + conversion/sync distribution machinery is the moat (README claims 5,200+ stars; CONTRIBUTING says 6,800+ — internally inconsistent).
**Activity/PRs:** Very active (bursts of 35-47 commits/day); ~95% single owner under four aliases + "Claude" AI commits, but external PRs land (ship-gate is external-authored) — then get rewritten/"hardened" post-merge. PRs must target `dev`.
**Distinctive mechanisms:**
- One-corpus 13-platform conversion pipeline (`scripts/convert.sh`, sync-*.py) with repo-integrity validators — every one of 593 Python tools must pass `--help` (`scripts/smoke_scripts.py`).
- Derived-skill provenance vendoring (Pocock's grill-me et al. with `derived_from` frontmatter, upstream discipline verbatim) — the pattern to copy if the harness vendors anything.
- self-improving-agent memory promotion lifecycle: MEMORY.md capture → recurrence-based promotion to CLAUDE.md or path-scoped `.claude/rules/*.md` loaded only when matching files open (`engineering-team/self-improving-agent/`).
**Steal:** grill-me's "provide a recommended answer with each question" and explore-instead-of-asking rules; zero-hallucination-coder's KNOWN/INFERRED/UNKNOWN map with "never write code that depends on an UNKNOWN" — a ready determinacy stop-criterion for plan-build; path-scoped rules files.
**Gotchas:** Contributor docs contradict themselves (205 vs 354 skills; a literal rule forbidding skill-count changes is dead letter); CONVENTIONS.md rules are violated by the repo's own skills; effectiveness numbers ("caveman cuts ~75%", "routing saves 60-80%") are unmeasured rules-of-thumb throughout — do not import as evidence.
**Gap findings:** Zero reward-hacking awareness in 354 skills; llm-cost-optimizer treats cache as an API-dollar lever and knows nothing of subscription windows.

## 9. obra/superpowers (Jesse Vincent / Prime Radiant)

**What/why popular:** A full methodology as 14 composable skills — brainstorming → zero-context plans → subagent-driven development (SDD) with adversarial two-verdict review — on both Anthropic's and OpenAI's official marketplaces; hiring a community engineer.
**Activity/PRs:** 397 commits since Jan, weekly releases; contribution gauntlet openly states a **94% PR rejection rate** (`CLAUDE.md`), demands agent-authorship disclosure + a named human reviewer + before/after eval evidence for any skill-content change; new skills routed to satellite repos/marketplace.
**Distinctive mechanisms:**
- SDD with file-based handoffs: briefs/diffs/reports move as files so controller context never accumulates them; `scripts/review-package` diffs the recorded per-task BASE, never HEAD~1 ("silently drops all but the last commit"); reviewer template's "Do Not Trust the Report" treats implementer rationales as unverified claims.
- Brainstorming/writing-plans pipeline: hard gate on any implementation before an approved design; plans written for an engineer with "zero context and questionable taste" — complete code per step, no placeholders (`skills/brainstorming/SKILL.md`, `skills/writing-plans/SKILL.md`).
- TDD-for-documentation: baseline runs without the skill = failing test; verbatim rationalizations become table rows; measured findings like "description = triggering conditions only" and prohibition-phrasing backfiring (`skills/writing-skills/SKILL.md`).
**Steal:** file handoffs + durable `.superpowers/sdd/progress.md` ledger ("trust the ledger and git log over your own recollection" — losing it was "the single most expensive failure observed"); "cheapen mechanics, never judgment" with enumerated judgment points and a measured ~$13/run cost decomposition (`docs/superpowers/specs/2026-06-10-strict-cost-sdd-design.md`); their "N=5 runs, not 1 — single-run gates were this campaign's weakest methodology" independently corroborates the 30x-variance finding.
**Gotchas:** Author-run headline numbers ("twice as fast, ~50% fewer tokens") with honest caveats but no independent replication; satellite-repo sprawl (evals, extra skills, marketplace are separate repos); brainstorming visual companion phones home version telemetry by default.
**Gap findings:** Implementer authors its own tests — reward-hacking mitigated socially, not structurally; zero rate-window handling (grep verified) despite advertising multi-hour autonomous runs; cost model counts tokens/turns, never cache misses.

## 10. santifer/career-ops

**What/why popular:** Local-first job-search command center (~25 prompt modes + ~50 Node scripts + Go TUI); WIRED/Business Insider coverage; CONTRIBUTING claims 55K+ stars (unverified). Mass-audience pain, agent-skill pack instead of SaaS.
**Activity/PRs:** The friendliest in the sample: explicit contribution ladder, no-issue-needed fast lane for providers/docs/translations, CodeRabbit on every PR, community PRs merged weekly.
**Distinctive mechanisms:**
- Two-layer system/user data contract with a checkout-only-allowlist self-updater, CI-enforced boundary, and loud in-file ownership banners (`DATA_CONTRACT.md`, `update-system.mjs`) — a tested answer to the harness's own P2-collision (pilot clones editing upstream machinery).
- Conductor/worker batch fan-out with **paused_rate_limit as a first-class state**: transient 429s retry without burning budget; Claude session/usage limits ("resets 3pm" grepped from worker logs) stop scheduling entirely until manual `--resume-paused` (`batch/batch-runner.sh` lines 370–527). It already matches the reset timestamp and throws it away.
- Negative-memory ledger as a hard gate: `interview-prep/retracted-claims.md` — retracted claims may never be reused even if the user repeats them (`modes/interview/practice.md`).
**Steal:** ownership banners + allowlist updater; paused-vs-failed state vocabulary; sentinel-file atomic ID reservation for parallel workers (`reserve-report-num.mjs`); embedded Machine Summary YAML inside human reports; the CONTRIBUTING playbook itself (sells contribution as résumé value; fast-lanes wanted PRs).
**Gotchas:** TRADEMARK.md reserves the name; settled doctrine pinned to issues (files-canonical #918, flat root #1386) is not open for relitigation; the "740+ offers → 1 role" spine is a self-reported anecdote and the scoring rubric's predictive accuracy is unbenchmarked; English mode edits create ~12-language translation debt.
**Gap findings:** batch-prompt.md interpolates per-job placeholders at the TOP of the prompt, defeating cross-worker prefix caching — a concrete cache-hygiene fix. No wake-on-reset, no window model, no statusline feed.

## 11. ruvnet/ruflo (formerly claude-flow)

**What/why popular:** Swarm meta-harness (~63k stars per badge; "8.1M downloads" marketing): 314 MCP tools, topologies + Raft/Byzantine/Gossip consensus, HNSW memory, and a 2026 "receipt-backed self-optimizing flywheel." Popularity = ruvnet's following + velocity + 176+ ADRs.
**Activity/PRs:** 464 commits in 5 weeks, releases near-daily — and ~97% of the last 1000 commits are one person under four aliases. Small convention-following PRs land; anything architectural gets reimplemented in the maintainer's style.
**Distinctive mechanisms:**
- Flywheel promotion as a conjunction of independent predicates (held-out score AND red/blue PASS AND drift AND deterministic replay AND canary rollback), champion-chained so lineage is monotone by construction (`v3/docs/adr/ADR-176-...md`, `harness-improvement-ledger.ts`).
- Pinned-hash frozen human eval: the benchmark's SHA-256 is a constant in code — the yardstick cannot silently drift (`v3/@claude-flow/cli/src/services/harness-frozen-eval.ts`).
- ContinueGate: budget-*acceleration* detection via regression on cost slope, gated at step boundaries with continue/checkpoint/throttle/pause/stop (`v3/@claude-flow/guidance/src/continue-gate.ts`) — a shipped implementation of closed-loop control.
**Steal:** pin the vault manifest hash inside the harness merge gate; seeded-bootstrap CI-lower-bound significance gating on improvement deltas (the right instrument for 30x variance); anti-pattern archive of rejected mutations ("rejections are knowledge"); witness markers attesting the load-bearing LINE of every fix (`verification/README.md`).
**Gotchas:** Bimodal evidence — HNSW numbers and ADR confessions are honest and measured (the "self-learning" consolidate worker was a stub for 6,000+ commits, ADR-174), while "89% routing accuracy" and "2.8-4.4x" have no methodology anywhere; mirrored `.claude/` trees must all be patched; branding split across two names.
**Gap findings:** "Held-out" means time-split self-benchmarks the optimizing system can read — tamper-EVIDENT, never context-SEPARATED; the statusline just shipped env vars to *hide* the cost segment as misleading on subscription plans (they found the problem, not the answer); zero cache-token handling (grep verified).

---

## Cross-cutting reading: where the ecosystem invests vs. what's unoccupied

**Crowded (do not build a standalone here without sharp differentiation):**
- **Spec elicitation / grilling.** Four of 11 ship a serious interview (gstack office-hours/spec, Pocock grilling, superpowers brainstorming, claude-skills' vendored grill-me), and two more name it as a wanted feature (planning-with-files deferred it explicitly, CHANGELOG:346; karpathy-skills preaches it without a mechanism). The *category* is occupied. What no one ships: a determinacy criterion plus a **ratified, machine-checkable plan artifact that the build refuses to start without** — every interview here ends in prose and vibes-based "enough."
- **Memory/lessons stores.** gstack (4 stores), ECC instincts, claude-skills promotion lifecycle, ruflo AgentDB/ADR-174. Converging on the same policies the harness already holds: confidence + independent confirmation before promotion, provenance tiers, negative memory.
- **Parallel subagent fan-out** (gstack review army, ECC Ralphinho, ruflo swarms, career-ops batch) and **disk-is-the-memory resumability** (gstack WIP commits, ECC blueprint cold briefs, wayfinder, planning-with-files ledgers, superpowers progress ledger). The researcher's asset #3 is independently validated five times over — it is now table stakes, not a differentiator.
- **Token size-reduction.** gstack carve gates (measured), caveman (measured, with caveats), Pocock's no-op test (argued). Everyone optimizes bytes.

**Unoccupied (verified absent across all 11):**
1. **Blind adversarial validation.** Zero repos context-separate test authorship from implementation; zero hold tests outside the repo; zero gate merges on clean-checkout runs. The nearest neighbors prove demand while missing the mechanism: no-mistakes' new-test-file tripwire (ignores modified tests), superpowers' "Do Not Trust the Report" (social, not structural), planning-with-files' unimplemented AcceptanceCheck, ruflo's tamper-evident-but-readable frozen evals, Pocock's *named* tautological-test anti-pattern with no defense. The ecosystem has vocabulary for reward hacking and no structure against it.
2. **Subscription rate-window awareness.** Zero repos model Claude Max 5-hour/weekly windows or consume the statusline rate_limits feed (grep-verified in gstack, Pocock, ECC, superpowers, planning-with-files, claude-skills, ruflo). The two that touch the problem do so reactively: career-ops greps "resets 3pm" then discards the timestamp and waits for a human; ruflo hides its misleading cost segment. Meanwhile the same repos advertise exactly the workloads that slam windows (10-15 parallel sprints, multi-hour autonomous SDD runs, overnight 50-job batches, /loop-start).
3. **Prompt-cache hygiene.** One repo of 11 — planning-with-files — engineers for KV-cache prefix stability (timestamp normalization, fixed-shape summaries, pointer-not-payload), independently converging on the researcher's finding. Everywhere else, cost thinking is token-count or dollar-flat-rate; ECC's cost-tracker and ruflo's gateway are *numerically wrong* because they ignore cache token classes. career-ops actively defeats caching by interpolating per-job values at the top of a 400-line static prompt.
4. **Measured run-to-run variance.** Superpowers ("single-run gates were our weakest methodology," N=5) and ruflo (seeded bootstrap CIs) gesture at it; caveman's evals are explicitly single-run; nobody has published a variance measurement. The ~30x same-task finding is novel, citable evidence — and the direct argument for closed-loop control, which only ruflo's ContinueGate implements in code.

**PR-friendliness map:** genuinely open — career-ops (fast lanes, ladder), no-mistakes, everything-claude-code (upstream, not the stale fork), claude-skills (dev branch), planning-with-files, gstack (waves), caveman (issue-with-data first). Effectively closed — mattpocock/skills (0 external merges ever; route via issues), superpowers (94% rejection; route via marketplace plugins), ruflo (97% single-author; small PRs only), karpathy-skills (stale/abandoned-ish).

**Evidence-culture map:** measured-and-pinned — gstack carve/eval gates, caveman snapshots, superpowers writing-skills, ruflo ADR confessions, planning-with-files' self-critical evals. Marketing-grade — every headline productivity multiplier (gstack 810x, ECC guides, claude-skills percentages, ruflo capability tables, career-ops origin story). The repos that measure honestly are exactly the ones most receptive to data-backed contributions.

## What the operator's project adds

Mapping cc-agent-harness assets onto the verified gaps:

- **Asset 1 — BLIND validation (vault-external held-out tests, clean-checkout merge gate):** unique against all 11. Deployment surfaces already scoped by the evidence: extend no-mistakes' tripwire to modified tests (S); implement planning-with-files' documented-but-missing AcceptanceCheck (M); a test-integrity hook for ECC (M); a blind-review specialist for gstack (L); standalone skill pack / superpowers-marketplace plugin as the distribution play, positioned as the adversarial complement to /tdd with the reward-hacking evidence as the pitch.
- **Asset 2 — determinacy-driven planning interview + ratified plan gate:** the interview alone is *not* differentiated (crowded category). The differentiated slice is the machine-checkable readiness gate (`python3 -m harness.planning ready` refusing the build) and determinacy stop-criteria — contributable as small upgrades to grill-me (claude-skills), career-ops onboarding, and planning-with-files' deferred brainstorm gate, borrowing loop-me's one-line determinacy test and zero-hallucination-coder's UNKNOWN rule as ecosystem-native framing.
- **Asset 3 — disk-is-the-memory resumability:** validated ~5x independently; no longer a moat. Steal back rather than evangelize: gstack's WIP-commit checkpoints, superpowers' progress-ledger discipline, planning-with-files' attestation.
- **Asset 4 — rate-window awareness:** unoccupied across the entire sample, with named, maintainer-acknowledged insertion points: career-ops `--wait-for-reset` (it already greps the reset time), ruflo's statusline segment (they just hid the misleading one), no-mistakes rate-limit parking, gstack-detach window gating, an ECC skill, a superpowers pacing plugin. This is the single most repeatable PR-sized contribution in the study.
- **Asset 5 — cache economics + 30x variance findings:** the evidence base nobody else has. It corrects shipped code (ECC cost-tracker, ruflo gateway, caveman-stats' explicitly documented open question), upgrades one convergent ally (planning-with-files), and fixes a concrete defect (career-ops prompt ordering). The variance finding slots into caveman's self-declared single-run weakness, superpowers' N=5 culture, and ruflo's bootstrap gates.

## Verdict on the operator's hypothesis

The operator's hypothesis — *contribute PR-sized value to popular projects and/or launch a small standalone project, leveraging these assets* — is **supported by the evidence, with routing constraints and two honest corrections.**

**Where it's right.** Two of the five assets (blind validation, rate-window awareness) are verified absent in all 11 repos while being demonstrably wanted: no-mistakes built half a tripwire, planning-with-files documented the security model for a gate it never implemented, superpowers wrote social defenses against exactly the failure the vault closes structurally, ruflo's own ADR calls its fitness function "gameable," career-ops greps the reset timestamp and throws it away. These aren't speculative gaps; they are half-finished features and maintainer-acknowledged blind spots with file-level insertion points. The empirical findings (cache-read discount, 30x variance) are the rarest commodity in a marketing-saturated ecosystem — several honest-measurement repos (caveman, superpowers, ruflo, planning-with-files) explicitly solicit exactly this kind of data.

**Corrections.** First: the planning-interview asset is *not* differentiated as a category — four strong implementations exist, one with 158k stars. Leading with "a better grill" would be entering the most crowded niche in the sample; lead instead with the ratified-gate mechanics as upgrades to incumbents. Second: disk-is-the-memory is now ecosystem consensus, not a moat — cite it as convergent validation, don't sell it.

**Routing.** The PR route only works on the open half of the map (career-ops, no-mistakes, ECC-upstream, claude-skills, planning-with-files, gstack, caveman) and demands their idioms: issue-first at caveman and career-ops, .tmpl regeneration at gstack, dogfooded PRs at no-mistakes, dev-branch at claude-skills. At mattpocock/skills, superpowers, and ruflo, the effective channels are issues, marketplace plugins, and standalone distribution respectively — a cold PR is wasted work. For the standalone route, the sample supplies both the playbook (karpathy-skills' multi-surface speed-to-package; caveman's HONEST-NUMBERS trust-marketing; career-ops' contribution ladder) and the warning (Pocock's zero-merge fortress shows stars ≠ community; single-maintainer velocity means clones stale in days — re-fetch every target before scoping).

**One discipline requirement.** The researcher's own findings are currently single-source author-run evidence — the exact category this document discounts in others. Per the standing confirmation rule, any PR or launch leaning on the cache/variance numbers must ship the methodology and a reproduction path, or it becomes indistinguishable from the marketing it outclasses. Done that way, the highest-expected-value sequence the evidence supports: (1) small evidence-backed correctness PRs that carry the findings (ECC cost-tracker, caveman stats/evals, career-ops --wait-for-reset), (2) the two documented-gap implementations (planning-with-files AcceptanceCheck, no-mistakes modified-test tripwire), (3) a standalone blind-validation + rate-window-scheduler skill pack riding skills.sh / plugin-marketplace distribution, with the merged PRs as its credibility trail.
