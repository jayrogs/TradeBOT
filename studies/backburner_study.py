"""backburner_study.py -- when do backburners work? Pre-registered, one shot.

Owner's ask (2026-09-04): "scan as many tickers as possible in the last 4
years, inc crypto, and see what conditions are there when backburners work.
backburners are on any timeframe ... from the 5m to the 1 week. just check
everything. including confluence of backburners within other backburners."

THE METHOD, owner 2026-09-04: "backburners mean you scale into a name going
oversold as long as it keeps going oversold, and you dont sell until theres
a bounce, or shit goes really bad."

CAMPAIGN   on a timeframe, the first RSI(14, Wilder) close at or under 30
           opens a campaign: buy one unit at the NEXT bar's open (signal and
           price never from the same bar). Every further close at or under
           30 buys another unit (cap 10). Nothing is sold until:
             bounce   RSI closes back above 50
             bad      close more than 3 ATR(14) under the average cost -> sell all
             cap      20 days' worth of bars with neither -> sell all (rare)
EXITS      three ways to handle the bounce, all measured on every campaign:
             sell all       everything out at the next open (the first pass)
             ride / 12 EMA  the OWNER'S exit (2026-09-04): at the bounce sell
                            just enough that a stop at the backburner LOW
                            leaves the whole trade breakeven, then hold the
                            rest until a bar CLOSES under the 12 EMA (by more
                            than EMA_TOL_ATR of the ATR) or the low breaks
             ride / trend   same partial, the rest held until a bar CLOSES
                            under the last higher low (the most recent
                            confirmed low pivot above the backburner low) --
                            "sell if the uptrend breaks" -- or the low breaks
OUTCOME    return on average cost, net of 0.2% round-trip; units bought; bars
           held; how it ended; worst point vs average cost along the way.
           Also the single-buy version (one unit at the first print, sell
           all at the bounce) and the frame's drift over the same holding
           time as the market baseline.
CONDITIONS all known at the first print's close:
           own trend; the next timeframe up's trend; the next timeframe up
           oversold right now / printed <=30 in its last 3 bars (confluence);
           two timeframes up the same; RSI depth; move over the prior day;
           distance from the 12 EMA; relative volume; asset class; first vs
           second half of the window.
VERDICT    a condition counts only if its edge over drift is positive in BOTH
           halves of the 4 years and in both asset classes where both have
           data.

    python studies/backburner_study.py            # writes validation/backburner_study.json (+ events csv)
"""

import concurrent.futures as cf
import glob
import json
import multiprocessing as mp
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import indicators as IND          # noqa: E402
import rider                      # noqa: E402
import rider_lab as RL            # noqa: E402  the frozen 12 EMA exit
import structure as ST            # noqa: E402

warnings.filterwarnings("ignore")

OS = 30
BOUNCE = 50               # RSI back above this = the bounce, sell all
STOP_ATR = 3.0            # "shit goes really bad": close this far under avg cost
STOP_MODE = "run"         # REFINED 2026-09-05 (risk test): half the 3-day run-up, floor 3 ATR
                          # "atr" (STOP_ATR under avg cost) | "low" (under the first print's low)
                          # | "run" (STOP_FRAC of the prior 3-day run-up, floor 1 ATR) | "none"
STOP_FRAC = 0.5           # owner 2026-09-05: "the higher it goes up, the harder it falls"
MAX_UNITS = 10
EMA_TOL_ATR = 0.25      # a close this far under the 12 EMA (in ATR) ends the ride
CAP_DAYS = 20
COST = 0.002              # legacy flat cost (the first passes)
# REFINED: realistic round-trip cost by class (stocks are near-free, Coinbase/Kraken are not)
CLASS_COST = {"stock": 0.0005, "etf": 0.0005, "futures": 0.0005, "forex": 0.0003,
              "crypto": 0.002, "cfd": 0.0005}   # crypto: Kraken volume tier (owner 2026-09-05)
YEARS = 4
CHAIN = ["5m", "15m", "1h", "4h", "12h", "1d", "1w"]
DUR = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "12h": "12h",
       "1d": "1D", "1w": "7D"}
BARS_DAY = {"5m": 288, "15m": 96, "1h": 24, "4h": 6, "12h": 2, "1d": 5, "1w": 4}
RULE = {"4h": "4h", "12h": "12h", "1d": "1D", "1w": "W-FRI"}
OUT_JSON = os.path.join("validation", "backburner_study.json")
OUT_CSV = os.path.join("validation", "backburner_events.csv.gz")


# ------------------------------------------------------------------ data

def resample(df, rule):
    o = df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min",
                               "Close": "last", "Volume": "sum"}).dropna()
    return o if len(o) >= 60 else None


def load_csv(p):
    try:
        d = pd.read_csv(p, index_col=0, parse_dates=True)
        d = d[~d.index.duplicated()].sort_index()
        return d if len(d) >= 60 else None
    except Exception:
        return None


_SRC = {}


def stock_all_hours():
    """True once the stock intraday files carry real pre/after-hours bars (Polygon)."""
    if "v" not in _SRC:
        try:
            import json as _j
            _SRC["v"] = bool(_j.load(open(os.path.join("history", "stocks", "SOURCE.json"))).get("all_hours"))
        except Exception:
            _SRC["v"] = False
    return _SRC["v"]


def session_only(d):
    """Drop pre/after-hours bars from a stock intraday frame."""
    if d is None:
        return None
    m = d.index.minute + 60 * d.index.hour
    # bars are stamped at their start, New York time. The hourly 09:00 bar holds
    # the 09:30 open, so it stays; on 5m/15m the 09:00-09:25 bars are pre-market.
    step = pd.Series(d.index).diff().dt.total_seconds().median() if len(d) > 2 else 0
    first = 9 * 60 if step >= 3600 else 9 * 60 + 30
    d = d[(m >= first) & (m < 16 * 60)]
    return d if len(d) >= 60 else None


def frames_for(sym, kind):
    """{tf: df} for one name from whatever history exists."""
    out = {}
    if kind == "crypto":
        h1 = load_csv(os.path.join("history", "%s_1h.csv.gz" % sym))
        out["15m"] = load_csv(os.path.join("history", "crypto_15m", "%s_15m.csv.gz" % sym))
        out["5m"] = load_csv(os.path.join("history", "crypto_5m", "%s_5m.csv.gz" % sym))
        d1 = None
    elif kind in ("futures", "forex", "cfd"):
        # futures: Databento minute bars (5m/15m/1h, 4y) where pulled, else
        # Yahoo hourly (2y); daily from Yahoo (10y). forex: Dukascopy
        # 5m/15m/1h (4y), daily from Yahoo. cfd: Dukascopy index/commodity
        # CFDs standing in for the futures not bought.
        folder = "futures_cfd" if kind == "cfd" else kind
        h1 = load_csv(os.path.join("history", folder, "%s_1h.csv.gz" % sym))
        out["15m"] = load_csv(os.path.join("history", folder, "%s_15m.csv.gz" % sym))
        out["5m"] = load_csv(os.path.join("history", folder, "%s_5m.csv.gz" % sym))
        d1 = load_csv(os.path.join("history", folder, "%s_1d.csv.gz" % sym))
    else:                                   # stock / etf
        # regular session only (bars starting 09:00-15:59 New York). The files
        # carry a sprinkling of pre/after-hours bars (08:xx, 16:xx): thin, gappy,
        # and the after-hours earnings bar is how CSCO 1h showed a -11% "trade"
        # on 2023-11-15 (owner: "we dont carry little 5m trades overnight").
        # Owner 2026-09-07: "we need to trade all hours". Once the files come from
        # Polygon (history/stocks/SOURCE.json says all_hours), every bar stays.
        trim = (lambda d: d) if stock_all_hours() else session_only
        h1 = trim(load_csv(os.path.join("history", "stocks", "%s_1h.csv.gz" % sym)))
        out["15m"] = trim(load_csv(os.path.join("history", "stocks", "%s_15m.csv.gz" % sym)))
        out["5m"] = trim(load_csv(os.path.join("history", "stocks", "%s_5m.csv.gz" % sym)))
        d1 = load_csv(os.path.join("history", "stocks", "%s_1d.csv.gz" % sym))
    out["1h"] = h1
    if h1 is not None:
        out["4h"] = resample(h1, RULE["4h"])
        out["12h"] = resample(h1, RULE["12h"])
        if d1 is None:
            d1 = resample(h1, RULE["1d"])
    out["1d"] = d1
    out["1w"] = resample(d1, RULE["1w"]) if d1 is not None else None
    return {k: v for k, v in out.items() if v is not None}


def universe():
    """(symbol, class): crypto, stock, etf, futures, forex -- whatever has
    hourly history on disk."""
    names = []
    for f in glob.glob(os.path.join("history", "*_1h.csv.gz")):
        names.append((os.path.basename(f).split("_")[0], "crypto"))
    etf = set()
    try:
        k = pd.read_csv(os.path.join("cache", "tier1.csv"))
        etf = set(k[k.kind == "etf"].symbol.astype(str))
    except Exception:
        pass
    for f in glob.glob(os.path.join("history", "stocks", "*_1h.csv.gz")):
        s = os.path.basename(f).split("_")[0]
        names.append((s, "etf" if s in etf else "stock"))
    for kind, folder in (("futures", "futures"), ("forex", "forex"), ("cfd", "futures_cfd")):
        for f in glob.glob(os.path.join("history", folder, "*_1h.csv.gz")):
            names.append((os.path.basename(f).rsplit("_", 1)[0], kind))
    return names


# ------------------------------------------------------------------ per frame

def atr(h, l, c, n=14):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().values


def ema_ride_exit(c, o, ema, a14, arm, n):
    """The owner's ride, in plain terms: once price is back above the 12 EMA,
    hold until a bar CLOSES under the 12 EMA by more than EMA_TOL_ATR of the
    ATR (so a wick or a hair under does not count). Sell at the next open.
    (The old rider rule switched this off once the trade was up 1% and left
    only a "3% under the EMA" stop, which never fires in a slow bleed because
    the EMA falls with price -- HBAR 1h 2026-08-06 rode all the way back to the
    low. That is not what "ride the 12 EMA" means.)"""
    if arm is None:
        return None
    for k in range(arm + 1, n - 1):
        buf = EMA_TOL_ATR * a14[k] if np.isfinite(a14[k]) else 0.0
        if c[k] < ema[k] - buf:
            return (k, o[k + 1], "closed under 12 EMA")
    return None


def low_pivots(df):
    """Confirmed low pivots as (confirm_bar, form_bar, price), in confirm order,
    plus the confirm bars as a list for bisecting."""
    piv = [(ci, j, p) for ci, j, p, kind, lab in ST.pivots(df) if kind == "low"]
    return piv, [ci for ci, _, _ in piv]


def hl_break_exit(c, o, piv, cis, i0, jb, camp_low, n):
    """The owner's other exit: sell when a bar CLOSES under the last higher
    low. The level is the most recent confirmed low pivot that formed after
    the first buy and sits above the backburner low (so it is a higher low
    relative to the dip). Until one exists the backburner low is the level,
    and that case is already covered by the low-break exit."""
    import bisect
    p = bisect.bisect_right(cis, i0)
    level = None
    for k in range(jb + 1, n - 1):
        while p < len(piv) and piv[p][0] <= k:
            ci, j, price = piv[p]; p += 1
            if j >= i0 and price > camp_low:
                level = price
        if level is not None and c[k] < level:
            return (k, o[k + 1] if k + 1 < len(o) else c[k], "closed under last higher low")
    return None


def higher_view(lower, lower_tf, higher, higher_tf):
    """Arrays on the lower frame: higher trend, higher RSI now, higher
    printed <=30 within its last 3 closed bars, and the higher RSI's peak
    over its last 20 closed bars ("was it running hot"). All from closed
    higher bars."""
    n = len(lower)
    trend = np.array(["NA"] * n, dtype=object)
    rsi_h = np.full(n, np.nan)
    recent = np.zeros(n, bool)
    peak = np.full(n, np.nan)
    if higher is None or len(higher) < 60:
        return trend, rsi_h, recent, peak
    hs = ST.states(higher, causal=True)
    hr = IND.rsi_parts(higher["Close"].values.astype(float))[0]
    h_os = hr <= OS
    h_recent = np.zeros(len(hr), bool)
    for k in range(len(hr)):
        h_recent[k] = h_os[max(0, k - 2):k + 1].any()
    h_peak = pd.Series(hr).rolling(20, min_periods=5).max().values
    lc = lower.index.values + pd.Timedelta(DUR[lower_tf]).to_timedelta64()
    hc = higher.index.values + pd.Timedelta(DUR[higher_tf]).to_timedelta64()
    pos = np.searchsorted(hc, lc, side="right") - 1
    ok = pos >= 0
    trend[ok] = hs[pos[ok]]
    rsi_h[ok] = hr[pos[ok]]
    recent[ok] = h_recent[pos[ok]]
    peak[ok] = h_peak[pos[ok]]
    return trend, rsi_h, recent, peak


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    cost = CLASS_COST.get(kind, COST)
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)
    n = len(c)
    r = IND.rsi_parts(c)[0]
    own = ST.states(df, causal=True)
    lpiv, lcis = low_pivots(df)
    ema = rider.ema(c)
    bpd = BARS_DAY[tf]
    med = pd.Series(v).rolling(bpd * 5, min_periods=bpd).median().values
    relvol = np.divide(v, med, out=np.full(n, np.nan), where=med > 0)
    up1 = frames.get(CHAIN[CHAIN.index(tf) + 1]) if CHAIN.index(tf) + 1 < len(CHAIN) else None
    up2 = frames.get(CHAIN[CHAIN.index(tf) + 2]) if CHAIN.index(tf) + 2 < len(CHAIN) else None
    t1, r1, rec1, pk1 = higher_view(df, tf, up1, CHAIN[CHAIN.index(tf) + 1]) if up1 is not None else (None, None, None, None)
    t2, r2, rec2, pk2 = higher_view(df, tf, up2, CHAIN[CHAIN.index(tf) + 2]) if up2 is not None else (None, None, None, None)
    own_peak = pd.Series(r).rolling(20 * bpd if tf in ("5m", "15m") else 20,
                                    min_periods=5).max().values
    last_start = None

    a14 = atr(h, l, c)
    # what rider_lab.run_exit needs, built directly (prep() runs the whole
    # v1 trend machine, which is minutes on a 400k-bar 5m frame)
    v = dict(c=c, lo=l, hi=h, e=ema, hold=(c >= ema), o=o,
             atr=np.where(np.isfinite(a14), a14, np.inf), n=n)
    in_win = df.index >= start
    # market drift baseline: the frame's mean per-bar log return in the window
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[in_win])) if in_win.any() else 0.0
    cap = CAP_DAYS * bpd

    rows = []
    mid = start + (df.index[-1] - start) / 2
    i = 1
    while i < n - 2:
        if not (r[i] <= OS and r[i - 1] > OS):
            i += 1
            continue
        # ---- a campaign opens at bar i
        k3 = min(i, 3 * bpd)
        run_up = max(0.0, c[i] / c[i - k3] - 1.0) if k3 > 0 else 0.0
        fills = [o[i + 1]]
        first_fill = o[i + 1]
        worst = 0.0
        ended, j = None, i + 1
        while j < n - 1:
            avg = float(np.mean(fills))
            worst = min(worst, l[j] / avg - 1)
            if r[j] > BOUNCE:
                ended, exit_px = "bounce", o[j + 1]
                break
            if STOP_MODE == "low":
                bad_now = c[j] < l[i]                # the backburner candle's low broke
            elif STOP_MODE == "run":
                dist = max(STOP_FRAC * run_up * avg, STOP_ATR * a14[j])   # floor = the old 3-ATR stop
                bad_now = c[j] < avg - dist
            elif STOP_MODE == "none":
                bad_now = False
            else:
                bad_now = c[j] < avg - STOP_ATR * a14[j]
            if bad_now:
                ended, exit_px = "bad", o[j + 1]
                break
            if j - i >= cap:
                ended, exit_px = "cap", o[j + 1]
                break
            if r[j] <= OS and len(fills) < MAX_UNITS:
                fills.append(o[j + 1])
            j += 1
        if ended is None:                      # still open at the end of data
            i = j + 1
            continue
        avg = float(np.mean(fills))
        # ---- the owner's exit: breakeven partial at the bounce, ride the rest
        part, ride = 0.0, {}
        if ended == "bounce":
            low = float(l[i + 1:j + 1].min())          # the backburner low
            P = o[j + 1]
            if P > avg and P > low:
                part = min(1.0, max(0.0, (avg - low) / (P - low)))
            # exits for the remainder, each = (bar, price, reason) or None
            lowbreak = next(((k, o[k + 1], "low broke") for k in range(j + 1, n - 1)
                             if c[k] < low), None)
            # the 12 EMA ride starts once price has reclaimed the 12 EMA
            # (a bounce from oversold is under it; the rider is a rule for
            # riding the line, not for the climb back to it)
            arm = next((k for k in range(j + 1, n - 1) if c[k] >= ema[k]), None)
            rx = ema_ride_exit(c, o, ema, a14, arm, n)
            tx = hl_break_exit(c, o, lpiv, lcis, i + 1, j, low, n)
            capx = (j + 1 + cap, o[min(n - 1, j + 1 + cap)], "cap") if j + 1 + cap < n - 1 else None
            # STANDARD ride (2026-09-06, owner's call): hold until the last higher
            # low breaks. The 12 EMA close exit is kept as the alternate.
            for name, cand in (("ride", (lowbreak, tx, capx)), ("ema", (lowbreak, rx, capx))):
                cs = [x for x in cand if x is not None]
                if not cs:
                    ride = None
                    break
                k, px, why = min(cs, key=lambda x: x[0])
                ride[name] = (float((part * P + (1 - part) * px) / avg - 1 - cost),
                              why, int(k + 1 - (i + 1)))
            if ride is None:                   # ran off the end of the data
                i = j + 1
                continue
        else:
            r_all = float(exit_px / avg - 1 - cost)
            ride = {"ride": (r_all, ended, j + 1 - (i + 1)),
                    "ema": (r_all, ended, j + 1 - (i + 1))}
        gap = (i - last_start) if last_start is not None else None
        last_start = i
        if in_win[i]:
            held = j + 1 - (i + 1)
            k = min(i, bpd)
            move = c[i] / c[i - k] - 1 if k > 0 else np.nan
            k3 = min(i, 3 * bpd)
            move3 = c[i] / c[i - k3] - 1 if k3 > 0 else np.nan
            k7 = min(i, 7 * bpd)
            move7 = c[i] / c[i - k7] - 1 if k7 > 0 else np.nan
            rows.append(dict(
                move3=float(move3) if np.isfinite(move3) else None,
                move7=float(move7) if np.isfinite(move7) else None,
                peak1=(float(pk1[i]) if pk1 is not None and np.isfinite(pk1[i]) else None),
                peak2=(float(pk2[i]) if pk2 is not None and np.isfinite(pk2[i]) else None),
                own_peak=(float(own_peak[i]) if np.isfinite(own_peak[i]) else None),
                gap_days=(gap / bpd if gap is not None else None),
                sym=sym, kind=kind, tf=tf, t=str(df.index[i]),
                half="first" if df.index[i] < mid else "second",
                rsi=float(r[i]), own=str(own[i]),
                up1=(str(t1[i]) if t1 is not None else "NA"),
                up1_os=(bool(r1[i] <= OS) if (r1 is not None and np.isfinite(r1[i])) else None),
                up1_recent=(bool(rec1[i]) if rec1 is not None else None),
                up2=(str(t2[i]) if t2 is not None else "NA"),
                up2_os=(bool(r2[i] <= OS) if (r2 is not None and np.isfinite(r2[i])) else None),
                up2_recent=(bool(rec2[i]) if rec2 is not None else None),
                move=float(move) if np.isfinite(move) else None,
                vs_ema=float(c[i] / ema[i] - 1) if np.isfinite(ema[i]) and ema[i] > 0 else None,
                relvol=float(relvol[i]) if np.isfinite(relvol[i]) else None,
                units=len(fills), held=int(held), ended=ended,
                ret=float(exit_px / avg - 1 - cost),
                ret_single=float(exit_px / first_fill - 1 - cost),
                worst=float(worst),
                drift=float(np.exp(drift * held) - 1 - cost),
                part=float(part),
                ret_ride=ride["ride"][0], ride_end=ride["ride"][1], ride_held=ride["ride"][2],
                ret_ema=ride["ema"][0], ema_end=ride["ema"][1], ema_held=ride["ema"][2]))
        # the next campaign can only start after this one closed
        i = j + 1
    return rows, dict(sym=sym, kind=kind, tf=tf, bars=int(in_win.sum()), drift=drift)


# ------------------------------------------------------------------ aggregate

def bucket(row):
    b = {}
    b["own trend"] = row["own"]
    b["higher trend"] = row["up1"]
    b["two-up trend"] = row["up2"]
    b["higher oversold now"] = {True: "yes", False: "no", None: "NA"}[row["up1_os"]]
    b["inside higher backburner (last 3 bars)"] = {True: "yes", False: "no", None: "NA"}[row["up1_recent"]]
    b["two-up oversold now"] = {True: "yes", False: "no", None: "NA"}[row["up2_os"]]
    b["inside two-up backburner"] = {True: "yes", False: "no", None: "NA"}[row["up2_recent"]]
    b["rsi depth at first print"] = ("<=20" if row["rsi"] <= 20 else "<=25" if row["rsi"] <= 25 else "<=30")
    b["units bought"] = ("1" if row["units"] == 1 else "2-3" if row["units"] <= 3 else "4+")
    def band(m):
        if m is None:
            return "NA"
        return ("down >5%" if m < -0.05 else "down 0-5%" if m < 0 else
                "up 0-5%" if m < 0.05 else "up 5-10%" if m < 0.10 else
                "up 10-20%" if m < 0.20 else "up 20-50%" if m < 0.50 else "up >50%")
    b["move over prior day"] = band(row["move"])
    b["move over prior 3 days"] = band(row["move3"])
    b["move over prior week"] = band(row["move7"])
    pk = row["peak1"]
    b["higher RSI hit 70+ in its last 20 bars"] = "NA" if pk is None else ("yes" if pk >= 70 else "no")
    pk2 = row["peak2"]
    b["two-up RSI hit 70+ in its last 20 bars"] = "NA" if pk2 is None else ("yes" if pk2 >= 70 else "no")
    op = row["own_peak"]
    b["own RSI hit 70+ recently"] = "NA" if op is None else ("yes" if op >= 70 else "no")
    hot = ((row["move"] is not None and row["move"] >= 0.10) or
           (row["move3"] is not None and row["move3"] >= 0.20))
    b["hot name (up 10%+ on the day or 20%+ in 3 days)"] = "yes" if hot else "no"
    b["hot name AND higher RSI hit 70+"] = ("yes" if (hot and pk is not None and pk >= 70)
                                            else "no")
    g = row["gap_days"]
    b["days since the last campaign on this chart"] = ("first seen" if g is None else "<1" if g < 1
                                                       else "1-3" if g < 3 else "3-10" if g < 10 else "10+")
    b["first selloff after a big run (week up 20%+, 3+ days since last)"] = (
        "yes" if (row["move7"] is not None and row["move7"] >= 0.20 and (g is None or g >= 3)) else "no")
    e = row["vs_ema"]
    b["vs 12 EMA"] = ("NA" if e is None else "far below (<-3%)" if e < -0.03 else
                      "below" if e < 0 else "above")
    rv = row["relvol"]
    b["relative volume"] = ("NA" if rv is None else "<1x" if rv < 1 else "1-2x" if rv < 2 else ">2x")
    b["asset"] = row["kind"]
    b["half"] = row["half"]
    return b


CONDS = ["own trend", "higher trend", "two-up trend", "higher oversold now",
         "inside higher backburner (last 3 bars)", "two-up oversold now",
         "inside two-up backburner", "rsi depth at first print", "units bought",
         "move over prior day", "move over prior 3 days", "move over prior week",
         "higher RSI hit 70+ in its last 20 bars", "two-up RSI hit 70+ in its last 20 bars",
         "own RSI hit 70+ recently", "hot name (up 10%+ on the day or 20%+ in 3 days)",
         "hot name AND higher RSI hit 70+", "days since the last campaign on this chart",
         "first selloff after a big run (week up 20%+, 3+ days since last)",
         "vs 12 EMA", "relative volume", "asset", "half"]
PER_TF_CONDS = ["higher trend", "inside higher backburner (last 3 bars)", "units bought",
                "move over prior day", "move over prior 3 days",
                "hot name (up 10%+ on the day or 20%+ in 3 days)",
                "hot name AND higher RSI hit 70+", "higher RSI hit 70+ in its last 20 bars",
                "first selloff after a big run (week up 20%+, 3+ days since last)"]


def block(d):
    """One line of results for a set of campaigns."""
    r = d["ret"]
    u = d["units"].astype(float)
    rr, rt = d["ret_ride"], d["ret_ema"]
    return dict(n=int(len(d)),
                ret=float(r.mean()), median=float(r.median()), win=float((r > 0).mean()),
                # dollar-weighted: the losers carry the most units, so this is
                # the return on the money actually put in
                dw=float((r * u).sum() / u.sum()),
                # the owner's exit: breakeven partial, ride the rest
                ride=float(rr.mean()), ride_dw=float((rr * u).sum() / u.sum()),
                ride_win=float((rr > 0).mean()), ride_held=float(d["ride_held"].mean()),
                ride_hl=float((d["ride_end"] == "closed under last higher low").mean()),
                ride_low=float((d["ride_end"] == "low broke").mean()),
                ema=float(rt.mean()), ema_dw=float((rt * u).sum() / u.sum()),
                ema_win=float((rt > 0).mean()), ema_held=float(d["ema_held"].mean()),
                part=float(d["part"].mean()),
                single=float(d["ret_single"].mean()),
                drift=float(d["drift"].mean()),
                edge=float(r.mean() - d["drift"].mean()),
                units=float(d["units"].mean()), held=float(d["held"].mean()),
                bounce=float((d["ended"] == "bounce").mean()),
                bad=float((d["ended"] == "bad").mean()),
                worst=float(d["worst"].mean()),
                # the whole point of scaling: per-unit return vs buying once
                scale_gain=float(r.mean() - d["ret_single"].mean()))


def summarise(ev):
    out = {"all": block(ev),
           "by_tf": {tf: block(g) for tf, g in ev.groupby("tf")},
           "by_tf_asset": {"%s %s" % (k, tf): block(g)
                           for (tf, k), g in ev.groupby(["tf", "kind"])}}
    conds = {}
    for cond in CONDS:
        conds[cond] = {}
        for val, g in ev.groupby(cond):
            if len(g) < 50:
                continue
            blk = block(g)
            splits = {}
            for hv, gg in g.groupby("half"):
                if len(gg) >= 50:
                    splits["half:" + hv] = float(gg["ret"].mean() - gg["drift"].mean())
            for kv, gg in g.groupby("kind"):
                if len(gg) >= 50:
                    splits["asset:" + kv] = float(gg["ret"].mean() - gg["drift"].mean())
            blk["splits"] = splits
            # holds = positive in both halves AND in every asset class that
            # has at least 50 campaigns under this condition
            blk["holds"] = bool(splits) and all(x > 0 for x in splits.values())
            conds[cond][str(val)] = blk
    out["conditions"] = conds
    per_tf = {}
    for tf, g in ev.groupby("tf"):
        per_tf[tf] = {}
        for cond in PER_TF_CONDS:
            per_tf[tf][cond] = {str(v): block(gg) for v, gg in g.groupby(cond) if len(gg) >= 40}
        # the owner's combination for the fast charts: hot name AND few adds
        hot = g[(g["hot name (up 10%+ on the day or 20%+ in 3 days)"] == "yes")]
        if len(hot) >= 40:
            per_tf[tf]["hot name, by units bought"] = {
                str(v): block(gg) for v, gg in hot.groupby("units bought") if len(gg) >= 40}
    out["per_tf"] = per_tf
    return out


def _work(args):
    """One name, every timeframe. Runs in its own process."""
    sym, kind, start = args
    rows, metas, errs = [], [], []
    try:
        fr = frames_for(sym, kind)
    except Exception as ex:
        return [], [], ["%s %s: %s" % (kind, sym, ex)]
    for tf in CHAIN:
        if tf not in fr:
            continue
        try:
            ev, meta = study_frame(sym, kind, tf, fr, start)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
            continue
        rows += ev
        metas.append(meta)
    return rows, metas, errs


def quiet_workers():
    """No console window per worker on Windows."""
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)


def main():
    procs = max(1, os.cpu_count() or 4)
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1,
                                           encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * YEARS)
    names = universe()
    rows, frames_meta, done = [], [], 0
    quiet_workers()
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for r, metas, errs in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            rows += r
            frames_meta += metas
            for e in errs:
                print("  " + e, flush=True)
            done += 1
            if done % 25 == 0 or done == len(names):
                print("  %d/%d names, %d campaigns  (%.0fs)" % (
                    done, len(names), len(rows), time.time() - t0), flush=True)
    ev = pd.DataFrame(rows)
    if ev.empty:
        sys.exit("  no events")
    for k, v in pd.DataFrame([bucket(r) for r in rows]).items():
        ev[k] = v.values
    os.makedirs("validation", exist_ok=True)
    ev.to_csv(OUT_CSV, index=False, compression="gzip")
    res = summarise(ev)
    res["meta"] = dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                       window_start=str(start.date()), years=YEARS, cost=COST,
                       os=OS, bounce=BOUNCE, stop_atr=STOP_ATR, max_units=MAX_UNITS,
                       cap_days=CAP_DAYS,
                       names=len(names), frames=len(frames_meta), campaigns=int(len(ev)),
                       tfs={tf: int((ev.tf == tf).sum()) for tf in CHAIN if (ev.tf == tf).any()},
                       names_by_kind={k: int(n) for k, n in pd.Series([k for _, k in names]).value_counts().items()})
    json.dump(res, open(OUT_JSON, "w"), indent=1)

    # plain-words console summary
    print("\n  BACKBURNER STUDY  %d names, %d frames, %d campaigns since %s  (%.0fs)" % (
        len(names), len(frames_meta), len(ev), start.date(), time.time() - t0))
    print("  %-5s %6s  %9s %9s %9s  %5s %5s %5s  %6s %5s %5s  %4s" % (
        "tf", "camps", "sell-all$", "ride-HL$", "ride-EMA$", "win", "winR", "held", "heldR", "bad", "lowbrk", "part"))
    for tf in CHAIN:
        b = res["by_tf"].get(tf)
        if not b:
            continue
        print("  %-5s %6d  %+8.2f%% %+8.2f%% %+8.2f%%  %4.0f%% %4.0f%% %5.0f  %5.0f %4.0f%% %4.0f%%  %3.0f%%" % (
            tf, b["n"], 100 * b["dw"], 100 * b["ride_dw"], 100 * b["ema_dw"],
            100 * b["win"], 100 * b["ride_win"], b["held"], b["ride_held"],
            100 * b["bad"], 100 * b["ride_low"], 100 * b["part"]))
    print("\n  conditions whose edge over drift holds in both halves AND both asset classes:")
    for cond, vals in res["conditions"].items():
        for val, blk in vals.items():
            if blk.get("holds"):
                print("    %-40s %-20s n=%6d  ret %+.2f%%  edge %+.2f%%  bad %3.0f%%" % (
                    cond, val, blk["n"], 100 * blk["ret"], 100 * blk["edge"], 100 * blk["bad"]))
    print("  -> %s" % OUT_JSON)
    for i, a in enumerate(sys.argv):
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout.flush()
            open(os.path.splitext(sys.argv[i + 1])[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
