"""pics_ride.py -- RANDOM CHARTS of the trend ride in the owner's words (2026-09-06):
"catch a higher low and ride... if the trend dies, you get out."
Entry: a higher low confirms while the chart is in an uptrend (live grammar),
buy the next open, skip if it already ran more than a normal bar's move above
the pivot. Partial: a third sold at twice the risk. Exit: the uptrend dies
(wick under the last higher low beyond tolerance, or a lower high / lower low). from studies/trend_study.py,
so the owner can check the technique instead of taking a number's word for it.

    python pics_trend.py              # writes validation/trend_case_NN.png + trend_cases_index.json (page: /trendcases)

Each chart shows ONE higher-low entry exactly as the study traded it:
  * the previous low pivot and the HIGHER low that triggered it
  * the buy, at the next bar's open after the pivot was confirmed
  * the stepped line = the level being held (the last higher low), rising
    every time a new higher low confirms
  * the exit, at the next open after a close under that line
  * AND 60 more bars after the exit, so it is visible whether the trend
    kept running after the rule sold -- the whole question.
Right side: the two higher timeframes through chartkit, with the trade's
window marked.
"""

import bisect
import concurrent.futures as cf
import json
import multiprocessing as mp
import time
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "studies")
import trend_study as T           # noqa: E402  the traded rules
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import indicators as IND          # noqa: E402
import rider                      # noqa: E402
import structure as ST            # noqa: E402

warnings.filterwarnings("ignore")
OUT = "validation"
DARK, DIM = "#0d0f12", "#8b93a1"
BOX = dict(boxstyle="round,pad=0.25", fc=DARK, ec="none", alpha=0.85)
HIGHER = {"5m": ("15m", "1h"), "15m": ("1h", "4h"), "1h": ("4h", "1d"), "4h": ("1d", "1w"),
          "12h": ("1d", "1w"), "1d": ("1w",), "1w": ()}


_CTX = {}


def context(df, key):
    """Per-frame work done ONCE (pivots, 12 EMA, ATR, RSI). Re-deriving this
    for every trade was the slow path."""
    if key in _CTX:
        return _CTX[key]
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    highs = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "high"]
    ctx = dict(c=c, o=df["Open"].values.astype(float), ema=rider.ema(c), a14=S.atr(h, l, c),
               rsi=IND.rsi_parts(c)[0], lows=lows, highs=highs,
               lcis=[x[0] for x in lows], hcis=[x[0] for x in highs],
               low_by_ci={x[0]: x for x in lows}, n=len(c),
               allp=piv, pos_by_ci={pv[0]: i for i, pv in enumerate(piv)})
    _CTX.clear()          # one frame at a time: these are big
    _CTX[key] = ctx
    return ctx


MAX_CHASE = 1.0         # skip the entry if the open is already this far above the pivot
PART_R = 2.0            # sell a third once up this many times the risk
PART_SIZE = 1 / 3
MANAGER = None          # set to an exit_managers.LABELS entry to draw a trade under that exit instead of the graded rule
TOL = 0.5               # the wick has to go this many normal bars' moves under the higher low to count
TRAIL_AFTER_R = 3.0     # once up this many times the risk, switch to a trailing stop (his SPY note)
TRAIL_BARS = 8.0        # ... this many normal bars' moves under the highest close


def trend_pivots_before(ctx, ci):
    """Walk back from the pivot confirmed at ci over the run of up-structure
    pivots (HL, HH, EH, EL). Returns (count including this one, has_HH).
    His count: the HL and HH printed BEFORE the chart turned green are part of
    the uptrend too. An EL counts as a higher low."""
    allp = ctx["allp"]
    k = ctx["pos_by_ci"].get(ci)
    if k is None:
        return 0, False
    cnt, has_hh = 0, False
    for m in range(k, -1, -1):
        lab = allp[m][4]
        if lab in ("LH", "LL"):
            break
        if lab in ("HL", "HH", "EH", "EL"):
            cnt += 1
            has_hh = has_hh or lab == "HH"
        else:
            break                                 # H / L: the very first pivots on the file
    return cnt, has_hh


def walk(df, tf, kind, t, key=None):
    """Re-walk one trade under the rules he graded in (2026-09-06, two rounds):
    the uptrend already has a higher low AND a higher high (before or after it
    turned green), and this is the NEXT higher low. Buy the next open, unless
    it opened under the pivot (gap through it) or more than one normal bar's
    move above it. Hold until a wick goes under the last higher low by more
    than TOL normal bars' moves. Lower highs are ignored. A third off at twice
    the risk. Fast stock charts do not hold overnight."""
    ctx = context(df, key or (id(df), tf))
    c, o, ema, a14, rsi = ctx["c"], ctx["o"], ctx["ema"], ctx["a14"], ctx["rsi"]
    lows, highs, lcis, hcis, n = ctx["lows"], ctx["highs"], ctx["lcis"], ctx["hcis"], ctx["n"]
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    e = int(df.index.get_indexer([pd.Timestamp(t)])[0])
    if e < 2 or e >= n - 2:
        return None
    trig = ctx["low_by_ci"].get(e - 1)
    if trig is None or trig[3] not in ("HL", "EL"):
        return None
    cnt, has_hh = trend_pivots_before(ctx, e - 1)
    if cnt < 3 or not has_hh:
        return None                               # need a higher low and a higher high already, then this one
    p = bisect.bisect_right(lcis, e - 1)
    prev_low = lows[p - 2] if p >= 2 else None
    nth = sum(1 for m in range(ctx["pos_by_ci"][e - 1], -1, -1)
              if ctx["allp"][m][4] in ("HL", "EL") or (ctx["allp"][m][4] in ("LH", "LL") and False))
    # count HLs (and ELs) in this run of up-structure, including this one
    nth = 0
    for m in range(ctx["pos_by_ci"][e - 1], -1, -1):
        lab = ctx["allp"][m][4]
        if lab in ("LH", "LL", "H", "L"):
            break
        if lab in ("HL", "EL"):
            nth += 1
    if nth != 2:
        return None                               # "why the 4th higher low? the second worked much better" (x8)
    fill = o[e]
    pivot = trig[2]
    atr0 = a14[e - 1]
    if not (np.isfinite(atr0) and atr0 > 0):
        return None
    if fill < pivot:
        return None                               # it opened under the higher low: already broken, no trade
    if (fill - pivot) / atr0 > (1.0 if tf in ("5m", "15m", "1h") else 3.0):
        return None                               # chased
    intraday_stock = kind in ("stock", "etf") and tf in ("5m", "15m")      # the 1h holds overnight now
    lv = np.full(n, np.nan)
    level = pivot
    q = p
    exit_bar, why = None, ""
    R0 = max(fill - pivot, atr0)
    peak, trailing = c[e], False
    if MANAGER:
        return _walk_manager(df, tf, kind, ctx, e, trig, prev_low, nth, fill, pivot, atr0, intraday_stock)
    for k in range(e, n - 1):
        while q < len(lows) and lows[q][0] <= k:
            ci, j2, price, lab = lows[q]; q += 1
            if j2 >= e and lab in ("HL", "EL") and price > level:
                level = price
        peak = max(peak, c[k])
        atr_k = a14[k] if np.isfinite(a14[k]) else 0.0
        # his SPY note: once the trade is up 3x the risk, stop waiting for the
        # higher low to break and trail 8 normal bars under the highest close
        if not trailing and c[k] >= fill + TRAIL_AFTER_R * R0:
            trailing = True
        if trailing:
            level = max(level, peak - TRAIL_BARS * atr_k)
        lv[k] = level
        buf = 0.0 if trailing else TOL * atr_k
        if trailing and c[k] < level:
            exit_bar = k
            why = "it had run 3x the risk, so the stop was trailing %g normal bars under the highest close, and price closed under it at %s" % (TRAIL_BARS, fmt_px(level))
            break
        if not trailing and l[k] < level - buf:
            exit_bar = k
            depth_pct = 100 * (level - l[k]) / level
            depth_bars = (level - l[k]) / a14[k] if np.isfinite(a14[k]) and a14[k] > 0 else np.nan
            gap = o[k] / c[k - 1] - 1 if k > 0 else 0.0
            why = "the wick went %.2f%% (%.1f normal bars) under the last higher low at %s" % (
                depth_pct, depth_bars, fmt_px(level))
            if abs(gap) > 0.01:
                why += ", on a %+.1f%% gap" % (100 * gap)
            break
        if intraday_stock and k + 1 < n and df.index[k + 1].normalize() != df.index[k].normalize():
            exit_bar = k; why = "the session ended (we don't hold fast trades overnight)"; break
        if k - e >= T.CAP_DAYS * 2 * T.BARS_DAY[tf]:
            exit_bar = k; why = "the time limit ran out"; break
    if exit_bar is None or exit_bar + 1 >= n:
        return None
    # sold at the next open; for a session end, at that bar's close
    if why.startswith("the session ended"):
        exit_px = c[exit_bar]
    else:
        exit_px = o[exit_bar + 1]
    broke = why.startswith("the wick") or why.startswith("it had run")
    R = max(fill - pivot, atr0)
    tgt = fill + PART_R * R
    pbar = next((k for k in range(e, exit_bar + 1) if h[k] >= tgt), None)
    cost = T.CLASS_COST.get(kind, 0.0005)
    if "flips" not in ctx:
        state = np.array(["FLAT"] * n, dtype=object)
        for kind_, s0_, s1_ in ST.spans(df, causal=True):
            state[s0_:s1_ + 1] = kind_
        chg = np.r_[0, (state[1:] != state[:-1]).astype(int)]
        cs = np.cumsum(chg); fl = np.zeros(n); fl[60:] = cs[60:] - cs[:-60]
        ctx["flips"] = fl
    flips = int(ctx["flips"][e - 1])
    sz = PART_SIZE if pbar is not None else 0.0
    ret = sz * (tgt / fill - 1 if pbar is not None else 0.0) + (1 - sz) * (exit_px / fill - 1) - cost
    after = min(n - 1, exit_bar + 60)
    return dict(e=e, fill=fill, trig=trig, prev_low=prev_low, level=lv, raises=[], hhs=[], nth=nth,
                exit_bar=exit_bar, exit_px=exit_px, ended=why, why=why, broke=broke, ema=ema, rsi=rsi, a14=a14,
                pbar=pbar, ppx=tgt, risk=R, ret=ret, after=after, flips=flips,
                after_px=c[after], after_ret=c[after] / fill - 1 - cost,
                mfe=float(np.max(c[e:exit_bar + 1]) / fill - 1),
                best_after=float(np.max(c[exit_bar:after + 1]) / fill - 1))


def _walk_manager(df, tf, kind, ctx, e, trig, prev_low, nth, fill, pivot, atr0, intraday_stock):
    """The same trade, but the exit comes from one of the twenty managers in
    studies/exit_managers.py (MANAGER). No partial. The drawn line is whatever
    that manager watches: the last higher low, a chandelier, an EMA, the SAR..."""
    import exit_managers as XM
    c, o, a14, lows, lcis, highs, hcis, n = ctx["c"], ctx["o"], ctx["a14"], ctx["lows"], ctx["lcis"], ctx["highs"], ctx["hcis"], ctx["n"]
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    if "ind" not in ctx:
        ctx["ind"] = XM.indicators(c, o, h, l, a14)
    ind = ctx["ind"]
    day = df.index.normalize().values if intraday_stock else None
    cap = T.CAP_DAYS * 2 * T.BARS_DAY[tf]
    import exit_managers2 as XM2
    if MANAGER in XM2.LABELS2:
        vol = df["Volume"].values.astype(float) if "Volume" in df else None
        if "ind2" not in ctx:
            ctx["ind2"] = XM2.prep(c, o, h, l, vol, a14, XM.ema)
        hi_lvl = ctx.get("hi_lvl")
        if hi_lvl is None:
            hi_lvl = np.full(n, np.nan)
        res = XM2.run_all2(c, o, l, h, vol, a14, ctx["ind2"], hi_lvl, lows, lcis, highs, hcis, e, pivot, n, cap, day)
    else:
        res = XM.run_all(c, o, l, h, a14, ind, lows, lcis, highs, hcis, e, pivot, n, cap, day)
    r = res.get(MANAGER)
    if r is None:
        return None
    exit_bar, exit_px, why0, worst = r
    if exit_bar + 1 >= n:
        return None
    # the line to draw
    lv = np.full(n, np.nan)
    lab = MANAGER
    level = pivot; peak = c[e]; q = bisect.bisect_right(lcis, e - 1)
    R0 = max(fill - pivot, atr0); trailing = False
    for k in range(e, exit_bar + 1):
        while q < len(lows) and lows[q][0] <= k:
            ci, j2, price, lb = lows[q]; q += 1
            if j2 >= e and lb in ("HL", "EL") and price > level:
                level = price
        peak = max(peak, c[k]); atr_k = a14[k] if np.isfinite(a14[k]) else 0.0
        if c[k] >= fill + 3 * R0:
            trailing = True
        m_ch = None
        import re as _re
        mm = _re.match(r"chandelier (\d+) bars", lab)
        if mm:
            m_ch = float(mm.group(1))
        if lab.startswith("chandelier that tightens with time"):
            lv[k] = peak - max(2.0, 5.0 - 0.05 * (k - e)) * atr_k
        elif lab.startswith("chandelier that tightens with profit"):
            up_r = (c[k] - fill) / R0 if R0 > 0 else 0
            lv[k] = peak - (2.0 if up_r >= 10 else 3.0 if up_r >= 5 else 5.0) * atr_k
        elif lab.startswith("trail 8%"):
            lv[k] = peak * 0.92
        elif lab.startswith("trail 15%"):
            lv[k] = peak * 0.85
        elif lab.startswith("close under the 20 EMA minus"):
            lv[k] = ctx["ind2"]["ema20"][k] - 2 * atr_k
        elif lab.startswith("close under the 50 EMA"):
            lv[k] = ctx["ind2"]["ema50"][k]
        elif lab.startswith("close under the 20-bar low"):
            lv[k] = ctx["ind2"]["low20"][k]
        elif lab.startswith("the NEXT chart"):
            lv[k] = ctx.get("hi_lvl", np.full(n, np.nan))[k]
        elif m_ch is not None and lab in XM2.LABELS2:
            lv[k] = peak - m_ch * atr_k
        elif lab.startswith("chandelier 3") or (trailing and "chandelier 3" in lab):
            lv[k] = peak - 3 * atr_k
        elif lab.startswith("chandelier 5"):
            lv[k] = peak - 5 * atr_k
        elif lab == "close under the 12 EMA" or lab.startswith("two closes") or (trailing and "12 EMA" in lab):
            lv[k] = ind["ema12"][k]
        elif lab == "close under the 21 EMA":
            lv[k] = ind["ema21"][k]
        elif lab.startswith("parabolic"):
            lv[k] = ind["sar"][k]
        elif lab.startswith("close under the 10-bar"):
            lv[k] = ind["low10"][k]
        elif trailing and "5-bar low" in lab:
            lv[k] = ind["low5"][k]
        elif trailing and "previous bar" in lab and k > e:
            lv[k] = l[k - 1]
        elif lab.startswith("supertrend"):
            lv[k] = np.nan
        elif "never give it back" in lab and c[k] >= fill + R0:
            lv[k] = max(level, fill)
        else:
            lv[k] = level
    why = "%s (managed by: %s)" % (why0, lab)
    cost = T.CLASS_COST.get(kind, 0.0005)
    ret = exit_px / fill - 1 - cost
    if "flips" not in ctx:
        state = np.array(["FLAT"] * n, dtype=object)
        for kind_, s0_, s1_ in ST.spans(df, causal=True):
            state[s0_:s1_ + 1] = kind_
        chg = np.r_[0, (state[1:] != state[:-1]).astype(int)]
        cs = np.cumsum(chg); fl = np.zeros(n); fl[60:] = cs[60:] - cs[:-60]
        ctx["flips"] = fl
    after = min(n - 1, exit_bar + 60)
    return dict(e=e, fill=fill, trig=trig, prev_low=prev_low, level=lv, raises=[], hhs=[], nth=nth,
                exit_bar=exit_bar, exit_px=exit_px, ended=why, why=why, broke=True, ema=ctx["ema"], rsi=ctx["rsi"], a14=a14,
                pbar=None, ppx=None, risk=R0, ret=ret, after=after, flips=int(ctx["flips"][e - 1]),
                after_px=c[after], after_ret=c[after] / fill - 1 - cost,
                mfe=float(np.max(c[e:exit_bar + 1]) / fill - 1),
                best_after=float(np.max(c[exit_bar:after + 1]) / fill - 1))


def keep_inside(ax, an, pad=3):
    """Measure one label against its own plot and move it back inside (2026-09-11: the stricter overlaps()
    found labels in the lowest lane hanging under the plot, and labels at the left edge hanging off it, on
    most charts in six sets). Off the top or bottom: put it BESIDE its marker instead of under/over it.
    Off the left or right: flip it to the inner side."""
    rend = ax.figure.canvas.get_renderer()
    box = ax.get_window_extent(rend)
    bb = an.get_window_extent(rend)
    ox, oy = an.xyann
    if bb.y0 < box.y0 + pad or bb.y1 > box.y1 - pad:
        ox = 12 if ox >= 0 else -12
        oy = 0
        an.set_va("center")
        an.set_ha("left" if ox > 0 else "right")
        an.xyann = (ox, oy)
        bb = an.get_window_extent(rend)
    if bb.x0 < box.x0 + pad:
        an.set_ha("left"); an.xyann = (max(abs(ox), 9), oy)
    elif bb.x1 > box.x1 - pad:
        an.set_ha("right"); an.xyann = (-max(abs(ox), 9), oy)


def overlaps(fig, axes_with_bars):
    """Measure every piece of text on the figure against every other piece, against the price and
    time scales, against the edges of its own plot, and against the candles. Returns a list of
    plain-English problems.

    2026-09-10: tick labels and plot edges were not measured before, so a label sitting on the
    price numbers or hanging off the side of a plot still came back "clean"."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    probs = []
    texts = []                       # (axes or None, label, window box, kind)
    piv = ("HH", "HL", "LH", "LL", "EH", "EL")
    for ax in fig.axes:
        for t in ax.texts:
            if not t.get_text().strip():
                continue
            try:
                bb = t.get_window_extent(rend)
            except Exception:
                continue
            if bb.width <= 0:
                continue
            texts.append((ax, t.get_text()[:28], bb, "label"))
        for t in (ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)):
            if t is None or not t.get_text().strip():
                continue
            try:
                bb = t.get_window_extent(rend)
            except Exception:
                continue
            if bb.width <= 0:
                continue
            texts.append((ax, t.get_text()[:28], bb, "title"))
    for t in fig.texts:
        if t.get_text().strip():
            texts.append((None, t.get_text()[:28], t.get_window_extent(rend), "figure"))

    def cover(a, b):
        ix = min(a.x1, b.x1) - max(a.x0, b.x0)
        iy = min(a.y1, b.y1) - max(a.y0, b.y0)
        return ix > 2 and iy > 2

    # text on text
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if texts[i][1].strip() in piv and texts[j][1].strip() in piv:
                continue                          # the pivot labels are the chart he already uses
            if cover(texts[i][2], texts[j][2]):
                probs.append("text on text: '%s' and '%s'" % (texts[i][1], texts[j][1]))

    # text on the price or time scale
    scale = []
    for ax in fig.axes:
        x_lo, x_hi = sorted(ax.get_xlim())
        y_lo, y_hi = sorted(ax.get_ylim())
        for tl in ax.get_xticklabels():
            if tl.get_visible() and tl.get_text().strip() and x_lo <= tl.get_position()[0] <= x_hi:
                try:
                    scale.append(tl.get_window_extent(rend))
                except Exception:
                    pass
        for tl in ax.get_yticklabels():
            if tl.get_visible() and tl.get_text().strip() and y_lo <= tl.get_position()[1] <= y_hi:
                try:
                    scale.append(tl.get_window_extent(rend))
                except Exception:
                    pass
    for _ax, label, bb, kind in texts:
        if label.strip() in piv:
            continue
        if any(cover(bb, sb) for sb in scale):
            probs.append("text on the price or time scale: '%s'" % label)

    # a label drawn inside a plot must stay inside that plot
    for ax, label, bb, kind in texts:
        if kind != "label" or label.strip() in piv:
            continue
        box = ax.get_window_extent(rend)
        if bb.x0 < box.x0 - 2 or bb.x1 > box.x1 + 2 or bb.y0 < box.y0 - 2 or bb.y1 > box.y1 + 2:
            probs.append("text hanging off the plot: '%s'" % label)

    # text on a candle
    for ax, d in axes_with_bars:
        lo = d["Low"].values; hi = d["High"].values
        tr = ax.transData
        for _ax, label, bb, kind in texts:
            if label.strip() in piv:
                continue
            x0d, _ = tr.inverted().transform((bb.x0, bb.y0)); x1d, _ = tr.inverted().transform((bb.x1, bb.y1))
            k0 = max(0, int(np.floor(x0d))); k1 = min(len(d) - 1, int(np.ceil(x1d)))
            if k1 < k0:
                continue
            for k in range(k0, k1 + 1):
                p0 = tr.transform((k, lo[k])); p1 = tr.transform((k, hi[k]))
                if bb.x0 <= p0[0] <= bb.x1 and not (p1[1] < bb.y0 or p0[1] > bb.y1):
                    probs.append("text on a candle: '%s'" % label); break

    # off the edge of the whole image
    W, H = fig.canvas.get_width_height()
    for _ax, label, bb, kind in texts:
        if bb.x0 < 0 or bb.y0 < 0 or bb.x1 > W or bb.y1 > H:
            probs.append("text clipped at the edge: '%s'" % label)
    return sorted(set(probs))


def fmt_px(x, ref=None):
    """Price text with the right number of decimals for the name's price level."""
    ref = x if ref is None else ref
    return ("%.4f" if ref < 1 else "%.3f" if ref < 10 else "%.2f") % x


def _chrome(ax):
    ax.set_facecolor(DARK); ax.tick_params(colors=DIM, labelsize=7)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)


def candles(ax, d, ema):
    o = d["Open"].values; hi = d["High"].values; lo = d["Low"].values; cc = d["Close"].values
    x = np.arange(len(d))
    col = np.where(cc >= o, "#3ddc97", "#ff5c72")
    ax.vlines(x, lo, hi, color=col, lw=1.1, zorder=2)
    blo = np.minimum(o, cc); bhi = np.maximum(o, cc)
    ax.bar(x, np.maximum(bhi - blo, np.nanmedian(hi - lo) * 0.12), bottom=blo, width=0.8,
           color=col, edgecolor=col, linewidth=0.4, zorder=3)
    ax.plot(x, ema, color="#c9a35d", lw=1.4, zorder=4)
    ax.set_xlim(-1, len(d)); _chrome(ax)


def render(sym, kind, tf, t, frames, tag, path):
    df = frames[tf]
    w = walk(df, tf, kind, t, key=(sym, tf))
    if w is None:
        return None
    e, xb, af = w["e"], w["exit_bar"], w["after"]
    x0 = max(0, e - 45); x1 = min(len(df) - 1, af)
    if x1 - x0 > 320:
        x0 = max(0, e - 30); x1 = min(len(df) - 1, e + 290)
    d = df.iloc[x0:x1 + 1]
    highs_tfs = [t_ for t_ in HIGHER.get(tf, ()) if frames.get(t_) is not None and len(frames[t_]) >= 40]
    if highs_tfs:
        fig = plt.figure(figsize=(18, 9.5), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(3, 2, width_ratios=[1.5, 1], height_ratios=[4, 1.2, 1.4], hspace=0.22, wspace=0.16, top=0.93, bottom=0.10)
    else:                       # nothing above the weekly: use the whole width
        fig = plt.figure(figsize=(15, 8.5), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(3, 1, height_ratios=[4, 1.2, 0.001], hspace=0.16, top=0.93, bottom=0.10)
    ax = fig.add_subplot(gs[0, 0]); ar = fig.add_subplot(gs[1, 0], sharex=ax)
    # the same drawing the side panels use: labelled pivots, trend colours, 12 EMA.
    # The trend colours here are the LIVE ones (what the rule could see bar by
    # bar), not the hindsight ones, so a buy always sits in green.
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0)
                    for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    plt.setp(ax.get_xticklabels(), visible=False)
    xs = np.arange(len(d))
    lv = w["level"][x0:x1 + 1]
    ax.step(xs, lv, where="post", color="#5aa9ff", lw=1.6, zorder=8)
    col = "#3ddc97" if w["ret"] > 0 else "#ff5c72"

    # NOTHING is allowed to sit on the candles: empty lanes are made above and
    # below the price, every marker and label lives in a lane, and a thin
    # dotted line joins it to the bar it belongs to.
    lo = float(np.nanmin(np.minimum(d["Low"].values, np.nan_to_num(lv, nan=np.inf))))
    hi = float(np.nanmax(d["High"].values))
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.34 * rng, hi + 0.34 * rng)
    ax.set_xlim(-1, len(d) + max(6, int(len(d) * 0.16)))     # a right margin for the level labels
    lane_dn2 = lo - 0.30 * rng      # lower lane: the buy and the pivots
    lane_dn1 = lo - 0.16 * rng
    lane_up = hi + 0.23 * rng       # upper lane: the sale
    lane_up_lo = hi + 0.12 * rng    # a lane under it: the partial
    xr = len(d) + 1

    def peg(x, y_bar, y_lane, colr, marker, size, label=None, weight="bold", fs=8.5, side=0):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=.7, ls=":", alpha=.55, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=size, color=colr,
                   edgecolor="#ffffff", lw=.8, zorder=13)
        if label:
            if marker == "D":
                an = ax.annotate(label, (x, y_lane), xytext=(-9, 0), textcoords="offset points",
                                 ha="right", va="center", color=colr, fontsize=fs, weight=weight, zorder=20)
                keep_inside(ax, an)
                return
            dy = -9 if marker == "^" else 9
            ha = "center" if side == 0 else ("right" if side < 0 else "left")
            an = ax.annotate(label, (x, y_lane), xytext=(9 * side, dy), textcoords="offset points",
                             ha=ha, va="top" if marker == "^" else "bottom",
                             color=colr, fontsize=fs, weight=weight, zorder=20)
            keep_inside(ax, an)

    lows_v = df["Low"].values; highs_v = df["High"].values
    if w["prev_low"] is not None and x0 <= w["prev_low"][1] <= x1:
        pj = w["prev_low"][1]
        peg(pj - x0, lows_v[pj], lane_dn2, "#8b93a1", "^", 70, "previous low", weight="normal", fs=8)
    tj = w["trig"][1]
    if x0 <= tj <= x1:
        crowded = abs(e - tj) <= 5
        peg(tj - x0, lows_v[tj], lane_dn1, "#5aa9ff", "^", 150, "higher low", side=-1 if crowded else 0)
    peg(e - x0, lows_v[e], lane_dn1, "#ffb84d", "^", 190, "buy", side=1 if abs(e - tj) <= 5 else 0)
    if w["pbar"] is not None and x0 <= w["pbar"] <= x1:
        peg(w["pbar"] - x0, highs_v[w["pbar"]], lane_up_lo, "#ffb84d", "D", 110, "sold a third", side=-1)
    peg(xb - x0, highs_v[xb], lane_up, col, "v", 190, "sold the rest %+.1f%%" % (100 * w["ret"]))
    if af > xb and af <= x1:
        ax.axvline(xb - x0, color="#5b6472", lw=.8, ls=":", zorder=5)
    ax.axhline(w["fill"], color="#ffb84d", lw=.8, ls="--", alpha=.6, zorder=5)
    # the two right-edge labels are almost always at the same price (the buy
    # is right above the higher low), so one goes above its line, one below
    lvl = float(np.nanmin(lv)) if np.isfinite(np.nanmin(lv)) else lo
    ax.text(xr, w["fill"], " bought here", color="#ffb84d", fontsize=8, ha="left", va="bottom", zorder=20)
    ax.text(xr, min(lvl, w["fill"]), " last higher low", color="#5aa9ff", fontsize=8, ha="left", va="top", zorder=20)
    ax.set_title("%s  %s      %s %+.1f%%      60 bars after the sale: %+.1f%% from the buy (best %+.1f%%)" % (
        sym, tf, "WORKED" if w["ret"] > 0.005 else "flat" if abs(w["ret"]) <= 0.005 else "LOST",
        100 * w["ret"], 100 * w["after_ret"], 100 * w["best_after"]),
        color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    ar.plot(xs, w["rsi"][x0:x1 + 1], color="#ffb84d", lw=1.2)
    ar.axhline(30, color="#ff5c72", lw=.9, ls="--"); ar.axhline(50, color="#3ddc97", lw=.6, ls=":")
    ar.set_ylim(0, 100); ar.set_yticks([30, 50, 70]); _chrome(ar)
    step = max(len(d) // 8, 1)
    ar.set_xticks(xs[::step]); ar.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    ar.set_xlim(*ax.get_xlim())
    key = [[("#5aa9ff", "▲ the higher low we bought off"), ("#ffb84d", "▲ the buy"),
            ("#ffb84d", "◆ sold a third when up twice the risk"), (col, "▼ sold the rest")],
           [("#5aa9ff", ("— blue line: the stop this exit watches. Exit: %s" % MANAGER) if MANAGER else "— blue line: the last higher low. A wick half a bar under it ends the trade. Once up 3x the risk it trails 8 bars under the high. Lower highs are ignored")],
           [("#8b93a1", "HH HL LH LL: the swing highs and lows. Green background: uptrend. Red: downtrend.   %s" % tag)]]
    for r_, items in enumerate(key):
        xpos = 0.055
        for c_, txt in items:
            fig.text(xpos, 0.058 - 0.024 * r_, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0056 * len(txt) + 0.02
    # higher timeframes: the BUY and the sale marked on them directly, because
    # a shaded band is not enough to see where the trade actually happened
    t_start = df.index[e]
    t_exit = df.index[min(xb + 1, len(df) - 1)]
    t_end = df.index[min(af, len(df) - 1)]
    panel_bars = []
    for row, htf in enumerate(highs_tfs):
        if len(highs_tfs) == 1:
            axh = fig.add_subplot(gs[0:3, 1])          # one panel: use the whole right side
        else:
            axh = fig.add_subplot(gs[0, 1]) if row == 0 else fig.add_subplot(gs[1:3, 1])
        hdf = frames.get(htf)
        if hdf is None or len(hdf) < 40:
            axh.set_visible(False); continue
        # ~90 bars of history before the buy and ~40 after it: he reads the
        # higher chart for what led INTO the trade
        pos = max(0, int(hdf.index.searchsorted(t_start)) - 90); win = min(len(hdf) - pos, 130)
        if win < 20:
            axh.set_visible(False); continue
        CK.render(axh, CK.bundle(hdf, pos, win), "", "%m-%d %H:%M")
        panel_bars.append((axh, hdf.iloc[pos:pos + win]))
        sub = hdf.index[pos:pos + win]
        a = int(sub.searchsorted(t_start)); b = int(sub.searchsorted(t_exit))
        a = min(max(a, 0), win - 1); b = min(max(b, 0), win - 1)
        # this chart can sit on a different price scale (a stock split that the
        # intraday history was never adjusted for), so put the marks on ITS
        # OWN prices at those bars rather than on the lower chart's numbers
        hc = hdf["Close"].values[pos:pos + win]
        buy_y = float(hc[a]); exit_y = float(hc[b])
        scale = buy_y / w["fill"] if w["fill"] else 1.0
        axh.axvline(a, color="#ffb84d", lw=1.0, alpha=.85, zorder=9)
        axh.axvline(b, color=col, lw=1.0, ls="--", alpha=.85, zorder=9)
        hl = hdf["Low"].values[pos:pos + win]; hh = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl)); yhi = float(np.nanmax(hh)); yrng = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.42 * yrng, yhi + 0.42 * yrng)
        band_dn = ylo - 0.25 * yrng      # under the second row of pivot labels
        band_up = yhi + 0.24 * yrng
        # labels go beside the marker, away from the vertical lines
        axh.scatter([a], [band_dn], marker="^", s=150, color="#ffb84d", edgecolor="#ffffff", lw=.8, zorder=14)
        axh.annotate("buy", (a, band_dn), xytext=(0, -10), textcoords="offset points",
                     ha="center", va="top", color="#ffb84d", fontsize=8, weight="bold", zorder=15)
        axh.scatter([b], [band_up], marker="v", s=150, color=col, edgecolor="#ffffff", lw=.8, zorder=14)
        axh.annotate("sold", (b, band_up), xytext=(0, 10), textcoords="offset points",
                     ha="center", va="bottom", color=col, fontsize=8, weight="bold", zorder=15)
        note = "%s  — buy and sale marked" % htf
        if kind in ("stock", "etf") and abs(scale - 1) > 0.25:
            note += "  (prices on a different scale: stock split)"
        axh.set_title(note, loc="left", color=DIM, fontsize=9.5, pad=3)      # above the plot, never on it
        plt.setp(axh.get_xticklabels(), fontsize=6)
    probs = overlaps(fig, [(ax, d)] + [(a_, d_) for a_, d_ in panel_bars])
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    bars = "bars" if tf not in ("1d", "1w") else ("days" if tf == "1d" else "weeks")
    nth_txt = {1: "first", 2: "second", 3: "third"}.get(w["nth"], "%dth" % w["nth"])
    chop_txt = ("calm chart" if w["flips"] <= 2 else "some chop" if w["flips"] <= 4 else "choppy chart") + " (%d trend flips in the last 60 bars)" % w["flips"]
    hi_txt = ""
    htf = HIGHER.get(tf, ())
    if htf and frames.get(htf[0]) is not None:
        try:
            st_ = T.B.higher_view(df, tf, frames[htf[0]], htf[0])[0]
            hi_txt = ", the %s chart was %s" % (htf[0], {"UP": "in an uptrend", "DOWN": "in a downtrend"}.get(str(st_[e - 1]), "flat"))
        except Exception:
            pass
    story = ("Second higher low of the uptrend. %s%s. Bought at %s, just above the low at %s, risking %s a share. "
             % (chop_txt[0].upper() + chop_txt[1:], hi_txt, fmt_px(w["fill"]), fmt_px(w["trig"][2]), fmt_px(w["risk"], w["fill"])))
    if w["pbar"] is not None:
        story += "Got up double the risk after %d %s, sold a third at %s. " % (w["pbar"] - e, bars, fmt_px(w["ppx"]))
    else:
        story += "Never got up double the risk, so no partial. "
    story += "After %d %s, %s. Sold the rest at %s. Result %+.1f%%. " % (xb + 1 - e, bars, w["why"], fmt_px(w["exit_px"]), 100 * w["ret"])
    if w["broke"]:
        if w["best_after"] > w["ret"] + 0.03:
            story += "It later climbed back to %+.1f%% from the buy. That would be a new trade, off a new higher low." % (100 * w["best_after"])
        elif w["after_ret"] < w["ret"] - 0.02:
            story += "60 %s later it was at %+.1f%% from the buy. Getting out was right." % (bars, 100 * w["after_ret"])
        else:
            story += "It went nowhere much after."
    return dict(sym=sym, kind=kind, tf=tf, t=str(t), ret=float(w["ret"]), after_ret=float(w["after_ret"]),
                problems=probs, story=story,
                best_after=float(w["best_after"]), held=int(xb + 1 - e), ended=w["ended"], tag=tag)


# ------------------------------------------------------------------ the set

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
PER_TF = 5
MIN_DOLLARS_DAY = 50e6          # "untradable volume": nothing under this much traded per day
PROCS = max(1, os.cpu_count() or 4)      # every core (owner 2026-09-08: "always using all cores possible")


def _ok_frame(df, tf, kind="stock"):
    """Tradeable data: enough traded, and no gappy candles on the fast charts."""
    dollars = float(np.nanmedian(df["Close"].values * df["Volume"].values)) * T.BARS_DAY[tf]
    if kind not in ("futures", "forex") and (not np.isfinite(dollars) or dollars < MIN_DOLLARS_DAY):
        return False
    cc_ = df["Close"].values.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        jump = cc_[1:] / cc_[:-1]
    if ((jump < 0.62) | (jump > 1.6)).any():
        return False                          # an unadjusted split is still in this file
    gaps = np.abs(df["Open"].values[1:] / df["Close"].values[:-1] - 1)
    if tf in ("5m", "15m", "1h") and np.nanmean(gaps > 0.002) > 0.25:
        return False
    return True


def _scan(args):
    """Worker: one name, every timeframe -> up to 6 random trades per timeframe
    that the rule would actually take. No drawing here."""
    sym, kind, seed = args
    rng = np.random.default_rng(seed)
    try:
        frames = S.frames_for(sym, kind)
    except Exception:
        return []
    out = []
    for tf in TFS:
        df = frames.get(tf)
        if df is None or len(df) < 400 or not _ok_frame(df, tf, kind):
            continue
        ctx = context(df, (sym, tf))
        cands = [(ci, j, p_, lab) for ci, j, p_, lab in ctx["lows"] if lab in ("HL", "EL") and 40 < ci < len(df) - 80]
        rng.shuffle(cands)
        got = 0
        for ci, j, p_, lab in cands[:150]:
            t = df.index[ci + 1]
            try:
                w = walk(df, tf, kind, t, key=(sym, tf))
            except Exception:
                w = None
            if w is None:
                continue
            out.append((tf, sym, kind, str(t)))
            got += 1
            if got >= 6:
                break
    return out


def _draw(args):
    """Worker: draw one chart."""
    n, sym, kind, tf, t = args
    try:
        frames = S.frames_for(sym, kind)
        row = render(sym, kind, tf, t, frames, "picked at random. Not chosen for how it turned out.",
                     os.path.join(OUT, "ride_case_%02d.png" % n))
    except Exception as ex:
        return None, "%s %s %s: %s" % (sym, tf, t, ex)
    if row:
        row.update(n=n, group="%s charts" % tf)
    return row, None


def _init(manager, out):
    """Pool initializer: the exit manager to draw under, and where to write."""
    global MANAGER, OUT
    MANAGER = manager
    OUT = out


def quiet_workers():
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)


def main():
    """Random examples on every timeframe. Nothing is filtered on the outcome.
    Scanning and drawing both run on all the cores."""
    global MANAGER, OUT, PER_TF
    seed = 20260906
    log = None
    for i_, a in enumerate(sys.argv):
        if a == "--seed" and i_ + 1 < len(sys.argv):
            seed = int(sys.argv[i_ + 1])
        if a == "--log" and i_ + 1 < len(sys.argv):
            log = sys.argv[i_ + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
        if a == "--manager" and i_ + 1 < len(sys.argv):
            MANAGER = sys.argv[i_ + 1]          # draw under one of exit_managers.LABELS
        if a == "--out" and i_ + 1 < len(sys.argv):
            OUT = sys.argv[i_ + 1]
        if a == "--per-tf" and i_ + 1 < len(sys.argv):
            PER_TF = int(sys.argv[i_ + 1])
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    rng = np.random.default_rng(seed)
    names = [(s_, k_) for s_, k_ in S.universe() if k_ != "forex"]
    liq = {}
    try:
        k = pd.read_csv("cache/tier1.csv")
        liq = {s_: i_ for i_, s_ in enumerate(k.sort_values("dollar", ascending=False).symbol.astype(str))}
    except Exception:
        pass
    names = [(s_, k_) for s_, k_ in names if k_ not in ("stock", "etf") or liq.get(s_, 9999) < 200]
    rng.shuffle(names)
    names = names[:160]                         # plenty of candidates for 30 charts
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    quiet_workers()
    cands = []
    with cf.ProcessPoolExecutor(max_workers=PROCS, initializer=_init, initargs=(MANAGER, OUT)) as ex:
        for out in ex.map(_scan, [(s_, k_, int(rng.integers(1 << 30))) for s_, k_ in names], chunksize=2):
            cands += out
    print("  scanned %d names, %d candidate trades  (%.0fs)" % (len(names), len(cands), time.time() - t0), flush=True)
    picks = []
    for tf in TFS:
        pool = [c for c in cands if c[0] == tf]
        if not pool:
            print("  no %s candidates" % tf); continue
        idx = rng.choice(len(pool), min(PER_TF, len(pool)), replace=False)
        picks += [pool[int(i_)] for i_ in idx]
    for f in os.listdir(OUT):
        if f.startswith("ride_case_") and f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    jobs = [(n, sym, kind, tf, t) for n, (tf, sym, kind, t) in enumerate(picks, 1)]
    index = []
    with cf.ProcessPoolExecutor(max_workers=PROCS, initializer=_init, initargs=(MANAGER, OUT)) as ex:
        for row, err in ex.map(_draw, jobs, chunksize=1):
            if err:
                print("  " + err, flush=True)
            if row:
                index.append(row)
                print("  ride_case_%02d %-7s %-3s %s  %+.1f%%  %s" % (
                    row["n"], row["sym"], row["tf"], row["t"], 100 * row["ret"],
                    ("PROBLEMS: " + "; ".join(row["problems"])) if row["problems"] else "clean"), flush=True)
    index.sort(key=lambda r: r["n"])
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), rule=MANAGER or "higher low breaks", items=index),
              open(os.path.join(OUT, "ride_cases_index.json"), "w"), indent=1)
    print("  %d charts, %d clean  (%.0fs)" % (len(index), sum(1 for r in index if not r["problems"]), time.time() - t0))
    if log:
        sys.stdout.flush()
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
