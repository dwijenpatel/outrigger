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
    ]
    if worker.get("effort"):
        # Effort flag semantics are vendor-build: --dry-run shows it, the
        # smoke probe proves it; a wrong flag fails loudly at launch.
        argv += ["--effort", worker["effort"]]
    return argv


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

    if dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "argv": argv_out,
                    "binary": binary_provenance(resolve_version=False),
                    "cwd": params["cwd"],
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
    proc = subprocess.Popen(
        argv_out,
        cwd=params["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = proc.communicate(timeout=params["timeout_s"])
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        output, _ = proc.communicate()

    with open(os.path.join(bundle, "transcript.txt"), "w", encoding="utf-8") as fh:
        fh.write(output or "")

    ok = (not timed_out) and proc.returncode == 0
    write_result(
        bundle,
        {
            "ok": ok,
            "exit": None if timed_out else proc.returncode,
            "started_at": started,
            "finished_at": utcnow(),
            "duration_s": round(time.monotonic() - t0, 3),
            "timed_out": timed_out,
            "binary": binary,
        },
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
