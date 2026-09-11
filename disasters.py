"""
disasters.py -- what do the catastrophic dip-buys look like, and could you tell?

    python disasters.py

TWO CORRECTIONS TO THE PREVIOUS TEST

1. The add rule was wrong. I added a tranche on every -5% in price. The user's
   actual rule is: only add while RSI is still making NEW LOWS. If RSI stops
   falling while price falls, that is the signal to stop adding and start
   selling into the bounce -- not to add more.

2. The question is not "how bad does it get" but "could you have known". So
   every setup is tagged with what was visible at entry and in the first few
   bars after, and the wipeouts are compared against the recoveries.

THE THING BEING HUNTED
    the 0.6% that never come back. What did they look like at RSI 30? Did RSI
    keep making new lows all the way down (so the rule kept you buying), or did
    it flatten early (so the rule would have stopped you)?
"""

import os
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
OVERSOLD = 35
MAX_ADDS = 4
HORIZON = 250


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def run(sym, d):
    hi = P.resample(d, "W-FRI")
    if len(hi) < 30 or len(d) < 300:
        return []
    st_h, _, _ = P.trend_state(hi)
    ctx = pd.Series(st_h, index=hi.index).reindex(d.index, method="ffill").values
    c = d["Close"].values.astype(float)
    l = d["Low"].values.astype(float)
    r = rsi(c)
    ma200 = pd.Series(c).rolling(200).mean().values
    vol = pd.Series(c).pct_change().rolling(20).std()
    volr = vol.rank(pct=True).values
    hi52 = pd.Series(c).rolling(252).max().values

    os_now = r < OVERSOLD
    trig = (ctx == "UP") & os_now & ~np.roll(os_now, 1)
    trig[:60] = False

    out = []
    for i0 in np.where(trig)[0]:
        lots = [c[i0]]
        rsi_low = r[i0]              # only add on a NEW RSI low
        worst_avg = 0.0
        recovered = None
        rsi_at_worst = np.nan
        worst_i = i0
        stopped_adding = None
        for i in range(i0 + 1, min(i0 + HORIZON, len(c))):
            if len(lots) < MAX_ADDS and r[i] < rsi_low and c[i] < lots[-1]:
                lots.append(c[i])
                rsi_low = r[i]
            elif stopped_adding is None and r[i] > rsi_low + 5 and c[i] < np.mean(lots):
                # RSI cooling while price still under water -- the user's
                # signal to stop adding and sell into the bounce
                stopped_adding = i - i0
            avg = float(np.mean(lots))
            dd = l[i] / avg - 1
            if dd < worst_avg:
                worst_avg = dd
                rsi_at_worst = r[i]
                worst_i = i
            if c[i] >= avg:
                recovered = i - i0
                break
        out.append(dict(
            symbol=sym, date=d.index[i0], adds=len(lots) - 1,
            rsi_entry=r[i0], rsi_at_worst=rsi_at_worst,
            vs200=c[i0] / ma200[i0] - 1 if np.isfinite(ma200[i0]) else np.nan,
            volpct=volr[i0], dd52=c[i0] / hi52[i0] - 1 if np.isfinite(hi52[i0]) else np.nan,
            mae=worst_avg, recovered=recovered is not None,
            bars=recovered if recovered is not None else HORIZON,
            rsi_cooled_at=stopped_adding))
    return out


def main():
    data = pd.read_pickle(CACHE)
    rows = []
    for sym, d in data.items():
        if len(d) < 500:
            continue
        try:
            rows += run(sym, d)
        except Exception:
            continue
    R = pd.DataFrame(rows)
    R.to_csv("disasters.csv", index=False)

    bad = R[~R.recovered]
    good = R[R.recovered]
    print("=" * 78)
    print("  %d setups. %d never recovered (%.1f%%)"
          % (len(R), len(bad), 100 * len(bad) / len(R)))
    print("  add rule corrected: only add while RSI makes a NEW LOW")
    print("=" * 78)

    print("\n  WHAT WAS VISIBLE AT ENTRY?")
    print("  %-22s %14s %14s" % ("", "recovered", "never recovered"))
    for col, lab in [("rsi_entry", "RSI at entry"),
                     ("vs200", "vs 200-day MA"),
                     ("volpct", "volatility pctile"),
                     ("dd52", "off 52-week high"),
                     ("adds", "tranches added")]:
        a, b = good[col].median(), bad[col].median()
        fmt = "%13.1f%%" if col in ("vs200", "dd52") else "%14.2f"
        if col in ("vs200", "dd52"):
            print("  %-22s %13.1f%% %13.1f%%" % (lab, 100 * a, 100 * b))
        else:
            print("  %-22s %14.2f %14.2f" % (lab, a, b))

    print("\n  RSI AT THE WORST POINT  (did it keep making new lows?)")
    print("     recovered      : median RSI %.1f" % good.rsi_at_worst.median())
    print("     never recovered: median RSI %.1f" % bad.rsi_at_worst.median())
    print("\n  'RSI cooled off' warning fired before the worst point:")
    print("     recovered      : %.0f%%" % (100 * good.rsi_cooled_at.notna().mean()))
    print("     never recovered: %.0f%%" % (100 * bad.rsi_cooled_at.notna().mean()))

    print("\n" + "=" * 78)
    print("  THE 15 WORST OUTCOMES")
    print("=" * 78)
    print("  %-10s %-12s %8s %9s %9s %7s %8s"
          % ("symbol", "date", "RSI in", "worst", "RSI@worst", "adds", "back?"))
    for _, x in R.nsmallest(15, "mae").iterrows():
        print("  %-10s %-12s %8.1f %8.1f%% %9.1f %7d %8s"
              % (x.symbol, str(x.date.date()), x.rsi_entry, 100 * x.mae,
                 x.rsi_at_worst, x.adds, "yes" if x.recovered else "NO"))

    print("\n" + "=" * 78)
    print("  DOES A LOWER ENTRY RSI MEAN MORE DANGER?")
    print("=" * 78)
    R["bucket"] = pd.cut(R.rsi_entry, [0, 15, 20, 25, 30, 35])
    g = R.groupby("bucket").agg(n=("mae", "size"), med_mae=("mae", "median"),
                                p99=("mae", lambda x: x.quantile(0.01)),
                                fail=("recovered", lambda x: 1 - x.mean()))
    print("  %-14s %8s %12s %12s %10s" % ("entry RSI", "n", "median heat",
                                          "1-in-100", "never back"))
    for b, x in g.iterrows():
        if x.n < 20:
            continue
        print("  %-14s %8d %11.1f%% %11.1f%% %9.1f%%"
              % (str(b), x.n, 100 * x.med_mae, 100 * x.p99, 100 * x.fail))


if __name__ == "__main__":
    main()
