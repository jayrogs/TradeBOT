"""eq_freeride.py -- the EQ trade the way he trades it (2026-09-10).

  "how do you think you know whether to buy or sell in these eq's? usually its based on
   whatever higher timeframe shapes going on. Like NVDA, that shit is so much a downtrend,
   like wtf? why would be long that"
  "the idea is buying the floor and selling the LH ideally to make a risk free position"

Two things change from eq_coil_study.py:

1. DIRECTION COMES FROM THE BIGGER CHART. Every EQ is traded both ways, and each trade is
   tagged WITH, AGAINST or NO TREND against several readings of "the higher timeframe shape":
     h_next    the engine's trend on the chart one size up (a higher low and a higher high)
     h_two     the same, two sizes up
     h_both    the next chart and two up agree
     h_ema     the chart one size up sits above its 50 EMA and the EMA is rising (or the mirror)
     h_daily   the daily chart's trend, whatever size the EQ is (weekly for a daily EQ)
   All of them read only from higher bars that had CLOSED before the entry decision.

2. THE ENTRY IS THE HIGHER LOW ITSELF, not a later touch of the floor. In a tightening EQ
   price does not come back to the last higher low; it makes a new, higher one. So the long is
   bought at the next open after a higher low CONFIRMS inside the live EQ (the same timing as the
   trend ride), the stop is a wick through that higher low, and the target is the lower high
   above it. The short is the mirror: a lower high confirms, short the next open, stop a wick
   over it, target the higher low below.

Managed four ways:
     free ride, rest keeps the stop      at the far line sell the share that makes the rest free;
                                         the rest keeps the original stop (worst case about even)
     free ride, rest moves to breakeven  same partial, then the rest's stop moves to the entry
     hold for the break, no partial      no partial: the stop, or trail once it breaks our way
     all out at the lower high           everything off at the far line: the pure HL-to-LH trade
Once price breaks through the far line our way, what is left trails 5 normal bars behind the
best close. A bar that touches both the stop and the far line counts as stopped (the careful
reading). 5m/15m stocks close at the bell. Costs are taken out.

Every number is reported with the MIDDLE trade beside the average, how often the free ride was
reached, and the three eras.

    pythonw studies/eq_freeride.py --procs 20 --log logs/eq_freeride.log
Writes validation/eq_freeride.json
"""
import bisect
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

TFS = ["5m", "15m", "1h", "4h", "1d"]
CAP_DAYS = 30
TRAIL = 5.0
OUT = os.path.join("validation", "eq_freeride.json")
MODES = [("free ride, rest keeps the stop", "keep"),
         ("free ride, rest moves to breakeven", "be"),
         ("hold for the break, no partial", "hold"),
         ("all out at the lower high", "all")]
# RESTING LIMIT ORDERS (2026-09-10). Buying after the higher low CONFIRMS arrives two bars late:
# price has already bounced most of the way to the lower high, so the far line sits CLOSER than the
# stop (median 0.8x the risk on 10 big names) and the trade wins 2 in 3 yet averages about nothing.
# "Buying the floor" done honestly is a resting buy limit down near the floor while the EQ is live.
# Three depths, measured up the box from the floor. The stop is the break rule of the EQ itself (a
# wick under the floor); the target is the lower high. The order rests only on bars after the EQ
# became knowable, at the levels as they stood on that bar. On the fill bar the far line does not
# count (it may have printed before the fill), but the stop does (the careful reading). A gap
# through the stop fills at the open and is stopped at the next open.
LIMITS = [(0.0, "limit at the floor"), (0.25, "limit a quarter up the box"), (0.5, "limit halfway up the box")]
VARIANTS = [m[0] for m in MODES] + ["%s, %s" % (lab, m[0]) for _, lab in LIMITS for m in MODES]
READS = ["h_ema_daily", "h_ema_both", "h_ema200", "h_big", "h_swings", "h_swings_daily", "h_daily_big", "h_weekly",
         "h_both", "h_next", "h_two", "h_ema", "h_daily"]
READ_NAMES = {"h_big": "the shape one size up AND on the daily agree",
              "h_swings": "the shape one size up (last high and last low both lower, or both higher)",
              "h_swings_daily": "the shape on the daily (weekly for a daily EQ)",
              "h_ema_daily": "the daily against its 50 EMA",
              "h_daily_big": "the shape on the daily, counting only big swings (3 normal bars or more)",
              "h_weekly": "the shape on the weekly",
              "h_ema200": "the daily above or below its 200 EMA",
              "h_ema_both": "the daily's 50 EMA read and 200 EMA read agree",
              "h_both": "the engine's trend one size up AND two up agree",
              "h_next": "the engine's trend one size up",
              "h_two": "the engine's trend two sizes up",
              "h_ema": "the chart one size up against its 50 EMA",
              "h_daily": "the engine's trend on the daily"}
# WHY THE SHAPE READS EXIST (2026-09-10): his NVDA example, May 2022, one of the clearest declines
# there is, came out as "no trend" on the engine's trend reading for both the 4h and the daily.
# Every bounce wicked over the last lower high and switched the trend off until a new lower high
# and lower low appeared. The shape read asks only what the eye asks: is the last swing high lower
# than the one before, and the last swing low lower than the one before.
# CHECKED AGAINST HIS EYE (2026-09-10), eight obvious trends (NVDA May 2022 down, Jun 2023 up, Mar 2024
# up; TSLA Dec 2022 down; BTC Jun 2022 down, Nov 2023 up; META Sep 2022 down; AAPL Jul 2023 up):
#   the daily against its rising/falling 50 EMA   8 of 8
#   the daily above/below its 200 EMA              8 of 8
#   every swing-shape read (4h, daily, big swings, weekly) missed several. Inside a big decline the
#   2-bar pivots flip on small bounces: NVDA's daily printed a "higher high" 27 cents above the last
#   lower high in the middle of a 60% crash. So the drawings and the page lead with the daily EMA.
TAGS = ["with", "against", "no trend"]


# ------------------------------------------------------------------ the bigger chart
def align(lower, ltf, higher, htf, values):
    """`values` (one per higher bar) as seen from each lower bar: only higher bars whose close
    came at or before the lower bar's close count."""
    n = len(lower)
    out = np.array(["NA"] * n, dtype=object)
    if higher is None or len(higher) < 60:
        return out
    lc = lower.index.values + pd.Timedelta(B.DUR[ltf]).to_timedelta64()
    hc = higher.index.values + pd.Timedelta(B.DUR[htf]).to_timedelta64()
    pos = np.searchsorted(hc, lc, side="right") - 1
    ok = pos >= 0
    out[ok] = np.asarray(values, dtype=object)[pos[ok]]
    return out


def higher_reads(df, tf, frames):
    n = len(df)
    na = np.array(["NA"] * n, dtype=object)
    cache = {}

    def state_of(htf):
        if htf is None:
            return na
        hdf = frames.get(htf)
        if hdf is None or len(hdf) < 60:
            return na
        if htf not in cache:
            cache[htf] = ST.states(hdf, causal=True)
        return align(df, tf, hdf, htf, cache[htf])

    up1 = R.UP.get(tf)
    up2 = R.UP.get(up1) if up1 else None
    h_next = state_of(up1)
    h_two = state_of(up2)
    h_daily = state_of("1d" if tf in ("5m", "15m", "1h", "4h") else "1w")
    h_ema = na.copy()
    hdf = frames.get(up1) if up1 else None
    if hdf is not None and len(hdf) >= 60:
        hc = hdf["Close"].values.astype(float)
        e50 = XM.ema(hc, 50)
        prev = np.r_[np.full(10, np.nan), e50[:-10]]
        slope = e50 - prev
        lab = np.where((hc > e50) & (slope > 0), "up", np.where((hc < e50) & (slope < 0), "down", "mixed")).astype(object)
        lab[~np.isfinite(slope)] = "NA"
        h_ema = align(df, tf, hdf, up1, lab)
    agree = (h_next == h_two) & np.isin(h_next.astype(str), ["UP", "DOWN"])
    h_both = np.where(agree, h_next, "none").astype(object)
    big_tf = "1d" if tf in ("5m", "15m", "1h", "4h") else "1w"
    h_swings = swings_of(df, tf, frames, up1)
    h_swings_daily = swings_of(df, tf, frames, big_tf)
    h_daily_big = swings_of(df, tf, frames, big_tf, min_atr=3.0)
    h_weekly = swings_of(df, tf, frames, "1w")
    h_ema_daily = ema_of(df, tf, frames, big_tf)
    h_ema200 = ema_of(df, tf, frames, big_tf, span=200, slope=False)
    ema_agree = (h_ema_daily == h_ema200) & np.isin(h_ema_daily.astype(str), ["up", "down"])
    h_ema_both = np.where(ema_agree, h_ema_daily, "none").astype(object)
    agree2 = (h_swings == h_swings_daily) & np.isin(h_swings.astype(str), ["up", "down"])
    h_big = np.where(agree2, h_swings, "none").astype(object)
    return dict(h_next=h_next, h_two=h_two, h_both=h_both, h_ema=h_ema, h_daily=h_daily,
                h_swings=h_swings, h_swings_daily=h_swings_daily, h_ema_daily=h_ema_daily, h_big=h_big,
                h_daily_big=h_daily_big, h_weekly=h_weekly, h_ema200=h_ema200, h_ema_both=h_ema_both)


def swings_of(df, tf, frames, htf, min_atr=None):
    """The shape on a bigger chart, as the eye reads it: the last confirmed swing high against the
    one before it, and the last confirmed swing low against the one before it. Both higher: up.
    Both lower: down. Anything else, including an equal one: mixed. Only pivots that had confirmed
    on a closed bigger bar count."""
    n = len(df)
    na = np.array(["NA"] * n, dtype=object)
    hdf = frames.get(htf) if htf else None
    if hdf is None or len(hdf) < 60:
        return na
    piv = ST.pivots(hdf, min_atr) if min_atr else ST.pivots(hdf)
    hn = len(hdf)
    lab = np.array(["NA"] * hn, dtype=object)
    last_hi = last_lo = None
    p = 0
    for k in range(hn):
        while p < len(piv) and piv[p][0] <= k:
            ci, j, pr, kd, lb = piv[p]
            p += 1
            if kd == "high":
                last_hi = lb
            else:
                last_lo = lb
        if last_hi is None or last_lo is None:
            continue
        if last_hi == "HH" and last_lo == "HL":
            lab[k] = "up"
        elif last_hi == "LH" and last_lo == "LL":
            lab[k] = "down"
        else:
            lab[k] = "mixed"
    return align(df, tf, hdf, htf, lab)


def ema_of(df, tf, frames, htf, span=50, slope=True):
    """Close against its EMA on a bigger chart. With `slope`, the EMA must also be moving the same
    way over the last 10 bars, else mixed. Without it, simply above or below."""
    n = len(df)
    hdf = frames.get(htf) if htf else None
    if hdf is None or len(hdf) < max(60, span):
        return np.array(["NA"] * n, dtype=object)
    hc = hdf["Close"].values.astype(float)
    e = XM.ema(hc, span)
    if slope:
        sl = e - np.r_[np.full(10, np.nan), e[:-10]]
        lab = np.where((hc > e) & (sl > 0), "up", np.where((hc < e) & (sl < 0), "down", "mixed")).astype(object)
        lab[~np.isfinite(sl)] = "NA"
    else:
        lab = np.where(hc > e, "up", "down").astype(object)
        lab[:span] = "NA"
    return align(df, tf, hdf, htf, lab)


def tag(side, v):
    v = str(v)
    if v in ("UP", "up"):
        return "with" if side == "long" else "against"
    if v in ("DOWN", "down"):
        return "with" if side == "short" else "against"
    return "no trend"


# ------------------------------------------------------------------ the trade
def walk(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, day, mode, target_on_fill_bar=True):
    """From the fill at bar e. Returns (exit_bar, blended exit price, reached the far line,
    why, worst close against us, the bar the far line was reached or None)."""
    risk = abs(fill - stop)
    gain = abs(target - fill)
    if risk <= 0 or gain <= 0:
        return None
    share = risk / (risk + gain) if mode in ("keep", "be") else 0.0
    took = False
    took_bar = None
    broke = False
    stop_now = stop
    best = c[e]
    worst = 0.0

    def blend(px):
        return share * target + (1 - share) * px if took else px

    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, sgn * (c[k] / fill - 1))
        # the stop first: a bar that reaches both counts as stopped
        if (sgn > 0 and l[k] < stop_now) or (sgn < 0 and h[k] > stop_now):
            why = ("the rest was stopped after the free ride" if took and mode == "keep" else
                   "the rest came back to the entry" if took else
                   "stopped before it reached the far line")
            return k, blend(o[k + 1]), took, why, worst, took_bar
        if not took and (k > e or target_on_fill_bar) and ((sgn > 0 and h[k] >= target) or (sgn < 0 and l[k] <= target)):
            if mode == "all":
                return k, target, True, "all out at the far line", worst, k
            if mode in ("keep", "be"):
                took = True
                took_bar = k
                if mode == "be":
                    stop_now = fill
        if not broke:
            tol = P.SAME_LEVEL_ATR * a
            if (sgn > 0 and h[k] > target + tol) or (sgn < 0 and l[k] < target - tol):
                broke = True
                best = c[k]
        if broke:
            best = max(best, c[k]) if sgn > 0 else min(best, c[k])
            if (sgn > 0 and c[k] < best - TRAIL * a) or (sgn < 0 and c[k] > best + TRAIL * a):
                return k, blend(o[k + 1]), took, "broke our way, trailed out", worst, took_bar
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, blend(c[k]), took, "session end", worst, took_bar
        if k - e >= cap:
            return k, blend(o[k + 1]), took, "time", worst, took_bar
    return None


def trades_for_frame(sym, kind, tf, frames, start, detail=False):
    df = frames.get(tf)
    if df is None or len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, cid, rs, atr = EC.coils(df)
    if not rs:
        return []
    piv = ST.pivots(df)
    pcis = [pv[0] for pv in piv]
    hr = higher_reads(df, tf, frames)
    cost = B.CLASS_COST.get(kind, B.COST)
    cap = CAP_DAYS * B.BARS_DAY[tf]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    out = []
    for r in rs:
        if not r["tradeable"] or r["born"] < 60:
            continue
        i, end = r["confirm"], r["end"]
        k0 = bisect.bisect_left(pcis, i)
        k1 = bisect.bisect_left(pcis, end)
        long_pv = next((pv for pv in piv[k0:k1] if pv[3] == "low" and pv[4] in ("HL", "EL")), None)
        short_pv = next((pv for pv in piv[k0:k1] if pv[3] == "high" and pv[4] in ("LH", "EH")), None)
        for side, pv in (("long", long_pv), ("short", short_pv)):
            if pv is None:
                continue
            ci, j, p, kd, lab = pv
            e = ci + 1
            if e >= n - 1:
                continue
            a = atr[ci] if np.isfinite(atr[ci]) and atr[ci] > 0 else np.nan
            if not np.isfinite(a):
                continue
            tol = P.SAME_LEVEL_ATR * a
            sgn = 1 if side == "long" else -1
            fill = o[e]
            if side == "long":
                stop = p - tol
                target = ceil[ci]
                if not np.isfinite(target) or not (stop < fill < target):
                    continue                       # opened under the higher low, or already past the far line
            else:
                stop = p + tol
                target = floor[ci]
                if not np.isfinite(target) or not (target < fill < stop):
                    continue
            t = df.index[e]
            era = "before" if t < start else "first" if t < mid else "second"
            tags = {k_: tag(side, hr[k_][ci]) for k_ in READS}
            rr_ = abs(target - fill) / abs(fill - stop)
            for vname, mode in MODES:
                res = walk(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, day, mode)
                if res is None:
                    continue
                xb, xpx, took, why, worst, took_bar = res
                held = xb + 1 - e
                ret = sgn * (xpx / fill - 1) - cost
                dr = sgn * (np.exp(drift * held) - 1) - cost
                row = dict(sym=sym, kind=kind, tf=tf, era=era, side=side, variant=vname, pivot=lab,
                           ret=float(ret), drift=float(dr), took=bool(took), held=int(held), why=why,
                           chase=float(abs(fill - p) / a), rr=float(rr_), **tags)
                if detail:
                    row.update(t=str(t), born=int(r["born"]), end=int(end), confirm=int(i), ci=int(ci), pj=int(j),
                               e=int(e), xb=int(xb), fill=float(fill), stop=float(stop), target=float(target),
                               took_bar=(int(took_bar) if took_bar is not None else None), pivot_price=float(p),
                               worst=float(worst), h_next_raw=str(hr["h_next"][ci]), h_two_raw=str(hr["h_two"][ci]),
                               h_swings_raw=str(hr["h_swings"][ci]), h_swings_daily_raw=str(hr["h_swings_daily"][ci]),
                               h_ema_daily_raw=str(hr["h_ema_daily"][ci]), h_daily_big_raw=str(hr["h_daily_big"][ci]),
                               h_weekly_raw=str(hr["h_weekly"][ci]), h_ema200_raw=str(hr["h_ema200"][ci]))
                out.append(row)
        # ---- the resting limit orders
        for frac, elab in LIMITS:
            for side in ("long", "short"):
                sgn = 1 if side == "long" else -1
                got = None
                for k in range(i + 1, min(end, n - 2) + 1):
                    fk = floor[k] if np.isfinite(floor[k]) else floor[k - 1]
                    ck = ceil[k] if np.isfinite(ceil[k]) else ceil[k - 1]
                    if not (np.isfinite(fk) and np.isfinite(ck)) or ck <= fk:
                        continue
                    lim = fk + frac * (ck - fk) if side == "long" else ck - frac * (ck - fk)
                    if side == "long" and l[k] <= lim:
                        got = (k, min(o[k], lim), fk, ck)
                        break
                    if side == "short" and h[k] >= lim:
                        got = (k, max(o[k], lim), fk, ck)
                        break
                if got is None:
                    continue
                k, fill, fk, ck = got
                a = atr[k - 1] if np.isfinite(atr[k - 1]) and atr[k - 1] > 0 else np.nan
                if not np.isfinite(a):
                    continue
                tol = P.SAME_LEVEL_ATR * a
                stop = fk - tol if side == "long" else ck + tol
                target = ck if side == "long" else fk
                if (side == "long" and fill >= target) or (side == "short" and fill <= target):
                    continue
                t = df.index[k]
                era = "before" if t < start else "first" if t < mid else "second"
                tags = {k_: tag(side, hr[k_][k - 1]) for k_ in READS}
                risk_ = abs(fill - stop)
                rr_ = abs(target - fill) / risk_ if risk_ > 0 else 0.0
                for vname, mode in MODES:
                    res = walk(sgn, c, o, h, l, atr, k, fill, stop, target, n, cap, day, mode, target_on_fill_bar=False)
                    if res is None:
                        continue
                    xb, xpx, took, why, worst, took_bar = res
                    held = xb + 1 - k
                    ret = sgn * (xpx / fill - 1) - cost
                    dr = sgn * (np.exp(drift * held) - 1) - cost
                    row = dict(sym=sym, kind=kind, tf=tf, era=era, side=side, variant="%s, %s" % (elab, vname),
                               pivot="limit", ret=float(ret), drift=float(dr), took=bool(took), held=int(held), why=why,
                               chase=float(frac), rr=float(rr_), **tags)
                    if detail:
                        prev = k - 1
                        row.update(t=str(t), born=int(r["born"]), end=int(end), confirm=int(i), ci=int(prev), pj=int(k),
                                   e=int(k), xb=int(xb), fill=float(fill), stop=float(stop), target=float(target),
                                   took_bar=(int(took_bar) if took_bar is not None else None),
                                   pivot_price=float(fk if side == "long" else ck), worst=float(worst),
                                   h_next_raw=str(hr["h_next"][prev]), h_two_raw=str(hr["h_two"][prev]),
                                   h_swings_raw=str(hr["h_swings"][prev]), h_swings_daily_raw=str(hr["h_swings_daily"][prev]),
                                   h_ema_daily_raw=str(hr["h_ema_daily"][prev]), h_daily_big_raw=str(hr["h_daily_big"][prev]),
                                   h_weekly_raw=str(hr["h_weekly"][prev]), h_ema200_raw=str(hr["h_ema200"][prev]))
                    out.append(row)
    return out


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    rows, errs = [], []
    for tf in TFS:
        try:
            rows += trades_for_frame(sym, kind, tf, frames, start)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    f = pd.DataFrame(rows)
    for col in ("sym", "kind", "tf", "era", "side", "variant", "pivot", "why") + tuple(READS):
        f[col] = f[col].astype("category")
    f["ret"] = f["ret"].astype("float32"); f["drift"] = f["drift"].astype("float32")
    f["chase"] = f["chase"].astype("float32"); f["rr"] = f["rr"].astype("float32")
    f["held"] = f["held"].astype("int32")
    return f, errs


# ------------------------------------------------------------------ folding
def stats(g):
    v = g["ret"].values.astype(float)
    if len(v) < 20:
        return None
    s = np.sort(v)
    cut = s[:max(1, len(s) - max(1, len(s) // 50))]
    return dict(n=int(len(v)), mean=float(v.mean()), median=float(np.median(v)), trimmed=float(cut.mean()),
                edge=float((g["ret"].values.astype(float) - g["drift"].values.astype(float)).mean()),
                won=float((v > 0).mean()), reached=float(g["took"].mean()), held=float(g["held"].mean()),
                best=float(s[-1]))


def table(f, cols):
    out = {}
    for k, g in f.groupby(cols, observed=True):
        st = stats(g)
        if st:
            out[" | ".join(str(x) for x in (k if isinstance(k, tuple) else (k,)))] = st
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
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    if "--focus" in sys.argv:
        import focus
        global OUT
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = OUT.replace(".json", "_focus.json")
    names = R._by_size(names)
    R.quiet_workers()
    parts, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for f, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if f is not None:
                parts.append(f)
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    f = pd.concat(parts, ignore_index=True)
    for col in ("tf", "era", "side", "variant", "kind") + tuple(READS):
        f[col] = f[col].astype(str)
    print("  %d trade rows, folding  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         variants=VARIANTS, entries=["after the higher low confirms"] + [lab for _, lab in LIMITS],
                         reads=READS, read_names=READ_NAMES, tags=TAGS,
                         rows=int(len(f)), seconds=int(time.time() - t0)),
               base=table(f, ["variant", "tf"]))
    for r_ in READS:
        res["by_" + r_] = table(f, ["variant", "tf", r_])
        res["pooled_" + r_] = table(f, ["variant", r_])
        res["era_" + r_] = table(f, ["variant", "tf", r_, "era"])
    res["kind_h_ema_daily"] = table(f, ["variant", "tf", "h_ema_daily", "kind"])
    res["side_h_ema_daily"] = table(f, ["variant", "tf", "h_ema_daily", "side"])
    res["kind_h_big"] = table(f, ["variant", "tf", "h_big", "kind"])
    res["side_h_big"] = table(f, ["variant", "tf", "h_big", "side"])
    res["kind_h_both"] = table(f, ["variant", "tf", "h_both", "kind"])
    res["side_h_both"] = table(f, ["variant", "tf", "h_both", "side"])
    res["kind_h_next"] = table(f, ["variant", "tf", "h_next", "kind"])
    json.dump(res, open(OUT, "w"))
    print()
    print("  EQ FREE RIDE STUDY  %d names, %d trade rows  (%.0fs)" % (len(names), len(f), time.time() - t0))
    for r_ in ("h_ema_daily", "h_ema_both", "h_big"):
        print("\n  direction from: %s   (middle trade / average / free ride reached / n)" % READ_NAMES[r_])
        for tf in TFS:
            print("   %s" % tf)
            for vname in VARIANTS:
                cells = []
                for tg in TAGS:
                    v = res["by_" + r_].get("%s | %s | %s" % (vname, tf, tg))
                    cells.append("%-8s avg %+6.2f%% mid %+6.2f%% %3.0f%% n%-7d" % (tg[:8], 100 * v["mean"], 100 * v["median"], 100 * v["reached"], v["n"])
                                 if v else "%-8s %28s" % (tg[:8], "-"))
                print("     %-58s %s" % (vname[:58], "  ".join(cells)))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
