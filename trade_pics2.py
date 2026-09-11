"""
trade_pics2.py -- draw the v4 trades: touches gate, EMA trailing stop.

    python trade_pics2.py                10 examples
    python trade_pics2.py --stop 0.02 --touches 2

Every statistical version of this playbook has come back flat, and every time
the reason was visible in a picture long before it was visible in a table. So
this draws what the current rule actually buys and sells:

    blue triangles   the TOUCHES -- the low reached the EMA, the body held.
                     The gate: N of these must happen before an entry is taken
    amber EMA        the ride, while armed
    green arrow      entry, taken on the next touch after the gate is met
    red dotted line  the trailing stop, X% below the EMA, rising with it
    red arrow        where the stop was hit

If these are not the trades you would take, the rule is still wrong and no
amount of re-running the statistics will fix it.
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import crypto
import panel as P
import rider
import rider_v4 as V4
import scanner as SC

STRIP = ["15m", "1h", "4h", "12h", "1d", "1w"]

warnings.filterwarnings("ignore")

OUT = "validation"


def trades_with_marks(df, need_touches, stop_pct):
    """The IDENTICAL rule to rider_v4.trades, plus the touch indices for
    drawing. If these two ever disagree, the charts are lying about the test.
    """
    import rider_lab as L
    c, lo, e, armed, holding, touch, near, rising, up_now = V4.prep(df)
    o = df["Open"].values.astype(float)
    atr = P._atr(df)
    upage = np.zeros(len(c), dtype=int)
    for q in range(1, len(c)):
        upage[q] = upage[q - 1] + 1 if up_now[q] else 0
    n = len(c)
    out = []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        # close-confirmed: the touch bar closes with its body holding the
        # EMA, buy at that close -- the variant that survived out of sample
        seen, marks, entry, fill = 0, [], None, None
        for k in range(i, j + 1):
            if touch[k]:
                seen += 1
                marks.append(k)
                if seen > need_touches and rising[k]:
                    # skip the ride if the wind is not there at ITS entry --
                    # waiting for a later touch tested worse in both eras
                    if upage[k] >= L.MIN_WIND:
                        entry = k
                        fill = c[k]
                    break
        if entry is None or entry >= n - 2:
            i = j + 1
            continue
        px, why, prom = None, None, None
        for k in range(entry + 1, n):
            floor = e[k] * (1 - stop_pct)
            if lo[k] <= floor:
                px, why = floor, "stop"
                break
            if prom is None and c[k] >= fill * 1.01:
                prom = k              # proven: body closes no longer exit
            buf = L.EXIT_TOL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
            if prom is None and c[k] < e[k] - buf:
                px, why = c[k], "body"
                break
        if px is None:
            i = j + 1
            continue
        out.append(dict(ride=i, entry=entry, exit=k, marks=marks, why=why,
                        prom=prom, fill=float(fill), bars=int(k - entry),
                        net=float(px / fill - 1 - 2 * V4.COST)))
        i = j + 1
    return out


def tf_strip(sym, when, base_raw):
    """Trend on every available timeframe at the moment of entry."""
    out = []
    for x in STRIP:
        if x in SC.BASE:
            d = base_raw.get(SC.BASE[x])
        else:
            src, rule = SC.DERIVE[x]
            d = SC.resample(base_raw.get(SC.BASE[src]), rule)
        if d is None or len(d) < 60:
            out.append((x, "-"))
            continue
        st, _, _ = P.trend_state(d)
        s = pd.Series(st, index=d.index)
        s = s[s.index <= when]
        out.append((x, str(s.iloc[-1]) if len(s) else "-"))
    return out


def draw(df, t, sym, tf, stop_pct, path, strip=None):
    c, lo, e, armed, holding, touch, near, rising, up_now = V4.prep(df)
    pad = min(40, max(15, t["bars"] // 2))
    a = max(0, t["ride"] - pad)
    b = min(len(df) - 1, t["exit"] + pad)
    d = df.iloc[a:b + 1]
    o = d["Open"].values.astype(float)
    hi = d["High"].values.astype(float)
    cc = c[a:b + 1]
    ll = lo[a:b + 1]
    ee = e[a:b + 1]
    am = armed[a:b + 1]
    x = np.arange(len(d))
    ei, xi = t["entry"] - a, t["exit"] - a

    w = min(30.0, max(13.5, len(d) / 14.0))
    fig, ax = plt.subplots(figsize=(w, 6.2), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    # paint the LIVE trend from the FULL series, sliced to the window. The
    # engine needs ~50 bars of warmup, so recomputing on the crop painted
    # everything grey and made honest green-trend entries look like
    # violations -- an entire grading round was spent on that lie.
    st_full, _, _ = P.trend_state(df)
    st = list(st_full[a:b + 1])
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
        ax.plot([k, k], [ll[k], hi[k]], color=col, lw=.9, zorder=2)
        ax.plot([k, k], [min(o[k], cc[k]), max(o[k], cc[k])], color=col, lw=3.2,
                zorder=2, solid_capstyle="butt")

    ax.plot(x, ee, color="#6b5636", lw=1.2, zorder=3)
    i = 0
    while i < len(d):
        if not am[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(d) and am[j + 1]:
            j += 1
        ax.plot(x[i:j + 1], ee[i:j + 1], color="#ffb84d", lw=3.2, zorder=4)
        i = j + 1

    # the trailing stop, live from entry to exit
    seg = slice(ei, xi + 1)
    ax.plot(x[seg], ee[seg] * (1 - stop_pct), color="#ff5c72", lw=1.3, ls=":",
            zorder=4)
    ax.annotate("stop  %.0f%% under the EMA" % (100 * stop_pct),
                (xi, ee[xi] * (1 - stop_pct)), color="#ff5c72", fontsize=8.5,
                xytext=(-140, -14), textcoords="offset points")

    mk = [m - a for m in t["marks"] if a <= m <= b]
    if mk:
        ax.scatter(mk, ll[mk], marker="^", s=52, color="#5aa9ff", zorder=6)
        ax.annotate("%d touches" % len(t["marks"]), (mk[0], ll[mk[0]]),
                    color="#5aa9ff", fontsize=9, weight="bold",
                    xytext=(-8, -18), textcoords="offset points")

    fp = t.get("fill", cc[ei])
    ax.scatter([ei], [fp], marker="^", s=210, color="#3ddc97", zorder=9,
               edgecolors="#0d0f12", linewidths=1.3)
    ax.scatter([xi], [cc[xi]], marker="v", s=210, color="#ff5c72", zorder=9,
               edgecolors="#0d0f12", linewidths=1.3)
    ax.annotate("BUY %.6g at the confirmed close" % fp, (ei, fp), color="#3ddc97",
                fontsize=9.5, weight="bold", xytext=(7, 12),
                textcoords="offset points")
    pr = t.get("prom")
    if pr is not None and a <= pr <= b:
        pp = pr - a
        ax.scatter([pp], [cc[pp]], marker="*", s=230, color="#ffd700",
                   zorder=8, edgecolors="#0d0f12", linewidths=0.8)
        ax.annotate("proven +1%: body closes ignored, trail only",
                    (pp, cc[pp]), color="#ffd700", fontsize=8.5,
                    xytext=(8, 14), textcoords="offset points")
    lab = ("TRAIL HIT %.6g" % (ee[xi] * (1 - stop_pct))
           if t.get("why") == "stop" else "BODY CLOSED UNDER EMA")
    ax.annotate(lab, (xi, cc[xi]),
                color="#ff5c72", fontsize=9.5, weight="bold",
                xytext=(7, -18), textcoords="offset points")

    ax.set_xlim(-1, len(d))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=.5)
    step = max(len(d) // 8, 1)
    ax.set_xticks(x[::step])
    fmt = "%Y-%m-%d" if tf in ("1d", "1w") else "%m-%d %H:%M"
    ax.set_xticklabels([v.strftime(fmt) for v in d.index[::step]], fontsize=7.5)
    ax.set_title("%s  %s   %d touches before entry   held %d bars   %+.2f%%"
                 % (sym, tf, len(t["marks"]), t["bars"], 100 * t["net"]),
                 color="#3ddc97" if t["net"] > 0 else "#ff5c72",
                 fontsize=12, loc="left", pad=26)

    # the trend on every timeframe, as it stood at the moment of entry
    if strip:
        col = {"UP": "#3ddc97", "DOWN": "#ff5c72", "BALANCE": "#5aa9ff"}
        x0 = 0.0
        fig.text(x0, 0.958, "trend at entry:", color="#8b93a1", fontsize=9,
                 transform=ax.transAxes)
        x0 = 0.115
        for name, stv in strip:
            c2 = col.get(stv, "#3a4150")
            fig.text(x0, 0.958, name, color="#5b6472", fontsize=8.5,
                     transform=ax.transAxes)
            fig.text(x0, 0.917, {"UP": "UP", "DOWN": "DN",
                                 "BALANCE": "EQ"}.get(stv, "--"),
                     color=c2, fontsize=10, weight="bold",
                     transform=ax.transAxes)
            x0 += 0.052
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", type=float, default=0.03)
    ap.add_argument("--touches", type=int, default=2)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--syms", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith("v4_"):
            os.remove(os.path.join(OUT, f))

    # every trade the rule takes, across the top names -- then a RANDOM 20,
    # not a curated worst/middle/best
    u = crypto.universe(a.syms)
    picks = []
    for _, row in u.iterrows():
        sym, src = row["sym"], row["source"]
        try:
            base_raw = {b: crypto.candles(sym, b, 12000, source=src)
                        for b in ("15m", "1h", "1d")}
        except Exception:
            continue
        for tf in ("1h", "4h"):
            raw = base_raw.get("1h")
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 400:
                continue
            for t in trades_with_marks(df, a.touches, a.stop):
                picks.append((sym, tf, df, t, base_raw))
        print("  %-6s %4d trades so far" % (sym, len(picks)))

    rng = np.random.default_rng(42)
    idx = rng.choice(len(picks), size=min(a.n, len(picks)), replace=False)
    rows = []
    for c, i in enumerate(sorted(idx), 1):
        sym, tf, df, t, base_raw = picks[i]
        p = os.path.join(OUT, "v4_%02d.png" % c)
        strip = tf_strip(sym, df.index[t["entry"]], base_raw)
        draw(df, t, sym, tf, a.stop, p, strip)
        rows.append(dict(n=c, sym=sym, tf=tf, touches=len(t["marks"]),
                         bars=t["bars"], net=100 * t["net"], why=t["why"],
                         proven=int(t.get("prom") is not None)))
        print("  v4_%02d  %-6s %-3s  %4d bars  %-5s %s %+7.2f%%"
              % (c, sym, tf, t["bars"], t["why"],
                 "proven" if t.get("prom") is not None else "      ",
                 100 * t["net"]))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "v4_index.csv"), index=False)


if __name__ == "__main__":
    main()
