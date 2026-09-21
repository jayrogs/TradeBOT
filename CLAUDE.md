# Rules for working with Jay on this project

One file. Read at the start of every session, before anything else.
Edit it freely. If a rule here and a memory note disagree, this file wins.

## How to talk

1. Short and plain. Answer first, then the why.
2. No jargon, no invented terms, no acronyms without the plain phrase.
   Say "a normal bar's move", not ATR. Say "worst dip", not drawdown.
   Never: span, wash, print, run, rung, ladder, clock, causal, grammar.
3. His words. **backburner** = RSI at or under 30 on a running name; never "ladder"/"rung".
   **EQ** = the sideways box; never call it a "range" (2026-09-08: "you seriously calling eq's
   ranges? wtf bro i set the language"). If he names a thing, that name is the only name.
4. Numbers go in a small table, never packed into a paragraph.
5. No absolutes. "As coded, this did not beat the control" — never "this doesn't work".
   He has caught the technique being wrong every time I said something was dead.
6. If he has to say "simplify" again, that is my miss, not his.

1b. ADHD MODE, ON PERMANENTLY (2026-09-12, his link: github.com/ayghri/i-have-adhd). Ten rules, and they
    outrank my habits:
      1. Lead with the next action. The answer first, context after, if at all.
      2. Number multi-step work. One discrete action per step.
      3. End with ONE concrete next step.
      4. Suppress tangents: finish the thing, raise side issues separately.
      5. Restate state every turn ("step 3 of 5 done: schema updated"). He should never have to scroll to know
         where we are.
      6. Time estimates in minutes, never "a bit".
      7. Make wins visible in plain terms ("the page saves now"), not buried in a paragraph.
      8. Errors matter-of-fact: what broke, what it means, what I am doing. No apologising twice.
      9. Cap lists at five items.
     10. No preamble, no recap, no closers.
    Bends only for: an explanation he asked for, anything destructive, a debug spiral, real ambiguity, and when
    the task itself needs more words. Off only if he says "stop adhd mode" or "normal mode".

## How to work

7. Just do it, ask later. Never hand him a command to run. Never ask to confirm a routine step.
   Batch questions for after the work.
8. Use ALL 20 cores for anything that takes more than about a minute (his words 2026-09-08: "always
   using all cores possible"): studies, chart rendering, data pulls, data fixes. Feed the biggest names
   first so the cores stay full to the end. One core is only for a handful of files.
9. Never launch anything through cmd.exe or a .bat file: black windows pop up on his screen.
   Launch with `pythonw.exe script.py --procs 16 --log logs\name.log`, detached with WMI.
   The server starts the same way (`run_server.ps1`).
10. Draw the trades before any verdict. Every study of his methods gets a page of random
    example charts, on every timeframe, before I report a number.
11. Every chart is MEASURED before it is saved (pics_ride.py `overlaps()`: label on label,
    label on candle, label off the edge, label on the price/time scale, label hanging off its own plot --
    the last two added 2026-09-10 after one slipped through) and the log says "clean" or lists the problems. Zero
    problems on every chart, then open at least three and look. Nothing may sit on the candles:
    markers and labels live in empty lanes above and below price, joined by a thin dotted line.
    Looking at one chart and calling it done is how he got the same overlap back three times.
12. Load a page and look at it before saying it is done. A page that SAVES anything must check the
    server's answer and show NOT SAVED in red when it fails. (2026-09-10: his whole grading of /eqfree was
    lost to a page that flashed "saved" while the server rejected every save -- wrong field names.)
13. When the technique is wrong, code the variants and run them. Do not ask which one to try.
13b. GitHub (github.com/jayrogs/TradeBOT): whenever a tracked file changes, I commit and push it to main myself,
    straight away. No branches, no pull requests. The app shows a "+N -N / Create PR" bar whenever the computer
    and GitHub differ, and his words (2026-09-11) were "i just dont want to be asked to do something for something
    i didnt do". Keep that bar at zero. Never push TCG_METHOD.md or tcg_slack/ (private TCG Slack content, ignored).

13c. THE BACKGROUND I WORK FROM: `TA_FOUNDATION.md` (2026-09-12, his words: "is there a way i can get you to
    understand trade psychology and technical analysis fundamentals? because youre acting like only the things we
    talk about exist for the most part"). Auction/balance vs trend, structure, location and confluence, moving
    averages as context not signal, volume and liquidity, the expectancy math, variance and sizing, the psychology
    that decides what is holdable, regimes, and how a test must be built. HIS CONSTRAINTS ARE REQUIREMENTS, NOT
    NOISE: if he wants a partial, find the best system that takes a partial. Every study now reports enough for a
    human to judge holdability: expectancy, win rate with average win vs loss, worst losing streak, worst dip, time
    in trade, trades a year. He is invited to correct that file; his corrections win.
13d. NEVER TEST ONE FLAG AT A TIME AND CALL IT THE METHOD (2026-09-12). Nobody trades a single condition. Tests are
    built as a stack -- regime, context, location, trigger, risk, management, size -- one skeleton with switches,
    and the control must skip exactly what the rule skips.

13e. TRADING IN THE ZONE, read in full 2026-09-12 (`TA_FOUNDATION.md` #11). Douglas backs HIS instinct, not my
    arguing: scaling out to a risk-free stop is the textbook, aim at about 3:1 reward to risk (then a sub-50% win
    rate still pays), take EVERY occurrence of an edge over a sample of 20 and judge the sample, define the trade in
    ONE chart size with the bigger charts as filters, and let structure -- not a dollar figure -- set the stop.
    Studies now report R multiples and a sample-of-20 view (how many blocks of 20 trades made money), and no
    variant without a predefined stop is reported as a real trade.

13f. MURPHY, TECHNICAL ANALYSIS OF THE FINANCIAL MARKETS, read 2026-09-12 (`TA_FOUNDATION.md` #12, his "gold
    standard"). A trade has three parts -- forecasting, timing, MONEY MANAGEMENT -- and this desk has only ever
    worked on the first two. His numbers: risk at most ~5% of equity a trade, aim 3:1 or better, split into a
    trading unit and a trending unit (Jay's partial and rest, published in 1986), add only to winners and in
    smaller size, raise size after an equity DIP not after a streak, and put stops beyond a valid level with
    volatility setting the distance. A level's weight comes from time spent, VOLUME traded and how recent it is,
    and a broken level reverses role. RESEARCH QUEUE from that chapter, none of it tested here: 40-60% retracement
    zones, role reversal, level weighting, VOLUME confirmation (we have the column and have never used it), gaps as
    levels, trendline breaks, oscillator divergence.

13g. NO NEGATIVE VERDICTS FROM MY OWN CODE (2026-09-12, his words: "i need an actual analysis thats not just
    jumping to conclusions based on your poor understanding of something. if youre making shit up on your own, it
    better be with positive results, and not just so you can say something doesnt work"). Every "as coded, nothing
    pays" I have reported was later traced to my bug -- the levels bug, the look-ahead flags, the caching. So a
    result is reported as "MY VERSION of this produced X, and here is its weakness", never as "the method fails",
    and a rule is not put down until there are at least two honest implementations, a drawn chart, and his read.
    Effort goes into making a rule work. `PLAYBOOK.md` is the distillation of both books plus the room, with the
    scoreboard written that way.

33. TWO BUGS THAT MADE A FAKE WINNER, AND THE TEST THAT CATCHES THEM (2026-09-12, overnight). A backburner
    setup (RSI 14 to 30 and back over on the 5m/15m, half off at 1x the risk, the rest with the stop walked under
    the idea chart's higher lows, only on the right side of that chart's 12 EMA) printed +1.32% a trade on 222,277
    trades, 69% won, positive in every era. All of it was mine:
      - THE PHANTOM PARTIAL: the fast walk booked "half off at 1R" even when price never reached 1R -- half a risk
        of free money on ~two thirds of trades.
      - THE STALE STOP: it measured the stop against the level the trade STARTED with while the trail had already
        moved, so exits were priced at the wrong level.
      - RISK SIZES: with no band, a 0.09%-risk trade printed +44R and a 12%-risk trade counted the same as any
        other. Trades now need the stop at least 3x the round-trip cost away and no more than 5% of price.
    After the fixes: the setup is -0.09R a trade against a control (any bar, same filter and management) of -0.13R.
    The trigger is worth about +0.04R over the control and that repeats across five different managements (idea-chart
    trail, small-chart trail, chandelier 3, small 12 EMA close, all out at 2x) -- real, small, and under the cost
    line as built. `studies/walk_selftest.py` now runs the vectorised walk beside a bar-by-bar walk on four real
    names and fails unless they agree on every trade; it found all of the above. RUN IT AFTER ANY CHANGE TO A TRADE
    WALK.

34. THE OVERNIGHT RUN, 2026-09-12: what survived and what did not.
    THE RULE TABLE (`studies/tcg_lab.py`, 809 names; `--slow` runs the same stack on 1h/4h entries with the daily
    and weekly as the idea chart). On the FAST charts every base trade is negative and the rules move it by
    hundredths of a percent. On the SWING charts the picture is different and better:
        eq_hl (a higher low inside a live EQ), walked stop, 1h/4h    base +0.135% a trade (n 3,543, won 32%)
          with the name STRONG against its benchmark                 +0.437% (n 1,523) vs -0.044% without
          with two of three charts above onside                      +0.296%
          with price on the idea chart's 12 EMA side                 +0.250%
          with the idea chart oversold                               +0.312%
        eq_break, 1h/4h, all out at 2x: strong +0.197% vs -0.240%; role reversal +0.265% vs -0.097%
    RELATIVE STRENGTH IS A SWING TOOL, NOT A FAST ONE: the ratio read did nothing on 5m/15m (#26n) and is the
    single biggest rule on the 1h/4h. That matches how Joey actually uses it.
    THEN THE VERIFICATION (`studies/swing_verify.py`, all names, R and blocks of 20): the swing EQ entry with the
    strength filter is +0.487% a trade and +0.29R on average -- but the MIDDLE trade is -0.302% (-0.24R), it wins
    33% of the time, only 29 of 65 blocks of twenty made money, and the worst losing streak is 23. Stocks alone are
    flat (+0.035%, median -0.002%); crypto carries the average (+0.772% average, -0.581% middle). This is the
    #26c lottery shape, not a clean edge. Its control (any bar, same management) is -0.08R, so the entry is worth
    something real; the shape is not yet holdable.
    NOT VERIFIED, NOT CLAIMED: nothing from tonight is tradeable as it stands.

35. THE BACKBURNER, FINISHED (2026-09-13). Two days of his corrections turned it into a different trade, and it is
    the best thing this desk has found. `studies/backburner_night.py` (7 ways in x 22 reads x 6 ways out, 809 names,
    3.0M rows), `studies/backburner_wallet.py` (what it is worth to an ACCOUNT), `studies/breadth.py`,
    `studies/sector_map.py`, drawings `pics_scalein.py` -> /scalein.
    THE RULE: the DAILY chart; RSI 14 at or under 30; the name OPENED BELOW YESTERDAY'S LOW (the fear gap); scaled
    into as it keeps falling, up to five units a quarter of a normal bar apart while the print stays at or under 30;
    stop at the nearest level under the LOWEST fill; half off at 1x; the rest on a chandelier 3 normal bars under
    the highest close.
    WHAT EACH PART IS WORTH (avg R, control in brackets, flat 1x partial): scale in +0.35 (buy the dip ONCE
    -0.06, which is WORSE than buying a random bar at +0.12); the fear gap +0.65 (+0.12), positive in 10 of 10
    years. OPEN: the 4h chart's fear gap has a BIGGER edge over its control (+0.60 vs -0.11) than the daily's
    (+0.65 vs +0.12) with about as many trades, and only the daily has been through the wallet. "The daily is the
    chart" is not yet proven.
    THE ACCOUNT (reviewed 2026-09-15, see #37): 5,790 trades in 9.5 years, ~611 a year, NOT independent (worst
    day: 172 at once). A CASH account, nothing borrowed, each position at most an equal share and at most 1% at
    the stop, 60 runs: 3 slots +10.6%/yr, 5 +14.0%, 10 +16.9%, 20 +17.3%. WORST DIP, MARKED EVERY DAY
    (`studies/backburner_marks.py`): -28% at ten slots, low on 2020-03-23 -- the wallet's own -17% only looks at
    the account when a trade closes and is not comparable to anything. SPY over the same window +13.1% with a
    -34% worst dip. Ten slots positive in all ten calendar years but BEAT SPY IN ONLY FOUR:
    its value is the bear years (2018 +8.4% vs -6.3%, 2022 +12.7% vs -19.5%) and it lags in bull ones. In 2020,
    the year of the biggest fear gaps, it made +2.4%: the slots were full of early-March stop-outs when the
    March 17th trades fired -- capacity, not edge.
    SURVIVORSHIP: the 601 stock/ETF names are the ones alive TODAY with history backfilled (509 have data from
    before mid-2017); every name that gapped down, printed 30 and never came back is missing. Bounded two ways:
    ETFs ONLY (sector ETFs do not go to zero) makes +11.2% at 10 slots -- BELOW SPY; names traded before 2018
    make +18.3%. The ETF row is the one this bias cannot flatter. Per trade: avg +3.4%, MIDDLE +0.67%, won 58%,
    +0.69R; top 5% of trades make about two thirds of the profit.
    WHAT DID NOT SURVIVE: momentum divergence (best thing on 183 trades, +0.13R and 3 of 8 years on 1,115);
    WAITING FOR THE TURN (on both the 200-day and breadth, "turning up" costs more than half the edge -- you are
    paid for buying while it is still falling); and filtering to weak markets only, which is better per trade
    (+1.36R) but makes the ACCOUNT less because it fires 219 times a year instead of 627 (his #29 point).
    MURPHY'S BREADTH (`studies/breadth.py` -> validation/breadth.json): share of each market's names above their
    own 200-day, per day. Reads true (stocks 77% at the Feb 2020 top, 4% at the COVID low, 17% at the Oct 2022 low).
    Douglas has NOTHING for calling bull vs bear and says so on purpose; what he gives is the standard for judging.
    SECTOR LEADERS (`studies/sector_map.py` -> validation/sector_map.json): every name matched to the leader it
    actually moves with, on the FIRST HALF of its history. 72 of 781 (the inverse ETFs at -0.87, the farm futures)
    get no leader rather than a noise one. THE LEADER CARRIES ITS MARKET ("crypto|BTC"): ticker BTC is a coin AND
    an ETF here, and looking it up by symbol handed every crypto name a 527-bar $35 trust.

36. THREE BUGS OF MINE FROM THESE TWO DAYS, all of which made a rule look better or worse than it was.
    THE DISCARDED LOSERS: when no structure lay under the lowest fill the trade was thrown away. Those are the dips
    that crashed through every level -- the losers -- and scaling reaches lower, so it discarded MORE of them than
    the one-unit rule did (45,767 trades vs 11,809 kept). It made averaging down look free. Now the stop goes one
    normal bar under the position and nothing is ever discarded. THE TELL was a sanity check: trades where only one
    unit filled must be identical between the two rules, and they were not.
    THE 5%-OF-PRICE CAP: the risk band capped the stop at 5% of price, which is fine on a 5m chart and impossible
    on a daily (the nearest structure is 0.8-1.3 normal bars away, which IS 10-16% of price). It threw out
    89-100% of every daily backburner, which is why this desk had never seen one. Murphy's 5% is 5% of the ACCOUNT.
    The band is now 3x the round-trip cost to 4 normal bars.
    THE RUN MEASURED ON THE WRONG CHART: "the name has a huge run going on" was read over the last 60 bars of the
    ENTRY chart -- five hours on a 5m chart. It co-occurred with a dip 993 times in 720,577. It is a DAILY read.
    AND ONE ABOUT MEMORY: every worker loaded every timeframe, so a daily run held SOL's 430,000-bar 5m frame 20
    times over and froze his machine. Studies now keep only the charts they use, and run on 8 cores, not 20.
    AND ONE ABOUT ANALYSIS, not the trade: results must never be split by HOW MANY UNITS filled. Whether a second
    unit fills depends on what price did after the buy, so that split reads the future.

37. THE REVIEW (2026-09-15, Fable, his ask: "i want it to review all of this"). Full write-up in
    `REVIEW_BACKBURNER.md`. What it found, in order of damage:
      - THE WALLET WAS 2.2x LEVERAGED. A 1% risk on a 3.9% stop is a 26% position; ten of those is 260% of the
        account, and the cap was 3/slots. Median exposure 218%, peak 288%, never stated. +40% a year was the
        levered number. Rebuilt as a cash account (`backburner_wallet.wallet`: dollars at entry, capped at an
        equal share, never more than free cash): +16.9% at 10 slots.
      - 23 NAMES HAD SPLIT GLITCHES (a one-day close-to-close move over 60%: APLD at exactly 2.0x, QXO 4.9x, KDP
        0.18x, OVV 0.28x, SOXS 0.054x). QXO's was a +107% "trade". All 23 out (`validation/suspect_names.json`,
        read by the wallet and the drawings), 4% of the profit.
      - THE DRAWINGS AND THE STUDY BOOKED DIFFERENT TRADES (#36 addendum): "chand" takes the partial at the idea
        chart's 12 EMA when further than 1x; the page said 1x. 34 of 59 disagreed. Fixed with "chand1r";
        walk_selftest now owns its reference walk and checks the chandelier (91 compared, 0 mismatches).
      - THE DAILY-VS-HOURLY CLAIM was R against R on different charts with different controls; by edge over
        control the 4h is better. Left open, said so on the page.
    WHAT PASSED: ATR and RSI are causal, pivots are keyed on the confirm bar, the fear gap and every scale-in fill
    use only what was known at that bar's open, the weekly aligns by bar close, breadth is cross-sectional on
    closed bars. The top trades are the March 2020 bottom and they are real (CELH, TSLA, DKNG, BX, SCCO).
    WHAT IT CANNOT FIX: survivorship (no delisted history on this machine). The ETF-only wallet, +11.2% and
    under SPY, is the floor; the all-names wallet, +16.9%, is the ceiling. The truth is between them.
    RULE THAT COMES OUT OF IT: every wallet reports its DEPLOYED share of the account, and no wallet may exceed
    100% without saying the word leverage on the page.
    THE SECOND PASS (same day, his ask: "review everything again"). Checked and passed: the daily open IS the
    9:30 print and the daily low IS the regular-session low (300 of 300 days on NVDA, META, XLV), so the gap and
    the fill are prices a person could get; hold times middle 24 days, 90th 115, 52 trades over a year; 15% of
    trades open in a name already held, and forbidding that changes nothing (+17.1%, -29%); each extra 0.10% of
    cost takes 3% of the average trade. FOUND: THE DRAWDOWN WAS THE WRONG MEASURE. The wallet marked the account
    only when a trade closed (-16%); marked every day like SPY is, ten slots was -28% with the low on 2020-03-23,
    the same day as SPY's -34%. "Half of SPY's drawdown" was wrong; it is about four fifths of it.
    RULE: a drawdown is marked every day or it is not called a drawdown. `studies/backburner_marks.py` does it.

38. GO TO THE SOURCE FIRST, AND THE BACKBURNER THE CHART GUYS' WAY (2026-09-20, his words: "this technique is so good
    but you keep jumping to conclusions"). He was right and it cost a week. BackBurner, EMA Rider, Stair Step and
    Equilibrium are TCG'S OWN NAMED STRATEGIES with written rules (chartguys.com/educational-videos, /ebooks; he has a
    member login; the distillation is TCG_METHOD.md #5b and #10, private). BEFORE TESTING ANY SETUP HE NAMES: find
    their definition, make its preconditions REQUIREMENTS not optional cuts, and print a "not one of these" row
    beside it so the definition's worth is visible.
    WHAT I HAD WRONG ABOUT THE BACKBURNER: I tested every RSI-under-30 print on any name at any time. Theirs is the
    FIRST 5m (or 1h) oversold AFTER A SUBSTANTIAL RUN to a new high on the chart above, long-term trend intact,
    technical pullback only, liquid names, in at 30 and again only at 20, and its PURPOSE is to mark the HIGHER LOW of
    the next chart up. It EXPIRES after the first bounce on that leg. On NVDA's 5m, 174 of 1,398 prints are first
    prints and 1,080 are third-or-later: ~78% of my samples were the prints they say not to take. THEIR EXITS are not
    R-multiples: all out when the bounce reaches the EMAs (the scalp), or half there with the stop moved under the dip's
    low and the rest for the old high. My first rebuild aimed at 2x a stop under the HOURLY structure -- a target 4.2%
    away on a trade that moves 0.6% -- and every row read zero against its control. A ruler problem, not a result.
    WITH THEIR EXITS (`studies/backburner_tcg.py`, 786 names, control = any bar stretched a normal bar under its 12
    EMA), the 1h print marking the DAILY higher low, scalp to the 12 EMA, average per trade:
        not a backburner (no run, trend not intact)   +0.079%   +0.05R
        every oversold print                          +0.143%   +0.07R
        the FIRST print since the daily's new high    +0.252%   +0.10R   10 of 12 years
        first print after a run of 4+ daily bars      +0.307%
        the full setup (run, trend, liquid, recent)   +0.364%   +0.12R   middle +0.447%, won 66%, 9 of 11 years
        first print after a run of 8+                 +0.570%   +0.22R   (n 131)
    EACH OF THEIR RULES ADDS A STEP, IN ORDER. Half at the EMA and the rest for the old high: full setup +0.447% /
    +0.15R, run 8+ +0.603% / +0.32R with a winning middle trade. The 5m shows the same ladder at a tenth the size
    (-0.027% -> +0.035%); at 0.05% cost a 5m stock scalp is marginal, the 1h is where it pays. NOT FILTERED YET: news and
    earnings (their rule), and liquidity is a crude top-third-by-dollars. Not drawn yet (rule 10), not claimed.
    THE FRAME I WAS MISSING (TCG_METHOD.md #10): TASK FIRST, THEN TOOL -- a small-chart pattern is a way INTO a
    bigger-chart scenario, never a trade on its own, which is how every EQ and higher-low study here was built. The
    risk-free trade is THIRDS at technical levels (Guardian / Harvest / Mr Clear), and moving the stop to the entry is
    in their words a rookie mistake -- /eqfree used "rest to breakeven" throughout. Risk:reward ACCEPTS OR REJECTS a
    trade; exits are EMAs, fibs, measured moves and prior zones. A breakout must hold two more closes. 1-2% risk per
    NON-CORRELATED trade, so 172 fear-gap signals on one day are one bet.
    TRANSCRIPTS: YouTube serves captions only to a signed-in viewer and yt-dlp here is from July 2023; the members
    videos are on Vimeo. The e-books (PDFs, readable) carry the method. Their text lives in scratch/ and is never pushed.

## What is settled (do not re-litigate)

14. Confirmation and price never come from the same bar. A buy fills at the next bar's open.
15. Every result is compared against a control (buy any bar, same exit) and against the
    chart's own drift, over three eras (before 2022, first half, second half).
16. The standard backburner exit after the breakeven partial: hold until a bar closes under the
    last higher low. The 12 EMA close is the alternate.
17. The trend ride, as he graded it in on 85 charts (2026-09-06, three rounds). Entry: the
    uptrend already has a higher low AND a higher high (count the ones before it turned green),
    then buy the SECOND higher low only, at the next open. An equal low counts. No buy if it
    opened under the pivot. Chase limit one normal bar's move on 5m/15m/1h, three on daily and up.
    Partial: a third when up twice the risk (risk floored at one normal bar's move). Exit: a wick
    half a normal bar under the last higher low, sold next open. A LOWER HIGH IS NOT A SALE. Once
    up 3x the risk, trail 8 normal bars' moves under the highest close. 5m/15m stock trades close
    at the bell; the 1h and up hold overnight. Stock intraday data is ALL HOURS since 2026-09-07 evening (Polygon, 04:00-20:00 New York, 5 years; owner: "we need to trade all hours"). A
    stop-out that does not follow through (price back above the line within 5 bars) is a re-entry,
    and it tests as well as a fresh entry. Honest numbers (2026-09-07 evening, trail fix #22, stocks all hours): 5m/15m flat, 1h +0.11%,
    4h +0.32%, daily +1.11% per trade (focus list: 1h +0.15%, 4h +1.17%, daily +2.95%). Later higher lows were NOT worse on average
    (2nd +0.07%, 3rd +0.06%, 4th+ +0.07% -- checked against the file 2026-09-08; the old +0.21/+0.23/+0.34
    predated the trail fix #22): "second only" is his preference, applied as such. My
    chop measure (trend flips in 60 bars) flags 78% of entries and separates nothing; higher-chart
    state, spacing, stretched, giant bar do not separate either. Open: his range/chop read, the
    higher-chart read (both ways: entering off a lower-chart flip, and a higher-chart higher low
    overriding an exit), and the 12 EMA rider (parked: "refine ema riders later").
18. Sizing the first buy by how far the name ran up does not help. Flat sizing.
19. The old rider exit (stop trailing only once up 1%) is dead for backburners: it rides bleeds
    back to the low.
20. Stock intraday history was not split-adjusted until 2026-09-06 (`fix_stock_history.py`) and had
    almost no pre/after-hours bars until 2026-09-07 (Polygon pull). Studies on stocks before then are suspect.
    About 400 of the 604 stocks trade thinly outside regular hours: an after-hours pivot there can be one trade.
    Polygon is now called Massive (massive.com). Stocks Starter $29 and Developer $79 are BOTH 15-minute delayed;
    real-time is Advanced, $199/month. (Checked 2026-09-08.)
21. A pivot confirms on the CLOSE of its confirm bar; the sale is the next open. Selling at the
    confirm bar's open inflated the ride from +0.21% to +0.49%.
22. The trail (once up 3x the risk) has two readings of his sentence. As graded on the charts and
    as the live page runs it, the trail only RAISES the higher-low line, and it almost never binds
    (8 bars under the high is usually below the last higher low). Until 2026-09-07 the study
    instead let the trail REPLACE the line (and did not floor the risk): a much looser exit that
    held 3x longer, made more per trade (daily +3.27% vs +1.11%), and gave the whole gain back on
    half of its trail exits. Variants (trail replaces the line at 8/4/2 bars) are in
    `validation/trend_ride_trail.json`. Which reading he wants is open.
23. Twenty exit managers after the same buy (2026-09-07 night, `studies/exit_managers.py`, results in
    `validation/trend_ride_exits.json`, charts on /exitcharts). The loosest stops made the most: a
    chandelier 5 normal bars under the highest close, from the start, ignoring the pivots (daily +4.70%
    vs +1.19% as graded, 4h +1.33% vs +0.36%, both about 2.5x the drift edge), then chandelier 3, then
    his line with a 1.5-bar wick. EMA closes, the SAR and "two closes under the 12 EMA" were the worst.
    Everything fades in the second half of the window. 5m/15m: nothing made money. Not settled: it is
    a different method from the pivots he graded; he has to look at /exitcharts and decide.
24. Twenty ways to buy with the exit held fixed (`studies/entry_study.py`, `validation/entry_study.json`,
    tables on /trends). Under the chandelier exit the buy barely matters on the whole universe: buy-any-
    bar control 4h +0.94% / daily +4.70% vs the second higher low +1.30% / +5.22%. On the focus list the
    pivot buy does earn its keep (4h +3.57% vs control +2.64%, daily +12.1% vs +9.6%). Best buy by edge
    over drift on all names: the backburner bounce (RSI back over 30), then any/second higher low. The
    higher-chart filter (only when the next chart is already up) LOWERED the edge everywhere: it buys late.
    5m/15m: every buy, both exits, loses after cost (edge over drift +0.02 to +0.07%, cost eats it).
25. Batch two of exits (`studies/exit_managers2.py`, `validation/trend_ride_exits2.json`, /exitcharts).
    Per trade keeps rising with a wider stop (chandelier 12: daily +14.3%, focus +29.8%) but the wide
    ones LOST to drift before 2022; they are a bull-market hold. Steadier: "chandelier that tightens
    with profit" (daily +4.2%, edge +1.4%, same dips as chandelier 5) and "the second lower high"
    (daily +2.7%, positive edge in all three eras, pure structure in his words). His graded rule is
    the floor of the table. Nothing works on 5m/15m; a 15% trail on the 15m is the one positive
    number there (+0.12% a trade) and it is a swing trade entered off a fast chart.
26b. WHAT AN EQ IS (2026-09-09, owner, after seeing my drawing): "this picture you sent is a channel,
    not an eq, and eq is a series of HL and LH increasingly tightening". So an EQ is a COIL: rising lows
    pressing up into falling highs, the gap narrowing, until price has to leave. Everything in #26 below
    was built on a flat-floor/flat-ceiling box, which is a CHANNEL. #26's findings are about channels and
    are kept under that name; they are NOT about EQs.
    The coil detector is `studies/eq_coil.py`: the pivot run where every low is a higher low and every
    high is a lower high (an equal one does not break the run), at least two of each, and the last pair
    closer together than the first. Floor = the last higher low, ceiling = the last lower high, both
    stepping inward. Dies on a close outside, or on a lower low / higher high pivot.
    TIMING MATTERS HERE: the shape spans ~20-35 bars but the last pivot only confirms two bars after it
    prints, and by then the edges have converged onto price -- the median coil has about 3 LIVE bars
    after it becomes knowable, and 27% break before they are knowable at all (recorded tradeable=False).
    That is probably the trade rather than a fault: buy the last higher low with the ceiling ~1.5 normal
    bars away, and it resolves within a few bars. His free-ride line fits it exactly ("buy a HL and sell
    partial at LH").
    Charts: `pics_eqcoil.py` -> /eqcoils, 24 drawn at random, all measured clean. NOTHING IS MEASURED YET
    ON PURPOSE: the shape gets graded first (rule 10). Open: does he want 2 pairs or more, must it be
    strictly tightening, and is a close the right break trigger.
26c. WHAT THE EQ IS WORTH (2026-09-10, `studies/eq_coil_study.py`, validation/eq_coil_study.json,
    page /eqcoils). 809 names, every chart 5m to weekly, 179,000 breaks, 828,000 trades.
    HE GRADED THE SHAPE FIRST (24 drawings, notes saved under set "eqcoils"). Verdicts ran from
    "beautiful eq, wow, like a painting" (COST weekly) and "great"/"clean" down to "ugly eq, bad
    candles, would not trade" (JPM 4h). Two corrections came out of it, both applied:
      - THE BREAK IS THE WICK, not the close: "a break isnt a close under the floor, a break is a
        wick though the floor, with slight tolerance, basically for it not to be an EL."
      - THE EDGES ARE FLAT STEPS, not angled trendlines: "i would rather have the thick blue
        outline lines be horizontal lines that continue straight until the next LH or HL."
    WHAT IS REAL:
      - Supply. EQs are everywhere on fast charts and almost absent on slow ones: per name a year,
        5m 73, 15m 28, 1h 5.5, 4h 1.3, daily 0.19, weekly 0.03. The shape always takes about 25
        bars to build, on every chart size, which says the rule is not tuned to one.
      - Only about 3 bars of EQ are left once the last pivot confirms and you could know it is
        there. By then the two lines are ~1.5 normal bars apart, sitting on top of price.
      - DIRECTION IS CALLABLE, and both reads point OPPOSITE to intuition:
          the line tested MORE is the one that HOLDS -> floor tested more breaks up 59%,
            ceiling tested more 46%
          it resolves AGAINST what it came in from -> from a downtrend 57% up, from an uptrend 47%
        Both together: 61% up vs 44%, a 17-point spread on 39,000 breaks, and it holds in ALL THREE
        eras (63/62/60 and 44/44/43) and on every chart size. The chart above is worth NOTHING here
        (52/52/52), and so is which line is steeper (51-53). My first call used those two and came
        out backwards; it is rebuilt on the two that work.
      - Follow-through is a coin flip: 54% run 2+ normal bars, 47% are back inside within 20.
    WHAT IS NOT: no version of the trade made money. Ten of them -- buy the floor, short the
    ceiling, both free rides (his "buy a HL and sell partial at LH"), buy/short the break, both
    failed-break trades, and the call traded with a normal bar of room instead of the line as the
    stop. EVERY ONE has a NEGATIVE MIDDLE TRADE on EVERY chart size. Filtering by the call does not
    rescue any of them. Win rate is ~13-25% throughout.
    THE TRAP THIS ALMOST SET: "buy the floor" averaged +2.83% on the daily and +10.06% weekly, which
    reads like a strong result. It is one trade in 2024 that made +167% out of a couple of hundred.
    Median -1.12%, negative in 7 of 10 years. The study now reports a MEDIAN beside every average and
    the page flags any column where the average is positive and the middle trade is not. NO AVERAGE
    GETS REPORTED TO HIM WITHOUT ITS MEDIAN.
    THE BUG DRAWING THE TRADES FOUND (2026-09-10, after he said "show me examples youre obviously
    fucking something up"): a "touch of the floor" was ANY bar whose low was at or under
    floor + 0.25 bars, which includes bars whose low went straight THROUGH the floor. Those are not
    touches, they are the break. So it bought the open after the EQ had already died. The drawings
    showed it instantly: several trades had a stop ABOVE the fill (printed as a NEGATIVE "bars
    below") and a wall of one-bar losses. Fixed: a touch must land INSIDE the band
    (floor - tolerance <= low <= floor + 0.25 bars) and the next open must not be under the floor,
    the same guard his trend ride has. After the fix: still 0 of 60 trade-and-chart combinations
    with a positive middle result. The verdict held, but it now stands on a machine that showed its
    work. Trades drawn on /eqtrades (pics_eqtrade.py), 24 of them, half winners half losers.
    LESSON: rule 10 says draw the trades before a verdict. I drew the SHAPE and skipped the TRADES,
    and he caught it. Drawing the shape is not drawing the trade.
    Open: the direction call is worth something and nothing built on it pays yet. The stop is the
    suspect -- the shape hands you an entry with the exit ~1.5 bars away. Worth trying: use the call
    on the NEXT chart's structure rather than the EQ's own edges, or wait for the break and use the
    trend-ride rules from there.
26d. THE EQ TRADE HIS WAY (2026-09-10, `studies/eq_freeride.py`, validation/eq_freeride.json, /eqfree,
    charts `pics_eqfree.py`). Two corrections from him after seeing /eqtrades:
      - DIRECTION COMES FROM THE BIGGER CHART: "usually its based on whatever higher timeframe shapes going
        on. Like NVDA, that shit is so much a downtrend, like wtf? why would be long that". #26c bought every
        floor blindly.
      - THE TRADE IS THE FREE RIDE ON THE HIGHER LOW: "the idea is buying the floor and selling the LH ideally
        to make a risk free position". #26c bought a later touch of the floor, but in a tightening EQ price
        does not come back to the last higher low -- it makes a new, higher one. So the long now buys the next
        open after a higher low CONFIRMS inside the live EQ (trend-ride timing), stop a wick through it, and at
        the lower high sells the share that makes the rest free. The short is the mirror.
    WHICH READ OF "THE BIGGER CHART" MATCHES HIS EYE. Checked against eight trends nobody would argue about
    (NVDA May 2022 down, Jun 2023 up, Mar 2024 up; TSLA Dec 2022 down; BTC Jun 2022 down, Nov 2023 up;
    META Sep 2022 down; AAPL Jul 2023 up):
        the daily over its rising / under its falling 50 EMA      8 of 8
        the daily above / below its 200 EMA                        8 of 8
        the engine's trend state one size up, two up, daily        missed several (FLAT in obvious trends)
        the swing shape (last high and last low both lower/higher) on the 4h, daily, big swings, weekly
                                                                   missed several
    Why the pivot reads fail here: inside a big decline the 2-bar pivots flip on every bounce. NVDA's daily
    printed a "higher high" 27 cents above the last lower high in the middle of a 60% crash, and his exact
    May 2022 example read "no trend" on the engine and "mixed" on every swing read. The daily 50 EMA read it
    as down. So the page and the drawings lead with the daily 50 EMA; every other read is kept for comparison.
    RESULTS, entry after the higher low confirms (809 names, 880k trade rows, all 20 cores, 13 minutes):
      - THE BIGGER CHART BARELY SEPARATES OUTCOMES as coded. With vs against the daily 50 EMA, average per
        trade, "all out at the lower high": 1h +0.01 vs -0.05, 4h +0.15 vs +0.03, daily +0.06 vs +0.59 (the
        daily goes the wrong way, small sample). Every other read the same or less. It picks the side he
        would pick; it does not yet pick a better trade.
      - THE FAR LINE IS REACHED 2 TIMES IN 3 (55-67% on every chart). The free ride idea is sound.
      - BUT IT PAYS ABOUT NOTHING, because the entry is late: a higher low confirms two bars after it prints,
        by which time price has bounced most of the way to the lower high. Median target 0.76-0.84x the
        risk (10 big names). Wins +0.63 / losses -0.93 on the 1h, +1.65 / -2.60 on the 4h. And a stop sold at
        the next open adds ~0.3% past the planned stop on the 1h.
      - READ BOTH NUMBERS. Here the MIDDLE trade is positive (4h +0.43%, daily +0.69%) while the AVERAGE is
        near zero (4h +0.09%, daily +0.41% carried by a few): the ordinary trade wins, the losses are bigger.
        That is the opposite disagreement from #26c's lottery ticket. The page now leads with the AVERAGE
        (the money) and flags both kinds of disagreement.
      - The steadiest row: 4h, all out at the lower high, with the daily 50 EMA: average +0.12/+0.17/+0.14 in
        the three eras, middle +0.47/+0.53/+0.45. Small, but it holds.
      - Hold for the break with no partial: lottery shape again (middle -0.70 to -2.35, average positive).
        Rest keeps the stop: middle negative everywhere (a "free" rest stopped out nets about zero minus costs).
      - 5m/15m: nothing, as always.
    RESTING LIMIT ORDERS (the same run, 4.0M trade rows, 18 minutes on 20 cores): a buy limit resting at the
    floor, a quarter up the box, or halfway up, while the EQ is live; stop a wick under the floor; target the
    lower high. WORSE THAN WAITING FOR THE HIGHER LOW, on every chart size:
        how often the far line is reached    after the HL confirms 55-65%   halfway up 37-44%   quarter up
                                             25-31%   at the floor 6-13%
        average per trade, 4h, all out, with the daily 50 EMA:  after the HL +0.15%   halfway -0.14%
                                             quarter -0.14%   at the floor -0.20%
    So the two-bar wait is not a flaw to fix by buying lower. It is the FILTER. When price comes all the way
    back to the floor, that is usually the EQ breaking (the same thing #26 found for channels), and waiting for
    the higher low to prove itself is what skips those. The price of the filter is the worse reward-to-risk.
    THE BEST ROWS, all "after the higher low confirms", with the daily 50 EMA:
        4h, all out at the lower high         average +0.15%, middle +0.47%, reached 65%, n 1,398; eras
                                              +0.12 / +0.17 / +0.14 (steady)
        4h, free ride, rest to breakeven      average +0.17%, middle +0.19%
        daily, free ride, rest to breakeven   average +1.23%, middle +0.29%, n 438 (the average leans on
                                              trailed winners; eras +2.29 / -0.62 / +0.63, not steady)
    Small. Nothing on 5m/15m, again.
    THE DRAWINGS (/eqfree, 20 trades, with the daily 50 EMA) showed three things the averages cannot:
      - COIN 4h short, -8.5%: the daily 50 EMA still read "falling" right at a V-shaped bottom (it lags), and
        price jumped past a -1.7% stop; the sale at the next open took -8.5%.
      - NVDA 5m: a 6-cent EQ in thin premarket, stop one cent from the entry. Noise (see #20).
      - ETH daily: a label hung off the plot onto the price scale and the drawing still passed. That exposed a
        blind spot in pics_ride.overlaps (it never measured tick labels or the plot's own edges). Fixed
        2026-09-10 with a self-test; every chart set drawn before then was measured with the weaker check.
26e. HIS GRADING OF /eqfree (2026-09-10, notes in validation/trade_notes_eqfree.csv). His words, and what each
    one turned out to be:
      - INJ daily "did this buy, after a HH? wtf?" -> A BUG. The EQ was declared on the bar its last pivot
        confirmed, but the two bars between that pivot printing and confirming were never checked: INJ had
        spiked to 28.80 through a 26.37 ceiling there. Fixed in eq_coil.py (the EQ is not declared).
      - RTY_F 4h "a HL then an LH in the next candle immediately after ... thats an anomaly, not an eq" -> in
        the first EQ study 78% of EQs had pivots within 2 bars of each other. eq_coil.coils(min_gap=) added.
      - V 4h "must not be much volume ... was this after hours?" / ORCL 1h "tons of gaps between candles" /
        NVDA 5m "hideous candles" -> he was right every time: 13 of 17, 18 of 31 and 23 of 23 bars outside
        regular hours (NVDA at 6% of normal volume). Stocks now also run on regular-hours bars only.
      - TSM 15m "wtf 91% sold? ... the wins are meaningless if you only have 9% position size" / ETH 1h "sold
        88%" -> the free-ride sizing (sell whatever makes the rest risk free) sells nearly everything when the
        far line sits on top of the entry. Partial is now a fixed third or half, rest to breakeven.
      - SOL 1h / COIN 4h "cant really tell where this is on the daily chart" -> a 30-hour EQ is one daily bar
        with a hairline. The drawings must mark the EQ's span and price on the bigger chart.
      - The ones he liked: ETH daily "great!", XRP 4h "reasonable", CL_F daily "not a bad failure", SOL daily
        "shame a fakeout! was definitely bearish otherwise", SI_F 5m "see how little risk it is".
    Study after the fixes: studies/eq_freeride2.py -> validation/eq_freeride2.json (spacing 0 vs 3, all hours vs
    regular hours for stocks, a third / half / all out / hold / the old sizing, far line bucketed by risk).
    RESULTS (809 names, 2.1M trade rows, 24 minutes on 20 cores). His fixes made the drawings honest; they did
    not change the money much:
      - A fixed third or half instead of the old sizing: about the same average (4h +0.18 / +0.17 vs +0.16),
        and a third makes the middle trade WORSE (4h -0.05 vs +0.19): two thirds ride to a breakeven stop.
      - Pivots 3+ bars apart keeps about a quarter of the trades and barely moves the averages. The daily
        "+6.82%" with a third is a handful of trades (n 103, eras +13.47 / -2.29 / -0.33, middle -0.34).
      - Regular-hours bars for stocks: NOT better in numbers (stocks 4h, a third: all hours +0.07, regular
        -0.31). The candles look cleaner; the trade does not improve.
      - THE LEAD: how far the far line sits. When it is under 1x the risk (TSM's 0.09x was his complaint) the
        partial trades earn about nothing; at 1-2x and 2x+ "half at the far line, rest to breakeven" is
        positive on BOTH numbers: 4h +0.35/+0.18 and +0.47/+0.28, 1h +0.21/+0.03 and +0.30/+0.01 (any spacing,
        all hours, with the daily 50 EMA). Skipping close far lines beats changing the sizing. Not yet run
        as a filter across eras.
      - Steadiest row is still "all out at the far line": middle positive on 1h/4h/daily in all three eras
        (4h +0.47 / +0.52 / +0.47) but the average is only about +0.1% (losses bigger than wins).
      - With vs against the daily 50 EMA still barely separates (4h all out +0.04 vs -0.05). 5m/15m: nothing.
    THE FAR-LINE FILTER (2026-09-11, `studies/eq_farline.py`, validation/eq_farline.json, table on /eqfree): take the
    trade only when the far line is at least N x the risk away. Any spacing, all hours, with the daily 50 EMA.
    Average / middle, then the three eras (before 2022 / first half / second half):
        4h all out, far line >= 1.5x   +0.59 / +0.79   n 320   eras +0.87/+1.14  +0.54/+0.79  +0.54/+0.66
        4h half, rest to BE, >= 1x     +0.40 / +0.19   n 524   eras +1.21/+0.44  +0.33/+0.17  +0.21/+0.20
        4h all out, >= 1x              +0.31 / +0.67   n 525   eras +0.67/+1.17  +0.18/+0.73  +0.33/+0.49
        1h all out, >= 1x              +0.20 / +0.30   n 1,899 eras +0.31/+0.41  +0.14/+0.25  +0.21/+0.32
        (no filter, 4h all out         +0.13 / +0.48;  4h half +0.17 / +0.14)
    The first EQ rows positive on BOTH numbers in ALL THREE eras. The daily is a few trades carrying it (lottery).
    Pivots 3+ apart on top of the filter: small samples, and the 4h turns negative in the second half. Not taken.
    Drawings on /eqfree now use: half at the far line, far line >= 1x, pivots 3+ apart, stocks regular hours
    (the last two are his visual rules; as coded they did not change the money).
26f. WHAT CALLS A FAST EQ (2026-09-11, `studies/eq_fastread.py`, validation/eq_fastread.json). After grading /eqfree he
    said the daily is "trying to base someones mood entirely on the phase of the moon" for a 5m EQ. He was right: the
    daily 50 EMA calls which way a 5m/15m EQ breaks 50-51% of the time (a coin flip). 809 names, 85,000 5m and 39,000
    15m EQ breaks, stocks on regular hours. Share of breaks the read got right (up call -> broke up, down -> down):
        read                                                   5m     15m    1h     how often it gives a call
        THIS chart: price over a rising 12 EMA / under falling 59%    58%    58%    72%
        inside the EQ: tested-more line holds + against prior  60%    59%    59%    22%
        both of those agree                                    66%    65%    68%    9-11%
        NEXT chart up 12 EMA (15m for a 5m EQ ...)             45%    44%    44%    90%   <- BACKWARDS
        this chart's 50 EMA / next chart's 50 EMA / 1h 50 EMA  45-49% (backwards or nothing)
        daily 50 EMA, day's open, next chart's pivot trend     48-51% (nothing)
    The bigger chart's 12 EMA points the WRONG way for the break: the EQ breaks against the move it came from (#26c).
    Joey's rule is about the move AFTER price gets back over that 12 EMA ("Will need to get over 15min 12ema ... for
    anything to stick"), which is a different trigger from where the EQ sits.
    BUT THE TRADE STILL DOES NOT PAY on 5m/15m: buying the higher low inside the EQ WITH any of these reads, half at the
    far line, far line >= 1x: 5m -0.02% to +0.05% average, middle trade -0.05% to 0.00; 15m +0.02% to +0.07%, middle
    about zero. The call is about the BREAK; the in-EQ entry does not capture it. Next: trade the break itself in the
    called direction (`studies/eq_breaktrade.py`). "This chart's pivot trend" gives no call at all (0%), and that is
    not a bug: an EQ is higher lows AND lower highs, which ends both an uptrend and a downtrend, so the moment an EQ
    becomes knowable its own chart always reads "no trend" (checked on BTC 15m: the read itself is fine bar by bar).
26g. HIS MENTOR'S RULES ON THE 5m/15m EQ (2026-09-11, `studies/eq_riders.py`, validation/eq_riders.json; rules from
    TCG_METHOD.md). 809 names, stocks on regular hours. Same entry as /eqfree (the next open after a higher low / lower
    high confirms inside the EQ). The reads were the 12 EMAs of the next three charts up (the next one only, the next
    two agreeing, two of three, all three) and this chart's own 12 EMA. Location was the EQ's line within half a normal
    bar of a bigger chart's 12 EMA. Exits were his: half at the far line then rest to breakeven, all out at the far
    line, a runner out on a close through this chart's 12 EMA, a runner stop walked up under each higher low, and a
    runner out on the next chart up's 12 EMA ("zoom out game").
    WHICH WAY THE EQ BREAKS (share right):
        this chart's 12 EMA                                    5m 60% up / 58% down    15m 59% / 56%
        next chart up, next two, two of three, all three       44-48% (all BACKWARDS)
        EQ ceiling sitting on a bigger chart's 12 EMA          breaks up 55% (5m and 15m)
        EQ floor sitting on a bigger chart's 12 EMA            breaks up 47-48%
        open space                                             51%
    The line pressed against a bigger chart's 12 EMA is the one that BREAKS. The 12 EMAs above point the wrong way
    for this entry, as #26f found.
    THE TRADE: NOTHING PAYS, with any read, location or exit. Best row of hundreds (n >= 500): 15m, next chart up's
    12 EMA, at a bigger 12 EMA, +0.05% a trade, middle trade about zero, eras +0.09 / +0.03 / +0.07. 5m rows about
    +0.00% average with a negative middle trade. The walked-up stop and the 12 EMA runner exits make no difference
    at this size. Fast charts after costs, again (#24, #26c).
    What the TCG Slack says instead (TCG_METHOD.md #9): the room does not trade the fast EQ on its own. It uses it to
    time a 1h/4h/daily higher low at a 12 EMA and holds for THAT chart's move. That is the next study.
26h. TRADING THE BREAK OF A 5m/15m EQ (2026-09-11, `studies/eq_breaktrade.py`, validation/eq_breaktrade.json). The
    reads that call the break 58-68% right (#26f, #26g), applied to the break itself: every break, this chart's 12
    EMA, the inside read, both, the next chart's 12 EMA, and its opposite. Location: the broken line on a bigger 12 EMA.
    Entries: the next open after the break bar, or a stop order resting at the line. Stop: a wick through the EQ's
    other line. Exits: all out at 2x the risk; half at 1x then a runner on this chart's 12 EMA, walked up under higher
    lows, or on the next chart's 12 EMA; hold 20 bars. 809 names, 85,000 5m and 39,000 15m breaks.
    EVERYTHING LOSES. Every break, average per trade:
                              next open        stop order at the line
        5m                    -0.06 to -0.07%  -0.05 to -0.06%
        15m                   -0.12 to -0.13%  -0.06 to -0.08%
    Middle trade negative almost everywhere. The best row of hundreds: 15m, stop order, next chart's 12 EMA agreeing,
    line on a bigger 12 EMA, hold 20 bars, -0.00% average, -0.10% middle, +0.10% over drift (n 1,752). The direction
    call is real; the fast break after costs does not pay, with any of the TCG exits. Together with #26f/#26g: the
    5m/15m EQ as a trade on its own is exhausted as coded. The TCG Slack says the fast EQ is TIMING for a 1h/4h higher
    low at a 12 EMA (TCG_METHOD.md #9) -> `studies/eq_playbook.py`.
26i. THE TCG PLAYBOOK WITH THE FAST CHART AS TIMING, first version (2026-09-11, `studies/eq_playbook.py`,
    validation/eq_playbook.json). Idea on the 1h (timed on the 5m) and on the 4h (timed on the 15m): the big chart in
    an uptrend or its last high a higher high; location = the small bar's low within half a big normal bar of the big
    12 EMA, that EMA rising; triggers = a small EQ breaking our way, a small higher low confirming, small RSI back over
    30, or no trigger; stop under the small structure; half at big RSI 70 or 2x the risk, runner walked up under big
    higher lows or out on the big 12 EMA; all out at 2x as control.
    AS CODED, NOTHING PAID: -0.06% to -0.12% a trade, middle trade -0.10% to -0.23%, won 35-44%, every trigger,
    location, exit and pair. Location added nothing (small higher low 1h/5m: at the 12 EMA -0.06/-0.14, anywhere -0.06/-0.13).
    BUT THIS VERSION DID NOT TEST THEIR TRADE, for two measured reasons:
      - IT FIRED LIKE A MACHINE GUN: 1.65 million "small higher low" trades on the 1h/5m pair. Every 5m pivot while the
        1h leaned up became a trade; they take one position per big higher low.
      - THE STOP WAS SMALLER THAN THE COST. Middle 5m higher-low stop against the round-trip cost: ES futures 0.06% vs
        0.05% (cost = 80% of the risk), SOL 0.38% vs 0.20% (53%), NVDA 0.44% vs 0.05% (11%). 4h/15m: ES 42%, SOL 29%,
        NVDA 6%. With cost at half the risk, no rule can pay.
    Version 2 (`studies/eq_playbook2.py`): one trade per big higher low; the stop never tighter than a fraction of a big
    normal bar; results split by market.
26j. THE TCG PLAYBOOK, VERSION 2: their trade, one idea at a time (2026-09-11, `studies/eq_playbook2.py`,
    validation/eq_playbook2.json). Fixes both flaws of #26i: ONE trade per big-chart higher low (per trigger), and the
    stop pushed out to at least 0, 0.5 or 1.0 of a normal big bar. Setup: big chart in an uptrend, pullback reached a
    rising big 12 EMA. Triggers: small EQ breaks our way, small higher low confirms, or no trigger (next open at the 12
    EMA). Exits: half at big RSI 70 or 2x the risk then runner under big higher lows / out on the big 12 EMA; all out
    at 2x. Split by market. Average / middle trade, far line not involved:
        1h idea, 5m timing        EVERY market and every row loses. Stocks small higher low -0.03/-0.04 (floor 1.0);
                                  ETFs -0.02/-0.03 (floor 1.0); no trigger -0.05; small EQ break -0.06 to -0.08.
        4h idea, 15m timing
          stocks, small higher low (floor 0.5 or 1.0)   +0.01 / -0.01, won 49-50%, +0.05 over drift, n 72,968,
                                                        eras +0.03-0.04 / -0.01 / +0.01 (flat, not negative)
          ETFs, small higher low (any floor)            +0.02-0.03 / -0.01 to -0.03, +0.07-0.08 over drift, n 13,260,
                                                        eras +0.02-0.05 / +0.01-0.02 / +0.03-0.05
          ETFs, small EQ breaks our way                 +0.06-0.09 / -0.04 to 0.00, n 463, eras -0.30 / -0.06 / +0.45:
                                                        a few trades carry it
          stocks and ETFs, no trigger at the 12 EMA     -0.03 to -0.05
          crypto (every row)                            -0.14 to -0.39, middle -0.3 to -2.2 (wider stops lose more)
          futures (every row)                           -0.03 to -0.15
    WHAT HOLDS: waiting for a 15m higher low at a 4h 12 EMA pullback beats buying the pullback outright by about +0.05%
    a trade on stocks and ETFs, in every era. That is real timing value from the small chart, in their words "Scouting
    a TSLA hourly higher low entry". WHAT DOES NOT: as coded, their trade on these charts is about break-even on stocks
    and ETFs and loses on crypto and futures. The management variants (walked-up stop, 12 EMA runner, all out at 2x)
    barely differ. Not yet drawn (rule 10): the break-even rows need pictures before any verdict, and the idea chart
    size may be the constraint -- their room plays the daily/weekly idea (see #26c supply: few EQs there).
26k. HIS SECOND GRADING OF /eqfree (notes saved 2026-09-11 00:47-00:54 in validation/trade_notes_eqfree.csv, on the
    redrawn set: half at the far line, far line >= 1x, pivots 3+ apart). I MISSED THESE for most of a day: I ran
    studies off his chat line and never went through the notes. Always read the notes file after he says "graded".
    What each note turned out to be (checked on the drawings and eq_free_index.json):
      - NVDA 15m "i can barely see that the hl was broken at all, not sure why it sold" -> NOT a stop: bought on the
        15:45 bar, the last of the session, and the 5m/15m stock rule closed it at the bell; next day it ran to 142.
        Fix: no entries on the last bar before the bell.
      - AVAX 5m "getting mogged by 12 ema ... why would you long that" -> bought under a FALLING 12 EMA with a 1-cent
        stop (17.53 / 17.52) on crypto with 0.2% cost. Fix: this chart's own 12 EMA must not point against the trade
        (#26f: 59% right on direction), and the risk must be several times the cost.
      - SI_F 1h "it went so high, why did it never sell. whats the actual sell plan" -> half at the lower high, the
        rest had only breakeven + a 5-bar trail after a break, rode the spike back down (-0.52%). Fix: a real plan
        for the rest, TCG way: sell into overbought / the next 12 EMA or resistance, stop walked under higher lows.
      - ETH 4h 2017 "seems like it gave a ton back" -> the 5-bar trail is too loose on the rest.
      - AAVE 4h "how did it lose so much" -> 3.5% risk plus a gap past the stop: -4.8%.
      - ORCL 1h "man that barely broke it, and it went straight into another eq" -> a small wick hit the stop. OPEN,
        asked him: how far under the higher low counts as broken for the EQ stop.
      - SOL 1d "went straight into ema12 and died as soon as it hit that resistance" -> the 12 EMA as resistance (his read).
      - ETH 4h 2019 / YM_F 1h "fair fakeout"; DOGE 4h "wow" (+21%); NVDA 5m daily-EMA question answered by #26f.
    Round 3 of /eqfree gets those fixes before he grades again.
    THE DAILY 50 EMA AND THE 12 EMA, his follow-ups (2026-09-11): "you didnt address needing more to buying than just
    the chart being over the daily 50ema, thats kind of ridiculous to base a 5m or 15m trade on something like that" ->
    5m/15m drawings switched to this chart's own 12 EMA + the EQ's own read. Then: "the ema 12 on 5 and 15m is usually
    right in the middle of the eq." He is right (GOOGL 5m, META 15m drawings: the 12 EMA runs through the middle of the
    box). Inside an EQ price crosses it on every swing, and right after a higher low confirms price has just bounced
    over it, so "price over a rising 12 EMA" nearly always agrees with a buy. #26f's 58-60% for that read is probably
    that bounce, not direction skill. DO NOT use this chart's 12 EMA as the direction for a fast EQ. What is left that
    is his: "whatever higher timeframe shapes going on" -- ASKED HIM what he actually looks at for a 5m/15m EQ's
    direction before building round 4. Also fixed: the EQ's own read counted touches against the EQ's final edges (a
    small look-ahead); it now uses the edges as they stood (eq_freeride2, eq_fastread, eq_breaktrade). #26f numbers
    for that read need a rerun.
26l. EQ DIRECTION, FIRST POKE AND FOLLOW-THROUGH (2026-09-11, `studies/eq_direction.py`, validation/eq_direction.json).
    His ask: "why not both? and we can compare to see which were fakeouts". Every EQ break scored on the poke (which line
    the first wick went through) and what came next: REAL (ran 2+ normal bars before a close back inside), FAKEOUT (back
    inside within 5 bars without running 1 bar), REVERSAL (the other line broke within 20 bars), weak. Reads taken at two
    moments (when the EQ became knowable, last bar before the break), EQ read without look-ahead, pivots 3+ apart,
    stocks regular hours. 809 names: 20,054 5m, 9,305 15m, 1,515 1h breaks.
    WHAT FAST EQ BREAKS DO:            real    fakeout   reversal   weak
        5m                              22%      24%        43%      11%
        15m                             28%      13%        53%       7%
        1h                              26%      16%        49%       8%
    THE MOST COMMON OUTCOME IS A REVERSAL: the EQ breaks one way and then breaks the other line within 20 bars.
    HIS RULE (his words: "if its in an uptrend on higher timeframes like hourly, or if its above the ema12 on something
    like the hourly and the eq can make a nice higher low from that for the hourly uptrend to continue"), coded as: 1h
    uptrend or price above the 1h 12 EMA, AND the EQ floor above the 1h's last swing low (4h for a 1h EQ):
        poke right 47-49% when the EQ became knowable (all three charts); last bar before the break 49% (5m), 54% (15m),
        58% (1h). Real break the called way ~ the same as the control. It calls 85-89% of EQs: TOO LOOSE as coded ("floor
        above the 1h's last low" is true for almost every EQ). Not his read yet.
    READS THAT ONLY SEE THE BREAK STARTING: price vs this chart's 12 EMA on the last bar before the break (poke right
    82-89%) and the last pivot (63-70%) mostly convert into reversals/fakeouts, not real moves (5m price vs 12 EMA: real
    20% vs control 11%, reversal 37% vs 22%). The 12 EMA's slope across the EQ and the next chart's 12 EMA point the WRONG
    way (44-47%). The daily 50 EMA is a coin flip (50-52%). The EQ's own read 57-58%.
    TIGHT VERSION OF HIS RULE AND THE SECOND BREAK (same run, rerun 2026-09-11): his_tight = (1h uptrend or above the
    1h 12 EMA) AND the EQ IN the 1h pullback (floor within a normal 1h bar above the 1h's last low, or within half a 1h
    bar of the 1h 12 EMA); "2nd" = the call was right on the SECOND break (the first went against it, then the EQ broke
    the other line within 20 bars).
                              calls   poke right   real right   2nd right   ended right   (control: poke / real / 2nd)
        5m, knowable           47%       51%          12%          21%          51%        51% / 11% / 21%
        5m, last bar           48%       56%          13%          19%          52%
        15m, knowable          77%       50%          14%          27%          51%        53% / 15% / 25%
        15m, last bar          78%       56%          16%          24%          53%
        1h (4h rule), knowable 80%       51%          15%          25%          51%        53% / 14% / 23%
        1h (4h rule), last bar 80%       60%          17%          21%          52%        eras 64 / 57 / 62
    AS CODED, NEITHER VERSION OF HIS RULE CALLS A 5m/15m EQ BETTER THAN CHANCE, on the first poke, on real follow-through,
    or on the second break. The one lean: 1h EQs with the 4h read on the last bar before the break, 60% poke right in all
    three eras, but real moves barely above the control (17% vs 14%). No read beat the control on the second break except
    the ones that point backwards on the first (the mirror). Nothing to trade yet. My coding of "the EQ can make a nice
    higher low for the hourly" may still not be his eye: next step proposed to him is to have HIM mark a set of 5m/15m
    EQs (with the 1h beside them) long / short / skip, and measure what his marks share.
26m. HE MARKS THE EQs BLIND (2026-09-11, he said "sure show me", then "and the daily chart too please").
    `pics_eqmark.py` -> validation/eq_mark/ -> /eqmark. 30 EQs from the focus list, 15 on the 5m and 15 on the 15m,
    pivots 3+ apart, stocks regular hours. Each chart STOPS at the bar the EQ became knowable (nothing after it is drawn).
    Left: the small chart, the EQ's flat steps in blue, its 12 EMA in purple. Right: the 1h (top) and the daily (bottom)
    with ONLY bars that had closed by then (1h bars that ended by that moment, daily bars from before that day), 12 EMA in
    purple, the EQ's prices as an orange band. Marks save under set "eqmark" as "long|short|skip | note". What happened
    next (which way it broke, real / fakeout / reversal, bars to the break, move 20 bars later) sits in the index under
    "hidden" and the page reveals it only once all 30 are marked. NEVER TELL HIM THE OUTCOMES BEFORE HE MARKS.
    After he marks: read the notes, compare his marks to the outcomes and to every read in eq_direction.py, and build the
    direction rule from what his long marks share that his short/skip marks do not.
26n. HIS MARKS, AND WHAT A FAST EQ IS FOR (2026-09-11, notes in validation/trade_notes_eqmark.csv: 19 long, 7 short,
    4 skip). Three corrections from him:
      - THE TRADE IS A POSITION ON THE BIGGER CHART, NOT THE BREAK: "we arent trying to have perfect eq breaks with massive
        follwo through, we are trying to establish a position on a slightly larger timeframe. it doesnt have to have
        immediate follow through." My real / fakeout / reversal labels were wrong for his trade: on a 5m EQ the lines
        are ~1.5 normal bars apart, so touching the other line within 20 bars is ordinary wiggle (17 of 30 got called
        "reversal"). FAST EQs ARE NOW SCORED AS A POSITION: price 4 / 8 / 24 HOURLY bars after the next open.
      - SHOW IT ON THE CHART: "it doesnt actually show me on the charts what ended up happening, i just have to read
        more fucking text". The reveal now swaps each chart for an after-chart (`pics_eqmark.py --after`: grey = after,
        his arrow at the entry, dashed = the EQ lines when he marked, hourly and daily continued) plus one small table.
      - AMD 15m "thats not an eq lol fix it": one bar made the second higher low AND wicked a normal bar over the ceiling;
        a bar can only be one pivot, so the engine never saw it. eq_coil.coils(strict_wicks=True, the default now): every
        bar of the shape must stay inside the lines as they stood. It also rejected his YM_F 15m. Every EQ study before
        2026-09-11 evening (#26b-#26m) ran on the looser shape.
    His marks as a position (small sample, no verdict): longs right 9 of 19 after 8 hourly bars and 4 of 19 after 24
    (average -2.08% at 24); shorts 6 of 7 after 8, 3 of 7 after 24. The shorts after a big dump with the EQ under the
    hourly 12 EMA mostly worked at 8. The "long just in case it runs more" marks after a big run (AAPL, MSFT, TSLA, SOL,
    XRP 5m, INJ, NFLX 15m) split 3 up / 4 down at 8 hourly bars and ALL 7 were down by 24: a fixed hold is not his
    management. Next: score his marks with his exits (half at the far line, stop walked under hourly higher lows).
    THE SPACING OF HIGHER LOWS VS LOWER HIGHS (his ask: "check the distance and size bw HL and Lh's ... how closer higher
    lows are or lower highs, and the likelihood of them breaking up or down"; `studies/eq_steps.py`,
    validation/eq_steps.json, 809 names, 39,574 EQs, strict shape). Price spacing (how fast the lows rise vs the highs
    drop), the last step only, time spacing (bars between lows vs between highs), both together, where price sits, last
    pivot. 5m, share: broke up first / higher 8 hourly bars later / higher 24 later:
        every EQ (control)                                       26,540   51% / 51% / 53%
        higher lows rising much faster                            4,355   55% / 51% / 53%
        lower highs dropping much faster                          4,268   50% / 52% / 55%
        higher lows rising faster AND closer together in time       733   60% / 49% / 53%
        price in the top third of the EQ                          7,003   71% / 51% / 53%
        last pivot a higher low                                  13,185   64% / 52% / 54%
    15m and 1h the same shape. AS CODED, THE SPACING NUDGES WHICH LINE GETS POKED FIRST BUT DOES NOT CALL WHERE PRICE IS
    8 OR 24 HOURLY BARS LATER: every group sits on the control, on all three charts and in all three eras.
26. CHANNELS (was called "EQs" in error until 2026-09-09). His trade: get positioned at an edge to catch the BREAK ("buying the floor
    or selling the ceiling in order to be positioned for the eq to break one way or the other ... eqs
    usually break with follow through ... the longer they go on the clearer the breaks"). NOT buy-floor-
    sell-ceiling. Live scan /eq (eq_scan.py, own server loop, every market 5m-1w, a pass is 10-15 min);
    study `studies/eq_break.py` (validation/eq_break.json); charts /eqcharts (pics_eq.py).
    The EQ that matches his eye is the RECTANGLE (30-bar window, high-low box at most 4 normal bars
    tall, both edges touched twice, dead on a close beyond an edge), not the four-pivot rule from
    structure.py (that one lives 3-7 bars and is a coil). Findings, 1.2M rectangle breaks:
    - Direction CAN be called. Three reads agree two-of-three -> UP call breaks up 79% (84% on the
      60-bar box), DOWN call breaks down 78%: the next chart's trend, lows rising/highs falling inside
      the box, which edge got tested more. "What came before the EQ" tells nothing (51%).
    - Follow-through: 61% of breaks run 2+ normal bars; 43% are back at the edge within 20 bars.
      Old EQs (60+ bars) run further (7 bars vs 4).
    - The trade that pays WITH the call is buying the break itself (open after the close above the
      ceiling, out on a close back inside, else chandelier 5): 4h +0.6-0.7%, daily +1.3-1.6%.
    - Buying the floor when the call is UP LOSES: a box pressing the ceiling rarely revisits the floor,
      and when it does that is the EQ failing. Buying the floor pays when the call is DOWN or
      unclear (cheap stop, occasional surprise break): 4h +0.2-0.6%, daily +0.3-2.1%.
    - The free ride (partial at the far edge so the rest cannot lose) gives up a little vs holding.
    - Shorting the ceiling / the break down lost everywhere, both boxes, all charts (2022-26 rose).
    - 5m/15m: nothing pays, again.
    /eq rows have a "chart" link: the EQ drawn on demand from live data (/api/eq_chart, pics_eq.render_live,
    5-minute cache, measured for overlap).
27. How far under the last higher low is a break (2026-09-08, `--tols`, validation/trend_ride_tol.json, table
    on /trends). Nine readings from "any wick under" to "two normal bars under", wick or close. Looser makes
    more per trade on the 4h and daily (daily: any wick +0.90%, half a bar as graded +1.11%, one bar +1.37%,
    two bars +1.86%; edge over drift +0.34 -> +0.52) but holds proportionally longer (16 -> 37 bars) and
    dips deeper (-2.6% -> -5.5%): per day in the trade it is about even. A close under the line = a wick half
    a bar under. On the 1h nothing changes. It does NOT explain the loose-trail gap (#22: 3.27% came with
    giving half back). His choice: he leans to his own line, not the trail.
28. A live reader sees pivots the study never sees (2026-09-08, owner saw the TradingView floor under
    "things that shouldn't have been an uptrend"). panel.zigzag REPLACES a pivot when a more extreme one of
    the same kind follows before an opposite pivot qualifies; the replaced one never appears in the study's
    list. About 1 pivot in 5 is such a phantom; a bar-by-bar reader that acts on it (the old Pine script)
    disagrees with the study on 12.6% of bars and spends 27% of the time in an uptrend vs the study's 30%.
    The Pine (`tradingview/pivots_trend.pine`) now rolls the trend back when a pivot is replaced. The live
    pages recompute from scratch each tick so they self-correct, but a signal fired off a phantom pivot
    stays in the log. Open: a "live-honest" study that acts on phantoms too (rides taken off them).

29. TRADES PER YEAR, not per trade (2026-09-08, his words: "the main difference is being able to make
    multiple trades vs just holding ... the number of trades is everything"). He was right and my earlier
    framing was wrong. `studies/portfolio.py` -> validation/portfolio.json: every signal in time order into
    a wallet with N slots, position sized off the running account, 60 runs with a random pick when signals
    collide. Hold times are in CALENDAR days (weekends counted).
    - Stocks: 1h holds 2.4 days and makes +0.25% (+0.104% a day held); 4h holds 8.3 days, +0.51% (+0.062%);
      daily holds 29.8 days, +1.45% (+0.049%). The chart that looks worst per trade is the best per day.
    - The wallet, stocks and ETFs, 4 years: 1h with 10-20 slots = +35% to +37% a year (1,470 trades a year,
      10-90% spread +31.6% to +39.1% at 10 slots). SPY buy-and-hold over the same window +17.3%. The 4h is
      +16% to +19%. The DAILY chart, best per trade, is the worst wallet: -1.4% to +1.4% a year (only 3.5
      signals per name a year, a month per hold).
    - Slots matter: 1 slot is a coin flip (-22.7% to +21.2%); 10+ slots is where the spread tightens.
    - Crypto on fast charts loses (1h -22.9% a year if never idle); futures near flat. This result is
      STOCKS AND ETFs.
    - THE CATCH: 1,470 trades a year makes it a cost story. At 0.05% round trip (what the study assumes)
      +34.8%; at 0.10% +25.4%; at 0.15% +16.7% (about SPY); at 0.25% it is gone. Before trusting the 1h,
      measure his real all-in cost including the spread and slippage on a market order.
    - Also open: #28 (phantom pivots) applies to these signals too.

30. WHICH NAMES play best this way (2026-09-08). `studies/portfolio_names.py` ->
    validation/portfolio_names.json. Judged per DAY held and against just OWNING the same name;
    "a year" for a name means one unit of money dedicated to it alone, its own trades compounded,
    idle cash earning nothing (an early version stretched a 1.6-day trade over 365 days: nonsense).
    - Picking names only carries on the 1h. Rank names on the FIRST two years, measure the NEXT two:
      stocks 1h link +0.15, top quarter +0.135%/day vs +0.067% for the rest; crypto 1h +0.15, top
      quarter +0.064%/day vs -0.292% (in crypto picking is mostly about AVOIDING the bad ones).
      On the 4h, the daily, ETFs and futures the link is about zero or negative: past name performance
      does not carry there.
    - The best single filter for stocks is HOW BIG THE NAME'S MOVES ARE, not its past result
      (link +0.34 vs +0.15). Out of sample, the 142 biggest movers of 567 (picked at the halfway
      point, 2024-09, then traded for two years, 1h, 10 slots): +83.0% a year (+76.1 to +87.8 across
      60 runs) vs +40.7% for every name and +26.1% for everything except them. SPY +18.7%. (The
      +64.0% first reported used trade size to measure "moves"; #32 measures it from price alone,
      which is both cleaner and better. Numbers on /trends, read from the file, never typed.)
      Their average move a trade is 2.30% against 1.25%, which is also why they survive costs better.
      Deployed only 74% of the time (fewer names, more idle) and still ahead.
    - Cost, movers only (round trip, all in): 0.05% +83%, 0.10% +72%, 0.15% +62%, 0.25% +43%,
      0.40% +19%, 0.60% negative. Every name: already at the market by 0.15%. Big movers hold up much
      further because the move is bigger than the friction. The whole curve is on /trends.
    - Share of trades won is a TRAP for stocks: picking on it made the next two years WORSE
      (+0.054%/day vs +0.094% for the rest). The trend-study score (steps x travel) did not predict
      this at all (link -0.04).
    - Caveat: this is ONE out-of-sample split, on two years that rose. Not the three-era test.
31. Forex intraday is real for the first time (2026-09-08). `backfill_dukascopy.py` read Dukascopy's
    time field as MILLISECONDS when it is SECONDS, so a day's 1440 minute bars all landed inside the
    first 86 seconds and every "1h" file came out with one bar a day -- and those files overwrote the
    real 2-year Yahoo hourly ones. Fixed; `fix_dukascopy_clock.py` repaired the cached minutes without
    re-downloading (4 days of pulling saved). Eleven pairs now have 4 years of true hourly bars
    (~24,000 each): AUDUSD EURCHF EURGBP EURJPY EURUSD GBPJPY GBPUSD NZDUSD USDCAD USDCHF USDJPY
    (AUDJPY only to 2024-03). The rest still have Yahoo's 2 years and the download is continuing.
    First result: forex loses under the trend ride -- 1h -0.03% a trade (-0.022% a day held),
    4h -0.05%, daily +0.18% but only 3.2 signals a name a year. Nothing there as coded.

32. HIS FRAMING TESTED (2026-09-08, his words: "it's not really about how much a stock goes up, it's
    about how much a name moves, and how predictable its moves can be"). `studies/name_traits.py` ->
    validation/name_traits.json. Three traits measured on the FIRST two years from PRICE ONLY (nothing
    about the trading rule), then tested on the next two: goes_up (drift), moves (a normal bar as a
    share of price), straight (net travel over 20 bars divided by the ground covered), follows (after a
    higher low confirms, is price higher 10 bars later), and the products.
    Pick the top quarter on each trait, trade them the next two years, 1h, 10 slots:
        how much it MOVES              +83.0% a year  (+76.1 to +87.8)
        moves x straight               +75.5%
        everything, no pick            +39.6%
        how much it went UP            +31.0%
        follow-through after a HL      +30.4%
        how STRAIGHT its moves are     +29.5%
        SPY                            +18.7%
    - He is RIGHT that it is not about going up: drift predicts nothing (link -0.04) and picking on it
      is WORSE than not picking.
    - He is RIGHT that it is about how much it moves: link +0.24, and it is the only trait that pays.
      Big movers average a 2.77% normal bar against 0.67%; +0.45% a trade against +0.13%.
    - The "predictable" half did NOT survive as I can measure it. Straightness and follow-through both
      land at or below the no-pick baseline, and follow-through's link is NEGATIVE (-0.14). The reason
      is that they fight movement: moves vs straight -0.34, moves vs follows -0.32. The biggest movers
      are the least tidy, and filtering for tidiness throws them away. My reading: the structural exit
      already handles unpredictability, so paying for it in movement is a bad trade. His definition of
      "predictable" may be something my two measures do not capture -- worth him saying what he looks at.
    - The price is pain, not win rate: both groups win 41%, but the movers' worst dip inside a trade is
      -1.30% against -0.69%. Same odds, bigger swings both ways.
    - Crypto: NO trait predicted anything (every link within 0.05 of zero). #30's crypto result came
      from the strategy's own past return, not from a trait.
    - Same caveat as #30: one out-of-sample split on two rising years. Big movers should hurt more in a
      falling market and that has not been tested.

## Where things are

- Data: `history/` (crypto), `history/stocks/` (Polygon, all hours, 5y; `SOURCE.json` flags it; old free-feed
  files in `history/stocks_iex/`; top up with `backfill_polygon.py`, key in livelog/polygon.json), `history/futures/`,
  `history/forex/` (11 pairs REAL hourly since 2026-09-08, see #31; the rest Yahoo 2y). Focus list: `focus.py` (20 stocks, 10 futures, 10 crypto).
- BEFORE handing him anything: `python check_pages.py` (server running). Every page loads, every file
  a page asks for answers, every number in those files is a real number, every chart an index points at
  is on disk and measured clean. It must say "no problems found". No number may be TYPED into a page:
  pages read their numbers from the files (2026-09-08, "if im gonna put my energy and eyes on
  everything, it needs to be aces").
- Studies: `studies/*.py`, results in `validation/*.json`, logs in `logs/`. Run them with
  `pythonw studies/<x>.py --procs 20 --log logs/<x>.log` (add `--focus` for the focus list).
  trend_ride.py flags: `--variants` (trail), `--exits`, `--exits2`, `--tols` (break tolerance).
  EQ (the coil): `studies/eq_coil.py` (the shape), `eq_coil_study.py` (#26c), `eq_coil_counts.py`
  (how many there are), `pics_eqcoil.py` -> /eqcoils (the shape), `pics_eqtrade.py` -> /eqtrades
  (every buy, stop and exit drawn), `eq_freeride.py` + `pics_eqfree.py` -> /eqfree (his trade, #26d). The old flat-box work is `eq_break.py` +
  `eq_scan.py` -> /eq, and it is a CHANNEL, not an EQ.
  `studies/portfolio.py` answers "how much a YEAR", not per trade (wallet with N slots; see #29);
  `--with-forex` adds the repaired pairs. `studies/portfolio_names.py` ranks names (#30).
  `rerun_portfolio.py` runs both. `studies/name_traits.py` measures moves/straight/follows (#32).
  `fix_dukascopy_clock.py` repairs forex minute stores (#31).
- Words: a "normal bar" / "bar-size" = the average height of one bar over the last 14 (high to low, gaps
  included; the ATR). Never say ATR to him.
- Live: `/bb` backburners (backburner_log.py), `/rides` trend rides (ride_log.py), both every 15 min.
- After the backburner study: `studies/name_scorecard.py` AND `studies/split_events.py` (the /name pages read
  validation/name_events/; forgetting the split leaves them stale or 404).
- Chart sets: `pics_ride.py` (/ridecharts; `--manager` + `--out` for /exitcharts), `pics_cases.py` (/cases),
  `pics_trendwin.py` (trend windows on /trendstudy), `pics_eq.py` (/eqcharts),
  `pics_idea.py` (the five idea pictures on the dashboard: trend ride, exits, backburner, EQ, trend steps;
  one real trade each, static/ideas/). `rerun_allpics.py` redraws all of them.
  Flask serves static with NO /static prefix (static_url_path=""): the dashboard links /ideas/x.png.
- TradingView: `tradingview/pivots_trend.pine` (pivots with prices, trend floor/ceiling, x at death; mirrors the
  engine). `tradingview/structure.pine` is the old EMA-rider one.
- Pages: `/` dashboard (focus list shown at the top), `/eq` + `/eqcharts` (EQs), `/trendstudy` + `/trendstudy/<kind>/<sym>` (trend behaviour: pivots per trend, fakeouts; old name /trendnames redirects), `/ridecharts`, `/trends`,
  `/names` + `/name/<kind>/<sym>`, `/cases`, `/study`, `/rules` (this file), `/paint`.
  The dashboard review with what each page is for: `REVIEW.md`.
- He trades on Kraken and Coinbase. Crypto cost is 0.2% round trip at his volume tier.
- HIS MENTOR'S METHOD: `TCG_METHOD.md` (2026-09-11, his words: "use basic TheChartGuys methodology, its simple and
  clean, also study twitter @Junglefunk_ trades, he's my mentor ... trying to maximize their strategy"). @junglefunk_ =
  Joey Hayes of The Chart Guys. His exact rules are quoted there (12 EMA riders on every chart size, higher lows /
  stair steps, patterns only at location, ratio charts, lose small win big). New ideas come from that file, not from me.
  Studies built on it: `studies/eq_fastread.py` (what calls a 5m/15m EQ), `studies/eq_riders.py` (the 12 EMAs above + location
  + his exits on 5m/15m EQs).
- Long-form notes: `PROJECT_STATE.md`. Per-rule memory notes with his exact words:
  `C:\Users\jayru\.claude\projects\C--Users-jayru-Desktop-AI-Trading-Project\memory\`.
