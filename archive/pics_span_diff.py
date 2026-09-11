"""pics_span_diff.py -- before vs after the HL-break rule, stacked.

Top panel: the first span grammar (a trend only died on the killing pivot).
Bottom panel: the corrected grammar (it also dies at the candle that closes
through the last HL / reclaims the last LH). Amber outlines on the bottom
panel mark exactly the bars whose color CHANGED -- the overstay the old
rule granted and the new rule takes away.
"""

import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import context_sheet as CS
import pics_spans as PS
import rider
import scanner as SC

warnings.filterwarnings("ignore")

OUT = "validation"
WIN = 200
RULES = {"1h": None, "4h": "4h", "1d": "1D"}
COLS = {"UP": "#12351f", "DOWN": "#3a1720"}


def paint_spans(ax, spans, pos, mark=None):
    for kind, s0, s1 in spans:
        aa = max(s0, pos) - pos
        bb = min(s1, pos + WIN - 1) - pos
        if bb < 0 or aa > WIN - 1 or bb < aa:
            continue
        ax.axvspan(aa - .5, bb + .5, color=COLS[kind], lw=0, zorder=0)
    if mark is not None:
        i = 0
        while i < WIN:
            if mark[i]:
                j = i
                while j + 1 < WIN and mark[j + 1]:
                    j += 1
                ax.axvspan(i - .5, j + .5, fill=False, edgecolor="#ffb84d",
                           lw=1.6, zorder=5)
                i = j + 1
            else:
                i += 1


def membership(spans, pos, n_all):
    m = np.zeros(WIN, dtype=object)
    m[:] = ""
    for kind, s0, s1 in spans:
        aa = max(s0, pos) - pos
        bb = min(s1, pos + WIN - 1) - pos
        if bb < 0 or aa > WIN - 1 or bb < aa:
            continue
        for b in range(aa, bb + 1):
            m[b] = kind
    return m


def main():
    import json
    W = json.load(open("validation/trend_windows.json"))
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
        piv = PS.labelled_pivots(df)
        old = PS.spans_from_pivots(piv, len(df))          # pivot kills only
        new = PS.spans_from_pivots(piv, len(df), df)      # + the HL break
        m_old = membership(old, pos, len(df))
        m_new = membership(new, pos, len(df))
        changed = m_old != m_new

        import chartkit as CK
        bnd_new = CK.bundle(df, pos, WIN)
        bnd_old = dict(bnd_new)
        bnd_old["spans"] = [(k, max(s0, pos) - pos,
                             min(s1, pos + WIN - 1) - pos)
                            for k, s0, s1 in old
                            if s1 >= pos and s0 <= pos + WIN - 1]
        fig, axs = plt.subplots(2, 1, figsize=(16, 9.6), dpi=110)
        fig.patch.set_facecolor("#0d0f12")
        fmt = "%Y-%m-%d" if tf == "1d" else "%m-%d %H:%M"
        CK.render(axs[0], bnd_old,
                  "BEFORE -- span ends only at the killing pivot", fmt)
        CK.render(axs[1], bnd_new,
                  "AFTER -- also ends at the candle that closes through the "
                  "last HL / LH, excluded  (amber = changed bars)", fmt)
        i2 = 0
        while i2 < WIN:
            if changed[i2]:
                j2 = i2
                while j2 + 1 < WIN and changed[j2 + 1]:
                    j2 += 1
                axs[1].axvspan(i2 - .5, j2 + .5, fill=False,
                               edgecolor="#ffb84d", lw=1.6, zorder=5)
                i2 = j2 + 1
            else:
                i2 += 1
        nch = int(changed.sum())
        fig.suptitle("%s %s   %s -> %s      %d bars changed"
                     % (sym, tf, d.index[0].date(), d.index[-1].date(), nch),
                     color="#e6e9ee", fontsize=13, x=0.16)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "v4_%02d.png" % w["n"]),
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        rows.append(dict(n=w["n"], sym=sym, tf=tf, touches=0, bars=nch, net=0))
        print("  v4_%02d  %-5s %-3s  %d bars changed" % (w["n"], sym, tf, nch),
              flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
