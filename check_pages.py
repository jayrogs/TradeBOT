"""check_pages.py -- walk the whole desk before he looks at it.

Every page loads, every file a page asks for exists and is fresh, every number in those
files is a real number, every chart an index points at is on disk, and every chart set has
been measured. Prints one line per problem and a PASS/FAIL count.

    python check_pages.py            (server must be running on :5001)
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE = "http://localhost:5001"
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = ["/", "/eq", "/eqcharts", "/eqcoils", "/eqtrades", "/eqfree", "/rides", "/ridecharts", "/bb", "/trends", "/trendstudy",
         "/names", "/cases", "/study", "/rules", "/paint", "/scan", "/markets", "/desk",
         "/exitcharts", "/log", "/backburner", "/trendcases"]
# file -> how many days old is too old
FRESH = {"validation/trend_ride.json": 30, "validation/trend_ride_focus.json": 30,
         "validation/trend_names.json": 30, "validation/eq_break.json": 30,
         "validation/portfolio.json": 30, "validation/portfolio_names.json": 30,
         "validation/name_traits.json": 30, "validation/trend_ride_tol.json": 30,
         "validation/trend_ride_exits.json": 30, "validation/trend_ride_exits2.json": 30,
         "validation/entry_study.json": 30, "livelog/eq_scan.json": 1,
         "validation/eq_coil_study.json": 30, "validation/eq_coil_counts.json": 30,
         "validation/eq_freeride.json": 30}
import glob as _glob
INDEXES = ([("validation/eq_cases/eq_cases_index.json", "validation/eq_cases"),
            ("validation/ride_cases_index.json", "validation/ride_cases"),
            ("validation/cases_index.json", "validation/cases"),
            ("validation/trend_cases_index.json", "validation/trend_cases"),
            ("validation/backburner_index.json", "validation/backburner_cases"),
            ("validation/eq_coils/eq_coils_index.json", "validation/eq_coils"),
            ("validation/eq_trades/eq_trades_index.json", "validation/eq_trades"),
            ("validation/eq_free/eq_free_index.json", "validation/eq_free")]
           + [(f.replace("\\", "/"), os.path.dirname(f).replace("\\", "/"))
              for f in sorted(_glob.glob(os.path.join("validation", "exit_cases", "*", "*index*.json")))])

bad = []
ok = 0


def problem(where, what):
    bad.append("  %-42s %s" % (where, what))


def get(path, binary=False):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.read()
    except Exception as ex:
        return None, str(ex).encode()


def walk_numbers(o, where, path=""):
    """Every number in a results file must be a real number."""
    n = 0
    if isinstance(o, dict):
        for k, v in o.items():
            n += walk_numbers(v, where, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o[:2000]):
            n += walk_numbers(v, where, path + "[%d]" % i)
    elif isinstance(o, float):
        n = 1
        if o != o or o in (float("inf"), float("-inf")):
            problem(where, "not a number at %s" % path)
    elif isinstance(o, int):
        n = 1
    return n


print("PAGES")
for p in PAGES:
    st, body = get(p)
    if st != 200:
        problem(p, "status %s" % st)
        continue
    if len(body) < 400:
        problem(p, "only %d bytes" % len(body))
        continue
    ok += 1
    # every file this page fetches must answer
    for m in set(re.findall(rb"fetch\('(/[^']+?)(?:\?[^']*)?'", body)):
        u = m.decode()
        if "${" in u:
            continue
        s2, b2 = get(u)
        if s2 != 200:
            problem(p, "asks for %s -> %s" % (u, s2))
        elif u.endswith(".json"):
            try:
                json.loads(b2)
            except Exception as ex:
                problem(p, "%s is not readable json (%s)" % (u, ex))

print("FILES")
now = time.time()
for rel, days in FRESH.items():
    f = os.path.join(HERE, rel)
    if not os.path.exists(f):
        problem(rel, "missing")
        continue
    age = (now - os.path.getmtime(f)) / 86400
    if age > days:
        problem(rel, "%.1f days old (limit %d)" % (age, days))
    try:
        d = json.load(open(f))
    except Exception as ex:
        problem(rel, "unreadable (%s)" % ex)
        continue
    cnt = walk_numbers(d, rel)
    ok += 1
    print("  %-42s %6.2f days old, %d numbers" % (rel, age, cnt))

print("CHART SETS")
for idx, folder in INDEXES:
    f = os.path.join(HERE, idx)
    if not os.path.exists(f):
        print("  %-42s (none)" % idx)
        continue
    d = json.load(open(f))
    items = d if isinstance(d, list) else d.get("items", d.get("rows", d.get("cases", [])))
    if isinstance(items, dict):
        items = list(items.values())
    miss = probs = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        png = it.get("png") or it.get("file") or it.get("path")
        if png and not os.path.exists(os.path.join(HERE, folder, os.path.basename(png))):
            miss += 1
        if it.get("problems"):
            probs += 1
    print("  %-42s %d charts, %d files missing, %d with text problems" % (idx, len(items), miss, probs))
    if miss:
        problem(idx, "%d chart files missing" % miss)
    if probs:
        problem(idx, "%d charts with text problems" % probs)
    ok += 1

print("IDEA PICTURES")
for n in ("trend_ride", "exits", "backburner", "eq", "channel", "trend_steps"):
    st, b = get("/ideas/%s.png" % n)
    if st != 200 or len(b) < 5000:
        problem("/ideas/%s.png" % n, "status %s, %s bytes" % (st, len(b)))
    else:
        ok += 1

print()
if bad:
    print("PROBLEMS (%d):" % len(bad))
    for b in bad:
        print(b)
else:
    print("no problems found")
print("%d checks passed, %d problems" % (ok, len(bad)))
sys.exit(1 if bad else 0)
