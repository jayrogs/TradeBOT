"""eq_managed.py -- his marked EQs traded HIS way (2026-09-11).

His words: "i am always for a partial profit taking to minimize losses" and "its not about always getting a killer
runner after an eq, its usually about locking in some partial to have security if the trade goes against you, and
once it makes the move in your favor, just sell everything".

So the trade is: buy the next open after the EQ becomes knowable, take a partial early for security, and sell the
rest into the move. No trailing runner. What gets varied:

    stop     the EQ's far side plus the equal-level tolerance (tight), or the last hourly higher low (hourly sized)
    partial  half at the EQ's far line, half at 1x the risk, or none
    sell     the rest at 2x or 3x the risk, or at the hourly's last swing high
    guard    no trade if the next open is already through the far line or past the stop (his trend-ride guard)
    give up  48 hourly bars

Controls: all out at the far line, and hold 24 hourly bars (the old way).
Costs: 0.2% round trip on crypto, 0.05% elsewhere.

    python studies/eq_managed.py --procs 20
Writes validation/eq_managed.json
"""
import concurrent.futures as cf
import itertools
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_direction as ED         # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402

OUT = os.path.join("validation", "eq_managed.json")
IDX = os.path.join("validation", "eq_mark", "eq_mark_index.json")
COST = {"crypto": 0.20, "stock": 0.05, "etf": 0.05, "futures": 0.05}
BPH = {"5m": 12, "15m": 4}
MAX_HOURS = 48
STOPS = {"EQ's far side": "eq", "the hourly higher low": "h1"}
PARTIALS = {"half at the EQ's far line": "far", "half at 1x the risk": "1r", "none": "none"}
SELLS = {"2x the risk": "2r", "3x the risk": "3r", "the hourly's last swing high": "h1"}


def plan_names():
    out = []
    for s, p, x in itertools.product(STOPS, PARTIALS, SELLS):
        out.append("stop %s, %s, sell the rest at %s" % (s, p, x))
    return out + ["all out at the EQ's far line", "hold 24 hourly bars (the old way)"]


def one_trade(stop_kind, partial_kind, sell_kind, tf, kind, df, r, side, h1lo, h1hi, h1atr, atr=None):
    o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    i = r["confirm"]
    e = i + 1
    if e >= n:
        return None
    entry = o[e]
    lows = [p for j, p, kd, lab in r["shape"] if kd == "low"]
    highs = [p for j, p, kd, lab in r["shape"] if kd == "high"]
    a_i = (atr if atr is not None else P._atr(df))[i]
    tol = P.SAME_LEVEL_ATR * (a_i if np.isfinite(a_i) else 0.0)
    floor, ceil = lows[-1], highs[-1]
    far = ceil if side > 0 else floor
    eq_stop = (floor - tol) if side > 0 else (ceil + tol)
    # HIS GUARD (the trend ride has it too): if the next open is already through either line, there is no trade
    if (side > 0 and (entry >= far or entry <= eq_stop)) or (side < 0 and (entry <= far or entry >= eq_stop)):
        return dict(pct=None, bars=0, how="no trade: it opened outside the EQ")
    if stop_kind == "eq":
        stop = eq_stop
    else:
        # THE CLOSEST structure that kills the idea, not the furthest (2026-09-11, his catch: the hourly swing
        # could sit 3% away while the target sat 0.6% away, so every trade risked five times what it aimed at).
        hl = h1lo[e] if side > 0 else h1hi[e]
        pad = 0.15 * (h1atr[e] if np.isfinite(h1atr[e]) else 0.0)
        h1_stop = (hl - pad) if side > 0 else (hl + pad)
        both = [x for x in (eq_stop, h1_stop) if np.isfinite(x) and
                ((side > 0 and x < entry) or (side < 0 and x > entry))]
        if not both:
            return dict(pct=None, bars=0, how="no trade: nothing to stop under")
        stop = max(both) if side > 0 else min(both)
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if sell_kind == "2r":
        target = entry + side * 2 * risk
    elif sell_kind == "3r":
        target = entry + side * 3 * risk
    else:
        sw = h1hi[e] if side > 0 else h1lo[e]
        target = sw if (np.isfinite(sw) and ((side > 0 and sw > entry) or (side < 0 and sw < entry))) \
            else entry + side * 2 * risk
    if abs(target - entry) < abs(entry - stop):
        return dict(pct=None, bars=0, how="no trade: the target was closer than the stop")
    if partial_kind == "far":
        cut = far
    elif partial_kind == "1r":
        cut = entry + side * risk
    else:
        cut = None
    last = min(n - 1, e + MAX_HOURS * BPH[tf])
    # THE WALK, DONE WITH ARRAY MATH (2026-09-11: the bar-by-bar version was most of every study's run time).
    # Same rules as before: within one bar the stop comes first, then the partial, then the target.
    lw, hw, cw = l[e:last + 1], h[e:last + 1], c[e:last + 1]

    def first(mask):
        return int(np.argmax(mask)) if mask.any() else None
    i_stop = first(lw <= stop) if side > 0 else first(hw >= stop)
    i_tgt = first(hw >= target) if side > 0 else first(lw <= target)
    i_cut = None if cut is None else (first(hw >= cut) if side > 0 else first(lw <= cut))
    BIG = len(lw) + 1
    s_, t_, c_ = (BIG if i_stop is None else i_stop), (BIG if i_tgt is None else i_tgt), (BIG if i_cut is None else i_cut)
    took = False
    if s_ <= c_ and s_ <= t_ and i_stop is not None:
        got, j, how = side * (stop - entry) / entry, e + s_, "stopped out"
    elif c_ <= t_:
        took = True
        got = 0.5 * side * (cut - entry) / entry
        after = c_
        s2 = first(lw[after:] <= stop) if side > 0 else first(hw[after:] >= stop)
        t2 = first(hw[after:] >= target) if side > 0 else first(lw[after:] <= target)
        s2 = BIG if s2 is None else after + s2
        t2 = BIG if t2 is None else after + t2
        if s2 <= t2 and s2 < BIG:
            got += 0.5 * side * (stop - entry) / entry
            j, how = e + s2, "rest stopped out"
        elif t2 < BIG:
            got += 0.5 * side * (target - entry) / entry
            j, how = e + t2, "sold into the move"
        else:
            got += 0.5 * side * (cw[-1] - entry) / entry
            j, how = last, "still open when time ran out"
    elif t_ < BIG:
        got, j, how = side * (target - entry) / entry, e + t_, "sold into the move, no partial taken"
    else:
        got, j, how = side * (cw[-1] - entry) / entry, last, "still open when time ran out"
    cost = COST.get(kind, 0.05) * (1.5 if took else 1.0)
    return dict(pct=got * 100 - cost, bars=int(j - e), how=how)


def simple(kind_of, tf, kind, df, r, side, atr=None):
    """The two controls: all out at the far line, and the plain hold."""
    o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    i = r["confirm"]; e = i + 1
    if e >= n:
        return None
    entry = o[e]
    lows = [p for j_, p, kd, lab in r["shape"] if kd == "low"]
    highs = [p for j_, p, kd, lab in r["shape"] if kd == "high"]
    a_i = (atr if atr is not None else P._atr(df))[i]
    tol = P.SAME_LEVEL_ATR * (a_i if np.isfinite(a_i) else 0.0)
    floor, ceil = lows[-1], highs[-1]
    far = ceil if side > 0 else floor
    stop = (floor - tol) if side > 0 else (ceil + tol)
    if (side > 0 and (entry >= far or entry <= stop)) or (side < 0 and (entry <= far or entry >= stop)):
        return dict(pct=None, bars=0, how="no trade: it opened outside the EQ")
    if kind_of == "hold":                       # the control walks the SAME entries the plans take
        j = min(n - 1, e + 24 * BPH[tf])
        return dict(pct=side * (c[j] - entry) / entry * 100 - COST.get(kind, 0.05), bars=int(j - e), how="held")
    last = min(n - 1, e + MAX_HOURS * BPH[tf])
    for j in range(e, last + 1):
        if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
            return dict(pct=side * (stop - entry) / entry * 100 - COST.get(kind, 0.05), bars=int(j - e),
                        how="stopped out")
        if (side > 0 and h[j] >= far) or (side < 0 and l[j] <= far):
            return dict(pct=side * (far - entry) / entry * 100 - COST.get(kind, 0.05), bars=int(j - e),
                        how="all out at the far line")
    return dict(pct=side * (c[last] - entry) / entry * 100 - COST.get(kind, 0.05), bars=int(last - e),
                how="still open when time ran out")


def _work(args):
    sym, kind, rows = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    out, errs = [], []
    for row in rows:
        tf = row["tf"]
        side = 1 if row.get("mark") == "long" else -1 if row.get("mark") == "short" else 0
        if side == 0:
            continue
        try:
            df = frames[tf]
            recs = EC.coils(df, min_gap=3)[3]
            confirm = int(row["id"].rsplit("_", 1)[1])
            r = next((x for x in recs if x["confirm"] == confirm), None)
            if r is None:
                errs.append("%s %s: the EQ at bar %d was not found" % (sym, tf, confirm))
                continue
            h1lo, h1hi = ED.last_swings(df, tf, frames, "1h")
            atr_all = P._atr(df)
            hdf = frames.get("1h")
            if hdf is not None and len(hdf) >= 60:
                al = FR.align(df, tf, hdf, "1h", P._atr(hdf).astype(object))
                h1atr = np.array([np.nan if isinstance(x, str) else float(x) for x in al], dtype=float)
            else:
                h1atr = np.full(len(df), np.nan)
            # IS THIS LINED UP AS AN ENTRY FOR THE BIGGER CHART? (his words: the runner is only for those)
            # hourly leaning his way, AND the EQ sitting in the hourly pullback: at the hourly 12 EMA, or its floor
            # within one normal hourly bar of the hourly's last swing low.
            state = EF.higher_state(df, tf, frames, "1h")
            ev = ER.above12(df, tf, frames, "1h")[1]
            e_ = r["confirm"] + 1
            cl = df["Close"].values.astype(float)
            lows_ = [p_ for j_, p_, kd_, lb_ in r["shape"] if kd_ == "low"]
            highs_ = [p_ for j_, p_, kd_, lb_ in r["shape"] if kd_ == "high"]
            ha = h1atr[e_] if e_ < len(h1atr) and np.isfinite(h1atr[e_]) else np.nan
            lean = (str(state[e_ - 1]) == "up" or (np.isfinite(ev[e_]) and cl[e_ - 1] > ev[e_ - 1])) if side > 0 else                    (str(state[e_ - 1]) == "down" or (np.isfinite(ev[e_]) and cl[e_ - 1] < ev[e_ - 1]))
            at_pull = False
            if np.isfinite(ha) and ha > 0:
                line = lows_[-1] if side > 0 else highs_[-1]
                sw = h1lo[e_] if side > 0 else h1hi[e_]
                at_pull = (np.isfinite(ev[e_]) and abs(line - ev[e_]) <= 0.5 * ha) or                           (np.isfinite(sw) and ((side > 0 and sw < line <= sw + ha) or
                                                (side < 0 and sw - ha <= line < sw)))
            lined_up = bool(lean and at_pull)
            got = {}
            for s, p, x in itertools.product(STOPS, PARTIALS, SELLS):
                t = one_trade(STOPS[s], PARTIALS[p], SELLS[x], tf, kind, df, r, side, h1lo, h1hi, h1atr, atr_all)
                if t:
                    got["stop %s, %s, sell the rest at %s" % (s, p, x)] = t
            for nm, kd in (("all out at the EQ's far line", "far"), ("hold 24 hourly bars (the old way)", "hold")):
                t = simple(kd, tf, kind, df, r, side, atr_all)
                if t:
                    got[nm] = t
            out.append(dict(id=row["id"], n=row["n"], sym=sym, kind=kind, tf=tf, mark=row["mark"],
                            lined_up=lined_up, plans=got))
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return out, errs


def main():
    procs = 20
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    rows = json.load(open(IDX))
    by_name = {}
    for row in rows:
        by_name.setdefault((row["sym"], row["kind"]), []).append(row)
    jobs = [(s_, k_, rs) for (s_, k_), rs in by_name.items()]
    got, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(jobs))) as ex:
        for g, e in ex.map(_work, jobs, chunksize=1):
            got += g
            errs += e
    got.sort(key=lambda x: x["n"])
    table = {}
    for name in plan_names():
        rs = [g["plans"][name] for g in got if name in g["plans"]]
        vals = [t["pct"] for t in rs if t["pct"] is not None]
        skipped = sum(1 for t in rs if t["pct"] is None)
        if len(vals) < 5:
            continue
        table[name] = dict(n=len(vals), skipped=int(skipped), avg=float(np.mean(vals)), middle=float(np.median(vals)),
                           won=float(np.mean([v > 0 for v in vals])), total=float(np.sum(vals)),
                           worst=float(np.min(vals)), best=float(np.max(vals)),
                           bars=float(np.mean([t["bars"] for t in rs if t["pct"] is not None])))
    json.dump(dict(meta=dict(marks=len(got), cost=COST, max_hours=MAX_HOURS, plans=plan_names(),
                             seconds=int(time.time() - t0)), table=table, trades=got), open(OUT, "w"), indent=1)
    print("\n  HIS MARKS, PARTIAL FOR SECURITY THEN SELL INTO THE MOVE  (%d marks, %.0fs)\n" % (
        len(got), time.time() - t0))
    print("    %-58s %4s %5s %8s %8s %6s %8s %7s" % (
        "plan", "n", "skip", "avg", "middle", "won", "worst", "bars"))
    for name in sorted(table, key=lambda k: -table[k]["avg"]):
        s = table[name]
        print("    %-58s %4d %5d %+7.2f%% %+7.2f%% %5.0f%% %+7.2f%% %6.0f" % (
            name, s["n"], s["skipped"], s["avg"], s["middle"], 100 * s["won"], s["worst"], s["bars"]))
    best = max(table, key=lambda k: table[k]["avg"])
    print("\n    every mark under the best plan (%s):" % best)
    for g in got:
        t = g["plans"].get(best)
        if t:
            print("      #%-2d %-6s %-3s %-5s %-9s %8s  %-36s %d bars" % (
                g["n"], g["sym"], g["tf"], g["mark"], "lined up" if g.get("lined_up") else "",
                "-" if t["pct"] is None else "%+.2f%%" % t["pct"], t["how"], t["bars"]))
    for e in errs:
        print("  " + e)


if __name__ == "__main__":
    main()
