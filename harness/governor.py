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
import os
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

# H8 (§5.1 amendment): live readings carry their age; stale ones fall through
DEFAULT_STALE_AFTER_S = 600.0
DEFAULT_AGE_MARGIN_SCALE = 0.1   # thresholds tighten linearly with data age
CONSERVATIVE_DELTA = 0.15        # preflight conservative-mode threshold cut


class GovernorError(ValueError):
    """A source document was unusable. Callers fall through to the next rung."""


class Occupancy:
    """Normalized occupancy reading: fractions (0..1+) per window."""

    def __init__(self, source: str, windows: dict, resets_at: dict | None = None,
                 optimistic: bool = False, tokens: dict | None = None,
                 age_s: float | None = None,
                 stale_after_s: float | None = None):
        self.source = source
        self.windows = windows            # window name -> fraction, may be empty
        self.resets_at = resets_at or {}  # window name -> unix epoch
        self.optimistic = optimistic
        self.tokens = tokens or {}        # window name -> raw token sum (estimate rung)
        self.age_s = age_s                # H8: reading age; None = age unknown
        self.stale_after_s = stale_after_s

    def to_dict(self) -> dict:
        return {"source": self.source, "windows": self.windows,
                "resets_at": self.resets_at, "optimistic": self.optimistic,
                "tokens": self.tokens, "age_s": self.age_s}


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


def _age_check(name: str, read_at: float | None, now_ts: float | None,
               stale_after_s: float) -> tuple[float | None, str | None]:
    """H8: (age_s, failure). Age is computable only when both timestamps are
    supplied; a reading older than ``stale_after_s`` is a rung failure — never
    consumed as live."""
    if read_at is None or now_ts is None:
        return None, None
    age = now_ts - read_at
    if age < 0:
        return None, f"{name}: reading timestamped in the future (clock skew?)"
    if age > stale_after_s:
        return age, (f"{name}: reading {age:.0f}s old exceeds the "
                     f"{stale_after_s:.0f}s staleness ceiling — stale data is "
                     f"not live data")
    return age, None


def resolve(statusline_doc: dict | None = None, oauth_doc: dict | None = None,
            runlog_records=None, now: _dt.datetime | None = None,
            ceilings: dict | None = None, cache_read_weight: float = 1.0,
            statusline_read_at: float | None = None,
            oauth_read_at: float | None = None,
            now_ts: float | None = None,
            stale_after_s: float = DEFAULT_STALE_AFTER_S) -> Occupancy:
    """Walk the source ladder best-source-first; a bad — or stale (H8) — rung
    falls through, never raises unless every supplied rung is unusable.
    ``*_read_at``/``now_ts`` are epoch seconds (e.g. the dump file's mtime);
    without them age is unknown and the reading is consumed as before."""
    failures = []
    if statusline_doc is not None:
        age, stale = _age_check("statusline", statusline_read_at, now_ts,
                                stale_after_s)
        if stale:
            failures.append(stale)
        else:
            try:
                occ = read_statusline(statusline_doc)
                occ.age_s, occ.stale_after_s = age, stale_after_s
                return occ
            except GovernorError as exc:
                failures.append(str(exc))
    if oauth_doc is not None:
        age, stale = _age_check("oauth-usage", oauth_read_at, now_ts,
                                stale_after_s)
        if stale:
            failures.append(stale)
        else:
            try:
                occ = read_oauth_usage(oauth_doc)
                occ.age_s, occ.stale_after_s = age, stale_after_s
                return occ
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
           pause: float = DEFAULT_PAUSE, mode: str = "observe",
           age_margin_scale: float = DEFAULT_AGE_MARGIN_SCALE,
           now_ts: float | None = None) -> dict:
    """Threshold decision. status: ok | degrade | pause | unknown.

    ``unknown`` means no window produced a fraction (estimate rung without ceilings) —
    the caller must treat that as "cannot admit heavy work", not as "ok".
    ``enforced`` is False in observe mode regardless of status (§11 Stage 0).

    H8: when the reading carries an age, the effective thresholds tighten
    linearly with it (up to ``age_margin_scale`` at the staleness ceiling) —
    the admission margin widens with data age instead of trusting an old
    number as current.
    """
    if mode not in ("observe", "enforce"):
        raise GovernorError(f"mode must be observe|enforce, got {mode!r}")
    if not 0 < degrade < pause:
        raise GovernorError(f"need 0 < degrade({degrade}) < pause({pause})")

    age_margin = 0.0
    if occupancy.age_s and occupancy.stale_after_s:
        age_margin = min(occupancy.age_s / occupancy.stale_after_s, 1.0) \
            * age_margin_scale
    eff_degrade, eff_pause = degrade - age_margin, pause - age_margin
    if eff_degrade <= 0:
        raise GovernorError(f"age margin {age_margin} consumed the degrade "
                            f"threshold {degrade} — misconfigured scale")

    if occupancy.windows:
        binding = max(occupancy.windows, key=lambda w: occupancy.windows[w])
        worst = occupancy.windows[binding]
        if worst >= eff_pause:
            status = "pause"
        elif worst >= eff_degrade:
            status = "degrade"
        else:
            status = "ok"
    else:
        binding, worst, status = None, None, "unknown"

    reset_info = {}
    if now_ts is not None:
        reset_info = resets_in_s(occupancy, now_ts)
    return {
        "event": GOVERNOR_EVENT,
        "status": status,
        "binding_window": binding,
        "resets_in_s": reset_info,
        "occupancy": worst,
        "windows": occupancy.windows,
        "source": occupancy.source,
        "optimistic": occupancy.optimistic,
        "thresholds": {"degrade": degrade, "pause": pause},
        "effective_thresholds": {"degrade": eff_degrade, "pause": eff_pause},
        "reading_age_s": occupancy.age_s,
        "mode": mode,
        "enforced": mode == "enforce" and status not in ("ok",),
    }


# -- I17: reset-time awareness ------------------------------------------------------
# The 5-hour reset arrives live via the statusline/oauth ``resets_at``; the
# weekly reset is fixed per account, so an operator-supplied anchor covers it
# when the live feed lacks one. A binding window about to reset is a SOFT
# constraint: if the occupancy projected AT the reset stays under pause, the
# scheduler's tail-phase capping is waived (degrade/pause still bind).

RESET_CONFIG_RELPATH = os.path.join("harness", "config", "window-resets.json")


def next_weekly_reset(anchor_iso: str, now_ts: float) -> float:
    """Roll a known weekly-reset anchor forward to the next occurrence.
    The anchor is ANY past (or future) reset instant in ISO form — the
    operator reads it off /usage once; it repeats every 7 days."""
    anchor = _iso_to_epoch(anchor_iso)
    week = 7 * 86400.0
    if anchor > now_ts:
        return anchor
    periods = int((now_ts - anchor) // week) + 1
    return anchor + periods * week


def _iso_to_epoch(ts: str) -> float:
    return _dt.datetime.fromisoformat(
        ts.replace("Z", "+00:00")).timestamp()


def load_reset_config(repo_root: str = ".",
                      path: str | None = None) -> dict:
    """Operator fallback config: {"weekly_reset_anchor": "<ISO>" | null}.
    Missing file or null anchor = no fallback (never guessed)."""
    cfg_path = path or os.path.join(repo_root, RESET_CONFIG_RELPATH)
    try:
        with open(cfg_path) as fh:
            doc = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def apply_weekly_reset_fallback(occ: Occupancy, anchor_iso: str | None,
                                now_ts: float) -> Occupancy:
    """Fill seven_day/seven_day_sonnet resets_at from the operator anchor
    when the live reading lacks them. Live data always wins."""
    if not anchor_iso:
        return occ
    try:
        nxt = next_weekly_reset(anchor_iso, now_ts)
    except ValueError:
        return occ  # unparseable anchor: no fallback, never a crash
    for window in ("seven_day", "seven_day_sonnet"):
        if window in occ.windows and window not in occ.resets_at:
            occ.resets_at[window] = nxt
    return occ


def resets_in_s(occ: Occupancy, now_ts: float) -> dict:
    """Seconds until each window's reset, from whatever resets_at carries."""
    out = {}
    for window, at in (occ.resets_at or {}).items():
        if isinstance(at, (int, float)) and not isinstance(at, bool):
            out[window] = max(0.0, float(at) - now_ts)
    return out


def fraction_rate(decisions: list, window: str,
                  min_span_s: float = 600.0,
                  max_age_s: float = 6 * 3600.0,
                  now_ts: float | None = None,
                  since_ts: float | None = None) -> float | None:
    """Occupancy burn rate (fraction/second) for one window, measured from
    the governor's own decision log — live (non-optimistic) readings only,
    so ceilings are never needed. None = not enough data (conservative).

    I25 (P3v2-3): pass ``since_ts`` = this firing's run-marker ``acquired_at``
    epoch. Burn rate is a per-firing quantity — the wall-clock lookback alone
    let a *prior* firing's readings (once, pre-clock-correction stamps)
    resolve a rate on tick 1 and engage reset-headroom early. Readings older
    than ``since_ts`` never count; a fresh firing therefore starts at None
    (conservative) until it has ~min_span of its own readings, by design."""
    now = now_ts if now_ts is not None else __import__("time").time()
    points = []
    for d in decisions:
        if d.get("event") != GOVERNOR_EVENT or d.get("optimistic"):
            continue
        frac = (d.get("windows") or {}).get(window)
        ts = d.get("ts")
        if not isinstance(frac, (int, float)) or isinstance(frac, bool) \
                or not isinstance(ts, str):
            continue
        try:
            t = _iso_to_epoch(ts)
        except ValueError:
            continue
        if now - t <= max_age_s and (since_ts is None or t >= since_ts):
            points.append((t, float(frac)))
    if len(points) < 2:
        return None
    points.sort()
    (t0, f0), (t1, f1) = points[0], points[-1]
    if t1 - t0 < min_span_s:
        return None
    return (f1 - f0) / (t1 - t0)


def reset_headroom(occupancy_frac: float | None,
                   window_resets_in_s: float | None,
                   rate_per_s: float | None,
                   pause: float = DEFAULT_PAUSE) -> dict:
    """Does the binding window's imminent reset neutralize tail-phase
    capping? Clears only when EVERY input is known and the projection at
    reset time stays under pause — anything unknown is conservative."""
    if occupancy_frac is None or window_resets_in_s is None \
            or rate_per_s is None:
        return {"clears": False, "projected": None,
                "why": "insufficient reset/rate data — conservative "
                       "(tail rules apply)"}
    projected = occupancy_frac + max(rate_per_s, 0.0) * window_resets_in_s
    if projected < pause:
        return {"clears": True, "projected": projected,
                "why": f"projected occupancy at reset "
                       f"{projected:.2f} < pause {pause:.2f} "
                       f"(resets in {window_resets_in_s / 3600:.1f}h) — "
                       f"tail capping waived; degrade/pause still bind"}
    return {"clears": False, "projected": projected,
            "why": f"projected occupancy at reset {projected:.2f} would "
                   f"reach pause {pause:.2f} — tail rules apply"}


def assumed_occupancy(fraction: float, acked_by: str) -> Occupancy:
    """P2-4 bootstrap rung — a first-ever firing has no live rung and no
    calibrated ceilings, so occupancy is unknown and admission (correctly)
    refuses everything. The way out is an **explicit, operator-attributed
    assumption**: recorded as its own source, always optimistic (sticky-``~``),
    bounds-checked. It exists for conservative-mode serial bootstrap only —
    it never clears a preflight and never justifies concurrency."""
    if not isinstance(acked_by, str) or not acked_by.strip():
        raise GovernorError("an assumed occupancy needs --acked-by <operator> "
                            "— assumptions are attributed, never ambient")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) \
            or not 0 <= fraction < 1:
        raise GovernorError(f"assumed occupancy must be in [0, 1), "
                            f"got {fraction!r}")
    return Occupancy(source=f"operator-assumed:{acked_by.strip()}",
                     windows={name: float(fraction) for name in WINDOWS},
                     optimistic=True)


def preflight(statusline_doc: dict | None = None,
              statusline_read_at: float | None = None,
              oauth_doc: dict | None = None,
              oauth_read_at: float | None = None,
              now_ts: float | None = None,
              stale_after_s: float = DEFAULT_STALE_AFTER_S,
              degrade: float = DEFAULT_DEGRADE,
              pause: float = DEFAULT_PAUSE) -> dict:
    """H8 — firing preflight (§5.1 amendment): probe the *live-utilization*
    rungs only (the estimate rung is optimistic and blind to interactive
    drain — it cannot clear a preflight). No live rung reachable → the firing
    starts in **conservative mode**: tightened thresholds, cheap-serial work
    only, or an explicit operator acknowledgment. A firing never silently
    begins full-fan-out on estimate-rung data alone."""
    try:
        occ = resolve(statusline_doc=statusline_doc, oauth_doc=oauth_doc,
                      statusline_read_at=statusline_read_at,
                      oauth_read_at=oauth_read_at, now_ts=now_ts,
                      stale_after_s=stale_after_s)
        return {"mode": "normal", "source": occ.source, "age_s": occ.age_s,
                "thresholds": {"degrade": degrade, "pause": pause},
                "restrictions": [],
                "why": f"live utilization from {occ.source}"
                       + (f" ({occ.age_s:.0f}s old)" if occ.age_s else "")}
    except GovernorError as exc:
        return {"mode": "conservative",
                "thresholds": {"degrade": max(degrade - CONSERVATIVE_DELTA,
                                              0.05),
                               "pause": max(pause - CONSERVATIVE_DELTA, 0.10)},
                "restrictions": ["cheap-serial only",
                                 "no concurrency admissions",
                                 "operator ack required for heavy tasks"],
                "why": f"no live-utilization rung reachable ({exc}) — "
                       f"estimate-rung data alone never clears a preflight"}


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


def _mtime_of(value: str) -> float | None:
    """H8: a dump *file*'s mtime is its natural read_at; stdin/inline JSON has
    no age the CLI can know."""
    import os as _os
    if value and value != "-" and not value.lstrip().startswith("{"):
        try:
            return _os.path.getmtime(value)
        except OSError:
            return None
    return None


def _load_source(value: str | None, label: str):
    """P2-2 — a missing or corrupt source *file* is an unavailable rung, not
    a crash: warn, return (None, None), and let the ladder fall through to
    the designed refusal/conservative path."""
    if not value:
        return None, None
    try:
        return _load_json_arg(value), _mtime_of(value)
    except (FileNotFoundError, OSError) as exc:
        print(f"warning: {label} source {value!r} unavailable ({exc}) — "
              f"rung skipped", file=sys.stderr)
        return None, None
    except json.JSONDecodeError as exc:
        print(f"warning: {label} source {value!r} corrupt ({exc}) — "
              f"rung skipped", file=sys.stderr)
        return None, None


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
    p.add_argument("--stale-after", type=float, default=DEFAULT_STALE_AFTER_S,
                   help="H8: max age (s) before a file-based live reading "
                        "falls through (age = dump-file mtime)")
    p.add_argument("--preflight", action="store_true",
                   help="H8: probe live rungs only; exit 0 normal, 3 "
                        "conservative")
    p.add_argument("--assume-occupancy", type=float,
                   help="P2-4 bootstrap: operator-attributed occupancy "
                        "assumption in [0,1), used only when no source "
                        "yields a usable window; requires --acked-by")
    p.add_argument("--acked-by",
                   help="operator name attributing --assume-occupancy")
    p.add_argument("--weekly-reset",
                   help="I17: ISO anchor of any known weekly reset instant "
                        "(operator-supplied; overrides "
                        "harness/config/window-resets.json); rolls +7d")
    p.add_argument("--log", help="append the decision to this JSONL file")
    args = p.parse_args(argv)

    import time as _time
    now_ts = _time.time()
    statusline_doc, statusline_read_at = _load_source(
        args.statusline_json, "statusline")
    oauth_doc, oauth_read_at = _load_source(args.oauth_json, "oauth")

    if args.preflight:
        result = preflight(statusline_doc=statusline_doc,
                           statusline_read_at=statusline_read_at,
                           oauth_doc=oauth_doc, oauth_read_at=oauth_read_at,
                           now_ts=now_ts, stale_after_s=args.stale_after,
                           degrade=args.degrade, pause=args.pause)
        print(json.dumps(result, indent=2))
        return 0 if result["mode"] == "normal" else 3

    records = None
    if args.runlog:
        records, errors = _runlog.RunLog(args.runlog).read()
        for lineno, message in errors:
            print(f"warning: {args.runlog}:{lineno}: {message}", file=sys.stderr)

    occ = None
    try:
        occ = resolve(statusline_doc=statusline_doc, oauth_doc=oauth_doc,
                      runlog_records=records,
                      ceilings=json.loads(args.ceilings) if args.ceilings
                      else None,
                      cache_read_weight=args.cache_read_weight,
                      statusline_read_at=statusline_read_at,
                      oauth_read_at=oauth_read_at, now_ts=now_ts,
                      stale_after_s=args.stale_after)
    except GovernorError:
        if args.assume_occupancy is None:
            raise
    # P2-4: the attributed assumption applies only when nothing else
    # produced a usable window fraction
    if args.assume_occupancy is not None and (occ is None or not occ.windows):
        occ = assumed_occupancy(args.assume_occupancy, args.acked_by or "")
    anchor = args.weekly_reset or load_reset_config().get("weekly_reset_anchor")
    occ = apply_weekly_reset_fallback(occ, anchor, now_ts)
    decision = decide(occ, degrade=args.degrade, pause=args.pause,
                      mode=args.mode, now_ts=now_ts)
    if args.log:
        log_decision(args.log, decision)
    print(json.dumps(decision, indent=2))
    return 0 if decision["status"] in ("ok",) else 1


if __name__ == "__main__":
    sys.exit(_cli())
