#!/usr/bin/env python3
"""Task ledger + event-log state — the disk state any context resumes from.

Design §3 principle 4 ("disk is the memory", 2026-07-04 amendments) and §9. Four
mechanics keep the resumable state trustworthy under crashes and concurrency
(research: unattended-operation-prior-art.md §1):

- **Append-only event log.** Status transitions and markers are *events*, appended
  durably (fsync) — never a mutated snapshot. The log is the write-ahead structure:
  an event is on disk before any consumer marker advances past it.
- **Derived reconciliation view.** Current state is *computed*, never stored as
  truth. Authoritative inputs are gate/run artifacts supplied by the caller; the
  event log is a *claim*. "Never infer current state from a tail of the log."
- **Write-ahead cursor.** Consumers record the last event they processed in a
  cursor file; the cursor can never advance past what is durably logged and never
  rewinds. Recovery after any crash = drain ``pending()``.
- **Generation-stamped mutations.** Every append can carry ``expected_generation``;
  a stale expectation fails loudly (:class:`StaleGenerationError`) instead of
  silently clobbering — load-bearing the moment concurrency exceeds 1 (§6.2).

The **Ledger** (task definitions: id, phase, risk profile, hard ``deps``, soft
``may_be_invalidated_by`` edges) is authored at planning time and read-only here.
Cycle detection and scheduling policy are increment B2; :func:`runnable` gives only
the dependency-correct candidate set a resume view needs, over *reconciled* state.

Digest output follows the §5.4 format policy: aggregate header first (turn economy,
§6.1), flattened Markdown table, definitive empty states.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile

from .runlog import PROFILES

STATUSES = ("not_started", "in_progress", "parked", "done", "failed")

#: Reconciliation may also report "unknown" — a task whose event-log claim is
#: contradicted by artifacts (e.g. in_progress with no live run). Never persisted.
UNKNOWN = "unknown"

#: Legal transitions. "done" is terminal by design — reopening a validated task is an
#: operator decision made by editing the file, never something the loop does silently.
TRANSITIONS = {
    "not_started": {"in_progress"},
    "in_progress": {"done", "failed", "parked"},
    "parked": {"in_progress", "failed"},
    "failed": {"in_progress"},
    "done": set(),
}

EVENT_KINDS = ("status", "marker_set", "marker_clear")


class LedgerError(ValueError):
    pass


class StaleGenerationError(LedgerError):
    """An append carried an ``expected_generation`` that no longer matches: the
    caller acted on a stale read. Fail loudly; the caller re-reads and re-decides."""


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


class EventLog:
    """Append-only JSONL event log with fsync'd writes and a consumer cursor.

    Crash model: an acknowledged append is durable (fsync before return). A crash
    *mid-append* leaves a torn final line — that event was never acknowledged, so
    reads ignore it and the next append truncates it away. Corruption anywhere
    *before* the tail is outside the crash model and raises loudly rather than
    silently resetting state.
    """

    def __init__(self, path: str):
        self.path = path
        self.cursor_path = path + ".cursor"

    # -- raw read ---------------------------------------------------------------

    def _read_raw(self) -> tuple[list, int]:
        """Return (events, clean_byte_length). Tolerates a torn tail; raises on
        interior corruption or a broken seq chain."""
        try:
            with open(self.path, "rb") as fh:
                data = fh.read()
        except FileNotFoundError:
            return [], 0
        events, offset = [], 0
        while offset < len(data):
            nl = data.find(b"\n", offset)
            if nl == -1:  # no newline: torn tail — unacknowledged, ignore
                break
            line = data[offset:nl]
            if line.strip():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerError(
                        f"event log {self.path}: corrupt event at byte {offset}: "
                        f"{exc}") from None
                if not isinstance(event, dict):
                    raise LedgerError(
                        f"event log {self.path}: event at byte {offset} is not an "
                        f"object")
                events.append(event)
            offset = nl + 1
        for i, event in enumerate(events, start=1):
            if event.get("seq") != i:
                raise LedgerError(
                    f"event log {self.path}: seq chain broken at position {i} "
                    f"(got {event.get('seq')!r}) — refusing to guess at state")
            if event.get("kind") not in EVENT_KINDS:
                raise LedgerError(
                    f"event log {self.path}: event {i} has unknown kind "
                    f"{event.get('kind')!r}")
        return events, offset

    def read(self) -> list:
        return self._read_raw()[0]

    def generation(self) -> int:
        """Monotonic generation = seq of the last durable event."""
        return len(self.read())

    # -- append (the write-ahead half) -------------------------------------------

    def _append(self, kind: str, payload: dict,
                expected_generation: int | None = None) -> dict:
        events, clean_len = self._read_raw()
        generation = len(events)
        if expected_generation is not None and expected_generation != generation:
            raise StaleGenerationError(
                f"expected generation {expected_generation} but log is at "
                f"{generation} — re-read before mutating")
        event = dict(payload, seq=generation + 1, ts=_utcnow_iso(), kind=kind)
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        line = json.dumps(event, sort_keys=True) + "\n"
        # "a" would append *after* a torn tail and corrupt the log; open r+/x and
        # write at the clean offset so the unacknowledged fragment is overwritten.
        mode = "r+b" if os.path.exists(self.path) else "xb"
        with open(self.path, mode) as fh:
            fh.seek(clean_len)
            fh.write(line.encode())
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
        return event

    def record_status(self, task_id: str, status: str, note: str | None = None,
                      ledger: Ledger | None = None,
                      expected_generation: int | None = None) -> dict:
        """Append a status-transition event. With a ledger supplied, unknown task ids
        are rejected — a typo'd id must not create a phantom task."""
        if status not in STATUSES:
            raise LedgerError(f"unknown status {status!r}; known: {STATUSES}")
        if ledger is not None and task_id not in ledger:
            raise LedgerError(f"unknown task id {task_id!r} (not in ledger)")
        if not isinstance(task_id, str) or not task_id:
            raise LedgerError("task_id must be a non-empty string")
        current = project(self.read())["tasks"].get(task_id, {}).get(
            "status", "not_started")
        if status != current and status not in TRANSITIONS[current]:
            raise LedgerError(
                f"illegal transition {current!r} -> {status!r} for task {task_id!r}; "
                f"legal: {sorted(TRANSITIONS[current])}")
        payload = {"task_id": task_id, "status": status}
        if note is not None:
            payload["note"] = note
        return self._append("status", payload, expected_generation)

    # -- governor pause/resume marker (§5.1) --------------------------------------

    def set_resume_marker(self, marker: dict,
                          expected_generation: int | None = None) -> dict:
        if not isinstance(marker, dict):
            raise LedgerError("resume marker must be an object")
        return self._append("marker_set", {"marker": dict(marker)},
                            expected_generation)

    def clear_resume_marker(self, expected_generation: int | None = None) -> dict:
        return self._append("marker_clear", {}, expected_generation)

    def get_resume_marker(self) -> dict | None:
        return project(self.read())["resume_marker"]

    # -- consumer cursor (the write-ahead ordering guarantee) ----------------------

    def processed_seq(self) -> int:
        try:
            with open(self.cursor_path) as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            return 0
        except json.JSONDecodeError as exc:
            raise LedgerError(
                f"cursor {self.cursor_path} is corrupt: {exc}") from None
        seq = doc.get("processed_seq")
        if not isinstance(seq, int) or seq < 0:
            raise LedgerError(f"cursor {self.cursor_path}: bad processed_seq {seq!r}")
        return seq

    def advance_cursor(self, seq: int) -> None:
        """Mark events up to ``seq`` processed. Refuses to advance past what is
        durably logged (write-ahead: nothing is 'processed' before it exists on
        disk) and refuses to rewind (recovery drains forward, never re-suppresses)."""
        if not isinstance(seq, int):
            raise LedgerError(f"cursor seq must be an int, got {seq!r}")
        generation = self.generation()
        current = self.processed_seq()
        if seq > generation:
            raise LedgerError(
                f"cannot advance cursor to {seq}: log generation is {generation} "
                f"(an event must be durable before it can be processed)")
        if seq < current:
            raise LedgerError(
                f"cannot rewind cursor from {current} to {seq}")
        parent = os.path.dirname(self.cursor_path) or "."
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=parent, prefix=".cursor-")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump({"processed_seq": seq, "advanced_at": _utcnow_iso()}, fh)
                fh.write("\n")
            os.replace(tmp, self.cursor_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def pending(self) -> list:
        """Drain view: durable events the cursor has not passed. Crash recovery is
        exactly 'process pending(), advancing the cursor as you go'."""
        processed = self.processed_seq()
        return [e for e in self.read() if e["seq"] > processed]


def project(events: list) -> dict:
    """Fold the event log into its claimed state: per-task status + resume marker.
    This is the *claim* half — reconciliation (below) is what may be trusted."""
    tasks: dict = {}
    marker = None
    for event in events:
        if event["kind"] == "status":
            entry = {"status": event["status"], "updated_at": event["ts"]}
            if "note" in event:
                entry["note"] = event["note"]
            tasks[event["task_id"]] = entry
        elif event["kind"] == "marker_set":
            marker = dict(event["marker"], set_at=event["ts"])
        elif event["kind"] == "marker_clear":
            marker = None
    return {"tasks": tasks, "resume_marker": marker}


def reconcile(ledger: Ledger, log: EventLog, artifacts: dict | None = None) -> dict:
    """Derive current state. The event log is a claim; ``artifacts`` — facts the
    caller established from gate outputs, run markers, and git — are authoritative.

    ``artifacts`` maps task_id → {"gate": "pass"|"fail", "run_active": bool}; both
    keys optional. Precedence per task: gate verdict > run liveness > event claim.
    Contradictions are surfaced in ``discrepancies`` (loud), never healed silently —
    appending a correcting event is the caller's decision.
    """
    events = log.read()
    proj = project(events)
    claims_only = artifacts is None
    artifacts = artifacts or {}
    tasks, discrepancies = {}, []
    for task_id in ledger.tasks:
        claim = proj["tasks"].get(task_id, {}).get("status", "not_started")
        note = proj["tasks"].get(task_id, {}).get("note")
        art = artifacts.get(task_id, {})
        status, source = claim, "events"
        gate = art.get("gate")
        run_active = art.get("run_active")
        if gate == "pass":
            status, source = "done", "gate"
            if claim != "done":
                discrepancies.append(
                    f"{task_id}: events claim {claim!r} but merge-gate artifact "
                    f"says pass")
        elif gate == "fail" and claim == "done":
            status, source = "failed", "gate"
            discrepancies.append(
                f"{task_id}: events claim 'done' but merge-gate artifact says fail")
        elif run_active is False and claim == "in_progress":
            status, source = UNKNOWN, "reconciliation"
            discrepancies.append(
                f"{task_id}: events claim 'in_progress' but no live run exists")
        elif run_active is True and claim not in ("in_progress", "done"):
            status, source = "in_progress", "run"
            discrepancies.append(
                f"{task_id}: events claim {claim!r} but a live run exists")
        entry = {"status": status, "source": source}
        if note is not None:
            entry["note"] = note
        tasks[task_id] = entry
    return {
        "tasks": tasks,
        "discrepancies": discrepancies,
        "claims_only": claims_only,
        "generation": len(events),
        "resume_marker": proj["resume_marker"],
    }


def runnable(ledger: Ledger, log: EventLog, artifacts: dict | None = None) -> list:
    """Task ids that are not_started with every hard dep reconciled done — the §6.1
    candidate set, computed over *reconciled* state (an 'unknown' dep blocks).
    Ordering, priorities, and soft-edge safety are B2's job."""
    state = reconcile(ledger, log, artifacts)["tasks"]
    return [tid for tid, entry in ledger.tasks.items()
            if state[tid]["status"] == "not_started"
            and all(state[dep]["status"] == "done" for dep in entry["deps"])]


def summary(ledger: Ledger, log: EventLog, artifacts: dict | None = None) -> dict:
    """The resume view, over reconciled state: counts, in-flight/parked/unknown ids,
    runnable set, marker, discrepancies, generation."""
    view = reconcile(ledger, log, artifacts)
    state = view["tasks"]
    counts = {status: 0 for status in STATUSES + (UNKNOWN,)}
    for entry in state.values():
        counts[entry["status"]] += 1
    return {
        "counts": counts,
        "in_progress": sorted(t for t, e in state.items()
                              if e["status"] == "in_progress"),
        "parked": sorted(t for t, e in state.items() if e["status"] == "parked"),
        "unknown": sorted(t for t, e in state.items() if e["status"] == UNKNOWN),
        "runnable": sorted(t for t, e in state.items()
                           if e["status"] == "not_started"
                           and all(state[d]["status"] == "done"
                                   for d in ledger.tasks[t]["deps"])),
        "resume_marker": view["resume_marker"],
        "complete": counts["done"] == len(ledger.tasks),
        "discrepancies": view["discrepancies"],
        "claims_only": view["claims_only"],
        "generation": view["generation"],
    }


def digest(ledger: Ledger, log: EventLog, artifacts: dict | None = None) -> str:
    """Model-facing digest per the §5.4 format policy: aggregate header first
    (§6.1 turn economy), definitive empty states, flattened Markdown table."""
    view = summary(ledger, log, artifacts)
    c, total = view["counts"], len(ledger.tasks)
    header = (f"tasks: {c['done']} of {total} done · {c['in_progress']} in-flight · "
              f"{c['parked']} parked · {c['failed']} failed · "
              f"{c[UNKNOWN]} unknown")
    if view["runnable"]:
        run_line = f"runnable: {len(view['runnable'])} — " + ", ".join(view["runnable"])
    else:
        blocked = c["not_started"] - len(view["runnable"])
        reasons = []
        if c["in_progress"]:
            reasons.append(f"{c['in_progress']} in-flight")
        if blocked:
            reasons.append(f"{blocked} blocked on deps")
        if c["parked"]:
            reasons.append(f"{c['parked']} parked")
        if c[UNKNOWN]:
            reasons.append(f"{c[UNKNOWN]} unknown")
        detail = f" ({', '.join(reasons)})" if reasons else " (all tasks done)"
        run_line = f"runnable: 0{detail}"
    flags = []
    if view["claims_only"]:
        flags.append("view: claims-only (no gate/run artifacts supplied)")
    if view["discrepancies"]:
        flags.append(f"discrepancies: {len(view['discrepancies'])} — "
                     + " | ".join(view["discrepancies"]))
    if view["resume_marker"] is not None:
        flags.append(f"resume-marker: {view['resume_marker'].get('reason', 'set')}")
    state = reconcile(ledger, log, artifacts)["tasks"]
    rows = ["| id | phase | profile | status | deps | note |",
            "|---|---|---|---|---|---|"]
    for tid in sorted(ledger.tasks, key=lambda t: (ledger.tasks[t]["phase"], t)):
        task = ledger.tasks[tid]
        note = state[tid].get("note", "")
        if len(note) > 60:
            note = note[:57] + "..."
        rows.append(f"| {tid} | {task['phase']} | {task['profile']} | "
                    f"{state[tid]['status']} | "
                    f"{';'.join(task['deps']) or '—'} | {note} |")
    lines = [header, run_line] + flags + ["", *rows]
    return "\n".join(lines)
