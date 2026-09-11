"""pics_eq.py -- random EQ trades drawn, so the EQ rule and the
textbook trade can be checked by eye (CLAUDE.md rule 10).

    pythonw pics_eq.py --log logs/pics_eq.log            # 3 per chart size, from validation/eq_events.csv.gz
    python  pics_eq.py --sym NVDA --kind stock --tf 4h --t "2025-03-04 12:00:00" --out x.png

The main chart: candles, the 12 EMA, labelled pivots, the EQ's floor and
ceiling as stepped lines while it lived, the touch that triggered the buy, the
buy and the sale in lanes above and below price (nothing on the candles), and
the chart runs on 40 bars past the sale. The two charts up sit beside it with
the trade marked. Every picture is measured with pics_ride.overlaps().
"""
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
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import structure as ST            # noqa: E402
import eq_study as EQ             # noqa: E402
import eq_break as EB             # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
OUT = os.path.join("validation", "eq_cases")
HIGHER = {"5m": ("15m", "1h"), "15m": ("1h", "4h"), "1h": ("4h", "1d"), "4h": ("1d", "1w"), "1d": ("1w",), "1w": ()}
PER_TF = 3
MODE = "rectangle"       # the reading the live scan uses: the sideways box, 30-bar window, dead on a close beyond an edge


def render(sym, kind, tf, t, frames, path, tag="picked at random. Not chosen for how it turned out."):
    df = frames[tf]
    e = int(df.index.get_indexer([pd.Timestamp(t)])[0])
    if e < 3:
        return None
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, rid, rlist, atr = EB.get_ranges(df, MODE)
    i = e - 1                                   # the touch bar
    if rid[i] < 0:
        return None
    r_ = rid[i]; born = rlist[r_][0]
    f0, c0 = float(floor[i]), float(ceil[i])
    cap = EQ.CAP_DAYS * S.BARS_DAY[tf]
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    res = EB.hold_for_break(+1, c, o, h, l, atr, floor, ceil, rid, r_, e, f0, c0, n, cap, day)
    if res is None:
        return None
    xb, xpx, why, worst = res
    fill = o[e]
    cost = S.CLASS_COST.get(kind, S.COST)
    ret = xpx / fill - 1 - cost
    x0 = max(0, min(born, e) - 25); x1 = min(n - 1, xb + 40)
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    highs_tfs = [t_ for t_ in HIGHER.get(tf, ()) if frames.get(t_) is not None and len(frames[t_]) >= 40]
    if highs_tfs:
        fig = plt.figure(figsize=(18, 9.5), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(2, 2, width_ratios=[1.5, 1], height_ratios=[1, 1], hspace=0.24, wspace=0.16, top=0.93, bottom=0.10)
        ax = fig.add_subplot(gs[:, 0])
    else:
        fig = plt.figure(figsize=(15, 8.5), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 1, top=0.93, bottom=0.10)
        ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0) for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    # the EQ while it lived: floor and ceiling as stepped lines
    # the box spans the whole sideways stretch (from the window's first bar to the break), not just
    # the bars after it was declared
    alive_idx = np.where(rid == r_)[0]
    dead = int(alive_idx.max()) if len(alive_idx) else i
    span_mask = np.zeros(n, bool); span_mask[born:dead + 1] = True
    fl = np.where(span_mask[x0:x1 + 1], f0, np.nan)
    cl = np.where(span_mask[x0:x1 + 1], c0, np.nan)
    ax.step(xs, fl, where="post", color="#5aa9ff", lw=1.8, zorder=8)
    ax.step(xs, cl, where="post", color="#5aa9ff", lw=1.8, zorder=8)
    ax.fill_between(xs, fl, cl, step="post", color="#5aa9ff", alpha=0.08, zorder=1)
    # lanes
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.40 * rng, hi + 0.40 * rng)
    ax.set_xlim(-1, len(d) + 40)
    lane_dn = lo - 0.20 * rng; lane_up = hi + 0.22 * rng
    col = "#3ddc97" if ret > 0.005 else "#ff5c72" if ret < -0.005 else "#8b93a1"

    def peg(x, y_bar, y_lane, colr, marker, size, label, dy, side=0):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=.7, ls=":", alpha=.55, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=size, color=colr, edgecolor="#ffffff", lw=.8, zorder=13)
        ha = "center" if side == 0 else ("right" if side < 0 else "left")
        ax.annotate(label, (x, y_lane), xytext=(9 * side, dy), textcoords="offset points", ha=ha,
                    va="bottom" if dy > 0 else "top", color=colr, fontsize=8.5, weight="bold", zorder=20)

    peg(i - x0, l[i], lane_dn, "#5aa9ff", "^", 130, "touched the floor", -10, side=-1)
    peg(e - x0, l[e], lane_dn, "#ffb84d", "^", 190, "buy", -10, side=1)
    peg(xb - x0, h[xb], lane_up, col, "v", 190, "sold %+.1f%%" % (100 * ret), 10)
    xr = len(d) + 1
    ax.text(xr, f0, "floor", color="#5aa9ff", fontsize=8, va="top", ha="left", zorder=20)
    ax.text(xr, c0, "ceiling", color="#5aa9ff", fontsize=8, va="bottom", ha="left", zorder=20)
    ax.axhline(fill, color="#ffb84d", lw=.8, ls="--", alpha=.6, zorder=5)       # the buy price (named in the key below)
    step = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    born_t = df.index[born].strftime("%m-%d %H:%M")
    ax.set_title("%s  %s      %s %+.1f%%      box %.1f normal bars tall, %s" % (
        sym, tf, "WORKED" if ret > 0.005 else "flat" if abs(ret) <= 0.005 else "LOST", 100 * ret,
        (c0 - f0) / atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else 0, why),
        color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    key = [[("#5aa9ff", "▲ the touch of the floor"), ("#ffb84d", "▲ the buy, next open (the dashed orange line is the buy price)"), (col, "▼ the sale")],
           [("#5aa9ff", "— blue box: the EQ while it lived (30-bar sideways box; a close beyond an edge ends it). Bought the floor, held for the break: out if it broke down, trailed 5 bars under the high once it broke up")],
           [("#8b93a1", "HH HL LH LL: the swing highs and lows. Green background: uptrend. Red: downtrend.   %s" % tag)]]
    for r_i, items in enumerate(key):
        xpos = 0.055
        for c_, txt in items:
            fig.text(xpos, 0.058 - 0.024 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0056 * len(txt) + 0.02
    panel_bars = []
    t_start = df.index[e]; t_exit = df.index[min(xb + 1, n - 1)]
    for row, htf in enumerate(highs_tfs):
        axh = fig.add_subplot(gs[row, 1])
        hdf = frames[htf]
        pos = max(0, int(hdf.index.searchsorted(t_start)) - 90); win = min(len(hdf) - pos, 130)
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos) for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panel_bars.append((axh, hb["d"]))
        sub = hdf.index[pos:pos + win]
        a = min(max(int(sub.searchsorted(t_start)), 0), win - 1); b = min(max(int(sub.searchsorted(t_exit)), 0), win - 1)
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.42 * yr, yhi + 0.42 * yr)
        axh.axvline(a, color="#ffb84d", lw=1.0, alpha=.85, zorder=9); axh.axvline(b, color=col, lw=1.0, ls="--", alpha=.85, zorder=9)
        axh.scatter([a], [ylo - 0.25 * yr], marker="^", s=150, color="#ffb84d", edgecolor="#ffffff", lw=.8, zorder=14)
        axh.annotate("buy", (a, ylo - 0.25 * yr), xytext=(0, -10), textcoords="offset points", ha="center", va="top", color="#ffb84d", fontsize=8, weight="bold", zorder=15)
        axh.scatter([b], [yhi + 0.24 * yr], marker="v", s=150, color=col, edgecolor="#ffffff", lw=.8, zorder=14)
        axh.annotate("sold", (b, yhi + 0.24 * yr), xytext=(0, 10), textcoords="offset points", ha="center", va="bottom", color=col, fontsize=8, weight="bold", zorder=15)
        axh.set_title("%s  — buy and sale marked" % htf, loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panel_bars)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    after = min(n - 1, xb + 40)
    story = ("An EQ was alive: floor at %s, ceiling at %s, %.1f normal bars tall, born %s. Price touched the floor, so the buy went in at the next open, %s, to be positioned for the break. "
             % (fmt(f0), fmt(c0), (c0 - f0) / atr[i], born_t, fmt(fill)))
    story += ("After %d bars: %s. Sold at %s for %+.1f%%. " % (xb + 1 - e, why, fmt(xpx), 100 * ret))
    story += "40 bars later the price was %+.1f%% from the buy." % (100 * (c[after] / fill - 1))
    return dict(sym=sym, kind=kind, tf=tf, t=str(t), ret=float(ret), held=int(xb + 1 - e), why=why, story=story,
                after_ret=float(c[after] / fill - 1), problems=probs)


def fmt(x):
    return ("%.4g" % x) if x < 10 else ("%.2f" % x) if x < 1000 else ("%.0f" % x)


def _draw(args):
    n, sym, kind, tf, t, out = args
    try:
        frames = S.frames_for(sym, kind)
        row = render(sym, kind, tf, t, frames, os.path.join(out, "eq_case_%02d.png" % n))
    except Exception as ex:
        return None, "%s %s %s: %s" % (sym, tf, t, ex)
    if row:
        row.update(n=n, group="%s charts" % tf)
    return row, None


def main():
    import concurrent.futures as cf
    import multiprocessing as mp
    log = None; out = OUT; per_tf = PER_TF; seed = 20260908
    a = sys.argv
    for i_, x in enumerate(a):
        if x == "--log" and i_ + 1 < len(a):
            log = a[i_ + 1]; sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
        if x == "--out" and i_ + 1 < len(a):
            out = a[i_ + 1]
        if x == "--per-tf" and i_ + 1 < len(a):
            per_tf = int(a[i_ + 1])
        if x == "--seed" and i_ + 1 < len(a):
            seed = int(a[i_ + 1])
    if "--sym" in a:
        sym = a[a.index("--sym") + 1]; kind = a[a.index("--kind") + 1]; tf = a[a.index("--tf") + 1]; t = a[a.index("--t") + 1]
        r = render(sym, kind, tf, t, S.frames_for(sym, kind), a[a.index("--out") + 1] if "--out" in a else "eq_test.png")
        print(r); return
    os.makedirs(out, exist_ok=True)
    ev = pd.read_csv(os.path.join("validation", "eq_break_events.csv.gz"))
    ev = ev[ev["mode"] == MODE]
    liq = {}
    try:
        k = pd.read_csv("cache/tier1.csv")
        liq = {s_: i_ for i_, s_ in enumerate(k.sort_values("dollar", ascending=False).symbol.astype(str))}
    except Exception:
        pass
    ev = ev[(~ev.kind.isin(["stock", "etf"])) | (ev.sym.map(liq).fillna(9999) < 300)]
    rng = np.random.default_rng(seed)
    picks = []
    for tf in ["5m", "15m", "1h", "4h", "1d", "1w"]:
        g = ev[ev.tf == tf]
        if len(g) == 0:
            continue
        idx = rng.choice(len(g), min(per_tf, len(g)), replace=False)
        picks += [g.iloc[int(j)] for j in idx]
    for f in os.listdir(out):
        if f.startswith("eq_case_") and f.endswith(".png"):
            os.remove(os.path.join(out, f))
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)
    t0 = time.time(); index = []
    jobs = [(n, r.sym, r.kind, r.tf, r.t, out) for n, r in enumerate(picks, 1)]
    with cf.ProcessPoolExecutor(max_workers=max(1, os.cpu_count() or 4)) as ex:
        for row, err in ex.map(_draw, jobs):
            if err:
                print("  " + err, flush=True); continue
            if row:
                index.append(row)
                print("  eq_case_%02d %-7s %-3s %s  %+.1f%%  %s" % (row["n"], row["sym"], row["tf"], row["t"], 100 * row["ret"],
                      ("PROBLEMS: " + "; ".join(row["problems"])) if row["problems"] else "clean"), flush=True)
    index.sort(key=lambda r: r["n"])
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), items=index), open(os.path.join(out, "eq_cases_index.json"), "w"), indent=1)
    print("  %d charts, %d clean  (%.0fs)" % (len(index), sum(1 for r in index if not r["problems"]), time.time() - t0))


if __name__ == "__main__":
    main()


def render_live(sym, kind, tf, frames, path):
    """The EQ as it stands NOW on one chart: the sideways box from its first bar to the last
    closed bar, every touch marked, where price sits, and the next chart up beside it. Used by
    /api/eq_chart on the live page. Returns a dict with the story and the measured problems, or None."""
    from eq_break import reads, pivot_lists
    import exit_managers as XM
    df = frames.get(tf)
    if df is None or len(df) < 60:
        return dict(story="Could not fetch this chart's bars just now (the free feed limits how often we may ask). Try again in a minute.", problems=[], png=False)
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, rid, rlist, atr = EB.get_ranges(df, MODE)
    last = n - 2 if n >= 2 else n - 1                      # the last CLOSED bar
    if rid[last] < 0 or not np.isfinite(floor[last]) or not np.isfinite(ceil[last]):
        return dict(story="No EQ is alive on this chart right now (it may have broken since the scan).", problems=[], png=False)
    r_ = rid[last]; born = rlist[r_][0]
    f0, c0 = float(floor[last]), float(ceil[last])
    a = atr[last] if np.isfinite(atr[last]) and atr[last] > 0 else np.nan
    touches_f = [k for k in range(born, last + 1) if l[k] <= f0 + 0.25 * a]
    touches_c = [k for k in range(born, last + 1) if h[k] >= c0 - 0.25 * a]
    x0 = max(0, born - 30); x1 = n - 1
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    hi_tf = HIGHER.get(tf, ())[:1]
    hdf = frames.get(hi_tf[0]) if hi_tf else None
    if hdf is not None and len(hdf) >= 40:
        fig = plt.figure(figsize=(18, 8.5), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1], wspace=0.14, top=0.92, bottom=0.12)
        ax = fig.add_subplot(gs[0, 0])
    else:
        fig = plt.figure(figsize=(15, 8), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 1, top=0.92, bottom=0.12)
        ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0) for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    span_mask = np.zeros(n, bool); span_mask[born:last + 1] = True
    fl = np.where(span_mask[x0:x1 + 1], f0, np.nan); cl = np.where(span_mask[x0:x1 + 1], c0, np.nan)
    ax.step(xs, fl, where="post", color="#5aa9ff", lw=1.8, zorder=8)
    ax.step(xs, cl, where="post", color="#5aa9ff", lw=1.8, zorder=8)
    ax.fill_between(xs, fl, cl, step="post", color="#5aa9ff", alpha=0.08, zorder=1)
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.36 * rng, hi + 0.36 * rng)
    ax.set_xlim(-1, len(d) + 34)
    lane_dn = lo - 0.18 * rng; lane_up = hi + 0.18 * rng
    for k in touches_f:
        ax.plot([k - x0, k - x0], [l[k], lane_dn], color="#5aa9ff", lw=.6, ls=":", alpha=.5, zorder=6)
        ax.scatter([k - x0], [lane_dn], marker="^", s=70, color="#5aa9ff", edgecolor="#ffffff", lw=.6, zorder=13)
    for k in touches_c:
        ax.plot([k - x0, k - x0], [h[k], lane_up], color="#5aa9ff", lw=.6, ls=":", alpha=.5, zorder=6)
        ax.scatter([k - x0], [lane_up], marker="v", s=70, color="#5aa9ff", edgecolor="#ffffff", lw=.6, zorder=13)
    xr = len(d) + 1
    ax.text(xr, f0, "floor %s" % fmt(f0), color="#5aa9ff", fontsize=8, va="top", ha="left", zorder=20)
    ax.text(xr, c0, "ceiling %s" % fmt(c0), color="#5aa9ff", fontsize=8, va="bottom", ha="left", zorder=20)
    price = float(c[-1])
    ax.scatter([len(d) - 1], [price], marker="o", s=60, color="#ffb84d", edgecolor="#ffffff", lw=.8, zorder=14)
    if abs(price - f0) > 0.15 * (c0 - f0) and abs(price - c0) > 0.15 * (c0 - f0):
        ax.text(xr, price, "now %s" % fmt(price), color="#ffb84d", fontsize=8, va="center", ha="left", zorder=20)
    step = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    where = (price - f0) / (c0 - f0) if c0 > f0 else 0.5
    zone = "at the floor" if where <= 0.2 else "at the ceiling" if where >= 0.8 else "in the middle"
    call = ""
    try:
        pl, ph = pivot_lists(ST.pivots(df))
        hi_state = str(ST.states(hdf, causal=True)[-1]) if hdf is not None else "NA"
        rd = reads(last, born, df, c, h, l, atr, floor, ceil, ST.states(df, causal=True), np.array([hi_state] * n, dtype=object), XM.rsi(c), XM.ema(c, 50), pl, ph)
        call = rd.get("read_call", "")
    except Exception:
        pass
    ax.set_title("%s  %s      EQ alive %d bars, %.1f normal bars tall, price %s      call: %s" % (
        sym, tf, last - born + 1, (c0 - f0) / a if np.isfinite(a) else 0, zone, call or "no clear call"), color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    key = [[("#5aa9ff", "blue box: the EQ, from the first bar of its 30-bar window to the last closed bar. It dies when a bar CLOSES beyond an edge; wicks through do not count.")],
           [("#5aa9ff", "^ v  every touch of the floor / ceiling (within a quarter of a normal bar)"), ("#ffb84d", "o  the newest price (the forming bar)")],
           [("#8b93a1", "HH HL LH LL: the swing highs and lows. Green background: uptrend. Red: downtrend.")]]
    for r_i, items in enumerate(key):
        xpos = 0.055
        for c_, txt in items:
            fig.text(xpos, 0.058 - 0.024 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0056 * len(txt) + 0.02
    panel_bars = []
    if hdf is not None and len(hdf) >= 40:
        axh = fig.add_subplot(gs[0, 1])
        pos = max(0, len(hdf) - 120); win = len(hdf) - pos
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos) for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panel_bars.append((axh, hb["d"]))
        t_born = df.index[born]
        sub = hdf.index[pos:pos + win]
        a_ = min(max(int(sub.searchsorted(t_born)), 0), win - 1)
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.3 * yr, yhi + 0.3 * yr)
        axh.axvspan(a_, win - 1, color="#5aa9ff", alpha=0.08, zorder=1)
        axh.axhline(f0, color="#5aa9ff", lw=.9, ls="--", alpha=.7, zorder=5); axh.axhline(c0, color="#5aa9ff", lw=.9, ls="--", alpha=.7, zorder=5)
        axh.set_title("%s, the next chart up  - shaded: while the EQ has been alive" % hi_tf[0], loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panel_bars)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    story = ("EQ alive for %d bars: floor %s, ceiling %s (%.1f normal bars tall). %d touches of the floor, %d of the ceiling. Price is %s%s." % (
        last - born + 1, fmt(f0), fmt(c0), (c0 - f0) / a if np.isfinite(a) else 0, len(touches_f), len(touches_c), zone, (", call: " + call) if call else ""))
    return dict(story=story, problems=probs, zone=zone, call=call, png=True)
