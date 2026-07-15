# Unattended operation — long-running resilience

**Scope.** Surviving without a human watching: durable state (event logs, reconciled views,
leases), crash/resume, pause/park/wake, liveness and supervision, stopping discipline for
multi-day runs, and rate-limit-aware continuation.

**Coverage: ◐ moderate** (2026-07-10). One deep practitioner study plus strong internal pilot
evidence; the wake-on-reset gap is field-wide.

## Holdings

- [unattended-operation-prior-art.md](unattended-operation-prior-art.md) — one practitioner's
  production stack: event-log/reconciled-state split, zero-token supervision, worktree
  pooling with durable leases, gate findings taxonomy, ratification-card UX, token-free loop
  testing.

## Related material elsewhere

- [../landscape/ecosystem-mining/limits-resume-and-wake.md](../landscape/ecosystem-mining/limits-resume-and-wake.md)
  — wake-on-reset 0/11; `paused_rate_limit` without the alarm clock; cache-cold wake
  economics (fresh session from ledger, never fat `--resume`).
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) §2 — the
  terminal-reviewer stopping rule; premature completion as the dominant failure.
- Internal: pause/ack protocol (I23), watchdog (I29), resume-marker discipline, the 38-minute
  pre-compute hang (P3v2-13).

## Open questions

- **Wake-on-reset — designed, not yet built.** The clearest demand/supply gap in the ecosystem;
  parkfile + fresh `claude -p` re-entry is designed but unproven.
- **Liveness beyond deadlines.** Heartbeats for slow-degrading workers (explicitly open after
  P3v2-13).
- **Multi-day supervision economics.** What does a week of unattended operation cost in
  human interrupts, and where do they cluster?
