"""
scanner.py -- scan the crypto universe for names exhibiting the behaviors we
              have detectors for.

    python scanner.py                    scan the top 40 by real volume
    python scanner.py --n 60 --tf 5m,15m,1h
    python scanner.py --json out.json    machine-readable, for the web app

WHAT IT LOOKS FOR
Every behavior here has its own module and its own history of being wrong and
then corrected against charts you graded.

    trend       UP / DOWN / EQ / unshaded from pivot structure   (panel.py)
                24 blind-graded charts, 8 hand-written cases
    rider       the 12 EMA held as a floor, with a live entry when price dips
                back into it                                     (rider.py)
                6 blind-graded charts
    backburner  5m / 15m oversold prints (RSI at or under 30) under a live
                higher-timeframe up-span (backburner_live.py), plus the price
                that would print the next one,
                plus the exact price that would print the next one
    stairstep   how many candles one side has taken in a row     (stairstep.py)
                detector only -- fading it tested negative on 25,000 events

HOW TO READ THE OUTPUT
It ranks by how many behaviors are firing, which is a way of sorting attention,
NOT a probability of profit. A name at the top is one where several things you
watch are true at once. Whether that is worth trading is your call and the
evidence for each component is in STATE.md.

Nothing here is validated as profitable. It is a way to look at 40 charts at
once instead of 3.
"""

import argparse
import json
import warnings

import numpy as np
import pandas as pd

import crypto
import indicators as IND
import panel as P
import rider

warnings.filterwarnings("ignore")

TFS = ["5m", "15m", "1h", "4h", "12h", "1d", "1w", "1mo"]

# Only these are fetched. Everything else is resampled from them, because no
# free source serves all eight: Coinbase has no 4h or 12h, Yahoo has neither
# and caps 5m at 60 days. Deriving them keeps one code path for crypto,
# equities, futures and FX.
BASE = {"5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
DERIVE = {"4h": ("1h", "4h"), "12h": ("1h", "12h"),
          "1w": ("1d", "W-FRI"), "1mo": ("1d", "ME")}
BARS = 500
RSI_N = IND.RSI_N

# one definition, in indicators.py -- see the note there about why
rsi_parts = IND.rsi_parts
reverse_rsi = IND.reverse_rsi






def read_tf(df):
    """Every detector, on one timeframe of one name."""
    # 40, not 60. A monthly frame built from six years of daily bars is only
    # ~53 candles, and a 60-bar floor silently blanked the entire monthly
    # column while every other timeframe looked fine.
    if df is None or len(df) < 40:
        return None
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    r, au, ad = rsi_parts(c)
    trend = P.trend_state(df)
    st, hl, lh = trend
    rd = rider.read(df, state=trend)      # reuse it rather than recompute
    # the RANGE OVERLAY (owner-verified 2026-08-31): the EQ rule living
    # beside the trend engine. A FLAT bar inside a live range reads EQ; a
    # trending bar inside one keeps its trend letter and carries eq=True
    import structure as ST
    eq_now = bool(ST.eq_overlay(df)[0][-1])
    # THE BACKBONE, live clock: the owner's span grammar on the last closed
    # bar. v1's state machine stays available as trend_v1 for comparison.
    span_now = str(ST.states(df, causal=True)[-1])

    # current green / red run, the stair-step count
    green = c > o
    run = 0
    for i in range(len(c) - 1, -1, -1):
        if green[i] == green[-1]:
            run += 1
        else:
            break

    hist = r[np.isfinite(r)]
    return dict(
        close=float(c[-1]),
        trend=("BALANCE" if (span_now == "FLAT" and eq_now) else span_now),
        trend_v1=str(st[-1]),
        eq=eq_now,
        stop=float(hl[-1]) if np.isfinite(hl[-1]) else
             (float(lh[-1]) if np.isfinite(lh[-1]) else None),
        rsi=float(r[-1]),
        rsi_pct=float((hist < r[-1]).mean() * 100) if len(hist) else None,
        bid40=reverse_rsi(c[-1], au[-1], ad[-1], 40),
        bid35=reverse_rsi(c[-1], au[-1], ad[-1], 35),
        bid30=reverse_rsi(c[-1], au[-1], ad[-1], 30),
        ema12=float(rd["ema"][-1]),
        vs_ema=float(c[-1] / rd["ema"][-1] - 1),
        armed=bool(rd["armed"][-1]),
        pullback=bool(rd["pullback"][-1] and rd["armed"][-1]),
        wick_holds=int(rd["wick_hold"][-40:].sum()),
        run=int(run), run_dir="up" if green[-1] else "down",
        oversold=bool(r[-1] <= 30), near_os=bool(r[-1] < 40),   # at or under (owner)
    )


def resample(df, rule):
    """OHLCV to a coarser bar. Calendar-aligned.

    On a 24/7 market that is exactly right. On equities a 4h bin does not divide
    a 6.5-hour session evenly, so a 4h bar here will not line up with
    TradingView's, which anchors to the session open. The trend reading is
    barely affected -- pivots move by at most a bar -- but the levels will
    differ slightly, so trade off the chart, not off this number.
    """
    if df is None or len(df) < 5:
        return None
    o = df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min",
                               "Close": "last", "Volume": "sum"}).dropna()
    return o if len(o) >= 30 else None


def frames_for(sym, source, tfs, fetch):
    """Fetch the base bars once, derive the rest."""
    need = {BASE[t] for t in tfs if t in BASE}
    need |= {BASE[DERIVE[t][0]] for t in tfs if t in DERIVE}
    raw = {}
    for b in need:
        try:
            raw[b] = fetch(sym, source, b)
        except Exception:
            raw[b] = None
    out = {}
    for t in tfs:
        if t in BASE:
            out[t] = raw.get(BASE[t])
        elif t in DERIVE:
            src, rule = DERIVE[t]
            out[t] = resample(raw.get(BASE[src]), rule)
        else:
            out[t] = None
    return out


def _crypto_fetch(sym, source, base):
    # 1600 daily bars is ~6 years, which is what the MONTHLY frame needs to
    # have enough candles for pivots. At 700 it produced 23 monthly bars and
    # the monthly column was simply blank.
    bars = {"5m": 500, "15m": 500, "1h": 900, "1d": 1600}.get(base, 500)
    return crypto.candles(sym, base, bars, source=source)


def scan_one(sym, source, tfs):
    fr = frames_for(sym, source, tfs, _crypto_fetch)
    out = {}
    for tf in tfs:
        try:
            out[tf] = read_tf(fr.get(tf))
        except Exception:
            out[tf] = None
    return out


def flags(tfs):
    """The behaviors, ranked by how tradable they are RIGHT NOW.

    Each entry is (key, why, weight). Weight drives the ranking, and it encodes
    a judgment rather than a measurement: a dip into the 12 EMA while a ride is
    live is something you could act on this minute; a name merely sitting in an
    uptrend is context. Stair steps are reported at weight 0 -- fading them
    tested NEGATIVE on 25,000 events, so they are shown as background and never
    lift a name up the list.
    """
    f = []
    lo = tfs.get("5m") or {}
    mid = tfs.get("15m") or {}
    hi = tfs.get("1h") or {}
    top = tfs.get("4h") or {}

    # --- the entries: something is happening on this bar
    for t in ("5m", "15m", "1h", "4h", "12h", "1d"):
        v = tfs.get(t) or {}
        if v.get("pullback"):
            f.append(("rider-dip-%s" % t,
                      "%s dip into the 12 EMA at %.6g" % (t, v["ema12"]), 5))

    HIGHER = ("1h", "4h", "12h", "1d", "1w")
    ups = [t for t in HIGHER if (tfs.get(t) or {}).get("trend") == "UP"]
    dns = [t for t in HIGHER if (tfs.get(t) or {}).get("trend") == "DOWN"]

    if lo.get("oversold") and ups:
        f.append(("backburner-5m", "5m RSI %.0f under a %s uptrend"
                  % (lo["rsi"], "+".join(ups)), 5))
    elif mid.get("oversold") and ("1h" in ups or "4h" in ups):
        f.append(("backburner-15m", "15m RSI %.0f under a higher uptrend"
                  % mid["rsi"], 4))

    # --- the rides: in progress, worth watching for the next dip
    for t, w in (("1d", 4), ("12h", 3), ("4h", 3), ("1h", 3), ("15m", 2)):
        v = tfs.get(t) or {}
        if v.get("armed") and not v.get("pullback"):
            f.append(("riding-%s" % t, "%s riding the 12 EMA (%d wick-holds)"
                      % (t, v.get("wick_holds", 0)), w))

    # --- the context
    if len(ups) >= 2:
        f.append(("trend-up", "+".join(ups) + " up", 2))
    elif len(ups) == 1:
        f.append(("trend-up1", ups[0] + " up", 1))
    if len(dns) >= 2:
        f.append(("trend-down", "+".join(dns) + " down", 2))

    for t, w in (("1w", 4), ("1d", 4), ("12h", 3), ("4h", 3), ("1h", 2),
                 ("15m", 1)):
        v = tfs.get(t) or {}
        if v.get("trend") == "BALANCE" or v.get("eq"):
            f.append(("eq-%s" % t, "%s in equilibrium" % t, w))

    if hi.get("rsi_pct") is not None and hi["rsi_pct"] <= 5:
        f.append(("hist-os", "1h RSI in its own bottom %.0f%%" % hi["rsi_pct"], 2))
    if top.get("rsi_pct") is not None and top["rsi_pct"] >= 95:
        f.append(("hist-ob", "4h RSI in its own top %.0f%%"
                  % (100 - top["rsi_pct"]), 1))

    # --- background only, never lifts a name
    for t in ("5m", "15m", "1h"):
        v = tfs.get(t) or {}
        if v.get("run", 0) >= 7:
            f.append(("stair-%s" % t, "%s %d %s candles in a row"
                      % (t, v["run"], v["run_dir"]), 0))
    return f


def score(fl):
    """A name is worth looking at in proportion to what is actionable on it."""
    return sum(w for _, _, w in fl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--tf", default=",".join(TFS))
    ap.add_argument("--json", default=None)
    ap.add_argument("--min-flags", type=int, default=1)
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    print("fetching universe...")
    u = crypto.universe(a.n)
    print("  %d names\nscanning %s ..." % (len(u), "/".join(tfs)))

    rows = []
    for _, x in u.iterrows():
        data = scan_one(x["sym"], x["source"], tfs)
        if not any(data.values()):
            continue
        fl = flags(data)
        rows.append(dict(sym=x["sym"], price=x["price"], volume=x["volume"],
                         chg24=x["chg24"], tfs=data, flags=fl))
    rows.sort(key=lambda r: (-score(r["flags"]), -r["volume"]))

    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1, default=float)
        print("  wrote %s" % a.json)

    print("\n" + "=" * 100)
    print("  CRYPTO SCAN  %s   %d names   %s"
          % (pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), len(rows), "/".join(tfs)))
    print("=" * 100)
    print("  %-7s %10s %8s  %-22s %s"
          % ("sym", "price", "24h", "trend 5m/15m/1h/4h", "what is firing"))
    print("  " + "-" * 96)
    short = {"UP": "U", "DOWN": "D", "BALANCE": "E", "FLAT": "."}
    for r in rows:
        if score(r["flags"]) < a.min_flags:
            continue
        seq = " ".join(short.get((r["tfs"].get(t) or {}).get("trend", "FLAT"), ".")
                       for t in tfs)
        names = ", ".join(n for n, _, w in r["flags"][:4] if w) or "-"
        print("  %-7s %10.4g %+7.1f%%  %-22s %s"
              % (r["sym"], r["price"], r["chg24"], seq, names))

    print("\n  detail on the top names:")
    for r in rows[:6]:
        if not r["flags"]:
            continue
        print("\n  %s   %.4g   %+.1f%% 24h" % (r["sym"], r["price"], r["chg24"]))
        for _, why, _w in r["flags"]:
            print("     - %s" % why)
        for t in tfs:
            v = r["tfs"].get(t)
            if not v:
                continue
            bid = v.get("bid30")
            print("     %-4s %-8s rsi %5.1f   ema %10.4g (%+5.1f%%)   rsi30 at %s"
                  % (t, v["trend"], v["rsi"], v["ema12"], 100 * v["vs_ema"],
                     ("%.4g" % bid) if bid else "above"))
    print("\n  Ranked by how many behaviors are firing. That sorts attention,")
    print("  not probability. Nothing here is validated as profitable.")


if __name__ == "__main__":
    main()
