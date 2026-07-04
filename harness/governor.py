#!/usr/bin/env python3
"""Budget governor — window occupancy via a source ladder, observe-only thresholds.

Design §5.1. A small deterministic script the loop consults *between* tasks ("don't
start what you can't finish"). Occupancy is read best-source-first:

1. ``statusline`` — the statusline stdin JSON's ``rate_limits`` block
   (server-side utilization, zero extra tokens; the primary rung).
2. ``oauth-usage`` — the parsed response of the undocumented OAuth usage endpoint
   (unstable internal fallback for headless firings). This module only *parses* the
   document; the authenticated fetch is a thin operator-side wrapper (see plan).
3. ``estimate`` — per-role token sums from the run-log over trailing windows.
   Systematically optimistic (it cannot see the operator's own interactive drain on the
   shared pool) and converts to occupancy only when calibrated ceilings are supplied —
   ceilings are never hard-coded (design §10.3).

Thresholds (degrade 0.8 / pause 0.95 of a window) ship **observe-only** (§11 Stage 0):
``decide`` always reports the crossing; ``enforced`` is True only in ``enforce`` mode,
which is a Stage-1 flip gated on telemetry.

Library code does no network I/O. CLI:

    python3 -m harness.governor --statusline-json - < statusline.json
    python3 -m harness.governor --runlog run-log.jsonl --ceilings '{"five_hour": 2e8}'
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys

from . import runlog as _runlog

WINDOWS = ("five_hour", "seven_day", "seven_day_sonnet")
WINDOW_SPANS = {
    "five_hour": _dt.timedelta(hours=5),
    "seven_day": _dt.timedelta(days=7),
    "seven_day_sonnet": _dt.timedelta(days=7),
}
DEFAULT_DEGRADE = 0.8
DEFAULT_PAUSE = 0.95
GOVERNOR_EVENT = "governor_decision"


class GovernorError(ValueError):
    """A source document was unusable. Callers fall through to the next rung."""


class Occupancy:
    """Normalized occupancy reading: fractions (0..1+) per window."""

    def __init__(self, source: str, windows: dict, resets_at: dict | None = None,
                 optimistic: bool = False, tokens: dict | None = None):
        self.source = source
        self.windows = windows            # window name -> fraction, may be empty
        self.resets_at = resets_at or {}  # window name -> unix epoch
        self.optimistic = optimistic
        self.tokens = tokens or {}        # window name -> raw token sum (estimate rung)

    def to_dict(self) -> dict:
        return {"source": self.source, "windows": self.windows,
                "resets_at": self.resets_at, "optimistic": self.optimistic,
                "tokens": self.tokens}


def _fraction(entry: dict) -> float | None:
    """Pull a utilization fraction out of one window entry, accepting the field
    spellings seen in the wild (used_percentage, utilization) — defensive on purpose,
    both surfaces are volatile (§10.3)."""
    for key in ("used_percentage", "utilization"):
        value = entry.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value < 0:
            raise GovernorError(f"negative utilization {value!r}")
        return value / 100.0
    return None


def _parse_windows(container: dict, source: str) -> Occupancy:
    windows, resets = {}, {}
    for name in WINDOWS:
        entry = container.get(name)
        if not isinstance(entry, dict):
            continue
        frac = _fraction(entry)
        if frac is not None:
            windows[name] = frac
        if isinstance(entry.get("resets_at"), (int, float)) \
                and not isinstance(entry.get("resets_at"), bool):
            resets[name] = entry["resets_at"]
    if not windows:
        raise GovernorError(f"{source}: no usable window utilization found")
    return Occupancy(source=source, windows=windows, resets_at=resets)


def read_statusline(doc: dict) -> Occupancy:
    """Parse the statusline stdin JSON's rate_limits block."""
    if not isinstance(doc, dict):
        raise GovernorError("statusline: document is not an object")
    rate_limits = doc.get("rate_limits")
    if not isinstance(rate_limits, dict):
        raise GovernorError("statusline: missing rate_limits block")
    return _parse_windows(rate_limits, "statusline")


def read_oauth_usage(doc: dict) -> Occupancy:
    """Parse an OAuth-usage endpoint response document (already fetched)."""
    if not isinstance(doc, dict):
        raise GovernorError("oauth-usage: document is not an object")
    container = doc.get("rate_limits") if isinstance(doc.get("rate_limits"), dict) else doc
    return _parse_windows(container, "oauth-usage")


def estimate_from_runlog(records, now: _dt.datetime, ceilings: dict | None = None,
                         cache_read_weight: float = 1.0,
                         five_hour_anchor: _dt.datetime | None = None) -> Occupancy:
    """Last-resort rung: trailing-window token sums from the run-log.

    ``five_hour_anchor`` (the window's first-message time, if the operator knows it)
    replaces the trailing 5h approximation. Occupancy fractions are produced only for
    windows with a calibrated ceiling in ``ceilings`` (tokens). Always flagged
    optimistic — the log can't see interactive drain on the shared pool.
    """
    tokens, windows = {}, {}
    for name in WINDOWS:
        if name == "five_hour" and five_hour_anchor is not None:
            start = five_hour_anchor
        else:
            start = now - WINDOW_SPANS[name]
        in_win = _runlog.in_window(records, start, now)
        if name == "seven_day_sonnet":
            in_win = [r for r in in_win if r.get("tier") == "standard"]
        tokens[name] = _runlog.sum_tokens(in_win, cache_read_weight=cache_read_weight)
        ceiling = (ceilings or {}).get(name)
        if isinstance(ceiling, (int, float)) and not isinstance(ceiling, bool) \
                and ceiling > 0:
            windows[name] = tokens[name] / ceiling
    return Occupancy(source="estimate", windows=windows, optimistic=True, tokens=tokens)


def resolve(statusline_doc: dict | None = None, oauth_doc: dict | None = None,
            runlog_records=None, now: _dt.datetime | None = None,
            ceilings: dict | None = None, cache_read_weight: float = 1.0) -> Occupancy:
    """Walk the source ladder best-source-first; a bad rung falls through, never raises
    unless every supplied rung is unusable."""
    failures = []
    if statusline_doc is not None:
        try:
            return read_statusline(statusline_doc)
        except GovernorError as exc:
            failures.append(str(exc))
    if oauth_doc is not None:
        try:
            return read_oauth_usage(oauth_doc)
        except GovernorError as exc:
            failures.append(str(exc))
    if runlog_records is not None:
        if now is None:
            now = _dt.datetime.now(_dt.timezone.utc)
        return estimate_from_runlog(runlog_records, now, ceilings=ceilings,
                                    cache_read_weight=cache_read_weight)
    raise GovernorError("no usable occupancy source: " + ("; ".join(failures) or
                        "no sources supplied"))


def decide(occupancy: Occupancy, degrade: float = DEFAULT_DEGRADE,
           pause: float = DEFAULT_PAUSE, mode: str = "observe") -> dict:
    """Threshold decision. status: ok | degrade | pause | unknown.

    ``unknown`` means no window produced a fraction (estimate rung without ceilings) —
    the caller must treat that as "cannot admit heavy work", not as "ok".
    ``enforced`` is False in observe mode regardless of status (§11 Stage 0).
    """
    if mode not in ("observe", "enforce"):
        raise GovernorError(f"mode must be observe|enforce, got {mode!r}")
    if not 0 < degrade < pause:
        raise GovernorError(f"need 0 < degrade({degrade}) < pause({pause})")

    if occupancy.windows:
        binding = max(occupancy.windows, key=lambda w: occupancy.windows[w])
        worst = occupancy.windows[binding]
        if worst >= pause:
            status = "pause"
        elif worst >= degrade:
            status = "degrade"
        else:
            status = "ok"
    else:
        binding, worst, status = None, None, "unknown"

    return {
        "event": GOVERNOR_EVENT,
        "status": status,
        "binding_window": binding,
        "occupancy": worst,
        "windows": occupancy.windows,
        "source": occupancy.source,
        "optimistic": occupancy.optimistic,
        "thresholds": {"degrade": degrade, "pause": pause},
        "mode": mode,
        "enforced": mode == "enforce" and status not in ("ok",),
    }


def log_decision(log_path: str, decision: dict) -> dict:
    """Append the decision to a run-log (the §5.1 'log the crossing' requirement)."""
    return _runlog.RunLog(log_path).append(dict(decision))


def summarize_decisions(decisions) -> dict:
    """Roll up governor decisions with the **sticky estimated flag** (§5.1,
    2026-07-04 amendment): if *any* reading in the set came from the optimistic
    estimate rung, every derived total is flagged ``estimated`` — measured and
    guessed numbers are never silently blended."""
    decisions = [d for d in decisions if d.get("event") == GOVERNOR_EVENT]
    estimated = any(d.get("optimistic") for d in decisions)
    worst = {}
    for d in decisions:
        for window, frac in (d.get("windows") or {}).items():
            if isinstance(frac, (int, float)) and not isinstance(frac, bool):
                worst[window] = max(worst.get(window, 0.0), frac)
    statuses = [d.get("status") for d in decisions]
    return {
        "readings": len(decisions),
        "estimated": estimated,
        "sources": sorted({d.get("source") for d in decisions if d.get("source")}),
        "worst_windows": worst,
        "any_degrade": any(s in ("degrade", "pause") for s in statuses),
        "any_pause": "pause" in statuses,
        "any_unknown": "unknown" in statuses,
    }


def fmt_estimated(value, estimated: bool) -> str:
    """Render a number honestly: ``~`` prefix when any input was estimated.
    Digest/report code must use this rather than printing raw totals."""
    if isinstance(value, float) and value == int(value):
        value = int(value)
    return f"~{value}" if estimated else f"{value}"


def _load_json_arg(value: str):
    if value == "-":
        return json.load(sys.stdin)
    if value.lstrip().startswith("{"):
        return json.loads(value)
    with open(value) as fh:
        return json.load(fh)


def _cli(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--statusline-json", help="statusline stdin JSON: path, '-', or inline")
    p.add_argument("--oauth-json", help="OAuth usage response JSON: path, '-', or inline")
    p.add_argument("--runlog", help="JSONL run-log path for the estimate rung")
    p.add_argument("--ceilings", help="inline JSON {window: ceiling_tokens} — calibrated, "
                   "never guessed")
    p.add_argument("--cache-read-weight", type=float, default=1.0)
    p.add_argument("--degrade", type=float, default=DEFAULT_DEGRADE)
    p.add_argument("--pause", type=float, default=DEFAULT_PAUSE)
    p.add_argument("--mode", choices=["observe", "enforce"], default="observe")
    p.add_argument("--log", help="append the decision to this JSONL file")
    args = p.parse_args(argv)

    statusline_doc = _load_json_arg(args.statusline_json) if args.statusline_json else None
    oauth_doc = _load_json_arg(args.oauth_json) if args.oauth_json else None
    records = None
    if args.runlog:
        records, errors = _runlog.RunLog(args.runlog).read()
        for lineno, message in errors:
            print(f"warning: {args.runlog}:{lineno}: {message}", file=sys.stderr)

    occ = resolve(statusline_doc=statusline_doc, oauth_doc=oauth_doc,
                  runlog_records=records,
                  ceilings=json.loads(args.ceilings) if args.ceilings else None,
                  cache_read_weight=args.cache_read_weight)
    decision = decide(occ, degrade=args.degrade, pause=args.pause, mode=args.mode)
    if args.log:
        log_decision(args.log, decision)
    print(json.dumps(decision, indent=2))
    return 0 if decision["status"] in ("ok",) else 1


if __name__ == "__main__":
    sys.exit(_cli())
