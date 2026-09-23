"""pics_messymark.py -- ten runs, half of them wandering, shuffled, for HIM to tap (2026-09-22).

The one number that agrees with both my eye and his five "messy chart" rejects is HOW MUCH THE RUN WANDERED:
every day's move added up over the 55 days into the dip, divided by how far price actually got. A straight climb
is about 2; a jerky one is 5 and up (#44b). It separates, and the money likes the straight climbs -- but any cut
also throws out trades he KEPT, so the cut is his call, not mine.

So: five runs that wandered the least, five that wandered the most, SHUFFLED, each stopped at the dip, no number
shown, nothing he has already graded. He taps only the ones he would not trade. If his taps land on the wandering
ones, the measure is his eye and the cut goes where his taps fall. If they do not, it is mine alone and it goes.

    pythonw pics_messymark.py --procs 8 --log logs/pics_messymark.log
Writes validation/messy_mark/*.png + index.json  (the number is in "hidden", never shown until he has marked)
"""
import concurrent.futures as cf
import glob as _glob
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_cleanrun as CR        # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "messy_mark")
N_EACH = 5
RUN_MIN, RUN_MAX = 5.6, 7.5   # every chart is a BIG run AND the two groups are matched on it, so the only
                              # thing that differs is the wandering. First try had the straight ones on runs of
                              # 6-10 and the wandering ones 5.7-6.8: the same confound again, one step smaller.
SEEN_NAMES = {"ENB", "HNT", "CHTR", "XLK", "GLW", "COF", "HLT", "AR", "FCX", "DHR",     # the first ten he marked
              "BTI", "KEY", "DOCN", "BHP", "UNP", "LYV", "ALAB", "BTC", "FDX", "FIX"}          # names he has already ruled on


def _one(args):
    sym, kind = args
    try:
        return [dict(sym=sym, kind=kind, k=r["k"], t=r["t"], wander=r["chop"], run=r["run"])
                for r in PB.trades_for(sym, kind) if r.get("chop") is not None and r.get("run") is not None]
    except Exception:
        return []


def _draw(args):
    sym, kind, picks = args
    out = []
    for p in picks:
        png = "%02d_%s_%s_%d.png" % (p["n"], kind, sym, p["k"])
        try:
            probs, _m = CR.draw(sym, kind, p["k"], p["t"], os.path.join(OUT, png))
            out.append(dict(p, png=png, problems=probs))
        except Exception as ex:
            out.append(dict(p, png=png, problems=["draw: %s" % ex]))
    return out


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = io.open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT]
    R.quiet_workers()
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got in ex.map(_one, names, chunksize=4):
            rows += got
    # never make him grade a trade he has already seen (#41: "why do we keep looking at the same trades")
    seen = set()
    for g_ in sorted(_glob.glob(os.path.join("validation", "trade_notes_*.csv"))):
        for ln in io.open(g_, encoding="utf-8").read().splitlines()[1:]:
            seen.add(ln.split(",")[0])
    rows = [r for r in rows if "%s_%s_%d.png" % (r["kind"], r["sym"], r["k"]) not in seen]
    print("  %d runs to choose from, none of them graded before  (%.0fs)" % (len(rows), time.time() - t0), flush=True)

    f = pd.DataFrame(rows).sort_values("wander")
    # one trade per NAME, so ten different charts rather than ten dips in the same stock
    f = f.groupby("sym", as_index=False).first().sort_values("wander")
    # ROUND 1 WAS NOT A TEST OF WANDERING AT ALL, and he caught it: "many of the ones you showed me just had chill
    # uptrends not big runups". Every chart he kept had a run of 5.6+ and every one he rejected 5.4 or less, so run
    # size and wandering moved together and the marks cannot tell them apart. EVERY CHART NOW HAS A BIG RUN, so
    # wandering is the only thing that differs -- his own one-variable rule, which I broke.
    # and not the same NAME twice either: HLT ("kind of unsure about the 6") and LYV (the megaphone he threw out on
    # /cleanruns) both came back on a different bar. A name he has ruled on is a name he should not be shown again.
    rng = np.random.default_rng(20260922)
    f = f[(f.run >= RUN_MIN) & (f.run <= RUN_MAX)]
    f = f[~f.sym.isin(SEEN_NAMES)]
    print("  %d runs between %.1f and %.1f normal bars to choose from" % (len(f), RUN_MIN, RUN_MAX))
    low = f[f.wander <= 2.5].sample(N_EACH, random_state=3)
    high = f[f.wander >= 4.5].sample(N_EACH, random_state=3)
    picks = pd.concat([low, high]).to_dict("records")
    order = rng.permutation(len(picks))
    picks = [dict(picks[j], n=i + 1) for i, j in enumerate(order)]
    print("  wandered least: %s" % ", ".join("%s %.1f (run %.1f)" % (p["sym"], p["wander"], p["run"]) for p in sorted(picks, key=lambda x: x["wander"])[:N_EACH]))
    print("  wandered most:  %s" % ", ".join("%s %.1f (run %.1f)" % (p["sym"], p["wander"], p["run"]) for p in sorted(picks, key=lambda x: -x["wander"])[:N_EACH]))

    by = {}
    for p in picks:
        by.setdefault((p["sym"], p["kind"]), []).append(p)
    drawn = []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by))) as ex:
        for got in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got
    drawn = [d for d in drawn if not d["problems"] or "draw:" not in str(d["problems"])]
    drawn.sort(key=lambda x: x["n"])
    keep = {d["png"] for d in drawn} | {"index.json"}
    for fn in os.listdir(OUT):
        if fn not in keep and os.path.isfile(os.path.join(OUT, fn)):
            os.remove(os.path.join(OUT, fn))

    def plain(v):
        return v.item() if hasattr(v, "item") else v
    charts = [dict(n=int(d["n"]), sym=d["sym"], kind=d["kind"], k=int(d["k"]), t=str(d["t"]), png=d["png"],
                   problems=d["problems"], hidden=dict(wander=float(plain(d["wander"])), run=float(plain(d["run"])))) for d in drawn]
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), charts=charts),
              io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d in drawn if d["problems"]), time.time() - t0))
    for d in drawn:
        print("    #%-2d %-6s %s  %s" % (d["n"], d["sym"], str(d["t"])[:10], d["problems"] or ""))


if __name__ == "__main__":
    main()
