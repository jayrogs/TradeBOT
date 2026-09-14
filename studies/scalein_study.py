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
SETUPS = [("scale-in, walked stop, ANY name", "walk", "any", "big", 3.0),
          ("scale-in, chandelier 3, ANY name", "chand", "any", "big", 3.0),
          ("scale-in, chandelier 8, ANY name", "chand", "any", "big", 8.0),
          ("scale-in, RIDE it, no partial, chandelier 8", "ride", "any", "big", 8.0),
          ("scale-in, RIDE it, no partial, chandelier 12", "ride", "any", "big", 12.0),
          ("scale-in, all out at 2x, ANY name", "out2r", "any", "big", 3.0),
          ("scale-in, walked stop, OVER its sector leader", "walk", "over", "big", 3.0)]
# EVERY NAME IS MEASURED AGAINST ITS OWN SECTOR LEADER (2026-09-12, his words: "The bench arm is obvious dude,
# whatever is the sector leader or etf of the sector. Like we compare to BTC for all crypto"). The map is built by
# studies/sector_map.py on the FIRST HALF of each name's history, so it cannot peek at what gets traded.
SECTOR_MAP = json.load(io.open(os.path.join("validation", "sector_map.json"), encoding="utf-8"))     if os.path.exists(os.path.join("validation", "sector_map.json")) else {}
# A name only HAS a sector if it actually moves with one. Below this the "leader" is noise and the name gets no
# strength read at all (72 of 781: the inverse ETFs, which sit at -0.87 to their index, and the farm futures).
MIN_R = 0.30
# MURPHY'S BREADTH (studies/breadth.py): how many of the market's names are above their own 200-day, each day.
# Breadth turns before the index does at a bottom, which is the bull-vs-bear question in his own words.
_BR = os.path.join("validation", "breadth.json")
BREADTH = json.load(io.open(_BR, encoding="utf-8")) if os.path.exists(_BR) else {}
BR_GROUP = {"stock": "stocks", "etf": "stocks", "crypto": "crypto", "futures": "futures"}
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
    # KEEP ONLY THE CHARTS THIS RUN USES. A daily run never touches the 5m frame, and SOL's is 430,000 bars;
    # holding all of them in 20 workers is what froze the machine (2026-09-12).
    need = set()
    for q in pairs:
        need.add(q[0])
        need.add(q[1])
        need.update(q[2])
    need.add("1d")                 # the strength ratio, the run, and the leader's regime are all read here
    frames = {k_: v_ for k_, v_ in frames.items() if k_ in need}
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
            lead_age = np.full(n, np.nan)
            br = np.full(n, np.nan)
            br_turn = np.full(n, np.nan)
            div = np.full(n, np.nan)
            lead_dd = np.full(n, np.nan)
            lead_turn = np.full(n, np.nan)
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
                        # THE REGIME, read on the LEADER: bear, the turn, early bull, mature bull. His words
                        # (2026-09-12): "its when markets go from bear to bull, that backburners are back in
                        # play". -1 means the leader is under its own 200-day; otherwise it is how many daily
                        # bars since it crossed back above.
                        b200 = XM.ema(bxa, 200)
                        abv = bxa > b200
                        age = np.full(len(abv), -1.0)
                        run_ = 0
                        for k_ in range(len(abv)):
                            run_ = run_ + 1 if abv[k_] else 0
                            age[k_] = run_ if abv[k_] else -1.0
                        lead_age = L.align_to(df, tf, frames, "1d", age)
                        # HOW DEEP the leader is under its own 200-day, and whether it has TURNED UP off that
                        # low. "Under the 200-day" on its own is a crude proxy for his bear-to-bull turn: it is
                        # true for most of a long grind down as well as for the bounce out of a crash.
                        dd = (bxa / np.where(b200 > 0, b200, np.nan) - 1.0) * 100.0
                        e20 = XM.ema(bxa, 20)
                        turn = np.zeros(len(bxa))
                        turn[5:] = (e20[5:] > e20[:-5]).astype(float)
                        lead_dd = L.align_to(df, tf, frames, "1d", dd)
                        lead_turn = L.align_to(df, tf, frames, "1d", turn)
                        over = L.align_to(df, tf, frames, "1d",
                                          np.where(ratio > r12, 1.0, 0.0))
                        rising = L.align_to(df, tf, frames, "1d",
                                            np.where((ratio > r12) & (up5 > 0), 1.0, 0.0))
            # BREADTH, on the name's own market, read on its daily clock
            bg = BREADTH.get(BR_GROUP.get(kind, kind))
            if bg is not None and d1 is not None and len(d1) > 60:
                bidx = pd.to_datetime(bg["dates"])
                a200 = pd.Series(bg["above200"], index=bidx).reindex(d1.index).ffill()
                t20 = pd.Series([np.nan if x is None else float(x) for x in bg["turn20"]],
                                index=bidx).reindex(d1.index).ffill()
                br = L.align_to(df, tf, frames, "1d", a200.values.astype(float))
                br_turn = L.align_to(df, tf, frames, "1d", t20.values.astype(float))
            # MURPHY'S DIVERGENCE, on the name's own daily: price at a 40-day low while momentum is HIGHER than
            # it was 40 days ago -- the selling is running out of force. His named bottom signal.
            if d1 is not None and len(d1) > 80:
                dc = d1["Close"].values.astype(float)
                dl = d1["Low"].values.astype(float)
                drsi = IND.rsi(dc, 14)
                lo40 = pd.Series(dl).rolling(40, min_periods=40).min().values
                dat = P._atr(d1)
                tol = np.where(np.isfinite(dat), 0.25 * dat, 0.0)
                dv = np.zeros(len(dc))
                # NEAR the 40-day low, not exactly on it: an exact touch fired on 0.2% of trades, which is not
                # a measurable sample and is not what Murphy describes (he describes the RETEST).
                dv[40:] = ((dl[40:] <= lo40[40:] + tol[40:]) & (drsi[40:] > drsi[:-40])).astype(float)
                div = L.align_to(df, tf, frames, "1d", dv)
            bells = None
            if kind in ("stock", "etf"):
                day = df.index.normalize().values
                bells = np.searchsorted(day, day, side="right") - 1
            os_ = (rsi <= 30)
            ob = (rsi >= 70)
            # HIS TWO PRECONDITIONS (2026-09-12): "backburners ... is only engaged when the name has a huge run
            # going on", and "first daily oversold in a long time has a huge bounce if you buy that dip".
            #   run60  how far the name has TRAVELLED in the last 60 bars, counted in normal bars so every
            #          market is on the same scale (a 20-bar run in NVDA and in SOL mean the same thing here)
            #   since  how many bars since the PREVIOUS print of the same kind: a first-in-a-long-time dip
            #          scores high, a name printing oversold every week scores low
            # THE RUN IS READ ON THE DAILY, always. Measuring it on the entry chart made "a huge run" mean
            # the last 60 FIVE-MINUTE bars -- five hours -- and it co-occurred with an oversold print 993
            # times in 720,577 (2026-09-12). A name that is running is running on the daily.
            run60 = np.full(n, np.nan)
            up200 = np.full(n, np.nan)
            dd = frames.get("1d")
            if dd is not None and len(dd) > 220:
                dc = dd["Close"].values.astype(float)
                da = P._atr(dd)
                rd = np.full(len(dc), np.nan)
                rd[60:] = (dc[60:] - dc[:-60]) / np.where(da[60:] > 0, da[60:], np.nan)
                run60 = L.align_to(df, tf, frames, "1d", rd)
                up200 = L.align_to(df, tf, frames, "1d",
                                   np.where(dc > XM.ema(dc, 200), 1.0, 0.0))
            since = {}
            for nm, flag in (("long", os_), ("short", ob)):
                gap = np.zeros(n)
                last_seen = -10 ** 6
                for k_ in range(n):
                    gap[k_] = k_ - last_seen
                    if flag[k_]:
                        last_seen = k_
                since[nm] = gap
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
                    if cands:
                        stop = max(cands) if side > 0 else min(cands)
                        stop = stop - 0.15 * a if side > 0 else stop + 0.15 * a
                    else:
                        stop = worst - a if side > 0 else worst + a     # never discard: see backburner_night
                    risk = abs(entry - stop)
                    if risk < 0.25 * a:
                        risk = 0.25 * a
                        stop = entry - side * risk
                    # A RISK BAND, so the numbers describe trades a person could take: the stop must be at least
                    # three times the round-trip cost away, and no more than 5% of price (2026-09-12: without this,
                    # a 0.09%-risk trade printed +44R and a 12%-risk trade counted the same as any other).
                    # THE RISK BAND, in the units the stop is actually set in. It used to cap the stop at 5% OF
                    # PRICE, which is fine on a 5m chart and impossible on a daily: a daily dip's nearest structure
                    # sits 0.8-1.3 normal bars away, which IS 10-16% of price, so the cap threw out 89-100% of
                    # every daily backburner (2026-09-12). Murphy's 5% is 5% of the ACCOUNT, which is a sizing
                    # question, not a reason to skip the trade. So: the stop must be at least three times the
                    # round-trip cost away (or cost eats the edge) and no more than four normal bars (further than
                    # that and it is not "the nearest structure" any more), with a loose sanity cap on price.
                    rp = risk / entry * 100
                    if rp < 3 * COSTV.get(kind, 0.05) or risk > 4.0 * a or rp > 25.0:
                        continue
                    # a SHORT is strong when the name is WEAK against its leader, so the flag mirrors
                    rn = run60[m_]
                    on_run = (rn if side > 0 else -rn) if np.isfinite(rn) else np.nan
                    la = lead_age[m_]
                    la = float(la) if np.isfinite(la) else -2.0
                    ldd = float(lead_dd[m_]) if np.isfinite(lead_dd[m_]) else 0.0
                    brv = float(br[m_]) if np.isfinite(br[m_]) else -1.0
                    brt = float(br_turn[m_]) if np.isfinite(br_turn[m_]) else -1.0
                    dvv = float(div[m_]) if np.isfinite(div[m_]) else 0.0
                    ltn = float(lead_turn[m_]) if np.isfinite(lead_turn[m_]) else 0.0
                    u2 = up200[m_]
                    on_200 = (u2 if side > 0 else (1.0 - u2)) if np.isfinite(u2) else 0.0
                    fresh = since["long" if side > 0 else "short"][max(0, k - 1)]
                    o_ = over[e_last]
                    r_ = rising[e_last]
                    f_over = (o_ if side > 0 else (1.0 - o_)) if np.isfinite(o_) else 0.0
                    f_rise = (r_ if side > 0 else (1.0 - r_)) if np.isfinite(r_) else 0.0
                    t_ = df.index[e]
                    era = 0 if t_ < start else 1 if t_ < mid_t else 2
                    res = []
                    for _, mode, _f, which, chd in SETUPS:
                        trail = (big_lo if side > 0 else big_hi) if which == "big" else                                 (last_lo if side > 0 else last_hi)
                        res.append(L.run_trade(kind, o, h, l, c, e_last, side, stop, risk, b12, trail, small12,
                                               None, mode, None if bells is None else bells[e_last], atr,
                                               chand=chd, entry_px=entry))
                    rows.append([tf_i, side, era, f_over, f_rise,
                                 on_run if np.isfinite(on_run) else 0.0, float(fresh), on_200, la, ldd, ltn,
                                 brv, brt, dvv,
                                 risk / entry * 100, float(t_.value), is_ctrl] + res)
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
             worst_losing_streak=int(streak), worst_dip_pct=dip,
             total=float(v.sum()),
             top5_share=float(np.sort(v)[-max(1, len(v) // 20):].sum() / v.sum()) if v.sum() > 0 else None,
             best=float(v.max()))
    d["blocks"] = blocks_of_20(v)
    return d


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    pairs = L.PAIRS
    out_path = OUT
    if "--slow" in sys.argv:                 # the swing charts: 1h idea daily, 4h idea weekly
        pairs = L.PAIRS_SLOW
        out_path = os.path.join("validation", "scalein_swing.json")
    if "--daily" in sys.argv:                # HIS bear-market case: the daily dip, the weekly as the idea
        pairs = [("1d", "1w", ["1w"]), ("4h", "1d", ["1d", "1w"])]
        out_path = os.path.join("validation", "scalein_daily.json")
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
    cols = ["tf", "side", "era", "f_over", "f_rise", "on_run", "fresh", "on_200", "lead_age", "lead_dd", "lead_turn", "breadth", "br_turn", "diverge", "risk_pct", "t", "ctrl"] +         ["r%d" % i for i in range(len(SETUPS))]
    d = pd.DataFrame(f, columns=cols)
    d["kind"] = kinds
    d = d.sort_values("t")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         rows=int(len(d)), setups=[s[0] for s in SETUPS], seconds=int(time.time() - t0)),
               table={})
    print("\n  THE SCALE-IN, %s CHARTS  (%d names, %d trades, %.0fs)" % (
        "SWING" if pairs is L.PAIRS_SLOW else "DAILY" if "--daily" in sys.argv else "FAST", len(names), len(d), time.time() - t0))
    for si, (name, mode, filt, _w, _ch) in enumerate(SETUPS):
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
    # HIS PRECONDITIONS, cut on the best management: did the name have to be RUNNING, and did the dip have
    # to be the first in a long time? Each cut gets its own control (any bar, same cut) so the trigger is what
    # is being measured and not the market the cut happens to select.
    col = "r0"
    out["preconditions"] = {}
    print("\n  HIS TWO PRECONDITIONS  (walked stop, any name)")
    print("    %-34s %8s %8s %8s %6s %7s %7s %9s" % (
        "cut", "n", "avg", "middle", "won", "avg R", "ctrl R", "20-blocks"))
    cuts = [("every dip (no precondition)", None),
            ("the name is over its 200-day", ("on_200", 0.5))]
    for b in (2, 4, 6, 10):
        cuts.append(("ran %d+ daily bars in 60 days" % b, ("on_run", b)))
    for b in (30, 60, 120, 250):
        cuts.append(("first dip in %d+ bars" % b, ("fresh", b)))
    for rb, fb in ((4, 60), (6, 120)):
        cuts.append(("ran %d+ AND first in %d+ bars" % (rb, fb), ("both", (rb, fb))))
    cuts.append(("over the 200-day AND first in 120+", ("t200", 120)))
    for lab, spec in cuts:
        if spec is None:
            m = d.ctrl >= 0
        elif spec[0] == "both":
            m = (d.on_run >= spec[1][0]) & (d.fresh >= spec[1][1])
        elif spec[0] == "t200":
            m = (d.on_200 > 0.5) & (d.fresh >= spec[1])
        else:
            m = d[spec[0]] >= spec[1]
        g = d[(d.ctrl == 0) & m]
        g = g[np.isfinite(g[col])]
        cc = d[(d.ctrl == 1) & m]
        cc = cc[np.isfinite(cc[col])]
        s = describe(g[col].values, (g[col] / g.risk_pct).values)
        sc = describe(cc[col].values, (cc[col] / cc.risk_pct).values)
        if not s:
            continue
        bl = s["blocks"]
        print("    %-34s %8d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %+6.2fR %9s" % (
            lab, s["n"], s["avg"], s["middle"], 100 * s["won"], s["avg_R"] or 0,
            (sc["avg_R"] or 0) if sc else 0, ("%d/%d" % (bl["blocks_up"], bl["blocks"])) if bl else "-"))
        out["preconditions"][lab] = dict(setup=s, control=sc)
        for kd in ("stock", "crypto"):
            sk = describe(g[g.kind == kd][col].values,
                          (g[g.kind == kd][col] / g[g.kind == kd].risk_pct).values)
            if sk:
                print("        %-30s %8d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR" % (
                    kd, sk["n"], sk["avg"], sk["middle"], 100 * sk["won"], sk["avg_R"] or 0))
                out["preconditions"][lab][kd] = sk
    # THE REGIME HE NAMED: where the name's own sector leader stands against its 200-day when the dip prints.
    REG = [("leader 10%+ UNDER its 200-day, still falling", lambda x: (x.lead_dd <= -10) & (x.lead_turn < 0.5)),
           ("leader 10%+ UNDER it but TURNING UP (the turn)", lambda x: (x.lead_dd <= -10) & (x.lead_turn > 0.5)),
           ("leader a little under its 200-day", lambda x: (x.lead_dd > -10) & (x.lead_dd < 0)),
           ("leader just over its 200-day, under 90 days", lambda x: (x.lead_age >= 0) & (x.lead_age < 90)),
           ("early bull, 90-365 days up", lambda x: (x.lead_age >= 90) & (x.lead_age < 365)),
           ("mature bull, 365+ days up", lambda x: x.lead_age >= 365)]
    out["regime"] = {}
    for si2 in (0, 3):
        colr = "r%d" % si2
        print("\n  THE BEAR-TO-BULL TURN  (%s)" % SETUPS[si2][0])
        print("    %-44s %7s %8s %8s %6s %7s %7s %8s" % (
            "where the leader stood", "n", "avg", "middle", "won", "avg R", "ctrl R", "top 5%"))
        for lab, fn in REG:
            g = d[(d.ctrl == 0) & fn(d)]
            g = g[np.isfinite(g[colr])]
            cc = d[(d.ctrl == 1) & fn(d)]
            cc = cc[np.isfinite(cc[colr])]
            s_ = describe(g[colr].values, (g[colr] / g.risk_pct).values)
            sc = describe(cc[colr].values, (cc[colr] / cc.risk_pct).values)
            if not s_:
                continue
            print("    %-44s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %+6.2fR %7s" % (
                lab, s_["n"], s_["avg"], s_["middle"], 100 * s_["won"], s_["avg_R"] or 0,
                (sc["avg_R"] or 0) if sc else 0,
                "-" if s_["top5_share"] is None else "%.0f%%" % (100 * s_["top5_share"])))
            out["regime"].setdefault(SETUPS[si2][0], {})[lab] = dict(setup=s_, control=sc)
            for kd in ("stock", "crypto"):
                gk = g[g.kind == kd]
                sk = describe(gk[colr].values, (gk[colr] / gk.risk_pct).values)
                if sk:
                    print("        %-40s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %7s %7s" % (
                        kd, sk["n"], sk["avg"], sk["middle"], 100 * sk["won"], sk["avg_R"] or 0,
                        "", "-" if sk["top5_share"] is None else "%.0f%%" % (100 * sk["top5_share"])))
                    out["regime"][SETUPS[si2][0]][lab][kd] = sk
    # MURPHY'S BULL-VS-BEAR READS, the ones this machine can actually build (2026-09-12, his question:
    # "is there anything you can use from trading in the zone or the other book on ways to test when something
    # is bullish vs bearish?"). Douglas has nothing here on purpose. These are Murphy's.
    MUR = [("breadth washed out, under 20% over their 200-day", lambda x: (x.breadth >= 0) & (x.breadth < 0.20)),
           ("breadth 20-40%", lambda x: (x.breadth >= 0.20) & (x.breadth < 0.40)),
           ("breadth 40-60%", lambda x: (x.breadth >= 0.40) & (x.breadth < 0.60)),
           ("breadth 60-80%", lambda x: (x.breadth >= 0.60) & (x.breadth < 0.80)),
           ("breadth over 80%, everything is up", lambda x: x.breadth >= 0.80),
           ("breadth under 30 AND turning up (his bottom)",
            lambda x: (x.breadth >= 0) & (x.breadth < 0.30) & (x.br_turn > 0.5)),
           ("breadth under 30 and still falling",
            lambda x: (x.breadth >= 0) & (x.breadth < 0.30) & (x.br_turn == 0)),
           ("momentum divergence at a 40-day low", lambda x: x.diverge > 0.5),
           ("divergence AND breadth under 40",
            lambda x: (x.diverge > 0.5) & (x.breadth >= 0) & (x.breadth < 0.40))]
    out["murphy"] = {}
    for si2 in (0, 3):
        colm = "r%d" % si2
        print("\n  MURPHY'S BULL-VS-BEAR READS  (%s)" % SETUPS[si2][0])
        print("    %-46s %7s %8s %8s %6s %7s %7s" % (
            "the read", "n", "avg", "middle", "won", "avg R", "ctrl R"))
        for lab, fn in MUR:
            g = d[(d.ctrl == 0) & fn(d)]
            g = g[np.isfinite(g[colm])]
            cc = d[(d.ctrl == 1) & fn(d)]
            cc = cc[np.isfinite(cc[colm])]
            s_ = describe(g[colm].values, (g[colm] / g.risk_pct).values)
            sc = describe(cc[colm].values, (cc[colm] / cc.risk_pct).values)
            if not s_:
                continue
            print("    %-46s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %+6.2fR" % (
                lab, s_["n"], s_["avg"], s_["middle"], 100 * s_["won"], s_["avg_R"] or 0,
                (sc["avg_R"] or 0) if sc else 0))
            out["murphy"].setdefault(SETUPS[si2][0], {})[lab] = dict(setup=s_, control=sc)
            for kd in ("stock", "crypto"):
                gk = g[g.kind == kd]
                sk = describe(gk[colm].values, (gk[colm] / gk.risk_pct).values)
                if sk:
                    print("        %-42s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR" % (
                        kd, sk["n"], sk["avg"], sk["middle"], 100 * sk["won"], sk["avg_R"] or 0))
                    out["murphy"][SETUPS[si2][0]][lab][kd] = sk
    json.dump(out, open(out_path, "w"))
    # keep the rows so a question can be answered without re-running the whole study
    try:
        d.to_parquet(os.path.splitext(out_path)[0] + "_rows.parquet")
    except Exception as _ex:
        np.save(os.path.splitext(out_path)[0] + "_rows.npy", d.to_records(index=False))
    for e_ in errs[:10]:
        print("  ERR " + e_)
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
