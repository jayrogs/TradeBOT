"""
rider_v3.py -- the rider with a trailing stop anchored to the 12 EMA itself.

    python rider_v3.py                 sweep the stop tolerance
    python rider_v3.py --n 40

THE RULE
  entry   the ride is armed, the EMA is rising, the ride has some age, and the
          CLOSE is within ENTRY_MAX_ATR of the EMA -- as close to the line as
          possible, because the distance above it is risk you take on before the
          trade starts
  exit    price dips more than X% below the 12 EMA. Nothing else. The stop
          trails upward as the EMA rises, so a winner is held until the line
          genuinely fails

WHY THIS REPLACED THE PREVIOUS STOP
v2 stopped on a break of the previous candle's low. On the bar after entry that
candle IS the entry candle, whose low sits just underneath an entry taken at the
EMA -- so the stop was a few ticks away and the first wiggle took it out. Median
hold: ONE bar, 13% winners. The stop was too tight to let anything breathe.

A percentage below the EMA is anchored to the thing the playbook is actually
about, and it gives the trade room in proportion to where the line is.

READ THE WHOLE CURVE, NOT THE BEST ROW
This sweeps the tolerance, and sweeping is how the other ~22,000 configurations
in this project produced winners that died out of sample. A single good X among
a dozen is what a sweep produces from noise. What would be persuasive is a
SMOOTH relationship -- returns improving steadily with room, then flattening --
because noise does not come in gradients. Every row is scored against its own
random-entry null with the same holding periods.
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
ENTRY_MAX_ATR = 0.15
MIN_AGE = 3
STOPS = [0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05]


def trades(df, stop_pct):
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
        for k in range(i + MIN_AGE, j + 1):
            if near[k] and rising[k]:
                entry = k
                break
        if entry is None or entry >= n - 2:
            i = j + 1
            continue

        px = None
        for k in range(entry + 1, n):
            floor = e[k] * (1 - stop_pct)     # trails up with the EMA
            if lo[k] <= floor:
                px = floor
                break
        if px is None:
            i = j + 1
            continue
        out.append(dict(bars=int(k - entry), stop=stop_pct,
                        net=float(px / c[entry] - 1 - 2 * COST)))
        i = j + 1
    return out


def null_for(df, n_trades, stop_pct, rng, reps=12):
    """Random entries run through the SAME trailing stop.

    THE PREVIOUS NULL WAS WRONG AND IT MATTERED. It drew random entries and held
    them for the same NUMBER of bars as the real trades. But a real trade lasts
    365 bars precisely BECAUSE it never hit its stop -- the holding period is
    selected for winning. Handing that same 365 bars to a random entry that
    faced no such filter compares a survivor against a non-survivor, and it
    manufactured an edge that grew with the stop width: +6.6% at a 5% stop.

    Here the random entry is put through the identical rule, so its holding
    period emerges the same way and the two are finally comparable.
    """
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    e = rider.ema(c)
    n = len(c)
    means = []
    for _ in range(reps):
        vals = []
        for _ in range(n_trades):
            i = int(rng.integers(0, n - 5))
            px = None
            for k in range(i + 1, n):
                floor = e[k] * (1 - stop_pct)
                if lo[k] <= floor:
                    px = floor
                    break
            if px is not None:
                vals.append(px / c[i] - 1 - 2 * COST)
        if vals:
            means.append(float(np.mean(vals)))
    return float(np.mean(means)) if means else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="15m,1h,4h,1d")
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

    rng = np.random.default_rng(3)
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
            for sp in STOPS:
                t = trades(df, sp)
                if not t:
                    continue
                for x in t:
                    x.update(sym=sym, tf=tf)
                rows += t
                nulls.append(dict(stop=sp, tf=tf,
                                  null=null_for(df, len(t), sp, rng)))
        print("  %-6s" % sym, end="\r")

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no trades")
        return
    R.to_csv("rider_v3.csv", index=False)

    print("\n" + "=" * 84)
    print("  TRAILING STOP: X%% BELOW THE 12 EMA -- crypto, %.1f%% round trip"
          % (200 * COST))
    print("=" * 84)
    print("  %-8s %8s %10s %10s %7s %7s %10s"
          % ("stop", "trades", "mean", "median", "win%", "bars", "vs null"))
    print("  " + "-" * 78)
    for sp in STOPS:
        g = R[R.stop == sp]
        if g.empty:
            continue
        nn = N[N.stop == sp].null.mean()
        print("  %-8s %8d %+9.3f%% %+9.3f%% %6.0f%% %7.0f %+9.3f%%"
              % ("%.2f%%" % (100 * sp), len(g), 100 * g.net.mean(),
                 100 * g.net.median(), 100 * (g.net > 0).mean(),
                 g.bars.median(), 100 * (g.net.mean() - nn)))

    print()
    print("  by timeframe, at each stop (edge over null)")
    print("  %-8s %s" % ("stop", "".join("%10s" % t for t in tfs)))
    for sp in STOPS:
        cells = []
        for tf in tfs:
            g = R[(R.stop == sp) & (R.tf == tf)]
            nn = N[(N.stop == sp) & (N.tf == tf)].null.mean()
            cells.append("%+9.3f%%" % (100 * (g.net.mean() - nn)) if len(g) else "        -")
        print("  %-8s %s" % ("%.2f%%" % (100 * sp), "".join(cells)))

    e = [(sp, R[R.stop == sp].net.mean() - N[N.stop == sp].null.mean())
         for sp in STOPS if len(R[R.stop == sp])]
    xs = np.array([x[0] for x in e])
    ys = np.array([x[1] for x in e])
    print()
    print("  edge vs stop size, correlation: %+.3f" % np.corrcoef(xs, ys)[0, 1])
    print("  (a real effect should trend smoothly; a single good row is noise)")
    print("  full table: rider_v3.csv")


if __name__ == "__main__":
    main()
