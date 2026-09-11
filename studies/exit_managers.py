"""exit_managers.py -- twenty ways to manage a trend ride after the same entry.

Owner 2026-09-07: "why dont you try like 10 different ways and see if theres a
better one, use any methods necessary, use new indicators, use whatever you can
think of, if it works it works."

Same entry for all of them (the second higher low, bought at the next open, from
trend_ride.study_frame). Every exit is sold at the NEXT open after the bar that
triggered it (rule 21: the trigger and the price never come from the same bar),
except the end-of-day close on 5m/15m stock charts. One pass over the bars per
entry, every manager checked on each bar, so the run stays cheap.

"the line" = the last higher low, raised each time a new one confirms (an equal
low counts). "wick rule" = a wick half a normal bar under the line.
"""
import numpy as np


def ema(c, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(c)
    out[0] = c[0]
    for i in range(1, len(c)):
        out[i] = a * c[i] + (1 - a) * out[i - 1]
    return out


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    au = np.empty_like(c); ad = np.empty_like(c)
    au[0] = up[:n].mean() if len(c) > n else 0; ad[0] = dn[:n].mean() if len(c) > n else 0
    for i in range(1, len(c)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    rs = au / np.where(ad == 0, np.nan, ad)
    out = 100 - 100 / (1 + rs)
    out[np.isnan(out)] = 100.0
    return out


def psar(h, l, c, af0=0.02, afmax=0.2):
    """Parabolic SAR. Returns the SAR value per bar and +1/-1 direction."""
    n = len(c)
    sar = np.empty(n); d = np.ones(n, dtype=int)
    up = True; af = af0; ep = h[0]; s = l[0]
    for i in range(1, n):
        s = s + af * (ep - s)
        if up:
            s = min(s, l[i - 1], l[i - 2] if i >= 2 else l[i - 1])
            if l[i] < s:
                up = False; s = ep; ep = l[i]; af = af0
            else:
                if h[i] > ep:
                    ep = h[i]; af = min(afmax, af + af0)
        else:
            s = max(s, h[i - 1], h[i - 2] if i >= 2 else h[i - 1])
            if h[i] > s:
                up = True; s = ep; ep = h[i]; af = af0
            else:
                if l[i] < ep:
                    ep = l[i]; af = min(afmax, af + af0)
        sar[i] = s; d[i] = 1 if up else -1
    sar[0] = l[0]
    return sar, d


def supertrend(h, l, c, a14, mult=3.0):
    """+1 while price is above the supertrend band, -1 below."""
    n = len(c)
    hl2 = (h + l) / 2
    ub = hl2 + mult * np.nan_to_num(a14); lb = hl2 - mult * np.nan_to_num(a14)
    fu = ub.copy(); fl = lb.copy(); d = np.ones(n, dtype=int)
    for i in range(1, n):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        if d[i - 1] == 1:
            d[i] = -1 if c[i] < fl[i] else 1
        else:
            d[i] = 1 if c[i] > fu[i] else -1
    return d


def prior_low(l, n):
    """Lowest low of the previous n bars (not counting the bar itself)."""
    out = np.full(len(l), np.nan)
    for i in range(n, len(l)):
        out[i] = l[i - n:i].min()
    return out


def indicators(c, o, h, l, a14):
    """Everything the managers need, once per frame."""
    sar, sard = psar(h, l, c)
    return dict(ema12=ema(c, 12), ema21=ema(c, 21), rsi=rsi(c), sar=sar, sard=sard,
                st=supertrend(h, l, c, a14), low5=prior_low(l, 5), low10=prior_low(l, 10))


LABELS = [
    "the line, wick rule (no trail)",
    "the line, but on a close under it",
    "the line, wick rule 1.5 bars wide",
    "chandelier 3 bars under the high, from the start",
    "chandelier 5 bars under the high, from the start",
    "the line, then chandelier 3 bars once up 3R (replaces the line)",
    "the line, then the previous bar's low once up 3R",
    "the line, then a close under the 12 EMA once up 3R",
    "the line, then a close under the 5-bar low once up 3R",
    "close under the 12 EMA",
    "close under the 21 EMA",
    "two closes in a row under the 12 EMA",
    "parabolic SAR flips down",
    "supertrend (3 bars) flips down",
    "close under the 10-bar low",
    "the line, or the first lower high",
    "the line, and never give it back once up 1R (stop to the buy price)",
    "the line, or sell after a climax bar (3+ bars' range, closed up)",
    "the line, or out after 20 bars if never up 1R",
    "the line, or RSI back under 50 after topping 70",
]


def run_all(c, o, l, h, a14, ind, lows, lcis, highs, hcis, e, level0, n, cap, day):
    """One pass. Returns {label: (exit_bar, exit_price, why, worst)} for every
    manager that exited inside the history; managers that never exit are absent."""
    import bisect
    fill = o[e]
    atr0 = a14[e - 1] if e >= 1 and np.isfinite(a14[e - 1]) else 0.0
    R = max(fill - level0, atr0)
    tgt1 = fill + R; tgt3 = fill + 3 * R
    level = level0; peak = c[e]; worst = 0.0
    p = bisect.bisect_right(lcis, e - 1)
    q = bisect.bisect_right(hcis, e - 1)
    ema12 = ind["ema12"]; ema21 = ind["ema21"]; rsi_ = ind["rsi"]; sard = ind["sard"]; st = ind["st"]
    low5 = ind["low5"]; low10 = ind["low10"]
    alive = {lab: True for lab in LABELS}
    out = {}
    trailing3 = False; up1 = False; rsi_hot = False; new_lh = False
    n_alive = len(LABELS)

    def done(lab, k, why, px=None):
        nonlocal n_alive
        if alive[lab]:
            alive[lab] = False; n_alive -= 1
            out[lab] = (k, o[k + 1] if px is None else px, why, worst)

    for k in range(e, n - 1):
        # the line: raise it on every new higher low / equal low confirmed by now
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j >= e and lab in ("HL", "EL") and price > level:
                level = price
        new_lh = False
        while q < len(highs) and highs[q][0] <= k:
            ci, j, price, lab = highs[q]; q += 1
            if j >= e and lab == "LH":
                new_lh = True
        worst = min(worst, c[k] / fill - 1)
        peak = max(peak, c[k])
        atr = a14[k] if np.isfinite(a14[k]) else 0.0
        if c[k] >= tgt3:
            trailing3 = True
        if c[k] >= tgt1:
            up1 = True
        if rsi_[k] > 70:
            rsi_hot = True
        wick = l[k] < level - 0.5 * atr           # the standard break of the line
        # ---- the managers
        if wick:
            done("the line, wick rule (no trail)", k, "higher low broke")
            done("the line, or the first lower high", k, "higher low broke")
            done("the line, or sell after a climax bar (3+ bars' range, closed up)", k, "higher low broke")
            done("the line, or out after 20 bars if never up 1R", k, "higher low broke")
            done("the line, or RSI back under 50 after topping 70", k, "higher low broke")
            done("the line, and never give it back once up 1R (stop to the buy price)", k, "higher low broke")
            if not trailing3:
                done("the line, then chandelier 3 bars once up 3R (replaces the line)", k, "higher low broke")
                done("the line, then the previous bar's low once up 3R", k, "higher low broke")
                done("the line, then a close under the 12 EMA once up 3R", k, "higher low broke")
                done("the line, then a close under the 5-bar low once up 3R", k, "higher low broke")
        if c[k] < level:
            done("the line, but on a close under it", k, "closed under the higher low")
        if l[k] < level - 1.5 * atr:
            done("the line, wick rule 1.5 bars wide", k, "higher low broke (wide)")
        if c[k] < peak - 3 * atr:
            done("chandelier 3 bars under the high, from the start", k, "chandelier hit")
            if trailing3:
                done("the line, then chandelier 3 bars once up 3R (replaces the line)", k, "chandelier hit")
        if c[k] < peak - 5 * atr:
            done("chandelier 5 bars under the high, from the start", k, "chandelier hit")
        if trailing3 and k > e and c[k] < l[k - 1]:
            done("the line, then the previous bar's low once up 3R", k, "closed under the previous bar's low")
        if c[k] < ema12[k]:
            done("close under the 12 EMA", k, "closed under the 12 EMA")
            if trailing3:
                done("the line, then a close under the 12 EMA once up 3R", k, "closed under the 12 EMA")
            if k > e and c[k - 1] < ema12[k - 1]:
                done("two closes in a row under the 12 EMA", k, "two closes under the 12 EMA")
        if c[k] < ema21[k]:
            done("close under the 21 EMA", k, "closed under the 21 EMA")
        if trailing3 and np.isfinite(low5[k]) and c[k] < low5[k]:
            done("the line, then a close under the 5-bar low once up 3R", k, "closed under the 5-bar low")
        if sard[k] == -1 and k > e:
            done("parabolic SAR flips down", k, "SAR flipped")
        if st[k] == -1 and k > e:
            done("supertrend (3 bars) flips down", k, "supertrend flipped")
        if np.isfinite(low10[k]) and c[k] < low10[k]:
            done("close under the 10-bar low", k, "closed under the 10-bar low")
        if new_lh:
            done("the line, or the first lower high", k, "a lower high showed up")
        if up1 and l[k] < fill:
            done("the line, and never give it back once up 1R (stop to the buy price)", k, "back to the buy price")
        if (h[k] - l[k]) > 3 * atr and c[k] > o[k] and atr > 0:
            done("the line, or sell after a climax bar (3+ bars' range, closed up)", k, "climax bar")
        if k - e >= 20 and not up1:
            done("the line, or out after 20 bars if never up 1R", k, "20 bars, never got going")
        if rsi_hot and rsi_[k] < 50:
            done("the line, or RSI back under 50 after topping 70", k, "RSI fell under 50")
        # session end on fast stock charts: everyone still in sells at the close
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            for lab in LABELS:
                if alive[lab]:
                    done(lab, k, "session end", px=c[k])
            break
        if k - e >= cap:
            for lab in LABELS:
                if alive[lab]:
                    done(lab, k, "time")
            break
        if n_alive == 0:
            break
    return out
