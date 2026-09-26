"""backburner_tier2_account.py -- the page's account (backburner_long's, 2021-10 on) with and without the tier-2 names
(history/stocks_more/, #62). Each worker reads a tier-2 name from its own folder by swapping backburner_study.frames_for.

    python studies/backburner_tier2_account.py --procs 16
Writes validation/backburner_tier2_account.json
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
import backburner_sizing as SZ    # noqa: E402
import backburner_long as BL      # noqa: E402
import backburner_tier2 as T2     # noqa: E402

_orig = S.frames_for
MORE = set()


def _frames_for(sym, kind):
    if kind in ("stock", "etf") and sym in MORE:
        return T2.frames(sym, T2.MORE)
    return _orig(sym, kind)


def _work(args):
    sym, kind, more = args
    if more:
        MORE.add(sym)
        S.frames_for = _frames_for
    return BL._work((sym, kind))


def main():
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 8
    kinds = pd.read_csv(os.path.join(T2.MORE, "KINDS.csv"), index_col=0).iloc[:, 0].to_dict()
    left_out = set(json.load(io.open(os.path.join("validation", "backburner_tier2.json")))[
        "tier 2 names whose hourly and daily disagree (left out)"])
    more = [(s, "etf" if kinds.get(s) == "etf" else "stock", True) for s in sorted(kinds)
            if os.path.exists(os.path.join(T2.MORE, "%s_1h.csv.gz" % s)) and s not in left_out]
    page = [(s, k, False) for s, k in S.universe()
            if (k in ("stock", "etf", "crypto") or (k == "futures" and s in PB.COMMODITY_FUTURES)) and s not in PB.T.SUSPECT]
    trades, closes, tier2 = [], {}, set()
    with cf.ProcessPoolExecutor(procs) as ex:
        for (a_, _b, c_, sym, kind), job in zip(ex.map(_work, page + more, chunksize=2), page + more):
            if job[2]:
                tier2.add((kind, sym))
            trades += [dict(t, tier2=job[2]) for t in a_]
            if c_ is not None:
                closes[(kind, sym)] = c_
    end = max(t["t_out"] for t in trades).normalize()
    a0 = pd.Timestamp("2021-10-01")
    out = {}
    for lab, tr in (("the page's list", [t for t in trades if not t["tier2"]]), ("with tier 2 added", trades)):
        out[lab] = BL.run(tr, closes, a0, end)
        d = out[lab]
        print("%-20s a year %+6.1f%%  worst drop %+6.1f%%  trades %d  | %s" % (lab, 100 * d["a_year"], 100 * d["dip"], d["trades"],
              "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in sorted(d["years"].items()))))
    json.dump(out, io.open(os.path.join("validation", "backburner_tier2_account.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
