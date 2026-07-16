# t12-cli — human-readable render

> **GENERATED from `t12-cli.plan.json` — do not edit.** The plan JSON is the
> ratified authority (stamp, preflight, hash-pinning all bind to it); regenerate this
> render after any plan change.

**Ratified:** dwijen at 2026-07-16T03:45:47Z
**Risk tier:** full

## Goal

Add the end-to-end CLI to eaitl: python3 -m eaitl run <source> <target_schema> [<target_examples>] --out <dir>, a thin veneer over run_job — parse argv, read only the given files, call the pipeline once, write transform.py / transform.mts / job.json (job.json always) under --out only, print the pinned stdout block, and exit 0 (completed) / 1 (failed job) / 2 (usage or file-level error, pipeline never called). This is the chain's end-state acceptance task. Done when the worked example runs from files to byte-exact artifacts with the pinned stdout, the boundary examples hold, mypy --strict passes, and the existing tests still pass.

## Non-goals

- No packaging, console-script entry point, or install step — the command form is python3 -m eaitl (an 'eaitl' binary is a distribution concern).
- No interactive mode and no approval prompt — run is the no-gate happy path; the staged human flow (propose, review/edit, confirm) uses the library pieces directly.
- No full-file transform execution — preview stays samples-only; full runs happen by executing the generated transform.py / transform.mts.
- No configuration files, environment variables, or output-format options.

## Constraints

- The committed engine and prior tasks' files must not change: the only edit to existing files is adding the new export(s) to eaitl/__init__.py.
- This task DOES perform I/O (the chain's only one): it reads exactly the argv paths and writes exactly under --out; nothing else is touched. No network, no subprocess, no clock, no randomness, no LLM.
- File writes are the externally-visible action, carved out exactly: --out only, created if missing, existing files overwritten (derived artifacts, deterministic regeneration).
- The CLI contains no transform/validation/policy logic — parse, read, one run_job call, write, print, exit.
- Exit codes and stdout lines are exactly as pinned; usage errors write nothing and never call run_job.

## Decisions

- **Problem & who it's for; why now (coverage item 1)**
  Sourced — chain-design task table: the end-to-end CLI ('eaitl run <source> <target> <samples> -> proposed IR -> preview -> generated Python/TypeScript + validation & policy reports'; end-state acceptance); next in the ratified cascade order (T2 through T10 done).
- **Scope and non-goals (coverage item 2)**
  Sourced — the chain-design row and the product draft's API surface; non-goals recorded above.
- **Use-cases / consumers (coverage item 3)**
  Sourced — chain-design dependency table: the operator (and the experiment's sealed end-to-end oracle) — the single command that exercises every ratified component.
- **Success in outcome terms (coverage item 4)**
  Sourced — the chain's correct-or-stop bar: behavior pinned exactly enough for the blind author to test from the spec alone, with the worked example as the anchor.
- **Appetite (coverage item 5)**
  Sourced — chain-design size/type table classes this task 'integration'; the experiment's measured per-task budget precedent bounds it.
- **Future-scope (coverage item 6)**
  Sourced — the chain fixes the sequence; extensions go to the post-experiment register.
- **Irreversible/externally-visible actions + risk tier (coverage item 7)**
  Asked-or-sourced: this is the chain's ONE task with externally-visible actions — file writes, carved out in constraints (--out only, overwrite as derived artifacts, usage errors write nothing). Tier: full, per the chain-wide precedent.
- **What is the chain sketch's third argument, '<samples>'?**
  Derived (from the product draft's propose-mappings payload): it is the example OUTPUT rows (the draft's example_output_rows) feeding the matcher's example-driven lane — source samples need no argument because introspection extracts them from the source file itself. Recorded as a gloss on the sketch; the argument is optional, matching the matcher's optional parameter. Cost: none — the alternative reading (source samples file) would duplicate what introspection already owns.
- **--out required rather than defaulting to the working directory**
  Derived (one-way-door caution on the chain's only externally-visible action): every write location is operator-named; no surprise files. Cost: one more required argument on every invocation.
- **Overwrite allowed inside --out; job.json written even on failure**
  Derived (two-way door, from derived-artifact convention): generated code and the record are pure functions of the inputs, so regeneration is the point (build-directory semantics); the failure record is the debugging artifact. Cost: a stale artifact a user hand-edited in --out is silently replaced — hand-edits belong outside the output directory.
- **Exit-code boundary: 2 vs 1**
  Derived (two-way door, from mechanism clarity): 2 = the CLI could not even assemble the pipeline call (argv, extension, unreadable file, invalid JSON, uncreatable --out; nothing written); 1 = the pipeline ran and reported failure (job.json written). Shape-semantic input problems are deliberately NOT pre-checked by the CLI — they flow to the pipeline (veneer principle). Cost: a malformed schema surfaces as a failed job rather than a usage message.
- **python3 -m eaitl invocation; main(argv) testable without subprocess**
  Derived (two-way door, from the stdlib-only convention): no packaging changes inside the experiment; tests call main directly. Cost: the literal command 'eaitl' does not exist on PATH in this slice.
- **What is the CLI for — local end-to-end testing, or something else?**
  Operator question at review (2026-07-16): both, in order. In the experiment it is the end-state acceptance surface — the sealed end-to-end oracle drives the whole flow through one command against files on disk. In the product it is the smallest real user-facing delivery: a data engineer points it at a source file and a target schema and gets generated code plus reports, scriptable in CI. It is NOT the product's eventual approval UX (diff / preview / accept-reject) — that is a service-plus-UI story that wraps the same library pieces; run is the no-gate happy path.

## Open questions

- none

## Task `end-to-end-cli` — One command from source file to generated code and reports

**Checks:** `python3 -m mypy --strict eaitl` · `python3 -m unittest discover -s tests -t .`
**Provides:** end-to-end-cli · **Requires:** job-pipeline

---

# End-to-end CLI — `eaitl run`: source file to generated code, one command

## What and why
The chain's end state: a human points the tool at a source data file and a target schema
and gets back generated Python and TypeScript plus the reports — the whole ratified
pipeline behind one command. This is the **end-state acceptance** task: it is deliberately
a thin veneer (parse arguments, read the input files, one `run_job` call, write artifacts,
print, exit) — **no transform, validation, or policy logic lives in the CLI**.

## Public interface (pin exactly)
- New files **`eaitl/cli.py`** (exporting `main(argv: list[str] | None = None) -> int`;
  `None` means `sys.argv[1:]`) and **`eaitl/__main__.py`** (calling
  `sys.exit(main())`), so the command form is:
  `python3 -m eaitl run <source> <target_schema> [<target_examples>] --out <dir>`
- Add `main` to `eaitl/__init__.py` (the only edit to existing files).
- **`run`** is the only subcommand. Arguments:
  - `<source>` — path to the source data file; `fmt` comes from its extension,
    case-insensitive: `.csv` → `"csv"`, `.json` → `"json"`, anything else is a usage error.
  - `<target_schema>` — path to a JSON file holding the ratified schema shape
    (`{"fields": [{"name", "type"}]}`).
  - `<target_examples>` — optional path to a JSON file holding example output rows (the
    product draft's `example_output_rows`; the chain sketch's `<samples>` argument).
    Omitted → the matcher's no-examples fallback lanes.
  - `--out <dir>` — required; the only place the CLI ever writes. Created (with parents)
    before the job runs; creation failure is a usage error.

## Behavior (pin exactly)
1. Parse argv; read the two or three input files (**the only files ever read**); every
   JSON file must parse as JSON. Any problem so far — bad argv, unknown extension,
   missing/unreadable file, invalid JSON text, uncreatable `--out` — is a **usage error**:
   message on stderr, nothing written, nothing on stdout, **exit 2** (`run_job` is never
   called). Shape-semantic problems beyond raw JSON validity are NOT the CLI's business —
   they flow into the pipeline and come back as a failed job.
2. Call `run_job(text, fmt, target_schema, target_examples)` — exactly once.
3. Write artifacts into `--out` (byte-deterministic; existing files overwritten — they are
   derived artifacts):
   - on `completed`: `transform.py` (the record's `stages.compile.python`, byte-exact) and
     `transform.mts` (`stages.compile.typescript`, byte-exact), then `job.json`;
   - on `failed`: `job.json` only.
   - `job.json` is always written: `json.dumps(record, indent=2, sort_keys=True,
     ensure_ascii=False)` plus a trailing newline.
4. Print to stdout, exactly these lines in this order, then exit:
   - completed (**exit 0**):
     `status: completed` · `version: <the record's version>` · `warnings: <len of the
     record's warnings>` · `preview_rows: <len of preview_rows>` · `wrote:
     <out>/transform.py` · `wrote: <out>/transform.mts` · `wrote: <out>/job.json`
   - failed (**exit 1**): `status: failed` · `stage: <failed_stage>` · `error: <error>` ·
     `wrote: <out>/job.json`
   - `<out>` is the `--out` value exactly as given, joined with `/`.

## Worked example (the pipeline task's scenario, from files — the chain's end-state anchor)
With `source.json` holding the pipeline task's pinned three-row array, `schema.json` its
five-field target schema, `examples.json` its three example rows:
`python3 -m eaitl run source.json schema.json examples.json --out out` exits 0 and prints:
```
status: completed
version: ec4a652a6db4123681215762326ce3c434a0448f0641b5119c3188d565beb417
warnings: 0
preview_rows: 3
wrote: out/transform.py
wrote: out/transform.mts
wrote: out/job.json
```
and afterwards `out/transform.py` is byte-equal to the ratified Python compiler's output
for the pinned five-mapping proposal, `out/transform.mts` byte-equal to the TypeScript
compiler's, and `out/job.json` parses back to exactly the `run_job` record.

Boundary examples to pin behavior (each must hold):
- Same command without `examples.json` → exit 0; the three-mapping fallback flow;
  `warnings: 2` (the two `unmapped_target` records).
- `<source>` named `data.txt` → exit 2, nothing written, nothing on stdout.
- `source.json` containing truncated JSON → **exit 1** (valid file read, the pipeline's
  introspect stage fails): stdout is the failed block with `stage: introspect`, and
  `out/job.json` holds the failed record with `"stages": {}`.
- Re-running the successful command over the same `--out` → identical bytes, identical
  stdout (deterministic overwrite).

## Conventions
Python stdlib only (`argparse`); `mypy --strict` clean across the package including
`__main__.py`; new stdlib-`unittest` tests under `tests/` calling `main([...])` directly
with a temporary directory (no subprocess needed), asserting exit codes, stdout (via
`contextlib.redirect_stdout`), file bytes, and the exit-code boundary (2 = `run_job` never
called; 1 = failed record; 0 = completed).
