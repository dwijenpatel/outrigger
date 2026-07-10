# Isolation — sandboxing, permissions, and boundaries

**Scope.** Making blindness and safety *structural* rather than prompt-promised: OS sandboxes,
permission/deny rules, egress control, per-role process isolation, credential posture, and the
documented ways agents escape all of the above.

**Coverage: ◐ moderate** (2026-07-10). One strong document, macOS-centric, vault-motivated.

## Holdings

- [isolation-and-sandboxing.md](isolation-and-sandboxing.md) — the six-layer vault-isolation
  stack, layer-by-layer gaps each next layer covers, the ona.com sandbox-escape incident,
  approval fatigue, the Trail-of-Bits anti-pattern.

## Related material elsewhere

- [../landscape/zenith-and-meta-zenith.md](../landscape/zenith-and-meta-zenith.md) §3 — what
  no-enforcement looks like in a shipped neighbor (`bypassPermissions`, prompt-only blindness).
- Internal: worker-overlay probes (I26), credential posture (pilot-2 P2-8/I13).

## Open questions

- Linux/bubblewrap parity: the stack was verified doc-deep on macOS Seatbelt; the bubblewrap
  escape incident suggests the Linux story needs its own pass.
- Egress control in practice: proxy allowlists, domain-fronting residuals, and what a
  *practical* worker egress policy costs in task success.
- Sandbox ↔ dependency management: can a worker `pip/npm install` inside strict mode?
  (Pre-registered watch item P2-1 — still unobserved.)
- Multi-tenant isolation: what changes when workers from different tasks share a host?
