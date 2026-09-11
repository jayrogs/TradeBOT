"""regen_windows.py -- rebuild trend_windows.json for SPECIFIC windows.

For when a round is mid-grading and the data must be regenerated exactly --
no random draw, the windows are named. Dumps the same structure pics_trend
does (candles, ema, state lane, eq, spans, pivots).
"""

import json
import warnings

import numpy as np
import pandas as pd

import panel as P
import panel_v3 as V3
import pics_spans as PSP
import rider
import scanner as SC

warnings.filterwarnings("ignore")

WIN = 200
RULES = {"1h": None, "4h": "4h", "1d": "1D"}

WINDOWS = [
    (1, "AVAX", "1h", "2024-11-22"),
    (2, "PUMP", "1h", "2026-04-03"),
    (3, "PEPE", "1h", "2026-02-26"),
    (4, "DOGE", "1d", "2022-06-17"),
    (5, "PENGU", "1h", "2025-04-30"),
]


def main():
    dumps, rows = [], []
    for n, sym, tf, start in WINDOWS:
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[tf]) if RULES[tf] else raw
        a0 = int(df.index.searchsorted(pd.Timestamp(start)))
        d = df.iloc[a0:a0 + WIN]
        st_full, _, _ = P.trend_state(df)
        eqd_full, _ = V3.eq_display(df)
        e_full = rider.ema(df["Close"].values.astype(float))
        piv_all = PSP.labelled_pivots(df)
        spans_all = PSP.spans_from_pivots(piv_all, len(df), df)
        dumps.append(dict(
            n=n, sym=sym, tf=tf,
            dates=[str(x) for x in d.index],
            o=[round(float(x), 8) for x in d["Open"]],
            h=[round(float(x), 8) for x in d["High"]],
            l=[round(float(x), 8) for x in d["Low"]],
            c=[round(float(x), 8) for x in d["Close"]],
            ema=[round(float(x), 8) for x in e_full[a0:a0 + WIN]],
            state=list(st_full[a0:a0 + WIN]),
            eq=[int(x) for x in eqd_full[a0:a0 + WIN]],
            spans=[(k, max(s0, a0) - a0, min(s1, a0 + WIN - 1) - a0)
                   for k, s0, s1 in spans_all
                   if s1 >= a0 and s0 <= a0 + WIN - 1],
            pivots=[dict(x=j - a0, px=price, kind=kind, lab=lab, cx=j - a0)
                    for j, price, kind, lab in piv_all
                    if a0 <= j < a0 + WIN]))
        rows.append(dict(n=n, sym=sym, tf=tf, touches=0, bars=len(d), net=0))
        print("  v4_%02d  %-5s %-3s %s -> %s"
              % (n, sym, tf, d.index[0].date(), d.index[-1].date()))
    json.dump(dumps, open("validation/trend_windows.json", "w"))
    pd.DataFrame(rows).to_csv("validation/v4_index.csv", index=False)
    print("windows restored")


if __name__ == "__main__":
    main()
