"""pics_cases.py -- backburner CASES for the owner to judge: where his method
lost, where the selective filter's picks worked (and lost), each with the
higher timeframes beside the campaign so the shape of the bigger picture is
visible.

    python pics_cases.py            # writes validation/case_NN.png + cases_index.json (page: /cases)

Cases come from the study's event table (validation/backburner_events.csv.gz):
15m and 5m, stocks + ETFs, hot names (up 10%+ on the day or 20%+ in 3 days).
Each campaign is re-walked with the study's rules so the drawn buys, bounce,
partial and exit are the scored ones. Left: the campaign chart (candles,
12 EMA, numbered buys, bounce, partial, exit, the stop). Right: the two
higher timeframes through chartkit (trend colours, pivots, 12 EMA) with the
campaign's time marked.
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "studies")
import backburner_study as S      # noqa: E402  the scored rules
import chartkit as CK             # noqa: E402
import indicators as IND          # noqa: E402
import rider                      # noqa: E402
import rider_lab as RL            # noqa: E402
import structure as ST            # noqa: E402

warnings.filterwarnings("ignore")
OUT = "validation"
DARK, DIM = "#0d0f12", "#8b93a1"
COSTS = S.CLASS_COST
PLAIN = {"bad": "stop hit", "time": "time ran out", "session end": "the day ended"}   # the study's exit codes, in words
HIGHER = {"5m": ("15m", "1h"), "15m": ("1h", "4h"), "1h": ("4h", "1d"), "4h": ("1d", "1w"),
          "12h": ("1d", "1w"), "1d": ("1w",), "1w": ()}


def walk(df, i):
    """Re-walk one campaign from its first print bar i (the study's rules).
    Returns a dict of bars/prices for drawing, or None if unresolved."""
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    r = IND.rsi_parts(c)[0]
    ema = rider.ema(c)
    a14 = S.atr(h, l, c)
    own = ST.states(df, causal=True)
    v = dict(c=c, lo=l, hi=h, e=ema, hold=(c >= ema), o=o,
             atr=np.where(np.isfinite(a14), a14, np.inf), n=n)
    fills = [(i + 1, o[i + 1])]
    k3 = min(i, 3 * S.BARS_DAY[TF])
    run_up = max(0.0, c[i] / c[i - k3] - 1.0) if k3 > 0 else 0.0
    stop_at = lambda avg, j: avg - max(S.STOP_FRAC * run_up * avg, S.STOP_ATR * a14[j])   # the study's stop
    j, ended = i + 1, None
    while j < n - 1:
        avg = float(np.mean([p for _, p in fills]))
        if r[j] > S.BOUNCE:
            ended = "bounce"; break
        if c[j] < stop_at(avg, j):
            ended = "bad"; break
        if j - i >= S.CAP_DAYS * S.BARS_DAY[TF]:
            ended = "cap"; break
        if r[j] <= S.OS and len(fills) < S.MAX_UNITS:
            fills.append((j + 1, o[j + 1]))
        j += 1
    if ended is None:
        return None
    avg = float(np.mean([p for _, p in fills]))
    out = dict(fills=fills, avg=avg, end_bar=j, ended=ended, stop=stop_at(avg, j), run_up=run_up,
               low=float(l[i + 1:j + 1].min()), rsi=r, ema=ema)
    if ended != "bounce":
        out.update(exit=(j + 1, o[j + 1], ended), part=0.0, ret=o[j + 1] / avg - 1)
        return out
    low = out["low"]; P = o[j + 1]
    part = min(1.0, max(0.0, (avg - low) / (P - low))) if (P > avg and P > low) else 0.0
    lowbreak = next(((k, o[k + 1], "low broke") for k in range(j + 1, n - 1) if c[k] < low), None)
    # the standard ride: hold until a bar closes under the last higher low
    lpiv, lcis = S.low_pivots(df)
    rx = S.hl_break_exit(c, o, lpiv, lcis, i + 1, j, low, n)
    cap = S.CAP_DAYS * S.BARS_DAY[TF]
    capx = (j + 1 + cap, o[min(n - 1, j + 1 + cap)], "cap") if j + 1 + cap < n - 1 else None
    cs = [x for x in (lowbreak, rx, capx) if x is not None]
    if not cs:
        return None
    k, px, why = min(cs, key=lambda x: x[0])
    out.update(bounce=(j + 1, P), part=part, exit=(k, px, why),
               ret=(part * P + (1 - part) * px) / avg - 1)
    return out


BOX = dict(boxstyle="round,pad=0.25", fc=DARK, ec="none", alpha=0.85)


def _chrome(ax):
    ax.set_facecolor(DARK); ax.tick_params(colors=DIM, labelsize=7)
    for s in ax.spines.values(): s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)


def candles(ax, d, ema):
    """Fat candles: bodies as bars 0.72 wide in bar units, so they scale
    with the window instead of staying hairline ("candle quality is shit")."""
    o = d["Open"].values; hi = d["High"].values; lo = d["Low"].values; cc = d["Close"].values
    x = np.arange(len(d))
    up = cc >= o
    col = np.where(up, "#3ddc97", "#ff5c72")
    ax.vlines(x, lo, hi, color=col, lw=1.1, zorder=2)
    body_lo = np.minimum(o, cc); body_hi = np.maximum(o, cc)
    ax.bar(x, np.maximum(body_hi - body_lo, (hi - lo).mean() * 0.02), bottom=body_lo, width=0.72,
           color=col, edgecolor=col, linewidth=0.4, zorder=3)
    ax.plot(x, ema, color="#c9a35d", lw=1.4, zorder=4)
    ax.set_xlim(-1, len(d)); _chrome(ax)


def render(n, sym, kind, tf, t, frames, verdict, tag, path=None):
    global TF
    TF = tf
    df = frames[tf]
    i = int(df.index.get_indexer([pd.Timestamp(t)])[0])
    if i < 0:
        return None
    w = walk(df, i)
    if w is None:
        return None
    # main panel: the ENTRY zoomed (40 bars before the first buy to 60 past
    # the bounce, or the exit if earlier); the whole ride in a strip below
    end_zoom = w["bounce"][0] + 60 if "bounce" in w else w["exit"][0] + 20
    x0 = max(0, i - 40); x1 = min(len(df) - 1, min(end_zoom, w["exit"][0] + 20), x0 + 160)
    d = df.iloc[x0:x1 + 1]
    fig = plt.figure(figsize=(18, 10), dpi=105); fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(4, 2, width_ratios=[1.35, 1], height_ratios=[4, 1.1, 1.4, 0.9], hspace=0.30, wspace=0.16)
    ax = fig.add_subplot(gs[0, 0]); ar = fig.add_subplot(gs[1, 0], sharex=ax); ax2 = fig.add_subplot(gs[2:4, 0])
    candles(ax, d, w["ema"][x0:x1 + 1])
    plt.setp(ax.get_xticklabels(), visible=False)
    # NOTHING sits on the candles (CLAUDE.md rule 11): every marker and label lives
    # in an empty lane above or below price, joined to its bar by a thin dotted line.
    lo_all = float(np.nanmin(d["Low"].values)); hi_all = float(np.nanmax(d["High"].values))
    span = max(hi_all - lo_all, 1e-9)
    lane_up = hi_all + span * 0.22; lane_dn = lo_all - span * 0.18
    ax.set_ylim(lo_all - span * 0.50, hi_all + span * 0.48)
    ax.set_xlim(-1, len(d) + 50)             # room on the right for the level names
    lows_v = d["Low"].values; highs_v = d["High"].values

    def peg(x, y_bar, y_lane, colr, marker, size, label=None, dy=9, side=0, fs=8.5, weight="bold"):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=.7, ls=":", alpha=.55, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=size, color=colr, edgecolor="#ffffff", lw=.8, zorder=13)
        if label:
            ha = "center" if side == 0 else ("right" if side < 0 else "left")
            an = ax.annotate(label, (x, y_lane), xytext=(9 * side, dy), textcoords="offset points", ha=ha,
                             va="bottom" if dy > 0 else "top", color=colr, fontsize=fs, weight=weight, zorder=20)
            from pics_ride import keep_inside
            keep_inside(ax, an)

    # the buys: numbered dots in the lower lane. Buys on neighbouring bars alternate
    # between two rows so the numbers never touch.
    lane_dn2 = lane_dn - span * 0.09
    last_x = -99; row = 0
    shown = [(k, b - x0) for k, (b, px) in enumerate(w["fills"], 1) if 0 <= b - x0 <= x1 - x0]
    for k, x in shown:
        row = 1 - row if x - last_x < 7 else 0
        peg(x, lows_v[x], lane_dn2 if row else lane_dn, "#ffb84d", "o", 90, None)
        last_x = x
    if shown:
        k0, xa = shown[0]; k1, xz = shown[-1]
        label = ("buy %d" % k0) if len(shown) == 1 else ("buys %d to %d, %d bars apart" % (k0, k1, xz - xa))
        ax.annotate(label, ((xa + xz) / 2, lane_dn2), xytext=(0, -12), textcoords="offset points", ha="center", va="top",
                    color="#ffb84d", fontsize=8.5, weight="bold", zorder=20)
    xr = len(d) + 1                          # level names sit to the RIGHT of the last candle
    y_lo, y_hi = ax.get_ylim()

    def level_text(y, txt, colr, va):
        # a level that sits off the chart gets its name pinned at the edge, marked "(below)" / "(above)"
        if y < y_lo + 0.02 * (y_hi - y_lo):
            y, txt, va = y_lo + 0.02 * (y_hi - y_lo), txt + " (below)", "bottom"
        elif y > y_hi - 0.02 * (y_hi - y_lo):
            y, txt, va = y_hi - 0.02 * (y_hi - y_lo), txt + " (above)", "top"
        t = ax.text(xr, y, txt, color=colr, fontsize=8, va=va, ha="left", zorder=20)
        # a long name ("stop: half the 38% run-up (below)") ran past the plot's right edge: measure it, and
        # if it does not fit in the margin, break it onto two lines at the colon
        rend = ax.figure.canvas.get_renderer()
        if t.get_window_extent(rend).x1 > ax.get_window_extent(rend).x1 - 3 and ": " in txt:
            t.set_text(txt.replace(": ", ":\n", 1))

    ax.axhline(w["avg"], color="#ffb84d", lw=1.0, ls="--", alpha=.9)
    level_text(w["avg"], "average buy", "#ffb84d", "bottom")
    ax.axhline(w["stop"], color="#ff5c72", lw=.8, ls=":", alpha=.8)
    level_text(w["stop"], "stop: 3 bars under avg" if w["run_up"] < 0.06 else "stop: half the %.0f%% run-up" % (100 * w["run_up"]),
               "#ff5c72", "top")
    xb = None
    if "bounce" in w:
        xb = w["bounce"][0] - x0
        sold = ("bounce: sold %.0f%%, the low is now breakeven" % (100 * w["part"])) if w["part"] >= 0.01 \
            else "bounce: kept it all (the low is already breakeven)"
        if 0 <= xb <= x1 - x0:
            peg(xb, highs_v[xb], lane_up, "#5aa9ff", "o", 110, sold, dy=9)
        ax.axhline(w["low"], color="#5aa9ff", lw=.8, ls="--", alpha=.7)
        if abs(w["low"] - w["avg"]) > 0.004 * w["avg"] and abs(w["low"] - w["stop"]) > 0.02 * span:
            level_text(w["low"], "breakeven stop (the low)", "#5aa9ff", "top")
    col = "#3ddc97" if w["ret"] > 0 else "#ff5c72"
    xe = w["exit"][0] - x0
    if 0 <= xe <= x1 - x0:
        # the bounce note sits above the upper lane, the exit note below it: they never meet
        peg(xe, highs_v[xe], lane_up, col, "X", 150, "out: %s" % PLAIN.get(w["exit"][2], w["exit"][2]), dy=-11)
    xs = np.arange(len(d))
    ar.plot(xs, w["rsi"][x0:x1 + 1], color="#ffb84d", lw=1.2)
    ar.axhline(30, color="#ff5c72", lw=.9, ls="--"); ar.axhline(50, color="#3ddc97", lw=.6, ls=":")
    ar.set_ylim(0, 100); ar.set_yticks([30, 50, 70]); _chrome(ar)
    step = max(len(d) // 7, 1)
    ar.set_xticks(xs[::step]); ar.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step]], fontsize=6.5)
    # the whole trade, first buy to exit, as a strip
    r0 = max(0, w["fills"][0][0] - 10); r1 = min(len(df) - 1, w["exit"][0] + 15)
    rd = df.iloc[r0:r1 + 1]
    rx = np.arange(len(rd))
    ax2.plot(rx, rd["Close"].values, color="#c9ced6", lw=1.0)
    ax2.plot(rx, w["ema"][r0:r1 + 1], color="#c9a35d", lw=1.0)
    ax2.axhline(w["avg"], color="#ffb84d", lw=.9, ls="--")
    for k, (b, px) in enumerate(w["fills"], 1):
        ax2.scatter([b - r0], [px], s=70, color="#ffb84d", edgecolor="#ffffff", lw=.6, zorder=6)
    if "bounce" in w:
        ax2.scatter([w["bounce"][0] - r0], [w["bounce"][1]], s=70, color="#5aa9ff", edgecolor="#ffffff", lw=.6, zorder=6)
        ax2.axhline(w["low"], color="#5aa9ff", lw=.8, ls="--", alpha=.7)
    ax2.scatter([w["exit"][0] - r0], [w["exit"][1]], marker="X", s=120, color=col, edgecolor="#ffffff", zorder=7)
    ax2.set_xlim(-1, len(rd)); _chrome(ax2)
    step2 = max(len(rd) // 7, 1)
    ax2.set_xticks(rx[::step2]); ax2.set_xticklabels([q.strftime("%m-%d %H:%M") for q in rd.index[::step2]], fontsize=6.5)
    ax2.set_title("the whole trade: %d bars, out: %s, %+.1f%%" % (w["exit"][0] - w["fills"][0][0], PLAIN.get(w["exit"][2], w["exit"][2]), 100 * (w["ret"] - COSTS.get(kind, 0.0005))),
                  loc="left", color=DIM, fontsize=9, pad=3)
    net = w["ret"] - COSTS.get(kind, 0.0005)
    ax.set_title("%s  %s      %s %+.1f%%      %s" % (sym, tf, "WORKED" if net > 0.005 else "flat" if abs(net) <= 0.005 else "LOST", 100 * net, tag),
                 color="#e6e9ee", fontsize=12, loc="left", pad=8)

    # the higher timeframes, through chartkit, campaign period marked
    t_start, t_end = df.index[w["fills"][0][0]], df.index[w["exit"][0]]
    panel_bars = []
    for row, htf in enumerate(HIGHER.get(tf, ())):
        axh = fig.add_subplot(gs[0, 1]) if row == 0 else fig.add_subplot(gs[1:3, 1])
        hdf = frames.get(htf)
        if hdf is None or len(hdf) < 30:
            axh.set_visible(False); continue
        pos_end = int(hdf.index.searchsorted(t_end)) + 12
        pos = max(0, pos_end - 130); win = min(len(hdf) - pos, 130)
        bnd = CK.bundle(hdf, pos, win)
        CK.render(axh, bnd, "", "%m-%d %H:%M")
        panel_bars.append((axh, bnd["d"]))
        ylo_, yhi_ = axh.get_ylim()
        axh.set_ylim(ylo_ - 0.08 * (yhi_ - ylo_), yhi_ + 0.12 * (yhi_ - ylo_))   # headroom: labels clear of the title and the dates
        sub = hdf.index[pos:pos + win]
        a = int(sub.searchsorted(t_start)); b = int(sub.searchsorted(t_end))
        axh.axvspan(a - .5, b + .5, color="#ffb84d", alpha=0.18, lw=0, zorder=1)
        axh.set_title(htf + "  (the campaign is the amber band)", loc="left", color=DIM, fontsize=9, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
    try:
        import pics_ride as PR
        probs = PR.overlaps(fig, [(ax, d)] + panel_bars)
    except Exception as ex:
        probs = ["could not measure: %s" % ex]
    fig.savefig(path or os.path.join(OUT, "case_%02d.png" % n), facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return dict(n=n, sym=sym, kind=kind, tf=tf, t=str(t), net=float(net), units=len(w["fills"]),
                ended=w["exit"][2], part=float(w["part"]), verdict=verdict, tag=tag, problems=probs)


def _draw(args):
    n, sym, kind, tf, t, verdict, tag = args
    try:
        frames = S.frames_for(sym, kind)
        return render(n, sym, kind, tf, t, frames, verdict, tag), None
    except Exception as ex:
        return None, "%s %s %s: %s" % (sym, tf, t, ex)


def main():
    ev = pd.read_csv(os.path.join(OUT, "backburner_events.csv.gz"), low_memory=False)   # always the current study
    k = pd.read_csv("cache/tier1.csv")
    rank = {s: i for i, s in enumerate(k.sort_values("dollar", ascending=False).symbol.astype(str))}
    d = ev[ev.tf.isin(["15m", "5m"]) & ev.kind.isin(["stock", "etf"])].copy()
    d["hot"] = (d["move"].fillna(0) >= 0.10) | (d["move3"].fillna(0) >= 0.20)
    d = d[d.hot]
    d["liq"] = d["sym"].map(rank).fillna(9999)
    d["rare"] = d["gap_days"].isna() | (d["gap_days"] >= 3)
    d["vol2"] = d["relvol"].fillna(0) >= 1.5
    d["net"] = d["ret_ride"] + 0.002 - 0.0005
    d["select"] = (d["liq"] < 150) & d["vol2"] & d["rare"]
    rng = np.random.default_rng(3)
    picks = []
    for tf, n_lose, n_win, n_selfail in (("15m", 5, 5, 2), ("5m", 3, 3, 1)):
        g = d[d.tf == tf]
        # losers from LIQUID names only: thin names have gappy IEX bars and
        # the point is the method, not the data quality
        lose = g[(g.net < -0.02) & (~g.select) & (g.liq < 300)]
        win = g[(g.net > 0.04) & g.select]
        selfail = g[(g.net < -0.02) & g.select]
        for pool, cnt, verdict in ((lose, n_lose, "your method: lost, filter would have skipped it"),
                                   (win, n_win, "filter pick: worked"),
                                   (selfail, n_selfail, "filter pick: lost")):
            if len(pool) == 0:
                continue
            for _, row in pool.iloc[rng.choice(len(pool), min(cnt, len(pool)), replace=False)].iterrows():
                why = []
                if not row["vol2"]: why.append("volume %.1fx" % (row["relvol"] or 0))
                if not row["rare"]: why.append("oversold %.1f days ago" % row["gap_days"])
                if row["liq"] >= 150: why.append("thin name")
                tag = ("; ".join(why) if why else "hot, liquid, volume %.1fx, first oversold in %s days" % (
                    row["relvol"] or 0, "many" if pd.isna(row["gap_days"]) else "%.0f" % row["gap_days"]))
                picks.append((row["sym"], row["kind"], tf, row["t"], verdict, tag))
    for f in os.listdir(OUT):
        if f.startswith("case_") and f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    import concurrent.futures as cf
    import multiprocessing as mp
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)
    index = []
    jobs = [(n, sym, kind, tf, t, verdict, tag) for n, (sym, kind, tf, t, verdict, tag) in enumerate(picks, 1)]
    with cf.ProcessPoolExecutor(max_workers=max(1, os.cpu_count() or 4)) as ex:
        for row, err in ex.map(_draw, jobs):
            if err:
                print("  " + err, flush=True); continue
            if row:
                index.append(row)
                print("  case_%02d %-6s %-3s %s  %+.1f%%  %s  %s" % (row["n"], row["sym"], row["tf"], row["t"], 100 * row["net"], row["verdict"],
                      ("PROBLEMS: " + "; ".join(row["problems"])) if row["problems"] else "clean"), flush=True)
    index.sort(key=lambda r: r["n"])
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), items=index),
              open(os.path.join(OUT, "cases_index.json"), "w"), indent=1)
    print("  %d cases" % len(index))


if __name__ == "__main__":
    if "--log" in sys.argv:
        sys.stdout = sys.stderr = open(sys.argv[sys.argv.index("--log") + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    main()
