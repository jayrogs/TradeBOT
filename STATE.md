# Project state — 2026-08-22

Read this first in a new session. It captures what exists, what was learned, and
what is still open. `NOTES.md` has the full research record; this is the map.

---

## 1. What this project turned out to be about

It started as "build a mechanical system that beats SPY." Roughly 20,000
configurations across six approaches were tested and **none survived
out-of-sample.** Twice a result looked strong and the holdout killed it.

The turn came from pulling the user's actual Robinhood trades (199 realised
closes, $16,094). Those said something the backtests could not:

| | trades | total | avg | win rate |
|---|---|---|---|---|
| position trades | 45 | **$15,501** | $344 | **84%** |
| scalps | 154 | $593 | $3.85 | 44% |

Top 20 trades = 90% of all profit. And a natural experiment: SLV **held** made
$8,190 in 11 trades; SLV **day-traded the same month** made $381 in 129.

**Conclusion: the edge is instrument selection, which is discretionary and did
not mechanise in five separate attempts. The leak is exiting too early, which is
fully mechanical.** The project became "build the tool that fixes the exit and
extends the eyes," not "find a strategy."

## 2. What is built and working

| file | purpose | status |
|---|---|---|
| `panel.py` | swing structure, trend state, equilibrium detection | **working, tested** |
| `chart.py` | annotated charts with labels + shading | working |
| `test_trend.py` | 8 trend cases that must all pass | **8/8** |
| `audit_chart.py` | checks shading agrees with its own labels | **0 contradictions / 76 panels** |
| `scan.py` | ~600-symbol setup scanner | working |
| `lights.py` | condition panel + confluence validation | working |
| `bot.py` | backtested trend-hold system | fails its spec, see §4 |
| `exits.py`, `exit_test2.py`, `pairs_test.py` | exit-rule comparisons | done |
| `heat.py`, `disasters.py` | drawdown / catastrophe analysis | done |

### The trend engine, final rules

- **Swings**: alternating highs/lows, minimum leg 1.0 ATR, two swings within
  **0.15 ATR** count as the same level (labelled EH/EL, drawn grey)
- **UP**: higher high *and* higher low; or a close above the last two swing highs
- **DOWN**: mirror
- **Ends**: opposite break, or either side of the structure turning
- **BALANCE**: 2 rising lows + 2 falling highs, range contracting, price inside
- **Stop**: close below the last higher low

Six bugs were found here, all by the user looking at a chart:
non-alternating swings, state re-evaluating every bar, a 1.5% "higher low"
counting as structure, a duplicate `zigzag` that silently disabled the ATR
filter, a deadlock preventing DOWN→UP, and labels using a different tolerance
from the logic.

**Run both checks before trusting any chart:**
```
python test_trend.py && python audit_chart.py
```

## 3. What the research actually established

**Exits (the valuable part).** Same entry, only the exit varying:

| | silver trade |
|---|---|
| +20% target *(what the user did)* | +20% |
| 50-day MA break | +72% |
| **daily higher-low break, close-based** | **+94.6%** |
| daily higher-low break, **wick**-based | +16.9% |

Wicks vs closes was worth **78 points on one trade**. Across timeframes,
exiting on a wick returned +2.06% vs **+43.45%** on a close (weekly).

**Manage on the higher timeframe -- RETRACTED.** An earlier version of this
document claimed +48.95% vs -0.01%. That was an artifact of the buggy trend
engine: the lower-timeframe stop was computed from a stale level already above
price at entry, so it fired on bar one. Re-run with the fixed engine the two are
tied (+3.52% vs +4.08%, weekly/daily; +27.07% vs +26.52%, monthly/weekly), and
the lower timeframe is slightly ahead on median and win rate. **The tell was a
median hold of 1 bar -- no real exit rule holds one bar.**

**Exit comparison, re-run on the fixed engine** (27,667 entries):

| exit | mean | median | win% | hold |
|---|---|---|---|---|
| daily HL close | +3.17% | -0.49% | 47% | 39 |
| **monthly HL close** | +112.65% | **+4.60%** | **56%** | 398 |
| +20% target | +30.24% | +20.30% | 77% | 176 |
| 20% trail | +37.25% | -3.17% | 44% | 139 |

The monthly higher-low break is the only structural exit with a positive median
and it captures 21% of the best-case move. That was not visible before the fix.

**Indicators.** RSI beats Williams %R at matched selectivity (+1.21% vs +0.50%);
combining them costs half the signals for +0.05pp. Confluence scores are not
monotonic — 0 green lights beat 4. Correlated oscillators give one vote and a
smaller sample.

**Risk.** Buying oversold dips: 99.4% recover, median heat −1.2%, but 1-in-100
goes −19%, worst −86%, and 0.6% never come back. Nothing at entry distinguishes
the disasters — RSI, trend, volatility all identical. The only tell is the
user's own rule: "RSI cools off while price doesn't" fired in 88% of disasters
vs 11% of normal cases (re-run: 91% vs 11%).

## 4. Known limitations — read before trusting numbers

- **`cache/scan_prices.pkl` is 2021-01-01 onward only (~1,412 bars).** The chart
  audit, trend tests and the RSI/Williams comparison all ran on 5.6 years — one
  regime. Re-downloading from 2005 is a one-minute job and was the agreed next
  step.
- Universe is *current* S&P 500 → survivorship bias, measured at ~2.7pp/yr.
- Futures `=F` series carry roll artifacts: mild on ES (15% vs 8% baseline),
  severe on NG (48%).
- Sub-hour data does not exist beyond 60 days from this source. 30M/15M/5M can
  be *displayed* live but never backtested.
- `bot.py` **fails its own pre-registered spec** (CAGR 15.01% vs SPY 15.86%).
  Its returns depend almost entirely on having TSLA/BTC/NVDA/AMD in the
  universe — remove those four and it makes 5.5%.
- Nothing has been forward-tested. Every number is hindsight.
- **Any result that used `trend_state` before 2026-08-19 is void.** Six bugs
  were fixed in it. `pairs_test.py`, `exit_test2.py`, `heat.py` and
  `disasters.py` have all been re-run; `exits.py` and the silver counterfactual
  never used it and stand unchanged.

## 5. Where to go next

1. **Re-download `scan_prices` from 2005** and re-run `test_trend.py`,
   `audit_chart.py` and the indicator comparison on 20 years instead of 5.6.
2. **Run the scanner across the full universe** with the finished trend engine —
   the "watch 600 charts" tool that was the original point.
3. **Build the exit manager** against live Robinhood positions: read holdings,
   show where each higher-low stop sits per timeframe.
4. Paper-trade one frozen rule forward. It is the only untainted test left.

## 7. The 2,016-combination overnight run (2026-08-20)

Full write-up in `GRAND_RESULTS.md`. Headline:

- `grand.py` 1,008 technical combos, `mind.py` 1,008 psychological combos, each
  with a matched null. 560 markets, holdout 2018-2026.
- **6 of 969** and **2 of 1,008** beat owning the same market, by +0.3%/yr and
  +0.2%/yr. On the psychological grid the best NULL (+0.7%) beat the best real
  result (+0.2%). Nothing there.
- Two flattering bugs found and fixed: the EMA12 exit was firing on the next bar
  (entry is below the EMA by construction), and scaling in was scored on average
  cost, ignoring the cash left uninvested. Both had produced fake winners.
  Scaling adds no return; it cuts the worst 5% from -17.2% to -11.0%.
- **The higher-timeframe filter measured negative** on both grids, per trade and
  per day in the market, with matched holding periods. Not just cash drag.
- `giveback.py`: the structural exit (break of the last higher low) is still in
  the trade at the peak **87%** of the time; RSI-relief exits leave a median
  **+20%** behind on ~70% of trades. The stated exit rule is the good part of
  the method. Cost of holding: worst 5% goes -11% to -30%.

## 8. Things not to redo (updated)

(previously section 6)


- Cross-sectional signal ranking (16 signals, 0 survivors)
- Chart pattern event studies (16 patterns, 44 combos, 0 survivors)
- Hourly parameter sweeps (1,586 configs; three nulls all beat the real data)
- Confluence scoring with correlated oscillators
- Adding a second momentum indicator to RSI

- Large grids of context x trigger x exit x management (2,016 tried, 8 winners,
  all inside the noise, one grid lost to its own null)
- Psychological fear/relief triggers as a mechanical entry (8 tried, ~2%/yr
  spread end to end -- the trigger is not where the outcome is decided)

## 9. The trend engine is validated (2026-08-22)

The engine was rebuilt from scratch after being graded WRONG on 11 of 11 charts
across three rounds. It now reads 19 of 19 blind-sampled charts the way the user
does, with no complaints.

**What was wrong.** Every version until now decided the state by watching price
cross levels. It should have been reading the SEQUENCE OF PIVOT LABELS. The bugs
that came out of that, each caught by the user looking at a chart:

- an unguarded breakout rule re-tested every bar, flipping the state candle to
  candle -- 22 state changes in 90 bars on TGT, including a 1-candle downtrend
- entry conditions were persistent facts (`lower_high` stays true for months),
  so the exit set FLAT and the entry restored the old state on the same bar --
  a trend literally could not end, pinning SPY at DOWN through a 440->520 rally
- no pending higher LOW, so a rally that never pulls back could never register
- the breakout tested the most recent pivot high instead of the highest recent
  one, painting BTC's falling highs green
- the display absorbed pivots at their CONFIRMATION bar while the chart drew
  labels at their FORMATION bar, so all shading landed exactly PIVOT_BARS late
- EQ needed four pivots, not two, and had to be backdated to its first pivot

**The agreed definitions.** UP = a HL and a HH. DOWN = a LH and a LL. Two pivots
each. EQ = HL LH HL LH, four pivots, with EH/EL counting as boundaries. A trend
dies the moment a contradicting pivot confirms, or when price closes through the
level. Death goes to UNSHADED, never straight to the opposite. Unshaded is a
real answer and it is common.

**Two states, deliberately.** `trend_state` is causal and is the only one that
may touch a backtest. `display_state` backdates a confirmed trend to its anchor
pivot and is for charts; it looks ahead by construction.

**Tests.** `test_trend.py` (8 hand-written cases) and `test_approved.py` (19
blind-graded charts, frozen by state mix). `audit_chart.py` is NOT a test of
correctness -- it passed clean on all three broken engines, because it only ever
compared my code to my code.

**Still open.** One chart was marked wrong for red shading starting before the
pattern's first pivot. Every fix for it cost 2 of the 8 regression cases, so it
was reverted rather than shipped. Needs a better formulation.
