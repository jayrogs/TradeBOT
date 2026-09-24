"""backburner_curve.py -- THE ACCOUNT BALANCE AS A LINE, the page's rules exactly (2026-09-23, his ask: "show me the account
balance as a simple line chart for those 4 years with this technique").

The account of backburner_sizing (#53): 5 buckets, the whole bucket at RSI 30, the later buys on top from spare cash at their
own time, at most 3 buckets in one coin, cash only, marked at every day's close, 20 runs (same-hour signals in random order).
Drawn from $100,000: the typical run, the band the lucky and unlucky 10% of runs sit in, and SPY bought and held.

    pythonw studies/backburner_curve.py --procs 8 --log logs/backburner_curve.log
Writes validation/backburner_curve.json and static/backburner_curve.png
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
import backburner_sizing as SZ    # noqa: E402
from backburner_account import START, stats  # noqa: E402

OUT = os.path.join("validation", "backburner_curve.json")
PNG = os.path.join("static", "backburner_curve.png")
RUNS = 20
START_USD = 100000.0


def cap_coin(tr, cap):
    """At most `cap` buckets in one coin: the later buys are cut once the running total reaches the cap."""
    if tr["kind"] != "crypto":
        return tr
    legs, tot = [tr["legs"][0]], 1.0
    for lg in tr["legs"][1:]:
        m = min(lg[1], max(0.0, cap - tot))
        if m > 0:
            legs.append((lg[0], m, lg[2], lg[3]))
            tot += m
    return dict(tr, legs=legs)


def draw(days, typ, lo, hi, spy, d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mt
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=130)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")
    ax.fill_between(days, lo, hi, color="#3ddc97", alpha=0.13, lw=0, label="unlucky 10% to lucky 10% of runs")
    ax.plot(days, typ, color="#3ddc97", lw=2.2, label="backburner (typical run)")
    ax.plot(days, spy, color="#8b93a1", lw=1.6, label="SPY bought and held")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: "$%dk" % round(v / 1000)))
    ax.yaxis.set_minor_formatter(mt.NullFormatter())
    ticks = [t for t in (100e3, 150e3, 200e3, 300e3, 400e3, 600e3, 800e3, 1e6, 1.5e6) if t <= max(hi) * 1.1]
    ax.set_yticks(ticks)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.tick_params(colors="#c9ced6", labelsize=10)
    ax.grid(color="#252a33", lw=0.6)
    ax.set_xlim(days[0], days[-1] + pd.Timedelta(days=150))
    # end labels in the empty space to the right of the lines
    for y, txt, col in ((typ[-1], "$%s" % format(int(round(typ[-1], -3)), ","), "#3ddc97"),
                        (spy[-1], "$%s" % format(int(round(spy[-1], -3)), ","), "#c9ced6")):
        ax.annotate(txt, (days[-1], y), xytext=(8, 0), textcoords="offset points", color=col, fontsize=11,
                    fontweight="bold", va="center")
    ax.set_title("$100,000 on the backburner, %s to %s  (cash only, marked every day)" % (
        days[0].strftime("%b %Y"), days[-1].strftime("%b %Y")), color="#e6e9ee", fontsize=13, loc="left")
    ax.legend(loc="upper left", frameon=False, labelcolor="#c9ced6", fontsize=10)
    fig.tight_layout()
    os.makedirs(os.path.dirname(PNG), exist_ok=True)
    fig.savefig(PNG, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if (k_ in ("stock", "etf", "crypto") or (k_ == "futures" and s_ in PB.COMMODITY_FUTURES))
                        and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    page, closes = [], {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for a_, _b, c_, sym, kind in ex.map(SZ._work, names, chunksize=2):
            page += a_
            if c_ is not None:
                closes[(kind, sym)] = c_
    page = [cap_coin(t, PB.ACCOUNT.get("crypto_max_buckets", 3)) for t in page]
    end = max(t["t_out"] for t in page).normalize()
    days = pd.date_range(START, end, freq="D")
    res = [SZ.account(page, closes, days, s_, slots=PB.ACCOUNT["buckets"], on_top=True) for s_ in range(RUNS)]
    curves = np.array([r[0] for r in res])
    ann = np.array([stats(c, days)["a_year"] for c in curves])
    mid = int(np.argsort(ann)[len(ann) // 2])
    typ = curves[mid] * START_USD
    lo = np.percentile(curves, 10, axis=0) * START_USD
    hi = np.percentile(curves, 90, axis=0) * START_USD
    spy = closes[("etf", "SPY")].reindex(days, method="ffill").values
    spy = spy / spy[np.isfinite(spy)][0] * START_USD
    st, ss = stats(typ / START_USD, days), stats(np.nan_to_num(spy / START_USD, nan=1.0), days)
    draw(days, typ, lo, hi, spy, st)
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), trades=len(page), runs=RUNS,
                         start=str(days[0].date()), end=str(days[-1].date()), start_usd=START_USD),
               typical=dict(end_usd=float(typ[-1]), a_year=st["a_year"], dip=st["dip"], years=st["years"]),
               spy=dict(end_usd=float(spy[-1]), a_year=ss["a_year"], dip=ss["dip"], years=ss["years"]),
               weekly=[dict(day=str(d.date()), typical=round(float(t)), low=round(float(l)), high=round(float(h)),
                            spy=round(float(s))) for d, t, l, h, s in zip(days[::7], typ[::7], lo[::7], hi[::7], spy[::7])])
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)
    print("  %d trades, %d runs, %.0fs" % (len(page), RUNS, time.time() - t0))
    print("  typical: $%s  %+.1f%% a year  worst drop %+.1f%%  %s" % (format(int(typ[-1]), ","), 100 * st["a_year"],
          100 * st["dip"], "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in st["years"].items())))
    print("  SPY:     $%s  %+.1f%% a year  worst drop %+.1f%%  %s" % (format(int(spy[-1]), ","), 100 * ss["a_year"],
          100 * ss["dip"], "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in ss["years"].items())))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
