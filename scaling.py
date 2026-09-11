"""
scaling.py -- does scaling in and out beat taking the whole position at once?

    python scaling.py

WHY THIS TEST EXISTS
The user's real CVX trade scaled INTO weakness in three tranches (174 -> 168 ->
167) and OUT of strength in six (181 -> 205). Every backtest in this project so
far used a single entry and a single exit, so none of them can say anything
about whether that tranching helps or hurts. It is a genuinely untested part of
the method, and it is mechanisable.

THREE WAYS TO TRADE THE SAME SIGNAL
    all_in       full size at the first signal, single exit at the target
    pyramid_in   thirds, adding as price falls further
    pyramid_out  full size in, thirds out as price rises
    both         thirds in AND thirds out (what the user actually does)

versus BUY AND HOLD of the same instrument over the same window, which is the
comparison that matters -- CVX buy-and-hold returned +17.5% over the exact
window in which the tranched version returned +11.5%.

Run across ten markets on daily bars, 12-30 years each.
"""

import warnings

import numpy as np
import pandas as pd

import daily_sweep as D

warnings.filterwarnings("ignore")

DROP = 0.03          # each additional tranche after another 3% fall
RISE = 0.04          # each exit tranche after another 4% rise
MAXHOLD = 120        # trading days
STOP = 0.15          # abandon the trade if it falls this far from first entry


def rsi_np(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def run_mode(c, sig, mode, cost):
    """Return a list of (capital-weighted return, days held) per trade."""
    n = len(c)
    trades = []
    i = 0
    while i < n - 1:
        if not sig[i]:
            i += 1
            continue
        entry0 = c[i]
        # tranche plan
        n_in = 3 if mode in ("pyramid_in", "both") else 1
        n_out = 3 if mode in ("pyramid_out", "both") else 1
        lots_in = []            # (price, weight)
        lots_in.append((entry0, 1.0 / n_in))
        next_buy = entry0 * (1 - DROP)
        filled_out, proceeds_w = 0, []
        j = i + 1
        stop_px = entry0 * (1 - STOP)
        while j < n and j - i <= MAXHOLD:
            p = c[j]
            if len(lots_in) < n_in and p <= next_buy:
                lots_in.append((p, 1.0 / n_in))
                next_buy = p * (1 - DROP)
            avg = sum(w * px for px, w in lots_in) / sum(w for _, w in lots_in)
            tgt = avg * (1 + RISE * (filled_out + 1))
            if p >= tgt and filled_out < n_out:
                proceeds_w.append((p, 1.0 / n_out))
                filled_out += 1
                if filled_out == n_out:
                    break
            if p <= stop_px:
                break
            j += 1
        j = min(j, n - 1)
        # close whatever is left at the final price
        rem = 1.0 - sum(w for _, w in proceeds_w)
        if rem > 1e-9:
            proceeds_w.append((c[j], rem))
        invested = sum(w for _, w in lots_in)
        avg_in = sum(w * px for px, w in lots_in) / invested
        avg_out = sum(w * px for px, w in proceeds_w) / sum(w for _, w in proceeds_w)
        r = (avg_out * (1 - cost / 2)) / (avg_in * (1 + cost / 2)) - 1
        trades.append((r, j - i, invested))
        i = j + 1
    return trades


def main():
    data = D.load()
    print("SIGNAL: RSI(14) < 35 while price is above its 200-day average")
    print("        (buying weakness inside an uptrend -- the user's entry style)\n")
    print("  %-10s %8s %9s %9s %9s %9s %10s"
          % ("market", "trades", "all_in", "pyr_in", "pyr_out", "both", "buy&hold"))
    rows = []
    for sym, (nm, cost) in D.MARKETS.items():
        if sym not in data:
            continue
        d = data[sym]
        c = d["Close"].values.astype(float)
        ma = pd.Series(c).rolling(200).mean().values
        r = rsi_np(c)
        sig = (r < 35) & (c > ma)
        sig = np.nan_to_num(sig).astype(bool)
        res = {}
        for mode in ("all_in", "pyramid_in", "pyramid_out", "both"):
            t = run_mode(c, sig, mode, cost)
            res[mode] = (np.mean([x[0] for x in t]) if t else np.nan, len(t),
                         np.mean([x[1] for x in t]) if t else np.nan)
        # buy and hold over the same average holding period
        hold = int(np.nanmean([res[m][2] for m in res]))
        fwd = pd.Series(c).shift(-hold) / pd.Series(c) - 1
        bh = float(fwd[sig].mean())
        rows.append(dict(sym=sym, n=res["all_in"][1], bh=bh,
                         **{m: res[m][0] for m in res}))
        print("  %-10s %8d %+8.2f%% %+8.2f%% %+8.2f%% %+8.2f%% %+9.2f%%"
              % (sym, res["all_in"][1], 100 * res["all_in"][0],
                 100 * res["pyramid_in"][0], 100 * res["pyramid_out"][0],
                 100 * res["both"][0], 100 * bh))
    R = pd.DataFrame(rows)
    print("\n  %-10s %8d %+8.2f%% %+8.2f%% %+8.2f%% %+8.2f%% %+9.2f%%"
          % ("AVERAGE", R.n.sum(), 100 * R.all_in.mean(), 100 * R.pyramid_in.mean(),
             100 * R.pyramid_out.mean(), 100 * R["both"].mean(), 100 * R.bh.mean()))
    print("\n  Per trade, averaged over %d trades across %d markets."
          % (R.n.sum(), len(R)))
    print("  buy&hold = simply holding the same instrument for the same number of")
    print("  days, starting on the same signal. That is the honest control.")

    best = max(["all_in", "pyramid_in", "pyramid_out", "both"],
               key=lambda m: R[m].mean())
    print("\n  best execution style: %s" % best)
    print("  does ANY style beat just holding? %s"
          % ("yes" if max(R[m].mean() for m in
                          ["all_in", "pyramid_in", "pyramid_out", "both"]) > R.bh.mean()
             else "NO -- holding the signal beats every tranching scheme"))
    R.to_csv("scaling_results.csv", index=False)


if __name__ == "__main__":
    main()
