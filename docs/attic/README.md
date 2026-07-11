# The attic — superseded v1 documents

**Everything here is dead.** These are the v1 ("token-time-optimized") harness's design,
implementation plan, and machinery API reference, moved here by the
[reincarnation](../reincarnation-plan.md) on 2026-07-11 and kept **only** because the Tier-A
internal evidence ([distilled/internal.md](../research/distilled/internal.md), the pilot
ledgers) cites their IDs — §-numbers, D-decisions, I-increments, GL-tasks — and would be
uninterpretable without a referent.

**Reading rule: prior art to argue against — never a source of defaults.** No decision in the
current design surface ([design/evidence-based-harness.md](../design/evidence-based-harness.md))
may cite these documents as justification; "the old design did it" is not a warrant. If
something in here looks right, find the Tier-A evidence that makes it right, and cite that.

The v1 *code* (the `harness/` modules, hooks, worker roles, skills) was deleted from HEAD in
the same operation. All of it — code and docs, at full fidelity — is anchored at the git tag
**`v1-attic`**: `git show v1-attic:harness/interlocks.py`, `git checkout v1-attic`, etc.

| File | What it was |
|---|---|
| [token-time-optimized-harness.md](token-time-optimized-harness.md) | The v1 design document (the lexicographic O0/O1/O2 objective, vault, governor, escalation ladder) |
| [plan/implementation-plan.md](plan/implementation-plan.md) | Its phased implementation plan — the I-increments the pilot ledgers cite |
| [reference.md](reference.md) | The machinery API reference for the deleted `harness.*` modules |
