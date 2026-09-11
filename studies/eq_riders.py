"""eq_riders.py -- his mentor's rules on the 5m / 15m EQ (2026-09-11). Rules from TCG_METHOD.md.

@junglefunk_ (Joey Hayes, The Chart Guys):
  "12ema riders from the 5min up, once you get through one you have to battle the next."
  "15min bounces underway ... Will need to get over 15min 12ema and secure uptrend for anything to stick."
  "EMA rider zoom out game ... hourly --> 4hr -- daily ... The smaller the timeframe HL you go for, the more aggressive."
  "I only really give a pattern credence if it is at location and within the multiple-time-frame most likely scenario.
   Without proper location, patterns are not that valuable, 50/50 at best."
TCG stop article: walk the stop up under the last higher low; or ride the 12 EMA and exit on a candle closing under it.

So, for every 5m and 15m EQ (same entry as /eqfree: the next open after a higher low / lower high confirms inside it,
stop a wick through that pivot):
  THE 12 EMA RIDERS ABOVE (the direction). The next three chart sizes up: a 5m EQ reads 15m, 1h, 4h; a 15m EQ reads 1h,
  4h, daily. Each says up when price is over a rising 12 EMA there, down when under a falling one (last CLOSED bar).
      the next chart up only / the next two agree / two of the three / all three
      plus this chart's own 12 EMA, and "every trade" (no read) for comparison
  LOCATION. The EQ's line on the trade's side (the floor for a long, the ceiling for a short) sits within half a normal
  bar of one of those 12 EMAs: "at a bigger 12 EMA". Otherwise "open space".
  MANAGEMENT, his way:
      half at the far line, rest to breakeven
      all out at the far line
      half at the far line, runner out on a close through THIS chart's 12 EMA (the TCG EMA exit)
      half at the far line, runner's stop walked up under each new higher low (the TCG stair step stop)
      half at the far line, runner out on a close through the NEXT chart up's 12 EMA ("zoom out game once each is lost")
Every result: average and middle trade, edge over the chart's drift, three eras, every trade and far line >= 1x the risk.
Also: which way the EQ breaks, by those reads and by location.
Stocks and ETFs on regular-hours bars; crypto and futures all hours.

    pythonw studies/eq_riders.py --procs 20 --log logs/eq_riders.log
Writes validation/eq_riders.json
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
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_riders.json")
TFS = ["5m", "15m"]
ABOVE = {"5m": ["15m", "1h", "4h"], "15m": ["1h", "4h", "1d"]}
NEAR = 0.5                                     # "at location": within half a normal bar of a bigger chart's 12 EMA
MANAGE = [("half at the far line, rest to breakeven", "half"),
          ("all out at the far line", "all"),
          ("half at the far line, runner out on a close through this chart's 12 EMA", "ema"),
          ("half at the far line, runner stop walked up under each higher low", "steps"),
          ("half at the far line, runner out on a close through the next chart up's 12 EMA (zoom out)", "zoom")]
READS = [("every", "every trade, no read (both ways)"),
         ("own12", "this chart's 12 EMA"),
         ("next1", "the next chart up's 12 EMA"),
         ("first2", "the next two charts up agree"),
         ("two_of_3", "two of the next three charts up"),
         ("all3", "all three charts up agree")]
TAGS = ["with", "against", "no call"]
LOCS = ["at a bigger 12 EMA", "open space"]
RRB = ["far line under 1x", "far line 1x or more"]
ERAS = ["before", "first", "second"]
DIMS = [("tf", TFS), ("manage", [m[0] for m in MANAGE]), ("read", [r[0] for r in READS]), ("tag", TAGS),
        ("loc", LOCS), ("rr", RRB), ("era", ERAS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def ema12_read(close):
    e = XM.ema(close, 12)
    prev = np.r_[np.full(3, np.nan), e[:-3]]
    sl = e - prev
    lab = np.where((close > e) & (sl > 0), "up", np.where((close < e) & (sl < 0), "down", "none")).astype(object)
    lab[~np.isfinite(sl)] = "none"
    return lab, e


def above12(df, tf, frames, htf):
    n = len(df)
    hdf = frames.get(htf)
    if hdf is None or len(hdf) < 60:
        return np.array(["none"] * n, dtype=object), np.full(n, np.nan)
    lab, e = ema12_read(hdf["Close"].values.astype(float))
    st = FR.align(df, tf, hdf, htf, lab)
    st[st == "NA"] = "none"
    ev = FR.align(df, tf, hdf, htf, e.astype(object))
    evf = np.array([np.nan if isinstance(x, str) else float(x) for x in ev], dtype=float)
    return st, evf


def walk3(sgn, c, o, h, l, atr, ema, e, fill, stop, target, n, cap, day, mode, lows_at, highs_at):
    """Half at the far line, stop to breakeven; then the runner leaves on a close through this chart's 12 EMA
    ("ema"), or its stop is walked up under each new higher low / down over each new lower high ("steps").
    Stop checked first on every bar. Returns (exit bar, exit price for the whole position, reached the far line)."""
    if abs(fill - stop) <= 0 or abs(target - fill) <= 0:
        return None
    share = 0.5
    took = False
    stop_now = stop
    for k in range(e, n - 1):
        if (sgn > 0 and l[k] < stop_now) or (sgn < 0 and h[k] > stop_now):
            px = o[k + 1]
            return k, (share * target + (1 - share) * px) if took else px, took
        if not took and ((sgn > 0 and h[k] >= target) or (sgn < 0 and l[k] <= target)):
            took = True
            stop_now = fill
        if took:
            if mode in ("ema", "zoom") and np.isfinite(ema[k]):
                if (sgn > 0 and c[k] < ema[k]) or (sgn < 0 and c[k] > ema[k]):
                    return k, share * target + (1 - share) * o[k + 1], True
            if mode == "steps":
                tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
                if sgn > 0:
                    for p in lows_at.get(k, ()):
                        stop_now = max(stop_now, p - tol)
                else:
                    for p in highs_at.get(k, ()):
                        stop_now = min(stop_now, p + tol)
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, (share * target + (1 - share) * c[k]) if took else c[k], took
        if k - e >= cap:
            px = o[k + 1]
            return k, (share * target + (1 - share) * px) if took else px, took
    return None


def break_dir(how):
    how = str(how)
    if "ceiling" in how or "higher high" in how:
        return "up"
    if "floor" in how or "lower low" in how:
        return "down"
    return None


def _work(args):
    sym, kind, start = args
    try:
        all_frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = FR2.regular_hours(all_frames) if kind in ("stock", "etf") else all_frames
    codes, rets, drifts, tooks = [], [], [], []
    brk = {}
    errs = []
    cost = B.CLASS_COST.get(kind, B.COST)
    for tf_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            own, own_e = ema12_read(c)
            rs_ = [above12(df, tf, frames, htf) for htf in ABOVE[tf]]
            up_st = [x[0] for x in rs_]; up_ev = [x[1] for x in rs_]
            floor, ceil, cid, recs, atr = EC.coils(df, min_gap=0)
            piv = ST.pivots(df)
            lows_at, highs_at = {}, {}
            for ci, j, p, kd, lab in piv:
                if kd == "low" and lab in ("HL", "EL"):
                    lows_at.setdefault(ci, []).append(float(p))
                elif kd == "high" and lab in ("LH", "EH"):
                    highs_at.setdefault(ci, []).append(float(p))
            cap = FR2.CAP_DAYS * B.BARS_DAY[tf]
            day = df.index.normalize().values if kind in ("stock", "etf") else None
            lr = np.diff(np.log(c), prepend=np.log(c[0]))
            drift = float(np.nanmean(lr[np.isfinite(lr)]))

            def reads_at(k):
                a = [str(up_st[0][k]), str(up_st[1][k]), str(up_st[2][k])]
                ups, dns = a.count("up"), a.count("down")
                return {"own12": str(own[k]), "next1": a[0],
                        "first2": a[0] if (a[0] == a[1] and a[0] != "none") else "none",
                        "two_of_3": "up" if ups >= 2 else "down" if dns >= 2 else "none",
                        "all3": "up" if ups == 3 else "down" if dns == 3 else "none"}

            def near(line, k):
                a = atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else np.nan
                if not (np.isfinite(line) and np.isfinite(a)):
                    return False
                return any(np.isfinite(ev[k]) and abs(line - ev[k]) <= NEAR * a for ev in up_ev)

            # which way it breaks
            for r in recs:
                if not r["tradeable"] or r["born"] < 60:
                    continue
                d = break_dir(r["how"])
                if d is None:
                    continue
                i = r["confirm"]
                vals = reads_at(i)
                fl, cl = near(floor[i], i), near(ceil[i], i)
                where = ("both lines on a bigger 12 EMA" if fl and cl else "floor on a bigger 12 EMA" if fl
                         else "ceiling on a bigger 12 EMA" if cl else "open space")
                for key in [(tf, "read", k, v) for k, v in vals.items()] + [(tf, "where", where, "")]:
                    cell = brk.setdefault(key, [0, 0]); cell[0] += 1; cell[1] += 1 if d == "up" else 0

            # the trade
            for x in FR2.trades(kind, tf, df, all_frames, start, 0, modes=[FR2.MODES[2][0]]):
                e = x["e"]; ci = e - 1
                sgn = 1 if x["side"] == "long" else -1
                fill, stop, target = x["fill"], x["stop"], x["target"]
                line = floor[ci] if sgn > 0 else ceil[ci]
                loc_i = 0 if near(line, ci) else 1
                rr_i = 1 if x["rr"] >= 1.0 else 0
                vals = reads_at(ci)
                vals["every"] = "up" if sgn > 0 else "down"
                outs = []
                for m_i, (_, mode) in enumerate(MANAGE):
                    if mode in ("half", "all"):
                        res = FR2.walk2(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, day, mode)
                        res = None if res is None else (res[0], res[1], res[2])
                    else:
                        guide = up_ev[0] if mode == "zoom" else own_e
                        res = walk3(sgn, c, o, h, l, atr, guide, e, fill, stop, target, n, cap, day, mode, lows_at, highs_at)
                    if res is None:
                        outs.append(None); continue
                    xb, px, took = res
                    held = xb + 1 - e
                    outs.append((sgn * (px / fill - 1) - cost, sgn * (np.exp(drift * held) - 1) - cost, took))
                for r_i, (rk, _) in enumerate(READS):
                    t = FR.tag(x["side"], vals[rk])
                    t_i = 2 if t == "no trend" else TAGS.index(t)
                    for m_i, out in enumerate(outs):
                        if out is None:
                            continue
                        codes.append(encode([tf_i, m_i, r_i, t_i, loc_i, rr_i, x["era_i"]]))
                        rets.append(out[0]); drifts.append(out[1]); tooks.append(1 if out[2] else 0)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not codes and not brk:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32),
            np.asarray(drifts, dtype=np.float32), np.asarray(tooks, dtype=np.int8), brk), errs


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
    parts, errs, done, brk = [], [], 0, {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if part is not None:
                parts.append(part[:4])
                for key, (n_, u_) in part[4].items():
                    cell = brk.setdefault(key, [0, 0]); cell[0] += n_; cell[1] += u_
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)

    breaks = {}
    for (tf, group, k, v), (n_, u_) in brk.items():
        breaks.setdefault(tf, {}).setdefault(group, {}).setdefault(k, {})[v or "all"] = dict(n=n_, broke_up=u_ / n_ if n_ else None)

    code = np.concatenate([p[0] for p in parts]).astype(np.int64)
    f = pd.DataFrame({"ret": np.concatenate([p[1] for p in parts]).astype(float),
                      "drift": np.concatenate([p[2] for p in parts]).astype(float),
                      "took": np.concatenate([p[3] for p in parts]).astype(float)})
    rem = code
    for (name, vals), size in reversed(list(zip(DIMS, SIZES))):
        f[name] = (rem % size).astype(np.int16)
        rem = rem // size
    f["won"] = (f.ret > 0).astype(float)
    f["edge"] = f.ret - f.drift
    print("  %d trade rows, folding  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    base = ["tf", "manage", "read", "tag"]
    names_of = dict(DIMS)
    trades = {}
    for rr_name, s1 in (("every trade", f), ("far line 1x or more", f[f.rr == 1])):
        for loc_name, s2 in (("any location", s1), (LOCS[0], s1[s1["loc"] == 0]), (LOCS[1], s1[s1["loc"] == 1])):
            for keys in (base, base + ["era"]):
                agg = s2.groupby(keys).agg(n=("ret", "size"), mean=("ret", "mean"), median=("ret", "median"),
                                           edge=("edge", "mean"), won=("won", "mean"), reached=("took", "mean"))
                for k, row in agg.iterrows():
                    if row["n"] < 30:
                        continue
                    lab = [names_of[c_][int(v)] for c_, v in zip(keys, k)]
                    era = lab[4] if len(keys) == 5 else "all"
                    trades[" | ".join(lab[:4] + [loc_name, rr_name, era])] = dict(
                        n=int(row["n"]), mean=float(row["mean"]), median=float(row["median"]), edge=float(row["edge"]),
                        won=float(row["won"]), reached=float(row["reached"]))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         above=ABOVE, manage=[m[0] for m in MANAGE], reads=[r[0] for r in READS],
                         read_names=dict(READS), tags=TAGS, locs=["any location"] + LOCS,
                         rr=["every trade", "far line 1x or more"], eras=["all"] + ERAS, near=NEAR, rows=int(len(f)),
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         seconds=int(time.time() - t0)),
               breaks=breaks, trades=trades)
    json.dump(res, open(OUT, "w"))

    print("\n  HIS 12 EMA RIDERS ON THE FAST EQ  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for tf in TFS:
        print("\n  %s EQs, which way they broke:" % tf)
        for k, row in sorted(breaks.get(tf, {}).get("read", {}).items()):
            up, dn = row.get("up"), row.get("down")
            print("    %-9s up call %5d -> %3.0f%% up    down call %5d -> %3.0f%% down" % (
                k, up["n"] if up else 0, 100 * (up["broke_up"] or 0) if up else 0,
                dn["n"] if dn else 0, 100 * (1 - (dn["broke_up"] or 0)) if dn else 0))
        for k, row in sorted(breaks.get(tf, {}).get("where", {}).items()):
            print("    %-30s %6d  %3.0f%% up" % (k, row["all"]["n"], 100 * (row["all"]["broke_up"] or 0)))
        for m_name, _ in MANAGE:
            print("   %s | %s, far line 1x or more (avg / middle / edge  n   eras avg/middle)" % (tf, m_name))
            for rk, _ in READS:
                for loc in ("any location", LOCS[0]):
                    t = trades.get("%s | %s | %s | with | %s | far line 1x or more | all" % (tf, m_name, rk, loc))
                    if not t:
                        continue
                    eras = "  ".join(("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"])) if e else "   -   "
                                     for e in (trades.get("%s | %s | %s | with | %s | far line 1x or more | %s" % (tf, m_name, rk, loc, er)) for er in ERAS))
                    print("     %-9s %-20s %+6.2f / %+6.2f / %+6.2f  n%-6d  %s" % (
                        rk, loc, 100 * t["mean"], 100 * t["median"], 100 * t["edge"], t["n"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
