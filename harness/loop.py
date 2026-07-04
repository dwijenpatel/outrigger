#!/usr/bin/env python3
"""Build-loop support — run marker, headless flags, resume, lessons (E2).

The skill (``.claude/skills/build-loop/SKILL.md``) is the procedure; this module
is its deterministic machinery:

- **Advisory run marker** — firings are operator-started and operator-stopped
  (design non-goal: no auto-cron); the marker prevents *accidental* concurrent
  firings and self-heals when its owner died.
- **Headless flags** — every unattended firing gets
  ``DISABLE_NON_ESSENTIAL_MODEL_CALLS=1`` and the strict-sandbox worker
  settings (§11 Stage 0); forgetting them is a config bug, so they come from
  one function.
- **Claims-not-evidence resume** (§7): a firing reconstructs state from
  artifacts — git, the reconciled ledger view, gate reports — never from a
  model summary. ``resume_context`` assembles exactly that bundle.
- **Lessons corpus** (§4): orchestrator-owned JSONL; workers read-only.
  Injection is curated per spawn (subsystem/tag match, hard cap) — lessons are
  never resident in the frozen prefix.
- **Skill-inventory budget check** (§5.4 skills discipline): the skill list
  silently truncates past ~15k chars in the wild; the check makes overflow a
  loud failure instead of vanishing skills.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess

from . import ledger as _ledger

DEFAULT_SKILL_LIST_BUDGET = 15_000  # chars; mechanical ceiling, config-overridable


class LoopError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- advisory run marker ---------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_run_marker(path: str, owner: str) -> dict:
    """Take the advisory marker. A live owner refuses (operator arbitrates);
    a dead owner's marker self-heals."""
    if os.path.exists(path):
        with open(path) as fh:
            try:
                current = json.load(fh)
            except json.JSONDecodeError:
                current = None  # torn marker from a dead firing: reclaim
        if current and _pid_alive(int(current.get("pid", -1))):
            raise LoopError(
                f"run marker held by live pid {current['pid']} "
                f"({current.get('owner')}) since {current.get('acquired_at')} — "
                f"concurrent firings are operator-arbitrated, not automatic")
    marker = {"owner": owner, "pid": os.getpid(), "acquired_at": _utcnow_iso()}
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(marker, fh)
    os.replace(tmp, path)
    return marker


def release_run_marker(path: str) -> bool:
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False


# -- headless flags ---------------------------------------------------------------


def headless_env(base_env: dict | None = None) -> dict:
    """Environment for unattended firings. Never includes ANTHROPIC_API_KEY —
    its presence silently bills API instead of the subscription (§4)."""
    env = dict(base_env or {})
    env.pop("ANTHROPIC_API_KEY", None)
    env["DISABLE_NON_ESSENTIAL_MODEL_CALLS"] = "1"
    return env


def worker_settings(vault_path: str | None = None) -> dict:
    """Strict worker settings; merges the vault isolation fragment when a
    vault is in play. Import stays lazy to keep loop importable standalone."""
    from . import vault as _vault
    settings: dict = {"sandbox": {"enabled": True,
                                  "allowUnsandboxedCommands": False,
                                  "failIfUnavailable": True}}
    if vault_path:
        frag = _vault.isolation_settings(vault_path)
        settings["permissions"] = frag["permissions"]
        settings["sandbox"] = frag["sandbox"]
    return settings


# -- claims-not-evidence resume -----------------------------------------------------


def resume_context(repo_dir: str, ledger: _ledger.Ledger, log: _ledger.EventLog,
                   artifacts: dict | None = None) -> dict:
    """Reconstruct firing state from artifacts only (§7 'never summarize a run
    from memory'). Returns the bundle the orchestrator reads before acting:
    git facts, reconciled ledger digest, pending events, resume marker."""
    git_facts = {}
    for name, args in (("branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
                       ("head", ["rev-parse", "--short", "HEAD"]),
                       ("dirty_entries", ["status", "--porcelain"])):
        try:
            out = subprocess.run(["git", "-C", repo_dir, *args],
                                 capture_output=True, text=True, timeout=10)
            git_facts[name] = (out.stdout.strip() if out.returncode == 0
                               else None)
        except (OSError, subprocess.TimeoutExpired):
            git_facts[name] = None
    git_facts["dirty"] = bool(git_facts.get("dirty_entries"))
    git_facts.pop("dirty_entries", None)

    view = _ledger.summary(ledger, log, artifacts)
    return {
        "git": git_facts,
        "ledger_digest": _ledger.digest(ledger, log, artifacts),
        "summary": view,
        "pending_events": log.pending(),
        "resume_marker": view["resume_marker"],
        "rule": "claims-not-evidence: act on this bundle, not on any prior "
                "model summary; verify surprises against the artifacts",
    }


# -- lessons corpus ------------------------------------------------------------------


class LessonsCorpus:
    """Orchestrator-owned JSONL of lessons. Workers get curated injections."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> list:
        try:
            with open(self.path) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            return []
        out = []
        for lineno, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LoopError(f"{self.path}:{lineno}: corrupt lesson: "
                                f"{exc}") from None
        return out

    def add(self, text: str, tags: list, source_task: str) -> dict:
        """Called with a handoff's key_learnings — 'surprising only' is the
        author's contract; dedup here is exact-text only."""
        if not text or not isinstance(tags, list):
            raise LoopError("lesson needs text and a tag list")
        if any(l["text"] == text for l in self.read()):
            return {"deduped": True, "text": text}
        rec = {"ts": _utcnow_iso(), "text": text, "tags": tags,
               "source_task": source_task}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def select_for_task(self, task: dict, cap: int = 5) -> list:
        """Curated per-spawn injection: tag-matched first (task subsystem,
        phase, profile), newest first, hard cap — never the whole corpus."""
        wanted = {task.get("subsystem"), task.get("phase"),
                  task.get("profile")} - {None}
        lessons = self.read()
        tagged = [l for l in lessons if wanted & set(l["tags"])]
        untagged_general = [l for l in lessons if "general" in l["tags"]
                            and l not in tagged]
        ranked = list(reversed(tagged)) + list(reversed(untagged_general))
        return ranked[:cap]


# -- skill-inventory budget -----------------------------------------------------------


def skill_budget_check(skills_dirs: list,
                       budget_chars: int = DEFAULT_SKILL_LIST_BUDGET) -> dict:
    """Sum the name+description surface of every SKILL.md; overflow is loud.
    (In the wild the list silently truncates — vanished skills, §5.4.)"""
    entries, total = [], 0
    for skills_dir in skills_dirs:
        if not os.path.isdir(skills_dir):
            continue
        for root, _dirs, files in os.walk(skills_dir):
            for name in files:
                if name != "SKILL.md":
                    continue
                path = os.path.join(root, name)
                with open(path) as fh:
                    head = fh.read(4000)
                desc = ""
                if head.startswith("---"):
                    for line in head.splitlines():
                        if line.startswith("description:"):
                            desc = line[len("description:"):].strip()
                            break
                cost = len(os.path.basename(os.path.dirname(path))) + len(desc)
                entries.append({"skill": path, "chars": cost})
                total += cost
    return {"ok": total <= budget_chars, "total_chars": total,
            "budget_chars": budget_chars, "skills": len(entries),
            "why": (f"{total} chars of {budget_chars} budget across "
                    f"{len(entries)} skill(s)" if total <= budget_chars else
                    f"OVER BUDGET: {total} > {budget_chars} — skills past the "
                    f"ceiling silently vanish from the prompt")}
