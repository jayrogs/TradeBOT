"""backburner_cryptolead.py -- EACH COIN'S OWN LEADER, AND DAN'S LEADER RULE ON CRYPTO BACKBURNERS (2026-09-23).

His words on round 6's XRP loser: "most crypto names are paired with a specific larger crypto name. Like most crypto moves
with BTC, certain coins move with eth, others with solana, etc..maybe if xrp moves closest with one of those, then we can
trade it based off of that? Cause the market usually moves simultaneously, and weaker names will dip harder."
Dan's leader rule (#39): do not buy a laggard's hourly oversold while its leader is only weak; the leader's own flush is
the trigger. validation/sector_map.json ties EVERY coin to BTC.

1. THE LEADER: of BTC, ETH and SOL, the one whose DAILY returns move most with the coin's, measured on the FIRST HALF of
   the coin's history only (no peeking). BTC's own leader: none. ETH and SOL: BTC.
2. THE READ: the leader's hourly RSI at the last close before the buy -- oversold too (35 or under), weak but not flushed
   (35-45), fine (over 45). Split the page's crypto trades (pyramid, quarter sale) by it, with his matching and with the
   old everything-follows-BTC, side by side. Nothing about the trade changes.

    python studies/backburner_cryptolead.py
Writes validation/backburner_cryptolead.json
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
import indicators as IND          # noqa: E402
import backburner_dan as D        # noqa: E402

OUT = os.path.join("validation", "backburner_cryptolead.json")
# his follow-up: "You can check for other leaders too shit idk all of them". The big coins in the data, biggest first;
# a coin can only be led by one ABOVE it in this list (BTC by none), every other coin by any of them.
LEADERS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC", "BCH", "SUI", "XLM", "HBAR"]


def _closes(sym, tf):
    d = S.frames_for(sym, "crypto").get(tf)
    if d is None:
        return None
    ix = pd.DatetimeIndex(d.index)
    ix = ix.tz_localize(None) if ix.tz is not None else ix
    return pd.Series(d["Close"].values.astype(float), index=ix)


def leader_of(sym, dailies):
    if sym == "BTC":
        return None, {}
    cands = LEADERS[:LEADERS.index(sym)] if sym in LEADERS else LEADERS
    me = dailies.get(sym)
    if me is None or len(me) < 120:
        return None, {}
    # a leader must have data from at least as early as the coin: BNB here starts 2025-10-22, and on the first run it
    # "led" 58 coins by being measured over a different, recent stretch -- and had no hourly history for their trades
    cands = [L_ for L_ in cands if dailies.get(L_) is not None and dailies[L_].index[0] <= me.index[0]]
    corr = {}
    for L_ in cands:
        ld = dailies.get(L_)
        if ld is None:
            continue
        j = pd.concat([np.log(me).diff(), np.log(ld).diff()], axis=1, join="inner").dropna()
        j = j.iloc[: len(j) // 2]                        # the first half only
        if len(j) >= 60:
            corr[L_] = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
    if not corr:
        return None, {}
    return max(corr, key=corr.get), corr


def _work(args):
    sym, lead_new, lead_rsi = args
    rows = []
    try:
        h = S.frames_for(sym, "crypto").get("1h")
        ix = pd.DatetimeIndex(h.index)
        ix = ix.tz_localize(None) if ix.tz is not None else ix
        for r in PB.trades_for(sym, "crypto"):
            t = ix[r["k"]]
            reads = {}
            for tag, ser in lead_rsi.items():
                if ser is None:
                    reads[tag] = np.nan
                    continue
                i = int(ser.index.searchsorted(t)) - 1          # the leader's last hourly bar that STARTED before the buy
                reads[tag] = float(ser.iloc[i - 1]) if i >= 1 else np.nan   # ... and the close before that one
            rows.append((sym, lead_new, float(t.year), r["pct"], reads.get("new", np.nan), reads.get("btc", np.nan)))
    except Exception:
        pass
    return rows


def main():
    t0 = time.time()
    names = [s_ for s_, k_ in S.universe() if k_ == "crypto" and s_ not in PB.T.SUSPECT]
    dailies = {s_: _closes(s_, "1d") for s_ in names}
    rsi_h = {}
    for L_ in LEADERS:
        c_ = _closes(L_, "1h")
        rsi_h[L_] = pd.Series(IND.rsi_parts(c_.values, D.N_RSI)[0], index=c_.index) if c_ is not None else None
    lead = {}
    for s_ in names:
        lead[s_] = leader_of(s_, dailies)
    count = pd.Series([v[0] for v in lead.values()]).value_counts(dropna=False).to_dict()
    print("\n  EACH COIN'S LEADER (first half of its history, daily returns): %s" % count)
    for s_ in ("ETH", "SOL", "XRP", "ADA", "DOGE", "LINK", "AVAX", "BONK", "JUP", "OP", "ARB", "PEPE", "SHIB", "WIF"):
        if s_ in lead:
            print("    %-6s -> %-4s %s" % (s_, lead[s_][0], {k: round(v, 2) for k, v in lead[s_][1].items()}))
    jobs = []
    for s_ in names:
        ln = lead[s_][0]
        jobs.append((s_, ln, {"new": rsi_h.get(ln) if ln else None, "btc": rsi_h["BTC"] if s_ != "BTC" else None}))
    rows = []
    with cf.ProcessPoolExecutor(max_workers=8) as ex:
        for got in ex.map(_work, jobs, chunksize=2):
            rows += got
    f = pd.DataFrame(rows, columns=["sym", "leader", "yr", "pct", "rsi_new", "rsi_btc"])
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), n=int(len(f)),
                         leaders={s_: v[0] for s_, v in lead.items()}), table={})

    def row(label, g):
        if len(g) < 15:
            print("    %-46s %4d  (too few)" % (label, len(g)))
            return
        yrs = g.groupby("yr").pct.mean()
        d = dict(n=int(len(g)), avg=float(g.pct.mean()), middle=float(g.pct.median()), won=float((g.pct > 0).mean()),
                 p5=float(np.percentile(g.pct, 5)), years_up=int((yrs > 0).sum()), years=int(len(yrs)))
        out["table"][label] = d
        print("    %-46s %4d %+7.2f%% %+7.2f%% %4.0f%% %+6.1f%% %3d/%-3d" % (label, d["n"], d["avg"], d["middle"],
                                                                        100 * d["won"], d["p5"], d["years_up"], d["years"]))

    print("\n  CRYPTO BACKBURNERS BY THE LEADER'S HOURLY RSI AT THE BUY  (%d trades, %.0fs)" % (len(f), time.time() - t0))
    print("    %-46s %4s %8s %8s %5s %7s %7s" % ("", "n", "avg", "middle", "won", "5%", "yrs"))
    row("every crypto trade (the page)", f)
    for col, lab in (("rsi_new", "HIS MATCHING (the big coin each one moves with)"), ("rsi_btc", "THE OLD WAY (everything follows BTC)")):
        print("  " + lab)
        g = f[np.isfinite(f[col])]
        row("  leader oversold too (35 or under)", g[g[col] <= 35])
        row("  leader weak, not flushed (35-45)", g[(g[col] > 35) & (g[col] <= 45)])
        row("  leader fine (over 45)", g[g[col] > 45])
    for L_ in sorted(set(f.leader.dropna()), key=lambda x: -int((f.leader == x).sum()))[:6]:
        g = f[(f.leader == L_) & np.isfinite(f.rsi_new)]
        if len(g):
            print("  coins led by %s:" % L_)
            row("  leader oversold too", g[g.rsi_new <= 35])
            row("  leader not oversold", g[g.rsi_new > 35])
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
