# The backburner, reviewed

2026-09-15. A second pass over the two days of backburner work, done as a skeptic would do it: read the code paths
the numbers depend on, test the things that could be wrong, fix what is, and say plainly what cannot be fixed here.

## The short version

1. **The wallet was 2.2x leveraged.** The +40% a year was borrowed money nobody mentioned. In a cash account it
   is **+16.9% a year at ten slots**, worst drawdown −17%. SPY over the same years: +13.1%, worst drawdown −34%.
2. **23 names had bad data** (split and reorganisation glitches). One was carrying a +107% "trade". They are out.
3. **Survivorship cannot be fixed on this machine**, only bounded. The ETF-only wallet, which the bias cannot
   flatter, makes **+11.2% — below SPY**. The truth is somewhere between +11% and +17%.
4. What survives is real and modest: a trade that **earns its keep in bear years** (2018 +8.4% vs −6.3%, 2022
   +12.7% vs −19.5%) and **lags in bull ones**. Positive in all ten years; beat SPY in four.

## What was checked and passed

| the thing | how it was checked | result |
|---|---|---|
| ATR, RSI | read the code | both exponential, both causal |
| pivots | tuple is (confirm bar, form bar, price, kind); code keys on confirm bar | no look-ahead |
| the fear gap | `open[k] < low[k-1]`, read on bar k, filled at k+1's open | known before the fill |
| the scale-in | each later fill needs RSI ≤ 30 on the bar before and a lower open | known at each open |
| the weekly stop level | aligned by bar CLOSE time | a Wednesday sees only weeks already closed |
| breadth | cross-sectional on closed daily bars, read the day before the fill | causal |
| the chandelier | one-bar lag on the running high; vectorised and bar-by-bar agree | 91 trades, 0 mismatches |
| the top trades | opened the price series around each | March 2020: CELH, TSLA, DKNG, BX, SCCO — real |

## What was wrong, and what was done

**1. Leverage.** `wallet()` sized each position as 1% of the account divided by the stop distance. A 3.9% stop
(the median) is a 26% position; ten slots of those is 260% of the account. The only cap was 3/slots = 30% per
name. Measured: median exposure 218%, peak 288%. Rebuilt as a cash account — dollars fixed at entry, at most an
equal share of the account, never more than free cash. Every wallet now prints its deployed share.

| slots | levered (before) | cash account (now) | worst drawdown now |
|---|---|---|---|
| 5 | +21.3% | +14.0% | −14% |
| 10 | +40.2% | **+16.9%** | **−17%** |
| 20 | +60.9% | +17.3% | −20% |

**2. Bad data.** A scan for one-day close-to-close moves over 60% found 23 names. APLD at exactly 2.000x, QXO at
4.9x, KDP at 0.18x, OVV at 0.28x, SOXS at 0.054x are adjustment errors; ARGX, PCG, RKT are real one-day moves.
All 23 are excluded together (`validation/suspect_names.json`, read by the wallet and the drawings). Cost: 4% of
the profit. QXO's +107% trade had a 240% day inside it.

**3. The drawings booked a different trade from the study** (found the night before, recorded here). The shared
chandelier mode takes its partial at the weekly 12 EMA when that is further than 1x the risk; the page said 1x.
34 of 59 trades disagreed, by up to 17%. Fixed with a flat-1x mode; the self-test now owns its reference and
checks this.

**4. "The daily is the chart" was not shown.** The page compared +0.35R on the daily to +0.27R on the hourly —
different charts, different controls. By edge over its own control the 4-hour is better (+0.71R vs +0.53R) with
about as many trades. Only the daily has been through the wallet. Left open, and the page now says so.

## What cannot be fixed here

**Survivorship.** The 601 stock and ETF names are the ones on disk today, history backfilled: 509 have data from
before mid-2017 and none of them went to zero. A dip-buying rule is the single most exposed thing there is to
that. Bounded two ways:

| population | 10 slots, a year |
|---|---|
| every name | +16.9% (the ceiling) |
| names with a trade before 2018 | +18.3% (removes late joiners, not leavers) |
| **ETFs only** — sector ETFs do not delist | **+11.2% (the floor; under SPY)** |

Fixing it needs delisted-company history, which costs money. Until then the honest statement is "between +11%
and +17% a year, with half of SPY's drawdown".

## Things worth knowing that are not bugs

- **2020 made +2.4%.** The year of the biggest fear gaps, and the account barely moved: the ten slots were full
  of early-March stop-outs when the March 17th trades fired. Capacity is the constraint in a crash, not edge.
- **Most scale-ins fill once.** 72% of daily dips never get a second unit. The averaging is still worth +0.4R
  over buying once, matched on stop width — but it is not the picture of five arrows stepping down.
- **Twenty-two reads, one winner.** The fear gap was the best of 22 market reads. It held in 10 of 10 years and
  against its own control, which is the right defence, but a best-of-22 deserves a discount the tables do not show.
- **Costs are 0.05% round trip.** At ~75 trades a year per account that is not the story here; it was on the 1h
  wallet in #29.

## What to do next, in order

1. Grade the sixteen drawings on /scalein. Nothing above is settled until you have looked at them.
2. Put the 4-hour chart through the wallet. It has a bigger edge over its control than the daily and the same
   trade count; it may be the better account.
3. Delisted history, if this trade is going to be run with money. It is the one number that could halve this.
