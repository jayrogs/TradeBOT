"""pics_intraday.py -- the grammar on 5m / 15m, for grading.

history/ is hourly, so these windows come live from the exchange: the most
recent 200 bars of 15m (BTC, SOL, ETH) and 5m (XRP, DOGE). Rendered through
chartkit (the same backbone as every other chart) and dumped for /paint.
"""

import json
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import chartkit as CK
import crypto
import rider
import structure as ST

warnings.filterwarnings("ignore")

OUT = "validation"
WIN = 200
# PINNED window starts: a re-render must show the SAME chart the owner is
# grading. Only --fresh moves them (and re-pins).
PIN = os.path.join(OUT, "intraday_plan.json")
PLAN = [(1, "BTC", "15m", "2026-08-30 19:30"),
        (2, "SOL", "15m", "2026-08-30 19:30"),
        (3, "ETH", "15m", "2026-08-30 19:30"),
        (4, "XRP", "5m", "2026-09-01 04:45"),
        (5, "DOGE", "5m", "2026-09-01 04:45")]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true",
                    help="move every window to the newest bars and re-pin")
    a = ap.parse_args()
    plan = PLAN
    if os.path.exists(PIN) and not a.fresh:
        plan = [tuple(x) for x in json.load(open(PIN))]
    for f in os.listdir(OUT):
        if f.startswith("v4_"):
            os.remove(os.path.join(OUT, f))
    dumps, rows, pinned = [], [], []
    for n, sym, tf, start in plan:
        df = crypto.candles(sym, tf, 1500, refresh=True)
        if df is None or len(df) < WIN + 100:
            print("  %s %s: no data" % (sym, tf))
            continue
        if a.fresh or start is None:
            pos = len(df) - WIN
        else:
            pos = int(df.index.searchsorted(pd.Timestamp(start)))
            pos = max(0, min(pos, len(df) - WIN))
        pinned.append((n, sym, tf, str(df.index[pos])))
        d = df.iloc[pos:pos + WIN]
        bnd = CK.bundle(df, pos, WIN)
        fig, ax = plt.subplots(figsize=(16, 6.6), dpi=110)
        fig.patch.set_facecolor("#0d0f12")
        CK.render(ax, bnd, "", "%m-%d %H:%M")
        ax.set_title("%s  %s   %s -> %s      PIVOT SPANS: %d in window"
                     % (sym, tf, d.index[0], d.index[-1], len(bnd["spans"])),
                     color="#e6e9ee", fontsize=12, loc="left", pad=10)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "v4_%02d.png" % n),
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        e_full = rider.ema(df["Close"].values.astype(float))
        eqd, _ = ST.eq_display(df)
        piv = ST.labelled_pivots(df)
        dumps.append(dict(
            n=n, sym=sym, tf=tf,
            dates=[str(x) for x in d.index],
            o=[round(float(x), 8) for x in d["Open"]],
            h=[round(float(x), 8) for x in d["High"]],
            l=[round(float(x), 8) for x in d["Low"]],
            c=[round(float(x), 8) for x in d["Close"]],
            ema=[round(float(x), 8) for x in e_full[pos:pos + WIN]],
            state=list(ST.states(df, causal=True)[pos:pos + WIN]),
            eq=[int(x) for x in eqd[pos:pos + WIN]],
            spans=[(k, max(s0, pos) - pos, min(s1, pos + WIN - 1) - pos)
                   for k, s0, s1 in ST.spans(df)
                   if s1 >= pos and s0 <= pos + WIN - 1],
            pivots=[dict(x=j - pos, px=p, kind=k, lab=lab, cx=j - pos)
                    for j, p, k, lab in piv if pos <= j < pos + WIN]))
        rows.append(dict(n=n, sym=sym, tf=tf, touches=0, bars=WIN, net=0))
        print("  v4_%02d  %-4s %-3s  %s -> %s" % (n, sym, tf, d.index[0],
                                                 d.index[-1]))
    json.dump(dumps, open(os.path.join(OUT, "trend_windows.json"), "w"))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)
    json.dump(pinned, open(PIN, "w"))
    print("  windows pinned: re-renders keep these exact starts")


if __name__ == "__main__":
    main()
