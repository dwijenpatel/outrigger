#!/usr/bin/env python3
"""codex_p — launcher for Codex CLI headless workers (`codex exec`).

Implements the tool-neutral launcher contract (CONTRACT.md) for the contract's
named first extension: translates the bundle's isolation INTENT into Codex CLI
mechanisms (`--sandbox workspace-write`, workspace network config), builds the
`codex exec` invocation from the worker params, enforces the timeout, writes
result.json and transcript.txt.

Isolation mechanism (verified against learn.chatgpt.com/docs/permissions,
2026-07-13): a generated Codex PERMISSION PROFILE, written per spawn as
$CODEX_HOME/<uniq>.config.toml and loaded via `--profile <uniq>` (smoke
attempt 1 proved `-c` cannot carry quoted path keys; activation stays on the
flat `-c default_permissions=...` so a failed file load aborts loudly as an
unknown profile, never an unwalled run). The profile `extends = ":workspace"`
(unmentioned paths are denied by default, so the preset supplies normal
workspace behavior — cwd writable, unattended commands) and each
isolation.deny_read path becomes a `"<path>" = "deny"` carve-out (denies
reads AND writes under it); network intent maps to
`permissions.<name>.network.enabled`. Profiles are documented as MUTUALLY
EXCLUSIVE with the older `--sandbox`/`sandbox_*` mechanism, so this launcher
never passes `--sandbox`. `--ignore-user-config` + `--ignore-rules` keep
ambient personal config from weakening the wall (auth is unaffected per
`codex exec --help`); `--strict-config` turns unknown config keys — e.g.
`permissions` on a build too old to speak it — into a loud startup failure
instead of a silent fallback.

Fail-closed: any part of the intent this launcher cannot express -> refuse
(nonzero exit, refused_reason in result.json), never launch unwalled.

Vendor-mechanism honesty: permission profiles are officially BETA ("may
change" — fast decay class), the `-c` dotted-path parser's handling of
quoted path segments is undocumented (a parse failure aborts the spawn
loudly under --strict-config — the safe direction), and none of this is
proven on a live run: the operator-run smoke probe (SMOKE.md, spends OpenAI
quota, NOT yet run) is the arbiter, including a deliberate read attempt
against a denied path. Self-contained by design.
"""

import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import time

KNOWN_ISOLATION_KEYS = {"deny_read", "sandbox", "network"}
KNOWN_WORKER_KEYS = {"tool", "model", "effort"}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_result(bundle, payload):
    with open(os.path.join(bundle, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def refuse(bundle, reason):
    write_result(
        bundle,
        {
            "contract": 1,
            "ok": False,
            "exit": None,
            "started_at": None,
            "finished_at": utcnow(),
            "refused_reason": reason,
        },
    )
    print(f"refused: {reason}", file=sys.stderr)
    return 2


def validate(params):
    """Return a refusal reason, or None if this launcher can express the intent."""
    if params.get("contract", 1) != 1:
        return f"unknown params contract {params.get('contract')!r} (this launcher speaks 1)"
    worker = params.get("worker", {})
    if not isinstance(worker, dict):
        return "params.worker must be an object"
    unknown = sorted(set(worker) - KNOWN_WORKER_KEYS)
    if unknown:
        return f"unknown worker field(s) this launcher cannot honor: {', '.join(unknown)}"
    if worker.get("tool") != "codex":
        return f"wrong launcher for tool {worker.get('tool')!r} (this is the codex launcher)"
    if not worker.get("model"):
        return "worker.model is required"

    isolation = params.get("isolation", {})
    if not isinstance(isolation, dict):
        return "params.isolation must be an object"
    unknown = sorted(set(isolation) - KNOWN_ISOLATION_KEYS)
    if unknown:
        return f"unknown isolation field(s) this launcher cannot express: {', '.join(unknown)}"
    deny = isolation.get("deny_read", [])
    if not isinstance(deny, list) or not all(
        isinstance(p, str) and os.path.isabs(p) for p in deny
    ):
        return "isolation.deny_read must be a list of absolute paths"
    if any('"' in p or "\n" in p for p in deny):
        # The path is embedded in a quoted TOML key; a quote inside it would
        # change the key's meaning. No legitimate workspace path contains one.
        return "isolation.deny_read paths must not contain quotes or newlines"
    if isolation.get("sandbox") is not True:
        # `codex exec` without an explicit sandbox flag inherits whatever
        # ~/.codex/config.toml says — unknowable here. This launcher only
        # launches explicitly sandboxed workers.
        return (
            "this launcher only launches sandboxed workers "
            "(isolation.sandbox must be true; sandbox=false has no safe "
            "codex expression)"
        )

    cwd = params.get("cwd")
    if not cwd or not os.path.isdir(cwd):
        return f"cwd is not a directory: {cwd!r}"
    if not isinstance(params.get("timeout_s"), (int, float)) or params["timeout_s"] <= 0:
        return "timeout_s must be a positive number"
    return None


def binary_provenance(resolve_version):
    """Which `codex` will actually run, and (on real runs) its version.
    Same rationale as claude_p: vendor builds are the fastest-decaying
    dependency; path+version per spawn makes every result self-describing.
    Dry-run promises to execute nothing, so it records the path only."""
    path = shutil.which("codex")
    prov = {"path": path}
    if path and resolve_version:
        try:
            r = subprocess.run([path, "--version"], capture_output=True,
                               text=True, timeout=30)
            prov["version"] = (r.stdout or r.stderr).strip()
        except Exception as exc:  # provenance must never break a launch
            prov["version"] = f"unavailable: {exc}"[:80]
    return prov


PROFILE = "exec_loop_wall"


def build_profile_toml(isolation):
    """The generated permission profile, as a TOML config-profile FILE.

    Shape (docs/permissions, verified 2026-07-13): `extends = ":workspace"`
    supplies the normal workspace behavior (unmentioned paths are DENIED by
    default, so a bare profile would break the worker — the preset is
    load-bearing); each deny_read path is a `"<path>" = "deny"` filesystem
    carve-out (denies reads and writes beneath it); network policy is
    per-profile. Profiles do not compose with the older sandbox settings —
    never add `--sandbox` or `sandbox_*` keys alongside these.

    Why a FILE and not `-c` overrides: smoke attempt 1 (2026-07-13, 0.142.5)
    proved the `-c` dotted-path parser does not honor quoted key segments —
    it split an absolute path key at a dot inside the path and aborted at
    config parse ($0, 0.07s; the pre-registered fallback trigger). Quoted
    keys are ordinary TOML in a real file. The file is delivered via
    `--profile <name>` ($CODEX_HOME/<name>.config.toml); ACTIVATION stays on
    the command line (`-c default_permissions=...`, a flat key the parser
    handles) so that if the profile file somehow fails to load, codex names
    an undefined profile and aborts loudly instead of running unwalled.
    """
    lines = [
        "# generated per-spawn by codex_p.py — removed after the run",
        f"[permissions.{PROFILE}]",
        'extends = ":workspace"',
    ]
    deny = [p.rstrip("/") for p in isolation.get("deny_read", [])]
    if deny:
        lines.append(f"[permissions.{PROFILE}.filesystem]")
        lines += [f'"{path}" = "deny"' for path in deny]
    lines.append(f"[permissions.{PROFILE}.network]")
    lines.append("enabled = " + ("true" if isolation.get("network", True) else "false"))
    return "\n".join(lines) + "\n"


def codex_home():
    return os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def build_argv(worker, cwd, last_message_path, profile_name):
    """Translate params into `codex exec` argv. The prompt travels via stdin
    (explicit `-`), never argv — instructions.md can be long.

    Flag facts (codex-cli 0.142.5 --help + docs/permissions, vendor-build):
    - `--profile <name>` loads the generated $CODEX_HOME/<name>.config.toml
      (the wall's definition — build_profile_toml); the flat
      `-c default_permissions=...` activates it and makes a failed file load
      a loud unknown-profile abort, never an unwalled run;
    - `--ignore-user-config` / `--ignore-rules`: ambient personal config and
      execpolicy rules cannot weaken the wall (a user-config `sandbox_mode`
      would otherwise conflict with profiles); auth still uses CODEX_HOME;
    - `--strict-config`: unknown keys (e.g. `permissions` on an old build)
      abort loudly instead of silently degrading;
    - `--skip-git-repo-check`: the author role's cwd (a suite workspace) is
      not a git repository; without this codex refuses to start there.
    - `--ephemeral`: workers are one-shot by contract; persist no session.
    - `--output-last-message`: the worker's final message, captured to a file
      (the transcript source of truth).
    - `--json`: JSONL events on stdout (usage extraction, best-effort).
    """
    argv = [
        "codex", "exec",
        "--json",
        "--color", "never",
        "--cd", cwd,
        "--model", worker["model"],
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--skip-git-repo-check",
        "--ephemeral",
        "--output-last-message", last_message_path,
        "--profile", profile_name,
        "-c", f'default_permissions="{PROFILE}"',
    ]
    if worker.get("effort"):
        # Effort names are vendor-interpreted (model_reasoning_effort);
        # a wrong value fails loudly at launch — same doctrine as claude_p.
        argv += ["-c", f'model_reasoning_effort="{worker["effort"]}"']
    argv.append("-")  # prompt from stdin
    return argv


def parse_events(stdout):
    """Parse `codex exec --json` JSONL stdout. Returns (usage, is_error).

    Fail-safe by design: the event schema is vendor-build and UNVERIFIED on a
    live run (the smoke probe is the arbiter); a moved field must never crash
    the launcher. Strategy: walk every line that parses as a JSON object,
    remember the last plausible token-usage payload seen (searched at the
    event's top level, under "usage", and under "info" token-usage keys —
    the shapes Codex versions are known to emit), and whether the last
    error-looking event type was fatal-looking.
    """
    usage_raw = None
    turns = 0
    last_type = None
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        etype = str(event.get("type") or event.get("msg", {}).get("type") or "")
        if etype:
            last_type = etype
        if "turn.completed" in etype:
            turns += 1
        for candidate in (
            event.get("usage"),
            event.get("msg", {}).get("usage") if isinstance(event.get("msg"), dict) else None,
            event.get("info", {}).get("total_token_usage") if isinstance(event.get("info"), dict) else None,
            event.get("msg", {}).get("info", {}).get("total_token_usage")
            if isinstance(event.get("msg"), dict) and isinstance(event.get("msg", {}).get("info"), dict)
            else None,
        ):
            if isinstance(candidate, dict) and any(
                isinstance(candidate.get(k), int)
                for k in ("input_tokens", "output_tokens")
            ):
                usage_raw = candidate
    if usage_raw is None:
        usage = {"error": "no usage-bearing event found in --json output"}
    else:
        usage = {
            "input_tokens": usage_raw.get("input_tokens"),
            "output_tokens": usage_raw.get("output_tokens"),
            # codex names cache reads "cached_input_tokens"; no write counter
            "cache_read_tokens": usage_raw.get("cached_input_tokens"),
            "cache_creation_tokens": None,
            "cost_usd": None,  # codex exposes no cost field
            "num_turns": turns or None,
            "api_duration_ms": None,
        }
    is_error = None
    if last_type:
        is_error = any(marker in last_type for marker in ("error", "failed"))
    return usage, is_error


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")
    if len(args) != 1:
        print("usage: codex_p.py [--dry-run] <bundle-dir>", file=sys.stderr)
        return 2
    bundle = os.path.abspath(args[0])

    try:
        with open(os.path.join(bundle, "params.json"), encoding="utf-8") as fh:
            params = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read params.json: {exc}", file=sys.stderr)
        return 2
    instructions = os.path.join(bundle, "instructions.md")
    if not os.path.isfile(instructions):
        return refuse(bundle, "bundle has no instructions.md")

    reason = validate(params)
    if reason:
        return refuse(bundle, reason)

    last_message_path = os.path.join(bundle, "last-message.txt")
    profile_toml = build_profile_toml(params.get("isolation", {}))
    profile_name = f"codex-p-{os.getpid()}-{int(time.time())}"
    argv_out = build_argv(params["worker"], params["cwd"], last_message_path, profile_name)
    # Audit copy: the wall's exact definition travels with the bundle.
    with open(os.path.join(bundle, "generated-profile.toml"), "w", encoding="utf-8") as fh:
        fh.write(profile_toml)

    if dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "argv": argv_out,
                    "binary": binary_provenance(resolve_version=False),
                    "cwd": params["cwd"],
                    "generated_profile": {
                        "would_write": f"$CODEX_HOME/{profile_name}.config.toml",
                        "content": profile_toml,
                    },
                    "prompt_from": instructions,
                    "timeout_s": params["timeout_s"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    with open(instructions, encoding="utf-8") as fh:
        prompt = fh.read()

    # The profile file must live in $CODEX_HOME — the only place --profile
    # reads from. Uniquely named per spawn, removed in the finally below; a
    # hard crash can orphan one (harmless, identifiable by the codex-p- prefix).
    home = codex_home()
    if not os.path.isdir(home):
        return refuse(
            bundle, f"CODEX_HOME not found at {home} (codex is not configured here)"
        )
    profile_path = os.path.join(home, f"{profile_name}.config.toml")

    binary = binary_provenance(resolve_version=True)
    started = utcnow()
    t0 = time.monotonic()
    with open(profile_path, "w", encoding="utf-8") as fh:
        fh.write(profile_toml)
    try:
        proc = subprocess.Popen(
            argv_out,
            cwd=params["cwd"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            out, errout = proc.communicate(input=prompt, timeout=params["timeout_s"])
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            out, errout = proc.communicate()
    finally:
        try:
            os.remove(profile_path)
        except OSError:
            pass

    # Raw JSONL events are the debugging/smoke record; keep them verbatim.
    with open(os.path.join(bundle, "events.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(out or "")

    usage, is_error = parse_events(out or "")
    final_message = None
    if os.path.isfile(last_message_path):
        with open(last_message_path, encoding="utf-8") as fh:
            final_message = fh.read()
    with open(os.path.join(bundle, "transcript.txt"), "w", encoding="utf-8") as fh:
        if final_message is not None:
            fh.write(final_message)
        else:
            # no final message captured: keep the raw streams so nothing is lost
            fh.write((out or "") + (f"\n--- stderr ---\n{errout}" if errout else ""))

    ok = (not timed_out) and proc.returncode == 0 and not is_error
    payload = {
        "contract": 1,
        "ok": ok,
        "exit": None if timed_out else proc.returncode,
        "started_at": started,
        "finished_at": utcnow(),
        "duration_s": round(time.monotonic() - t0, 3),
        "timed_out": timed_out,
        "binary": binary,
        "usage": usage,
    }
    if not ok:
        # Surface the vendor's own words so the caller can classify the
        # failure (environment vs solution — e.g. a usage-window wall).
        payload["error_summary"] = (
            (final_message or "").strip()[:300]
            or (errout or "").strip()[-300:]
            or (out or "").strip()[-300:]
        )
    write_result(bundle, payload)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
