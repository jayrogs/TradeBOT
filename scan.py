"""
scan.py -- multi-timeframe setup scanner across the whole liquid market.

    python scan.py                  full scan, ranked report
    python scan.py --setup slv      only one setup type
    python scan.py --refresh        re-download everything

WHAT THIS IS, AND WHAT IT IS NOT

It is an ATTENTION ALLOCATOR. It reads a few thousand charts every day and hands
back a shortlist. It is not a prediction engine and it does not claim the setups
are independently profitable -- most of them tested at roughly break-even in
this project. The value is coverage: the user has demonstrated real skill at
choosing which market to be in, and can only watch a couple of dozen charts.
This watches all of them and surfaces the ones matching conditions they have
historically bought.

Every setup below is labelled with what the testing actually found, so nothing
here is presented as more reliable than it is.

THE SETUPS

  SLV-PROFILE   *** their most profitable historical setup ***
                A violent pullback inside a parabolic move. Derived by
                reverse-engineering their 73 SLV buy orders: 3-month return
                >= +30%, drawdown from the 52-week high >= 20%, one-month
                return <= -10%, volatility in the top quartile, price still
                above the 200-day average.
                EVIDENCE: this is the profile of their single best trade
                sequence. n=1 as a distinct setup. Treat as a hypothesis.

  PULLBACK      The ordinary trade, also reverse-engineered from their orders:
                above the 200-day, below the 50-day, 10-25% off the 52-week
                high, daily RSI 35-50.
                EVIDENCE: mechanised as system_spec_v2; beat SPY on Sharpe in
                both test windows, not on raw return.

  WEEKLY-OS     Weekly RSI(14) below 40 while above the 200-day.
                EVIDENCE: the strongest single component found. Being oversold
                on the weekly was the entire signal in the spring test -- the
                chart-reading refinements added nothing on top.

  SPRING        Their failed-breakdown pattern: oversold weekly RSI, a lower
                weekly low, then a reclaim.
                EVIDENCE: NO measurable edge over plain weekly oversold
                (+4.33% vs +4.77% at 13 weeks). Included because they asked for
                it and because it may work with their judgment applied. Flagged
                honestly as unverified.

  EMA12-REJECT  Crypto only. A rally into the 12-day EMA while below the
                200-day average.
                EVIDENCE: the one thing verified in their EMA12 claim -- 42%
                hold rate, -1.41% edge over 5 days. This is a SHORT / avoid
                signal, not a buy.
"""

import argparse
import os
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")

ETFS = ["SPY", "QQQ", "IWM", "DIA", "MDY", "EFA", "EEM", "VGK", "EWJ", "EWZ",
        "FXI", "INDA", "GLD", "SLV", "GDX", "GDXJ", "PPLT", "PALL", "CPER",
        "USO", "UNG", "DBC", "DBA", "XLE", "XLF", "XLK", "XLV", "XLI", "XLU",
        "XLP", "XLY", "XLB", "XLRE", "XLC", "XOP", "OIH", "XME", "URA", "LIT",
        "TAN", "ICLN", "ITB", "XHB", "SMH", "SOXX", "IBB", "XBI", "ARKK",
        "TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "VNQ", "REM",
        "UUP", "FXE", "FXY", "FXB", "BITO", "IBIT"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD",
          "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD", "LTC-USD", "BCH-USD",
          "UNI7083-USD", "ATOM-USD", "XLM-USD", "HBAR-USD", "NEAR-USD",
          "APT21794-USD", "ARB11841-USD", "OP-USD"]
FUTURES = ["ES=F", "NQ=F", "YM=F", "RTY=F", "CL=F", "NG=F", "GC=F", "SI=F",
           "HG=F", "PL=F", "ZC=F", "ZS=F", "ZW=F", "KC=F", "SB=F", "CT=F",
           "CC=F", "LE=F", "ZN=F", "ZB=F", "6E=F", "6J=F", "6B=F", "6A=F"]


def universe():
    syms = list(ETFS) + list(CRYPTO) + list(FUTURES)
    try:
        import data as D
        syms += sorted(set(D.sp500_current()["symbol"]))
    except Exception:
        pass
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def download(syms, refresh=False, batch=80):
    if os.path.exists(CACHE) and not refresh:
        store = pd.read_pickle(CACHE)
    else:
        store = {}
    need = [s for s in syms if s not in store]
    if need:
        import yfinance as yf
        print("downloading %d symbols (%d cached)..." % (len(need), len(syms) - len(need)))
        for i in range(0, len(need), batch):
            ch = need[i:i + batch]
            try:
                raw = yf.download(ch, start="2005-01-01", end="2026-08-20",
                                  progress=False, auto_adjust=False,
                                  group_by="ticker", threads=True)
            except Exception:
                continue
            for s in ch:
                try:
                    d = raw[s].dropna(subset=["Close"]) if isinstance(raw.columns, pd.MultiIndex) else raw.dropna()
                    if len(d) > 260:
                        if getattr(d.index, "tz", None) is not None:
                            d.index = d.index.tz_localize(None)
                        store[s] = d[["Open", "High", "Low", "Close", "Volume"]]
                except Exception:
                    pass
            print("  %d/%d" % (min(i + batch, len(need)), len(need)))
            time.sleep(0.3)
        pd.to_pickle(store, CACHE)
    return {s: store[s] for s in syms if s in store}


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def scan_one(sym, d):
    c = d["Close"].values.astype(float)
    h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float)
    if len(c) < 260:
        return None
    px = c[-1]
    ma50 = pd.Series(c).rolling(50).mean().values[-1]
    ma200 = pd.Series(c).rolling(200).mean().values[-1]
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values[-1]
    rsi_d = rsi(c)[-1]
    wk = d["Close"].resample("W-FRI").last().dropna()
    wl = d["Low"].resample("W-FRI").min().dropna()
    if len(wk) < 60:
        return None
    rsi_w = rsi(wk.values.astype(float))[-1]
    hi52 = np.nanmax(c[-252:])
    lo52 = np.nanmin(c[-252:])
    dd = px / hi52 - 1
    r20 = px / c[-21] - 1 if len(c) > 21 else np.nan
    r60 = px / c[-61] - 1 if len(c) > 61 else np.nan
    vol = pd.Series(c).pct_change().rolling(20).std()
    volpct = float(vol.rank(pct=True).iloc[-1])
    adv = float((pd.Series(c) * pd.Series(d["Volume"].values.astype(float))
                 ).rolling(20).mean().iloc[-1]) if "Volume" in d else np.nan

    # weekly failed breakdown, checked over the last 8 weeks
    wc = wk.values.astype(float)
    wlv = wl.values.astype(float)
    rw = rsi(wc)
    spring = False
    piv = [i for i in range(2, len(wc) - 2)
           if wlv[i] == np.nanmin(wlv[i - 2:i + 3])]
    for pi in piv[-8:]:
        lvl = wlv[pi]
        for j in range(pi + 3, len(wc)):
            if wlv[j] < lvl and rw[j] < 40:
                for k in range(j, min(j + 5, len(wc))):
                    if wc[k] > lvl and k >= len(wc) - 8:
                        spring = True
                break

    setups = []
    if px > ma200 and r60 >= 0.30 and dd <= -0.20 and r20 <= -0.10 and volpct >= 0.75:
        setups.append("SLV-PROFILE")
    if px > ma200 and px < ma50 and -0.25 <= dd <= -0.10 and 35 <= rsi_d <= 50:
        setups.append("PULLBACK")
    if px > ma200 and rsi_w < 40:
        setups.append("WEEKLY-OS")
    if spring:
        setups.append("SPRING")
    if sym.endswith("-USD") and px < ma200 and abs(px / ema12 - 1) < 0.02 \
            and c[-6] < ema12:
        setups.append("EMA12-REJECT")

    if not setups:
        return None
    return dict(symbol=sym, price=px, setups=",".join(setups),
                rsi_d=rsi_d, rsi_w=rsi_w, dd52=dd, r20=r20, r60=r60,
                vs200=px / ma200 - 1, vs50=px / ma50 - 1, volpct=volpct,
                adv=adv, n_setups=len(setups))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--setup", default=None)
    ap.add_argument("--min-adv", type=float, default=5e6)
    args = ap.parse_args()

    syms = universe()
    print("universe: %d symbols" % len(syms))
    data = download(syms, args.refresh)
    print("scanning %d with usable history...\n" % len(data))

    rows = [r for r in (scan_one(s, d) for s, d in data.items()) if r]
    R = pd.DataFrame(rows)
    if R.empty:
        print("no setups today")
        return
    R = R[(R.adv.isna()) | (R.adv >= args.min_adv)]
    if args.setup:
        R = R[R.setups.str.contains(args.setup.upper())]
    R.to_csv("scan_results.csv", index=False)

    order = ["SLV-PROFILE", "PULLBACK", "WEEKLY-OS", "SPRING", "EMA12-REJECT"]
    note = {"SLV-PROFILE": "their best historical setup -- hypothesis, n=1",
            "PULLBACK": "mechanised & tested: beats SPY on Sharpe, not return",
            "WEEKLY-OS": "strongest verified component",
            "SPRING": "NO measured edge over plain weekly oversold",
            "EMA12-REJECT": "crypto only -- AVOID/SHORT signal, 42% hold rate"}

    print("=" * 92)
    print("  SCAN  %s   --  %d symbols flagged" % (pd.Timestamp.today().date(), len(R)))
    print("=" * 92)
    for s in order:
        g = R[R.setups.str.contains(s)]
        if g.empty:
            continue
        print("\n  %s   (%d)   %s" % (s, len(g), note[s]))
        print("  %-10s %10s %7s %7s %9s %9s %9s %8s"
              % ("symbol", "price", "rsi_d", "rsi_w", "off high", "1m ret",
                 "3m ret", "vs 200d"))
        g = g.sort_values("rsi_w") if s == "WEEKLY-OS" else g.sort_values("r60", ascending=False)
        for _, r in g.head(25).iterrows():
            print("  %-10s %10.2f %7.1f %7.1f %+8.1f%% %+8.1f%% %+8.1f%% %+7.1f%%"
                  % (r.symbol, r.price, r.rsi_d, r.rsi_w, 100 * r.dd52,
                     100 * r.r20, 100 * r.r60, 100 * r.vs200))
        if len(g) > 25:
            print("  ... %d more in scan_results.csv" % (len(g) - 25))

    multi = R[R.n_setups >= 2]
    if len(multi):
        print("\n" + "=" * 92)
        print("  MULTIPLE SETUPS AT ONCE  (%d)" % len(multi))
        print("=" * 92)
        for _, r in multi.sort_values("n_setups", ascending=False).head(20).iterrows():
            print("  %-10s %10.2f  %s" % (r.symbol, r.price, r.setups))
    print("\n  full results: scan_results.csv")


if __name__ == "__main__":
    main()
