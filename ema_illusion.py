"""
ema_illusion.py -- four monthly BTC charts. One is real. Three are shuffled.

    python ema_illusion.py

The user's claim is that BTC "rides the EMA12 almost comically" on monthly
candles. That observation is CORRECT -- measured, the candle body sits above the
monthly EMA12 in 70% of months.

The question this answers is whether that is the EMA doing something, or simply
what a strongly trending series looks like. Three of these four panels use BTC's
own monthly returns in a RANDOMISED ORDER: identical drift, identical
volatility, every trace of memory or level-respecting behaviour destroyed. If
the ride is caused by the EMA, the shuffled panels should look obviously
different. If it is caused by drift, they will not.

The real panel is revealed at the bottom of the printed output.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import warnings

warnings.filterwarnings("ignore")

SEED = 11


def load_btc_monthly():
    import yfinance as yf
    d = yf.download("BTC-USD", start="2014-09-01", end="2026-08-20",
                    progress=False, auto_adjust=False).dropna()
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    m = d.resample("ME").agg({"Open": "first", "High": "max",
                              "Low": "min", "Close": "last"}).dropna()
    return m


def shuffle_ohlc(m, rng):
    """Same monthly returns, shuffled order. Wick and body proportions are
    resampled from the real distribution so the candles look native."""
    c = m["Close"].values.astype(float)
    r = np.diff(np.log(c))
    rr = rng.permutation(r)
    cc = c[0] * np.exp(np.concatenate([[0], np.cumsum(rr)]))

    o_ratio = (m["Open"].values / m["Close"].values)
    hi_ratio = (m["High"].values / np.maximum(m["Open"].values, m["Close"].values))
    lo_ratio = (m["Low"].values / np.minimum(m["Open"].values, m["Close"].values))
    idx = rng.integers(0, len(o_ratio), len(cc))
    oo = cc * o_ratio[idx]
    hh = np.maximum(oo, cc) * hi_ratio[idx]
    ll = np.minimum(oo, cc) * lo_ratio[idx]
    return pd.DataFrame({"Open": oo, "High": hh, "Low": ll, "Close": cc},
                        index=m.index)


def body_above(df, span=12):
    e = df["Close"].ewm(span=span, adjust=False).mean().values
    lo = np.minimum(df["Open"].values, df["Close"].values)
    return float((lo >= e).mean())


def draw(ax, df, title):
    e12 = df["Close"].ewm(span=12, adjust=False).mean()
    e26 = df["Close"].ewm(span=26, adjust=False).mean()
    x = np.arange(len(df))
    o = df["Open"].values
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    for i in range(len(df)):
        up = c[i] >= o[i]
        col = "#26a69a" if up else "#ef5350"
        ax.plot([x[i], x[i]], [l[i], h[i]], color=col, lw=0.8, zorder=2)
        ax.add_patch(Rectangle((x[i] - 0.34, min(o[i], c[i])), 0.68,
                               max(abs(c[i] - o[i]), 1e-9),
                               facecolor=col, edgecolor=col, zorder=3))
    ax.plot(x, e12.values, color="#f2c744", lw=1.6, zorder=4, label="EMA12")
    ax.plot(x, e26.values, color="#e05a3a", lw=1.2, zorder=4, label="EMA26")
    ax.set_yscale("log")
    ax.set_title(title, fontsize=11, color="#ddd")
    ax.set_facecolor("#131722")
    ax.tick_params(colors="#888", labelsize=7)
    for s in ax.spines.values():
        s.set_color("#333")
    ax.grid(alpha=0.12)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.2)


def main():
    rng = np.random.default_rng(SEED)
    real = load_btc_monthly()
    panels = [("A", real, True)]
    for i, tag in enumerate(["B", "C", "D"]):
        panels.append((tag, shuffle_ohlc(real, rng), False))
    order = rng.permutation(len(panels))
    panels = [panels[i] for i in order]
    labels = "ABCD"

    fig, axes = plt.subplots(2, 2, figsize=(15, 9), facecolor="#0d1117")
    for ax, (tag, df, is_real), lab in zip(axes.ravel(), panels, labels):
        draw(ax, df, "Panel %s  --  body above EMA12: %.0f%% of months"
             % (lab, 100 * body_above(df)))
    fig.suptitle("Monthly candles with EMA12.  One of these is real Bitcoin.\n"
                 "The other three are Bitcoin's own monthly returns in a "
                 "shuffled order - same drift, same volatility, no memory.",
                 color="#eee", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig("ema_illusion.png", dpi=110, facecolor="#0d1117")

    print("wrote ema_illusion.png\n")
    print("body-above-EMA12 rate, each panel:")
    for (tag, df, is_real), lab in zip(panels, labels):
        print("   Panel %s : %.0f%%   %s" % (lab, 100 * body_above(df),
                                             "<-- THE REAL BITCOIN" if is_real else "shuffled"))
    print("\nIf the EMA12 were causing the ride, only the real panel would show it.")


if __name__ == "__main__":
    main()
