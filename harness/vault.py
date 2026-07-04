#!/usr/bin/env python3
"""Held-out vault — isolation config, canary, and manifest (D1 + C4 logic).

Design §5.5/§7: panel-authored held-out tests persist where the implementer's
context/worktree can never see them. Isolation is the **six-layer OS-enforced
stack**, not path convention:

1. sandbox ``denyRead`` on the vault path (OS-enforced for Bash + children);
2. Read/Edit permission deny rules (the built-in file tools bypass the sandbox);
3. strict-mode flags (``allowUnsandboxedCommands: false``,
   ``failIfUnavailable: true``) — without them the boundary is prompt-dependent;
4. deny rules + sandbox config live in a scope the worker cannot write
   (enforced by the machinery-paths gate, C2, and the ratified-branch rule);
5. network egress control (operator-side; recorded here as a required layer);
6. per-role isolation via separate processes (headless one-shot workers).

This module *generates and validates* the config for layers 1–3 and provides
the **canary**: the isolation is verified by a failing read-attempt in the gate
self-tests, never assumed (§7). It also maintains the **vault manifest**
(relpath → sha256) that the held-out-test-drop check (C4) enforces at merge:
held-out tests may only change through the panel authoring path, which
regenerates the manifest — a merge that drops or mutates them is blocked.
"""

from __future__ import annotations

import hashlib
import json
import os

CANARY_NAME = ".canary"
CANARY_CONTENT = "vault-canary: if a worker can read this, isolation is broken\n"
MANIFEST_NAME = "manifest.json"

REQUIRED_LAYERS = ("sandbox_deny_read", "file_tool_deny", "strict_flags",
                   "config_out_of_scope", "egress_control", "role_processes")


class VaultError(ValueError):
    pass


def isolation_settings(vault_path: str) -> dict:
    """The worker-settings fragment for layers 1–3. The loop merges this into
    each worker's settings; layers 4–6 are structural/operator-side and are
    tracked by :func:`validate_isolation` so they cannot be silently skipped."""
    if not vault_path or ".." in vault_path.split(os.sep):
        raise VaultError(f"suspicious vault path {vault_path!r}")
    return {
        "permissions": {
            "deny": [
                f"Read({vault_path}/**)",
                f"Edit({vault_path}/**)",
                f"Write({vault_path}/**)",
                f"Grep({vault_path}/**)",
                f"Glob({vault_path}/**)",
            ],
        },
        "sandbox": {
            "enabled": True,
            "denyRead": [vault_path],
            "allowUnsandboxedCommands": False,
            "failIfUnavailable": True,
        },
    }


def validate_isolation(doc: dict) -> list:
    """Check a full isolation declaration covers all six layers. Returns the
    list of missing/misconfigured layers — non-empty means the vault must be
    treated as readable (fail closed)."""
    missing = []
    settings = doc.get("worker_settings") or {}
    sandbox = settings.get("sandbox") or {}
    denies = (settings.get("permissions") or {}).get("deny") or []

    if not sandbox.get("denyRead"):
        missing.append("sandbox_deny_read")
    if not any(rule.startswith("Read(") for rule in denies):
        missing.append("file_tool_deny")
    if sandbox.get("allowUnsandboxedCommands") is not False \
            or sandbox.get("failIfUnavailable") is not True:
        missing.append("strict_flags")
    for layer in ("config_out_of_scope", "egress_control", "role_processes"):
        if not (doc.get("structural_layers") or {}).get(layer):
            missing.append(layer)
    return missing


# -- canary --------------------------------------------------------------------


def write_canary(vault_path: str) -> str:
    os.makedirs(vault_path, exist_ok=True)
    path = os.path.join(vault_path, CANARY_NAME)
    with open(path, "w") as fh:
        fh.write(CANARY_CONTENT)
    return path


def canary_read_attempt(vault_path: str) -> dict:
    """Attempt to read the canary the way a worker's process would. The gate
    self-test requires ``isolation_ok`` True — i.e. the read must FAIL. A
    successful read is proof the boundary is broken (e.g. this process is not
    under the worker sandbox), reported honestly, never papered over."""
    path = os.path.join(vault_path, CANARY_NAME)
    try:
        with open(path) as fh:
            content = fh.read()
    except OSError as exc:
        return {"isolation_ok": True,
                "detail": f"read attempt failed as required: {exc}"}
    broken = content == CANARY_CONTENT
    return {"isolation_ok": False,
            "detail": ("canary content read back verbatim — the vault is "
                       "READABLE from this context" if broken else
                       "vault path readable (unexpected content) — boundary "
                       "not enforced")}


# -- manifest + held-out-drop check (C4 core) ------------------------------------


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(vault_path: str) -> dict:
    """relpath → sha256 for every vault file (canary + manifest excluded)."""
    if not os.path.isdir(vault_path):
        raise VaultError(f"vault path {vault_path!r} is not a directory")
    entries = {}
    for root, _dirs, files in os.walk(vault_path):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), vault_path)
            if rel in (CANARY_NAME, MANIFEST_NAME):
                continue
            entries[rel] = _sha256(os.path.join(root, name))
    return entries


def save_manifest(vault_path: str, entries: dict) -> str:
    path = os.path.join(vault_path, MANIFEST_NAME)
    with open(path, "w") as fh:
        json.dump({"entries": entries}, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def load_manifest(vault_path: str) -> dict:
    path = os.path.join(vault_path, MANIFEST_NAME)
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise VaultError(f"no manifest at {path} — the drop check cannot run "
                         f"(fail closed)") from None
    except json.JSONDecodeError as exc:
        raise VaultError(f"manifest {path} corrupt: {exc}") from None
    entries = doc.get("entries")
    if not isinstance(entries, dict):
        raise VaultError(f"manifest {path} has no 'entries' object")
    return entries


def check_heldout_drop(recorded: dict, current: dict) -> dict:
    """C4: compare the recorded manifest against the vault's current state.
    Dropped or mutated held-out tests block the merge — the corpus changes only
    via the panel authoring path, which re-records the manifest. New files are
    fine (fresh authoring grows the corpus)."""
    dropped = sorted(set(recorded) - set(current))
    mutated = sorted(r for r in recorded
                     if r in current and current[r] != recorded[r])
    added = sorted(set(current) - set(recorded))
    ok = not dropped and not mutated
    return {"ok": ok, "dropped": dropped, "mutated": mutated, "added": added,
            "why": ("held-out corpus intact" if ok else
                    "held-out tests dropped/mutated outside the authoring path")}
