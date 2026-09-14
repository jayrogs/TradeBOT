"""pics_scalein.py -- the backburner drawn, winners and losers (2026-09-13).

THE TRADE, exactly as `studies/backburner_wallet.py` measures it -- his rules, the overnight run's answers:

    the DAILY chart. A daily dip is worth about four times what a 5m one is, and on the fast charts the
      market condition stops mattering at all.
    RSI 14 at or under 30, and the name OPENED BELOW YESTERDAY'S LOW -- the fear gap. That one read is the
      biggest in the whole study: +0.84R against a control of +0.14R, positive in 10 of 10 years.
    SCALED INTO as it keeps falling: up to five units, each a quarter of a normal bar lower, while the print
      stays at or under 30. Buying the dip ONCE is worse than buying a random bar (-0.08R); the averaging is
      the edge.
    stop at the nearest structure under the LOWEST fill, half off at 1x the risk, the rest on a chandelier
      three normal bars under the highest close.

Nothing is claimed about this trade until these are looked at (rule 10).

    pythonw pics_scalein.py --procs 8 --log logs\\pics_scalein.log
Writes validation/scale_in/*.png + scale_in_index.json  ->  /scalein
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
import backburner_wallet as W     # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, RED, AMBER, BLUE = "#b48cff", "#3ddc97", "#ff5c72", "#ffb84d", "#5aa9ff"
OUT = os.path.join("validation", "scale_in")
COST = L.COST


def walk_one(kind, o, h, l, c, e, side, stop, risk, atr, entry_px, chand=3.0):
    """The same trade tcg_lab.run_trade books in "chand" mode, walked bar by bar so each step can be drawn."""
    n = len(c)
    last = min(n - 1, e + L.MAX_BARS)
    entry = float(entry_px)
    cut = entry + side * risk
    a0 = float(atr[e - 1]) if np.isfinite(atr[e - 1]) else risk
    took_at = None
    line = stop
    run = -np.inf if side > 0 else np.inf
    steps = [(int(e), float(stop))]
    for j in range(e, last + 1):
        if (side > 0 and l[j] <= line) or (side < 0 and h[j] >= line):
            px = o[j + 1] if j + 1 <= last else c[last]
            pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry) \
                if took_at is not None else side * (px - entry) / entry
            return dict(end=int(j), exit_px=float(px),
                        pct=float(pnl * 100 - COST.get(kind, 0.05) * (1.5 if took_at else 1)),
                        took_at=None if took_at is None else int(took_at), cut=float(cut), steps=steps,
                        how="the rest trailed out" if took_at is not None else "stopped out")
        if took_at is None and ((side > 0 and h[j] >= cut) or (side < 0 and l[j] <= cut)):
            took_at = j
        run = max(run, c[j]) if side > 0 else min(run, c[j])
        cand = (run - chand * a0) if side > 0 else (run + chand * a0)
        if (side > 0 and cand > line) or (side < 0 and cand < line):
            line = cand
            steps.append((int(j), float(line)))
    px = c[last]
    pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry) \
        if took_at is not None else side * (px - entry) / entry
    return dict(end=int(last), exit_px=float(px),
                pct=float(pnl * 100 - COST.get(kind, 0.05) * (1.5 if took_at else 1)),
                took_at=None if took_at is None else int(took_at), cut=float(cut), steps=steps,
                how="time ran out")


def trades_for(sym, kind):
    frames = S.frames_for(sym, kind)
    frames = {k: v for k, v in frames.items() if k in ("1d", "1w")}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    df, bdf = frames.get("1d"), frames.get("1w")
    if df is None or bdf is None or len(df) < 300 or len(bdf) < 80:
        return []
    o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df); rsi = IND.rsi(c, 14)
    piv = ST.pivots(df)
    last_lo = np.full(n, np.nan); cl = np.nan; q = 0
    for k in range(n):
        while q < len(piv) and piv[q][0] <= k:
            if piv[q][3] == "low":
                cl = float(piv[q][2])
            q += 1
        last_lo[k] = cl
    bp = ST.pivots(bdf)
    bl = np.full(len(bdf), np.nan); cl2 = np.nan; p2 = 0
    for k in range(len(bdf)):
        while p2 < len(bp) and bp[p2][0] <= k:
            if bp[p2][3] == "low":
                cl2 = float(bp[p2][2])
            p2 += 1
        bl[k] = cl2
    big_lo = L.align_to(df, "1d", frames, "1w", bl)
    gap_down = np.zeros(n)
    gap_down[1:] = (o[1:] < l[:-1]).astype(float)
    cost = COST.get(kind, 0.05)
    got = []
    os_ = rsi <= W.LEVEL
    for k in np.where(os_[1:] & ~os_[:-1])[0] + 1:
        e = k + 1
        m_ = e - 1
        if e < 120 or e + 6 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
            continue
        if gap_down[m_] < 0.5:                      # the fear gap, read on the bar before the fill
            continue
        a = atr[m_]
        fills = [o[e]]; fill_bars = [e]; j = e
        while len(fills) < W.ADDS and j + 1 < n:
            j += 1
            if rsi[j - 1] > W.LEVEL:
                break
            if o[j] <= fills[-1] - W.GAP * a:
                fills.append(o[j]); fill_bars.append(j)
        entry = float(np.mean(fills))
        e_last = fill_bars[-1]
        worst = min(fills)
        pool = [(x, lab) for x, lab in ((last_lo[e_last], "the daily's last low"),
                                        (big_lo[e_last], "the weekly's last low"))
                if np.isfinite(x) and x < worst]
        if pool:
            base, from_ = max(pool)
            stop = base - 0.15 * a
        else:
            base, from_ = worst - a, "no level left, so a normal bar under the fill"
            stop = base
        risk = abs(entry - stop)
        if risk < 0.25 * a:
            risk = 0.25 * a
            stop = entry - risk
            base, from_ = stop, "floored at a quarter of a normal bar"
        rp = risk / entry * 100
        if rp < 3 * cost or risk > 4.0 * a or rp > 25.0:
            continue
        r = walk_one(kind, o, h, l, c, e_last, 1, stop, risk, atr, entry)
        got.append(dict(sym=sym, kind=kind, tf="1d", big="1w", side=1, e=int(e_last), first=int(e),
                        entry=float(entry), fills=[float(x) for x in fills],
                        fill_bars=[int(x) for x in fill_bars], leader="-",
                        stop=float(stop), risk_pct=float(rp), t=str(df.index[e].date()),
                        stop_from=from_, base=float(base),
                        R=float(r["pct"] / rp), **r))
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
    ax.set_ylim(lo - 0.62 * rng, hi + 0.62 * rng)
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
    fill_lanes = [lane(0.10 + 0.06 * i_) for i_ in range(len(fx))]
    lane2 = lane(0.10 + 0.06 * len(fx) + 0.10)      # the partial often lands a bar or two after the buy, so
    lane3 = lane(0.10 + 0.06 * len(fx) + 0.24)      # its marker needs real space, not a hair's gap
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
    ax.set_title("%s daily   gapped under yesterday's low, RSI %d   scaled in %d unit%s   "
                 "1R = %.2f%%  ->  %+.2fR" % (
                     sym, 30, len(fx), "" if len(fx) == 1 else "s", tr["risk_pct"], tr["R"]),
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
    fig.text(0.045, 0.016, "red band = 1R, the average down to the first stop, just past %s    orange band = "
             "the same distance up, where half comes off" % tr.get("stop_from", "the nearest level"),
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
        frames = {k: v for k, v in frames.items() if k in ("1d", "1w")}
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        out = []
        for tr in picks:
            png = "%s_%s_%s_%d.png" % (kind, sym, tr["tf"], tr["e"])
            probs = draw(sym, tr["tf"], tr["big"], frames["1d"], frames["1w"], tr, os.path.join(OUT, png))
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
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf")]
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
    keep = {d["png"] for d in drawn} | {"scale_in_index.json"}
    for f in os.listdir(OUT):
        if f not in keep:
            os.remove(os.path.join(OUT, f))
    allR = np.array([r["R"] for r in rows])
    stats = dict(n=len(rows), avg_R=float(allR.mean()), middle_R=float(np.median(allR)),
                 won=float((allR > 0).mean()), avg_pct=float(np.mean([r["pct"] for r in rows])),
                 median_risk=float(np.median([r["risk_pct"] for r in rows])),
                 took_partial=float(np.mean([r["took_at"] is not None for r in rows])),
                 avg_units=float(np.mean([len(r["fills"]) for r in rows])),
                 per_year=float(len(rows) / 9.5))
    slim = [{k: v for k, v in d.items() if k != "steps"} for d in drawn]
    json.dump(dict(stats=stats, charts=slim), open(os.path.join(OUT, "scale_in_index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d in drawn if d["problems"]), time.time() - t0))
    for d in drawn:
        print("    #%-2d %-6s %-3s %-5s %+6.2fR  risk %.2f%%  %-18s %s" % (
            d["n"], d["sym"], d["tf"], "long" if d["side"] > 0 else "short", d["R"], d["risk_pct"], d["how"],
            d["problems"] or ""))
    for e_ in (errs + derr)[:10]:
        print("  " + e_)


if __name__ == "__main__":
    main()
