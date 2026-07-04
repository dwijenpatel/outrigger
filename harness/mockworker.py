#!/usr/bin/env python3
"""Token-free loop test rig — deterministic mock worker + trace replay.

Design §11 Stage 0 (2026-07-04 amendment; research:
unattended-operation-prior-art.md §7). A **mock worker** stands in for an
implementer/validator subagent: it emits scripted, schema-shaped results with
synthetic usage counters and performs workspace side effects only on successful
turns — so the build loop, governor thresholds, window-aware admission, ledger
accounting, and gate logic are e2e-testable at **zero quota**.

- Usage modes: ``static`` (each turn reports its scripted usage) and
  ``cumulative`` (reported usage scales with the count of successful turns so
  far — exercises multi-turn accounting; cancelled/error turns don't increment).
- Turn kinds: a normal result (``outcome`` pass/fail/parked), an infrastructure
  ``error`` (text for :mod:`harness.failures` to classify), or ``cancelled``.
- **Trace replay:** record normalized result events once (JSONL), replay them
  forever for free. Re-recording from *real* agents spends quota and is
  operator-gated (plan ground rule).

The result shape mirrors the worker-return contract (E1 will freeze the full
schema; this rig is expected to iterate with it — plan A6 note).
"""

from __future__ import annotations

import json
import os

from . import runlog as _runlog

USAGE_MODES = ("static", "cumulative")
USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_read_tokens", "cache_creation_tokens")


class MockWorkerError(ValueError):
    pass


def _validate_turn(turn: dict, i: int) -> dict:
    if not isinstance(turn, dict):
        raise MockWorkerError(f"turn {i}: must be an object")
    kinds = sum(k in turn for k in ("outcome", "error", "cancelled"))
    if kinds != 1:
        raise MockWorkerError(
            f"turn {i}: exactly one of outcome/error/cancelled required")
    if "outcome" in turn and turn["outcome"] not in _runlog.OUTCOMES:
        raise MockWorkerError(
            f"turn {i}: outcome {turn['outcome']!r} not in {_runlog.OUTCOMES}")
    usage = turn.get("usage", {})
    if not isinstance(usage, dict):
        raise MockWorkerError(f"turn {i}: usage must be an object")
    for field, value in usage.items():
        if field not in USAGE_FIELDS:
            raise MockWorkerError(f"turn {i}: unknown usage field {field!r}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MockWorkerError(f"turn {i}: usage {field}={value!r} must be a "
                                  f"non-negative int")
    for j, effect in enumerate(turn.get("workspace_effects", [])):
        if not isinstance(effect, dict) or not isinstance(effect.get("path"), str) \
                or not isinstance(effect.get("append"), str):
            raise MockWorkerError(
                f"turn {i}: workspace effect {j} needs string 'path' and 'append'")
        if os.path.isabs(effect["path"]) or ".." in effect["path"].split(os.sep):
            raise MockWorkerError(
                f"turn {i}: workspace effect {j} path must stay inside the cwd")
    return turn


class MockWorker:
    """Deterministic scripted worker. ``run_turn()`` steps through the script."""

    def __init__(self, script: list, usage_mode: str = "static",
                 cwd: str | None = None):
        if usage_mode not in USAGE_MODES:
            raise MockWorkerError(f"usage_mode {usage_mode!r} not in {USAGE_MODES}")
        if not isinstance(script, list) or not script:
            raise MockWorkerError("script must be a non-empty list of turns")
        self.script = [_validate_turn(t, i) for i, t in enumerate(script)]
        self.usage_mode = usage_mode
        self.cwd = cwd
        self.turn_index = 0
        self.successful_turns = 0

    @property
    def exhausted(self) -> bool:
        return self.turn_index >= len(self.script)

    def _usage(self, turn: dict, successful_count: int) -> dict:
        base = {f: turn.get("usage", {}).get(f, 0) for f in USAGE_FIELDS}
        if self.usage_mode == "cumulative":
            base = {f: v * successful_count for f, v in base.items()}
        base["total_tokens"] = sum(base.values())
        return base

    def run_turn(self) -> dict:
        """Execute the next scripted turn. Workspace effects apply only after a
        successful ('pass') turn — mirroring the recorded-agent contract."""
        if self.exhausted:
            raise MockWorkerError("script exhausted — no more turns")
        turn = self.script[self.turn_index]
        self.turn_index += 1

        if "error" in turn:
            return {"kind": "error", "error": turn["error"],
                    "turn": self.turn_index}
        if turn.get("cancelled"):
            return {"kind": "cancelled", "turn": self.turn_index}

        success = turn["outcome"] == "pass"
        if success:
            self.successful_turns += 1
        usage = self._usage(turn, self.successful_turns if success else
                            max(self.successful_turns, 1))
        if success:
            for effect in turn.get("workspace_effects", []):
                if self.cwd is None:
                    raise MockWorkerError(
                        "workspace effects scripted but no cwd configured")
                path = os.path.join(self.cwd, effect["path"])
                os.makedirs(os.path.dirname(path) or self.cwd, exist_ok=True)
                with open(path, "a") as fh:
                    fh.write(effect["append"])
        result = {
            "kind": "result",
            "turn": self.turn_index,
            "outcome": turn["outcome"],
            "usage": usage,
            "summary": turn.get("summary", ""),
            "key_changes_made": turn.get("key_changes_made", []),
            "key_learnings": turn.get("key_learnings", []),
            "intent": turn.get("intent", ""),
        }
        return result

    def to_runlog_record(self, result: dict, task_id: str, role: str,
                         profile: str, tier: str, model_id: str,
                         effort: str) -> dict:
        """Shape one result as a validated run-log task record — the bridge that
        lets integration tests feed the governor's estimate rung."""
        if result.get("kind") != "result":
            raise MockWorkerError("only 'result' turns become run-log records")
        rec = {
            "event": "task_complete", "task_id": task_id, "role": role,
            "profile": profile, "tier": tier, "model_id": model_id,
            "effort": effort, "outcome": result["outcome"],
        }
        rec.update({f: result["usage"][f] for f in USAGE_FIELDS})
        rec["total_tokens"] = result["usage"]["total_tokens"]
        return _runlog.validate_record(rec)


# -- trace record/replay -----------------------------------------------------


def record_trace(path: str, events: list) -> None:
    """Write normalized result events as a JSONL trace (record once, replay
    forever). Overwrites: a trace is a committed fixture, not a log."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        for i, event in enumerate(events):
            if not isinstance(event, dict) or "kind" not in event:
                raise MockWorkerError(f"trace event {i}: needs a 'kind'")
            fh.write(json.dumps(event, sort_keys=True) + "\n")


def replay_trace(path: str) -> list:
    """Read a trace back. Corruption is loud — a silently-truncated fixture
    would make a regression test pass vacuously."""
    events = []
    with open(path) as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MockWorkerError(
                    f"trace {path}:{lineno}: corrupt event: {exc}") from None
            if not isinstance(event, dict) or "kind" not in event:
                raise MockWorkerError(f"trace {path}:{lineno}: needs a 'kind'")
            events.append(event)
    return events


def worker_from_trace(path: str, cwd: str | None = None) -> MockWorker:
    """Build a MockWorker whose turns replay a recorded trace's results."""
    script = []
    for event in replay_trace(path):
        if event["kind"] == "result":
            turn = {"outcome": event["outcome"],
                    "usage": {f: event.get("usage", {}).get(f, 0)
                              for f in USAGE_FIELDS},
                    "summary": event.get("summary", "")}
            script.append(turn)
        elif event["kind"] == "error":
            script.append({"error": event.get("error", "recorded error")})
        elif event["kind"] == "cancelled":
            script.append({"cancelled": True})
    if not script:
        raise MockWorkerError(f"trace {path}: no replayable events")
    return MockWorker(script, cwd=cwd)
