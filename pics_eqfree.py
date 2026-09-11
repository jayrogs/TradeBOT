"""pics_eqfree.py -- his EQ trade drawn: direction from the bigger chart, buy the higher low
(or short the lower high), sell part at the far line, rest to breakeven.

    pythonw pics_eqfree.py --procs 20 --log logs/eq_free.log
    --per-tf N     how many per chart size (default 4: two that reached the far line, two that did not)
    --variant V    exit variant from eq_freeride2.MODES (default: a third at the far line, rest to breakeven)
    --gap G        pivots at least G bars apart (default 3)
    --hours H      "regular" (default) or "all": which bars stocks and ETFs are drawn on
    --min-rr R     only trades whose far line is at least R times the risk away (default 1.0, eq_farline.py)

Redone after his grading (2026-09-10): a fixed partial instead of "sell 91%", no EQ whose pivots sit on top
of each other, stocks on regular-hours bars, the EQ that had already broken before it was declared is gone
(eq_coil.py), and the EQ is boxed on the daily panel so its place on the bigger chart is obvious.
Only trades taken WITH the bigger picture: the daily chart over its rising 50 EMA for a long, under its
falling 50 EMA for a short (weekly for a daily EQ). Picked at random inside each group. Every chart measured.
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
from matplotlib.patches import Rectangle  # noqa: E402
import pandas as pd               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import structure as ST            # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import exit_managers as XM        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
UP, DN, BLUE, AMBER = "#3ddc97", "#ff5c72", "#5aa9ff", "#ffb84d"
OUT = os.path.join("validation", "eq_free")
TFS = FR2.TFS
VARIANT = [m[0] for m in FR2.MODES if m[1] == "tcg"][0]   # round 3: half at the far line, the TCG rest
MIN_RR = 1.0                        # skip trades whose far line is closer than 1x the risk (eq_farline.py)
EMAWORD = {"down": "under its falling 50 EMA", "up": "over its rising 50 EMA", "mixed": "tangled around its 50 EMA", "NA": "no data"}
SOLD = {"third": "sold a third here, rest to breakeven", "half": "sold half here, rest to breakeven",
        "all": "sold everything here", "tcg": "sold half here, rest walked up under higher lows"}


def fmt(x):
    return ("%.4g" % x) if abs(x) < 10 else ("%.2f" % x) if abs(x) < 1000 else ("%.0f" % x)


def render(sym, kind, tf, row, df, hdf, path, hours, gap, min_rr=MIN_RR):
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    born, end, e, xb, pj = row["born"], row["end"], row["e"], row["xb"], row["pj"]
    took_bar = row["took_bar"]
    long_ = row["side"] == "long"
    fill, stop, target = row["fill"], row["stop"], row["target"]
    risk = abs(fill - stop); gain = abs(target - fill)
    share = row["share"]
    ret = row["ret"]; won = ret > 0
    x0 = max(0, born - 12); x1 = min(n - 1, max(xb, end) + 20)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    htf = "1d" if tf in ("5m", "15m", "1h", "4h") else "1w"      # where the reason for the direction lives
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
    ax.set_xlim(-1, len(d) + max(30, int(0.22 * len(d))))       # room for the price labels on long windows
    below = [lo - 0.17 * rng, lo - 0.34 * rng, lo - 0.51 * rng]
    above = [hi + 0.17 * rng, hi + 0.34 * rng, hi + 0.51 * rng]

    def lane(under, level):
        return below[level] if under else above[level]

    def peg(axis, x, y_bar, y_lane, col, label, side=0):
        under = y_lane < y_bar
        axis.plot([x, x], [y_bar, y_lane], color=col, lw=.8, ls=":", alpha=.7, zorder=6)
        axis.scatter([x], [y_lane], marker="^" if under else "v", s=210, color=col, edgecolor="#ffffff", lw=.9, zorder=14)
        dy = -13 if under else 13
        an = axis.annotate(label, (x, y_lane), xytext=(10 * side, dy), textcoords="offset points",
                           ha="center" if side == 0 else ("right" if side < 0 else "left"),
                           va="top" if dy < 0 else "bottom", color=col, fontsize=10, weight="bold", zorder=20)
        # measure it against its own plot and flip it back inside if it would hang off either side
        rend = fig.canvas.get_renderer()
        box = axis.get_window_extent(rend)
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

    # a label near the left edge points right, one near the right edge points left
    def inward(x, prefer):
        if x < 0.22 * len(d):
            return 1
        if x > 0.72 * len(d):
            return -1
        return prefer
    peg(ax, pj - x0, pbar, lane(sig_under, 0), BLUE, "%s: the signal" % near, side=inward(pj - x0, -1))
    peg(ax, e - x0, o[e], lane(sig_under, 1), AMBER, "BOUGHT" if long_ else "SHORTED", side=inward(e - x0, 1))
    if took_bar is not None and row["mode"] in SOLD and xb != took_bar:
        label = SOLD[row["mode"]]
        peg(ax, took_bar - x0, h[took_bar] if long_ else l[took_bar], lane(not sig_under, 0), UP, label,
            side=inward(took_bar - x0, 1 if (took_bar - x0) < 0.6 * len(d) else -1))
    if won:
        peg(ax, xb - x0, h[xb] if long_ else l[xb], lane(not sig_under, 1), UP, "OUT %+.1f%%" % (100 * ret),
            side=inward(xb - x0, 1 if (xb - x0) < 0.6 * len(d) else -1))
    else:
        peg(ax, xb - x0, l[xb] if long_ else h[xb], lane(sig_under, 2), DN, "OUT %+.1f%%" % (100 * ret),
            side=inward(xb - x0, 1 if (xb - x0) < 0.6 * len(d) else -1))
    xr = len(d) + 1
    labs = sorted([(stop, DN, "stop %s" % fmt(stop)), (fill, AMBER, "%s %s" % ("bought" if long_ else "shorted", fmt(fill))),
                   (target, UP, "%s %s" % (far, fmt(target)))])
    gap_y = 0.05 * rng
    ys = [labs[0][0]]
    for m in range(1, len(labs)):
        ys.append(max(labs[m][0], ys[-1] + gap_y))
    for (y0, col, txt), y_ in zip(labs, ys):
        ax.text(xr, y_, txt, color=col, fontsize=8.5, va="center", ha="left", zorder=20)
    step_ = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    ax.set_yticks([y for y in ax.get_yticks() if y >= 0 and ax.get_ylim()[0] <= y <= ax.get_ylim()[1]])
    reason = "%s %s" % ("daily" if htf == "1d" else "weekly", "falling" if row["e50"] == "down" else "rising" if row["e50"] == "up" else "mixed")
    if tf in ("5m", "15m"):
        reason = "its 12 EMA and the EQ agree"
    ax.set_title("%s  %s   %s, %s   %s %+.1f%% in %d bars   far line %s" % (
        sym, tf, "LONG" if long_ else "SHORT", reason, "WON" if won else "LOST", 100 * ret, row["held"],
        "reached" if row["took"] else "not reached"), color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    bars_word = ("regular-hours bars only" if hours == "regular hours" and kind in ("stock", "etf") and tf != "1d"
                 else "all bars")
    key = [[(BLUE, "blue: the EQ, flat until the next higher low or lower high"),
            (AMBER, "dotted: the entry"), (DN, "red dashed: the stop, a wick through the signal pivot"),
            (UP, "green dashed: the far line, where part is sold")],
           [("#8b93a1", ("Direction on 5m/15m: this chart's own 12 EMA AND the EQ's read (the line tested more holds, against the move it came from) agree. Right panel: the daily, 50 EMA in purple, EQ boxed."
                         if tf in ("5m", "15m") else "Direction: the daily chart over its rising 50 EMA = long, under its falling 50 EMA = short (weekly for a daily EQ). Right panel: that chart, 50 EMA in purple, the EQ boxed in orange."))],
           [("#8b93a1", "Pivots at least %d bars apart. Far line at least %.1fx the risk. Drawn on %s. Picked at random among trades WITH the bigger picture, NOT for how they turned out." % (gap, min_rr, bars_word))],
           [("#8b93a1", "Round 3: no buy on the last bar before the bell, none against this chart's own 12 EMA, stop at least 3x the cost. The rest: stop under each new higher low, sold into overbought or a close through the 12 EMA.")]]
    for r_i, items in enumerate(key):
        xpos = 0.045
        for c_, txt in items:
            fig.text(xpos, 0.086 - 0.024 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0052 * len(txt) + 0.016
    panels = []
    if hdf is not None and len(hdf) >= 60:
        axh = fig.add_subplot(gs[0, 1])
        te = df.index[e]
        anchor = int(hdf.index.searchsorted(te, side="right")) - 1
        pos = max(0, anchor - 55)
        win = min(len(hdf) - pos, 75)
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos)
                       for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panels.append((axh, hb["d"]))
        sub = hdf.index[pos:pos + win]
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.3 * yr, yhi + 0.3 * yr)
        # no price below zero on the scale (ETH weekly showed "-250")
        axh.set_yticks([y for y in axh.get_yticks() if y >= 0 and axh.get_ylim()[0] <= y <= axh.get_ylim()[1]])
        e50 = XM.ema(hdf["Close"].values.astype(float), 50)[pos:pos + win]
        axh.plot(np.arange(len(e50)), e50, color="#b48cff", lw=1.7, zorder=7)
        # where the EQ sits on the bigger chart: an orange box over the bars it lived in, at its prices
        # the box is the EQ only: from its first higher low / lower high to the bar it ended, at the prices of
        # those pivots (not the low it came in from, not the rest of the trade)
        c_lows = [float(x[2]) for x in coil if x[3] == "low"]; c_highs = [float(x[2]) for x in coil if x[3] == "high"]
        first_bar = min(x[1] for x in coil) if coil else born
        b_ = int(sub.searchsorted(df.index[first_bar], side="right")) - 1
        z_ = int(sub.searchsorted(df.index[min(end, n - 1)], side="right")) - 1
        b_ = min(max(b_, 0), win - 1); z_ = min(max(z_, b_), win - 1)
        lo_b = min(c_lows) if c_lows else row["eq_lo"]
        hi_b = max(c_highs) if c_highs else row["eq_hi"]
        if hi_b - lo_b < 0.03 * yr:
            mid_b = (hi_b + lo_b) / 2
            lo_b, hi_b = mid_b - 0.015 * yr, mid_b + 0.015 * yr
        axh.add_patch(Rectangle((b_ - 0.7, lo_b), (z_ - b_) + 1.4, hi_b - lo_b, facecolor=AMBER, alpha=.28,
                                edgecolor=AMBER, lw=2.4, zorder=12))
        peg(axh, (b_ + z_) / 2, hi_b, yhi + 0.17 * yr, AMBER, "the %s EQ" % tf, side=-1 if (b_ + z_) / 2 > 0.6 * win else 1)
        axh.set_title("%s: %s" % ("daily" if htf == "1d" else "weekly", EMAWORD.get(row["e50"], row["e50"])),
                      loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    big = "daily" if tf in ("5m", "15m", "1h", "4h") else "weekly"
    fast = tf in ("5m", "15m")
    story = (((
              "%sThis chart's %s, so this EQ was a %s. A %s confirmed, so the %s went in " if fast else
              "The %s chart was %s, so this EQ was a %s. A %s confirmed, so the %s went in ")
             + "at the next open, %s. The stop sat a wick past that %s at %s, and the %s was %s, %.1f times the risk away. ") % (
                 ("" if fast else big),
                 (("price was over a rising 12 EMA, the floor held more tests and it came from a downtrend" if long_ else
                   "price was under a falling 12 EMA, the ceiling held more tests and it came from an uptrend") if fast
                  else EMAWORD.get(row["e50"], "?")),
                 "buy" if long_ else "short", near, "buy" if long_ else "short", fmt(fill), near, fmt(stop), far,
                 fmt(target), gain / risk))
    if row["took"]:
        if row["mode"] == "all":
            story += "Price reached the %s after %d bars and everything was sold there. " % (far, took_bar - e + 1)
        elif row["mode"] in SOLD:
            story += "Price reached the %s after %d bars: %s. " % (far, took_bar - e + 1, SOLD[row["mode"]].replace(" here", ""))
    else:
        story += "It never reached the %s. " % far
    story += "Out after %d bars: %s. %+.2f%%." % (row["held"], row["why"], 100 * ret)
    return dict(sym=sym, kind=kind, tf=tf, t=row["t"], side=row["side"], ret=float(ret), held=int(row["held"]),
                reached=bool(row["took"]), why=row["why"], rr=float(gain / risk), share=float(share),
                variant=row["variant"], gap=gap, hours=bars_word, min_rr=min_rr,
                h_next=row["e50"], h_two=row["e200"], story=story,
                png=os.path.basename(path), problems=probs)


def direction_ok(x, tf):
    """5m/15m: this chart's own 12 EMA AND the EQ's own read must both point the trade's way (his note: the daily
    50 EMA is too far away for a 5m trade). 1h and up: with the daily 50 EMA (weekly for a daily EQ)."""
    if tf in ("5m", "15m"):
        want = "up" if x["side"] == "long" else "down"
        return x.get("own12") == want and x.get("inside") == want
    return x["tag1"] == 0


def _one(args):
    sym, kind, seed, variant, gap, hours, min_rr = args
    try:
        fr = S.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    use = FR2.regular_hours(fr) if (hours == "regular hours" and kind in ("stock", "etf")) else fr
    rng = np.random.default_rng(seed)
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * S.YEARS)
    got, errs = [], []
    for tf in TFS:
        df = use.get(tf)
        if df is None:
            continue
        try:
            rows = [x for x in FR2.trades(kind, tf, df, fr, start, gap, modes=[variant], filters=True)
                    if direction_ok(x, tf) and x["rr"] >= min_rr and x["born"] > 40 and x["xb"] + 22 < len(df)]
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex)); continue
        if not rows:
            continue
        htf = "1d" if tf in ("5m", "15m", "1h", "4h") else "1w"
        for want in (True, False):                 # one that reached the far line, one that did not
            pool = [r for r in rows if bool(r["took"]) == want]
            if not pool:
                continue
            r = pool[int(rng.integers(len(pool)))]
            os.makedirs(OUT, exist_ok=True)
            path = os.path.join(OUT, "%s_%s_%s_%s_%d.png" % (kind, sym, tf, r["side"], r["e"]))
            try:
                out = render(sym, kind, tf, r, df, fr.get(htf), path, hours, gap, min_rr)
            except Exception as ex:
                errs.append("%s %s %s draw: %s" % (kind, sym, tf, ex)); continue
            if out:
                got.append(out)
    return got, errs


def main():
    procs, per_tf, variant, gap, hours, min_rr = max(1, os.cpu_count() or 4), 4, VARIANT, 3, "regular hours", MIN_RR
    for i, a in enumerate(sys.argv):
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if a == "--procs" and nxt:
            procs = int(nxt)
        if a == "--per-tf" and nxt:
            per_tf = int(nxt)
        if a == "--variant" and nxt:
            variant = nxt
        if a == "--gap" and nxt:
            gap = int(nxt)
        if a == "--min-rr" and nxt:
            min_rr = float(nxt)
        if a == "--hours" and nxt:
            hours = "all hours" if nxt.startswith("all") else "regular hours"
        if a == "--log" and nxt:
            sys.stdout = sys.stderr = open(nxt, "w", buffering=1, encoding="utf-8", errors="replace")
    assert variant in [m[0] for m in FR2.MODES], "unknown variant: %s" % variant
    t0 = time.time()
    import focus
    names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    rng = np.random.default_rng(20260910)
    jobs = [(s_, k_, int(rng.integers(1 << 30)), variant, gap, hours, min_rr) for s_, k_ in names]
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
    print("  %s | pivots %d+ bars apart | far line >= %.1fx the risk | %s" % (variant, gap, min_rr, hours))
    print("  %d trades drawn from %d candidates, %d with text problems  (%.0fs)" % (len(keep), len(rows), len(bad), time.time() - t0))
    for r in keep:
        print("    %-6s %-3s %-5s %+7.2f%%  %3d bars  far line %-11s %4.1fx  %-5s/%-5s  %s" % (
            r["sym"], r["tf"], r["side"], 100 * r["ret"], r["held"], "reached" if r["reached"] else "not reached",
            r["rr"], r["h_next"], r["h_two"], "clean" if not r["problems"] else r["problems"]))
    for e in errs[:12]:
        print("  " + e)


if __name__ == "__main__":
    main()
