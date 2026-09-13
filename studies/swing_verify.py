"""swing_verify.py -- the swing EQ entry, checked the way scalein_study checks things (2026-09-12, overnight).

The setup: on the 1h (idea chart the daily) or the 4h (idea chart the weekly), a higher low confirms INSIDE a live
EQ; buy the next open; stop at the nearest structure; half off at 1x the risk; the rest with the stop walked under
each new higher low on the idea chart. Shorts mirror it. The filter that looked strongest in the rule table is
RELATIVE STRENGTH: the name over its benchmark (SPY / BTC / ES) above that ratio's 12 EMA on the daily.

Reports eras, markets, charts, sides, R, blocks of twenty, worst losing streak -- and a control that takes the same
management on any bar.

The corner (from `tcg_lab.py`, focus list): the BACKBURNER trigger -- RSI 14 at or under 30 on the 5m/15m, then
back over it -- bought at the next open, half off at 1x the risk, the rest with the stop walked under each new
higher low on the idea chart (1h for a 5m entry, 4h for a 15m), filtered to trades where price is on the right side
of that idea chart's 12 EMA. It showed +0.84% a trade on 18,396 trades against +0.00% without the filter.

Every number that looked like that before turned out to be my bug, so this script reports what a human needs to
judge it, not an average:

    expectancy per trade, in percent AND in R (multiples of the risk taken)
    win rate, average win vs average loss, the middle trade
    the three eras, and each market on its own
    blocks of 20 trades in time order: how many blocks made money (Douglas's sample-of-20)
    worst losing streak, worst equity dip across the trades in order
    how long trades are held, and how many a name produces a year
    the control: the same trigger and management with no filter, and the same filter with a plain 2R exit

    pythonw studies/scalein_study.py --procs 20 --log logs/scalein_study.log
Writes validation/scalein_study.json
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402

COSTV = L.COST

OUT = os.path.join("validation", "swing_verify.json")
ERAS = ["before 2022", "first half", "second half"]
# (name, mode, use the 12 EMA filter, which array the stop walks on)
SETUPS = [("EQ higher low, walked stop, STRONG vs its benchmark", "walk", True, "big"),
          ("EQ higher low, walked stop, any strength", "walk", False, "big"),
          ("EQ higher low, all out at 2x, strong", "out2r", True, "big"),
          ("EQ higher low, chandelier 3, strong", "chand", True, "big")]
CONTROL = "control: any bar, same management and filter"        # rule 15: every result needs a control


BENCH_CLOSE = {}


def _work(args):
    sym, kind, start, BENCH_CLOSE_IN = args
    global BENCH_CLOSE
    BENCH_CLOSE = BENCH_CLOSE_IN
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for tf_i, (tf, big, above) in enumerate(L.PAIRS_SLOW):
        df = frames.get(tf)
        bdf = frames.get(big)
        if df is None or bdf is None or len(df) < 500 or len(bdf) < 80:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            atr = P._atr(df)
            small12 = XM.ema(c, 12)
            rsi = IND.rsi(c, 14)
            piv = ST.pivots(df)
            last_lo = np.full(n, np.nan); last_hi = np.full(n, np.nan)
            cl_ = ch_ = np.nan; q = 0
            for k in range(n):
                while q < len(piv) and piv[q][0] <= k:
                    if piv[q][3] == "low":
                        cl_ = float(piv[q][2])
                    else:
                        ch_ = float(piv[q][2])
                    q += 1
                last_lo[k] = cl_; last_hi[k] = ch_
            b12 = L.align_to(df, tf, frames, big, XM.ema(bdf["Close"].values.astype(float), 12))
            # relative strength: the name over its benchmark, against that ratio's own 12 EMA on the daily
            strong = np.full(n, np.nan)
            d1 = frames.get("1d")
            bench = BENCH_CLOSE.get(kind)
            if bench is not None and sym != L.BENCH.get(kind, (None, None))[0] and d1 is not None and len(d1) > 40:
                bx = bench.reindex(d1.index).ffill()
                ratio = d1["Close"].values.astype(float) / bx.values.astype(float)
                ok = np.isfinite(ratio)
                if ok.sum() > 40:
                    r12 = XM.ema(np.where(ok, ratio, np.nan), 12)
                    strong = L.align_to(df, tf, frames, "1d", np.where(ratio > r12, 1.0, 0.0))
            batr = L.align_to(df, tf, frames, big, P._atr(bdf))
            bl = np.full(len(bdf), np.nan); bh = np.full(len(bdf), np.nan)
            cl2 = ch2 = np.nan; p2 = 0
            bp = ST.pivots(bdf)
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
            import eq_coil as EC
            floor, ceil, cid, recs, _a = EC.coils(df, min_gap=3)
            live = np.zeros(n, dtype=bool)
            for r_ in recs:
                if r_["tradeable"]:
                    live[r_["confirm"]:r_["end"] + 1] = True
            ups, dns = [], []
            for ci, j_, price_, kind_, lab_ in piv:
                if ci + 1 >= n or not live[ci]:
                    continue
                if kind_ == "low" and lab_ in ("HL", "EL"):
                    ups.append(ci)
                elif kind_ == "high" and lab_ in ("LH", "EH"):
                    dns.append(ci)
            ups = np.array(ups, dtype=int); dns = np.array(dns, dtype=int)
            # the control: the same trade taken on ANY bar, same management, same filter
            step = max(40, n // 4000)
            ctrl_up = np.arange(100, n - 6, step)
            ctrl_dn = np.arange(120, n - 6, step)
            for side, ks, is_ctrl in ((1, ups, 0), (-1, dns, 0), (1, ctrl_up, 1), (-1, ctrl_dn, 1)):
                for k in ks:
                    e = k + 1
                    m_ = e - 1
                    if e < 100 or e + 5 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                        continue
                    a = atr[m_]
                    ba = batr[m_] if np.isfinite(batr[m_]) else a
                    entry = o[e]
                    cands = []
                    near = last_lo[m_] if side > 0 else last_hi[m_]
                    if np.isfinite(near):
                        cands.append(near)
                    bigline = big_lo[m_] if side > 0 else big_hi[m_]
                    if np.isfinite(bigline):
                        cands.append(bigline)
                    cands = [x for x in cands if np.isfinite(x) and ((side > 0 and x < entry) or (side < 0 and x > entry))]
                    if not cands:
                        continue
                    stop = max(cands) if side > 0 else min(cands)
                    stop = stop - 0.15 * a if side > 0 else stop + 0.15 * a
                    risk = abs(entry - stop)
                    if risk < 0.25 * a:
                        risk = 0.25 * a
                        stop = entry - side * risk
                    # A RISK BAND, so the numbers describe trades a person could take: the stop must be at least
                    # three times the round-trip cost away, and no more than 5% of price (2026-09-12: without this,
                    # a 0.09%-risk trade printed +44R and a 12%-risk trade counted the same as any other).
                    rp = risk / entry * 100
                    if rp < 3 * COSTV.get(kind, 0.05) or rp > 5.0:
                        continue
                    st_ = strong[m_] if np.isfinite(strong[m_]) else np.nan
                    on_side = 0.0 if not np.isfinite(st_) else float(st_ if side > 0 else 1.0 - st_)
                    t_ = df.index[e]
                    era = 0 if t_ < start else 1 if t_ < mid_t else 2
                    res = []
                    for _, mode, _f, which in SETUPS:
                        trail = (big_lo if side > 0 else big_hi) if which == "big" else                                 (last_lo if side > 0 else last_hi)
                        res.append(L.run_trade(kind, o, h, l, c, e, side, stop, risk, b12, trail, small12, None,
                                               mode, None if bells is None else bells[e], atr))
                    rows.append([tf_i, side, era, on_side, risk / entry * 100, float(t_.value), is_ctrl] + res)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return (np.asarray(rows, dtype=np.float64), kind), errs


def blocks_of_20(v):
    if len(v) < 40:
        return None
    nb = len(v) // 20
    sums = [float(np.sum(v[i * 20:(i + 1) * 20])) for i in range(nb)]
    return dict(blocks=nb, blocks_up=int(sum(1 for s in sums if s > 0)),
                share_up=float(np.mean([s > 0 for s in sums])),
                worst_block=float(np.min(sums)), best_block=float(np.max(sums)))


def streaks_and_dip(v):
    worst = run = 0
    eq = 0.0; peak = 0.0; dip = 0.0
    for x in v:
        if x <= 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
        eq += x
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    return worst, float(dip)


def describe(v, r_mult):
    v = np.asarray(v, dtype=float)
    if len(v) < 60:
        return None
    wins = v[v > 0]; losses = v[v <= 0]
    streak, dip = streaks_and_dip(v)
    d = dict(n=int(len(v)), avg=float(v.mean()), middle=float(np.median(v)),
             won=float((v > 0).mean()),
             avg_win=float(wins.mean()) if len(wins) else None,
             avg_loss=float(losses.mean()) if len(losses) else None,
             avg_R=float(np.mean(r_mult)) if len(r_mult) else None,
             middle_R=float(np.median(r_mult)) if len(r_mult) else None,
             worst_losing_streak=int(streak), worst_dip_pct=dip)
    d["blocks"] = blocks_of_20(v)
    return d


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, kinds, errs, done = [], [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        benches = {}
        for kd, (bs, bk) in L.BENCH.items():
            try:
                benches[kd] = B.frames_for(bs, bk)["1d"]["Close"]
            except Exception:
                benches[kd] = None
        for got, err in ex.map(_work, [(s_, k_, start, benches) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if got is not None:
                parts.append(got[0])
                kinds += [got[1]] * len(got[0])
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    f = np.concatenate(parts)
    kinds = np.array(kinds)
    cols = ["tf", "side", "era", "on_side", "risk_pct", "t", "ctrl"] + ["r%d" % i for i in range(len(SETUPS))]
    d = pd.DataFrame(f, columns=cols)
    d["kind"] = kinds
    d = d.sort_values("t")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         rows=int(len(d)), setups=[s[0] for s in SETUPS], seconds=int(time.time() - t0)),
               table={})
    print("\n  THE BACKBURNER CORNER, CHECKED  (%d names, %d trades, %.0fs)" % (len(names), len(d), time.time() - t0))
    for si, (name, mode, filt, _w) in enumerate(SETUPS):
        col = "r%d" % si
        g = d[(d.ctrl == 0) & (d.on_side > 0)] if filt else d[d.ctrl == 0]
        g = g[np.isfinite(g[col])]
        rmult = (g[col] / g.risk_pct).values
        whole = describe(g[col].values, rmult)
        if not whole:
            continue
        out["table"][name] = dict(all=whole, eras={}, markets={}, charts={})
        print("\n  %s" % name)
        print("    %-22s %7s %8s %8s %6s %8s %8s %7s %7s %9s %7s" % (
            "cut", "n", "avg", "middle", "won", "avg win", "avg loss", "avg R", "mid R", "20-blocks", "streak"))

        def line(lab, sub):
            s = describe(sub[col].values, (sub[col] / sub.risk_pct).values)
            if not s:
                return None
            bl = s["blocks"]
            print("    %-22s %7d %+7.3f%% %+7.3f%% %5.0f%% %+7.3f%% %+7.3f%% %+6.2fR %+6.2fR %6s %7d" % (
                lab, s["n"], s["avg"], s["middle"], 100 * s["won"], s["avg_win"] or 0, s["avg_loss"] or 0,
                s["avg_R"] or 0, s["middle_R"] or 0, ("%d/%d" % (bl["blocks_up"], bl["blocks"])) if bl else "-",
                s["worst_losing_streak"]))
            return s
        line("everything", g)
        ctl = d[(d.ctrl == 1) & (d.on_side > 0)] if filt else d[d.ctrl == 1]
        ctl = ctl[np.isfinite(ctl[col])]
        s_ctl = line("CONTROL any bar", ctl)
        if s_ctl:
            out["table"][name]["control"] = s_ctl
        for e_i, e_name in enumerate(ERAS):
            s = line(e_name, g[g.era == e_i])
            if s:
                out["table"][name]["eras"][e_name] = s
        for kd in ("stock", "etf", "crypto", "futures"):
            s = line(kd, g[g.kind == kd])
            if s:
                out["table"][name]["markets"][kd] = s
        for tf_i, tf in enumerate([p[0] for p in L.PAIRS_SLOW]):
            s = line(tf, g[g.tf == tf_i])
            if s:
                out["table"][name]["charts"][tf] = s
        for sd, lab in ((1, "longs"), (-1, "shorts")):
            s = line(lab, g[g.side == sd])
            if s:
                out["table"][name][lab] = s
    json.dump(out, open(OUT, "w"))
    for e_ in errs[:10]:
        print("  ERR " + e_)
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
