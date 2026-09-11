"""
event_spike.py -- what happens after a huge single-day event gap?

    python event_spike.py

WHY THIS EXISTS
giveback.py measured exits after an OVERSOLD DIP inside an established uptrend.
That sample cannot say anything about a stock that doubled in a day on twenty
times its normal volume. There is no swing structure to break, the ATR is
meaningless because yesterday's bars were a fifth the width of today's, and RSI
is pinned near 100 instead of below 35. Applying the dip-buy exit rules here
would be using a finding outside the sample it came from.

So this measures the actual case: a one-day close-to-close jump of >= JUMP on
>= VOL_MULT times average volume, entered at the close of the FOLLOWING day
(which is when a discretionary buyer actually gets in), and tracked forward.

Reported: the forward path, how often the day-after close is ever seen again,
and which exit rule would have captured the most. No recommendation is produced.
"""

import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
JUMP = 0.50             # single-day close-to-close gain that counts as an event
VOL_MULT = 5.0          # and it must come on this multiple of average volume
HORIZ = [5, 10, 20, 60, 120]


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def find(sym, d):
    if len(d) < 300 or "Volume" not in d:
        return []
    c = d["Close"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    v = d["Volume"].values.astype(float)
    if not np.all(np.isfinite(c)) or c.min() <= 0:
        return []
    n = len(c)
    prev = np.roll(c, 1); prev[0] = c[0]
    jump = c / prev - 1
    v20 = pd.Series(v).rolling(20).mean().shift(1).values

    out = []
    for i in np.where((jump >= JUMP) & (v >= VOL_MULT * v20))[0]:
        # entry is the close of the day AFTER the event -- the realistic fill
        e = i + 1
        if e >= n - max(HORIZ) - 1:
            continue
        px = c[e]
        row = dict(sym=sym, date=d.index[i], jump=jump[i],
                   vmult=v[i] / v20[i],
                   fade=c[e] / c[i] - 1,          # day-after move off the spike
                   entry=px)
        seg = c[e:]
        for h in HORIZ:
            if len(seg) > h:
                row["r%d" % h] = seg[h] / px - 1
            else:
                row["r%d" % h] = np.nan
        # does it ever trade back to the day-after close, and how deep first?
        fwd = c[e:min(e + 120, n)]
        row["mdd120"] = float(np.min(fwd)) / px - 1
        row["mfe120"] = float(np.max(fwd)) / px - 1
        # where did the pre-event price sit -- the gap that could close
        row["pre_gap"] = prev[i] / px - 1
        out.append(row)
    return out


def main():
    store = pd.read_pickle(CACHE)
    rows = []
    for s, d in store.items():
        try:
            rows.extend(find(s, d))
        except Exception:
            continue
    R = pd.DataFrame(rows)
    if R.empty:
        print("no events found")
        return
    R.to_csv("event_spike_results.csv", index=False)

    print("=" * 86)
    print("  ONE-DAY EVENT SPIKES:  >= %.0f%% close-to-close on >= %.0fx volume"
          % (100 * JUMP, VOL_MULT))
    print("=" * 86)
    print("  %d events across %d markets" % (len(R), R.sym.nunique()))
    print("  entry modelled at the CLOSE OF THE NEXT DAY, which is where a")
    print("  discretionary buyer actually gets filled.")
    print()
    print("  the day after the spike, price moved %+.1f%% at the median"
          % (100 * R.fade.median()))
    print("  (it faded on %.0f%% of events)" % (100 * (R.fade < 0).mean()))

    print("\n" + "=" * 86)
    print("  FORWARD PATH FROM THAT ENTRY")
    print("=" * 86)
    print("  %-8s %9s %9s %9s %9s %9s"
          % ("horizon", "median", "mean", "share up", "25th", "75th"))
    print("  " + "-" * 82)
    for h in HORIZ:
        x = R["r%d" % h].dropna()
        print("  %-8s %+8.1f%% %+8.1f%% %8.0f%% %+8.1f%% %+8.1f%%"
              % ("%dd" % h, 100 * x.median(), 100 * x.mean(),
                 100 * (x > 0).mean(), 100 * x.quantile(0.25),
                 100 * x.quantile(0.75)))

    print("\n  worst drawdown in the next 120 days, from that entry:")
    print("    median %+.1f%%   25th %+.1f%%   worst 10%% %+.1f%%"
          % (100 * R.mdd120.median(), 100 * R.mdd120.quantile(0.25),
             100 * R.mdd120.quantile(0.10)))
    print("  best gain in the next 120 days:")
    print("    median %+.1f%%   75th %+.1f%%   best 10%% %+.1f%%"
          % (100 * R.mfe120.median(), 100 * R.mfe120.quantile(0.75),
             100 * R.mfe120.quantile(0.90)))
    deep = float((R.mdd120 <= -0.25).mean())
    print("\n  %.0f%% of these gave back 25%% or more at some point within 120 days"
          % (100 * deep))
    print("  %.0f%% were below the entry 60 days later"
          % (100 * (R["r60"] < 0).mean()))

    print("\n" + "=" * 86)
    print("  DOES THE SIZE OF THE SPIKE CHANGE THE OUTCOME?")
    print("=" * 86)
    R["bucket"] = pd.cut(R.jump, [0.5, 0.75, 1.0, 1.5, 100],
                         labels=["50-75%", "75-100%", "100-150%", ">150%"])
    g = R.groupby("bucket").agg(n=("jump", "size"), d20=("r20", "median"),
                                d60=("r60", "median"), d120=("r120", "median"),
                                mdd=("mdd120", "median"),
                                up60=("r60", lambda x: (x > 0).mean()))
    print("  %-10s %5s %9s %9s %9s %9s %9s"
          % ("spike", "n", "+20d", "+60d", "+120d", "worst dd", "up at 60d"))
    for k, x in g.iterrows():
        if x.n < 3:
            continue
        print("  %-10s %5d %+8.1f%% %+8.1f%% %+8.1f%% %+8.1f%% %8.0f%%"
              % (k, x.n, 100 * x.d20, 100 * x.d60, 100 * x.d120,
                 100 * x.mdd, 100 * x.up60))

    print("\n" + "=" * 86)
    print("  SIMPLE EXIT RULES ON THIS SAMPLE")
    print("=" * 86)
    print("  Structure-based stops are not usable here -- there is no swing")
    print("  structure yet and the pre-event low is %.0f%% below the entry at"
          % (-100 * R.pre_gap.median()))
    print("  the median, so a 'higher low break' is not a stop, it is a wipeout.")
    print()
    for lab, col in [("hold 20 days", "r20"), ("hold 60 days", "r60"),
                     ("hold 120 days", "r120")]:
        x = R[col].dropna()
        print("    %-14s median %+6.1f%%   mean %+6.1f%%   share up %3.0f%%"
              % (lab, 100 * x.median(), 100 * x.mean(), 100 * (x > 0).mean()))

    print("\n  full table: event_spike_results.csv")


if __name__ == "__main__":
    main()
