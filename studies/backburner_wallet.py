"""backburner_wallet.py -- what the fear-gap backburner is worth to an ACCOUNT, not to a trade (2026-09-13).

His "yeah so what", and he is right to ask. A per-trade number is not money. This setup fires 661 times a year
across the universe and the worst single day had 172 of them at once -- everything gaps down on the same day --
so you cannot take them all, and the ones you do take are not independent of each other.

So: a wallet. N slots, each position risked at a fixed share of the RUNNING account, trades taken in time order,
a random pick when more signals arrive than there are free slots, and the slot is tied up until the trade
actually closes. Sixty runs of the random pick so the spread is visible, not one lucky draw. This is #29's
machinery, pointed at this setup.

THE SETUP, as the overnight run left it:
    the daily chart, RSI 14 at or under 30, scaled into over up to 5 units a quarter of a normal bar apart
    the name opened BELOW yesterday's low on the dip (Murphy's gap, and the biggest single read in the study)
    stop at the nearest structure under the lowest fill, half off at 1x the risk, the rest on a chandelier 3
    stocks and ETFs only: crypto barely gaps, 92 trades in ten years

    python studies/backburner_wallet.py --procs 8
Writes validation/backburner_wallet.json
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
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
from scalein_study import BREADTH, BR_GROUP        # noqa: E402

OUT = os.path.join("validation", "backburner_wallet.json")
ADDS, GAP, LEVEL = 5, 0.25, 30
SLOTS = [3, 5, 10, 20, 40]
RISK = 0.01                       # a fixed 1% of the running account per trade
RUNS = 60


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    frames = {k: v for k, v in frames.items() if k in ("1d", "1w")}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    df, bdf = frames.get("1d"), frames.get("1w")
    if df is None or bdf is None or len(df) < 300 or len(bdf) < 80:
        return [], []
    out, errs = [], []
    try:
        o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        n = len(c)
        atr = P._atr(df)
        rsi = IND.rsi(c, 14)
        small12 = XM.ema(c, 12)
        piv = ST.pivots(df)
        last_lo = np.full(n, np.nan)
        cl = np.nan; q = 0
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
        b12 = L.align_to(df, "1d", frames, "1w", XM.ema(bdf["Close"].values.astype(float), 12))
        gap_down = np.zeros(n)
        gap_down[1:] = (o[1:] < l[:-1]).astype(float)
        bg = BREADTH.get(BR_GROUP.get(kind, kind))
        breadth = np.full(n, np.nan)
        if bg is not None:
            breadth = pd.Series(bg["above200"], index=pd.to_datetime(bg["dates"])) \
                .reindex(df.index).ffill().values.astype(float)
        cost = L.COST.get(kind, 0.05)
        os_ = rsi <= LEVEL
        for k in np.where(os_[1:] & ~os_[:-1])[0] + 1:
            e = k + 1
            m_ = e - 1
            if e < 120 or e + 6 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                continue
            if gap_down[m_] < 0.5:                 # the fear gap, read on the bar before the fill
                continue
            a = atr[m_]
            fills = [o[e]]; fill_bars = [e]; j = e
            while len(fills) < ADDS and j + 1 < n:
                j += 1
                if rsi[j - 1] > LEVEL:
                    break
                if o[j] <= fills[-1] - GAP * a:
                    fills.append(o[j]); fill_bars.append(j)
            entry = float(np.mean(fills))
            e_last = fill_bars[-1]
            worst = min(fills)
            cands = [x for x in (last_lo[e_last], big_lo[e_last])
                     if np.isfinite(x) and x < worst]
            stop = (max(cands) - 0.15 * a) if cands else (worst - a)
            risk = abs(entry - stop)
            if risk < 0.25 * a:
                risk = 0.25 * a
                stop = entry - risk
            rp = risk / entry * 100
            if rp < 3 * cost or risk > 4.0 * a or rp > 25.0:
                continue
            pct, exit_i = L.run_trade(kind, o, h, l, c, e_last, 1, stop, risk, b12, big_lo, small12, rsi,
                                      "chand", None, atr, chand=3.0, entry_px=entry, want_exit=True)
            out.append(dict(sym=sym, kind=kind, t_in=str(df.index[e].date()),
                            t_out=str(df.index[min(exit_i + 1, n - 1)].date()),
                            pct=float(pct), risk_pct=float(rp), R=float(pct / rp),
                            breadth=float(breadth[m_]) if np.isfinite(breadth[m_]) else -1.0))
    except Exception as ex:
        errs.append("%s %s: %s" % (kind, sym, ex))
    return out, errs


def wallet(trades, slots, seed, risk=RISK):
    """Trades in time order into an account with a fixed number of slots. A slot is tied up until its trade
    closes. Position size is `risk` of the RUNNING account divided by the trade's own stop distance, so a wide
    stop takes a small position -- Murphy's money management, not a flat bet."""
    rng = np.random.default_rng(seed)
    eq = 1.0
    free = slots
    open_ = []                      # (exit_date, pct, size)
    peak, dip = 1.0, 0.0
    taken = missed = 0
    by_day = {}
    for tr in trades:
        by_day.setdefault(tr["t_in"], []).append(tr)
    curve = []
    for day in sorted(by_day):
        while open_ and open_[0][0] <= day:
            _d, pct, size = open_.pop(0)
            eq *= (1.0 + size * pct / 100.0)
            free += 1
            peak = max(peak, eq)
            dip = min(dip, eq / peak - 1.0)
        todays = by_day[day]
        if len(todays) > free:
            idx = rng.permutation(len(todays))[:max(0, free)]
            picks = [todays[i] for i in idx]
            missed += len(todays) - len(picks)
        else:
            picks = todays
        for tr in picks:
            size = risk / (tr["risk_pct"] / 100.0)          # 1% of the account at risk, whatever the stop
            size = min(size, 1.0 / max(1, slots) * 3.0)     # never more than 3 normal slots in one name
            open_.append((tr["t_out"], tr["pct"], size))
            free -= 1
            taken += 1
        open_.sort(key=lambda x: x[0])
        curve.append((day, eq))
    for _d, pct, size in open_:
        eq *= (1.0 + size * pct / 100.0)
        peak = max(peak, eq)
        dip = min(dip, eq / peak - 1.0)
    return eq, dip, taken, missed, curve


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = [(s_, k_) for s_, k_ in B.universe() if k_ in ("stock", "etf")]
    R.quiet_workers()
    trades, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=4):
            trades += got
            errs += err
    trades.sort(key=lambda x: x["t_in"])
    yrs = (pd.Timestamp(trades[-1]["t_in"]) - pd.Timestamp(trades[0]["t_in"])).days / 365.25
    print("  %d trades, %s to %s (%.1f years), %.0f a year  (%.0fs)" % (
        len(trades), trades[0]["t_in"], trades[-1]["t_in"], yrs, len(trades) / yrs, time.time() - t0))
    Rs = np.array([t["R"] for t in trades])
    print("  per trade: avg %+.2f%%  middle %+.2f%%  won %.0f%%  avg R %+.2f\n" % (
        np.mean([t["pct"] for t in trades]), np.median([t["pct"] for t in trades]),
        100 * np.mean(Rs > 0), Rs.mean()))
    out = dict(meta=dict(trades=len(trades), years=round(yrs, 1), per_year=round(len(trades) / yrs),
                         avg_R=float(Rs.mean()), generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
               wallets={})
    print("  %-8s %12s %12s %12s %10s %10s" % ("slots", "a year", "10-90% band", "worst dip", "taken", "missed"))
    for slots in SLOTS:
        res = [wallet(trades, slots, s) for s in range(RUNS)]
        ann = np.array([r[0] ** (1 / yrs) - 1 for r in res])
        dips = np.array([r[1] for r in res])
        tk = np.mean([r[2] for r in res])
        ms = np.mean([r[3] for r in res])
        print("  %-8d %11.1f%% %11s %11.1f%% %10.0f %10.0f" % (
            slots, 100 * ann.mean(),
            "%.0f to %.0f%%" % (100 * np.percentile(ann, 10), 100 * np.percentile(ann, 90)),
            100 * dips.mean(), tk, ms))
        out["wallets"][slots] = dict(a_year=float(ann.mean()), lo=float(np.percentile(ann, 10)),
                                     hi=float(np.percentile(ann, 90)), worst_dip=float(dips.mean()),
                                     taken=float(tk), missed=float(ms))
    # the same wallet with the market filter he cares about
    weak = [t for t in trades if 0 <= t["breadth"] < 0.40]
    print("\n  ONLY WHEN THE MARKET IS WEAK (breadth under 40%%): %d trades, %.0f a year, avg R %+.2f" % (
        len(weak), len(weak) / yrs, np.mean([t["R"] for t in weak])))
    print("  %-8s %12s %12s %12s" % ("slots", "a year", "10-90% band", "worst dip"))
    for slots in (3, 5, 10):
        res = [wallet(weak, slots, s) for s in range(RUNS)]
        ann = np.array([r[0] ** (1 / yrs) - 1 for r in res])
        dips = np.array([r[1] for r in res])
        print("  %-8d %11.1f%% %11s %11.1f%%" % (
            slots, 100 * ann.mean(),
            "%.0f to %.0f%%" % (100 * np.percentile(ann, 10), 100 * np.percentile(ann, 90)),
            100 * dips.mean()))
        out["wallets"]["weak_%d" % slots] = dict(a_year=float(ann.mean()), worst_dip=float(dips.mean()),
                                                 n=len(weak))
    out["trades"] = trades
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)


if __name__ == "__main__":
    main()
