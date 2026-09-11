"""eq_breaktrade.py -- trade the BREAK of a 5m / 15m EQ in the direction the read calls (2026-09-11).

Why: eq_fastread.py found reads that call which way a fast EQ breaks (this chart's 12 EMA 58-59%, the inside read
59-60%, both together 65-68%; the next chart up's 12 EMA points the wrong way, 44-45%), yet buying the higher low
INSIDE the EQ with those reads made about nothing. The call is about the break, so this trades the break.

The EQ, the break and the reads (all known before the break bar):
    the break      the first bar whose wick goes through the EQ's ceiling (long) or floor (short) by more than an equal
                   high/low would (eq_coil.py). EQs that died on a pivot are skipped.
    reads          at the bar BEFORE the break:
                     every break, no read (the control)
                     this chart: price over a rising 12 EMA / under a falling one
                     inside the EQ: the line tested more holds + it breaks against the trend it came from
                     both of those agree
                     the next chart up's 12 EMA (15m for a 5m EQ, 1h for a 15m EQ)
                     the opposite of the next chart up's 12 EMA (it pointed backwards in eq_fastread)
    location       the broken line within half a normal bar of a bigger chart's 12 EMA (15m/1h/4h for a 5m EQ,
                   1h/4h/daily for a 15m EQ), or open space
The trade:
    entry          (a) the next open after the break bar (the house rule: price never comes from the confirming bar)
                   (b) a stop order resting at the line plus that tolerance, filled on the break bar (at the open if
                       it gapped past), for comparison
    stop           a wick through the EQ's other line, sold at the next open (the whole EQ has to fail)
    exits          all out at 2x the risk
                   half at 1x the risk, stop to breakeven, runner out on a close through this chart's 12 EMA
                   half at 1x the risk, stop to breakeven, runner stop walked up under each new higher low
                   half at 1x the risk, stop to breakeven, runner out on a close through the next chart up's 12 EMA
                   hold 20 bars (plain follow through)
    5m/15m stock trades close at the bell. Costs out. Stocks and ETFs on regular-hours bars.

    pythonw studies/eq_breaktrade.py --procs 20 --log logs/eq_breaktrade.log
Writes validation/eq_breaktrade.json
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
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402

OUT = os.path.join("validation", "eq_breaktrade.json")
TFS = ["5m", "15m"]
ABOVE = {"5m": ["15m", "1h", "4h"], "15m": ["1h", "4h", "1d"]}
NEAR = 0.5
HOLD_BARS = 20
ENTRIES = ["next open after the break bar", "stop order at the line"]
EXITS = [("all out at 2x the risk", "t2"),
         ("half at 1x, runner out on a close through this chart's 12 EMA", "ema"),
         ("half at 1x, runner stop walked up under each higher low", "steps"),
         ("half at 1x, runner out on a close through the next chart up's 12 EMA (zoom out)", "zoom"),
         ("hold 20 bars", "hold")]
READS = [("every", "every break, no read"),
         ("own12", "this chart's 12 EMA"),
         ("inside", "inside the EQ: tested-more line holds + against the prior trend"),
         ("own12_and_inside", "this chart's 12 EMA and the inside read agree"),
         ("next12", "the next chart up's 12 EMA"),
         ("fade_next12", "the opposite of the next chart up's 12 EMA")]
TAGS = ["with", "against", "no call"]
LOCS = ["at a bigger 12 EMA", "open space"]
ERAS = ["before", "first", "second"]
DIMS = [("tf", TFS), ("entry", ENTRIES), ("exit", [x[0] for x in EXITS]), ("read", [r[0] for r in READS]),
        ("tag", TAGS), ("loc", LOCS), ("era", ERAS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def walk_break(sgn, c, o, h, l, atr, guide, e, fill, stop, n, cap, day, mode, lows_at, highs_at, from_bar):
    """From the fill. `from_bar` is the first bar whose extremes count (the break bar itself for a stop-order fill,
    where the stop is still checked on that bar: the careful reading). Returns (exit bar, price, reached 1x)."""
    risk = abs(fill - stop)
    if risk <= 0:
        return None
    t1 = fill + sgn * risk
    t2 = fill + sgn * 2 * risk
    share = 0.5
    took = False
    stop_now = stop
    for k in range(from_bar, n - 1):
        if (sgn > 0 and l[k] < stop_now) or (sgn < 0 and h[k] > stop_now):
            px = o[k + 1]
            return k, (share * t1 + (1 - share) * px) if took else px, took
        if k == e and from_bar == e:
            continue                      # the fill bar: only the stop counts, the targets do not
        if mode == "t2":
            if (sgn > 0 and h[k] >= t2) or (sgn < 0 and l[k] <= t2):
                return k, t2, True
        elif mode == "hold":
            if k - e >= HOLD_BARS:
                return k, c[k], False
        else:
            if not took and ((sgn > 0 and h[k] >= t1) or (sgn < 0 and l[k] <= t1)):
                took = True
                stop_now = fill
            if took:
                if mode in ("ema", "zoom") and np.isfinite(guide[k]):
                    if (sgn > 0 and c[k] < guide[k]) or (sgn < 0 and c[k] > guide[k]):
                        return k, share * t1 + (1 - share) * o[k + 1], True
                if mode == "steps":
                    tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
                    if sgn > 0:
                        for p in lows_at.get(k, ()):
                            stop_now = max(stop_now, p - tol)
                    else:
                        for p in highs_at.get(k, ()):
                            stop_now = min(stop_now, p + tol)
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, (share * t1 + (1 - share) * c[k]) if took else c[k], took
        if k - e >= cap:
            px = o[k + 1]
            return k, (share * t1 + (1 - share) * px) if took else px, took
    return None


def _work(args):
    sym, kind, start = args
    try:
        all_frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = FR2.regular_hours(all_frames) if kind in ("stock", "etf") else all_frames
    cost = B.CLASS_COST.get(kind, B.COST)
    codes, rets, drifts, reach = [], [], [], []
    errs = []
    mid = start + (pd.Timestamp.now() - start) / 2
    for tf_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            own, own_e = ER.ema12_read(c)
            ab = [ER.above12(df, tf, frames, htf) for htf in ABOVE[tf]]
            next_st, next_ev = ab[0]
            states = ST.states(df, causal=True)
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
            for r in recs:
                if not r["tradeable"] or r["born"] < 60:
                    continue
                how = str(r["how"])
                if "wick through the ceiling" in how:
                    sgn = 1
                elif "wick through the floor" in how:
                    sgn = -1
                else:
                    continue
                k = r["end"]
                if k < 2 or k >= n - 2:
                    continue
                a = atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else np.nan
                if not np.isfinite(a):
                    continue
                tol = P.SAME_LEVEL_ATR * a
                line = r["ceil"] if sgn > 0 else r["floor"]
                other = r["floor"] if sgn > 0 else r["ceil"]
                stop = other - tol if sgn > 0 else other + tol
                b = k - 1                                   # everything read on the bar before the break
                call, _lean = EF.inside_read(r, states, l, h, atr, floor, ceil)
                o12 = str(own[b]); n12 = str(next_st[b])
                vals = {"every": "up" if sgn > 0 else "down", "own12": o12, "inside": call,
                        "own12_and_inside": o12 if (o12 == call and call != "none") else "none",
                        "next12": n12,
                        "fade_next12": "down" if n12 == "up" else "up" if n12 == "down" else "none"}
                side = "long" if sgn > 0 else "short"
                ab_ev = [x[1] for x in ab]
                loc_i = 0 if any(np.isfinite(ev[b]) and abs(line - ev[b]) <= NEAR * a for ev in ab_ev) else 1
                t = df.index[k]
                era_i = 0 if t < start else 1 if t < mid else 2
                fills = []
                trig = line + sgn * tol
                fills.append((0, o[k + 1], k + 1, k + 1))  # next open: fill bar k+1, bars from k+1
                gap_fill = max(o[k], trig) if sgn > 0 else min(o[k], trig)
                fills.append((1, gap_fill, k, k))           # stop order on the break bar, stop checked that bar
                for en_i, fill, e, from_bar in fills:
                    if (sgn > 0 and not (stop < fill)) or (sgn < 0 and not (fill < stop)):
                        continue
                    for x_i, (_, mode) in enumerate(EXITS):
                        guide = next_ev if mode == "zoom" else own_e
                        res = walk_break(sgn, c, o, h, l, atr, guide, e, fill, stop, n, cap, day, mode,
                                         lows_at, highs_at, from_bar)
                        if res is None:
                            continue
                        xb, px, took = res
                        held = xb + 1 - e
                        ret = sgn * (px / fill - 1) - cost
                        dr = sgn * (np.exp(drift * held) - 1) - cost
                        for r_i, (rk, _) in enumerate(READS):
                            tg = FR.tag(side, vals[rk])
                            t_i = 2 if tg == "no trend" else TAGS.index(tg)
                            codes.append(encode([tf_i, en_i, x_i, r_i, t_i, loc_i, era_i]))
                            rets.append(ret); drifts.append(dr); reach.append(1 if took else 0)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not codes:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32),
            np.asarray(drifts, dtype=np.float32), np.asarray(reach, dtype=np.int8)), errs


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
    names_of = dict(DIMS)
    base = ["tf", "entry", "exit", "read", "tag"]
    trades = {}
    for loc_name, s1 in (("any location", f), (LOCS[0], f[f["loc"] == 0]), (LOCS[1], f[f["loc"] == 1])):
        for keys in (base, base + ["era"]):
            agg = s1.groupby(keys).agg(n=("ret", "size"), mean=("ret", "mean"), median=("ret", "median"),
                                       edge=("edge", "mean"), won=("won", "mean"), reached=("took", "mean"))
            for kk, row in agg.iterrows():
                if row["n"] < 30:
                    continue
                lab = [names_of[c_][int(v)] for c_, v in zip(keys, kk)]
                era = lab[5] if len(keys) == 6 else "all"
                trades[" | ".join(lab[:5] + [loc_name, era])] = dict(
                    n=int(row["n"]), mean=float(row["mean"]), median=float(row["median"]), edge=float(row["edge"]),
                    won=float(row["won"]), reached=float(row["reached"]))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         entries=ENTRIES, exits=[x[0] for x in EXITS], reads=[r[0] for r in READS],
                         read_names=dict(READS), tags=TAGS, locs=["any location"] + LOCS, eras=["all"] + ERAS,
                         rows=int(len(f)), hold_bars=HOLD_BARS, near=NEAR,
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         seconds=int(time.time() - t0)),
               trades=trades)
    json.dump(res, open(OUT, "w"))
    print("\n  TRADING THE FAST EQ BREAK  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for tf in TFS:
        for en in ENTRIES[:1]:
            for ex_name, _ in EXITS:
                print("\n   %s | %s | %s   WITH the read: avg / middle / edge  n   eras avg/middle" % (tf, en, ex_name))
                for rk, _ in READS:
                    for loc in ("any location", LOCS[0]):
                        t = trades.get(" | ".join([tf, en, ex_name, rk, "with", loc, "all"]))
                        if not t:
                            continue
                        eras = "  ".join(("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"])) if e else "   -   "
                                         for e in (trades.get(" | ".join([tf, en, ex_name, rk, "with", loc, er])) for er in ERAS))
                        print("     %-17s %-20s %+6.2f / %+6.2f / %+6.2f  n%-7d %s" % (
                            rk, loc, 100 * t["mean"], 100 * t["median"], 100 * t["edge"], t["n"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
