"""pics_boom.py -- draw 20 RANDOM trades from the exploding-names verdict,
exactly as rider_boom.py scored them, off the frozen history/ files.

If these are not what "buy the dips in a name that is blowing up" means,
the verdict judged the wrong thing and the test is invalid -- that is what
the grading is for.
"""
import glob
import os
import warnings

import numpy as np
import pandas as pd

import panel as P
import rider_lab as L
import scanner as SC
import trade_pics2 as TP

warnings.filterwarnings("ignore")

CUTOFF = pd.Timestamp("2022-07-01")
DOLLAR = 1e6
BOOM = 0.25
LOOK = {"1h": 168, "4h": 42}
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
        raw = raw[raw.index < CUTOFF]
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok = liquid_years(df, mult)
            if not ok:
                continue
            v = L.prep(df)
            years = df.index.year.values
            liq = np.isin(years, list(ok))
            c = v["c"]
            lb = LOOK[tf]
            boom = np.zeros(len(c), dtype=bool)
            boom[lb:] = c[lb:] / c[:-lb] - 1.0 >= BOOM
            gate = boom & liq

            # identical to rider_boom: L.entries + gate + promote1 exit,
            # plus the touch marks and promotion bar for drawing
            n = v["n"]
            # the canonical rule, verified identical to the scored one by test_harden
            for t in TP.trades_with_marks(df, 2, 0.03):
                entry = t["entry"]
                if not gate[entry]:
                    continue
                base_raw = {"1h": raw, "1d": SC.resample(raw, "1D")}
                picks.append((sym, tf, df, t, base_raw,
                              float(c[entry] / c[entry - lb] - 1)))
        print("  %-6s scanned" % sym, flush=True)

    print("  %d boom trades total" % len(picks))
    rng = np.random.default_rng(20)
    idx = rng.choice(len(picks), size=min(20, len(picks)), replace=False)
    rows = []
    for cn, i in enumerate(sorted(idx), 1):
        sym, tf, df, t, base_raw, spike = picks[i]
        p = os.path.join(OUT, "v4_%02d.png" % cn)
        strip = TP.tf_strip(sym, df.index[t["entry"]], base_raw)
        TP.draw(df, t, "%s (was +%.0f%% that week)" % (sym, 100 * spike),
                tf, 0.03, p, strip)
        rows.append(dict(n=cn, sym=sym, tf=tf, touches=len(t["marks"]),
                         bars=t["bars"], net=100 * t["net"]))
        print("  v4_%02d  %-5s %-3s %s  %4d bars  %-4s %+7.2f%%"
              % (cn, sym, tf, df.index[t["entry"]].date(), t["bars"],
                 t["why"], 100 * t["net"]), flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
