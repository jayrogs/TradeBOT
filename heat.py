"""
heat.py -- how much heat do you take, and how often does it never come back?

    python heat.py

THE PROBLEM THE USER RAISED
    "you just have to take the heat as long as it keeps going down. usually you
     enter around 30 rsi, keep entering if it keeps going lower quickly, and
     sell on the rebound at least half to make your average break even. so
     you're not even really sure what your maximum loss is."

There is no stop in this method, by design -- selling into the fall would
abandon the setup. So the risk is not "where is my stop", it is:

    how far does it go against me before it bounces,
    how long am I stuck,
    and how often does it simply never come back?

That last number is the one that decides position size, and it is the only one
that can ruin you.

WHAT IS SIMULATED
    context   higher timeframe trend light GREEN
    entry 1   lower timeframe RSI(14) drops below 35
    adds      a further tranche every ADD_DROP lower, up to MAX_ADDS
    exit      average cost recovered (break even) -- the user sells at least
              half there
    measured  worst excursion below average cost, bars underwater, and the
              share that never recover inside the horizon

Reported as percentiles, not averages. The average is useless here; the tail is
the whole question.
"""

import os
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
OVERSOLD = 35
ADD_DROP = 0.05          # add another tranche every 5% lower
MAX_ADDS = 4             # first entry plus 3 adds
HORIZON = 250            # bars allowed to recover


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def run(sym, d, hi_rule, lo_rule):
    hi = P.resample(d, hi_rule)
    lo = P.resample(d, lo_rule) if lo_rule else d
    if len(hi) < 30 or len(lo) < 200:
        return []
    st_h, _, _ = P.trend_state(hi)
    ctx = pd.Series(st_h, index=hi.index).reindex(lo.index, method="ffill").values
    c = lo["Close"].values.astype(float)
    l = lo["Low"].values.astype(float)
    r = rsi(c)
    os_now = r < OVERSOLD
    trig = (ctx == "UP") & os_now & ~np.roll(os_now, 1)
    trig[:60] = False

    out = []
    for i0 in np.where(trig)[0]:
        lots = [c[i0]]
        next_add = c[i0] * (1 - ADD_DROP)
        worst_single = 0.0      # worst drawdown from FIRST entry
        worst_avg = 0.0         # worst drawdown from AVERAGE cost
        recovered_at = None
        for i in range(i0 + 1, min(i0 + HORIZON, len(c))):
            if len(lots) < MAX_ADDS and c[i] <= next_add:
                lots.append(c[i])
                next_add = c[i] * (1 - ADD_DROP)
            avg = float(np.mean(lots))
            worst_single = min(worst_single, l[i] / c[i0] - 1)
            worst_avg = min(worst_avg, l[i] / avg - 1)
            if c[i] >= avg:
                recovered_at = i - i0
                break
        out.append(dict(symbol=sym, adds=len(lots) - 1,
                        mae_first=worst_single, mae_avg=worst_avg,
                        bars=recovered_at if recovered_at is not None else HORIZON,
                        recovered=recovered_at is not None))
    return out


def report(R, label):
    n = len(R)
    rec = R.recovered.mean()
    print("\n" + "=" * 76)
    print("  %s   --   %d setups across %d markets" % (label, n, R.symbol.nunique()))
    print("=" * 76)
    print("  recovered to break even within %d bars : %.1f%%" % (HORIZON, 100 * rec))
    print("  NEVER recovered                        : %.1f%%   <-- the tail"
          % (100 * (1 - rec)))
    print("\n  HEAT TAKEN (worst point below your average cost)")
    print("  %-14s %10s %10s %10s %10s %10s %10s"
          % ("", "median", "75th", "90th", "95th", "99th", "worst"))
    for col, lab in [("mae_avg", "vs average"), ("mae_first", "vs 1st entry")]:
        q = R[col].quantile([0.5, 0.25, 0.10, 0.05, 0.01]).values
        print("  %-14s %9.1f%% %9.1f%% %9.1f%% %9.1f%% %9.1f%% %9.1f%%"
              % (lab, 100 * q[0], 100 * q[1], 100 * q[2], 100 * q[3],
                 100 * q[4], 100 * R[col].min()))
    print("\n  TIME UNDERWATER (bars until back to average cost)")
    q = R[R.recovered].bars.quantile([0.5, 0.75, 0.9, 0.95]).values
    print("  median %.0f   75th %.0f   90th %.0f   95th %.0f bars"
          % (q[0], q[1], q[2], q[3]))
    print("\n  TRANCHES USED")
    for k in range(MAX_ADDS):
        share = (R.adds == k).mean()
        print("     %d add%s : %5.1f%%" % (k, "" if k == 1 else "s", 100 * share))
    deep = R[R.mae_avg <= -0.20]
    print("\n  when heat exceeded 20%% below average cost (%.1f%% of setups),"
          % (100 * len(deep) / n))
    print("     %.0f%% still recovered" % (100 * deep.recovered.mean()))


def main():
    data = pd.read_pickle(CACHE)
    for label, hr, lr in [("WEEKLY context, DAILY oversold", "W-FRI", None),
                          ("MONTHLY context, WEEKLY oversold", "ME", "W-FRI")]:
        rows = []
        for sym, d in data.items():
            if len(d) < 500:
                continue
            try:
                rows += run(sym, d, hr, lr)
            except Exception:
                continue
        R = pd.DataFrame(rows)
        if not R.empty:
            report(R, label)
            R.to_csv("heat_%s.csv" % hr.replace("-", ""), index=False)


if __name__ == "__main__":
    main()
