#!/usr/bin/env python3
"""Window-aware admission — "don't start what you can't finish" (design §5.1, §6.2).

Each candidate task carries a **quantile** cost forecast, never a point estimate
(measured same-task spend varies up to 30×, and models can't self-predict burn).
Sources, in order of trust:

- ``profile-tier-estimates.json``'s per-profile P95 (Stage 0/1). Below the sample
  floor the estimate is widened, never trusted raw; a null estimate is never replaced
  with an invented number.
- The duration-bucket predictor's per-bucket quantiles (Stage 1+) — only after
  ``validate_predictor.py`` signs off; out of scope here.

Admission compares occupancy + forecast-added burn against the degrade threshold.
Converting forecast tokens → occupancy fraction needs a calibrated window ceiling;
ceilings are deliberately never hard-coded (§10.3), so until one is calibrated the
rule falls back to requiring a conservative extra margin below the degrade threshold
(see the plan's "Deviations & open items"). Unknown occupancy never admits.
"""

from __future__ import annotations

import json

from .spawncheck import DEFAULT_ESTIMATES_PATH

DEFAULT_DEGRADE = 0.8
#: Extra headroom demanded below the degrade threshold when the forecast can't be
#: expressed as an occupancy fraction (no calibrated ceiling, or no estimate yet).
DEFAULT_UNKNOWN_COST_MARGIN = 0.15
#: Widening multiplier applied to a quantile backed by fewer samples than the floor.
DEFAULT_LOW_CONFIDENCE_WIDEN = 1.5


class AdmissionError(ValueError):
    pass


def load_estimates(path: str | None = None) -> dict:
    with open(path or DEFAULT_ESTIMATES_PATH) as fh:
        doc = json.load(fh)
    if "cost_estimate_by_profile" not in doc:
        raise AdmissionError("estimates file: missing cost_estimate_by_profile")
    return doc


def forecast_tokens(profile: str, estimates_doc: dict, quantile: str = "p95",
                    widen_factor: float = DEFAULT_LOW_CONFIDENCE_WIDEN) -> dict:
    """Quantile token forecast for one task on ``profile``.

    Returns {"tokens": float|None, "sample_size": int, "low_confidence": bool,
    "quantile": str}. tokens is None when the table has no data for the profile —
    never fabricated (§5.1 / the estimates file's own _meta rules). A below-floor
    sample widens the quantile by ``widen_factor``.
    """
    table = estimates_doc["cost_estimate_by_profile"]
    if profile not in table:
        raise AdmissionError(
            f"unknown profile {profile!r}; known: {sorted(table)}")
    entry = table[profile]
    value = entry.get(quantile)
    sample_size = entry.get("sample_size") or 0
    floor = (estimates_doc.get("_meta") or {}).get("min_samples_per_profile", 8)
    low_confidence = sample_size < floor
    if value is None:
        tokens = None
    else:
        tokens = float(value) * (widen_factor if low_confidence else 1.0)
    return {"tokens": tokens, "sample_size": sample_size,
            "low_confidence": low_confidence, "quantile": quantile}


def admit(occupancy: float | None, forecast: dict,
          window_ceiling_tokens: float | None = None,
          degrade: float = DEFAULT_DEGRADE,
          unknown_cost_margin: float = DEFAULT_UNKNOWN_COST_MARGIN) -> dict:
    """Admit/defer one candidate task against one window.

    ``occupancy`` is the binding window's current fraction (None = unknown → never
    admit). With both a forecast and a calibrated ceiling, the §5.1 rule applies
    exactly: admit iff occupancy + tokens/ceiling < degrade. Without either, the
    conservative-margin fallback applies: admit iff occupancy < degrade - margin.
    """
    if not 0 < degrade <= 1:
        raise AdmissionError(f"degrade must be in (0, 1], got {degrade}")
    if unknown_cost_margin < 0:
        raise AdmissionError(f"margin must be >= 0, got {unknown_cost_margin}")

    def decision(admitted: bool, reason: str, projected=None) -> dict:
        return {"admit": admitted, "reason": reason, "occupancy": occupancy,
                "projected_occupancy": projected, "degrade": degrade,
                "forecast": forecast}

    if occupancy is None:
        return decision(False, "occupancy unknown — cannot admit against an "
                               "unmeasured window (governor status 'unknown')")
    if occupancy >= degrade:
        return decision(False, f"occupancy {occupancy:.2f} already at/over degrade "
                               f"threshold {degrade:.2f}")

    tokens = forecast.get("tokens")
    if tokens is not None and window_ceiling_tokens:
        projected = occupancy + tokens / window_ceiling_tokens
        if projected < degrade:
            return decision(True, f"projected occupancy {projected:.2f} stays below "
                                  f"degrade {degrade:.2f}", projected)
        return decision(False, f"projected occupancy {projected:.2f} would cross "
                               f"degrade {degrade:.2f}", projected)

    # Fallback: no way to express the forecast as occupancy — demand extra margin.
    limit = degrade - unknown_cost_margin
    why = "no calibrated ceiling" if tokens is not None else "no cost estimate yet"
    if occupancy < limit:
        return decision(True, f"{why}; occupancy {occupancy:.2f} below conservative "
                              f"limit {limit:.2f} (degrade - margin)")
    return decision(False, f"{why}; occupancy {occupancy:.2f} not below conservative "
                           f"limit {limit:.2f} (degrade - margin)")


def admit_task(profile: str, occupancy: float | None,
               estimates_doc: dict | None = None,
               window_ceiling_tokens: float | None = None,
               degrade: float = DEFAULT_DEGRADE,
               unknown_cost_margin: float = DEFAULT_UNKNOWN_COST_MARGIN) -> dict:
    """Convenience wrapper: profile → forecast → admit decision."""
    doc = estimates_doc or load_estimates()
    fc = forecast_tokens(profile, doc)
    return admit(occupancy, fc, window_ceiling_tokens=window_ceiling_tokens,
                 degrade=degrade, unknown_cost_margin=unknown_cost_margin)
