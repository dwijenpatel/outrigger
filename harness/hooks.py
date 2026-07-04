#!/usr/bin/env python3
"""Zero-token enforcement library — logic behind the hooks/ scripts (C1–C3).

Design §5.2 rule 1 and §7 (2026-07-04 amendments). Split of responsibility:

- **Advisory layers fail open** — the prefix-edit *warning* (C1) never blocks;
  its whole job is making the silent-no-op/cache hazard visible.
- **Enforcement gates fail closed** — destructive-git, machinery-paths, and
  risk-floor checks (C2/C3) block on violation *and on their own inability to
  decide* (undeterminable git state, unloadable config): a gate that cannot run
  refuses.
- **Executable/gate config loads only from the ratified default branch** at its
  committed state (``git show <ref>:<path>``), never from a task branch's
  working tree — a task branch editing the gate's own config must not be able
  to weaken the gate that judges it (§7, extends isolation layer 4).

Hook protocol: scripts read the PreToolUse JSON from stdin and exit 0 (allow) /
2 (block, message on stderr). This module is pure logic — testable without a
subprocess.
"""

from __future__ import annotations

import json
import re
import subprocess

from .runlog import PROFILES


class HookError(ValueError):
    pass


def parse_hook_input(text: str) -> dict:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HookError(f"hook stdin is not JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise HookError("hook stdin must be a JSON object")
    return doc


# -- glob matching (supports **) ----------------------------------------------


def _glob_to_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def path_matches(path: str, pattern: str) -> bool:
    while path.startswith("./"):
        path = path[2:]
    return bool(_glob_to_regex(pattern).match(path))


# -- C1: prefix-edit warning (advisory, fail-open) ------------------------------

#: Files in the frozen prefix (§5.2): a mid-firing edit is a silent no-op that
#: also risks the cache; the hook makes it loud. Config may extend this.
PREFIX_GLOBS = (
    "CLAUDE.md",
    "**/CLAUDE.md",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/agents/**",
    ".claude/skills/**",
)


def check_prefix_edit(tool_name: str, tool_input: dict,
                      globs=PREFIX_GLOBS) -> str | None:
    """Return a warning string when an Edit/Write touches a prefix file."""
    if tool_name not in ("Edit", "Write", "NotebookEdit"):
        return None
    path = tool_input.get("file_path") or ""
    for pattern in globs:
        if path_matches(path, pattern):
            return (f"prefix-edit warning: {path} is part of the frozen prompt "
                    f"prefix (§5.2). A mid-firing edit does NOT take effect until "
                    f"the next session and risks cache churn — make prefix changes "
                    f"between firings.")
    return None


# -- C2: destructive git + machinery paths (gates, fail-closed) -----------------

DESTRUCTIVE_GIT_PATTERNS = (
    (r"push\s+[^|;&]*(--force\b|-f\b|--force-with-lease)", "force push"),
    (r"push\s+[^|;&]*--delete", "remote branch deletion"),
    (r"reset\s+[^|;&]*--hard", "hard reset discards work"),
    (r"clean\s+[^|;&]*-[a-z]*f", "git clean -f deletes untracked files"),
    (r"checkout\s+[^|;&]*--\s+\.", "checkout -- . discards the working tree"),
    (r"restore\s+[^|;&]*(--worktree|\s--\s+\.)", "restore discards edits"),
    (r"branch\s+[^|;&]*-D\b", "force branch deletion"),
    (r"filter-branch|filter-repo", "history rewrite"),
    (r"update-ref\s+[^|;&]*-d", "ref deletion"),
    (r"reflog\s+expire", "reflog expiry destroys recovery points"),
    (r"stash\s+(drop|clear)", "stash deletion"),
    (r"rebase\s", "rebase rewrites task-branch history mid-loop"),
)


def check_destructive_git(command: str) -> str | None:
    """Return a violation string when a Bash command contains destructive git."""
    if not isinstance(command, str):
        raise HookError("Bash tool_input.command must be a string")
    if not re.search(r"\bgit\b", command):
        return None
    for pattern, why in DESTRUCTIVE_GIT_PATTERNS:
        if re.search(r"\bgit\b[^|;&]*" + pattern, command):
            return f"destructive git blocked: {why} (`{command.strip()}`)"
    return None


#: Paths a task branch may never edit: the loop's own machinery (§7).
MACHINERY_GLOBS = (
    "harness/**",
    "hooks/**",
    "tools/**",
    ".claude/**",
    "docs/plan/**",
    "docs/design/**",
)

#: Branches where machinery edits are legitimate (the loop itself merges here;
#: ratification happens before merge).
MACHINERY_BRANCH_ALLOW = re.compile(r"^(main|master|feat/|chore/|docs/)")


def check_machinery_paths(tool_name: str, tool_input: dict, branch: str | None,
                          globs=MACHINERY_GLOBS,
                          branch_allow=MACHINERY_BRANCH_ALLOW) -> str | None:
    """Block Edit/Write to machinery paths from task branches. ``branch`` None
    (undeterminable git state) blocks — fail closed."""
    if tool_name not in ("Edit", "Write", "NotebookEdit"):
        return None
    path = tool_input.get("file_path") or ""
    hit = next((p for p in globs if path_matches(path, p)), None)
    if hit is None:
        return None
    if branch is None:
        return (f"machinery-path edit blocked: cannot determine the current "
                f"branch, refusing to allow an edit under {hit!r} (fail-closed)")
    if branch_allow.match(branch):
        return None
    return (f"machinery-path edit blocked: task branch {branch!r} may not edit "
            f"{path} (matches protected {hit!r}); machinery changes go through "
            f"the ratification queue (§7)")


def current_branch(repo_dir: str) -> str | None:
    """Best-effort branch name; None when undeterminable (callers fail closed)."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    name = out.stdout.strip()
    return name or None


def load_ratified_config(repo_dir: str, rel_path: str,
                         ref: str = "main") -> dict | None:
    """Load gate config from the ratified branch's committed state — never from
    the working tree under judgment. Returns None when unreadable; the caller
    must treat None as 'refuse' (fail-closed), never as 'empty config, allow'."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, "show", f"{ref}:{rel_path}"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        doc = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


# -- C3: risk-floor map (gate, fail-closed; enforced against diff paths) --------


def validate_floor_map(doc) -> list:
    """Floor map: [{"glob": ..., "min_profile": ...}]. Bad config is loud."""
    if not isinstance(doc, list):
        raise HookError("risk-floor map must be a JSON list")
    out = []
    for i, entry in enumerate(doc):
        if not isinstance(entry, dict) or not isinstance(entry.get("glob"), str) \
                or not entry.get("glob"):
            raise HookError(f"floor entry {i}: needs a non-empty 'glob'")
        if entry.get("min_profile") not in PROFILES:
            raise HookError(
                f"floor entry {i}: min_profile {entry.get('min_profile')!r} "
                f"not in {PROFILES}")
        out.append({"glob": entry["glob"], "min_profile": entry["min_profile"]})
    return out


def floor_for_paths(paths, floor_map: list) -> dict:
    """Highest minimum profile any touched path demands, with the matches."""
    best_rank, matched = -1, []
    for path in paths:
        for entry in floor_map:
            if path_matches(path, entry["glob"]):
                matched.append({"path": path, "glob": entry["glob"],
                                "min_profile": entry["min_profile"]})
                best_rank = max(best_rank, PROFILES.index(entry["min_profile"]))
    return {"min_profile": PROFILES[best_rank] if best_rank >= 0 else None,
            "matched": matched}


def check_risk_floor(task_profile: str, diff_paths, floor_map: list) -> dict:
    """The §7 rule: the *actual diff paths* decide the minimum validation
    profile — a mis-tagged security task cannot be validated cheaply."""
    if task_profile not in PROFILES:
        raise HookError(f"unknown profile {task_profile!r}")
    floor = floor_for_paths(diff_paths, floor_map)
    required = floor["min_profile"]
    ok = required is None or PROFILES.index(task_profile) >= PROFILES.index(required)
    return {"ok": ok, "task_profile": task_profile, "required": required,
            "matched": floor["matched"],
            "why": ("no floored paths touched" if required is None else
                    f"diff touches paths floored at {required!r}; task profile "
                    f"is {task_profile!r}")}
