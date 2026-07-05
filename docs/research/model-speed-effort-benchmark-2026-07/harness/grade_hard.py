#!/usr/bin/env python3
"""Grade hard regex-engine task: run each solution's match() against re.fullmatch
on the 36-case battery, in a subprocess with a timeout (buggy engines can hang)."""
import json, glob, os, re, shutil, statistics, subprocess, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
GRADE_DIR = os.path.join(BENCH, "grading")

RUNNER = r'''
import json, re, sys
sys.setrecursionlimit(100000)
from solution import match
cases = [
    ("abc","abc"),("abc","abd"),("a.c","axc"),("a.c","ac"),
    ("a*","" ),("a*","aaaa"),("a*b","b"),("a+",""),("a+","aa"),
    ("ab?c","ac"),("ab?c","abc"),("ab?c","abbc"),
    ("(ab)*","abab"),("(ab)*","aba"),
    ("(a|b)*abb","aababb"),("(a|b)*abb","aabab"),
    ("ab|cd","ab"),("ab|cd","cd"),("ab|cd","abcd"),
    ("a(b|c)d","abd"),("a(b|c)d","aed"),
    ("[abc]+","cab"),("[abc]+","cabd"),
    ("[a-z0-9]*","abc123"),("[a-z0-9]*","ABC"),
    ("[^ab]c","xc"),("[^ab]c","ac"),
    ("a*a","aaa"),("(a+)+b","aaab"),("x(y|z)?","x"),
    (".*","anything"),("","" ),("","a"),
    ("(ab|a)b","ab"),("a(bc)+d","abcbcd"),("a(bc)+d","ad"),
]
passed = 0; fails = []
for p, t in cases:
    want = bool(re.fullmatch(p, t))
    try:
        got = bool(match(p, t))
    except Exception as e:
        got = f"EXC:{type(e).__name__}"
    if got == want:
        passed += 1
    else:
        fails.append([p, t, str(want), str(got)])
print(json.dumps({"passed": passed, "total": len(cases), "fails": fails}))
'''

def strip_fences(code):
    code = code.strip()
    m = re.match(r"^```(?:python)?\s*\n(.*)\n```\s*$", code, re.S)
    return m.group(1) if m else code

rows = []
for f in sorted(glob.glob(os.path.join(BENCH, "result3_hard_*.json"))):
    m = re.match(r"result3_hard_(\w+)_r(\d)\.json", os.path.basename(f))
    model, rep = m.groups()
    d = json.load(open(f))
    if d.get("is_error"):
        rows.append(dict(model=model, rep=rep, error=str(d.get("result"))[:100])); continue
    gd = os.path.join(GRADE_DIR, f"hard_{model}_r{rep}")
    shutil.rmtree(gd, ignore_errors=True); os.makedirs(gd)
    open(os.path.join(gd, "solution.py"), "w").write(strip_fences(d.get("result","")))
    open(os.path.join(gd, "runner.py"), "w").write(RUNNER)
    try:
        r = subprocess.run(["python3", "runner.py"], cwd=gd, capture_output=True, text=True, timeout=60)
        g = json.loads(r.stdout) if r.stdout.strip() else {"passed": 0, "total": 36, "fails": [["RUNNER-ERROR", r.stderr[-150:], "", ""]]}
    except subprocess.TimeoutExpired:
        g = {"passed": 0, "total": 36, "fails": [["TIMEOUT (catastrophic backtracking or hang)", "", "", ""]]}
    rows.append(dict(
        model=model, rep=int(rep),
        api_s=round(d["duration_api_ms"]/1000, 1),
        out_tok=d["usage"]["output_tokens"],
        cost=round(d.get("total_cost_usd", 0), 4),
        passed=g["passed"], total=g["total"],
        fails=g["fails"][:4],
    ))

mo = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
rows.sort(key=lambda r: (mo.get(r["model"], 9), r.get("rep", 0)))
print(f"{'model':8}{'rep':>4}{'api_s':>8}{'out_tok':>9}{'cost$':>9}{'tests':>9}  first fails")
for r in rows:
    if "error" in r:
        print(f"{r['model']:8}{r['rep']:>4}  ERROR {r['error']}"); continue
    fl = "; ".join(f"{p!r}~{t!r} want {w} got {g}" for p,t,w,g in r["fails"]) if r["fails"] else ""
    print(f"{r['model']:8}{r['rep']:>4}{r['api_s']:>8}{r['out_tok']:>9}{r['cost']:>9}{str(r['passed'])+'/'+str(r['total']):>9}  {fl[:90]}")

print("\n--- HARD aggregate ---")
for model in ("haiku","sonnet","opus","fable"):
    rs = [r for r in rows if r["model"]==model and "error" not in r]
    if not rs: continue
    solved = sum(1 for r in rs if r["passed"]==r["total"])
    med = lambda k: statistics.median(r[k] for r in rs)
    print(f"{model:8} solved {solved}/{len(rs)}  med_api_s {med('api_s'):7.1f}  med_out_tok {med('out_tok'):7.0f}  med_cost$ {med('cost'):.3f}  tests {'/'.join(str(r['passed']) for r in rs)}")
