#!/usr/bin/env python3
"""H2 — merge + spawn interlocks: the mandatory-step *triggers* as machinery.

Design §7 wiring amendments 2–3: the C/D-series built the enforcement logic;
these interlocks force its invocation. "Merge only through the gate" and
"governor between tasks" stop being skill prose:

- **Merge interlock** — during a live firing, ``git merge``/``git push`` to a
  protected ref requires a **fresh PASS gate stamp bound to the merged ref and
  its current HEAD sha** (the gate writes stamps on PASS, nothing else does).
- **Spawn interlock** — during a live firing, spawning a worker (Task/Agent
  tool, or headless ``claude -p``) requires a **fresh admission stamp**
  written after a governor + scheduler tick.

Both are **inert outside a live firing** (operator sessions, machinery
development) and **fail closed inside one** — an undeterminable target, a
stale stamp, or a moved HEAD refuses.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import time

from . import hooks as _hooks
from . import loop as _loop

DEFAULT_GATE_STAMP_MAX_AGE_S = 3600
DEFAULT_ADMISSION_MAX_AGE_S = 900
PROTECTED_REFS = ("main", "master")

#: merge flags that consume the following token (so it is not the target ref)
_MERGE_VALUE_FLAGS = {"-m", "--message", "-F", "--file", "-s", "--strategy",
                      "-X", "--strategy-option", "--cleanup", "-S",
                      "--gpg-sign"}
#: merge state operations that name no new target and need no stamp
_MERGE_STATE_OPS = {"--continue", "--abort", "--quit"}

_SPAWN_BASH_RE = re.compile(r"\bclaude\b[^|;&]*\s(-p|--print)\b")
SPAWN_TOOLS = ("Task", "Agent")


class InterlockError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_to_epoch(ts: str) -> float:
    return _dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _slug(branch: str) -> str:
    return branch.replace("/", "__")


def _rev_parse(repo_dir: str, ref: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", repo_dir, "rev-parse", ref],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


# -- stamps ---------------------------------------------------------------------


def write_gate_stamp(stamp_dir: str, branch: str, head: str, base: str,
                     ok: bool, now_iso: str | None = None) -> dict | None:
    """Written by the gate on PASS — and only on PASS: a FAIL leaves no stamp,
    and absence is the enforcement state the merge interlock keys on."""
    if not ok:
        return None
    if not branch or not head:
        raise InterlockError("gate stamp needs branch and head")
    doc = {"branch": branch, "head": head, "base": base, "ok": True,
           "ts": now_iso or _utcnow_iso()}
    os.makedirs(stamp_dir, exist_ok=True)
    path = os.path.join(stamp_dir, _slug(branch) + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, sort_keys=True)
    os.replace(tmp, path)
    return doc


def read_gate_stamp(stamp_dir: str, branch: str) -> dict | None:
    try:
        with open(os.path.join(stamp_dir, _slug(branch) + ".json")) as fh:
            doc = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def write_admission_stamp(path: str, decision: dict,
                          now_iso: str | None = None) -> dict:
    """Written by the loop after a governor + scheduler tick admits work. The
    spawn interlock demands a fresh one — proof the judgment happened."""
    if not isinstance(decision, dict):
        raise InterlockError("admission decision must be a dict")
    doc = {"decision": "admit", **decision, "ts": now_iso or _utcnow_iso()}
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, sort_keys=True)
    os.replace(tmp, path)
    return doc


def _stamp_age_violation(doc: dict, what: str, max_age_s: float,
                         now_ts: float | None) -> str | None:
    ts = doc.get("ts")
    if not isinstance(ts, str):
        return f"{what} carries no timestamp (fail-closed)"
    try:
        age = (now_ts if now_ts is not None else time.time()) - _iso_to_epoch(ts)
    except ValueError:
        return f"{what} timestamp unparseable (fail-closed)"
    if age > max_age_s:
        return (f"{what} is stale ({int(age)}s old > {int(max_age_s)}s) — "
                f"re-run before acting on it")
    return None


# -- merge interlock --------------------------------------------------------------


def _merge_target(tokens: list) -> tuple[str | None, bool]:
    """Return (target_ref, is_state_op) for a ``git ... merge ...`` token list."""
    try:
        idx = tokens.index("merge")
    except ValueError:
        return None, False
    rest = tokens[idx + 1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in _MERGE_STATE_OPS:
            return None, True
        if tok in _MERGE_VALUE_FLAGS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok, False
    return None, False


def _push_protected_sources(tokens: list, repo_dir: str) -> list | None:
    """Refs whose push would land on a protected ref. None = undeterminable."""
    try:
        idx = tokens.index("push")
    except ValueError:
        return []
    rest = [t for t in tokens[idx + 1:] if not t.startswith("-")]
    refspecs = rest[1:]  # rest[0] is the remote, when present
    if not refspecs:
        current = _hooks.current_branch(repo_dir)
        if current is None:
            return None
        return [current] if current.rsplit("/", 1)[-1] in PROTECTED_REFS else []
    out = []
    for spec in refspecs:
        src, _, dst = spec.partition(":")
        dst = dst or src
        if dst.rsplit("/", 1)[-1] in PROTECTED_REFS:
            out.append(src or dst)
    return out


def _require_stamp(ref: str, repo_dir: str, stamp_dir: str,
                   max_age_s: float, now_ts: float | None) -> str | None:
    stamp = read_gate_stamp(stamp_dir, ref)
    if stamp is None:
        return (f"merge interlock: no PASS gate stamp for {ref!r} — merge only "
                f"through the gate (§7); run harness.gate.run_gate with "
                f"stamp_dir first")
    stale = _stamp_age_violation(stamp, f"gate stamp for {ref!r}", max_age_s,
                                 now_ts)
    if stale:
        return f"merge interlock: {stale}"
    head = _rev_parse(repo_dir, ref)
    if head is None:
        return (f"merge interlock: cannot resolve {ref!r} in this repo "
                f"(fail-closed)")
    if head != stamp.get("head"):
        return (f"merge interlock: {ref!r} moved since the gate passed it "
                f"(gated {str(stamp.get('head'))[:12]}, now {head[:12]}) — "
                f"re-run the gate on the current commit")
    return None


def check_merge(command: str, repo_dir: str, stamp_dir: str, marker_path: str,
                max_age_s: float = DEFAULT_GATE_STAMP_MAX_AGE_S,
                now_ts: float | None = None) -> str | None:
    """Violation string when a live firing merges/pushes without a fresh PASS
    stamp; None to allow. Inert (None) outside a live firing."""
    if not isinstance(command, str):
        raise InterlockError("command must be a string")
    if not re.search(r"\bgit\b", command):
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = None
    is_merge = bool(tokens) and "merge" in tokens
    is_push = bool(tokens) and "push" in tokens
    if tokens is not None and not (is_merge or is_push):
        return None
    if _loop.run_marker_live(marker_path) is None:
        return None  # inert outside firings
    if tokens is None:
        return ("merge interlock: unparseable git command during a live "
                "firing (fail-closed)")
    if is_merge:
        target, state_op = _merge_target(tokens)
        if state_op:
            return None
        if target is None:
            return ("merge interlock: cannot determine the merge target "
                    "during a live firing (fail-closed)")
        return _require_stamp(target, repo_dir, stamp_dir, max_age_s, now_ts)
    sources = _push_protected_sources(tokens, repo_dir)
    if sources is None:
        return ("merge interlock: cannot determine what a bare `git push` "
                "targets during a live firing (fail-closed)")
    for src in sources:
        violation = _require_stamp(src, repo_dir, stamp_dir, max_age_s, now_ts)
        if violation:
            return violation
    return None


# -- spawn interlock ---------------------------------------------------------------


def check_spawn(tool_name: str, tool_input: dict, marker_path: str,
                stamp_path: str,
                max_age_s: float = DEFAULT_ADMISSION_MAX_AGE_S,
                now_ts: float | None = None) -> str | None:
    """Violation string when a live firing spawns a worker without a fresh
    admission stamp; None to allow. Inert outside a live firing."""
    if tool_name in SPAWN_TOOLS:
        spawnish = True
    elif tool_name == "Bash":
        spawnish = bool(_SPAWN_BASH_RE.search(
            str((tool_input or {}).get("command", ""))))
    else:
        spawnish = False
    if not spawnish:
        return None
    if _loop.run_marker_live(marker_path) is None:
        return None
    try:
        with open(stamp_path) as fh:
            doc = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ("spawn interlock: no admission stamp — run the governor and "
                "scheduler tick (which writes it) before spawning workers "
                "(§5.1/§7); spawning without admission is the prose-skip this "
                "interlock exists to catch")
    if not isinstance(doc, dict) or doc.get("decision") != "admit":
        return "spawn interlock: admission stamp does not record an admit"
    stale = _stamp_age_violation(doc, "admission stamp", max_age_s, now_ts)
    if stale:
        return f"spawn interlock: {stale}"
    return None
