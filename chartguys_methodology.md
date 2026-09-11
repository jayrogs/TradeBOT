# ChartGuys Swing Report — Reverse-Engineered Methodology

**Source:** 145 weekly reports, Oct 2023 – Aug 2026, 291 picks, 155 unique tickers.
Extracted from saved HTML; geometry complete on 100% of rows.
**Outcomes:** recomputed independently from nominal (un-split, un-dividend-adjusted)
daily bars. Nothing below relies on the vendor's own P/L column.

---

## 1. Publication format

- Weekly, published Sunday. Almost always exactly **2 picks per week**.
- Each pick ships with: direction, price at time of highlight, entry zone (a range),
  caution (stop), target, a short prose rationale, a video, and weekly + daily charts.
- Each pick also carries a **weekly and daily trend label** (up / sideways / down) and
  four S/R levels per timeframe (R1, R2, S1, S2).
- Reports also contain an index market update (SPX, IWM, DIA, QQQ) — not tradeable picks.

## 2. Directional bias

| | count | share |
|---|---|---|
| Long | 258 | 89% |
| Short | 33 | 11% |

Overwhelmingly long. Note this is not a trend-following book — weekly trend at time
of pick was **up 162, sideways 71, down 56**. They take longs in downtrends (44 cases)
and shorts in uptrends (11 cases).

## 3. Trade geometry — the core mechanic

The defining feature: **the entry zone is always below the current price on a long.**
258 of 258 longs, zero exceptions in three years. You are never told to buy at
publication. You place a resting limit and wait.

Median values for longs (IQR in brackets):

| measurement | median | IQR |
|---|---|---|
| zone top below highlight price | 5.69% | 3.61 – 8.50 |
| zone bottom below highlight price | 13.16% | 9.63 – 17.94 |
| zone width | 7.89% of price | 5.91 – 10.24 |
| caution (stop) below zone bottom | **1.27%** | 0.80 – 1.85 |
| target above highlight price | 6.82% | 4.56 – 9.48 |
| target above zone top | 13.35% | 9.28 – 19.87 |

**The stop sits only ~1.3% beneath the zone floor.** This single number drives
everything about how the system behaves — see §6.

## 4. Where the levels come from

Not a formula. Tested every mapping of zone boundaries onto the published S/R levels;
best single match was zone_top ≈ daily_S1 at **19% of picks**. All other pairings
landed 3–15%.

The levels are drawn by hand off horizontal structure visible on the weekly and daily
charts, informed by the S/R table but not derived from it. Round-number shaving is
applied inconsistently (−0.3% to −1.0% observed on adjacent picks).

**Implication: this component cannot be mechanically cloned.** Any replication has to
substitute its own level logic — swing pivots, or ATR bands, or volume-profile nodes.

## 5. The conceptual framework

Vocabulary frequency across 291 rationales:

| term | occurrences | per pick |
|---|---|---|
| all-time high | 167 | 0.57 |
| ema | 153 | 0.53 |
| support | 132 | 0.45 |
| consolidation | 91 | 0.31 |
| pullback | 75 | 0.26 |
| higher low | 58 | 0.20 |
| range / balancing | 111 | 0.38 |
| relative (strength) | 56 | 0.19 |
| sector | 39 | 0.13 |

Stock phrases: *"makes the list this week"*, *"playing off of the area"*,
*"traders will be looking for a move back to new all-time highs"*, *"as long as X holds"*.

The framework is **two-timeframe structural**: classify weekly trend, classify daily
trend, identify a horizontal demand area beneath price, buy into it, target prior
highs. Language is light auction-market-theory (balancing, rotation, acceptance)
layered over conventional support/resistance and EMA reading. Not quantitative —
there is no screen or score being applied.

---

## 6. Measured performance (independently recomputed)

Backtest: limit fill at the zone, exit at whichever of caution/target price touches
first, same-bar ties scored as losses, un-split nominal prices.

| fill assumption | never entered | resolved | win rate | mean/trade | profit factor | expectancy/setup |
|---|---|---|---|---|---|---|
| zone top | 99 | 169 | 52.7% | +2.91% | 1.72 | **+1.74%** |
| zone mid | 146 | 130 | 33.1% | +3.01% | 2.01 | +1.39% |
| zone bottom | 182 | 98 | 10.2% | +2.14% | 5.65 | +0.75% |

**Roughly a third of picks never trigger at all** (99 of 286 at the shallowest fill).

### The stop-placement trap

Reward:risk measured at the zone boundaries looks spectacular at the bottom
(median 19.3:1 vs 1.46:1 at the top) because the stop is only 1.27% below the
zone floor. In practice this is a trap: filling deep puts a hair-trigger stop
immediately under the entry, and the win rate collapses from 52.7% to **10.2%**.
The favourable R:R is real and almost never collects.

### Versus doing nothing

- Strategy: ~**+20.6%/yr** gross, fully invested (~7.5 concurrent positions, 58 trades/yr)
- SPY buy & hold, same window: **+21.9%/yr, excluding dividends**

After slippage: +19.0%/yr at 0.10% per side, +16.7% at 0.25%, +12.8% at 0.50%.
Before tax — and 58 trades/yr is entirely short-term gains at ordinary income rates,
versus deferred long-term treatment for buy-and-hold.

### Fragility

- 95% CI on mean per trade: **[+0.91%, +4.90%]** — barely separated from zero
- Dropping the 10 best trades of 169 cuts the mean from +2.91% to +1.21%
- 2026 YTD is negative: mean −0.33%, median −7.02%, win rate 46.7% (n=15)

### Vendor's own reporting

The published dashboard shows an **88% win rate**. That figure counts 34 setups that
never reached their entry zone, booking a "profit" measured from the publication
price — the entry their own methodology tells you not to take. Honestly computed,
the number is 52.7%.

---

## 7. What actually predicted outcomes

Signals worth carrying forward into any replacement system:

**Counter-trend entries beat with-trend entries.** Directly contrary to the framing.

| daily trend at pick | n | win rate | mean |
|---|---|---|---|
| down | 51 | 60.8% | +4.60% |
| sideways | 34 | 58.8% | +2.60% |
| up | 83 | 45.8% | +1.75% |

Worst combination was weekly-up/daily-up (n=58, 44.8%, +1.91%). Best was
weekly-down/daily-down (n=20, 55.0%, +5.84%). Buying dips in already-strong names
underperformed buying into weakness.

**Zone depth has a sweet spot.** Mid-depth zones (n=56) won 64.3% at +4.92%;
the deepest third won 37.5% at +0.44%. Deeper is not better.

**Narrower zones beat wider ones.** Bottom two width terciles: 58.9% / 57.1%.
Top tercile: 42.9%.

**Rationale keywords that correlated with success** (small samples, treat as hypotheses):

| keyword present | n | win | mean | vs absent |
|---|---|---|---|---|
| "range" | 21 | 76.2% | +6.09% | 49.3% / +2.46% |
| "relative" strength | 29 | 69.0% | +6.22% | 49.3% / +2.22% |
| "balancing" | 20 | 65.0% | +3.92% | 51.0% / +2.77% |
| "higher low" | 31 | 51.6% | **−0.46%** | 52.9% / +3.67% |
| "50" (50-day EMA) | 28 | 46.4% | +0.58% | 53.9% / +3.37% |

Range/balance setups and explicit relative-strength calls were their best work.
Momentum-continuation language ("higher low", 50-EMA bounces) was their worst.

**Shorts outperformed longs**: 56.0% win / +4.17% on 25 trades, versus
52.1% / +2.69% on 144. Their strongest edge sits in 9% of their output.

---

## 8. Summary judgement

Not a scam. A competent discretionary system with a genuine but small edge that
approximately matches the index gross and loses to it after costs and tax. The
marketing number is inflated roughly 35 percentage points by counting untriggered
setups as wins.

**The exploitable observations, for building against it:**

1. Their edge concentrates in counter-trend and range-rotation setups, not the
   trend-continuation trades that make up most of the book.
2. Stop placement 1.27% below the zone floor is too tight for the zone width —
   it converts good R:R into stop-outs.
3. A third of picks never trigger, so capital sits idle without any mechanism to
   redeploy it.
4. Two picks per week is a publishing schedule, not an opportunity count. There is
   no evidence the market offered exactly two setups every week for three years.
5. 89% long with no explicit market-regime filter, in a period when the index rose
   every year but one.

---

## 9. Confound test on the trend finding

The daily-trend result was the one finding with a clean monotonic ordering, so it
was worth checking against the obvious alternative explanation: that falling stocks
simply reach their entry zone more readily, making the group a selection artifact
rather than a real effect.

**Fill rates do differ, modestly:**

| daily trend | setups | filled | fill rate |
|---|---|---|---|
| down | 76 | 54 | 71.1% |
| sideways | 54 | 36 | 66.7% |
| up | 150 | 92 | 61.3% |

**But fill speed does not drive returns.** Correlation between days-to-fill and
win/loss is +0.032; with return, +0.014. Both are zero for practical purposes.
Bucketing by fill speed shows no gradient (fast 51.7%, medium 51.8%, slow 54.5%).

**And the trend effect survives inside every fill-speed bucket:**

| fill speed | daily down | daily up |
|---|---|---|
| fast (median 4d) | 57.9% (n=19) | 36.0% (n=25) |
| medium (median 20d) | 66.7% (n=12) | 53.1% (n=32) |
| slow (median 75d) | 60.0% (n=20) | 46.2% (n=26) |

Down beats up in all three. Three replications within the dataset, holding the
confound constant.

**Refinements to §7:**

- The effect is **daily-timeframe only**. The weekly label is scrambled
  (down 58.8%, sideways 50.0%, up 51.5%) and carries no signal.
- **"Sideways" is noise** — 76.9% / 33.3% / 66.7% across fill-speed buckets on
  small samples. Only the down-vs-up contrast is reliable.
- The trend labels are **discretionary analyst judgment, not a calculation**, so
  they cannot be cloned mechanically. Any replication must define its own
  short-term weakness measure and re-verify.
- Labels are written at publication but **median 19 days elapse before fill**
  (IQR 5–47; 37% of fills occur >30 days later). The label describes a condition
  that frequently no longer holds at entry — yet it still predicts. That is
  interesting and unexplained.

### Standing caveat

Everything in §7 came from roughly fifteen exploratory splits of 169 trades.
Simulation on this exact dataset: a single random split has a 5.6% chance of
showing a ≥15-point win-rate gap; across fifteen splits the chance that at least
one does is **57.7%**. Finding something was the expected outcome regardless of
whether anything real was present.

The daily down-vs-up contrast is the only finding that has survived a confound
test and replicated across sub-samples. Treat the rest — zone depth, zone width,
rationale keywords — as unverified.

**2026 data has not been used for any of this and must be held out as the single
honest test of whatever gets built.**
