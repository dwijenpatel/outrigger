# Spawn-path portability probe — 2026-07-04

Resolves design doc §12 open question #3 ("per-agent effort portability") for the current
build. Re-run this probe (script below) whenever the harness moves to a new Claude Code build
or execution environment — portability, not a one-time fact, is the open question.

**Build:** Claude Code 2.1.45. **Method:** `Workflow` tool, `agent()` calls with `opts.effort` /
`opts.model`, schema-forced trivial replies. Full script:
[probe-spawn-portability.js](probe-spawn-portability.js).

## Results

| Probe | Input | Result |
|---|---|---|
| Effort dispatch | `low`, `medium`, `high`, `xhigh`, `max` | **All 5 dispatched successfully** — `agent()` accepted `opts.effort` for every documented level, no errors. |
| Model override | `haiku`, `sonnet` | **Both dispatched successfully** — `agent()` accepted `opts.model` for both. |
| Invalid effort | `'ultra-mega'` | **Did NOT fail loud.** The call completed normally (no thrown error, no logged failure); the agent replied as expected. The invalid value was silently accepted/ignored rather than rejected. |
| Invalid model | `'gpt-99-turbo'` | **Fails, but asynchronously and non-throwing.** No JS exception was thrown at the call site (a `try/catch` around the `await` did not trigger). Instead: `agent()` resolved to `null` (its documented behavior "if... the subagent dies on a terminal API error after terminal retries"), and the workflow's own failure log recorded: `"[model:invalid] failed: There's an issue with the selected model (gpt-99-turbo). It may not exist or you may not have access to it."` |

## Correction to the design doc

§5.3 previously stated the Workflow spawn path was "verified by direct probe: all five effort
levels dispatch; model overrides are honored; **invalid ids fail loud**." The first two clauses
are reconfirmed. The third is **only half true**:

- **Invalid `effort` values are silently accepted** — no validation, no error, no log entry.
  A typo'd or stale effort string in a profile config would silently no-op the intended
  escalation without any signal.
- **Invalid `model` values do fail** — but as an async `null` result + a workflow-level log
  entry, not a synchronous throw. Code that only wraps the `agent()` call in try/catch (as this
  probe initially did) will not observe the failure; it must check for a `null`/falsy result.

## Design implication (actionable)

The primitive cannot be trusted to reject bad config on its own for `effort`, and only
partially for `model`. **The harness's spawn code must validate `(model, effort)` against an
explicit allowlist before calling `agent()`/`Workflow`**, and must check `agent()` results for
`null` rather than relying on a catchable exception. This is a mechanized-validation gap of
exactly the kind the design's own critique warns about (safety-relevant behavior must not be
assumed from the primitive's prose-implied contract) — see
[landscape-and-novelty.md §4](../../docs/research/landscape-and-novelty.md) risk #1.

## Re-verification protocol

1. Run [probe-spawn-portability.js](probe-spawn-portability.js) via the `Workflow` tool.
2. Record: Claude Code version (`claude --version`), date, and the four result rows above.
3. If any row's behavior changed from this baseline, update this file (new dated section, don't
   overwrite) and re-check whether the spawn-code allowlist guard in §5.3 is still necessary or
   whether the primitive itself started validating.
