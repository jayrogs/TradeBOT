"""pics_backburner_tcg.py -- the BackBurner as Dan teaches it, drawn, winners and losers (2026-09-21).

THE TRADE (`studies/backburner_dan.py`, TCG_METHOD.md #5b, #11): the name has RUN to a new high on the daily; the
FIRST time the hourly RSI touches 30 after that high he buys -- inside the candle, at the touch -- with a second bid at
RSI 20; half comes off when the bounce reaches the hourly 12 EMA; the stop then goes UNDER THE LOW OF THE DROP; the
rest is for the old high. Each drawing shows the hourly with its RSI underneath (the 30 line is the trigger) and the
daily beside it (the run, the old high, where the dip sits against the daily 12 EMA).

Nothing is claimed about this trade until these are looked at (rule 10).

    python pics_backburner_tcg.py --procs 8
Writes validation/backburner_tcg/*.png + index.json  ->  /backburners
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
import panel as P                 # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
import backburner_tcg as T        # noqa: E402
import backburner_dan as D        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, RED, AMBER, BLUE = "#b48cff", "#3ddc97", "#ff5c72", "#ffb84d", "#5aa9ff"
OUT = os.path.join("validation", "backburner_tcg")
COST = L.COST


DISASTER_BARS = 6.0            # the only line while the hourly is still oversold: a "day loser", not a chart stop


# THE STOP VARIANTS (his ask 2026-09-22: "spend some time analyzing different methods"). One dict per way:
#   first    a chart stop from the buy bar, this many normal bars under the lowest fill (None = disaster line only)
#   arm      when the stop under the low of the drop goes live: "rsi" (RSI closes back over 30), "half" (when the
#            half is sold at the 12 EMA), "never"
#   wiggle   how far under the low of the drop, in normal bars
#   off      the stop switches off again while RSI is back under 30 (his "never sell while it's oversold")
STOPS = {
    "round 1: 3 bars under the fill from the start":           dict(first=3.0, arm="half", wiggle=0.1, off=False),
    "round 2: none while oversold, RSI cross, 0.1 bar":        dict(first=None, arm="rsi", wiggle=0.1, off=True),
    "RSI cross, 0.25 bar of room":                             dict(first=None, arm="rsi", wiggle=0.25, off=True),
    "RSI cross, 0.5 bar of room":                              dict(first=None, arm="rsi", wiggle=0.5, off=True),
    "RSI cross, 1 bar of room":                                dict(first=None, arm="rsi", wiggle=1.0, off=True),
    "Dan as written: no stop until the half is sold, then under the low":
                                                               dict(first=None, arm="half", wiggle=0.1, off=False),
    "half sold, then under the low with 0.5 bar of room":      dict(first=None, arm="half", wiggle=0.5, off=False),
    "never: disaster line only, half at the EMA, rest for the high":
                                                               dict(first=None, arm="never", wiggle=0.0, off=False),
}
STOP = STOPS["Dan as written: no stop until the half is sold, then under the low"]     # round 3, after backburner_stops


def walk(kind, o, h, l, c, k, e_last, entry, stop, ema12, target, a, rsi, v=None):
    """ROUND 2 (his grading of round 1, 2026-09-21: JBHT "why did this even sell??? we need sharp dips", MNST "it
    feels really bad to sell while it's oversold"). Round 1 put a stop 3 normal bars under the fill on the buy bar
    itself, and on a waterfall candle that same candle went through it. Dan: with one fill there is NO stop, the
    unfilled second bid is the protection. So now: while the hourly RSI is still at or under 30 there is no chart
    stop, only a wide disaster line (`stop`, DISASTER_BARS under the lowest fill). The moment RSI closes back over
    30 -- the bounce is on -- the stop goes UNDER THE LOW OF THE DROP. Half at the 12 EMA, the rest for the old high."""
    n = len(c)
    last = min(n - 1, e_last + L.MAX_BARS)
    cost = COST.get(kind, 0.05)
    low0 = float(np.min(l[k:e_last + 1]))
    if l[e_last] <= stop:
        j2 = min(e_last + 1, n - 1)
        return dict(end=j2, exit_px=float(o[j2]), pct=float((o[j2] - entry) / entry * 100 - cost), half_at=None,
                    half_px=None, steps=[(int(e_last), float(stop))], how="through the disaster line on the buy bar")
    v = v or STOP
    line = stop if v["first"] is None else (stop + DISASTER_BARS * a - v["first"] * a)
    steps = [(int(e_last), float(line))]
    if l[e_last] <= line:
        j2 = min(e_last + 1, n - 1)
        return dict(end=j2, exit_px=float(o[j2]), pct=float((o[j2] - entry) / entry * 100 - cost), half_at=None,
                    half_px=None, steps=steps, how="through the stop on the bar it was bought")
    half_at = half_px = None
    armed = False
    for j in range(e_last + 1, last + 1):
        if half_at is None and v["arm"] == "rsi":
            # his rule: never sell while it is still oversold. The stop is live only while the last close had RSI
            # over 30; when RSI goes back under, the stop is off again and re-arms under the new low of the drop.
            if rsi[j - 1] <= 30:
                low0 = min(low0, float(l[j]))
                if armed and v["off"]:
                    armed = False
                    line = stop
                    steps.append((int(j), float(line)))
            elif not armed:
                armed = True
                line = low0 - v["wiggle"] * a
                steps.append((int(j), float(line)))
        elif half_at is None:
            low0 = min(low0, float(l[j]))
        if l[j] <= line:
            px = o[j + 1] if j + 1 <= last else c[last]
            got = 0.5 * (half_px - entry) / entry if half_at is not None else 0.0
            share = 0.5 if half_at is not None else 1.0
            pct = (got + share * (px - entry) / entry) * 100 - cost * (1.5 if half_at is not None else 1.0)
            return dict(end=int(j), exit_px=float(px), pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                        how="the rest stopped under the low" if half_at is not None else "stopped out")
        if half_at is None:
            if np.isfinite(ema12[j]) and h[j] >= ema12[j]:
                half_at = int(j)
                half_px = float(max(o[j], ema12[j]))
                low0 = min(low0, float(np.min(l[e_last + 1:j + 1])))
                if v["arm"] != "never" and low0 - v["wiggle"] * a != line:
                    line = low0 - v["wiggle"] * a
                    steps.append((int(j), float(line)))
        elif np.isfinite(target) and h[j] >= target:
            px = float(max(o[j], target))
            pct = (0.5 * (half_px - entry) / entry + 0.5 * (px - entry) / entry) * 100 - cost * 1.5
            return dict(end=int(j), exit_px=px, pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                        how="the rest reached the old high")
    px = float(c[last])
    got = 0.5 * (half_px - entry) / entry if half_at is not None else 0.0
    share = 0.5 if half_at is not None else 1.0
    pct = (got + share * (px - entry) / entry) * 100 - cost * (1.5 if half_at is not None else 1.0)
    return dict(end=int(last), exit_px=px, pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                how="time ran out")


def trades_for(sym, kind, v=None):
    frames = S.frames_for(sym, kind)
    frames = {k_: v for k_, v in frames.items() if k_ in ("1h", "1d", "1w")}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    df, sdf, tdf = frames.get("1h"), frames.get("1d"), frames.get("1w")
    if df is None or sdf is None or tdf is None or len(df) < 500 or len(sdf) < 120 or len(tdf) < 60:
        return []
    o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df)
    rsi, au, ad = IND.rsi_parts(c, D.N_RSI)
    ema12 = XM.ema(c, 12)
    p30 = D.rsi_price(c, au, ad, 30); p20 = D.rsi_price(c, au, ad, 20)
    sc = sdf["Close"].values.astype(float)
    satr = P._atr(sdf)
    run = np.full(len(sc), np.nan)
    run[T.RUN_LOOK:] = (sc[T.RUN_LOOK:] - sc[:-T.RUN_LOOK]) / np.where(satr[T.RUN_LOOK:] > 0, satr[T.RUN_LOOK:], np.nan)
    s_run = L.align_to(df, "1h", frames, "1d", run)
    top = pd.Series(sdf["High"].values.astype(float)).rolling(T.HIGH_LOOK, min_periods=T.HIGH_LOOK).max().values
    s_top = L.align_to(df, "1h", frames, "1d", top)
    ext_t = L.align_to(df, "1h", frames, "1d", T._last_extreme_time(sdf, 1)[0])
    tc = tdf["Close"].values.astype(float)
    e50 = XM.ema(tc, 50)
    up = np.zeros(len(tc))
    up[5:] = ((tc[5:] > e50[5:]) & (e50[5:] > e50[:-5])).astype(float)
    t_up = L.align_to(df, "1h", frames, "1w", up)
    touch = np.isfinite(p30) & (l <= p30)
    was_out = np.r_[False, rsi[:-1] > 30]
    starts = np.where(touch & was_out)[0]
    got, cnt, cur = [], 0, None
    cost = COST.get(kind, 0.05)
    for k in starts:
        t_ext = ext_t[k - 1] if k > 0 else np.nan
        if not np.isfinite(t_ext):
            continue
        if cur is None or t_ext != cur:
            cur, cnt = t_ext, 0
        cnt += 1
        m_ = k - 1
        if cnt != 1 or k < 150 or k + 8 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
            continue
        if not (np.isfinite(s_run[m_]) and s_run[m_] >= 4 and t_up[m_] > 0.5):
            continue                                    # the run into the high, and the weekly trend intact
        a = atr[m_]
        fills = [float(min(o[k], p30[k]))]; fill_bars = [int(k)]; e_last = k
        for j in range(k, min(n - 1, k + D.SECOND_BID_BARS)):
            if j > k and rsi[j - 1] > 40:
                break
            if np.isfinite(p20[j]) and l[j] <= p20[j]:
                fills.append(float(min(o[j], p20[j])) if j > k else float(p20[j])); fill_bars.append(int(j)); e_last = j
                break
        entry = float(np.mean(fills))
        stop = min(fills) - DISASTER_BARS * a
        rp = (entry - stop) / entry * 100
        if rp < 3 * cost or rp > 40.0:
            continue
        r = walk(kind, o, h, l, c, k, e_last, entry, stop, ema12, s_top[m_], a, rsi, v)
        got.append(dict(sym=sym, kind=kind, k=int(k), e=int(e_last), entry=entry, fills=fills, fill_bars=fill_bars,
                        stop=float(stop), risk_pct=float(rp), t=str(df.index[k]), run=float(s_run[m_]),
                        target=float(s_top[m_]) if np.isfinite(s_top[m_]) else None,
                        R=float(r["pct"] / rp), **r))
    return got


def draw(sym, df, sdf, tr, path):
    import pics_ride as PR
    k, end = tr["k"], tr["end"]
    x0 = max(0, k - 70)
    x1 = min(len(df) - 1, end + 14)
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    fig = plt.figure(figsize=(16, 8.6), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[3.2, 1], wspace=0.12, hspace=0.06,
                          top=0.92, bottom=0.14)
    ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, len(d)); bnd["spans"] = []
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    c_all = df["Close"].values.astype(float)
    ax.plot(xs, XM.ema(c_all[:x1 + 1], 12)[x0:x1 + 1], color=PURPLE, lw=1.3, zorder=6)
    lo = min(float(np.nanmin(d["Low"].values)), min(y for _j, y in tr["steps"][1:]) if len(tr["steps"]) > 1 else tr["stop"])
    hi = float(np.nanmax(d["High"].values))
    if tr.get("target"):
        hi = max(hi, min(tr["target"], hi * 1.08))
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.50 * rng, hi + 0.12 * rng)
    pad_x = max(18, int(0.16 * len(d)))
    ax.set_xlim(-1, len(d) + pad_x)
    plt.setp(ax.get_xticklabels(), visible=False)
    # the stop as it moved, the average fill, the old high
    steps = tr["steps"] + [(end, tr["steps"][-1][1])]
    for q, ((j0, y0), (j1, _y)) in enumerate(zip(steps, steps[1:])):
        ax.plot([max(j0, x0) - x0, min(j1, x1) - x0], [y0, y0], color=RED, lw=1.0 if q == 0 else 1.6,
                ls=":" if q == 0 else "--", alpha=0.55 if q == 0 else 1.0, zorder=7)
    ax.hlines(tr["entry"], k - x0, len(d) - 1, colors="#e6e9ee", lw=1.1, ls=":", zorder=8)
    if tr.get("target") and tr["target"] <= hi + 0.1 * rng:
        ax.hlines(tr["target"], 0, len(d) - 1, colors=BLUE, lw=1.1, ls="-.", zorder=6)
        an0 = ax.annotate("the old high", (len(d) - 1, tr["target"]), xytext=(5, 0), textcoords="offset points",
                          ha="left", va="center", color=BLUE, fontsize=8, zorder=20)
        PR.keep_inside(ax, an0)

    def lane(frac):
        return lo - frac * rng

    def peg(x, y_bar, y_lane, colr, marker, label):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=0.7, ls=":", alpha=0.6, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=130, color=colr, edgecolor="#ffffff", lw=0.8, zorder=13)
        if label:
            an = ax.annotate(label, (x, y_lane), xytext=(0, -10), textcoords="offset points", ha="center", va="top",
                             color=colr, fontsize=8.5, weight="bold", zorder=20)
            PR.keep_inside(ax, an)
    fb, fx = tr["fill_bars"], tr["fills"]
    for i_, (b_, px_) in enumerate(zip(fb, fx)):
        peg(b_ - x0, px_, lane(0.08 + 0.07 * i_), GREEN, "^",
            ("buy at the touch of 30" if len(fx) == 1 else "bought at 30, again at 20") if i_ == len(fx) - 1 else None)
    if tr["half_at"] is not None:
        peg(tr["half_at"] - x0, tr["half_px"], lane(0.08 + 0.07 * len(fx) + 0.10), AMBER, "o", "half off at the 12 EMA")
    peg(end - x0, tr["exit_px"], lane(0.08 + 0.07 * len(fx) + 0.24), "#e6e9ee", "X", "out %+.2fR" % tr["R"])
    ax.set_title("%s hourly   first oversold after a run of %.0f daily bars   risk %.2f%%  ->  %+.2f%%  (%+.2fR)" % (
        sym, tr["run"], tr["risk_pct"], tr["pct"], tr["R"]), color="#e6e9ee", fontsize=11, loc="left", pad=8)
    # the RSI under it: the 30 line is the trigger
    axr = fig.add_subplot(gs[1, 0], sharex=ax)
    axr.set_facecolor(DARK)
    rsi_all = IND.rsi(c_all[:x1 + 1], 14)[x0:x1 + 1]
    axr.plot(xs, rsi_all, color="#e6e9ee", lw=1.1)
    axr.axhline(30, color=GREEN, lw=0.9, ls="--"); axr.axhline(70, color=RED, lw=0.9, ls="--")
    axr.set_ylim(5, 95); axr.set_yticks([30, 50, 70])
    axr.tick_params(colors=DIM, labelsize=7)
    for sp in axr.spines.values():
        sp.set_color("#252a33")
    axr.grid(color="#1a1e25", lw=0.5)
    step_ = max(len(d) // 7, 1)
    axr.set_xticks(xs[::step_]); axr.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    axr.set_ylabel("RSI 14", color=DIM, fontsize=8)
    panels = [(ax, d)]
    # the daily beside it: the run, the old high, the daily 12 EMA
    t_now = df.index[k]
    end_d = int(sdf.index.searchsorted(t_now.normalize(), side="right"))
    pos = max(0, end_d - 80); stop_d = min(len(sdf), end_d + 30)
    if stop_d - pos >= 20:
        axd = fig.add_subplot(gs[:, 1])
        hb = CK.bundle(sdf, pos, stop_d - pos); hb["spans"] = []
        CK.render(axd, hb, "", "%Y-%m-%d")
        e12 = XM.ema(sdf["Close"].values.astype(float)[:stop_d], 12)[pos:stop_d]
        axd.plot(np.arange(len(e12)), e12, color=PURPLE, lw=1.5, zorder=6)
        ylo = float(np.nanmin(sdf["Low"].values[pos:stop_d])); yhi = float(np.nanmax(sdf["High"].values[pos:stop_d]))
        yr = max(yhi - ylo, 1e-9)
        axd.set_ylim(max(0, ylo - 0.12 * yr), yhi + 0.12 * yr)
        axd.set_xlim(-1, stop_d - pos + 2)
        axd.axvline(end_d - pos - 0.5, color=DIM, lw=0.9, ls=":", zorder=4)
        axd.set_title("the daily: the run, and its 12 EMA (purple)", loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axd.get_xticklabels(), fontsize=6)
        panels.append((axd, hb["d"]))
    fig.text(0.045, 0.080, "green arrows = bought inside the candle as hourly RSI touched 30 (and 20)    "
             "white dotted = the average paid    orange = half sold when the bounce reached the hourly 12 EMA (purple)",
             color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.048, "red dotted = NO STOP yet (a wide disaster line only)    "
             "red dashed = the stop under the low of the drop, set the moment the half is sold",
             color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.016, "blue = the old high, where the rest is sold    right = the daily, dotted line is the day of the dip",
             color=DIM, fontsize=8.5, ha="left")
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def _one(args):
    try:
        return trades_for(*args), []
    except Exception as ex:
        return [], ["%s %s: %s" % (args[1], args[0], ex)]


def _draw(args):
    sym, kind, picks = args
    try:
        frames = S.frames_for(sym, kind)
        frames = {k_: v for k_, v in frames.items() if k_ in ("1h", "1d")}
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        out = []
        for tr in picks:
            png = "%s_%s_%d.png" % (kind, sym, tr["k"])
            probs = draw(sym, frames["1h"], frames["1d"], tr, os.path.join(OUT, png))
            out.append(dict(tr, png=png, problems=probs))
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
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in T.SUSPECT]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, names, chunksize=4):
            rows += got; errs += err
    print("  %d trades (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    same = os.path.join(OUT, "index_round1.json")
    if "--same" in sys.argv and os.path.exists(same):
        want = {(c_["kind"], c_["sym"], c_["k"]) for c_ in json.load(open(same))["charts"]}
        picks = [r for r in rows if (r["kind"], r["sym"], r["k"]) in want]     # the SAME 16 he graded, new stop
    else:
        rng = np.random.default_rng(20260921)
        wins = [r for r in rows if r["R"] > 0.15]
        losses = [r for r in rows if r["R"] <= -0.15]
        picks = ([wins[i] for i in rng.choice(len(wins), 8, replace=False)]
                 + [losses[i] for i in rng.choice(len(losses), 8, replace=False)])
    by = {}
    for tr in picks:
        by.setdefault((tr["sym"], tr["kind"]), []).append(tr)
    drawn, derr = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by))) as ex:
        for got, err in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got; derr += err
    drawn.sort(key=lambda x: -x["R"])
    for i, tr in enumerate(drawn, 1):
        tr["n"] = i
    keep = {d_["png"] for d_ in drawn} | {"index.json", "index_round1.json"}
    for f in os.listdir(OUT):
        if f not in keep:
            os.remove(os.path.join(OUT, f))
    pct = np.array([r["pct"] for r in rows]); R_ = np.array([r["R"] for r in rows])
    stats = dict(n=len(rows), avg_pct=float(pct.mean()), middle_pct=float(np.median(pct)), won=float((pct > 0).mean()),
                 avg_R=float(R_.mean()), half_taken=float(np.mean([r["half_at"] is not None for r in rows])),
                 reached_high=float(np.mean([r["how"] == "the rest reached the old high" for r in rows])),
                 two_fills=float(np.mean([len(r["fills"]) > 1 for r in rows])),
                 median_risk=float(np.median([r["risk_pct"] for r in rows])))
    slim = [{k_: v for k_, v in d_.items() if k_ != "steps"} for d_ in drawn]
    json.dump(dict(stats=stats, charts=slim), open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d_ in drawn if d_["problems"]), time.time() - t0))
    print("  stats:", {k_: round(v, 3) for k_, v in stats.items()})
    for d_ in drawn:
        print("    #%-2d %-6s %+6.2fR %+7.2f%%  risk %.2f%%  %-32s %s" % (
            d_["n"], d_["sym"], d_["R"], d_["pct"], d_["risk_pct"], d_["how"], d_["problems"] or ""))
    for e_ in (errs + derr)[:8]:
        print("  " + e_)


if __name__ == "__main__":
    main()
