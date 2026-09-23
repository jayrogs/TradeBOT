"""backburner_news.py -- THE NEWS / EARNINGS SKIP (2026-09-23, his words: "we absolutely need a news earnings skip, it muddies
the water way too much, adds so many variables. That's why I like crypto, it's always going so it kind of constantly
prices stuff in").

His round-6 rejects were news: CORZ opened -18% the day CoreWeave announced it was buying Core Scientific; SPGI opened -6% on
its earnings morning (the brokerage earnings calendar confirms: 2023-07-27, before the open). A news day shows up as an
OPENING GAP far bigger than the name's normal daily move. The gap is known at the open, before any hourly buy that day.

ONE change: skip a stock / ETF trade when the buy day, or the day before it, opened with a gap of N daily normal bars or
more (either direction -- news can spike a name before it dumps). Crypto has no earnings and is not touched. Same trades,
only the skip changes. Every skipped trade is saved with its date so the flag can be checked against the real calendar.

    pythonw studies/backburner_news.py --procs 8 --log logs/backburner_news.log
Writes validation/backburner_news.json and _rows.parquet
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
import eq_freeride2 as FR2        # noqa: E402
import panel as P                 # noqa: E402

OUT = os.path.join("validation", "backburner_news.json")
CUTS = [1.0, 1.5, 2.0, 3.0]
SMAP = json.load(open(os.path.join("validation", "sector_map.json")))
# VERSION 2 (same day): the gap catches whole-market news too (2026-04-08 every energy name gapped with oil; 2026-01-30 the
# gold and silver names) and most of those trades WON. His skip is about COMPANY news and earnings. So: stocks only (a
# fund has no earnings), and only when the stock gapped but its SECTOR FUND did not (under 1 of its own normal days).


def _work(args):
    sym, kind = args
    rows = []
    try:
        got = PB.trades_for(sym, kind)
        if not got:
            return rows, []
        fr = {k_: v for k_, v in S.frames_for(sym, kind).items() if k_ in ("1h", "1d")}
        fr = FR2.regular_hours(fr)
        d = fr["1d"]
        o = d["Open"].values.astype(float); c = d["Close"].values.astype(float)
        a = P._atr(d)
        di = pd.DatetimeIndex(d.index)
        if di.tz is not None:
            di = di.tz_localize(None)
        di = di.normalize()
        lead = SMAP.get("%s|%s" % (kind, sym))
        lk, ls = (lead[0].split("|") if lead and lead[0] != "%s|%s" % (kind, sym) else ("etf", "SPY"))
        sgap = {}
        sd = S.frames_for(ls, lk).get("1d")
        if sd is not None:
            so = sd["Open"].values.astype(float); sc = sd["Close"].values.astype(float); sa = P._atr(sd)
            si = pd.DatetimeIndex(sd.index)
            si = (si.tz_localize(None) if si.tz is not None else si).normalize()
            for q in range(1, len(si)):
                if np.isfinite(sa[q - 1]) and sa[q - 1] > 0:
                    sgap[si[q]] = (so[q] - sc[q - 1]) / sa[q - 1]
        for r in got:
            t = pd.Timestamp(r["t"])
            if t.tz is not None:
                t = t.tz_localize(None)
            i = int(di.searchsorted(t.normalize()))             # the buy day's daily bar
            if i >= len(di) or di[i] != t.normalize() or i < 3:
                continue
            gaps = []
            for q in (i, i - 1):                                 # the buy day and the day before
                ref = a[q - 1]
                gaps.append((o[q] - c[q - 1]) / ref if np.isfinite(ref) and ref > 0 else np.nan)
            gpct = 100 * (o[i] / c[i - 1] - 1)
            sg = max(abs(sgap.get(di[i], 0.0)), abs(sgap.get(di[i - 1], 0.0)))
            rows.append((kind, sym, str(t)[:10], float(t.year), gaps[0], gaps[1], gpct, r["pct"], sg))
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    return rows, []


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=2):
            rows += got
            errs += err
    f = pd.DataFrame(rows, columns=["kind", "sym", "date", "yr", "gap_today", "gap_prev", "gap_pct", "pct",
                                  "sector_gap"])
    f["gap_big"] = np.fmax(f.gap_today.abs(), f.gap_prev.abs())
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), n=int(len(f))), table={})

    def st(g):
        if len(g) < 20:
            return None
        v = g.pct.values
        yrs = g.groupby("yr").pct.mean()
        return dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                    worst=float(v.min()), p5=float(np.percentile(v, 5)), years_up=int((yrs > 0).sum()),
                    years=int(len(yrs)), total=float(v.sum()))

    print("\n  THE NEWS / EARNINGS SKIP: stocks + ETFs, %d trades  (%.0fs)\n" % (len(f), time.time() - t0))
    print("    %-52s %5s %8s %8s %5s %8s %7s %7s %9s" % ("skip when the buy day or the day before gapped", "n", "avg",
                                                        "middle", "won", "worst", "5%", "yrs", "total"))
    base = st(f)
    out["table"]["every trade (the page)"] = base
    print("    %-52s %5d %+7.2f%% %+7.2f%% %4.0f%% %+7.1f%% %+6.1f%% %2d/%-2d %+8.0f%%" % (
        "every trade (the page now)", base["n"], base["avg"], base["middle"], 100 * base["won"], base["worst"],
        base["p5"], base["years_up"], base["years"], base["total"]))
    for n_ in CUTS:
        for lab, g in (("KEPT: no gap of %.1f normal days" % n_, f[~(f.gap_big >= n_)]),
                       ("   skipped: a gap of %.1f+ normal days" % n_, f[f.gap_big >= n_])):
            s = st(g)
            if not s:
                print("    %-52s %5d  (too few)" % (lab, len(g)))
                continue
            out["table"][lab.strip()] = s
            print("    %-52s %5d %+7.2f%% %+7.2f%% %4.0f%% %+7.1f%% %+6.1f%% %2d/%-2d %+8.0f%%" % (
                lab, s["n"], s["avg"], s["middle"], 100 * s["won"], s["worst"], s["p5"], s["years_up"], s["years"],
                s["total"]))
        print()
    print("  total = the sum of every trade's return: what the whole list made. 'normal day' = the daily normal bar.")
    print("\n  VERSION 2: STOCKS ONLY, AND ONLY WHEN THE STOCK GAPPED BUT ITS SECTOR FUND DID NOT (under 1 of its normal days)")
    for n_ in (1.5, 2.0, 3.0):
        news = (f.kind == "stock") & (f.gap_big >= n_) & (f.sector_gap < 1.0)
        for lab, g in (("KEPT: no company-only gap of %.1f" % n_, f[~news]),
                       ("   skipped: company-only gap of %.1f+" % n_, f[news])):
            s = st(g)
            if not s:
                print("    %-52s %5d  (too few)" % (lab, len(g)))
                continue
            out["table"]["v2 " + lab.strip()] = s
            print("    %-52s %5d %+7.2f%% %+7.2f%% %4.0f%% %+7.1f%% %+6.1f%% %2d/%-2d %+8.0f%%" % (
                lab, s["n"], s["avg"], s["middle"], 100 * s["won"], s["worst"], s["p5"], s["years_up"], s["years"],
                s["total"]))
        print()
    mk = f[(f.gap_big >= 2.0) & ~((f.kind == "stock") & (f.sector_gap < 1.0))]
    s = st(mk)
    if s:
        print("  the 2.0+ gaps version 2 KEEPS (the sector gapped too, or a fund): %d trades, avg %+.2f%%, won %.0f%%" % (
            s["n"], s["avg"], 100 * s["won"]))
    big = f[f.gap_big >= 2.0].sort_values("date")
    print("\n  the trades a 2.0 cut skips, newest first (to check against the earnings calendar):")
    for r in big.sort_values("date", ascending=False).head(40).itertuples():
        print("    %s %-6s gap %+5.1f%% (%+.1f normal days)  trade %+6.2f%%" % (r.date, r.sym, r.gap_pct,
                                                                             r.gap_today, r.pct))
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
