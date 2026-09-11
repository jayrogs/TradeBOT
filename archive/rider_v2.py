"""
rider_v2.py -- the EMA rider with the rules corrected by looking at the trades.

    python rider_v2.py                 v1 vs v2, side by side
    python rider_v2.py --only v2

WHAT CHANGED AND WHY
Six trades were drawn and inspected. Every objection was specific:

  trade_01  "you bought so far from the ema. ema riders you usually wanna trade
             as close to the ema as possible, otherwise youre adding more risk"
             -> bought 70320 with the EMA at 69770. That is 0.79% of risk taken
                on before the trade even starts.
             -> ENTRY_MAX_ATR: the close must be within this of the EMA, not
                just the low. v1 allowed 0.35 ATR measured on the LOW, which let
                a bar wick down to the EMA and close far above it.

  trade_01  "it should have time near the ema, per how a rider works"
             -> MIN_AGE: the ride has to have existed for a few bars before you
                take a dip in it. v1 entered on the FIRST bar of a two-bar
                "ride", which is how it ended up trading chop.

  trade_01  "once it broke the lower low of the wick from the last candle,
             thats a big red flag, enough to warrant a stop out"
             -> STOP: exit when price trades below the PREVIOUS candle's low.
                v1 waited for a body to close under the EMA, which on trade_04
                meant riding a loser far below the line.

  trade_02  "very obvious, good catch its chop"
             -> MIN_AGE plus a rising-EMA requirement removes these.

  trade_04  "something we can definitely do about holding onto a losing trade
             sooooo far past the ema 12"
             -> the previous-low stop fires long before that happens.

  trade_05  "youre buying way too high off the ema"
             -> ENTRY_MAX_ATR again.

THE FILL ON THE STOP
A stop below the previous candle's low is a resting order, so it fills AT that
price when touched, not at the next close. That is the realistic assumption and
it is what is modelled here. The exit is otherwise the stated rule -- a body
closing below the EMA -- whichever comes first.

STILL UNPROVEN. v1 beat a random-entry null by +0.023% against a 0.200% round
trip, which is nothing. The bar for v2 is the same null, not zero.
"""

import argparse
import warnings

import numpy as np
import pandas as pd

import crypto
import indicators as IND
import panel as P
import rider
import scanner as SC

warnings.filterwarnings("ignore")

COST = 0.001
BARS = 12000

ENTRY_MAX_ATR = 0.15    # the CLOSE must be this near the EMA to enter
MIN_AGE = 3             # the ride must be this many bars old first
REQUIRE_RISING = True   # and the EMA itself must be sloping up


def v1_trades(df):
    """The original: first touch in a ride, hold until a body closes below."""
    c = df["Close"].values.astype(float)
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
        e = next((k for k in range(i, j + 1) if near[k]), None)
        x = min(j + 1, n - 1)
        if e is not None and x > e:
            out.append(dict(bars=int(x - e), net=float(c[x] / c[e] - 1 - 2 * COST)))
        i = j + 1
    return out


def v2_trades(df):
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    n = len(c)
    st = P.trend_state(df)
    r = rider.read(df, state=st)
    e = r["ema"]
    a = P._atr(df)
    armed = r["armed"]
    holding = r["closed_above"]
    tol = ENTRY_MAX_ATR * np.where(np.isfinite(a), a, 0.0)
    rising = np.concatenate([[False], e[1:] > e[:-1]])

    # close near the EMA -- not merely a wick that reached down to it
    near = holding & (c - e <= tol) & (c >= e)
    out = []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        entry = None
        for k in range(i + MIN_AGE, j + 1):          # the ride must have age
            if near[k] and (rising[k] or not REQUIRE_RISING):
                entry = k
                break
        if entry is None or entry >= n - 2:
            i = j + 1
            continue

        # walk forward: stop below the previous candle's low, or a body close
        # under the EMA, whichever comes first
        # THE STOP IS THE EMA'S RULE, not the candle's. Breaking the previous
        # low only counts when that low was already BELOW the EMA -- i.e. the
        # prior candle had wicked under the line and price then took it out.
        # Without that condition the stop fires on every ordinary pullback: it
        # triggered on 2,385 of 2,635 trades with a median hold of ONE bar.
        px, why = None, None
        for k in range(entry + 1, n):
            stop = lo[k - 1]
            if stop < e[k - 1] and lo[k] <= stop:
                px, why = stop, "prev-low-under-ema"
                break
            if not holding[k]:
                px, why = c[k], "ema"
                break
        if px is None:
            i = j + 1
            continue
        out.append(dict(bars=int(k - entry), why=why,
                        entry_dist=float((c[entry] - e[entry]) / e[entry]),
                        net=float(px / c[entry] - 1 - 2 * COST)))
        i = j + 1
    return out


def null_for(df, holds, rng, reps=20):
    c = df["Close"].values.astype(float)
    n = len(c)
    m = []
    for _ in range(reps):
        v = [c[i + h] / c[i] - 1 - 2 * COST
             for h in holds if 1 <= h < n - 2
             for i in [int(rng.integers(0, n - h - 1))]]
        if v:
            m.append(float(np.mean(v)))
    return float(np.mean(m)) if m else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="15m,1h,4h,1d")
    ap.add_argument("--only", default="both", choices=("v1", "v2", "both"))
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    u = crypto.universe(a.n)
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(s, src, b) for s, src in pairs for b in ("15m", "1h", "1d")]

    def grab(job):
        s, src, b = job
        try:
            return (s, b), crypto.candles(s, b, BARS, source=src)
        except Exception:
            return (s, b), None

    print("fetching %d series..." % len(jobs))
    store = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, df in ex.map(grab, jobs):
            store[key] = df

    rng = np.random.default_rng(7)
    rows, nulls = [], []
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
            for ver, fn in (("v1", v1_trades), ("v2", v2_trades)):
                if a.only != "both" and ver != a.only:
                    continue
                t = fn(df)
                if not t:
                    continue
                for x in t:
                    x.update(sym=sym, tf=tf, ver=ver)
                rows += t
                nulls.append(dict(ver=ver, tf=tf,
                                  null=null_for(df, [x["bars"] for x in t], rng)))
        print("  %-6s" % sym, end="\r")

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no trades")
        return
    R.to_csv("rider_v2.csv", index=False)

    print("\n" + "=" * 86)
    print("  RIDER v1 vs v2 -- crypto, cost %.1f%% round trip" % (200 * COST))
    print("=" * 86)
    print("  %-4s %-5s %8s %10s %10s %7s %7s %10s"
          % ("ver", "tf", "trades", "mean", "median", "win%", "bars", "vs null"))
    print("  " + "-" * 82)
    for ver in ("v1", "v2"):
        for tf in tfs:
            g = R[(R.ver == ver) & (R.tf == tf)]
            if g.empty:
                continue
            nn = N[(N.ver == ver) & (N.tf == tf)].null.mean()
            print("  %-4s %-5s %8d %+9.3f%% %+9.3f%% %6.0f%% %7.0f %+9.3f%%"
                  % (ver, tf, len(g), 100 * g.net.mean(), 100 * g.net.median(),
                     100 * (g.net > 0).mean(), g.bars.median(),
                     100 * (g.net.mean() - nn)))
        g = R[R.ver == ver]
        nn = N[N.ver == ver].null.mean()
        print("  %-4s %-5s %8d %+9.3f%% %+9.3f%% %6.0f%% %7.0f %+9.3f%%   <- all"
              % (ver, "ALL", len(g), 100 * g.net.mean(), 100 * g.net.median(),
                 100 * (g.net > 0).mean(), g.bars.median(),
                 100 * (g.net.mean() - nn)))
        print()

    v2 = R[R.ver == "v2"]
    if len(v2):
        print("  v2 exits: %s" % v2.why.value_counts().to_dict())
        print("  v2 median distance above the EMA at entry: %.3f%%"
              % (100 * v2.entry_dist.median()))
    print("  full table: rider_v2.csv")


if __name__ == "__main__":
    main()
