"""scalein_study.py -- put the one positive corner through everything before it is believed (2026-09-12).

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

    pythonw studies/scalein_study.py --procs 20 --log logs/scalein.log
Writes validation/scalein.json
"""
import concurrent.futures as cf
import io
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

OUT = os.path.join("validation", "scalein.json")
ERAS = ["before 2022", "first half", "second half"]
# (name, mode, use the 12 EMA filter, which array the stop walks on)
# HIS BACKBURNER, 2026-09-12: "its about buying it AT OR UNDER 30 ... its about scaling into a dip".
# Not a bounce trigger. The first unit goes on while RSI is at or under 30 and more units go on as it drops
# further; the position is the average of those fills.
ADDS = 3               # at most three units
ADD_GAP = 0.5          # a new unit only after price falls another half a normal bar
# (name, mode, which strength cut, which structure the stop walks on)
#   "any"    every scale-in
#   "over"   the name's ratio to ITS OWN SECTOR LEADER is above that ratio's 12 EMA on the daily
#   "rising" the same, and the ratio has been climbing for a week (the ratio trending, not just above)
SETUPS = [("scale-in, walked stop, ANY name", "walk", "any", "big"),
          ("scale-in, walked stop, OVER its sector leader", "walk", "over", "big"),
          ("scale-in, walked stop, sector ratio RISING", "walk", "rising", "big"),
          ("scale-in, small-chart trail, ratio rising", "walk", "rising", "small"),
          ("scale-in, chandelier 3, ratio rising", "chand", "rising", "big"),
          ("scale-in, all out at 2x, ratio rising", "out2r", "rising", "big")]
# EVERY NAME IS MEASURED AGAINST ITS OWN SECTOR LEADER (2026-09-12, his words: "The bench arm is obvious dude,
# whatever is the sector leader or etf of the sector. Like we compare to BTC for all crypto"). The map is built by
# studies/sector_map.py on the FIRST HALF of each name's history, so it cannot peek at what gets traded.
SECTOR_MAP = json.load(io.open(os.path.join("validation", "sector_map.json"), encoding="utf-8"))     if os.path.exists(os.path.join("validation", "sector_map.json")) else {}
# A name only HAS a sector if it actually moves with one. Below this the "leader" is noise and the name gets no
# strength read at all (72 of 781: the inverse ETFs, which sit at -0.87 to their index, and the farm futures).
MIN_R = 0.30
SECTOR_MAP = {k: v for k, v in SECTOR_MAP.items() if v[1] >= MIN_R}
CONTROL = "control: any bar, same management and filter"        # rule 15: every result needs a control


BENCH_CLOSE = {}


def _work(args):
    # THE PAIRS TRAVEL IN THE JOB, not in a global: Windows re-imports this module in every worker, so a
    # `global PAIRS` set in main() never reaches them (2026-09-12, that bug silently re-ran the fast charts).
    sym, kind, start, benches, pairs = args
    global BENCH_CLOSE
    BENCH_CLOSE = benches
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for tf_i, (tf, big, above) in enumerate(pairs):
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
            # RELATIVE STRENGTH, his requirement: the name over its benchmark, that ratio above its own 12 EMA
            # on the daily. Stocks and ETFs are measured against SPY and QQQ, strong against EITHER counts.
            over = np.full(n, np.nan)
            rising = np.full(n, np.nan)
            d1 = frames.get("1d")
            lead = SECTOR_MAP.get("%s|%s" % (kind, sym))
            if d1 is not None and len(d1) > 60 and lead:
                bx = BENCH_CLOSE.get(lead[0])
                if bx is not None and lead[0] != "%s|%s" % (kind, sym):
                    bxa = bx.reindex(d1.index).ffill().values.astype(float)
                    ratio = d1["Close"].values.astype(float) / bxa
                    ok = np.isfinite(ratio)
                    if ok.sum() >= 60:
                        rr = np.where(ok, ratio, np.nan)
                        r12 = XM.ema(rr, 12)
                        up5 = r12 - np.r_[np.full(5, np.nan), r12[:-5]]
                        over = L.align_to(df, tf, frames, "1d",
                                          np.where(ratio > r12, 1.0, 0.0))
                        rising = L.align_to(df, tf, frames, "1d",
                                            np.where((ratio > r12) & (up5 > 0), 1.0, 0.0))
            bells = None
            if kind in ("stock", "etf"):
                day = df.index.normalize().values
                bells = np.searchsorted(day, day, side="right") - 1
            os_ = (rsi <= 30)
            ob = (rsi >= 70)
            # the first oversold bar of each run: that is where the scale-in starts
            ups = np.where(os_[1:] & ~os_[:-1])[0] + 1
            dns = np.where(ob[1:] & ~ob[:-1])[0] + 1
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
                    # SCALE IN while the print stays at or under 30: a unit now, more as it drops further
                    fills = [o[e]]
                    fill_bars = [e]
                    j = e
                    while len(fills) < ADDS and j + 1 < n:
                        j += 1
                        if not ((rsi[j - 1] <= 30) if side > 0 else (rsi[j - 1] >= 70)):
                            break
                        gap = ADD_GAP * a
                        lower = (o[j] <= fills[-1] - gap) if side > 0 else (o[j] >= fills[-1] + gap)
                        if lower:
                            fills.append(o[j])
                            fill_bars.append(j)
                    entry = float(np.mean(fills))
                    e_last = fill_bars[-1]
                    cands = []
                    near = last_lo[e_last] if side > 0 else last_hi[e_last]
                    if np.isfinite(near):
                        cands.append(near)
                    bigline = big_lo[e_last] if side > 0 else big_hi[e_last]
                    if np.isfinite(bigline):
                        cands.append(bigline)
                    worst = min(fills) if side > 0 else max(fills)
                    cands = [x for x in cands if np.isfinite(x) and ((side > 0 and x < worst) or (side < 0 and x > worst))]
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
                    # a SHORT is strong when the name is WEAK against its leader, so the flag mirrors
                    o_ = over[e_last]
                    r_ = rising[e_last]
                    f_over = (o_ if side > 0 else (1.0 - o_)) if np.isfinite(o_) else 0.0
                    f_rise = (r_ if side > 0 else (1.0 - r_)) if np.isfinite(r_) else 0.0
                    t_ = df.index[e]
                    era = 0 if t_ < start else 1 if t_ < mid_t else 2
                    res = []
                    for _, mode, _f, which in SETUPS:
                        trail = (big_lo if side > 0 else big_hi) if which == "big" else                                 (last_lo if side > 0 else last_hi)
                        res.append(L.run_trade(kind, o, h, l, c, e_last, side, stop, risk, b12, trail, small12,
                                               None, mode, None if bells is None else bells[e_last], atr,
                                               entry_px=entry))
                    rows.append([tf_i, side, era, f_over, f_rise, risk / entry * 100,
                                 float(t_.value), is_ctrl] + res)
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
    pairs = L.PAIRS
    out_path = OUT
    if "--slow" in sys.argv:                 # the swing charts: 1h idea daily, 4h idea weekly
        pairs = L.PAIRS_SLOW
        out_path = os.path.join("validation", "scalein_swing.json")
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
        # the leader is named market-and-all ("crypto|BTC"): ticker BTC is ALSO an ETF in this data
        benches = {}
        for _key, _lead in SECTOR_MAP.items():
            if _lead[0] in benches:
                continue
            _kd, _sym = _lead[0].split("|")
            try:
                benches[_lead[0]] = B.frames_for(_sym, _kd)["1d"]["Close"]
            except Exception as _ex:
                print("  LEADER MISSING %s: %s" % (_lead[0], _ex), flush=True)
        print("  leaders loaded: %s" % ", ".join(sorted(benches)), flush=True)
        jobs = [(s_, k_, start, benches, pairs) for s_, k_ in names]
        for got, err in ex.map(_work, jobs, chunksize=1):
            done += 1
            errs += err or []
            if got is not None:
                parts.append(got[0])
                kinds += [got[1]] * len(got[0])
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    f = np.concatenate(parts)
    kinds = np.array(kinds)
    cols = ["tf", "side", "era", "f_over", "f_rise", "risk_pct", "t", "ctrl"] +         ["r%d" % i for i in range(len(SETUPS))]
    d = pd.DataFrame(f, columns=cols)
    d["kind"] = kinds
    d = d.sort_values("t")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         rows=int(len(d)), setups=[s[0] for s in SETUPS], seconds=int(time.time() - t0)),
               table={})
    print("\n  THE SCALE-IN, %s CHARTS  (%d names, %d trades, %.0fs)" % (
        "SWING" if pairs is L.PAIRS_SLOW else "FAST", len(names), len(d), time.time() - t0))
    for si, (name, mode, filt, _w) in enumerate(SETUPS):
        col = "r%d" % si
        keep = (d.f_over > 0) if filt == "over" else (d.f_rise > 0) if filt == "rising" else (d.ctrl >= 0)
        g = d[(d.ctrl == 0) & keep]
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
        ctl = d[(d.ctrl == 1) & keep]
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
        for tf_i, tf in enumerate([q[0] for q in pairs]):
            s = line(tf, g[g.tf == tf_i])
            if s:
                out["table"][name]["charts"][tf] = s
        for sd, lab in ((1, "longs"), (-1, "shorts")):
            s = line(lab, g[g.side == sd])
            if s:
                out["table"][name][lab] = s
    json.dump(out, open(out_path, "w"))
    for e_ in errs[:10]:
        print("  ERR " + e_)
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
