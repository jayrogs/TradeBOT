"""
trade_pics.py -- draw the actual trades the rider test took.

    python trade_pics.py                 six examples, winners and losers
    python trade_pics.py --sym BTC --tf 1h

WHY
Four separate tests of the EMA rider have come back flat, and every one of them
depends on my reading of a rule described in words. Before concluding anything
it is worth LOOKING at what the code actually bought and sold, because three
times already the flaw was that entry and exit sat at the same price and no
amount of statistics said so as clearly as one chart would have.

Each picture shows one trade: where it entered, where it exited, the 12 EMA it
was riding, and the trend shading underneath. If these do not look like the
trades you would have taken, the test is measuring the wrong thing.
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import crypto
import panel as P
import rider
import scanner as SC

warnings.filterwarnings("ignore")

COST = 0.001
OUT = "validation"


def ride_trades(df):
    """One trade per ride, exactly as rider_test.py --exit ride does it."""
    c = df["Close"].values.astype(float)
    n = len(c)
    st = P.trend_state(df)
    r = rider.read(df, state=st)
    armed, near = r["armed"], r["pullback"]
    out = []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        entry = next((k for k in range(i, j + 1) if near[k]), None)
        x = min(j + 1, n - 1)
        if entry is not None and x > entry:
            out.append(dict(entry=int(entry), exit=int(x), ride_start=int(i),
                            bars=int(x - entry),
                            net=float(c[x] / c[entry] - 1 - 2 * COST)))
        i = j + 1
    return out, r


def draw(df, r, t, sym, tf, path):
    pad = max(12, t["bars"])
    a = max(0, t["ride_start"] - pad)
    b = min(len(df) - 1, t["exit"] + pad)
    d = df.iloc[a:b + 1]
    c = d["Close"].values.astype(float)
    o = d["Open"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    e = r["ema"][a:b + 1]
    armed = r["armed"][a:b + 1]
    x = np.arange(len(d))
    ei, xi = t["entry"] - a, t["exit"] - a

    fig, ax = plt.subplots(figsize=(13, 6), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    st, _, _ = P.display_state(d)
    tcol = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d"}
    i = 0
    while i < len(d):
        j = i
        while j + 1 < len(d) and st[j + 1] == st[i]:
            j += 1
        col = tcol.get(st[i])
        if col:
            ax.axvspan(i - .5, j + .5, color=col, lw=0, zorder=0)
        i = j + 1

    for k in range(len(d)):
        col = "#3ddc97" if c[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=.9, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col, lw=3.4,
                zorder=2, solid_capstyle="butt")

    ax.plot(x, e, color="#6b5636", lw=1.2, zorder=3)
    i = 0
    while i < len(d):
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(d) and armed[j + 1]:
            j += 1
        ax.plot(x[i:j + 1], e[i:j + 1], color="#ffb84d", lw=3.2, zorder=4)
        i = j + 1

    ax.axvline(ei, color="#3ddc97", lw=1.2, ls="--", alpha=.7, zorder=5)
    ax.axvline(xi, color="#ff5c72", lw=1.2, ls="--", alpha=.7, zorder=5)
    ax.scatter([ei], [c[ei]], marker="^", s=190, color="#3ddc97", zorder=8,
               edgecolors="#0d0f12", linewidths=1.2)
    ax.scatter([xi], [c[xi]], marker="v", s=190, color="#ff5c72", zorder=8,
               edgecolors="#0d0f12", linewidths=1.2)
    ax.annotate("BUY %.6g" % c[ei], (ei, c[ei]), color="#3ddc97", fontsize=9,
                weight="bold", xytext=(6, -16), textcoords="offset points")
    ax.annotate("SELL %.6g" % c[xi], (xi, c[xi]), color="#ff5c72", fontsize=9,
                weight="bold", xytext=(6, 10), textcoords="offset points")
    # the exit level: the EMA the body had to close under
    ax.plot([ei, xi], [e[ei], e[ei]], color="#5aa9ff", lw=1, ls=":", alpha=.6,
            zorder=4)
    ax.annotate("EMA at entry %.6g" % e[ei], (ei, e[ei]), color="#5aa9ff",
                fontsize=8, xytext=(6, -14), textcoords="offset points")

    ax.set_xlim(-1, len(d))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.5)
    step = max(len(d) // 8, 1)
    ax.set_xticks(x[::step])
    fmt = "%Y-%m-%d" if tf in ("1d", "1w") else "%m-%d %H:%M"
    ax.set_xticklabels([v.strftime(fmt) for v in d.index[::step]], fontsize=7.5)
    ax.set_title("%s  %s   held %d bars   %+.2f%% net" %
                 (sym, tf, t["bars"], 100 * t["net"]),
                 color="#3ddc97" if t["net"] > 0 else "#ff5c72",
                 fontsize=12, loc="left", pad=9)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default=None)
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--n", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    syms = [a.sym] if a.sym else ["BTC", "ETH", "SOL"]
    found = []
    for sym in syms:
        base = SC.BASE.get(a.tf)
        rule = None
        if base is None:
            src, rule = SC.DERIVE[a.tf]
            base = SC.BASE[src]
        raw = crypto.candles(sym, base, 6000)
        df = SC.resample(raw, rule) if rule else raw
        if df is None or len(df) < 300:
            continue
        tr, r = ride_trades(df)
        if not tr:
            continue
        tr.sort(key=lambda t: t["net"])
        picks = [tr[0], tr[len(tr) // 2], tr[-1]]      # worst, median, best
        for t in picks:
            found.append((sym, df, r, t))

    for i, (sym, df, r, t) in enumerate(found[:a.n], 1):
        p = os.path.join(OUT, "trade_%02d.png" % i)
        draw(df, r, t, sym, a.tf, p)
        print("  %-6s %s  entry %s  exit %s  %d bars  %+.2f%%"
              % (sym, p, df.index[t["entry"]].strftime("%m-%d %H:%M"),
                 df.index[t["exit"]].strftime("%m-%d %H:%M"),
                 t["bars"], 100 * t["net"]))


if __name__ == "__main__":
    main()
