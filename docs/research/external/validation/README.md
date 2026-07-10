# Validation — the correctness floor

**Scope.** How a harness knows work is actually correct: blind generator–verifier separation,
held-out testing, merge/closure gates, validator panels and their calibration, reward-hacking
defenses, verifier precision (false FAILs), and the statistics of re-using a hidden oracle.

**Coverage: ● rich** (2026-07-10). This is the corpus's deepest subtopic — deliberately so
historically, and the reason the taxonomy exists is to stop it from crowding out the others.

## Holdings

- [correctness-and-verification-evidence.md](correctness-and-verification-evidence.md) — the O0
  evidence base: reward-hacking/stale-green threat, blind separation, panel diversity vs
  correlated errors, false-FAIL base rates, the calibration-probe novelty claim.
- [revalidation-reuse-and-leakage.md](revalidation-reuse-and-leakage.md) — the vault's
  economics: safe regression-test selection, corpus persistence/freshness, adaptive-reuse
  leakage theory (the Ladder, Thresholdout).

## Related material elsewhere

- [../landscape/ecosystem-mining/verification-and-blind-gating.md](../landscape/ecosystem-mining/verification-and-blind-gating.md)
  — the 11-repo census (reward-hacking hole 11/11).
- [../self-improvement/meta-harness-and-self-improving-harnesses.md](../self-improvement/meta-harness-and-self-improving-harnesses.md)
  §4 — the gaming ledger; the two-split promotion rule.
- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) §2–3 —
  stopping discipline and prompt-blind (vs OS-enforced) verification in the closest neighbor.
- Internal: pilot ledgers (P2-10, P2-13, P3v2-5); [../../distilled/](../../distilled/README.md).

## Open questions

- False-FAIL engineering beyond Refute-or-Promote: what drives verifier *precision*, per lens?
- Verifier ROI curves: marginal catch-rate of the Nth lens, measured rather than assumed.
- Held-out corpus rotation policy: when does refresh beat metered replay?
