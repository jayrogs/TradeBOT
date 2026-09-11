"""
chart.py -- draw the charts with every pivot labelled, so the user can
            check whether the algorithm reads trend the way they do.

    python chart.py BTC-USD W
    python chart.py GLD D SLV W BTC-USD M

Marks each confirmed pivot:
    HH  higher high      HL  higher low
    LH  lower high       LL  lower low

Background shading is the trend state from panel.py:
    green  = uptrend (higher lows intact, last one unbroken)
    red    = downtrend
    grey   = neither

The dashed line is the level that invalidates the current trend -- the last
higher low in an uptrend, the last lower high in a downtrend.

Every pivot is drawn where it was CONFIRMED, not where it printed, so the
chart shows what was actually knowable at the time.
"""

import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import panel as P

warnings.filterwarnings("ignore")


def pivot_labels(df, pv=P.PIVOT):
    """
    Labels from the alternating sequence, using THE SAME tolerance the state
    machine uses.

    Previously the labels compared pivots strictly (any difference above zero
    counted) while trend_state treated anything within 0.5 ATR as the same
    level. So the chart could print "HH" where the logic saw no higher high,
    and the shading looked wrong when it was actually consistent.

    EH / EL mean equal high / equal low -- a pivot close enough to the previous
    one that it is not structure.
    """
    seq = P.zigzag(df, pv)
    atr = P._atr(df)
    out = []
    prev_low = prev_high = None
    for conf, j, price, kind in seq:
        tol = P.SAME_LEVEL_ATR * (atr[j] if np.isfinite(atr[j]) else 0.0)
        if kind == "low":
            if prev_low is None:
                tag = "L"
            elif price > prev_low + tol:
                tag = "HL"
            elif price < prev_low - tol:
                tag = "LL"
            else:
                tag = "EL"
            prev_low = price
        else:
            if prev_high is None:
                tag = "H"
            elif price > prev_high + tol:
                tag = "HH"
            elif price < prev_high - tol:
                tag = "LH"
            else:
                tag = "EH"
            prev_high = price
        out.append((j, price, tag, kind))
    return out


def draw(sym, tf, bars=90, out=None):
    src = {t[0]: (t[1], t[2]) for t in P.TIMEFRAMES}
    if tf not in src:
        print("  unknown timeframe %s" % tf)
        return None
    interval, rule = src[tf]
    d = P.fetch(sym, interval)
    if d is None:
        print("  no data for %s" % sym)
        return None
    df = P.resample(d, rule).tail(bars)
    if len(df) < 20:
        print("  not enough %s bars for %s" % (tf, sym))
        return None

    st, hl, lh = P.trend_state(df)
    marks = pivot_labels(df)
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    e12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(16, 8), facecolor="#0d1117")
    ax.set_facecolor("#131722")

    # trend shading
    col = {"UP": "#12351f", "DOWN": "#3a1414", "FLAT": "#1c1f26",
           "BALANCE": "#13293d"}
    i = 0
    while i < len(st):
        j = i
        while j + 1 < len(st) and st[j + 1] == st[i]:
            j += 1
        ax.axvspan(i - 0.5, j + 0.5, color=col[st[i]], zorder=0)
        i = j + 1

    for k in range(len(df)):
        up = c[k] >= o[k]
        cc = "#26a69a" if up else "#ef5350"
        ax.plot([x[k], x[k]], [l[k], h[k]], color=cc, lw=0.9, zorder=2)
        ax.add_patch(Rectangle((x[k] - 0.32, min(o[k], c[k])), 0.64,
                               max(abs(c[k] - o[k]), (h[k] - l[k]) * 0.002),
                               facecolor=cc, edgecolor=cc, zorder=3))

    ax.plot(x, e12, color="#f2c744", lw=1.4, zorder=4, label="EMA12")

    rng = np.nanmax(h) - np.nanmin(l)
    for idx, price, tag, kind in marks:
        if idx >= len(df):
            continue
        cc = {"HH": "#4ec9b0", "HL": "#4ec9b0",
              "LH": "#e06c75", "LL": "#e06c75",
              "EH": "#9aa0a6", "EL": "#9aa0a6"}.get(tag, "#9aa0a6")
        dy = -rng * 0.035 if kind == "low" else rng * 0.02
        ax.annotate(tag, (idx, price), xytext=(idx, price + dy),
                    color=cc, fontsize=8, ha="center", fontweight="bold",
                    zorder=6)
        ax.plot([idx], [price], marker="o", ms=3.5, color=cc, zorder=6)

    # equilibrium boundaries: two dotted lines -- the most recent LH
    # and the most recent HL. Those are the two levels that break.
    # The blue background already says we are in an EQ, so no extra shading.
    inb, bhi, blo, beq, er = P.balance_zones(df)
    seq = P.zigzag(df)
    k = 0
    while k < len(inb):
        if not inb[k]:
            k += 1
            continue
        j = k
        while j + 1 < len(inb) and inb[j + 1]:
            j += 1
        lows = [q for q in seq if q[3] == "low" and q[0] <= j][-1:]
        highs = [q for q in seq if q[3] == "high" and q[0] <= j][-1:]
        x0, x1 = max(k - 1, 0), min(j + 4, len(df) - 1)
        for group, colr, tag in ((highs, "#e06c75", "LH"), (lows, "#4ec9b0", "HL")):
            for n_, (_, _, price, _) in enumerate(group):
                ax.plot([x0, x1], [price] * 2, color=colr, ls=":", lw=1.3,
                        zorder=5)
                if n_ == len(group) - 1:
                    ax.annotate(" %s %.4g" % (tag, price), (x1, price),
                                color=colr, fontsize=8, va="center", zorder=7)
        k = j + 1

    # the live invalidation level
    s = st[-1]
    lvl = hl[-1] if s == "UP" else (lh[-1] if s == "DOWN" else np.nan)
    if np.isfinite(lvl):
        ax.axhline(lvl, color="#c586c0", ls="--", lw=1.2, zorder=5)
        ax.annotate("  invalidates %.4g" % lvl, (len(df) - 1, lvl),
                    color="#c586c0", fontsize=9, va="bottom")

    ax.set_title("%s   %s   --   currently %s   (%d bars shown)"
                 % (sym, tf, s, len(df)), color="#eee", fontsize=13)
    ax.tick_params(colors="#888", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#333")
    ax.grid(alpha=0.10)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.2)
    n_dates = min(12, len(df))
    ticks = np.linspace(0, len(df) - 1, n_dates).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([df.index[t].strftime("%Y-%m-%d") for t in ticks],
                       rotation=35, ha="right")
    fig.tight_layout()
    path = out or ("chart_%s_%s.png" % (sym.replace("-", ""), tf))
    fig.savefig(path, dpi=105, facecolor="#0d1117")
    plt.close(fig)
    print("  wrote %s   (%s %s, currently %s)" % (path, sym, tf, s))
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = ["BTC-USD", "W"]
    pairs = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    for sym, tf in pairs:
        draw(sym.upper(), tf.upper())


# older scripts call it by its former name
swing_labels = pivot_labels
