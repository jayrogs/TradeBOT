"""context_sheet.py -- one chart, all the context: the answer to "add extra
timeframes so i can zoom out" and "what about the trend checks for all the
higher timeframes".

Each example renders as a sheet:
  - the trade on its own timeframe (touches, entry, promotion star, exit,
    trail), live-trend background
  - a zoomed-out 4h panel and a daily panel, each with their own live-trend
    background, the trade's time window shaded
  - a COMPLETE trend row at entry: 1h 4h 12h 1d 1w 1mo, with FLAT labeled
    FLAT (the old strip printed '--' for FLAT, which read as missing data)
  - the graded context vetoes COMPUTED, not eyeballed, from the ride_study
    quintiles: dead tape, extended week, violent range

Trades themselves come from trade_pics2.trades_with_marks, which
test_harden.py proves identical to the scored rule.
"""

import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import panel as P
import rider
import trade_pics2 as TP
import rider_v4 as V4

warnings.filterwarnings("ignore")

DEAD_TAPE = 0.79      # relvol bottom quintile averaged -0.21%/trade
EXTENDED = 0.0481     # 7d return above the 60th pct: buckets go negative
VIOLENT = 0.0206      # atr/price top quintile averaged -0.51%/trade
CTX_TFS = ["1h", "4h", "12h", "1d", "1w", "1mo"]
CTX_RULE = {"4h": "4h", "12h": "12h", "1d": "1D", "1w": "W-FRI", "1mo": "ME"}


def _paint(ax, d, st, e, label, fmt, eq=None):
    o = d["Open"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    cc = d["Close"].values.astype(float)
    tcol = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d"}
    i = 0
    while i < len(d):
        j = i
        while j + 1 < len(d) and st[j + 1] == st[i]:
            j += 1
        col = tcol.get(st[i])
        if col:
            ax.axvspan(i - .5, j + .5, color=col, lw=0, zorder=0)
        i = j + 1
    for k in range(len(d)):
        col = "#3ddc97" if cc[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=.7, zorder=2)
        ax.plot([k, k], [min(o[k], cc[k]), max(o[k], cc[k])], color=col,
                lw=2.2, zorder=2, solid_capstyle="butt")
    if e is not None:
        ax.plot(np.arange(len(d)), e, color="#c9a35d", lw=1.1, zorder=3)
    if eq is not None:
        # the range overlay, owner-verified: translucent blue wherever the
        # EQ rule is alive -- can coexist with a trend background
        i = 0
        while i < len(d):
            if eq[i]:
                j = i
                while j + 1 < len(d) and eq[j + 1]:
                    j += 1
                ax.axvspan(i - .5, j + .5, color="#5aa9ff", alpha=0.13,
                           lw=0, zorder=1)
                i = j + 1
            else:
                i += 1
    ax.set_facecolor("#0d0f12")
    ax.set_xlim(-1, len(d))
    ax.tick_params(colors="#8b93a1", labelsize=7)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.4)
    step = max(len(d) // 7, 1)
    ax.set_xticks(np.arange(len(d))[::step])
    ax.set_xticklabels([v.strftime(fmt) for v in d.index[::step]],
                       fontsize=6.5)
    if label:
        ax.set_title(label, color="#8b93a1", fontsize=9, loc="left", pad=3)


def context_checks(raw1h, df, when, entry_idx):
    """The graded vetoes, computed instead of eyeballed."""
    past = raw1h[raw1h.index <= when]
    dv = past["Close"] * past["Volume"]
    rv = float(dv.tail(24).mean() / max(dv.tail(24 * 30).median(), 1e-9))
    c7 = past["Close"]
    r7 = float(c7.iloc[-1] / c7.iloc[-168] - 1) if len(c7) > 168 else np.nan
    a = P._atr(df)
    ap = (float(a[entry_idx] / df["Close"].values[entry_idx])
          if np.isfinite(a[entry_idx]) else np.nan)
    out = [("tape %.1fx normal" % rv, rv < DEAD_TAPE, "DEAD TAPE")]
    if np.isfinite(r7):
        out.append(("week %+.1f%%" % (100 * r7), r7 > EXTENDED, "EXTENDED"))
    if np.isfinite(ap):
        out.append(("range %.1f%%/bar" % (100 * ap), ap > VIOLENT, "VIOLENT"))
    return out


def trend_row(raw1h, when):
    import panel_v3 as V3
    out = []
    for x in CTX_TFS:
        d = raw1h if x == "1h" else P.resample(raw1h, CTX_RULE[x])
        if d is None or len(d) < 60:
            out.append((x, "n/a"))
            continue
        st, _, _ = P.trend_state(d)
        s = pd.Series(st, index=d.index)
        s = s[s.index <= when]
        if not len(s):
            out.append((x, "n/a"))
            continue
        val = str(s.iloc[-1])
        if val == "FLAT":
            eq, _ = V3.eq_overlay(d)
            se = pd.Series(eq, index=d.index)
            se = se[se.index <= when]
            if len(se) and bool(se.iloc[-1]):
                val = "BALANCE"
        out.append((x, val))
    return out


def draw_context(sym, tf, df, t, raw1h, path):
    c, lo, e, armed, holding, touch, near, rising, up_now = V4.prep(df)
    pad = min(40, max(15, t["bars"] // 2))
    a = max(0, t["ride"] - pad)
    b = min(len(df) - 1, t["exit"] + pad)
    d = df.iloc[a:b + 1]
    when = df.index[t["entry"]]

    fig = plt.figure(figsize=(16, 10.5), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    gs = gridspec.GridSpec(2, 2, height_ratios=[2.1, 1.0], hspace=0.28,
                           wspace=0.10, left=0.045, right=0.985,
                           top=0.90, bottom=0.05)

    # ---- the trade, on its own timeframe
    ax = fig.add_subplot(gs[0, :])
    import panel_v3 as V3
    import pics_spans as PSpan
    st_full = PSpan.span_states(df)        # the owner's span grammar
    eqd_full, _ = V3.eq_display(df)
    fmt = "%Y-%m-%d" if tf in ("1d", "1w") else "%m-%d %H:%M"
    _paint(ax, d, list(st_full[a:b + 1]), e[a:b + 1], "", fmt,
           eq=list(eqd_full[a:b + 1]))
    x = np.arange(len(d))
    am = armed[a:b + 1]
    i = 0
    while i < len(d):
        if not am[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(d) and am[j + 1]:
            j += 1
        ax.plot(x[i:j + 1], e[a:b + 1][i:j + 1], color="#ffb84d", lw=3.0,
                zorder=4)
        i = j + 1
    ei, xi = t["entry"] - a, t["exit"] - a
    seg = slice(ei, xi + 1)
    ax.plot(x[seg], e[a:b + 1][seg] * 0.97, color="#ff5c72", lw=1.2, ls=":",
            zorder=4)
    mk = [m - a for m in t["marks"] if a <= m <= b]
    if mk:
        ll = df["Low"].values.astype(float)[a:b + 1]
        ax.scatter(mk, [ll[m] for m in mk], marker="^", s=46,
                   color="#5aa9ff", zorder=6)
    # markers sit OFF the candles -- below the low for the buy, above the
    # high for the exit -- so they never cover the bar they refer to
    fp = t.get("fill", c[t["entry"]])
    cc = d["Close"].values.astype(float)
    hh = d["High"].values.astype(float)
    llw = d["Low"].values.astype(float)
    off = (hh.max() - llw.min()) * 0.03
    ax.scatter([ei], [llw[ei] - off], marker="^", s=170, color="#3ddc97",
               zorder=9, edgecolors="#0d0f12", linewidths=1.2)
    ax.scatter([xi], [hh[xi] + off], marker="v", s=170, color="#ff5c72",
               zorder=9, edgecolors="#0d0f12", linewidths=1.2)
    pr = t.get("prom")
    if pr is not None and a <= pr <= b:
        ax.scatter([pr - a], [hh[pr - a] + off], marker="*", s=190,
                   color="#ffd700", zorder=8, edgecolors="#0d0f12",
                   linewidths=0.7)
    ax.annotate("BUY %.6g" % fp, (ei, llw[ei] - off), color="#3ddc97",
                fontsize=9, weight="bold", xytext=(6, -14),
                textcoords="offset points")
    lab = "TRAIL HIT" if t.get("why") == "stop" else "BODY CLOSED UNDER EMA"
    ax.annotate(lab, (xi, hh[xi] + off), color="#ff5c72", fontsize=9,
                weight="bold", xytext=(6, 8), textcoords="offset points")

    # ---- headline, full trend row, computed vetoes
    net = 100 * t["net"]
    fig.text(0.045, 0.962, "%s  %s   held %d bars   %+.2f%%"
             % (sym, tf, t["bars"], net),
             color="#3ddc97" if net > 0 else "#ff5c72",
             fontsize=13, weight="bold")
    col = {"UP": "#3ddc97", "DOWN": "#ff5c72", "BALANCE": "#5aa9ff",
           "FLAT": "#6b7280"}
    x0 = 0.335
    fig.text(x0 - 0.072, 0.952, "trend at entry:", color="#8b93a1", fontsize=9)
    for name, stv in trend_row(raw1h, when):
        disp = {"UP": "UP", "DOWN": "DN", "BALANCE": "EQ",
                "FLAT": "FLAT"}.get(stv, stv)
        fig.text(x0, 0.964, name, color="#5b6472", fontsize=8)
        fig.text(x0, 0.944, disp, color=col.get(stv, "#6b7280"),
                 fontsize=10, weight="bold")
        x0 += 0.045
    x0 += 0.022
    fig.text(x0 - 0.014, 0.952, "checks:", color="#8b93a1", fontsize=9)
    for txt, bad, flag in context_checks(raw1h, df, when, t["entry"]):
        fig.text(x0 + 0.038, 0.964, txt, color="#8b93a1", fontsize=8)
        fig.text(x0 + 0.038, 0.944, flag if bad else "ok",
                 color="#ff5c72" if bad else "#3ddc97", fontsize=9.5,
                 weight="bold")
        x0 += 0.095

    # ---- zoomed-out panels: 4h and daily, trade window shaded
    for gpos, ctf, rule, nbars, cfmt in (
            ((1, 0), "4h", "4h", 240, "%m-%d"),
            ((1, 1), "1d", "1D", 200, "%Y-%m")):
        axc = fig.add_subplot(gs[gpos])
        dd = P.resample(raw1h, rule)
        if dd is None or len(dd) < 60:
            continue
        pos = int(dd.index.searchsorted(when))
        aa = max(0, pos - int(nbars * 0.7))
        bb = min(len(dd) - 1, pos + int(nbars * 0.3))
        dw = dd.iloc[aa:bb + 1]
        stc = PSpan.span_states(dd)
        eqc, _ = V3.eq_display(dd)
        ee = rider.ema(dd["Close"].values.astype(float))[aa:bb + 1]
        _paint(axc, dw, list(stc[aa:bb + 1]), ee, "%s context" % ctf, cfmt,
               eq=list(eqc[aa:bb + 1]))
        t0 = int(dw.index.searchsorted(when))
        t1 = int(dw.index.searchsorted(df.index[t["exit"]]))
        axc.axvspan(t0 - .5, t1 + .5, color="#ffffff", alpha=0.07, zorder=1)
        axc.axvline(t0, color="#3ddc97", lw=1.0, ls="--", alpha=0.8, zorder=5)

    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
