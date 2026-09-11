"""eq_coil_study.py -- what the EQ (the coil) is actually worth.

His EQ: "a series of HL and LH increasingly tightening" (2026-09-09). The shape comes from
studies/eq_coil.py. This measures two things on every EQ in the universe, every chart size:

  1. THE BREAK. Which way did it go, did it follow through, and could the direction have been
     called BEFORE it broke? A coil has no "lows rising vs highs falling" read -- by definition
     both are true -- so the reads here are coil-specific:
        which way it came in       the trend before the coil started
        the next chart up          that chart's trend at the moment the shape completed
        which edge tested more     how many touches of the floor against the ceiling
        which line is steeper      lows rising faster than highs falling (a rising wedge)
                                   or the reverse. This is the coil's own shape read.
        how many pairs             2, 3, 4 or more higher lows and lower highs
        how tight it got           how far the two lines closed, in normal bars
     THE CALL is two of three agreeing: the next chart, the steeper line, the tested edge.

  2. THE TRADES, all entered only with what was known at the time (nothing acts before the
     final pivot confirms, and an EQ that broke before that is skipped entirely):
        buy the floor, hold for the break        buy the last higher low, out on a close under it
        buy the floor, partial at the ceiling    his free ride: sell the share that makes the rest free
        short the ceiling (both versions)        the mirror
        buy the break up / short the break down  in at the open after the close beyond the line
     Everything is compared against the chart's own drift over the same bars, and split by era.

    pythonw studies/eq_coil_study.py --procs 20 --log logs/eq_coil_study.log
    add --focus for the focus list.

Writes validation/eq_coil_study.json and eq_coil_events.csv.gz.
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
import eq_break as EB             # noqa: E402
import eq_coil as EC              # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
TOUCH = 0.25
CAP_DAYS = 30
OUT = os.path.join("validation", "eq_coil_study.json")
EVENTS_OUT = os.path.join("validation", "eq_coil_events.csv.gz")
KEYS = ["trade", "tf", "kind", "era", "read_prior", "read_next", "read_touch", "read_steeper",
        "read_pairs", "read_tight", "read_call", "read_spacing", "read_bars", "read_clean"]
BKEYS = [k for k in KEYS if k != "trade"]
READS = ["read_call", "read_clean", "read_spacing", "read_bars", "read_next", "read_steeper",
         "read_touch", "read_pairs", "read_tight", "read_prior"]
TRADES = ["buy the floor, hold for the break", "buy the floor, partial at the ceiling (the free ride)",
          "short the ceiling, hold for the break", "short the ceiling, partial at the floor (the free ride)",
          "buy the break up", "short the break down",
          "buy a break down that failed", "short a break up that failed",
          "buy on an UP call, stop a normal bar under the floor",
          "short on a DOWN call, stop a normal bar over the ceiling"]
FAIL_BARS = 5                     # a break that is back inside this soon "lacked follow through"


def reads(r, df, c, h, l, atr, state, hi_state, piv):
    """What a trader could see the moment the shape completed, and nothing after."""
    i = r["confirm"]; born = r["born"]
    a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
    pre = state[max(0, born - 1)] if born > 0 else "FLAT"
    prior = ("came in from an uptrend" if pre == "UP" else "came in from a downtrend" if pre == "DOWN"
             else "came in from nothing (flat)")
    nxt = ("next chart up" if str(hi_state[i]) == "UP" else "next chart down" if str(hi_state[i]) == "DOWN"
           else "next chart flat")
    f, ce = r["floor"], r["ceil"]
    tf_ = int(np.sum(l[born:i + 1] <= f + TOUCH * a)) if np.isfinite(a) else 0
    tc = int(np.sum(h[born:i + 1] >= ce - TOUCH * a)) if np.isfinite(a) else 0
    touch = ("floor tested more" if tf_ > tc else "ceiling tested more" if tc > tf_ else "both tested the same")
    # which line is steeper: the lows climbing or the highs falling
    lows = [(j, p) for ci, j, p, k_, lab in piv if k_ == "low" and born <= j <= i and lab in EC.UP_LAB]
    highs = [(j, p) for ci, j, p, k_, lab in piv if k_ == "high" and born <= j <= i and lab in EC.DN_LAB]
    steeper = "neither line is steeper"
    if len(lows) >= 2 and len(highs) >= 2 and np.isfinite(a):
        up_rate = (lows[-1][1] - lows[0][1]) / max(lows[-1][0] - lows[0][0], 1) / a
        dn_rate = (highs[0][1] - highs[-1][1]) / max(highs[-1][0] - highs[0][0], 1) / a
        if up_rate > dn_rate * 1.35:
            steeper = "the lows are climbing faster"
        elif dn_rate > up_rate * 1.35:
            steeper = "the highs are falling faster"
    pairs = r["pairs"]
    pr = "2 pairs" if pairs <= 2 else "3 pairs" if pairs == 3 else "4 or more pairs"
    tightened = (r["wide_at_start"] / r["wide_at_end"]) if (r["wide_at_start"] and r["wide_at_end"]) else np.nan
    tight = ("closed a little (under 2x)" if tightened < 2 else "closed a lot (2-4x)" if tightened < 4
             else "closed hard (4x or more)") if np.isfinite(tightened) else "unknown"
    # his two complaints, measured. "one candle LH and next immediate candle a HL" -> spacing.
    # "bar and wick lengths are all over the place" -> how even the bars are inside the coil.
    gaps = []
    allp = sorted([j for j, _ in lows] + [j for j, _ in highs])
    for m in range(1, len(allp)):
        gaps.append(allp[m] - allp[m - 1])
    mingap = min(gaps) if gaps else 0
    spacing = ("pivots right on top of each other (2 bars or less)" if mingap <= 2 else
               "pivots 3 to 5 bars apart" if mingap <= 5 else "pivots well spread out (6+ bars)")
    rngs = (h[born:i + 1] - l[born:i + 1])
    rngs = rngs[np.isfinite(rngs) & (rngs > 0)]
    evenness = float(np.std(rngs) / np.mean(rngs)) if len(rngs) >= 5 and np.mean(rngs) > 0 else np.nan
    bars_b = ("even bars" if evenness < 0.45 else "bars a bit uneven" if evenness < 0.75
              else "bar sizes all over the place") if np.isfinite(evenness) else "unknown"
    clean = ("clean" if (mingap > 2 and np.isfinite(evenness) and evenness < 0.6)
             else "not clean")
    # THE CALL, rebuilt 2026-09-10 on the only two reads that carry anything. Both point the
    # OPPOSITE way to intuition, and both hold in all three eras and on every chart size:
    #   the line that gets tested MORE is the one that HOLDS, so it breaks the other way
    #     (floor tested more -> breaks up 59%, ceiling tested more -> 46%)
    #   and it resolves AGAINST what it came in from
    #     (came from a downtrend -> up 57%, from an uptrend -> 47%)
    # The chart above and which line is steeper are worth nothing here (52/52/52 and 51-53).
    score = ((1 if tf_ > tc else -1 if tc > tf_ else 0)
             + (1 if pre == "DOWN" else -1 if pre == "UP" else 0))
    call = ("the call is UP (both reads agree)" if score >= 2 else
            "leaning up" if score == 1 else
            "the call is DOWN (both reads agree)" if score <= -2 else
            "leaning down" if score == -1 else "no clear call")
    return dict(read_prior=prior, read_next=nxt, read_touch=touch, read_steeper=steeper,
                read_pairs=pr, read_tight=tight, read_call=call,
                read_spacing=spacing, read_bars=bars_b, read_clean=clean)


def walk_hold(sgn, c, o, h, l, atr, e, f, ce, n, cap, day, partial=False):
    """From bar e. The EQ is dead the moment a WICK goes through a line by more than an equal
    low would be -- the same rule that ends the shape. If it dies our way we are in the break
    and trail 5 normal bars behind the best close; if it dies against us we are out at the next
    open. `partial` is his free ride: sell the share at the far line that makes the rest free."""
    fill = o[e]
    a0 = atr[e - 1] if e >= 1 and np.isfinite(atr[e - 1]) else 0.0
    stop = f - P.SAME_LEVEL_ATR * a0 if sgn > 0 else ce + P.SAME_LEVEL_ATR * a0
    target = ce if sgn > 0 else f
    risk = abs(fill - stop); gain = abs(target - fill)
    share = min(1.0, risk / (risk + gain)) if (partial and risk > 0 and gain > 0) else 0.0
    took = False; peak = c[e]; trough = c[e]; worst = 0.0; broke = False
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        tol = P.SAME_LEVEL_ATR * a
        worst = min(worst, sgn * (c[k] / fill - 1))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        if share and not took and k > e and ((sgn > 0 and h[k] >= target) or (sgn < 0 and l[k] <= target)):
            took = True
        blend = (lambda px: share * target + (1 - share) * px) if took else (lambda px: px)
        if not broke:
            if (sgn > 0 and l[k] < f - tol) or (sgn < 0 and h[k] > ce + tol):
                return k, blend(o[k + 1]), ("stopped, the rest was free" if took else "the EQ broke the wrong way"), worst
            if (sgn > 0 and h[k] > ce + tol) or (sgn < 0 and l[k] < f - tol):
                broke = True
        else:
            if (sgn > 0 and c[k] < peak - 5 * a) or (sgn < 0 and c[k] > trough + 5 * a):
                return k, blend(o[k + 1]), "broke our way, trailed out", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, blend(c[k]), "session end", worst
        if k - e >= cap:
            return k, blend(o[k + 1]), "time (never broke)", worst
    return None


def walk_room(sgn, c, o, h, l, atr, e, f, ce, n, cap, day, room=1.0):
    """The same entry, but the stop is `room` normal bars BEYOND the line instead of at it.
    Every version that stops at the line loses, and it wins only about one trade in five, which
    points at the stop rather than the idea: by the time the shape is knowable the two lines are
    about a bar and a half apart and sitting on top of price. This gives it somewhere to breathe.
    Out on the stop, else trail 5 normal bars behind the best close once it is 1 bar in profit."""
    fill = o[e]
    a0 = atr[e - 1] if e >= 1 and np.isfinite(atr[e - 1]) else 0.0
    stop = (f - room * a0) if sgn > 0 else (ce + room * a0)
    peak = c[e]; trough = c[e]; worst = 0.0; armed = False
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, sgn * (c[k] / fill - 1))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        if (sgn > 0 and l[k] < stop) or (sgn < 0 and h[k] > stop):
            return k, o[k + 1], "stopped out", worst
        if not armed and sgn * (c[k] - fill) > a:
            armed = True
        if armed:
            if (sgn > 0 and c[k] < peak - 5 * a) or (sgn < 0 and c[k] > trough + 5 * a):
                return k, o[k + 1], "trailed out", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time", worst
    return None


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return [], [], []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, cid, rs, atr = EC.coils(df)
    if not rs:
        return [], [], []
    state = ST.states(df, causal=True)
    hdf = frames.get(R.UP.get(tf))
    hi_state = (B.higher_view(df, tf, hdf, R.UP[tf])[0] if hdf is not None and len(hdf) >= 60
                else np.array(["NA"] * n, dtype=object))
    piv = ST.pivots(df)
    cost = B.CLASS_COST.get(kind, B.COST)
    cap = CAP_DAYS * B.BARS_DAY[tf]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid_t = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    trades, breaks, events = [], [], []

    for r in rs:
        if not r["tradeable"] or r["born"] < 60:
            continue
        i, end = r["confirm"], r["end"]
        f, ce = r["floor"], r["ceil"]
        a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
        if not np.isfinite(a) or ce <= f:
            continue
        t = df.index[i]
        era = "before" if t < start else "first" if t < mid_t else "second"
        rd = reads(r, df, c, h, l, atr, state, hi_state, piv)
        base = dict(tf=tf, kind=kind, era=era, **rd)

        # ---- part 1: the break itself
        if r["how"].startswith("a wick") and end + 21 < n:
            f_e = float(floor[end - 1]) if end >= 1 and np.isfinite(floor[end - 1]) else f
            c_e = float(ceil[end - 1]) if end >= 1 and np.isfinite(ceil[end - 1]) else ce
            up = h[end] > c_e
            edge = c_e if up else f_e
            beyond = (np.max(h[end + 1:end + 21]) - edge) if up else (edge - np.min(l[end + 1:end + 21]))
            end20 = (c[min(n - 1, end + 20)] - edge) if up else (edge - c[min(n - 1, end + 20)])
            breaks.append(dict(base, up=bool(up), follow=float(beyond / a), end20=float(end20 / a),
                               age=int(end - r["born"] + 1), height=float((c_e - f_e) / a),
                               live=int(r["live_bars"])))

        # ---- part 2: the trades. Nothing may act before bar i (the shape is not knowable before).
        # the floor / ceiling entry: the first bar from i to the break that touches the edge
        # the floor and ceiling AS THEY STOOD on each bar (they tighten; the record's are the last)
        def edge_at(k):
            fk = floor[k] if np.isfinite(floor[k]) else f
            ck = ceil[k] if np.isfinite(ceil[k]) else ce
            return float(fk), float(ck)
        # A TOUCH, not a break. The low has to come INTO the band and stay in it; a low that
        # goes through the floor is the EQ dying, and buying the open after that is buying a
        # shape that no longer exists (found 2026-09-10 by drawing the trades: it produced
        # stops sitting ABOVE the fill and a wall of one-bar losses).
        def touched_floor(k):
            fk = edge_at(k)[0]
            tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
            return (fk - tol) <= l[k] <= (fk + TOUCH * a)

        def touched_ceiling(k):
            ck = edge_at(k)[1]
            tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
            return (ck - TOUCH * a) <= h[k] <= (ck + tol)
        e_lo = next((k for k in range(i, min(end + 1, n - 1))
                     if touched_floor(k) and o[k + 1] >= edge_at(k)[0]), None)      # and it did not open under the floor
        e_hi = next((k for k in range(i, min(end + 1, n - 1))
                     if touched_ceiling(k) and o[k + 1] <= edge_at(k)[1]), None)
        plans = []
        if e_lo is not None and e_lo + 1 < n:
            plans.append((TRADES[0], +1, e_lo + 1, "hold"))
            plans.append((TRADES[1], +1, e_lo + 1, "free"))
        if e_hi is not None and e_hi + 1 < n:
            plans.append((TRADES[2], -1, e_hi + 1, "hold"))
            plans.append((TRADES[3], -1, e_hi + 1, "free"))
        # the call, traded with room instead of the EQ's own edge as the stop
        if rd["read_call"].startswith("the call is UP") and e_lo is not None and e_lo + 1 < n:
            plans.append((TRADES[8], +1, e_lo + 1, "room"))
        if rd["read_call"].startswith("the call is DOWN") and e_hi is not None and e_hi + 1 < n:
            plans.append((TRADES[9], -1, e_hi + 1, "room"))
        if r["how"].startswith("a wick") and end + 1 < n:
            fb_, cb_ = edge_at(max(end - 1, i))
            up_break = h[end] > cb_
            if up_break:
                plans.append((TRADES[4], +1, end + 1, "ride"))
            else:
                plans.append((TRADES[5], -1, end + 1, "ride"))
            # his AVGO note: a break that does NOT follow through is a trade the other way.
            # Back inside the coil within FAIL_BARS -> in at the next open, the other direction.
            edge = cb_ if up_break else fb_
            back = next((k for k in range(end + 1, min(n - 1, end + 1 + FAIL_BARS))
                         if (c[k] < edge if up_break else c[k] > edge)), None)
            if back is not None and back + 1 < n:
                plans.append((TRADES[7] if up_break else TRADES[6], -1 if up_break else +1, back + 1, "ride"))
        for label, sgn, e, how in plans:
            if e >= n - 1 or e < 1:
                continue
            fe, cee = edge_at(e - 1)          # what the two lines were on the bar before the fill
            if how == "hold":
                res = walk_hold(sgn, c, o, h, l, atr, e, fe, cee, n, cap, day, partial=False)
            elif how == "free":
                res = walk_hold(sgn, c, o, h, l, atr, e, fe, cee, n, cap, day, partial=True)
            elif how == "room":
                res = walk_room(sgn, c, o, h, l, atr, e, fe, cee, n, cap, day, room=1.0)
            else:
                res = EB.ride_break(sgn, c, o, h, l, atr, e, fe, cee, n, cap, day)
            if res is None:
                continue
            xb, xpx, why, worst = res
            fill = o[e]
            ret = sgn * (xpx / fill - 1) - cost
            held = xb + 1 - e
            dr = sgn * (np.exp(drift * held) - 1) - cost
            after = min(n - 1, xb + 40)
            best = float(sgn * (np.max(c[xb:after + 1]) / fill - 1)) if sgn > 0 else float(sgn * (np.min(c[xb:after + 1]) / fill - 1))
            trades.append(dict(base, trade=label, ret=float(ret), drift=float(dr), held=int(held),
                               worst=float(worst), best_after=best, took=False, why=why))
            events.append(dict(sym=sym, kind=kind, tf=tf, trade=label, t=str(df.index[e]), born=str(df.index[r["born"]]),
                               ret=round(float(ret), 5), held=int(held), why=why, call=rd["read_call"],
                               pairs=r["pairs"], live=r["live_bars"]))
    return trades, breaks, events


def fold_trades(rows):
    keep = R.KEYS
    R.KEYS = KEYS
    try:
        return R.fold(rows)
    finally:
        R.KEYS = keep


def fold_breaks(rows):
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d["ups"] = d.up.astype(int)
    d["ft_ok"] = (d.follow >= 1.0).astype(int)
    d["ft2"] = (d.follow >= 2.0).astype(int)
    d["stuck"] = (d.end20 <= 0).astype(int)
    g = d.groupby(BKEYS, observed=True)
    return g.agg(n=("up", "size"), ups=("ups", "sum"), sum_follow=("follow", "sum"), sum_end=("end20", "sum"),
                 ft_ok=("ft_ok", "sum"), ft2=("ft2", "sum"), stuck=("stuck", "sum"),
                 sum_age=("age", "sum"), sum_h=("height", "sum"), sum_live=("live", "sum")).reset_index()


def bblock(g):
    n = float(g["n"].sum())
    if not n:
        return None
    return dict(n=int(n), up=float(g.ups.sum() / n), follow=float(g.sum_follow.sum() / n),
                end20=float(g.sum_end.sum() / n), ft_ok=float(g.ft_ok.sum() / n), ft2=float(g.ft2.sum() / n),
                stuck=float(g.stuck.sum() / n), age=float(g.sum_age.sum() / n),
                height=float(g.sum_h.sum() / n), live=float(g.sum_live.sum() / n))


def bby(f, cols):
    return {(k if isinstance(k, str) else " | ".join(k)): bblock(g) for k, g in f.groupby(cols, observed=True)}


def _work(args):
    sym, kind, start = args
    trades, breaks, events, errs = [], [], [], []
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, None, [], ["%s %s: %s" % (kind, sym, ex)]
    for tf in TFS:
        if tf not in frames:
            continue
        try:
            t_, b_, e_ = study_frame(sym, kind, tf, frames, start)
            trades += t_; breaks += b_; events += e_
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    ft = fold_trades(trades) if trades else None
    fb = fold_breaks(breaks) if breaks else None
    # every return, unfolded, so a median can be taken centrally: an average alone lets one
    # trade carry a whole column (the daily was +2.83% on the strength of a single +167%)
    rets = [(t["trade"], t["tf"], float(t["ret"])) for t in trades]
    return ft, fb, events[:400], errs, rets


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    global OUT, EVENTS_OUT
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = OUT.replace(".json", "_focus.json"); EVENTS_OUT = EVENTS_OUT.replace(".csv.gz", "_focus.csv.gz")
    names = R._by_size(names)
    R.quiet_workers()
    tparts, bparts, events, done, errs, raw = [], [], [], 0, [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for tp, bp, ev, err, rr in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1; errs += err or []; raw += rr
            if tp is not None:
                tparts.append(tp)
            if bp is not None:
                bparts.append(bp)
            events += ev
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    if not tparts:
        print("  nothing found"); return
    ft = pd.concat(tparts, ignore_index=True)
    fb = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    # the middle trade, and the average once the best 2% are dropped: an outlier cannot carry these
    middles = {}
    if raw:
        rw = pd.DataFrame(raw, columns=["trade", "tf", "ret"])
        for (tr_, tf_), g in rw.groupby(["trade", "tf"], observed=True):
            v = np.sort(g.ret.values)
            cut = v[:max(1, len(v) - max(1, len(v) // 50))]
            middles["%s | %s" % (tr_, tf_)] = dict(
                n=int(len(v)), mean=float(v.mean()), median=float(np.median(v)),
                trimmed=float(cut.mean()), best=float(v[-1]), worst=float(v[0]),
                won=float((v > 0).mean()))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         trades=TRADES, reads=READS, shape="his EQ: a series of higher lows and lower highs, tightening"),
               breaks=(dict(all=bblock(fb), by_tf=bby(fb, ["tf"]), by_kind=bby(fb, ["kind"]), by_era=bby(fb, ["era"]),
                            **{"by_" + r_: bby(fb, [r_]) for r_ in READS},
                            **{"by_tf_" + r_: bby(fb, ["tf", r_]) for r_ in READS},
                            by_touch_prior=bby(fb, ["read_touch", "read_prior"]),
                            by_touch_prior_tf=bby(fb, ["read_touch", "read_prior", "tf"]),
                            by_touch_prior_era=bby(fb, ["read_touch", "read_prior", "era"])) if len(fb) else {}),
               middles=middles,
               trades=dict(by_trade=R.by(ft, ["trade"]), by_trade_tf=R.by(ft, ["trade", "tf"]),
                           by_trade_kind=R.by(ft, ["trade", "kind"]), by_trade_era=R.by(ft, ["trade", "era"]),
                           by_trade_call_tf=R.by(ft, ["trade", "read_call", "tf"]),
                           **{"by_trade_" + r_: R.by(ft, ["trade", r_]) for r_ in READS}))
    json.dump(res, open(OUT, "w"))
    pd.DataFrame(events).to_csv(EVENTS_OUT, index=False, compression="gzip")
    print()
    print("  EQ (COIL) STUDY  %d names, %d breaks, %d trades  (%.0fs)" % (
        len(names), int(fb.n.sum()) if len(fb) else 0, int(ft.n.sum()), time.time() - t0))
    b = res["breaks"].get("all")
    if b:
        print("  every break: %d, up %.0f%%, follow-through %.1f normal bars, 2+ bars %.0f%%, back inside after 20 %.0f%%, shape %.0f bars, live %.1f" % (
            b["n"], 100 * b["up"], b["follow"], 100 * b["ft2"], 100 * b["stuck"], b["age"], b["live"]))
        for r_ in READS:
            print("   by %s" % r_.replace("read_", ""))
            for k, v in sorted((res["breaks"].get("by_" + r_) or {}).items(), key=lambda x: -x[1]["up"]):
                print("     %-38s n %7d  up %2.0f%%  follow %.1f  2+ %2.0f%%  back inside %2.0f%%" % (
                    k, v["n"], 100 * v["up"], v["follow"], 100 * v["ft2"], 100 * v["stuck"]))
    print()
    # the whole point of the call: does filtering by it turn any trade positive?
    print()
    print("  every trade, filtered by the call (the middle trade in brackets)")
    for tr in TRADES:
        for cl in ("the call is UP (both reads agree)", "the call is DOWN (both reads agree)"):
            cells = []
            for tf in TFS:
                v = res["trades"]["by_trade_call_tf"].get("%s | %s | %s" % (tr, cl, tf))
                cells.append("%+7.2f%% n%-6d" % (100 * v["ret"], v["n"]) if v else "%15s" % "-")
            print("    %-46s %-38s %s" % (tr[:46], cl.replace(" (both reads agree)", ""), " ".join(cells)))
    mid = res.get("middles") or {}
    print()
    print("  the middle trade, so one winner cannot carry a column")
    print("    %-56s %s" % ("", "  ".join("%9s" % t for t in TFS)))
    for tr in TRADES:
        cells = []
        for tf in TFS:
            m = mid.get("%s | %s" % (tr, tf))
            cells.append("%+8.2f%%" % (100 * m["median"]) if m else "        -")
        print("    %-56s %s" % (tr[:56], "  ".join("%9s" % c for c in cells)))
    print()
    print("  the trades, per trade after costs (and the edge over just holding those bars)")
    print("    %-56s %s" % ("", "  ".join("%9s" % t for t in TFS)))
    for tr in TRADES:
        cells = []
        for tf in TFS:
            x = res["trades"]["by_trade_tf"].get("%s | %s" % (tr, tf))
            cells.append("%+8.2f%%" % (100 * x["ret"]) if x else "        -")
        print("    %-56s %s" % (tr[:56], "  ".join("%9s" % c for c in cells)))
    print("    edges over drift:")
    for tr in TRADES:
        cells = []
        for tf in TFS:
            x = res["trades"]["by_trade_tf"].get("%s | %s" % (tr, tf))
            cells.append("%+8.2f%%" % (100 * x["edge"]) if x else "        -")
        print("    %-56s %s" % (tr[:56], "  ".join("%9s" % c for c in cells)))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
