# Tool-surface & serialization-format economics — AXI, MCP-vs-CLI, TOON

Evidence base for *how workers and the orchestrator touch tools and data*: the AXI
(Agent eXperience Interface) design principles and benchmarks (github.com/kunchenguid/axi and
family), the MCP-vs-CLI/deferred-loading evidence landscape, and serialization-format token
economics (TOON, toonformat.dev) — read against the design's §4 leverage map, §5.4 context
hygiene, and §6.1 turn accelerators
([../design/token-time-optimized-harness.md](../design/token-time-optimized-harness.md)).

**Provenance:** kunchenguid repo survey 2026-07-04 (four-agent fan-out; shallow clones);
**independent-confirmation pass 2026-07-04** (three adversarial web-verification agents,
instructed to use only sources independent of the claim authors); **local zero-quota token
measurement 2026-07-04** on this harness's own data shapes (§4.3; script preserved in the
session scratchpad, reproducible from the description). `[E]` established in cited source;
`[I]` inference/synthesis. Tags follow the corpus convention, with `single-source` /
`replicated` qualifiers added where the confirmation pass settled them.

---

## 1. The AXI principles (prior art for agent-facing interfaces)

Ten numbered principles for agent-ergonomic tools, positioned as "the reliability advantages
MCP promises (structured output, discoverability) at the cost profile of a CLI" `[E]`. The
harness **no longer builds agent-facing CLIs**, but most principles are *interface* principles
that transfer to any surface a worker reads — skill outputs, hook messages, gate reports,
status digests, structured returns:

1. **Token-efficient output format** (TOON at the print boundary, JSON internally — but see §4
   before adopting).
2. **Minimal default schemas** — every field costs tokens × row count; list views carry 3–4
   fields; detail views carry bodies; defaults sized to cover the common case in one call.
3. **Content truncation** — never omit, never dump: truncated preview + total-size hint +
   escape hatch (`--full`, a file path) only when actually truncated.
4. **Pre-computed aggregates** — "the most expensive token cost is often not a longer response
   — it's a follow-up call." `count: N of T total`; derived status inline (`checks: 3/3
   passed`). Extended to *actions*: combined operations (act + observe in one step).
5. **Definitive empty states** — `tasks: 0 closed tasks found`, never ambiguous blank output
   (which makes agents re-run variations to distinguish empty from failure).
6. **Structured errors** — errors in the same structured shape as data, on the data channel;
   idempotent no-ops succeed (exit 0, `already: true`); unknown flags fail loud *with the
   valid set inlined* so correction takes one turn; dependency errors translated, never leaked.
7. **Ambient context via session hooks** — opt-in SessionStart dashboard, "ruthlessly
   token-minimized" because it loads every session.
8. **Content first** — a no-args/entry view shows live data + suggestions, not a usage manual.
9. **Contextual disclosure** — 1–4 state-aware next-step suggestions as complete command
   templates with `<placeholders>` for unknowable values; omitted when output is
   self-contained; "guide discovery, not workflows."
10. **Consistent help** — concise, per-subcommand, 2–3 examples.

Implementation patterns repeated across the family (gh-axi, chrome-devtools-axi, tasks-axi,
lavish-axi) `[E]`:

- **Count-line vocabulary:** `count: N`, `count: N of T total`, `count: N+ (search API limit
  reached)` — totals fetched so the agent never paginates to answer "how many."
- **Tail-biased truncation + disk spill:** CI logs keep the *last* 20k chars (failures live at
  the end), set `truncated: true` + original length, write the full log to a temp file
  surfaced as `full_log` with a grep hint; generic text keeps 40% head / 60% tail. This is
  disk-as-memory applied to tool output.
- **Confirmation-forward mutations:** first line `ok: <action> -> <resulting state>`;
  optional `--json` returns a deterministic write receipt so no read-back turn is needed.
- **Generation-stamped refs:** acting on a stale snapshot ref fails loudly (`STALE_REF`)
  rather than silently no-op'ing.
- **Channel discipline:** data + errors + suggestions on the channel the agent reads;
  progress/heartbeats on the one it doesn't; exit codes 0 (incl. no-ops) / 1 (error) /
  2 (usage).
- **Turns, not bytes, are the budget:** the engineering target throughout is eliminating
  follow-up calls, because each extra turn re-sends the whole growing context. `[E]` — the
  benchmark's decisive tasks were all turn-count stories (a task solved 5/5 vs 0/5 purely
  because output included `totalCount`; an 11-turn extraction fused to 2).

`[I]` Design mapping: these become interface rules for whatever surfaces the harness keeps —
verdict/return schemas, gate reports, status digests, skill bodies, hook `stderr` messages.
The specific rules worth lifting verbatim into the design: pre-computed aggregates on every
status artifact; definitive empty states; tail-truncate + spill-to-disk for gate/test output;
one-turn self-correcting errors; combined act+observe steps in worker instructions.

## 2. The AXI benchmarks — what they claim, what independent evidence supports

Author-run: Sonnet 4.6 agent + Sonnet 4.6 judge, 5 repeats/task; GitHub domain n=425
(17 tasks × 5 conditions), browser domain n=490. `[measured, single-source]`

Headline author numbers: gh-axi 100% success / $0.050/task / ~46K input tokens / 3 turns, vs
raw `gh` 86% / $0.054, vs GitHub MCP eager 87% / $0.148 / ~176K tokens / 6 turns, vs MCP +
ToolSearch 82% / $0.147 / 8 turns, vs MCP code-mode 84% / $0.101. Browser: chrome-devtools-axi
100% / $0.074 / ~79K tokens vs wrapped MCP eager 99% / $0.101 / ~185K. `[E]`

The independent-confirmation pass (2026-07-04) splits the claims:

- **MCP schema tax is real and replicated** `[measured, replicated]`: GitHub MCP tool
  definitions measured at ~42–55K tokens by independent parties (Unblocked; StackOne;
  GitHub's own changelog cut "~23K tokens (50%)", implying ~46K prior); Anthropic's own posts
  measure ~77K tokens of definitions before work begins in a multi-server setup and a
  150K→2K (−98.7%) drop consuming MCP via code execution. Typical per-tool schema 500–1,400
  tokens. Sources: anthropic.com/engineering/advanced-tool-use,
  anthropic.com/engineering/code-execution-with-mcp, getunblocked.com, stackone.com,
  github.blog changelog 2026-01-28.
- **"Hand-crafted CLI beats MCP on success" is single-source and actively contested**
  `[contested]`: the only other controlled head-to-head (Mao & Pradhan, Smithery, n=756,
  code released) found the *opposite* — native MCP 91.7% vs 83.3% for their CLI, with the CLI
  using **2.9× more** billed tokens — but their CLI was auto-generated from API specs, and
  they explicitly leave open "whether a hand-crafted, agent-first CLI could close the
  remaining gap" — exactly the cell only axi has measured. The **replicated** meta-finding
  across Smithery, Vercel (17→2 tools: 80%→100% success, ~102K→61K tokens), and Terminal-Bench
  (harness engineering moves success more than model choice) is weaker but solid:
  **interface ergonomics — few, well-described, well-shaped tools with shaped outputs —
  dominates the transport choice** `[measured, replicated]`.
- **The cost multiplier "2–3× for MCP vs CLI" is design-dependent, not a law** `[contested]`:
  prompt caching bills most eager schema re-sends at cache-read rates, and Smithery measured
  the sign reversed for a generic CLI. What survives: verbose tool *outputs* (the browser
  domain's 12,891-char MCP responses vs 6-char CLI responses) and schema bloat are each
  independently confirmed cost drivers; a purpose-built surface fixes both, a naive CLI
  wrapper fixes neither.

## 3. Deferred tool loading — the contradiction, reconciled `[contested → regime-split]`

axi's Finding 4 (ToolSearch over one ~90-tool MCP server: cost parity $0.147 vs $0.148,
success *down* 87%→82%, +1–2 discovery turns, tool-not-found hard failures) directly
contradicts Anthropic's published Tool Search results (Opus 4: 49%→74% accuracy on MCP evals;
Opus 4.5: 79.5%→88.1%; ~85% token reduction). The confirmation pass reconciles them as
**different operating regimes**, each conceded by the other side's own documentation `[E]`:

| Variable | axi regime (deferral loses) | Anthropic/Stacklok regime (deferral wins) |
|---|---|---|
| Catalog | 1 server, ~90–100 tools (~40–55K tokens) | Hundreds–thousands of tools (77K–206K+) |
| Hot-set fraction | High — agent needs most tools | Tiny — 3–5 tools relevant per request |
| Distractor load | Low | High (selection degrades past ~30–50 tools) |
| Cost mechanics | Eager schemas mostly cache-read-priced; discovery turns re-bill growing context | Context reduction dominates extra turns |

Anthropic's own docs state the boundary: standard (eager) loading is better "when every tool
is used in every request" or the library is small; keep the 3–5 hottest tools non-deferred;
selection accuracy degrades past 30–50 tools `[official]`. Stacklok independently confirmed
the retrieval-miss failure mode (Anthropic's built-in search: 48% retrieval / 34% selection
accuracy at 2,792 tools) while still measuring 206K→~3K token cuts — the failure mode is
retrieval quality, not deferral per se. Academic corroboration: RAG-MCP (selection accuracy
13.6%→43.1% with retrieval vs eager at scale); adaptive shortlists (7 adaptive ≈ 50 fixed);
Chroma context-rot (−7.9% avg accuracy from length alone, 18 models). `[measured]`

**Design rule this settles (§5.4 revision):** defer when catalog-tokens ≫ 10K *and* the
per-task hot set is a small fraction; eagerly load (or pin non-deferred) the small hot set a
worker certainly uses. For this harness's workers — small curated surfaces used every task —
that means: pin the hot set, keep the MCP surface near zero (CLI/code paths preferred
`[official + replicated]`), and reserve deferral for genuinely long-tail tools. `[I]`

## 4. Serialization formats — TOON verified

### 4.1 What TOON is

Lossless JSON-model encoding: YAML-style nesting + CSV-style tabular blocks for uniform
object arrays, with explicit guardrails (`items[N]{f1,f2}:` header declaring length and
fields). Spec/tooling mature (TS reference, multi-language ports, CLI with token stats). `[E]`

### 4.2 Author claims vs independent verification (2026-07-04 pass)

- **Token savings, uniform tabular:** author −60.7% vs pretty / −36.9% vs compact JSON.
  Independent replications: −20–35% (Stäbler), −25% (InfoQ playground), −15–26% (Orange
  Force), −2–18% on real agentic payloads with cl100k (Kutschka & Geiger), −68% on one
  wide-table case (Improving Agents), 1.8% *net* in one production pipeline (Page/PwC).
  **Direction robustly replicated; magnitude is tokenizer- and shape-dependent; the author's
  figures sit at the optimistic end.** Verdict: `[measured, replicated — 20–40% band vs
  compact JSON on uniform tabular]`. CSV remains smaller than TOON (~6–9%). Off-uniform
  shapes: TOON *loses* to compact JSON, independently confirmed and amplified (+10–20%).
- **Read accuracy "neutral or better, edge on small models":** **CONTRADICTED — every
  independent replication points the other way** `[contested, leaning negative]`: Improving
  Agents (12 formats, 95% CIs, gpt-4.1-nano): TOON 47.5% vs JSON 52.3%, 9th of 12 —
  **Markdown-KV won at 60.7%; Markdown-Table 51.9% beat TOON at nearly the same token cost**;
  nested/gpt-5-nano: TOON *last* (43.1% vs JSON 50.3%); Kutschka & Geiger: ~9pp accuracy cost
  across 4 agentic benchmarks × 5 open-weight models. The author's +1.4pp aggregate edge on
  n=209 is within noise (~±3pp). The small-model claim *inverts*: small models are more
  format-*sensitive* (Microsoft/MIT arXiv 2411.10541: up to 40% swing on GPT-3.5, GPT-4
  robust), and the sensitivity runs *against* the unfamiliar format.
- **Generation reliability:** author never benchmarked it; independent evidence is strongly
  negative `[measured, negative]`: one-shot valid-TOON 50% vs JSON 75% median across 21 models
  (0% on two of four case types); parallel tool calls in non-JSON formats collapse to
  near-zero; repair loops doubled token use. "Not safe as a default in multi-turn agentic
  systems" (Kutschka & Geiger).
- **Production adoption:** effectively zero named-company reports with numbers, eight months
  post-launch. `[E]`

### 4.3 Local measurement on this harness's own shapes (2026-07-04, zero quota)

o200k_base tokenizer (js-tiktoken; same proxy as the author's benchmark — Anthropic's
tokenizer differs, so treat ratios, not absolutes), official `@toon-format/toon` encoder,
seeded synthetic data mirroring the exact field sets of the harness's ledger and run-log
schemas. Round-trip losslessness verified. `[measured, local]`

| Shape (vs compact JSON baseline) | TOON | CSV | Markdown table |
|---|---|---|---|
| Ledger view, 40 tasks, **raw** (list-valued `deps`) | **+16.8%** | — | — |
| Ledger view, 40 tasks, **flattened** (deps joined to string) | **−48.0%** | −55.0% | −36.7% |
| Run-log, 30 records, mixed events (as shipped, semi-uniform) | **+17.5%** | — | — |
| Run-log, task_complete only, uniformed fields | **−38.3%** | −41.6% | — |
| Validator panel verdict (nested) | **+7.1%** | — | — |

(JSONL ≈ compact JSON, +0.8%. Pretty JSON costs +48–82% over compact — the cheapest
always-correct move is simply *never pretty-printing into context*.)

Replicates the shape-dependence on our own data: TOON wins only after a **flattening
transformation** (list fields joined, uniform projection extracted) — and once a view is
flattened, CSV is smaller still, and a Markdown table captures ~75% of TOON's saving with a
format every model is saturated in and the only independent accuracy test *favors*. `[E]`

### 4.4 Format guidance for the design `[I]`

1. **Never pretty-print into context** (+48–82% for nothing). Compact JSON is the baseline.
2. **Model-generated output (verdicts, returns): JSON only**, schema-validated — TOON/CSV
   generation reliability is independently negative, and structured-output validation is a
   design pillar (§6.1).
3. **Digest views read by models (status summaries, run-log projections): flatten first, then
   prefer Markdown tables** — ~37% cheaper than compact JSON on our shapes, training-prior
   familiar, and the only independent multi-format accuracy test puts Markdown formats at the
   Pareto frontier (Markdown-KV 60.7% / Markdown-Table 51.9% vs TOON 47.5%). TOON remains a
   candidate *only* for large uniform tables where the last ~11pp of savings matters and a
   deterministic consumer (script, not model) or a calibration check guards the accuracy risk.
4. **Persisted state files (ledger, run-log): stay JSON/JSONL.** They are semi-uniform (TOON
   loses), the readers are deterministic scripts (accuracy irrelevant, so no reason to leave
   the most tool-supported format), and digests are generated at read time anyway.
5. The accuracy risk of exotic formats concentrates exactly where the harness routes cheap
   models (§5.3) — format conservatism is a *correctness-floor* concern on the cheap tier, not
   just an economy knob.

## 5. What this changes in the design doc `[I]`

- **§5.4 ToolSearch line:** replace "deferral on (default)" with the regime rule from §3;
  pin the hot set.
- **§4 leverage map / §5.4:** "prefer CLI over MCP" upgraded from `[official]` guidance to
  replicated evidence — but restated as *interface ergonomics dominates transport*: few,
  well-shaped tools with aggregates, definitive empties, and shaped outputs.
- **§6.1 accelerators:** add follow-up-call elimination (pre-computed aggregates, combined
  act+observe steps, one-turn self-correcting errors) as a named token-free accelerator
  class; add tail-truncate+spill as the standard output-filter shape.
- **New format-policy paragraph (§5.4):** the rules in §4.4.
- **Confidence ledger additions:** TOON read-accuracy parity `[contested, leaning negative]`;
  hand-crafted-CLI-beats-MCP `[single-source, contested]`; MCP schema tax `[replicated]`;
  deferral regime rule `[official + replicated]`.
