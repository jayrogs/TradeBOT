"""pics_eqmark.py -- 5m / 15m EQs for HIM to mark long / short / skip, drawn BLIND (2026-09-11).

His words: "usually based on if its in an uptrend on higher timeframes like hourly, or if its above the ema12 on
something like the hourly and the eq can make a nice higher low from that for the hourly uptrend to continue".
Every coded version of that came out a coin flip (CLAUDE.md #26l), so the rule gets built from his marks instead.

Each chart stops at the bar the EQ became knowable (its last pivot confirmed): NOTHING after that bar is drawn, so the
break cannot be seen. Left: the 5m/15m chart with the EQ's flat steps. Right: the 1h chart up to the same moment, with its
12 EMA and pivots. The index keeps what happened next (which way it broke, real / fakeout / reversal, the move 20 bars
later) for the reveal after he marks. Picked at random from the focus list: pivots 3+ bars apart, stocks on regular hours.

    pythonw pics_eqmark.py --procs 20 --n 30 --log logs/pics_eqmark.log
Writes validation/eq_mark/*.png + eq_mark_index.json  ->  /eqmark
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
import eq_freeride2 as FR2        # noqa: E402
import eq_direction as ED         # noqa: E402
import exit_managers as XM        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
BLUE, PURPLE = "#5aa9ff", "#b48cff"
OUT = os.path.join("validation", "eq_mark")
TFS = ["5m", "15m"]


def render(sym, tf, df, h1, d1, r, path):
    i = r["confirm"]
    born = r["born"]
    x0 = max(0, born - 40)
    d = df.iloc[x0:i + 1]
    xs = np.arange(len(d))
    fig = plt.figure(figsize=(17, 9.6), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1], wspace=0.12, hspace=0.30, top=0.93, bottom=0.09)
    ax = fig.add_subplot(gs[:, 0])
    bnd = CK.bundle(df, x0, i - x0 + 1)
    bnd["spans"] = [(k_, max(s0, x0) - x0, min(s1, i) - x0) for k_, s0, s1 in ST.spans(df.iloc[:i + 1], causal=True)
                    if s1 >= x0 and s0 <= i]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    # the EQ as it stood at that moment: flat steps through its higher lows and lower highs
    coil = [x for x in ST.pivots(df.iloc[:i + 1]) if born <= x[1] <= i and x[0] <= i and
            ((x[3] == "low" and x[4] in EC.UP_LAB) or (x[3] == "high" and x[4] in EC.DN_LAB))]

    def steps(pts):
        y = np.full(len(d), np.nan)
        for m, (j, pr) in enumerate(pts):
            j2 = pts[m + 1][0] if m + 1 < len(pts) else i
            a_, b_ = max(j, x0), min(j2, i)
            if b_ >= a_:
                y[a_ - x0:b_ - x0 + 1] = pr
        return y
    fl = steps([(x[1], float(x[2])) for x in coil if x[3] == "low"])
    cl = steps([(x[1], float(x[2])) for x in coil if x[3] == "high"])
    ax.plot(xs, XM.ema(df["Close"].values.astype(float)[:i + 1], 12)[x0:i + 1], color=PURPLE, lw=1.7, zorder=7)
    ax.step(xs, fl, where="post", color=BLUE, lw=2.0, zorder=8)
    ax.step(xs, cl, where="post", color=BLUE, lw=2.0, zorder=8)
    lo = float(np.nanmin(d["Low"].values)); hi = float(np.nanmax(d["High"].values)); rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.25 * rng, hi + 0.25 * rng)
    ax.set_xlim(-1, len(d) + max(6, int(0.12 * len(d))))       # empty space on the right: the future is hidden
    ax.axvline(len(d) - 0.5, color=DIM, lw=0.8, ls=":", zorder=4)
    step_ = max(len(d) // 7, 1)
    ax.set_xticks(xs[::step_]); ax.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    ax.set_title("%s  %s   the EQ in blue as you'd see it now, 12 EMA in purple (nothing after the dotted line)" % (sym, tf),
                 color="#e6e9ee", fontsize=11.5, loc="left", pad=8)
    panels = [(ax, d)]
    t_now = df.index[i]
    f_now, c_now = float(np.nanmin(fl)), float(np.nanmax(cl))
    # only bigger-chart bars that had CLOSED by this moment: 1h bars that ended by now, daily bars from before today
    big = [(h1, (lambda x: int(x.index.searchsorted(t_now - pd.Timedelta(hours=1), side="right"))),
            "1 hour up to the same moment", "%m-%d %H:%M"),
           (d1, (lambda x: int(x.index.searchsorted(t_now.normalize(), side="left"))),
            "Daily through the day before", "%m-%d")]
    for row, (hf, end_of, title, fmt) in enumerate(big):
        if hf is None or len(hf) < 30:
            continue
        end_h = end_of(hf)
        pos = max(0, end_h - 90)
        win = end_h - pos
        if win < 20:
            continue
        axh = fig.add_subplot(gs[row, 1])
        hb = CK.bundle(hf, pos, win)
        hb["spans"] = [(k_, max(s0, pos) - pos, min(s1, end_h - 1) - pos)
                       for k_, s0, s1 in ST.spans(hf.iloc[:end_h], causal=True) if s1 >= pos and s0 <= end_h - 1]
        CK.render(axh, hb, "", fmt)
        e12 = XM.ema(hf["Close"].values.astype(float)[:end_h], 12)[pos:end_h]
        axh.plot(np.arange(len(e12)), e12, color=PURPLE, lw=1.7, zorder=7)
        ylo = min(float(np.nanmin(hf["Low"].values[pos:end_h])), f_now)
        yhi = max(float(np.nanmax(hf["High"].values[pos:end_h])), c_now)
        yr = max(yhi - ylo, 1e-9)
        axh.set_ylim(max(0, ylo - 0.2 * yr), yhi + 0.2 * yr)
        axh.set_xlim(-1, win + 6)
        # where the EQ sits on the bigger chart: an orange band at its floor-to-ceiling prices
        axh.axhspan(f_now, c_now, color="#ffb84d", alpha=0.25, zorder=3)
        axh.set_title("%s: 12 EMA in purple, the EQ's prices in orange" % title, loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axh.get_xticklabels(), fontsize=6)
        panels.append((axh, hb["d"]))
    fig.text(0.045, 0.03, "Mark it: long, short, or skip. What happened next is hidden until you've marked them all.",
             color=DIM, fontsize=9, ha="left")
    import pics_ride as PR
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def _one(args):
    sym, kind, seed, per_name = args
    try:
        fr = S.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    use = FR2.regular_hours(fr) if kind in ("stock", "etf") else fr
    rng = np.random.default_rng(seed)
    got, errs = [], []
    for tf in TFS:
        df = use.get(tf)
        h1 = use.get("1h")
        d1 = use.get("1d")
        if df is None or len(df) < 500:
            continue
        try:
            c = df["Close"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            floor, ceil, cid, recs, atr = EC.coils(df, min_gap=3)
            pool = []
            for r in recs:
                if not r["tradeable"] or r["born"] < 80:
                    continue
                how = str(r["how"]); k = r["end"]
                sgn = 1 if ("ceiling" in how or "higher high" in how) else -1 if ("floor" in how or "lower low" in how) else 0
                if sgn == 0 or k - 1 < r["confirm"] or k + ED.N_AFTER >= n:
                    continue
                pool.append((r, sgn))
            if not pool:
                continue
            for pick in rng.choice(len(pool), size=min(per_name, len(pool)), replace=False):
                r, sgn = pool[int(pick)]
                k = r["end"]; kb = k - 1
                fl_b, ce_b = floor[kb], ceil[kb]
                a = atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else np.nan
                if not (np.isfinite(fl_b) and np.isfinite(ce_b) and np.isfinite(a)):
                    continue
                cls, run = ED.outcome(sgn, k, ce_b if sgn > 0 else fl_b, fl_b if sgn > 0 else ce_b, h, l, c, a, n)
                move20 = float((c[min(n - 1, k + ED.N_AFTER)] - (fl_b + ce_b) / 2) / a)
                os.makedirs(OUT, exist_ok=True)
                mid = "%s_%s_%s_%d" % (kind, sym, tf, r["confirm"])
                path = os.path.join(OUT, mid + ".png")
                probs = render(sym, tf, df, h1, d1, r, path)
                got.append(dict(id=mid, sym=sym, kind=kind, tf=tf, t=str(df.index[r["confirm"]]), png=mid + ".png",
                                problems=probs,
                                hidden=dict(broke="up" if sgn > 0 else "down", what_next=ED.OUTCOMES[cls],
                                            bars_to_break=int(k - r["confirm"]), move20_normal_bars=round(move20, 2))))
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return got, errs


def main():
    procs, n_total = max(1, os.cpu_count() or 4), 30
    for i, a in enumerate(sys.argv):
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if a == "--procs" and nxt:
            procs = int(nxt)
        if a == "--n" and nxt:
            n_total = int(nxt)
        if a == "--log" and nxt:
            sys.stdout = sys.stderr = open(nxt, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    import focus
    names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    rng = np.random.default_rng(20260911)
    jobs = [(s_, k_, int(rng.integers(1 << 30)), 1) for s_, k_ in names]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, jobs, chunksize=1):
            rows += got; errs += err
    keep = []
    for tf in TFS:                                           # half 5m, half 15m, clean charts only, random order
        g = [r for r in rows if r["tf"] == tf and not r["problems"]]
        rng.shuffle(g)
        keep += g[:n_total // 2]
    rng.shuffle(keep)
    for k_i, r in enumerate(keep, 1):
        r["n"] = k_i
    kept = {r["png"] for r in keep}
    if os.path.isdir(OUT):
        for fn in os.listdir(OUT):
            if fn.endswith(".png") and fn not in kept:
                os.remove(os.path.join(OUT, fn))
    json.dump(keep, open(os.path.join(OUT, "eq_mark_index.json"), "w"), indent=1)
    print("  %d EQs to mark (%d candidates, %d with text problems dropped)  (%.0fs)" % (
        len(keep), len(rows), sum(1 for r in rows if r["problems"]), time.time() - t0))
    for r in keep:
        print("    #%-2d %-6s %-3s %s  hidden: broke %-4s %-8s" % (r["n"], r["sym"], r["tf"], r["t"], r["hidden"]["broke"],
                                                               r["hidden"]["what_next"]))
    for e in errs[:12]:
        print("  " + e)


if __name__ == "__main__":
    main()
