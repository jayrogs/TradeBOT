"""eq_fastread.py -- what calls the direction of a 5m / 15m EQ? (2026-09-11)

His words after grading /eqfree: "theres definitely a lot more things to take into account on the 5 and 15m
than just a daily timeframe. thats like trying to base someones mood entirely on the phase of the moon ...
its just too far outside the scope. gotta help me figure out the idea. maybe use ema 12 somehow, try some
shit out".

So every read here sits CLOSE to the chart the EQ is on. For every EQ on the 5m, 15m (and the 1h, for
comparison), read each of these at the bar the EQ becomes knowable:
    this chart      price over a rising 12 EMA / under a falling one; the 12 EMA's slope alone; the 50 EMA;
                    the pivot trend
    next chart up   (15m for a 5m EQ, 1h for a 15m EQ, 4h for a 1h EQ) the 12 EMA, the 50 EMA, the pivot trend
    the 1h          its 50 EMA
    the session     price above / below the day's open
    inside the EQ   the line tested more holds, and it breaks against the trend it came from (#26c: 61% vs 44%)
    combinations    12 EMA here and next chart up agreeing; 12 EMA here and the inside read agreeing
    the daily 50 EMA, what the last round used, as the baseline
Two measures for each read:
    1. WHICH WAY THE EQ BREAKS when the read says up / down (first wick through a line, or a higher high /
       lower low), against the plain share that break up.
    2. THE TRADE taken in the read's direction: the same entry as /eqfree (next open after a higher low / lower
       high confirms inside the EQ, stop a wick through it), half at the far line + rest to breakeven, and
       all out at the far line; every trade and only far line >= 1x the risk; three eras; against drift.
Stocks and ETFs on regular-hours bars (his after-hours complaint); crypto and futures all hours.

    pythonw studies/eq_fastread.py --procs 20 --log logs/eq_fastread.log
Writes validation/eq_fastread.json
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
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_fastread.json")
TFS = ["5m", "15m", "1h"]
TOUCH = 0.25
VARIANTS = [FR2.MODES[1][0], FR2.MODES[2][0]]          # half at the far line, all out at the far line
READS = [
    ("daily50", "the daily 50 EMA (what the last round used)"),
    ("ema12", "this chart: price over a rising 12 EMA / under a falling 12 EMA"),
    ("ema12_slope", "this chart: the 12 EMA rising / falling"),
    ("ema50", "this chart: price over a rising 50 EMA / under a falling 50 EMA"),
    ("trend", "this chart: uptrend / downtrend (the pivots)"),
    ("ema12_up1", "next chart up: price over a rising 12 EMA / under a falling 12 EMA"),
    ("ema50_up1", "next chart up: price over a rising 50 EMA / under a falling 50 EMA"),
    ("trend_up1", "next chart up: uptrend / downtrend (the pivots)"),
    ("ema50_1h", "the 1 hour chart: price over a rising 50 EMA / under a falling 50 EMA"),
    ("day_open", "price above / below the day's open"),
    ("inside", "inside the EQ: the line tested more holds AND it breaks against the trend it came from"),
    ("inside_lean", "inside the EQ: either one of those two"),
    ("ema12_and_up1", "the 12 EMA here AND on the next chart up agree"),
    ("ema12_and_inside", "the 12 EMA here AND the inside read agree"),
]
READ_KEYS = [k for k, _ in READS]
TAGS = ["with", "against", "no call"]
RRB = ["far line under 1x", "far line 1x or more"]
ERAS = ["before", "first", "second"]
DIMS = [("tf", TFS), ("variant", VARIANTS), ("read", READ_KEYS), ("tag", TAGS), ("rr", RRB), ("era", ERAS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def ema_read(close, span, slope_bars, need_price=True):
    e = XM.ema(close, span)
    prev = np.r_[np.full(slope_bars, np.nan), e[:-slope_bars]]
    sl = e - prev
    if need_price:
        lab = np.where((close > e) & (sl > 0), "up", np.where((close < e) & (sl < 0), "down", "none"))
    else:
        lab = np.where(sl > 0, "up", np.where(sl < 0, "down", "none"))
    lab = lab.astype(object)
    lab[~np.isfinite(sl)] = "none"
    return lab


def state_read(states):
    s = np.asarray(states).astype(str)
    return np.where(s == "UP", "up", np.where(s == "DOWN", "down", "none")).astype(object)


def higher_ema(df, tf, frames, htf, span, slope_bars):
    hdf = frames.get(htf) if htf else None
    if hdf is None or len(hdf) < max(60, span):
        return np.array(["none"] * len(df), dtype=object)
    lab = ema_read(hdf["Close"].values.astype(float), span, slope_bars)
    out = FR.align(df, tf, hdf, htf, lab)
    out[out == "NA"] = "none"
    return out


def higher_state(df, tf, frames, htf):
    hdf = frames.get(htf) if htf else None
    if hdf is None or len(hdf) < 60:
        return np.array(["none"] * len(df), dtype=object)
    out = FR.align(df, tf, hdf, htf, state_read(ST.states(hdf, causal=True)))
    out[out == "NA"] = "none"
    return out


def both(a, b):
    return np.where((a == b) & np.isin(a.astype(str), ["up", "down"]), a, "none").astype(object)


def bar_reads(df, tf, frames, all_frames):
    c = df["Close"].values.astype(float)
    up1 = R.UP.get(tf)
    rd = {}
    d50 = FR.ema_of(df, tf, all_frames, "1d")
    rd["daily50"] = np.where(np.isin(d50.astype(str), ["up", "down"]), d50, "none").astype(object)
    rd["ema12"] = ema_read(c, 12, 3)
    rd["ema12_slope"] = ema_read(c, 12, 3, need_price=False)
    rd["ema50"] = ema_read(c, 50, 10)
    states = ST.states(df, causal=True)
    rd["trend"] = state_read(states)
    rd["ema12_up1"] = higher_ema(df, tf, frames, up1, 12, 3)
    rd["ema50_up1"] = higher_ema(df, tf, frames, up1, 50, 10)
    rd["trend_up1"] = higher_state(df, tf, frames, up1)
    rd["ema50_1h"] = rd["ema50"] if tf == "1h" else higher_ema(df, tf, frames, "1h", 50, 10)
    day_first = df["Open"].groupby(df.index.normalize()).transform("first").values.astype(float)
    rd["day_open"] = np.where(c > day_first, "up", np.where(c < day_first, "down", "none")).astype(object)
    rd["ema12_and_up1"] = both(rd["ema12"], rd["ema12_up1"])
    return rd, states


def inside_read(r, states, l, h, atr, floor_a=None, ceil_a=None):
    """#26c's call, as a trader could see it the moment the EQ became knowable."""
    i, born = r["confirm"], r["born"]
    a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
    if not np.isfinite(a):
        return "none", "none"
    pre = str(states[max(0, born - 1)]) if born > 0 else "FLAT"
    # edges as they stood when the EQ became knowable (2026-09-11: the final edges were a small look-ahead)
    fl_ = floor_a[i] if floor_a is not None and np.isfinite(floor_a[i]) else r["floor"]
    ce_ = ceil_a[i] if ceil_a is not None and np.isfinite(ceil_a[i]) else r["ceil"]
    tf_ = int(np.sum(l[born:i + 1] <= fl_ + TOUCH * a))
    tc = int(np.sum(h[born:i + 1] >= ce_ - TOUCH * a))
    s1 = 1 if tf_ > tc else -1 if tc > tf_ else 0
    s2 = 1 if pre == "DOWN" else -1 if pre == "UP" else 0
    score = s1 + s2
    call = "up" if score >= 2 else "down" if score <= -2 else "none"
    lean = "up" if score >= 1 else "down" if score <= -1 else "none"
    return call, lean


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
    brk = {}                                   # (tf, read, value) -> [n, broke_up]
    errs = []
    for tf_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            rd, states = bar_reads(df, tf, frames, all_frames)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            floor_a, ceil_a, _, rs, atr = EC.coils(df, min_gap=0)
            ins = {}
            for r in rs:
                if not r["tradeable"] or r["born"] < 60:
                    continue
                call, lean = inside_read(r, states, l, h, atr, floor_a, ceil_a)
                ins[(r["born"], r["end"])] = (call, lean)
                d = break_dir(r["how"])
                if d is None:
                    continue
                i = r["confirm"]
                vals = {k: str(rd[k][i]) for k in rd}
                vals["inside"] = call
                vals["inside_lean"] = lean
                vals["ema12_and_inside"] = vals["ema12"] if (vals["ema12"] == call and call != "none") else "none"
                for k in READ_KEYS:
                    key = (tf, k, vals.get(k, "none"))
                    cell = brk.setdefault(key, [0, 0])
                    cell[0] += 1
                    cell[1] += 1 if d == "up" else 0
            for x in FR2.trades(kind, tf, df, all_frames, start, 0, modes=VARIANTS):
                ci = x["e"] - 1
                call, lean = ins.get((x["born"], x["end"]), ("none", "none"))
                vals = {k: str(rd[k][ci]) for k in rd}
                vals["inside"] = call
                vals["inside_lean"] = lean
                vals["ema12_and_inside"] = vals["ema12"] if (vals["ema12"] == call and call != "none") else "none"
                v_i = VARIANTS.index(x["variant"])
                rr_i = 1 if x["rr"] >= 1.0 else 0
                for r_i, k in enumerate(READ_KEYS):
                    t = FR.tag(x["side"], vals.get(k, "none"))
                    t_i = 2 if t == "no trend" else TAGS.index(t)
                    codes.append(encode([tf_i, v_i, r_i, t_i, rr_i, x["era_i"]]))
                    rets.append(x["ret"]); drifts.append(x["drift"]); tooks.append(1 if x["took"] else 0)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not codes and not brk:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32),
            np.asarray(drifts, dtype=np.float32), np.asarray(tooks, dtype=np.int8), brk), errs


def stats(g):
    if len(g) < 30:
        return None
    return dict(n=int(len(g)), mean=float(g.ret.mean()), median=float(g.ret.median()),
                edge=float((g.ret - g.drift).mean()), won=float((g.ret > 0).mean()), reached=float(g.took.mean()))


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
    brk = {}
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

    # 1. which way it breaks
    breaks = {}
    for tf in TFS:
        tot = sum(v[0] for (t_, k_, _), v in brk.items() if t_ == tf and k_ == "daily50")
        ups = sum(v[1] for (t_, k_, _), v in brk.items() if t_ == tf and k_ == "daily50")
        breaks[tf] = dict(n=tot, share_up=(ups / tot) if tot else None, reads={})
        for k in READ_KEYS:
            row = {}
            for val in ("up", "down", "none"):
                n_, u_ = brk.get((tf, k, val), [0, 0])
                row[val] = dict(n=n_, broke_up=(u_ / n_) if n_ else None)
            called = row["up"]["n"] + row["down"]["n"]
            right = (row["up"]["n"] * (row["up"]["broke_up"] or 0) + row["down"]["n"] * (1 - (row["down"]["broke_up"] or 0)))
            row["called"] = called / tot if tot else None
            row["right"] = right / called if called else None
            breaks[tf]["reads"][k] = row

    # 2. the trade
    code = np.concatenate([p[0] for p in parts]).astype(np.int64)
    f = pd.DataFrame({"ret": np.concatenate([p[1] for p in parts]).astype(float),
                      "drift": np.concatenate([p[2] for p in parts]).astype(float),
                      "took": np.concatenate([p[3] for p in parts])})
    rem = code
    for (name, vals), size in reversed(list(zip(DIMS, SIZES))):
        f[name] = (rem % size).astype(np.int16)
        rem = rem // size
    print("  %d trade rows (a trade counted once per read), folding  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    trades = {}
    for rr_name, sub in (("every trade", f), ("far line 1x or more", f[f.rr == 1])):
        for keys, with_era in ((["tf", "variant", "read", "tag"], False), (["tf", "variant", "read", "tag", "era"], True)):
            for k, g in sub.groupby(keys, sort=False):
                st = stats(g)
                if not st:
                    continue
                label = [TFS[k[0]], VARIANTS[k[1]], READ_KEYS[k[2]], TAGS[k[3]], rr_name, ERAS[k[4]] if with_era else "all"]
                trades[" | ".join(label)] = st
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         reads=READ_KEYS, read_names=dict(READS), variants=VARIANTS, tags=TAGS,
                         rr=["every trade", "far line 1x or more"], eras=["all"] + ERAS, rows=int(len(f)),
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         seconds=int(time.time() - t0)),
               breaks=breaks, trades=trades)
    json.dump(res, open(OUT, "w"))

    print("\n  WHAT CALLS A FAST EQ  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for tf in TFS:
        b = breaks[tf]
        print("\n  %s: %d EQs broke, %.0f%% of them up" % (tf, b["n"], 100 * (b["share_up"] or 0)))
        print("    %-18s %7s %7s %8s %8s    trade WITH the read, half at the far line, far line 1x+: avg / mid / edge  n   eras" % (
            "read", "called", "right", "up->up", "dn->dn"))
        for k in READ_KEYS:
            r = b["reads"][k]
            t = trades.get("%s | %s | %s | with | far line 1x or more | all" % (tf, VARIANTS[0], k))
            eras = "  ".join(("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"])) if e else "  -  "
                             for e in (trades.get("%s | %s | %s | with | far line 1x or more | %s" % (tf, VARIANTS[0], k, er)) for er in ERAS))
            print("    %-18s %6.0f%% %6.0f%% %7.0f%% %7.0f%%    %s   %s" % (
                k, 100 * (r["called"] or 0), 100 * (r["right"] or 0), 100 * (r["up"]["broke_up"] or 0),
                100 * (1 - (r["down"]["broke_up"] or 0)) if r["down"]["n"] else 0,
                ("%+6.2f / %+6.2f / %+6.2f  n%-6d" % (100 * t["mean"], 100 * t["median"], 100 * t["edge"], t["n"])) if t else "   -   ",
                eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
