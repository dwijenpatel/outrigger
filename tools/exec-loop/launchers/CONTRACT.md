# The launcher contract (v1)

A **launcher** is the executable that starts one headless AI worker. It is the loop's only
seam to any AI tool: the loop never calls a vendor CLI directly, and a new tool (Codex CLI is
the named first extension) is a new launcher file honoring this contract — never loop surgery.

## Invocation

```
<launcher> <bundle-dir>            # run the worker
<launcher> --dry-run <bundle-dir>  # print what WOULD run (argv, env, generated config); execute nothing
```

## The bundle directory

The caller (the loop) prepares it with exactly:

- `instructions.md` — the role prompt the worker must follow. Tool-neutral prose.
- `params.json` — tool-neutral parameters:

```json
{
  "contract": 1,
  "role": "author",
  "worker": {"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
  "isolation": {"deny_read": ["/abs/path"], "sandbox": true, "network": true},
  "cwd": "/abs/working-dir",
  "timeout_s": 3600
}
```

`contract` is the bundle's major version (T11 policy, [tools/CONTRACTS.md](../../CONTRACTS.md)):
a launcher refuses an unknown major fail-closed; absence means legacy major-1. `result.json`
carries the same field back.

`worker.effort` is optional and tool-interpreted. **`isolation` is intent, never mechanism**:
the launcher translates it into its own tool's enforcement (settings files, sandbox flags,
whatever the tool offers). The caller never writes tool-specific configuration. The caller may
add `"attempt": <int>` (informational — lets launchers/transcripts distinguish retries).

## Fail-closed (the load-bearing clause)

**A launcher that cannot express any part of the isolation intent — an unknown field, an
unsupported combination, a wrong `worker.tool` — must refuse to launch**: exit nonzero,
`result.json` written with `ok: false` and `refused_reason` naming the unexpressible part.
Never launch unwalled and hope.

## What the launcher must produce (in the bundle dir)

- `result.json` — `{ok, exit, started_at, finished_at, refused_reason?, binary?, usage?}`.
  `ok: true` means the worker session ran to completion with exit 0. **Task success is not the
  launcher's judgment** — gates judge results; the launcher only reports that the session ran.
  `binary` (recommended) records the tool binary's resolved path and version actually used for
  this spawn — vendor builds are the fastest-decaying dependency, and the 2026-07-12 version
  skew (PATH at 2.1.202, app at 2.1.205) showed silent divergence is real; provenance makes
  every result self-describing. `usage` (recommended) records the session's own token/cost
  accounting so spend is a durable artifact rather than a forensic recovery (D14/R4): a launcher
  that can get it reports `{input_tokens, output_tokens, cache_read_tokens,
  cache_creation_tokens, cost_usd, num_turns, api_duration_ms}` (nulls where the tool doesn't
  expose a field), or `{error: <reason>}` when the tool's output couldn't be parsed. Capturing
  usage must be best-effort — a token-accounting miss never fails an otherwise-good launch.
- `transcript.txt` — the worker session's captured output.

Launcher exit code: `0` = worker session ran to completion · nonzero = launch failure or
refusal (see `result.json` for which).

## Timeout

The launcher enforces `timeout_s`: on expiry it kills the worker's whole process group and
reports `ok: false`. A hung worker is a failure, not a wait.

## Vendor-mechanism honesty

How a given tool actually enforces isolation (deny rules, sandbox flags) is vendor-build
behavior: it can change with any release and is **verified only by that launcher's
operator-run smoke probe** (see `../SMOKE.md` once present) — including a deliberate
read-attempt against a denied path. Every new launcher earns trust through its own smoke run
before any real plan uses it; `--dry-run` shows what would be attempted, the smoke proves
what actually holds.

## Shipped launchers

- `claude_p.py` — Claude Code headless (`claude -p`). Translates `deny_read` into generated
  per-spawn settings (Read-deny rules), `sandbox`/`network` into the sandbox configuration;
  refuses `network: false` without `sandbox: true` (no mechanism exists to express it).
- `codex_p.py` — Codex CLI headless (`codex exec`, the contract's named first extension;
  probed against codex-cli 0.142.5). Translates `sandbox` into `--sandbox workspace-write`
  and `network` into the workspace network config; prompt via stdin; usage parsed
  best-effort from `--json` events. **Refuses any non-empty `deny_read`** — Codex has no
  read-deny facility, and launching without the wall the caller asked for is exactly what
  fail-closed forbids. Consequence: roles whose isolation needs `deny_read` (the loop's
  implementer, shadow-pilot's workers) cannot run on Codex today; the author role
  (`deny_read: []`) can. Also refuses `sandbox: false` (without an explicit sandbox flag,
  codex inherits unknowable user config). **Its smoke probe has not run yet** — see
  SMOKE.md's codex section before first real use.
- `mock.py` — the test substrate: executes a scripted scenario (`MOCK_SCRIPT`) in `cwd` as
  the "worker"; honors a `#MOCK_REFUSE <reason>` first-line directive to simulate a
  fail-closed refusal.
