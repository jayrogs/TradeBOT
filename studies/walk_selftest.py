"""walk_selftest.py -- the fast walk must equal the bar-by-bar walk, trade for trade (2026-09-12).

Two implementations of the same trade disagreed on 120 of 658 trades, and the fast one was wrong twice over: it
booked a partial that never happened, and it measured the stop against the level the trade STARTED with instead of
the one the stop had walked to. This is the test that keeps them honest.

    python studies/walk_selftest.py            (a few real names; prints MISMATCHES: 0 or fails)
"""
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pics_scalein as W           # noqa: E402

NAMES = [("NVDA", "stock", "5m", "1h"), ("SOL", "crypto", "15m", "4h"),
         ("ES_F", "futures", "5m", "1h"), ("AAPL", "stock", "15m", "4h")]


def levels(df, frames, tf, big):
    bdf = frames[big]
    n = len(df)
    piv = ST.pivots(df)
    last_lo = np.full(n, np.nan); last_hi = np.full(n, np.nan)
    cl = ch = np.nan; q = 0
    for k in range(n):
        while q < len(piv) and piv[q][0] <= k:
            if piv[q][3] == "low":
                cl = float(piv[q][2])
            else:
                ch = float(piv[q][2])
            q += 1
        last_lo[k] = cl; last_hi[k] = ch
    bp = ST.pivots(bdf)
    bl = np.full(len(bdf), np.nan); bh = np.full(len(bdf), np.nan)
    cl2 = ch2 = np.nan; p2 = 0
    for k in range(len(bdf)):
        while p2 < len(bp) and bp[p2][0] <= k:
            if bp[p2][3] == "low":
                cl2 = float(bp[p2][2])
            else:
                ch2 = float(bp[p2][2])
            p2 += 1
        bl[k] = cl2; bh[k] = ch2
    return (last_lo, last_hi, L.align_to(df, tf, frames, big, bl), L.align_to(df, tf, frames, big, bh),
            L.align_to(df, tf, frames, big, XM.ema(bdf["Close"].values.astype(float), 12)))


def main():
    tot = bad = 0
    for sym, kind, tf, big in NAMES:
        frames = B.frames_for(sym, kind)
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        df = frames[tf]
        o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
        n = len(c)
        atr = P._atr(df); rsi = IND.rsi(c, 14); small12 = XM.ema(c, 12)
        last_lo, last_hi, big_lo, big_hi, b12 = levels(df, frames, tf, big)
        bells = None
        if kind in ("stock", "etf"):
            day = df.index.normalize().values
            bells = np.searchsorted(day, day, side="right") - 1
        os_ = rsi <= 30; ob = rsi >= 70
        for side, ks in ((1, np.where(os_[:-1] & ~os_[1:])[0] + 1), (-1, np.where(ob[:-1] & ~ob[1:])[0] + 1)):
            for k in ks:
                e = k + 1; m_ = e - 1
                if e < 120 or e + 10 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                    continue
                if not (np.isfinite(b12[m_]) and ((side > 0 and c[m_] > b12[m_]) or (side < 0 and c[m_] < b12[m_]))):
                    continue
                entry = o[e]; a = atr[m_]
                cands = [x for x in ((last_lo[m_] if side > 0 else last_hi[m_]),
                                     (big_lo[m_] if side > 0 else big_hi[m_]))
                         if np.isfinite(x) and ((side > 0 and x < entry) or (side < 0 and x > entry))]
                if not cands:
                    continue
                stop = (max(cands) - 0.15 * a) if side > 0 else (min(cands) + 0.15 * a)
                risk = abs(entry - stop)
                if risk < 0.25 * a:
                    risk = 0.25 * a
                    stop = entry - side * risk
                rp = risk / entry * 100
                if rp < 3 * L.COST.get(kind, 0.05) or rp > 5.0:
                    continue
                bell = None if bells is None else bells[e]
                hl = big_lo if side > 0 else big_hi
                fast = L.run_trade(kind, o, h, l, c, e, side, stop, risk, b12, hl, small12, None, "walk", bell)
                slow = W.walk_one(kind, o, h, l, c, e, side, stop, risk, hl, bell)
                tot += 1
                if abs(fast - slow["pct"]) > 1e-9:
                    bad += 1
                    if bad <= 3:
                        print("  %s %s bar %d: fast %+0.4f%%  slow %+0.4f%%  (%s)" % (
                            sym, tf, e, fast, slow["pct"], slow["how"]))
    print("TRADES COMPARED: %d   MISMATCHES: %d" % (tot, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
