"""
validate_trend.py -- generate a blind batch of charts for the user to grade.

    python validate_trend.py              20 charts, seed 7
    python validate_trend.py --n 30 --seed 12

WHY THIS EXISTS
audit_chart.py checks that the shading agrees with the labels -- but both come
from panel.py, so it is my code checking my code. It catches internal
contradictions and nothing else. The only thing that can tell us whether the
engine reads a trend the way the user does is the user looking at a chart and
saying yes or no.

Right now that has happened for exactly 8 charts, which are the cases in
test_trend.py. Eight is a thin foundation for everything built on top.

THE SAMPLING IS RANDOM ON PURPOSE
If I chose the charts, I would choose ones the engine handles well without
meaning to. So symbols, timeframes and windows are drawn at random from the
cached universe under a fixed seed. The windows that come up are whatever they
are -- clean trends, chop, reversals, gaps. Anything already covered by
test_trend.py is skipped so the batch tests something new.

Grades land in validation/grades.csv. Every chart the user marks WRONG is a new
regression case, exactly like the first eight.
"""

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import chart
import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
OUT = "validation"
BARS = 90
# already graded -- do not re-ask
KNOWN = {("SPY", "W"), ("SOL-USD", "W"), ("BTC-USD", "D"), ("QQQ", "W")}
COLOR = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d", "FLAT": None}


def render(df, sym, tf, path):
    # charts use the backdated shading -- what the eye draws looking back.
    # Anything that gets TESTED must use P.trend_state instead.
    st, hl, lh = P.display_state(df)
    marks = chart.pivot_labels(df)
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(13, 5.6), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    # trend shading, drawn as contiguous runs
    i = 0
    while i < len(st):
        j = i
        while j + 1 < len(st) and st[j + 1] == st[i]:
            j += 1
        col = COLOR.get(st[i])
        if col:
            ax.axvspan(i - 0.5, j + 0.5, color=col, lw=0, zorder=0)
        i = j + 1

    for k in range(len(df)):
        up = c[k] >= o[k]
        col = "#3ddc97" if up else "#ff5c72"
        ax.plot([k, k], [l[k], h[k]], color=col, lw=0.8, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col,
                lw=3.4, zorder=2, solid_capstyle="butt")

    lab_col = {"HH": "#3ddc97", "HL": "#3ddc97", "LH": "#ff5c72",
               "LL": "#ff5c72", "EH": "#8b93a1", "EL": "#8b93a1"}
    # pivot_labels yields (index, price, tag, kind) -- tag is HH/HL/LH/LL/EH/EL
    for pos, price, tag, kind in marks:
        if pos >= len(df):
            continue
        above = kind == "high"
        ax.annotate(tag, (pos, price), fontsize=8.5, weight="bold",
                    color=lab_col.get(tag, "#8b93a1"), zorder=4,
                    ha="center", va="bottom" if above else "top",
                    xytext=(0, 7 if above else -7), textcoords="offset points")

    # Only the level that gets traded off: the low of the last higher low in an
    # uptrend, the high of the last lower high in a downtrend. The engine's own
    # invalidation level (lowest of the last two pivots) is an internal detail
    # and was only noise on the chart.
    tlo, thi = P.tight_levels(df)
    tight = np.where(st == "UP", tlo, np.where(st == "DOWN", thi, np.nan))
    if np.any(np.isfinite(tight)):
        ax.step(x, tight, where="post", color="#5aa9ff", lw=1.5, zorder=3,
                alpha=.95)

    ax.set_xlim(-1, len(df))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=0.6)
    step = max(len(df) // 9, 1)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([d.strftime("%Y-%m-%d") for d in df.index[::step]],
                       rotation=0, fontsize=7.5)
    ax.set_title("%s  %s        %s to %s" %
                 (sym, tf, df.index[0].date(), df.index[-1].date()),
                 color="#e7ebf0", fontsize=11, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)

    frac = {s: float(np.mean(st == s)) for s in ("UP", "DOWN", "BALANCE", "FLAT")}
    return frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--eq-min", type=float, default=0.0,
                    help="only keep windows whose BALANCE share is at least this")
    ap.add_argument("--prefix", default="chart")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    store = pd.read_pickle(CACHE)
    syms = sorted([s for s, d in store.items() if len(d) > 900])
    rng = np.random.default_rng(a.seed)

    items, tries = [], 0
    while len(items) < a.n and tries < a.n * 2000:
        tries += 1
        sym = syms[int(rng.integers(len(syms)))]
        tf = ["D", "W"][int(rng.integers(2))]
        if (sym, tf) in KNOWN:
            continue
        d = store[sym]
        df_all = P.resample(d, "W-FRI") if tf == "W" else d
        if len(df_all) < BARS + 40:
            continue
        end = int(rng.integers(BARS + 20, len(df_all)))
        df = df_all.iloc[end - BARS:end]
        if len(df) < BARS or not np.all(np.isfinite(df["Close"].values)):
            continue
        if any(it["sym"] == sym and it["tf"] == tf for it in items):
            continue
        idx = len(items) + 1
        name = "%s_%02d.png" % (a.prefix, idx)
        if a.eq_min > 0:
            # peek at the state mix before committing to a render, so a batch
            # can be aimed at windows that actually contain an equilibrium.
            # This targets the PRESENCE of EQ, not whether the engine gets it
            # right, so the verdict is still blind.
            try:
                st, _, _ = P.display_state(df)
            except Exception:
                continue
            if float(np.mean(st == "BALANCE")) < a.eq_min:
                continue
        try:
            frac = render(df, sym, tf, os.path.join(OUT, name))
        except Exception as e:
            print("  skip %s %s: %s" % (sym, tf, e))
            continue
        items.append(dict(id=idx, file=name, sym=sym, tf=tf,
                          start=str(df.index[0].date()),
                          end=str(df.index[-1].date()),
                          up=round(frac["UP"], 3), down=round(frac["DOWN"], 3),
                          bal=round(frac["BALANCE"], 3),
                          flat=round(frac["FLAT"], 3)))
        print("  %2d  %-10s %-2s  %s -> %s   up %3.0f%% down %3.0f%% eq %3.0f%%"
              % (idx, sym, tf, df.index[0].date(), df.index[-1].date(),
                 100 * frac["UP"], 100 * frac["DOWN"], 100 * frac["BALANCE"]))

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(dict(seed=a.seed, items=items), f, indent=1)
    print("\n  %d charts in %s/   grade them at http://127.0.0.1:5001/validate"
          % (len(items), OUT))


if __name__ == "__main__":
    main()
