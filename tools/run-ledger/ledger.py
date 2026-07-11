#!/usr/bin/env python3
"""run-ledger — append-only, schema-validated JSONL measurement ledger.

One thing well: durable, validated appends of measurement/run records, an
integrity check, and a summary. Nothing else — query with jq/grep, rotate
with mv, diff with git. Contract: README.md next to this file.

Pure stdlib. Exit codes: 0 ok · 1 integrity/summary found invalid records
· 2 usage or input error.
"""

import argparse
import datetime
import json
import os
import sys

ENVELOPE_KEYS = {"ts", "kind", "subject", "data", "source"}
REQUIRED_KEYS = ("ts", "kind", "subject", "data")


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value):
    """RFC3339 / ISO-8601; returns aware datetime or raises ValueError."""
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate_record(rec):
    """Return a list of problems (empty = valid envelope)."""
    problems = []
    if not isinstance(rec, dict):
        return ["record is not a JSON object"]
    unknown = sorted(set(rec) - ENVELOPE_KEYS)
    if unknown:
        problems.append(f"unknown top-level key(s): {', '.join(unknown)}")
    for key in REQUIRED_KEYS:
        if key not in rec:
            problems.append(f"missing required key: {key}")
    if "ts" in rec:
        try:
            parse_ts(rec["ts"])
        except (ValueError, TypeError):
            problems.append(f"ts is not RFC3339/ISO-8601: {rec['ts']!r}")
    for key in ("kind", "subject"):
        if key in rec and (not isinstance(rec[key], str) or not rec[key].strip()):
            problems.append(f"{key} must be a non-empty string")
    if "data" in rec and not isinstance(rec["data"], dict):
        problems.append("data must be a JSON object")
    if "source" in rec and (not isinstance(rec["source"], str) or not rec["source"].strip()):
        problems.append("source, when present, must be a non-empty string")
    return problems


def encode(rec) -> str:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def append_record(path, rec):
    """Single-line, single-write append under an advisory lock, fsync'd."""
    line = encode(rec) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except ImportError:  # non-POSIX: best-effort append-only semantics
            pass
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def iter_lines(path):
    """Yield (lineno, raw_line_without_newline). Notes torn tail separately."""
    with open(path, "rb") as fh:
        raw = fh.read()
    ends_with_newline = raw.endswith(b"\n")
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if ends_with_newline:
        lines = lines[:-1]  # drop the empty artifact of the final newline
    for idx, line in enumerate(lines, start=1):
        yield idx, line, (idx == len(lines) and not ends_with_newline)


def scan(path):
    """Parse a ledger file. Returns (records, problems).

    records: list of (lineno, rec) for valid records.
    problems: list of {line, error, torn_tail} for invalid lines.
    """
    records, problems = [], []
    for lineno, line, is_torn_candidate in iter_lines(path):
        if not line.strip():
            problems.append({"line": lineno, "error": "empty line", "torn_tail": False})
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(
                {
                    "line": lineno,
                    "error": f"not valid JSON: {exc.msg}",
                    "torn_tail": bool(is_torn_candidate),
                }
            )
            continue
        envelope_problems = validate_record(rec)
        if envelope_problems:
            problems.append(
                {"line": lineno, "error": "; ".join(envelope_problems), "torn_tail": False}
            )
        else:
            records.append((lineno, rec))
    return records, problems


def cmd_append(args):
    if args.data is not None and args.data_file is not None:
        print("error: pass --data or --data-file, not both", file=sys.stderr)
        return 2
    if args.data_file is not None:
        try:
            with open(args.data_file, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"error: cannot read --data-file: {exc}", file=sys.stderr)
            return 2
    elif args.data == "-":
        raw = sys.stdin.read()
    else:
        raw = args.data if args.data is not None else "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: data is not valid JSON: {exc.msg}", file=sys.stderr)
        return 2

    rec = {
        "ts": args.ts or utcnow(),
        "kind": args.kind,
        "subject": args.subject,
        "data": data,
    }
    if args.source:
        rec["source"] = args.source

    problems = validate_record(rec)
    if problems:
        print("error: invalid record: " + "; ".join(problems), file=sys.stderr)
        return 2

    append_record(args.ledger, rec)
    print(encode(rec))
    return 0


def cmd_check(args):
    total_records, all_problems, per_file = 0, 0, {}
    for path in args.ledger:
        if not os.path.exists(path):
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        records, problems = scan(path)
        total_records += len(records)
        all_problems += len(problems)
        per_file[path] = {"records": len(records), "problems": problems}
    print(
        json.dumps(
            {"ok": all_problems == 0, "records": total_records, "files": per_file},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all_problems == 0 else 1


def cmd_summarize(args):
    records, invalid = [], 0
    for path in args.ledger:
        if not os.path.exists(path):
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        recs, problems = scan(path)
        records.extend(rec for _, rec in recs)
        invalid += len(problems)

    by_kind, by_subject, ts_values = {}, {}, []
    for rec in records:
        by_kind[rec["kind"]] = by_kind.get(rec["kind"], 0) + 1
        by_subject[rec["subject"]] = by_subject.get(rec["subject"], 0) + 1
        ts_values.append(parse_ts(rec["ts"]))

    summary = {
        "records": len(records),
        "invalid_lines": invalid,
        "by_kind": dict(sorted(by_kind.items())),
        "by_subject": dict(sorted(by_subject.items())),
        "ts_min": min(ts_values).strftime("%Y-%m-%dT%H:%M:%SZ") if ts_values else None,
        "ts_max": max(ts_values).strftime("%Y-%m-%dT%H:%M:%SZ") if ts_values else None,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if invalid == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ledger.py", description="append-only schema-validated JSONL ledger"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append", help="validate and append one record")
    p_append.add_argument("ledger", help="ledger file (created if absent)")
    p_append.add_argument("--kind", required=True, help="record kind, e.g. measurement|run|prediction|outcome|note")
    p_append.add_argument("--subject", required=True, help="what the record is about, e.g. t1/arm-a")
    p_append.add_argument("--data", help="JSON object string, or '-' to read stdin (default {})")
    p_append.add_argument("--data-file", help="read the JSON object from a file")
    p_append.add_argument("--source", help="who/what produced the record")
    p_append.add_argument("--ts", help="override the timestamp (RFC3339; default: now UTC)")
    p_append.set_defaults(fn=cmd_append)

    p_check = sub.add_parser("check", help="strict integrity check; exit 1 on any invalid line")
    p_check.add_argument("ledger", nargs="+", help="ledger file(s)")
    p_check.set_defaults(fn=cmd_check)

    p_sum = sub.add_parser("summarize", help="tolerant aggregate: counts, subjects, time range")
    p_sum.add_argument("ledger", nargs="+", help="ledger file(s)")
    p_sum.set_defaults(fn=cmd_summarize)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
