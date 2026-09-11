"""
sweep.py -- 1,800 variants of the multi-timeframe setup, reported as a
distribution rather than as a search for a winner.

    python sweep.py

WHY A DISTRIBUTION AND NOT A WINNER
Testing 1,800 variants and reporting the best one is how false positives are
manufactured. The best of 1,800 is spectacular even when nothing is there. The
only question worth asking is whether the best of 1,800 on REAL data beats the
best of 1,800 on data where the signal has been deliberately broken.

THE NULL
For every variant, the same trigger matrix is re-run with the trigger TIMES
randomly permuted within each symbol. Same setup, same number of trades, same
prices, same volatility clustering -- only the link between signal and future
return is destroyed. Anything the real version does that the permuted version
also does is not the signal working.

THE GRID (frozen before running)
    RSI length          7, 14, 21
    oversold level      20, 25, 30, 35, 40
    lookback window     3, 6, 12 bars
    higher low          required / not
    candle confirm      required / not
    higher-tf uptrend   required / not
    holding period      3, 6, 12, 24, 48 bars
    = 1,800 combinations, run on two universes

THE TWO UNIVERSES test the user's hypothesis directly:
    high-retail   TSLA NVDA AMD PLTR SOFI RIVN ... (median 72% annual vol)
    institutional JNJ PG KO PEP MRK ABT LIN ...    (median 21% annual vol)
If crowd psychology drives these patterns, the edge should concentrate in the
first group.

Every trade is scored against its own basket's equal-weight return over the
identical hours, so a high-beta basket does not get credit for being high-beta,
and 0.20% is charged per round trip.
"""

import itertools
import os
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "sweep_hourly.pkl")

HIGH_RETAIL = ["TSLA", "NVDA", "AMD", "PLTR", "SOFI", "RIVN", "LCID", "COIN",
               "MARA", "RIOT", "HOOD", "DKNG", "RBLX", "SNAP", "F", "NIO",
               "MSTR", "SMCI", "ARM", "IONQ", "AFRM", "CVNA", "GME", "AMC", "UPST"]
INSTITUTIONAL = ["JNJ", "PG", "KO", "PEP", "MRK", "ABT", "LIN", "HON", "UNP",
                 "ADP", "AON", "ITW", "ECL", "SHW", "CL", "GIS", "SYY", "WM", "BDX"]

GRID = dict(
    rsi_len=[7, 14, 21],
    oversold=[20, 25, 30, 35, 40],
    os_window=[3, 6, 12],
    need_hl=[True, False],
    need_candle=[True, False],
    need_trend=[True, False],
    hold=[3, 6, 12, 24, 48],
)
COST = 0.0020          # 0.10% per side, one round trip
PIVOT = 3
MIN_TRADES = 100


# ---------------------------------------------------------------- data

def load(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pd.read_pickle(CACHE)
    import yfinance as yf
    syms = HIGH_RETAIL + INSTITUTIONAL + ["SPY"]
    raw = yf.download(syms, interval="1h", period="730d", progress=False,
                      auto_adjust=False, group_by="ticker", threads=True)
    idx = raw["SPY"].dropna(subset=["Close"]).index
    out = {}
    for f in ("Open", "High", "Low", "Close"):
        out[f.lower()] = pd.DataFrame(
            {s: raw[s][f].reindex(idx) for s in syms
             if s in raw.columns.get_level_values(0)})
    pd.to_pickle(out, CACHE)
    return out


def rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).where(dn != 0, 100.0)


def higher_low(low):
    piv = low.rolling(2 * PIVOT + 1, center=True).min().eq(low)
    piv = piv.shift(PIVOT).fillna(False)
    v = low.shift(PIVOT).where(piv)
    last = v.ffill()
    prev = v.apply(lambda c: c.dropna().shift(1).reindex(c.index).ffill())
    return ((last > prev) & last.notna() & prev.notna()).fillna(False)


def prep(h, syms):
    """Everything that does not depend on the swept parameters, computed once."""
    o = h["open"][syms]
    hi = h["high"][syms]
    lo = h["low"][syms]
    c = h["close"][syms]

    P = {}
    P["close"], P["open"] = c, o
    P["hl"] = higher_low(lo)
    P["candle"] = ((c > o) & (c > hi.shift(1))).fillna(False)
    # higher-timeframe uptrend: 50-bar above 200-bar on the hourly chart,
    # which on ~6.5 bars/day is roughly the 8-day vs 30-day trend
    P["trend"] = ((c > c.rolling(50).mean()) &
                  (c.rolling(50).mean() > c.rolling(200).mean())).fillna(False)
    P["rsi"] = {n: rsi(c, n) for n in GRID["rsi_len"]}

    # equal-weight basket index, used as the benchmark for every trade
    basket = (1 + c.pct_change().mean(axis=1).fillna(0)).cumprod()
    P["basket"] = basket

    P["fwd"] = {}
    for hold in GRID["hold"]:
        entry = o.shift(-1)
        exit_ = c.shift(-hold - 1)
        b = basket.shift(-hold - 1) / basket.shift(-1) - 1.0
        P["fwd"][hold] = (exit_ / entry - 1.0).sub(b, axis=0)
    return P


# ---------------------------------------------------------------- sweep

def evaluate(trig, fwd):
    vals = fwd.where(trig).stack().dropna().values
    if len(vals) < MIN_TRADES:
        return None
    net = vals - COST
    mu = net.mean()
    t = mu / (net.std(ddof=1) / np.sqrt(len(net)))
    return dict(n=len(net), mean=mu, t=t, hit=float((vals > COST).mean()))


def run_universe(P, label, rng, verbose=True):
    keys = list(GRID)
    combos = list(itertools.product(*[GRID[k] for k in keys]))
    rows = []
    t0 = time.time()
    for i, combo in enumerate(combos):
        p = dict(zip(keys, combo))
        r = P["rsi"][p["rsi_len"]]
        os_ = (r <= p["oversold"]).rolling(p["os_window"],
                                           min_periods=1).max().astype(bool)
        trig = os_
        if p["need_hl"]:
            trig = trig & P["hl"]
        if p["need_candle"]:
            trig = trig & P["candle"]
        if p["need_trend"]:
            trig = trig & P["trend"]

        fwd = P["fwd"][p["hold"]]
        real = evaluate(trig, fwd)
        if real is None:
            continue

        # NULL: same trigger count per symbol, times permuted
        arr = trig.values.copy()
        for j in range(arr.shape[1]):
            arr[:, j] = rng.permutation(arr[:, j])
        null = evaluate(pd.DataFrame(arr, index=trig.index, columns=trig.columns),
                        fwd)

        rows.append(dict(universe=label, **p, n=real["n"],
                         real=real["mean"], t_real=real["t"], hit=real["hit"],
                         null=null["mean"] if null else np.nan,
                         t_null=null["t"] if null else np.nan))
        if verbose and (i + 1) % 300 == 0:
            print("    %d/%d  (%.0fs)" % (i + 1, len(combos), time.time() - t0))
    return pd.DataFrame(rows)


def describe(df, label):
    real, null = df["real"] * 100, df["null"] * 100
    print("\n  %s   %d testable variants" % (label, len(df)))
    print("  %-22s %9s %9s" % ("", "REAL", "SHUFFLED"))
    for name, f in [("median per trade", np.median), ("mean per trade", np.mean),
                    ("90th percentile", lambda x: np.percentile(x, 90)),
                    ("best variant", np.max)]:
        print("  %-22s %+8.3f%% %+8.3f%%" % (name, f(real), f(null)))
    print("  %-22s %9d %9d" % ("variants profitable",
                               int((real > 0).sum()), int((null > 0).sum())))
    print("  %-22s %9d %9d" % ("variants with t > 2",
                               int((df.t_real > 2).sum()), int((df.t_null > 2).sum())))
    return dict(label=label, median=np.median(real), best=np.max(real),
                best_null=np.max(null), n_pos=int((real > 0).sum()),
                n_t2=int((df.t_real > 2).sum()), n_t2_null=int((df.t_null > 2).sum()),
                n=len(df))


def main():
    h = load()
    print("hourly panel: %d bars, %s -> %s"
          % (len(h["close"]), h["close"].index[0].date(), h["close"].index[-1].date()))
    rng = np.random.default_rng(42)

    out, summ = [], []
    for label, syms in [("HIGH-RETAIL / volatile", HIGH_RETAIL),
                        ("INSTITUTIONAL / calm", INSTITUTIONAL)]:
        syms = [s for s in syms if s in h["close"].columns]
        print("\nsweeping %s (%d names, 1800 variants + 1800 shuffled)..."
              % (label, len(syms)))
        P = prep(h, syms)
        df = run_universe(P, label, rng)
        out.append(df)
        summ.append(describe(df, label))

    res = pd.concat(out, ignore_index=True)
    res.to_csv("sweep_results.csv", index=False)

    print("\n" + "=" * 74)
    print("  THE ONLY COMPARISON THAT MATTERS")
    print("=" * 74)
    print("  If the best real variant is no better than the best shuffled one,")
    print("  the setup carries no information -- the number just reflects how")
    print("  good the best of 1,800 tries looks by chance.\n")
    print("  %-24s %12s %12s %10s" % ("universe", "best real", "best shuffled",
                                      "verdict"))
    for s in summ:
        v = "REAL WINS" if s["best"] > s["best_null"] * 1.5 else "no better than noise"
        print("  %-24s %+11.3f%% %+11.3f%% %10s" % (s["label"], s["best"],
                                                   s["best_null"], v))
    print("\n  %-24s %12s %12s" % ("", "t>2 real", "t>2 shuffled"))
    for s in summ:
        print("  %-24s %12d %12d" % (s["label"], s["n_t2"], s["n_t2_null"]))
    print("\n  wrote sweep_results.csv")


if __name__ == "__main__":
    main()
