"""chartkit.py -- ONE way to assemble a trend chart. Layers cannot be
forgotten because they are not optional.

Born from a graded failure: the span-diff page silently omitted the EQ wash
because every render script hand-assembled its layers and the wash argument
was optional. The owner burned grading time catching a renderer omission --
the class of bug the machines are supposed to own.

    bundle(df, pos, win)   computes EVERY layer once: candles window, ema,
                           pivot spans, eq wash, labelled pivots
    render(ax, b, title)   draws EVERY layer in the bundle, always, in
                           order. No layer parameters exist to forget.

Scripts choose windows and add annotations ON TOP of render(); they never
re-assemble layers. A deliberate override (like the diff page's old-grammar
panel) replaces a key in the bundle -- visible in the code, not a silent
default. test_harden 3d pins the exact PENGU window that exposed the miss.
"""

import warnings

import numpy as np

import panel as P
import panel_v3 as V3
import pics_spans as PS
import rider

warnings.filterwarnings("ignore")

SPAN_COLS = {"UP": "#12351f", "DOWN": "#3a1720"}
LAB_COLS = {"HH": "#3ddc97", "HL": "#3ddc97", "LL": "#ff5c72",
            "LH": "#ff5c72", "EH": "#9aa3b2", "EL": "#9aa3b2",
            "H": "#9aa3b2", "L": "#9aa3b2"}


def bundle(df, pos, win):
    """Every layer for df[pos:pos+win], computed from the FULL series."""
    d = df.iloc[pos:pos + win]
    piv_all = PS.labelled_pivots(df)
    spans_all = PS.spans_from_pivots(piv_all, len(df), df)
    eqd, _ = V3.eq_display(df)
    return dict(
        d=d,
        pos=pos,
        win=len(d),
        ema=rider.ema(df["Close"].values.astype(float))[pos:pos + win],
        spans=[(k, max(s0, pos) - pos, min(s1, pos + win - 1) - pos)
               for k, s0, s1 in spans_all
               if s1 >= pos and s0 <= pos + win - 1],
        eq=[bool(x) for x in eqd[pos:pos + win]],
        pivots=[(j - pos, price, kind, lab)
                for j, price, kind, lab in piv_all
                if pos <= j < pos + win],
    )


def render(ax, b, title, fmt):
    """Draw the WHOLE bundle. There are no layer switches."""
    d = b["d"]
    n = len(d)
    o = d["Open"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    cc = d["Close"].values.astype(float)

    # 1. span backgrounds
    for kind, s0, s1 in b["spans"]:
        if s1 >= 0 and s0 <= n - 1 and s1 >= s0:
            ax.axvspan(s0 - .5, s1 + .5, color=SPAN_COLS[kind], lw=0,
                       zorder=0)
    # 2. eq wash
    i = 0
    while i < n:
        if b["eq"][i]:
            j = i
            while j + 1 < n and b["eq"][j + 1]:
                j += 1
            ax.axvspan(i - .5, j + .5, color="#5aa9ff", alpha=0.13, lw=0,
                       zorder=1)
            i = j + 1
        else:
            i += 1
    # 3. candles
    for k in range(n):
        col = "#3ddc97" if cc[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=.7, zorder=2)
        ax.plot([k, k], [min(o[k], cc[k]), max(o[k], cc[k])], color=col,
                lw=2.2, zorder=2, solid_capstyle="butt")
    # 4. ema
    ax.plot(np.arange(n), b["ema"], color="#c9a35d", lw=1.1, zorder=3)
    # 5. pivots, labelled
    # two labels of the same side within 3 bars would print on top of each other
    # ("HHHH"): the second one steps out one more row so both stay readable
    last = {"low": (-99, 0), "high": (-99, 0)}
    for x, price, kind, lab in b["pivots"]:
        c = LAB_COLS.get(lab, "#9aa3b2")
        ax.scatter([x], [price], marker="^" if kind == "low" else "v",
                   s=28, color=c, zorder=6)
        lx, lrow = last[kind]
        row = (lrow + 1) % 2 if x - lx <= 3 else 0
        last[kind] = (x, row)
        dy = (-15 - 11 * row) if kind == "low" else (9 + 11 * row)
        ax.annotate(lab, (x, price), color=c, fontsize=7.5, weight="bold",
                    ha="center", xytext=(0, dy),
                    textcoords="offset points", zorder=6)
    # chrome
    ax.set_facecolor("#0d0f12")
    ax.set_xlim(-1, n)
    ax.tick_params(colors="#8b93a1", labelsize=7)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)
    step = max(n // 7, 1)
    ax.set_xticks(np.arange(n)[::step])
    ax.set_xticklabels([v.strftime(fmt) for v in d.index[::step]],
                       fontsize=6.5)
    if title:
        ax.set_title(title, color="#8b93a1", fontsize=9, loc="left", pad=3)
