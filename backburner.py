"""
backburner.py -- the ladder tracker for a name that is blowing up.

    python backburner.py MRNA
    python backburner.py MRNA --since 2026-08-19      anchor to the event day
    python backburner.py MRNA --entry 137             mark your average

THE METHOD THIS SERVES
When a name explodes upward there is no pivot structure to lean on yet, so a
structural stop is meaningless -- the last real higher low can be 60% below.
What there IS, is a ladder:

    1. the move goes vertical
    2. the first thing to look for is a 5m oversold -- a BACKBURNER
    3. while it keeps bouncing off 5m OS and running hard, keep buying those
    4. when it finally reaches its first 15m OS, buy that
    5. rinse and repeat, the timeframe escalating as the move matures

So the thing to track is not "where is the stop", it is "which rung are we on,
and what price puts us on the next one".

WHY ABSOLUTE RSI 30 IS NOT ENOUGH
In a name running this hard the 5m RSI may never print 30 -- it bottoms at 42
and turns. A fixed threshold would show no backburners at all for days. So every
RSI is reported three ways:

    now        the plain RSI(14) reading
    pctile     where that sits in the name's OWN recent RSI range
    OS price   the price that WOULD produce an oversold print on the next bar

That last column is the actionable one: it is where a bid belongs, computed by
inverting Wilder's RSI rather than eyeballed off a chart.

ALSO TRACKED (the baselines)
    stair-steps    consecutive higher lows -- how many candles the bulls have
                   defended in a row; the continuation / exhaustion tell
    VWAP           session-anchored, the most-watched intraday line
    EMA12          the dynamic floor a strong trend rides
    fib            retracement of the event leg

Reports state. Makes no recommendation and sizes nothing.
"""

import argparse
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

TFS = [("5m", "5m", 5), ("15m", "15m", 15), ("30m", "30m", 30), ("1h", "1h", 60)]
OS_LEVELS = [30, 35, 40]
# how close to a level still counts as touching it. Intraday feeds disagree by
# a few cents on thin bars, which is worth ~0.3 RSI points at these levels.
GRAZE = 1.0
RSI_N = 14


def rsi(c, n=RSI_N):
    """Wilder's RSI -- exponential smoothing of up and down moves."""
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs), up, dn


def rsi_sma(c, n=RSI_N):
    """Cutler's RSI -- simple moving average of up and down moves.

    THIS IS NOT A COSMETIC DIFFERENCE. On MRNA's 15m since 2026-08-20, Wilder
    never printed below 30.4 while Cutler printed <= 30 on twenty-two bars.
    A ladder built on one and read off a chart drawn with the other will
    disagree about whether a rung ever happened. Always check which one the
    charting platform uses.
    """
    d = pd.Series(np.diff(c, prepend=c[0]))
    up = d.clip(lower=0).rolling(n).mean().values
    dn = (-d).clip(lower=0).rolling(n).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs), up, dn


def reverse_rsi(close, avg_up, avg_dn, target, n=RSI_N):
    """The price on the NEXT bar that would print exactly `target` Wilder RSI.

    Wilder's smoothing, one bar forward. If price falls by x:
        avgU' = avgU*(n-1)/n           (no upward move)
        avgD' = (avgD*(n-1) + x)/n
    Setting RS' = target/(100-target) and solving for x gives the drop needed.
    A non-positive x means price would have to RISE to get there -- i.e. the
    reading is already below the target -- and None is returned.
    """
    if target >= 100:
        return None
    rs_t = target / (100.0 - target)
    if rs_t <= 0:
        return None
    x = avg_up * (n - 1) / rs_t - avg_dn * (n - 1)
    if x <= 0:
        return None
    px = close - x
    return px if px > 0 else None


def reverse_rsi_sma(close, ups, dns, target, n=RSI_N):
    """Same question for Cutler's RSI, where the window rolls instead of decays.

    Next bar drops the oldest move out of the window and adds (0, x):
        avgU' = (sumU - oldestU) / n
        avgD' = (sumD - oldestD + x) / n
    `ups` and `dns` are the last n up/down moves, oldest first.
    """
    if target >= 100 or len(ups) < n:
        return None
    rs_t = target / (100.0 - target)
    if rs_t <= 0:
        return None
    su, sd = float(np.sum(ups[-n:])), float(np.sum(dns[-n:]))
    ou, od = float(ups[-n]), float(dns[-n])
    x = (su - ou) / rs_t - (sd - od)
    if x <= 0:
        return None
    px = close - x
    return px if px > 0 else None


def intrabar_rsi(m1, minutes, n=RSI_N):
    """The lowest RSI actually DISPLAYED while each bar was still forming.

    THIS IS THE ONE THAT MATTERS AND IT TOOK THREE WRONG ANSWERS TO FIND.
    RSI is computed on closes, so a completed-bar series never sees what the
    indicator showed mid-bar. A trader watching a live 15m candle sees RSI dip
    to 29.8, buys it, and the candle then closes higher -- printing 37.5 and
    erasing the rung from every closed-bar calculation forever.

    MRNA's 15m bar of 2026-08-20 13:15 did exactly that: 29.6 intrabar, 30.4 on
    the close. A strict "closed below 30" test reports the 15m never got
    oversold, while the chart plainly showed 29 while the candle was live.

    Reconstructed from 1m bars: hold the Wilder averages from the last CLOSED
    bar, then re-evaluate RSI at every 1m close inside the forming bar, exactly
    as the platform repaints it tick by tick.

    LIMIT: Yahoo serves roughly 7 days of 1m data, so this only reaches back
    that far. Older bars fall back to the closed-bar reading and are marked.
    """
    rule = "%dmin" % minutes
    closes = m1["Close"].resample(rule).last().dropna()
    lows = m1["Low"].resample(rule).min().dropna()
    c = closes.values.astype(float)
    if len(c) < n + 2:
        return None
    d = np.diff(c, prepend=c[0])
    au = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    ad = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    closed = 100 - 100 / (1 + np.divide(au, ad, out=np.full_like(au, np.inf),
                                        where=ad > 0))
    out = []
    step = pd.Timedelta(minutes=minutes)
    for i in range(1, len(closes)):
        t = closes.index[i]
        # pandas labels each bin by its START, so the bar labelled 13:30 is the
        # minutes 13:30-13:45. Sampling [t-step, t) grabs the PREVIOUS candle
        # and pairs its intrabar low with this candle's close -- which reported
        # a 29.6 intrabar against a 37.5 close that belonged to a different bar.
        win = m1["Close"].loc[(m1.index >= t) & (m1.index < t + step)]
        pu, pdn, pc = au[i - 1], ad[i - 1], c[i - 1]

        def prov(p):
            ch = p - pc
            u = (pu * (n - 1) + max(ch, 0.0)) / n
            dd = (pdn * (n - 1) + max(-ch, 0.0)) / n
            return 100 - 100 / (1 + (u / dd if dd > 0 else np.inf))

        vals = [prov(p) for p in win.values.astype(float)]
        vals.append(prov(float(lows.iloc[i])))     # the true intrabar extreme
        out.append((t, min(vals) if vals else closed[i], closed[i]))
    return pd.DataFrame(out, columns=["t", "intra", "closed"]).set_index("t")


def stair_steps(low):
    """Consecutive higher lows ending at the last bar."""
    k = 0
    for i in range(len(low) - 1, 0, -1):
        if low[i] > low[i - 1]:
            k += 1
        else:
            break
    return k


def session_vwap(d):
    day = d.index.normalize()
    tp = (d["High"] + d["Low"] + d["Close"]) / 3.0
    pv = (tp * d["Volume"]).groupby(day).cumsum()
    vv = d["Volume"].groupby(day).cumsum()
    return (pv / vv.replace(0, np.nan)).values


def fetch(sym, interval, days):
    import yfinance as yf
    # prepost=True is mandatory here. On an event name the ladder runs in
    # extended hours; without it those bars simply do not exist.
    d = yf.download(sym, interval=interval, period="%dd" % days,
                    progress=False, auto_adjust=False, prepost=True)
    if d is None or len(d) == 0:
        return None
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d.dropna()


def os_events(r, level, gap=3):
    """Bars sitting below `level`.

    An earlier version counted CROSSINGS down through the level, which produced
    a table where "bars under 35" exceeded "bars under 40" -- legitimate for
    crossings (RSI can dip under 35 twice without ever recovering above 40) but
    it reads as a bug. Counting bars below is monotone in the level and answers
    the only question that matters: did this rung print, and when last.
    """
    return [i for i in range(len(r)) if np.isfinite(r[i]) and r[i] <= level]


def read_tf(sym, label, interval, since, entry):
    d = fetch(sym, interval, 60)
    if d is None or len(d) < RSI_N + 5:
        return None
    full = d
    if since is not None:
        d = d[d.index >= since]
    if len(d) < RSI_N + 2:
        d = full.tail(120)

    c = d["Close"].values.astype(float)
    lo = d["Low"].values.astype(float)
    # RSI must be warmed on the FULL series and only then sliced. Computing it
    # on the window alone leaves RSI(14) un-warmed -- on the 1h that is only
    # ~19 bars since the anchor, and it prints a fake 0.0 minimum that invents
    # oversold events which never happened.
    cf = full["Close"].values.astype(float)
    r_full, up_f, dn_f = rsi(cf)
    rs_full, _, _ = rsi_sma(cf)
    keep = full.index >= d.index[0]
    r, up, dn = r_full[keep], up_f[keep], dn_f[keep]
    r_sma = rs_full[keep]
    # raw per-bar moves, needed to invert the SMA variant
    dmov = np.diff(cf, prepend=cf[0])
    ups_raw, dns_raw = np.clip(dmov, 0, None), np.clip(-dmov, 0, None)

    # historical RSI: where does now sit in this name's own recent range?
    hist = r_full[-1500:] if len(r_full) > 1500 else r_full
    hist = hist[np.isfinite(hist)]
    pct = float((hist < r[-1]).mean() * 100) if len(hist) else np.nan

    rec = dict(
        tf=label, bars=len(d), close=c[-1], rsi=r[-1], pct=pct,
        rsi_min=float(np.nanmin(r)), rsi_max=float(np.nanmax(r)),
        hist_min=float(np.nanmin(hist)) if len(hist) else np.nan,
        steps=stair_steps(lo),
        ema12=pd.Series(c).ewm(span=12, adjust=False).mean().values[-1],
        vwap=session_vwap(d)[-1] if "Volume" in d else np.nan,
    )
    rec["rsi_sma"] = r_sma[-1]
    rec["rsi_sma_min"] = float(np.nanmin(r_sma))
    rec["events_sma"] = {lv: os_events(r_sma, lv) for lv in OS_LEVELS}
    for lv in OS_LEVELS:
        rec["px%d" % lv] = reverse_rsi(c[-1], up[-1], dn[-1], lv)
        rec["sma%d" % lv] = reverse_rsi_sma(c[-1], ups_raw, dns_raw, lv)
    # the name's own historical oversold extreme, and the price that retests it
    rec["px_hist"] = (reverse_rsi(c[-1], up[-1], dn[-1], rec["hist_min"])
                      if np.isfinite(rec["hist_min"]) else None)
    rec["events"] = {lv: os_events(r, lv) for lv in OS_LEVELS}
    rec["idx"] = d.index
    rec["entry"] = entry
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--since", default=None,
                    help="anchor date of the explosion, e.g. 2026-08-19")
    ap.add_argument("--entry", type=float, default=None)
    ap.add_argument("--both", action="store_true",
                    help="also show the Cutler/SMA variant for comparison")
    a = ap.parse_args()
    sym = a.symbol.upper()
    since = pd.Timestamp(a.since) if a.since else None

    recs = []
    for label, iv, mins in TFS:
        try:
            rec = read_tf(sym, label, iv, since, a.entry)
            if rec:
                rec["mins"] = mins
        except Exception as e:
            print("  %s failed: %s" % (label, e))
            rec = None
        if rec:
            recs.append(rec)
    if not recs:
        print("no data")
        return

    show_both = a.both
    # one 1m pull serves every timeframe
    m1 = fetch(sym, "1m", 7)
    for r in recs:
        r["intra_min"] = np.nan
        r["intra_hits"] = 0
        if m1 is None or len(m1) < 60:
            continue
        # Warm on the FULL 1m series, THEN slice to the window. Slicing first
        # leaves the resampled 15m/1h series un-warmed and prints RSI 0.0,
        # inventing rungs -- the same mistake as the closed-bar version.
        ib = intrabar_rsi(m1, r["mins"])
        if ib is None or ib.empty:
            continue
        if since is not None:
            ib = ib[ib.index >= since]
        ib = ib[np.isfinite(ib.intra) & (ib.intra > 0)]
        if ib.empty:
            continue
        r["intra_min"] = float(ib.intra.min())
        r["intra_hits"] = int((ib.intra <= 30).sum())
        hid = ib[(ib.closed > 30) & (ib.intra <= 30)]
        r["intra_last"] = (hid.index[-1].strftime("%m-%d %H:%M")
                           if len(hid) else "")
    px = recs[0]["close"]
    print("=" * 86)
    print("  %s  BACKBURNER LADDER   last %.2f%s" %
          (sym, px, ("   your avg %.2f (%+.1f%%)" %
                     (a.entry, 100 * (px / a.entry - 1))) if a.entry else ""))
    if since:
        print("  anchored to %s" % since.date())
    print("=" * 86)

    print("\n  WHERE THE OVERSOLD PRICES ARE")
    print("  %-5s %7s %7s %8s %9s %9s %9s %10s"
          % ("TF", "rsi", "pctile", "lowest", "RSI 40", "RSI 35", "RSI 30",
             "own low"))
    print("  " + "-" * 82)
    for r in recs:
        def f(v):
            return ("%9.2f" % v) if v else "     above"
        print("  %-5s %7.1f %6.0f%% %8.1f %s %s %s %s"
              % (r["tf"], r["rsi"], r["pct"], r["rsi_min"],
                 f(r["px40"]), f(r["px35"]), f(r["px30"]),
                 ("%10.2f" % r["px_hist"]) if r["px_hist"] else "     above"))
        if show_both:
            print("  %-5s %7.1f %6s %8.1f %s %s %s %10s"
                  % ("  sma", r["rsi_sma"], "-", r["rsi_sma_min"],
                     f(r["sma40"]), f(r["sma35"]), f(r["sma30"]), "-"))
    print("\n  pctile = where this RSI sits in the name's own history "
          "(0 = most oversold it has ever been)")
    print("  'own low' = price that would retest this name's historical RSI "
          "extreme (%.1f)" % recs[0]["hist_min"])
    print("  'above' means the reading is already below that level")

    print("\n  THE LADDER -- oversold prints since the move began")
    print("  Wilder RSI, which is what TradingView's rsi() computes (rma = Wilder).")
    print("  %-5s %7s %7s %7s %8s %14s"
          % ("TF", "<=40", "<=35", "<=30", "lowest", "last <=35"))
    print("  " + "-" * 60)
    for r in recs:
        ev = r["events"]
        last = ""
        for lv in (30, 35):
            if ev[lv]:
                last = r["idx"][ev[lv][-1]].strftime("%m-%d %H:%M")
                break
        # A hard 30 cutoff is a false negative generator. MRNA's 15m bottomed at
        # 30.36 -- zero "prints" by a strict test, but the chart plainly touched
        # oversold, and a few cents of venue difference in a thin post-market
        # bar is worth a third of an RSI point. Anything within GRAZE counts.
        graze = " <- grazed 30" if 30 < r["rsi_min"] <= 30 + GRAZE else ""
        print("  %-5s %7d %7d %7d %8.1f %14s%s"
              % (r["tf"], len(ev[40]), len(ev[35]), len(ev[30]),
                 r["rsi_min"], last or "-", graze))

    print("\n  WHAT THE CHART ACTUALLY SHOWED WHILE THE BAR WAS LIVE")
    print("  A closed-bar series erases any dip the candle recovered from.")
    print("  %-5s %11s %11s %7s %16s"
          % ("TF", "closed min", "intra min", "<=30", "rung hidden at"))
    print("  " + "-" * 56)
    for r in recs:
        if not np.isfinite(r.get("intra_min", np.nan)):
            print("  %-5s %11.1f %11s %7s %16s"
                  % (r["tf"], r["rsi_min"], "no 1m", "-", "-"))
            continue
        print("  %-5s %11.1f %11.1f %7d %16s"
              % (r["tf"], r["rsi_min"], r["intra_min"], r["intra_hits"],
                 r.get("intra_last") or "-"))
    print("  'rung hidden at' = a bar that touched <=30 live but closed above")
    print("  1m history reaches back ~7 days only.")

    if show_both:
        print("\n  Cutler/SMA variant, for comparison only -- NOT what your chart uses")
        print("  %-5s %7s %7s %7s %8s" % ("TF", "<=40", "<=35", "<=30", "lowest"))
        for r in recs:
            e = r["events_sma"]
            print("  %-5s %7d %7d %7d %8.1f"
                  % (r["tf"], len(e[40]), len(e[35]), len(e[30]),
                     r["rsi_sma_min"]))

    print("\n  THE BASELINES")
    print("  %-5s %8s %10s %10s %9s %9s"
          % ("TF", "steps", "ema12", "vwap", "vs ema", "vs vwap"))
    print("  " + "-" * 60)
    for r in recs:
        vw = r["vwap"]
        print("  %-5s %8d %10.2f %10s %+8.1f%% %9s"
              % (r["tf"], r["steps"], r["ema12"],
                 ("%.2f" % vw) if np.isfinite(vw) else "-",
                 100 * (r["close"] / r["ema12"] - 1),
                 ("%+.1f%%" % (100 * (r["close"] / vw - 1)))
                 if np.isfinite(vw) else "-"))

    # Fibonacci on the two legs that matter: the event impulse, and the leg
    # since the gap (which is the one an intraday ladder actually trades).
    f5 = next((r for r in recs if r["tf"] == "5m"), None)
    if f5 is not None and since is not None:
        leg = fetch(sym, "5m", 60)
        leg = leg[leg.index >= since]
        lo_i = int(np.argmin(leg["Low"].values))
        hi_i = int(np.argmax(leg["High"].values))
        swing_lo = float(leg["Low"].values[lo_i])
        swing_hi = float(leg["High"].values[hi_i])
        print("\n  FIB -- leg since the gap  %.2f -> %.2f"
              % (swing_lo, swing_hi))
        print("  %-8s %10s %9s" % ("level", "price", "vs now"))
        print("  " + "-" * 32)
        rng = swing_hi - swing_lo
        for lv in (0.236, 0.382, 0.5, 0.618, 0.786):
            p = swing_hi - lv * rng
            print("  %-8s %10.2f %+8.1f%%"
                  % ("%.1f%%" % (100 * lv), p, 100 * (px / p - 1)))

    # which rung are we on
    five = next((r for r in recs if r["tf"] == "5m"), None)
    fift = next((r for r in recs if r["tf"] == "15m"), None)
    if five and fift:
        n5 = len(five["events"][40])
        n15 = len(fift["events"][40])
        print("\n  RUNG: %d backburners on the 5m, %d oversold prints on the 15m."
              % (n5, n15))
        if n15 == 0:
            nxt = fift["px40"] or fift["px35"]
            print("        The first 15m OS has NOT happened yet. It needs "
                  "roughly %s."
                  % (("%.2f" % nxt) if nxt else "a lower reading than current"))
        else:
            print("        The 15m has already printed oversold %d time(s); "
                  "last %s." % (n15, fift["idx"][fift["events"][40][-1]]
                                .strftime("%m-%d %H:%M")))


if __name__ == "__main__":
    main()
