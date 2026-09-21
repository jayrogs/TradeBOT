"""backburner_dan.py -- the BackBurner the way Dan teaches it on video (2026-09-20, transcripts in TCG_METHOD.md #11).

`backburner_tcg.py` got the definition from the e-book (first print after a run, their exits). Dan's own 17-minute
video adds the mechanics, and they are not small:

    THE ENTRY IS INSIDE THE CANDLE   one buy the moment the RSI BREAKS 30 -- he watches RSI at the candle's LOW,
                                     because a candle can touch 30 and close back over it -- and a second bid
                                     resting at RSI 20. `backburner_tcg` bought the NEXT OPEN after a CLOSE at or
                                     under 30, which on a waterfall is a different price and a different trade.
                                     The price that prints a given RSI is exact: Wilder's smoothing, one bar forward.
    A WATERFALL                      a fast hard drop with no little bear flags cooling it off on the way down.
    BLUE SKY                         best from all-time highs; "an uptrend on every single time frame".
    DOLLARS TRADED                   "hundreds of millions of dollars traded".
    REGULAR HOURS                    a first print in extended hours is skipped: "we used up that bounce".
    THE STOP                         none with one fill (the second bid is still waiting); a dollar stop once both
                                     are on. Coded as a catastrophic stop STOP_BARS normal bars under the lowest
                                     fill, which is also what R is measured against.
    THE EXIT                         half off quickly once the bounce gets going, stop UNDER THE LOW OF THE DROP,
                                     the rest for the bigger chart's higher low; or lock the whole "day maker".

NOT MODELLED, said plainly: news and earnings (his box 1), the 2-minute chart, and "how did this ticker react last
time" (his box 5).

    pythonw studies/backburner_dan.py --procs 8 --log logs/backburner_dan.log
Writes validation/backburner_dan.json and _rows.parquet
"""
import concurrent.futures as cf
import io
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
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
import backburner_tcg as T        # noqa: E402
from scalein_study import describe        # noqa: E402

_SM = os.path.join("validation", "sector_map.json")
SECTOR = json.load(io.open(_SM, encoding="utf-8")) if os.path.exists(_SM) else {}     # "kind|sym" -> ["kind|leader", r]

OUT = os.path.join("validation", "backburner_dan.json")
PAIRS = [("5m", "1h", "1d"), ("1h", "1d", "1w"), ("4h", "1d", "1w")]
STOP_BARS = 3.0
SECOND_BID_BARS = 12           # how long the RSI-20 bid rests before he pulls it
HOLD_LOOK = 35                 # "did the print MARK the higher low": the dip's low must stand this many bars
FALL_LOOK = 8                  # the waterfall is read over the last 8 bars of the entry chart
N_RSI = 14
# (label, kind of exit, parameter, close 5m stock trades at the bell)
MANAGERS = [("DAY MAKER: all out half a bigger-chart normal bar up", "fixed", 0.5, True),
            ("SCALP: all out when the bounce reaches the 12 EMA", "ema", 12, True),
            ("HALF at the 12 EMA, stop under the low of the drop, rest for the OLD HIGH", "half", 12, False),
            ("HALF at the 26 EMA, stop under the low of the drop, rest for the OLD HIGH", "half", 26, False)]


def rsi_price(c, au, ad, target):
    """The price on bar k that prints exactly `target` RSI, from the smoothing as it stood at the close of k-1.
    Below 50 it is a fall from the last close, above 50 a rise. NaN when price is already past it."""
    n = N_RSI
    rs = target / (100.0 - target)
    out = np.full(len(c), np.nan)
    if target < 50:
        x = (n - 1) * (au[:-1] / rs - ad[:-1])
        out[1:] = np.where(x > 0, c[:-1] - x, np.nan)
    else:
        y = (n - 1) * (rs * ad[:-1] - au[:-1])
        out[1:] = np.where(y > 0, c[:-1] + y, np.nan)
    return out


def dan_exit(kind, o, h, l, c, e, side, stop, entry, last, a, low0, how, ema=None, fixed=None, target=None):
    """Exits from bar `e` on (the bar AFTER the last fill: nothing is sold on the bar it was bought).
    how = "fixed": all out at the price `fixed`.  "ema": all out when the bounce reaches the EMA.
          "half":  half at the EMA, the stop moves under the low of the drop (`low0` and everything since),
                   the rest out at `target` (the old high). Same bar as the stop: the stop wins."""
    cost = L.COST.get(kind, 0.05)
    if e > last:
        return side * (c[last] - entry) / entry * 100 - cost
    lw, hw = l[e:last + 1], h[e:last + 1]
    s_hit = (lw <= stop) if side > 0 else (hw >= stop)
    if how == "fixed":
        t_hit = (hw >= fixed) if side > 0 else (lw <= fixed)
        lvl_arr = np.full(len(lw), fixed)
    else:
        em = ema[e:last + 1]
        t_hit = np.isfinite(em) & ((hw >= em) if side > 0 else (lw <= em))
        lvl_arr = em
    i_s = int(np.argmax(s_hit)) if s_hit.any() else None
    i_t = int(np.argmax(t_hit)) if t_hit.any() else None
    if i_s is not None and (i_t is None or i_s <= i_t):
        j = e + i_s + 1
        px = o[j] if j <= last else c[last]
        return side * (px - entry) / entry * 100 - cost
    if i_t is None:
        return side * (c[last] - entry) / entry * 100 - cost
    j = e + i_t
    px_t = (max(o[j], lvl_arr[i_t]) if side > 0 else min(o[j], lvl_arr[i_t]))
    if how != "half":
        return side * (px_t - entry) / entry * 100 - cost
    got = 0.5 * side * (px_t - entry) / entry
    if side > 0:
        stop2 = min(low0, float(np.min(lw[:i_t + 1]))) - 0.1 * a
    else:
        stop2 = max(low0, float(np.max(hw[:i_t + 1]))) + 0.1 * a
    if j + 1 > last:
        return (got + 0.5 * side * (c[last] - entry) / entry) * 100 - cost * 1.5
    l2, h2 = l[j + 1:last + 1], h[j + 1:last + 1]
    s2 = (l2 <= stop2) if side > 0 else (h2 >= stop2)
    if np.isfinite(target):
        t2 = (h2 >= target) if side > 0 else (l2 <= target)
    else:
        t2 = np.zeros(len(l2), dtype=bool)
    k_s = int(np.argmax(s2)) if s2.any() else None
    k_t = int(np.argmax(t2)) if t2.any() else None
    if k_s is not None and (k_t is None or k_s <= k_t):
        jj = j + 1 + k_s + 1
        px2 = o[jj] if jj <= last else c[last]
    elif k_t is not None:
        jj = j + 1 + k_t
        px2 = (max(o[jj], target) if side > 0 else min(o[jj], target))
    else:
        px2 = c[last]
    return (got + 0.5 * side * (px2 - entry) / entry) * 100 - cost * 1.5


_LEAD = {}                     # per worker: a leader's RSI on one chart, loaded once


def _lead_rsi(lead_key, tf):
    """THE LEADER RULE (TCG_METHOD 19l, 2Q__6_9f6JY): do not buy a laggard's oversold while its sector leader is
    still only near 34 -- the leader's own oversold print is the trigger. Returns the leader's RSI 14 on `tf` as a
    time series (regular hours for stocks and ETFs), or None."""
    key = (lead_key, tf)
    if key not in _LEAD:
        out = None
        try:
            lk, ls = lead_key.split("|")
            fr = {tf: B.frames_for(ls, lk).get(tf)}
            if fr[tf] is not None and lk in ("stock", "etf"):
                fr = FR2.regular_hours(fr)
            ldf = fr.get(tf)
            if ldf is not None and len(ldf) > 100:
                out = pd.Series(IND.rsi(ldf["Close"].values.astype(float), N_RSI), index=ldf.index)
        except Exception:
            out = None
        _LEAD[key] = out
    return _LEAD[key]


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    need = {x for p in PAIRS for x in p}
    frames = {k: v for k, v in frames.items() if k in need}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)          # his rule: an extended-hours print is skipped
    rows, errs = [], []
    d1 = frames.get("1d")
    for tf_i, (tf, sf, tt) in enumerate(PAIRS):
        if tf == "4h" and kind != "crypto":
            continue                                # his 4-hour version is a crypto rule
        df, sdf, tdf = frames.get(tf), frames.get(sf), frames.get(tt)
        if df is None or sdf is None or tdf is None or len(df) < 500 or len(sdf) < 120 or len(tdf) < 60:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            tns = df.index.values.astype("int64")
            atr = P._atr(df)
            rsi, au, ad = IND.rsi_parts(c, N_RSI)
            ema12 = XM.ema(c, 12); ema26 = XM.ema(c, 26)
            p30 = rsi_price(c, au, ad, 30); p20 = rsi_price(c, au, ad, 20)
            p70 = rsi_price(c, au, ad, 70); p80 = rsi_price(c, au, ad, 80)
            # the structure chart: the run into the high, the high itself, its normal bar
            sc = sdf["Close"].values.astype(float)
            satr = P._atr(sdf)
            run = np.full(len(sc), np.nan)
            run[T.RUN_LOOK:] = (sc[T.RUN_LOOK:] - sc[:-T.RUN_LOOK]) / np.where(satr[T.RUN_LOOK:] > 0,
                                                                                satr[T.RUN_LOOK:], np.nan)
            s_run = L.align_to(df, tf, frames, sf, run)
            s_atr = L.align_to(df, tf, frames, sf, satr)
            top = pd.Series(sdf["High"].values.astype(float)).rolling(T.HIGH_LOOK, min_periods=T.HIGH_LOOK).max().values
            bot = pd.Series(sdf["Low"].values.astype(float)).rolling(T.HIGH_LOOK, min_periods=T.HIGH_LOOK).min().values
            s_top = L.align_to(df, tf, frames, sf, top)
            s_bot = L.align_to(df, tf, frames, sf, bot)
            ext = {sd: (L.align_to(df, tf, frames, sf, T._last_extreme_time(sdf, sd)[0]),
                        T._last_extreme_time(sdf, sd)[1]) for sd in (1, -1)}
            tc = tdf["Close"].values.astype(float)
            e50 = XM.ema(tc, 50)
            up = np.zeros(len(tc)); dn = np.zeros(len(tc))
            up[5:] = ((tc[5:] > e50[5:]) & (e50[5:] > e50[:-5])).astype(float)
            dn[5:] = ((tc[5:] < e50[5:]) & (e50[5:] < e50[:-5])).astype(float)
            t_up = L.align_to(df, tf, frames, tt, up)
            t_dn = L.align_to(df, tf, frames, tt, dn)
            # BLUE SKY and DOLLARS, both read on the daily
            blue = np.full(n, np.nan); blue_dn = np.full(n, np.nan); dollars = np.full(n, np.nan)
            if d1 is not None and len(d1) > 260:
                dh = d1["High"].values.astype(float); dl = d1["Low"].values.astype(float)
                dc = d1["Close"].values.astype(float)
                hi = pd.Series(dh).rolling(252, min_periods=252).max().values
                lo = pd.Series(dl).rolling(252, min_periods=252).min().values
                since_hi = np.full(len(dc), np.nan); since_lo = np.full(len(dc), np.nan)
                a_ = b_ = np.nan
                for i in range(len(dc)):
                    if np.isfinite(hi[i]) and dh[i] >= hi[i]:
                        a_ = 0.0
                    elif np.isfinite(a_):
                        a_ += 1.0
                    if np.isfinite(lo[i]) and dl[i] <= lo[i]:
                        b_ = 0.0
                    elif np.isfinite(b_):
                        b_ += 1.0
                    since_hi[i] = a_; since_lo[i] = b_
                blue = L.align_to(df, tf, frames, "1d", since_hi)
                blue_dn = L.align_to(df, tf, frames, "1d", since_lo)
                if "Volume" in d1:
                    dv = pd.Series(dc * d1["Volume"].values.astype(float)).rolling(50, min_periods=20).median().values
                    dollars = L.align_to(df, tf, frames, "1d", dv)
            # HIS STACK (TCG_METHOD #13): several charts oversold at once, AT a level. How many of the bigger charts
            # (4h, daily) read RSI 35 or under when the print comes, and is price sitting on the DAILY 12 EMA.
            stack = np.zeros(n)
            for big_tf in ("4h", "1d"):
                bdf_ = frames.get(big_tf) if big_tf != tf else None
                if bdf_ is not None and len(bdf_) > 60:
                    br = IND.rsi(bdf_["Close"].values.astype(float), N_RSI)
                    al = L.align_to(df, tf, frames, big_tf, br)
                    stack = stack + np.where(np.isfinite(al) & (al <= 35), 1.0, 0.0)
            at_d12 = np.full(n, np.nan)
            d12 = np.full(n, np.nan); dat_ = np.full(n, np.nan)
            if d1 is not None and len(d1) > 60:
                dcl = d1["Close"].values.astype(float)
                d12 = L.align_to(df, tf, frames, "1d", XM.ema(dcl, 12))
                dat_ = L.align_to(df, tf, frames, "1d", P._atr(d1))
                with np.errstate(invalid="ignore"):
                    at_d12 = np.where(np.isfinite(d12) & (dat_ > 0), (c - d12) / dat_, np.nan)
            # HIS SWITCH (TCG_METHOD 19e): "when we lose the 4-hour 12 EMA ... we watch for back burners, first hourly
            # oversold". A second honest reading of FIRST: the first print since THIS name's 4h close lost its 12 EMA
            # (mirror for shorts), and how many 4h bars the EMA had held before that ("the first time in weeks").
            leg4 = {1: np.full(n, np.nan), -1: np.full(n, np.nan)}
            held4 = {1: np.full(n, np.nan), -1: np.full(n, np.nan)}
            off4 = {1: np.full(n, np.nan), -1: np.full(n, np.nan)}
            f4 = frames.get("4h") if tf in ("5m", "1h") else None
            if f4 is not None and len(f4) > 60:
                c4 = f4["Close"].values.astype(float)
                e4 = XM.ema(c4, 12)
                for sd in (1, -1):
                    onside = (c4 > e4) if sd > 0 else (c4 < e4)
                    lid = np.full(len(c4), np.nan); hl = np.full(len(c4), np.nan)
                    runlen, cur_id, cur_h = 0, np.nan, np.nan
                    for i4 in range(len(c4)):
                        if onside[i4]:
                            runlen += 1
                        else:
                            if i4 > 0 and onside[i4 - 1]:
                                cur_id, cur_h = float(i4), float(runlen)
                            runlen = 0
                        lid[i4] = cur_id; hl[i4] = cur_h
                    leg4[sd] = L.align_to(df, tf, frames, "4h", lid)
                    held4[sd] = L.align_to(df, tf, frames, "4h", hl)
                    off4[sd] = L.align_to(df, tf, frames, "4h", (~onside).astype(float))
            # HE WANTS THE GAP DOWN (TCG_METHOD #16): "crush it into the close and gap down open to hourly oversold".
            # Which bar of its session this is, and where the session OPENED against yesterday's low / high / close.
            # Read off this chart's own bars, so it is exactly what he would have seen at the open. Stocks and ETFs only.
            bar_of_day = np.full(n, np.nan); gap_lo = np.full(n, np.nan); gap_hi = np.full(n, np.nan)
            if kind in ("stock", "etf"):
                dayv = df.index.normalize().values
                first_i = np.r_[0, np.where(dayv[1:] != dayv[:-1])[0] + 1]
                last_i = np.r_[first_i[1:] - 1, n - 1]
                for q in range(1, len(first_i)):
                    a0, a1 = first_i[q], last_i[q]
                    b0, b1 = first_i[q - 1], last_i[q - 1]
                    bar_of_day[a0:a1 + 1] = np.arange(a1 - a0 + 1)
                    gap_lo[a0:a1 + 1] = float(np.min(l[b0:b1 + 1])) - o[a0]     # + = opened UNDER yesterday's low
                    gap_hi[a0:a1 + 1] = o[a0] - float(np.max(h[b0:b1 + 1]))     # + = opened OVER yesterday's high
            lead_rsi = np.full(n, np.nan)
            lead = SECTOR.get("%s|%s" % (kind, sym))
            if lead and lead[1] >= 0.30 and tf in ("1h", "4h") and lead[0] != "%s|%s" % (kind, sym):
                lr = _lead_rsi(lead[0], tf)
                if lr is not None:
                    lead_rsi = lr.reindex(df.index, method="ffill").values.astype(float)
            vol = df["Volume"].values.astype(float) if "Volume" in df else np.zeros(n)
            vavg = pd.Series(vol).rolling(50, min_periods=20).mean().values
            bells = None
            if kind in ("stock", "etf") and tf == "5m":
                day = df.index.normalize().values
                bells = np.searchsorted(day, day, side="right") - 1
            cost = L.COST.get(kind, 0.05)
            stepc = max(12, n // 9000)
            for side in (1, -1):
                pa, pb = (p30, p20) if side > 0 else (p70, p80)
                if side > 0:
                    touch = np.isfinite(pa) & (l <= pa)
                    was_out = np.r_[False, rsi[:-1] > 30]
                else:
                    touch = np.isfinite(pa) & (h >= pa)
                    was_out = np.r_[False, rsi[:-1] < 70]
                starts = np.where(touch & was_out)[0]
                ext_t, sstep = ext[side]
                ordinal, cnt, cur = {}, 0, None
                for k in starts:
                    t_ext = ext_t[k - 1] if k > 0 else np.nan
                    if not np.isfinite(t_ext):
                        ordinal[k] = 0
                        continue
                    if cur is None or t_ext != cur:
                        cur, cnt = t_ext, 0
                    cnt += 1
                    ordinal[k] = cnt
                ord4, cnt4, cur4 = {}, 0, None
                for k in starts:
                    lk = leg4[side][k - 1] if k > 0 else np.nan
                    if not np.isfinite(lk) or not (off4[side][k - 1] > 0.5):
                        ord4[k] = 0
                        continue
                    if cur4 is None or lk != cur4:
                        cur4, cnt4 = lk, 0
                    cnt4 += 1
                    ord4[k] = cnt4
                ctrl_ks = np.arange(150 if side > 0 else 190, n - 8, stepc)
                for ks, is_ctrl in ((starts, 0), (ctrl_ks, 1)):
                    for k in ks:
                        m_ = k - 1
                        if k < 150 or k + 8 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                            continue
                        a = atr[m_]
                        if is_ctrl:
                            gap = (ema12[m_] - c[m_]) if side > 0 else (c[m_] - ema12[m_])
                            if not (np.isfinite(gap) and gap >= a):
                                continue
                            fills = [o[k]]; e_last = k
                        else:
                            # IN AT THE TOUCH: a gap through the level fills at the open
                            f1 = min(o[k], pa[k]) if side > 0 else max(o[k], pa[k])
                            fills = [f1]; e_last = k
                            for j in range(k, min(n - 1, k + SECOND_BID_BARS)):
                                if j > k and ((side > 0 and rsi[j - 1] > 40) or (side < 0 and rsi[j - 1] < 60)):
                                    break                       # the bounce is on: he pulls the second bid
                                if np.isfinite(pb[j]) and ((side > 0 and l[j] <= pb[j]) or (side < 0 and h[j] >= pb[j])):
                                    f2 = (min(o[j], pb[j]) if side > 0 else max(o[j], pb[j])) if j > k else pb[j]
                                    fills.append(f2); e_last = j
                                    break
                        entry = float(np.mean(fills))
                        worst = min(fills) if side > 0 else max(fills)
                        stop = worst - STOP_BARS * a if side > 0 else worst + STOP_BARS * a
                        risk = abs(entry - stop)
                        rp = risk / entry * 100
                        if rp < 3 * cost or rp > 25.0:
                            continue
                        low0 = float(np.min(l[k:e_last + 1])) if side > 0 else float(np.max(h[k:e_last + 1]))
                        sa = s_atr[m_] if np.isfinite(s_atr[m_]) else a
                        res = []
                        blown = (side > 0 and l[e_last] <= stop) or (side < 0 and h[e_last] >= stop)
                        for _lab, how, par, use_bell in MANAGERS:
                            last = min(n - 1, e_last + L.MAX_BARS)
                            if bells is not None and use_bell:
                                last = min(last, int(bells[e_last]))
                            if blown:                           # through the stop on the bar it was bought
                                j2 = min(e_last + 1, n - 1)
                                res.append(side * (o[j2] - entry) / entry * 100 - cost)
                                continue
                            res.append(dan_exit(kind, o, h, l, c, e_last + 1, side, stop, entry, last, a, low0, how,
                                                ema=(ema12 if par == 12 else ema26) if how != "fixed" else None,
                                                fixed=(entry + side * par * sa) if how == "fixed" else None,
                                                target=(s_top[m_] if side > 0 else s_bot[m_])))
                        # the waterfall: how far, how fast, and how many green candles on the way down
                        w0 = max(0, k - FALL_LOOK)
                        if side > 0:
                            fall = (float(np.max(h[w0:k + 1])) - fills[0]) / a
                            pauses = int(np.sum(c[w0:k] > o[w0:k]))
                        else:
                            fall = (fills[0] - float(np.min(l[w0:k + 1]))) / a
                            pauses = int(np.sum(c[w0:k] < o[w0:k]))
                        t_ext = ext_t[m_]
                        since = (tns[m_] - t_ext) / sstep if (np.isfinite(t_ext) and sstep > 0) else -1.0
                        rn = s_run[m_]
                        rn = (rn if side > 0 else -rn) if np.isfinite(rn) else np.nan
                        bl = blue[m_] if side > 0 else blue_dn[m_]
                        vclimax = float(vol[k] / vavg[k - 1]) if (k > 0 and np.isfinite(vavg[k - 1]) and vavg[k - 1] > 0) else np.nan
                        d12gap = at_d12[m_]
                        d12gap = (d12gap if side > 0 else -d12gap) if np.isfinite(d12gap) else np.nan
                        # did the DIP ITSELF reach the daily 12 EMA (his favourite: the first hourly oversold that
                        # lines up with the daily 12 EMA to set the daily higher low). Measured from the worst fill.
                        d12fill = ((worst - d12[m_]) / dat_[m_] * side) if (np.isfinite(d12[m_]) and dat_[m_] > 0) else np.nan
                        gp = gap_lo[k] if side > 0 else gap_hi[k]
                        gapopen = (gp / dat_[m_]) if (np.isfinite(gp) and dat_[m_] > 0) else np.nan
                        # THE HEALTH READ, no money in it: did the dip's low STAND (the print marked the higher low)
                        # or did the bounce go on to a lower low
                        j9 = e_last + 1 + HOLD_LOOK
                        if j9 < n:
                            kept = float(np.min(l[e_last + 1:j9]) >= low0) if side > 0 else float(np.max(h[e_last + 1:j9]) <= low0)
                        else:
                            kept = np.nan
                        o4 = float(ord4.get(k, 0)) if not is_ctrl else -1.0
                        h4 = held4[side][m_]
                        rows.append([tf_i, side, float(ordinal.get(k, 0)) if not is_ctrl else -1.0, since, rn,
                                     float(t_up[m_] if side > 0 else t_dn[m_]) if np.isfinite(t_up[m_]) else np.nan,
                                     fall, float(pauses), float(bl) if np.isfinite(bl) else np.nan,
                                     float(dollars[m_]) if np.isfinite(dollars[m_]) else np.nan,
                                     float(stack[m_]), d12gap, vclimax, d12fill, gapopen,
                                     float(bar_of_day[k]) if np.isfinite(bar_of_day[k]) else np.nan,
                                     o4, float(h4) if np.isfinite(h4) else np.nan, kept,
                                     float(lead_rsi[m_]) if np.isfinite(lead_rsi[m_]) else np.nan,
                                     float(len(fills)), rp, float(df.index[k].value), is_ctrl] + res)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return (np.asarray(rows, dtype=np.float64), kind, sym), errs


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex" and s_ not in T.SUSPECT])
    R.quiet_workers()
    parts, kinds, syms, errs, done = [], [], [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if got is not None:
                parts.append(got[0]); kinds += [got[1]] * len(got[0]); syms += [got[2]] * len(got[0])
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    cols = ["tf", "side", "ordinal", "since", "run", "intact", "fall", "pauses", "blue", "dollars", "stacked", "d12gap",
            "vclimax", "d12fill", "gapopen", "bar_of_day", "ord4", "held4", "kept", "lead_rsi", "units",
            "risk_pct", "t", "ctrl"] + ["r%d" % i for i in range(len(MANAGERS))]
    d = pd.DataFrame(np.concatenate(parts), columns=cols)
    d["kind"] = np.array(kinds); d["sym"] = np.array(syms)
    d = d.sort_values("t")
    d["yr"] = pd.to_datetime(d.t).dt.year
    # HIS CHECKLIST, BOX 5: "prior examples on that same ticker". For every first print, how this NAME's EARLIER first
    # prints did under the scalp (known before this one: rows are in time order and a scalp lasts a few bars).
    d["prior_n"] = np.nan; d["prior_win"] = np.nan
    fp = d[(d.ctrl == 0) & (d.ordinal == 1)]
    scalp = "r1"
    for _key, g in fp.groupby(["sym", "tf", "side"]):
        w = (g[scalp] > 0).astype(float)
        d.loc[g.index, "prior_n"] = np.arange(len(g), dtype=float)
        d.loc[g.index, "prior_win"] = w.shift(1).expanding().mean().values
    # "hundreds of millions of dollars traded": $100M+ a day for stocks and ETFs; the top third elsewhere
    thr = d.groupby("kind").dollars.transform(lambda x: x.quantile(2 / 3))
    d["liquid"] = np.where(d.kind.isin(["stock", "etf"]), d.dollars >= 1e8, d.dollars >= thr).astype(float)
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), rows=int(len(d)),
                         seconds=int(time.time() - t0), managers=[m[0] for m in MANAGERS]), tables={})
    print("\n  THE BACKBURNER, DAN'S MECHANICS  (%d names, %d rows, %.0fs)\n" % (len(names), len(d), time.time() - t0),
          flush=True)

    def stat(g, col):
        g = g[np.isfinite(g[col])]
        return describe(g[col].values, (g[col] / g.risk_pct).values) if len(g) >= 60 else None

    def yrs(g, col):
        g = g[np.isfinite(g[col])]
        if not len(g):
            return 0, 0
        y = g.groupby("yr").apply(lambda x: (x[col] / x.risk_pct).mean(), include_groups=False)
        return int((y > 0).sum()), int(len(y))

    first = lambda x, c: (x.ordinal == 1) | (c == 1)                       # noqa: E731
    CUTS = [
        ("every first-touch of 30", lambda x, c: x.ctrl == c),
        ("the FIRST print since the bigger chart's new high", lambda x, c: (x.ctrl == c) & first(x, c)),
        ("the THIRD print or later", lambda x, c: (x.ctrl == c) & ((x.ordinal >= 3) | (c == 1))),
        ("first print + a RUN of 4+ into the high", lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4)),
        ("  + long-term trend INTACT", lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.intact > 0.5)),
        ("  + a WATERFALL (fell 4+ bars, 3 or fewer pauses)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.intact > 0.5) & (x.fall >= 4) & (x.pauses <= 3)),
        ("  + BLUE SKY (a 1-year high in the last 10 days)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.intact > 0.5) & (x.fall >= 4) & (x.pauses <= 3)
         & (x.blue <= 10)),
        ("DAN'S FULL CHECKLIST (+ liquid)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.intact > 0.5) & (x.fall >= 4) & (x.pauses <= 3)
         & (x.blue <= 10) & (x.liquid > 0.5)),
        ("first print + blue sky + liquid (no waterfall asked)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.blue <= 10) & (x.liquid > 0.5) & (x.intact > 0.5)),
        ("waterfall only, any print", lambda x, c: (x.ctrl == c) & (x.fall >= 4) & (x.pauses <= 3)),
        ("first print + run, ON THE DAILY 12 EMA (within half a daily bar)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12gap.abs() <= 0.5)),
        ("first print + run, well ABOVE the daily 12 EMA (1+ bars)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12gap > 1.0)),
        ("first print + run, UNDER the daily 12 EMA (1+ bars)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12gap < -1.0)),
        ("first print + run + a VOLUME CLIMAX (2x its average)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.vclimax >= 2.0)),
        ("first print + run, the DIP REACHED the daily 12 EMA (fill within half a daily bar)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12fill.abs() <= 0.5)),
        ("first print + run, dip stopped ABOVE the daily 12 EMA (0.5+ bars over)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12fill > 0.5)),
        ("first print + run, dip went THROUGH the daily 12 EMA (0.5+ bars under)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.d12fill < -0.5)),
        ("first print + run, IN THE FIRST TWO BARS of a day that GAPPED under yesterday's low",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.bar_of_day <= 1) & (x.gapopen > 0)),
        ("first print + run, first two bars of the day, NO gap under yesterday's low",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.bar_of_day <= 1) & (x.gapopen <= 0)),
        ("first print + run, LATER in the day (bar 3 on)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.bar_of_day >= 2)),
        ("any print, first two bars of a GAP-DOWN day",
         lambda x, c: (x.ctrl == c) & (x.bar_of_day <= 1) & (x.gapopen > 0)),
        ("the FIRST print since the 4h 12 EMA was LOST (his switch)",
         lambda x, c: (x.ctrl == c) & ((x.ord4 == 1) | (c == 1))),
        ("  ... and the 4h 12 EMA had HELD 10+ bars before that",
         lambda x, c: (x.ctrl == c) & ((x.ord4 == 1) | (c == 1)) & (x.held4 >= 10)),
        ("  ... held 10+ bars AND a run of 4+ into the high",
         lambda x, c: (x.ctrl == c) & ((x.ord4 == 1) | (c == 1)) & (x.held4 >= 10) & (x.run >= 4)),
        ("the THIRD print or later since the 4h 12 EMA was lost",
         lambda x, c: (x.ctrl == c) & ((x.ord4 >= 3) | (c == 1))),
        ("first by BOTH counts (since the high AND since the 4h 12 EMA) + run",
         lambda x, c: (x.ctrl == c) & first(x, c) & ((x.ord4 == 1) | (c == 1)) & (x.run >= 4)),
        ("first print + run, this NAME's earlier first prints mostly WON (3+ seen, 60%+)",
         lambda x, c: (x.ctrl == c) & (x.ordinal == 1) & (x.run >= 4) & (x.prior_n >= 3) & (x.prior_win >= 0.6)),
        ("first print + run, this NAME's earlier first prints mostly LOST (3+ seen, under 50%)",
         lambda x, c: (x.ctrl == c) & (x.ordinal == 1) & (x.run >= 4) & (x.prior_n >= 3) & (x.prior_win < 0.5)),
        ("first print + run, the sector LEADER is oversold too (its RSI 35 or under)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.lead_rsi <= 35)),
        ("first print + run, the leader is weak but NOT oversold (35-45)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.lead_rsi > 35) & (x.lead_rsi <= 45)),
        ("first print + run, the leader is FINE (over 45)",
         lambda x, c: (x.ctrl == c) & first(x, c) & (x.run >= 4) & (x.lead_rsi > 45)),
        ("ANY print, the leader oversold too (35 or under)", lambda x, c: (x.ctrl == c) & (x.lead_rsi <= 35)),
        ("ANY print, the leader weak but not oversold (35-45)",
         lambda x, c: (x.ctrl == c) & (x.lead_rsi > 35) & (x.lead_rsi <= 45)),
        ("ANY print, the leader fine (over 45)", lambda x, c: (x.ctrl == c) & (x.lead_rsi > 45)),
        ("any print, bigger charts ALSO oversold (stack 1+)", lambda x, c: (x.ctrl == c) & (x.stacked >= 1)),
        ("any print, BOTH bigger charts oversold (stack 2)", lambda x, c: (x.ctrl == c) & (x.stacked >= 2)),
        ("NOT a backburner: no run, trend broken", lambda x, c: (x.ctrl == c) & (x.run < 1) & (x.intact < 0.5)),
    ]
    TFN = [p[0] for p in PAIRS]
    for tf_i, tf in enumerate(TFN):
        for side, sname in ((1, "LONG"), (-1, "SHORT")):
            base = d[(d.tf == tf_i) & (d.side == side)]
            if len(base) < 500:
                continue
            for mi, (mlab, _h, _p, _b) in enumerate(MANAGERS):
                col = "r%d" % mi
                key = "%s | %s | %s" % (tf, sname, mlab)
                print("  %s  %s  --  %s" % (tf, sname, mlab))
                print("    %-52s %7s %8s %8s %5s %7s %7s %7s %6s" % (
                    "cut", "n", "avg", "middle", "won", "avg R", "ctrl R", "yrs up", "low held"))
                out["tables"][key] = {}
                for lab, fn in CUTS:
                    g = base[fn(base, 0)]; cc = base[fn(base, 1)]
                    s1, s2 = stat(g, col), stat(cc, col)
                    if not s1:
                        continue
                    yu, yt = yrs(g, col)
                    kp = g.kept[np.isfinite(g.kept)]
                    kept = float(kp.mean()) if len(kp) >= 60 else None
                    print("    %-52s %7d %+7.3f%% %+7.3f%% %4.0f%% %+6.2fR %+6.2fR %4d/%-2d %5s" % (
                        lab[:52], s1["n"], s1["avg"], s1["middle"], 100 * s1["won"], s1["avg_R"] or 0,
                        (s2["avg_R"] or 0) if s2 else 0, yu, yt, ("%.0f%%" % (100 * kept)) if kept is not None else "-"))
                    out["tables"][key][lab] = dict(setup=s1, control=s2, years_up=yu, years=yt, low_held=kept)
                print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    try:
        d.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    except Exception:
        pass
    for e_ in errs[:10]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
