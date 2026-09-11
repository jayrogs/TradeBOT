"""pics_surge.py -- winners under the surge-gated rider, 2022-2026.

These are drawn FROM THE MINED YEARS: the point is to see what the rule
looks like when it fires well and judge whether it matches the good riders
the group trades -- not to prove profitability (the frozen years already
said no for the mechanical version).
"""
import glob
import os
import warnings

import numpy as np
import pandas as pd

import rider_lab as L
import scanner as SC
import trade_pics2 as TP

warnings.filterwarnings("ignore")

START = pd.Timestamp("2022-07-01")
DOLLAR = 1e6
RELVOL = 2.210
RET7 = 0.0481
OUT = "validation"


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith("v4_"):
            os.remove(os.path.join(OUT, f))

    picks = []
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[raw.index >= START]
        if len(raw) < 2000:
            continue
        for tf, per_day, mult in (("1h", 24, 1), ("4h", 6, 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok = liquid_years(df, mult)
            if not ok:
                continue
            v = L.prep(df)
            c, e, lo = v["c"], v["e"], v["lo"]
            n = v["n"]
            years = df.index.year.values
            liq = np.isin(years, list(ok))
            dv = pd.Series(c * df["Volume"].values, index=df.index)
            dv30 = dv.rolling(30 * per_day, min_periods=per_day).median().values
            dv1 = dv.rolling(per_day, min_periods=2).mean().values
            lb7 = 7 * per_day
            with np.errstate(divide="ignore", invalid="ignore"):
                rv = np.where(dv30 > 0, dv1 / dv30, np.nan)
            r7 = np.full(n, np.nan)
            r7[lb7:] = c[lb7:] / c[:-lb7] - 1.0
            gate = liq & (rv >= RELVOL) & (r7 <= RET7)

            # the canonical rule, verified identical to the scored one by test_harden
            for t in TP.trades_with_marks(df, 2, 0.03):
                entry = t["entry"]
                if not gate[entry]:
                    continue
                base_raw = {"1h": raw, "1d": SC.resample(raw, "1D")}
                picks.append((sym, tf, df, t, base_raw,
                              float(rv[entry]), float(r7[entry])))
        print("  %-6s %4d gated trades" % (sym, len(picks)), flush=True)

    wins = [p for p in picks if p[3]["net"] > 0]
    wins.sort(key=lambda p: -p[3]["net"])
    rng = np.random.default_rng(9)
    rest = wins[10:]
    sel = wins[:10] + [rest[i] for i in
                       rng.choice(len(rest), size=min(10, len(rest)),
                                  replace=False)]
    print("  %d trades passed the gate, %d winners, drawing %d"
          % (len(picks), len(wins), len(sel)))

    rows = []
    for cn, (sym, tf, df, t, base_raw, rvx, r7x) in enumerate(sel, 1):
        p = os.path.join(OUT, "v4_%02d.png" % cn)
        strip = TP.tf_strip(sym, df.index[t["entry"]], base_raw)
        TP.draw(df, t, "%s (vol %.1fx normal, %+.0f%% wk)" % (sym, rvx, 100 * r7x),
                tf, 0.03, p, strip)
        rows.append(dict(n=cn, sym=sym, tf=tf, touches=len(t["marks"]),
                         bars=t["bars"], net=100 * t["net"]))
        print("  v4_%02d  %-5s %-3s %s  %4d bars  %+7.2f%%"
              % (cn, sym, tf, df.index[t["entry"]].date(), t["bars"],
                 100 * t["net"]), flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
