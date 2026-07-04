#!/usr/bin/env python3
"""Liveness guard — multi-signal park for stuck/doomed tasks (design §9, B3).

Per-run token cost grows ~O(n²) in agent steps, so a stuck retry loop is a
multi-million-token event. Signals (all deterministic, fed by the loop driver —
git delta is authoritative, never a model's claim of progress):

- **step cap** — steps beyond the per-task cap;
- **token cap** — mid-flight spend beyond the §5.1 P95 forecast × multiplier
  (checked *inside* the task, not only between tasks — 2026-07-04 amendment);
- **repeated-error signature** — the same normalized error N times in a row
  (numbers/paths/hex stripped, so `line 42` and `line 57` match);
- **no-op rule** — a turn with zero git delta and zero new artifacts counts as
  a *failure*; a streak of them means the loop is spinning, not working;
- **slow grind** — wall-clock far past the predicted duration bucket.

Ships **observe-only** (§5.6): ``assess`` always reports, ``enforced`` is True
only in ``enforce`` mode — a Stage-2 flip gated on the false-abort rate being
proven against O0 (an external abort recovers 28–64% of a failing trajectory's
tokens, but a false abort violates the correctness floor's economics).
"""

from __future__ import annotations

import re

DEFAULT_ERROR_REPEAT_THRESHOLD = 3
DEFAULT_NOOP_THRESHOLD = 2
DEFAULT_TOKEN_CAP_MULTIPLIER = 2.0


class LivenessError(ValueError):
    pass


def error_signature(text: str) -> str:
    """Normalize an error so recurrences match across incidental detail:
    numbers, hex ids, and path segments are collapsed."""
    if not isinstance(text, str):
        raise LivenessError("error text must be a string")
    sig = text.strip().lower()
    sig = re.sub(r"(/[\w.\-]+)+", "<path>", sig)          # unix paths
    sig = re.sub(r"0x[0-9a-f]+", "<hex>", sig)
    sig = re.sub(r"\d+", "<n>", sig)
    sig = re.sub(r"\s+", " ", sig)
    return sig[:300]


def token_cap_from_forecast(forecast_tokens: float | None,
                            multiplier: float = DEFAULT_TOKEN_CAP_MULTIPLIER
                            ) -> float | None:
    """Mid-flight token cap = P95 forecast × multiplier. None forecast → no cap
    (never fabricate a ceiling; the step cap still guards)."""
    if forecast_tokens is None:
        return None
    if multiplier <= 1.0:
        raise LivenessError(f"multiplier must be > 1.0, got {multiplier}")
    return forecast_tokens * multiplier


class Vitals:
    """Per-task accumulator the loop driver feeds after every worker step."""

    def __init__(self):
        self.steps = 0
        self.tokens_spent = 0
        self.wall_secs = 0.0
        self.last_signature = None
        self.signature_streak = 0
        self.noop_streak = 0

    def record_step(self, tokens: int = 0, wall_secs: float = 0.0,
                    error: str | None = None, git_delta_bytes: int = 0,
                    artifacts_written: int = 0) -> None:
        if tokens < 0 or wall_secs < 0 or git_delta_bytes < 0 \
                or artifacts_written < 0:
            raise LivenessError("vitals inputs must be non-negative")
        self.steps += 1
        self.tokens_spent += tokens
        self.wall_secs += wall_secs
        if error is not None:
            sig = error_signature(error)
            if sig == self.last_signature:
                self.signature_streak += 1
            else:
                self.last_signature, self.signature_streak = sig, 1
        else:
            self.last_signature, self.signature_streak = None, 0
        if git_delta_bytes == 0 and artifacts_written == 0:
            self.noop_streak += 1
        else:
            self.noop_streak = 0


def assess(vitals: Vitals, step_cap: int,
           token_cap: float | None = None,
           wall_cap_secs: float | None = None,
           error_repeat_threshold: int = DEFAULT_ERROR_REPEAT_THRESHOLD,
           noop_threshold: int = DEFAULT_NOOP_THRESHOLD,
           mode: str = "observe") -> dict:
    """Evaluate all signals. Any signal → recommendation 'park' (with every
    firing signal listed, so the park blocker record explains itself)."""
    if mode not in ("observe", "enforce"):
        raise LivenessError(f"mode must be observe|enforce, got {mode!r}")
    if step_cap < 1:
        raise LivenessError(f"step_cap must be >= 1, got {step_cap}")

    signals = []
    if vitals.steps > step_cap:
        signals.append({"signal": "step_cap",
                        "detail": f"{vitals.steps} steps > cap {step_cap}"})
    if token_cap is not None and vitals.tokens_spent > token_cap:
        signals.append({"signal": "token_cap",
                        "detail": f"{vitals.tokens_spent} tokens > cap "
                                  f"{token_cap:.0f} (P95-derived, mid-flight)"})
    if wall_cap_secs is not None and vitals.wall_secs > wall_cap_secs:
        signals.append({"signal": "slow_grind",
                        "detail": f"{vitals.wall_secs:.0f}s wall > predicted "
                                  f"bucket cap {wall_cap_secs:.0f}s"})
    if vitals.signature_streak >= error_repeat_threshold:
        signals.append({"signal": "repeated_error",
                        "detail": f"same error signature {vitals.signature_streak}"
                                  f"× in a row: {vitals.last_signature!r}"})
    if vitals.noop_streak >= noop_threshold:
        signals.append({"signal": "no_op",
                        "detail": f"{vitals.noop_streak} consecutive turns with "
                                  f"zero git delta and zero artifacts"})

    recommendation = "park" if signals else "continue"
    return {
        "recommendation": recommendation,
        "signals": signals,
        "steps": vitals.steps,
        "tokens_spent": vitals.tokens_spent,
        "mode": mode,
        "enforced": mode == "enforce" and recommendation == "park",
    }
