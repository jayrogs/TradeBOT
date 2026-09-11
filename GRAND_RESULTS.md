# The 2,016-combination run — 2026-08-20

Run overnight against the request: *"run 1000 simulations of different
combinations you believe are technical and psychological approaches to riding
trends, buying dips."*

Two independent grids of 1,008 each, plus a null of the same size for each, plus
a give-back study. 560 markets, 2005–2017 to search, **2018–2026 held back and
never tuned on**, 0.05% per side in costs throughout.

---

## The verdict first

**Nothing beat simply owning the same market.**

| grid | combinations | beat buy-and-hold | best margin |
|---|---|---|---|
| technical (`grand.py`) | 969 scored | **6** | **+0.3%/yr** |
| psychological (`mind.py`) | 1,008 scored | **2** | **+0.2%/yr** |

On the psychological grid the **null won**: the best result on reversed-return
data was +0.7%/yr against +0.2%/yr for the real data. When broken data beats
real data at the same search scale, there is nothing there. That is the cleanest
negative this project has produced.

The median combination in both grids lost to buy-and-hold by about **-6%/yr**.
That number is roughly the cost of being out of the market during 2018–2026, and
almost every rule paid it without earning it back.

---

## Two measurement bugs found and fixed, both of which had been flattering

These are worth recording because each one had produced a fake winner.

**1. The EMA exit was firing on the next bar.** "Exit on the first close below
the 12-EMA" sounds like a trend-riding rule. But entry is an oversold dip, which
is *already* below the EMA — so the condition was true on day one and every
trade lasted a single bar. It topped the first run at +0.57%/day. Once it has to
arm first (reclaim the EMA, *then* exit on the break) it fell to **last place**
in both grids.

**2. Averaging down was scored on average cost.** If you plan three tranches and
only one fills, the other two sat in cash — but scoring the trade on the average
of the lots that did fill hides that, and makes scaling look free. With every
style risking the **same maximum budget**, the advantage vanished:

| | before fix | after fix |
|---|---|---|
| scale | +5.3%/yr | +2.5%/yr |
| all-in | +2.2%/yr | +2.5%/yr |

Scaling in does not add return. What it does is cut the tail: worst 5% of trades
went **-17.2% → -11.0%**, and the RSI-halt variant reached -7.1%. That is a real
benefit, just not the one it appeared to have.

---

## What held up across both grids

Component effects — each choice averaged over every combination containing it —
are far more trustworthy than any single winner, because they are not the
best-of-1,008.

### Higher-timeframe filters subtracted value

| context | grand: per trade | grand: per day in market | mind: per day |
|---|---|---|---|
| `any` (no filter) | **+9.77%** | **+0.048%** | **+0.045%** |
| `M` monthly up | +8.13% | +0.042% | +0.043% |
| `W` weekly up | +8.22% | +0.038% | +0.035% |
| `W+M` both up | +7.09% | +0.035% | +0.034% |
| `D+W` daily+weekly | +8.29% | +0.040% | +0.032% |

This is the uncomfortable one, because the alignment filter is the core of the
method. Note it is **not** just cash drag: holding periods are matched (188–194
days) and no-filter still wins per trade and per day in the market. Requiring
confirmed structure means entering after the trend is established, and an RSI
below 35 *inside* a confirmed uptrend selects partly for trends already breaking.

### Which dip trigger you use barely matters

Eight very different triggers — RSI thresholds, EQ resolution, EMA reclaim,
capitulation volume, gap downs, three and five down days, stretched below the
50-day, climax bars — span about **2%/yr** end to end. The entry signal is not
where the outcome is decided.

### Exits are where the spread is

| exit | grand, per trade | mind, per trade | days held |
|---|---|---|---|
| `HL_d` structural break | +14.4% | +13.7% | ~290 |
| `HL_m` monthly break | +14.4% | — | 320 |
| `target20` | +7.9% | — | 207 |
| `climax_up` | — | +7.3% | 176 |
| `be_half` | — | +7.8% | 287 |
| `rsi60` | — | +1.1% | 26 |
| `time60` | +2.3% | — | 59 |
| `rsi50` | — | +0.4% | 9 |
| `up3` / `ema12` | +0.4% | +0.5% | ~12 |

Structure-based exits beat relief-based exits by an order of magnitude per trade.

---

## The one actionable result: `giveback.py`

5,693 entries across 559 markets, the documented setup (weekly uptrend + daily
RSI < 35). For each exit rule: what it captured, and what the move did *after*.

| rule | median captured | share of the move | still in at the peak | median given back after exiting |
|---|---|---|---|---|
| hold 250 bars | +8.2% | 42% | 100% | — |
| `target20` | +20.0% | 40% | 49% | +0.9% |
| **`HL_d` (the stated rule)** | **+6.0%** | **31%** | **87%** | **—** |
| `HL_m` | +5.9% | 31% | 95% | — |
| `rsi70` | +7.9% | 27% | 23% | +11.1% |
| `time60` | +2.6% | 11% | 22% | +16.7% |
| `rsi50` | +3.0% | 10% | 7% | **+19.9%** |
| `ema12` | +1.2% | 5% | 10% | **+20.5%** |
| `atr3` | -1.5% | -7% | 22% | +19.1% |
| `trail20` | -2.8% | -11% | 77% | — |

**How often the move continues after you sell:**

| rule | peak came later | gave back more than 10% |
|---|---|---|
| `rsi50` | 93% | 71% |
| `ema12` | 90% | 73% |
| `atr3` | 78% | 71% |
| `rsi70` | 77% | 52% |
| `target20` | 51% | 32% |
| **`HL_d`** | **13%** | **12%** |
| `HL_m` | 5% | 4% |

### What this says

The exit rule already in use — *sell when it breaks the low of the last higher
low* — is the good part of the method. It is still in the trade at the peak
**87%** of the time and gives back more than 10% on only **12%** of trades. Every
relief-based exit (RSI recovers, three green days, EMA cross) leaves a median
**+19% to +20%** on the table and does so on roughly 7 out of 10 trades.

So the early-exit leak visible in the real trade history is **not** a flaw in the
rule. It is the gap between the rule and what actually gets done.

**The price of holding on is real and should be stated:** the worst 5% of trades
goes from about **-11%** with a tight exit to **-30%** with a structural one.
That is the trade being made — a much fatter tail in exchange for staying in the
87%.

---

## Bottom line

- The premise "a mechanical dip-buying system beats buy-and-hold" has now failed
  across roughly **22,000 configurations** in this project. Two more grids of
  1,008 did not change it, and one of them lost to its own null.
- The higher-timeframe alignment filter measured **negative** on both grids, on
  both a per-trade and a per-day-in-market basis. That is worth confronting.
- The structural exit measured **strongly positive relative to every
  alternative**, and matches what is already being done by hand.
- Files: `grand.py`, `mind.py`, `giveback.py`. Full tables in
  `grand_results.csv`, `mind_results.csv`, `giveback_results.csv`; raw console
  output in `grand_log.txt`, `mind_log.txt`, `giveback_log.txt`.
