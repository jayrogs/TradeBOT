"""pics_trendwin.py -- draw ONE trend (an uptrend or a downtrend) from the trend
study, so it can be checked by eye from /trendstudy/<kind>/<sym>.

The window runs from 40 bars before the trend opened to 25 bars after it died.
Same drawing as every other chart here (chartkit: candles, labelled pivots, the
12 EMA), with the LIVE trend colours (what the rule could see bar by bar). The
floor of an uptrend (the last higher low) / the ceiling of a downtrend (the last
lower high) is drawn as a stepped line, and an x marks the bar that killed it.
Every label is placed in a lane above or below price, then the picture is
measured with pics_ride.overlaps().
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "studies"))
import chartkit as CK             # noqa: E402
import structure as ST            # noqa: E402
import panel as P                 # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
UP, DN = "#3ddc97", "#ff5c72"


def floor_series(df, spans, piv, s0, s1, kind):
    """The live floor/ceiling bar by bar inside [s0, s1]: the last HL (or LH)
    confirmed at or before each bar, starting from the one that opened it."""
    n = len(df)
    lvl = np.full(n, np.nan)
    want = "HL" if kind == "UP" else "LH"
    cur = np.nan
    # the level at the open is the last such pivot confirmed by s0
    for ci, j, price, k_, lab in piv:
        if ci > s1:
            break
        if lab == want and ci <= s0:
            cur = price
    k = 0
    for b in range(s0, s1 + 1):
        for ci, j, price, k_, lab in piv:
            if ci == b and lab == want and b > s0:
                cur = price
        lvl[b] = cur
    return lvl


def render(sym, kind, tf, frames, t_start, t_end, path):
    df = frames[tf]
    idx = df.index
    p0 = int(idx.get_indexer([pd.Timestamp(t_start)])[0])
    p1 = int(idx.get_indexer([pd.Timestamp(t_end)])[0])
    if p0 < 0 or p1 < 0:
        return None
    n = len(df)
    x0 = max(0, p0 - 40)
    x1 = min(n - 1, p1 + 25)
    spans = ST.spans(df, causal=True)
    span = next(((k_, s0, s1) for k_, s0, s1 in spans if s0 == p0), None)
    if span is None:
        return None
    k_, s0, s1 = span
    piv = ST.pivots(df)
    lvl = floor_series(df, spans, piv, s0, s1, k_)
    c = df["Close"].values.astype(float)
    more = sum(1 for ci, j, price, kk, lab in piv if s0 < ci <= s1 and lab in (("HL", "HH") if k_ == "UP" else ("LH", "LL")))
    died = "still open" if s1 >= n - 1 else "died"
    gain = c[s1] / c[s0] - 1 if c[s0] > 0 else 0.0

    fig = plt.figure(figsize=(15, 7.5), dpi=105)
    fig.patch.set_facecolor(DARK)
    ax = fig.add_subplot(111)
    bnd = CK.bundle(df, x0, x1 - x0 + 1)
    bnd["spans"] = [(kk, max(a, x0) - x0, min(b, x1) - x0) for kk, a, b in spans if b >= x0 and a <= x1]
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    xs = np.arange(x1 - x0 + 1)
    col = UP if k_ == "UP" else DN
    ax.step(xs, lvl[x0:x1 + 1], where="post", color=col, lw=1.8, zorder=8)
    # the kill: an x on the first bar after the trend, at the level that broke
    if s1 + 1 <= x1 and np.isfinite(lvl[s1]):
        ax.plot([s1 + 1 - x0], [lvl[s1]], marker="x", ms=11, mew=2.2, color=col, zorder=9)
    # lanes above and below price for the two notes, joined by dotted lines
    lo = np.nanmin(bnd["d"]["Low"].values); hi = np.nanmax(bnd["d"]["High"].values)
    pad = (hi - lo) * 0.16
    ax.set_ylim(lo - pad * 1.6, hi + pad * 1.6)
    word = "uptrend" if k_ == "UP" else "downtrend"
    ax.annotate("%s opened" % word, xy=(s0 - x0, lo), xytext=(s0 - x0, lo - pad * 1.25),
                color=col, fontsize=10, ha="center", va="top",
                arrowprops=dict(arrowstyle="-", color=col, ls=":", lw=0.8))
    if s1 < n - 1:
        ax.annotate("%s over" % word, xy=(s1 + 1 - x0, hi), xytext=(s1 + 1 - x0, hi + pad * 1.25),
                    color=col, fontsize=10, ha="center", va="bottom",
                    arrowprops=dict(arrowstyle="-", color=col, ls=":", lw=0.8))
    title = ("%s %s   %s from %s to %s: %d bars, %d more pivot%s after it opened, %s, %+.1f%% open to end"
             % (sym, tf, word, idx[s0].strftime("%Y-%m-%d %H:%M"), idx[s1].strftime("%Y-%m-%d %H:%M"),
                s1 - s0 + 1, more, "" if more == 1 else "s", died, 100 * gain))
    fig.suptitle(title, color="#e6e9ee", fontsize=11.5, x=0.01, ha="left", y=0.985)
    fig.text(0.01, 0.01, "HH HL LH LL: the swing highs and lows (they show 2 bars after they form). Green background: uptrend. Red: downtrend. "
             "The stepped line is the floor (last higher low) or ceiling (last lower high). The x is the bar that ended it.",
             color=DIM, fontsize=9)
    fig.subplots_adjust(left=0.045, right=0.99, top=0.94, bottom=0.09)
    import pics_ride as PR
    probs = PR.overlaps(fig, [(ax, bnd["d"])])          # measured, never silently "clean"
    fig.savefig(path, facecolor=DARK)
    plt.close(fig)
    return dict(problems=probs, bars=int(s1 - s0 + 1), pivots=int(more), gain=float(gain))


if __name__ == "__main__":
    import backburner_study as B
    fr = B.frames_for("BTC", "crypto")
    sp = ST.spans(fr["4h"], causal=True)
    k_, s0, s1 = [x for x in sp if x[0] == "UP" and x[2] - x[1] > 20][-1]
    r = render("BTC", "crypto", "4h", fr, fr["4h"].index[s0], fr["4h"].index[s1], "validation/_trendwin_test.png")
    print(r)
