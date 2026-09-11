"""
exit_test2.py -- the structural exit, tested on every daily uptrend we can find.

    python exit_test2.py

ENTRY, identical for every rule: the daily trend light turns GREEN -- price has
made a higher low and has not broken it. That is our own state machine, so the
entries are exactly what the panel would have shown you.

EXITS COMPARED
    daily HL break, close     break of the last higher low on the daily
    daily HL break, wick      same level, but a wick through it counts
    weekly HL break, close    the same rule read on weekly structure
    monthly HL break, close   the same rule read on monthly structure
    50-day MA close-below     a conventional trend exit
    +20% profit target        what the user used to do
    20% trailing stop         the arbitrary number I quoted earlier

Costs 0.05% per side. Everything is close-based unless the rule says otherwise.
"""

import os
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
COST = 0.0005
MAX_HOLD = 750


def hl_levels(df):
    """
    Per-bar level of the last higher low, taken straight from the state machine.

    An earlier version computed this separately as a running maximum, which
    never reset -- it carried a stale level from a previous uptrend, so 18 of
    36 SPY entries began already below their own stop and exited on bar one.
    Using trend_state's own level keeps the exit consistent with the light.
    """
    _, hl, _ = P.trend_state(df)
    return hl


def run_symbol(sym, d):
    if len(d) < 400:
        return []
    dd = d
    wk = P.resample(d, "W-FRI")
    mo = P.resample(d, "ME")
    if len(wk) < 40 or len(mo) < 15:
        return []

    st, _, _ = P.trend_state(dd)
    c = dd["Close"].values.astype(float)
    l = dd["Low"].values.astype(float)
    idx = dd.index
    ma50 = pd.Series(c).rolling(50).mean().values

    hl_d = hl_levels(dd)
    hl_w = pd.Series(hl_levels(wk), index=wk.index).reindex(idx, method="ffill").values
    hl_m = pd.Series(hl_levels(mo), index=mo.index).reindex(idx, method="ffill").values

    entries = [i for i in range(60, len(c) - 5)
               if st[i] == "UP" and st[i - 1] != "UP"]
    out = []
    for i0 in entries:
        entry = c[i0] * (1 + COST / 2)
        peak = c[i0]
        done = {}
        for i in range(i0 + 1, min(i0 + MAX_HOLD, len(c))):
            peak = max(peak, c[i])
            checks = {
                "daily HL close":   np.isfinite(hl_d[i]) and c[i] < hl_d[i],
                "daily HL wick":    np.isfinite(hl_d[i]) and l[i] < hl_d[i],
                "weekly HL close":  np.isfinite(hl_w[i]) and c[i] < hl_w[i],
                "monthly HL close": np.isfinite(hl_m[i]) and c[i] < hl_m[i],
                "50d MA close":     np.isfinite(ma50[i]) and c[i] < ma50[i],
                "+20% target":      c[i] >= c[i0] * 1.20,
                "20% trail":        c[i] <= peak * 0.80,
            }
            for k, hit in checks.items():
                if hit and k not in done:
                    done[k] = (i, c[i])
            if len(done) == len(checks):
                break
        last = min(i0 + MAX_HOLD, len(c) - 1)
        mfe = peak / c[i0] - 1
        for k in ["daily HL close", "daily HL wick", "weekly HL close",
                  "monthly HL close", "50d MA close", "+20% target", "20% trail"]:
            i, px = done.get(k, (last, c[last]))
            out.append(dict(symbol=sym, rule=k, entry=idx[i0], bars=i - i0,
                            ret=(px * (1 - COST / 2)) / entry - 1, mfe=mfe))
    return out


def main():
    data = pd.read_pickle(CACHE)
    rows = []
    for k, (sym, d) in enumerate(data.items()):
        try:
            rows += run_symbol(sym, d)
        except Exception:
            continue
        if (k + 1) % 100 == 0:
            print("  %d/%d symbols" % (k + 1, len(data)))
    R = pd.DataFrame(rows)
    R.to_csv("exit_test2.csv", index=False)

    n_tr = R[R.rule == "daily HL close"].shape[0]
    print("\n" + "=" * 82)
    print("  STRUCTURAL EXIT vs THE ALTERNATIVES")
    print("  %d uptrend entries across %d markets, identical entries throughout"
          % (n_tr, R.symbol.nunique()))
    print("=" * 82)
    print("  %-20s %10s %10s %8s %8s %9s %9s"
          % ("exit rule", "mean", "median", "win%", "bars", "capture", "no exit"))
    # average each symbol first, then across symbols, so a handful of crypto
    # moonshots cannot dominate. Median reported alongside.
    per = R.groupby(["rule", "symbol"])["ret"].mean().reset_index()
    g = per.groupby("rule")["ret"].mean().to_frame("mean")
    g["med"] = R.groupby("rule")["ret"].median()
    g["win"] = R.groupby("rule")["ret"].apply(lambda x: (x > 0).mean())
    g["bars"] = R.groupby("rule")["bars"].median()
    g["ran_out"] = R.groupby("rule")["bars"].apply(lambda x: (x >= MAX_HOLD - 1).mean())
    cap = R.copy()
    cap["cap"] = np.where(cap.mfe > 0, cap.ret / cap.mfe.replace(0, np.nan), np.nan)
    g["cap"] = cap.groupby("rule")["cap"].median()
    order = ["daily HL close", "daily HL wick", "weekly HL close",
             "monthly HL close", "50d MA close", "+20% target", "20% trail"]
    for k in order:
        if k not in g.index:
            continue
        x = g.loc[k]
        print("  %-20s %+9.2f%% %+9.2f%% %7.0f%% %8.0f %8.0f%% %8.0f%%"
              % (k, 100 * x["mean"], 100 * x["med"], 100 * x["win"],
                 x["bars"], 100 * x["cap"], 100 * x["ran_out"]))

    print("\n  'capture' = share of the trade's best-ever gain that the rule kept.")

    print("\n" + "=" * 82)
    print("  BY ASSET CLASS  (mean return per trade)")
    print("=" * 82)
    groups = {
        "crypto": lambda s: s.endswith("-USD"),
        "futures": lambda s: s.endswith("=F"),
        "metals/miners": lambda s: s in ("GLD", "SLV", "GDX", "GDXJ", "UUUU",
                                         "PPLT", "PALL", "URA"),
        "index ETF": lambda s: s in ("SPY", "QQQ", "IWM", "DIA", "MDY", "EFA",
                                     "EEM"),
    }
    print("  MEDIAN return per trade, so outliers cannot distort it")
    print("  %-20s %12s %12s %12s %12s"
          % ("rule", "crypto", "futures", "metals", "index ETF"))
    for k in order:
        vals = []
        for gname, fn in groups.items():
            x = R[(R.rule == k) & (R.symbol.map(fn))]
            vals.append("%+11.2f%%" % (100 * x.ret.median()) if len(x) > 15 else "          -")
        print("  %-20s %s" % (k, " ".join(vals)))


if __name__ == "__main__":
    main()
