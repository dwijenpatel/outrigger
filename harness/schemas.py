#!/usr/bin/env python3
"""Worker return contracts — verdict / handoff / blocker schemas (E1).

Design §6.1 (structured outputs everywhere) + §7 + §5.4 format policy: model
output is **schema-validated JSON only**; these validators are the harness-side
enforcement, and the matching JSON Schema files in ``harness/config/schemas/``
are what headless spawns pass via ``--json-schema`` (server-side validation).

Contract rules the validators enforce (2026-07-04 amendments):

- **Verdicts quote reproduced behavior.** A FAIL verdict must carry evidence
  entries that quote what was *observed* ("reload persistence did not restore
  contents"), never impressions; a PASS verdict must say what was exercised.
- **Every return carries a one-line ``intent``** — the audit-trail field.
- **Handoffs report material outcomes, not activities** (``key_changes_made``)
  and only *surprising* lessons (``key_learnings``) — the lessons-corpus feed.
- Findings inside verdicts are the D2 typed shape (severity × action).
"""

from __future__ import annotations

import json
import os

from .gate import ACTIONS, SEVERITIES, VERDICTS

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "config", "schemas")

_OUTCOMES = ("pass", "fail", "parked")


class SchemaError(ValueError):
    pass


def _require_str(doc: dict, field: str, what: str, allow_empty=False):
    value = doc.get(field)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SchemaError(f"{what}: {field!r} must be a non-empty string")
    return value


def _require_str_list(doc: dict, field: str, what: str) -> list:
    value = doc.get(field)
    if not isinstance(value, list) or not all(
            isinstance(v, str) and v.strip() for v in value):
        raise SchemaError(f"{what}: {field!r} must be a list of non-empty strings")
    return value


def validate_verdict(doc: dict) -> dict:
    """Validator-panel return: lens, PASS/FAIL, behavior-quoting evidence,
    typed findings, intent."""
    if not isinstance(doc, dict):
        raise SchemaError("verdict must be an object")
    _require_str(doc, "lens", "verdict")
    if doc.get("verdict") not in VERDICTS:
        raise SchemaError(f"verdict: 'verdict' must be one of {VERDICTS}")
    evidence = _require_str_list(doc, "evidence", "verdict")
    if not evidence:
        raise SchemaError("verdict: evidence must quote at least one observed "
                          "behavior — impressions don't gate merges")
    _require_str(doc, "intent", "verdict")
    findings = doc.get("findings", [])
    if not isinstance(findings, list):
        raise SchemaError("verdict: findings must be a list")
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            raise SchemaError(f"verdict: finding {i} must be an object")
        if f.get("severity") not in SEVERITIES:
            raise SchemaError(f"verdict: finding {i} severity not in {SEVERITIES}")
        if f.get("action") not in ACTIONS:
            raise SchemaError(f"verdict: finding {i} action not in {ACTIONS}")
        _require_str(f, "summary", f"verdict finding {i}")
    if doc["verdict"] == "FAIL" and not findings:
        raise SchemaError("verdict: a FAIL must carry at least one finding — "
                          "an unexplained FAIL cannot drive escalation")
    return dict(doc)


def validate_handoff(doc: dict) -> dict:
    """Implementer/test-author return: outcome + material changes + surprising
    lessons + intent. Empty lists are legal (definitive: 'nothing surprising')."""
    if not isinstance(doc, dict):
        raise SchemaError("handoff must be an object")
    if doc.get("outcome") not in _OUTCOMES:
        raise SchemaError(f"handoff: outcome must be one of {_OUTCOMES}")
    _require_str(doc, "summary", "handoff")
    _require_str(doc, "intent", "handoff")
    _require_str_list(doc, "key_changes_made", "handoff")
    _require_str_list(doc, "key_learnings", "handoff")
    files = doc.get("files_touched", [])
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise SchemaError("handoff: files_touched must be a list of paths")
    if doc["outcome"] == "pass" and not doc["key_changes_made"]:
        raise SchemaError("handoff: a passing task with zero material changes "
                          "is a no-op claiming success (§9 no-op rule)")
    return dict(doc)


def validate_blocker(doc: dict) -> dict:
    """Park blocker record (§6.3): everything a human needs to decide in one
    round-trip — repro, options, recommendation."""
    if not isinstance(doc, dict):
        raise SchemaError("blocker must be an object")
    _require_str(doc, "task_id", "blocker")
    _require_str(doc, "repro", "blocker")
    _require_str(doc, "recommendation", "blocker")
    options = doc.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise SchemaError("blocker: needs >= 2 options — a single option is a "
                          "notification, not a decision")
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise SchemaError(f"blocker: option {i} must be an object")
        _require_str(opt, "key", f"blocker option {i}")
        _require_str(opt, "label", f"blocker option {i}")
    keys = [o["key"] for o in options]
    if len(set(keys)) != len(keys):
        raise SchemaError("blocker: option keys must be unique")
    return dict(doc)


def load_json_schema(name: str) -> dict:
    """Load the committed JSON Schema (for --json-schema spawns)."""
    path = os.path.join(SCHEMA_DIR, f"{name}.json")
    with open(path) as fh:
        return json.load(fh)
