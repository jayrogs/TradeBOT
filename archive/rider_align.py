"""
rider_align.py -- does multi-timeframe alignment make the rider work?

    python rider_align.py

THE CLAIM
"Usually the more green trends the better, on different time frames. The wind
is at your back if you're playing bull."

So: take the same one-trade-per-ride EMA rider, and at the moment of entry count
how many HIGHER timeframes read UP. Then sort the results by that count. If the
claim holds, returns should rise monotonically with alignment -- and the top
bucket has to clear the 0.2% round-trip cost, not merely be positive.

WHAT HAS ALREADY FAILED, so this is not tested in a vacuum
  plain rider          +0.023% per trade against a 0.200% cost -- nothing
  name selection       past EMA obedience predicts future return at r = +0.015,
                       which is no relationship at all
  short side           every obedience bucket negative, and MORE obedient was
                       WORSE (r = -0.132). Shorting the 12 EMA as resistance
                       lost money in crypto over this window

Alignment is a genuinely different filter from either of those, so it deserves
its own test rather than an assumption.

NO LOOKAHEAD
The higher-timeframe state is taken from bars that had CLOSED at the moment of
entry, forward-filled onto the trading timeframe. An earlier version of this
test exited on the last bar of a ride rather than the bar after it broke, and
that single bar of hindsight was worth +1.0% per trade -- the entire apparent
edge. Anything that looks good here should be assumed to have a similar hole
until it survives being looked for.
"""

import argparse
import warnings

import numpy as np
import pandas as pd

import crypto
import panel as P
import rider
import scanner as SC

warnings.filterwarnings("ignore")

COST = 0.001
BARS = 12000
HIGHER = ["1h", "4h", "12h", "1d", "1w"]


def ride_trades(df):
    """One trade per ride: enter at the first touch, exit the bar after it breaks."""
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    n = len(c)
    st = P.trend_state(df)
    r = rider.read(df, state=st)
    armed, near = r["armed"], r["pullback"]
    out = []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        entry = next((k for k in range(i, j + 1) if near[k]), None)
        x = min(j + 1, n - 1)
        if entry is not None and x > entry:
            out.append(dict(i=int(entry), j=int(x), bars=int(x - entry),
                            net=float(c[x] / c[entry] - 1 - 2 * COST)))
        i = j + 1
    return out


def higher_states(raw, index):
    """UP/DOWN/other on each higher timeframe, aligned to `index` by ffill.

    Forward-fill is what makes this causal: a 1d bar only becomes known at its
    close, so its state applies to trading bars AFTER it, never before.
    """
    out = {}
    for tf in HIGHER:
        if tf in SC.BASE:
            df = raw.get(SC.BASE[tf])
        else:
            src, rule = SC.DERIVE[tf]
            df = SC.resample(raw.get(SC.BASE[src]), rule)
        if df is None or len(df) < 60:
            out[tf] = None
            continue
        st, _, _ = P.trend_state(df)
        s = pd.Series(st, index=df.index).reindex(index, method="ffill")
        out[tf] = s.values
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="15m,1h,4h")
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    u = crypto.universe(a.n)
    print("universe: %d names" % len(u))
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(s, src, b) for s, src in pairs for b in ("15m", "1h", "1d")]

    def grab(job):
        s, src, b = job
        try:
            return (s, b), crypto.candles(s, b, BARS, source=src)
        except Exception:
            return (s, b), None

    store = {}
    print("fetching %d series..." % len(jobs))
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, df in ex.map(grab, jobs):
            store[key] = df

    rows = []
    for sym, src in pairs:
        raw = {b: store.get((sym, b)) for b in ("15m", "1h", "1d")}
        for tf in tfs:
            if tf in SC.BASE:
                df = raw.get(SC.BASE[tf])
            else:
                s2, rule = SC.DERIVE[tf]
                df = SC.resample(raw.get(SC.BASE[s2]), rule)
            if df is None or len(df) < 400:
                continue
            hs = higher_states(raw, df.index)
            for t in ride_trades(df):
                k = t["i"]
                ups = sum(1 for x in HIGHER
                          if hs.get(x) is not None and hs[x][k] == "UP")
                have = sum(1 for x in HIGHER if hs.get(x) is not None)
                rows.append(dict(sym=sym, tf=tf, ups=ups, have=have,
                                 bars=t["bars"], net=t["net"]))
        print("  %-6s" % sym, end="\r")

    R = pd.DataFrame(rows)
    if R.empty:
        print("no trades")
        return
    R = R[R.have >= 4]
    R.to_csv("rider_align.csv", index=False)

    print("\n" + "=" * 80)
    print("  ALIGNMENT: does the rider do better with more green above it?")
    print("=" * 80)
    print("  %d trades, %d names. Cost 0.200%% round trip." % (len(R), R.sym.nunique()))
    print()
    print("  %-22s %8s %10s %10s %8s %8s"
          % ("higher TFs reading UP", "trades", "mean", "median", "win%", "bars"))
    print("  " + "-" * 72)
    for k, g in R.groupby("ups"):
        print("  %-22s %8d %+9.3f%% %+9.3f%% %7.0f%% %8.0f"
              % ("%d of %d" % (k, int(g.have.median())), len(g),
                 100 * g.net.mean(), 100 * g.net.median(),
                 100 * (g.net > 0).mean(), g.bars.median()))
    c = R.ups.corr(R.net)
    print()
    print("  correlation between alignment and return: %+.4f" % c)
    top = R[R.ups >= 4]
    print("  4+ higher timeframes up: %d trades, %+.3f%% per trade vs %.3f%% cost"
          % (len(top), 100 * top.net.mean(), 200 * COST))
    print("  full table: rider_align.csv")


if __name__ == "__main__":
    main()
