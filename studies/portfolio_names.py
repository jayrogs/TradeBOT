"""portfolio_names.py -- which NAMES play best under the trend ride, judged the way he asked
(2026-09-08): per day of the trade, not per trade, and against just holding that same name.

Reads validation/portfolio_trades.csv.gz (from portfolio.py) and adds, per name and chart:
    days           how long a trade lasts, in calendar days
    trades_a_year  how many signals this name gives in a year
    busy_days      days a year this name would actually hold your money (the rest is idle)
    a_year         one unit of money dedicated to THIS NAME ONLY: its trades compounded,
                   idle cash earning nothing. NOT stretched over days it was not in a trade.
    hold_a_year    what just holding the name made over the same 4 years
    edge           a_year minus hold_a_year: does TRADING it beat OWNING it
    both_halves    same sign in the first and second half of the window (the honesty check)

    pythonw studies/portfolio_names.py --procs 20 --log logs/portfolio_names.log

Writes validation/portfolio_names.json (and _focus).
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402

MIN_TRADES = 12                   # below this a name's number is noise
OUT = os.path.join("validation", "portfolio_names.json")
CSV = os.path.join("validation", "portfolio_trades.csv.gz")


def hold_rate(args):
    """What buying and holding this name made per calendar day over the window."""
    sym, kind, start, end = args
    try:
        df = B.frames_for(sym, kind).get("1d")
    except Exception:
        return sym, kind, None
    if df is None:
        return sym, kind, None
    d = df[(df.index >= start) & (df.index <= end)]
    if len(d) < 100:
        return sym, kind, None
    c = d["Close"].values.astype(float)
    days = max((d.index[-1] - d.index[0]).days, 1)
    return sym, kind, float((c[-1] / c[0]) ** (1 / days) - 1)


def main():
    procs = max(1, os.cpu_count() or 4)
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    global OUT, CSV
    if "--focus" in sys.argv:
        OUT = OUT.replace(".json", "_focus.json"); CSV = CSV.replace(".csv.gz", "_focus.csv.gz")
    f = pd.read_csv(CSV, parse_dates=["t_in", "t_out"])
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    end = pd.Timestamp.now().normalize()
    f = f[(f.t_in >= start) & (f.t_out <= end) & (f.days > 0)]
    mid = start + (end - start) / 2
    f["half"] = np.where(f.t_in < mid, "first", "second")

    pairs = sorted(set(zip(f.sym, f.kind)))
    holds = {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for sym, kind, r in ex.map(hold_rate, [(s_, k_, start, end) for s_, k_ in pairs], chunksize=4):
            if r is not None:
                holds[(sym, kind)] = r
    print("  %d names, hold rates for %d  (%.0fs)" % (len(pairs), len(holds), time.time() - t0), flush=True)

    rows = []
    for (sym, kind, tf), g in f.groupby(["sym", "kind", "tf"]):
        if len(g) < MIN_TRADES:
            continue
        days = float(g.days.mean())
        per_day = float(g.ret.mean() / days)
        halves = {}
        for h in ("first", "second"):
            gg = g[g.half == h]
            halves[h] = float(gg.ret.mean() / gg.days.mean()) if len(gg) >= 5 else None
        hr = holds.get((sym, kind))
        tpy = float(len(g) / ((end - start).days / 365.25))
        rows.append(dict(
            sym=sym, kind=kind, tf=tf, n=int(len(g)),
            days=round(days, 2), bars=round(float(g.bars.mean()), 1),
            ret=float(g.ret.mean()), win=float((g.ret > 0).mean()),
            worst=float(g.worst.mean()), per_day=per_day,
            # one unit of money dedicated to this name: only its own trades compound
            a_year=float((1 + float(g.ret.mean())) ** tpy - 1) if g.ret.mean() > -1 else None,
            busy_days=round(tpy * days, 1),
            trades_a_year=tpy,
            hold_a_year=float((1 + hr) ** 365.25 - 1) if hr is not None else None,
            first=halves["first"], second=halves["second"],
            both_halves=bool(halves["first"] is not None and halves["second"] is not None
                             and halves["first"] > 0 and halves["second"] > 0)))
    for r in rows:
        r["edge"] = (r["a_year"] - r["hold_a_year"]) if (r["a_year"] is not None and r["hold_a_year"] is not None) else None
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                         years=round((end - start).days / 365.25, 2), min_trades=MIN_TRADES,
                         rows=len(rows), seconds=int(time.time() - t0)), rows=rows)
    json.dump(res, open(OUT, "w"))

    d = pd.DataFrame(rows)
    for tf in ("1h", "4h", "1d"):
        for kind in ("stock", "etf", "crypto", "futures", "forex"):
            g = d[(d.tf == tf) & (d.kind == kind) & d.both_halves]
            if len(g) < 5:
                continue
            g = g.sort_values("edge", ascending=False).head(14)
            print()
            print("  %s, %s -- best by trading it vs owning it (both halves positive)" % (tf, kind))
            print("    %-8s %5s %6s %7s %8s %9s %9s %9s %6s" % ("name", "n", "days", "a yr", "a trade", "dedicated", "hold", "edge", "won"))
            for _, r in g.iterrows():
                print("    %-8s %5d %6.1f %6.1f %+7.2f%% %+8.0f%% %+8.0f%% %+8.0f%% %5.0f%%" % (
                    r["sym"], r["n"], r["days"], r["trades_a_year"], 100 * r["ret"], 100 * r["a_year"],
                    100 * r["hold_a_year"], 100 * r["edge"], 100 * r["win"]))
    print()
    print("  done (%.0fs)" % (time.time() - t0))


if __name__ == "__main__":
    main()
