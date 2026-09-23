"""backburner_sector.py -- DOES SECTOR MOMENTUM MAKE A BETTER BACKBURNER? Ratio charts, Joey's way (2026-09-23).

His words: "Ideally that's what I would do [hold for the daily move, the ETH stop], if I think the sector is getting more
momentum. Sector momentum is best identified with ratio charts .. Joey talks about it so much, and it's an incredible tool
to see relative strength and sector rotation." So before any stop changes, step 1: is the read real on these trades?

For every page trade, on the DAILY charts, using only bars dated before the day of the buy:
  STOCKS  the sector = the fund the name actually moves with (validation/sector_map.json: XLI, XLK, XLY ...)
          ratio = sector / SPY.  gaining = ratio above its own daily 12 EMA (Joey's line on the ratio chart).
          THE "DOWN LESS" TRAP (#42): a rising ratio is the sector going UP MORE or DOWN LESS. So split by whether the
          sector itself is above its own daily 12 EMA.  Names whose leader IS SPY have no sector read.
  CRYPTO  ratio = coin / BTC, split by BTC above / below its own 12 EMA. BTC itself has no read.
Four groups, the page's trades and management unchanged -- only the split.

    pythonw studies/backburner_sector.py --procs 8 --log logs/backburner_sector.log
Writes validation/backburner_sector.json and _rows.parquet
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
import exit_managers as XM        # noqa: E402

OUT = os.path.join("validation", "backburner_sector.json")
SMAP = json.load(open(os.path.join("validation", "sector_map.json")))
_cache = {}


def _daily(kind, sym):
    key = (kind, sym)
    if key not in _cache:
        d = S.frames_for(sym, kind).get("1d")
        if d is None:
            _cache[key] = None
        else:
            idx = pd.DatetimeIndex(d.index)
            if idx.tz is not None:
                idx = idx.tz_localize(None)
            _cache[key] = pd.Series(d["Close"].values.astype(float), index=idx.normalize()).groupby(level=0).last()
    return _cache[key]


def _read(sec, bench, t):
    """ratio above its 12 EMA, and the sector above its own 12 EMA, on the last daily bar dated before t's day."""
    j = pd.concat([sec, bench], axis=1, join="inner").dropna()
    j.columns = ["s", "b"]
    j = j[j.index < t.normalize()]
    if len(j) < 40:
        return None
    r = (j.s / j.b).values
    r12 = XM.ema(r, 12)
    s12 = XM.ema(j.s.values, 12)
    return (1.0 if r[-1] > r12[-1] else 0.0, 1.0 if j.s.values[-1] > s12[-1] else 0.0)


def _work(args):
    sym, kind = args
    rows = []
    try:
        lead = SMAP.get("%s|%s" % (kind, sym))
        if kind == "crypto":
            if sym == "BTC":
                return rows, []
            sec, bench = _daily(kind, sym), _daily("crypto", "BTC")
            sec_name = "BTC"
        else:
            if not lead or lead[0] == "etf|SPY" or ("%s|%s" % (kind, sym)) == lead[0]:
                return rows, []
            lk, ls = lead[0].split("|")
            sec, bench = _daily(lk, ls), _daily("etf", "SPY")
            sec_name = ls
        if sec is None or bench is None:
            return rows, []
        for r in PB.trades_for(sym, kind):
            t = pd.Timestamp(r["t"])
            if t.tz is not None:
                t = t.tz_localize(None)
            rd = _read(sec, bench, t)
            if rd is None:
                continue
            rows.append((kind, sym, sec_name, float(t.year), rd[0], rd[1], r["pct"],
                         1.0 if r["half_at"] is not None else 0.0, float(r["end"] - r["k"])))
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
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=2):
            rows += got
            errs += err
    f = pd.DataFrame(rows, columns=["kind", "sym", "sector", "yr", "ratio_up", "sector_up", "pct", "half", "bars"])
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), n=int(len(f))),
               table={})

    def row(cut, label, g):
        if len(g) < 30:
            print("    %-58s %5d  (too few)" % (label, len(g)))
            return
        g = g.sort_values("yr", kind="stable")
        v = g.pct.values
        yrs = g.groupby("yr").pct.mean()
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        d = dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                 p5=float(np.percentile(v, 5)), years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                 blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)), hold=float(g.bars.median()))
        out["table"]["%s | %s" % (cut, label)] = d
        print("    %-58s %5d %+7.2f%% %+7.2f%% %4.0f%% %+6.1f%% %3d/%-3d %4d/%-4d %5.0f" % (
            label, d["n"], d["avg"], d["middle"], 100 * d["won"], d["p5"], d["years_up"], d["years"],
            d["blocks_up"], d["blocks"], d["hold"]))

    for cut, sel in (("stocks + ETFs", f.kind != "crypto"), ("crypto", f.kind == "crypto")):
        g0 = f[sel]
        print("\n  %s, %d trades with a read  (%.0fs)" % (cut.upper(), len(g0), time.time() - t0))
        print("    %-58s %5s %8s %8s %5s %7s %7s %9s %5s" % ("at the buy (daily, bars already closed)", "n", "avg",
                                                             "middle", "won", "5%", "yrs", "blocks", "hours"))
        row(cut, "every trade", g0)
        if cut == "crypto":
            row(cut, "coin GAINING on BTC, and BTC rising (up more)", g0[(g0.ratio_up == 1) & (g0.sector_up == 1)])
            row(cut, "coin GAINING on BTC, BTC falling (down less)", g0[(g0.ratio_up == 1) & (g0.sector_up == 0)])
            row(cut, "coin LOSING to BTC, BTC rising", g0[(g0.ratio_up == 0) & (g0.sector_up == 1)])
            row(cut, "coin LOSING to BTC, BTC falling", g0[(g0.ratio_up == 0) & (g0.sector_up == 0)])
        else:
            row(cut, "sector GAINING on SPY, and rising itself (UP MORE)", g0[(g0.ratio_up == 1) & (g0.sector_up == 1)])
            row(cut, "sector GAINING on SPY, but falling (DOWN LESS)", g0[(g0.ratio_up == 1) & (g0.sector_up == 0)])
            row(cut, "sector LOSING to SPY, but rising", g0[(g0.ratio_up == 0) & (g0.sector_up == 1)])
            row(cut, "sector LOSING to SPY, and falling", g0[(g0.ratio_up == 0) & (g0.sector_up == 0)])
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
