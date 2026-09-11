"""panel_v2.py -- the trend grammar with the two graded amendments.

NOT wired into anything. It exists to be scored against (a) the user's
1,636 painted bars and (b) the 24 approved charts, by trend_v2_score.py.
Only if it wins both does it touch panel.py.

Amendment 1 -- RESUMPTION IS CHEAPER THAN BIRTH
    v1: any death resets the grammar; rebirth needs a fresh confirming PAIR
    (HL+HH or LH+LL), which left the engine mute through the middle of
    obvious trends (chart 1: DOWN x42, one bounce, FLAT x18 while printing
    fresh LH LL pairs).
    v2: when a trend dies, it leaves a resumption level -- its own extreme
    (the top of the dead uptrend, the bottom of the dead downtrend). While
    no other trend has formed, a single new pivot BEYOND that extreme
    resumes the old trend on the spot. New trends still pay full price;
    resumed trends show their receipt.

Amendment 2 -- A BALANCE THAT EXISTS
    v1: BALANCE required four alternating contained pivots and fired on
    0.4% of history; it matched 2 of the user's 156 painted EQ bars.
    v2: the last four pivots all inside a BAND_ATR-wide band = BALANCE.
    The band is frozen at birth; a close or pivot beyond its edges ends it.

Everything else -- pivot detection, labels, kills by contrary pivots,
close-below-the-HL death -- is byte-for-byte v1 semantics.
"""

import numpy as np

import panel as P

BAND_ATR = 2.5      # dead: the band experiment lost the trial
RESUME = True       # owner verdict 2026-08-31 (ZBH): resumption's one-pivot
                    # revival is 'only 2 pivots, shouldnt count' -- OFF


def trend_state_v2(df, PIV=P.PIVOT_BARS, at_formation=False):
    c = df["Close"].values.astype(float)
    n = len(c)
    seq = P.zigzag(df, PIV)
    atr = P._atr(df)
    state = np.array(["FLAT"] * n, dtype=object)
    hl_arr = np.full(n, np.nan)
    lh_arr = np.full(n, np.nan)

    cur = "FLAT"
    lows, highs = [], []
    piv_prices = []          # every pivot price, for the EQ band
    recent = []
    last_hl = np.nan
    last_lh = np.nan
    resume = None            # ("UP"|"DOWN", extreme price) left by a death
    band = None              # (lo, hi) frozen at BALANCE birth
    last4 = []               # last 4 labels, never reset -- the EQ's memory
    # the trend's own extreme, tracked live -- NOT highs[-1] at death, which
    # by then is the killing LH itself and would make resumption too cheap
    trend_ext = np.nan
    k = 0

    def die(to_resume):
        nonlocal cur, recent, resume, band, trend_ext
        if cur in ("UP", "DOWN") and to_resume and np.isfinite(trend_ext):
            resume = (cur, trend_ext)
        else:
            resume = None
        # a RANGE resolving keeps its label memory: the breakout pivot plus
        # the range's own HLs/LHs form the new trend's base, exactly as a
        # chart reader uses them. Only contrary-pivot trend deaths wipe.
        if cur != "BALANCE":
            recent = []
        cur, band = "FLAT", None
        trend_ext = np.nan

    for i in range(n):
        while k < len(seq) and seq[k][1 if at_formation else 0] <= i:
            _, _, price, kind = seq[k]
            k += 1
            tol_p = P.SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
            if kind == "low":
                prev = lows[-1] if lows else np.nan
                lab = (("HL" if price > prev + tol_p else
                        "LL" if price < prev - tol_p else "EL")
                       if np.isfinite(prev) else None)
                lows.append(price)
            else:
                prev = highs[-1] if highs else np.nan
                lab = (("HH" if price > prev + tol_p else
                        "LH" if price < prev - tol_p else "EH")
                       if np.isfinite(prev) else None)
                highs.append(price)
            piv_prices.append(price)
            if len(piv_prices) > 4:
                piv_prices = piv_prices[-4:]
            if lab is None:
                continue

            if cur == "BALANCE":
                # the RANGE's walls are the pattern's own extremes. An HH or
                # LL only resolves the range if it lands BEYOND them -- an
                # inside-the-walls HH resolves nothing ('a 2 candle blue is
                # just stupid')
                if (lab in ("HH", "LL") and band
                        and not (band[0] - tol_p <= price <= band[1] + tol_p)):
                    die(False)
            else:
                kills = {"UP": ("LL", "LH"),
                         "DOWN": ("HH", "HL")}.get(cur, ())
                if lab in kills:
                    die(True)

            recent.append(lab)
            if len(recent) > 6:
                recent = recent[-6:]
            # labels are FACTS about structure; deaths must not erase them.
            # v1's EQ starved because `recent` resets on every kill, and in a
            # range the phantom birth/kill cycle wiped the HL LH pattern two
            # pivots in (chart 4: literal HL LH HL LH, engine never called it)
            last4.append(lab)
            if len(last4) > 4:
                last4 = last4[-4:]

            if cur == "FLAT":
                # AMENDMENT 1: one pivot beyond the dead trend's extreme
                # resumes it
                if (RESUME and resume and resume[0] == "UP"
                        and kind == "high" and price > resume[1] + tol_p):
                    cur = "UP"
                elif (RESUME and resume and resume[0] == "DOWN"
                        and kind == "low" and price < resume[1] - tol_p):
                    cur = "DOWN"
                elif "HL" in recent and "HH" in recent:
                    cur = "UP"
                elif "LH" in recent and "LL" in recent:
                    cur = "DOWN"
                elif (sum(last4.count(x) for x in ("HL", "EL")) >= 2
                      and sum(last4.count(x) for x in ("LH", "EH")) >= 2):
                    # the OWNER's EQ, unchanged: HL LH HL LH with EH/EL as
                    # substitutes -- read from the unresettable label window.
                    # The walls are the PATTERN's extremes, frozen at birth
                    cur = "BALANCE"
                    if len(piv_prices) >= 4:
                        band = (min(piv_prices), max(piv_prices))
                if cur in ("UP", "DOWN"):
                    resume = None
                    band = None
                    trend_ext = (highs[-1] if cur == "UP" and highs else
                                 lows[-1] if cur == "DOWN" and lows else np.nan)
                elif cur == "BALANCE":
                    resume = None
            if cur == "UP" and lows:
                last_hl = lows[-1]
                if kind == "high" and (not np.isfinite(trend_ext)
                                       or price > trend_ext):
                    trend_ext = price
            elif cur == "DOWN" and highs:
                last_lh = highs[-1]
                if kind == "low" and (not np.isfinite(trend_ext)
                                      or price < trend_ext):
                    trend_ext = price

        tol = P.SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
        if cur == "UP" and np.isfinite(last_hl) and c[i] < last_hl - tol:
            die(True)
        elif cur == "DOWN" and np.isfinite(last_lh) and c[i] > last_lh + tol:
            die(True)
        elif cur == "BALANCE" and band:
            # a close beyond the pattern's walls ends the range
            if c[i] > band[1] + tol or c[i] < band[0] - tol:
                die(False)

        state[i] = cur
        hl_arr[i] = last_hl if cur == "UP" else np.nan
        lh_arr[i] = last_lh if cur == "DOWN" else np.nan

    return state, hl_arr, lh_arr


def display_state_v2(df, PIV=P.PIVOT_BARS):
    """v2 causal states + the SAME backfill pass v1's display uses: each
    confirmed trend extends back to its anchoring pivots, never across a
    contradicting label; BALANCE extends back over its four banded pivots."""
    state, hl, lh = trend_state_v2(df, PIV, at_formation=True)
    out = state.copy()
    seq = P.zigzag(df, PIV)
    lows = [j for _, j, _, kind in seq if kind == "low"]
    highs = [j for _, j, _, kind in seq if kind == "high"]
    allp = [j for _, j, _, _ in seq]
    atr = P._atr(df)
    labelled = []
    prev_lo = prev_hi = np.nan
    for _, j, price, kind in seq:
        t = P.SAME_LEVEL_ATR * (atr[j] if np.isfinite(atr[j]) else 0.0)
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
            continue
        if state[i] == "BALANCE":
            pat = [b for b, lab in labelled if b <= i and lab in ("HL", "LH")]
            if len(pat) < 4:
                continue
            for b in range(pat[-4], i):
                if out[b] == "FLAT":
                    out[b] = "BALANCE"
            continue
        piv = lows if state[i] == "UP" else highs
        prior = [j for j in piv if j <= i]
        if len(prior) < 2:
            continue
        anchor = prior[-2]
        bad = ("LL", "LH") if state[i] == "UP" else ("HH", "HL")
        for b, lab in labelled:
            if anchor <= b < i and lab in bad:
                anchor = b + 1
        for b in range(anchor, i):
            if out[b] == "FLAT":
                out[b] = state[i]
    return out, hl, lh
