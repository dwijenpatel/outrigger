#!/usr/bin/env python3
"""Task ledger + status index — the disk state any context resumes from.

Design §3 principle 4 ("disk is the memory") and §9: phase ledgers, the status index,
and the run-log live on disk; any context can die at any moment and the loop resumes
from files alone. This module is that canonical state.

- **Ledger** — the task definitions: id, phase, risk profile, hard ``deps``, soft
  ``may_be_invalidated_by`` edges (the §6.1 ``start-early-safe`` input). Ledger files
  are authored at planning time and are read-only to this module.
- **StatusIndex** — the mutable side: per-task status with validated transitions,
  atomically written (write-temp + rename) so a mid-write death never corrupts the
  resume state. Also carries the governor's pause/resume marker (§5.1).

Cycle detection and scheduling policy (priorities, start-early-safe) are increment B2
(``harness/scheduler.py``); here :func:`runnable` gives only the dependency-correct
candidate set a resume view needs. Tasks on a dependency cycle are simply never
runnable — B2's preflight DAG check is what reports them loudly.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile

from .runlog import PROFILES

STATUSES = ("not_started", "in_progress", "parked", "done", "failed")

#: Legal transitions. "done" is terminal by design — reopening a validated task is an
#: operator decision made by editing the file, never something the loop does silently.
TRANSITIONS = {
    "not_started": {"in_progress"},
    "in_progress": {"done", "failed", "parked"},
    "parked": {"in_progress", "failed"},
    "failed": {"in_progress"},
    "done": set(),
}


class LedgerError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_str_list(entry: dict, field: str, task_id: str) -> list:
    values = entry.get(field, [])
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise LedgerError(f"task {task_id!r}: {field} must be a list of task ids")
    return values


def validate_tasks(doc: dict) -> dict:
    """Validate a ledger document {"tasks": [...]} → tasks keyed by id."""
    if not isinstance(doc, dict) or not isinstance(doc.get("tasks"), list):
        raise LedgerError("ledger document must be an object with a 'tasks' list")
    tasks = {}
    for entry in doc["tasks"]:
        if not isinstance(entry, dict):
            raise LedgerError(f"task entry must be an object, got {type(entry).__name__}")
        task_id = entry.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise LedgerError(f"task missing a non-empty string id: {entry!r}")
        if task_id in tasks:
            raise LedgerError(f"duplicate task id {task_id!r}")
        if not isinstance(entry.get("phase"), str) or not entry["phase"]:
            raise LedgerError(f"task {task_id!r}: missing phase")
        if entry.get("profile") not in PROFILES:
            raise LedgerError(
                f"task {task_id!r}: profile {entry.get('profile')!r} not in {PROFILES}")
        tasks[task_id] = dict(entry)
        tasks[task_id]["deps"] = _require_str_list(entry, "deps", task_id)
        tasks[task_id]["may_be_invalidated_by"] = _require_str_list(
            entry, "may_be_invalidated_by", task_id)

    for task_id, entry in tasks.items():
        for field in ("deps", "may_be_invalidated_by"):
            for ref in entry[field]:
                if ref == task_id:
                    raise LedgerError(f"task {task_id!r}: {field} references itself")
                if ref not in tasks:
                    raise LedgerError(
                        f"task {task_id!r}: {field} references unknown task {ref!r}")
    return tasks


class Ledger:
    def __init__(self, tasks_by_id: dict):
        self.tasks = tasks_by_id

    @classmethod
    def load(cls, path: str) -> "Ledger":
        with open(path) as fh:
            return cls(validate_tasks(json.load(fh)))

    def __contains__(self, task_id: str) -> bool:
        return task_id in self.tasks

    def __getitem__(self, task_id: str) -> dict:
        return self.tasks[task_id]


class StatusIndex:
    """Mutable per-task status, atomically persisted. Absent task → not_started."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> dict:
        try:
            with open(self.path) as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            return {"tasks": {}}
        except json.JSONDecodeError as exc:
            # A half-written index would silently reset every status — that must be a
            # loud stop, not a fresh start. Atomic writes make this unreachable except
            # via outside interference.
            raise LedgerError(f"status index {self.path} is corrupt: {exc}") from None
        if not isinstance(doc, dict) or not isinstance(doc.get("tasks"), dict):
            raise LedgerError(f"status index {self.path} has no 'tasks' object")
        return doc

    def _write(self, doc: dict) -> None:
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=parent, prefix=".status-index-")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def status_of(self, task_id: str) -> str:
        entry = self.read()["tasks"].get(task_id)
        return entry["status"] if entry else "not_started"

    def update(self, task_id: str, status: str, note: str | None = None,
               ledger: Ledger | None = None) -> dict:
        """Transition one task. With a ledger supplied, unknown task ids are rejected —
        a typo'd id must not create a phantom task."""
        if status not in STATUSES:
            raise LedgerError(f"unknown status {status!r}; known: {STATUSES}")
        if ledger is not None and task_id not in ledger:
            raise LedgerError(f"unknown task id {task_id!r} (not in ledger)")
        doc = self.read()
        current = doc["tasks"].get(task_id, {}).get("status", "not_started")
        if status != current and status not in TRANSITIONS[current]:
            raise LedgerError(
                f"illegal transition {current!r} -> {status!r} for task {task_id!r}; "
                f"legal: {sorted(TRANSITIONS[current])}")
        entry = {"status": status, "updated_at": _utcnow_iso()}
        if note is not None:
            entry["note"] = note
        doc["tasks"][task_id] = entry
        self._write(doc)
        return entry

    # -- governor pause/resume marker (§5.1: "clean pause — resume marker to the
    # status index"). One marker at a time; the next firing reads it and clears it.

    def set_resume_marker(self, marker: dict) -> None:
        if not isinstance(marker, dict):
            raise LedgerError("resume marker must be an object")
        doc = self.read()
        doc["resume_marker"] = dict(marker, set_at=_utcnow_iso())
        self._write(doc)

    def get_resume_marker(self) -> dict | None:
        return self.read().get("resume_marker")

    def clear_resume_marker(self) -> None:
        doc = self.read()
        if doc.pop("resume_marker", None) is not None:
            self._write(doc)


def runnable(ledger: Ledger, index: StatusIndex) -> list:
    """Task ids that are not_started with every hard dep done — the §6.1 candidate set
    ("every not-started task whose hard deps are complete, any phase"). Ordering,
    priorities, and soft-edge safety are B2's job."""
    statuses = {tid: index.status_of(tid) for tid in ledger.tasks}
    return [tid for tid, entry in ledger.tasks.items()
            if statuses[tid] == "not_started"
            and all(statuses[dep] == "done" for dep in entry["deps"])]


def summary(ledger: Ledger, index: StatusIndex) -> dict:
    """The resume view: counts per status, in-flight/parked ids, runnable set, marker."""
    statuses = {tid: index.status_of(tid) for tid in ledger.tasks}
    counts = {status: 0 for status in STATUSES}
    for status in statuses.values():
        counts[status] += 1
    return {
        "counts": counts,
        "in_progress": sorted(t for t, s in statuses.items() if s == "in_progress"),
        "parked": sorted(t for t, s in statuses.items() if s == "parked"),
        "runnable": sorted(runnable(ledger, index)),
        "resume_marker": index.get_resume_marker(),
        "complete": counts["done"] == len(ledger.tasks),
    }
