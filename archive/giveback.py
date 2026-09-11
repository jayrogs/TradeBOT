"""
giveback.py -- how much of the move does each exit rule actually capture?

    python giveback.py

THE QUESTION THIS ANSWERS
grand.py and mind.py rank exits by what they earn. Neither shows what they MISS.
That matters here because the leak identified in the real trade history is
exiting too early, and "too early" is not visible in a return column -- a rule
that books +6% looks fine until you see the move ran +31% afterwards.

So for one fixed entry -- the documented setup, weekly uptrend with a daily
oversold reading -- every exit rule is measured three ways:

  captured    what the rule booked
  available   the best close within 250 bars of the entry
  capture %   captured / available, the share of the move actually taken
  give-back   what price did AFTER the exit, if the peak came later

An exit with a high capture share is not automatically better. Holding for the
peak means sitting through everything in between, so the worst 5% of trades is
reported alongside. The point is to see the trade-off, not to crown a rule.

NOT A BACKTEST. There is no compounding and no position sizing here. It is a
measurement of where the money goes after you get out.
"""

import os
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
COST = 0.0005
SPLIT = pd.Timestamp("2018-01-01")
WINDOW = 250            # how far ahead "available" looks
MIN_GAP = 20            # bars before the same market may signal again
OVERSOLD = 35


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def atr(h, l, c, n=14):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def first_after(cond, n):
    nxt = np.full(n, n - 1, dtype=int)
    last = n - 1
    for i in range(n - 1, -1, -1):
        if cond[i]:
            last = i
        nxt[i] = last
    return nxt


def measure(sym, d):
    if len(d) < 800:
        return []
    c = d["Close"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    if not np.all(np.isfinite(c)) or c.min() <= 0:
        return []
    idx, n = d.index, len(c)

    st_d, hl_d, _ = P.trend_state(d)
    wk = P.resample(d, "W-FRI")
    mo = P.resample(d, "ME")
    if len(wk) < 60 or len(mo) < 20:
        return []
    st_w, hl_w, _ = P.trend_state(wk)
    _, hl_m, _ = P.trend_state(mo)

    def align(src, arr):
        return pd.Series(arr, index=src).reindex(idx, method="ffill").values

    w_up = pd.Series(st_w == "UP", index=wk.index).reindex(
        idx, method="ffill").fillna(False).values
    hl_w_a, hl_m_a = align(wk.index, hl_w), align(mo.index, hl_m)

    r = rsi(c)
    a = atr(hi, lo, c)
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values

    # exits that are pure bar conditions
    above = first_after(c > ema12, n)
    below = first_after(c < ema12, n)
    ema_armed = np.array([below[min(above[i] + 1, n - 1)] for i in range(n)])
    cond = {
        "HL_d": first_after(np.isfinite(hl_d) & (c < hl_d), n),
        "HL_w": first_after(np.isfinite(hl_w_a) & (c < hl_w_a), n),
        "HL_m": first_after(np.isfinite(hl_m_a) & (c < hl_m_a), n),
        "ema12": ema_armed,
        "rsi70": first_after(r >= 70, n),
        "rsi50": first_after(r >= 50, n),
    }

    entries = []
    last = -MIN_GAP - 1
    sig = w_up & (r < OVERSOLD) & (idx >= SPLIT)
    for i in np.where(sig)[0]:
        if i - last >= MIN_GAP and i < n - WINDOW // 5:
            entries.append(i)
            last = i

    rows = []
    for i0 in entries:
        end = min(i0 + WINDOW, n - 1)
        seg = c[i0:end + 1]
        pk = int(np.argmax(seg))
        peak_bar, peak_px = i0 + pk, float(seg[pk])
        available = peak_px / c[i0] - 1
        if available <= 0.001:
            continue                    # never went anywhere: nothing to capture

        for name in list(cond) + ["trail20", "atr3", "target20", "time60",
                                  "hold250"]:
            if name in cond:
                j = min(max(cond[name][i0], i0 + 1), end)
            elif name == "time60":
                j = min(i0 + 60, end)
            elif name == "hold250":
                j = end
            elif name == "target20":
                hit = np.where(c[i0 + 1:end + 1] >= c[i0] * 1.20)[0]
                j = i0 + 1 + hit[0] if len(hit) else end
            elif name == "trail20":
                j, peak = end, c[i0]
                for k in range(i0 + 1, end + 1):
                    peak = max(peak, c[k])
                    if c[k] <= peak * 0.80:
                        j = k
                        break
            else:                        # atr3
                j, peak = end, c[i0]
                for k in range(i0 + 1, end + 1):
                    peak = max(peak, c[k])
                    if c[k] <= peak - 3.0 * a[k]:
                        j = k
                        break

            captured = (c[j] * (1 - COST / 2)) / (c[i0] * (1 + COST / 2)) - 1
            # the worst it felt on the way, which is what makes people sell
            trough = float(np.min(c[i0:j + 1]))
            rows.append(dict(
                sym=sym, rule=name, i0=i0, days=j - i0,
                captured=captured, available=available,
                capture=captured / available,
                peak_after=int(peak_bar > j),
                giveback=(peak_px / c[j] - 1) if peak_bar > j else 0.0,
                days_to_peak=int(peak_bar - j) if peak_bar > j else 0,
                heat=trough / c[i0] - 1))
    return rows


def main():
    store = pd.read_pickle(CACHE)
    syms = sorted([s for s, d in store.items() if len(d) > 2500])
    syms = syms[:int(os.environ.get("GB_N", 10**6))]
    print("scanning %d markets for the documented setup..." % len(syms))
    rows = []
    for s in syms:
        try:
            rows.extend(measure(s, store[s]))
        except Exception:
            continue
    R = pd.DataFrame(rows)
    if R.empty:
        print("no entries found")
        return
    R.to_csv("giveback_results.csv", index=False)

    n_entries = R.groupby("rule").size().iloc[0]
    print("  %d entries across %d markets, %s onward"
          % (n_entries, R.sym.nunique(), SPLIT.date()))
    print("  entry = weekly uptrend + daily RSI < %d, one per %d bars"
          % (OVERSOLD, MIN_GAP))

    print("\n" + "=" * 94)
    print("  WHAT EACH EXIT CAPTURES OF THE MOVE IT WAS IN")
    print("=" * 94)
    print("  %-9s %7s %9s %9s %8s %9s %10s %9s"
          % ("rule", "days", "captured", "capture%", "kept", "gave back",
             "days after", "worst 5%"))
    print("  " + "-" * 90)
    g = R.groupby("rule")
    tab = pd.DataFrame({
        "days": g.days.median(),
        "captured": g.captured.median(),
        "capture": g.capture.median(),
        "peak_after": g.peak_after.mean(),
        "giveback": g.giveback.median(),
        "d2peak": g.days_to_peak.median(),
        "worst": g.captured.quantile(0.05),
        "mean": g.captured.mean(),
    }).sort_values("capture", ascending=False)
    for k, x in tab.iterrows():
        print("  %-9s %7.0f %+8.1f%% %8.0f%% %8.0f%% %+8.1f%% %10.0f %+8.1f%%"
              % (k, x["days"], 100 * x.captured, 100 * x.capture,
                 100 * (1 - x.peak_after), 100 * x.giveback, x.d2peak,
                 100 * x.worst))

    print("\n  captured  = median return the rule booked")
    print("  capture%%  = share of the best close within %d bars that it took" % WINDOW)
    print("  kept      = share of trades where the rule was still in at the peak")
    print("  gave back = median further move AFTER the exit, when the peak came later")
    print("  worst 5%%  = the fifth percentile trade, the price of holding on")

    print("\n" + "=" * 94)
    print("  IS EXITING EARLY ACTUALLY THE LEAK?")
    print("=" * 94)
    base = tab.loc["HL_d"] if "HL_d" in tab.index else tab.iloc[0]
    best = tab.capture.idxmax()
    print("  Across every rule, the median trade captured %.0f%% to %.0f%% of the"
          % (100 * tab.capture.min(), 100 * tab.capture.max()))
    print("  move that was there. The widest gap between two rules is %.0f points"
          % (100 * (tab.capture.max() - tab.capture.min())))
    print("  of capture, worth %+.1f%% per trade at the median."
          % (100 * (tab.captured.max() - tab.captured.min())))
    print()
    print("  But holding longer is not free. Best capture (%s) takes a worst-5%%"
          % best)
    print("  trade of %+.1f%%, against %+.1f%% for the tightest rule."
          % (100 * tab.loc[best, "worst"], 100 * tab.worst.max()))
    print()
    lift = tab.captured.max() - base.captured
    print("  Switching from HL_d to the best-capturing rule changes the median")
    print("  trade by %+.1f%% and the mean by %+.1f%%."
          % (100 * lift, 100 * (tab["mean"].max() - base["mean"])))

    print("\n" + "=" * 94)
    print("  HOW OFTEN DOES THE MOVE CONTINUE AFTER YOU SELL?")
    print("=" * 94)
    for k, x in tab.sort_values("peak_after", ascending=False).iterrows():
        sub = R[R.rule == k]
        big = float((sub.giveback > 0.10).mean())
        print("  %-9s peak came later on %3.0f%% of trades; %3.0f%% gave back more"
              " than 10%%" % (k, 100 * x.peak_after, 100 * big))

    print("\n  full table: giveback_results.csv")


if __name__ == "__main__":
    main()
