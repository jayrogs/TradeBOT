"""backburner_young.py (review 2026-09-26, CLAUDE.md #55). The page's account (5 buckets, whole bucket at 30, later buys on top), with and without the trades the live page
could never take (name too young for trades_for's own 500 hourly / 120 daily / 60 weekly bar minimum AT THE TIME)."""
import sys, os
sys.path.insert(0, r"C:\Users\jayru\Desktop\AI Trading Project"); sys.path.insert(0, r"C:\Users\jayru\Desktop\AI Trading Project\studies")
os.chdir(r"C:\Users\jayru\Desktop\AI Trading Project")
import pandas as pd, numpy as np, concurrent.futures as cf
import backburner_study as S, pics_backburner_tcg as PB, eq_freeride2 as FR2, panel as P
import backburner_sizing as SZ
from backburner_account import START, _naive, stats

def work(a):
    sym, kind = a
    try:
        fr = {k: v for k, v in S.frames_for(sym, kind).items() if k in ("1h", "1d", "1w")}
        if kind in ("stock", "etf"): fr = FR2.regular_hours(fr)
        h1, d = fr["1h"], fr["1d"]; w = fr["1w"]
        hix = _naive(h1.index); h = h1["High"].values.astype(float); atr = P._atr(h1)
        closes = pd.Series(d["Close"].values.astype(float), index=_naive(d.index).normalize())
        closes = closes[~closes.index.duplicated(keep="last")]
        page = dict(PB.STOP, **(PB.CRYPTO_BUYS if kind == "crypto" else {}))
        tr = SZ._trades(sym, kind, page, h, hix, atr)
        dix = _naive(d.index); wix = _naive(w.index)
        for t in tr:
            k = int(hix.searchsorted(t["t_in"]))
            t["young"] = bool(k < 500 or dix.searchsorted(t["t_in"].normalize()) < 120 or wix.searchsorted(t["t_in"]) < 60)
        return tr, closes, sym, kind
    except Exception:
        return [], None, sym, kind

if __name__ == "__main__":
    names = [(s, k) for s, k in S.universe() if (k in ("stock", "etf", "crypto") or (k == "futures" and s in PB.COMMODITY_FUTURES)) and s not in PB.T.SUSPECT]
    trades, closes = [], {}
    with cf.ProcessPoolExecutor(8) as ex:
        for tr, c, sym, kind in ex.map(work, names, chunksize=2):
            trades += tr
            if c is not None: closes[(kind, sym)] = c
    end = max(t["t_out"] for t in trades).normalize()
    days = pd.date_range(START, end, freq="D")
    for lab, tr in (("as in the study (all)", trades), ("only trades live could take", [t for t in trades if not t["young"]]), ("new listings out, futures kept", [t for t in trades if not (t["young"] and t["kind"] != "futures")])):
        res = [SZ.account(tr, closes, days, s, slots=5, on_top=True) for s in range(20)]
        st = [stats(r[0], days) for r in res]
        ann = np.array([x["a_year"] for x in st]); dip = np.array([x["dip"] for x in st])
        print("%-30s n=%d  a year %+.1f%% (10-90 %+.1f / %+.1f)  worst dip %+.1f%%" % (lab, len(tr), 100*np.median(ann), 100*np.percentile(ann,10), 100*np.percentile(ann,90), 100*np.median(dip)))
