"""
panel.py -- multi-timeframe trend lights.

    python panel.py BTC-USD              full panel, all timeframes
    python panel.py GLD SLV CVX          several symbols
    python panel.py --watchlist          everything in watchlist.txt
    python panel.py --scan               broad scan, daily-derived timeframes
    python panel.py --validate           does the trend state actually persist?

THE LIGHTS
    GREEN   uptrend    higher highs and higher lows, and the last higher low
                       has NOT been broken
    RED     downtrend  lower highs and lower lows, and the last lower high has
                       NOT been broken
    YELLOW  neither    structure is mixed, or the prevailing trend was just
                       invalidated

The trend definition IS the exit rule, by design: an uptrend lasts until price
breaks the low of the last higher low. So a light turning from green to yellow
is the signal to be out. Same logic inverted for shorts.

TIMEFRAMES        3M  M  W  D  4H  1H  30M  15M  5M

DATA REALITY, stated plainly
    3M / M / W / D    daily bars, 16+ years -- can be displayed AND backtested
    4H / 1H           hourly bars, 730 days -- displayed and backtested
    30M / 15M / 5M    60 days only. Enough to show the CURRENT state honestly,
                      not enough to validate anything historically. They are
                      displayed and marked with a dot.

Each row also shows where price sits against the EMA12 on that timeframe, and
the exact price that would invalidate the trend -- which is your stop level for
that timeframe.
"""

import argparse
import os
import sys
import warnings

import weakref

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
PIVOT_BARS = 2
MIN_PIVOT_ATR = 1.0     # a pivot leg must move this many ATR to register
SAME_LEVEL_ATR = 0.15   # two pivots closer than this are the SAME level
LOOKBACK_PIVOTS = 2     # a break must clear this many recent pivots

# --- backwards-compatible aliases. A dozen older research scripts still
# import the pre-rename names; they mean exactly the same thing.
PIVOT = PIVOT_BARS
MIN_SWING_ATR = MIN_PIVOT_ATR
LOOKBACK_SWINGS = LOOKBACK_PIVOTS


# label, source interval, resample rule, backtestable
TIMEFRAMES = [
    ("3M",  "1d", "QE",     True),
    ("M",   "1d", "ME",     True),
    ("W",   "1d", "W-FRI",  True),
    ("D",   "1d", None,     True),
    ("4H",  "1h", "4h",     True),
    ("1H",  "1h", None,     True),
    ("30M", "5m", "30min",  False),
    ("15M", "5m", "15min",  False),
    ("5M",  "5m", None,     False),
]


def fetch(sym, interval):
    import yfinance as yf
    kw = dict(progress=False, auto_adjust=False)
    if interval == "1d":
        d = yf.download(sym, start="2005-01-01", end="2026-08-21", **kw)
    elif interval == "1h":
        d = yf.download(sym, interval="1h", period="730d", **kw)
    else:
        d = yf.download(sym, interval="5m", period="60d", **kw)
    d = d.dropna()
    if len(d) < 30:
        return None
    d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d


def resample(d, rule):
    return d if rule is None else d.resample(rule).agg(AGG).dropna()



def _atr(df, n=14):
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    c = df["Close"].values.astype(float)
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().values


def zigzag(df, P=PIVOT_BARS, min_atr=MIN_PIVOT_ATR):
    """
    Alternating pivot sequence, with a MINIMUM SIZE filter.

    Highs and lows must alternate; when two of the same type arrive in a row the
    more extreme replaces the other.

    A pivot must also move at least `min_atr` x ATR from the previous pivot to
    register at all. Without this, tiny wiggles count as structure: SOL printed
    a "higher low" of 78.00 against 76.86 -- 1.5% -- in April 2022, and that was
    enough to label a chart that had fallen from 204 as an uptrend.

    Using ATR rather than a percentage means the same rule works on monthly gold
    and 5-minute crypto without retuning.

    Each pivot is emitted at the bar where it is CONFIRMED (P bars after it
    printed). Returns (confirm_index, pivot_index, price, kind).
    """
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    a = _atr(df)
    n = len(h)
    seq = []
    # The window min/max for EVERY bar at once (2026-09-11). The old version called nanmin/nanmax per bar:
    # 860,000 calls on one 5m crypto frame, and it was the slowest thing in every study.
    win = 2 * P + 1
    lmin = pd.Series(l).rolling(win, center=True, min_periods=1).min().values
    hmax = pd.Series(h).rolling(win, center=True, min_periods=1).max().values
    cand = np.nonzero(((l == lmin) | (h == hmax)) & (np.arange(n) >= P) & (np.arange(n) + P < n))[0]
    for j in cand:
        j = int(j)
        i = j + P
        is_low = l[j] == lmin[j]
        is_high = h[j] == hmax[j]
        if is_low and is_high:
            is_high = False
        kind = "low" if is_low else "high"
        price = l[j] if is_low else h[j]
        thresh = min_atr * (a[j] if np.isfinite(a[j]) and a[j] > 0 else 0.0)

        if seq and seq[-1][3] == kind:
            if (kind == "low" and price < seq[-1][2]) or                (kind == "high" and price > seq[-1][2]):
                seq[-1] = (i, j, price, kind)
            continue
        if seq:
            # DIRECTIONAL leg: a high must sit ABOVE the prior low by the
            # threshold, a low BELOW the prior high. abs() let a bounce
            # whose peak was UNDER the previous trough register as a
            # "high", satisfying alternation and stranding LL markers
            # mid-slope (PENGU 2025-05-03, owner-caught)
            leg = (price - seq[-1][2]) if kind == "high"                 else (seq[-1][2] - price)
            if leg < thresh:
                continue                  # leg too small to be structure
        seq.append((i, j, price, kind))
    return seq


def compression(df, P=PIVOT_BARS, min_pairs=1, require_contraction=True):
    """
    EQUILIBRIUM: HL, LH, HL, LH repeating -- higher lows AND lower highs at the
    same time, with the range narrowing. A coil, not a range and not a pullback.

    min_pairs=1 means two rising lows and two falling highs -- the user's
    'HL LH HL LH'. Deeper convergence than that is a stronger coil, not a
    requirement, so it is reported as `depth` rather than demanded.

    The zone is painted across the WHOLE converging structure, from the first
    pivot in the sequence to the bar where price finally leaves the coil --
    not just the bar where the pattern completes.

    An equilibrium ends when price closes outside its boundaries. That break is
    the tradeable event.
    """
    n = len(df)
    c = df["Close"].values.astype(float)
    seq = zigzag(df, P)

    in_eq = np.zeros(n, dtype=bool)
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    mid = np.full(n, np.nan)
    depth = np.zeros(n, dtype=int)
    resolved = np.zeros(n, dtype=int)

    # index the pivots so we can walk them
    lows = [(conf, j, price) for conf, j, price, k in seq if k == "low"]
    highs = [(conf, j, price) for conf, j, price, k in seq if k == "high"]

    for li in range(len(lows) - 1, 0, -1):
        # how many converging pairs end at this low?
        hi_idx = [x for x in range(len(highs)) if highs[x][0] <= lows[li][0]]
        if len(hi_idx) < 2:
            continue
        hj = hi_idx[-1]
        d = 0
        while (li - d - 1 >= 0 and hj - d - 1 >= 0 and
               lows[li - d][2] > lows[li - d - 1][2] and
               highs[hj - d][2] < highs[hj - d - 1][2]):
            d += 1
        if d < min_pairs:
            continue
        top, bot = highs[hj][2], lows[li][2]
        if require_contraction:
            if (top - bot) >= (highs[hj - 1][2] - lows[li - 1][2]):
                continue
        # the structure spans from the earliest pivot in the run...
        start = min(lows[li - d][1], highs[hj - d][1])
        confirm = max(lows[li][0], highs[hj][0])
        # ...forward until price closes outside the coil
        end = n - 1
        for i in range(confirm, n):
            if c[i] > top or c[i] < bot:
                resolved[i] = 1 if c[i] > top else -1
                end = i - 1
                break
        if end < start:
            continue
        # Enter the coil the first time price is actually inside it, then paint
        # forward and STOP the moment price leaves. Painting the whole span
        # blindly let a 9% three-day drop sit inside a "balance" whose floor was
        # 2,000 above it, because overlapping coils overwrote one another.
        first_in = None
        for b in range(start, end + 1):
            if bot <= c[b] <= top:
                first_in = b
                break
        if first_in is None:
            continue
        for b in range(first_in, end + 1):
            if not (bot <= c[b] <= top):
                resolved[b] = 1 if c[b] > top else -1
                break
            in_eq[b] = True
            hi[b] = top
            lo[b] = bot
            mid[b] = (top + bot) / 2.0
            depth[b] = 2 * d + 2
    return in_eq, hi, lo, mid, depth, resolved


def balance_zones(df, n=20, er_max=0.30):
    """Kept for the chart module's signature. Delegates to compression()."""
    a, b, c_, d, e, _r = compression(df)
    return a, b, c_, d, e.astype(float)


def display_state(df, P=PIVOT_BARS):
    """The shading a chart reader would draw, looking back.

    trend_state is CAUSAL: at every bar it only knows what had happened by that
    bar, so a trend only turns green once enough pivots have confirmed it, and
    the run-up before that stays unshaded. That is the honest answer for a
    signal and the wrong answer for a picture -- the eye says "the uptrend
    started at that low", not "the uptrend started once I could prove it".

    So this takes the causal states and extends each confirmed trend BACK to the
    pivot that anchors it: for an uptrend, the earlier of the two lows whose
    relationship made the higher low. Only unshaded bars get filled. A stretch
    that was genuinely a downtrend at the time is never repainted green.

    USE THE RIGHT ONE.
        trend_state    signals, backtests, anything acted on
        display_state  charts, and judging whether we read a chart the same way

    This one looks ahead by construction. Feeding it to a backtest would leak
    the future into every entry.
    """
    state, hl, lh = trend_state(df, P, at_formation=True)
    out = state.copy()
    seq = zigzag(df, P)
    lows = [j for _, j, _, kind in seq if kind == "low"]
    highs = [j for _, j, _, kind in seq if kind == "high"]

    # label every pivot the same way trend_state does, so the backfill can see
    # which ones contradict the trend it is extending
    atr = _atr(df)
    labelled = []
    prev_lo = prev_hi = np.nan
    for _, j, price, kind in seq:
        t = SAME_LEVEL_ATR * (atr[j] if np.isfinite(atr[j]) else 0.0)
        if kind == "low":
            if np.isfinite(prev_lo):
                labelled.append((j, "HL" if price > prev_lo + t else
                                 "LL" if price < prev_lo - t else "EL"))
            prev_lo = price
        else:
            if np.isfinite(prev_hi):
                labelled.append((j, "HH" if price > prev_hi + t else
                                 "LH" if price < prev_hi - t else "EH"))
            prev_hi = price

    for i in range(len(state)):
        if state[i] not in ("UP", "DOWN", "BALANCE"):
            continue
        if i > 0 and state[i - 1] == state[i]:
            continue                      # only act on the first bar of a run

        if state[i] == "BALANCE":
            # A range confirms on its FOURTH pivot, so shading forward from
            # there leaves the other three outside the block -- an equilibrium
            # drawn around a single HL. Extend it back to the first pivot of the
            # HL/LH sequence so the block actually contains the pattern.
            pat = [b for b, lab in labelled if b <= i and lab in ("HL", "LH")]
            if len(pat) < 4:
                continue
            for b in range(pat[-4], i):
                if out[b] == "FLAT":
                    out[b] = "BALANCE"
            continue

        # Anchor on the two pivots that actually FORM this trend -- the last
        # HL and HH for an uptrend. Using "the second most recent pivot low"
        # reached back past the pattern and shaded candles from before the
        # first pivot was even identified.
        piv = lows if state[i] == "UP" else highs
        prior = [j for j in piv if j <= i]
        if len(prior) < 2:
            continue
        anchor = prior[-2]
        # Never paint back ACROSS a pivot that contradicts the trend. Without
        # this the fill walks past lower highs and lower lows and shades BTC's
        # July 2026 chop green -- repainting exactly the rot the causal engine
        # was careful not to call.
        bad = ("LL", "LH") if state[i] == "UP" else ("HH", "HL")
        for b, lab in labelled:
            if anchor <= b < i and lab in bad:
                anchor = b + 1
        for b in range(anchor, i):
            if out[b] == "FLAT":
                out[b] = state[i]
    return out, hl, lh


def tight_levels(df):
    """The MOST RECENT pivot low / pivot high, as opposed to what trend_state
    reports as the invalidation level.

    trend_state deliberately invalidates on the lowest of the last two pivot
    lows: with a single pivot, one bounce inside SOL's 2022 collapse registered
    as an uptrend and two regression cases failed. That conservatism is right
    for deciding WHETHER a trend is alive, but it puts the reported level a full
    pivot behind price -- a median 11.8% away, versus 7.2% for the last pivot
    alone -- which is too loose to trade off.

    So this returns the tighter reading separately. The two answer different
    questions and should not be the same number:

        trend_state's level   what would flip the state to DOWN
        tight_levels's level  the low of the last higher low, the stated exit

    The tight level can sit ABOVE price while the state is still UP. That is not
    an error: it means the last higher low has already given way even though the
    trend has not formally broken.
    """
    seq = zigzag(df)
    n = len(df)
    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    last_lo = np.nan
    last_hi = np.nan
    k = 0
    for i in range(n):
        while k < len(seq) and seq[k][0] <= i:
            _, _, price, kind = seq[k]
            if kind == "low":
                last_lo = price
            else:
                last_hi = price
            k += 1
        lo[i] = last_lo
        hi[i] = last_hi
    return lo, hi

def trend_state(df, P=PIVOT_BARS, at_formation=False):
    """UP / DOWN / BALANCE / FLAT, driven by the SEQUENCE OF PIVOT LABELS.

    Earlier versions ran the state off price crossing levels and kept getting
    graded wrong on real charts. The rules below are the ones stated by the
    person reading them, and they are about labels, not levels.

    ENTRY -- a trend needs two pivots, not one
        UP        a HL and a HH, with nothing invalidating in between
        DOWN      a LH and a LL
        BALANCE   HL, LH, HL, LH -- four pivots, lows rising into falling
                  highs. Two pivots is not a range, it is one pullback
    A single pivot is never enough. "An uptrend needs at least 2 pivots of HL
    and HH."

    DEATH -- immediate, on the pivot that contradicts the pattern
        UP dies on a LL or a LH
        DOWN dies on a HH or a HL
        BALANCE dies on a HH or a LL, which is what resolves the range
    It dies the moment that pivot confirms. It does not linger, and it does not
    wait for price to travel somewhere.

    UP also dies if price simply closes below the last higher low, without
    waiting for a pivot to form. That is the stated exit rule.

    WHAT DEATH LEADS TO
        FLAT -- unshaded. Not the opposite trend, not balance. Those need their
        own pivots. Unshaded is a real answer and it is common.

    Labels use SAME_LEVEL_ATR tolerance, so a pivot within noise of the previous
    one is EH / EL -- equal, not structure, and it neither builds nor kills a
    trend.
    """
    c = df["Close"].values.astype(float)
    n = len(c)
    seq = zigzag(df, P)
    atr = _atr(df)
    state = np.array(["FLAT"] * n, dtype=object)
    hl = np.full(n, np.nan)
    lh = np.full(n, np.nan)

    cur = "FLAT"
    lows, highs = [], []
    recent = []          # pivot labels since the last invalidation
    last_hl = np.nan     # price of the higher low holding an uptrend up
    last_lh = np.nan
    k = 0
    for i in range(n):
        # A pivot is CONFIRMED PIVOT_BARS after it forms. Causally the state
        # cannot react until then. But the chart draws the label at the bar the
        # pivot FORMED, so a display built on confirmation bars shades two
        # candles late -- "first LL should immediately kill the uptrend green,
        # why does it wait another candle after??". display_state passes
        # at_formation=True so label and shading change on the same bar.
        while k < len(seq) and seq[k][1 if at_formation else 0] <= i:
            _, _, price, kind = seq[k]
            k += 1
            tol_p = SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
            if kind == "low":
                prev = lows[-1] if lows else np.nan
                lab = ("HL" if price > prev + tol_p else
                       "LL" if price < prev - tol_p else "EL")                     if np.isfinite(prev) else None
                lows.append(price)
            else:
                prev = highs[-1] if highs else np.nan
                lab = ("HH" if price > prev + tol_p else
                       "LH" if price < prev - tol_p else "EH")                     if np.isfinite(prev) else None
                highs.append(price)
            if lab is None:
                continue

            kills = {"UP": ("LL", "LH"), "DOWN": ("HH", "HL"),
                     "BALANCE": ("HH", "LL")}.get(cur, ())
            if lab in kills:
                cur = "FLAT"
                recent = []
            recent.append(lab)
            if len(recent) > 6:
                recent = recent[-6:]

            if cur == "FLAT":
                if "HL" in recent and "HH" in recent:
                    cur = "UP"
                elif "LH" in recent and "LL" in recent:
                    cur = "DOWN"
                elif (sum(recent.count(x) for x in ("HL", "EL")) >= 2
                      and sum(recent.count(x) for x in ("LH", "EH")) >= 2):
                    # An equal high bounds a range exactly as a lower high does,
                    # and an equal low as a higher low: "EH and EL make it an EQ
                    # if it would have otherwise been an eq if it was a lh or
                    # hl". Counting only strict HL/LH missed flat-topped ranges.
                    # An equal high bounds a range exactly as a lower high does,
                    # and an equal low as a higher low: "EH and EL make it an EQ
                    # if it would have otherwise been an eq if it was a lh or
                    # hl". Counting only strict HL/LH missed flat-topped ranges.
                    # "an eq is HL LH HL LH repeating" -- FOUR pivots, not two.
                    # Requiring only one of each produced one-bar equilibriums
                    # that formed and were invalidated on the very next candle.
                    cur = "BALANCE"
            if cur == "UP":
                last_hl = lows[-1]
            elif cur == "DOWN":
                last_lh = highs[-1]

        tol = SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
        # the stated exit: an uptrend ends when price closes under the last
        # higher low, without waiting for a pivot to confirm it
        if cur == "UP" and np.isfinite(last_hl) and c[i] < last_hl - tol:
            cur, recent = "FLAT", []
        elif cur == "DOWN" and np.isfinite(last_lh) and c[i] > last_lh + tol:
            cur, recent = "FLAT", []
        elif cur == "BALANCE":
            # "eq should break if any candle breaks the last LH or HL" -- a
            # range ends when price leaves it, without waiting for the pivot
            # that would confirm the breakout.
            hi_edge = highs[-1] if highs else np.nan
            lo_edge = lows[-1] if lows else np.nan
            if ((np.isfinite(hi_edge) and c[i] > hi_edge + tol)
                    or (np.isfinite(lo_edge) and c[i] < lo_edge - tol)):
                cur, recent = "FLAT", []

        state[i] = cur
        hl[i] = last_hl if cur == "UP" else np.nan
        lh[i] = last_lh if cur == "DOWN" else np.nan

    
    return state, hl, lh


LIGHT = {"UP": "GREEN ", "DOWN": "RED   ", "FLAT": "YELLOW",
         "BALANCE": "BLUE  "}


def panel_for(sym, intraday=True):
    cache = {}
    need = {"1d"} | ({"1h", "5m"} if intraday else set())
    for iv in need:
        try:
            cache[iv] = fetch(sym, iv)
        except Exception:
            cache[iv] = None

    rows = []
    for lab, src, rule, testable in TIMEFRAMES:
        if src not in cache or cache[src] is None:
            continue
        df = resample(cache[src], rule)
        if len(df) < 4 * PIVOT_BARS + 6:
            continue
        st, hl, lh = trend_state(df)
        c = df["Close"].values.astype(float)
        e12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
        px = c[-1]
        s = st[-1]
        inb, bhi, blo, beq, er = balance_zones(df)
        inval = hl[-1] if s == "UP" else (lh[-1] if s == "DOWN" else np.nan)
        rows.append(dict(tf=lab, state=s, price=px,
                         eqmid=beq[-1], eq_hi=bhi[-1], eq_lo=blo[-1], effic=er[-1],
                         ema12=e12[-1], above=px > e12[-1],
                         inval=inval,
                         dist=(px / inval - 1) if np.isfinite(inval) else np.nan,
                         bars=len(df), testable=testable))
    return pd.DataFrame(rows)


def show(sym, R):
    if R.empty:
        print("  %s -- no data" % sym)
        return
    ups = (R.state == "UP").sum()
    dns = (R.state == "DOWN").sum()
    bal = (R.state == "BALANCE").sum()
    print("\n" + "=" * 74)
    print("  %-12s   %d UP, %d DOWN, %d in BALANCE, %d neutral"
          % (sym, ups, dns, bal, len(R) - ups - dns - bal))
    print("=" * 74)
    print("  %-5s %-8s %11s %9s %13s %10s %7s %11s"
          % ("TF", "trend", "price", "vs EMA12", "invalidates at", "distance",
             "effic", "EQ level"))
    for _, r in R.iterrows():
        mark = "" if r.testable else " *"
        inval = "%11.4f" % r.inval if np.isfinite(r.inval) else "          -"
        dist = "%+9.2f%%" % (100 * r.dist) if np.isfinite(r.dist) else "        -"
        eqv = float(r["eqmid"]) if pd.notna(r["eqmid"]) else float("nan")
        erv = float(r["effic"]) if pd.notna(r["effic"]) else float("nan")
        eq = "%11.4f" % eqv if np.isfinite(eqv) else "          -"
        print("  %-5s %-8s %11.4f %9s %13s %10s %6.2f %11s%s"
              % (r.tf, LIGHT[r.state].strip(), r.price,
                 "above" if r.above else "below", inval, dist,
                 erv, eq, mark))
    if (~R.testable).any():
        print("  * 60 days of history only -- state is real, not back-testable")


def validate():
    """Does the state persist, as required? Measures run length and coverage."""
    syms = ["BTC-USD", "ETH-USD", "SPY", "QQQ", "AAPL", "GLD", "SLV", "CVX",
            "TSLA", "NVDA"]
    print("=" * 74)
    print("  DOES THE TREND STATE PERSIST?")
    print("  the requirement was: 'true for most of the uptrend/downtrend'")
    print("=" * 74)
    print("  %-6s %10s %10s %10s %12s %12s"
          % ("TF", "% in UP", "% in DOWN", "% flat", "avg UP run", "avg DOWN run"))
    for lab, src, rule, testable in TIMEFRAMES:
        if src != "1d":
            continue
        up_p, dn_p, fl_p, up_r, dn_r = [], [], [], [], []
        for s in syms:
            d = fetch(s, "1d")
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 60:
                continue
            st, _, _ = trend_state(df)
            up_p.append((st == "UP").mean())
            dn_p.append((st == "DOWN").mean())
            fl_p.append((st == "FLAT").mean())
            runs = pd.Series(st)
            grp = (runs != runs.shift()).cumsum()
            rl = runs.groupby(grp).agg(["first", "size"])
            up_r.append(rl[rl["first"] == "UP"]["size"].mean())
            dn_r.append(rl[rl["first"] == "DOWN"]["size"].mean())
        if up_p:
            print("  %-6s %9.0f%% %9.0f%% %9.0f%% %11.1f %11.1f"
                  % (lab, 100 * np.mean(up_p), 100 * np.mean(dn_p),
                     100 * np.mean(fl_p), np.nanmean(up_r), np.nanmean(dn_r)))
    print("\n  avg run = how many bars the light stays on before changing.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--watchlist", action="store_true")
    ap.add_argument("--no-intraday", action="store_true")
    a = ap.parse_args()

    if a.validate:
        validate()
        return
    syms = a.symbols
    if a.watchlist:
        if not os.path.exists("watchlist.txt"):
            sys.exit("create watchlist.txt, one symbol per line")
        syms = [x.strip() for x in open("watchlist.txt") if x.strip()]
    if not syms:
        syms = ["BTC-USD", "GLD", "SLV", "CVX", "SPY"]
    for s in syms:
        show(s.upper(), panel_for(s.upper(), not a.no_intraday))


if __name__ == "__main__":
    main()
