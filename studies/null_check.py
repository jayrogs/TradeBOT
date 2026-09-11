"""null_check.py -- the adopted rule vs its own matched null, both eras."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glob, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import rider_lab as L, scanner as SC

SPLIT = pd.Timestamp("2022-07-01")
rng = np.random.default_rng(99)
for label, lo_t, hi_t in (("mined ", SPLIT, pd.Timestamp("2100-01-01")),
                          ("frozen", pd.Timestamp("2000-01-01"), SPLIT)):
    nets, nulls = [], []
    for f in sorted(glob.glob("history/*_1h.csv.gz")):
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[(raw.index >= lo_t) & (raw.index < hi_t)]
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
            ok = set(dv[dv >= 1e6 * mult].index)
            if not ok:
                continue
            v = L.prep(df)
            liq = np.isin(df.index.year.values, list(ok))
            got = 0
            for entry, fill in L.entries(v, 2, "promote1"):
                if entry >= v["n"] - 2 or not liq[entry]:
                    continue
                r = L.run_exit(v, entry, fill, "promote1")
                if r:
                    nets.append(r[1] / fill - 1 - 2 * L.COST)
                    got += 1
            # matched null: random LIQUID bars through the identical
            # adopted exit (tolerant body + promotion + trail)
            pool = np.flatnonzero(liq[:-5])
            if got and len(pool) > 50:
                vals = []
                for _ in range(min(40, got) * 6):
                    i = int(rng.choice(pool))
                    r = L.run_exit(v, i, v["c"][i], "promote1")
                    if r:
                        vals.append(r[1] / v["c"][i] - 1 - 2 * L.COST)
                if vals:
                    nulls.append(float(np.mean(vals)))
    a = np.array(nets)
    nn = float(np.mean(nulls))
    print("%s: %4d trades  rule %+.3f%%  null %+.3f%%  ->  EDGE %+.3f%%"
          % (label, len(a), 100 * a.mean(), 100 * nn, 100 * (a.mean() - nn)))
