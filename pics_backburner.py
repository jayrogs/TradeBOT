"""pics_backburner.py -- pictures of the backburner draft (backburner_live),
for grading at /backburner.

Scans the top crypto names' last ~7 days of 5m bars, finds every RUN the
draft would have worked (1h span up, at least two 5m prints or a 15m print)
and renders a mix: the ones live right now first, then a seeded random
sample of finished ones. Price panel through chartkit (5m spans, EQ wash,
pivots -- the same grammar as every other chart), then the RSI panel with
the 30 line (5m solid, 15m stepped), then volume.

    python pics_backburner.py     # writes validation/backburner_NN.png + backburner_index.json
"""

import json
import os
import random
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import backburner_live as BB
import chartkit as CK
import crypto

warnings.filterwarnings("ignore")

OUT = "validation"
N_PICS = 12
N_LIVE = 4
UNIVERSE = 60
BARS5 = 2000
WIN = 220
LEAD = 40
SEED = 11
DARK, DIM = "#0d0f12", "#8b93a1"
MARK = {"5m": ("#ffb84d", 60, "5m"), "15m": ("#5aa9ff", 110, "15m"),
        "30m": ("#c58cff", 150, "30m"), "1h": ("#ff5c72", 190, "1h")}


def _chrome(ax):
    ax.set_facecolor(DARK)
    ax.tick_params(colors=DIM, labelsize=7)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)


def render(n, sym, run, res, d5, winds):
    """The full chart (chartkit: spans, EQ wash, pivots -- 'the chart was
    great'), with as few WORDS as possible: the owner found the badges,
    legend and long title too much. Prints are numbered circles only."""
    s, e = run["start"], run["end"]
    # the window starts just before the FIRST circle, so the numbering is
    # never cut off on the left; a long stretch loses its tail instead
    first = min(p["bar"] for tf in run["prints"] for p in run["prints"][tf])
    pos = max(0, first - LEAD)
    win = min(len(d5) - pos, WIN)
    bnd = CK.bundle(d5, pos, win)
    fig = plt.figure(figsize=(16, 9.8), dpi=110)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(4, 1, height_ratios=[0.42, 5, 1.7, 1.1], hspace=0.05)
    ax = fig.add_subplot(gs[1])
    at = fig.add_subplot(gs[0], sharex=ax)
    ar = fig.add_subplot(gs[2], sharex=ax)
    av = fig.add_subplot(gs[3], sharex=ax)
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    plt.setp(ax.get_xticklabels(), visible=False)
    plt.setp(ar.get_xticklabels(), visible=False)
    plt.setp(at.get_xticklabels(), visible=False)

    # the higher timeframes as a strip: one row each, green up / red down
    # (shading the whole chart was "not the right idea" -- owner)
    rows = [("1h", winds.get("1h")), ("4h", winds.get("4h")), ("D", winds.get("1d"))]
    for r, (lab, st) in enumerate(reversed(rows)):
        y0, y1 = r / 3.0, (r + 1) / 3.0
        if st is not None:
            seg = st[pos:pos + win]
            k = 0
            while k < win:
                j = k
                while j + 1 < win and seg[j + 1] == seg[k]:
                    j += 1
                col = {"UP": "#3ddc97", "DOWN": "#ff5c72"}.get(seg[k], "#20242b")
                at.axvspan(k - .5, j + .5, ymin=y0 + .04, ymax=y1 - .04,
                           color=col, lw=0, alpha=.85 if seg[k] != "FLAT" else 1)
                k = j + 1
        at.text(-1.5, (y0 + y1) / 2, lab, color=DIM, fontsize=7, ha="right",
                va="center")
    at.set_ylim(0, 1)
    at.set_yticks([])
    at.set_facecolor(DARK)
    for sp in at.spines.values():
        sp.set_visible(False)
    at.tick_params(length=0)
    lo = d5["Low"].values.astype(float)
    xs = np.arange(win)
    ar.plot(xs, res["rsi5"][pos:pos + win], color="#ffb84d", lw=1.0)
    # the prints: 5m = numbered amber circle; 15m / 30m / 1h = a plain
    # circle in their colour (no words). They sit in a LANE along the
    # bottom of the price panel (axes fraction), so a print at the lowest
    # low of the window is never clipped -- the dotted line joins the lane
    # to the candle and on down to the RSI dot.
    y0, y1 = ax.get_ylim()
    ax.set_ylim(y0 - (y1 - y0) * 0.16, y1)
    for tf, lane in (("5m", 0.035), ("15m", 0.095), ("30m", 0.155), ("1h", 0.215)):
        col, _, _ = MARK[tf]
        for k, p in enumerate(run["prints"][tf], 1):
            x = p["bar"] - pos
            if not (0 <= x < win):
                continue
            for a in (ax, ar):
                a.axvline(x, color=col, lw=1.0, alpha=.5, ls=":", zorder=1)
            ax.annotate(str(k) if tf == "5m" else " ", (x, lane),
                        xycoords=("data", "axes fraction"), ha="center",
                        va="center", color=DARK, fontsize=9, weight="bold",
                        bbox=dict(boxstyle="circle,pad=0.28", fc=col,
                                  ec="#ffffff", lw=0.8), zorder=12)
            if tf == "5m":
                ar.scatter([x], [p["rsi"]], s=70, color=col,
                           edgecolor="#ffffff", lw=0.8, zorder=9)
    ar.axhline(BB.OS, color="#ff5c72", lw=.9, ls="--")
    ar.set_ylim(0, 100)
    ar.set_yticks([30, 50, 70])
    _chrome(ar)

    v = d5["Volume"].values.astype(float)[pos:pos + win]
    rv = res["relvol"][pos:pos + win]
    cols = ["#5aa9ff" if (np.isfinite(x) and x >= 2.0) else "#3a3f4a" for x in rv]
    av.bar(xs, v, color=cols, width=.8)
    av.set_yticks([])
    _chrome(av)
    step = max(win // 7, 1)
    av.set_xticks(xs[::step])
    av.set_xticklabels([t.strftime("%m-%d %H:%M")
                        for t in d5.index[pos:pos + win][::step]], fontsize=6.5)

    at.set_title("%s  5m%s" % (sym, "   (live)" if run["live"] else ""),
                 color="#e6e9ee", fontsize=12, loc="left", pad=6)
    fig.savefig(os.path.join(OUT, "backburner_%02d.png" % n),
                facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def main():
    u = crypto.universe(UNIVERSE)
    cands = []
    for _, x in u.iterrows():
        try:
            d5 = crypto.candles(x["sym"], "5m", BARS5, source=x["source"])
            d1h = crypto.candles(x["sym"], "1h", 900, source=x["source"])
            d1d = crypto.candles(x["sym"], "1d", 600, source=x["source"])
        except Exception as ex:
            print("  %s: %s" % (x["sym"], ex))
            continue
        if d5 is None or len(d5) < 600 or d1h is None:
            continue
        res = BB.read(d5, d1h)
        import scanner as SC
        winds = {"1h": BB.wind_at(d5, d1h, "1h"),
                 "4h": BB.wind_at(d5, SC.resample(d1h, "4h"), "4h"),
                 "1d": BB.wind_at(d5, d1d, "1d") if d1d is not None else None}
        for run in res["runs"]:
            p = run["prints"]
            if (len(p["5m"]) >= 2 or p["15m"]) and run["start"] >= LEAD:
                cands.append((x["sym"], run, res, d5, winds))
        print("  %-6s %4d 5m bars  runs %d  live %s" % (
            x["sym"], len(d5), len(res["runs"]),
            "yes" if res["now"]["running"] else "no"))
    live = [c for c in cands if c[1]["live"]]
    done = [c for c in cands if not c[1]["live"]]
    random.seed(SEED)
    random.shuffle(live)
    random.shuffle(done)
    picks = live[:N_LIVE] + done[:N_PICS - min(N_LIVE, len(live))]
    for f in os.listdir(OUT):
        if f.startswith("backburner_") and f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    index = []
    for n, (sym, run, res, d5, winds) in enumerate(picks, 1):
        render(n, sym, run, res, d5, winds)
        p = run["prints"]
        index.append(dict(
            n=n, sym=sym, live=run["live"],
            start=str(d5.index[run["start"]]), end=str(d5.index[run["end"]]),
            prints={tf: [str(d5.index[q["bar"]]) for q in p[tf]] for tf in p},
            chg24=run["chg24"],
            first_best=p["5m"][0].get("best_after"),
            first_after=p["5m"][0].get("close_after"),
            now=(res["now"] if run["live"] else {})))
        print("  backburner_%02d  %-6s from %s  5m x%d 15m x%d  %s" % (
            n, sym, index[-1]["start"], len(p["5m"]), len(p["15m"]),
            "LIVE" if run["live"] else "ended"))
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                   rules=dict(os=BB.OS, wind=BB.WIND_TF,
                              escalate=list(BB.ESCALATE)),
                   candidates=len(cands), live=len(live), items=index),
              open(os.path.join(OUT, "backburner_index.json"), "w"), indent=1)
    print("  %d runs (%d live) -> %d pictures" % (len(cands), len(live), len(index)))


if __name__ == "__main__":
    main()
