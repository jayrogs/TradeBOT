# Project State — hardened 2026-08-29

The one-page map. Read this before building anything.

## The load-bearing stack (re-founded 2026-09-01)

| file | role | guarded by |
|---|---|---|
| **`structure.py`** | **THE BACKBONE.** The owner's grammar in one module, in the owner's words: pivots (directional legs), trend SPANS (wick-kill, per owner 2026-09-02), the EQ machine, and TWO CLOCKS — `review` (formation, for pictures/grading) and `live` (confirmation, causal, for anything that acts). `states(df, causal=True)` and `now(df)` are what the scanner asks. | `test_structure.py` (9): invariants both clocks, causality, live⊆review, **fixture floor ≥65% agree / ≤12% conflict**, owner-graded regressions |
| `panel.py` | pivot detector (`zigzag`, directional legs) + the OLD v1 state machine (still feeds the rider gate and `trend_v1`) | 24/24 approved, 8/8 hand cases, causality |
| `scanner.py` | 8-timeframe scan; **trend letters now come from the live span clock** (`trend`), v1 kept as `trend_v1`; EQ from the overlay; backburner-5m/15m flags = RSI at or under 30 under a live up-span | smoke + battery |
| `crypto.py` | candles + universe. **The universe is Coinbase ∪ Kraken USD pairs** (the owner's exchanges, 2026-09-03), ranked by CoinGecko cross-exchange volume, floor $5M/day (~270 names). Coinbase is the candle source when it lists the name (paginated, deep); Kraken otherwise (**720 bars per timeframe, hard API cap** → Kraken-only names have thin 12h/monthly frames); OKX is a last-resort fallback only. Kraken calls are paced by one lock (~1/s). `/scan` has a size picker (top 30/100/300, `n` param); the 24h column is computed from the bars (was hard-coded 0). | smoke (`python crypto.py`) |
| `signal_log.py` | forward ledger, frozen rider-v1 rule; every row carries `in_range` + `span` (live clock at entry) as metadata — rule unchanged | `test_livelog.py` (8) |
| `notify.py` | alerts: always to `livelog/alerts.log`; webhook (Discord/Slack-style) when `livelog/alerts.json` has one. Server's hourly loop fires SIGNAL / CLOSED alerts | `--test` |
| `rider_lab.py` / `rider.py` / `rider_v4.py` | canonical rider rule library (frozen) | `test_harden.py` |
| `chartkit.py` / `context_sheet.py` / `trade_pics2.py` / `pics_spans.py` / `pics_trend.py` / `pics_random.py` / `regen_windows.py` | rendering; all backgrounds via the backbone's review clock | harden 3 (renderer == scored rule) |
| `server.py` | Flask :5001 — `/scan` `/log` `/v4` `/paint` `/api/gen`; **no-store** on every response (stale-tab gremlin killed). **Launch it with `run_server.bat`** (→ `run_server.ps1`, WMI `Win32_Process.Create`). Anything started from a tool shell — `nohup`, and even PowerShell `Start-Process` — stays inside that session's job object and is killed when the session ends (died 22:10 on 2026-09-03 that way, no error logged). WMI spawns outside any job; verified ancestry python ← cmd ← WmiPrvSE. Not auto-started at logon (owner's call). | route smoke |
| `history/*.csv.gz` | 11y hourly, 1.2M candles, audited clean (30 original crypto names) | — |
| **data pulls (2026-09-05 overnight)** | Owner wants everything free kept locally, all timeframes 5m→1w. Sources by class: **crypto** Coinbase (`backfill_crypto_intraday.py`: 4y 15m/5m for the 30, hourly+15m for 67 more Coinbase names) and OKX for Kraken-only names (`backfill_okx.py`, 173 names, 1h/15m, 5m for the top 30) → `history/`, `history/crypto_15m/`, `history/crypto_5m/`; **stocks/ETFs** Alpaca (`backfill_stocks.py`, top 600, 1h/15m/5m/1d since 2021, IEX volume only) → `history/stocks/`; **futures** Databento (`backfill_databento.py`, 30 CME roots, 4y 1-min → 5m/15m/1h, $119.66 of the owner's $125 credit; 13 cheap roots + ICE not bought) → `history/futures/`, daily from Yahoo (`backfill_yahoo.py`); **forex** Dukascopy (`backfill_dukascopy.py`, 32 pairs 4y minute → 5m/15m/1h, scale verified vs Yahoo) → `history/forex/`, plus index/commodity CFD stand-ins → `history/futures_cfd/`. `overnight.py` waits for the pulls, reruns `studies/backburner_study.py`, runs tests, writes `logs/morning_report.txt`. | — |
| `studies/` | the one-shot verdict scripts (rider_2015, boom, surge, short, ride/wind/red studies, null_check, rider_oos) — the lab notebook, runnable from root | — |
| `archive/` | dead experiments (panel_v2, trend_v2_score, dial/diff renderers, verdict-era renderers) | — |

Run all tests: `python run_tests.py` — trend 8, approved 24, rider 6, harden 26, livelog 8, **structure 9**.

## Grammar verified on every timeframe the owner uses (2026-09-02)

Intraday round (15m BTC/SOL/ETH, 5m XRP/DOGE, pinned windows in
`validation/intraday_plan.json`): owner verdict "they look good" — the
1.0-ATR leg filter and the wick-kill spans read correctly at 5m/15m. With
the earlier 1h/4h/daily fixture, the backbone is now owner-validated across
5m, 15m, 1h, 4h, and daily. Pivot detector is CLOSED (1.0 ATR, directional
legs) — the owner considers pivots settled.

## The rule vocabulary (frozen meanings)

- **live trend**: knowable at the bar's close from confirmed pivots — what every gate uses. **Verified causal** (zero mismatches, 400k bars, prefix test in `test_harden.py` 3b). **Forward meaning is timeframe-dependent** (measured 11y, all names): daily UP +2.64% vs DOWN +0.35% next 10 bars; 4h +0.74% vs +0.38%; **1h UP +0.15% vs DOWN +0.16% — no forward information at hourly scale**. The 1h gate is a flicker filter, not a forecast; daily/4h trend lights are the meaningful ones. HTF-alignment as a rider gate was measured (ride_study) and does not improve rider outcomes — the exit dominates. The **backdated** trend repaints history; charts must never paint it (that bug burned two grading rounds).
- **touch**: low reaches the EMA12 (± 0.25 ATR) while the candle body holds above (10% grace). "Wick belows are holds."
- **entry**: after N defended touches, buy the **confirmed close** of the next held touch, EMA rising, trend UP at that bar.
- **promote1 exit** (canonical): body close under the EMA exits while unproven — but only if the close is under by **more than 0.25 ATR** (owner spec 2026-08-29, measured on both eras in `wind_study.py`: mined +0.32→+0.53, frozen +0.07→+0.14); once up 1%, only the 3%-under-EMA trail exits.
- **minimum wind** (owner spec, same study): entries require the live trend UP for **≥ 5 bars** (`MIN_WIND`); both eras improve at 5, the eras disagree beyond it (frozen loved 20, mined punished it). The trail follows the EMA **down** too (not a ratchet) — `ratchet1/2` modes exist and are tested but added no edge.
- **fills**: confirmation and price must never come from the same bar (three fake edges died that way — see memory `entry-fill-lookahead`).
- **null**: random entries pushed through the IDENTICAL exit, conditioned on the same gates.

## Verdicts (all one-shot, pre-registered, on data never tuned on)

Exploration = 2022-07→now (burned by months of tuning). Frozen = 2015→2022-07.

1. Rider everywhere: **−0.20%/trade** on frozen. The 2022-26 "+0.8%" was curve-fit.
2. Exploding names (+25%/7d): entry beats a conditioned null by +1.3% but **absolute −0.41%**; blind dip-buying in explosions loses −1.7%.
3. ATR-scaled exits: **−1.10%**, worse than fixed %.
4. Surge gate (relvol≥2.2, 7d≤4.8%): +0.85% in exploration → **−1.43% frozen**; entry −2.7% vs its own null.
5. Shorts (exact mirror via price inversion, full 11y): **−0.14%**, entry −0.36% vs a *positive* random-short null (+0.22%). 2018 shorts +1.31%; 2022 flat.
6. Partials (both eras agree): 62% of green trades die back, yet **every partial variant costs EV** — sell-half-at-+1% burns ~¾ of the edge. Comfort, priced.
7. Exit-on-red (`red_study.py`, both eras, under the adopted rule): **every variant destroys the mean** — even DOWN-only-when-promoted erases ~95% of the edge (mined +0.67→+0.03, frozen +0.36→+0.00) while raising win% (the partials story again). Holding through red is the price of the tails; the 3% trail is the only red protection that pays.

**The unifying finding**: the exit asymmetry (cut fast / never cap winners) makes money in both directions even with random entries; the touch-confirmation entry costs about what it's worth (~±0.3%) everywhere. Profit concentration: top 10% of trades ≈ 97% of gross profit. Touch-count odds are ~70% flat regardless of count.

**Do not** resurrect any of these with tweaks. New ideas: pre-register, run once against `history/`, believe the answer. Nothing found on 2022-26 has ever transferred to 2015-22 (0 for 4).

## The trend-grammar bench (2026-08-31) — read before touching panel.py

v1 remains the live engine (24/24 approved, proven causal). `panel_v2.py` holds the graded experiments; `trend_v2_score.py` runs the full trial (paint + approved + causality) in one command. The user's 1,636 painted bars (`validation/trend_marks.json` + `trend_windows.json`) are a **permanent fixture** — any grammar candidate must beat v1's 44/44/12 there AND hold the approved suite.

Verdicts so far: **band-EQ dead** (imprisons trends, lost twice). **Resumption dead** (owner: one pivot past the old top is "only 2 pivots, shouldnt count" — ZBH). **EQ label-memory fix promising but unshipped**: the owner's HL-LH-HL-LH rule starves in v1 because kills wipe the label memory (chart 4: literal textbook sequence, no call); with an unresettable last-4 window it catches 26/156 of painted EQ vs 2, scores 46/41/13, but produces short-lived blues the owner rejected ("a 2 candle blue is just stupid") and pattern-wall deaths trade that for conflict (45/40/15).

**SHIPPED 2026-08-31 (owner verified the blue washes) as an OVERLAY, not a replacement** (`panel_v3.py` + `trend_v3_score.py`): v1's trend engine stays byte-identical (24/24 by construction); the owner's EQ runs beside it as an independent layer (unresettable label memory, pattern-extreme walls). Scoreboard: paint conflict 12%->7%, EQ matches 2->26, fully causal; census: trend+range coexist on 1.0% of bars, range-alone 2.8%. Charts hide sub-4-bar blips (display-only hindsight); the causal overlay keeps them. First-draft lesson recorded: independent UP/DOWN machines are WORSE (regime pollution; UP+DOWN never coexist anyway) — only trend+range overlap exists in nature. AWAITING OWNER VERDICT on the paint page's blue washes before wiring into scanner/panel. The original phrasing of the problem, in the owner's words: "trends can overlap... we need a way to ID that."** One-state-per-bar with hard boundaries fights how the owner reads structure (a downtrend's last LH can simultaneously be a range's first LH). A v3 should be designed around that, not patched into v1. Also parked: "two pivots is noise unless continued" (DOW note — raises the birth bar, cuts against the silence complaint; needs its own graded round), and pivot granularity (runaway moves print no pivots until the top — XRP wick note).

## Detector fix (2026-09-01, owner-caught): DIRECTIONAL legs

`zigzag`'s leg filter used abs(), so a bounce whose PEAK was below the prior
TROUGH could register as a "high", satisfy alternation, and strand LL
markers mid-slope (PENGU 2025-05-03). Legs are now directional. Impact:
zero inverted pivot pairs remain (32k pivots checked), all 5 suites green
including 24/24 approved, fixture 68/23/10 (statistically unchanged).
Granularity DIAL verdict: stays 1.0 ATR (owner, after the 5-window 0.75
comparison — "I dont agree with the pivots that did get brought up").

## The final grammar scoreboard (2026-09-01)

The owner's span grammar + EQ overlay vs the 1,636-bar fixture (painted
blind, before spans existed): **69% agree / 21% silent / 10% conflict**,
vs the old v1 engine's 44/44/12. EQ matches 25/156 vs 2. Span backgrounds
now official on every chart surface (v4, paint, context sheets — all via
chartkit/span_states). Generation stamps on grading pages (`/api/gen`).
OPEN DECISION: the causal twin — whether the rider's trend gate and the
scanner letters switch from v1's state machine to "span currently open"
(knowable live: pair confirmed, no death yet). That changes the frozen
forward-log rule → version bump + era re-runs. Owner's call.

## Open, untested, or agreed

- **Live signal log** — BUILT 2026-08-29: `signal_log.py` + `/log` page. The frozen rule (version-tagged rows) stamps every signal hourly via a server thread; outcomes settle through the canonical exit; the user logs their own trades beside it. Append-only, fills = confirmed closes, `late` flag for catch-up scans. **The server must be running for the ledger to accrue.** Expectation to beat: +0.67%/trade raw, +0.28% over matched null (both-era edge ~+0.25%, but the knobs were chosen on both eras — the log IS the validation).
- **Backburner study + forward log (2026-09-04/05).** `studies/backburner_study.py` (824k campaigns, 837 names, 5 classes, 5m→1w; refined rules: stop = max(half the 3-day run-up, 3 ATR), class costs, breakeven partial + 12 EMA ride); pages `/study`, `/names` (per-name grades vs BTC/SPY), `/cases`. Verdicts: fast-chart backburners pay only on hot, liquid names with no oversold for 3+ days; adds beyond 3 lose; rarity (10+ days since last oversold) is the strongest filter; the ATR stop was the drag (owner right); crypto fees decide crypto. **`backburner_log.py`** = the live twin (server thread, 15-min ticks, `livelog/bb_campaigns.csv`, page `/bb`, alerts on selective setups); replay-tested equal to the study's walk on real BTC campaigns. Frozen: do not tune on live results.
- **Backburners** (owner's word — never "ladders"): first causal draft in `backburner_live.py` (running = 1h live span UP; 5m print = RSI at or under 30; 15m/30m/1h prints as escalation; run ends when the 1h span dies), pictures via `pics_backburner.py` at `/backburner` (notes set `backburner`). AWAITING the owner's grading + the five questions at the bottom of the module. `backburner.py` is the older one-name CLI tracker.
- Scanner `/markets`: refreshed 2026-09-03 on the span engine, 4,189 names x 8 timeframes (`python bigscan.py --json bigscan_latest.json`, ~45 min). Its crypto rows still come from the pre-Kraken universe until the next run.
- **Stock history via Alpaca (2026-09-03, keys in `livelog/alpaca.json`, owner-written, never printed):** `alpaca.py` + `backfill_stocks.py` → `history/stocks/<SYM>_<tf>.csv.gz`, intraday bars back to **2021-01** (measured). Verdict on the live scanner: **stays on Yahoo** — the free feed's volume is IEX-only (~2% of consolidated, SPY 1.4M vs ~60M) so volume flags/liquidity gates would misfire, and it pages by bar-minutes (~9 requests per symbol per 300 days of hourly), slower than Yahoo's batch. Opt-in flag `"scanner": true` exists but is not recommended.
- Descriptive study (`ride_study.py`, 9,726 entries): calm names > violent, relative-volume surge > quiet, extended-week = poison. Valid as *scanner attention filters*, not as validated trade signals.

## Process rules that keep saving us

1. Grade charts by eye after every change to a rule — every major bug was visible in pictures before tables.
2. Charts must render the same arrays the scorer used (enforced by `test_harden.py` part 3). Trend/window charts must be assembled ONLY through `chartkit.py` (`bundle` + `render`, no optional layers) — a fourth hand-assembled renderer silently dropped the EQ wash and burned an owner grading round (the PENGU miss, pinned as harden 3d).
3. Edits by string-replace must `assert old in s` — silent no-op replaces shipped a half-edited renderer once. Anchors containing backslashes get mangled by the shell layer — use the Edit tool for those.
4. Snapshot `backups/code_*.zip` before refactors (`server.py` was once corrupted to 281k lines).
5. Yahoo 15m data: request `59d`, never `60d+`. Coinbase granularity 300 bars/request.

## Name pages (2026-09-05)
- `/name/<kind>/<sym>` (static/name.html): every backburner a name had in the 4-year study, grade chips per timeframe, by-year table (to check a grade held up), every-trade table with a **chart** button. Reached from /names (symbols are links) and /bb rows.
- Data: `studies/split_events.py` splits validation/backburner_events.csv.gz into validation/name_events/<kind>_<sym>.json (837 files). Rerun after every study rerun.
- Charts: `/api/name_chart?sym&kind&tf&t` renders through pics_cases.render (now uses the study's run-up stop, all timeframes, CLASS_COST) into validation/name_cases/, cached on disk; frames cached 15 min in memory; one at a time (lock).
- `/bb`: "A and B names" filter button; "what you did" note box per row (tradenote set=bb; ids are strings now).
- Sizing test `studies/size_by_runup.py` -> validation/size_by_runup.txt: sizing the first buy by the rally into the recent 30-day high does NOT help (bigger rallies win more often but lose more when they lose; flat sizing is best or tied everywhere except 12h 100%+ rallies, n=151).

## Standard backburner exit = higher-low break (2026-09-06, owner's call)
- Ride after the breakeven partial: hold until a bar CLOSES under the last higher low (most recent confirmed low pivot formed after the first buy, above the backburner low). Before one forms, the backburner low is the stop. Code: `studies/backburner_study.py: low_pivots(), hl_break_exit()`; used by the study (`ret_ride`/`ride_end`), pics_cases.walk, backburner_log (VERSION bb-v3).
- The 12 EMA close exit (`ema_ride_exit`, EMA_TOL_ATR 0.25) is kept as the alternate: `ret_ema`/`ema_end`, `ema_dw` in study.json. The OLD rider promote1 exit is gone from the backburner code (it stopped exiting once up 1% and rode bleeds back to the low -- HBAR 1h 2026-08-07).
- 4-year result per $: higher-low beats 12 EMA on every tf (4h +1.21 vs +0.92, 1d +2.67 vs +2.37, hot 15m +1.05 vs +0.59).
- Sizing by run-up (studies/size_by_runup.py) does NOT help: flat sizing.
- Study rerun chain: `rerun_study.bat` (study -> split_events -> name_scorecard -> pics_cases; ~65 min), writes logs/rerun_study.done.

## Trend riding study (2026-09-06, overnight)
- `studies/trend_study.py` -> validation/trend_study.json + trend_events.csv.gz (10.6M rows: 6.4M higher-low entries + 4.2M control entries), page `/trends` (static/trends.html), launcher `run_trend_study.bat` (~2h15).
- Trade: confirmed higher-low pivot, buy next open, hold until a close under the last higher low (level raised by later HLs), cap 30 days. Control: entries every 25 bars, same exit off the last low pivot. Eras: before / first / second.
- VERDICT: the higher-low entry has NO edge over the control on any timeframe (4h +0.46% vs +0.36%, 1d +1.23% vs +1.15%, 1w worse). ~83% of entries stop out small. Trend context (uptrend open, higher tf up, EMA slope, HL count, first HL off a bottom) does not separate winners. Hot names on 4h/1d make 3-4x the average (+1.8%, +3.3%); pivot low well under the 12 EMA +0.49% vs ~0. 62% of HLs print a new HH before breaking (70%+ with a steep EMA) but the exit gives it back on the rest.
- 157 rows with zero opens (SOXS, SNDQ, XCN...) were dropped after the run; study should filter fill>0 next time.

## Trend ride charts (/trendcases, 2026-09-06)
- `pics_trend.py` draws 30 trend-ride trades from trend_events.csv.gz on 16 A/major names, grouped by what actually happened (sold-then-ran, sold-near-the-top, quick small loss, big winners, hot names, deep dips). Each chart: previous low, the HIGHER low, the buy, the STEPPED level being held, the sale, and 60 bars AFTER the sale with "best it reached" so the exit can be judged. Notes box per chart (tradenote set=trendcases).
- `context()` caches pivots/EMA/ATR/RSI per frame: walking every trade was minutes, now 200 walks in 0.3s.
- Open suspicion from the charts: the level raises to EVERY new higher low, so routine pullbacks sell (CRDO 1h 2022-07-19 sold -3%, ran +38% after). Variant to try next: raise the level only after a new higher HIGH confirms, or lag it by one pivot.

## Trend ride variants (2026-09-06, after the charts exposed the technique)
- `studies/trend_variants.py` -> validation/trend_variants.json, shown on /trends ("Same idea, different technique"). 13 variants x 837 names x 15m/1h/4h/1d, 21.8M trades, 34 min, launcher run_trend_variants.bat.
- Entries: next open (v1) / skip if the open is >1 ATR above the pivot ("no chase") / resting bid at the pivot (10 bars). Stops: newest HL (v1) / one behind / raise only after a new HH; each with an optional 0.5 ATR buffer.
- BEST: no chase + one behind + 0.5 ATR buffer: +0.10%/trade, +0.17% over drift (v1 +0.04%/+0.10%, control +0.06%). 4h +0.69% (edge +0.73%), 1d +1.59% (edge +0.80%). Positive in all 3 eras and in stock/crypto/etf/futures.
- Resting bid at the pivot LOSES (-0.13 to -0.15%): it fills on the dips that keep falling.
- OPEN: "left behind" is +4% overall, +11% on 4h, +16% on 1d -- the higher-low stop cuts live rides. Next: partial + looser trail, or hold the first break while the higher tf is up.

## How to hold a trend ride (2026-09-06)
- `studies/trend_partials.py` (partials), `studies/trend_leash.py` (hold lengths + drawdown), `studies/trend_trail.py` (stop width sweep) -> validation/trend_partials.json, trend_leash.json, trend_trail.json; shown on /trends.
- ALL of these now run PARALLEL (16 workers, ProcessPoolExecutor, workers fold their own sums) and WINDOWLESS: launch with `pythonw.exe studies\<x>.py --procs 16 --log logs\<x>.log`; each writes logs/<x>.done when finished. 74 min -> ~10 min. No .bat/cmd wrappers (they flashed console windows). run_server.ps1 also switched to pythonw + `server.py --log logs\server.log`.
- Stop width: wider is better all the way to 14 normal bars' moves under the highest close (+0.78%/trade) vs the higher-low stop (+0.06%). 8 bars = +0.42% with a -2.7% typical worst dip; positive edge in ALL THREE eras at every width tested.
- Partials cost return and buy real risk reduction: no partial +0.61% (dip -3.6%), a third at 2R +0.42% (dip -2.7%), half at 2R +0.33% (dip -2.2%).
- Fixed-time holds (14/30/60d, no stop) make the most (+1.5% to +7%) but dip -8% to -22% and have NEGATIVE edge in the pre-2022 era: bull-market number, not a rule.
- 15m is flat under every rule; 4h and 1d carry everything.

## Trend ride = trend death (2026-09-06, his rule)
- `studies/trend_death.py` -> validation/trend_death.json (3 min on 16 cores). Entry: confirmed HL while causal state is UP, next open, no chase. Exit: the causal UP span ends (structure.spans(causal=True) s1) -> sell open s1+1. Partial: none / a third at 2R. Compared with trail-8 and the old higher-low close exit on the same entries.
- Result: trend dies +0.49%/trade, held 9 bars, worst dip -0.2% (trail-8: +0.53%, 125 bars, -2.9%; higher-low close: +0.07%). 15m positive for the first time (+0.29%, vs drift +0.40%). 1d +2.23% (+1.96% vs drift). Partial costs ~0.1%.
- Selectivity tested: next chart UP/FLAT/DOWN (+0.52/+0.49/+0.45) and uptrend age (<3 / 3-10 / 10+ bars: +0.51/+0.48/+0.48) -- neither separates, as coded.
- `pics_ride.py` draws this rule (live-clock trend colours, lanes, partial diamond), liquid names only (>$20M/day); page /ridecharts; notes set=ridecases (bug: it posted to trendcases before, his 4 notes are in validation/trade_notes_trendcases.csv).

## Trend ride, graded rules (2026-09-06 evening)
- His 27 notes: validation/trade_notes_ridecases.csv (+4 in trade_notes_trendcases.csv). Rules extracted: LH is not an exit; entry = next HL after the trend opened; higher charts matter; tolerance for wicks; partial risk floor; liquidity/gap filter; never say "sold early" on an HL break.
- `studies/trend_ride.py` -> validation/trend_ride.json (11 min, 16 cores). Exits: HL wick break at tol 0.15/0.35/0.6 normal bars, and the NEXT chart's HL break. Conditions folded: nth HL, higher chart state, stretched (6+ green closes on the next chart), giant bar in the last 10.
- Results: HL-break exit +0.01%/trade overall (5m -0.03, 15m -0.03, 1h +0.08, 4h +0.32, 1d +0.68, 1w +4.67), win 14%, worst dip -0.4%. Next chart's HL as the line: +0.11% overall, 4h +0.85%, held 48 bars. Filters: none separate (stretched and giant-bar slightly BETTER). Tolerance: no difference.
- `pics_ride.py` now scans and draws on 16 cores (48 s for 30 charts), measures every chart (`overlaps()`), liquid names only ($50M/day, no gappy intraday, no unadjusted splits), story under each chart, `--log`.

## Trend ride, round 2 of grading (2026-09-06 night)
- His 30 notes: validation/trade_notes_ridecases.csv. Facts pulled per case (scratch facts.py): HONA bought UNDER the pivot on a gap; CSCO 1h -11% was an after-hours earnings bar; PFE/SPY/BMY/AMD wicks were 0.40-0.49 normal bars (tolerance now 0.5); PM's preferred entry was blocked by the 1-bar chase limit (2.28 bars).
- Changes: `backburner_study.session_only()` drops pre/after-hours stock bars everywhere; pics_ride + trend_ride: his pivot count (HL/HH/EH/EL run, >=3 pivots with an HH), EL counts as HL, skip if open<pivot, TOL 0.5, no overnight on 5m/15m/1h stocks, trail 8 bars under the highest close once up 3R (adopted), chase variants 1/2/3, spacing condition, wick depth in the story, higher panels anchored 90 bars before the buy, 3-row legend.
- trend_ride.json: trail-once-up-3R beats waiting 3-4x on 1h/4h/1d; no-overnight lifts 15m to +0.03% and halves dips; chase: tight on fast charts, loose ok on daily; spacing/hi/nth/stretched/giant: no separation. Weekly: trend rule > trail.
- pics_ride: scan + draw parallel (16 cores, ~35 s), `--log`, `--seed`.
- NEXT: lower-chart flip entry for a higher-chart trend (his ABT note). Also: the 4h stock gaps question (treat like fast charts or swing?) is open for him.

## Trend ride, round 3 (2026-09-06 late)
- 28 notes -> validation/trade_notes_ridecases.csv (keyed by sym|tf|t now; rounds 1-2 archived in his_grades_trend_rides.csv).
- Rules applied: SECOND higher low only; 1h holds overnight (5m/15m still close at the bell); chase 1 bar fast / 3 bars daily+; chop measure (trend flips in 60 bars) and fakeout re-entry (close back above the broken line within 5 bars -> buy next open) added to trend_ride.py.
- Results (2nd HL, trail once up 3R): 5m -0.03, 15m -0.03, 1h +0.33, 4h +0.97, 1d +3.27, 1w +6.75 (1w trail is below drift: use the plain HL rule there). nth: 2nd +0.21 / 3rd +0.23 / 4th+ +0.34 -- his preference, not an edge. Chop measure flags 78% as choppy, no separation. Fakeout re-entry ~= fresh entry (1d +3.48%, 1h +0.41%). Spacing far-above slightly worse (+0.16 vs +0.22). Stretched slightly BETTER again (+0.51%).
- pics_ride: 2nd HL only, story adds chop count and the higher chart's state; 30 charts, measured clean.

## Overnight 2026-09-07: focus list, trend names page, live rides, dashboard review
- `focus.py`: 20 stocks / 10 futures / 10 crypto. NVDA, TSLA, NFLX, PLTR were missing from tier1 entirely; pulled (pull_focus.py) and split-adjusted. `trend_ride.py --focus` -> validation/trend_ride_focus.json (focus: 4h +3.5%, 1d +8.5% per trade with the trail; futures ~0; crypto +0.33% vs drift +0.38%).
- `studies/trend_names.py` -> validation/trend_names.json (+ _focus), per-name event files in validation/trend_name_events/; grades A-F vs benchmark with halves, beta; pages /trendnames and /trendname/<kind>/<sym>; `/api/trend_chart` draws any trade via pics_ride.render. Raw rows cached in trend_names_rows.pkl (`--agg-only` re-aggregates).
- `ride_log.py`: live trend rides on the focus names, 15m/1h/4h/1d, every 15 min (server thread _ride_loop); signals wait for the real next open (state "signal"), skip if the open is under the low or chased; page /rides, notes set=rides; alerts "RIDE ...".
- Dashboard reorganized: Live / Trend riding / Backburners / Tools / Archive (collapsed). /rules serves CLAUDE.md. /trends now leads with the current rule and its numbers. REVIEW.md holds the page-by-page review.

## 2026-09-07 afternoon: full error check (see REVIEW.md "Second pass")
- Study trail (trend_ride.hl_break_exit) now matches pics_ride.walk and ride_log.live_walk: risk floored at a normal bar, trail only raises the line. Re-run: 1h +0.07%, 4h +0.35%, 1d +1.11%, 1w +4.03% (was +0.33/+0.97/+3.27/+6.75 with the old "trail replaces the line" version). Variants (replace at 8/4/2 bars) running -> validation/trend_ride_trail.json (+_focus). CLAUDE.md #21, #22 added.
- backburner_log.frames: stocks regular session only (9 after-hours rows voided). session_only: 09:30 start on 5m/15m, 09:00 kept on 1h.
- ride_log: dedupe by id; last_closed uses the bars' own clock (UTC crypto, New York stocks/futures).
- trend_names passes all frames (next-chart column now real); /trendname hides that column when it does not vary.
- name_scorecard rebuilt (13:08) on the post-split events; `--log` flag added. favicon route.

## 2026-09-07 evening: /trendstudy (was /trendnames), trend behaviour
- studies/trend_names.py: per trend (causal spans, up and down): more pivots after opening, died by wick / contrary pivot / still open, gain. Per name/tf: trends, piv_per_trend, fakeout (0 more pivots), long_share (3+), wick_death, longest_piv, up_piv, down_piv, behave_score = piv_per_trend * (1 - fakeout). 5m added to TFS. "all" row = equal weight per timeframe. Event files carry `trends` per tf.
- Pages renamed: /trendstudy, /trendstudy/<kind>/<sym> (old routes redirect). Drill-down has behaviour cards + every trend with a chart button -> /api/trend_window (pics_trendwin.py: window, floor/ceiling step line, x at the kill, measured with overlaps()).
- Finding as coded: the spread is narrow. Median 1.5 more pivots per trend, 40-45% fakeouts, on nearly every name; daily separates most (0.6 to 1.3). Best behaved are steady large caps (BAC, GE, CSX, BLK, IVV) which are NOT the best ride names.
- Trail variants (trend_ride --variants) -> validation/trend_ride_trail.json (+focus): replace-the-line at 8 bars: 1d +3.00%, 4h +0.90%; raise-the-line (as graded): 1d +1.11%. Shown on /trends "The trail question".
- Crypto 1h/1d history ends 2026-08-29 (15m ends 09-05): needs a top-up.

## 2026-09-07 night: all-hours stock data (Polygon)
- Owner: "we need to trade all hours". Alpaca free feed had 0-3 extended-hours bars a day (that was the fake-gap source). Polygon Stocks Starter ($29/mo, keep data locally): backfill_polygon.py pulled 5m/15m/1h, 5y, 04:00-20:00 NY, split-adjusted, for all 604 stocks (32 threads, ~12 min). First pull wrote blank prices (Series aligned to a new index) -> fixed, re-pulled, verified all 1,812 files. Old files in history/stocks_iex/. history/stocks/SOURCE.json all_hours -> frames_for keeps every bar; live pages LIVE_ALL_HOURS=True (Yahoo prepost). Thin extended hours on ~400 names.
- Re-run on it: trend_names (+5m, pivots x travel default sort), trend_ride: 5m -0.01, 15m 0.00, 1h +0.11, 4h +0.32, 1d +1.11; focus 4h +1.17, 1d +2.95. Backburner (bb-v3): 1h +0.02, 4h +0.66, 12h +1.77, 1d +2.68 per $ overall; stocks alone 1h +0.20, 4h +1.07, 1d +3.83. Scorecard rebuilt.
- Polygon Starter is 15-min delayed; real-time is Developer $79. Alpaca free feed is real-time from one exchange.

## 2026-09-07 night: twenty exit managers
- studies/exit_managers.py (one pass per entry, all managers), trend_ride.py --exits (2nd HL only, no partial), pics_ride.py --manager/--out/--per-tf, /exitcharts (validation/exit_cases/<slug>/), /trends "Twenty ways to manage the exit". See CLAUDE.md #23.

## 2026-09-07 night: entry study (studies/entry_study.py). See CLAUDE.md #24. Forex still excluded (intraday not real).

## Night of 2026-09-07/08: batch-two exits, full review
- exit_managers2.py (22 exits), trend_ride --exits2 -> validation/trend_ride_exits2.json (+focus). Wide chandeliers (8, 12 bars) made the most per trade but their "before 2022" edge is negative; "tightens with profit" (5->3 at 5R->2 at 10R) beats chandelier 5 on edge with the same dips; "the second lower high" beats the graded rule in every era. See CLAUDE.md #25.
- Review pass: /trends apostrophe bug fixed; name_events rebuilt (split_events now in the chain); case charts redrawn lane-style and measured; chartkit staggers crowded pivot labels; panel titles moved above plots; overlaps() now measures titles; 143 charts, 0 problems. All studies default to every core, biggest names first.

## 2026-09-08: ranges (EQ): /eq live scan (eq_scan.py + server _eq_loop), studies/eq_study.py (4 readings x 2 sides x 3 exits, factors: touch, height, next chart, RSI), pics_eq.py -> /eqcharts. See CLAUDE.md #26. As coded the textbook trade makes nothing; the range definition needs his grading.

## 2026-09-08 pm: eq_break.py (positioned range trades + direction reads), rectangle ranges in eq_scan, /eq call column, eq.html tables, pics_eq on the rectangle + hold-for-break. See CLAUDE.md #26.

## 2026-09-08 pm: his review of the day
- Break tolerance study (`--tols`, CLAUDE #27): looser line = more per trade, proportionally longer holds; about even per day in trade.
- Phantom pivots (CLAUDE #28): live readers see ~1 in 5 pivots the study never has; Pine rewritten with rollback (`tradingview/pivots_trend.pine`); "live-honest" study still open.
- /trendstudy rewritten in plain words (steps per trend, fakeouts, how far it ran, score); 10 default columns, "show all the numbers" toggle.
- Focus list on the dashboard. /eq rows have an on-demand chart (/api/eq_chart). Polygon (now Massive): Developer is also delayed; real-time is $199.
- Hold times (his rules): 1h 17 bars, 4h 20 bars, daily 21 bars. Per day in a trade about SPY's pace on daily; 4h focus about 4x it.
- Dashboard now opens with five idea pictures (pics_idea.py -> static/ideas/): one real trade each for the trend ride, the exits question, the backburner, the range break, and what the trend study counts. All measured clean.
- 2026-09-08: studies/portfolio.py (his question: trades per year, not per trade). Hold times in calendar days; a wallet with N slots, 60 runs. Stocks on the 1h: +35-37%/yr at 10-20 slots vs SPY +17.3%. The daily chart is the worst wallet despite the best per trade. Whole thing hinges on cost: gone by 0.25% round trip. See CLAUDE.md #29.
- 2026-09-08: which names play best (CLAUDE #30). Picking carries only on the 1h. For stocks the filter is how big the name's moves are, not its past result: the 142 biggest movers picked at the halfway point made +64%/yr over the next two years vs +40.7% for all names, +25.2% for the rest, SPY +18.7%. Crypto: picking mostly avoids losers. 4h/daily/ETF/futures: no carry. Win rate is a trap.
- 2026-09-08: forex clock bug found and fixed (CLAUDE #31). Dukascopy seconds read as milliseconds; every "1h" forex file had one bar a day and had overwritten the real Yahoo hourly files. Repaired from cache, no re-download. 11 pairs now have 4 years of true hourly bars. Forex loses under the trend ride as coded.
- 2026-09-08: tested his framing directly (CLAUDE #32). Going up predicts nothing. How much a name MOVES is the whole edge (+83%/yr out of sample vs +39.6% no pick, SPY +18.7%). Predictability, measured as straightness or as follow-through after a higher low, does not pay and fights movement (correlation -0.34 / -0.32). Crypto: no trait predicts.
- 2026-09-08 review: EQ is his word, "range" purged from every page, chart and comment. check_pages.py added (50 checks, 0 problems; 191 charts across 12 sets measured clean). Fixed: duplicate column heading on /eq; box height now shows both "when it formed" (the number the 4-bar rule tested) and "now"; the old rider log's UTC clock labelled; the cost curve and the movers result moved out of typed page text into portfolio.json so pages read them. Two stale numbers in CLAUDE.md corrected (#17 later higher lows, #30 movers).
- 2026-09-09: owner corrected the EQ definition. An EQ is a COIL (higher lows into lower highs, tightening), not the flat box I built. studies/eq_coil.py + pics_eqcoil.py + /eqcoils, 24 examples drawn clean, awaiting his grading before any study. The old rectangle work is renamed CHANNELS. His cost is "like nothing", so the 1h and big-mover findings stand.
- 2026-09-10 overnight: EQ (coil) study finished. He graded 24 drawings first; two corrections applied (break = wick not close, edges = flat steps not angled lines). Shape and supply are real; direction is callable at 61% vs 44%, stable in all three eras and every chart size, from two reads that both run opposite to intuition (the line tested more holds; it resolves against what it came in from). No trade pays: all ten have a negative median on every chart. Caught a look-ahead bug (trades were using the coil's final floor, not the floor at entry) and an outlier trap (+2.83% daily was one 2024 trade at +167%). Study now reports medians beside every average.
- 2026-09-10: he called out that I had drawn the EQ shape but never the trades. Doing so exposed a real entry bug (buying bars whose low had already broken the floor, producing stops above the fill). Fixed; the "no version pays" verdict survived, now 0 of 60 combinations with a positive median. New page /eqtrades shows every buy, stop and exit.
- 2026-09-10: his correction on EQs: direction from the bigger chart, and the trade is buying the higher low and selling part at the lower high for a free ride. New study eq_freeride.py. Checked which reading of "the bigger chart" matches his eye on eight obvious trends: the daily 50 EMA and the daily 200 EMA both 8/8, every pivot-based reading missed several (his NVDA May 2022 example read "no trend" on the engine). Page /eqfree, drawings pics_eqfree.py.
- 2026-09-10: resting limit orders tested (at the floor / quarter / halfway up the EQ). Worse than buying after the higher low confirms on every chart: the far line is reached 6-44% vs 55-65%. The two-bar wait is the filter, not a flaw. Best row: 4h, after the HL confirms, all out at the lower high, with the daily 50 EMA, +0.15% a trade, steady across eras. Small. Also fixed a blind spot in the shared chart check (tick labels and plot edges were not measured).
