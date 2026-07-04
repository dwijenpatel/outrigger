#!/usr/bin/env python3
"""Failure taxonomy for the loop driver — design §5.1 (2026-07-04 amendment).

Three-way classification drives the retry policy, "a stderr-pattern table, not a
judgment call" (research: unattended-operation-prior-art.md §3):

- **Agent-reported failures are not errors.** A worker returning
  ``outcome: fail`` is the §5.3 escalation signal — the loop *continues*
  immediately (next attempt, possibly escalated). This module never sees those;
  it classifies *infrastructure* errors only.
- **retryable** — transient infrastructure trouble (network, 5xx/overloaded,
  transient 429): exponential backoff, then retry.
- **permanent** — the firing cannot proceed on any retry (auth expired, credit
  exhausted, subscription problems): abort the firing at once, cleanly.

Patterns are config (never hard-coded magnitudes, §10.3): a JSON list of
``{"pattern": <regex>, "class": "permanent"|"retryable", "why": <str>}`` entries
extends/overrides the defaults. Unknown errors default to **retryable** — a
wrongly-retried permanent error costs bounded backoff time and then hits the
attempt cap; a wrongly-aborted transient error kills a whole firing.
"""

from __future__ import annotations

import json
import re

PERMANENT = "permanent"
RETRYABLE = "retryable"
CLASSES = (PERMANENT, RETRYABLE)

#: Default pattern table. Matched case-insensitively against the error text
#: (stderr, exception message). First match wins; config entries are consulted
#: before these defaults.
DEFAULT_PATTERNS = (
    {"pattern": r"credit balance\s+is\s+too\s+low", "class": PERMANENT,
     "why": "usage credits exhausted; retrying cannot help"},
    {"pattern": r"(invalid|expired).{0,20}(api key|token|credentials)",
     "class": PERMANENT, "why": "auth is broken; operator must re-authenticate"},
    {"pattern": r"authentication[_ ]error|unauthorized|401\b", "class": PERMANENT,
     "why": "auth is broken; operator must re-authenticate"},
    {"pattern": r"billing|payment required|402\b", "class": PERMANENT,
     "why": "billing problem; operator decision required"},
    {"pattern": r"permission[_ ]denied|403\b", "class": PERMANENT,
     "why": "authorization is broken; retrying cannot help"},
    {"pattern": r"rate.?limit|429\b|overloaded|529\b", "class": RETRYABLE,
     "why": "window/server pressure; backs off and clears"},
    {"pattern": r"5\d\d\b|internal server error|bad gateway|service unavailable",
     "class": RETRYABLE, "why": "transient server error"},
    {"pattern": r"timeout|timed out|connection (reset|refused|error)|econnreset",
     "class": RETRYABLE, "why": "transient network trouble"},
)

DEFAULT_BASE_DELAY_SECS = 30.0
DEFAULT_MAX_DELAY_SECS = 1800.0
DEFAULT_MAX_ATTEMPTS = 5


class FailureConfigError(ValueError):
    pass


def load_patterns(doc) -> list:
    """Validate a config pattern table (list of dicts). Returns compiled entries.
    Bad config is a loud stop — a silently-dropped pattern would misclassify."""
    if doc is None:
        doc = []
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, list):
        raise FailureConfigError("pattern table must be a JSON list")
    compiled = []
    for i, entry in enumerate(doc):
        if not isinstance(entry, dict):
            raise FailureConfigError(f"pattern entry {i} must be an object")
        cls = entry.get("class")
        if cls not in CLASSES:
            raise FailureConfigError(
                f"pattern entry {i}: class {cls!r} not in {CLASSES}")
        try:
            rx = re.compile(entry.get("pattern", ""), re.IGNORECASE)
        except re.error as exc:
            raise FailureConfigError(
                f"pattern entry {i}: bad regex: {exc}") from None
        if not rx.pattern:
            raise FailureConfigError(f"pattern entry {i}: empty pattern")
        compiled.append({"rx": rx, "class": cls, "why": entry.get("why", "")})
    return compiled


def classify(error_text: str, extra_patterns: list | None = None) -> dict:
    """Classify infrastructure error text. Config patterns are consulted first,
    then the defaults; no match → retryable (see module docstring for why)."""
    if not isinstance(error_text, str):
        raise FailureConfigError("error_text must be a string")
    tables = (extra_patterns or []) + [
        {"rx": re.compile(e["pattern"], re.IGNORECASE), "class": e["class"],
         "why": e["why"]} for e in DEFAULT_PATTERNS]
    for entry in tables:
        if entry["rx"].search(error_text):
            return {"class": entry["class"], "why": entry["why"],
                    "matched": entry["rx"].pattern}
    return {"class": RETRYABLE, "why": "unmatched error; defaulting to retryable",
            "matched": None}


def next_action(classification: dict, attempt: int,
                base_delay_secs: float = DEFAULT_BASE_DELAY_SECS,
                max_delay_secs: float = DEFAULT_MAX_DELAY_SECS,
                max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> dict:
    """Policy step for attempt N (1-based) of an infrastructure error.

    permanent → abort now. retryable → exponential backoff (base·2^(N-1), capped)
    until max_attempts, then abort — a retry loop that never gives up is the §9
    multi-million-token stuck-loop event.
    """
    if not isinstance(attempt, int) or attempt < 1:
        raise FailureConfigError(f"attempt must be a positive int, got {attempt!r}")
    if classification["class"] == PERMANENT:
        return {"action": "abort", "why": classification["why"]}
    if attempt >= max_attempts:
        return {"action": "abort",
                "why": f"retryable error persisted through {attempt} attempts"}
    delay = min(base_delay_secs * (2 ** (attempt - 1)), max_delay_secs)
    return {"action": "backoff", "delay_secs": delay, "why": classification["why"]}
