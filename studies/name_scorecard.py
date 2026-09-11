"""name_scorecard.py -- which names obey the backburner + 12 EMA rules best?

Owner 2026-09-05: "we pick certain names to focus on, ones that obey these
rules the best ... BTC is normally like the average, we try to pick
something that moves better compared to btc."

From the study's campaign table (validation/backburner_events.csv.gz), per
name and timeframe: campaigns, return per dollar (breakeven partial + 12 EMA
ride, class costs), win rate, average winner / loser, how often the stop
hit, and the same on hot names only. Benchmarks: BTC for crypto, SPY for
stocks and ETFs, ES for futures, EURUSD for forex. Plus how much the name
moves relative to its benchmark (beta of daily returns) and whether it was
positive in BOTH halves of the window (consistent).

    python studies/name_scorecard.py        # -> validation/name_scores.json  (page: /names)
"""

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCH = {"crypto": "BTC", "stock": "SPY", "etf": "SPY", "futures": "ES_F", "forex": "EURUSD_X", "cfd": "ES_F"}
MIN_N = 15
TFS = ["5m", "15m", "1h", "4h", "12h", "1d", "1w"]


def hourly(sym, kind):
    p = {"crypto": os.path.join("history", "%s_1h.csv.gz" % sym),
         "futures": os.path.join("history", "futures", "%s_1h.csv.gz" % sym),
         "forex": os.path.join("history", "forex", "%s_1h.csv.gz" % sym),
         "cfd": os.path.join("history", "futures_cfd", "%s_1h.csv.gz" % sym)}.get(
        kind, os.path.join("history", "stocks", "%s_1h.csv.gz" % sym))
    try:
        d = pd.read_csv(p, index_col=0, parse_dates=True)["Close"]
        return d[~d.index.duplicated()].sort_index()
    except Exception:
        return None


def betas(names):
    """Beta and move ratio of each name's DAILY returns vs its benchmark."""
    out = {}
    bench_ret = {}
    for kind, b in BENCH.items():
        if b in bench_ret:
            continue
        h = hourly(b, "crypto" if b == "BTC" else "futures" if b == "ES_F" else "forex" if b == "EURUSD_X" else "stock")
        bench_ret[b] = None if h is None else np.log(h.resample("1D").last().dropna()).diff().dropna()
    for sym, kind in names:
        h = hourly(sym, kind)
        br = bench_ret.get(BENCH.get(kind))
        if h is None or br is None:
            continue
        r = np.log(h.resample("1D").last().dropna()).diff().dropna()
        r = r[r.index >= r.index[-1] - pd.Timedelta(days=365 * 4)]
        j = r.index.intersection(br.index)
        if len(j) < 60:
            continue
        x, y = br.loc[j].values, r.loc[j].values
        beta = float(np.cov(x, y)[0, 1] / np.var(x)) if np.var(x) > 0 else np.nan
        out[(sym, kind)] = dict(beta=beta, move_ratio=float(np.mean(np.abs(y)) / np.mean(np.abs(x))),
                                corr=float(np.corrcoef(x, y)[0, 1]))
    return out


def block(d):
    r = d["ret_ride"]; u = d["units"].astype(float)
    win = r > 0.005; loss = r < -0.005
    return dict(n=int(len(d)), dw=float((r * u).sum() / u.sum()), mean=float(r.mean()),
                win=float(win.mean()), flat=float((r.abs() <= 0.005).mean()), loss=float(loss.mean()),
                avg_win=float(r[win].mean()) if win.any() else 0.0,
                avg_loss=float(r[loss].mean()) if loss.any() else 0.0,
                stopped=float((d["ended"] == "bad").mean()), units=float(u.mean()),
                held=float(d["ride_held"].mean()))


def main():
    ev = pd.read_csv(os.path.join("validation", "backburner_events.csv.gz"), low_memory=False)
    ev["hot"] = (ev["move"].fillna(0) >= 0.10) | (ev["move3"].fillna(0) >= 0.20)
    names = sorted(set(zip(ev["sym"], ev["kind"])))
    bt = betas(names)
    rows = []
    for (sym, kind), g in ev.groupby(["sym", "kind"]):
        for tf, gt in list(g.groupby("tf")) + [("all", g)]:
            if len(gt) < MIN_N:
                continue
            b = block(gt)
            halves = {}
            for hv, gg in gt.groupby("half"):
                if len(gg) >= 8:
                    halves[hv] = float((gg["ret_ride"] * gg["units"]).sum() / gg["units"].sum())
            hot = gt[gt["hot"]]
            row = dict(sym=sym, kind=kind, tf=tf, bench=BENCH.get(kind), **b,
                       consistent=(len(halves) == 2 and all(x > 0 for x in halves.values())),
                       half1=halves.get("first"), half2=halves.get("second"),
                       hot_n=int(len(hot)), hot_dw=(float((hot["ret_ride"] * hot["units"]).sum() / hot["units"].sum()) if len(hot) >= 5 else None))
            row.update(bt.get((sym, kind), {}))
            rows.append(row)
    df = pd.DataFrame(rows)
    # vs benchmark: same class, same tf
    # benchmark by SYMBOL (SPY is filed as an ETF, so keying by class left stocks blank)
    bench_dw = {(r["sym"], r["tf"]): r["dw"] for r in rows if r["sym"] in BENCH.values()}
    df["vs_bench"] = [r["dw"] - bench_dw.get((BENCH.get(r["kind"]), r["tf"]), np.nan) for _, r in df.iterrows()]
    def grade(r):
        v = r["vs_bench"]
        if r["dw"] < -0.01: return "F", "loses money on these rules"
        if pd.isna(v): return "?", "no benchmark on this timeframe"
        if v > 0.005 and r["consistent"]: return "A", "beats %s, steady in both halves" % BENCH.get(r["kind"])
        if v > 0.005: return "B", "beats %s, but only in one half" % BENCH.get(r["kind"])
        if v >= -0.005: return "C", "about the same as %s" % BENCH.get(r["kind"])
        return "D", "worse than %s" % BENCH.get(r["kind"])
    gg = [grade(r) for _, r in df.iterrows()]
    df["grade"] = [g for g, _ in gg]; df["verdict"] = [w for _, w in gg]
    out = dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), min_n=MIN_N, tfs=TFS + ["all"],
               bench=BENCH, rows=json.loads(df.to_json(orient="records")))
    json.dump(out, open(os.path.join("validation", "name_scores.json"), "w"))
    print("  %d name-timeframe rows for %d names" % (len(df), len(names)))
    for tf in ("1h", "4h", "15m", "all"):
        d = df[(df.tf == tf) & (df.kind == "crypto") & (df.n >= 30)].sort_values("dw", ascending=False)
        if d.empty:
            continue
        print("\n  CRYPTO %s (>=30 campaigns), best and worst vs BTC:" % tf)
        for _, r in pd.concat([d.head(8), d.tail(5)]).iterrows():
            print("    %-8s n=%4d  %+6.2f%%  vs BTC %+6.2f%%  win %3.0f%%  beta %.2f  %s" % (
                r["sym"], r["n"], 100 * r["dw"], 100 * (r["vs_bench"] if pd.notna(r["vs_bench"]) else 0), 100 * r["win"],
                r.get("beta", np.nan) if pd.notna(r.get("beta", np.nan)) else 0, "consistent" if r["consistent"] else ""))


if __name__ == "__main__":
    if "--log" in sys.argv:
        sys.stdout = sys.stderr = open(sys.argv[sys.argv.index("--log") + 1], "a", buffering=1)
    main()
    print("done")
