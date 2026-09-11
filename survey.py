"""
survey.py -- measure every pre-specified signal in signals.py, once.

    python survey.py                 discovery window 2010-2022
    python survey.py --confirm       2023-2025, survivors only
    python survey.py --all           print every signal on both windows

METHOD, in plain language
-------------------------
For one signal, on every trading day: score every S&P 500 member, sort them,
buy the top tenth and short the bottom tenth, equally weighted. Hold each
basket a month. Because a new basket is started every day and old ones are still
running, at any moment we hold 21 overlapping baskets -- this is the standard way
to get a daily return series out of a monthly-holding idea without pretending
that overlapping months are independent observations.

The result is one number per day: what the long-short pair earned. String those
together and you can ask whether the average is distinguishable from zero.

WHAT THE t-STATISTIC MEANS
    |t| below 2      indistinguishable from noise
    |t| 2 to 3       suggestive, and routinely turns out to be nothing
    |t| above 3      worth a second look

Sixteen signals are tested, so roughly one |t| above 2 is expected by luck alone.
Benjamini-Hochberg controls for that; a signal that only clears the raw bar and
not the corrected one has not really cleared anything.

Signals are lagged two days: scored on day t, traded at the close of day t+1,
earning from t+1 onward. Nothing is bought using a price that produced the score.
"""

import argparse
import os

import numpy as np
import pandas as pd

import data as D
import signals as S

DISCOVERY = ("2010-01-01", "2022-12-31")
CONFIRM = ("2023-01-01", "2025-12-31")
HOLD = 21          # trading days a basket is held
LAG = 2            # days between scoring and trading
DECILES = 10
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


# ------------------------------------------------------------------ data

def load_panel(start, end):
    """Wide matrices (dates x symbols) plus an eligibility mask."""
    pq = os.path.join(CACHE, "panel.pkl")
    if os.path.exists(pq):
        d = pd.read_pickle(pq)
    else:
        print("building price panel (one-off, then cached)...")
        memb, sectors = D.membership_intervals("2009-01-01", "2026-12-31")
        syms = sorted(memb)
        bars = D.download_bars(syms + ["SPY"], "2007-06-01", "2026-08-18")
        spy = bars.pop("SPY")
        cal = spy.index

        def wide(field):
            return pd.DataFrame({s: b[field].reindex(cal)
                                 for s, b in bars.items()})

        d = {"close": wide("Close"), "open": wide("Open"),
             "high": wide("High"), "low": wide("Low"),
             "volume": wide("Volume")}
        d["spy_close"] = spy["Close"]
        d["spy_ret"] = spy["Close"].pct_change()

        # point-in-time membership as a boolean matrix
        mask = pd.DataFrame(False, index=cal, columns=d["close"].columns)
        for s in mask.columns:
            for a, b in memb.get(s, []):
                mask.loc[(cal >= a) & (cal <= b), s] = True
        d["member"] = mask
        d["sectors"] = sectors
        pd.to_pickle(d, pq)
        print("  cached %d symbols x %d days" % (d["close"].shape[1],
                                                 d["close"].shape[0]))

    # eligibility: in the index that day, has a price, priced above $5.
    # Index membership is itself the liquidity screen -- no extra filter, so
    # there is no threshold here to accidentally tune.
    elig = d["member"] & d["close"].notna() & (d["close"] > 5)
    d["elig"] = elig
    return d


# ------------------------------------------------------------------ engine

def spread_returns(sig, d, start, end):
    """
    Daily long-short return series for one signal, plus the long-only leg
    measured against the equal-weight universe (the part we could trade).
    """
    close = d["close"]
    fwd = close.pct_change()                    # return earned on day t
    elig = d["elig"]

    s = sig.where(elig)
    s = s.shift(LAG)                            # score known LAG days earlier

    # rank into deciles across the names available that day
    n_valid = s.notna().sum(axis=1)
    rank = s.rank(axis=1, pct=True)
    days = (close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))
    ok = days & (n_valid >= 50).values

    top = (rank > 1 - 1.0 / DECILES) & elig
    bot = (rank <= 1.0 / DECILES) & elig
    uni = s.notna() & elig

    def leg(mask):
        w = mask.astype(float)
        w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0)
        # overlapping baskets: today's book is the average of the last HOLD days
        w = w.rolling(HOLD, min_periods=1).mean()
        w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0)
        return (w * fwd).sum(axis=1).where(w.sum(axis=1) > 0)

    long_r, short_r, uni_r = leg(top), leg(bot), leg(uni)
    out = pd.DataFrame({"long": long_r, "short": short_r, "uni": uni_r})[ok]
    out["ls"] = out["long"] - out["short"]
    out["excess"] = out["long"] - out["uni"]
    return out.dropna()


def stats(r):
    """Annualised mean, t-statistic, and a two-sided p-value."""
    n = len(r)
    if n < 250 or r.std(ddof=1) == 0:
        return dict(n=n, ann=np.nan, t=np.nan, p=np.nan, sharpe=np.nan)
    mu, sd = r.mean(), r.std(ddof=1)
    t = mu / (sd / np.sqrt(n))
    # normal approximation is fine at n in the thousands
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return dict(n=n, ann=(1 + mu) ** 252 - 1, t=t, p=p,
                sharpe=mu / sd * np.sqrt(252))


def benjamini_hochberg(pvals, q=0.05):
    """Which results survive once you account for testing this many things."""
    idx = np.argsort(pvals)
    m = len(pvals)
    keep = np.zeros(m, dtype=bool)
    for rank, i in enumerate(idx, 1):
        if pvals[i] <= q * rank / m:
            keep[idx[:rank]] = True
    return keep


# ------------------------------------------------------------------ report

def run(d, start, end, title):
    print("\n" + "=" * 78)
    print("  %s   %s to %s" % (title, start, end))
    print("=" * 78)
    print("  positive = the published effect showed up in the direction claimed")
    print("  %-14s %22s %8s %7s %8s %8s" %
          ("signal", "long-short /yr", "t", "Sharpe", "long-only", "t"))
    print("  " + "-" * 74)

    rows = []
    for name, (fn, desc) in S.SIGNALS.items():
        sig = fn(d)
        r = spread_returns(sig, d, start, end)
        if len(r) < 250:
            print("  %-14s  insufficient data" % name)
            continue
        ls, ex = stats(r["ls"]), stats(r["excess"])
        rows.append(dict(name=name, desc=desc, **{"ls_" + k: v for k, v in ls.items()},
                         **{"ex_" + k: v for k, v in ex.items()}))
        print("  %-14s %+21.2f%% %8.2f %7.2f %+7.2f%% %8.2f"
              % (name, 100 * ls["ann"], ls["t"], ls["sharpe"],
                 100 * ex["ann"], ex["t"]))

    res = pd.DataFrame(rows)
    if res.empty:
        return res
    res["ls_survives"] = benjamini_hochberg(res["ls_p"].values)
    print("  " + "-" * 74)
    print("\n  After correcting for having tested %d signals:" % len(res))
    surv = res[res.ls_survives].sort_values("ls_t", key=abs, ascending=False)
    if surv.empty:
        print("    nothing survives. Every result here is consistent with luck.")
    for _, r in surv.iterrows():
        direction = "as published" if r.ls_ann > 0 else "BACKWARDS"
        print("    %-14s %+6.2f%%/yr  t=%+.2f  %-12s  %s"
              % (r["name"], 100 * r.ls_ann, r.ls_t, direction, r["desc"]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    d = load_panel("2009-01-01", "2026-12-31")

    if args.confirm or args.all:
        pass
    disc = run(d, *DISCOVERY, title="DISCOVERY -- all 16 signals, one pass")
    disc.to_csv("survey_discovery.csv", index=False)

    if args.all or args.confirm:
        conf = run(d, *CONFIRM, title="CONFIRMATION -- untouched window")
        conf.to_csv("survey_confirm.csv", index=False)
        merged = disc[["name", "ls_ann", "ls_t", "ls_survives"]].merge(
            conf[["name", "ls_ann", "ls_t"]], on="name", suffixes=("_disc", "_conf"))
        print("\n" + "=" * 78)
        print("  DOES IT REPLICATE?  discovery vs confirmation")
        print("=" * 78)
        print("  %-14s %12s %8s %12s %8s   %s" %
              ("signal", "2010-22 /yr", "t", "2023-25 /yr", "t", "verdict"))
        for _, r in merged.sort_values("ls_t_disc", key=abs, ascending=False).iterrows():
            same_sign = np.sign(r.ls_ann_disc) == np.sign(r.ls_ann_conf)
            if r.ls_survives and same_sign and abs(r.ls_t_conf) > 2:
                v = "HOLDS UP"
            elif r.ls_survives and same_sign:
                v = "same direction, weaker"
            elif r.ls_survives:
                v = "REVERSED out of sample"
            else:
                v = "-"
            print("  %-14s %+11.2f%% %8.2f %+11.2f%% %8.2f   %s"
                  % (r["name"], 100 * r.ls_ann_disc, r.ls_t_disc,
                     100 * r.ls_ann_conf, r.ls_t_conf, v))
    print("\n2026 remains untouched.")


if __name__ == "__main__":
    main()
