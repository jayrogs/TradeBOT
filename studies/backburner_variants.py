"""backburner_variants.py -- the selective fast-chart style, re-simulated:
buy once (or up to 3) at the first 5m/15m oversold, tight stop under the
backburner candle's low vs the 3-ATR stop, breakeven partial + 12 EMA ride.
Stocks + ETFs, the 150 most liquid names, realistic 0.05% cost."""
import os, sys, time, warnings
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S
warnings.filterwarnings("ignore")
k = pd.read_csv("cache/tier1.csv")
etf = set(k[k.kind == "etf"].symbol.astype(str))
top = k.sort_values("dollar", ascending=False).symbol.astype(str).tolist()
have = {os.path.basename(f).split("_")[0] for f in __import__("glob").glob("history/stocks/*_15m.csv.gz")}
names = [s for s in top if s in have][:150]
start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * 4)
VARIANTS = [("stop 2 ATR under avg", 10, "atr", 2.0, 0.5), ("stop 3 ATR under avg (current)", 10, "atr", 3.0, 0.5),
            ("stop 5 ATR under avg", 10, "atr", 5.0, 0.5),
            ("stop = 1/4 of the 3-day run-up", 10, "run", 3.0, 0.25),
            ("stop = 1/2 of the 3-day run-up", 10, "run", 3.0, 0.5),
            ("stop = the whole 3-day run-up", 10, "run", 3.0, 1.0),
            ("no stop until the bounce (20-day cap)", 10, "none", 3.0, 0.5)]
frames = {s: S.frames_for(s, "etf" if s in etf else "stock") for s in names}
out = []
for label, units, mode, mult, frac in VARIANTS:
    S.MAX_UNITS, S.STOP_MODE, S.STOP_ATR, S.STOP_FRAC = units, mode, mult, frac
    t0 = time.time(); rows = []
    for s in names:
        for tf in ("15m", "5m"):
            if tf in frames[s]:
                try:
                    r, _ = S.study_frame(s, "etf" if s in etf else "stock", tf, frames[s], start)
                    rows += r
                except Exception as ex:
                    print("  %s %s: %s" % (s, tf, ex), flush=True)
    ev = pd.DataFrame(rows)
    ev["c"] = ev["ret_ride"] - 0.0005 + 0.002          # realistic cost
    ev["hot"] = (ev["move"].fillna(0) >= 0.10) | (ev["move3"].fillna(0) >= 0.20)
    ev["u"] = ev["units"].astype(float)
    def f(d):
        r, u = d["c"], d["u"]; w = r > 0.005; l = r < -0.005
        return "n=%6d  $-wtd %+5.2f%%  win %2.0f%% (avg %+4.1f%%)  flat %2.0f%%  loss %2.0f%% (avg %+4.1f%%)  stopped %2.0f%%  units %.1f" % (
            len(d), 100 * (r * u).sum() / u.sum(), 100 * w.mean(), 100 * r[w].mean() if w.any() else 0, 100 * (r.abs() <= 0.005).mean(), 100 * l.mean(), 100 * r[l].mean() if l.any() else 0, 100 * (d["ended"] == "bad").mean(), u.mean())
    print("\n== %s  (%.0fs) ==" % (label, time.time() - t0), flush=True)
    for tf in ("15m", "5m"):
        d = ev[ev.tf == tf]
        print("  %-3s all       %s" % (tf, f(d)), flush=True)
        print("  %-3s hot       %s" % (tf, f(d[d.hot])), flush=True)
    out.append((label, ev))
