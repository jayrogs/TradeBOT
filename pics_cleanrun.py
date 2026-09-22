"""pics_cleanrun.py -- HE marks the runs (2026-09-22).

His round-1 and round-3 notes rejected two backburners for the RUN, not the trade: BHP "this does not look like a
clean run up, very messy chart"; UNP "really wild daily candles ... daily chart just a bit too hectic for a clean
backburner play". I then fitted a measure ("the share of the last 20 daily bars making a higher low") to his 14
grades, and coded with the study's own window it keeps BHP and drops two he liked. An overfit on 14 points.

So he marks instead, the way he marked the EQs (#26m). 24 DAILY charts of the run into a real backburner dip, drawn
from the trade pool at random, EACH ONE STOPPED AT THE DIP so nothing after it is visible and the outcome cannot
colour the mark. No trade is drawn -- this is only "is that a clean run". Numbers I can measure are recorded in the
index but NOT shown on the page, so the marks stay his eye. After he marks, the measure is built from what his
"clean" runs share that his "messy" ones do not.

    python pics_cleanrun.py --procs 8
Writes validation/clean_run/*.png + index.json  ->  /cleanruns
"""
import concurrent.futures as cf
import glob as _glob
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import panel as P                 # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, AMBER = "#b48cff", "#3ddc97", "#ffb84d"
OUT = os.path.join("validation", "clean_run")
LOOK = 55                          # daily bars of run to show before the dip
N = 12


def suspicion(d, i):
    """MY TWO READS OF WHAT HE DISLIKED, used to PICK the charts he is shown -- not to filter anything yet.
    From his notes on BHP ("does not look like a clean run up, very messy chart") and UNP ("really wild daily
    candles ... too hectic"), and from looking at all three charts beside BIDU and EAT, which he liked:
      bounce  UNP fell 247 -> 220 over two months and then bounced back to 250. My 20-day run measure saw the
              BOUNCE and called it a run. Score: how much of the 40 days before the dip was a fall that the run
              then merely won back.
      twoway  BHP made big candles in BOTH directions the whole way -- up to 55, back to 54, down to 50, sideways
              a week, grind up. A fight, not a run. Score: how much of the total candle length was spent going
              DOWN, against a clean run where the down days are small.
    Higher means more like the two he rejected. Neither is validated -- that is what he is being asked."""
    h = d["High"].values.astype(float); l = d["Low"].values.astype(float); c = d["Close"].values.astype(float)
    hi40 = float(np.max(h[i - 41:i - 15])); lo40 = float(np.min(l[i - 41:i - 15]))
    fall = (hi40 - lo40) / hi40 if hi40 else 0.0
    won_back = (c[i - 1] - lo40) / (hi40 - lo40) if hi40 > lo40 else 0.0
    w = slice(i - 20, i)
    rngs = h[w] - l[w]; steps = np.diff(c[i - 21:i])
    dn = float(np.sum(rngs[steps < 0])); up = float(np.sum(rngs[steps > 0]))
    return dict(bounce=float(fall * max(0.0, min(1.0, won_back))), twoway=float(dn / (up + dn) if up + dn else 0.5))


def measures(d, i):
    """Everything I can think of that might mean 'clean', measured on the 20 daily bars before the dip. Recorded,
    never shown to him, so his mark is his eye and the fit comes afterwards."""
    w = d.iloc[i - 20:i]
    o, h, l, c = (w[x].values.astype(float) for x in ("Open", "High", "Low", "Close"))
    steps = np.diff(c)
    ground = float(np.sum(np.abs(steps))) or np.nan
    rng = np.where(h - l > 0, h - l, np.nan)
    prev_c = np.r_[float(d["Close"].values[i - 21]), c[:-1]]
    return dict(
        straight=float(abs(c[-1] - c[0]) / ground),                       # net travel / ground covered
        hl_share=float(np.mean(l[1:] > l[:-1])),                          # days making a higher low
        up_share=float(np.mean(steps > 0)),
        body=float(np.nanmean(np.abs(c - o) / rng)),                      # body as a share of the candle
        rng_pct=float(np.mean((h - l) / c) * 100),                        # how big a daily candle is
        overlap=float(np.nanmean(np.minimum(h[1:], h[:-1]) - np.maximum(l[1:], l[:-1]) > 0)),
        gaps=float(np.mean(np.abs(o - prev_c) / np.where(rng > 0, rng, np.nan) > 0.25)),
        wick_up=float(np.nanmean((h - np.maximum(o, c)) / rng)),
        wick_dn=float(np.nanmean((np.minimum(o, c) - l) / rng)),
        biggest=float(np.max(np.abs(steps)) / (np.mean(np.abs(steps)) or np.nan)),
        rsi=float(IND.rsi(d["Close"].values.astype(float), 14)[i - 1]),
    )


def _one(args):
    sym, kind = args
    try:
        out = []
        for r in PB.trades_for(sym, kind):
            out.append(dict(sym=sym, kind=kind, k=r["k"], t=r["t"], run=r["run"], clean=r.get("clean")))
        if out:
            fr = S.frames_for(sym, kind)
            fr = {x: v for x, v in fr.items() if x in ("1h", "1d")}
            if kind in ("stock", "etf"):
                fr = FR2.regular_hours(fr)
            for o in out:
                i = int(fr["1d"].index.searchsorted(fr["1h"].index[o["k"]]))
                o.update(suspicion(fr["1d"], i) if i > 45 else dict(bounce=np.nan, twoway=np.nan))
        return out
    except Exception:
        return []


def draw(sym, kind, k, t, path):
    import pics_ride as PR
    fr = S.frames_for(sym, kind)
    fr = {x: v for x, v in fr.items() if x in ("1h", "1d")}
    if kind in ("stock", "etf"):
        fr = FR2.regular_hours(fr)
    df, d = fr["1h"], fr["1d"]
    i = int(d.index.searchsorted(df.index[k]))          # the day of the dip; nothing after it is drawn
    pos = max(0, i - LOOK)
    win = i - pos + 1
    dd = d.iloc[pos:pos + win]
    fig = plt.figure(figsize=(15, 8), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.06, top=0.93, bottom=0.11)
    ax = fig.add_subplot(gs[0])
    bnd = CK.bundle(d, pos, win); bnd["spans"] = []; bnd["pivots"] = []; bnd["eq"] = [False] * win
    CK.render(ax, bnd, "", "%Y-%m-%d")
    c_all = d["Close"].values.astype(float)
    ax.plot(np.arange(win), XM.ema(c_all[:pos + win], 12)[pos:pos + win], color=PURPLE, lw=1.4, zorder=6)
    lo = float(np.nanmin(dd["Low"].values)); hi = float(np.nanmax(dd["High"].values))
    rg = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.10 * rg, hi + 0.10 * rg)
    ax.set_xlim(-1, win + 2)
    plt.setp(ax.get_xticklabels(), visible=False)
    an = ax.annotate("the dip is here", (win - 1, hi + 0.045 * rg), xytext=(0, 0), textcoords="offset points",
                     ha="right", va="center", color=AMBER, fontsize=9, weight="bold", zorder=20)
    PR.keep_inside(ax, an)
    ax.axvline(win - 1, color=AMBER, lw=1.0, ls=":", zorder=5)
    ax.set_title("%s   daily   the run into a backburner dip on %s" % (sym, str(t)[:10]),
                 color="#e6e9ee", fontsize=12, loc="left", pad=8)
    axr = fig.add_subplot(gs[1], sharex=ax)
    axr.set_facecolor(DARK)
    axr.plot(np.arange(win), IND.rsi(c_all[:pos + win], 14)[pos:pos + win], color="#e6e9ee", lw=1.1)
    axr.axhline(30, color=GREEN, lw=0.9, ls="--"); axr.axhline(70, color="#ff5c72", lw=0.9, ls="--")
    axr.set_ylim(5, 95); axr.set_yticks([30, 50, 70]); axr.set_ylabel("RSI 14", color=DIM, fontsize=8)
    axr.tick_params(colors=DIM, labelsize=7)
    for sp in axr.spines.values():
        sp.set_color("#252a33")
    axr.grid(color="#1a1e25", lw=0.5)
    step = max(win // 8, 1)
    axr.set_xticks(np.arange(win)[::step])
    axr.set_xticklabels([q.strftime("%Y-%m-%d") for q in dd.index[::step]], fontsize=6.5)
    fig.text(0.045, 0.035, "the daily chart only, and it STOPS at the dip -- nothing after it is drawn. purple = the 12 EMA."
                           "   Is this a clean run up, or too messy to call a backburner?", color=DIM, fontsize=9, ha="left")
    probs = PR.overlaps(fig, [(ax, dd)])
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs, measures(d, i)


def _draw(args):
    sym, kind, picks = args
    out = []
    for p in picks:
        png = "%s_%s_%d.png" % (kind, sym, p["k"])
        try:
            probs, m = draw(sym, kind, p["k"], p["t"], os.path.join(OUT, png))
            out.append(dict(p, png=png, problems=probs, hidden=m))
        except Exception as ex:
            out.append(dict(p, png=png, problems=["draw: %s" % ex], hidden={}))
    return out


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT]
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got in ex.map(_one, names, chunksize=4):
            rows += got
    print("  %d backburner dips to draw the run for  (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    seen = set()
    for g_ in sorted(_glob.glob(os.path.join("validation", "trade_notes_cleanrun*.csv"))):
        for ln in io.open(g_, encoding="utf-8").read().splitlines()[1:]:
            seen.add(ln.split(",")[0])
    rows = [r for r in rows if "%s_%s_%d.png" % (r["kind"], r["sym"], r["k"]) not in seen]
    # PICKED, NOT RANDOM (his ask): half the set scores most like the two he rejected on my two reads, half least.
    # He is not told which is which, and the page explains both reads in words first.
    rows = [r for r in rows if np.isfinite(r.get("bounce", np.nan)) and np.isfinite(r.get("twoway", np.nan))]
    b = np.array([r["bounce"] for r in rows]); t_ = np.array([r["twoway"] for r in rows])
    z = (b - b.mean()) / (b.std() or 1) + (t_ - t_.mean()) / (t_.std() or 1)
    for r, zz in zip(rows, z):
        r["suspect"] = float(zz)
    order = np.argsort(-z)
    rng = np.random.default_rng(20260922)
    top = [rows[i] for i in order[:60]]; bot = [rows[i] for i in order[-60:]]
    picks = ([top[i] for i in rng.choice(len(top), N // 2, replace=False)]
             + [bot[i] for i in rng.choice(len(bot), N // 2, replace=False)])
    by = {}
    for p in picks:
        by.setdefault((p["sym"], p["kind"]), []).append(p)
    drawn = []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by))) as ex:
        for got in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got
    rng.shuffle(drawn)
    for i, p in enumerate(drawn, 1):
        p["n"] = i
    keep = {d_["png"] for d_ in drawn} | {"index.json"}
    for f in os.listdir(OUT):
        if f not in keep and os.path.isfile(os.path.join(OUT, f)):
            os.remove(os.path.join(OUT, f))

    def _plain(v):
        return v.item() if hasattr(v, "item") else v
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                   charts=[{k_: (_plain(v) if k_ != "hidden" else {a_: _plain(b_) for a_, b_ in v.items()})
                            for k_, v in d_.items()} for d_ in drawn]),
              open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d_ in drawn if d_["problems"]), time.time() - t0))
    for d_ in drawn:
        print("    #%-2d %-6s %s  %s" % (d_["n"], d_["sym"], str(d_["t"])[:10], d_["problems"] or ""))


if __name__ == "__main__":
    main()
