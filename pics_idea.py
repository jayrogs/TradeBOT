"""pics_idea.py -- one simple picture per idea on the dashboard, drawn from real bars.

    python pics_idea.py            -> static/ideas/*.png  (+ ideas.json with the captions)

The point is the IDEA, not the study: few candles, big labels, one story each.
    trend_ride.png   buy the second higher low, sell when the last higher low breaks
    exits.png        the same buy, two ways to sell (his line vs a stop under the highest close)
    backburner.png   oversold on a running name: buy, a third off at the bounce, hold to the line
    eq.png           the EQ: higher lows into lower highs, tightening, then the break
    channel.png      a flat-sided box (NOT an EQ); the other page
    trend_steps.png  what the trend study counts: steps per trend, and a fakeout
Every picture is measured with pics_ride.overlaps before it is saved.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import structure as ST            # noqa: E402
import eq_break as EB             # noqa: E402
import exit_managers as XM        # noqa: E402
import pics_ride as PR            # noqa: E402

OUT = os.path.join(HERE, "static", "ideas")
DARK, FG, DIM, FAINT = "#0d0f12", "#e6e9ee", "#8b93a1", "#5b6472"
UP, DN, BLUE, AMBER, GREY = "#3ddc97", "#ff5c72", "#5aa9ff", "#ffb84d", "#8b93a1"
FS = 10.5


def fmt(x):
    return ("%.4g" % x) if x < 10 else ("%.2f" % x) if x < 1000 else ("%.0f" % x)


def fig_ax(w=11.5, h=5.4):
    fig = plt.figure(figsize=(w, h), dpi=100); fig.patch.set_facecolor(DARK)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.20)
    ax = fig.add_subplot(111); ax.set_facecolor(DARK)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.tick_params(colors=DIM, labelsize=7.5)
    ax.grid(color="#1b1f26", lw=.4)
    return fig, ax


def candles(ax, d, ema=None, nticks=7):
    o = d["Open"].values.astype(float); h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float); c = d["Close"].values.astype(float)
    for k in range(len(d)):
        col = UP if c[k] >= o[k] else DN
        ax.plot([k, k], [l[k], h[k]], color=col, lw=.8, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col, lw=3.2, zorder=2, solid_capstyle="butt")
    if ema is not None:
        ax.plot(np.arange(len(d)), ema, color="#c9a35d", lw=1.0, zorder=3, alpha=.8)
    step = max(len(d) // nticks, 1)
    ax.set_xticks(np.arange(len(d))[::step])
    ax.set_xticklabels([q.strftime("%Y-%m-%d" if (d.index[1] - d.index[0]) >= pd.Timedelta(days=1) else "%m-%d %H:%M") for q in d.index[::step]], fontsize=7.5)


def lanes(ax, d, pad=0.42):
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - pad * rng, hi + pad * rng)
    ax.set_xlim(-1, len(d) + 1)
    return lo - 0.22 * rng, hi + 0.22 * rng, rng


def peg(ax, x, y_bar, y_lane, col, marker, label, side=0, size=200, dy=None):
    """A marker in the empty lane, a dotted thread down/up to the bar, the words next to it."""
    ax.plot([x, x], [y_bar, y_lane], color=col, lw=.8, ls=":", alpha=.7, zorder=6)
    ax.scatter([x], [y_lane], marker=marker, s=size, color=col, edgecolor="#ffffff", lw=.9, zorder=13)
    below = y_lane < y_bar
    if dy is None:
        dy = -13 if below else 13
    ha = "center" if side == 0 else ("right" if side < 0 else "left")
    ax.annotate(label, (x, y_lane), xytext=(10 * side, dy), textcoords="offset points", ha=ha,
                va="top" if dy < 0 else "bottom", color=col, fontsize=FS, weight="bold", zorder=20)


def note(fig, lines):
    """The words under the picture, wrapped so nothing runs off the edge."""
    import textwrap
    rows = []
    for col, txt in lines:
        rows += [(col, w) for w in textwrap.wrap(txt, 150)]
    for i, (col, txt) in enumerate(rows):
        fig.text(0.04, 0.012 + 0.028 * (len(rows) - 1 - i), txt, color=col, fontsize=9.5, ha="left", va="bottom")


def save(fig, ax, d, name, panels=()):
    probs = PR.overlaps(fig, [(ax, d)] + list(panels))
    path = os.path.join(OUT, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("  %-16s %s" % (name, "clean" if not probs else probs))
    return probs


# ------------------------------------------------------------------ 1. the trend ride
def find_ride(candidates, tf="1d", want=(0.06, 0.60), held=(12, 45)):
    """A trade under his rules that worked, with a few raises of the line: the picture of the idea."""
    best = None
    for sym, kind in candidates:
        fr = S.frames_for(sym, kind)
        df = fr.get(tf)
        if df is None or len(df) < 400:
            continue
        ctx = PR.context(df, ("idea", sym, tf))
        for ci, j, p, lab in ctx["lows"]:
            if lab not in ("HL", "EL") or ci + 1 >= len(df) - 60:
                continue
            r = PR.walk(df, tf, kind, df.index[ci + 1], key=("idea", sym, tf))
            if r is None or r["nth"] != 2 or not r["broke"]:
                continue
            hold = r["exit_bar"] - r["e"]
            raises = len(set(np.round(r["level"][r["e"]:r["exit_bar"] + 1], 6))) - 1
            if want[0] <= r["ret"] <= want[1] and held[0] <= hold <= held[1] and raises >= 1 and r["pbar"] is not None:
                score = raises * 10 + hold
                if best is None or score > best[0]:
                    best = (score, sym, kind, df, r)
    return best


def idea_trend_ride(pick):
    _, sym, kind, df, r = pick
    e, xb = r["e"], r["exit_bar"]
    trig = r["trig"]; prev = r["prev_low"]
    x0 = max(0, (prev[1] if prev else trig[1]) - 14); x1 = min(len(df) - 1, xb + 6)
    d = df.iloc[x0:x1 + 1]
    l = df["Low"].values.astype(float); h = df["High"].values.astype(float); o = df["Open"].values.astype(float)
    fig, ax = fig_ax()
    candles(ax, d)
    ldn, lup, rng = lanes(ax, d)
    xs = np.arange(len(d))
    lv = r["level"]
    seg = np.array([lv[k] if e <= k <= xb else np.nan for k in range(x0, x1 + 1)])
    ax.step(xs, seg, where="post", color=BLUE, lw=2.2, zorder=8)
    # the two higher lows that opened the idea, and the one we buy
    if prev is not None:
        peg(ax, prev[1] - x0, l[prev[1]], ldn, BLUE, "^", "1st higher low", side=-1)
    peg(ax, trig[1] - x0, l[trig[1]], ldn, BLUE, "^", "2nd higher low", side=0, dy=-28)
    peg(ax, e - x0, o[e], ldn, AMBER, "^", "BUY at the next open", side=1, size=260)
    # the higher high before it
    hh = [(ci, j, p, lab) for ci, j, p, lab in PR.context(df, ("idea", sym, "1d"))["highs"] if lab == "HH" and j < trig[1] and j >= x0]
    if hh:
        ci, j, p, lab = hh[-1]
        peg(ax, j - x0, h[j], lup, BLUE, "v", "a higher high: the uptrend is real", side=-1, dy=13)
    if r["pbar"] is not None:
        peg(ax, r["pbar"] - x0, h[r["pbar"]], lup, UP, "v", "sell a third: up 2x the risk", side=1, dy=13)
    peg(ax, xb - x0, l[xb], ldn, DN, "^", "a wick under the line: SELL next open", side=1, dy=-13, size=240)
    ax.text(len(d), lv[xb], "the line = the last higher low\n(it only ever moves UP)", color=BLUE, fontsize=9, va="center", ha="left", zorder=20)
    ax.set_xlim(-8, len(d) + 30)
    ax.set_title("Trend ride: buy the second higher low, sell when the last higher low breaks      %s %s, %+.1f%%" % (sym, "daily", 100 * r["ret"]),
                 color=FG, fontsize=12, loc="left", pad=8)
    note(fig, [(DIM, "The uptrend needs a higher low AND a higher high first. Then buy the SECOND higher low at the next open. Take a third off when up twice the risk. Out on a wick under the last higher low.")])
    return save(fig, ax, d, "trend_ride.png"), dict(sym=sym, tf="1d", t=str(df.index[e]), ret=r["ret"])


# ------------------------------------------------------------------ 2. exits: same buy, two ways to sell
def idea_exits(pick):
    _, sym, kind, df, r = pick
    e = r["e"]
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    a14 = S.atr(h, l, c); n = len(c)
    # chandelier 5 from the same buy
    peak = c[e]; ch = np.full(n, np.nan); xb2 = None
    for k in range(e, n - 1):
        peak = max(peak, c[k]); ch[k] = peak - 5 * a14[k]
        if c[k] < ch[k]:
            xb2 = k; break
    if xb2 is None:
        xb2 = min(n - 2, e + 80)
    xb1 = r["exit_bar"]
    x0 = max(0, e - 8); x1 = min(n - 1, max(xb1, xb2) + 6)
    d = df.iloc[x0:x1 + 1]
    fig, ax = fig_ax()
    candles(ax, d)
    ldn, lup, rng = lanes(ax, d)
    xs = np.arange(len(d))
    lv = r["level"]
    ax.step(xs, np.array([lv[k] if e <= k <= xb1 else np.nan for k in range(x0, x1 + 1)]), where="post", color=BLUE, lw=2.2, zorder=8)
    ax.plot(xs, np.array([ch[k] if e <= k <= xb2 else np.nan for k in range(x0, x1 + 1)]), color=AMBER, lw=1.8, ls="--", zorder=8)
    peg(ax, e - x0, o[e], ldn, GREY, "^", "same BUY", side=0, size=240)
    ret1 = o[xb1 + 1] / o[e] - 1; ret2 = o[xb2 + 1] / o[e] - 1
    peg(ax, xb1 - x0, l[xb1], ldn, BLUE, "^", "his line breaks: sold %+.0f%%" % (100 * ret1), side=-1 if xb1 <= xb2 else 1)
    peg(ax, xb2 - x0, h[xb2], lup, AMBER, "v", "the loose stop hits: sold %+.0f%%" % (100 * ret2), side=1 if xb2 >= xb1 else -1)
    ax.text(len(d), lv[xb1], "his line: the last higher low", color=BLUE, fontsize=9, va="center", ha="left", zorder=20)
    ax.text(len(d), ch[xb2], "loose stop: 5 normal bars\nunder the highest close", color=AMBER, fontsize=9, va="center", ha="left", zorder=20)
    ax.set_xlim(-1, len(d) + 26)
    ax.set_title("Exits: the same buy, two ways to sell      %s daily" % sym, color=FG, fontsize=12, loc="left", pad=8)
    note(fig, [(DIM, "Forty exits were tested after the same buy. Looser stops made more per trade and held longer; his line is the tightest. /exitcharts shows random examples of each.")])
    return save(fig, ax, d, "exits.png"), dict(sym=sym, ret1=ret1, ret2=ret2)


# ------------------------------------------------------------------ 3. the backburner
def find_backburner(candidates, tf="1h"):
    """RSI at or under 30 on a name whose daily chart is in an uptrend; buy the next open; a third off
    when price is back one normal bar above the buy; the rest out on a close under the last higher low."""
    best = None
    for sym, kind in candidates:
        fr = S.frames_for(sym, kind)
        df, hdf = fr.get(tf), fr.get("1d")
        if df is None or hdf is None or len(df) < 500:
            continue
        c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        n = len(c); a14 = S.atr(h, l, c); rsi = XM.rsi(c)
        hi_state = S.higher_view(df, tf, hdf, "1d")[0]
        piv = ST.pivots(df)
        lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
        lcis = [x[0] for x in lows]
        import bisect
        for i in range(60, n - 80):
            if not (rsi[i] <= 30 and rsi[i - 1] > 30 and str(hi_state[i]) == "UP"):
                continue
            e = i + 1; fill = o[e]
            # the bounce: a third off at fill + 1 normal bar
            tgt = fill + a14[i]
            pb = next((k for k in range(e, min(n - 1, e + 40)) if h[k] >= tgt), None)
            if pb is None:
                continue
            # the line: last higher low confirmed by then (must exist), rest out on a close under it
            q = bisect.bisect_right(lcis, e - 1)
            level = None
            for m in range(q - 1, -1, -1):
                if lows[m][3] in ("HL", "EL"):
                    level = lows[m][2]; break
            if level is None or level >= fill:
                continue
            xb = None; lv = {}
            for k in range(e, n - 1):
                while q < len(lows) and lows[q][0] <= k:
                    ci, j, p, lab = lows[q]; q += 1
                    if j >= e and lab in ("HL", "EL") and p > level:
                        level = p
                lv[k] = level
                if c[k] < level:
                    xb = k; break
                if k - e > 120:
                    break
            if xb is None or xb <= pb:
                continue
            ret = (tgt / fill - 1) / 3 + 2 * (o[xb + 1] / fill - 1) / 3
            if 0.03 <= ret <= 0.25 and 15 <= xb - e <= 90:
                score = ret * 100 + min(xb - e, 60) / 10
                if best is None or score > best[0]:
                    best = (score, sym, kind, df, dict(i=i, e=e, pb=pb, tgt=tgt, xb=xb, lv=lv, ret=ret, rsi=rsi, a14=a14, hi_state=hi_state))
    return best


def idea_backburner(pick):
    _, sym, kind, df, r = pick
    i, e, pb, xb = r["i"], r["e"], r["pb"], r["xb"]
    o = df["Open"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float); c = df["Close"].values.astype(float)
    x0 = max(0, i - 30); x1 = min(len(df) - 1, xb + 8)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    fig = plt.figure(figsize=(11.5, 6.4), dpi=100); fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.16, top=0.91, bottom=0.21)
    ax = fig.add_subplot(gs[0]); axr = fig.add_subplot(gs[1], sharex=ax)
    for a_ in (ax, axr):
        a_.set_facecolor(DARK)
        for s in a_.spines.values():
            s.set_color("#252a33")
        a_.tick_params(colors=DIM, labelsize=7.5); a_.grid(color="#1b1f26", lw=.4)
    candles(ax, d, ema=XM.ema(c, 12)[x0:x1 + 1])
    plt.setp(ax.get_xticklabels(), visible=False)
    ldn, lup, rng = lanes(ax, d, pad=0.55)
    seg = np.array([r["lv"].get(k, np.nan) for k in range(x0, x1 + 1)])
    ax.step(xs, seg, where="post", color=BLUE, lw=2.2, zorder=8)
    peg(ax, i - x0, l[i], ldn, DN, "^", "oversold bar (RSI under 30)", side=-1)
    peg(ax, e - x0, o[e], ldn - 0.14 * rng, AMBER, "^", "BUY next open", side=1, size=260)
    peg(ax, pb - x0, h[pb], lup, UP, "v", "the bounce: sell a third, the rest rides free", side=1 if pb - x0 < len(d) * 0.5 else -1)
    peg(ax, xb - x0, l[xb], ldn, DN, "^", "a close under the line: SELL the rest", side=0, dy=-13)
    ax.text(len(d) + 1, seg[xb - x0], "the line = last higher low", color=BLUE, fontsize=9, va="center", ha="left", zorder=20)
    ax.set_xlim(-16, len(d) + 34)
    # rsi panel
    rs = r["rsi"][x0:x1 + 1]
    axr.plot(xs, rs, color=GREY, lw=1.2); axr.axhline(30, color=DN, lw=.9, ls="--"); axr.axhline(70, color=FAINT, lw=.6, ls=":")
    axr.fill_between(xs, rs, 30, where=rs <= 30, color=DN, alpha=.35)
    axr.set_ylim(0, 100); axr.set_yticks([30, 70]); axr.set_xlim(-16, len(d) + 34)
    axr.text(len(d) + 1, 30, "RSI 30", color=DN, fontsize=8.5, va="center", ha="left")
    step = max(len(d) // 7, 1)
    axr.set_xticks(xs[::step]); axr.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=7.5)
    ax.set_title("Backburner: a running name goes oversold      %s %s, daily chart in an uptrend, %+.1f%%" % (sym, "1h", 100 * r["ret"]), color=FG, fontsize=12, loc="left", pad=8)
    note(fig, [(DIM, "The name is in an uptrend on the bigger chart. RSI dips to 30 or under on this one: buy the next open. Sell a third at the bounce so the rest cannot lose. Hold the rest until a bar closes under the last higher low.")])
    return save(fig, ax, d, "backburner.png", panels=[(axr, d)]), dict(sym=sym, tf="1h", t=str(df.index[e]), ret=r["ret"])


# ------------------------------------------------------------------ 4. the range
def find_range(candidates, tf="1d"):
    best = None
    for sym, kind in candidates:
        fr = S.frames_for(sym, kind)
        df = fr.get(tf)
        if df is None or len(df) < 400:
            continue
        c = df["Close"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        floor, ceil, rid, rlist, atr = EB.get_ranges(df, "rectangle")
        n = len(c)
        for r_, (born, dead, how) in enumerate(rlist):
            if how == "still open" or dead + 25 >= n or dead - born < 35:
                continue
            i = dead - 1
            f0, c0 = float(floor[i]), float(ceil[i]); a = atr[i]
            if not (np.isfinite(a) and a > 0) or (c0 - f0) / a < 2:
                continue
            up = c[dead] > c0
            if not up:
                continue
            follow = (np.max(h[dead + 1:dead + 15]) - c0) / a
            tf_ = int(np.sum(l[born:i + 1] <= f0 + 0.25 * a)); tc = int(np.sum(h[born:i + 1] >= c0 - 0.25 * a))
            mid = (born + dead) // 2
            spread = np.any(h[mid:i + 1] >= c0 - 0.25 * a) and np.any(l[mid:i + 1] <= f0 + 0.25 * a) and np.any(h[born:mid] >= c0 - 0.25 * a) and np.any(l[born:mid] <= f0 + 0.25 * a)
            tall = (np.max(h[dead + 1:dead + 15]) - c0) / (c0 - f0)      # keep the box readable: the run after must not dwarf it
            if 4 <= follow <= 9 and tf_ >= 3 and tc >= 3 and spread and tall <= 2.5 and np.min(c[dead + 1:dead + 15]) > c0 - 0.5 * (c0 - f0):
                score = -abs(follow - 6) + (dead - born) / 20
                if best is None or score > best[0]:
                    best = (score, sym, kind, df, dict(born=born, dead=dead, f0=f0, c0=c0, a=a, tf=tf_, tc=tc, follow=follow))
    return best


def idea_range(pick):
    _, sym, kind, df, r = pick
    born, dead, f0, c0, a = r["born"], r["dead"], r["f0"], r["c0"], r["a"]
    o = df["Open"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float); c = df["Close"].values.astype(float)
    x0 = max(0, born - 10); x1 = min(len(df) - 1, dead + 14)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    fig, ax = fig_ax()
    candles(ax, d)
    ldn, lup, rng = lanes(ax, d, pad=0.5)
    mask = np.array([born <= k <= dead - 1 for k in range(x0, x1 + 1)])
    fl = np.where(mask, f0, np.nan); cl = np.where(mask, c0, np.nan)
    ax.step(xs, fl, where="post", color=BLUE, lw=2.2, zorder=8); ax.step(xs, cl, where="post", color=BLUE, lw=2.2, zorder=8)
    ax.fill_between(xs, fl, cl, step="post", color=BLUE, alpha=0.10, zorder=1)
    for k in range(born, dead):
        if l[k] <= f0 + 0.25 * a:
            ax.scatter([k - x0], [ldn], marker="^", s=60, color=BLUE, edgecolor="#ffffff", lw=.5, zorder=12)
        if h[k] >= c0 - 0.25 * a:
            ax.scatter([k - x0], [lup], marker="v", s=60, color=BLUE, edgecolor="#ffffff", lw=.5, zorder=12)
    mid = (born + dead) // 2
    ax.annotate("every touch of the floor", (mid - x0, ldn), xytext=(0, -13), textcoords="offset points", ha="center", va="top", color=BLUE, fontsize=FS, weight="bold", zorder=20)
    ax.annotate("every touch of the ceiling", (mid - x0, lup), xytext=(0, 13), textcoords="offset points", ha="center", va="bottom", color=BLUE, fontsize=FS, weight="bold", zorder=20)
    peg(ax, dead - x0, h[dead], lup + 0.14 * rng, AMBER, "v", "the BREAK: a close above the ceiling", side=-1, size=240)
    peg(ax, dead + 1 - x0, o[dead + 1], ldn - 0.14 * rng, AMBER, "^", "BUY the open after", side=-1, size=240)
    ax.text(len(d), f0, "floor", color=BLUE, fontsize=9, va="top", ha="left"); ax.text(len(d), c0, "ceiling", color=BLUE, fontsize=9, va="bottom", ha="left")
    ax.set_xlim(-1, len(d) + 10)
    ax.set_title("Channel: a flat-sided box, then the break      %s daily, %d bars in the box, ran %.0f normal bars after" % (sym, dead - born, r["follow"]),
                 color=FG, fontsize=12, loc="left", pad=8)
    note(fig, [(DIM, "Over 30 bars the highs and lows stay inside a box at most 4 normal bars tall, both edges touched twice or more; it lives until a bar CLOSES past an edge."),
               (DIM, "The trade is to be positioned for that break: buy the floor (or short the ceiling) and hold for it, or buy the break itself. Three reads call the direction right about 4 times in 5.")])
    return save(fig, ax, d, "channel.png"), dict(sym=sym, tf="1d", t=str(df.index[dead]))


# ------------------------------------------------------------------ 5. trend steps and a fakeout
def find_steps(candidates, tf="1d"):
    best, fake = None, None
    for sym, kind in candidates:
        fr = S.frames_for(sym, kind)
        df = fr.get(tf)
        if df is None or len(df) < 400:
            continue
        piv = ST.pivots(df)
        for kind_, s0, s1 in ST.spans(df, causal=True):
            if kind_ != "UP" or s1 >= len(df) - 5:
                continue
            inside = [(ci, j, p, k_, lab) for ci, j, p, k_, lab in piv if s0 < ci <= s1 and lab in ("HL", "HH", "EL")]
            steps = len(inside)
            if 4 <= steps <= 7 and 25 <= s1 - s0 <= 90 and (best is None or steps > best[0]):
                best = (steps, sym, kind, df, s0, s1, inside)
            if steps == 0 and 4 <= s1 - s0 <= 15 and fake is None and sym == (best[1] if best else sym):
                fake = (sym, kind, df, s0, s1)
    return best, fake


def idea_steps(pick, fake):
    steps, sym, kind, df, s0, s1, inside = pick
    o = df["Open"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    x0 = max(0, s0 - 14); x1 = min(len(df) - 1, s1 + 8)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    fig = plt.figure(figsize=(11.5, 5.6), dpi=100); fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1], wspace=0.12, top=0.86, bottom=0.22)
    ax = fig.add_subplot(gs[0]); ax.set_facecolor(DARK)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.tick_params(colors=DIM, labelsize=7.5); ax.grid(color="#1b1f26", lw=.4)
    candles(ax, d)
    ldn, lup, rng = lanes(ax, d, pad=0.5)
    ax.set_xlim(-1, len(d) + 6)
    ax.axvspan(s0 - x0 - .5, s1 - x0 + .5, color=UP, alpha=0.08, zorder=0)
    # the two pivots that opened it: the last HL and HH confirmed at or before s0
    openers = [(ci, j, p, k_, lab) for ci, j, p, k_, lab in ST.pivots(df) if ci <= s0 and lab in ("HL", "HH")][-2:]
    for ci, j, p, k_, lab in openers:
        peg(ax, j - x0, p, ldn if k_ == "low" else lup, GREY, "^" if k_ == "low" else "v",
            "higher low" if k_ == "low" else "higher high", side=-1, size=120)
    last = {"low": (-99, 0), "high": (-99, 0)}
    for m, (ci, j, p, k_, lab) in enumerate(inside, 1):
        lx, lrow = last[k_]
        row = (lrow + 1) % 2 if j - lx <= 6 else 0            # two steps close together: stagger the words
        last[k_] = (j, row)
        dy = (-13 - 14 * row) if k_ == "low" else (13 + 14 * row)
        peg(ax, j - x0, p, ldn if k_ == "low" else lup, UP, "^" if k_ == "low" else "v", "step %d" % m, size=150, dy=dy)
    ax.scatter([s1 - x0], [l[s1]], marker="x", s=120, color=DN, lw=2, zorder=14)
    ax.plot([s1 - x0, s1 - x0], [l[s1], ldn], color=DN, lw=.8, ls=":", alpha=.7, zorder=6)
    ax.annotate("x  the trend ends", (s1 - x0, ldn), xytext=(10, -13), textcoords="offset points", color=DN, fontsize=FS, weight="bold", ha="left", va="top", zorder=20)
    ax.set_xlim(-1, len(d) + 14)
    fig.text(0.07, 0.93, "Trend study: how many steps a trend takes before it ends      %s daily, %d steps" % (sym, steps), color=FG, fontsize=12, ha="left", va="bottom")
    panels = []
    if fake is not None:
        fsym, fkind, fdf, f0, f1 = fake
        axf = fig.add_subplot(gs[1]); axf.set_facecolor(DARK)
        for s in axf.spines.values():
            s.set_color("#252a33")
        axf.tick_params(colors=DIM, labelsize=7.5); axf.grid(color="#1b1f26", lw=.4)
        fx0 = max(0, f0 - 12); fx1 = min(len(fdf) - 1, f1 + 8)
        fd = fdf.iloc[fx0:fx1 + 1]
        candles(axf, fd, nticks=3)
        fldn, flup, frng = lanes(axf, fd, pad=0.5)
        axf.axvspan(f0 - fx0 - .5, f1 - fx0 + .5, color=UP, alpha=0.08, zorder=0)
        fl_ = fdf["Low"].values.astype(float)
        axf.scatter([f1 - fx0], [fl_[f1]], marker="x", s=120, color=DN, lw=2, zorder=14)
        axf.annotate("ended with no step:\na FAKEOUT", (f1 - fx0, fldn), xytext=(0, -6), textcoords="offset points", ha="center", va="top", color=DN, fontsize=FS, weight="bold", zorder=20)
        axf.plot([f1 - fx0, f1 - fx0], [fl_[f1], fldn], color=DN, lw=.8, ls=":", alpha=.7)
        axf.set_title("%s daily: started, then quit" % fsym, color=DIM, fontsize=9.5, loc="left", pad=3)
        panels.append((axf, fd))
    note(fig, [(DIM, "A trend starts on a higher low plus a higher high (grey). Every new higher low or higher high after that is a step (green). It ends on a wick under the last higher low, or a lower high / lower low."),
               (DIM, "The trend study ranks every name by steps per trend, how far it ran, and how often it started and quit (fakeouts).")])
    return save(fig, ax, d, "trend_steps.png", panels=panels), dict(sym=sym, tf="1d", t=str(df.index[s0]))


# ------------------------------------------------------------------ 6. the EQ (the coil)
def find_coil(candidates):
    """A clear EQ: several higher lows into several lower highs, well separated, that broke and ran."""
    import eq_coil as EC
    best = None
    for sym, kind in candidates:
        for tf in ("1d", "4h"):
            try:
                df = S.frames_for(sym, kind).get(tf)
            except Exception:
                continue
            if df is None or len(df) < 400:
                continue
            _, _, _, rs, atr = EC.coils(df)
            c = df["Close"].values.astype(float)
            for r in rs:
                if not r["tradeable"] or not r["how"].startswith("a wick"):
                    continue
                if r["end"] + 25 >= len(df) or r["born"] < 40 or r["pairs"] < 3:
                    continue
                a = atr[r["end"]]
                if not np.isfinite(a) or a <= 0:
                    continue
                run = abs(c[min(len(c) - 1, r["end"] + 15)] - c[r["end"]]) / a
                score = r["pairs"] * 6 + min(run, 8) + r["live_bars"]
                if best is None or score > best[0]:
                    best = (score, sym, kind, df, r, tf)
    return best


def idea_coil(pick):
    import eq_coil as EC
    _, sym, kind, df, r, tf = pick
    born, end, confirm = r["born"], r["end"], r["confirm"]
    o = df["Open"].values.astype(float); h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float); c = df["Close"].values.astype(float)
    piv = [(ci, j, p, k_, lab) for ci, j, p, k_, lab in ST.pivots(df) if born <= j <= end]
    coil = [x for x in piv if (x[3] == "low" and x[4] in EC.UP_LAB) or (x[3] == "high" and x[4] in EC.DN_LAB)]
    x0 = max(0, born - 10); x1 = min(len(df) - 1, end + 18)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    fig, ax = fig_ax(11.5, 5.8)
    candles(ax, d)
    ldn, lup, rng = lanes(ax, d, pad=0.52)
    ax.set_xlim(-1, len(d) + 12)

    def steps(pts):
        y = np.full(len(d), np.nan)
        for m, (j, pr) in enumerate(pts):
            j2 = pts[m + 1][0] if m + 1 < len(pts) else end
            a_ = max(j, x0); b_ = min(j2, end, x1)
            if b_ >= a_:
                y[a_ - x0:b_ - x0 + 1] = pr
        return y
    lo_p = [(x[1], float(x[2])) for x in coil if x[3] == "low"]
    hi_p = [(x[1], float(x[2])) for x in coil if x[3] == "high"]
    fl = steps(lo_p); cl = steps(hi_p)
    ax.step(xs, fl, where="post", color=BLUE, lw=2.4, zorder=8)
    ax.step(xs, cl, where="post", color=BLUE, lw=2.4, zorder=8)
    m_ = np.isfinite(fl) & np.isfinite(cl)
    ax.fill_between(xs, np.where(m_, fl, np.nan), np.where(m_, cl, np.nan), step="post", color=BLUE, alpha=0.11, zorder=1)
    last = {"low": (-99, 0), "high": (-99, 0)}
    nl = nh = 0
    near = max(3, len(d) // 7)
    for ci, j, p, k_, lab in coil:
        col = UP if k_ == "low" else DN
        lx, lrow = last[k_]
        row = (lrow + 1) % 2 if j - lx <= near else 0
        last[k_] = (j, row)
        dy = (-13 - 14 * row) if k_ == "low" else (13 + 14 * row)
        if k_ == "low":
            nl += 1; txt = "higher low" if nl == 1 else "%d" % nl
        else:
            nh += 1; txt = "lower high" if nh == 1 else "%d" % nh
        peg(ax, j - x0, p, ldn if k_ == "low" else lup, col, "^" if k_ == "low" else "v", txt, size=130, dy=dy)
    up_ = "ceiling" in r["how"]
    peg(ax, end - x0, h[end] if up_ else l[end], (lup + 0.16 * rng) if up_ else (ldn - 0.16 * rng),
        AMBER, "v" if up_ else "^", "the break", side=-1, size=230)
    ax.text(len(d), r["floor"], "floor", color=BLUE, fontsize=9, va="top", ha="left")
    ax.text(len(d), r["ceil"], "ceiling", color=BLUE, fontsize=9, va="bottom", ha="left")
    ax.set_title("EQ: higher lows into lower highs, tightening      %s %s, closed from %.1f to %.1f normal bars" % (
        sym, "daily" if tf == "1d" else tf, r["wide_at_start"] or 0, r["wide_at_end"] or 0),
        color=FG, fontsize=12, loc="left", pad=8)
    note(fig, [(DIM, "Every low higher than the last, every high lower than the last, at least two of each, and the gap closing. The floor is the last higher low and the ceiling the last lower high; each holds flat until the next one replaces it. It breaks when a wick goes through a line."),
               (DIM, "The shape is real and which way it breaks can be called about 6 times in 10. No version of the trade made money as coded: the lines close onto price, so the stop sits on top of the entry.")])
    return save(fig, ax, d, "eq.png"), dict(sym=sym, tf=tf, t=str(df.index[born]))


def main():
    os.makedirs(OUT, exist_ok=True)
    import focus
    cands = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_) and k_ in ("stock", "crypto")]
    meta = {}
    print("ideas:")
    ride = find_ride(cands)
    if ride:
        p1, m1 = idea_trend_ride(ride); meta["trend_ride"] = m1
        p2, m2 = idea_exits(ride); meta["exits"] = m2
    bb = find_backburner([(s_, k_) for s_, k_ in cands if k_ == "crypto"])
    if bb:
        p3, m3 = idea_backburner(bb); meta["backburner"] = m3
    rg = find_range(cands)
    if rg:
        p4, m4 = idea_range(rg); meta["channel"] = m4
    st, fk = find_steps(cands)
    if st:
        p5, m5 = idea_steps(st, fk); meta["trend_steps"] = m5
    co = find_coil(cands)
    if co:
        p6, m6 = idea_coil(co); meta["eq"] = m6
    meta["generated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    json.dump(meta, open(os.path.join(OUT, "ideas.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
