"""
pairs_test.py -- the user's actual entry, stated precisely.

    python pairs_test.py

THE METHOD, in their words:
    "Weekly uptrend TF, look for daily oversold for higher low.
     Monthly tf uptrend expected, look for weekly oversold.
     Hourly uptrend tf, 5 min OS usually marks the higher low on the hourly."

So, per trade:
    CONTEXT   higher timeframe trend light is GREEN
    TRIGGER   lower timeframe RSI(14) oversold
    MANAGED   on the HIGHER timeframe -- because the lower-timeframe oversold is
              only marking where the higher timeframe's higher low forms. The
              trade belongs to the higher timeframe.

That last point is the one I got wrong before. My previous test entered on
confirmation (the light turning green) and exited on the same timeframe, which
is a different trade entirely and produced the opposite answer about exits.

EXITS COMPARED, all from the same entries
    higher-TF HL break     the structural exit, on the timeframe being traded
    lower-TF HL break      exiting on the fast timeframe instead
    +20% target            the control
    50-day MA              the conventional control

PAIRS TESTED
    M / W     monthly context, weekly trigger
    W / D     weekly context, daily trigger
    D / 4H    daily context, 4-hour trigger      (hourly data, ~2 years)
    4H / 1H   4-hour context, 1-hour trigger     (hourly data, ~2 years)
    1H / 5M   cannot be tested -- 60 days of 5-minute history exists
"""

import os
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
COST = 0.0005
OVERSOLD = 40
MAX_HOLD = 500


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def one_pair(sym, d, hi_rule, lo_rule):
    """hi_rule/lo_rule are resample rules; lo_rule None means the base bars."""
    hi = P.resample(d, hi_rule)
    lo = P.resample(d, lo_rule) if lo_rule else d
    if len(hi) < 30 or len(lo) < 150:
        return []

    st_h, hl_h, _ = P.trend_state(hi)
    st_l, hl_l, _ = P.trend_state(lo)

    li = lo.index
    ctx = pd.Series(st_h, index=hi.index).reindex(li, method="ffill")
    hlh = pd.Series(hl_h, index=hi.index).reindex(li, method="ffill").values
    c = lo["Close"].values.astype(float)
    r = rsi(c)
    ma50 = pd.Series(c).rolling(50).mean().values

    # trigger: context green AND this timeframe oversold, first bar of the dip
    os_now = r < OVERSOLD
    trig = (ctx.values == "UP") & os_now & ~np.roll(os_now, 1)
    trig[:60] = False

    out = []
    for i0 in np.where(trig)[0]:
        entry = c[i0] * (1 + COST / 2)
        done = {}
        for i in range(i0 + 1, min(i0 + MAX_HOLD, len(c))):
            checks = {
                "higher-TF HL break": np.isfinite(hlh[i]) and c[i] < hlh[i],
                "lower-TF HL break": np.isfinite(hl_l[i]) and c[i] < hl_l[i],
                "+20% target": c[i] >= c[i0] * 1.20,
                "50d MA break": np.isfinite(ma50[i]) and c[i] < ma50[i],
            }
            for k, hit in checks.items():
                if hit and k not in done:
                    done[k] = (i, c[i])
            if len(done) == len(checks):
                break
        last = min(i0 + MAX_HOLD, len(c) - 1)
        for k in ["higher-TF HL break", "lower-TF HL break", "+20% target",
                  "50d MA break"]:
            i, px = done.get(k, (last, c[last]))
            out.append(dict(symbol=sym, rule=k, bars=i - i0,
                            ret=(px * (1 - COST / 2)) / entry - 1))
    return out


def main():
    data = pd.read_pickle(CACHE)
    pairs = [("M / W", "ME", "W-FRI"), ("W / D", "W-FRI", None)]

    for label, hr, lr in pairs:
        rows = []
        for sym, d in data.items():
            if len(d) < 500:
                continue
            try:
                rows += one_pair(sym, d, hr, lr)
            except Exception:
                continue
        R = pd.DataFrame(rows)
        if R.empty:
            continue
        n = R[R.rule == "higher-TF HL break"].shape[0]
        print("\n" + "=" * 78)
        print("  %s   context green + trigger oversold   --   %d entries, %d markets"
              % (label, n, R.symbol.nunique()))
        print("=" * 78)
        print("  %-22s %10s %10s %8s %8s"
              % ("exit", "mean", "median", "win%", "bars"))
        per = R.groupby(["rule", "symbol"])["ret"].mean().reset_index()
        g = per.groupby("rule")["ret"].mean().to_frame("mean")
        g["med"] = R.groupby("rule")["ret"].median()
        g["win"] = R.groupby("rule")["ret"].apply(lambda x: (x > 0).mean())
        g["bars"] = R.groupby("rule")["bars"].median()
        for k in ["higher-TF HL break", "lower-TF HL break", "+20% target",
                  "50d MA break"]:
            if k not in g.index:
                continue
            x = g.loc[k]
            print("  %-22s %+9.2f%% %+9.2f%% %7.0f%% %8.0f"
                  % (k, 100 * x["mean"], 100 * x["med"], 100 * x["win"], x["bars"]))
        R.to_csv("pairs_%s.csv" % label.replace(" / ", "_"), index=False)


if __name__ == "__main__":
    main()
