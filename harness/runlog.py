#!/usr/bin/env python3
"""Canonical run-log: the single telemetry stream every harness component reads.

Design §5.1 (governor estimate rung), §5.3 (per-(tier, effort) cost segmentation), §8
(controller inputs). One JSONL file, one record per completed task attempt (or other event).
Consumers already in-repo:

- tools/budget-governor/populate_estimates.py reads ``{"profile", "total_tokens"}`` — a
  subset of this schema, so the run-log feeds it directly.
- tools/budget-governor/validate_predictor.py reads
  ``{"predicted_bucket", "actual_total_tokens", "escaped"}`` — use
  :func:`to_predictor_records` to project task records into that shape.

Validation is strict on append (fail loud at the source) and tolerant on read (a corrupt
line must never kill a resume — design §3.4, disk is the memory).
"""

from __future__ import annotations

import datetime as _dt
import json
import os

PROFILES = ("routine", "elevated", "high", "critical")
TIERS = ("cheap", "standard", "capable", "max")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
OUTCOMES = ("pass", "fail", "parked", "aborted")
BUCKETS = ("XS", "S", "M", "L", "XL")
ROLES = ("implementer", "validator", "test_author", "orchestrator", "other")

#: Event type for a completed task attempt — the record shape most consumers care about.
TASK_COMPLETE = "task_complete"
FALSE_FAIL = "false_fail"  # H4: per-lens verifier-precision telemetry (§8)
# I15 (P2-12): routing-preserving worker lifecycle events — a spawn/abort/park
# record survives mid-task death by contract, not by orchestrator invention
TASK_SPAWN = "task_spawn"
TASK_ABORTED = "task_aborted"
TASK_PARKED = "task_parked"
WORKER_EVENTS = (TASK_SPAWN, TASK_ABORTED, TASK_PARKED)

_TOKEN_COMPONENTS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
)


class RunLogError(ValueError):
    """A record failed schema validation on append."""


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> _dt.datetime:
    """Parse an ISO-8601 timestamp; 'Z' suffix and explicit offsets both accepted."""
    if not isinstance(value, str):
        raise RunLogError(f"ts must be an ISO-8601 string, got {type(value).__name__}")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise RunLogError(f"unparseable ts {value!r}: {exc}") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def _require_enum(rec: dict, field: str, allowed: tuple, required: bool = False) -> None:
    value = rec.get(field)
    if value is None:
        if required:
            raise RunLogError(f"missing required field {field!r}")
        return
    if value not in allowed:
        raise RunLogError(f"{field}={value!r} not in {allowed}")


def _require_nonneg_int(rec: dict, field: str, required: bool = False) -> None:
    value = rec.get(field)
    if value is None:
        if required:
            raise RunLogError(f"missing required field {field!r}")
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RunLogError(f"{field}={value!r} must be a non-negative integer")


def validate_record(rec: dict) -> dict:
    """Validate and normalize one record. Returns a copy; raises RunLogError on failure.

    Fills ``ts`` (now, UTC) and ``event`` (task_complete) when absent. task_complete
    records require ``profile`` and ``total_tokens``; every other event type only needs a
    parseable ``ts`` — the schema stays open for governor decisions, escapes, canaries.
    """
    if not isinstance(rec, dict):
        raise RunLogError(f"record must be a dict, got {type(rec).__name__}")
    out = dict(rec)
    out.setdefault("ts", _utcnow_iso())
    parse_ts(out["ts"])
    out.setdefault("event", TASK_COMPLETE)
    if not isinstance(out["event"], str) or not out["event"]:
        raise RunLogError(f"event must be a non-empty string, got {out['event']!r}")

    if out["event"] == TASK_COMPLETE:
        _require_enum(out, "profile", PROFILES, required=True)
        _require_nonneg_int(out, "total_tokens", required=True)
        _require_enum(out, "tier", TIERS)
        _require_enum(out, "effort", EFFORTS)
        if "model" in out and (not isinstance(out["model"], str)
                               or not out["model"].strip()):
            # I10: the CONCRETE model id (§5.3/§8 segment by tier+model+effort
            # — tiers.json is config, so tier alone blends models across
            # remappings); comes from spawncheck's resolved params, never a
            # worker self-report
            raise RunLogError(f"model={out['model']!r} must be a non-empty "
                              f"string when present")
        _require_enum(out, "outcome", OUTCOMES)
        _require_enum(out, "predicted_bucket", BUCKETS)
        _require_enum(out, "role", ROLES)
        for field in _TOKEN_COMPONENTS:
            _require_nonneg_int(out, field)
        if "escaped" in out and not isinstance(out["escaped"], bool):
            raise RunLogError(f"escaped={out['escaped']!r} must be a boolean")
        if "wall_secs" in out:
            ws = out["wall_secs"]
            if isinstance(ws, bool) or not isinstance(ws, (int, float)) or ws < 0:
                raise RunLogError(f"wall_secs={ws!r} must be a non-negative number")
    elif out["event"] == FALSE_FAIL:
        for field in ("reproduced", "unreproduced", "no_repro"):
            _require_nonneg_int(out, field)
    elif out["event"] in WORKER_EVENTS:
        if not isinstance(out.get("task_id"), str) or not out["task_id"]:
            raise RunLogError(f"{out['event']}: needs a task_id")
        _require_enum(out, "role", ROLES, required=True)
        _require_enum(out, "tier", TIERS)
        _require_enum(out, "effort", EFFORTS)
        _require_nonneg_int(out, "total_tokens")
        if "model" in out and (not isinstance(out["model"], str)
                               or not out["model"].strip()):
            raise RunLogError(f"model={out['model']!r} must be a non-empty "
                              f"string when present")
    if "attempt" in out:
        _require_nonneg_int(out, "attempt")
        if out["attempt"] < 1:
            raise RunLogError(f"attempt={out['attempt']!r} must be >= 1")
    return out


def worker_event(event: str, task_id: str, role: str, resolved: dict,
                 attempt: int | None = None, **extra) -> dict:
    """I15 — build a validated routing-preserving record straight from
    spawncheck's resolved params. The loop appends this at spawn time
    (write-ahead), and again as abort/park if the worker never returns —
    so the routing choice is never lost to a mid-task death."""
    if event not in WORKER_EVENTS:
        raise RunLogError(f"worker_event: {event!r} not in {WORKER_EVENTS}")
    rec = {"event": event, "task_id": task_id, "role": role,
           "tier": resolved.get("tier"), "model": resolved.get("model"),
           "effort": resolved.get("effort")}
    rec = {k: v for k, v in rec.items() if v is not None}
    if attempt is not None:
        rec["attempt"] = attempt
    rec.update(extra)
    return validate_record(rec)


class RunLog:
    """Append-validated, read-tolerant JSONL run-log."""

    def __init__(self, path: str):
        self.path = path

    def append(self, rec: dict) -> dict:
        normalized = validate_record(rec)
        line = json.dumps(normalized, sort_keys=True)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(line + "\n")
        return normalized

    def read(self):
        """Return (records, errors). Missing file → ([], []). Bad lines are skipped and
        reported as (line_number, message) — never raised."""
        records, errors = [], []
        try:
            fh = open(self.path)
        except FileNotFoundError:
            return records, errors
        with fh:
            for lineno, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    records.append(validate_record(rec))
                except (json.JSONDecodeError, RunLogError) as exc:
                    errors.append((lineno, str(exc)))
        return records, errors


def in_window(records, start: _dt.datetime, end: _dt.datetime | None = None):
    """Records whose ts falls in [start, end] (end defaults to +infinity)."""
    out = []
    for rec in records:
        ts = parse_ts(rec["ts"])
        if ts >= start and (end is None or ts <= end):
            out.append(rec)
    return out


def sum_tokens(records, cache_read_weight: float = 1.0) -> float:
    """Weighted token total across records.

    When a record carries component counts, cache reads are weighted by
    ``cache_read_weight`` (default 1.0 — the conservative branch of design §10.2's
    contested question; lower it only when the cache-weight experiment says so).
    Records with only ``total_tokens`` are counted at face value.
    """
    total = 0.0
    for rec in records:
        components = [rec.get(f) for f in _TOKEN_COMPONENTS]
        if any(c is not None for c in components):
            inp, outp, cache_w, cache_r = (c or 0 for c in components)
            total += inp + outp + cache_w + cache_read_weight * cache_r
        else:
            total += rec.get("total_tokens") or 0
    return total


def to_predictor_records(records):
    """Project task records into validate_predictor.py's expected shape.

    Only records carrying a predicted_bucket qualify (the predictor only gets scored on
    tasks it actually predicted).
    """
    out = []
    for rec in records:
        if rec.get("event", TASK_COMPLETE) != TASK_COMPLETE \
                or rec.get("predicted_bucket") is None:
            continue
        out.append({
            "predicted_bucket": rec["predicted_bucket"],
            "actual_total_tokens": rec["total_tokens"],
            "escaped": rec.get("escaped", False),
        })
    return out
