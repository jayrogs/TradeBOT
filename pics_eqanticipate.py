"""pics_eqanticipate.py -- the anticipated EQ (studies/eq_anticipate.py), drawn for grading at /eqanticipate.

Rule 10: no verdict before the trades are drawn. THE TRADE: on the 4-hour chart a BIG move (4+ normal bars), then a
swing back of 50% or more -- by The Chart Guys' number an equilibrium is now the likely pattern -- so the higher low
is scouted on the 15-minute chart. Two ways in are drawn, eight of each, half winners and half losers, at random:

    touch     bought INSIDE the 15m candle the moment its RSI touches 30 (the backburner marking the 4h higher low),
              stop under the low of the big move, all out just before the lower high
    confirm   bought at the next open after the higher low CONFIRMS on the 4-hour chart, only when the lower high is
              at least 1x the risk away, stop a wick under that higher low, all out just before the lower high

Left: the 15m with its RSI. Right: the 4h with A (where the move began), B (its low), C (the swing back).
Every chart is measured (pics_ride.overlaps) and the log says how many have problems.

    python pics_eqanticipate.py --procs 8
Writes validation/eq_anticipate/*.png + index.json
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
import indicators as IND          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_anticipate as EA        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, RED, AMBER, BLUE = "#b48cff", "#3ddc97", "#ff5c72", "#ffb84d", "#5aa9ff"
OUT = os.path.join("validation", "eq_anticipate")
PAIR = 1                       # 4h idea, 15m timing
T_TF, t_TF = EA.PAIRS[PAIR]
WAY_NAME = {0: "confirm", 2: "touch"}
try:
    SUSPECT = set(json.load(open(os.path.join("validation", "suspect_names.json"))).get("names", []))
except Exception:
    SUSPECT = set()


def _frames(sym, kind):
    fr = S.frames_for(sym, kind)
    need = {x for p in EA.PAIRS for x in p} | {"1d", "1w"}       # EXACTLY the charts the study loaded
    fr = {k: v for k, v in fr.items() if k in need}
    if kind in ("stock", "etf"):
        fr = FR2.regular_hours(fr)
    return fr


def _one(args):
    sym, kind, start = args
    try:
        EA.DETAIL = []
        EA._work((sym, kind, start))
        out = [d for d in EA.DETAIL
               if d["pair"] == PAIR and d["side"] == 1 and d["leg"] >= 4 and d["retrace"] >= 0.5
               and ((d["way"] == 2) or (d["way"] == 0 and d["rr"] >= 1.0))]
        EA.DETAIL = None
        return out, []
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]


def draw(tr, D, d, path):
    import pics_ride as PR
    # every bar is looked up by its TIME, never by a stored bar number (GIS, 2026-09-21: the 4h marks landed seven
    # months from the trade because the drawing's frames were not the study's)
    e = int(d.index.get_loc(pd.Timestamp(tr["t_e"]))); xb = int(d.index.get_loc(pd.Timestamp(tr["t_x"])))
    k = e - 1 if tr["way"] == 2 else e            # the bar it was bought on
    x1 = min(len(d) - 1, xb + 16)
    x0 = max(0, k - 120)
    if x1 - x0 > 300:
        x0 = max(0, min(k - 40, x1 - 300))
    dd = d.iloc[x0:x1 + 1]
    xs = np.arange(len(dd))
    fig = plt.figure(figsize=(16, 8.6), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1], height_ratios=[3.2, 1], wspace=0.12, hspace=0.06,
                          top=0.92, bottom=0.12)
    ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(d, x0, len(dd)); bnd["spans"] = []; bnd["pivots"] = []; bnd["eq"] = [False] * len(dd)
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    lo = min(float(np.nanmin(dd["Low"].values)), tr["stop"])
    hi = max(float(np.nanmax(dd["High"].values)), tr["tgt"])
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.46 * rng, hi + 0.10 * rng)
    pad_x = max(34, int(0.24 * len(dd)))
    ax.set_xlim(-1, len(dd) + pad_x)
    plt.setp(ax.get_xticklabels(), visible=False)
    ax.hlines(tr["stop"], k - x0, len(dd) - 1, colors=RED, lw=1.5, linestyles="--", zorder=7)
    ax.hlines(tr["tgt"], 0, len(dd) - 1, colors=BLUE, lw=1.2, linestyles="-.", zorder=6)
    ax.hlines(tr["fill"], k - x0, len(dd) - 1, colors="#e6e9ee", lw=1.0, linestyles=":", zorder=8)
    for y, txt, colr in ((tr["tgt"], "sell here", BLUE), (tr["stop"], "stop", RED)):
        an = ax.annotate(txt, (len(dd) + 3, y), xytext=(6, 0), textcoords="offset points", ha="left", va="center",
                         color=colr, fontsize=8, zorder=20)
        PR.keep_inside(ax, an)

    def peg(x, y_bar, frac, colr, marker, label):
        y_lane = lo - frac * rng
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=0.7, ls=":", alpha=0.6, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=130, color=colr, edgecolor="#ffffff", lw=0.8, zorder=13)
        an = ax.annotate(label, (x, y_lane), xytext=(0, -10), textcoords="offset points", ha="center", va="top",
                         color=colr, fontsize=8.5, weight="bold", zorder=20)
        PR.keep_inside(ax, an)
    peg(k - x0, tr["fill"], 0.10, GREEN, "^",
        "bought as 15m RSI touched 30" if tr["way"] == 2 else "bought: the 4h higher low confirmed")
    peg(xb - x0, tr["xpx"], 0.28, "#e6e9ee", "X", "out %+.2fR" % tr["R"])
    ax.set_title("%s 15m   %s   risk %.2f%%  ->  %+.2f%%  (%+.2fR)" % (
        tr["sym"], "bought at the touch of 30" if tr["way"] == 2 else "bought after the 4h higher low confirmed",
        tr["risk_pct"], tr["pct"], tr["R"]), color="#e6e9ee", fontsize=10.5, loc="left", pad=8)
    axr = fig.add_subplot(gs[1, 0], sharex=ax)
    axr.set_facecolor(DARK)
    rsi_all = IND.rsi(d["Close"].values.astype(float)[:x1 + 1], 14)[x0:x1 + 1]
    axr.plot(xs, rsi_all, color="#e6e9ee", lw=1.1)
    axr.axhline(30, color=GREEN, lw=0.9, ls="--"); axr.axhline(70, color=RED, lw=0.9, ls="--")
    axr.set_ylim(5, 95); axr.set_yticks([30, 50, 70])
    axr.tick_params(colors=DIM, labelsize=7)
    for sp in axr.spines.values():
        sp.set_color("#252a33")
    axr.grid(color="#1a1e25", lw=0.5)
    step_ = max(len(dd) // 7, 1)
    axr.set_xticks(xs[::step_]); axr.set_xticklabels([q.strftime("%m-%d %H:%M") for q in dd.index[::step_]], fontsize=6.5)
    axr.set_ylabel("RSI 14", color=DIM, fontsize=8)
    panels = [(ax, dd)]
    # the 4h beside it: A, B, C and the two lines
    jA, jB, jC = (int(D.index.get_loc(pd.Timestamp(tr[q]))) for q in ("tA", "tB", "tC"))
    assert abs(float(D["Low"].values[jB]) - tr["pB"]) < 1e-6 * max(1.0, tr["pB"]), "B is not where the study put it"
    t_out = d.index[min(xb, len(d) - 1)]
    end_T = int(D.index.searchsorted(t_out, side="right"))
    pos = max(0, jA - 45); stop_T = min(len(D), max(end_T + 8, jC + 14))
    axd = fig.add_subplot(gs[:, 1])
    hb = CK.bundle(D, pos, stop_T - pos); hb["spans"] = []; hb["pivots"] = []; hb["eq"] = [False] * (stop_T - pos)
    CK.render(axd, hb, "", "%Y-%m-%d")
    ylo = min(float(np.nanmin(D["Low"].values[pos:stop_T])), tr["stop"])
    yhi = float(np.nanmax(D["High"].values[pos:stop_T]))
    yr = max(yhi - ylo, 1e-9)
    axd.set_ylim(ylo - 0.22 * yr, yhi + 0.22 * yr)
    axd.set_xlim(-1, stop_T - pos + 3)
    Dh = D["High"].values.astype(float); Dl = D["Low"].values.astype(float)
    # the marks live in fixed lanes clear of every candle: A high up, C one lane lower, B under all of price
    for j_, y_, up, txt, y_l in ((jA, Dh[jA], True, "A", yhi + 0.13 * yr), (jB, Dl[jB], False, "B", ylo - 0.08 * yr),
                                 (jC, Dh[jC], True, "C", yhi + 0.04 * yr)):
        axd.plot([j_ - pos, j_ - pos], [y_, y_l], color=AMBER, lw=0.8, ls=":", zorder=6)
        an = axd.annotate(txt, (j_ - pos, y_l), xytext=(0, 4 if up else -4), textcoords="offset points", ha="center",
                          va="bottom" if up else "top", color=AMBER, fontsize=11, weight="bold", zorder=20)
        PR.keep_inside(axd, an)
    axd.hlines(tr["tgt"], jC - pos, stop_T - pos - 1, colors=BLUE, lw=1.1, linestyles="-.", zorder=6)
    axd.hlines(tr["stop"], jB - pos, stop_T - pos - 1, colors=RED, lw=1.2, linestyles="--", zorder=6)
    t_in = d.index[min(k, len(d) - 1)]
    axd.axvline(int(D.index.searchsorted(t_in, side="right")) - 1 - pos, color=GREEN, lw=1.0, ls=":", zorder=4)
    axd.set_title("4h: A to B fell %.1f normal bars, C took back %.0f%%" % (tr["leg"], 100 * tr["retrace"]),
                  loc="left", color=DIM, fontsize=9.5, pad=3)
    plt.setp(axd.get_xticklabels(), fontsize=6)
    panels.append((axd, hb["d"]))
    fig.text(0.045, 0.045, "green arrow = the buy    white dotted = the price paid    red dashed = the stop    "
             "blue = where it is all sold, just under the lower high (C)", color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.015, "right = the 4-hour chart; the green dotted line is the bar it was bought on    the tan line on both charts is the 12 EMA",
             color=DIM, fontsize=8.5, ha="left")
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def _draw(args):
    sym, kind, picks = args
    try:
        fr = _frames(sym, kind)
        out = []
        for tr in picks:
            png = "%s_%s_%s_%d.png" % (kind, sym, WAY_NAME[tr["way"]], tr["e"])
            probs = draw(tr, fr[T_TF], fr[t_TF], os.path.join(OUT, png))
            out.append(dict(tr, png=png, problems=probs, way_name=WAY_NAME[tr["way"]]))
        return out, []
    except Exception as ex:
        return [], ["%s %s draw: %s" % (kind, sym, ex)]


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * S.YEARS)
    names = [(s_, k_, start) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in SUSPECT]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, names, chunksize=4):
            rows += got; errs += err
    print("  %d trades (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    rng = np.random.default_rng(20260921)
    picks, stats = [], {}
    for way in (2, 0):
        sub = [r for r in rows if r["way"] == way]
        pct = np.array([r["pct"] for r in sub]); R_ = np.array([r["R"] for r in sub])
        stats[WAY_NAME[way]] = dict(n=len(sub), avg_pct=float(pct.mean()), middle_pct=float(np.median(pct)),
                                    won=float((pct > 0).mean()), avg_R=float(R_.mean()),
                                    median_risk=float(np.median([r["risk_pct"] for r in sub])))
        wins = [r for r in sub if r["R"] > 0.15]; losses = [r for r in sub if r["R"] <= -0.15]
        picks += [wins[i] for i in rng.choice(len(wins), 4, replace=False)]
        picks += [losses[i] for i in rng.choice(len(losses), 4, replace=False)]
    by = {}
    for tr in picks:
        by.setdefault((tr["sym"], tr["kind"]), []).append(tr)
    drawn, derr = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by))) as ex:
        for got, err in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got; derr += err
    drawn.sort(key=lambda x: (x["way"] != 2, -x["R"]))
    for i, tr in enumerate(drawn, 1):
        tr["n"] = i
    keep = {d_["png"] for d_ in drawn} | {"index.json"}
    for f in os.listdir(OUT):
        if f not in keep:
            os.remove(os.path.join(OUT, f))
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), stats=stats, charts=drawn),
              open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d_ in drawn if d_["problems"]), time.time() - t0))
    for k_, v in stats.items():
        print("  %-8s" % k_, {a: round(b, 3) for a, b in v.items()})
    for d_ in drawn:
        print("    #%-2d %-7s %-8s %+6.2fR %+7.2f%%  risk %.2f%%  %s" % (
            d_["n"], d_["sym"], d_["way_name"], d_["R"], d_["pct"], d_["risk_pct"], d_["problems"] or "clean"))
    for e_ in (errs + derr)[:8]:
        print("  " + e_)


if __name__ == "__main__":
    main()
