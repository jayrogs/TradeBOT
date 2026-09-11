"""eq_break.py -- ranges ("EQ") as the owner trades them: get positioned at an
edge to catch the BREAK, and read which way it will break.

Owner 2026-09-08: "it's buying the floor or selling the ceiling in order to be
positioned for the eq to break one way or the other ... try different
methodologies to see if it's worth expecting a bear eq break or a bull break.
eqs are money because they usually break with follow through, eqs can't
continue forever, and the longer they go on the clearer the breaks and trades
are."

Three readings of "the range":
  pivots      the box around four alternating pivots (two higher/equal lows,
              two lower/equal highs), dead on a close beyond an edge (his rule
              in structure.py, box form). Short-lived by nature.
  rectangle   a sideways stretch: over the last 30 bars the highest high and
              lowest low are at most 4 normal bars apart and BOTH edges were
              touched at least twice; alive while closes stay inside; dead on a
              close beyond an edge. This is the long range a trader draws.
  rectangle60 the same with a 60-bar window (older, cleaner).

Part 1, which way does it break, and does it follow through: for every range
that died on a close beyond an edge, the direction (up/down), the move over
the next 20 bars in normal bars (follow-through), and what was true just
before: the trend before the range was born, the chart one size up, the
range's age, which edge was touched more, whether lows were rising / highs
falling inside it, where the last close sat, RSI, the 50 EMA slope.

Part 2, the positioned trades, fill at the next open after the signal (rule 14):
  buy the floor, hold for the break     out at the next open if it breaks DOWN
                                         (close under the floor); once it breaks
                                         UP, trail 5 normal bars under the highest
                                         close (chandelier)
  short the ceiling, hold for the break  the mirror
  buy the break up                       buy the next open after a close above
                                         the ceiling; out on a close back inside
                                         the box; else chandelier 5
  short the break down                   the mirror
Costs by class, compared to the drift over the same bars. Trades are also cut by
the direction reads, so "buy the floor only when the read says up" can be seen.

    pythonw studies/eq_break.py --procs 20 --log logs/eq_break.log   [--focus]
Writes validation/eq_break.json (+_focus) and validation/eq_break_events.csv.gz.
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_study as EQ             # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
OUT = os.path.join("validation", "eq_break.json")
EVENTS_OUT = os.path.join("validation", "eq_break_events.csv.gz")
MODES = ["pivots", "rectangle", "rectangle60"]
TOUCH = 0.25
CAP_DAYS = 30
KEYS = ["mode", "trade", "tf", "kind", "era", "read_prior", "read_next", "read_age", "read_touch", "read_inside", "read_where", "read_call"]


def rectangle(df, W=30, max_h=4.0, min_touch=2):
    """Rolling rectangle: floor[], ceil[], rid[], list of (birth, death, how)."""
    c = df["Close"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df)
    hh = pd.Series(h).rolling(W).max().values; ll = pd.Series(l).rolling(W).min().values
    floor = np.full(n, np.nan); ceil = np.full(n, np.nan); rid = np.full(n, -1)
    out = []
    alive = False; f = ce = np.nan; born = None
    for i in range(W, n):
        a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
        if not np.isfinite(a):
            continue
        tol = P.SAME_LEVEL_ATR * a
        if alive:
            if c[i] > ce + tol or c[i] < f - tol:
                out.append((born, i, "a close above the ceiling" if c[i] > ce + tol else "a close under the floor"))
                alive = False; born = None
            else:
                floor[i] = f; ceil[i] = ce; rid[i] = len(out)
                continue
        # not alive: can a rectangle be declared on this window?
        height = (hh[i] - ll[i]) / a
        if height < 1.0 or height > max_h:
            continue
        w_l = l[i - W + 1:i + 1]; w_h = h[i - W + 1:i + 1]
        if np.sum(w_l <= ll[i] + TOUCH * a) < min_touch or np.sum(w_h >= hh[i] - TOUCH * a) < min_touch:
            continue
        alive = True; f = float(ll[i]); ce = float(hh[i]); born = i - W + 1
        floor[i] = f; ceil[i] = ce; rid[i] = len(out)
    if alive and born is not None:
        out.append((born, n - 1, "still open"))
    return floor, ceil, rid, out, atr


def get_ranges(df, mode):
    if mode == "pivots":
        return EQ.ranges(df, "box_close")
    if mode == "rectangle":
        return rectangle(df, 30)
    return rectangle(df, 60, max_h=6.0)


def pivot_lists(piv):
    """(bars, prices) for the lows and for the highs, sorted by bar: the shape reads() wants.
    The live scan and the live chart must build it the same way as the study."""
    _lows = sorted((j, p) for ci, j, p, k_, lab in piv if k_ == "low")
    _highs = sorted((j, p) for ci, j, p, k_, lab in piv if k_ == "high")
    return ([j for j, p in _lows], [p for j, p in _lows]), ([j for j, p in _highs], [p for j, p in _highs])


def reads(i, born, df, c, h, l, atr, floor, ceil, state, hi_state, rsi, ema50, piv_lows, piv_highs):
    """What a trader could see at bar i (inside a live range born at `born`)."""
    a = atr[i]
    f, ce = floor[i], ceil[i]
    # the trend before the range was born
    pre = state[max(0, born - 1)] if born > 0 else "FLAT"
    prior = "came from an uptrend" if pre == "UP" else "came from a downtrend" if pre == "DOWN" else "came from nothing (flat)"
    nxt = "next chart up" if str(hi_state[i]) == "UP" else "next chart down" if str(hi_state[i]) == "DOWN" else "next chart flat"
    age = i - born + 1
    age_b = "young (under 10 bars)" if age < 10 else "10-30 bars" if age < 30 else "30-60 bars" if age < 60 else "old (60+ bars)"
    tf_ = int(np.sum(l[born:i + 1] <= f + TOUCH * a)); tc = int(np.sum(h[born:i + 1] >= ce - TOUCH * a))
    touch = "floor tested more" if tf_ > tc else "ceiling tested more" if tc > tf_ else "both tested the same"
    # inside the range: are the lows rising, the highs falling? (bisect on the pivot bars)
    import bisect
    lj, lp = piv_lows; hj, hp = piv_highs
    lows_in = lp[bisect.bisect_left(lj, born):bisect.bisect_right(lj, i)]
    highs_in = hp[bisect.bisect_left(hj, born):bisect.bisect_right(hj, i)]
    rising = len(lows_in) >= 2 and lows_in[-1] > lows_in[0] + 0.15 * a
    falling = len(highs_in) >= 2 and highs_in[-1] < highs_in[0] - 0.15 * a
    inside = ("lows rising, highs flat (pressing the ceiling)" if rising and not falling else
              "highs falling, lows flat (pressing the floor)" if falling and not rising else
              "both squeezing (a coil)" if rising and falling else "flat inside")
    where = (c[i] - f) / (ce - f) if ce > f else 0.5
    where_b = "last close near the floor" if where < 0.33 else "last close in the middle" if where < 0.67 else "last close near the ceiling"
    # the call: the three reads that carry information, added up
    score = (1 if nxt == "next chart up" else -1 if nxt == "next chart down" else 0)         + (1 if rising and not falling else -1 if falling and not rising else 0)         + (1 if tc > tf_ else -1 if tf_ > tc else 0)
    call = "the call is UP (2 or 3 reads agree)" if score >= 2 else "the call is DOWN (2 or 3 reads agree)" if score <= -2 else "no clear call"
    return dict(read_prior=prior, read_next=nxt, read_age=age_b, read_touch=touch, read_inside=inside, read_where=where_b, read_call=call,
                rsi=float(rsi[i]), ema_slope="50 EMA rising" if ema50[i] > ema50[max(0, i - 10)] else "50 EMA falling", age=int(age))


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return [], [], []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df)
    state = ST.states(df, causal=True)
    hdf = frames.get(R.UP.get(tf))
    hi_state = B.higher_view(df, tf, hdf, R.UP[tf])[0] if hdf is not None and len(hdf) >= 60 else np.array(["NA"] * n, dtype=object)
    rsi = XM.rsi(c); ema50 = XM.ema(c, 50)
    piv = ST.pivots(df)
    piv_lows, piv_highs = pivot_lists(piv)
    cost = B.CLASS_COST.get(kind, B.COST)
    cap = CAP_DAYS * B.BARS_DAY[tf]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid_t = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    trades, breaks, events = [], [], []
    for mode in MODES:
        floor, ceil, rid, rlist, _ = get_ranges(df, mode)
        # ---- part 1: every break, its direction and follow-through
        for r_, (born, dead, how) in enumerate(rlist):
            if how == "still open" or dead + 21 >= n or dead - 1 < born or born < 60:
                continue
            i = dead - 1                                   # the last bar inside
            if rid[i] != r_ or not np.isfinite(floor[i]):
                continue
            a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
            if not np.isfinite(a):
                continue
            up = "above" in how or "higher high" in how
            rd = reads(i, born, df, c, h, l, atr, floor, ceil, state, hi_state, rsi, ema50, piv_lows, piv_highs)
            edge = ceil[i] if up else floor[i]
            follow = (np.max(c[dead:dead + 21]) - edge) / a if up else (edge - np.min(c[dead:dead + 21])) / a
            end20 = (c[dead + 20] - edge) / a if up else (edge - c[dead + 20]) / a
            t = df.index[dead]
            era = "before" if t < start else "first" if t < mid_t else "second"
            breaks.append(dict(mode=mode, tf=tf, kind=kind, era=era, up=bool(up), follow=float(follow), end20=float(end20),
                               height=float((ceil[i] - floor[i]) / a), **{k: v for k, v in rd.items() if k.startswith("read_")}, age=rd["age"]))
        # ---- part 2: the positioned trades
        busy = {}
        for i in range(60, n - 2):
            if rid[i] < 0 or not np.isfinite(floor[i]):
                continue
            a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
            if not np.isfinite(a):
                continue
            r_ = rid[i]; born = rlist[r_][0] if r_ < len(rlist) else i
            f, ce = floor[i], ceil[i]
            sigs = []
            if l[i] <= f + TOUCH * a and c[i] >= f - P.SAME_LEVEL_ATR * a:
                sigs.append(("buy the floor, hold for the break", +1))
            if h[i] >= ce - TOUCH * a and c[i] <= ce + P.SAME_LEVEL_ATR * a:
                sigs.append(("short the ceiling, hold for the break", -1))
            # the break itself: the close that ended the range is bar i+? -> handled below on death bars
            # the free ride: same buy, sell just enough at the far edge that the rest cannot lose
            sigs += [(name.replace("hold for the break", "partial at the far edge, free ride"), sgn) for name, sgn in sigs]
            for name, sgn in sigs:
                e = i + 1
                if e <= busy.get(name, -1):
                    continue
                rd = reads(i, born, df, c, h, l, atr, floor, ceil, state, hi_state, rsi, ema50, piv_lows, piv_highs)
                if "free ride" in name:
                    res = free_ride(sgn, c, o, h, l, atr, e, f, ce, n, cap, day)
                else:
                    res = hold_for_break(sgn, c, o, h, l, atr, floor, ceil, rid, r_, e, f, ce, n, cap, day)
                if res is None:
                    busy[name] = n; continue
                xb, xpx, why, worst = res
                busy[name] = xb + 1
                fill = o[e]
                ret = sgn * (xpx / fill - 1) - cost
                t = df.index[e]; era = "before" if t < start else "first" if t < mid_t else "second"
                trades.append(dict(mode=mode, trade=name, tf=tf, kind=kind, era=era, ret=float(ret), held=int(xb + 1 - e), why=why,
                                   took=False, worst=float(worst), best_after=0.0, drift=float(sgn * (np.exp(drift * (xb + 1 - e)) - 1) - cost),
                                   **{k: v for k, v in rd.items() if k.startswith("read_")}))
                if mode != "pivots" and sgn > 0:
                    events.append(dict(mode=mode, sym=sym, kind=kind, tf=tf, t=str(t), ret=round(float(ret), 5), held=int(xb + 1 - e), why=why,
                                       floor=float(f), ceil=float(ce), born=str(df.index[born])))
        # the breakout entries: the bar that closed beyond an edge
        for r_, (born, dead, how) in enumerate(rlist):
            if how == "still open" or dead + 2 >= n or born < 60 or dead - 1 < born:
                continue
            if "close" not in how:
                continue
            up = "above" in how
            name = "buy the break up" if up else "short the break down"
            sgn = 1 if up else -1
            i = dead; e = dead + 1
            if e <= busy.get(name, -1):
                continue
            f, ce = float(floor[dead - 1]), float(ceil[dead - 1])
            rd = reads(dead - 1, born, df, c, h, l, atr, floor, ceil, state, hi_state, rsi, ema50, piv_lows, piv_highs)
            res = ride_break(sgn, c, o, h, l, atr, e, f, ce, n, cap, day)
            if res is None:
                busy[name] = n; continue
            xb, xpx, why, worst = res
            busy[name] = xb + 1
            fill = o[e]
            ret = sgn * (xpx / fill - 1) - cost
            t = df.index[e]; era = "before" if t < start else "first" if t < mid_t else "second"
            trades.append(dict(mode=mode, trade=name, tf=tf, kind=kind, era=era, ret=float(ret), held=int(xb + 1 - e), why=why,
                               took=False, worst=float(worst), best_after=0.0, drift=float(sgn * (np.exp(drift * (xb + 1 - e)) - 1) - cost),
                               **{k: v for k, v in rd.items() if k.startswith("read_")}))
    return trades, breaks, events


def hold_for_break(sgn, c, o, h, l, atr, floor, ceil, rid, r_, e, f, ce, n, cap, day):
    """Long from the floor (sgn +1) or short from the ceiling (-1). Out at the next
    open if the range breaks against us; once it breaks our way, chandelier 5."""
    fill = o[e]; peak = c[e]; trough = c[e]; worst = 0.0; broke = False
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, sgn * (c[k] / fill - 1))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        tol = P.SAME_LEVEL_ATR * a
        if not broke:
            if sgn > 0 and c[k] < f - tol:
                return k, o[k + 1], "broke the wrong way", worst
            if sgn < 0 and c[k] > ce + tol:
                return k, o[k + 1], "broke the wrong way", worst
            if sgn > 0 and c[k] > ce + tol:
                broke = True
            if sgn < 0 and c[k] < f - tol:
                broke = True
        else:
            if sgn > 0 and c[k] < peak - 5 * a:
                return k, o[k + 1], "broke our way, trailed out", worst
            if sgn < 0 and c[k] > trough + 5 * a:
                return k, o[k + 1], "broke our way, trailed out", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time (never broke)", worst
    return None


def free_ride(sgn, c, o, h, l, atr, e, f, ce, n, cap, day):
    """His note: "if you can buy a HL and sell partial at LH you have a risk free trade
    and it doesn't really matter which way it breaks." Long from the floor: the stop
    is a close under the floor; at the ceiling sell the share that makes the rest free
    (share = risk / (risk + gain)); then hold the rest: out at the stop (net about zero)
    or, once it breaks up, trail 5 normal bars under the highest close. Mirror for the short.
    Returns a blended sale price so the trade's return is the whole position's."""
    fill = o[e]
    a0 = atr[e - 1] if np.isfinite(atr[e - 1]) else 0.0
    tol0 = P.SAME_LEVEL_ATR * a0
    stop = f - tol0 if sgn > 0 else ce + tol0
    target = ce if sgn > 0 else f
    risk = abs(fill - stop); gain = abs(target - fill)
    if gain <= 0 or risk <= 0:
        return None
    share = min(1.0, risk / (risk + gain))
    took = False; peak = c[e]; trough = c[e]; worst = 0.0; broke = False
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, sgn * (c[k] / fill - 1))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        tol = P.SAME_LEVEL_ATR * a
        if not took and ((sgn > 0 and h[k] >= target and k > e) or (sgn < 0 and l[k] <= target and k > e)):
            took = True
        blend = lambda px: (share * target + (1 - share) * px) if took else px
        if not broke:
            if (sgn > 0 and c[k] < f - tol) or (sgn < 0 and c[k] > ce + tol):
                return k, blend(o[k + 1]), ("stopped, the rest was free" if took else "broke the wrong way before the partial"), worst
            if (sgn > 0 and c[k] > ce + tol) or (sgn < 0 and c[k] < f - tol):
                broke = True
        else:
            if (sgn > 0 and c[k] < peak - 5 * a) or (sgn < 0 and c[k] > trough + 5 * a):
                return k, blend(o[k + 1]), "broke our way, trailed out", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, blend(c[k]), "session end", worst
        if k - e >= cap:
            return k, blend(o[k + 1]), "time (never broke)", worst
    return None


def ride_break(sgn, c, o, h, l, atr, e, f, ce, n, cap, day):
    """Entered after the close beyond the edge. Out on a close back inside the box; else chandelier 5."""
    fill = o[e]; peak = c[e]; trough = c[e]; worst = 0.0
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, sgn * (c[k] / fill - 1))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        if sgn > 0 and c[k] < ce:
            return k, o[k + 1], "fell back inside the box", worst
        if sgn < 0 and c[k] > f:
            return k, o[k + 1], "climbed back inside the box", worst
        if sgn > 0 and c[k] < peak - 5 * a:
            return k, o[k + 1], "trailed out", worst
        if sgn < 0 and c[k] > trough + 5 * a:
            return k, o[k + 1], "trailed out", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time", worst
    return None


def fold_trades(rows):
    R.KEYS, keep = KEYS, R.KEYS
    try:
        return R.fold(rows)
    finally:
        R.KEYS = keep


BKEYS = ["mode", "tf", "kind", "era", "read_prior", "read_next", "read_age", "read_touch", "read_inside", "read_where", "read_call"]


def fold_breaks(rows):
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d["ups"] = d.up.astype(int)
    d["ft_ok"] = (d.follow >= 1.0).astype(int)          # followed through at least one normal bar beyond the edge
    d["ft2"] = (d.follow >= 2.0).astype(int)
    d["stuck"] = (d.end20 <= 0).astype(int)              # 20 bars later back at or inside the edge
    g = d.groupby(BKEYS, observed=True)
    return g.agg(n=("up", "size"), ups=("ups", "sum"), sum_follow=("follow", "sum"), sum_end=("end20", "sum"),
                 ft_ok=("ft_ok", "sum"), ft2=("ft2", "sum"), stuck=("stuck", "sum"), sum_age=("age", "sum"), sum_h=("height", "sum")).reset_index()


def bblock(g):
    n = float(g["n"].sum())
    if not n:
        return None
    return dict(n=int(n), up=float(g.ups.sum() / n), follow=float(g.sum_follow.sum() / n), end20=float(g.sum_end.sum() / n),
                ft_ok=float(g.ft_ok.sum() / n), ft2=float(g.ft2.sum() / n), stuck=float(g.stuck.sum() / n),
                age=float(g.sum_age.sum() / n), height=float(g.sum_h.sum() / n))


def bby(f, cols):
    return {(k if isinstance(k, str) else " | ".join(k)): bblock(g) for k, g in f.groupby(cols, observed=True)}


def _work(args):
    sym, kind, start = args
    errs, trades, breaks, events = [], [], [], []
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
    return fold_trades(trades), fold_breaks(breaks), events, errs


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
    tparts, bparts, events, done, errs = [], [], [], 0, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for tp, bp, ev, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1; errs += err or []
            if tp is not None:
                tparts.append(tp)
            if bp is not None:
                bparts.append(bp)
            events += ev
            if done % 50 == 0:
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    ft = pd.concat(tparts, ignore_index=True); fb = pd.concat(bparts, ignore_index=True)
    reads_ = ["read_call", "read_next", "read_inside", "read_touch", "read_age", "read_prior", "read_where"]
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS, modes=MODES,
                         trades=["buy the floor, hold for the break", "buy the floor, partial at the far edge, free ride",
                                 "short the ceiling, hold for the break", "short the ceiling, partial at the far edge, free ride",
                                 "buy the break up", "short the break down"],
                         reads=reads_),
               breaks=dict(by_mode=bby(fb, ["mode"]), by_mode_tf=bby(fb, ["mode", "tf"]), by_mode_kind=bby(fb, ["mode", "kind"]),
                           by_mode_era=bby(fb, ["mode", "era"]),
                           **{"by_mode_" + r_: bby(fb, ["mode", r_]) for r_ in reads_},
                           **{"by_mode_tf_" + r_: bby(fb, ["mode", "tf", r_]) for r_ in reads_}),
               trades=dict(by_mode_trade=R.by(ft, ["mode", "trade"]), by_mode_trade_tf=R.by(ft, ["mode", "trade", "tf"]),
                           by_mode_trade_kind=R.by(ft, ["mode", "trade", "kind"]), by_mode_trade_era=R.by(ft, ["mode", "trade", "era"]),
                           by_mode_trade_call_tf=R.by(ft, ["mode", "trade", "read_call", "tf"]),
                           **{"by_mode_trade_" + r_: R.by(ft, ["mode", "trade", r_]) for r_ in reads_}))
    json.dump(res, open(OUT, "w"))
    pd.DataFrame(events).to_csv(EVENTS_OUT, index=False)
    print("  EQ BREAK STUDY  %d names, %d breaks, %d trades  (%.0fs)" % (len(names), int(fb.n.sum()), int(ft.n.sum()), time.time() - t0))
    for mode in MODES:
        b = res["breaks"]["by_mode"].get(mode)
        if b:
            print("\n  %-12s breaks %7d  up %2.0f%%  follow-through avg %.1f bars, 1+ bar %2.0f%%, 2+ bars %2.0f%%, back inside after 20 bars %2.0f%%  age %.0f" % (
                mode, b["n"], 100 * b["up"], b["follow"], 100 * b["ft_ok"], 100 * b["ft2"], 100 * b["stuck"], b["age"]))
        for tr in res["meta"]["trades"]:
            print("    %-40s " % tr + "  ".join("%s %+.2f%%/%+.2f%%" % (tf, 100 * x["ret"], 100 * x["edge"]) for tf in TFS
                                              for x in [res["trades"]["by_mode_trade_tf"].get("%s | %s | %s" % (mode, tr, tf))] if x))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
