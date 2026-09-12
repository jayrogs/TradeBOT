"""structure.py -- THE BACKBONE. The owner's market-structure grammar, in one
place, in the owner's words. Everything that reads a chart imports from
here: charts, the scanner, the forward log, the tests.

PIVOTS   (panel.zigzag) alternating highs/lows, 2 bars each side, a leg must
         travel >= 1.0 ATR *in its own direction* (a high above the prior
         low, a low below the prior high -- 2026-09-01 fix), same-type
         pivots replace when more extreme. Labels: HH/HL/LH/LL, or EH/EL
         when within SAME_LEVEL_ATR of the previous same-kind pivot.

TRENDS   "im using pivots as HL HH, LH, LL, thats all there is to trends."
  open   an uptrend opens when a HL and a HH have both printed with nothing
         invalidating between them (contrary evidence resets the courtship)
  die    at the EARLIER of: a contrary pivot (LH or LL), or a candle CLOSING
         through the last HL. The executioner -- killer pivot or breaking
         candle -- is never a member of the trend it ends. Downtrend mirror.
  E's    EH / EL neither build, kill, nor move the break level.

EQ       "an eq needs at least 4: HL LH HL LH", EH/EL accepted as
         substitutes. Read from a label memory that trend deaths cannot
         wipe. Edges are LIVING: ceiling = last LH/EH, floor = last HL/EL.
         Dies the instant any candle's WICK pierces an edge ("it was taken
         out by the long wick") -- trends survive wicks, ranges do not.
         A resolved range's pivots are spent: four fresh labels for the
         next one. Ranges live BESIDE trends (overlap is real: ~1% of bars).

TWO CLOCKS, never confused:
  review   spans/washes placed at pivot FORMATION -- how a human reads a
           chart in hindsight. For pictures and grading. Never for signals.
  live     the same grammar processed at pivot CONFIRMATION -- knowable at
           each bar's close. For the scanner, the forward log, any gate.
           Prefix-tested causal.
"""

import numpy as np

import panel as P

E_LABELS = ("EH", "EL", "H", "L")


# ------------------------------------------------------------------ pivots

def pivots(df, min_atr=None):
    """[(confirm_bar, form_bar, price, kind, label), ...] in confirm order."""
    key = "_pivots_%s_%d" % (min_atr, len(df))
    hit = df.attrs.get(key)
    if hit is not None:
        return hit
    seq = (P.zigzag(df) if min_atr is None
           else P.zigzag(df, min_atr=min_atr))
    atr = P._atr(df)
    lows, highs, out = [], [], []
    for ci, j, price, kind in seq:
        tol = P.SAME_LEVEL_ATR * (atr[ci] if np.isfinite(atr[ci]) else 0.0)
        if kind == "low":
            prev = lows[-1] if lows else np.nan
            lab = (("HL" if price > prev + tol else
                    "LL" if price < prev - tol else "EL")
                   if np.isfinite(prev) else "L")
            lows.append(price)
        else:
            prev = highs[-1] if highs else np.nan
            lab = (("HH" if price > prev + tol else
                    "LH" if price < prev - tol else "EH")
                   if np.isfinite(prev) else "H")
            highs.append(price)
        out.append((int(ci), int(j), float(price), kind, lab))
    try:
        df.attrs[key] = out          # studies ask for the same frame's pivots over and over
    except Exception:
        pass
    return out


def labelled_pivots(df, min_atr=None):
    """Compat: [(form_bar, price, kind, label), ...]."""
    return [(j, p, k, lab) for _, j, p, k, lab in pivots(df, min_atr)]


# ------------------------------------------------------------------ spans

def _spans(piv5, n, df, causal):
    # OWNER RULE 2026-09-02: "it doesnt matter what it closes at, trends die
    # on the wick." A low under the last HL (high over the last LH) kills the
    # span -- same physics as ranges. Same noise tolerance as the labels.
    lo_arr = df["Low"].values.astype(float)
    hi_arr = df["High"].values.astype(float)
    atr = P._atr(df)
    spans = []
    cur = None                      # ("UP"|"DOWN", start_bar)
    pend = {}
    lvl = np.nan                    # last HL (in UP) / last LH (in DOWN)
    last_hl = last_lh = np.nan
    prev_b = -1

    def bar_break(j0, j1):
        if not np.isfinite(lvl):
            return None
        for b in range(j0 + 1, min(j1 + 1, n)):
            tol = P.SAME_LEVEL_ATR * (atr[b] if np.isfinite(atr[b]) else 0.0)
            if cur[0] == "UP" and lo_arr[b] < lvl - tol:
                return b
            if cur[0] == "DOWN" and hi_arr[b] > lvl + tol:
                return b
        return None

    for ci, j, price, kind, lab in piv5:
        eb = ci if causal else j    # the bar the event is known / formed
        if cur is not None:
            bb = bar_break(prev_b, eb - 1)
            if bb is not None:
                spans.append((cur[0], cur[1], max(bb - 1, cur[1])))
                cur, pend, lvl = None, {}, np.nan
        prev_b = eb
        if lab in E_LABELS:
            continue
        if lab == "HL":
            last_hl = price
        elif lab == "LH":
            last_lh = price
        if cur is None:
            if lab in ("HL", "HH"):
                pend.pop("LH", None)
                pend.pop("LL", None)
            else:
                pend.pop("HL", None)
                pend.pop("HH", None)
            pend[lab] = eb
            if "HL" in pend and "HH" in pend:
                start = eb if causal else min(pend["HL"], pend["HH"])
                cur, lvl, pend = ("UP", start), last_hl, {}
            elif "LH" in pend and "LL" in pend:
                start = eb if causal else min(pend["LH"], pend["LL"])
                cur, lvl, pend = ("DOWN", start), last_lh, {}
        elif cur[0] == "UP":
            if lab in ("LH", "LL"):
                spans.append(("UP", cur[1], max(eb - 1, cur[1])))
                cur, pend, lvl = None, {lab: eb}, np.nan
            elif lab == "HL":
                lvl = price
        else:
            if lab in ("HH", "HL"):
                spans.append(("DOWN", cur[1], max(eb - 1, cur[1])))
                cur, pend, lvl = None, {lab: eb}, np.nan
            elif lab == "LH":
                lvl = price
    if cur is not None:
        bb = bar_break(prev_b, n - 1)
        spans.append((cur[0], cur[1],
                      max(bb - 1, cur[1]) if bb is not None else n - 1))
    return spans


def spans(df, causal=False, min_atr=None):
    """[(kind, start_bar, end_bar)] -- review (formation) or live (confirm)."""
    return _spans(pivots(df, min_atr), len(df), df, causal)


def spans_from_pivots(piv, n, df=None):
    """Compat for the old 4-tuple API (review clock). df required."""
    piv5 = [(j, j, p, k, lab) for j, p, k, lab in piv]
    return _spans(piv5, n, df, causal=False)


def states(df, causal=False, min_atr=None):
    """Per-bar UP / DOWN / FLAT under the span grammar."""
    arr = np.array(["FLAT"] * len(df), dtype=object)
    for kind, s0, s1 in spans(df, causal, min_atr):
        arr[s0:s1 + 1] = kind
    return arr


def span_states(df):
    return states(df, causal=False)


# ------------------------------------------------------------------ EQ

def _eq_machine(df, PIV=P.PIVOT_BARS, at_formation=False):
    c = df["Close"].values.astype(float)
    h_arr = df["High"].values.astype(float)
    l_arr = df["Low"].values.astype(float)
    n = len(c)
    seq = P.zigzag(df, PIV)
    atr = P._atr(df)
    eq = np.zeros(n, bool)

    lows, highs = [], []
    piv_prices = []
    labelled = []
    last4, last4_bars, last4_meta = [], [], []
    births = []
    alive = False
    ceil_p = floor_p = np.nan
    k = 0
    for i in range(n):
        while k < len(seq) and seq[k][1 if at_formation else 0] <= i:
            _, j, price, kind = seq[k]
            k += 1
            tol = P.SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
            if kind == "low":
                prev = lows[-1] if lows else np.nan
                lab = (("HL" if price > prev + tol else
                        "LL" if price < prev - tol else "EL")
                       if np.isfinite(prev) else None)
                lows.append(price)
            else:
                prev = highs[-1] if highs else np.nan
                lab = (("HH" if price > prev + tol else
                        "LH" if price < prev - tol else "EH")
                       if np.isfinite(prev) else None)
                highs.append(price)
            piv_prices.append(price)
            if len(piv_prices) > 4:
                piv_prices = piv_prices[-4:]
            if lab is None:
                continue
            labelled.append((j, float(price), kind, lab))
            last4 = (last4 + [lab])[-4:]
            last4_bars = (last4_bars + [j])[-4:]
            last4_meta = (last4_meta + [(kind, lab, price)])[-4:]
            if alive:
                if ((lab == "HH" and np.isfinite(ceil_p)
                     and price > ceil_p + tol)
                        or (lab == "LL" and np.isfinite(floor_p)
                            and price < floor_p - tol)):
                    alive = False
                    ceil_p = floor_p = np.nan
                    last4, last4_bars, last4_meta = [], [], []
                elif lab in ("LH", "EH"):
                    ceil_p = price
                elif lab in ("HL", "EL"):
                    floor_p = price
            if (not alive
                    and sum(last4.count(x) for x in ("HL", "EL")) >= 2
                    and sum(last4.count(x) for x in ("LH", "EH")) >= 2
                    and len(piv_prices) >= 4):
                alive = True
                ceil_p = next((p for kk, ll, p in reversed(last4_meta)
                               if ll in ("LH", "EH")), np.nan)
                floor_p = next((p for kk, ll, p in reversed(last4_meta)
                                if ll in ("HL", "EL")), np.nan)
                births.append((i, last4_bars[0]))
        tol = P.SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
        if alive and ((np.isfinite(ceil_p) and h_arr[i] > ceil_p + tol)
                      or (np.isfinite(floor_p) and l_arr[i] < floor_p - tol)):
            alive = False
            ceil_p = floor_p = np.nan
            last4, last4_bars, last4_meta = [], [], []
        eq[i] = alive
    return eq, labelled, births


def eq_overlay(df, PIV=P.PIVOT_BARS, at_formation=False):
    """Live clock by default. Returns (eq_bool_array, labelled_pivots)."""
    eq, labelled, _ = _eq_machine(df, PIV, at_formation)
    return eq, labelled


def eq_display(df, PIV=P.PIVOT_BARS, min_span=4):
    """Review clock: at formation, each wash stretched back over its birth
    pattern, spans shorter than min_span suppressed. Pictures only."""
    eq, labelled, births = _eq_machine(df, PIV, at_formation=True)
    out = eq.copy()
    for birth, pat_start in births:
        if 0 <= pat_start < birth:
            out[pat_start:birth] = True
    i = 0
    n = len(out)
    while i < n:
        if out[i]:
            j = i
            while j + 1 < n and out[j + 1]:
                j += 1
            if j - i + 1 < min_span:
                out[i:j + 1] = False
            i = j + 1
        else:
            i += 1
    return out, labelled


# ------------------------------------------------------------------ all

def read(df):
    """Everything the grammar knows about a frame, both clocks."""
    live = states(df, causal=True)
    review = states(df, causal=False)
    eq_live, _ = eq_overlay(df)
    eq_rev, _ = eq_display(df)
    return dict(live=live, review=review, eq_live=eq_live,
                eq_review=eq_rev, pivots=pivots(df))


def now(df):
    """The scanner's question: what is true on the LAST closed bar?"""
    live = states(df, causal=True)
    eq_live, _ = eq_overlay(df)
    st = str(live[-1])
    return dict(trend=st, eq=bool(eq_live[-1]),
                label=("BALANCE" if (st == "FLAT" and eq_live[-1]) else st))
