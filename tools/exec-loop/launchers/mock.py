#!/usr/bin/env python3
"""mock — the test-substrate launcher (no AI, no network, no quota).

Honors the same contract as every real launcher (CONTRACT.md): reads the
bundle, "runs the worker" by executing a scripted scenario in params.cwd,
enforces timeout_s, writes result.json + transcript.txt.

The scenario script is named by the MOCK_SCRIPT environment variable (set by
tests). A first line of `#MOCK_REFUSE <reason>` simulates a fail-closed
launcher refusal. Self-contained on purpose — it is the exemplar that proves
the loop never depends on any particular AI tool.
"""

import datetime
import json
import os
import signal
import subprocess
import sys
import time


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_result(bundle, payload):
    with open(os.path.join(bundle, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--dry-run" in args:
        args.remove("--dry-run")
        print(json.dumps({"dry_run": True, "launcher": "mock"}))
        return 0
    if len(args) != 1:
        print("usage: mock.py [--dry-run] <bundle-dir>", file=sys.stderr)
        return 2
    bundle = os.path.abspath(args[0])

    try:
        with open(os.path.join(bundle, "params.json"), encoding="utf-8") as fh:
            params = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read params.json: {exc}", file=sys.stderr)
        return 2

    scenario = os.environ.get("MOCK_SCRIPT")
    if not scenario or not os.path.isfile(scenario):
        print(f"error: MOCK_SCRIPT not set or missing: {scenario!r}", file=sys.stderr)
        return 2

    with open(scenario, encoding="utf-8") as fh:
        first_line = fh.readline().strip()
    if first_line.startswith("#MOCK_REFUSE"):
        reason = first_line[len("#MOCK_REFUSE"):].strip() or "scenario-directed refusal"
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

    started = utcnow()
    t0 = time.monotonic()
    env = dict(os.environ)
    env["MOCK_BUNDLE"] = bundle  # scenarios may read params/instructions if they wish
    proc = subprocess.Popen(
        ["sh", scenario],
        cwd=params.get("cwd") or bundle,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = proc.communicate(timeout=params.get("timeout_s", 600))
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
