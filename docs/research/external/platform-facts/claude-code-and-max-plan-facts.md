# Claude Code & Max-plan facts — the mechanics the harness depends on

The volatile, vendor-specific facts underneath the design's O1 machinery
([../attic/token-time-optimized-harness.md](../../../attic/token-time-optimized-harness.md) §5, §10):
prompt-cache behavior, rate-window mechanics, quota introspection, usage credits, and the
capacity/regime changelog. These are the facts most likely to change under the harness — the
design's §10.3 volatility discipline exists because of this document's contents.

**Provenance:** deep-research workflow, 2026-07-04. The three most design-changing facts
(1-hour cache TTL, the paused Agent SDK plan change, the statusline `rate_limits` JSON) were
**re-verified by direct fetch of the official page on 2026-07-04** and carry
`[official, re-fetched]`. Community measurements are `[measured]`; unanswered questions are
`[contested]`. Related economics/routing evidence:
[token-economics-and-scheduling.md](../economics/token-economics-and-scheduling.md).

---

## 1. Prompt-cache TTL & billing

- **The 1-hour cache TTL is automatic on subscription (Pro/Max) auth** — no
  `ENABLE_PROMPT_CACHING_1H` needed (that env var is for API-key / third-party auth only,
  where the default stays 5 minutes). **The TTL silently drops to 5 minutes while drawing on
  usage credits.** `FORCE_PROMPT_CACHING_5M=1` forces 5 min regardless.
  `[official, re-fetched: code.claude.com/docs/en/prompt-caching]`
  → **Corrects design §5.2 rule 3 and §11 Stage 3**, which assume a 5-min default and an
  env-var opt-in.
- **Cache reads bill at ~10% of the standard input rate** (`cache_read_input_tokens`). The docs
  state this as a *billing* rate and say **nothing about how cache reads weigh against
  subscription usage limits** — that question is officially unanswered (see §4). `[official]`

## 2. What invalidates the cache (bears on §5.2 and §5.3 escalation)

The cache matches an exact prefix; a change anywhere recomputes everything after it. Layers,
outermost-cached first: system prompt (tools, output style) → project context (CLAUDE.md,
memory, unscoped rules) → conversation.

- **Model and effort level are both part of the cache key** (alongside the fast-mode header).
  Mid-session `/model`, `/effort`, or the first fast-mode toggle → full-history re-read, zero
  hits. Claude Code shows a confirmation dialog before a cache-busting effort change.
  → **The §5.3 escalation ladder cannot escalate model or effort mid-session for free**; do it
  at a worker respawn / session boundary. `[official, re-fetched]`
- **Bare-tool deny rules** added mid-session (`Bash`, `WebFetch`, `Bash(*)`, `"*"`) invalidate
  (tool defs live in the system-prompt layer). Scoped deny rules (`Bash(rm *)`) and all
  allow/ask rules do not. `[official, re-fetched]`
- **MCP server connect/disconnect** invalidates only when its tools load into the prefix
  (non-deferred: Haiku, some providers, `alwaysLoad`, threshold-loading). Deferred tools (the
  default) only append. `[official]`
- **Mid-session CLAUDE.md and output-style edits neither invalidate the cache nor apply** —
  they load at session start / `/clear` / `/compact` only.
  → **Reframes the §5.2 frozen-prefix warning hook:** the risk of a mid-firing CLAUDE.md edit is
  a *silent no-op*, not a cache-bust; the actual mid-firing cache-busters to warn on are model /
  effort / fast-mode / bare-tool-deny / non-deferred-MCP changes. `[official, re-fetched]`
- **Compaction** invalidates the conversation layer but reuses the system-prompt layer; the
  summary call shares the prefix (cheap), so the post-compaction turn is not the slow part.
  **Upgrading Claude Code** rebuilds from the top. `/rewind` re-hits the earlier (still-warm)
  entry. `[official]`

## 3. Cache scope, subagents, resume

- **Cache is scoped per machine + directory.** The system prompt embeds cwd/platform/shell/OS,
  so **worktrees of the same repo do NOT share cache** (each is a different cwd). Parallel
  same-dir sessions share; sequential sessions share only if the **startup git snapshot (branch
  + recent commits) matches** — i.e. **every commit cold-starts the next fresh session's
  prefix**. Agent SDK fleets can suppress per-machine system-prompt sections to share cache
  across machines. `[official, re-fetched]`
  → **§6.2 admission cost side:** each concurrent worktree pipeline pays its own ~20–30k prefix
  warmup.
- **Subagents start with a cold cache and use the 5-minute TTL even on subscription** (the 1h
  TTL is main-conversation only); paused/slow subagents lose warmth after 5 min. **Forks**
  inherit and read the parent's cache. Community measurement: 17 subagents ≈ 24M tokens in 15
  min, ~25–46k-token cache creation each `[measured; issue #24016]`. `[official, re-fetched]`
- **"Resuming a long transcript reprocesses at full cost" — confirmed with conditions.** True
  after a Claude Code upgrade or after the TTL lapses; within-TTL resume hits the warm cache, so
  the design's flat claim is over-broad as stated. Community telemetry adds two sharp edges:
  a resumed idle session attributes its full accumulated cache context to the **new** rate
  window (15M tokens attributed for ~20k of real work), and per-call overhead grows to full
  context size (192k cache-reads to produce a 1-token response) `[official, re-fetched +
  measured; #24016]`. → **Reinforces §5.2 rule 4** (fresh session + disk state beats `--resume`)
  and **adds a §9 failure row** (treat idle-session resumes as heavy admissions).

## 4. Rate-window model & quota introspection

- **Windows:** rolling 5-hour session window that **anchors at the first message** (re-confirmed
  by multiple practitioner sources incl. the cron "warmup" tactic; **still no official
  statement** — keep `[measured]`), plus weekly caps: **one overall + one Sonnet-only**, with
  independent reset times. No published absolute numbers, only relative plan multipliers
  (Max 5x = 5× Pro, etc.) `[official/vendor]`. Three buckets are visible in the desktop UI:
  session %, Weekly (All) %, Weekly (Sonnet) % `[measured]`.
- **Shared pool, re-confirmed (verified 3-0):** Claude app (web/desktop/mobile) + Claude Code
  terminal + IDE + (currently) Agent SDK all draw from the same allocation. → The governor must
  treat the window as **externally drainable** by the operator's own interactive use, which
  local token accounting cannot see. `[official]`
- **Programmatic quota access — partially shipped, via the statusline.** The statusline stdin
  JSON officially documents:
  - `rate_limits.five_hour.used_percentage`, `rate_limits.seven_day.used_percentage` (0–100)
  - `rate_limits.five_hour.resets_at`, `rate_limits.seven_day.resets_at` (Unix epoch seconds)
  - `context_window.current_usage` (input/output/`cache_creation_input_tokens`/
    `cache_read_input_tokens`), `effort.level`

  This is **server-side utilization, machine-readable in-session, zero extra tokens** — a real,
  official quota feed the design's §5.1 source ladder should adopt as its primary rung.
  `[official, re-fetched: code.claude.com/docs/en/statusline]`
- **Gaps that remain (re-verified 2026-07-04 evening, through changelog v2.1.201):** issue
  #13585 (a dedicated `claude quota` CLI) is still **open — 22 comments, all community, zero
  maintainer responses**; no new CLI command/flag and no rate-limit fields in
  `--output-format json`/stream-json anywhere in the changelog. OTEL confirmed
  **consumption-only** by exact metric list (`session.count`, `lines_of_code.count`,
  `pull_request.count`, `commit.count`, `cost.usage`, `token.usage`,
  `code_edit_tool.decision`, `active_time.total` — no utilization or reset gauge; the
  `api_error` event's `status_code` detects 429s only after the fact); `anthropic-ratelimit-*`
  headers are API-key-only. Statusline caveats now documented: `rate_limits` appears **only
  for Pro/Max subscribers after the first API response**, and each window may be
  **independently absent** — read defensively `[official]`. Headless options, ranked: a
  **statusline-dump shim** (a statusline command on the operator's interactive session tees
  its stdin JSON to a file — official data, unofficial acquisition, stales when the host
  session idles); the **undocumented OAuth endpoint** (`GET api.anthropic.com/api/oauth/usage`,
  Bearer token + header `anthropic-beta: oauth-2025-04-20`) `[measured, community]` — with the
  probed caveat (2026-07-04, this dev machine) that **credentials may not be non-interactively
  accessible** (no `~/.claude/.credentials.json`; no Claude Code Keychain item), so the rung
  needs explicit per-environment operator wiring; then the run-log estimate. A `StopFailure`
  hook matcher for `rate_limit` / `overloaded` / `billing_error` is reported for *reactive*
  limit-hit detection `[folklore/vendor blog — single source, verify before relying]`.
- **Cache-read subscription weighting — still officially unanswered `[contested]`.** Community
  telemetry points to near-full weight in the 5-hour window: issue #24016 (~70M attributed
  tokens in <2h, >99% cache) was **closed "not planned" with no answer**; issue #24147 (the
  provenance of the design's "1,310×" figure: one user, 30 days, 5.09B cache reads vs 3.89M
  I/O) remains **open, unanswered** (re-verified 2026-07-04 via the issues API — no maintainer
  comment). One new *indirect* official signal: the `/usage` plan-limits attribution
  (v2.1.174+, costs docs) itemizes **cache misses** as a limit driver — implying cache *hits*
  are weighted differently, weight still unstated `[official, indirect]`. → The conservative
  branch in design §10.2 stands; settle it with the §12 controlled measurement — now the
  single highest-value experiment.

## 5. Usage credits (the escape valve)

- Billed at **standard API rates**; **$2,000/day** redemption cap + operator-set monthly cap +
  auto-reload thresholds; eligible on Pro, Max 5x, Max 20x. `[official]`
- **Strictly opt-in-in-advance, no silent spillover** — an unattended run halts at the wall
  unless credits were pre-enabled. A hard no-overflow policy is enforceable by keeping Console
  credentials out of the harness login (`claude logout` → re-login plan-only). Session (5h)
  limits keep resetting while credits burn, so stop buying credits the moment the included
  window resets. `[official]`

## 6. Capacity & regime changelog (extends design §10.3)

| Date | Change | Confidence |
|---|---|---|
| 2026-05-06 | 5-hour limits doubled (Pro/Max/Team/Enterprise); peak-hour throttling removed | `[official/vendor]` |
| 2026-06-15 (announced) → **PAUSED** | Agent SDK / `claude -p` / third-party usage would move **off** plan windows onto a monthly programmatic dollar credit (Pro $20 / Max 5x $100 / Max 20x $200; overflow to opt-in usage credits at API rates); **interactive terminal/IDE explicitly carved out**. Currently paused — everything still draws from subscription windows. | `[official, re-fetched: support 15036540]` |

**Live regime-change risk `[I]`:** if the paused SDK change un-pauses, headless firings — the
harness's primary execution mode — stop draining the rate windows entirely and O1 becomes
**dollar-budget management**, while interactive Claude Code stays on windows. The budget governor
should abstract *which pool a given spend drains* now, so the accounting model can be swapped
without a redesign. This belongs in the design's §10.3 volatility log as a standing watch item.
