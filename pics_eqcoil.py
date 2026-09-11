"""pics_eqcoil.py -- the EQ as he defines it, drawn for grading.

    "eq is a series of HL and LH increasingly tightening"   (2026-09-09)

Random examples on every chart size, NOT picked for how they turned out. The converging
floor and ceiling are drawn as stepped lines so you can see them close on each other; every
higher low and lower high that built the coil is marked in its own lane; the break is marked.

    pythonw pics_eqcoil.py --procs 20 --log logs/pics_eqcoil.log
    --per-tf N   how many per chart size (default 3)

Writes validation/eq_coils/*.png and eq_coils_index.json  ->  /eqcoils
Every chart is measured with pics_ride.overlaps before it is saved.
"""
import concurrent.futures as cf
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
import structure as ST            # noqa: E402
import eq_coil as EC              # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
UP, DN, BLUE, AMBER = "#3ddc97", "#ff5c72", "#5aa9ff", "#ffb84d"
OUT = os.path.join("validation", "eq_coils")
TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
HIGHER = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w", "1w": None}
PER_TF = 3


def fmt(x):
    return ("%.4g" % x) if x < 10 else ("%.2f" % x) if x < 1000 else ("%.0f" % x)


def render(sym, kind, tf, born, end, frames, path):
    df = frames[tf]
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, cid, out, atr = EC.coils(df)
    r0 = next((r for r in out if r["born"] == born and r["end"] == end), None)
    if r0 is None or not r0["tradeable"]:
        return None
    how, depth, confirm = r0["how"], r0["pairs"], r0["confirm"]
    f_end, c_end = r0["floor"], r0["ceil"]
    # the pivots that built it
    piv = [(ci, j, p, k_, lab) for ci, j, p, k_, lab in ST.pivots(df) if born <= j <= end]
    coil_piv = [x for x in piv if (x[4] in EC.UP_LAB and x[3] == "low") or (x[4] in EC.DN_LAB and x[3] == "high")]
    x0 = max(0, born - 12); x1 = min(n - 1, end + 25)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    htf = HIGHER.get(tf)
    hdf = frames.get(htf) if htf else None
    if hdf is not None and len(hdf) >= 60:
        fig = plt.figure(figsize=(17, 8.6), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.75, 1], wspace=0.13, top=0.92, bottom=0.13)
        ax = fig.add_subplot(gs[0, 0])
    else:
        fig = plt.figure(figsize=(14, 8), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 1, top=0.92, bottom=0.13)
        ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0) for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    # THE EDGES, his way (2026-09-09): flat lines that hold until the next higher low or lower
    # high replaces them. No angled trendlines -- "it gets pretty ugly with these angled lines".
    lows_p = [(x[1], float(x[2])) for x in coil_piv if x[3] == "low"]
    highs_p = [(x[1], float(x[2])) for x in coil_piv if x[3] == "high"]

    def steps(pts, upto):
        """A flat level from each pivot until the next one of its kind, out to bar `upto`."""
        y = np.full(x1 - x0 + 1, np.nan)
        for m, (j, pr) in enumerate(pts):
            j2 = pts[m + 1][0] if m + 1 < len(pts) else upto
            a_ = max(j, x0); b_ = min(j2, upto, x1)
            if b_ >= a_:
                y[a_ - x0:b_ - x0 + 1] = pr
        return y

    fl_s = steps(lows_p, end)
    cl_s = steps(highs_p, end)
    ax.step(xs, fl_s, where="post", color=BLUE, lw=2.0, zorder=8)
    ax.step(xs, cl_s, where="post", color=BLUE, lw=2.0, zorder=8)
    okm = np.isfinite(fl_s) & np.isfinite(cl_s)
    ax.fill_between(xs, np.where(okm, fl_s, np.nan), np.where(okm, cl_s, np.nan), step="post",
                    color=BLUE, alpha=0.09, zorder=1)
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.58 * rng, hi + 0.58 * rng)
    ax.set_xlim(-1, len(d) + 26)
    lane_dn = lo - 0.15 * rng; lane_up = hi + 0.15 * rng          # the pivots that built the coil
    brk_dn = lo - 0.40 * rng; brk_up = hi + 0.40 * rng            # the break gets its own lane
    seen = {"low": (-99, 0), "high": (-99, 0)}
    nhl = nlh = 0
    span_bars = max(len(d), 1)
    near = max(4, int(span_bars * 0.16))          # how close counts as crowded, on this window
    for ci, j, p, k_, lab in coil_piv:
        col = UP if k_ == "low" else DN
        y_lane = lane_dn if k_ == "low" else lane_up
        lx, lrow = seen[k_]
        row = (lrow + 1) % 3 if j - lx <= near else 0     # three rows, not two: coils are tight
        seen[k_] = (j, row)
        dy = (-12 - 13 * row) if k_ == "low" else (12 + 13 * row)
        if k_ == "low":
            nhl += 1
            txt = "higher low %d" % nhl if nhl == 1 else "%d" % nhl
        else:
            nlh += 1
            txt = "lower high %d" % nlh if nlh == 1 else "%d" % nlh
        ax.plot([j - x0, j - x0], [p, y_lane], color=col, lw=.7, ls=":", alpha=.6, zorder=6)
        ax.scatter([j - x0], [y_lane], marker="^" if k_ == "low" else "v", s=110, color=col, edgecolor="#ffffff", lw=.7, zorder=13)
        ax.annotate(txt, (j - x0, y_lane), xytext=(0, dy), textcoords="offset points", ha="center",
                    va="top" if dy < 0 else "bottom", color=col, fontsize=9, weight="bold", zorder=20)
    broke = how.startswith("a wick")
    if broke and end + 1 <= x1:
        up_ = "ceiling" in how
        y_b = brk_up if up_ else brk_dn
        ax.plot([end - x0, end - x0], [c[end], y_b], color=AMBER, lw=.9, ls=":", alpha=.8, zorder=6)
        ax.scatter([end - x0], [y_b], marker="v" if up_ else "^", s=200, color=AMBER, edgecolor="#ffffff", lw=.9, zorder=14)
        side = -1 if (end - x0) > 0.72 * len(d) else 1
        ax.annotate("the break: a wick through the %s" % ("ceiling" if up_ else "floor"),
                    (end - x0, y_b), xytext=(11 * side, 12 if up_ else -12), textcoords="offset points",
                    ha="left" if side > 0 else "right", va="bottom" if up_ else "top",
                    color=AMBER, fontsize=9.5, weight="bold", zorder=20)
    ax.axvline(confirm - x0, color=BLUE, lw=1.0, ls="--", alpha=.55, zorder=5)
    side_c = 1 if (confirm - x0) < 0.75 * len(d) else -1
    ax.annotate("the shape is complete here", (confirm - x0, brk_up - 0.02 * rng), xytext=(6 * side_c, 0),
                textcoords="offset points", ha="left" if side_c > 0 else "right", va="bottom",
                color=BLUE, fontsize=8.5, zorder=20)
    xr = len(d) + 1
    if np.isfinite(f_end):
        ax.text(xr, f_end, "floor %s" % fmt(f_end), color=BLUE, fontsize=8, va="top", ha="left", zorder=20)
    if np.isfinite(c_end):
        ax.text(xr, c_end, "ceiling %s" % fmt(c_end), color=BLUE, fontsize=8, va="bottom", ha="left", zorder=20)
    step = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    tight = ""
    if r0["wide_at_start"] and r0["wide_at_end"]:
        tight = "   tightened %.1f -> %.1f bars" % (r0["wide_at_start"], r0["wide_at_end"])
    ax.set_title("%s  %s   EQ, %d bars, %d up into %d down%s" % (
        sym, tf, end - born + 1, nhl, nlh, tight), color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    key = [[(BLUE, "blue: the floor and the ceiling. Each level holds flat until the next higher low or lower high replaces it, so the two step INWARD. The shaded part is the EQ.")],
           [(UP, "^ each higher low"), (DN, "v each lower high"), (AMBER, "the break: a wick through a line, deeper than an equal low"),
            (BLUE, "dashed line: where you could first know the shape was there")],
           [("#8b93a1", "HH HL LH LL are the swing highs and lows. Green background: uptrend. Red: downtrend. Picked at random, NOT for how it turned out.")]]
    for r_i, items in enumerate(key):
        xpos = 0.045
        for c_, txt in items:
            fig.text(xpos, 0.062 - 0.023 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0053 * len(txt) + 0.018
    panels = []
    if hdf is not None and len(hdf) >= 60:
        axh = fig.add_subplot(gs[0, 1])
        t0 = df.index[born]; t1 = df.index[end]
        pos = max(0, int(hdf.index.searchsorted(t0)) - 70); win = min(len(hdf) - pos, 120)
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos) for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panels.append((axh, hb["d"]))
        sub = hdf.index[pos:pos + win]
        a_ = min(max(int(sub.searchsorted(t0)), 0), win - 1); b_ = min(max(int(sub.searchsorted(t1)), 0), win - 1)
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.3 * yr, yhi + 0.3 * yr)
        axh.axvspan(a_, max(b_, a_ + 0.4), color=BLUE, alpha=0.12, zorder=1)
        axh.set_title("%s - shaded: while the EQ was on" % htf, loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    after = min(n - 1, end + 20)
    story = ("A coil: %d higher lows pressing up into %d lower highs over %d bars%s. By the time the last pivot confirmed, "
             "the floor was %s and the ceiling %s, %s apart, and it lasted %d more bars before %s." % (
                 nhl, nlh, end - born + 1,
                 (", tightening from %.1f to %.1f normal bars" % (r0["wide_at_start"], r0["wide_at_end"])) if tight else "",
                 fmt(f_end), fmt(c_end),
                 ("%.1f normal bars" % r0["wide_at_end"]) if r0["wide_at_end"] else "a short way",
                 r0["live_bars"], how))
    if broke:
        story += " Twenty bars later price was %+.1f%% from the break." % (100 * (c[after] / c[end] - 1))
    return dict(sym=sym, kind=kind, tf=tf, t=str(df.index[born]), end=str(df.index[end]),
                bars=int(end - born + 1), live=int(r0["live_bars"]), pairs=int(min(nhl, nlh)),
                wide_start=r0["wide_at_start"], wide_end=r0["wide_at_end"], how=how, story=story,
                png=os.path.basename(path), problems=probs)


def _one(args):
    sym, kind, seed = args
    try:
        fr = S.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    rng = np.random.default_rng(seed)
    got, errs = [], []
    for tf in TFS:
        df = fr.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            _, _, _, out, _ = EC.coils(df)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex)); continue
        done = [(r["born"], r["end"]) for r in out
                if r["tradeable"] and r["how"] != "still open" and r["end"] + 22 < len(df) and r["born"] > 30]
        if not done:
            continue
        b, e = done[rng.integers(len(done))]
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "%s_%s_%s_%d.png" % (kind, sym, tf, b))
        try:
            r = render(sym, kind, tf, b, e, fr, path)
        except Exception as ex:
            errs.append("%s %s %s draw: %s" % (kind, sym, tf, ex)); continue
        if r:
            got.append(r)
    return got, errs


def main():
    procs = max(1, os.cpu_count() or 4)
    per_tf = PER_TF
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
    rng = np.random.default_rng(20260909)
    jobs = [(s_, k_, int(rng.integers(1 << 30))) for s_, k_ in names]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, jobs, chunksize=1):
            rows += got; errs += err
    # keep per_tf per chart size, spread across markets
    keep, seen = [], {}
    rng.shuffle(rows)
    for r in rows:
        k = r["tf"]
        if seen.get(k, 0) >= per_tf:
            continue
        seen[k] = seen.get(k, 0) + 1
        keep.append(r)
    keep.sort(key=lambda r: (TFS.index(r["tf"]), r["sym"]))
    json.dump(keep, open(os.path.join(OUT, "eq_coils_index.json"), "w"), indent=1)
    bad = [r for r in keep if r["problems"]]
    print("  %d EQs drawn from %d found, %d with text problems  (%.0fs)" % (len(keep), len(rows), len(bad), time.time() - t0))
    for r in keep:
        print("    %-6s %-3s %4d bars (%2d live)  %d pairs  %-28s %s" % (r["sym"], r["tf"], r["bars"], r["live"], r["pairs"], r["how"],
                                                              "clean" if not r["problems"] else r["problems"]))
    for e in errs[:15]:
        print("  " + e)


if __name__ == "__main__":
    main()
