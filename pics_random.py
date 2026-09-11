"""pics_random.py -- N random trades from the canonical engine, uncurated.

Any liquid name, any year 2015-2026, both timeframes. The pure spot-check:
whatever the draw serves is what gets graded.
"""
import argparse
import glob
import os
import time
import warnings

import numpy as np
import pandas as pd

import scanner as SC
import trade_pics2 as TP

warnings.filterwarnings("ignore")

DOLLAR = 1e6
OUT = "validation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=int(time.time()) % 100000)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith("v4_"):
            os.remove(os.path.join(OUT, f))

    picks = []
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
            ok = set(dv[dv >= DOLLAR * mult].index)
            if not ok:
                continue
            liq = np.isin(df.index.year.values, list(ok))
            base_raw = {"1h": raw, "1d": SC.resample(raw, "1D")}
            for t in TP.trades_with_marks(df, 2, 0.03):
                if liq[t["entry"]]:
                    picks.append((sym, tf, df, t, base_raw))
        print("  %-6s %5d trades pooled" % (sym, len(picks)), flush=True)

    rng = np.random.default_rng(a.seed)
    idx = rng.choice(len(picks), size=min(a.n, len(picks)), replace=False)
    print("  seed %d -> drawing %d of %d" % (a.seed, len(idx), len(picks)))
    rows = []
    for cn, i in enumerate(sorted(idx), 1):
        sym, tf, df, t, base_raw = picks[i]
        p = os.path.join(OUT, "v4_%02d.png" % cn)
        import context_sheet as CS
        CS.draw_context(sym, tf, df, t, base_raw["1h"], p)
        rows.append(dict(n=cn, sym=sym, tf=tf, touches=len(t["marks"]),
                         bars=t["bars"], net=100 * t["net"]))
        print("  v4_%02d  %-5s %-3s %s  %4d bars  %-4s %+7.2f%%"
              % (cn, sym, tf, df.index[t["entry"]].date(), t["bars"],
                 t["why"], 100 * t["net"]), flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
