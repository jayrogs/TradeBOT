"""eq_his_trade.py -- his EQ trade, his management, every name (2026-09-11).

The rules he laid out over 2026-09-11, put together and run on all 809 names instead of the 30 he marked:

    direction   the way the HOURLY leans: up if the hourly is in an uptrend or price is over its 12 EMA, else down
    lined up    and the EQ sits IN that hourly pullback: its floor at the hourly 12 EMA (within half a normal hourly
                bar) or within one normal hourly bar above the hourly's last swing low. His words: the runner is only
                for "something thats lined up nicely to have an entry for a larger timeframe".
    entry       the next open after the EQ becomes knowable; no trade if that open is already outside the EQ
    stop        the EQ's far side, or the hourly higher low (hourly sized)
    partial     half at the EQ's far line, half at 1x the risk, or none ("locking in some partial to have security")
    sell        the rest at 2x the risk or at the hourly's last swing high ("once it makes the move, just sell")
    controls    all out at the far line; hold 24 hourly bars; and the SAME plans on EQs that are NOT lined up

Split by lined up / not, by chart, and over the three eras. Costs 0.2% round trip on crypto, 0.05% elsewhere.

    pythonw studies/eq_his_trade.py --procs 20 --log logs/eq_his_trade.log
Writes validation/eq_his_trade.json
"""
import concurrent.futures as cf
import itertools
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import trend_ride as R            # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_direction as ED         # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402
import eq_managed as MG           # noqa: E402

OUT = os.path.join("validation", "eq_his_trade.json")
TFS = ["5m", "15m"]
ERAS = ["before", "first", "second"]
PLANS = [("EQ's far side", "half at the EQ's far line", "2x the risk"),
         ("EQ's far side", "none", "2x the risk"),
         ("the hourly higher low", "half at the EQ's far line", "the hourly's last swing high"),
         ("the hourly higher low", "half at 1x the risk", "the hourly's last swing high"),
         ("the hourly higher low", "none", "the hourly's last swing high"),
         ("the hourly higher low", "half at 1x the risk", "2x the risk")]
NAMES = ["stop %s, %s, sell the rest at %s" % p for p in PLANS] + \
        ["all out at the EQ's far line", "hold 24 hourly bars (the old way)"]


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for tf_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            c = df["Close"].values.astype(float)
            n = len(c)
            recs = EC.coils(df, min_gap=3)[3]
            if not recs:
                continue
            h1lo, h1hi = ED.last_swings(df, tf, frames, "1h")
            hdf = frames.get("1h")
            if hdf is None or len(hdf) < 60:
                continue
            al = FR.align(df, tf, hdf, "1h", P._atr(hdf).astype(object))
            h1atr = np.array([np.nan if isinstance(x, str) else float(x) for x in al], dtype=float)
            state = EF.higher_state(df, tf, frames, "1h")
            ev = ER.above12(df, tf, frames, "1h")[1]
            for r in recs:
                if not r["tradeable"] or r["born"] < 60 or r["confirm"] + 2 >= n:
                    continue
                e = r["confirm"] + 1
                up = str(state[e]) == "up" or (np.isfinite(ev[e]) and c[e] > ev[e])
                down = str(state[e]) == "down" or (np.isfinite(ev[e]) and c[e] < ev[e])
                if up == down:
                    continue
                side = 1 if up else -1
                lows_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "low"]
                highs_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "high"]
                ha = h1atr[e]
                lined = False
                if np.isfinite(ha) and ha > 0:
                    line = lows_[-1] if side > 0 else highs_[-1]
                    sw = h1lo[e] if side > 0 else h1hi[e]
                    lined = (np.isfinite(ev[e]) and abs(line - ev[e]) <= 0.5 * ha) or \
                            (np.isfinite(sw) and ((side > 0 and sw < line <= sw + ha) or
                                                  (side < 0 and sw - ha <= line < sw)))
                t_ = df.index[e]
                era = 0 if t_ < start else 1 if t_ < mid_t else 2
                out = [tf_i, era, 1 if lined else 0]
                for stop_k, part_k, sell_k in PLANS:
                    t = MG.one_trade(MG.STOPS[stop_k], MG.PARTIALS[part_k], MG.SELLS[sell_k],
                                     tf, kind, df, r, side, h1lo, h1hi, h1atr)
                    out.append(np.nan if (t is None or t["pct"] is None) else t["pct"])
                for kd in ("far", "hold"):
                    t = MG.simple(kd, tf, kind, df, r, side)
                    out.append(np.nan if (t is None or t["pct"] is None) else t["pct"])
                rows.append(out)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float32), errs


def stats(v):
    v = v[np.isfinite(v)]
    if len(v) < 50:
        return None
    return dict(n=int(len(v)), avg=float(v.mean()), middle=float(np.median(v)),
                won=float((v > 0).mean()), worst=float(v.min()))


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if part is not None:
                parts.append(part)
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    f = np.concatenate(parts)
    table = {}
    for tf_i, tf in enumerate(TFS + ["both"]):
        g = f if tf == "both" else f[f[:, 0] == tf_i]
        table[tf] = {}
        for lined, lname in ((1, "lined up for the hourly"), (0, "not lined up"), (None, "every EQ")):
            gg = g if lined is None else g[g[:, 2] == lined]
            table[tf][lname] = {}
            for k, name in enumerate(NAMES):
                s = stats(gg[:, 3 + k])
                if not s:
                    continue
                s["eras"] = {ERAS[e]: stats(gg[gg[:, 1] == e][:, 3 + k]) for e in range(3)}
                table[tf][lname][name] = s
    json.dump(dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                             tfs=TFS, plans=NAMES, cost=MG.COST, rows=int(len(f)),
                             seconds=int(time.time() - t0)), table=table), open(OUT, "w"))
    print("\n  HIS EQ TRADE, HIS MANAGEMENT, %d names, %d EQs  (%.0fs)" % (len(names), len(f), time.time() - t0))
    for tf in TFS + ["both"]:
        print("\n  %s" % tf)
        for lname in ("lined up for the hourly", "not lined up", "every EQ"):
            print("   %s" % lname)
            print("     %-66s %7s %8s %8s %5s   eras (average)" % ("plan", "n", "avg", "middle", "won"))
            for name in NAMES:
                s = table[tf][lname].get(name)
                if not s:
                    continue
                eras = "  ".join(("%+5.2f" % e["avg"]) if e else "  -  " for e in (s["eras"].get(x) for x in ERAS))
                print("     %-66s %7d %+7.3f%% %+7.3f%% %4.0f%%   %s" % (
                    name, s["n"], s["avg"], s["middle"], 100 * s["won"], eras))
    for e_ in errs[:15]:
        print("  ERR " + e_)
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
