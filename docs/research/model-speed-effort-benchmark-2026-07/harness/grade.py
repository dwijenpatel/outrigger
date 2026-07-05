#!/usr/bin/env python3
"""Grade and aggregate round-3 results."""
import json, glob, os, re, shutil, statistics, subprocess, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
GRADE_DIR = os.path.join(BENCH, "grading")

def strip_fences(code: str) -> str:
    code = code.strip()
    m = re.match(r"^```(?:python)?\s*\n(.*)\n```\s*$", code, re.S)
    return m.group(1) if m else code

def pytest_counts(cwd, extra_files=None):
    """Run pytest in cwd, return (passed, failed_or_error_total)."""
    r = subprocess.run(["python3", "-m", "pytest", "-q", "--tb=no"],
                       cwd=cwd, capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    passed = failed = errors = 0
    m = re.search(r"(\d+) passed", out)
    if m: passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m: failed = int(m.group(1))
    m = re.search(r"(\d+) error", out)
    if m: errors = int(m.group(1))
    if "collected 0 items" in out or ("error" in out.lower() and passed+failed == 0):
        return (0, 17, "import/collect error")
    return (passed, failed + errors, "")

def grade_gen(model, rep, result_text):
    d = os.path.join(GRADE_DIR, f"gen_{model}_r{rep}")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    with open(os.path.join(d, "solution.py"), "w") as f:
        f.write(strip_fences(result_text))
    shutil.copy(os.path.join(BENCH, "fixtures", "test_eval_hidden.py"),
                os.path.join(d, "test_eval_hidden.py"))
    try:
        return pytest_counts(d)
    except Exception as e:
        return (0, 17, str(e)[:60])

def grade_fix(model, rep):
    ws = os.path.join(BENCH, f"ws_fix_{model}_r{rep}")
    if not os.path.isdir(ws):
        return (0, 10, "workspace missing")
    # ensure tests weren't modified
    orig = open(os.path.join(BENCH, "fixtures", "fixws", "test_wordwrap.py")).read()
    cur = open(os.path.join(ws, "test_wordwrap.py")).read()
    tampered = " TESTS-MODIFIED!" if orig != cur else ""
    try:
        p, f, note = pytest_counts(ws)
        return (p, f, note + tampered)
    except Exception as e:
        return (0, 10, str(e)[:60])

rows = []
for f in sorted(glob.glob(os.path.join(BENCH, "result3_*.json"))):
    m = re.match(r"result3_(gen|fix)_(\w+)_r(\d)\.json", os.path.basename(f))
    task, model, rep = m.groups()
    try:
        d = json.load(open(f))
    except Exception:
        rows.append(dict(task=task, model=model, rep=rep, error="json parse fail")); continue
    if d.get("is_error"):
        rows.append(dict(task=task, model=model, rep=rep, error=str(d.get("result"))[:100])); continue
    if task == "gen":
        passed, failed, note = grade_gen(model, rep, d.get("result", ""))
        total = 17
    else:
        passed, failed, note = grade_fix(model, rep)
        total = 10
    rows.append(dict(
        task=task, model=model, rep=int(rep),
        api_s=round(d["duration_api_ms"]/1000, 1),
        total_s=round(d["duration_ms"]/1000, 1),
        out_tok=d["usage"]["output_tokens"],
        in_tok=d["usage"]["input_tokens"] + d["usage"].get("cache_creation_input_tokens", 0) + d["usage"].get("cache_read_input_tokens", 0),
        cost=round(d.get("total_cost_usd", 0), 4),
        turns=d.get("num_turns"),
        passed=passed, total=total, note=note,
    ))

print(json.dumps(rows, indent=1))

# aggregate
print("\n--- AGGREGATE (median [min-max] across reps) ---")
mo = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
for task in ("gen", "fix"):
    print(f"\n{task.upper()}  (tests per run: {'17' if task=='gen' else '10'})")
    print(f"{'model':8}{'api_s':>16}{'out_tok':>18}{'cost$':>22}{'solved':>9}{'tests':>8}")
    for model in sorted({r['model'] for r in rows if 'error' not in r}, key=lambda m: mo.get(m, 9)):
        rs = [r for r in rows if r.get("task")==task and r.get("model")==model and "error" not in r]
        if not rs: continue
        def agg(key, fmt="{:.1f}"):
            vals = [r[key] for r in rs]
            return f"{fmt.format(statistics.median(vals))} [{fmt.format(min(vals))}-{fmt.format(max(vals))}]"
        solved = sum(1 for r in rs if r["passed"] == r["total"])
        tests = "/".join(str(r["passed"]) for r in rs)
        print(f"{model:8}{agg('api_s'):>16}{agg('out_tok', '{:.0f}'):>18}{agg('cost', '{:.3f}'):>22}{solved:>6}/{len(rs)}{tests:>8}")
