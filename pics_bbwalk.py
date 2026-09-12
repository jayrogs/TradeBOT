"""pics_bbwalk.py -- the backburner trade drawn, winners and losers (2026-09-12).

THE TRADE (`studies/bb_verify.py`), in his words: "its about buying it AT OR UNDER 30 ... its about scaling into a
dip". RSI 14 on the 5m/15m reaches 30 or under: a first unit goes on at the next open, and up to two more as price
keeps falling, each a further half a normal bar down, while the print STAYS at or under 30. The position is the
average of those fills. Stop at the nearest structure below the LOWEST fill that kills the idea (this chart's last
low or the idea chart's, plus a little). Half off at 1x the risk. The rest with the stop walked under each new
higher low on the idea chart (1h for a 5m entry, 4h for a 15m). Only in names with relative strength to their own
sector leader. Shorts mirror it.

Nothing is claimed about this trade until these are looked at.

    pythonw pics_bbwalk.py --procs 20 --log logs\\pics_bbwalk.log
Writes validation/bb_walk/*.png + bb_walk_index.json  ->  /bbwalk
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import structure as ST            # noqa: E402
import panel as P                 # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
import bb_verify as BB            # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, RED, AMBER, BLUE = "#b48cff", "#3ddc97", "#ff5c72", "#ffb84d", "#5aa9ff"
OUT = os.path.join("validation", "bb_walk")
PAIRS = L.PAIRS
COST = L.COST
L_ADDS = BB.ADDS
L_ADD_GAP = BB.ADD_GAP


def walk_one(kind, o, h, l, c, e, side, stop, risk, big_hl, bell, entry_px=None):
    """The same walk bb_verify runs, but recording every step so it can be drawn.
    `e` is the LAST fill of the scale-in and `entry_px` the average of the fills."""
    n = len(c)
    last = min(n - 1, e + L.MAX_BARS)
    if bell is not None:
        last = min(last, int(bell))
    entry = o[e] if entry_px is None else float(entry_px)
    cut = entry + side * risk
    took_at = None
    line = stop
    steps = [(int(e), float(stop))]
    for j in range(e, last + 1):
        if (side > 0 and l[j] <= line) or (side < 0 and h[j] >= line):
            px = o[j + 1] if j + 1 <= last else c[last]
            pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry) if took_at is not None \
                else side * (px - entry) / entry
            return dict(end=int(j), exit_px=float(px), pct=float(pnl * 100 - COST.get(kind, 0.05) * (1.5 if took_at else 1)),
                        took_at=None if took_at is None else int(took_at), cut=float(cut), steps=steps,
                        how="rest stopped out" if took_at is not None else "stopped out")
        if took_at is None and ((side > 0 and h[j] >= cut) or (side < 0 and l[j] <= cut)):
            took_at = j
        if np.isfinite(big_hl[j]):
            cand = big_hl[j]
            if side > 0 and cand < l[j] and cand > line:
                line = cand
                steps.append((int(j), float(line)))
            if side < 0 and cand > h[j] and cand < line:
                line = cand
                steps.append((int(j), float(line)))
    px = c[last]
    pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry) if took_at is not None \
        else side * (px - entry) / entry
    return dict(end=int(last), exit_px=float(px), pct=float(pnl * 100 - COST.get(kind, 0.05) * (1.5 if took_at else 1)),
                took_at=None if took_at is None else int(took_at), cut=float(cut), steps=steps,
                how="time ran out")


def trades_for(sym, kind):
    frames = S.frames_for(sym, kind)
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    got = []
    for tf, big, _ in PAIRS:
        df, bdf = frames.get(tf), frames.get(big)
        if df is None or bdf is None or len(df) < 500 or len(bdf) < 80:
            continue
        o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        n = len(c)
        atr = P._atr(df); rsi = IND.rsi(c, 14)
        piv = ST.pivots(df)
        last_lo = np.full(n, np.nan); last_hi = np.full(n, np.nan)
        cl = ch = np.nan; q = 0
        for k in range(n):
            while q < len(piv) and piv[q][0] <= k:
                if piv[q][3] == "low":
                    cl = float(piv[q][2])
                else:
                    ch = float(piv[q][2])
                q += 1
            last_lo[k] = cl; last_hi[k] = ch
        b12 = L.align_to(df, tf, frames, big, XM.ema(bdf["Close"].values.astype(float), 12))
        bp = ST.pivots(bdf)
        bl = np.full(len(bdf), np.nan); bh = np.full(len(bdf), np.nan)
        cl2 = ch2 = np.nan; p2 = 0
        for k in range(len(bdf)):
            while p2 < len(bp) and bp[p2][0] <= k:
                if bp[p2][3] == "low":
                    cl2 = float(bp[p2][2])
                else:
                    ch2 = float(bp[p2][2])
                p2 += 1
            bl[k] = cl2; bh[k] = ch2
        big_lo = L.align_to(df, tf, frames, big, bl)
        big_hi = L.align_to(df, tf, frames, big, bh)
        bells = None
        if kind in ("stock", "etf"):
            day = df.index.normalize().values
            bells = np.searchsorted(day, day, side="right") - 1
        # RELATIVE STRENGTH against the name's OWN sector leader, exactly as bb_verify measures it
        strong = np.zeros(n)
        lead_name = "-"
        lead = BB.SECTOR_MAP.get("%s|%s" % (kind, sym))
        d1 = frames.get("1d")
        if lead and d1 is not None and len(d1) > 60:
            lk, ls = lead[0].split("|")
            try:
                bx = S.frames_for(ls, lk)["1d"]["Close"]
            except Exception:
                bx = None
            if bx is not None:
                bxa = bx.reindex(d1.index).ffill().values.astype(float)
                ratio = d1["Close"].values.astype(float) / bxa
                ok = np.isfinite(ratio)
                if ok.sum() >= 60:
                    lead_name = ls
                    r12 = XM.ema(np.where(ok, ratio, np.nan), 12)
                    up5 = r12 - np.r_[np.full(5, np.nan), r12[:-5]]
                    flag = np.where((ratio > r12) & (up5 > 0), 1.0, 0.0)
                    al = L.align_to(df, tf, frames, "1d", flag)
                    strong = np.where(np.isfinite(al), al, 0.0)
        os_ = rsi <= 30; ob = rsi >= 70
        # the FIRST bar of each oversold run: that is where the scale-in starts (not the cross back over)
        for side, ks in ((1, np.where(os_[1:] & ~os_[:-1])[0] + 1), (-1, np.where(ob[1:] & ~ob[:-1])[0] + 1)):
            for k in ks:
                e = k + 1; m_ = e - 1
                if e < 120 or e + 10 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                    continue
                a = atr[m_]
                # SCALE IN while the print stays at or under 30, each unit half a normal bar lower
                fills = [o[e]]
                fill_bars = [e]
                j = e
                while len(fills) < L_ADDS and j + 1 < n:
                    j += 1
                    if not ((rsi[j - 1] <= 30) if side > 0 else (rsi[j - 1] >= 70)):
                        break
                    gap = L_ADD_GAP * a
                    lower = (o[j] <= fills[-1] - gap) if side > 0 else (o[j] >= fills[-1] + gap)
                    if lower:
                        fills.append(o[j])
                        fill_bars.append(j)
                entry = float(np.mean(fills))
                e_last = fill_bars[-1]
                worst = min(fills) if side > 0 else max(fills)
                near_small = last_lo[e_last] if side > 0 else last_hi[e_last]
                near_big = big_lo[e_last] if side > 0 else big_hi[e_last]
                pool = [(x, lab) for x, lab in ((near_small, "this chart's last %s" % ("low" if side > 0 else "high")),
                                                (near_big, "the %s's last %s" % (big, "low" if side > 0 else "high")))
                        if np.isfinite(x) and ((side > 0 and x < worst) or (side < 0 and x > worst))]
                if not pool:
                    continue
                base, from_ = max(pool) if side > 0 else min(pool)
                stop = (base - 0.15 * a) if side > 0 else (base + 0.15 * a)
                risk = abs(entry - stop)
                if risk < 0.25 * a:
                    risk = 0.25 * a
                    stop = entry - side * risk
                    from_ = "floored at a quarter of a normal bar"
                rp = risk / entry * 100
                if rp < 3 * COST.get(kind, 0.05) or rp > 5.0:
                    continue
                if not (strong[e_last] > 0):        # his filter: strength against its own sector leader
                    continue
                r = walk_one(kind, o, h, l, c, e_last, side, stop, risk, big_lo if side > 0 else big_hi,
                             None if bells is None else bells[e_last], entry_px=entry)
                got.append(dict(sym=sym, kind=kind, tf=tf, big=big, side=int(side), e=int(e_last), first=int(e),
                                entry=float(entry), fills=[float(x) for x in fills],
                                fill_bars=[int(x) for x in fill_bars], leader=lead_name,
                                stop=float(stop), risk_pct=float(risk / entry * 100), t=str(df.index[e]),
                                stop_from=from_, base=float(base) if "floored" not in from_ else float(stop),
                                R=float(r["pct"] / (risk / entry * 100)), **r))
    return got


def draw(sym, tf, big, df, bdf, tr, path):
    e, end = tr["e"], tr["end"]
    fb = tr.get("fill_bars", [e])
    fx = tr.get("fills", [tr["entry"]])
    x0 = max(0, min(fb) - 60)
    x1 = min(len(df) - 1, end + 12)
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    fig = plt.figure(figsize=(16, 7.8), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.5, 1], wspace=0.12, top=0.90, bottom=0.155)
    ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, len(d)); bnd["spans"] = []
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    ax.plot(xs, XM.ema(df["Close"].values.astype(float)[:x1 + 1], 12)[x0:x1 + 1], color=PURPLE, lw=1.3, zorder=6)
    lo = min(float(np.nanmin(d["Low"].values)), tr["stop"], min(fx))
    hi = max(float(np.nanmax(d["High"].values)), tr["cut"], max(fx))
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.46 * rng, hi + 0.46 * rng)
    pad_x = max(20, int(0.18 * len(d)))
    ax.set_xlim(-1, len(d) + pad_x)
    # the stop as it was walked
    stx, sty = [], []
    steps = tr["steps"] + [(end, tr["steps"][-1][1])]
    for (j0_, y0_), (j1_, _) in zip(steps, steps[1:]):
        stx += [max(j0_, x0) - x0, min(j1_, x1) - x0]
        sty += [y0_, y0_]
    ax.plot(stx, sty, color=RED, lw=1.6, ls="--", zorder=7)
    ax.hlines(tr["cut"], e - x0, min(tr["took_at"] or end, x1) - x0, colors=AMBER, lw=1.4, ls="--", zorder=7)
    # the average of the fills: the price the position actually sits at
    ax.hlines(tr["entry"], min(fb) - x0, len(d) - 1, colors="#e6e9ee", lw=1.2, ls=":", zorder=8)
    ax.annotate("avg %.4g" % tr["entry"], (len(d) - 1, tr["entry"]), xytext=(5, 0),
                textcoords="offset points", ha="left", va="center", color="#e6e9ee", fontsize=8, zorder=20)
    # the risk, shaded: the average fill down to the first stop is 1R; the same distance up is where half comes off
    ax.axhspan(min(tr["entry"], tr["steps"][0][1]), max(tr["entry"], tr["steps"][0][1]),
               xmin=(e - x0 + 1) / (len(d) + pad_x + 1), color=RED, alpha=0.10, zorder=2)
    ax.axhspan(min(tr["entry"], tr["cut"]), max(tr["entry"], tr["cut"]),
               xmin=(e - x0 + 1) / (len(d) + pad_x + 1), color=AMBER, alpha=0.08, zorder=2)

    long_ = tr["side"] > 0
    sgn = -1 if long_ else 1

    def lane(frac):
        return (lo if long_ else hi) + sgn * frac * rng
    # ONE LANE PER UNIT: three fills a bar apart landed on the same spot and read as a single entry
    fill_lanes = [lane(0.10 + 0.055 * i_) for i_ in range(len(fx))]
    lane2 = lane(0.10 + 0.055 * len(fx) + 0.055)
    lane3 = lane(0.10 + 0.055 * len(fx) + 0.145)
    import pics_ride as PR

    def peg(x, y_bar, y_lane, colr, marker, label):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=0.7, ls=":", alpha=0.6, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=130, color=colr, edgecolor="#ffffff", lw=0.8, zorder=13)
        if not label:
            return
        an = ax.annotate(label, (x, y_lane), xytext=(0, -10 if long_ else 10), textcoords="offset points",
                         ha="center", va="top" if long_ else "bottom", color=colr, fontsize=8.5, weight="bold",
                         zorder=20)
        PR.keep_inside(ax, an)
    # every unit on its own lane, joined so the scale-in reads as a sequence, labelled once at the last
    word = "buy" if long_ else "short"
    if len(fx) > 1:
        ax.plot([b_ - x0 for b_ in fb], fill_lanes, color=BLUE, lw=1.0, ls="-", alpha=0.65, zorder=10)
    for i_, (b_, px_, ly_) in enumerate(zip(fb, fx, fill_lanes)):
        peg(b_ - x0, px_, ly_, GREEN if long_ else RED, "^" if long_ else "v",
            (word if len(fx) == 1 else "%s x%d, avg %.4g" % (word, len(fx), tr["entry"]))
            if i_ == len(fx) - 1 else None)
    if tr["took_at"] is not None:
        peg(tr["took_at"] - x0, tr["cut"], lane2, AMBER, "o", "half off at 1R")
    peg(end - x0, tr["exit_px"], lane3, "#e6e9ee", "X", "out %+.2fR" % tr["R"])
    step_ = max(len(d) // 7, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    ax.set_title("%s %s %s   scaled into the dip, %d unit%s   1R = %.2f%% of price  ->  %+.2fR" % (
        sym, tf, "long" if long_ else "short", len(fx), "" if len(fx) == 1 else "s", tr["risk_pct"], tr["R"]),
        color="#e6e9ee", fontsize=11, loc="left", pad=8)
    panels = [(ax, d)]
    t_now = df.index[e]
    end_h = int(bdf.index.searchsorted(t_now, side="right"))
    pos = max(0, end_h - 70); stop_h = min(len(bdf), end_h + 40)
    if stop_h - pos >= 20:
        axh = fig.add_subplot(gs[0, 1])
        hb = CK.bundle(bdf, pos, stop_h - pos); hb["spans"] = []
        CK.render(axh, hb, "", "%m-%d %H:%M")
        e12 = XM.ema(bdf["Close"].values.astype(float)[:stop_h], 12)[pos:stop_h]
        axh.plot(np.arange(len(e12)), e12, color=PURPLE, lw=1.5, zorder=6)
        ylo = float(np.nanmin(bdf["Low"].values[pos:stop_h])); yhi = float(np.nanmax(bdf["High"].values[pos:stop_h]))
        yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(max(0, ylo - 0.15 * yr), yhi + 0.15 * yr)
        axh.set_xlim(-1, stop_h - pos + 2)
        axh.axvline(end_h - pos - 0.5, color=DIM, lw=0.9, ls=":", zorder=4)
        axh.set_title("the %s" % big, loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
        panels.append((axh, hb["d"]))
    fig.text(0.045, 0.048, "arrows = each unit going on while RSI stayed at or under 30    "
             "white dotted = the average they add up to    red dashed = the stop as it stepped up",
             color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.016, "red band = what is risked (1R), from that average down to the first stop, just past %s"
             "    orange band = the same distance up, where half comes off    strong vs %s"
             % (tr.get("stop_from", "the nearest structure"), tr.get("leader", "its leader")),
             color=DIM, fontsize=8.5, ha="left")
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def _one(args):
    sym, kind = args
    try:
        return trades_for(sym, kind), []
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]


def _draw(args):
    sym, kind, picks = args
    try:
        frames = S.frames_for(sym, kind)
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        out = []
        for tr in picks:
            png = "%s_%s_%s_%d.png" % (kind, sym, tr["tf"], tr["e"])
            probs = draw(sym, tr["tf"], tr["big"], frames[tr["tf"]], frames[tr["big"]], tr, os.path.join(OUT, png))
            out.append(dict(tr, png=png, problems=probs))
        return out, []
    except Exception as ex:
        return [], ["%s %s draw: %s" % (kind, sym, ex)]


def main():
    procs = 20
    for i, a in enumerate(sys.argv):
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if a == "--procs" and nxt:
            procs = int(nxt)
        if a == "--log" and nxt:
            sys.stdout = sys.stderr = open(nxt, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    import focus
    names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, names, chunksize=1):
            rows += got; errs += err
    print("  %d trades (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    rng = np.random.default_rng(20260912)
    wins = [r for r in rows if r["R"] > 0.3]
    losses = [r for r in rows if r["R"] <= -0.5]
    picks = [wins[i] for i in rng.choice(len(wins), 8, replace=False)] + \
            [losses[i] for i in rng.choice(len(losses), 8, replace=False)]
    by_name = {}
    for tr in picks:
        by_name.setdefault((tr["sym"], tr["kind"]), []).append(tr)
    drawn, derr = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by_name))) as ex:
        for got, err in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by_name.items()], chunksize=1):
            drawn += got; derr += err
    drawn.sort(key=lambda x: -x["R"])
    for i, tr in enumerate(drawn, 1):
        tr["n"] = i
    keep = {d["png"] for d in drawn} | {"bb_walk_index.json"}
    for f in os.listdir(OUT):
        if f not in keep:
            os.remove(os.path.join(OUT, f))
    allR = np.array([r["R"] for r in rows])
    stats = dict(n=len(rows), avg_R=float(allR.mean()), middle_R=float(np.median(allR)),
                 won=float((allR > 0).mean()), avg_pct=float(np.mean([r["pct"] for r in rows])),
                 median_risk=float(np.median([r["risk_pct"] for r in rows])),
                 took_partial=float(np.mean([r["took_at"] is not None for r in rows])),
                 avg_units=float(np.mean([len(r["fills"]) for r in rows])))
    slim = [{k: v for k, v in d.items() if k != "steps"} for d in drawn]
    json.dump(dict(stats=stats, charts=slim), open(os.path.join(OUT, "bb_walk_index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d in drawn if d["problems"]), time.time() - t0))
    for d in drawn:
        print("    #%-2d %-6s %-3s %-5s %+6.2fR  risk %.2f%%  %-18s %s" % (
            d["n"], d["sym"], d["tf"], "long" if d["side"] > 0 else "short", d["R"], d["risk_pct"], d["how"],
            d["problems"] or ""))
    for e_ in (errs + derr)[:10]:
        print("  " + e_)


if __name__ == "__main__":
    main()
