"""backburner_tier2.py -- do the next tier of names ($100M-$186M a day, history/stocks_more/, #62) trade the backburner as
well as the list the page uses? The page's own trades (pics_backburner_tcg.trades_for, same rules), 2021-10 on (the
tier-2 names have Polygon's 5 years only), per trade, beside the page's own stocks and funds over the same years. Also a
check that each tier-2 name's hourly and daily closes agree (data_scale_check's test).

    python studies/backburner_tier2.py --procs 16
Writes validation/backburner_tier2.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

MORE = os.path.join("history", "stocks_more")
START = pd.Timestamp("2021-10-01")


def frames(sym, folder):
    h1 = S.load_csv(os.path.join(folder, "%s_1h.csv.gz" % sym))
    d1 = S.load_csv(os.path.join(folder, "%s_1d.csv.gz" % sym))
    if h1 is None or d1 is None:
        return None
    return {"1h": h1, "1d": d1, "1w": S.resample(d1, S.RULE["1w"])}


def one(args):
    sym, kind, folder = args
    try:
        fr = frames(sym, folder) if folder else None
        if folder and fr is None:
            return sym, kind, [], None
        tr = PB.trades_for(sym, kind, frames=fr) if folder else PB.trades_for(sym, kind)
        scale = None
        if folder:
            h = fr["1h"]; h = h[(h.index.hour >= 9) & (h.index.hour <= 15)]
            hc = h["Close"].groupby(h.index.normalize()).last()
            dc = fr["1d"]["Close"]; dc.index = pd.DatetimeIndex(dc.index).normalize()
            j = hc.index.intersection(dc.index)
            scale = float((np.abs(np.log(dc.loc[j] / hc.loc[j])) > np.log(1.15)).mean()) if len(j) > 20 else None
        rows = [(pd.Timestamp(t["t"]).year, t["pct"], t["R"]) for t in tr if pd.Timestamp(t["t"]) >= START]
        return sym, kind, rows, scale
    except Exception:
        return sym, kind, [], None


def main():
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 8
    kinds = pd.read_csv(os.path.join(MORE, "KINDS.csv"), index_col=0).iloc[:, 0].to_dict()
    more = [(s, "etf" if kinds.get(s) == "etf" else "stock", MORE) for s in sorted(kinds)
            if os.path.exists(os.path.join(MORE, "%s_1h.csv.gz" % s))]
    page = [(s, k, None) for s, k in S.universe() if k in ("stock", "etf") and s not in PB.T.SUSPECT]
    out = {}
    bad = []
    for lab, jobs in (("tier 2 ($100M-$186M a day)", more), ("the page's list ($186M+ a day)", page)):
        rows = []
        with cf.ProcessPoolExecutor(procs) as ex:
            for sym, kind, r, scale in ex.map(one, jobs, chunksize=2):
                if scale is not None and scale > 0.01:
                    bad.append(sym)
                    continue
                rows += [(sym, kind) + x for x in r]
        d = pd.DataFrame(rows, columns=["sym", "kind", "year", "pct", "R"])
        yrs = d.groupby("year").pct.mean()
        out[lab] = dict(trades=len(d), names=int(d.sym.nunique()), avg=float(d.pct.mean()), middle=float(d.pct.median()),
                        won=float((d.pct > 0).mean()), R=float(d.R.mean()), years={int(k): float(v) for k, v in yrs.items()},
                        per_name_year=float(len(d) / max(1, len(jobs)) / 5.0))
        print("%-32s %5d trades on %3d names  avg %+.2f%%  middle %+.2f%%  won %.0f%%  %+.2fR  | %s" % (
            lab, len(d), d.sym.nunique(), d.pct.mean(), d.pct.median(), 100 * (d.pct > 0).mean(), d.R.mean(),
            "  ".join("%d %+.2f" % (k, v) for k, v in yrs.items())))
    out["tier 2 names whose hourly and daily disagree (left out)"] = bad
    print("left out (hourly and daily disagree):", bad)
    json.dump(out, io.open(os.path.join("validation", "backburner_tier2.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
