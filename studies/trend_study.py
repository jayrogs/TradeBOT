"""trend_study.py -- catching a HIGHER LOW and riding the trend. When do
trends keep running?  Every name, every timeframe, all classes.

    python studies/trend_study.py            # ~1h; writes validation/trend_study.json + trend_events.csv.gz

THE TRADE (the owner's other method, 2026-09-06: "not waiting for the
backburner, just trying to catch a higher low and ride that shit"):

  entry   a low pivot is CONFIRMED (2 bars after it printed) and it is a
          HIGHER low: above the previous low pivot by more than the
          same-level tolerance (structure.pivots label "HL"). Buy at the
          NEXT bar's open. Confirmation and price never come from the
          same bar.
  ride    hold until a bar CLOSES under the last higher low. Every later
          confirmed low pivot above the current level raises the level.
          Sell at the next open. (Same rule that is now the standard
          backburner exit.)  Alternate exit: first close under the 12 EMA
          by more than 0.25 ATR.  Cap: CAP_DAYS.
  null    "buy any bar, same exit": entries every NULL_EVERY bars with the
          level = the most recent confirmed low pivot (any label). If the
          higher-low entry has no timing skill, it will not beat this.
  drift   what the chart did on average over the same number of bars.

"KEPT RUNNING" is measured three ways per trade: return per $, did it make
a new higher high after entry (new_hh), how many more higher lows formed
during the ride (legs).

CONDITIONS at entry, all knowable at the entry bar:
  trend state on the chart (UP/FLAT/DOWN under the causal grammar), age of
  the uptrend, how many higher lows the trend has already made, the higher
  and two-up timeframes' trend, RSI at the pivot low (was the dip oversold),
  RSI at entry, pullback depth in ATR and as a fraction of the prior leg,
  the pivot vs the 12 EMA, the 12 EMA slope, moves over 1/3/7 days, hot,
  relative volume at the pivot, how far the entry chased above the pivot,
  the higher timeframe's RSI peak (70+ recently), rally into the 30-day
  high on the daily, drawdown from that high, asset class, era.

ERAS  "before" = anything before the 4-year window (crypto hourly back to
      2015 for the big names, stock daily to 2016), "first"/"second" = the
      two halves of the 4-year window. A condition HOLDS when its edge over
      drift is positive in every era with 50+ trades and every class with
      50+ trades.
"""

import bisect
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B          # noqa: E402  frames_for, universe, higher_view, atr, constants
import indicators as IND              # noqa: E402
import rider                          # noqa: E402
import structure as ST                # noqa: E402

CHAIN, BARS_DAY, CLASS_COST = B.CHAIN, B.BARS_DAY, B.CLASS_COST
YEARS = B.YEARS
CAP_DAYS = 30
EMA_TOL_ATR = 0.25
NULL_EVERY = 25          # null entries every N bars (per frame, offset by frame)
OUT_JSON = os.path.join("validation", "trend_study.json")
OUT_CSV = os.path.join("validation", "trend_events.csv.gz")


# ------------------------------------------------------------------ one frame

def rally_table(d1):
    """Daily: rally into the trailing-30-day high and the drop from it."""
    c = d1["Close"].astype(float)
    hi = c.rolling(30, min_periods=5).max()
    idx = c.rolling(30, min_periods=5).apply(lambda w: int(np.argmax(w)), raw=True)
    pos = np.clip(np.arange(len(c)) - (29 - idx.fillna(0).values.astype(int)), 0, len(c) - 1)
    before = np.clip(pos - 30, 0, len(c) - 1)
    return pd.DataFrame(dict(rally=hi.values / c.values[before] - 1, drop=c.values / hi.values - 1),
                        index=d1.index.normalize())


def ride(c, o, ema, a14, e, level, lows, lcis, highs, hcis, n, cap):
    """From entry bar e (filled at o[e]) with the higher-low level: returns
    (exit_bar, exit_px, why, ema_exit, mfe, mae, new_hh, legs)."""
    p = bisect.bisect_right(lcis, e - 1)          # low pivots confirmed from bar e on
    q = bisect.bisect_right(hcis, e - 1)
    fill = o[e]
    mfe = mae = 0.0
    new_hh = False
    legs = 0
    ema_x = None
    out = None
    for k in range(e, n - 1):
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j >= e and price > level:
                level = price; legs += 1
        while q < len(highs) and highs[q][0] <= k:
            ci, j, price, lab = highs[q]; q += 1
            if j >= e and lab == "HH":
                new_hh = True
        mfe = max(mfe, c[k] / fill - 1); mae = min(mae, c[k] / fill - 1)
        if ema_x is None:
            buf = EMA_TOL_ATR * a14[k] if np.isfinite(a14[k]) else 0.0
            if c[k] < ema[k] - buf:
                ema_x = (k, o[k + 1])
        if c[k] < level:
            out = (k, o[k + 1], "closed under last higher low"); break
        if k - e >= cap:
            out = (k, o[k + 1], "cap"); break
    if out is None:
        return None
    k, px, why = out
    if ema_x is None or ema_x[0] > k:
        ema_x = (k, px)
    return k, px, why, ema_x, mfe, mae, new_hh, legs


def study_frame(sym, kind, tf, frames, start, rt):
    df = frames[tf]
    if len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)
    n = len(c)
    bpd = BARS_DAY[tf]
    cap = CAP_DAYS * bpd
    cost = CLASS_COST.get(kind, B.COST)
    r = IND.rsi_parts(c)[0]
    ema = rider.ema(c)
    a14 = B.atr(h, l, c)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, kind_, lab in piv if kind_ == "low"]
    highs = [(ci, j, p, lab) for ci, j, p, kind_, lab in piv if kind_ == "high"]
    lcis = [x[0] for x in lows]; hcis = [x[0] for x in highs]
    spans = ST.spans(df, causal=True)
    own = np.array(["FLAT"] * n, dtype=object)
    age = np.zeros(n, dtype=int)
    for kind_, s0, s1 in spans:
        own[s0:s1 + 1] = kind_
        if kind_ == "UP":
            age[s0:s1 + 1] = np.arange(s1 - s0 + 1)
    med = pd.Series(v).rolling(bpd * 5, min_periods=bpd).median().values
    relvol = np.divide(v, med, out=np.full(n, np.nan), where=med > 0)
    ci_ = CHAIN.index(tf)
    up1 = frames.get(CHAIN[ci_ + 1]) if ci_ + 1 < len(CHAIN) else None
    up2 = frames.get(CHAIN[ci_ + 2]) if ci_ + 2 < len(CHAIN) else None
    t1, r1, _, pk1 = B.higher_view(df, tf, up1, CHAIN[ci_ + 1]) if up1 is not None else (None, None, None, None)
    t2, r2, _, pk2 = B.higher_view(df, tf, up2, CHAIN[ci_ + 2]) if up2 is not None else (None, None, None, None)
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    days = df.index.normalize()
    rally = rt.reindex(days - pd.Timedelta(days=1), method="ffill") if rt is not None else None
    mid = start + (pd.Timestamp.now() - start) / 2

    def era(i):
        t = df.index[i]
        return "before" if t < start else "first" if t < mid else "second"

    def base(i, e):
        k = min(i, bpd); k3 = min(i, 3 * bpd); k7 = min(i, 7 * bpd)
        return dict(sym=sym, kind=kind, tf=tf, t=str(df.index[e]), era=era(e),
                    own=str(own[i]), age_days=float(age[i] / bpd),
                    up1=(str(t1[i]) if t1 is not None else "NA"),
                    up1_rsi=(float(r1[i]) if r1 is not None and np.isfinite(r1[i]) else None),
                    up2=(str(t2[i]) if t2 is not None else "NA"),
                    peak1=(float(pk1[i]) if pk1 is not None and np.isfinite(pk1[i]) else None),
                    rsi=float(r[i]) if np.isfinite(r[i]) else None,
                    move=float(c[i] / c[i - k] - 1) if k > 0 else None,
                    move3=float(c[i] / c[i - k3] - 1) if k3 > 0 else None,
                    move7=float(c[i] / c[i - k7] - 1) if k7 > 0 else None,
                    vs_ema=float(c[i] / ema[i] - 1) if np.isfinite(ema[i]) and ema[i] > 0 else None,
                    ema_slope=float((ema[i] - ema[i - 5]) / a14[i]) if i >= 5 and np.isfinite(a14[i]) and a14[i] > 0 else None,
                    relvol=float(relvol[i]) if np.isfinite(relvol[i]) else None,
                    rally=(float(rally["rally"].iloc[i]) if rally is not None and np.isfinite(rally["rally"].iloc[i]) else None),
                    drop=(float(rally["drop"].iloc[i]) if rally is not None and np.isfinite(rally["drop"].iloc[i]) else None))

    def finish(row, e, res, cost):
        k, px, why, ema_x, mfe, mae, new_hh, legs = res
        held = k + 1 - e
        row.update(held=int(held), ended=why, ret=float(px / o[e] - 1 - cost),
                   ret_ema=float(ema_x[1] / o[e] - 1 - cost), ema_held=int(ema_x[0] + 1 - e),
                   mfe=float(mfe), mae=float(mae), new_hh=bool(new_hh), legs=int(legs),
                   drift=float(np.exp(drift * held) - 1 - cost))
        return row

    rows = []
    # ---- the trade: every confirmed HIGHER low
    prev_low = None
    prev_high = None
    q = 0
    for idx, (ci, j, price, lab) in enumerate(lows):
        while q < len(highs) and highs[q][0] <= ci:
            prev_high = highs[q]; q += 1
        this_prev_low = prev_low
        prev_low = (ci, j, price, lab)
        e = ci + 1
        if lab != "HL" or e >= n - 1 or ci < 30:
            continue
        # higher lows already inside this uptrend (walk back over recent pivots)
        hl_count = 0
        if own[ci] == "UP":
            s0 = ci - age[ci]
            for x in reversed(lows[:idx + 1]):
                if x[1] < s0:
                    break
                if x[3] == "HL":
                    hl_count += 1
        if df.index[e] < pd.Timestamp("2015-01-01"):
            continue
        res = ride(c, o, ema, a14, e, price, lows, lcis, highs, hcis, n, cap)
        if res is None:
            continue
        row = base(ci, e)
        leg = (prev_high[2] - price) if prev_high is not None and prev_high[1] > (this_prev_low[1] if this_prev_low else -1) else None
        row.update(null=0, hl_px=float(price), hl_rsi=float(r[j]) if np.isfinite(r[j]) else None,
                   pull_atr=(float((prev_high[2] - price) / a14[ci]) if prev_high is not None and np.isfinite(a14[ci]) and a14[ci] > 0 else None),
                   retrace=(float((prev_high[2] - price) / (prev_high[2] - this_prev_low[2])) if prev_high is not None and this_prev_low is not None and prev_high[2] > this_prev_low[2] else None),
                   chase_atr=(float((o[e] - price) / a14[ci]) if np.isfinite(a14[ci]) and a14[ci] > 0 else None),
                   hl_vs_ema=(float(price / ema[j] - 1) if np.isfinite(ema[j]) and ema[j] > 0 else None),
                   hl_count=int(hl_count), first_hl=bool(this_prev_low is not None and this_prev_low[3] in ("LL", "L")))
        rows.append(finish(row, e, res, cost))
    # ---- the null: buy any bar, same exit off the last confirmed low pivot
    off = (hash(sym + tf) % NULL_EVERY)
    for e in range(max(31, off), n - 2, NULL_EVERY):
        if df.index[e] < pd.Timestamp("2015-01-01"):
            continue
        p = bisect.bisect_right(lcis, e - 1) - 1
        if p < 0:
            continue
        level = lows[p][2]
        if c[e - 1] < level:
            continue
        res = ride(c, o, ema, a14, e, level, lows, lcis, highs, hcis, n, cap)
        if res is None:
            continue
        row = base(e - 1, e); row.update(null=1)
        rows.append(finish(row, e, res, cost))
    return rows


# ------------------------------------------------------------------ aggregate

def bucket(row):
    b = {}
    b["trend on the chart at entry"] = row["own"]
    a = row["age_days"]
    b["age of the uptrend"] = ("not in an uptrend" if row["own"] != "UP" else "<2 days" if a < 2 else "2-7 days" if a < 7 else "7-30 days" if a < 30 else "30+ days")
    hc = row.get("hl_count")
    b["higher lows already in this uptrend"] = ("NA" if hc is None or row["null"] else "0-1 (just opening)" if hc <= 1 else "2-3" if hc <= 3 else "4+")
    b["first higher low after a lower low (bottom turning)"] = ("NA" if row["null"] else "yes" if row.get("first_hl") else "no")
    b["higher timeframe trend"] = row["up1"]
    b["two-up timeframe trend"] = row["up2"]
    hr = row.get("hl_rsi")
    b["RSI at the pivot low"] = ("NA" if hr is None else "<=30 (oversold)" if hr <= 30 else "30-40" if hr <= 40 else "40-50" if hr <= 50 else ">50")
    rs = row.get("rsi")
    b["RSI at entry"] = ("NA" if rs is None else "<40" if rs < 40 else "40-50" if rs < 50 else "50-60" if rs < 60 else "60-70" if rs < 70 else "70+")
    pa = row.get("pull_atr")
    b["pullback depth (ATR)"] = ("NA" if pa is None else "<1 ATR" if pa < 1 else "1-2 ATR" if pa < 2 else "2-4 ATR" if pa < 4 else "4+ ATR")
    rt = row.get("retrace")
    b["pullback as a share of the prior leg"] = ("NA" if rt is None else "<25%" if rt < .25 else "25-50%" if rt < .5 else "50-75%" if rt < .75 else "75%+")
    he = row.get("hl_vs_ema")
    b["pivot low vs the 12 EMA"] = ("NA" if he is None else "above" if he > 0 else "just under (0 to -1%)" if he > -0.01 else "under")
    es = row.get("ema_slope")
    b["12 EMA slope (5 bars, in ATR)"] = ("NA" if es is None else "falling" if es < -0.1 else "flat" if es < 0.1 else "rising" if es < 0.5 else "steep")
    ch = row.get("chase_atr")
    b["entry above the pivot (chase)"] = ("NA" if ch is None else "<1 ATR" if ch < 1 else "1-2 ATR" if ch < 2 else "2+ ATR")
    def band(m):
        if m is None:
            return "NA"
        return ("down >5%" if m < -0.05 else "down 0-5%" if m < 0 else "up 0-5%" if m < 0.05 else
                "up 5-10%" if m < 0.10 else "up 10-20%" if m < 0.20 else "up 20-50%" if m < 0.50 else "up >50%")
    b["move over prior day"] = band(row["move"])
    b["move over prior 3 days"] = band(row["move3"])
    b["move over prior week"] = band(row["move7"])
    hot = ((row["move"] is not None and row["move"] >= 0.10) or (row["move3"] is not None and row["move3"] >= 0.20))
    b["hot name (up 10%+ on the day or 20%+ in 3 days)"] = "yes" if hot else "no"
    pk = row["peak1"]
    b["higher RSI hit 70+ in its last 20 bars"] = "NA" if pk is None else ("yes" if pk >= 70 else "no")
    ur = row.get("up1_rsi")
    b["higher timeframe RSI"] = ("NA" if ur is None else "<40" if ur < 40 else "40-55" if ur < 55 else "55-70" if ur < 70 else "70+")
    ra = row.get("rally")
    b["rally into the 30-day high (daily)"] = ("NA" if ra is None else "<10%" if ra < .1 else "10-30%" if ra < .3 else "30-100%" if ra < 1 else "100%+")
    dr = row.get("drop")
    b["drop from the 30-day high (daily)"] = ("NA" if dr is None else "at the high (0 to -3%)" if dr > -.03 else "-3 to -10%" if dr > -.1 else "-10 to -25%" if dr > -.25 else "-25%+")
    rv = row["relvol"]
    b["relative volume"] = ("NA" if rv is None else "<1x" if rv < 1 else "1-2x" if rv < 2 else ">2x")
    b["asset"] = row["kind"]
    b["era"] = row["era"]
    return b


CONDS = ["trend on the chart at entry", "age of the uptrend", "higher lows already in this uptrend",
         "first higher low after a lower low (bottom turning)", "higher timeframe trend", "two-up timeframe trend",
         "RSI at the pivot low", "RSI at entry", "pullback depth (ATR)", "pullback as a share of the prior leg",
         "pivot low vs the 12 EMA", "12 EMA slope (5 bars, in ATR)", "entry above the pivot (chase)",
         "move over prior day", "move over prior 3 days", "move over prior week",
         "hot name (up 10%+ on the day or 20%+ in 3 days)", "higher RSI hit 70+ in its last 20 bars",
         "higher timeframe RSI", "rally into the 30-day high (daily)", "drop from the 30-day high (daily)",
         "relative volume", "asset", "era"]


def block(d):
    r = d["ret"]
    return dict(n=int(len(d)), ret=float(r.mean()), median=float(r.median()),
                win=float((r > 0.005).mean()), flat=float((r.abs() <= 0.005).mean()),
                avg_win=float(r[r > 0.005].mean()) if (r > 0.005).any() else None,
                avg_loss=float(r[r < -0.005].mean()) if (r < -0.005).any() else None,
                ema=float(d["ret_ema"].mean()), held=float(d["held"].mean()),
                new_hh=float(d["new_hh"].mean()), legs=float(d["legs"].mean()),
                mfe=float(d["mfe"].mean()), mae=float(d["mae"].mean()),
                drift=float(d["drift"].mean()), edge=float(r.mean() - d["drift"].mean()),
                capped=float((d["ended"] == "cap").mean()))


def summarise(ev):
    tr = ev[ev.null == 0]; nu = ev[ev.null == 1]
    out = {"all": block(tr), "null": block(nu),
           "by_tf": {tf: block(g) for tf, g in tr.groupby("tf")},
           "null_by_tf": {tf: block(g) for tf, g in nu.groupby("tf")},
           "by_tf_asset": {"%s %s" % (k, tf): block(g) for (tf, k), g in tr.groupby(["tf", "kind"])},
           "null_by_tf_asset": {"%s %s" % (k, tf): block(g) for (tf, k), g in nu.groupby(["tf", "kind"])},
           "by_era": {e: block(g) for e, g in tr.groupby("era")}}
    conds = {}
    for cond in CONDS:
        conds[cond] = {}
        for val, g in tr.groupby(cond):
            if len(g) < 50:
                continue
            blk = block(g)
            splits = {}
            for hv, gg in g.groupby("era"):
                if len(gg) >= 50:
                    splits["era:" + hv] = float(gg["ret"].mean() - gg["drift"].mean())
            for kv, gg in g.groupby("kind"):
                if len(gg) >= 50:
                    splits["asset:" + kv] = float(gg["ret"].mean() - gg["drift"].mean())
            blk["splits"] = splits
            blk["holds"] = bool(splits) and all(x > 0 for x in splits.values())
            # the same condition on the null entries, for "is it the entry or the weather"
            gn = nu[nu[cond] == val] if cond in nu.columns else nu.iloc[0:0]
            blk["null_ret"] = float(gn["ret"].mean()) if len(gn) >= 50 else None
            conds[cond][str(val)] = blk
    out["conditions"] = conds
    per_tf = {}
    for tf, g in tr.groupby("tf"):
        per_tf[tf] = {cond: {str(v): block(gg) for v, gg in g.groupby(cond) if len(gg) >= 40}
                      for cond in CONDS if cond not in ("era",)}
    out["per_tf"] = per_tf
    return out


def main():
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * YEARS)
    names = B.universe()
    rows = []
    for sym, kind in names:
        fr = B.frames_for(sym, kind)
        rt = rally_table(fr["1d"]) if fr.get("1d") is not None and len(fr["1d"]) > 60 else None
        if rt is not None:
            rt = rt[~rt.index.duplicated()]
        for tf in CHAIN:
            if tf not in fr:
                continue
            try:
                rows += study_frame(sym, kind, tf, fr, start, rt)
            except Exception as ex:
                print("  %s %s %s: %s" % (kind, sym, tf, ex), flush=True)
        print("  %-6s %-6s frames %-28s rows so far %d  (%.0fs)" % (
            kind, sym, ",".join(t for t in CHAIN if t in fr), len(rows), time.time() - t0), flush=True)
    ev = pd.DataFrame(rows)
    if ev.empty:
        sys.exit("  no events")
    for k, v in pd.DataFrame([bucket(r) for r in rows]).items():
        ev[k] = v.values
    os.makedirs("validation", exist_ok=True)
    ev.to_csv(OUT_CSV, index=False, compression="gzip")
    res = summarise(ev)
    res["meta"] = dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                       trades=int((ev.null == 0).sum()), null=int((ev.null == 1).sum()),
                       cap_days=CAP_DAYS, ema_tol_atr=EMA_TOL_ATR, class_cost=CLASS_COST, years=YEARS,
                       window_start=str(start.date()), seconds=int(time.time() - t0))
    import json
    json.dump(res, open(OUT_JSON, "w"))
    print("\n  TREND STUDY  %d names, %d higher-low entries, %d null entries  (%.0fs)" % (
        len(names), res["meta"]["trades"], res["meta"]["null"], time.time() - t0))
    print("  %-5s %7s  %8s %8s %8s  %5s %5s  %6s %5s" % ("tf", "n", "ride$", "null$", "drift", "win", "newHH", "held", "legs"))
    for tf in CHAIN:
        b = res["by_tf"].get(tf); nb = res["null_by_tf"].get(tf)
        if not b:
            continue
        print("  %-5s %7d  %+7.2f%% %+7.2f%% %+7.2f%%  %4.0f%% %4.0f%%  %6.0f %5.1f" % (
            tf, b["n"], 100 * b["ret"], 100 * (nb["ret"] if nb else 0), 100 * b["drift"],
            100 * b["win"], 100 * b["new_hh"], b["held"], b["legs"]))
    print("\n  conditions that hold in every era and every class (edge over drift):")
    for cond, vals in res["conditions"].items():
        for val, b in vals.items():
            if b["holds"] and b["edge"] > 0.002:
                print("    %-52s %-24s n=%6d  ret %+.2f%%  edge %+.2f%%  newHH %.0f%%  null %s" % (
                    cond, val, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["new_hh"],
                    "%+.2f%%" % (100 * b["null_ret"]) if b["null_ret"] is not None else "-"))


if __name__ == "__main__":
    main()
