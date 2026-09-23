"""backburner_slow.py -- HIS JBHT RULE: a slow bounce is out (2026-09-22). Built from backburner_cool.py.

"Slow, steady RSI cooling drops are not good for buying" (JBHT, round 1). "The faster the dips the better ... bulls
showed up to buy discounted stock" (on BURL). backburner_coolshape: RSI 4-6 hours to get back over 31 -> -0.84% a trade.

OLD HEADER, kept for the column meanings:

His words, round 1 and round 3 on BURL: "did bounce after entry tho, that cools off rsi and makes further legs down less
healthy for bull dip buying" and "if it bounces to cool off rsi that's a red flag. We shouldn't keep long stop for
something that gave a red flag .. the long stop is for when we are scaling in during a solid dip". The e-book says the
same: the setup EXPIRES after the first bounce on that leg.

Same trades, same buys, same half at the 12 EMA, same walked rest. ONLY what happens between the buy and the half
changes: once RSI has closed at 35 (or 40) before the half sold, either the stop goes under the low of the drop
("low"), or the trade is out on the next close back at or under 30 ("exit"). Every row is PAIRED with the page as it
is, trade for trade, so the difference is exact.

    pythonw studies/backburner_cool.py --procs 8 --log logs/backburner_cool.log
Writes validation/backburner_slow.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time
import zlib

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "backburner_slow.json")
WAYS = {"the page now": None,
        "slow bounce = RSI took 4+ hours to get back over 31, out": 4,
        "slow bounce = 5+ hours, out": 5,
        "slow bounce = 7+ hours, out": 7}


def _work(args):
    sym, kind = args
    rows = []
    try:
        for w_i, (w, cool) in enumerate(WAYS.items()):
            v_ = dict(PB.STOP, slow=cool)
            for r in PB.trades_for(sym, kind, v_):
                rows.append([w_i, float(zlib.crc32(("%s|%s" % (kind, sym)).encode()) * 1000000 + r["k"]), r["pct"], r["risk_pct"],
                             float(pd.Timestamp(r["t"]).year), 0.0 if kind in ("stock", "etf") else 1.0,
                             r["end"] - r["k"], 1.0 if r["how"].startswith("out: RSI took") else 0.0,
                             1.0 if r["half_at"] is not None else 0.0])
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    return (np.asarray(rows, dtype=np.float64) if rows else None), []


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
    parts, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, names, chunksize=2):
            errs += err
            if part is not None:
                parts.append(part)
    f = pd.DataFrame(np.concatenate(parts),
                     columns=["way", "id", "pct", "risk", "yr", "crypto", "bars", "cooled_out", "half"])
    base = f[f.way == 0].set_index("id").pct

    def st(g):
        v = g.pct.values
        g2 = g.sort_values("yr", kind="stable")
        blocks = [g2.pct.values[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        diff = g.set_index("id").pct - base.reindex(g.id.values).values
        yd = (g.set_index("id").pct - base).groupby(g.set_index("id").yr).mean()
        tt = diff.mean() / (diff.std() / np.sqrt(len(diff))) if diff.std() > 0 else 0.0
        return dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                    avg_R=float((g.pct / g.risk).mean()), worst=float(v.min()), p5=float(np.percentile(v, 5)),
                    bars=float(g.bars.median()), cooled_out=float(g.cooled_out.mean()), half=float(g.half.mean()),
                    vs_page=float(diff.mean()), t=float(tt), years_better=int((yd > 0).sum()), years=int(len(yd)),
                    blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)))

    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         seconds=int(time.time() - t0), ways=list(WAYS)), table={})
    print("\n  HIS JBHT RULE: A SLOW BOUNCE IS OUT   %d names  (%.0fs)\n" % (len(names), time.time() - t0))
    for cut, sel in (("everything", lambda g: g.pct == g.pct), ("stocks + ETFs", lambda g: g.crypto == 0),
                     ("crypto", lambda g: g.crypto == 1)):
        print("  " + cut)
        print("    %-52s %5s %7s %7s %4s %7s %6s %6s %5s %8s %5s %6s %7s" % (
            "after the buy", "n", "avg", "middle", "won", "worst", "5%", "cooled", "half", "vs page", "t", "yrs", "blocks"))
        for w_i, w in enumerate(WAYS):
            g = f[f.way == w_i]
            g = g[sel(g)]
            if len(g) < 40:
                continue
            s = st(g)
            out["table"]["%s | %s" % (cut, w)] = s
            print("    %-52s %5d %+6.2f%% %+6.2f%% %3.0f%% %+6.1f%% %+5.1f%% %5.0f%% %4.0f%% %+7.2f%% %+5.1f %2d/%-2d %3d/%-3d" % (
                w[:52], s["n"], s["avg"], s["middle"], 100 * s["won"], s["worst"], s["p5"], 100 * s["cooled_out"],
                100 * s["half"], s["vs_page"], s["t"], s["years_better"], s["years"], s["blocks_up"], s["blocks"]))
        print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
