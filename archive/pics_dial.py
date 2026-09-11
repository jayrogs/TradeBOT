"""pics_dial.py -- the granularity dial across the round's windows.

Top panel: min leg = 1.00 ATR (current). Bottom: 0.75 ATR (candidate).
Spans and labels recomputed at each setting so the whole downstream effect
is visible, not just the extra pivots. EQ wash omitted on purpose -- one
variable at a time.
"""

import json
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pics_spans as PS
import scanner as SC

warnings.filterwarnings("ignore")

OUT = "validation"
WIN = 200
RULES = {"1h": None, "4h": "4h", "1d": "1D"}


def panel(ax, df, pos, d, min_atr, fmt):
    piv = PS.labelled_pivots(df, min_atr=min_atr)
    spans = PS.spans_from_pivots(piv, len(df), df)
    o = d["Open"].values
    hi = d["High"].values
    lo = d["Low"].values
    cc = d["Close"].values
    for k, s0, s1 in spans:
        a0 = max(s0, pos) - pos
        b0 = min(s1, pos + WIN - 1) - pos
        if b0 >= 0 and a0 <= WIN - 1 and b0 >= a0:
            ax.axvspan(a0 - .5, b0 + .5, lw=0, zorder=0,
                       color={"UP": "#12351f", "DOWN": "#3a1720"}[k])
    for k in range(len(d)):
        col = "#3ddc97" if cc[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=.7, zorder=2)
        ax.plot([k, k], [min(o[k], cc[k]), max(o[k], cc[k])], color=col,
                lw=2.0, zorder=2, solid_capstyle="butt")
    npv = 0
    for j, price, kind, lab in piv:
        if pos <= j < pos + WIN:
            npv += 1
            c2 = PS.LC.get(lab, "#9aa3b2")
            ax.scatter([j - pos], [price], s=24, zorder=6, color=c2,
                       marker="^" if kind == "low" else "v")
            ax.annotate(lab, (j - pos, price), color=c2, fontsize=6.5,
                        weight="bold", ha="center",
                        xytext=(0, -13 if kind == "low" else 8),
                        textcoords="offset points", zorder=6)
    ax.set_facecolor("#0d0f12")
    ax.set_xlim(-1, len(d))
    ax.tick_params(colors="#8b93a1", labelsize=7)
    for sp in ax.spines.values():
        sp.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)
    step = max(len(d) // 7, 1)
    ax.set_xticks(np.arange(len(d))[::step])
    ax.set_xticklabels([v.strftime(fmt) for v in d.index[::step]],
                       fontsize=6.5)
    ax.set_title("min leg = %.2f ATR   (%d pivots in window)"
                 % (min_atr, npv),
                 color="#8b93a1", fontsize=10, loc="left", pad=4)


def main():
    W = json.load(open("validation/trend_windows.json"))
    rows = []
    for w in W:
        sym, tf = w["sym"], w["tf"]
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[tf]) if RULES[tf] else raw
        pos = df.index.get_indexer([pd.Timestamp(w["dates"][0])])[0]
        d = df.iloc[pos:pos + WIN]
        fig, axs = plt.subplots(2, 1, figsize=(16, 9.6), dpi=110)
        fig.patch.set_facecolor("#0d0f12")
        fmt = "%Y-%m-%d" if tf == "1d" else "%m-%d %H:%M"
        panel(axs[0], df, pos, d, 1.00, fmt)
        panel(axs[1], df, pos, d, 0.75, fmt)
        fig.suptitle("%s %s   %s -> %s" % (sym, tf, d.index[0].date(),
                                           d.index[-1].date()),
                     color="#e6e9ee", fontsize=13, x=0.14)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "v4_%02d.png" % w["n"]),
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        rows.append(dict(n=w["n"], sym=sym, tf=tf, touches=0, bars=WIN,
                         net=0))
        print("  v4_%02d  %-5s %-3s rendered" % (w["n"], sym, tf))
    rows.append(dict(n=6, sym="PUMP", tf="1h", touches=0, bars=200, net=0))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
