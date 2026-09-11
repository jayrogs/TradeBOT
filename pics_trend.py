"""pics_trend.py -- CHARTS of the trend-riding trades from studies/trend_study.py,
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
import json
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
               low_by_ci={x[0]: x for x in lows}, n=len(c))
    _CTX.clear()          # one frame at a time: these are big
    _CTX[key] = ctx
    return ctx


def walk(df, tf, kind, t, key=None):
    """Re-walk one trade from its entry timestamp. Returns everything needed
    to draw it, including the level at every bar of the ride."""
    ctx = context(df, key or (id(df), tf))
    c, o, ema, a14, rsi = ctx["c"], ctx["o"], ctx["ema"], ctx["a14"], ctx["rsi"]
    lows, highs, lcis, hcis, n = ctx["lows"], ctx["highs"], ctx["lcis"], ctx["hcis"], ctx["n"]
    e = int(df.index.get_indexer([pd.Timestamp(t)])[0])
    if e < 2 or e >= n - 2:
        return None
    trig = ctx["low_by_ci"].get(e - 1)
    if trig is None:
        return None
    p = bisect.bisect_right(lcis, e - 1)
    prev_low = lows[p - 2] if p >= 2 else None
    q = bisect.bisect_right(hcis, e - 1)
    level = trig[2]
    lv = np.full(n, np.nan)
    raises, hhs = [], []
    ended, exit_bar, exit_px = None, None, None
    cap = T.CAP_DAYS * T.BARS_DAY[tf]
    for k in range(e, n - 1):
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j >= e and price > level:
                level = price; raises.append((ci, j, price))
        while q < len(highs) and highs[q][0] <= k:
            ci, j, price, lab = highs[q]; q += 1
            if j >= e and lab == "HH":
                hhs.append((j, price))
        lv[k] = level
        if c[k] < level:
            ended, exit_bar, exit_px = "closed under the last higher low", k, o[k + 1]
            break
        if k - e >= cap:
            ended, exit_bar, exit_px = "30 days up", k, o[k + 1]
            break
    if ended is None:
        return None
    cost = T.CLASS_COST.get(kind, 0.0005)
    fill = o[e]
    after = min(n - 1, exit_bar + 60)
    return dict(e=e, fill=fill, trig=trig, prev_low=prev_low, level=lv, raises=raises, hhs=hhs,
                exit_bar=exit_bar, exit_px=exit_px, ended=ended, ema=ema, rsi=rsi, a14=a14,
                ret=exit_px / fill - 1 - cost, after=after,
                after_px=c[after], after_ret=c[after] / fill - 1 - cost,
                mfe=float(np.max(c[e:exit_bar + 1]) / fill - 1),
                best_after=float(np.max(c[exit_bar:after + 1]) / fill - 1))


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
    ax.bar(x, np.maximum(bhi - blo, (hi - lo).mean() * 0.02), bottom=blo, width=0.72,
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
    fig = plt.figure(figsize=(18, 9.5), dpi=105); fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(3, 2, width_ratios=[1.5, 1], height_ratios=[4, 1.2, 1.4], hspace=0.16, wspace=0.16)
    ax = fig.add_subplot(gs[0, 0]); ar = fig.add_subplot(gs[1, 0], sharex=ax)
    candles(ax, d, w["ema"][x0:x1 + 1])
    plt.setp(ax.get_xticklabels(), visible=False)
    xr = len(d) - 0.5
    # the level being held, as a step line
    xs = np.arange(len(d))
    lv = w["level"][x0:x1 + 1]
    ax.step(xs, lv, where="post", color="#5aa9ff", lw=1.6, zorder=8)
    ax.text(xr, np.nanmax(lv), "the line being held: the last higher low ", color="#5aa9ff",
            fontsize=8.5, ha="right", va="bottom", bbox=BOX, zorder=20)
    # the pivots
    if w["prev_low"] is not None:
        pj, pp = w["prev_low"][1], w["prev_low"][2]
        if x0 <= pj <= x1:
            ax.scatter([pj - x0], [pp], marker="v", s=90, color="#8b93a1", zorder=11)
            ax.annotate("previous low", (pj - x0, pp), xytext=(0, -16), textcoords="offset points",
                        ha="center", color="#8b93a1", fontsize=8, bbox=BOX, zorder=20)
    tj, tp = w["trig"][1], w["trig"][2]
    if x0 <= tj <= x1:
        ax.scatter([tj - x0], [tp], marker="^", s=150, color="#5aa9ff", edgecolor="#ffffff", lw=.8, zorder=12)
        ax.annotate("HIGHER low", (tj - x0, tp), xytext=(0, -18), textcoords="offset points",
                    ha="center", color="#5aa9ff", fontsize=8.5, weight="bold", bbox=BOX, zorder=20)
    for ci, j, price in w["raises"]:
        if x0 <= j <= x1:
            ax.scatter([j - x0], [price], marker="^", s=80, color="#5aa9ff", alpha=.75, zorder=11)
    for j, price in w["hhs"]:
        if x0 <= j <= x1:
            ax.scatter([j - x0], [price], marker="v", s=70, color="#3ddc97", alpha=.8, zorder=11)
    # buy, exit, and what happened after
    ax.scatter([e - x0], [w["fill"]], s=260, color="#ffb84d", edgecolor="#ffffff", lw=1.0, zorder=13)
    ax.annotate("BUY", (e - x0, w["fill"]), ha="center", va="center", color=DARK, fontsize=8, weight="bold", zorder=14)
    col = "#3ddc97" if w["ret"] > 0 else "#ff5c72"
    ax.scatter([xb - x0], [w["exit_px"]], marker="X", s=180, color=col, edgecolor="#ffffff", zorder=13)
    ax.annotate("SOLD %+.1f%%: %s" % (100 * w["ret"], w["ended"]), (xb - x0, w["exit_px"]),
                xytext=(0, -20), textcoords="offset points", ha="center", color=col,
                fontsize=8.5, weight="bold", bbox=BOX, zorder=20)
    if af > xb and af <= x1:
        ax.axvline(xb - x0, color="#5b6472", lw=.8, ls=":", zorder=5)
        ax.annotate("60 bars later: %+.1f%% from the buy (best %+.1f%%)" % (100 * w["after_ret"], 100 * w["best_after"]),
                    (af - x0, w["after_px"]), xytext=(-6, 12), textcoords="offset points", ha="right",
                    color="#c9ced6", fontsize=8.5, bbox=BOX, zorder=20)
    ax.axhline(w["fill"], color="#ffb84d", lw=.8, ls="--", alpha=.7)
    ax.text(xr, w["fill"], "bought here ", color="#ffb84d", fontsize=8, ha="right", va="top", bbox=BOX, zorder=20)
    ax.set_title("%s  %s      %s %+.1f%%      %s" % (
        sym, tf, "WORKED" if w["ret"] > 0.005 else "flat" if abs(w["ret"]) <= 0.005 else "LOST",
        100 * w["ret"], tag), color="#e6e9ee", fontsize=12, loc="left", pad=8)
    ar.plot(xs, w["rsi"][x0:x1 + 1], color="#ffb84d", lw=1.2)
    ar.axhline(30, color="#ff5c72", lw=.9, ls="--"); ar.axhline(50, color="#3ddc97", lw=.6, ls=":")
    ar.set_ylim(0, 100); ar.set_yticks([30, 50, 70]); _chrome(ar)
    step = max(len(d) // 8, 1)
    ar.set_xticks(xs[::step]); ar.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    # higher timeframes
    t_start, t_end = df.index[e], df.index[min(af, len(df) - 1)]
    for row, htf in enumerate(HIGHER.get(tf, ())):
        axh = fig.add_subplot(gs[0, 1]) if row == 0 else fig.add_subplot(gs[1:3, 1])
        hdf = frames.get(htf)
        if hdf is None or len(hdf) < 40:
            axh.set_visible(False); continue
        pos_end = int(hdf.index.searchsorted(t_end)) + 12
        pos = max(0, pos_end - 130); win = min(len(hdf) - pos, 130)
        if win < 20:
            axh.set_visible(False); continue
        CK.render(axh, CK.bundle(hdf, pos, win), "", "%m-%d %H:%M")
        sub = hdf.index[pos:pos + win]
        a = int(sub.searchsorted(t_start)); b = int(sub.searchsorted(t_end))
        axh.axvspan(a - .5, b + .5, color="#ffb84d", alpha=0.16, lw=0, zorder=1)
        axh.text(0.01, 0.97, htf, transform=axh.transAxes, color=DIM, fontsize=10, va="top", bbox=BOX, zorder=20)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return dict(sym=sym, kind=kind, tf=tf, t=str(t), ret=float(w["ret"]), after_ret=float(w["after_ret"]),
                best_after=float(w["best_after"]), held=int(xb + 1 - e), ended=w["ended"], tag=tag)


# ------------------------------------------------------------------ the set

# A modest, checkable set of names: the ones the scorecard calls A/B plus the
# majors, so the charts are on names worth trading rather than random dust.
NAMES = [("BTC", "crypto"), ("ETH", "crypto"), ("SOL", "crypto"), ("XRP", "crypto"),
         ("AAVE", "crypto"), ("INJ", "crypto"), ("LDO", "crypto"), ("RENDER", "crypto"),
         ("NVDA", "stock"), ("TSLA", "stock"), ("CLS", "stock"), ("IREN", "stock"),
         ("CRDO", "stock"), ("APP", "stock"), ("HUT", "stock"), ("SOXL", "etf")]
TFS = ["1h", "4h", "1d"]
GROUPS = [
    ("sold, then the trend kept running without me", lambda r: r["ret"] < 0.01 and r["best_after"] > 0.10, 6),
    ("sold near the top, the rule was right", lambda r: r["ret"] > 0.02 and r["best_after"] < r["ret"] + 0.02, 5),
    ("stopped out fast for a small loss (what most of them look like)", lambda r: -0.04 < r["ret"] < 0 and r["held"] <= 8, 5),
    ("the big winners the rule did catch", lambda r: r["ret"] > 0.12, 5),
    ("hot name at the entry", lambda r: r["hot"], 5),
    ("the pivot low sat well under the 12 EMA (a real dip)", lambda r: r["deep"], 4),
]


def main():
    ev = pd.read_csv(os.path.join(OUT, "trend_events.csv.gz"), low_memory=False)
    ev = ev[(ev.null == 0) & ev.tf.isin(TFS)]
    for f in os.listdir(OUT):
        if f.startswith("trend_case_") and f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    # walk every trade on these names first (cheap next to drawing), so the
    # groups below are picked on what ACTUALLY happened, not on a guess
    cand = []
    for sym, kind in NAMES:
        g = ev[(ev.sym == sym) & (ev.kind == kind)]
        if not len(g):
            print("  %s: no trades in the study" % sym); continue
        frames = S.frames_for(sym, kind)
        for tf in TFS:
            if tf not in frames:
                continue
            for _, r in g[g.tf == tf].iterrows():
                try:
                    w = walk(frames[tf], tf, kind, r["t"], key=(sym, tf))
                except Exception:
                    w = None
                if w is None:
                    continue
                cand.append(dict(sym=sym, kind=kind, tf=tf, t=r["t"], ret=w["ret"],
                                 best_after=w["best_after"], after_ret=w["after_ret"],
                                 held=int(w["exit_bar"] + 1 - w["e"]),
                                 hot=bool(r["hot name (up 10%+ on the day or 20%+ in 3 days)"] == "yes"),
                                 deep=bool(r["pivot low vs the 12 EMA"] == "under"),
                                 own=str(r["trend on the chart at entry"]), up1=str(r["higher timeframe trend"])))
        print("  walked %-6s %d trades so far" % (sym, len(cand)), flush=True)
    rng = np.random.default_rng(11)
    picks, seen = [], set()
    for title, test, cnt in GROUPS:
        pool = [c for c in cand if test(c) and (c["sym"], c["tf"], c["t"]) not in seen]
        if not pool:
            continue
        idx = rng.choice(len(pool), min(cnt, len(pool)), replace=False)
        for i in idx:
            c = pool[int(i)]
            seen.add((c["sym"], c["tf"], c["t"]))
            picks.append((title, c))
    index, n, cache = [], 1, {}
    for title, c in picks:
        if c["sym"] not in cache:
            cache = {c["sym"]: S.frames_for(c["sym"], c["kind"])}
        tag = "%s on this chart · higher tf %s · %s%s" % (
            c["own"].lower(), c["up1"].lower(), "hot" if c["hot"] else "not hot",
            " · pivot under the 12 EMA" if c["deep"] else "")
        try:
            row = render(c["sym"], c["kind"], c["tf"], c["t"], cache[c["sym"]], tag,
                         os.path.join(OUT, "trend_case_%02d.png" % n))
        except Exception as ex:
            print("  %s %s %s: %s" % (c["sym"], c["tf"], c["t"], ex)); continue
        if row:
            row.update(n=n, group=title)
            index.append(row)
            print("  trend_case_%02d %-6s %-3s %s  sold %+.1f%%  (best in the 60 bars after: %+.1f%%)  %s" % (
                n, c["sym"], c["tf"], c["t"], 100 * row["ret"], 100 * row["best_after"], title), flush=True)
            n += 1
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), items=index),
              open(os.path.join(OUT, "trend_cases_index.json"), "w"), indent=1)
    print("  %d charts" % len(index))


if __name__ == "__main__":
    main()
