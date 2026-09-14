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


def ref_walk(kind, o, h, l, c, e, side, stop, risk, big_hl, bell):
    """The reference: the walked stop done bar by bar, the slow obvious way. It lives in this file on purpose --
    it used to be borrowed from a chart script, and when that script was rewritten for a different trade the test
    silently started comparing the wrong two things (2026-09-13)."""
    n = len(c)
    last = min(n - 1, e + L.MAX_BARS)
    if bell is not None:
        last = min(last, int(bell))
    entry = o[e]
    cut = entry + side * risk
    took_at = None
    line = stop
    cost = L.COST.get(kind, 0.05)
    for j in range(e, last + 1):
        if (side > 0 and l[j] <= line) or (side < 0 and h[j] >= line):
            px = o[j + 1] if j + 1 <= last else c[last]
            pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry)                 if took_at is not None else side * (px - entry) / entry
            return dict(pct=float(pnl * 100 - cost * (1.5 if took_at else 1)),
                        how="rest stopped out" if took_at is not None else "stopped out")
        if took_at is None and ((side > 0 and h[j] >= cut) or (side < 0 and l[j] <= cut)):
            took_at = j
        if np.isfinite(big_hl[j]):
            cand = big_hl[j]
            if side > 0 and cand < l[j] and cand > line:
                line = cand
            if side < 0 and cand > h[j] and cand < line:
                line = cand
    px = c[last]
    pnl = (0.5 * side * (cut - entry) / entry + 0.5 * side * (px - entry) / entry)         if took_at is not None else side * (px - entry) / entry
    return dict(pct=float(pnl * 100 - cost * (1.5 if took_at else 1)), how="time ran out")

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
                slow = ref_walk(kind, o, h, l, c, e, side, stop, risk, hl, bell)
                tot += 1
                if abs(fast - slow["pct"]) > 1e-9:
                    bad += 1
                    if bad <= 3:
                        print("  %s %s bar %d: fast %+0.4f%%  slow %+0.4f%%  (%s)" % (
                            sym, tf, e, fast, slow["pct"], slow["how"]))
    print("TRADES COMPARED: %d   MISMATCHES: %d" % (tot, bad))
    return 1 if bad else 0


def chand_check():
    """The drawings and the studies must book the SAME trade. They did not: `chand` takes its partial at the idea
    chart's 12 EMA when that is further than 1x the risk, while every page and every chart said "half off at 1x".
    34 of 59 trades disagreed, by up to 17% (2026-09-13). `chand1r` is the flat-1x version; this holds the two
    implementations of it against each other."""
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))))
    import pics_scalein as PS
    import backburner_wallet as W
    bad = n = 0
    worst = 0.0
    for sym, kind in [("NVDA", "stock"), ("AAPL", "stock"), ("XLV", "etf"), ("META", "stock"),
                      ("USB", "stock"), ("UPS", "stock"), ("SAP", "stock"), ("URI", "stock")]:
        a = {t["t"]: t for t in PS.trades_for(sym, kind)}
        b = {t["t_in"]: t for t in W._work((sym, kind, None))[0]}
        for t in sorted(set(a) & set(b)):
            n += 1
            d = abs(a[t]["pct"] - b[t]["pct"])
            if d > 1e-6:
                bad += 1
                worst = max(worst, d)
    print("CHANDELIER, DRAWING vs STUDY: COMPARED %d   MISMATCHES %d   worst gap %.4f%%" % (n, bad, worst))
    return bad == 0


if __name__ == "__main__":
    _bad = main()
    if not chand_check():
        _bad = 1
    sys.exit(_bad)
