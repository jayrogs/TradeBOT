"""exit_managers2.py -- twenty MORE ways to manage the ride (owner 2026-09-07:
"try like 20 more unique but justified methodologies of selling").

Same entry (second higher low, next open), same accounting as exit_managers.py:
sold at the open after the trigger bar. The first batch said "looser wins", so
this batch pushes on that from every side: how wide, measured off what, does
it tighten with time or profit, percent instead of normal bars, a slower
average, a stall clock, fixed targets, scaling out, the NEXT chart's line, a
volume climax, and pure structure (second lower high, a lower low).

R = the risk at entry (buy price minus the higher low, floored at one normal
bar). "peak" = highest close since the buy. "line" = last higher low, raised.
"""
import numpy as np

LABELS2 = [
    "chandelier 5 bars (the batch-1 winner, for reference)",
    "chandelier 8 bars under the highest close",
    "chandelier 12 bars under the highest close",
    "chandelier 5 bars, but a WICK under it (not a close)",
    "chandelier 5 bars under the highest HIGH (not close)",
    "chandelier that tightens with time: 5 bars, minus 0.05 a bar, floor 2",
    "chandelier that tightens with profit: 5 bars, 3 once up 5R, 2 once up 10R",
    "trail 8% under the highest close (percent, not bars)",
    "trail 15% under the highest close",
    "close under the 20 EMA minus 2 bars (a volatility band)",
    "close under the 50 EMA",
    "the line, then two down closes in a row once up 3R",
    "stall: no new highest close for 20 bars",
    "the line, or stall: no new highest close for 30 bars",
    "the line, or take profit at 5R",
    "chandelier 5, or take profit at 10R",
    "half off at 3R, chandelier 5 on the rest",
    "the NEXT chart's last higher low breaks (wick half a bar)",
    "the line, or a volume climax (3x average volume, closed in the lower half)",
    "the second lower high (pure structure)",
    "a lower low confirms (pure structure)",
    "close under the 20-bar low",
]


def prep(c, o, h, l, v, a14, ema_fn):
    ema20 = ema_fn(c, 20); ema50 = ema_fn(c, 50)
    n = len(c)
    low20 = np.full(n, np.nan)
    for i in range(20, n):
        low20[i] = l[i - 20:i].min()
    vavg = np.full(n, np.nan)
    if v is not None:
        for i in range(20, n):
            vavg[i] = v[i - 20:i].mean()
    return dict(ema20=ema20, ema50=ema50, low20=low20, vavg=vavg)


def run_all2(c, o, l, h, v, a14, ind2, hi_lvl, lows, lcis, highs, hcis, e, level0, n, cap, day):
    import bisect
    fill = o[e]
    atr0 = a14[e - 1] if e >= 1 and np.isfinite(a14[e - 1]) else 0.0
    R = max(fill - level0, atr0)
    level = level0; peak = c[e]; peak_hi = h[e]; peak_bar = e; worst = 0.0
    p = bisect.bisect_right(lcis, e - 1); q = bisect.bisect_right(hcis, e - 1)
    ema20 = ind2["ema20"]; ema50 = ind2["ema50"]; low20 = ind2["low20"]; vavg = ind2["vavg"]
    alive = {lab: True for lab in LABELS2}; out = {}; n_alive = len(LABELS2)
    lh_count = 0; half_taken = False; half_px = None
    trailing3 = False

    def done(lab, k, why, px=None):
        nonlocal n_alive
        if alive[lab]:
            alive[lab] = False; n_alive -= 1
            price = o[k + 1] if px is None else px
            if lab.startswith("half off") and half_taken:
                price = 0.5 * half_px + 0.5 * price          # blended sale price
            out[lab] = (k, price, why, worst)

    for k in range(e, n - 1):
        new_ll = False; new_lh = False
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j >= e and lab in ("HL", "EL") and price > level:
                level = price
            if j >= e and lab == "LL":
                new_ll = True
        while q < len(highs) and highs[q][0] <= k:
            ci, j, price, lab = highs[q]; q += 1
            if j >= e and lab == "LH":
                new_lh = True; lh_count += 1
        worst = min(worst, c[k] / fill - 1)
        if c[k] > peak:
            peak = c[k]; peak_bar = k
        peak_hi = max(peak_hi, h[k])
        atr = a14[k] if np.isfinite(a14[k]) else 0.0
        up_r = (c[k] - fill) / R if R > 0 else 0.0
        if up_r >= 3:
            trailing3 = True
        wick = l[k] < level - 0.5 * atr
        # half off at 3R: the partial happens on the bar the high reaches it
        if not half_taken and h[k] >= fill + 3 * R:
            half_taken = True; half_px = fill + 3 * R
        # ---- chandeliers
        if c[k] < peak - 5 * atr:
            done("chandelier 5 bars (the batch-1 winner, for reference)", k, "chandelier hit")
            done("chandelier 5, or take profit at 10R", k, "chandelier hit")
            done("half off at 3R, chandelier 5 on the rest", k, "chandelier hit")
        if c[k] < peak - 8 * atr:
            done("chandelier 8 bars under the highest close", k, "chandelier hit")
        if c[k] < peak - 12 * atr:
            done("chandelier 12 bars under the highest close", k, "chandelier hit")
        if l[k] < peak - 5 * atr:
            done("chandelier 5 bars, but a WICK under it (not a close)", k, "chandelier wicked")
        if c[k] < peak_hi - 5 * atr:
            done("chandelier 5 bars under the highest HIGH (not close)", k, "chandelier hit")
        width_t = max(2.0, 5.0 - 0.05 * (k - e))
        if c[k] < peak - width_t * atr:
            done("chandelier that tightens with time: 5 bars, minus 0.05 a bar, floor 2", k, "chandelier hit (%.1f bars)" % width_t)
        width_p = 2.0 if up_r >= 10 else 3.0 if up_r >= 5 else 5.0
        if c[k] < peak - width_p * atr:
            done("chandelier that tightens with profit: 5 bars, 3 once up 5R, 2 once up 10R", k, "chandelier hit (%g bars)" % width_p)
        if c[k] < peak * 0.92:
            done("trail 8% under the highest close (percent, not bars)", k, "8% trail hit")
        if c[k] < peak * 0.85:
            done("trail 15% under the highest close", k, "15% trail hit")
        # ---- averages
        if c[k] < ema20[k] - 2 * atr:
            done("close under the 20 EMA minus 2 bars (a volatility band)", k, "closed under the band")
        if c[k] < ema50[k]:
            done("close under the 50 EMA", k, "closed under the 50 EMA")
        # ---- the line family
        if wick:
            done("the line, then two down closes in a row once up 3R", k, "higher low broke") if not trailing3 else None
            done("the line, or stall: no new highest close for 30 bars", k, "higher low broke")
            done("the line, or take profit at 5R", k, "higher low broke")
            done("the line, or a volume climax (3x average volume, closed in the lower half)", k, "higher low broke")
        if trailing3 and k >= e + 1 and c[k] < c[k - 1] and c[k - 1] < c[k - 2]:
            done("the line, then two down closes in a row once up 3R", k, "two down closes")
        if k - peak_bar >= 20:
            done("stall: no new highest close for 20 bars", k, "stalled 20 bars")
        if k - peak_bar >= 30:
            done("the line, or stall: no new highest close for 30 bars", k, "stalled 30 bars")
        if h[k] >= fill + 5 * R:
            done("the line, or take profit at 5R", k, "hit 5R", px=fill + 5 * R)
        if h[k] >= fill + 10 * R:
            done("chandelier 5, or take profit at 10R", k, "hit 10R", px=fill + 10 * R)
        # ---- the next chart's line
        if np.isfinite(hi_lvl[k]) and l[k] < hi_lvl[k] - 0.5 * atr:
            done("the NEXT chart's last higher low breaks (wick half a bar)", k, "next chart's higher low broke")
        # ---- volume climax
        if np.isfinite(vavg[k]) and vavg[k] > 0 and v is not None and v[k] > 3 * vavg[k] and (h[k] - l[k]) > 0 and c[k] < l[k] + 0.5 * (h[k] - l[k]):
            done("the line, or a volume climax (3x average volume, closed in the lower half)", k, "volume climax")
        # ---- pure structure
        if new_lh and lh_count >= 2:
            done("the second lower high (pure structure)", k, "second lower high")
        if new_ll:
            done("a lower low confirms (pure structure)", k, "lower low confirmed")
        if np.isfinite(low20[k]) and c[k] < low20[k]:
            done("close under the 20-bar low", k, "closed under the 20-bar low")
        # ---- session end / cap
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            for lab in LABELS2:
                if alive[lab]:
                    done(lab, k, "session end", px=c[k])
            break
        if k - e >= cap:
            for lab in LABELS2:
                if alive[lab]:
                    done(lab, k, "time")
            break
        if n_alive == 0:
            break
    return out
