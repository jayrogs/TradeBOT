"""
chartweb.py -- render a chart of what is firing, for the scanner to link to.

Two ways to look at a name the scanner surfaced:

  our chart      everything the detectors see -- trend shading, pivot labels,
                 the invalidation level, the EMA rider and its dips. TradingView
                 cannot show this unless the Pine script is loaded, so this is
                 the only place the actual reasoning is visible
  TradingView    the real chart, with the right symbol and interval already
                 selected. Uses the account you already pay for

The symbol mapping matters and is easy to get subtly wrong: a US equity resolves
bare, but crypto needs the exchange we actually pulled the candles from or you
are looking at a different book than the one that produced the signal.
"""

import io
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import panel as P
import rider

warnings.filterwarnings("ignore")

TV_INTERVAL = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60",
               "4h": "240", "12h": "720", "1d": "D", "1w": "W", "1mo": "M"}


def tv_symbol(sym, kind):
    """The symbol string TradingView needs, per asset class."""
    if kind == "crypto":
        return "COINBASE:%sUSD" % sym
    if kind == "forex":
        return "FX:%s" % sym.replace("=X", "")
    if kind == "future":
        root = sym.replace("=F", "")
        cme = {"ES": "CME_MINI", "NQ": "CME_MINI", "RTY": "CME_MINI",
               "MES": "CME_MINI", "MNQ": "CME_MINI", "M2K": "CME_MINI",
               "YM": "CBOT_MINI", "MYM": "CBOT_MINI",
               "GC": "COMEX", "SI": "COMEX", "HG": "COMEX", "MGC": "COMEX",
               "SIL": "COMEX", "PL": "NYMEX", "PA": "NYMEX",
               "CL": "NYMEX", "NG": "NYMEX", "RB": "NYMEX", "HO": "NYMEX",
               "BZ": "NYMEX", "QM": "NYMEX", "QG": "NYMEX",
               "ZC": "CBOT", "ZS": "CBOT", "ZW": "CBOT", "ZM": "CBOT",
               "ZL": "CBOT", "ZO": "CBOT", "ZR": "CBOT", "KE": "CBOT",
               "ZB": "CBOT", "ZN": "CBOT", "ZF": "CBOT", "ZT": "CBOT",
               "UB": "CBOT", "KC": "ICEUS", "SB": "ICEUS", "CC": "ICEUS",
               "CT": "ICEUS", "OJ": "ICEUS", "LE": "CME", "GF": "CME",
               "HE": "CME", "DC": "CME", "NKD": "CME",
               "6E": "CME", "6J": "CME", "6B": "CME", "6A": "CME",
               "6C": "CME", "6S": "CME", "6N": "CME", "6M": "CME",
               "6L": "CME", "BTC": "CME", "ETH": "CME"}
        return "%s:%s1!" % (cme.get(root, "CME"), root)
    return sym                       # equities and ETFs resolve bare


def tv_url(sym, kind, tf):
    return "https://www.tradingview.com/chart/?symbol=%s&interval=%s" % (
        tv_symbol(sym, kind), TV_INTERVAL.get(tf, "5"))



# ---------------------------------------------------------------- names
# Shown ONLY in the chart preview, never in the main list -- full names there
# would crowd out the thing you are actually scanning for.

FUT_NAMES = {
    "ES": "E-mini S&P 500", "MES": "Micro E-mini S&P 500",
    "NQ": "E-mini Nasdaq-100", "MNQ": "Micro E-mini Nasdaq-100",
    "YM": "E-mini Dow", "MYM": "Micro E-mini Dow",
    "RTY": "E-mini Russell 2000", "M2K": "Micro E-mini Russell 2000",
    "NKD": "Nikkei 225", "ZB": "30-Year T-Bond", "UB": "Ultra T-Bond",
    "ZN": "10-Year T-Note", "ZF": "5-Year T-Note", "ZT": "2-Year T-Note",
    "6E": "Euro FX", "6J": "Japanese Yen", "6B": "British Pound",
    "6A": "Australian Dollar", "6C": "Canadian Dollar", "6S": "Swiss Franc",
    "6N": "New Zealand Dollar", "6M": "Mexican Peso", "6L": "Brazilian Real",
    "BTC": "Bitcoin futures", "ETH": "Ether futures",
    "CL": "Crude Oil (WTI)", "QM": "E-mini Crude Oil", "BZ": "Brent Crude",
    "NG": "Natural Gas", "QG": "E-mini Natural Gas", "RB": "RBOB Gasoline",
    "HO": "Heating Oil", "GC": "Gold", "MGC": "Micro Gold", "SI": "Silver",
    "SIL": "Micro Silver", "HG": "Copper", "PL": "Platinum",
    "PA": "Palladium", "ALI": "Aluminum", "ZC": "Corn", "ZS": "Soybeans",
    "ZM": "Soybean Meal", "ZL": "Soybean Oil", "ZW": "Wheat (Chicago)",
    "KE": "Wheat (Kansas City)", "ZO": "Oats", "ZR": "Rough Rice",
    "KC": "Coffee", "SB": "Sugar No. 11", "CC": "Cocoa", "CT": "Cotton",
    "OJ": "Orange Juice", "LE": "Live Cattle", "GF": "Feeder Cattle",
    "HE": "Lean Hogs", "DC": "Class III Milk",
}

CCY = {"USD": "US Dollar", "EUR": "Euro", "JPY": "Japanese Yen",
       "GBP": "British Pound", "AUD": "Australian Dollar",
       "CAD": "Canadian Dollar", "CHF": "Swiss Franc",
       "NZD": "New Zealand Dollar", "MXN": "Mexican Peso",
       "ZAR": "South African Rand", "TRY": "Turkish Lira",
       "SEK": "Swedish Krona", "NOK": "Norwegian Krone",
       "SGD": "Singapore Dollar", "HKD": "Hong Kong Dollar",
       "CNY": "Chinese Yuan", "INR": "Indian Rupee"}

_NAME_CACHE = {}
_NAME_FILE = os.path.join("cache", "names.csv")


def _equity_names():
    """Symbol -> company name, from the Nasdaq daily symbol files. Cached to
    disk because it is two HTTP calls for ~13,000 rows and never changes
    intraday."""
    if "equity" in _NAME_CACHE:
        return _NAME_CACHE["equity"]
    out = {}
    if os.path.exists(_NAME_FILE):
        try:
            d = pd.read_csv(_NAME_FILE)
            out = dict(zip(d.symbol.astype(str), d.name.astype(str)))
        except Exception:
            out = {}
    if not out:
        import io as _io
        import requests
        for url, col in [
                ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
                 "Symbol"),
                ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
                 "ACT Symbol")]:
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                                 timeout=40)
                d = pd.read_csv(_io.StringIO(r.text), sep="|")
                d = d[~d[col].astype(str).str.startswith("File Creation")]
                for sym, nm in zip(d[col].astype(str),
                                   d["Security Name"].astype(str)):
                    out[sym] = nm
            except Exception:
                pass
        if out:
            os.makedirs("cache", exist_ok=True)
            pd.DataFrame({"symbol": list(out), "name": list(out.values())}
                         ).to_csv(_NAME_FILE, index=False)
    _NAME_CACHE["equity"] = out
    return out


def _crypto_names():
    if "crypto" in _NAME_CACHE:
        return _NAME_CACHE["crypto"]
    out = {}
    try:
        import requests
        for page in (1, 2):
            r = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                             params={"vs_currency": "usd",
                                     "order": "volume_desc",
                                     "per_page": 250, "page": page},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            for x in r.json():
                out[str(x.get("symbol", "")).upper()] = x.get("name") or ""
    except Exception:
        pass
    _NAME_CACHE["crypto"] = out
    return out


def display_name(sym, kind):
    """A human name for the preview header. Never returns None."""
    try:
        if kind == "future":
            root = sym.replace("=F", "")
            return FUT_NAMES.get(root, root + " futures")
        if kind == "forex":
            p = sym.replace("=X", "")
            if len(p) == 6:
                a, b = CCY.get(p[:3], p[:3]), CCY.get(p[3:], p[3:])
                return "%s / %s" % (a, b)
            return p
        if kind == "crypto":
            return _crypto_names().get(sym.upper(), "")
        nm = _equity_names().get(sym.upper(), "")
        # the Nasdaq files pad names with share-class boilerplate
        for junk in (" - Common Stock", " Common Stock", " - Class A Common Stock",
                     " (The)"):
            nm = nm.replace(junk, "")
        return nm.strip()
    except Exception:
        return ""


def fetch(sym, kind, tf, bars=260):
    """Bars for any timeframe, deriving the ones no source serves.

    Only 5m / 15m / 1h / 1d are downloadable. 4h and 12h are resampled from the
    1h, weekly and monthly from the daily -- exactly as scanner.py does it, so
    the chart shows the same bars the scan judged. Before this, asking the
    preview for 12h or weekly silently returned nothing.
    """
    import scanner as SC
    base = SC.BASE.get(tf)
    rule = None
    if base is None and tf in SC.DERIVE:
        src, rule = SC.DERIVE[tf]
        base = SC.BASE[src]
    if base is None:
        base, rule = "1d", None

    if kind == "crypto":
        import crypto
        need = {"5m": 700, "15m": 700, "1h": 2600, "1d": 2600}.get(base, 700)
        raw = crypto.candles(sym, base, need)
    else:
        import yfinance as yf
        # Yahoo hard-caps 5m and 15m at 60 days. Asking "2mo" for 15m is
        # 61 days and the request is REFUSED outright, so the whole
        # timeframe came back empty rather than short.
        period = {"5m": "1mo", "15m": "59d", "1h": "2y",
                  "1d": "20y"}.get(base)
        raw = yf.download(sym, interval=base, period=period, progress=False,
                          auto_adjust=False, prepost=True)
        if raw is None or len(raw) == 0:
            return None
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        if getattr(raw.index, "tz", None) is not None:
            raw.index = raw.index.tz_localize(None)
        raw = raw.dropna()

    if raw is None or len(raw) < 30:
        return None
    out = SC.resample(raw, rule) if rule else raw
    if out is None or len(out) < 30:
        return None
    return out.tail(bars)


def png(sym, kind, tf, bars=260):
    """Everything the detectors see, on one image."""
    df = fetch(sym, kind, tf, bars)
    if df is None or len(df) < 40:
        return None
    r = rider.read(df)
    st, hl, lh = P.display_state(df)
    import chart as CH
    marks = CH.pivot_labels(df)

    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    e = r["ema"]
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(13.5, 6.0), dpi=100)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    tcol = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d"}
    i = 0
    while i < len(df):
        j = i
        while j + 1 < len(df) and st[j + 1] == st[i]:
            j += 1
        col = tcol.get(st[i])
        if col:
            ax.axvspan(i - 0.5, j + 0.5, color=col, lw=0, zorder=0)
        i = j + 1

    for k in range(len(df)):
        col = "#3ddc97" if c[k] >= o[k] else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=0.8, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col, lw=3.0,
                zorder=2, solid_capstyle="butt")

    ax.plot(x, e, color="#6b5636", lw=1.2, zorder=3)
    live = r["armed"]
    i = 0
    while i < len(df):
        if not live[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(df) and live[j + 1]:
            j += 1
        sl = slice(i, j + 1)
        ax.plot(x[sl], e[sl], color="#ffb84d", lw=3.0, zorder=4,
                solid_capstyle="round")
        ax.fill_between(x[sl], e[sl], c[sl], where=c[sl] >= e[sl],
                        color="#ffb84d", alpha=.12, lw=0, zorder=1)
        i = j + 1

    tlo, thi = P.tight_levels(df)
    tight = np.where(st == "UP", tlo, np.where(st == "DOWN", thi, np.nan))
    if np.any(np.isfinite(tight)):
        ax.step(x, tight, where="post", color="#5aa9ff", lw=1.4, zorder=3)

    w = np.where(r["wick_hold"])[0]
    if len(w):
        ax.scatter(w, lo[w], marker="^", s=34, color="#5aa9ff", zorder=5)
    p = np.where(r["pullback"] & r["armed"])[0]
    if len(p):
        ax.scatter(p, c[p], marker="o", s=44, facecolors="none",
                   edgecolors="#3ddc97", linewidths=1.6, zorder=6)

    lab_col = {"HH": "#3ddc97", "HL": "#3ddc97", "LH": "#ff5c72",
               "LL": "#ff5c72", "EH": "#8b93a1", "EL": "#8b93a1"}
    for pos, price, tag, kd in marks:
        if pos >= len(df):
            continue
        up = kd == "high"
        ax.annotate(tag, (pos, price), fontsize=8, weight="bold",
                    color=lab_col.get(tag, "#8b93a1"), zorder=7, ha="center",
                    va="bottom" if up else "top",
                    xytext=(0, 6 if up else -6), textcoords="offset points")

    ax.set_xlim(-1, len(df))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=0.5)
    step = max(len(df) // 8, 1)
    ax.set_xticks(x[::step])
    fmt = "%Y-%m-%d" if tf in ("1d", "1w", "1mo") else "%m-%d %H:%M"
    ax.set_xticklabels([d.strftime(fmt) for d in df.index[::step]], fontsize=7.5)
    ax.set_title("%s  %s   %s%s" % (sym, tf, st[-1],
                                    "   RIDER ARMED" if live[-1] else ""),
                 color="#e7ebf0", fontsize=11, loc="left", pad=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
