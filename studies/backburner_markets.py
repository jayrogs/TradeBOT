"""backburner_markets.py -- THE BACKBURNER ON FUTURES AND FOREX (2026-09-23, his question: "How come we haven't tested these w
futures, commodities, or forex yet?").

Futures were in the first two backburner studies (backburner_tcg, backburner_dan) and fell out when the drawing page was
built on stocks, ETFs and crypto; forex was always left out. This runs the page's own trade on them, nothing else changed:
the first hourly RSI-30 touch after a run, a second buy at RSI 20, half at the hourly 12 EMA, the rest walked under the
higher lows. Stock-style buys (the crypto pyramid and quarter sale are crypto's own, #45 / #48).

Two rows per market, one change: the page exactly (the run must be 10%+ in price -- a STOCK number from his /messymark
marks; currencies almost never move 10% in a month), and the same without that rule (the run still has to be 4+ daily
normal bars and reach levels price was not already at). Costs: futures 0.05% a round trip; forex has no cost of its own
in the table and gets 0.05%, which is on the high side for major pairs. No news skip here (that is for company news).

    pythonw studies/backburner_markets.py --procs 8 --log logs/backburner_markets.log
Writes validation/backburner_markets.json and _rows.parquet
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "backburner_markets.json")
WAYS = {"the page exactly (run 10%+ in price)": {}, "without the 10% rule": dict(run_pct_min=-1e9)}
REAL_FX = {"AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD", "GBPJPY", "GBPUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"}


def _work(args):
    sym, kind = args
    rows = []
    try:
        for w_i, (w, v) in enumerate(WAYS.items()):
            for r in PB.trades_for(sym, kind, dict(PB.STOP, **v)):
                rows.append((w_i, kind, sym, float(pd.Timestamp(r["t"]).year), r["pct"], r["risk_pct"],
                             r.get("run_pct") if r.get("run_pct") is not None else np.nan,
                             1.0 if r["half_at"] is not None else 0.0))
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    return rows, []


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe() if k_ in ("futures", "forex") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=1):
            rows += got
            errs += err
    f = pd.DataFrame(rows, columns=["way", "kind", "sym", "yr", "pct", "risk", "run_pct", "half"])
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names)), table={})

    def row(label, g):
        if len(g) < 20:
            print("    %-58s %5d  (too few to say anything)" % (label, len(g)))
            return
        g = g.sort_values("yr", kind="stable")
        v = g.pct.values
        yrs = g.groupby("yr").pct.mean()
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        d = dict(n=int(len(g)), names=int(g.sym.nunique()), avg=float(v.mean()), middle=float(np.median(v)),
                 won=float((v > 0).mean()), p5=float(np.percentile(v, 5)), years_up=int((yrs > 0).sum()),
                 years=int(len(yrs)), blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)),
                 risk=float(g.risk.median()))
        out["table"][label] = d
        print("    %-58s %5d %4d %+7.2f%% %+7.2f%% %4.0f%% %+6.1f%% %3d/%-3d %4d/%-4d %6.2f%%" % (
            label, d["n"], d["names"], d["avg"], d["middle"], 100 * d["won"], d["p5"], d["years_up"], d["years"],
            d["blocks_up"], d["blocks"], d["risk"]))

    f["fx_real"] = f.sym.str.replace("_X", "", regex=False).isin(REAL_FX)
    groups = [("FUTURES, all", f.kind == "futures"),
              ("  futures: stock indexes (ES NQ YM RTY and micros, NKD)",
               f.sym.isin(["ES_F", "NQ_F", "YM_F", "RTY_F", "MES_F", "MNQ_F", "MYM_F", "M2K_F", "NKD_F"])),
              ("  futures: energy (CL BZ NG HO RB QM QG)", f.sym.isin(["CL_F", "BZ_F", "NG_F", "HO_F", "RB_F", "QM_F", "QG_F"])),
              ("  futures: metals (GC SI HG PL PA ALI and micros)",
               f.sym.isin(["GC_F", "SI_F", "HG_F", "PL_F", "PA_F", "ALI_F", "MGC_F", "SIL_F"])),
              ("  futures: farm (grains, softs, meats)",
               f.sym.isin(["ZC_F", "ZS_F", "ZW_F", "ZL_F", "ZM_F", "ZO_F", "ZR_F", "KE_F", "CC_F", "KC_F", "SB_F", "CT_F",
                           "OJ_F", "LE_F", "GF_F", "HE_F", "DC_F"])),
              ("  futures: currencies and bonds (6x, Z-notes, bonds)",
               f.sym.str.startswith("6") | f.sym.isin(["ZB_F", "ZN_F", "ZF_F", "ZT_F", "UB_F"])),
              ("  futures: crypto (BTC, ETH)", f.sym.isin(["BTC_F", "ETH_F"])),
              ("FOREX, all pairs", f.kind == "forex"),
              ("  forex: the 11 pairs with 4 years of real hourly bars", (f.kind == "forex") & f.fx_real)]
    for w_i, w in enumerate(WAYS):
        print("\n  %s  (%.0fs)" % (w.upper(), time.time() - t0))
        print("    %-58s %5s %4s %8s %8s %5s %7s %7s %9s %7s" % ("market", "n", "names", "avg", "middle", "won", "5%",
                                                              "yrs", "blocks", "risk"))
        for lab, sel in groups:
            row("%s | %s" % (lab, w) if False else lab, f[(f.way == w_i) & sel])
            out["table"]["%s | %s" % (lab.strip(), w)] = out["table"].pop(lab, None)
    print("\n  for comparison, the page now: stocks + ETFs +0.86% a trade (won 63%), crypto +3.06% (won 78%)")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
