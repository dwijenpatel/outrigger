#!/usr/bin/env python3
"""claude_p — launcher for Claude Code headless workers (`claude -p`).

Implements the tool-neutral launcher contract (CONTRACT.md): translates the
bundle's isolation INTENT into Claude Code mechanisms (a generated per-spawn
settings file with Read-deny rules + sandbox config), builds the `claude -p`
invocation from the worker params, enforces the timeout, writes result.json
and transcript.txt.

Fail-closed: any part of the intent this launcher cannot express -> refuse
(nonzero exit, refused_reason in result.json), never launch unwalled.

Vendor-mechanism honesty: the exact settings/flag semantics are vendor-build
behavior, verified only by the operator-run smoke probe (--dry-run shows what
would be attempted). Self-contained by design — a new tool's launcher copies
this file's shape, not its imports.
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
        # Unknown bundle major: refuse fail-closed (T11 policy). Absence is
        # legacy major-1 — old bundles on disk stay readable.
        return f"unknown params contract {params.get('contract')!r} (this launcher speaks 1)"
    worker = params.get("worker", {})
    if not isinstance(worker, dict):
        return "params.worker must be an object"
    unknown = sorted(set(worker) - KNOWN_WORKER_KEYS)
    if unknown:
        return f"unknown worker field(s) this launcher cannot honor: {', '.join(unknown)}"
    if worker.get("tool") != "claude":
        return f"wrong launcher for tool {worker.get('tool')!r} (this is the claude launcher)"
    if not worker.get("model"):
        return "worker.model is required"

    isolation = params.get("isolation", {})
    if not isinstance(isolation, dict):
        return "params.isolation must be an object"
    unknown = sorted(set(isolation) - KNOWN_ISOLATION_KEYS)
    if unknown:
        # Fail-closed: an unknown intent field is an unexpressible intent field.
        return f"unknown isolation field(s) this launcher cannot express: {', '.join(unknown)}"
    deny = isolation.get("deny_read", [])
    if not isinstance(deny, list) or not all(
        isinstance(p, str) and os.path.isabs(p) for p in deny
    ):
        return "isolation.deny_read must be a list of absolute paths"
    if isolation.get("network") is False and isolation.get("sandbox") is not True:
        return "network=false requires sandbox=true (no non-sandbox mechanism expresses network denial)"

    cwd = params.get("cwd")
    if not cwd or not os.path.isdir(cwd):
        return f"cwd is not a directory: {cwd!r}"
    if not isinstance(params.get("timeout_s"), (int, float)) or params["timeout_s"] <= 0:
        return "timeout_s must be a positive number"
    return None


def build_settings(isolation):
    """Translate isolation intent into a Claude Code settings object.

    Two layers, learned from smoke runs 1-2 (2026-07-12) + doc research:
    - The OS wall for arbitrary bash (cat/ls/python open()) is
      `sandbox.filesystem.denyRead` (Seatbelt/bubblewrap-enforced,
      independent of permission mode). This is the load-bearing wall.
    - `permissions.deny: Read(...)` additionally blocks Claude's in-process
      Read TOOL (which is NOT sandboxed). Absolute paths need the `//` prefix
      (a single leading `/` is project-relative — a real footgun).
    - `sandbox.autoAllowBashIfSandboxed` runs sandboxed bash unattended (no
      approval prompt, so headless git commit / python3 do not abort) WHILE
      the filesystem wall stays up. This is why bypassPermissions (which
      dropped the wall in smoke run 2) is not used.
    - `sandbox.failIfUnavailable` turns sandbox-start failure (missing
      dependencies, unsupported platform) into a startup abort. The
      documented default is to WARN AND RUN UNSANDBOXED — a fail-open that
      would silently void every wall above (operator-caught, 2026-07-12).

    Confidence: doc-grounded (code.claude.com/docs sandboxing + settings), but
    the commit-under-auto-allow and denyRead-blocks-bash behaviors are
    vendor-build — the smoke probe is the arbiter on the target build.
    """
    deny_read = [p.rstrip("/") for p in isolation.get("deny_read", [])]
    settings = {}
    if deny_read:
        # `f"Read(/{path})"` where path already starts with "/" yields "//path"
        # = absolute per the permission-rule path syntax.
        rules = []
        for path in deny_read:
            rules.append(f"Read(/{path})")
            rules.append(f"Read(/{path}/**)")
        settings["permissions"] = {"deny": rules}
    if isolation.get("sandbox"):
        sandbox = {
            "enabled": True,
            "failIfUnavailable": True,          # sandbox can't start (missing deps/platform)
                                                # -> abort at startup; the documented default
                                                # WARNS AND RUNS UNSANDBOXED (fail-open)
            "autoAllowBashIfSandboxed": True,   # unattended sandboxed bash; no prompt/abort
            "allowUnsandboxedCommands": False,  # close the dangerouslyDisableSandbox escape hatch
            "excludedCommands": [],             # nothing runs outside the wall
        }
        if deny_read:
            sandbox["filesystem"] = {"denyRead": deny_read}
        if not isolation.get("network", True):
            # network intent is allowlist-based in the sandbox; false = deny external.
            # network=true leaves the sandbox default (local ops work; verified-
            # external-allow is a separate probe, unneeded by the smoke). See
            # SMOKE.md's network note.
            sandbox["network"] = {"allowedDomains": []}
        settings["sandbox"] = sandbox
    return settings


def binary_provenance(resolve_version):
    """Which `claude` will actually run, and (on real runs) its version.

    Vendor builds are the fastest-decaying dependency in the system and the
    2026-07-12 skew (PATH served 2.1.202 while the desktop app ran 2.1.205)
    was invisible until someone thought to look. Recording path+version per
    spawn makes every result self-describing. Version resolution execs the
    binary, so dry-run (which promises to execute nothing) records the path
    only.
    """
    path = shutil.which("claude")
    prov = {"path": path}
    if path and resolve_version:
        try:
            r = subprocess.run([path, "--version"], capture_output=True,
                               text=True, timeout=30)
            prov["version"] = (r.stdout or r.stderr).strip()
        except Exception as exc:  # provenance must never break a launch
            prov["version"] = f"unavailable: {exc}"[:80]
    return prov


def build_argv(worker, settings_path, instructions_path):
    with open(instructions_path, encoding="utf-8") as fh:
        prompt = fh.read()
    argv = [
        "claude",
        "-p",
        prompt,
        "--model",
        worker["model"],
        "--settings",
        settings_path,
        # acceptEdits (NOT bypassPermissions): covers the Edit/Write tool for
        # in-cwd edits so it won't prompt->abort headless; mutating bash is
        # handled by sandbox.autoAllowBashIfSandboxed, so the OS filesystem wall
        # (sandbox.filesystem.denyRead) stays enforced. bypassPermissions was
        # falsified by smoke run 2: it dropped the read wall.
        "--permission-mode",
        "acceptEdits",
        # Structured output so the session's own token/cost usage is captured
        # in result.json instead of being lost (D14/R4: the harness must
        # measure its own spend). stdout becomes one JSON object; the human
        # transcript is its `result` field. Schema is vendor-build — parsed
        # fail-safe (parse_session) and probed by the smoke.
        "--output-format",
        "json",
        # Ambient-config hardening (flags verified present on 2.1.207 --help;
        # semantics are vendor-build — smoke run 5 is the arbiter): a worker
        # must be reproducible, not shaped by whoever's machine it runs on.
        # User/project/local settings (hooks! could act on every tool call)
        # are excluded — our generated --settings file is a separate source
        # and still applies; managed policy always applies. NOT --bare: that
        # kills OAuth/keychain auth, which the subscription path needs.
        "--setting-sources", "",
        "--strict-mcp-config",        # no --mcp-config given -> zero MCP servers
        "--disable-slash-commands",   # workers follow instructions.md, not skills
        "--no-session-persistence",   # one-shot workers leave no resumable state
    ]
    if worker.get("effort"):
        # Effort flag semantics are vendor-build: --dry-run shows it, the
        # smoke probe proves it; a wrong flag fails loudly at launch.
        argv += ["--effort", worker["effort"]]
    return argv


def parse_session(stdout):
    """Parse `claude -p --output-format json` stdout.

    Returns (transcript_text, usage, is_error):
    - transcript_text: the session's final message (.result), for human reading
    - usage: normalized token/cost dict, or {"error": ...} if unparseable
    - is_error: the vendor's own error flag, or None if it couldn't be read

    Fail-safe by design: a moved/renamed field or non-JSON output must never
    crash the launcher (its job is to report that the session ran). Token
    capture is best-effort; the gate is the correctness authority regardless.
    Schema decay is vendor-build (validated on the benchmark's 2.1.201 JSONs:
    .usage.{input,output,cache_read_input,cache_creation_input}_tokens,
    .total_cost_usd, .num_turns, .duration_api_ms) — re-probed by the smoke.
    """
    obj = None
    try:
        obj = json.loads((stdout or "").strip())
    except (json.JSONDecodeError, AttributeError):
        # Tolerate stray lines around the JSON: take the last line that parses.
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    if not isinstance(obj, dict):
        return (stdout or "", {"error": "unparseable --output-format json output"}, None)
    u = obj.get("usage") or {}
    usage = {
        "input_tokens": u.get("input_tokens"),
        "output_tokens": u.get("output_tokens"),
        "cache_read_tokens": u.get("cache_read_input_tokens"),
        "cache_creation_tokens": u.get("cache_creation_input_tokens"),
        "cost_usd": obj.get("total_cost_usd"),
        "num_turns": obj.get("num_turns"),
        "api_duration_ms": obj.get("duration_api_ms"),
    }
    text = obj.get("result")
    return (text if isinstance(text, str) else (stdout or ""), usage, bool(obj.get("is_error")))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")
    if len(args) != 1:
        print("usage: claude_p.py [--dry-run] <bundle-dir>", file=sys.stderr)
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

    settings = build_settings(params.get("isolation", {}))
    settings_path = os.path.join(bundle, "generated-settings.json")
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, sort_keys=True)
        fh.write("\n")

    argv_out = build_argv(params["worker"], settings_path, instructions)
    # Auto-memory would leak the operator's accumulated context into a worker
    # that is supposed to see only its bundle. Env-var name is community-
    # reported, unverified on this build — harmless if ignored, and smoke
    # run 5 checks the transcript for memory traces either way.
    env_extra = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}

    if dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "argv": argv_out,
                    "binary": binary_provenance(resolve_version=False),
                    "cwd": params["cwd"],
                    "env_extra": env_extra,
                    "generated_settings": settings,
                    "timeout_s": params["timeout_s"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    binary = binary_provenance(resolve_version=True)
    started = utcnow()
    t0 = time.monotonic()
    # stderr kept SEPARATE from stdout so stdout is clean JSON to parse;
    # stderr is preserved only when parsing fails (for debuggability).
    proc = subprocess.Popen(
        argv_out,
        cwd=params["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, **env_extra},
    )
    timed_out = False
    try:
        out, errout = proc.communicate(timeout=params["timeout_s"])
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        out, errout = proc.communicate()

    transcript_text, usage, is_error = parse_session(out or "")
    with open(os.path.join(bundle, "transcript.txt"), "w", encoding="utf-8") as fh:
        if usage.get("error"):
            # parse failed: keep the raw streams so nothing is lost
            fh.write((out or "") + (f"\n--- stderr ---\n{errout}" if errout else ""))
        else:
            fh.write(transcript_text or "")

    # Fail-closed on a vendor-reported session error (is_error), on top of the
    # exit/timeout checks. is_error is None when unparseable -> exit governs.
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
        # failure (environment vs solution — e.g. the usage-window wall).
        payload["error_summary"] = (
            (transcript_text or "").strip()[:300]
            or (errout or "").strip()[-300:]
        )
    write_result(bundle, payload)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
