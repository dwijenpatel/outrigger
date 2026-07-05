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
EVIDENCE_DIRNAME = "evidence"  # H7: vault-side evidence store

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
    """relpath → sha256 for every vault file (canary, manifest, and the H7
    evidence store excluded — evidence is execution *output*, not held-out
    corpus, and must not trip the drop check when it changes)."""
    if not os.path.isdir(vault_path):
        raise VaultError(f"vault path {vault_path!r} is not a directory")
    entries = {}
    for root, dirs, files in os.walk(vault_path):
        if root == vault_path and EVIDENCE_DIRNAME in dirs:
            dirs.remove(EVIDENCE_DIRNAME)
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), vault_path)
            if rel in (CANARY_NAME, MANIFEST_NAME):
                continue
            entries[rel] = _sha256(os.path.join(root, name))
    return entries


# -- H7: evidence leakage policy ----------------------------------------------------


def heldout_evidence_dir(vault_path: str) -> str:
    """The vault-side evidence store (§5.5 point 5): held-out execution
    output (validator transcripts, held-out test logs) is written HERE —
    covered by the same deny rules as the corpus — never to the in-repo
    evidence directory a retry implementer can read."""
    if not os.path.isdir(vault_path):
        raise VaultError(f"vault path {vault_path!r} is not a directory")
    path = os.path.join(vault_path, EVIDENCE_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def scrub(text: str, entries: dict) -> str:
    """Manifest-based scrubbing for in-repo artifacts (§5.5 point 5):
    vault-relative paths and test-file identifiers are replaced with stable
    ``vault:<hash>`` tokens, so gate reports and verdicts ride review without
    naming held-out content. Behavior-level quotes are the accepted, budgeted
    leak; identifiers are not."""
    if not text or not entries:
        return text
    replacements: dict = {}
    for rel in entries:
        token = "vault:" + hashlib.sha256(rel.encode()).hexdigest()[:8]
        replacements[rel] = token
        base = os.path.basename(rel)
        replacements.setdefault(base, token)
        stem = os.path.splitext(base)[0]
        if stem and stem != base:
            replacements.setdefault(stem, token)
    for needle in sorted(replacements, key=len, reverse=True):
        text = text.replace(needle, replacements[needle])
    return text


# -- I4: vault config is generated + machine-checked, never trusted from hand-edits


DEFAULT_CONFIG_RELPATH = os.path.join("harness", "config",
                                      "vault-isolation.json")


def load_vault_config(repo_root: str, config_path: str | None = None) -> dict:
    path = config_path or os.path.join(repo_root, DEFAULT_CONFIG_RELPATH)
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise VaultError(f"no vault config at {path}") from None
    except json.JSONDecodeError as exc:
        raise VaultError(f"vault config {path} corrupt: {exc}") from None
    if not isinstance(doc, dict):
        raise VaultError(f"vault config {path}: not an object")
    return doc


def check_vault_config(doc: dict, repo_root: str) -> dict:
    """P2-3 — the checks a hand-edit skips. Returns {"ok", "configured",
    "checks", "why"}. Unconfigured (vault_path null) is reported distinctly:
    fine for a template repo, refused at firing time. A configured path must
    be **absolute**, **outside the repo**, and the worker_settings must equal
    exactly what ``isolation_settings(vault_path)`` regenerates — any drift
    (typo'd denyRead, deny rules naming a different path) is loud."""
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": ok, "detail": detail})
        return ok

    def finish(configured):
        ok = all(c["ok"] for c in checks)
        failing = next((c for c in checks if not c["ok"]), None)
        return {"ok": ok, "configured": configured, "checks": checks,
                "why": (f"{failing['check']}: {failing['detail']}"
                        if failing else
                        ("vault config valid" if configured else
                         "vault unconfigured — run `python3 -m harness.vault "
                         "configure --vault-path /abs/path-outside-repo` "
                         "before any firing"))}

    vault_path = doc.get("vault_path")
    if vault_path in (None, ""):
        check("configured", True,
              "vault_path is null — template state; firings refuse until "
              "configured")
        return finish(False)
    if not isinstance(vault_path, str):
        check("vault_path", False, "vault_path must be a string or null")
        return finish(True)
    if not os.path.isabs(vault_path):
        check("vault_path_absolute", False,
              f"{vault_path!r} is relative — a relative vault path binds to "
              f"whatever cwd a worker happens to have (fail-closed)")
        return finish(True)
    check("vault_path_absolute", True, vault_path)

    real_vault = os.path.realpath(vault_path)
    real_repo = os.path.realpath(repo_root)
    inside = real_vault == real_repo or \
        os.path.commonpath([real_vault, real_repo]) == real_repo
    if inside:
        check("vault_outside_repo", False,
              f"{vault_path!r} resolves inside the repo — an in-repo vault "
              f"dirties the tree and rides git history into worker "
              f"worktrees (P1-7)")
        return finish(True)
    check("vault_outside_repo", True, "outside the repo tree")

    expected = isolation_settings(vault_path)
    if doc.get("worker_settings") != expected:
        check("worker_settings_regenerable", False,
              "worker_settings differ from isolation_settings(vault_path) — "
              "hand-edited drift (typo'd denyRead, mismatched deny rules); "
              "regenerate with `python3 -m harness.vault configure`")
        return finish(True)
    check("worker_settings_regenerable", True,
          "exactly the generated layers 1–3")

    missing = validate_isolation(doc)
    if missing:
        check("six_layers", False, f"missing/misconfigured layers: {missing}")
        return finish(True)
    check("six_layers", True, "all six layers declared")
    return finish(True)


def configure_vault(repo_root: str, vault_path: str,
                    config_path: str | None = None) -> dict:
    """The one sanctioned way to set the vault location: regenerates
    layers 1–3 from ``vault_path``, preserves ``_meta`` and
    ``structural_layers``, refuses anything ``check_vault_config`` would
    refuse. Hand-editing the config is exactly the human-error class this
    replaces."""
    path = config_path or os.path.join(repo_root, DEFAULT_CONFIG_RELPATH)
    try:
        existing = load_vault_config(repo_root, path)
    except VaultError:
        existing = {}
    doc = {
        "_meta": existing.get("_meta", {}),
        "structural_layers": existing.get("structural_layers", {}),
        "vault_path": vault_path,
        "worker_settings": isolation_settings(vault_path),
    }
    result = check_vault_config(doc, repo_root)
    if not result["ok"] or not result["configured"]:
        raise VaultError(f"refusing to write an invalid vault config: "
                         f"{result['why']}")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return result


def verdict_verbosity(verdicts: list, entries: dict) -> dict:
    """H7 — the leakage budget's verdict-verbosity line: how many vault
    identifiers appear in verdict text. Mentions are counted post-scrub (each
    ``vault:`` token = one identifier occurrence), so nested path/basename
    overlaps don't inflate the count. Non-zero means validator output is
    carrying corpus identifiers toward in-repo surfaces."""
    by_lens: dict = {}
    total = 0
    for verdict in verdicts:
        lens = verdict.get("lens", "?")
        raw = json.dumps(verdict, sort_keys=True)
        mentions = scrub(raw, entries).count("vault:")
        by_lens[lens] = by_lens.get(lens, 0) + mentions
        total += mentions
    why = ("verdicts name no vault identifiers" if total == 0 else
           f"{total} vault-identifier mention(s) in verdict text — scrub "
           f"before these ride review, and tighten validator verbosity")
    return {"mentions": total, "by_lens": by_lens, "why": why}


def scrub_for_repo(text: str, vault_path: str) -> str:
    """Scrub with the vault's own manifest; a missing/corrupt manifest scrubs
    nothing (the drop check already fails the merge in that state — this
    layer is protective, not the enforcement point)."""
    try:
        entries = load_manifest(vault_path)
    except VaultError:
        return text
    return scrub(text, entries)


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


# -- CLI (I4) ----------------------------------------------------------------------


def _cli(argv=None) -> int:
    import argparse
    import sys
    p = argparse.ArgumentParser(
        description="Vault config: machine-checked, never hand-edited (I4)")
    sub = p.add_subparsers(dest="cmd", required=True)
    check_p = sub.add_parser("check", help="validate the committed config; "
                                           "exit 2 unless configured + valid")
    check_p.add_argument("--repo", default=".")
    check_p.add_argument("--config")
    cfg_p = sub.add_parser("configure", help="the one sanctioned way to set "
                                             "the vault location")
    cfg_p.add_argument("--repo", default=".")
    cfg_p.add_argument("--config")
    cfg_p.add_argument("--vault-path", required=True,
                       help="absolute path OUTSIDE the repo")
    args = p.parse_args(argv)

    if args.cmd == "configure":
        try:
            result = configure_vault(args.repo, args.vault_path,
                                     config_path=args.config)
        except VaultError as exc:
            print(f"configure refused: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return 0

    try:
        doc = load_vault_config(args.repo, args.config)
    except VaultError as exc:
        print(f"vault config unreadable: {exc} (fail-closed)", file=sys.stderr)
        return 2
    result = check_vault_config(doc, args.repo)
    print(json.dumps(result, indent=2))
    if not result["ok"] or not result["configured"]:
        print(f"vault NOT fireable: {result['why']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli())
