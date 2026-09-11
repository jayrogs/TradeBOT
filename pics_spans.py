"""pics_spans.py -- the owner's model, verbatim: trends are PIVOT SPANS.

"im using pivots as HL HH, LH, LL, thats all there is to trends, thats it."

So: an uptrend OPENS once a HL and a HH have both printed (span starts at
the first pivot of that pair), runs while HL/HH keep printing, and CLOSES on
the first LH or LL (span ends at that pivot's bar). Downtrend is the mirror.
EH/EL neither build nor kill. There is NO close-break death, NO rebuild tax,
NO per-bar second-guessing -- the pivots are the whole grammar.

Spans are painted at pivot FORMATION bars (the way a human reads a chart in
review). This is a structure view, not a causal trading signal -- a span's
end is only knowable when the killing pivot confirms.

Renders the same windows as the last pics_trend run (same seed) with the
span painting, labeled pivots, and the verified EQ wash.
"""

import argparse
import glob
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import context_sheet as CS
import panel as P
import panel_v3 as V3
import rider
import scanner as SC

warnings.filterwarnings("ignore")

OUT = "validation"
WIN = 200
RULES = {"1h": None, "4h": "4h", "1d": "1D"}
LC = {"HH": "#3ddc97", "HL": "#3ddc97", "LL": "#ff5c72", "LH": "#ff5c72",
      "EH": "#9aa3b2", "EL": "#9aa3b2", "H": "#9aa3b2", "L": "#9aa3b2"}


def labelled_pivots(df, min_atr=None):
    """Compat shim -> structure.labelled_pivots (the backbone)."""
    import structure as ST
    return ST.labelled_pivots(df, min_atr)


def spans_from_pivots(piv, n, df=None):
    """Compat shim -> structure._spans (review clock). The grammar lives in
    structure.py now; this name stays so older renders keep working."""
    import structure as ST
    return ST.spans_from_pivots(piv, n, df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="validation/trend_windows.json")
    a = ap.parse_args()
    import json
    W = json.load(open(a.windows))
    for f in os.listdir(OUT):
        if f.startswith("v4_"):
            os.remove(os.path.join(OUT, f))

    rows = []
    for w in W:
        sym, tf = w["sym"], w["tf"]
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[tf]) if RULES[tf] else raw
        pos = df.index.get_indexer([pd.Timestamp(w["dates"][0])])[0]
        d = df.iloc[pos:pos + WIN]
        piv_all = labelled_pivots(df)
        spans_all = spans_from_pivots(piv_all, len(df), df)
        e = rider.ema(df["Close"].values.astype(float))[pos:pos + WIN]
        eqd, _ = V3.eq_display(df)

        import chartkit as CK
        bnd = CK.bundle(df, pos, WIN)
        nsp = len(bnd["spans"])
        fig, ax = plt.subplots(figsize=(16, 6.6), dpi=110)
        fig.patch.set_facecolor("#0d0f12")
        fmt = "%Y-%m-%d" if tf in ("1d",) else "%m-%d %H:%M"
        CK.render(ax, bnd, "", fmt)
        ax.set_title("%s  %s   %s -> %s      PIVOT SPANS: %d in window"
                     % (sym, tf, d.index[0].date(), d.index[-1].date(), nsp),
                     color="#e6e9ee", fontsize=12, loc="left", pad=10)
        fig.tight_layout()
        p = os.path.join(OUT, "v4_%02d.png" % w["n"])
        fig.savefig(p, facecolor=fig.get_facecolor())
        plt.close(fig)
        rows.append(dict(n=w["n"], sym=sym, tf=tf, touches=0, bars=WIN, net=0))
        print("  v4_%02d  %-5s %-3s  %d spans" % (w["n"], sym, tf, nsp),
              flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()


def span_states(df):
    import structure as ST
    return ST.states(df, causal=False)
