"""pics_eqtrade.py -- the EQ TRADES drawn, not just the shape.

The study says every version loses. Before that verdict stands, the machine has to show its
work: where it bought, where the stop was, where it got out and why. Rule 10.

    pythonw pics_eqtrade.py --procs 20 --log logs/pics_eqtrade.log
    --per-tf N   how many per chart size (default 4)
    --trade "..."  which trade to draw (default: buy the floor, hold for the break)

Writes validation/eq_trades/*.png + eq_trades_index.json  ->  /eqtrades
Half winners, half losers, picked at random inside each. Every chart measured before saving.
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
import panel as P                 # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_coil_study as ES        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
UP, DN, BLUE, AMBER, GREY = "#3ddc97", "#ff5c72", "#5aa9ff", "#ffb84d", "#8b93a1"
OUT = os.path.join("validation", "eq_trades")
TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
HIGHER = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w", "1w": None}
TRADE = "buy the floor, hold for the break"


def fmt(x):
    return ("%.4g" % x) if x < 10 else ("%.2f" % x) if x < 1000 else ("%.0f" % x)


def one_trade(df, kind, tf, r, floor, ceil, atr, trade=TRADE):
    """Re-walk exactly what the study did, and hand back every number it used."""
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    i, end = r["confirm"], r["end"]
    a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
    if not np.isfinite(a):
        return None
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    cap = ES.CAP_DAYS * S.BARS_DAY[tf]

    def edge_at(k):
        fk = floor[k] if np.isfinite(floor[k]) else r["floor"]
        ck = ceil[k] if np.isfinite(ceil[k]) else r["ceil"]
        return float(fk), float(ck)

    def touched_floor(k):
        fk = edge_at(k)[0]
        tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
        return (fk - tol) <= l[k] <= (fk + ES.TOUCH * a)
    touch = next((k for k in range(i, min(end + 1, n - 1))
                  if touched_floor(k) and o[k + 1] >= edge_at(k)[0]), None)
    if touch is None or touch + 1 >= n - 1:
        return None
    e = touch + 1
    f, ce = edge_at(e - 1)
    res = ES.walk_hold(+1, c, o, h, l, atr, e, f, ce, n, cap, day, partial=False)
    if res is None:
        return None
    xb, xpx, why, worst = res
    fill = o[e]
    cost = S.CLASS_COST.get(kind, S.COST)
    a0 = atr[e - 1] if np.isfinite(atr[e - 1]) else 0.0
    return dict(touch=touch, e=e, fill=fill, floor=f, ceil=ce, stop=f - P.SAME_LEVEL_ATR * a0,
                xb=xb, xpx=xpx, why=why, worst=worst, ret=xpx / fill - 1 - cost,
                held=xb + 1 - e, atr0=a0)


def render(sym, kind, tf, r, frames, path):
    df = frames[tf]
    floor, ceil, cid, rs, atr = EC.coils(df)
    rr = next((x for x in rs if x["born"] == r["born"] and x["end"] == r["end"]), None)
    if rr is None:
        return None
    t = one_trade(df, kind, tf, rr, floor, ceil, atr)
    if t is None:
        return None
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    born, end, confirm, e, xb = rr["born"], rr["end"], rr["confirm"], t["e"], t["xb"]
    x0 = max(0, born - 10); x1 = min(n - 1, max(xb, end) + 22)
    d = df.iloc[x0:x1 + 1]; xs = np.arange(len(d))
    htf = HIGHER.get(tf)
    hdf = frames.get(htf) if htf else None
    if hdf is not None and len(hdf) >= 60:
        fig = plt.figure(figsize=(17, 8.8), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.8, 1], wspace=0.13, top=0.92, bottom=0.15)
        ax = fig.add_subplot(gs[0, 0])
    else:
        fig = plt.figure(figsize=(14, 8.2), dpi=105); fig.patch.set_facecolor(DARK)
        gs = fig.add_gridspec(1, 1, top=0.92, bottom=0.15)
        ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, x1) - x0) for k_, s0, s1 in ST.spans(df, causal=True) if s1 >= x0 and s0 <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    # the EQ's two edges, flat steps, only while it was alive
    piv = [(ci, j, p, k_, lab) for ci, j, p, k_, lab in ST.pivots(df) if born <= j <= end]
    coil = [x for x in piv if (x[3] == "low" and x[4] in EC.UP_LAB) or (x[3] == "high" and x[4] in EC.DN_LAB)]

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
    ax.set_ylim(lo - 0.50 * rng, hi + 0.40 * rng)
    ax.set_xlim(-1, len(d) + 26)
    lane_dn = lo - 0.17 * rng; lane_dn2 = lo - 0.36 * rng; lane_up = hi + 0.18 * rng

    def peg(x, y_bar, y_lane, col, mk, label, side=0, size=200, dy=None):
        ax.plot([x, x], [y_bar, y_lane], color=col, lw=.8, ls=":", alpha=.7, zorder=6)
        ax.scatter([x], [y_lane], marker=mk, s=size, color=col, edgecolor="#ffffff", lw=.9, zorder=14)
        if dy is None:
            dy = -13 if y_lane < y_bar else 13
        an = ax.annotate(label, (x, y_lane), xytext=(10 * side, dy), textcoords="offset points",
                         ha="center" if side == 0 else ("right" if side < 0 else "left"),
                         va="top" if dy < 0 else "bottom", color=col, fontsize=10, weight="bold", zorder=20)
        from pics_ride import keep_inside
        keep_inside(ax, an)
    # the stop, drawn as a line so you can see how close it is to the fill
    ax.axhline(t["stop"], color=DN, lw=1.1, ls="--", alpha=.75, zorder=5)
    ax.axhline(t["fill"], color=AMBER, lw=1.0, ls=":", alpha=.7, zorder=5)
    won = t["ret"] > 0
    col = UP if won else DN
    ax.axvline(confirm - x0, color=BLUE, lw=1.0, ls="--", alpha=.5, zorder=5)
    peg(t["touch"] - x0, l[t["touch"]], lane_dn, BLUE, "^", "touched the floor", side=-1, size=140)
    peg(e - x0, o[e], lane_dn2, AMBER, "^", "BOUGHT", side=-1, size=250)
    peg(xb - x0, h[xb] if won else l[xb], lane_up if won else lane_dn2, col, "v" if won else "^",
        "SOLD %+.1f%%" % (100 * t["ret"]), side=1, size=250,
        dy=13 if won else (-13 if abs(xb - e) > len(d) * 0.08 else -30))
    xr = len(d) + 1
    # three price labels on the right, pushed apart when the lines sit close together
    lab = sorted([(t["stop"], DN, "stop"), (t["fill"], AMBER, "bought"), (t["ceil"], BLUE, "ceiling")])
    gap = 0.045 * rng
    for m in range(1, len(lab)):
        if lab[m][0] - lab[m - 1][0] < gap:
            lab[m] = (lab[m - 1][0] + gap, lab[m][1], lab[m][2])
    for y_, c_, n_ in lab:
        ax.text(xr, y_, "%s %s" % (n_, fmt({"stop": t["stop"], "bought": t["fill"], "ceiling": t["ceil"]}[n_])),
                color=c_, fontsize=8.5, va="center", ha="left", zorder=20)
    step_ = max(len(d) // 8, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    room = (t["fill"] - t["stop"]) / t["atr0"] if t["atr0"] > 0 else float("nan")
    up_room = (t["ceil"] - t["fill"]) / t["atr0"] if t["atr0"] > 0 else float("nan")
    ax.set_title("%s  %s   %s %+.1f%% in %d bars   stop %.2f bars under, ceiling %.2f over" % (
        sym, tf, "WON" if won else "LOST", 100 * t["ret"], t["held"], room, up_room),
        color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    key = [[(BLUE, "blue: the EQ's floor and ceiling, flat until the next pivot replaces them"),
            (AMBER, "dotted: what we paid"), (DN, "dashed: the stop, a wick through the floor")],
           [(BLUE, "the vertical dashed line is where the shape became knowable; nothing acts before it")],
           [("#8b93a1", "HH HL LH LL are the swing highs and lows. Green background: uptrend. Red: downtrend. Picked at random, NOT for how it turned out.")]]
    for r_i, items in enumerate(key):
        xpos = 0.045
        for c_, txt in items:
            fig.text(xpos, 0.072 - 0.023 * r_i, txt, color=c_, fontsize=8.5, ha="left", va="bottom")
            xpos += 0.0053 * len(txt) + 0.018
    panels = []
    if hdf is not None and len(hdf) >= 60:
        axh = fig.add_subplot(gs[0, 1])
        pos = max(0, int(hdf.index.searchsorted(df.index[born])) - 70); win = min(len(hdf) - pos, 120)
        hb = CK.bundle(hdf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, pos + win - 1) - pos) for k_, s0, s1 in ST.spans(hdf, causal=True) if s1 >= pos and s0 <= pos + win - 1]
        CK.render(axh, hb, "", "%m-%d %H:%M")
        panels.append((axh, hb["d"]))
        sub = hdf.index[pos:pos + win]
        a_ = min(max(int(sub.searchsorted(df.index[e])), 0), win - 1)
        hl_ = hdf["Low"].values[pos:pos + win]; hh_ = hdf["High"].values[pos:pos + win]
        ylo = float(np.nanmin(hl_)); yhi = float(np.nanmax(hh_)); yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(ylo - 0.3 * yr, yhi + 0.3 * yr)
        axh.axvline(a_, color=AMBER, lw=1.1, alpha=.85, zorder=9)
        axh.set_title("%s" % htf, loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, d)] + panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    after = min(n - 1, xb + 20)
    story = ("The EQ had closed to %.1f normal bars. Price came back to the floor at %s, so we bought the next open at %s. "
             "The stop sat at %s, only %.2f of a normal bar below the fill, and the ceiling was %.2f above. "
             "%s after %d bars: %s. %+.1f%%. Twenty bars later price was %+.1f%% from where we bought." % (
                 rr["wide_at_end"] or 0, fmt(l[t["touch"]]), fmt(t["fill"]), fmt(t["stop"]), room, up_room,
                 "Out" if not won else "Out", t["held"], t["why"], 100 * t["ret"],
                 100 * (c[after] / t["fill"] - 1)))
    return dict(sym=sym, kind=kind, tf=tf, t=str(df.index[e]), ret=float(t["ret"]), held=int(t["held"]),
                why=t["why"], room=float(room), up_room=float(up_room), story=story,
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
            floor, ceil, cid, rs, atr = EC.coils(df)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex)); continue
        good = [r for r in rs if r["tradeable"] and r["born"] > 40 and r["end"] + 25 < len(df)]
        rng.shuffle(good)
        for r in good[:6]:
            t = one_trade(df, kind, tf, r, floor, ceil, atr)
            if t is None:
                continue
            os.makedirs(OUT, exist_ok=True)
            path = os.path.join(OUT, "%s_%s_%s_%d.png" % (kind, sym, tf, r["born"]))
            try:
                out = render(sym, kind, tf, r, fr, path)
            except Exception as ex:
                errs.append("%s %s %s draw: %s" % (kind, sym, tf, ex)); continue
            if out:
                got.append(out)
                break
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
        wins = [r for r in g if r["ret"] > 0]; losses = [r for r in g if r["ret"] <= 0]
        rng.shuffle(wins); rng.shuffle(losses)
        half = max(1, per_tf // 2)
        keep += wins[:half] + losses[:per_tf - min(half, len(wins))]
    keep.sort(key=lambda r: (TFS.index(r["tf"]), -r["ret"]))
    json.dump(keep, open(os.path.join(OUT, "eq_trades_index.json"), "w"), indent=1)
    bad = [r for r in keep if r["problems"]]
    print("  %d trades drawn from %d, %d with text problems  (%.0fs)" % (len(keep), len(rows), len(bad), time.time() - t0))
    for r in keep:
        print("    %-6s %-3s %+7.2f%%  %3d bars  stop %.2f bars below, ceiling %.2f above  %-30s %s" % (
            r["sym"], r["tf"], 100 * r["ret"], r["held"], r["room"], r["up_room"], r["why"][:30],
            "clean" if not r["problems"] else r["problems"]))
    for e in errs[:12]:
        print("  " + e)


if __name__ == "__main__":
    main()
