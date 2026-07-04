#!/usr/bin/env python3
"""Spawn-parameter allowlist validation — the guard design §5.3 makes mandatory.

The 2026-07-04 spawn-portability probe (tools/budget-governor/
probe-spawn-portability-2026-07-04.md) found the spawn primitive does NOT fail loud:
an invalid ``effort`` string is silently accepted, and an invalid ``model`` id surfaces
only as an async ``null`` result. So (design §5.3 correction, §12 Q3):

1. every ``(model, effort)`` pair is validated against an explicit allowlist *before*
   any ``agent()``/``Workflow`` call — :func:`validate_spawn`;
2. every spawn *result* is checked for ``None`` rather than relying on an exception —
   :func:`require_result`.

The tier → model-id table lives in ``harness/config/tiers.json`` (config, not code —
design §5.3's "one config table"). Per-profile spawn parameters come from
``tools/budget-governor/profile-tier-estimates.json``'s ``risk_profiles`` block.
"""

from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TIERS_PATH = os.path.join(_HERE, "config", "tiers.json")
DEFAULT_ESTIMATES_PATH = os.path.join(
    os.path.dirname(_HERE), "tools", "budget-governor", "profile-tier-estimates.json")

TIER_NAMES = ("cheap", "standard", "capable", "max")


class SpawnValidationError(ValueError):
    """A spawn parameter failed allowlist validation. Never spawn after catching this."""


class NullSpawnResult(RuntimeError):
    """A spawn returned null — the probe-verified signature of an invalid model id
    (or a skipped/dead agent)."""


def load_tiers(path: str | None = None) -> dict:
    """Load and sanity-check the tier config. Returns the parsed document."""
    with open(path or DEFAULT_TIERS_PATH) as fh:
        doc = json.load(fh)
    tiers = doc.get("tiers")
    if not isinstance(tiers, dict):
        raise SpawnValidationError("tiers.json: missing 'tiers' table")
    for name in TIER_NAMES:
        model_id = tiers.get(name)
        if not isinstance(model_id, str) or not model_id:
            raise SpawnValidationError(
                f"tiers.json: tier {name!r} missing or has empty model id")
    efforts = doc.get("efforts")
    if not isinstance(efforts, list) or not all(isinstance(e, str) for e in efforts) \
            or not efforts:
        raise SpawnValidationError("tiers.json: 'efforts' must be a non-empty string list")
    doc.setdefault("extra_allowed_models", [])
    return doc


def allowed_models(tiers_doc: dict) -> set:
    return set(tiers_doc["tiers"].values()) | set(tiers_doc["extra_allowed_models"])


def validate_spawn(model: str | None = None, tier: str | None = None,
                   effort: str | None = None, tiers_doc: dict | None = None) -> dict:
    """Resolve + validate spawn params. Returns {"model", "effort", "tier"}.

    Exactly the checks §5.3 requires: model id must be on the explicit allowlist,
    effort must be a known level. ``tier`` and ``model`` may both be given only if
    consistent. ``effort`` may be None (session-level default applies at spawn), but a
    *present* invalid effort always raises — silence is what the primitive would give us.
    """
    doc = tiers_doc or load_tiers()

    if model is None and tier is None:
        raise SpawnValidationError("must give a model id or a tier")

    resolved_tier = tier
    if tier is not None:
        if tier not in doc["tiers"]:
            raise SpawnValidationError(
                f"unknown tier {tier!r}; known: {sorted(doc['tiers'])}")
        tier_model = doc["tiers"][tier]
        if model is not None and model != tier_model:
            raise SpawnValidationError(
                f"model {model!r} conflicts with tier {tier!r} -> {tier_model!r}")
        model = tier_model
    else:
        reverse = {v: k for k, v in doc["tiers"].items()}
        resolved_tier = reverse.get(model)  # None for extra_allowed_models — fine

    if model not in allowed_models(doc):
        raise SpawnValidationError(
            f"model {model!r} is not on the allowlist "
            f"{sorted(allowed_models(doc))}; invalid ids do NOT fail loud at spawn "
            "(probe 2026-07-04) so this is the only gate")

    if effort is not None and effort not in doc["efforts"]:
        raise SpawnValidationError(
            f"effort {effort!r} not in {doc['efforts']}; invalid efforts are "
            "SILENTLY accepted at spawn (probe 2026-07-04) so this is the only gate")

    return {"model": model, "effort": effort, "tier": resolved_tier}


def require_result(result, context: str = "spawn"):
    """Raise NullSpawnResult if a spawn result is None; otherwise return it unchanged.

    The probe found an invalid model id yields an async null result, not a throw —
    every agent()/Workflow result must pass through this check.
    """
    if result is None:
        raise NullSpawnResult(
            f"{context}: spawn returned null (invalid model id, skipped agent, or "
            "terminal agent error — see probe-spawn-portability-2026-07-04.md)")
    return result


def load_risk_profiles(path: str | None = None) -> dict:
    with open(path or DEFAULT_ESTIMATES_PATH) as fh:
        doc = json.load(fh)
    profiles = doc.get("risk_profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SpawnValidationError("estimates file: missing 'risk_profiles' block")
    return profiles


def profile_spawn_params(profile: str, tiers_doc: dict | None = None,
                         profiles: dict | None = None) -> dict:
    """Fully-validated spawn parameters for a risk profile.

    Returns {"model", "effort", "tier", "validator_count", "lenses"} with the
    (model, effort) pair already through validate_spawn — the one path harness code
    should use to turn a task's risk profile into spawn arguments.
    """
    table = profiles or load_risk_profiles()
    if profile not in table:
        raise SpawnValidationError(
            f"unknown risk profile {profile!r}; known: {sorted(table)}")
    entry = table[profile]
    resolved = validate_spawn(tier=entry.get("starting_tier"),
                              effort=entry.get("effort"), tiers_doc=tiers_doc)
    count = entry.get("validator_count")
    lenses = entry.get("lenses")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise SpawnValidationError(
            f"profile {profile!r}: validator_count must be a positive int, got {count!r}")
    if not isinstance(lenses, list) or not lenses:
        raise SpawnValidationError(
            f"profile {profile!r}: lenses must be a non-empty list, got {lenses!r}")
    resolved["validator_count"] = count
    resolved["lenses"] = list(lenses)
    return resolved
