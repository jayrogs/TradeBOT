"""
es_hourly2.py -- the expanded hourly ES search, ~2,000 configurations.

    python es_hourly2.py

Adds to es_hourly.py: short and long-short variants, stop-losses, session
restrictions, and trend-filter x mean-reversion combinations.

THE POINT OF EXPANDING
Not to find a better system. To test whether the gap between the best REAL
configuration and the best NULL configuration ever opens up. In the 396-config
run the null actually won (2.36 vs 2.05). If real signal exists, more searching
should pull real ahead of null. If it does not, more searching is just a more
expensive way of sampling the same noise -- and that is worth demonstrating
rather than asserting.

THREE NULLS this time, not one, because a single null draw is itself a sample:
    reversed    return series played backwards -- same volatility clustering,
                same total drift, causality broken
    block       returns resampled in 24-bar blocks (preserves intraday shape)
    shifted     signals applied to returns 500 bars out of phase

The honest headline is the HELD-BACK period, never the search period.
"""

import itertools
import warnings

import numpy as np
import pandas as pd

import es_hourly as E

warnings.filterwarnings("ignore")

rng = np.random.default_rng(20260819)


def add_stop(pos, c, stop_pct):
    """Exit and stay flat for the rest of the run if drawdown from entry
    exceeds stop_pct."""
    p = pos.copy()
    in_pos = False
    entry = 0.0
    for i in range(len(p)):
        if p[i] > 0 and not in_pos:
            in_pos, entry = True, c[i]
        elif p[i] > 0 and in_pos:
            if c[i] / entry - 1 <= -stop_pct:
                p[i] = 0.0
                in_pos = False
        elif p[i] <= 0:
            in_pos = False
    return p


def build_more(d, base):
    c = d["Close"].values
    hr = d.index.hour.values
    n = len(c)
    out = list(base)

    rth = ((hr >= 9) & (hr < 16)).astype(float)
    onx = 1.0 - rth
    trend_fast = (E.ema(c, 24) > E.ema(c, 168)).astype(float)
    trend_slow = (E.ema(c, 48) > E.ema(c, 336)).astype(float)

    for fam, name, pos in base:
        if fam in ("time_of_day", "day_hour"):
            continue
        # session-restricted versions
        out.append((fam + "_rth", name + " +RTH only", pos * rth))
        out.append((fam + "_onx", name + " +overnight only", pos * onx))
        # trend-filtered versions
        out.append((fam + "_tf", name + " +trend24/168", pos * trend_fast))
        out.append((fam + "_tf2", name + " +trend48/336", pos * trend_slow))
        # short side
        out.append((fam + "_short", name + " SHORT", -pos))

    # stop-loss variants on a representative subset
    for fam, name, pos in base:
        if fam not in ("donchian", "ma_cross", "zscore_mr", "rsi_mr"):
            continue
        for sp in (0.005, 0.01, 0.02):
            out.append((fam + "_stop", "%s stop%.1f%%" % (name, 100 * sp),
                        add_stop(pos, c, sp)))
    return out


def make_nulls(ret):
    reversed_ = np.concatenate([[0.0], ret[1:][::-1]])
    blocks = ret[1:].copy()
    nb = len(blocks) // 24
    idx = rng.permutation(nb)
    block = np.concatenate([blocks[i * 24:(i + 1) * 24] for i in idx])
    block = np.concatenate([[0.0], block, np.zeros(len(ret) - 1 - len(block))])
    shifted = np.roll(ret, 500)
    return {"reversed": reversed_, "block": block[:len(ret)], "shifted": shifted}


def main():
    d = E.load()
    c = d["Close"].values
    ret = np.zeros(len(c))
    ret[1:] = c[1:] / c[:-1] - 1
    n = len(c)
    cut = int(n * E.SPLIT)
    m1 = np.zeros(n, bool); m1[:cut] = True
    m2 = np.zeros(n, bool); m2[cut:] = True

    print("ES hourly %d bars. search %s..%s | HELD BACK %s..%s"
          % (n, d.index[0].date(), d.index[cut].date(),
             d.index[cut].date(), d.index[-1].date()))
    bh1 = E.evaluate(np.ones(n), ret, m1, min_trades=0)
    bh2 = E.evaluate(np.ones(n), ret, m2, min_trades=0)
    print("buy & hold: search Sharpe %.2f (%+.1f%%/yr) | held back Sharpe %.2f (%+.1f%%/yr)"
          % (bh1["sharpe"], 100 * bh1["cagr"], bh2["sharpe"], 100 * bh2["cagr"]))

    base = E.build_all(d)
    systems = build_more(d, base)
    print("\nbuilt %d configurations (was %d)" % (len(systems), len(base)))
    nulls = make_nulls(ret)

    rows = []
    for k, (fam, name, pos) in enumerate(systems):
        a = E.evaluate(pos, ret, m1)
        b = E.evaluate(pos, ret, m2)
        if a is None or b is None:
            continue
        rec = dict(family=fam, name=name, s1=a["sharpe"], s2=b["sharpe"],
                   c2=b["cagr"], dd2=b["dd"])
        for nm, nr in nulls.items():
            x = E.evaluate(pos, nr, m1)
            rec["null_" + nm] = x["sharpe"] if x else np.nan
        rows.append(rec)
        if (k + 1) % 500 == 0:
            print("  %d/%d" % (k + 1, len(systems)))
    r = pd.DataFrame(rows)
    r.to_csv("es_hourly2_results.csv", index=False)

    print("\n" + "=" * 78)
    print("  DOES MORE SEARCHING PULL REAL AHEAD OF NULL?")
    print("=" * 78)
    print("  %-34s %10s" % ("configurations evaluated", len(r)))
    print("  %-34s %10.2f" % ("BEST Sharpe, real, search period", r.s1.max()))
    for nm in nulls:
        print("  %-34s %10.2f" % ("BEST Sharpe, null (%s)" % nm, r["null_" + nm].max()))
    print("  %-34s %10.2f" % ("median real, search", r.s1.median()))
    print("  %-34s %10.2f" % ("median null (reversed)", r.null_reversed.median()))

    print("\n" + "=" * 78)
    print("  WHAT THE HELD-BACK PERIOD SAYS  (the only number that counts)")
    print("=" * 78)
    print("  buy & hold, held back                    Sharpe %5.2f  %+.1f%%/yr"
          % (bh2["sharpe"], 100 * bh2["cagr"]))
    top = r.nlargest(50, "s1")
    print("  top 50 by search Sharpe: mean search %.2f -> mean held back %.2f"
          % (top.s1.mean(), top.s2.mean()))
    print("  of those 50, beat buy & hold when held back: %d"
          % (top.s2 > bh2["sharpe"]).sum())
    print("  correlation, search vs held back, all configs: %+.3f" % r.s1.corr(r.s2))

    print("\n  %-38s %8s %8s %9s" % ("top 12 by search Sharpe", "search", "held", "CAGR held"))
    for _, x in r.nlargest(12, "s1").iterrows():
        print("  %-38s %8.2f %8.2f %+8.1f%%"
              % ((x.family + " " + x["name"])[:38], x.s1, x.s2, 100 * x.c2))

    print("\n  %-38s %8s %8s %9s" % ("best 12 in the HELD-BACK period", "search", "held", "CAGR held"))
    for _, x in r.nlargest(12, "s2").iterrows():
        print("  %-38s %8.2f %8.2f %+8.1f%%"
              % ((x.family + " " + x["name"])[:38], x.s1, x.s2, 100 * x.c2))


if __name__ == "__main__":
    main()
