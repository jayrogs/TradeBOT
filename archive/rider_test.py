"""
rider_test.py -- does the EMA 12 Rider actually make money?

    python rider_test.py                  crypto, 5m/15m/1h/4h/12h/1d
    python rider_test.py --n 40 --tf 1h

WHAT IS BEING TESTED
The playbook, exactly as it was graded: while the ride is ARMED (trend up, the
candle body holding the 12 EMA, higher lows stacked), buy the dips back into the
EMA. Hold until the ride dies -- a body close under the EMA, or a close under
the last higher low.

That is a complete trade with an entry and an exit, so it can be scored.

WHY CRYPTO
It is the only market where we have deep intraday history for free. Yahoo caps
equities, futures and FX at 60 days of 5m, which is not enough to test anything.
Coinbase and OKX page back years at any interval.

THE CONTROLS, because a positive number alone means nothing here
    baseline   the average forward return over the SAME holding period, from
               every bar in the same series. Crypto drifts; a strategy that
               merely holds during an uptrend will look good against zero and
               awful against this
    random     entries drawn at random with the same count and the same holding
               periods. This is the honest null: same exposure, no signal

Roughly 22,000 configurations have been tested in this project and none beat
buy-and-hold out of sample. Five apparent winners turned out to be measurement
artifacts. Expect nothing and check the controls first.

COSTS
0.1% per side, which is a realistic crypto taker fee. On short holds this is not
a rounding error and it is applied to every trade.
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

COST = 0.001            # per side
BARS = 12000            # per name per base timeframe


def trades(df, tf, exit_rule="hl"):
    """Every dip-into-the-EMA entry, and where the trade ended.

    EXIT RULES
      "body" hold until a candle BODY closes below the 12 EMA. Nothing else --
             no higher-low stop. This is the stated rule: "keep holding your
             entry until a candle body closes below the ema12; when it works
             out it usually keeps going". Expect a negative median and a
             positive mean -- many small losses, occasional long runs. Judge it
             on the MEAN against the null, not on the win rate.
      "ema"  body under the EMA *or* under the last higher low. Mixing the two
             is what produced two-bar trades earlier.
      "hl"   close under the last higher low -- the stated exit rule, and the
             blue line on the charts. It sits meaningfully below the entry, so
             the trade has room to ride.
    """
    if df is None or len(df) < 120:
        return []
    st = P.trend_state(df)
    state, hl, _ = st
    r = rider.read(df, state=st)
    c = r["close"]
    n = len(c)
    entries = np.where(r["pullback"] & r["armed"])[0]
    if exit_rule == "ema":
        dead = r["dead"]
    elif exit_rule in ("body", "ride"):
        dead = ~r["closed_above"]
    else:
        dead = np.isfinite(hl) & (c < hl)

    if exit_rule == "ride":
        # ONE TRADE PER RIDE. Enter once, near the EMA so the stop is tight,
        # then hold until a body closes below it.
        #
        # Everything before this re-entered on EVERY bar whose low came near the
        # EMA, which in a tight grind along the line is bar after bar: 13,663
        # trades from 30 names, median hold 4 bars, paying 0.2% round trip each
        # time. That is not the playbook, it is the playbook run 13,663 times
        # and charged for it.
        armed = r["armed"]
        near = r["pullback"]
        out = []
        i = 0
        while i < n:
            if not armed[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and armed[j + 1]:
                j += 1
            # first touch near the EMA inside this ride
            entry = next((k for k in range(i, j + 1) if near[k]), None)
            # Exit on the bar AFTER the ride dies, not on its last live bar.
            # `armed[j] and not armed[j+1]` means the body closed below the EMA
            # at j+1 -- so j+1 is when you KNOW, and j+1's close is what you
            # actually get. Selling at c[j] is a one-bar lookahead into the last
            # good price before the break, and it flatters every trade.
            x = min(j + 1, n - 1)
            if entry is not None and x > entry and x < n:
                out.append(dict(tf=tf, i=int(entry), j=int(x), bars=int(x - entry),
                                gross=float(c[x] / c[entry] - 1),
                                net=float((c[x] * (1 - COST)) /
                                          (c[entry] * (1 + COST)) - 1)))
            i = j + 1
        return out

    out = []
    last_exit = -1
    for i in entries:
        if i <= last_exit or i >= n - 2:
            continue                      # no overlapping positions
        if exit_rule == "hl" and np.isfinite(hl[i]) and c[i] < hl[i]:
            continue                      # stop already gone: not a trade
        j = None
        for k in range(i + 1, n):
            if dead[k]:
                j = k
                break
        if j is None:
            continue                      # still open at the end of the data
        out.append(dict(tf=tf, i=int(i), j=int(j), bars=int(j - i),
                        gross=float(c[j] / c[i] - 1),
                        net=float((c[j] * (1 - COST)) / (c[i] * (1 + COST)) - 1)))
        last_exit = j
    return out


def baseline(df, holds):
    """What the same holding periods earn from an ARBITRARY bar."""
    c = df["Close"].values.astype(float)
    n = len(c)
    out = []
    for h in holds:
        if h < 1 or h >= n - 2:
            continue
        fwd = c[h:] / c[:-h] - 1
        out.append(float(np.nanmean(fwd)))
    return float(np.mean(out)) if out else np.nan


def random_null(df, holds, rng, reps=20):
    """Same number of trades, same holding periods, entries drawn at random."""
    c = df["Close"].values.astype(float)
    n = len(c)
    means = []
    for _ in range(reps):
        vals = []
        for h in holds:
            if h < 1 or h >= n - 2:
                continue
            i = int(rng.integers(0, n - h - 1))
            vals.append((c[i + h] * (1 - COST)) / (c[i] * (1 + COST)) - 1)
        if vals:
            means.append(float(np.mean(vals)))
    return float(np.mean(means)) if means else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="5m,15m,1h,4h,12h,1d")
    ap.add_argument("--exit", default="hl", choices=("hl", "ema", "body", "ride"))
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    print("universe...")
    u = crypto.universe(a.n)
    print("  %d names" % len(u))

    rng = np.random.default_rng(11)
    rows, ctrl = [], []

    # 12,000 bars at 300 per request is ~40 calls per (name, base), so ~160 per
    # name. Sequentially that was 113 seconds a name -- 53 minutes for thirty.
    # The same thread pool the live scanner uses cuts it to a few minutes.
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(sym, src, b) for sym, src in pairs
            for b in ("5m", "15m", "1h", "1d")]

    def grab(job):
        sym, src, b = job
        try:
            return (sym, b), crypto.candles(sym, b, BARS, source=src)
        except Exception:
            return (sym, b), None

    print("fetching %d series..." % len(jobs))
    store = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (key, df) in enumerate(ex.map(grab, jobs), 1):
            store[key] = df
            if i % 20 == 0:
                print("  %d/%d" % (i, len(jobs)))

    for sym, src in pairs:
        raw = {b: store.get((sym, b)) for b in ("5m", "15m", "1h", "1d")}
        for tf in tfs:
            if tf in SC.BASE:
                df = raw.get(SC.BASE[tf])
            elif tf in SC.DERIVE:
                s, rule = SC.DERIVE[tf]
                df = SC.resample(raw.get(SC.BASE[s]), rule)
            else:
                df = None
            if df is None or len(df) < 200:
                continue
            t = trades(df, tf, a.exit)
            if not t:
                continue
            for x2 in t:
                x2["sym"] = sym
            rows += t
            holds = [x2["bars"] for x2 in t]
            ctrl.append(dict(sym=sym, tf=tf, n=len(t),
                             base=baseline(df, holds),
                             rand=random_null(df, holds, rng)))
        print("  %-6s %d trades so far" % (sym, len(rows)))

    R = pd.DataFrame(rows)
    C = pd.DataFrame(ctrl)
    if R.empty:
        print("no trades")
        return
    R.to_csv("rider_test_trades.csv", index=False)

    print()
    print("=" * 78)
    print("  EMA 12 RIDER -- %d trades, %d names, crypto" % (len(R), R.sym.nunique()))
    print("=" * 78)
    print("  entry: dip into the EMA while armed")
    print("  exit : %s" % {"hl": "close under the last higher low",
                            "body": "a candle BODY closes below the 12 EMA",
                            "ema": "body under the EMA, or under the higher low",
                            "ride": "ONE entry per ride, held until a body closes below the EMA"}[a.exit])
    print("  costs: %.1f%% per side" % (100 * COST))
    print()
    print("  %-6s %7s %9s %9s %9s %8s %9s"
          % ("tf", "trades", "median", "mean", "win%", "bars", "vs random"))
    print("  " + "-" * 74)
    for tf in tfs:
        g = R[R.tf == tf]
        if g.empty:
            continue
        cc = C[C.tf == tf]
        rand = cc.rand.mean() if len(cc) else np.nan
        print("  %-6s %7d %+8.3f%% %+8.3f%% %8.0f%% %8.0f %+8.3f%%"
              % (tf, len(g), 100 * g.net.median(), 100 * g.net.mean(),
                 100 * (g.net > 0).mean(), g.bars.median(),
                 100 * (g.net.mean() - rand)))

    print()
    print("  ALL: %d trades   mean %+.3f%%   median %+.3f%%   win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean()))
    print("  controls, averaged over every name and timeframe:")
    print("    same holding period from an arbitrary bar : %+.3f%%"
          % (100 * C.base.mean()))
    print("    same trades, entries drawn at random      : %+.3f%%"
          % (100 * C.rand.mean()))
    edge = R.net.mean() - C.rand.mean()
    print()
    print("  EDGE OVER THE RANDOM NULL: %+.3f%% per trade" % (100 * edge))
    # An edge of a couple of basis points on a 0.2% cost base is noise, not a
    # finding. Anything under a tenth of the round-trip cost gets called what it
    # is.
    if edge > 2 * COST:
        verdict = "beats its own null by more than the round trip costs"
    elif edge > 0.2 * COST:
        verdict = "positive but smaller than the round trip -- marginal"
    else:
        verdict = "NO EDGE -- inside the noise, random entries did as well"
    print("  -> %s" % verdict)
    print()
    print("  gross, before costs: mean %+.3f%%  (costs take %.3f%%)"
          % (100 * R.gross.mean(), 100 * (R.gross.mean() - R.net.mean())))
    print("  full table: rider_test_trades.csv")


if __name__ == "__main__":
    main()
