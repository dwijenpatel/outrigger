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

    The deny-rule shape (permissions.deny Read rules; denies are monotonic
    across scopes) is a verified vendor commitment; the sandbox block is
    best-known vendor-build mechanism — the smoke probe is what proves it.
    """
    deny = []
    for path in isolation.get("deny_read", []):
        clean = path.rstrip("/")
        deny.append(f"Read({clean})")
        deny.append(f"Read({clean}/**)")
    settings = {"permissions": {"deny": deny}}
    if isolation.get("sandbox"):
        settings["sandbox"] = {
            "enabled": True,
            "network": bool(isolation.get("network", True)),
        }
    return settings


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
        # bypassPermissions, deliberately: the OS sandbox is the wall (probed
        # live 2026-07-12 — a real worker's ls/cat of the denied workspace was
        # blocked THROUGH BASH). acceptEdits was falsified by smoke run #1:
        # headless workers cannot answer approval prompts, so git commit and
        # check commands hung behind "requires approval" and no work landed.
        "--permission-mode",
        "bypassPermissions",
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
                    "cwd": params["cwd"],
                    "generated_settings": settings,
                    "timeout_s": params["timeout_s"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

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
        },
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
