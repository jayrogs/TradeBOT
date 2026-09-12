"""pics_eqrisk.py -- the picture of why the losers are bigger than the winners (2026-09-11, his words: "no show me
on a chart, not with word ... i need visuals").

One summary picture: every trade's stop distance against its target distance, and the money side by side.
Then real trades drawn: entry, stop, target, the partial, and where it ended -- winners and losers.

The trade drawn is the one that won 59%: EQ lined up with the hourly, buy the next open, stop at the hourly higher
low, half off at 1x the risk, sell the rest at the hourly's last swing high.

    pythonw pics_eqrisk.py --procs 20 --log logs\\pics_eqrisk.log
Writes validation/eq_risk/*.png + eq_risk_index.json  ->  /eqrisk
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
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_direction as ED         # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402
import exit_managers as XM        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
BLUE, PURPLE = "#5aa9ff", "#b48cff"
GREEN, RED, AMBER = "#3ddc97", "#ff5c72", "#ffb84d"
OUT = os.path.join("validation", "eq_risk")
TFS = ["5m", "15m"]
BPH = {"5m": 12, "15m": 4}
MAX_HOURS = 48


def trades_for(sym, kind):
    """Every lined-up EQ trade for one name, with the levels and what happened, ready to draw."""
    frames = S.frames_for(sym, kind)
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    got = []
    for tf in TFS:
        df = frames.get(tf)
        hdf = frames.get("1h")
        if df is None or len(df) < 300 or hdf is None or len(hdf) < 60:
            continue
        o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        n = len(c)
        recs = EC.coils(df, min_gap=3)[3]
        h1lo, h1hi = ED.last_swings(df, tf, frames, "1h")
        al = FR.align(df, tf, hdf, "1h", P._atr(hdf).astype(object))
        h1atr = np.array([np.nan if isinstance(x, str) else float(x) for x in al], dtype=float)
        state = EF.higher_state(df, tf, frames, "1h")
        ev = ER.above12(df, tf, frames, "1h")[1]
        for r in recs:
            if not r["tradeable"] or r["born"] < 60 or r["confirm"] + 2 >= n:
                continue
            e = r["confirm"] + 1
            up = str(state[e]) == "up" or (np.isfinite(ev[e]) and c[e] > ev[e])
            down = str(state[e]) == "down" or (np.isfinite(ev[e]) and c[e] < ev[e])
            if up == down:
                continue
            side = 1 if up else -1
            lows_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "low"]
            highs_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "high"]
            ha, hl = h1atr[e], (h1lo[e] if side > 0 else h1hi[e])
            if not (np.isfinite(ha) and ha > 0 and np.isfinite(hl)):
                continue
            line = lows_[-1] if side > 0 else highs_[-1]
            near = h1lo[e] if side > 0 else h1hi[e]
            lined = (np.isfinite(ev[e]) and abs(line - ev[e]) <= 0.5 * ha) or \
                    (np.isfinite(near) and ((side > 0 and near < line <= near + ha) or
                                            (side < 0 and near - ha <= line < near)))
            if not lined:
                continue
            entry = o[e]
            far = highs_[-1] if side > 0 else lows_[-1]
            tol = P.SAME_LEVEL_ATR * P._atr(df)[r["confirm"]]
            eq_stop = (lows_[-1] - tol) if side > 0 else (highs_[-1] + tol)
            if (side > 0 and (entry >= far or entry <= eq_stop)) or (side < 0 and (entry <= far or entry >= eq_stop)):
                continue
            h1_stop = hl - 0.15 * ha if side > 0 else hl + 0.15 * ha
            both = [x for x in (eq_stop, h1_stop) if np.isfinite(x) and
                    ((side > 0 and x < entry) or (side < 0 and x > entry))]
            if not both:
                continue
            stop = max(both) if side > 0 else min(both)
            risk = abs(entry - stop)
            sw = h1hi[e] if side > 0 else h1lo[e]
            target = sw if (np.isfinite(sw) and ((side > 0 and sw > entry) or (side < 0 and sw < entry))) \
                else entry + side * 2 * risk
            if abs(target - entry) < abs(entry - stop):
                continue                              # the target was closer than the stop: not a trade
            cut = entry + side * risk
            last = min(n - 1, e + MAX_HOURS * BPH[tf])
            share, pnl, took_at, end_at, how = 1.0, 0.0, None, last, "time ran out"
            for j in range(e, last + 1):
                if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
                    pnl += share * side * (stop - entry) / entry
                    end_at, how, share = j, ("rest stopped out" if took_at else "stopped out"), 0.0
                    break
                if took_at is None and ((side > 0 and h[j] >= cut) or (side < 0 and l[j] <= cut)):
                    pnl += 0.5 * side * (cut - entry) / entry
                    share, took_at = 0.5, j
                if (side > 0 and h[j] >= target) or (side < 0 and l[j] <= target):
                    pnl += share * side * (target - entry) / entry
                    end_at, how, share = j, "sold into the move", 0.0
                    break
            if share > 0:
                pnl += share * side * (c[end_at] - entry) / entry
            got.append(dict(sym=sym, kind=kind, tf=tf, side=int(side), born=int(r["born"]), confirm=int(r["confirm"]),
                            shape=[(int(j_), float(p_), kd_) for j_, p_, kd_, lb_ in r["shape"]],
                            e=int(e), entry=float(entry), stop=float(stop), target=float(target), cut=float(cut),
                            took_at=None if took_at is None else int(took_at), end_at=int(end_at), how=how,
                            pct=float(pnl * 100), risk_pct=float(risk / entry * 100),
                            target_pct=float(abs(target - entry) / entry * 100),
                            t=str(df.index[e])))
    return got, frames


def draw_trade(sym, tf, df, hdf, tr, path):
    x0 = max(0, tr["born"] - 40)
    x1 = min(len(df) - 1, tr["end_at"] + 12)
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    fig = plt.figure(figsize=(16, 7.6), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.5, 1], wspace=0.11, top=0.90, bottom=0.11)
    ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, len(d))
    bnd["spans"] = []
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    ax.plot(xs, XM.ema(df["Close"].values.astype(float)[:x1 + 1], 12)[x0:x1 + 1], color=PURPLE, lw=1.4, zorder=6)
    e, end = tr["e"] - x0, tr["end_at"] - x0

    def steps(pts):                                  # the EQ as he draws it: flat lines to the next pivot
        y = np.full(len(d), np.nan)
        for m_, (j_, pr_) in enumerate(pts):
            j2 = pts[m_ + 1][0] if m_ + 1 < len(pts) else tr["confirm"]
            a_, b_ = max(j_, x0), min(j2, tr["confirm"])
            if b_ >= a_:
                y[a_ - x0:b_ - x0 + 1] = pr_
        return y
    sh = tr.get("shape") or []
    ax.step(xs, steps([(j_, p_) for j_, p_, kd_ in sh if kd_ == "low"]), where="post", color=BLUE, lw=2.2, zorder=8)
    ax.step(xs, steps([(j_, p_) for j_, p_, kd_ in sh if kd_ == "high"]), where="post", color=BLUE, lw=2.2, zorder=8)
    ax.axvline(tr["confirm"] - x0 + 0.5, color=DIM, lw=0.9, ls=":", zorder=4)
    ax.hlines(tr["entry"], e, len(d) - 1, colors=DIM, lw=1.2, linestyles=":", zorder=7)
    ax.hlines(tr["stop"], e, end, colors=RED, lw=1.6, linestyles="--", zorder=7)
    ax.hlines(tr["target"], e, end, colors=GREEN, lw=1.6, linestyles="--", zorder=7)
    lo = min(float(np.nanmin(d["Low"].values)), tr["stop"], tr["target"])
    hi = max(float(np.nanmax(d["High"].values)), tr["stop"], tr["target"])
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.18 * rng, hi + 0.18 * rng)
    ax.set_xlim(-1, len(d) + 2)
    mk = "^" if tr["side"] > 0 else "v"
    ax.scatter([e], [tr["entry"] - tr["side"] * 0.10 * rng], marker=mk, s=150,
               color=GREEN if tr["side"] > 0 else RED, zorder=9)
    if tr["took_at"] is not None:
        ax.scatter([tr["took_at"] - x0], [tr["cut"]], marker="o", s=70, facecolor=DARK, edgecolor=AMBER, lw=1.8, zorder=9)
    ax.scatter([end], [tr["stop"] if "stopped" in tr["how"] else tr["target"] if "sold" in tr["how"]
                       else float(df["Close"].values[tr["end_at"]])], marker="x", s=110, color="#e6e9ee", lw=2, zorder=9)
    step_ = max(len(d) // 7, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    ax.set_title("%s %s %s   EQ blue, risk %.2f%% red, target %.2f%% green  ->  %+.2f%%" % (
        sym, tf, "long" if tr["side"] > 0 else "short", tr["risk_pct"], tr["target_pct"], tr["pct"]),
        color="#e6e9ee", fontsize=11, loc="left", pad=8)
    panels = [(ax, d)]
    t_now = df.index[tr["e"]]
    end_h = int(hdf.index.searchsorted(t_now, side="right"))
    pos, stop_h = max(0, end_h - 60), min(len(hdf), end_h + 24)
    if stop_h - pos >= 20:
        axh = fig.add_subplot(gs[0, 1])
        hb = CK.bundle(hdf, pos, stop_h - pos)
        hb["spans"] = []
        CK.render(axh, hb, "", "%m-%d %H:%M")
        e12 = XM.ema(hdf["Close"].values.astype(float)[:stop_h], 12)[pos:stop_h]
        axh.plot(np.arange(len(e12)), e12, color=PURPLE, lw=1.5, zorder=6)
        axh.hlines(tr["stop"], 0, stop_h - pos - 1, colors=RED, lw=1.4, linestyles="--", zorder=7)
        axh.hlines(tr["target"], 0, stop_h - pos - 1, colors=GREEN, lw=1.4, linestyles="--", zorder=7)
        ylo = min(float(np.nanmin(hdf["Low"].values[pos:stop_h])), tr["stop"])
        yhi = max(float(np.nanmax(hdf["High"].values[pos:stop_h])), tr["target"])
        yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(max(0, ylo - 0.15 * yr), yhi + 0.15 * yr)
        axh.set_xlim(-1, stop_h - pos + 2)
        axh.axvline(end_h - pos - 0.5, color=DIM, lw=0.9, ls=":", zorder=4)
        axh.set_title("the hourly", loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
        panels.append((axh, hb["d"]))
    import pics_ride as PR
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def summary_png(rows, path):
    risk = np.array([r["risk_pct"] for r in rows])
    tgt = np.array([r["target_pct"] for r in rows])
    pct = np.array([r["pct"] for r in rows])
    win = pct > 0
    fig = plt.figure(figsize=(15, 6.4), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.22, top=0.86, bottom=0.13, left=0.07, right=0.97)
    ax = fig.add_subplot(gs[0, 0])
    ax.set_facecolor(DARK)
    cap = float(np.percentile(np.r_[risk, tgt], 97))
    ax.scatter(np.clip(risk[~win], 0, cap), np.clip(tgt[~win], 0, cap), s=9, color=RED, alpha=0.45, lw=0)
    ax.scatter(np.clip(risk[win], 0, cap), np.clip(tgt[win], 0, cap), s=9, color=GREEN, alpha=0.45, lw=0)
    ax.plot([0, cap], [0, cap], color="#e6e9ee", lw=1.4, ls="--")
    ax.plot([0, cap / 2], [0, cap], color=AMBER, lw=1.4, ls="--")
    ax.text(cap * 0.97, cap * 0.97, "target = risk", color="#e6e9ee", fontsize=9, ha="right", va="bottom")
    ax.text(cap * 0.50, cap * 0.99, "target = 2x risk", color=AMBER, fontsize=9, ha="right", va="bottom")
    ax.text(cap * 0.97, cap * 0.06, "%d%% of trades sit UNDER the white line:\ntarget closer than the stop" %
            round(100 * np.mean(tgt < risk)), color=DIM, fontsize=10, ha="right", va="bottom")
    ax.set_xlim(0, cap); ax.set_ylim(0, cap)
    ax.set_xlabel("how far the stop sits from the entry (%)", color=DIM, fontsize=10)
    ax.set_ylabel("how far the target sits (%)", color=DIM, fontsize=10)
    ax.tick_params(colors=DIM, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#252a33")
    ax.grid(color="#1a1e25", lw=0.6)
    ax.set_title("every trade: what it risked against what it aimed for", color="#e6e9ee", fontsize=12, loc="left", pad=8)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(DARK)
    aw, al_ = float(pct[win].mean()), float(pct[~win].mean())
    ax2.bar([0, 1], [aw, al_], color=[GREEN, RED], width=0.55)
    ax2.text(0, aw + 0.06, "+%.2f%%" % aw, color=GREEN, ha="center", fontsize=13)
    ax2.text(1, al_ - 0.06, "%.2f%%" % al_, color=RED, ha="center", va="top", fontsize=13)
    ax2.set_xticks([0, 1]); ax2.set_xticklabels(["the average win\n%d%% of trades" % round(100 * win.mean()),
                                                 "the average loss\n%d%% of trades" % round(100 * (~win).mean())],
                                                color=DIM, fontsize=10)
    ax2.axhline(0, color="#252a33", lw=1)
    ax2.set_ylim(min(al_ * 1.45, -0.5), max(aw * 1.45, 0.5))
    ax2.tick_params(colors=DIM, labelsize=8)
    for sp in ax2.spines.values():
        sp.set_color("#252a33")
    ax2.set_title("the wins are %s than the losses" % ("bigger" if aw > -al_ else "smaller"),
                  color="#e6e9ee", fontsize=12, loc="left", pad=8)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def _one(args):
    sym, kind = args
    try:
        got, _ = trades_for(sym, kind)
        return got, []
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]


def _draw(args):
    sym, kind, picks = args
    try:
        frames = S.frames_for(sym, kind)
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        out, errs = [], []
        for tr in picks:
            png = "%s_%s_%s_%d.png" % (kind, sym, tr["tf"], tr["confirm"])
            probs = draw_trade(sym, tr["tf"], frames[tr["tf"]], frames["1h"], tr, os.path.join(OUT, png))
            out.append(dict(tr, png=png, problems=probs))
        return out, errs
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
            rows += got
            errs += err
    print("  %d trades (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    summary_png(rows, os.path.join(OUT, "summary.png"))
    rng = np.random.default_rng(20260911)
    wins = [r for r in rows if r["pct"] > 0]
    losses = [r for r in rows if r["pct"] <= 0]
    picks = [wins[i] for i in rng.choice(len(wins), 6, replace=False)] + \
            [losses[i] for i in rng.choice(len(losses), 6, replace=False)]
    by_name = {}
    for tr in picks:
        by_name.setdefault((tr["sym"], tr["kind"]), []).append(tr)
    drawn, derr = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by_name))) as ex:
        for got, err in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by_name.items()], chunksize=1):
            drawn += got
            derr += err
    drawn.sort(key=lambda x: -x["pct"])
    for k_i, tr in enumerate(drawn, 1):
        tr["n"] = k_i
    stats = dict(n=len(rows), won=float(np.mean([r["pct"] > 0 for r in rows])),
                 avg_win=float(np.mean([r["pct"] for r in rows if r["pct"] > 0])),
                 avg_loss=float(np.mean([r["pct"] for r in rows if r["pct"] <= 0])),
                 median_risk=float(np.median([r["risk_pct"] for r in rows])),
                 median_target=float(np.median([r["target_pct"] for r in rows])),
                 share_target_under_risk=float(np.mean([r["target_pct"] < r["risk_pct"] for r in rows])),
                 avg=float(np.mean([r["pct"] for r in rows])))
    json.dump(dict(stats=stats, charts=drawn), open(os.path.join(OUT, "eq_risk_index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d in drawn if d["problems"]), time.time() - t0))
    for d in drawn:
        print("    #%-2d %-6s %-3s %+7.2f%%  risk %.2f%%  target %.2f%%  %-18s %s" % (
            d["n"], d["sym"], d["tf"], d["pct"], d["risk_pct"], d["target_pct"], d["how"], d["problems"] or ""))
    for e in (errs + derr)[:10]:
        print("  " + e)


if __name__ == "__main__":
    main()
