# Tool surface — interfaces, tools, and formats

**Scope.** How workers touch tools and data: interface ergonomics (AXI principles), MCP vs
CLI vs code execution, deferred tool loading, skill surfaces and their triggering, and
serialization formats for model-facing data.

**Coverage: ◐ moderate** (2026-07-10). One document with unusually good independent
confirmation (the TOON and MCP-tax claims were adversarially verified).

## Holdings

- [tool-surface-and-format-economics.md](tool-surface-and-format-economics.md) — AXI's ten
  interface principles, the MCP schema tax `[measured, replicated]`, the deferred-loading
  regime split, the "ergonomics dominates transport" meta-finding, TOON verification incl.
  local measurements (the origin of the **No TOON** rule).

## Related material elsewhere

- [../evaluation/harness-evaluation-prior-art.md](../evaluation/harness-evaluation-prior-art.md)
  — skill under-invocation (why load-bearing procedures are phase-gated, not trigger-reliant).
- [../platform-facts/claude-code-and-max-plan-facts.md](../platform-facts/claude-code-and-max-plan-facts.md)
  — tool definitions in the cache prefix; deferred-loading cache semantics.
- Design §4/§5.4; internal tokenizer measurements (`[measured, local]`, §4.3 of the holding).

## Open questions

- Applying AXI principles to the harness's *own* surfaces (the reference page and count-line
  vocabulary are first steps; unmeasured).
- Skill-triggering reliability engineering beyond phase-gating: can routing canaries drive a
  measured improvement loop?
- Structured-output contracts across CLI versions (the `--json-schema` breakage class) — a
  probe-on-every-build candidate.
