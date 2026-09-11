# Dashboard review, 2026-09-07

Every page, what it is for, whether it earns its place. Written after the
trend-ride rounds; the dashboard was reorganized to match.

## Live (updates on its own)

**/bb, Backburners live.** The real forward test of the backburner method,
with the current standard exit and the A/B grades. Earns its place. Keep
writing what you did next to each row; that is the only way to compare the
paper trades to your real ones.

**/rides, Trend rides live.** New tonight. The 40 focus names, every 15
minutes, under the rule as you graded it in. A signal is a second higher low
confirmed on the last closed bar; it becomes a ride at the next open, or is
skipped if the open is under the low or too far above it. Four futures
signals were waiting for Monday's open when I finished.

**/scan, Scanner.** Useful as a live universe browser (sizes, movers,
exchange source). But "what is firing" still ranks by the old rider signals,
which failed the 2015-2022 test. It needs re-basing on the two live rules
(backburner selective, second higher low). Until then, read it as attention,
not signals. Card says so now.

**/markets, All markets deep pass.** A weekly sweep of 4,000 names tagged
with old rider behaviours ("dip into the EMA", "ride the EMA"). The list is
useful; the tags are not. Keep as a liquidity list, retag later.

**/desk.** Positions plus "lights" from the old rider conditions. No
positions are loaded, and the lights are the dead rule. Moved to Tools;
candidate to fold into the scanner or drop.

## Trend riding

**/trendstudy (was /trendnames), which names behave.** Renamed 2026-09-07 evening; now leads with trend behaviour (pivots per trend, fakeouts, how trends die), every trend drawable. Every name and timeframe
graded on how it trends and what your ride made on it, against BTC, SPY or
ES, with both halves, beta, and a drill-down to every trade and a chart for
each. Same depth as /names.

**/ridecharts, Grade the rides.** Your grading tool. Three rounds so far,
85 charts, every rule change came from here. Keep.

**/trends, the numbers.** The 4-year results. It had a stale header from the
first version at the top; now the current rule and its numbers sit first
and the older versions are below as history.

**/trendcases (archived).** The first version's charts with the entry and
stop you rejected. Kept so the before and after is visible.

## Backburners

**/names.** Scorecard with grades, halves, beta, drill-down. Keep.

**/cases.** The drawn campaigns with notes. Keep. Its charts were redrawn
after the split fix.

**/study.** The 4-year numbers. Keep.

**/backburner (archived).** The very first coding of the method, before the
study. Superseded.

## Tools

**/paint.** Grade the trend colouring itself on random windows. Low use now,
but it is the only page that checks the engine every other page relies on.
Keep.

**/rules.** New: the one rules file, readable in the browser.

## Archive (nothing live)

**/log, the old rider forward log.** It still ticks hourly and still sends
alerts for a rule that failed its frozen test. It stays running so the
record is unbroken, but its alerts are noise next to the backburner and ride
alerts. Recommend: turn its alerts off, keep the log.

**/v4, /validate, /trades.** Early picture rounds. Archive.

## Things I fixed while reviewing

- Stock intraday data had after-hours bars sprinkled in (fake gaps, one
  fake -11% trade). Removed everywhere.
- 81 stocks had unadjusted splits in the intraday files (a 2-for-1 looked
  like a 50% crash). Fixed, 15 odd ones left.
- NVDA, TSLA, NFLX, PLTR were not in the data at all. Pulled and adjusted.
- Every chart is now measured for overlapping labels before it is saved.
- Studies and chart drawing run on 16 cores with no console windows.

## What I would do next, in order

1. Re-base the scanner's "firing" on the two live rules.
2. Your ABT note: enter a higher chart's uptrend on the lower chart flipping
   down-to-up. It is the answer to the chase problem and to "why the 4th
   higher low".
3. A range/chop read that matches your eye. My flip counter did not.
4. Turn off the old rider alerts.

## Second pass, 2026-09-07 afternoon (full check for errors)

Every Python file compiles, every page and API answers 200, and no page
throws a script error. Found and fixed while checking:

- **The study's trailing stop did not match the charts or the live tracker.**
  In the study, once a trade was up 3x the risk the last-higher-low line was
  thrown away and only the 8-bar trail remained, and the risk was not floored
  at a normal bar's move. Half of all "trail hit" exits ended under the buy
  price. The charts you graded and the live /rides page never had this flaw
  (there the trail only raises the line). The study now does the same, and
  every trend number (/trends, /trendnames, rule #17) is being re-run.
- **Live backburners were firing on after-hours stock bars.** Nine 15m stock
  rows opened at 19:30 on Friday. The live logger now keeps regular-session
  bars only, like the study; those nine rows are marked "voided".
- **The session filter kept two pre-market bars a day** (09:00 and 09:15) on
  the 5m/15m stock charts. Fixed; the hourly 09:00 bar (which holds the open)
  stays.
- **A skipped ride signal could come back as a duplicate row** on /rides
  (AAVE was listed twice). Fixed, and the duplicate removed.
- **The live tracker compared bar times to your PC clock.** Crypto bars are
  UTC, stock and futures bars are New York time, your clock is neither. It
  now uses the right clock for each. (Both pages say which zone their times
  are in.)
- **The "next chart" column on /trendname always said "flat"** because the
  study was never handed the higher chart. Fixed in the study; the column
  hides itself until a run fills it.
- The backburner scorecard on /names was built before the split fix; rebuilt.
- The favicon 404 on every page is gone.

## Third pass, night of 2026-09-07 to 08 (after the all-hours data)

Everything re-run on the Polygon all-hours stock data, every chart set redrawn,
every page walked in the browser, every Python file compiled.

Found and fixed:

- **/trends was blank.** One unescaped apostrophe in a note I added ("the next
  chart's") broke the whole page script. Fixed, and the page checked in the
  browser after.
- **/name pages for newer names 404'd** (NVDA, TSLA and others), and older ones
  showed the campaigns from before the data fix. The per-name event files were
  never rebuilt after the study re-ran. Rebuilt (841 files); the split step is
  now part of the post-study chain.
- **Chart labels.** The backburner case charts (/cases) still had notes sitting
  on the candles and buy numbers piling up ("13579"). Redrawn in the lane style
  with one measured pass per chart: 17 of 17 clean. Crowded pivot labels in the
  side panels ("HHHH") now step to a second row. The panel "buy"/"sold" words
  sit under and over their markers, clear of pivot labels. The trend-window
  chart was reporting "clean" without measuring (a wrong call that was being
  swallowed); it measures now.
- **Live loops.** A failed tick used to retry every 20 seconds for the rest of
  the slot. It now waits for the next slot.
- **Jargon** on /scan, /markets, /paint, /trends ("print", "wash", "spans")
  replaced with plain words.
- **All 20 cores, biggest names first** for every study and chart run.

New tonight, on the pages:

- /trends: "Twenty MORE ways to manage the exit" and "Twenty ways to buy".
- /exitcharts: four batch-two exits added to the dropdown.

Still open, unchanged from before: the scanner's "firing" marks are the old
rider rule; forex intraday is not real; the old rider log (/log) still sends
alerts; 4h stock rides hold overnight (a choice, not a finding).
