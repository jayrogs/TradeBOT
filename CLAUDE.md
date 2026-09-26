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
    TRANSCRIPTS WORK NOW (2026-09-21): yt-dlp updated to 2026.08.19 with his OK; `yt-dlp --skip-download
    --write-auto-subs` pulls the spoken words, `scratch/tcg_youtube/vtt2txt.py` cleans them. The channel has 9,647
    videos (ten years of dailies): the named-setup and teaching videos are read first, then recent dailies. The course
    he owns (Entries & Exits, 72 lessons) is slides on Vimeo with no captions: readable only by screenshot, paused, with
    the Chrome window in front. Everything of theirs lives in scratch/ and TCG_METHOD.md, never pushed.
    DAN'S OWN MECHANICS (`studies/backburner_dan.py`, TCG_METHOD.md #11; "easily my most profitable trading strategy"):
    he buys INSIDE THE CANDLE the moment RSI breaks 30 (RSI at the candle's low; the price is exact -- Wilder one bar
    forward, verified to print 30.0000), a second bid rests at RSI 20, no stop with one fill, half off once the bounce
    gets going with the stop moved UNDER THE LOW OF THE DROP, the rest for the bigger chart's higher low. Best from
    all-time highs, in a waterfall, in names trading hundreds of millions of dollars, regular hours only, no news.
    BUYING AT THE TOUCH ROUGHLY DOUBLES IT (1h long, all out at the 12 EMA, per trade; next-open version in brackets):
        not a backburner                          +0.195%  +0.07R
        every first touch of 30                   +0.271%  +0.09R
        the FIRST print since the daily's high    +0.476%  +0.16R   12 of 12 years   (+0.252%)
        first print after a run of 4+             +0.634%  +0.19R   12 of 12, middle +0.648%, won 71%   (+0.307%)
        third print or later                      +0.253%
    CRYPTO 4-HOUR, his own rule (first 4h oversold after a strong run): first print after a run +4.81% a trade, middle
    +4.06%, won 80%, 10 of 11 years -- on 158 trades; not-a-backburner +0.43%. Shorts mirror it smaller (1h +0.325% vs
    +0.168%). The 5m keeps the ladder (first print up 6 of 6 years, the rest 0 of 6) but nets about zero after cost.
    MY waterfall, blue-sky and dollar-liquidity reads ADDED NOTHING on top of first-print-plus-run (+0.596 / +0.585 /
    +0.493%): crude codings of his boxes 2 and 4, not a verdict on them (13g). News/earnings still unfiltered.
    EQUILIBRIUMS, from Dan and from him (2026-09-21): an EQ is ANTICIPATED -- after volatility both ways (big drop,
    50%+ bounce) the next lower high and higher low are the trade, entered off the chart two sizes down -- "but not
    exclusively of course" (his words): that is one tell, not the definition. My detector needs two CONFIRMED pairs,
    which is why only ~3 live bars were ever left (#26b). Not rebuilt yet.

39. THE FULL READ OF THE CHART GUYS' YOUTUBE CHANNEL (2026-09-21, his words: "go over EVERYTHING"). 324 videos, 1.6
    million spoken words, every one read to its end by reader agents in 32 batches; per-video notes in
    scratch/tcg_youtube/notes/batch_NN.md, the distillation in TCG_METHOD.md #17-#19 (private, never pushed). What it
    changed, in the order it matters:
      - THERE ARE TWO OVERSOLD TRADES AND I HAD MIXED THEM. The BACKBURNER is WITH the trend: the FIRST oversold after
        a run / breakout, bigger chart strong, it marks the next chart up's higher low (5m->1h, 15m->4h, 1h->daily,
        4h->weekly, daily->MONTHLY), each step used up once, and "hourly oversold coming out of a downtrend is NOT a
        backburner" (Dan). The OVERSOLD BOUNCE is AGAINST the trend: a beaten-up name, SEVERAL chart sizes oversold at
        once (the super stack), a fast flush with a volume climax, never a slow bleed. Different trades, different rules.
      - THE LOCATION IS THE NEXT CHART UP'S 12 EMA. Joey's recipe for a failed break: oversold on the small charts + a
        support break + INTO a bigger chart's EMA. My rows agree: 1h first print after a run, scalp to the 12 EMA --
        dip stopped ABOVE the daily 12 EMA +1.30% a trade (won 76%, 12 of 12 years), REACHED it +0.71% (74%), went
        THROUGH it +0.13% (62%).
      - HE WANTS THE GAP DOWN, AND SAYS HOW MUCH: a flat open is ~50% conviction on a daily bounce, a gap down ~75%;
        no gap, no trade. (#35's fear gap is his rule.) Stocks, first two hourly bars: gapped under yesterday's low
        +0.43% vs no gap +0.22%. TIME OF DAY is a precondition too: an hourly backburner in the last hour is skipped
        (mine: +0.34% in the last bar vs +0.56-0.69% mid-day, n 309).
      - "RISK FREE" HAS TWO HONEST FORMS and neither is a stop moved to the raw entry: (a) half off at 1x the risk with
        the ORIGINAL stop left alone (half made 1, half can lose 1); (b) a partial that drags the COST BASIS under the
        low of the day, then the stop goes under that structure. The partial's job is to get bullets back and put the
        basis under the low, not to bank money. A full position is FOUR bullets, the first entry fires TWO, never all four.
        So /eqfree's "half at the far line, rest to breakeven" was their management after all (corrects #38).
      - THE STOP is the NEAREST level that kills the idea, never the big chart's swing low, with wiggle room to a round
        number; a stop that is TOO TIGHT is an error Dan names; no level nearby = a dollar stop (his "day loser").
        A STOP-OUT DOES NOT KILL THE SETUP: Joey's rule is two attempts minimum, three maximum; his year-end review found
        most "failed" stair steps worked on the second or third try.
      - SIZE IS BACKED OUT OF THE STOP AND THE NAME'S OWN RANGE (TSLA moves 6%, a name that moves 30% gets a fifth of
        the dollars); day-trade size is 3-4x swing size and the trim is what turns one into the other.
      - THE FLAG / EQ NUMBER: a pullback of 38.2% or less = a flag; 50% or more = an EQ is the likely pattern; and
        "buying the floor only works if an EQ is the likely pattern". VOLUME must drop off while an EQ forms.
      - PATTERNS MUST NOT BE BACKTESTED AS STANDALONE OBJECTS (Dan, in those words). That is 13d.
      - JOEY'S OWN NUMBERS: 43% of trades win, 72% of days win. RSI'S LIMITS, Dan's own list: not comparable across
        names or chart sizes (the level that matters is the NAME'S OWN historic bounce level: NVDA 4h 18-21), useless
        for 14 bars after a gap, useless at all-time highs.
    WHAT I BUILT FROM IT THE SAME NIGHT (all MY VERSIONS, none drawn yet, so none is a verdict -- rule 10):
      `studies/eq_retrace.py` -- their numbers on my detector's EQs. VOLUME FADING vs RISING through the shape
        separates on every chart and both exits (half at the far line: 1h +0.04% vs -0.01%, 4h +0.24% vs -0.05%, daily
        +1.77% vs -0.15%; years up 8 of 11-12 vs 3-5). First use of the volume column on this desk. The 38.2/50 number
        barely moves MY EQs, because my detector only fires after two pairs, so 85% of them are already "their EQ".
        Best single row: daily, LONG, shape began from a LOW (drop, then the bounce -- their example), all out at the
        far line: avg +1.18%, middle +1.01%, won 70%, 19 of 23 blocks of twenty up, all three eras up, n 466.
      `studies/eq_anticipate.py` -- THEIR EQ, acted on after the FIRST swing back (high -> low -> lower high, which is
        Dan's on-camera definition), 809 names, 705,051 trades, three ways in, timed on the chart two sizes down.
        (1) BUYING TOWARD THE FLOOR AT THE SMALL CHART'S RSI-30 TOUCH, STOP UNDER THE LOW -- the test of Dan's sentence.
            4h idea / 15m timing: their EQ avg +0.31%, MIDDLE +1.33%, won 55% | their flag +0.15% / -0.57% / 47% | not
            one of theirs -0.02% / -0.70% / 42%. 1h idea / 5m timing: +0.05% / +0.45% / 54% | -0.02% / -0.29% / 47% |
            -0.03% / -0.29% / 42%. The middle trade flips from losing to winning exactly where he says it should. On
            the DAILY idea chart it does NOT hold (-0.21% / -0.97%), and the 4h row lost before 2022 (-0.46%).
        (2) WAITING FOR THE HIGHER LOW TO CONFIRM ON THE IDEA CHART, far line 1x+ the risk, LONG: 4h +0.60% a trade,
            +0.27R, 5 of 6 years, eras +0.66 / +0.38 / +0.75; 1h +0.26%, +0.26R, 6 of 6 years, 319 of 502 blocks up,
            eras +0.22 / +0.21 / +0.31. Middle trade negative (won 44-48%): a 1x+ target wins under half the time by
            construction. THE FAR LINE is what matters here; their flag does as well as their EQ on this entry.
        (3) MY SMALL-CHART TRIGGER (first small higher low after a 38.2% giveback, stop under the pullback low) LOSES
            on every chart, 0 of 6 years. Its weakness is mine: the stop is 0.5-1% wide, which Dan calls an error, and
            one small higher low is not their "trend change" (a higher low AND a higher high). Not their entry yet.
        SHORTS lose or sit flat throughout (the window rose).
      `studies/backburner_dan.py` gained the daily-12-EMA-at-the-fill, gap-open, time-of-day, first-since-the-4h-12-
        EMA-was-lost and the name's-own-history reads. "First since the 4h 12 EMA was lost" ALONE added nothing over
        every touch (+0.24% vs +0.27%); first-since-the-high + a run stays the working count. Names whose EARLIER first
        prints mostly won: +0.71% vs +0.37% for names whose earlier ones mostly lost (n 416) -- their checklist box 5.
      THE LEADER RULE (Dan: do not buy a laggard's hourly oversold while its sector leader is only near RSI 34; the
        leader's own oversold print is the trigger). `lead_rsi` in backburner_dan, leaders from validation/sector_map.json.
        1h longs, all out at the 12 EMA, by the leader's hourly RSI at the buy -- ANY print: leader oversold too (35 or
        under) +0.41% a trade, weak but not oversold (35-45) +0.25%, fine (over 45) +0.15%, 75-92 thousand trades each.
        FIRST print after a run: +0.79% (won 74%, 10 of 10 years) / +0.53% / +0.66%. The worst place to buy is exactly
        where he says -- the leader weak but not yet flushed. Crypto 4h, any print: +0.83% / +0.45% / +0.53%.
      `pics_eqanticipate.py` -> /eqanticipate: 16 anticipated-EQ trades drawn, measured clean, ready to grade (set
        "eqanticipate"). THE DRAWINGS CAUGHT A BUG OF MINE ON THE FIRST LOOK: GIS's A, B and C sat seven months from
        its trade, because the drawing loaded a different set of charts from the study and the 4-hour bar NUMBERS did
        not line up. RULE: a drawing looks bars up by TIME, loads exactly the study's frames, and asserts one price.
        GIS also showed what averages hide: it came within 20 cents of the sell line, then stopped out. All-out at the
        far line is fragile; their "sell a piece into the first bounce" is what protects against that.
    HE CAUGHT THE TOUCH ENTRY BUYING LATE (2026-09-21, on the first drawing: "wtf is this you waited for the rsi to come
    up? is this better than scaling in on the way down?"). It was a flaw of mine, not a choice: that way in could not act
    until C CONFIRMED, two idea bars later (a whole trading day on a stock's 4h), so the flush itself was gone and it
    bought the NEXT brush of 30 on the way back up. It now buys the FIRST touch after C prints, and a fourth way in
    adds Dan's second buy at RSI 20 (only at a better price; it fills 13% of the time). 1,019,499 trades. WHAT CHANGED:
      - THE "(1)" RESULT ABOVE IS WITHDRAWN. With the honest entry their FLAG has a winning middle trade too (4h: EQ
        +0.17% avg / +1.47% middle / won 60% | flag +0.28% / +0.90% / 53%; 1h: +0.02 / +0.56 / 57% | +0.03 / +0.14 /
        51%; daily: EQ -0.33 / +1.05 | flag +0.46 / +1.92). The flip I reported came mostly from the late entry. It
        agrees with eq_nextlow below: what matters is ROOM, not the number 50.
      - SCALING IN IS A LITTLE BETTER, EVERYWHERE, as he thought: their EQ, one buy vs two -- 4h +0.17% -> +0.28%
        (middle +1.47 -> +1.51), 1h +0.02% -> +0.09% (years up 4 -> 5 of 6), daily -0.33% -> -0.14% (5 -> 8 of 11).
        Small, same sign on every chart and in every bucket.
      - Waiting for the 4h higher low to confirm with the sell line 1x+ away is unchanged and is still the best average
        (4h +0.60%, 1h +0.26%).
    LESSON: a confirmed-pivot rule silently delays every entry built on it by two bars of THAT chart. Any "buy the first
    X after pivot Y" must say whether Y is printed or confirmed, and the drawing must show the buy on the way DOWN.
    EVERY CHART SIZE, AND THE DETECTOR AFTER ONE PAIR (same day, his ask: "how are you implementing that on other time
    frames too"). eq_anticipate runs FOUR pairs, the buy timed two sizes down: weekly<-4h, daily<-1h, 4h<-15m, 1h<-5m,
    everything measured in the idea chart's own normal bars; /eqanticipate has a chart-size picker and 48 drawings (12 a
    size, all measured clean). WEEKLY, their EQ, two buys: avg +3.47%, middle +5.91%, won 57%, 8 of 8 years, n 508 (their
    flag: middle -1.48%) -- BUT the stop under the weekly low is often 30-50% away (AAVE drawn at 53%), which nobody
    holds, and Dan says the stop for a big-chart higher low is NEVER that chart's swing low. Not a trade until a
    nearer stop is built.
    HIS OWN EQ TRADE WITH THE DETECTOR FIRING AFTER ONE PAIR INSTEAD OF TWO (`EQ_PAIRS=1 pythonw studies/eq_retrace.py`,
    -> validation/eq_retrace_pairs1.json; buy the higher low, half at the lower high, rest to breakeven): 20-27x MORE
    TRADES AT ABOUT THE SAME PER TRADE. 4h, every EQ trade: two pairs +0.19% (n 3,151) | one pair +0.19% (n 69,417).
    4h, far line 1x+: two pairs +0.28% (n 1,226, 8 of 11 years) | ONE PAIR +0.40% (n 32,271, 11 of 12 years, eras
    +0.30 / +0.43 / +0.41). 1h far line 1x+: +0.15% (n 4,655) | +0.12% (n 119,406), both 11 of 12 years. Daily: two
    pairs is better per trade (+1.39% vs +0.57%) but one pair has 27x the trades and steadier eras. By #29 ("the number
    of trades is everything") one pair is the wallet candidate. NOT YET through the wallet, not yet drawn on /eqfree.
    HE ASKED "R U SURE IT'S GOOD" AND I HAD SKIPPED THE MIDDLE TRADE (#26c's rule: no average without its median). The
    4h one-pair row, far line 1x+: avg +0.40% but MIDDLE -0.11%, won 48%, THE TOP 5% OF TRADES MAKE 191% OF THE PROFIT
    (without them it loses), worst losing streak 15. It is the #26c / #34 lottery shape again: the money is the trailed
    runners. What holds: +0.47% over the chart's own drift, positive in stocks (+0.43%), crypto (+0.44%), ETFs (+0.25%),
    futures (+0.07%), long (+0.64%) and short (+0.18%), 11 of 12 years. CLEANEST SLICE: stocks + ETFs, LONG: avg +0.77%,
    middle +0.14%, won 52%, n 9,500 (still: the top 5% make 107% of the profit).
    HE ASKED AGAIN ("r u sure"), SO THE CONTROL WAS RUN (`EQ_PAIRS=1 EQ_CONTROL=1`, -> eq_retrace_pairs1_control_rows
    .parquet): the SAME side, the SAME stop and target distance as a share of price, the SAME management, from a bar
    picked at random on the same chart. THE EQ ENTRY BEATS IT EVERYWHERE. Far line 1x+, EQ vs any bar, avg / won:
        4h everything        +0.40% / 48%  vs  -0.12% / 40%     1h everything        +0.12% / 47%  vs  -0.11% / 38%
        4h stocks+ETFs long  +0.77% / 52%  vs  +0.14% / 42%     1h stocks+ETFs long  +0.28% / 51%  vs  -0.00% / 41%
        4h crypto long       +0.46% / 45%  vs  -0.18% / 37%     1h all shorts        +0.02% / 46%  vs  -0.15% / 38%
        4h all shorts        +0.18% / 47%  vs  -0.24% / 40%     daily stocks+ETFs L  +1.91% / 50%  vs  +0.40% / 41%
    With NO far-line filter: 4h +0.19% vs -0.11%, 1h +0.00% vs -0.14%, daily +0.57% vs -0.21%. The entry is worth about
    +0.3 to +0.6% a trade on the 4h and 8-10 points of win rate, on every market and both sides. Daily crypto is the
    one place it does not separate (+1.09% vs +0.97%). WEAKNESS OF THIS CONTROL: the random bar is not matched in
    TIME to the trade, so the year-by-year count (10-12 of 12) compares an EQ year with an all-years random sample;
    the overall numbers are the ones to trust. A BUG OF MINE ON THE WAY: a second save at the end of the script
    overwrote the rows file without the controls; the tell was the index stepping by 2. And `j.eq` is a DataFrame
    method, the #36 column-name trap again.
    SO: the EQ higher-low entry is REAL (it beats drift AND a fair random control). Its SHAPE is still mostly lottery
    (middle trade under zero except stocks + ETFs long). The management, not the entry, is what needs work.
    HIS SENTENCE, COUNTED (2026-09-21, "after a larger move, if it has 3 of those pivots, high low lower high, you can
    expect a higher low, I think"; `studies/eq_nextlow.py`, no trades, 809 names, 2.8M shapes). HE IS RIGHT, and the
    first high's label does not matter (his correction: "if it makes an eq it's an eq" -- my detector already works
    that way; the only difference from Dan is that mine waits for two pairs and Dan acts after the first lower high).
    4h, the next low is a HIGHER low: small move first (under 2 normal bars) 20% | 2-4 bars 39% | LARGER (4-8) 57% |
    VERY large (8+) 69% | every pivot low 56%. 1h and daily the same. BUT MOST OF IT IS ROOM: what decides it is how
    far B sits under C in normal bars (1-2 bars 24-36%, 2-3 bars 53-64%, 3-4 bars 76-87%, 4-6 bars 90-93%). At the
    SAME room the size of the move first still adds 7-11 points; the swing-back PERCENT adds nothing (59% -> 54%).
    So The Chart Guys' 50% number works because big move x big swing back = a lot of room, not because 50 is special.
    When the higher low holds, the next high is another lower high (the EQ keeps forming) ~40-47% of the time and a
    higher high ~55-60%. A likely higher low is not yet money: /eqanticipate is the trade built on it.
    TWO PLACES THE ROOM DISAGREES WITH ITSELF, so neither is "the rule": (1) 2017-21 Dan scales into a drop in four
    lots; 2025-26 Dan has "moved away from scaling in" and wants ONE entry with an "or I'm wrong" level close by; Joey
    never scales into freefall. #35's five-unit scale-in is the older Dan. (2) Dan walks a stop under each higher low;
    Lamont (and later Dan) move it only after a NEW sideways structure forms and breaks -- "don't choke the trade".
    My trend ride (#17) walks it under every higher low. Both need a side-by-side row, not a choice made by me.
    DAN'S EQ IS LOOSER THAN OURS: on camera it is high -> low -> lower high, or on the 12-hour "a base, a high, a
    higher low, a double top, a double bottom" -- paired tests, not strictly tightening. Jay's tightening series is
    the rule here (#26b); the strict detector throws away shapes Dan would call an EQ. Worth asking him.
    STILL NOT BUILT: a news/earnings filter; the failed-backburner regime switch (their main market-health read);
    Lori's market table to pick the SIDE; the super-stack oversold bounce as its own study; per-name RSI levels;
    two-to-three attempts per setup; drawings for both EQ studies.

40. THE PHANTOM-PIVOT BIAS IS NOT A FOOTNOTE: IT WAS MOST OF THE EQ "EDGE", AND IT SITS UNDER EVERY "BUY AFTER THE
    PIVOT CONFIRMS" NUMBER ON THIS DESK (2026-09-21; he asked "r u sure" FOUR times and said "I'm gonna keep asking until
    you take this seriously". He was right each time). #28 warned of it in 2026-09-08 and I left it as "open".
    THE MECHANISM: panel.zigzag REPLACES a confirmed low when a lower low comes before a high has qualified, and the
    replaced low is gone from the list every study reads. In real time that low DID confirm, the rule DID buy it, and
    price then went under it: a stopped-out loser the study never sees. A FINAL pivot low is, by construction, one
    that was followed by a rise of a normal bar or more before it was undercut -- so "buy the confirmed higher low"
    is handed a head start that a random-bar control is not.
    THE MEASUREMENT (`studies/eq_livecheck.py`, 809 names, 342,609 trades; its replay reproduces the engine's final
    pivots exactly, 887 of 887 on NVDA 4h, and finds 20% of confirmations are phantoms -- #28's number). The one-pair EQ
    entry, sell line 1x+ the risk away, half there, rest to breakeven. Avg per trade / won:
                               FINAL LIST (the studies)   THE PHANTOMS ALONE   LIVE (both)      random-bar control
        4h everything          +0.38% / 48%               -0.95% / 23%         -0.08% / 39%     -0.12% / 40%
        4h stocks+ETFs long    +0.70% / 52%               -0.59% / 28%         +0.17% / 42%     +0.14% / 42%
        4h crypto long         +0.44% / 46%               -1.85% / 13%         -0.34% / 34%     -0.18% / 37%
        1h everything          +0.12% / 47%               -0.63% / 22%         -0.11% / 39%     -0.11% / 38%
        1h stocks+ETFs long    +0.29% / 50%               -0.45% / 26%         +0.04% / 42%     -0.00% / 41%
        daily stocks+ETFs long +1.69% / 48%               -0.78% / 28%         +1.05% / 43%     +0.40% / 41%
    Phantoms are 26-41% of the trades a person would really have taken. LIVE, THE EQ HIGHER-LOW ENTRY IS THE RANDOM BAR,
    on the 1h and 4h, every market, both sides. The one row still ahead of its control is the DAILY, stocks and ETFs,
    long (+1.05% vs +0.40%) -- and that control is not time-matched, so it is a lead and nothing more.
    WITHDRAWN: "the EQ entry beats a fair random control everywhere" (#39, an hour earlier), the one-pair "+0.40% on
    32,271 trades, 11 of 12 years", and eq_anticipate's "confirm" way (+0.60% on the 4h, +0.26% on the 1h).
    CONTAMINATED UNTIL RE-RUN LIVE-HONEST, because they all buy the open after a pivot confirms: THE TREND RIDE (#17,
    #21-#27), THE WALLETS BUILT ON ITS SIGNALS (#29's +35% a year, #30 and #32's +83% movers), every EQ study
    (#26b-#26n, eq_retrace, eq_farline's "first rows positive in all three eras"), tcg_lab's eq_hl rows (#34), and
    eq_playbook. The size of the hole here (a third of the trades, each about -1R) is bigger than any edge those report.
    NOT TOUCHED BY IT, because the entry is a price or an RSI level, not a confirmed pivot: the backburner studies
    (#35 the daily fear gap and its wallet, backburner_dan, backburner_tcg -- pivots there only place stops), the
    "touch" ways of eq_anticipate (their pivots are behind the entry, and the selection runs against the long), breadth,
    the sector map, eq_nextlow (it counts against the FINAL low, which is the honest one).
    THE RULE FROM NOW ON: a study that acts on a pivot acts on the EVENT STREAM (`eq_livecheck.live_events`: every
    confirmation, replaced or not), never on the finished list. A result from the finished list is printed beside its
    live version or not at all. And when he asks "are you sure", the answer is a new check, not a restatement.

41. HE GRADED /backburners, ROUND 1 (2026-09-21 evening, 16 charts, notes in validation/trade_notes_backburners.csv):
    12 good, 2 bad, 1 fix, and on the losers "almost all had some issue". THE SETUP IS RIGHT: not one "that's not a
    backburner". THE STOP WAS WRONG, and it was mine: 3 normal bars under the fill, set on the buy bar, so a waterfall
    candle went straight through it (JBHT: "why did this even sell??? we need sharp dips, those get bought up the best";
    MNST: "it feels really bad to sell while it's oversold"). His rules from the grading, in his words as far as possible:
      - NO STOP WHILE THE HOURLY RSI IS STILL OVERSOLD. (Dan: one fill = no stop, the unfilled second bid is the protection.)
      - THE RUN MUST BE CLEAN, not just big (BHP "very messy chart", UNP "daily just a bit too hectic"). My run check
        is size over 20 days only. Not coded yet.
      - A BOUNCE THAT COOLS THE RSI ENDS THE SETUP: "makes further legs down less healthy for bull dip buying" (BURL).
      - NEWS DAYS OUT (FIX was 2025-01-27, the DeepSeek Monday; UNP was 2024-08-05). Still no filter.
      - HLT: "would've cashed out a bit more after the big bounce" -> thirds, not halves; the rest-for-the-old-high leg
        gives bounces back (JBHT round 2 too).
    ROUND 2 (`pics_backburner_tcg.py --same`, the SAME 16, set "backburners2", his round-1 note shown under each): no
    chart stop while RSI <= 30 (a disaster line 6 normal bars under the lowest fill only), the stop goes under the low
    of the drop once RSI closes back over 30 and switches OFF again if RSI goes back under. On the 16: JBHT -0.80R ->
    -0.56R, MNST -1.01R -> -0.50R, BHP -1.11R -> -0.41R, no winner changed sign. Over all 3,554 trades the average is
    about the same (+0.68% vs +0.68%) with the risk measured against the disaster line, so R reads smaller (+0.10R).
    HE ASKED HOW THE AVERAGE STAYED THE SAME, then "what do you think, spend some time analyzing different methods"
    (2026-09-22). `studies/backburner_stops.py` -> validation/backburner_stops.json, table on /backburners: EIGHT
    stops on the SAME 3,554 trades (729 names, suspects out), same buys, same half at the 12 EMA, same old-high target.
        the stop                                              avg     middle  won   worst 1-in-20  early  half  blocks
        round 1 (3 bars under the fill from the start)       +0.66%  +0.11%  53%   -4.4%          19%    81%   136/177
        round 2 (RSI cross, 0.1 bar)                          +0.68%  +0.04%  51%   -3.9%          35%    64%   135/177
        RSI cross, 0.25 / 0.5 / 1 bar of room                 +0.70 / +0.71 / +0.78%, middle +0.04 / +0.02 / -0.03%
        DAN AS WRITTEN: nothing until the half, then the low  +0.86%  +0.28%  57%   -4.5%           5%    95%   148/177
        half, then the low with 0.5 bar of room               +0.87%  +0.23%  55%   -4.6%           5%    95%   139/177
        never (disaster line only)                            +1.01%  +1.43%  56%   -6.2%           5%    95%   142/177
    WHAT IT SAYS: arming a stop at the RSI cross, before the bounce is real, was the round-2 mistake -- every RSI-cross
    way has a WORSE middle trade than round 1 (a tight stop right where the re-test lands). DAN'S RULE AS WRITTEN is the
    best-balanced: highest win rate, best blocks of 20 (84%), a positive middle trade, and the same tail as round 1.
    "Never" makes more on average with a fat left tail (-6.2% at 1 in 20, 4 of 6 years in stocks): it is the rest sitting
    through drawdowns until the old high; not a stop, a hold. ROUND 3 = Dan as written, same 16, set "backburners3".
    On the 16: UNP flipped to +0.49R (its rest reached the old high), BURL is now -0.96R (no half, disaster line),
    the rest as round 2. LESSON: a stop that goes live before the trade has proven anything is the worst of both worlds.
    THE REST'S TARGET (2026-09-22, his ask: "is the old high the best sale target you could find? that's kind of an odd
    target ... run everything, and be very sure of it"). THE OLD HIGH WAS MY INVENTION: the e-book's three exit plans are
    all at the EMAs (scalp), half at the EMAs then "let the other half run for continuation", or "walk up the stop
    according to your time frame". No target. `studies/backburner_rests.py` -> validation/backburner_rests.json, table
    on /backburners: NINE rests on the same 3,554 trades, Dan's stop, PAIRED against the old high so the differences
    are exact (avg / middle / won / worst 1-in-20 / paired diff / t):
        the old high                                  +0.86 / +0.28 / 57% / -4.5%      --
        hourly RSI 70                                 +0.83 / +0.34 / 59% / -4.5%   -0.03%  t -0.9
        A CLOSE UNDER THE LAST HIGHER LOW (his #16)   +0.80 / +0.44 / 61% / -4.0%   -0.06%  t -1.4   <- THE PAGE NOW
        chandelier 3                                  +0.72 / +0.43 / 62% / -3.8%   -0.13%  t -3.4
        close under the hourly 12 EMA                 +0.70 / +0.55 / 67% / -3.8%   -0.15%  t -3.5
        hold (stop under the low only)                +1.27 / -0.08 / 47% / -4.7%   +0.41%  t +3.4  (lottery)
        thirds (EMA, RSI 70, then walked / high / EMA close)  +0.87-0.90 / +0.04-0.07 / 51%   ~0, t < 1.2
    WHAT IS SURE: the final target barely moves the money -- the old high, RSI 70, the walked higher low and thirds are
    within a few hundredths of a percent, each better in about half the years. The money is the half at the 12 EMA
    (95% of trades) and Dan's stop. The two exits that cut at the 12 EMA or a chandelier give up ~0.15% a trade for a
    much better middle trade, win rate and tail (a comfort trade). Thirds do not help because hourly RSI 70 is rarely
    reached and two thirds sit. THE PAGE NOW USES HIS EXIT: the stop walked under each LIVE-confirmed higher low
    (rule 40: eq_livecheck.live_events, phantoms included), out on a close under it -- the e-book's plan 3 and his own
    rule, no target. On the 16: HLT -1.10% -> +1.27% (his note), JBHT -3.08% -> +0.85%, BIDU +9.03% -> +4.59% (the
    old high was a lucky target there). All 3,554: +0.80% avg, +0.44% middle, won 61%, 64% of trades end on the
    walked line.
    "WHAT'S 'MOST OF IT' MEAN?!" (same day) -> `studies/backburner_legs.py`, every trade split into its two legs, both
    measured on the whole position so they add up. All 3,554 (+0.80% a trade): THE HALF AT THE 12 EMA +0.56% = 70% of
    the money, won 79% of the time, middle +0.45%; THE REST, WALKED +0.24% = 30%, won 45%, middle -0.13%. The 5% of
    trades that never bounce to the EMA lose -5.3% each and cost -0.27% per trade overall -- the whole price of "no stop
    until the half". Crypto: the half is 74% (won 89%). RULE FOR ME: no more "most of it"; a share is a number.
    THE FIRST SELL, SIXTEEN PLACES (same day, his ask: "since the ema12 sell is so good, is there any other type of sell
    you can test that's even better?? using all the tools we know about"; `studies/backburner_firstsell.py` ->
    validation/backburner_firstsell.json; same trades, Dan's stop arms when the half sells, the rest walked; paired):
        the half sells at                 avg    middle  won   1-in-20  half sold  hold(bars)  vs 12 EMA   t    yrs better
        hourly 12 EMA touch (the page)   +0.80  +0.44   61%   -4.0%     95%        21           --
        hourly 26 EMA                    +0.87  +0.74   66%   -5.7%     89%        28          +0.08     2.4   6/11
        hourly 50 EMA                    +0.90  +0.80   69%   -6.2%     87%        29          +0.10     2.7   6/11
        RSI back over 30                 +0.46  -0.00   50%   -3.0%     97%        14          -0.34   -11.7   0/11
        hourly RSI 50 / 60 / 70          +0.85 / +1.06 / +1.21   middle +0.74 / +1.24 / +1.86   half sold 88 / 78 / 63%
                                          RSI 60: +0.26 vs the EMA, t 4.4, 8 of 11 years, hold 40 bars, 1-in-20 -7.6%
        1 / 2 normal bars above the buy  +0.67 / +0.93   middle +0.41 / +1.01   won 67 / 76%   1-in-20 -4.9 / -7.1%
        38.2 / 50 / 61.8% of the drop    +0.73 / +0.91 / +1.00   middle +0.46 / +0.83 / +1.23   half sold 92 / 85 / 79%
                                          61.8%: +0.20 vs the EMA, t 3.3, 8 of 11 years, hold 35 bars, 1-in-20 -7.5%
        the top of the drop              +1.21  +2.05   63%  -10.4%     62%        53          +0.42     4.0   7/11
        the daily 12 EMA                 +0.66  +0.34   61%   -5.1%     90%        22          -0.14    -2.8   0/11
        yesterday's low (stocks)         +0.64  +0.01   50%   -8.1%     86%        19          -0.16    -1.0   3/11
    WHAT IT SAYS: the farther the target, the more per trade AND the more it costs -- fewer trades ever sell the half
    (so under "no stop until the half" a third of them sit with no stop for days: the 1-in-20 loss goes from -4% to
    -10%), and the hold doubles or triples. PER BAR HELD the 12 EMA is the best of the sixteen (+0.038%/bar vs RSI 60
    +0.027, the top +0.023), and by #29 (trades a year) that is the number. The honest upgrades are HOURLY RSI 60 and
    61.8% OF THE DROP: +0.20-0.26% more a trade, 8 of 11 years, for double the hold and double the tail. Selling the
    first bounce (RSI back over 30) is the one clearly WORSE choice (-0.34%, 0 of 11 years), and so is the daily 12 EMA
    as a first target. NOT A FAIR TEST OF FAR TARGETS ON ITS OWN: the stop rule ("nothing until the half") was held
    fixed, and a far target needs its own stop; that is the next single change if he wants a far target.
    "WHY WOULDN'T I WANT MORE PER TRADE" -- HE WAS RIGHT, AND MY "PER BAR HELD" ARGUMENT WAS WRONG. I claimed the 12 EMA
    wins by #29 without running an account. `studies/backburner_slots.py` -> validation/backburner_slots.json: the same
    signals, stocks + ETFs, 581 names, 4.9 years, a CASH account (nothing borrowed, equal share per slot, a trade holds
    its slot to its exit), 60 runs. A year / worst dip (marked at closes only, so shallower than the truth, #37):
        the half sells at          5 slots          10 slots         20 slots
        hourly 12 EMA (the page)   +27.8% / -7.9%   +22.3% / -8.3%   +16.8% / -7.8%
        hourly 50 EMA              +29.0% / -11.0%  +24.6% / -10.4%  +19.1% / -10.4%
        61.8% of the drop          +30.0% / -14.2%  +25.8% / -12.0%  +20.3% / -14.5%
        hourly RSI 60              +27.9% / -18.9%  +24.8% / -17.0%  +20.0% / -16.8%
        hourly RSI 70              +25.0% / -21.9%  +19.9% / -20.3%  +18.5% / -18.7%
        the top of the drop        +17.5% / -25.2%  +16.7% / -22.9%  +16.7% / -21.7%
    At 10-20 slots the farther targets make 2-3.5% MORE A YEAR (10%-90% bands mostly apart) because the slots were not
    the constraint: the 12 EMA frees its slot sooner but there are not enough signals to refill it. The price is the
    dip: -8% becomes -10 to -17%. Too far (RSI 70, the top of the drop) and the account makes LESS: too many trades
    never sell the half. The sweet spot is the hourly 50 EMA or 61.8% of the drop. NOT YET: a daily mark of the dip, the
    far target's own stop (held fixed at "nothing until the half"), crypto, and drawings of it. LESSON: an argument
    about what the account would do is not a result; run the account.
    HIS RULE, IN HIS WORDS (2026-09-22): "we can only be changing one thing at a time, to isolate the variable. Can't
    solve for x if y is unsolved too." One change per round, graded, before the next.
    HIS ROUND-3 GRADING (2026-09-22, 14 of 16, validation/trade_notes_backburners3.csv): 10 good, 2 bad, 1 fix, and on
    two losers "didn't bounce well but HANDLED WELL" -- the management is now his. What the four notes were:
      - MNST "still sold while oversold" -> A REAL HOLE AND I FIXED IT (round 4). Dan's stop arms when the half sells,
        and on MNST the half sold AT RSI 28, so the stop went live while still oversold and took it out at 24. Now the
        ONLY line that can end a trade while the hourly RSI is 30 or under is the wide disaster line: the stop under
        the low of the drop AND the walked higher low both wait for RSI back over 30. MNST exits at RSI 34, -0.50R ->
        -0.47R. All 3,554: avg +0.799% -> +0.800%, middle +0.436 -> +0.446, won 61.2 -> 61.7%. Tiny, and right.
      - ETH "was the higher low on the higher timeframe set? If so we might wanna use that as the stop, not just the
        lower timeframe trend loss" -> THE NEXT SINGLE CHANGE. The rest walks under HOURLY higher lows; the whole point
        of the trade is that the hourly dip marks the DAILY higher low, so the stop belongs under the DAILY one and the
        hold is for the daily move. `walk_rest` already takes a pivot list; it needs the idea chart's.
      - BURL "was this news? if it bounces to cool off rsi that's a red flag ... the long stop is for when we are
        scaling in during a solid dip" -> HIS RULE AND THE E-BOOK'S EXPIRY, SAME THING. BURL bounced from RSI 28 to 35,
        rolled over and fell to 19 while the wide disaster line stayed under it. THE WIDE LINE IS ONLY VALID WHILE THE
        DIP IS STILL DIPPING: a bounce that cools the RSI without reaching the 12 EMA ends the setup. Not coded.
      - BHP "why did you run this one with new rules, it's not a backburner" -> because I froze the SAME 16 on purpose
        so only the stop changed (his own one-variable rule). The reason it is in the pool at all is that my run filter
        is size only (4+ normal bars in 20 days); BHP's 20 days were +4.4% with 1.3% daily ranges. THE CLEANLINESS
        TEST HE ASKED FOR IN ROUND 1 IS STILL NOT BUILT.
      - CDNS "what was the target again?" -> there is none any more; the chart was still drawing the old high in blue
        "for reference". Removed, and the footer now says THERE IS NO TARGET.
    "WHY DO WE KEEP LOOKING AT THE SAME TRADES WHEN THE ONES I HAVE ISSUES WITH SHOULDN'T EVEN BE BACKBURNERS"
    (2026-09-22). Right, and it was my miss: freezing the 16 isolated the stop but made him re-grade BHP and UNP, which
    he had already thrown out, twice. TWO CHANGES:
      - `pics_backburner_tcg.py --fresh` never draws a trade he has already graded (it reads every
        validation/trade_notes_backburners*.csv). The set on /backburners is now 16 he has never seen.
      - I TRIED TO BUILD THE CLEAN-RUN FILTER AND IT FAILED ITS OWN CHECK, so it is NOT shipped. I measured six things
        on the 20 daily bars before each dip and fitted them to his 14 grades; "the share of days making a higher low"
        looked like it split clean from hectic (his clean median 0.68, BHP 0.58, UNP 0.53). Coded with the study's own
        window it scores BHP 0.70 -- the one he rejected twice -- and drops UNP and HLT, both of which he liked. An
        overfit on 14 points, caught only because the two windows disagreed. LESSON: fit and code the SAME window, and
        a filter is not shipped until it reproduces his grades on the version that will actually run.
      - AND THEN HE SAID THE OBVIOUS THING I HAD MISSED: "why don't we observe the ones I don't like to make the rule
        versus wearing me out seeing 20 random charts". So I drew HIS two rejects beside two he kept and LOOKED:
          UNP IS NOT A RUN AT ALL. It fell 247 -> 220 over two months and bounced back to 250; my 20-day run measure
            saw the BOUNCE. A backburner is a name that has been going, not one climbing out of its own hole.
          BHP IS A FIGHT, NOT A RUN: big candles in BOTH directions the whole way (up to 55, back to 54, down to 50,
            a week sideways, grind up). A clean run has big candles up and small ones back.
          BIDU, which he kept: two months of quiet little candles at 88, then one clean leg to 140.
        I still could not measure it -- twelve measures and BHP/UNP sit inside the good group on every one. TWO
        REJECTS IS NOT ENOUGH TO FIT ANYTHING, which is exactly how the hl_share fit fooled me.
      - INSTEAD HE MARKS: `pics_cleanrun.py` -> /cleanruns, 12 DAILY charts of the run into a real backburner dip, each
        one STOPPED AT THE DIP so the outcome cannot colour the mark, no trade drawn, no numbers shown. He marks clean
        / passable / too messy with a note. Eleven measures per chart sit in the index under "hidden" and are never
        shown. Then the filter is built from what his clean runs share -- the method that worked for the EQ (#26m).
        HIS TWO CONDITIONS ON IT (2026-09-22): the charts must be PICKED from what he disliked, not random, and the
        page must SAY what I am looking for so he is not going in blind. Both done: six of the twelve score most like
        his two rejects on `bounce` (how much of the 40 days before was a fall the run merely won back) and `twoway`
        (the share of total candle length spent going DOWN), six score least, shuffled. The page opens with his two
        rejects and two keeps drawn side by side and my read of each in plain words. He only taps the BAD ones, then
        one "the rest are fine" button -- three or four taps instead of twelve decisions.
43. HE GAVE ME THE DEFINITION I DID NOT HAVE, AND IT MEASURES (2026-09-22, after marking /cleanruns). Two sentences:
      "back burner is AFTER A LARGE MOVE, UP OFF THE EMAS. An ema 12 ride is nice on a larger timeframe if you wanna
       zoom in and use a smaller timeframe oversold bounce as an entry onto the larger timeframe ema ride. I wouldn't
       really call that a backburner though."
      "previous price history was already at the levels we were looking at now .. that's not a significant run up,
       it's just OSCILLATIONS." (on LYV, which he called a megaphone: "a reverse eq, higher highs and lower lows.")
    MY RUN TEST WAS "the daily rose 4+ normal bars in 20 days", which passes an EMA RIDE and passes OSCILLATION inside
    an old range. Two measures out of his words, both on the daily, both in daily normal bars:
      FRESH = the top of the last 20 bars minus the top of the 60 before those. "Did the run reach levels price was
        not already at." HIS THREE OSCILLATION REJECTS ARE THE THREE LOWEST OF ALL 18 TRADES HE HAS GRADED
        (UNP 0.09, LYV 0.80, BHP 1.05) and twelve of his thirteen keeps are over 2.0 (the one below is ETH Jan 2018,
        under its December peak -- arguably his rule rejects that too).
      OFF12 = at the top of the run, how far price had pulled away from the daily 12 EMA. Every one of his five
        rejects is under 2.36; seven of thirteen keeps are above it. Right direction, too blunt to cut on yet: it is
        what separates ALAB and BTC (both "really an EMA rider, take it a timeframe down"), which FRESH does not.
    FRESH ON THE WHOLE POOL (`studies/backburner_fresh.py` -> validation/backburner_fresh.json, 3,554 trades, the
    page's own rules, only the cut changes). Avg / middle / won / years up / blocks of 20 up:
        oscillation, under 1 normal bar over its 60-day high    416  +0.65% / +0.26% / 56% /  7 of 9  /  13 of 20
        borderline, 1 to 2                                      310  +0.65% / +0.37% / 58% /  6 of 7  /  12 of 15
        HIS BACKBURNER, cleared it by 2+                      2,828  +0.84% / +0.49% / 63% / 10 of 11 / 107 of 141
        cleared it by 4+                                      1,816  +0.90% / +0.49% / 63% / 10 of 11 /  69 of 90
        everything (the page today)                           3,554  +0.80% / +0.45% / 62%
    HIS RULE IS WORTH ABOUT +0.19% A TRADE AND 7 POINTS OF WIN RATE over the trades it throws out, and it throws out
    only 20%. Crypto: +2.10% vs +1.28%. SHIPPED AS THE FILTER (FRESH_MIN = 2.0) AND ROUND 5 IS DRAWN FROM IT: 2,815 trades, 16 he has
    never seen, set "backburners5". Pool: +0.842% a trade, middle +0.491%, won 63%.
    HIS STANDING LIST, SO NOTHING GETS DROPPED (he asked 2026-09-22: "I hope you're tracking my other issues too"):
        DONE  the stop sold on the drop candle (JBHT) | "still sold while oversold" (MNST) | the old high was an odd
              target (CDNS) -> the stop walks under higher lows, no target | the run must reach fresh levels (this one)
        OPEN  a bounce that COOLS THE RSI should end the setup and the wide stop with it (BURL, and the e-book's own
              expiry) | ~~NEWS AND EARNINGS out~~ DONE #49 | the stop
              under the DAILY higher low, not the hourly one (ETH) -- ONLY WHEN THE SECTOR HAS MOMENTUM, read from ratio
              charts (his words 2026-09-23: "that's what I would do, if I think the sector is getting more momentum.
              Sector momentum is best identified with ratio charts"; step 1 is backburner_sector.py) | take more off after a big bounce, thirds (HLT) |
              the 12 EMA ride is a different trade, entered a timeframe down (he calls this one obvious, low priority)
    HIS ROUND-5 GRADING (2026-09-22, 16 fresh trades, set "backburners5"): 9 good, 6 "fix", 1 bad. THE FRESHNESS
    FILTER HELD -- not one complaint about oscillation or a bounce dressed as a run, which was the whole point.
    The complaints moved to two NEW things, and I can measure NEITHER of them yet:
      MESSY CANDLES (BTI "oscillating all over the place, gaps everywhere"; DOCN "the size of daily candles is pretty
        big all the time, long wicks both directions ... and so the dip was very dirty"; KEY "technically a backburner
        but I wouldn't like this name, candles all over the place, lots of gaps, long bodies and wicks"). FOUR examples
        now with BHP, and he names the ingredients: gaps, body size, wick size, big candles all the time. I measured
        all four on the 20 daily bars before each dip and NONE separates them from his 20 keeps (gaps: his messy 0.45
        median, his keeps 0.30, but BIDU 0.75 and COP 0.65 are keeps).
      NOT RUNNING HOT ANY MORE (MOD "the daily chart had so many days for the ema12 to catch up, not really a name
        running hot at this point ... didn't keep up the momentum the past several days, which cools off the hot run
        up"; BKNG "a lot of time to wind down in this eq after the last HH, the big move up was really just one candle
        that didn't go much higher than the last HH"; HIG "more of a sustained daily uptrend, less the classic
        backburner and more a generic oversold bounce"). Price-above-the-daily-12-EMA at the dip does NOT catch them:
        his three score 0.79 / 1.15 / 2.06 against a keeps median of 1.25.
    AND A LOOK-AHEAD BUG OF MINE, CAUGHT IN THE SAME HOUR: my first pass at "still hot" measured price against the 12
    EMA on the DIP DAY'S OWN CLOSE -- which is low because of the dip. It made all three of his rejects look strongly
    negative and I nearly shipped it. The study's own numbers are causal (align_to gives the last daily bar that had
    CLOSED before the buy) and they show no separation at all. RULE: fit on the STUDY'S recorded numbers, never on a
    fresh calculation in a scratch script, because the scratch one will not respect the study's clock.
    TSLA, graded good, is worth keeping: "ended up bouncing really well, with LL and no follow through. That's not
    really a backburner trade though, more a regular trade" -- a lower low with no follow-through is its own setup.
44. "MESSY CANDLES": SIXTEEN MEASURES, THREE WINDOWS, AND I STILL CANNOT CODE IT (2026-09-22). He rejected BTI, KEY,
    DOCN and BHP on their candles ("oscillating all over the place, gaps everywhere"; "the size of daily candles is
    pretty big all the time, long wicks both directions"), then: "we should make an AUTOMATIC filter to not have
    shitty charting names, I'm not gonna manually filter every single stock name in existence"; "you could probably
    CODIFY the choppiness of that chart, it doesn't have to define the entire existence of the stock"; and when I
    said I could see it, "why can't you try and filter it out then".
    I CAN SEE IT. CW rides a smooth rising 12 EMA in a staircase, every candle above it, ZERO crosses in 55 days,
    320 -> 475. BTI weaves ACROSS the 12 EMA, chops around a flat EMA between 40.2 and 41.5 for three weeks, spikes
    to 38, comes back: eight crosses. Put side by side they are obviously different charts.
    EVERY WAY I TRIED TO TURN THAT INTO A NUMBER FAILED:
      per trade, 20 and 40 and 55 daily bars: gaps, wick share, body size, candle size vs the normal bar, crosses of
        the 12 EMA, ground covered / net travel, share of days above the EMA, share of days the EMA rose, overlap,
        biggest bar vs average. His keeps are scattered right through his rejects on every one. On the 55 bars he is
        actually shown: chop -- his messiest keep 45.2, his cleanest reject 4.96.
      per NAME over its whole daily history (`studies/name_quality.py`, 782 names): medians 0.53 for his keeps and
        0.58 for his rejects, and HIG -- a name HE KEPT -- is the messiest of all 23. BTI ranks CLEANER than most of
        his keeps. So it is not a name property either.
      by SHAPE, no hand-made measure at all (the 55-bar path, distance from the 12 EMA, candle size and body as one
        vector; nearest neighbour, leave one out): 19 of 25 right, when always saying "good" scores 21.
    WHY, MY READING: every ingredient I can name is present in his GOOD charts at the same levels. The difference is
    how the parts arrange over the whole run, not how much of each there is. 4 rejects against 21 keeps is also far
    too few for anything to separate honestly -- two of my earlier "successes" were this same trap.
    WHAT IS ACTUALLY LEFT: more labels. If he taps the bad ones on 60-80 runs, even a weak signal becomes findable and
    the shape method has enough to work with. Until then MESSY IS NOT FILTERED and the pool still contains names he
    would not trade. NOT A VERDICT ON HIS EYE -- a limit of mine, and it is written down so nobody re-fits it on four
    examples and ships it.
44b. SOLVED, THE SAME DAY, WITH 160 LABELS INSTEAD OF 25 (2026-09-22, his approval: "yeah I guess we can do that if it
    will help you codify a way to filter out messy charts, the backburner method is going really well this is like the
    last issue"). `studies/messy_label.py` drew 160 runs the same way he is shown them (daily, the 55 bars into the dip,
    stopped at the dip, every ingredient recorded but hidden). I labelled all 160 BY EYE against his own rejects, in
    eight batches: 111 clean, 44 messy, 5 I could not call. Then every measure was re-fitted on those.
    ONE MEASURE AGREES WITH BOTH MY EYE AND HIS. CHOP: the ground the run covered day to day over those 55 days,
    divided by how far it actually travelled. A march is near 2; a fight is 5 and up.
        measure                                   my 155 labels   his 32 marks   (0.50 = a coin flip)
        chop (ground covered / net travel)             0.82           0.76
        how far the run went, in normal bars           0.84           0.75
        crosses of the 12 EMA                          0.77           0.62
        `clean` (the higher-low share already in the code, fitted on two examples)   0.60   0.62
    THE FIX THAT MADE IT WORK WAS NOT A NEW MEASURE: UNP was in my earlier fits as a KEEP. It is a messy REJECT in his
    own words ("really wild daily candles ... too hectic for a clean backburner play"). With it mislabelled, the best
    measure looked like a coin flip. #44's "nothing separates" was partly my own bad label.
    AND THE MONEY AGREES, on the same trades, one variable (`studies/backburner_chop.py`, 729 names, 2,825 trades):
        the run                                        n      avg   middle   won      R   years  blocks
        a march: under 3x the ground it travelled     985   +1.37%  +0.74%   66%   +0.17  10/11  44/49
        3 to 4x                                       781   +0.56%  +0.43%   61%   +0.11   9/10  30/39
        4 to 5x                                       446   +0.39%  +0.28%   60%   +0.08   5/8   13/22
        a fight: 5x and up (what he rejected)         613   +0.62%  +0.36%   63%   +0.11   9/9   25/30
        everything (what the page does now)          2,825   +0.83%  +0.49%   63%   +0.12  10/11 109/141
    READ THAT HONESTLY: the money does NOT say messy is bad -- the fight is not the worst row, 4-to-5x is. It says the
    MARCH is the good trade, worth about double the pool average, and it is not run size or freshness in disguise (link
    to run size -0.13; the march wins inside every run-size band and every freshness band: +0.85/+1.34/+1.73% and
    +1.08/+1.05/+1.60%).
    THE COST, SAID PLAINLY: a cut at 5x catches 4 of his 5 rejects and throws out 7 of his 27 KEEPS. Under 3x keeps
    only 8 of his 27. So this is a DIAL, NOT A SWITCH: the number is shown on every trade on /backburners (a march in
    green, a fight in red) and nothing is filtered out until he says where to cut. BTI, at 3.7, is the one reject it
    misses.
    THE BAR IT IS MEASURED AT MATTERS: the code records it at k-1, one hour before the buy, so nothing from the entry
    bar can leak in. Measured at the dip bar instead it separates the same (0.81 / 0.76) but the numbers differ by up
    to 2x on individual trades -- check which bar before comparing two runs.
    AND A MISTAKE FROM THIS: `--same` redrew the round-1 set and DELETED his round-5 drawings, because it read an index
    file that is rewritten on every run. It now reads the set from HIS NOTES (`--same round1|round5`), which are the
    only copy that is safe, and `pics_backburner_tcg.py` takes `--log`.
44c. AND THEN HE TESTED IT AND IT DIED (2026-09-22, /messymark, `pics_messymark.py`, notes in
    validation/trade_notes_messymark.csv). Ten runs he had never seen, five that zig-zagged about 2x and five that
    zig-zagged 5 to 9x, shuffled, the number hidden, each stopped at the dip. He tapped the ones he would not trade.
        his three keeps zig-zagged   1.9 (GLW), 2.0 (AR), 6.6 (HLT)
        his seven rejects            1.9, 2.0, 2.1, 5.1, 5.6, 8.5, 9.0
    HIS KEEPS SIT RIGHT ACROSS THE RANGE. The measure agreed with MY eye (0.82 on 155 charts) and with a re-reading
    of his old notes (0.76), and it does not agree with him on charts he had not seen. DROPPED: the number is off
    /backburners, nothing is filtered by it. `studies/backburner_chop.py` and its result stand as an honest record of
    what I measured; they are not a rule.
    WHY IT FAILED, AND IT IS THE SAME TRAP AS #44: fitting a number to 25 old marks and to my own eye is not the same
    as predicting a mark he has not made. A held-out test is the only thing that settles it, and it cost him ten taps.
    RUN THE HELD-OUT TEST BEFORE SHIPPING ANY FILTER FROM NOW ON.
    WHAT HE ACTUALLY POINTED AT, in his two notes: COF "not really a good runup", XLK "this wasn't a good runup". Not
    candles at all -- THE SIZE OF THE RUN. On those ten it splits his marks perfectly (his keeps 5.6 / 6.8 / 6.9 daily
    normal bars; the biggest of the seven rejects 5.4). A perfect split on ten points is exactly how #43 and #44 fooled
    me, so it was TESTED ON THE POOL, not shipped (`studies/backburner_run.py` -> validation/backburner_run.json, 729
    names, same trades, only the cut changes; the pool already requires 4+):
        the run, in daily normal bars      n      avg    middle   won      R    worst    years   blocks
        4 to 5 (the smallest allowed)    1,171   +0.66%  +0.45%   63%   +0.12  -23.4%   10/11   46/58
        5 to 6                             825   +0.87%  +0.46%   61%   +0.11  -15.6%   10/10   35/41
        6 to 7                             472   +1.12%  +0.56%   64%   +0.16  -13.4%    8/10   22/23
        7 to 9                             312   +0.97%  +0.55%   63%   +0.11   -9.7%    8/10   11/15
        9 and up                            48   +1.14%  +0.87%   75%   +0.20   -4.2%    6/7     2/2
        HIS TEN SAID 5.6+                1,118   +1.09%  +0.53%   64%   +0.15  -13.4%    9/10   46/55
        everything (the page today, 4+)  2,828   +0.84%  +0.49%   63%   +0.12  -23.4%   10/11  107/141
    THE GRADIENT IS THERE ACROSS THE WHOLE POOL, which is evidence his ten did not supply: every step up in run size
    is worth more per trade AND a smaller worst trade (-23.4% -> -13.4% at 5.6+, -4.2% at 9+). Crypto is where it is
    biggest (5.6+ +3.03% vs +2.10%); stocks and ETFs +0.84% vs +0.66%.
    THE PRICE, SAID PLAINLY: 5.6+ keeps 1,118 of 2,828 trades. It throws out SIXTY PERCENT of them, which by #29
    ("the number of trades is everything") is a capacity question the per-trade number cannot answer. NOT SHIPPED:
    his call, and an account test is owed before it.
    HOW THIS WORKS NOW (his words: "how can you know what trades I'd take if we haven't worked together to see what
    you're doing is even right"): ~10-16 drawings of ONE setup, he grades, I fix what he flags and redraw the SAME
    ones, and only when the drawings look like his trade do numbers get run. One change per round.

44d. THE RUN IN PLAIN PERCENT, AND THE ACCOUNT (2026-09-22). On the matched /messymark set (every run 5.6-7.5 normal
    bars) he rejected IWD (+3%), XYL (+5%, "just a beautiful uptrend ema rider, not a run up for a backburner really")
    and XLC (+5%), and would trade the seven that ran +7% to +230%. HE WAS NOT JUDGING WANDERING, HE WAS JUDGING SIZE --
    and my run measure, in the name's own normal bars, cannot see size: a quiet fund's normal bar is tiny, so +3% scores
    like +45%. `run_pct` (the 20-day move in percent) is now recorded on every trade.
    PER TRADE (`studies/backburner_run.py` -> validation/backburner_run_pct.json): under 5% +0.40% (119), 5-7% +0.37%
    (167), 7-10% +0.24% (473), 10-20% +0.52% (1,160), 20%+ +1.70% (909, 10 of 11 years). SHIPPED: RUN_PCT_MIN = 6.0 in
    pics_backburner_tcg -- his line; it removes 6% of the trades and costs nothing (+0.86% vs +0.84%).
    THE ACCOUNT (`studies/backburner_runwallet.py` -> validation/backburner_runwallet.json; stocks + ETFs, cash, 60 runs,
    4.9 years; a year / worst dip at closes):
        runs taken      5 slots          10 slots         20 slots
        6%+ (the page)  +28.6% / -10.5%  +22.7% / -9.0%   +16.6% / -5.7%
        10%+            +32.6% / -8.6%   +25.3% / -8.2%   +15.8% / -6.1%
        20%+            +23.5% / -11.2%  +15.5% / -7.0%   +8.4% / -3.5%
    HIS #29 WAS RIGHT AGAIN: 20%+ makes double per trade and LESS A YEAR (114 trades a year against 312). 10%+ is the
    one that beats the page at 5-10 slots (+2.6 to +4.0% a year, 10-90% bands apart, a shallower dip), and ties at 20.
    HE PICKED IT ("sure", 2026-09-22): RUN_PCT_MIN = 10.0 is now the page's rule.

44e. HIS BURL RULE, MY THREE VERSIONS (2026-09-22, `studies/backburner_cool.py` -> validation/backburner_cool.json; switches
    `cool` and `cancel_second` in pics_backburner_tcg, OFF on the page). His words: "if it bounces to cool off rsi that's a
    red flag .. the long stop is for when we are scaling in during a solid dip". Same 2,069 trades, paired with the page:
        version                                                  avg     middle  won   vs page   years better  fires
        the page now                                            +1.04%  +0.63%  64%     --          --          --
        RSI back over 35 / 40, then stop under the low           +0.95 / +1.02   60/63%  -0.09/-0.02  3/11, 2/11   16% / 4%
        no second buy once RSI closed over 35                    +1.01%  +0.62%  64%   -0.03%      2/11
        BURL'S OWN LEVEL: back over 31 / 33, then out on the     +0.78 / +0.86   55/59%  -0.26/-0.18  0/11, 0/11   28% / 17%
          next close under 30
        back over 31 / 33, then stop under the low               +0.83 / +0.88   56/59%  -0.21/-0.16  2/11, 2/11   31% / 23%
    MY FIRST TWO VERSIONS NEVER TOUCHED BURL: its bounce peaked at RSI 34.9, under my 35. At its real level (over 31, then
    out on the next close under 30) BURL goes from -4.07% to -1.41%, as he said. ON THE WHOLE POOL THAT VERSION COSTS
    -0.26% A TRADE, WORSE IN ALL 11 YEARS: it fires on 28% of trades and most of them go on to reach the 12 EMA anyway
    (win rate 64% -> 55%). It does cut the worst trade (-23.4% -> -15.6%). Same shape as #35's "you are paid for buying
    while it is still falling". NOT A VERDICT ON HIS RULE (13g): what is missing is what separates a BURL from the bounces
    that come back, which only drawings of both can show. Not drawn yet (rule 10).
    HIS CORRECTION: "I noticed burl cooled off rsi pretty quickly with its bounce" -- BURL's RSI went 26.5 -> 34.9 in three
    hours while price rose 0.8%. `studies/backburner_coolshape.py` split the 1,866 trades whose RSI got back over 31
    before the half by the SHAPE of that bounce (all known at the cooling close; saved = rule minus page, same trades):
        the bounce                                  n     page     saved   reached the 12 EMA
        fast (3h or less) AND price under half a bar  73   +1.61%   -0.58%   99%   <- BURL's shape
        price bounced two normal bars or more        600   +1.94%   -0.17%   96%
        RSI SLOW to cool: 4 to 6 hours               115   -0.84%   +0.12%   97%
        RSI SLOW to cool: 7 hours or more             43   -1.56%   +0.02%   98%
    BURL'S SHAPE IS COMMON AND USUALLY FINE: fast RSI and little price move still reach the EMA 99% of the time. BURL was
    the unlucky one, not a pattern I can find. THE TRADES THAT GO WRONG ARE THE SLOW ONES -- RSI crawling back over 31
    for 4+ hours -- which lose on average, and that is HIS OWN JBHT NOTE from round 1: "Slow, steady RSI cooling drops
    are not good for buying". 158 trades, 8% of the pool. Next test, one variable: out at the open when the bounce is slow.
    THEN THE ACTION, one variable (`studies/backburner_slow.py` -> validation/backburner_slow.json; switch `slow` in
    pics_backburner_tcg, OFF on the page): out at the next open when RSI took 4 / 5 / 7+ hours to climb back over 31.
    vs the page -0.02% / -0.01% / -0.02% a trade, better in 3-4 of 11 years: NOTHING EITHER WAY. The slow trades are the
    bad ones, but by the time a bounce is KNOWN to be slow the damage is already in the price, so selling then saves
    nothing. It also turns his JBHT (+0.85%) into -1.64%. What he actually said was "the faster the DIPS the better" --
    that is a read on the DROP, knowable BEFORE the buy, and it is the next test. (#38's crude "waterfall" read added
    nothing on the old, looser pool; it has not been tried on the 10%-run pool.)

44f. WHERE THE BUYS GO, AND HOW FAST THE DIP (2026-09-23). His words: "be clear when you're buying too. I think it's just rsi
    30 and 20. Maybe we try 25 also, as long as the rsi hasn't closed above 31, aka cooled down".
    THE PAGE'S BUYS: the first at the RSI-30 price inside the candle; one equal order resting at RSI 20 for up to 12
    hours, pulled once RSI has CLOSED above 40. Now switches `bids` and `cancel_second` in pics_backburner_tcg.
    `studies/backburner_bids.py` -> validation/backburner_bids.json, 2,069 trades, paired on the first buy. "bullets" =
    return x buys filled = money made per trade counted in first-buy sizes (the fair number when one version adds more):
        the buys                                   avg     won   buys   bullets  5% worst (bullets)  vs now  years
        NOW: 30 + 20, pulled over 40              +1.04%   64%   1.16   +0.86%   -6.6%               --      --
        A: 30 + 20, pulled over 31 (his cooling)  +0.92%   63%   1.12   +0.81%   -6.7%              -0.05%   4/11
        B: 30 + 25 + 20, pulled over 31           +1.08%   66%   1.45   +1.05%   -9.3%              +0.19%   9/11
        C: 30 + 25, pulled over 31                +0.95%   64%   1.33   +0.93%   -9.2%              +0.07%   7/11
        D: 30 only                                +0.70%   61%   1.00   +0.70%   -6.2%              -0.15%   4/11
    Scaling in pays (D is the worst, as #35 found). B makes the most money a trade and wins most often, crypto most of
    all (+0.74 bullets), BUT PER DOLLAR IT IS A WASH: 1.05/1.45 = 0.72 a buy against 0.86/1.16 = 0.74 now. It makes
    more by putting more money into the same trades, and its bad trades are bigger (-9.3% vs -6.6% at 1 in 20).
    HOW FAST THE DIP CAME (`studies/backburner_dipspeed.py` -> validation/backburner_dipspeed.json; at the first buy,
    hours since the top of the last 50 hourly bars and normal bars fallen per hour; nothing after the buy):
        top to buy in 5 hours or less   +1.68% (101)   6-10 hours +1.39% (306)   11-20 +0.87% (642)   21+ +0.98% (1,020)
        speed, quarters of the pool     slowest +0.98%   second +0.91%   third +0.82%   FASTEST +1.44% (10 of 10 years)
    HE IS RIGHT THAT THE FASTEST DIPS ARE THE BEST (about +0.45% a trade over the rest). THE SLOWEST ARE NOT THE WORST:
    the middle is. So it is not a "skip slow dips" filter; cutting to the fastest quarter throws out 75% of the trades
    (#29). Its natural use is choosing which signal gets a slot when the slots are full. Not built.
    HE CAUGHT THE TWO-AT-ONCE AGAIN ("we really gotta try and only do one at a time and not get ahead of ourselves"). Row B
    changed the 25 buy AND the cancel together. `studies/backburner_bidwallet.py` -> validation/backburner_bidwallet.json
    splits them, stocks + ETFs, SAME CASH per slot (a slot is split into as many equal buys as the version allows; buys that
    never fill sit in cash):
        change                                   per trade   per slot   a year at 10 slots   dip
        now: 30 + 20, pulled over 40              +0.83%      +0.30%     +9.7%                -7.0%
        ONLY pull at 31 instead of 40             +0.73%      +0.30%     +10.2%               -6.3%
        ONLY add the 25 buy                       +1.07%      +0.28%     +8.6%                -7.2%
    Pulling at 31 (his "cooled") is free: same money, a slightly smaller dip. Adding the 25 buy makes each trade look
    better and the account worse: more cash tied up for less. RECOMMENDED: no 25 buy; 31 is his choice. Page unchanged
    until he picks.
    NOT YET A RESULT, AND ITS OWN QUESTION: "30 only" comes out at +19.1% a year here, but only because this model locks the
    second buy's half of the slot in cash for the WHOLE trade, when in life that order is pulled within 12 hours and the
    cash goes back to work. How much of the slot the first buy should take is a separate variable, not tested.
    THE SPLIT, WITH THE CASH DONE RIGHT (his ask: "unless you can find out if a pyramid style works better";
    `studies/backburner_split.py` -> validation/backburner_split.json). ONE change: how the slot's money divides between
    the 30 buy and the 20 buy; the 20 buy's money is held back only until it fills or the 12 hours run out. Stocks + ETFs,
    1,728 trades, THE 20 BUY FILLS ON 17% OF THEM:
        split (30 / 20)      per trade   5% worst   a year at 5 / 10 / 20 slots   dip at 10
        all in at 30          +0.56%      -6.0%      +23.0 / +18.2 / +11.0%        -10.3%
        67 / 33               +0.39%      -4.2%      +17.8 / +13.3 / +8.0%         -10.2%
        NOW 50 / 50           +0.31%      -3.3%      +15.0 / +10.8 / +6.4%         -9.8%
        pyramid 33 / 67       +0.23%      -2.5%      +11.8 / +8.2 / +4.7%          -9.3%
        25 / 75               +0.19%      -2.2%      +10.2 / +7.1 / +3.9%          -8.9%
    THE PYRAMID LOSES and the more that waits for 20, the less it makes: that buy happens one trade in six, so the money
    waiting for it mostly does nothing. READ IT CAREFULLY: "all in at 30 on 20 slots" (+11.0%) is about the same as
    "50 / 50 on 10 slots" (+10.8%) -- in both the 30 buy is 1/20 of the account. So the real finding is that holding
    money back for the 20 buy is worth about nothing, and the extra a year comes from having more of the account working.
    The price: a bad trade costs more (-6.0% vs -3.3% at 1 in 20). His call.
    IN PLAIN DOLLARS, his framing ("increments of $10k ... only look at total percentage return. So not to get confused";
    `studies/backburner_dollars.py` -> validation/backburner_dollars.json; no account, a fixed amount rests at each level,
    same 2,069 trades, the page's cancel/stop/exits). Return = money made / money that went in:
        buys ($k at 30 / 25 / 20)        stocks + ETFs   crypto   every market   worst trade
        30 only (10)                      +0.54%         +1.55%   +0.70%         -$2.6k
        NOW 30 + 20 (10 / 10)             +0.54%         +1.89%   +0.76%         -$4.3k
        30 + 25 + 20 (10 / 10 / 10)       +0.53%         +2.08%   +0.77%         -$6.5k
        pyramid 30 + 25 + 20 (10/20/30)   +0.50%         +2.38%   +0.79%         -$11.8k
        pyramid 30 + 20 (10 / 20)         +0.52%         +2.09%   +0.77%         -$5.9k
        top-heavy (30 / 20 / 10)          +0.54%         +1.90%   +0.76%         -$14.1k
    STOCKS: EVERY DOLLAR EARNS THE SAME WHEREVER IT GOES IN (+0.50 to +0.54%). More buys only means more money in, more
    money made and bigger worst trades; the split does not matter. CRYPTO: THE DEEPER BUYS EARN MORE PER DOLLAR, so the
    pyramid is best (+2.38% vs +1.89% now, 8 of 10 years like the rest), at about triple the worst trade. This is also why
    backburner_split's account favoured all-in at 30 on stocks: when every dollar earns the same, money held back is idle.

45. STOCKS AND CRYPTO BEHAVE DIFFERENTLY IN A DEEP DIP -- KEEP THIS (2026-09-23, his words: "very good finding, want to make
    sure that's saved and put somewhere, cause that's very important behavior difference between sectors").
    `studies/backburner_legbuys.py` -> validation/backburner_legbuys.json: every backburner with orders at RSI 30, 25 and
    20, each BUY's own return per dollar, split by how deep the dip went (per dollar / won):
                                                STOCKS + ETFs        CRYPTO
        30 buy, price turned right away         +1.95% / 82%         +3.23% / 82%
        30 buy, the dip went on to 25           -0.99% / 38%         -0.54% / 45%
        the 25 buy itself                       +0.47% / 57%         +2.61% / 68%
        the 30 buy, the dip went on to 20       -2.91% / 21%         -3.50% / 29%
        the 20 buy itself                       +0.42% / 57%         +3.70% / 75%
        the average dollar                      about +0.54%         about +1.89%
    WHAT IT MEANS, in both markets: the best trades never reach 25 -- they turn on the first buy. A dip that keeps falling
    is the weaker trade. WHERE THEY DIFFER: in STOCKS the lower buys are ordinary dollars (+0.4-0.5%, the same as any other
    dollar), so adding them or pyramiding changes nothing but the size of the position and of the worst trade. In CRYPTO
    the deep flushes SNAP BACK HARD and the lower buys are the BEST dollars (+2.6% and +3.7%), so buying more lower pays.
    CONSEQUENCES: a sizing or scale-in rule is set PER MARKET, never one rule for all; any study that mixes stocks and
    crypto into one average can hide the opposite behaviour of each; and #35's "scale in +0.35R" on the daily was an
    all-markets number that has not been split this way. The 10/20/30 pyramid on crypto: +2.38% per dollar vs +1.89%
    (backburner_dollars), at about triple the worst trade. Futures and forex: not measured.
    SHIPPED FOR CRYPTO ONLY (his "sure okay"): CRYPTO_BUYS in pics_backburner_tcg -- $10k at 30, $20k at 25, $30k at 20,
    the position priced as total dollars / total shares. Crypto pool, 341 trades, return on the money in each trade:
    +2.90% average (was +2.12%), middle +1.70%, won 76% (was 70%). Stocks unchanged: 30 + 20, one equal amount each.

46. A LOOK-AHEAD IN THE STOP, FOUND AND MEASURED (2026-09-23). walk_rest chose which stop was resting during an hour (the
    wide disaster line while oversold, the tight one after) from THAT HOUR'S OWN CLOSE: a wick through the tight stop was
    ignored if the hour later closed oversold. Not knowable while the wick happens. `studies/backburner_gate.py` ->
    validation/backburner_gate.json, same 2,069 trades: old +1.17% / honest +1.17% a trade (stocks +0.83 / +0.82, crypto
    +2.90 / +2.95). IT INFLATED NOTHING, and the page now uses the honest version (STOP gate_prev=True). The close check
    under the walked higher low stays on the hour's own close: it is decided at the close and sold at the next open.

47. RATIO CHARTS ARE PARKED UNTIL THE BACKBURNER IS FINISHED (2026-09-23, his words: "Reading ratio charts is a whole nother
    thing honestly, so we might wanna finish backburners first"). One crude first look was already run and is kept, not
    claimed (`studies/backburner_sector.py` -> validation/backburner_sector.json; sector fund / SPY above its daily 12 EMA,
    split by the sector itself up or down, #42's "down less" trap; crypto = coin / BTC):
        stocks: every trade +0.80% (1,633) | gaining AND rising (up more) +0.84% (807) | gaining but falling (down less)
                +0.56% (117) | losing but rising +0.58% (330) | losing and falling +0.98% (379)
        crypto: 255 of 278 trades already have the coin gaining on BTC -- a big run up does that by itself.
    As coded, the read barely separates the stock trades. MY VERSION, one line on one ratio: not a verdict on ratio charts
    (13g). The ETH stop (hold for the daily move when the sector has momentum) waits for this, per his open-list note.

48. HIS HLT RULE, "CASH OUT A BIT MORE AFTER THE BIG BOUNCE" (2026-09-23, `studies/backburner_trim.py` ->
    validation/backburner_trim.json; switch `trim` = (rule, share) in pics_backburner_tcg, OFF on the page). One change:
    after the half sells at the 12 EMA, a QUARTER more sells when the bounce is big; the last quarter rides as before.
    Same 2,069 trades, paired:
        a quarter more at                  avg     middle   won    vs page   years better
        (the page now)                    +1.17%   +0.66%   64%      --        --
        an hourly close with RSI 60+      +1.15%   +0.80%   66%    -0.03%     4/11
        RSI 65+ / 70+                     +1.15 / +1.14%   +0.72 / +0.67%
        3 normal bars over the buy        +1.14%   +1.00%   67%    -0.04%     6/11
        5 normal bars over the buy        +1.13%   +0.74%   65%    -0.04%     4/11
    IT IS A COMFORT TRADE, NOT MORE MONEY: the average barely moves (-0.03 to -0.04%) while the ordinary trade gets much
    better (middle +0.66% -> +1.00% at 3 bars) and more trades win. Same as #41 found for cutting earlier. Crypto at 3 bars
    is the one place it is better on every number (+3.06% vs +2.95%, middle +2.40% vs +1.68%, won 78% vs 75%). Not drawn
    yet (rule 10); his call.
    HE PICKED CRYPTO ONLY (2026-09-23). On stocks it gives up about 0.07% a trade (3 of 6 years better) for the smoother
    ride, and he chose the money. CRYPTO_BUYS now carries trim=("up3", 0.25). Stocks unchanged.

49. THE NEWS / EARNINGS SKIP, SHIPPED (2026-09-23, his words: "we absolutely need a news earnings skip, it muddies the water way
    too much, adds so many variables. That's why I like crypto, it's always going so it kind of constantly prices stuff
    in"). His round-6 rejects were news: CORZ opened -18% the day CoreWeave announced it was buying Core Scientific; SPGI
    -6% on its earnings morning. `studies/backburner_news.py` -> validation/backburner_news.json.
    VERSION 1, any opening gap of N daily normal bars on the buy day or the day before, stocks + ETFs: the big gaps are the
    worse trades (3+ normal days: 37 trades, -0.94% each) -- BUT it also caught WHOLE-MARKET news (2026-04-08 every energy
    name gapped with oil; 2026-01-30 the gold and silver names), and most of those WON.
    CHECKED AGAINST THE REAL EARNINGS CALENDAR (the brokerage tool's get_earnings_results): CRWD 2026-06-04 and CSCO
    2026-02-12 were the mornings after their reports; COF 2026-01-12 and CHRW 2026-07-24 were other company news. So the gap
    catches earnings AND company news, which is what he asked for.
    VERSION 2 = THE RULE: STOCKS ONLY, a gap of 2+ daily normal bars while the stock's SECTOR FUND gapped under 1 of its own
    (company news, not the market), on the buy day or the day after the gap:
        skipped (company news)         68 trades   +0.04% a trade   won 47%   worst 1 in 20 -7.6%
        big gaps it keeps (sector too) 45 trades   +0.97%            won 73%
        everything kept             1,660 trades   +0.86%            won 63%   (was +0.82% / 62% on 1,728)
    The skipped trades made nothing and carried the worst losses; the total money is unchanged. NEWS_GAP / SECTOR_CALM /
    _news_days in pics_backburner_tcg. Crypto and ETFs are not touched (no earnings). News with no opening gap (mid-day
    headlines) is not caught.

50. THE BACKBURNER ON FUTURES AND FOREX, FIRST LOOK (2026-09-23, his question: "How come we haven't tested these w futures,
    commodities, or forex yet?"). Honest answer: futures WERE in backburner_tcg / backburner_dan and fell out when the
    drawing page was built on stocks, ETFs and crypto; forex was always out. `studies/backburner_markets.py` ->
    validation/backburner_markets.json, the page's own trade (stock-style buys), two rows, one change:
        market                           page exactly (run 10%+)                  without the 10% rule
        futures, all                     187 trades  +0.96%  mid +0.36%  59%  5/5y  376  +0.49%  mid +0.12%  55%
          energy (CL BZ NG HO RB QM QG)   28  +3.15%  mid +0.78%  68%              the same 28
          metals                          97  +0.60%  mid +0.39%  63%  4/5y        143  +0.50%
          farm                            26  +0.91%                               43   +0.48%
          stock-index futures             18 (too few)                             109  -0.12%  won 45%  2/4y
          currencies and bonds             0                                        35  +0.07%
        forex, the 11 real-hourly pairs    0                                        36  -0.03%  won 50%
        forex, the other pairs (Yahoo)     0                                       239  about +0.3%, won ~90% -- NOT TRUSTED
    WHAT IT SAYS: futures behave like stocks under his rules (+0.96% a trade, every year up) but there are few of them
    (~47 trades a year on 32 contracts); the 10% rule is what keeps the stock-index futures out, and without it they lose.
    FOREX: a 10% run in a month almost never happens, so the backburner as he defines it does not fire on currencies; with
    the rule off, the pairs with real data make nothing. The ~90% win rate on the Yahoo pairs is a data warning, not a
    result (2-year Yahoo hourly bars, see #31). Sub-groups are too small for any verdict (13g). Not on the page; his call.
    LOWERING THE 10% PER MARKET (his idea: "keep lowering the requirement % until it starts hitting"), read from the same
    rows, one number changing. It does NOT unlock these markets: the other rules (a run of 4+ daily normal bars to fresh
    highs) already set the supply, so a lower % adds few trades, and the ones it adds are worse -- same as stocks, the
    bigger the run the better. Futures all: any run +0.49% (376) -> 6%+ +0.65% -> 10%+ +0.96% (187). Stock-index futures
    lose at EVERY level (-0.10 to -0.13%, won 43-45%). Currency and bond futures about zero at every level. Forex, 11 real
    pairs: -0.03% to -0.01% at every level, 26-36 trades in four years. What is left worth having: COMMODITY futures
    (energy, metals, farm) at his 10%.
    HE PICKED IT ("keep the one that wins"): COMMODITY_FUTURES in pics_backburner_tcg are in the page's pool from the next
    drawing round on, stock-style buys, no news skip. Stock-index, currency and bond futures and forex stay out.
    THIN CONTRACTS OUT (his words: "Remove thinly traded completely"): middle hourly volume under 150 over the last year --
    ALI, ZO, DC, ZR, OJ, QG, QM, PA. 24 commodity futures remain.
    THE FUTURES DAILY WAS BROKEN, AND HIS GRADING FOUND IT (round 7, 2026-09-23: PL "daily chart wtf", HG "daily is weird, huge
    gaps", PL "huuuuge gaps wtf", KE "is the correct area highlighted on the daily?", HO "it just had an hourly OS right
    before this extra move down. Why didn't it take that one???"). The Yahoo futures daily file is, on many days, ONE FLAT
    SETTLEMENT PRINT WITH ZERO VOLUME (O = H = L = C): platinum 65% of days since 2024, micro silver 29%, cocoa 23%, cotton and
    coffee 17%, silver 11%, wheat 7% (oil, gas, heating oil about 1%). It blanked the daily drawings and broke the daily
    numbers the trade reads -- the normal daily move, the run, where the run topped -- which is also why HO skipped the first
    oversold: with real daily bars it buys 2025-11-19 08:00, the one he pointed at. FIX: backburner_study.frames_for builds
    the futures daily FROM THE HOURLY BARS (Databento, real trading) on the futures clock -- New York stamps, the 17:00
    break, a session 18:00-17:00 belongs to the next day. Every futures number before this is SUSPECT.
    THE FUTURES NUMBERS ON THE FIXED DATA: all futures under his rules 151 trades +0.61%; THE PAGE'S 24 COMMODITY FUTURES 107
    trades, +0.76% a trade, middle +0.36%, won 62%, up in 4 of 4 years (2023 +0.16, 2024 +0.88, 2025 +0.62, 2026 +1.17).
    Smaller than the first "about +1%", still in line with stocks (+0.86%). They stay in.
    HE GRADED THE REDRAWN SEVEN (set backburners7b): ALL SEVEN GOOD, winners and losers alike. The futures backburner looks
    right to him on real data.

51. EACH COIN'S OWN LEADER, AND DAN'S LEADER RULE ON CRYPTO (2026-09-23, his XRP note: "most crypto names are paired with a
    specific larger crypto name ... BTC, certain coins move with eth, others with solana ... weaker names will dip harder";
    then "check for other leaders too ... all of them"). `studies/backburner_cryptolead.py` ->
    validation/backburner_cryptolead.json: each coin matched to the big coin its DAILY returns move with most, on the FIRST
    HALF of its history, a leader only from coins bigger than it; then the page's 341 crypto trades split by the leader's
    hourly RSI at the last close before the buy. Nothing about the trade changed.
        the leader at the buy          his matching (16 big coins)     the old way (all follow BTC)
        oversold too (35 or under)     +3.08%  mid +1.37%  (40)         +4.09%  mid +3.28%  (43)
        weak, not flushed (35-45)      +2.50%  mid +1.91%  (98)         +3.13%  mid +1.62%  (102)
        fine (over 45)                 +3.66%  mid +3.11%  (140)        +2.90%  mid +2.79%  (133)
    With his matching the weak-not-flushed group is the worst, which is Dan's warning -- but every group makes +2.5 to +4%
    and the groups are 40-140 trades over 4-9 years. AS CODED IT DOES NOT SEPARATE ENOUGH TO CHANGE THE PAGE (13g: my
    version, not a verdict). TWO FLAWS FOUND ON THE WAY: (1) BNB is in our data only from 2025-10-22 (Coinbase and Kraken
    listed it late; he: "BNB's been around forever tho") and on the first run it "led" 58 coins by being measured over a
    different, recent stretch -- a leader now must have data from at least as early as the coin. (2) Correlation finds the
    coin a name moves MOST LIKE, not the one it FOLLOWS: DOT "leads" 42 coins because it is a very typical alt. A real
    leader read needs timing (who moves first), not likeness.
    BNB BACKFILLED (his yes, same day): `backfill_binance.py BNB` pulled 69,661 hourly bars 2017-11-06 .. 2025-10-22 from
    Binance's public mirror (data-api.binance.vision; api.binance.com answers 451 from the US) IN FRONT of the Coinbase
    file, seam 1067.39 -> 1072.85; original kept in history/_backup/. On full history BNB leads 3 coins, not 58. The crypto
    pool gains BNB's own trades (361, +3.04% a trade). The leader split is unchanged in substance: with his matching,
    oversold-too +3.08% (43), weak-not-flushed +2.60% (106), fine +3.55% (149). Page unchanged.
    HIS CORRECTIONS (same day): "I'd drop dot then, and just let those names not have a leader pairing. Just like make
    sure these are actually tied to the coins from your research online too." DOT is out as a leader. Every pairing now
    needs a REAL tie from CoinGecko (scratch/coingecko/: the top 2,000 coins, the category lists, and each of our 146
    coins' HOME chain). First try used CoinGecko's ecosystem LISTS, which include bridged copies (ENA and WLFI counted as
    Solana, ATOM as BNB, FET as Cardano, ICP as Ethereum); the rule now uses the HOME chain (where the coin was built):
    Ethereum or its layer 2s -> ETH, Solana -> SOL, BNB Chain -> BNB, Avalanche -> AVAX, Sui -> SUI, Cardano -> ADA; plus
    two sector ties from the coin's own categories -- a meme coin -> DOGE, proof of work -> LTC / BTC -- and the 20 biggest
    coins -> BTC. The coin takes its best-matching TIED leader; none tied, no leader. Result: ETH 60 (ARB, OP, UNI, AAVE,
    ENA, LDO ...), DOGE 17 (PEPE, SHIB, BONK, WIF, FLOKI ...), BTC 12 (the majors), SOL 11 (JUP, JTO, PYTH, PENGU,
    FARTCOIN ...), BNB 5 (CAKE, ASTER ...), LTC 3 (BCH, DASH, ZEC), AVAX 1 (JOE), ADA 1 (NIGHT), NO LEADER 38 (the coins
    on their own chains: ATOM, NEAR, ICP, SUI, APT, SEI, TIA, TAO, FIL ...).
    ON THE TIED PAIRINGS: leader oversold too +3.67% (38) | weak, not flushed +2.43% (99) | fine +3.26% (123). THE
    WEAK-NOT-FLUSHED GROUP IS THE WORST ON EVERY VERSION OF HIS MATCHING (+2.43 / +2.50 / +2.60%), which is Dan's warning --
    but it still makes +2.4% a trade, so skipping it would cost money a year (#29). Page unchanged; the pairing is kept
    for later (sizing, ratio charts).

52. THE WHOLE BACKBURNER AS AN ACCOUNT, EVERYTHING FROM 2026-09-23 ON (`studies/backburner_account.py` ->
    validation/backburner_account.json). The page's own trades in every market, cash only, N slots, a slot split the way the
    page buys (money for a later buy held back only until that order is pulled), EVERY OPEN POSITION MARKED AT EVERY DAY'S
    CLOSE, 20 runs, 2022-09-06 .. 2026-09-04 (when the futures data starts) for every row, SPY marked the same way.
        account                     slots   a year    worst dip (daily)   deployed   trades a year
        SPY bought and held                 +18.5%    -19.0%              100%
        everything                    5     +22.8%    -10.1%              40%        216
                                     10     +18.2%    -7.9%               29%        319
                                     20     +10.7%    -6.5%               17%        395
        stocks + ETFs only            5     +19.2%    -10.4%              39%        179
                                     10     +13.7%    -9.5%               28%        265
        crypto only                   5     +6.5%     -7.1%               1%         46
        commodity futures only        5     +1.3%     -8.3%               2%         26
    Every calendar year up at every slot count. At 5 slots it beats SPY by ~4% a year with about half its worst dip; at 10
    it matches SPY with about 40% of its dip. Crypto and futures fire rarely (46 and 26 a year) and add ~3.6% a year on top
    of stocks at 5 slots. THE MONEY IS MOSTLY IDLE: 29-40% deployed on average, so the slot count is the lever.
    CAVEATS, plainly: four years, mostly rising; the names are the ones alive today (#35 survivorship); a position is marked
    whole until it closes (the half sold at the 12 EMA is not taken out of the daily mark, so the dips are if anything deep).
    A DATA BUG THE MARKING FOUND FIRST: the first run showed a -57% dip with 18% deployed, which cash cannot do. BNY's
    hourly bars are priced ~$9 and its daily ~$101. `studies/data_scale_check.py` (hourly vs daily closes, every name) found
    35: 17 at different scales (BNY 4.8x, SOXS 15x, FDX, HIMS, INSM, MP, FTNT ...) and 18 that disagree 15%+ on 7-46% of days
    (CVNA, META, T, GSK, KEY ...). All in validation/suspect_names.json now, out of every study and page until repaired.
    The per-trade numbers reported earlier the same day included them; they are ~4% of the stock names. RUN
    data_scale_check.py AFTER ANY DATA PULL.

53. HOW BIG AND HOW MANY, TESTED WIDE (2026-09-23, his words: "Test as broad and wide as you need"; `studies/backburner_sizing.py`
    -> validation/backburner_sizing.json). The account of #52, ONE change a row from the base (5 slots, the page's buys,
    same-hour signals in random order), 20 runs, 2022-09 .. 2026-09, cash only, marked every day. A year / worst dip:
        the page now, 3 / 5 / 10 slots                  +25.2% / -11.3%   +25.7% / -8.4%    +17.2% / -8.8%
        (1, 2, 4, 6, 8 slots in the file; 3-5 is the top, it falls off past 6)
        sized by risk at the disaster line 1% / 2% / 3% +16.9% / -6.5%    +19.4% / -7.9%    +21.1% / -8.4%   (no better)
        fastest dips first when signals share an hour  5 slots +28.6% / -10.4% -- inside the random-order band (+20.7 to
                                                        +29.2%): not a clear win
        ALL IN AT 30, ONE BUY, 3 / 5 / 10 slots         +46.2% / -14.8%   +43.0% / -11.8%   +31.1% / -9.4%
        FULL SLOT AT 30, THE LATER BUYS ON TOP (each at its own time, only with cash free then), 3 / 5 / 8 / 10 slots
                                                        +52.4% / -16.8%   +46.6% / -14.7%   +40.5% / -11.1%   +35.7% / -9.6%
        SPY bought and held                             +18.5% / -19.0%
    WHAT IT SAYS: the trade was never the constraint, the MONEY WAS. The page splits every slot between the buy at 30 and a
    buy at 20 that happens about one trade in six, so half of each stock slot (5/6 of a crypto one) sits idle and the
    slot count caps what else can use it. Putting the whole slot in at 30 -- and adding the later buys on top from free
    cash when they happen -- keeps the same trades and more money working: 10 slots goes from +17.2% to +35.7% a year
    with about the same worst dip (-8.8% -> -9.6%). Every calendar year up in every row.
    THREE BUGS OF MINE FOUND AND FIXED IN THE SAME HOUR, all flattering: (1) "fastest first" ranked a whole DAY's signals
    by speed, so a 3pm dip took a slot before a 10am one (+35.5% -> +28.6%); (2) both account tests settled a day's sales
    before its buys, so a slot freed at 3pm was used at 10am -- now every buy, sale and release runs in real time order;
    (3) the first "later buys on top" sized the whole position at the first buy KNOWING whether the later buys would fill
    (+40.2% -> +35.7% at 10 slots) -- now each later buy is placed at its own time with the cash free then.
    CAVEATS: four years, 2024 alone +75-118% in the top rows (the crypto run); crypto pyramids add 2x and 3x the first buy,
    so one coin can take several slots' worth of cash; survivorship (#35). His call on the sizing and the slot count.
    HIS QUESTION "what makes the most money" -- full slot at 30, later buys on top, 20 runs (typical / unlucky 10% / lucky
    10% a year, typical worst drop, the worst run's drop): 1 at once +52.0% / +34.9 / +63.8, -25.8% (-35.3%) | 2 +48.1% /
    +37.6 / +60.5, -17.8% (-29.0%) | 3 +52.4% / +41.1 / +58.0, -16.8% (-20.9%) | 4 +46.3%, -16.8% | 5 +46.6% / +42.0 /
    +51.8, -14.7% (-18.7%) | 6 +43.7%, -13.4%. THE MOST IS 3 AT ONCE; 1 makes the same with far bigger drops; 5 makes a
    few % less typically but its UNLUCKY case (+42.0%) is as good as 3's (+41.1%) with a smaller drop.
    HE PICKED 5 AT ONCE ("Okay we can do 5 at once"). ACCOUNT in pics_backburner_tcg and the /backburners rules say it: 5
    buckets, the whole bucket at RSI 30, the later buys on top from spare cash. OPEN QUESTION PUT TO HIM: on crypto the
    pyramid then means +2x and +3x a bucket at 25 and 20 -- up to 6 buckets in one coin on a deep flush, if cash is free.
    HIS ANSWER: "keep it however makes the most money". Tested (5 buckets, 20 runs): uncapped +46.6% / -14.7%, capped at 3
    buckets a coin +46.6% / -14.1%, at 2 +45.7% / -12.3%, one bucket +42.3% / -10.9%. SHIPPED: at most 3 buckets in one coin.

54. THE BACKBURNER, LIVE (2026-09-23): /bb is now `bb_live.py` + static/bblive.html (the old Sept-5 forward log is /bbold,
    still running). IT RUNS THE EXACT TRADE CODE THE STUDIES RUN (pics_backburner_tcg.trades_for takes `frames=` and
    `sector_daily=` now), so the live page and the backtest cannot drift apart. The server starts it as its own hidden
    process every 15 minutes (`_bb_live_loop`, never two at once; 8 cores, a pass ~9-10 minutes on ~685 names).
    DATA: stocks = the history on disk + the bars since from Polygon / Massive (his paid feed, ~15 min late; Yahoo rate-
    limited 220 of 600 names on the first try); crypto = Coinbase / Kraken live; commodity futures = the Databento
    history + recent Yahoo hourly bars. A name whose last bar is stale (over 4 days, 6 hours for crypto) is SKIPPED and
    named on the page -- corn and wheat showed as "open since Sept 3" on a failed feed before that guard.
    ARMED = every condition met and the first RSI-30 touch not yet made: found by asking trades_for itself -- nine made-up
    hours are added after the last real one, the first falling through every buy level; if it takes a trade there, the
    fills ARE the order prices (the RSI-30, 25, 20 prices for the next hour). OPEN = trades taken in the last 10 days and
    not closed, with the half's sell price (the hourly 12 EMA) and the stop. Crypto's later buys are shown with the
    3-bucket cap applied (so a crypto dip buys at 30 and 25 only). Account size is typed on the page (kept in the
    browser); a bucket is a fifth of it. READ-ONLY: no order path.
    A MISTAKE ON THE WAY: I first wrote this as backburner_live.py, which already existed (the older 5m detector the
    scanner and pics_backburner use) -- overwritten, restored from git the same minute, the new code renamed bb_live.py.
    LOOK BEFORE WRITING A FILE NAME THAT SOUNDS LIKE IT MIGHT EXIST.
    AND A BIGGER ONE, FOUND BY THE LIVE LOOP (same hour): server.py starts its loops with module-level threads, and
    something in the server uses a pool of worker processes; on Windows every worker RE-IMPORTS server.py, so every loop
    ran again inside every worker -- 20 copies. The new live loop then launched 21 copies of an 8-core pass at once
    (killed within minutes). The old loops had been running 20 copies of their Yahoo downloads the whole time, which is
    a likely cause of the Yahoo rate limits. FIX: the loops start only when multiprocessing.current_process().name is
    "MainProcess". After it: one server, one live pass. A dropped Polygon connection no longer kills a pass (each name
    fails alone). Yahoo was still refusing the 24 futures an hour later; they are skipped and named on the page until it
    recovers.
    FUTURES FROM HIS DATABENTO CREDIT (his OK: "yes u can handle 1.50 a year"; ~$5.34 of the $125 credit was left).
    `databento_recent.py` appends ohlcv-1h for the 19 CME roots of the pool to history/futures/<ROOT>_F_1h.csv.gz from the
    last bar to about 7 hours ago -- WITHOUT A PAID SUBSCRIPTION DATABENTO SERVES CME ONLY UP TO ~6-7 HOURS AGO (exchange
    licensing), and it reads the exact cutoff from Databento's refusal if the window moves. BUDGET ENFORCED IN CODE: the
    price is asked first (free), a pull over $0.05 is refused, every pull is logged in livelog/databento_spend.json and
    nothing is pulled once the last 365 days reach $2.00. The catch-up (Sep 3 -> Sep 23) cost $0.0474 for 4,641 bars;
    a day costs about $0.004. bb_live runs it about once an hour; Yahoo fills ONLY the hours after Databento's last bar.
    The five ICE contracts (BZ, CC, KC, SB, CT) are not on his Databento plan and stay on Yahoo. Backups of every futures
    1h file before the first append: history/_backup/futures_1h_2026-09-23/. The page shows a futures or crypto name's
    data age when it is over 2 hours.
    GRADING ON /bb (2026-09-23, his ask: "why don't I have a comment field and good or bad boxes"): every card has good /
    bad and a comment box, saved to validation/trade_notes_bblive.csv (keys armed|kind|sym|day and open|kind|sym|bought).
    READ THAT FILE whenever he says he graded /bb.

55. THE OVERNIGHT REVIEW, AFTER THE MOVE TO THIS ACCOUNT (2026-09-26, his ask: "review everything to make sure there isnt
    any major inconsistencies"). Checks and what they found:
      - THE SERVER WAS DOWN since 2026-09-24 16:55 (no python running after the move): /bb had not updated for two days.
        Restarted with run_server.ps1.
      - THE BACKTEST TAKES TRADES THE LIVE PAGE NEVER CAN. trades_for demands 500 hourly, 120 daily and 60 WEEKLY bars, but
        checks it on the WHOLE FILE, not on what existed at the trade. So a coin 55 days old (ENA 2025-07-29) trades in the
        study; live it needs ~14 months of history first. 211 of 2,043 page trades are like that, and they are the best
        ones (crypto +4.71% a trade vs +2.56%). Two kinds: NEW LISTINGS (new coins, IPOs) the live page will never take,
        and FUTURES in their first 14 months of data (history starts 2022-09) -- those the live page takes now.
        The page's account (5 buckets, whole bucket at 30, later buys on top), 20 runs (`studies/backburner_young.py`):
            as in #53 (everything)                        +47.0% a year, worst dip -14.9%
            new listings out (what the live page can do)  +39.8% a year, worst dip -12.2%
            every young trade out                         +38.0% a year, worst dip -12.2%
        So #53's +46.6% / backburner_curve's line are ~7 points a year too high FOR THE PAGE AS IT RUNS. His call which way
        to close it: keep the rule (the honest number is ~+40%), or let the live page take new listings with the weekly
        check skipped when there is not enough weekly history (the backtest says those are the best trades).
      - THE LIVE CRYPTO WINDOW WAS TOO SHORT. bb_live read 720 hourly + 600 daily bars from the exchange; replaying the
        last two years that way missed 22 of 100 study trades (most are the new-listing kind above; AVAX 2025-09-22 was
        missed only because a 50 EMA on 85 weeks is not the one on the full history). FIXED: the history on disk is joined
        in front of the live bars and the daily is built from the hourly, as frames_for does. THE DISK HISTORY ENDS
        2026-09-07; once it is 30+ days behind (about 2026-10-07) the join leaves a hole and the name is listed under
        `short_history` in livelog/bb_live.json. The crypto hourly history needs a top-up before then.
      - THE CRYPTO CARD PRICED THE POSITION WITH THE 20 BUY the 3-bucket cap never lets it make. Fixed in open_trades. The
        study's per-trade crypto numbers (#45, #48) still include that buy; the account tests apply the cap.
      - PASSED: walk_selftest 658 / 0 mismatches (it checks tcg_lab's walk, NOT the page's _walk_rest -- no self-test
        covers the page's walk yet); check_pages clean but for eq_scan being stale from the downtime; bars between the
        first buy and a later buy are never walked, and the 12 EMA was reached in that gap on only 9 of 2,043 trades.
      - NOTED, NOT CHANGED: the weekly bar (W-FRI) counts as closed a week after its Friday, so the weekly trend read is a
        week late in both study and live -- late, not look-ahead. `cancel_second` is still 40 on the page; #44f left 31
        as his pick to make.

42. JOEY'S RATIO-CHART WEBINAR (2026-09-22, Jay sent the link with Joey's post "ratio charts continue to be one of the
    most powerful and underused tools in the market"). Pulled, read in full, distilled in TCG_METHOD.md #20. It is the
    4th of his four-part series and it says MY VERSION OF THE BIGGEST RULE ON THIS DESK IS TOO CRUDE:
      - THE "DOWN LESS" TRAP. A rising ratio means the name is going UP MORE **or** DOWN LESS, and only the first makes
        money: "you can be positioned bull in a relatively strong name, but if it is still going down you still lose
        money". `strong` in tcg_lab (#34, the single biggest swing rule here) is only "the ratio is over its daily 12
        EMA" -- it does not separate the two, so some of that +0.44% a trade may be down-less names. NEXT TEST, and it
        is one variable: split every strong row into up-more and down-less.
      - A RATIO READ NEEDS THE DRIVER TO MOVE TOO: if you want a QQQ bounce you need SPY to bounce. Never tested here.
      - THE SHIFT FROM WEAK TO STRONG IS CAUSED BY A HOLD OF A KEY LEVEL (a double bottom at support, a rejection at
        resistance), and he names it the number one cause. Testable, never tested.
      - "LAST MAN STANDING", his named play: of four correlated names (ES/NQ/RTY/YM), when THREE have broken to lower
        lows and the three are EXTENDED and due a bounce, the fourth is a low-risk bottom fish. Fully codeable with
        validation/sector_map.json, and nothing like it exists here.
      - RATIO DIVERGENCE (the ratio holds a higher low while the name makes a lower low, or the ratio breaks resistance
        first), timed with a stair step. ALL ORDINARY TA APPLIES TO THE RATIO CHART ITSELF: EQs, 12 EMA riders, support.
      - A DIRECTIONAL PATTERN IS LESS LIKELY AGAINST CLEAR RELATIVE STRENGTH: a rising wedge on a name much stronger
        than its peers is usually waiting for the peers, not exhaustion. My pattern studies score patterns alone (13d).
    TCG also has a correlations e-book by Joey (already read, #18) -- the webinar is the deeper version.
    AND I WATCHED IT, not just read it (his words: "seeing the charts is so important too" -- right, the transcript is
    him saying "this here" at a chart I could not see). `yt-dlp` for the video, `ffmpeg -ss` for a frame at each of the
    16 moments he puts a chart up; frames in scratch/tcg_youtube/frames/ (private). TCG_METHOD.md #20b. What only the
    pictures show: he compares two names SIDE BY SIDE WITH A SYNCED CROSSHAIR (never an overlay), every pane carries a
    green 12 EMA, an orange 26 EMA, volume and an RSI panel -- INCLUDING THE RATIO CHART -- and the last-man-standing
    quad puts ES/NQ/RTY/YM on one timeframe each with its RSI, so "which one has not broken" and "are the others
    extended" are one glance. Nothing else is on his charts. NEW RULE FOR ME: when a source is a video and the words
    point at a picture, pull the frames.

## What is settled (do not re-litigate)

14. Confirmation and price never come from the same bar. A buy fills at the next bar's open.
15. Every result is compared against a control (buy any bar, same exit) and against the
    chart's own drift, over three eras (before 2022, first half, second half).
16. The standard backburner exit after the breakeven partial: hold until a bar closes under the
    last higher low. The 12 EMA close is the alternate.
17. [NUMBERS SUSPECT SINCE 2026-09-21: see #40, the phantom-pivot bias. The RULES he graded stand; the results do not
    until re-run live-honest.] The trend ride, as he graded it in on 85 charts (2026-09-06, three rounds). Entry: the
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

29. [NUMBERS SUSPECT SINCE 2026-09-21: see #40. These wallets are built on trend-ride signals.]
    TRADES PER YEAR, not per trade (2026-09-08, his words: "the main difference is being able to make
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

30. [NUMBERS SUSPECT SINCE 2026-09-21: see #40.] WHICH NAMES play best this way (2026-09-08). `studies/portfolio_names.py` ->
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
