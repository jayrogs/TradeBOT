"""pics_eqfree.py -- his EQ trade drawn: direction from the bigger chart, buy the higher low
(or short the lower high), sell part at the far line so the rest is free.

    pythonw pics_eqfree.py --procs 20 --log logs/pics_eqfree.log
    --per-tf N   how many per chart size (default 4: two that reached the free ride, two that did not)

Only trades taken WITH the bigger picture: the daily chart over its rising 50 EMA for a long, under
its falling 50 EMA for a short (weekly for a daily EQ). That read matched his eye on 8 of 8 obvious
trends; every swing-shape read missed several. Picked at random inside each group. Every chart measured before saving.
Writes validation/eq_free/*.png + eq_free_index.json  ->  /eqfree
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import pandas as pd               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import structure as ST            # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import exit_managers as XM        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
UP, DN, BLUE, AMBER = "#3ddc97", "#ff5c72", "#5aa9ff", "#ffb84d"
OUT = os.path.join("validation", "eq_free")
TFS = FR.TFS
VARIANT = "free ride, rest keeps the stop"
WORD = {"UP": "uptrend", "DOWN": "downtrend", "FLAT": "no trend", "NA": "no data",
        "up": "higher highs and higher lows", "down": "lower highs and lower lows", "mixed": "mixed swings"}
FILTER = "h_ema_daily"
EMAWORD = {"down": "under its falling 50 EMA", "up": "over its rising 50 EMA", "mixed": "tangled around its 50 EMA", "NA": "no data"}


def fmt(x):
    return ("%.4g" % x) if abs(x) < 10 else ("%.2f" % x) if abs(x) < 1000 else ("%.0f" % x)


def render(sym, kind, tf, row, frames, path):
    df = frames[tf]
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    born, end, e, xb, pj = row["born"], row["end"], row["e"], row["xb"], row["pj"]
    took_bar = row["took_bar"]
    long_ = row["side"] == "long"
    fill, stop, target = row["fill"], row["stop"], row["target"]
    risk = abs(fill - stop); gain = abs(target - fill)
    share = risk / (risk + gain)
    ret = row["ret"]; won = ret > 0
    x0 = max(0, born - 12); x1 = min(n - 1, max(xb, end) + 20)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    htf = "1d" if tf in ("5m", "15m", "1h", "4h") else "1w"      # where the reason for the direction lives
    hdf = frames.get(htf)
    if hdf is not None and len(hdf) >= 60:
        fig = plt.figure(figsize=(17, 9.2), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.8, 1], wspace=0.13, top=0.92, bottom=0.17)
        ax = fig.add_subplot(gs[0, 0])
    else:
        fig = plt.figure(figsize=(14, 8.6), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 1, top=0.92, bottom=0.17)
        ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0) for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    # the EQ: flat steps through its higher lows and lower highs, while it lived
    coil = [x for x in ST.pivots(df) if born <= x[1] <= end and
            ((x[3] == "low" and x[4] in EC.UP_LAB) or (x[3] == "high" and x[4] in EC.DN_LAB))]

    def steps(pts):
        y = np.full(len(d), np.nan)
        for m, (j, pr) in enumerate(pts):
            j2 = pts[m + 1][0] if m + 1 < len(pts) else end
            a_ = max(j, x0); b_ = min(j2, end, x1)
            if b_ >= a_:
                y[a_ - x0:b_ - x0 + 1] = pr
        return y
    fl = steps([(x[1], float(x[2])) for x in coil if x[3] == "low"])
    cl = steps([(x[1], float(x[2])) for x in coil if x[3] == "high"])
    ax.step(xs, fl, where="post", color=BLUE, lw=2.0, zorder=8)
    ax.step(xs, cl, where="post", color=BLUE, lw=2.0, zorder=8)
    m_ = np.isfinite(fl) & np.isfinite(cl)
    ax.fill_between(xs, np.where(m_, fl, np.nan), np.where(m_, cl, np.nan), step="post", color=BLUE, alpha=0.09, zorder=1)
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.66 * rng, hi + 0.66 * rng)
    ax.set_xlim(-1, len(d) + 30)
    below = [lo - 0.17 * rng, lo - 0.34 * rng, lo - 0.51 * rng]
    above = [hi + 0.17 * rng, hi + 0.34 * rng, hi + 0.51 * rng]

    def lane(under, level):
        return below[level] if under else above[level]

    def peg(x, y_bar, y_lane, col, label, side=0):
        under = y_lane < y_bar
        ax.plot([x, x], [y_bar, y_lane], color=col, lw=.8, ls=":", alpha=.7, zorder=6)
        ax.scatter([x], [y_lane], marker="^" if under else "v", s=210, color=col, edgecolor="#ffffff", lw=.9, zorder=14)
        dy = -13 if under else 13
        an = ax.annotate(label, (x, y_lane), xytext=(10 * side, dy), textcoords="offset points",
                         ha="center" if side == 0 else ("right" if side < 0 else "left"),
                         va="top" if dy < 0 else "bottom", color=col, fontsize=10, weight="bold", zorder=20)
        # measure it against its own plot and flip it back inside if it would hang off either side
        rend = fig.canvas.get_renderer()
        box = ax.get_window_extent(rend)
        bb = an.get_window_extent(rend)
        if bb.x0 < box.x0 + 3:
            an.set_ha("left"); an.xyann = (10, dy)
        elif bb.x1 > box.x1 - 3:
            an.set_ha("right"); an.xyann = (-10, dy)
    sig_under = long_
    far = "lower high" if long_ else "higher low"
    near = "higher low" if long_ else "lower high"
    ax.axhline(stop, color=DN, lw=1.1, ls="--", alpha=.75, zorder=5)
    ax.axhline(fill, color=AMBER, lw=1.0, ls=":", alpha=.8, zorder=5)
    ax.axhline(target, color=UP, lw=1.1, ls="--", alpha=.75, zorder=5)
    pbar = l[pj] if long_ else h[pj]
    # a label near the left edge points right, one near the right edge points left, so no text
    # ever runs off the plot onto the price scale
    def inward(x, prefer):
        if x < 0.22 * len(d):
            return 1
        if x > 0.72 * len(d):
            return -1
        return prefer
    peg(pj - x0, pbar, lane(sig_under, 0), BLUE, "%s: the signal" % near, side=inward(pj - x0, -1))
    peg(e - x0, o[e], lane(sig_under, 1), AMBER, "BOUGHT" if long_ else "SHORTED", side=inward(e - x0, 1))
    if took_bar is not None:
        peg(took_bar - x0, h[took_bar] if long_ else l[took_bar], lane(not sig_under, 0), UP,
            "sold %.0f%% here: the rest is free" % (100 * share), side=inward(took_bar - x0, 1 if (took_bar - x0) < 0.6 * len(d) else -1))
    if won:
        peg(xb - x0, h[xb] if long_ else l[xb], lane(not sig_under, 1), UP, "OUT %+.1f%%" % (100 * ret),
            side=inward(xb - x0, 1 if (xb - x0) < 0.6 * len(d) else -1))
    else:
        peg(xb - x0, l[xb] if long_ else h[xb], lane(sig_under, 2), DN, "OUT %+.1f%%" % (100 * ret),
            side=inward(xb - x0, 1 if (xb - x0) < 0.6 * len(d) else -1))
    xr = len(d) + 1
    labs = sorted([(stop, DN, "stop %s" % fmt(stop)), (fill, AMBER, "%s %s" % ("bought" if long_ else "shorted", fmt(fill))),
                   (target, UP, "%s %s" % (far, fmt(target)))])
    gap = 0.05 * rng
    ys = [labs[0][0]]
    for m in range(1, len(labs)):
        ys.append(max(labs[m][0], ys[-1] + gap))
    for (y0, col, txt), y_ in zip(labs, ys):
        ax.text(xr, y_, txt, color=col, fontsize=8.5, va="center", ha="left", zorder=20)
    step_ = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    ax.set_yticks([y for y in ax.get_yticks() if y >= 0 and ax.get_ylim()[0] <= y <= ax.get_ylim()[1]])
    reason = "%s %s" % ("daily" if htf == "1d" else "weekly", "falling" if row["h_ema_daily_raw"] == "down" else "rising" if row["h_ema_daily_raw"] == "up" else "mixed")
    ax.set_title("%s  %s   %s, %s   %s %+.1f%% in %d bars   free ride %s" % (
        sym, tf, "LONG" if long_ else "SHORT", reason, "WON" if won else "LOST", 100 * ret, row["held"],
        "reached" if took_bar is not None else "not reached"), color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    key = [[(BLUE, "blue: the EQ, flat until the next higher low or lower high"),
            (AMBER, "dotted: the entry"), (DN, "red dashed: the stop, a wick through the signal pivot"),
            (UP, "green dashed: the far line, where part is sold")],
           [("#8b93a1", "Direction: the daily chart over its rising 50 EMA = long, under its falling 50 EMA = short (weekly for a daily EQ). Right panel: that chart, 50 EMA in purple.")],
           [("#8b93a1", "HH HL LH LL: swing highs and lows. Green background: uptrend. Red: downtrend. Picked at random among trades WITH the bigger picture, NOT for how they turned out.")]]
    for r_i, items in enumerate(key):
        xpos = 0.045
        for c_, txt in items:
            fig.text(xpos, 0.086 - 0.024 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0052 * len(txt) + 0.016
    panels = []
    if hdf is not None and len(hdf) >= 60:
        axh = fig.add_subplot(gs[0, 1])
        te = df.index[e]
        pos = max(0, int(hdf.index.searchsorted(te)) - 90)
        win = min(len(hdf) - pos, 110)
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos)
                       for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panels.append((axh, hb["d"]))
        sub = hdf.index[pos:pos + win]
        a_ = min(max(int(sub.searchsorted(te)) - 1, 0), win - 1)
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.3 * yr, yhi + 0.3 * yr)
        axh.axvline(a_, color=AMBER, lw=1.2, alpha=.9, zorder=9)
        e50 = XM.ema(hdf["Close"].values.astype(float), 50)[pos:pos + win]
        axh.plot(np.arange(len(e50)), e50, color="#b48cff", lw=1.7, zorder=7)
        axh.set_title("%s: %s" % ("daily" if htf == "1d" else "weekly", EMAWORD.get(row["h_ema_daily_raw"], row["h_ema_daily_raw"])),
                      loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    big = "daily" if tf in ("5m", "15m", "1h", "4h") else "weekly"
    story = ("The %s chart was %s, so this EQ was a %s. A %s confirmed, so the %s went in "
             "at the next open, %s. The stop sat a wick past that %s at %s, and the %s was %s, %.1f times the risk away. " % (
                 big, EMAWORD.get(row["h_ema_daily_raw"], "?"),
                 "buy" if long_ else "short", near, "buy" if long_ else "short", fmt(fill), near, fmt(stop), far,
                 fmt(target), gain / risk))
    if took_bar is not None:
        story += "Price reached the %s after %d bars, %.0f%% was sold there, and the rest could no longer lose. " % (
            far, took_bar - e + 1, 100 * share)
    else:
        story += "It never reached the %s. " % far
    story += "Out after %d bars: %s. %+.2f%%." % (row["held"], row["why"], 100 * ret)
    return dict(sym=sym, kind=kind, tf=tf, t=row["t"], side=row["side"], ret=float(ret), held=int(row["held"]),
                reached=took_bar is not None, why=row["why"], rr=float(gain / risk), share=float(share),
                h_next=row["h_ema_daily_raw"], h_two=row["h_ema200_raw"], story=story,
                png=os.path.basename(path), problems=probs)


def _one(args):
    sym, kind, seed = args
    try:
        fr = S.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    rng = np.random.default_rng(seed)
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * S.YEARS)
    got, errs = [], []
    for tf in TFS:
        try:
            rows = FR.trades_for_frame(sym, kind, tf, fr, start, detail=True)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex)); continue
        rows = [r for r in rows if r["variant"] == VARIANT and r[FILTER] == "with" and r["born"] > 40 and r["xb"] + 22 < len(fr[tf])]
        if not rows:
            continue
        for want in (True, False):                 # one that reached the free ride, one that did not
            pool = [r for r in rows if (r["took_bar"] is not None) == want]
            if not pool:
                continue
            r = pool[int(rng.integers(len(pool)))]
            os.makedirs(OUT, exist_ok=True)
            path = os.path.join(OUT, "%s_%s_%s_%s_%d.png" % (kind, sym, tf, r["side"], r["e"]))
            try:
                out = render(sym, kind, tf, r, fr, path)
            except Exception as ex:
                errs.append("%s %s %s draw: %s" % (kind, sym, tf, ex)); continue
            if out:
                got.append(out)
    return got, errs


def main():
    procs, per_tf = max(1, os.cpu_count() or 4), 4
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--per-tf" and i + 1 < len(sys.argv):
            per_tf = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    import focus
    names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    rng = np.random.default_rng(20260910)
    jobs = [(s_, k_, int(rng.integers(1 << 30))) for s_, k_ in names]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, jobs, chunksize=1):
            rows += got; errs += err
    keep = []
    for tf in TFS:
        g = [r for r in rows if r["tf"] == tf]
        yes = [r for r in g if r["reached"]]; no = [r for r in g if not r["reached"]]
        rng.shuffle(yes); rng.shuffle(no)
        half = per_tf // 2
        keep += yes[:half] + no[:per_tf - min(half, len(yes))]
    keep.sort(key=lambda r: (TFS.index(r["tf"]), not r["reached"], -r["ret"]))
    kept = {r["png"] for r in keep}
    for fn in os.listdir(OUT):
        if fn.endswith(".png") and fn not in kept:
            os.remove(os.path.join(OUT, fn))
    json.dump(keep, open(os.path.join(OUT, "eq_free_index.json"), "w"), indent=1)
    bad = [r for r in keep if r["problems"]]
    print("  %d trades drawn from %d candidates, %d with text problems  (%.0fs)" % (len(keep), len(rows), len(bad), time.time() - t0))
    for r in keep:
        print("    %-6s %-3s %-5s %+7.2f%%  %3d bars  free ride %-11s %4.1fx  %-5s/%-5s  %s" % (
            r["sym"], r["tf"], r["side"], 100 * r["ret"], r["held"], "reached" if r["reached"] else "not reached",
            r["rr"], r["h_next"], r["h_two"], "clean" if not r["problems"] else r["problems"]))
    for e in errs[:12]:
        print("  " + e)


if __name__ == "__main__":
    main()
