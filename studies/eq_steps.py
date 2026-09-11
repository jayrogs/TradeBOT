"""eq_steps.py -- does the spacing of an EQ's higher lows and lower highs call which way it goes? (2026-09-11)

His words: "check the distance and size bw HL and Lh's, if there some calculatable edge on how closer higher lows are or
lower highs, and the likelihood of them breaking up or down". And on what counts as right: "we arent trying to have
perfect eq breaks with massive follwo through, we are trying to establish a position on a slightly larger timeframe. it
doesnt have to have immediate follow through."

Measured at the moment the EQ becomes knowable (its last pivot confirmed), from its own higher lows and lower highs:
    lean        how fast the higher lows rise against how fast the lower highs drop, per step, -1 .. +1
                (+1 = only the lows rising, a flat top; -1 = only the highs dropping, a flat bottom)
    last_lean   the same for the last step only
    time_lean   bars between the higher lows against bars between the lower highs, -1 .. +1
                (+ = the higher lows come closer together in time)
    where       where price sits inside the EQ at that moment (0 = on the floor, 1 = on the ceiling)
    last_pivot  whether the last pivot was a higher low or a lower high
What came next, two ways:
    the first break  which line the first wick went through (the old way, kept for comparison)
    the position     price 4, 8 and 24 HOURLY bars after buying the next open, in this chart's normal bars (+ = up).
                     Same clock on every chart: 4 hourly bars = 48 5m bars = 16 15m bars = 4 1h bars.
Every EQ counts (pivots 3+ bars apart, the strict shape), stocks and ETFs on regular hours. Three eras.

    pythonw studies/eq_steps.py --procs 20 --log logs/eq_steps.log
Writes validation/eq_steps.json
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
import trend_ride as R            # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_steps.json")
TFS = ["5m", "15m", "1h"]
BPH = {"5m": 12, "15m": 4, "1h": 1}              # bars in one hourly bar
LOOKS = [4, 8, 24]                               # hourly bars later
ERAS = ["before", "first", "second"]
BINS = [(-9.0, -0.5), (-0.5, -0.15), (-0.15, 0.15), (0.15, 0.5), (0.5, 9.0)]
LEAN_NAMES = ["lower highs dropping much faster", "lower highs dropping a bit faster", "about even",
              "higher lows rising a bit faster", "higher lows rising much faster"]
TIME_NAMES = ["lower highs much closer together", "lower highs a bit closer together", "about even",
              "higher lows a bit closer together", "higher lows much closer together"]
COLS = ["tf", "era", "sgn", "lean", "last_lean", "time_lean", "where", "width", "last_pivot", "rise", "drop"] + \
       ["mv%d" % x for x in LOOKS]


def features(r, c, atr):
    """The spacing of one EQ's higher lows and lower highs, as they stood when it became knowable."""
    sh = r.get("shape") or []
    lows = [(j, p) for j, p, kd, lab in sh if kd == "low"]
    highs = [(j, p) for j, p, kd, lab in sh if kd == "high"]
    m = r["confirm"]
    a = atr[m] if np.isfinite(atr[m]) and atr[m] > 0 else np.nan
    if len(lows) < 2 or len(highs) < 2 or not np.isfinite(a):
        return None
    rise = (lows[-1][1] - lows[0][1]) / (len(lows) - 1) / a          # normal bars per step
    drop = (highs[0][1] - highs[-1][1]) / (len(highs) - 1) / a
    rp, dp = max(rise, 0.0), max(drop, 0.0)
    lean = (rp - dp) / (rp + dp) if rp + dp > 1e-9 else 0.0
    lr = max((lows[-1][1] - lows[-2][1]) / a, 0.0)
    ld = max((highs[-2][1] - highs[-1][1]) / a, 0.0)
    last_lean = (lr - ld) / (lr + ld) if lr + ld > 1e-9 else 0.0
    gl = (lows[-1][0] - lows[0][0]) / (len(lows) - 1)
    gh = (highs[-1][0] - highs[0][0]) / (len(highs) - 1)
    time_lean = (gh - gl) / (gh + gl) if gh + gl > 0 else 0.0
    f, ce = lows[-1][1], highs[-1][1]
    return dict(lows_rise=float(rise), highs_drop=float(drop), lean=float(lean), last_lean=float(last_lean),
                low_gap_bars=float(gl), high_gap_bars=float(gh), time_lean=float(time_lean),
                where=float((c[m] - f) / (ce - f)) if ce > f else 0.5, width=float((ce - f) / a),
                last_pivot=1 if sh[-1][2] == "low" else -1)


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
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            n = len(c)
            floor, ceil, cid, recs, atr = EC.coils(df, min_gap=3)
            for r in recs:
                if not r["tradeable"] or r["born"] < 60 or r["confirm"] + 1 >= n:
                    continue
                ft = features(r, c, atr)
                if ft is None:
                    continue
                how = str(r["how"])
                sgn = 1 if ("ceiling" in how or "higher high" in how) else -1 if ("floor" in how or "lower low" in how) else 0
                m = r["confirm"]
                a = atr[m]
                entry = o[m + 1]
                mv = []
                for H in LOOKS:
                    j = m + 1 + H * BPH[tf]
                    mv.append((c[j] - entry) / a if j < n else np.nan)
                t = df.index[m]
                era = 0 if t < start else 1 if t < mid_t else 2
                rows.append([tf_i, era, sgn, ft["lean"], ft["last_lean"], ft["time_lean"], ft["where"], ft["width"],
                             ft["last_pivot"], ft["lows_rise"], ft["highs_drop"]] + mv)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float32), errs


def stats(g):
    if len(g) < 100:
        return None
    poked = g[g.sgn != 0]
    d = dict(n=int(len(g)), broke_up=float((poked.sgn > 0).mean()) if len(poked) else None)
    for H in LOOKS:
        v = g["mv%d" % H].dropna()
        d["higher_after_%d" % H] = float((v > 0).mean()) if len(v) else None
        d["avg_move_%d" % H] = float(v.mean()) if len(v) else None
        d["median_move_%d" % H] = float(v.median()) if len(v) else None
    return d


def with_eras(g):
    s = stats(g)
    if s:
        s["eras"] = {ERAS[e]: stats(g[g.era == e]) for e in range(3)}
    return s


def groups(g):
    out = {"every EQ (the control)": g}
    for (lo, hi), nm in zip(BINS, LEAN_NAMES):
        out["spacing in price: " + nm] = g[(g.lean > lo) & (g.lean <= hi)]
    for (lo, hi), nm in zip(BINS, LEAN_NAMES):
        out["last step only: " + nm] = g[(g.last_lean > lo) & (g.last_lean <= hi)]
    for (lo, hi), nm in zip(BINS, TIME_NAMES):
        out["spacing in time: " + nm] = g[(g.time_lean > lo) & (g.time_lean <= hi)]
    out["both: higher lows rising faster AND closer together"] = g[(g.lean > 0.15) & (g.time_lean > 0.15)]
    out["both: lower highs dropping faster AND closer together"] = g[(g.lean < -0.15) & (g.time_lean < -0.15)]
    out["price in the top third of the EQ"] = g[g["where"] > 2 / 3]
    out["price in the middle third"] = g[(g["where"] >= 1 / 3) & (g["where"] <= 2 / 3)]
    out["price in the bottom third"] = g[g["where"] < 1 / 3]
    out["last pivot a higher low"] = g[g.last_pivot > 0]
    out["last pivot a lower high"] = g[g.last_pivot < 0]
    return out


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
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    table = {}
    print("\n  EQ SPACING: HIGHER LOWS VS LOWER HIGHS  %d names, %d EQs  (%.0fs)" % (len(names), len(f), time.time() - t0))
    for tf_i, tf in enumerate(TFS):
        g = f[f.tf == tf_i]
        table[tf] = {}
        print("\n  %s  (%d EQs)" % (tf, len(g)))
        print("    %-58s %7s %6s %6s %6s %6s %6s %6s   eras: broke up / higher after 24" % (
            "group", "n", "up", "hi4", "hi8", "hi24", "avg24", "mid24"))
        for nm, gg in groups(g).items():
            s = with_eras(gg)
            if not s:
                continue
            table[tf][nm] = s
            eras = "  ".join(("%2.0f/%2.0f" % (100 * (e["broke_up"] or 0), 100 * (e["higher_after_24"] or 0))) if e
                             else " -/- " for e in (s["eras"].get(er) for er in ERAS))
            print("    %-58s %7d %5.0f%% %5.0f%% %5.0f%% %5.0f%% %+6.2f %+6.2f   %s" % (
                nm, s["n"], 100 * (s["broke_up"] or 0), 100 * (s["higher_after_4"] or 0), 100 * (s["higher_after_8"] or 0),
                100 * (s["higher_after_24"] or 0), s["avg_move_24"] or 0, s["median_move_24"] or 0, eras))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         looks_hourly_bars=LOOKS, bins=BINS, rows=int(len(f)), min_gap=3,
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         moves="in this chart's normal bars, from the next bar's open", seconds=int(time.time() - t0)),
               table=table)
    json.dump(res, open(OUT, "w"))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
