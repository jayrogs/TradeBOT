"""
stairstep.py -- the Stair Step playbook: fade an exhausted run of candles.

    python stairstep.py --measure          what happens after the break
    python stairstep.py --charts 6         render a blind batch to grade
    python stairstep.py NVDA D             read one name

THE PLAYBOOK, as described
    "Fade an exhausted higher-low / lower-high streak. Trade the break of a
    long streak on the trigger timeframe when the higher timeframe favors a
    pullback. Risk stays tiny by entering [near the streak's extreme]."

THE DEFINITION WE USE
    A stair step is CONSECUTIVE GREEN CANDLES -- close above open, N times in a
    row. Not consecutive higher lows. One side has bought every single bar, and
    past some length that is unsustainable rather than strong.

    STAIR_N = 7. Measured across 3.0M daily bars in 605 markets, a run of 7+
    green candles happens 12,179 times -- about one per market per year. Six is
    twice as common, eight is half. Seven is frequent enough to trade and rare
    enough to mean something.

    Mirror for shorts: 7+ consecutive red candles, faded upward.

THE TENSION WORTH KNOWING
    rider.py uses a run of higher lows as a CONTINUATION tell -- two or more
    means the ride is healthy, keep buying dips. This playbook reads a long run
    as EXHAUSTION and bets against it. Same family of measurement, opposite
    conclusion, so the threshold is doing all the work.

UNVALIDATED. The forward returns below are a first look at a raw pattern with
no context filter and no costs. Roughly 22,000 configurations have been tested
in this project and none beat buy-and-hold out of sample. Treat a positive
number here as a reason to look closer, not as an edge.
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

import panel as P

warnings.filterwarnings("ignore")

STAIR_N = 7             # consecutive candles that make a stair step
OUT = "validation"
CACHE = os.path.join("cache", "scan_prices.pkl")


def runs(df, n=STAIR_N):
    """Every completed stair step. Returns (start, end, direction) per run.

    `end` is the last candle OF the streak. The break is the bar after it.
    """
    o = df["Open"].values.astype(float)
    c = df["Close"].values.astype(float)
    green = c > o
    red = c < o
    out = []
    for flag, side in ((green, "up"), (red, "down")):
        i = 0
        while i < len(flag):
            if not flag[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(flag) and flag[j + 1]:
                j += 1
            if j - i + 1 >= n:
                out.append((i, j, side))
            i = j + 1
    return sorted(out)


def read(df, n=STAIR_N):
    """Per-bar view: how long the current run is, and where a step just ended."""
    o = df["Open"].values.astype(float)
    c = df["Close"].values.astype(float)
    m = len(c)
    green = c > o
    red = c < o
    up_run = np.zeros(m, dtype=int)
    dn_run = np.zeros(m, dtype=int)
    for i in range(m):
        up_run[i] = up_run[i - 1] + 1 if (i and green[i]) else int(green[i])
        dn_run[i] = dn_run[i - 1] + 1 if (i and red[i]) else int(red[i])
    return dict(idx=df.index, close=c, open=o, green=green, red=red,
                up_run=up_run, dn_run=dn_run,
                stepped_up=up_run >= n, stepped_dn=dn_run >= n,
                runs=runs(df, n))


def measure(n=STAIR_N, horizons=(1, 3, 5, 10, 20)):
    """After a stair step breaks, what does price actually do?"""
    store = pd.read_pickle(CACHE)
    rows = []
    for sym, d in store.items():
        if len(d) < 400:
            continue
        c = d["Close"].values.astype(float)
        h = d["High"].values.astype(float)
        l = d["Low"].values.astype(float)
        if not np.all(np.isfinite(c)) or c.min() <= 0:
            continue
        for i, j, side in runs(d, n):
            b = j + 1                       # the break bar
            if b >= len(c) - max(horizons) - 1:
                continue
            entry = c[b]
            rec = dict(sym=sym, side=side, length=j - i + 1,
                       run_gain=c[j] / c[i - 1] - 1 if i else np.nan,
                       stop=(h[i:j + 1].max() if side == "up"
                             else l[i:j + 1].min()),
                       entry=entry)
            rec["risk"] = abs(rec["stop"] / entry - 1)
            for k in horizons:
                fwd = c[b + k] / entry - 1
                # a fade is short after a green run, long after a red one
                rec["r%d" % k] = -fwd if side == "up" else fwd
            rows.append(rec)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ chart

def draw(df, sym, tf, path, n=STAIR_N):
    r = read(df, n)
    c, o = r["close"], r["open"]
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(13, 5.6), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    # background stays with the trend engine, as everywhere else
    tstate, _, _ = P.display_state(df)
    tcol = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d"}
    i = 0
    while i < len(df):
        j = i
        while j + 1 < len(df) and tstate[j + 1] == tstate[i]:
            j += 1
        col = tcol.get(tstate[i])
        if col:
            ax.axvspan(i - 0.5, j + 0.5, color=col, lw=0, zorder=0)
        i = j + 1

    # the stair steps themselves, and where each one broke
    for a, b, side in r["runs"]:
        band = "#ffb84d" if side == "up" else "#5aa9ff"
        ax.axvspan(a - 0.5, b + 0.5, color=band, alpha=0.16, lw=0, zorder=1)
        top = hi[a:b + 1].max() if side == "up" else lo[a:b + 1].min()
        ax.plot([a - 0.5, b + 0.5], [top, top], color=band, lw=1.2, ls="--",
                zorder=4)
        ax.annotate("%d" % (b - a + 1), (a + (b - a) / 2, top), color=band,
                    fontsize=9, weight="bold", ha="center", va="bottom",
                    xytext=(0, 5), textcoords="offset points", zorder=5)
        if b + 1 < len(df):
            ax.scatter([b + 1], [c[b + 1]], marker="v" if side == "up" else "^",
                       s=64, color="#ff5c72" if side == "up" else "#3ddc97",
                       zorder=6)

    for k in range(len(df)):
        col = "#3ddc97" if c[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=0.8, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col,
                lw=3.4, zorder=2, solid_capstyle="butt")

    ax.plot([], [], color="#ffb84d", lw=6, alpha=.4, label="stair step up (fade short)")
    ax.plot([], [], color="#5aa9ff", lw=6, alpha=.4, label="stair step down (fade long)")
    ax.scatter([], [], marker="v", color="#ff5c72", label="the break -- entry")
    ax.set_xlim(-1, len(df))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=0.6)
    step = max(len(df) // 9, 1)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([d.strftime("%Y-%m-%d") for d in df.index[::step]],
                       fontsize=7.5)
    ax.set_title("%s  %s   STAIR STEP (%d+)    %s to %s"
                 % (sym, tf, n, df.index[0].date(), df.index[-1].date()),
                 color="#e7ebf0", fontsize=11, loc="left", pad=10)
    leg = ax.legend(loc="upper left", fontsize=8, framealpha=.3,
                    facecolor="#15181d", edgecolor="#252a33")
    for t in leg.get_texts():
        t.set_color("#8b93a1")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return len(r["runs"])


def batch(count, seed, n=STAIR_N):
    store = pd.read_pickle(CACHE)
    syms = sorted([s for s, d in store.items() if len(d) > 900])
    rng = np.random.default_rng(seed)
    items, tries = [], 0
    os.makedirs(OUT, exist_ok=True)
    while len(items) < count and tries < count * 3000:
        tries += 1
        sym = syms[int(rng.integers(len(syms)))]
        tf = ["D", "W"][int(rng.integers(2))]
        d = P.resample(store[sym], "W-FRI") if tf == "W" else store[sym]
        if len(d) < 130:
            continue
        end = int(rng.integers(110, len(d)))
        df = d.iloc[end - 90:end]
        if len(df) < 90 or not np.all(np.isfinite(df["Close"].values)):
            continue
        if any(it["sym"] == sym for it in items):
            continue
        if not runs(df, n):
            continue                        # nothing to look at
        idx = len(items) + 1
        name = "stair_%02d.png" % idx
        k = draw(df, sym, tf, os.path.join(OUT, name), n)
        items.append(dict(id=idx, file=name, sym=sym, tf=tf,
                          start=str(df.index[0].date()),
                          end=str(df.index[-1].date()),
                          up=round(k / 10.0, 3), down=0.0, bal=0.0, flat=0.0))
        print("  %2d  %-9s %-2s  %s -> %s   %d stair step(s)"
              % (idx, sym, tf, df.index[0].date(), df.index[-1].date(), k))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(dict(seed=seed, items=items), f, indent=1)
    print("\n  %d charts -- grade at http://127.0.0.1:5001/validate" % len(items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?")
    ap.add_argument("tf", nargs="?", default="D")
    ap.add_argument("--charts", type=int, default=0)
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--n", type=int, default=STAIR_N)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()

    if a.measure:
        R = measure(a.n)
        R.to_csv("stairstep_results.csv", index=False)
        print("=" * 74)
        print("  FADING A %d+ CANDLE STAIR STEP -- %d events" % (a.n, len(R)))
        print("=" * 74)
        print("  a fade is SHORT after a green run, LONG after a red one")
        print("  no costs, no context filter, no stop applied")
        print()
        print("  %-8s %9s %9s %9s" % ("horizon", "median", "mean", "share up"))
        for k in (1, 3, 5, 10, 20):
            x = R["r%d" % k].dropna()
            print("  %-8s %+8.2f%% %+8.2f%% %8.0f%%"
                  % ("%dd" % k, 100 * x.median(), 100 * x.mean(),
                     100 * (x > 0).mean()))
        print()
        print("  by direction, at 5 days:")
        for side, g in R.groupby("side"):
            print("    %-5s %6d events   median %+.2f%%   mean %+.2f%%   up %.0f%%"
                  % (side, len(g), 100 * g.r5.median(), 100 * g.r5.mean(),
                     100 * (g.r5 > 0).mean()))
        print()
        print("  median risk to the streak's extreme: %.1f%%"
              % (100 * R.risk.median()))
        print("  full table: stairstep_results.csv")
        return

    if a.charts:
        batch(a.charts, a.seed, a.n)
        return
    if not a.symbol:
        ap.error("give a symbol, or --charts N, or --measure")

    store = pd.read_pickle(CACHE)
    d = store[a.symbol.upper()]
    df = P.resample(d, "W-FRI") if a.tf.upper() == "W" else d
    r = read(df.tail(200), a.n)
    print("  %s %s   up-run %d   down-run %d   stair steps in window: %d"
          % (a.symbol.upper(), a.tf.upper(), r["up_run"][-1], r["dn_run"][-1],
             len(r["runs"])))


if __name__ == "__main__":
    main()
