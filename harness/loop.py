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


def run_marker_live(path: str) -> dict | None:
    """Read the advisory run marker; return its doc only when the owner pid is
    alive. A missing, torn, or dead-owner marker is *not* a live firing — the
    H1 Stop-hook closure gate keys on this to stay inert outside firings."""
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    try:
        pid = int(doc.get("pid", -1))
    except (TypeError, ValueError):
        return None
    return doc if pid > 0 and _pid_alive(pid) else None


DEFAULT_PAUSE_REQUEST_PATH = os.path.join("state", "pause.request")


def request_pause(path: str, reason: str, requested_by: str) -> dict:
    """I11 — flag a graceful pause from ANY session/terminal. The loop checks
    this at every tick boundary and performs the same clean pause a governor
    ``pause`` triggers. Attributed, like every operator judgment call."""
    if not isinstance(requested_by, str) or not requested_by.strip():
        raise LoopError("a pause request needs requested_by — operator "
                        "judgment calls are attributed, never ambient")
    doc = {"reason": (reason or "operator pause").strip(),
           "requested_by": requested_by.strip(),
           "requested_at": _utcnow_iso()}
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, sort_keys=True)
    os.replace(tmp, path)
    return doc


def pause_requested(path: str) -> dict | None:
    """The loop's tick-boundary check. A torn/corrupt request still pauses
    (fail toward the safe action — pausing is always recoverable)."""
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return {"reason": "unreadable pause request — pausing anyway "
                          "(fail-safe)", "requested_by": "unknown"}
    return doc if isinstance(doc, dict) else {
        "reason": "malformed pause request — pausing anyway (fail-safe)",
        "requested_by": "unknown"}


def clear_pause_request(path: str) -> bool:
    """Cleared by the loop AFTER the pause completes — a request is never
    consumed before the pause it asked for actually happened."""
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False


DEFAULT_PAUSE_ACK_PATH = os.path.join("state", "pause.ack")


def acknowledge_pause(request_path: str, ack_path: str, draining: list) -> dict:
    """I23 (P3v2-8) — the instant the loop SEES a pause request it says so on
    disk, before draining: the operator watching ``state/pause.ack`` learns
    the request landed, what is still in flight, and the policy (no new
    admissions; in-flight attempts run to their handoff — a killed attempt is
    a redone attempt, so drain latency is the price of zero rework). Written
    ack-then-drain so a session dying mid-drain still leaves the receipt."""
    req = pause_requested(request_path)
    if req is None:
        raise LoopError(f"no pause request at {request_path} to acknowledge")
    doc = {"request": req, "seen_at": _utcnow_iso(),
           "draining": list(draining or []),
           "policy": "no new admissions; in-flight attempts drain to handoff"}
    parent = os.path.dirname(ack_path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = ack_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    os.replace(tmp, ack_path)
    return doc


def closure_hook_config(path: str, snapshot: str, ledger: str, events: str,
                        **extra) -> dict:
    """Write the Stop-hook closure config at firing start (H1). The hook reads
    it from a fixed path; a live firing without one blocks stopping — so the
    loop writes it right after acquiring the run marker."""
    doc = {"snapshot": snapshot, "ledger": ledger, "events": events, **extra}
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, sort_keys=True)
    os.replace(tmp, path)
    return doc


# -- headless flags ---------------------------------------------------------------


def headless_env(base_env: dict | None = None) -> dict:
    """Environment for unattended firings. Never includes ANTHROPIC_API_KEY —
    its presence silently bills API instead of the subscription (§4)."""
    env = dict(base_env or {})
    env.pop("ANTHROPIC_API_KEY", None)
    env["DISABLE_NON_ESSENTIAL_MODEL_CALLS"] = "1"
    return env


def machinery_deny_rules() -> list:
    """H10 (§7 wiring amendment 5): file-tool deny rules for the loop's own
    machinery, applied to every worker **unconditionally** — branch-name
    prefixes are a dev convenience for the loop's own development, not a
    boundary a worker with git can adopt. Bash-side writes are caught by the
    machinery-paths gate step at merge; these rules close the file-tool path
    inside the worker session itself."""
    from . import hooks as _hooks
    return [f"{tool}({glob})"
            for glob in _hooks.MACHINERY_GLOBS
            for tool in ("Edit", "Write", "NotebookEdit")]


def worker_settings(vault_path: str | None = None) -> dict:
    """Strict worker settings: machinery denies always (H10); the vault
    isolation fragment merged in when a vault is in play. Imports stay lazy
    to keep loop importable standalone."""
    from . import vault as _vault
    settings: dict = {"sandbox": {"enabled": True,
                                  "allowUnsandboxedCommands": False,
                                  "failIfUnavailable": True},
                      "permissions": {"deny": machinery_deny_rules()}}
    if vault_path:
        frag = _vault.isolation_settings(vault_path)
        settings["permissions"]["deny"] += frag["permissions"]["deny"]
        settings["sandbox"] = frag["sandbox"]
    return settings


# -- headless one-shot workers (I26) -------------------------------------------------

DEFAULT_WORKER_MAX_TURNS = 80
WORKER_OVERLAY_RELPATH = os.path.join(".claude", "settings.local.json")

#: Raw pattern table for ``failures.load_patterns`` → ``classify`` on headless
#: worker deaths. Max-turns exhaustion is an AGENT failure (feeds the
#: escalation ladder at a fresh worker boundary), never an infra retry.
HEADLESS_FAILURE_PATTERNS = (
    {"pattern": r"out.of.usage.credits", "class": "permanent",
     "why": "credit/window exhaustion — park until the window resets; model "
            "substitution does not dodge the window (P3v2-12/13)"},
    {"pattern": r"max.?turns", "class": "permanent",
     "why": "worker exhausted --max-turns — agent-level failure; escalate at a "
            "fresh worker boundary (ladder), do not blind-retry"},
    {"pattern": r"may not exist or you may not have access", "class": "permanent",
     "why": "model id rejected at spawn — tiers.json vs build config error"},
    {"pattern": r"session limit|usage limit", "class": "retryable",
     "why": "window pressure — back off; the governor decides the pace"},
)


def write_worker_overlay(worktree: str, vault_path: str | None = None) -> str:
    """I26 — bind :func:`worker_settings` to one worker's worktree as
    ``.claude/settings.local.json`` (gitignored; the local scope merges with
    the worktree's committed machinery settings, deny-first). This is the
    layer-6 binding the Agent-tool spawn path could never do: each worker
    process loads its own strict sandbox + deny set from its own cwd."""
    path = os.path.join(worktree, WORKER_OVERLAY_RELPATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(worker_settings(vault_path), fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def headless_worker_cmd(prompt: str, model: str, *,
                        effort: str | None = None,
                        system_prompt: str | None = None,
                        json_schema_path: str | None = None,
                        max_turns: int = DEFAULT_WORKER_MAX_TURNS,
                        disallowed_tools: list | None = None,
                        session_persistence: bool = False,
                        tiers_doc: dict | None = None) -> list:
    """I26 — argv for one headless one-shot worker (``claude -p``): the one
    spawn path where every requested knob verifiably binds — per-spawn
    ``--model`` (concrete allowlisted id) AND ``--effort`` (measured-applied:
    benchmark 2026-07 round 2) — plus per-worker settings via
    :func:`write_worker_overlay`.

    Run with ``cwd=<worktree>`` and ``env=headless_env(...)``. Deny rules and
    blocking PreToolUse hooks survive ``--dangerously-skip-permissions``
    [official], so the six-layer stack holds. The spawn interlock's Bash
    regex recognizes this command — a fresh admission stamp is still required.
    """
    from . import spawncheck as _spawncheck
    if not isinstance(prompt, str) or not prompt.strip():
        raise LoopError("headless worker needs a non-empty prompt")
    resolved = _spawncheck.validate_spawn(model=model, effort=effort,
                                          tiers_doc=tiers_doc)
    if not isinstance(max_turns, int) or isinstance(max_turns, bool) \
            or max_turns < 1:
        raise LoopError(f"max_turns must be a positive int, got {max_turns!r}")
    cmd = ["claude", "-p", prompt,
           "--model", resolved["model"],
           "--output-format", "json",
           "--max-turns", str(max_turns),
           "--dangerously-skip-permissions"]
    if resolved["effort"] is not None:
        cmd += ["--effort", resolved["effort"]]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    if json_schema_path:
        # P3v2-9: the CLI (2.1.201) parses the flag value as INLINE JSON, not
        # a path — inline the file's contents, loud when unreadable.
        try:
            with open(json_schema_path) as fh:
                schema_doc = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise LoopError(f"json_schema_path {json_schema_path!r} unreadable "
                            f"or not JSON: {exc}")
        cmd += ["--json-schema", json.dumps(schema_doc, sort_keys=True)]
    if disallowed_tools:
        cmd += ["--disallowedTools", ",".join(disallowed_tools)]
    if not session_persistence:
        cmd += ["--no-session-persistence"]
    return cmd


def _strip_code_fences(text: str) -> str:
    """P3v2-10 — a compliant worker's final JSON often arrives fenced in
    ```json … ``` inside ``result``; strip one outer fence before parsing so
    an honoring worker is never misread as a contract violation."""
    body = text.strip()
    if not body.startswith("```"):
        return body
    lines = body.splitlines()
    if lines[-1].strip() == "```":
        lines = lines[1:-1]
    else:
        lines = lines[1:]
    return "\n".join(lines).strip()


def parse_worker_result(output_text: str) -> dict:
    """Normalize a ``--output-format json`` worker document. Returns
    ``{result, parsed, structured_output, usage, total_cost_usd, session_id}``
    — ``parsed`` is the role contract's final-message JSON when the worker
    honored it (fence-tolerant, P3v2-10; else None: an agent-level failure
    for the ladder, not a crash). Loud on output that is not the CLI's JSON
    document at all. Note: on CLI 2.1.201 ``structured_output`` stays null
    even with ``--json-schema`` — the ``result`` parse is the working path."""
    try:
        doc = json.loads(output_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LoopError(f"worker output is not the CLI's JSON document: {exc}")
    if not isinstance(doc, dict) or not isinstance(doc.get("result"), str):
        raise LoopError("worker output JSON lacks a string 'result' field")
    usage = doc.get("usage")
    parsed = doc.get("structured_output")
    if parsed is None:
        try:
            candidate = json.loads(_strip_code_fences(doc["result"]))
            parsed = candidate if isinstance(candidate, dict) else None
        except json.JSONDecodeError:
            parsed = None
    return {"result": doc["result"],
            "parsed": parsed,
            "structured_output": doc.get("structured_output"),
            "usage": usage if isinstance(usage, dict) else {},
            "total_cost_usd": doc.get("total_cost_usd"),
            "session_id": doc.get("session_id")}


DEFAULT_WORKER_WALL_TIMEOUT_S = 2700  # 45 min — absent calibrated estimates


def run_headless_worker(argv: list, cwd: str, env: dict | None = None,
                        timeout_s: float = DEFAULT_WORKER_WALL_TIMEOUT_S) -> dict:
    """I29 (P3v2-13) — run one headless worker under a wall-clock deadline.

    ``--max-turns`` never fires on a pre-compute hang: a quota-stalled worker
    sat 38 min at 0% CPU with an idle API socket and nothing killed it. Every
    worker therefore runs under a client-side deadline (3× the profile's P95
    wall estimate when calibrated; this default otherwise). On expiry the
    whole process group is killed and the death is returned structured —
    classify it and feed the ladder/park; never blind-retry a window stall."""
    import signal
    import subprocess
    import time
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        out, err = proc.communicate()
        timed_out = True
    wall = time.monotonic() - start
    return {"ok": (not timed_out) and proc.returncode == 0,
            "exit": None if timed_out else proc.returncode,
            "timed_out": timed_out, "wall_secs": round(wall, 3),
            "stdout": out or "", "stderr": err or ""}


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
