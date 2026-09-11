"""
harness.py -- the testing engine.

Implements strategy_spec_v1.md. The engine is deliberately dumb and literal:
it walks forward one trading day at a time and is only ever allowed to see
bars up to and including the current day. Everything that could leak the
future is funnelled through a small number of places, all marked LOOKAHEAD.

The strategy itself is ONE function at the bottom: weakness_reversion().
Everything above it is plumbing and should not need to change when testing a
new idea.

Order of events within trading day t:
    1. exits   -- open positions checked against bar t (stop first: same-bar
                  ties score as losses, per spec section 7)
    2. fills   -- resting limit orders from earlier days checked against bar t
    3. expiry  -- orders past their good-for window are cancelled, capital freed
    4. signals -- computed on the CLOSE of t, orders go live from t+1

Nothing placed on day t can fill on day t. That is the single most important
anti-lookahead rule in here.
"""

import json
import math
import os
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
TRIALS_LOG = os.path.join(HERE, "trials.json")


# ======================================================================
# parameters -- every number here comes from strategy_spec_v1.md
# ======================================================================

DEFAULTS = dict(
    # universe
    min_adv=20e6,          # sec.3  20-day average dollar volume
    min_price=10.0,        # sec.3
    earnings_buffer=5,     # sec.3  trading days either side
    # entry
    rsi_max=40,            # sec.4.1
    rsi_len=14,
    min_range_pos=0.60,    # sec.4.2  position in 252-day low->high range
    range_len=252,
    atr_len=14,
    atr_pct_min=0.015,     # sec.4.3
    atr_pct_max=0.06,      # sec.4.3
    regime_sma=200,        # sec.4.4  SPY above its own SMA200
    n_picks=5,             # sec.4.5  lowest-RSI names per day
    limit_atr=0.5,         # sec.4    limit = close - 0.5 * ATR
    order_good_days=10,    # sec.4    trading days, then cancelled
    # exit
    stop_atr=2.0,          # sec.5
    target_atr=3.0,        # sec.5
    max_hold=30,           # sec.5    trading days
    # sizing
    risk_frac=0.01,        # sec.6
    max_pos_frac=0.20,     # sec.6
    max_positions=8,       # sec.6
    max_per_sector=2,      # sec.6
    # costs
    slippage=0.0010,       # sec.7    per side
    start_equity=100_000.0,
)


# ======================================================================
# indicators
# ======================================================================

def wilder(s, n):
    """Wilder's smoothing == EWM with alpha 1/n."""
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    gain = d.clip(lower=0.0)
    loss = (-d).clip(lower=0.0)
    ag, al = wilder(gain, n), wilder(loss, n)
    rs = ag / al.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.where(al != 0.0, 100.0)


def atr(df, n=14):
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def build_features(bars, earn_dates, p):
    """
    Per-symbol indicator frame. Every column at row t uses only bars <= t.

    LOOKAHEAD CHECK: all rolling/ewm windows are backward-looking and no
    column is shifted forward. Verified by test_lookahead() in validate.py.
    """
    out = {}
    for sym, df in bars.items():
        if len(df) < p["range_len"] + p["atr_len"] + 5:
            continue
        f = pd.DataFrame(index=df.index)
        f["open"] = df["Open"].astype(float)
        f["high"] = df["High"].astype(float)
        f["low"] = df["Low"].astype(float)
        f["close"] = df["Close"].astype(float)
        f["rsi"] = rsi(f["close"], p["rsi_len"])
        f["atr"] = atr(df, p["atr_len"])
        f["adv"] = (f["close"] * df["Volume"].astype(float)).rolling(20).mean()
        lo = f["low"].rolling(p["range_len"]).min()
        hi = f["high"].rolling(p["range_len"]).max()
        f["rngpos"] = (f["close"] - lo) / (hi - lo).replace(0.0, np.nan)
        f["atrpct"] = f["atr"] / f["close"]

        # earnings blackout: +/- N trading days around each reported date
        blocked = np.zeros(len(f), dtype=bool)
        dates = earn_dates.get(sym)
        if dates is not None and len(dates):
            pos = f.index.searchsorted(pd.DatetimeIndex(dates))
            k = p["earnings_buffer"]
            for q in pos:
                blocked[max(0, q - k): min(len(f), q + k + 1)] = True
        f["earn_block"] = blocked
        out[sym] = f
    return out


# ======================================================================
# portfolio objects
# ======================================================================

@dataclass
class Order:
    sym: str
    limit: float
    shares: int
    place_day: int          # index into the calendar; order is live day+1..
    expire_day: int
    sector: str
    atr_at_signal: float


@dataclass
class Position:
    sym: str
    shares: int
    entry_px: float         # after slippage
    entry_day: int
    stop: float
    target: float
    sector: str
    atr_at_entry: float


@dataclass
class Trade:
    sym: str
    sector: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_px: float
    exit_px: float
    shares: int
    reason: str
    pnl: float
    ret_pct: float
    bars_held: int
    r_multiple: float
    signal_rsi: float = float("nan")


# ======================================================================
# the engine
# ======================================================================

def run_backtest(feats, sectors, spy, membership, start, end,
                 strategy, params=None, verbose=True):
    """
    feats      : {sym: indicator DataFrame}
    sectors    : {sym: GICS sector}
    spy        : DataFrame of SPY bars (drives the calendar and the regime gate)
    membership : {sym: [(start, end), ...]} point-in-time index membership,
                 or None to disable the check
    strategy   : callable(snap, ctx, p) -> DataFrame with a 'limit' column
    """
    p = dict(DEFAULTS)
    if params:
        p.update(params)

    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cal = spy.index[(spy.index >= start) & (spy.index <= end)]
    if len(cal) == 0:
        raise ValueError("no trading days in window")

    spy_close = spy["Close"].astype(float)
    spy_sma = spy_close.rolling(p["regime_sma"]).mean()

    cash = p["start_equity"]
    positions = {}          # sym -> Position
    orders = {}             # sym -> Order
    trades = []
    equity_curve = []
    n_signals = 0
    n_expired = 0
    n_blocked_caps = 0

    def member(sym, day):
        if membership is None:
            return True
        for a, b in membership.get(sym, ()):
            if a <= day <= b:
                return True
        return False

    for di, day in enumerate(cal):

        # ---------------------------------------------------- 1. exits
        for sym in list(positions):
            pos = positions[sym]
            f = feats[sym]
            held = di - pos.entry_day
            if day not in f.index:
                # symbol stopped trading (delisted, acquired). Liquidate at the
                # last price that actually existed rather than holding a ghost.
                if day > f.index[-1]:
                    px = float(f["close"].iloc[-1]) * (1.0 - p["slippage"])
                    cash += pos.shares * px
                    risk = pos.shares * (pos.entry_px - pos.stop)
                    trades.append(Trade(
                        sym=sym, sector=pos.sector,
                        entry_date=cal[pos.entry_day], exit_date=f.index[-1],
                        entry_px=pos.entry_px, exit_px=px, shares=pos.shares,
                        reason="delisted", pnl=pos.shares * (px - pos.entry_px),
                        ret_pct=(px / pos.entry_px - 1.0) * 100.0, bars_held=held,
                        r_multiple=(pos.shares * (px - pos.entry_px) / risk)
                        if risk > 0 else float("nan")))
                    del positions[sym]
                continue
            bar = f.loc[day]
            reason = exit_px = None

            # stop checked before target: same-bar ties score as losses (sec.7)
            if bar["low"] <= pos.stop:
                reason, exit_px = "stop", pos.stop
                if bar["open"] < pos.stop:      # gapped through the stop
                    exit_px = bar["open"]
            elif bar["high"] >= pos.target:
                reason, exit_px = "target", pos.target
                if bar["open"] > pos.target:    # gapped through the target
                    exit_px = bar["open"]
            elif held >= p["max_hold"]:
                reason, exit_px = "time", bar["close"]

            if reason is None:
                continue
            fill = exit_px * (1.0 - p["slippage"])
            cash += pos.shares * fill
            pnl = pos.shares * (fill - pos.entry_px)
            risk = pos.shares * (pos.entry_px - pos.stop)
            trades.append(Trade(
                sym=sym, sector=pos.sector,
                entry_date=cal[pos.entry_day], exit_date=day,
                entry_px=pos.entry_px, exit_px=fill, shares=pos.shares,
                reason=reason, pnl=pnl,
                ret_pct=(fill / pos.entry_px - 1.0) * 100.0,
                bars_held=held,
                r_multiple=(pnl / risk) if risk > 0 else float("nan"),
            ))
            del positions[sym]

        # ---------------------------------------------------- 2. fills
        for sym in list(orders):
            o = orders[sym]
            if di <= o.place_day:               # cannot fill the day it is placed
                continue
            f = feats[sym]
            if day not in f.index:
                continue
            bar = f.loc[day]
            if bar["low"] > o.limit:
                continue
            raw = min(bar["open"], o.limit)     # a gap down fills at the open
            entry = raw * (1.0 + p["slippage"])
            cost = o.shares * entry
            if o.shares <= 0 or cost > cash:
                del orders[sym]
                continue
            # LOOKAHEAD: the bracket must be sized off the LAST COMPLETED bar.
            # Using bar["atr"] here would use the entry day's own high and low,
            # which are not known at the moment the limit fills intraday.
            j = f.index.get_loc(day)
            a = float(f["atr"].iloc[j - 1]) if j > 0 else float("nan")
            if not np.isfinite(a) or a <= 0:
                a = o.atr_at_signal
            stop = raw - p["stop_atr"] * a
            target = raw + p["target_atr"] * a
            cash -= cost
            positions[sym] = Position(
                sym=sym, shares=o.shares, entry_px=entry, entry_day=di,
                stop=stop, target=target, sector=o.sector, atr_at_entry=a,
            )
            del orders[sym]

            # Same-bar risk. We do not know whether the day's low came before or
            # after our fill, so assume the worse of the two, consistent with
            # spec sec.7 scoring ties as losses.
            if bar["low"] <= stop:
                fill_out = stop * (1.0 - p["slippage"])
                cash += o.shares * fill_out
                risk = o.shares * (entry - stop)
                pnl = o.shares * (fill_out - entry)
                trades.append(Trade(
                    sym=sym, sector=o.sector, entry_date=day, exit_date=day,
                    entry_px=entry, exit_px=fill_out, shares=o.shares,
                    reason="stop", pnl=pnl,
                    ret_pct=(fill_out / entry - 1.0) * 100.0, bars_held=0,
                    r_multiple=(pnl / risk) if risk > 0 else float("nan")))
                del positions[sym]

        # ---------------------------------------------------- 3. expiry
        for sym in list(orders):
            if di >= orders[sym].expire_day:
                del orders[sym]
                n_expired += 1

        # ---------------------------------------------------- mark to market
        mtm = 0.0
        for sym, pos in positions.items():
            f = feats[sym]
            px = f["close"].asof(day)
            mtm += pos.shares * (px if np.isfinite(px) else pos.entry_px)
        equity = cash + mtm
        equity_curve.append((day, equity, cash, len(positions), len(orders)))

        # ---------------------------------------------------- 4. signals
        if di + 1 >= len(cal):
            continue
        sma = spy_sma.asof(day)
        regime_ok = bool(np.isfinite(sma) and spy_close.asof(day) > sma)

        slots = p["max_positions"] - len(positions) - len(orders)
        if not regime_ok or slots <= 0:
            continue

        rows = []
        for sym, f in feats.items():
            if sym in positions or sym in orders:
                continue
            if not member(sym, day):
                continue
            i = f.index.searchsorted(day, side="right") - 1
            if i < 0 or f.index[i] != day:      # no bar for this symbol today
                continue
            r = f.iloc[i]
            if not np.isfinite(r["atr"]) or not np.isfinite(r["rngpos"]):
                continue
            rows.append((sym, r["close"], r["rsi"], r["atr"], r["adv"],
                         r["rngpos"], r["atrpct"], bool(r["earn_block"])))
        if not rows:
            continue
        snap = pd.DataFrame(rows, columns=["sym", "close", "rsi", "atr", "adv",
                                           "rngpos", "atrpct", "earn_block"]
                            ).set_index("sym")

        picks = strategy(snap, {"regime_ok": regime_ok, "day": day}, p)
        if picks is None or len(picks) == 0:
            continue

        sector_count = {}
        for s in list(positions) + list(orders):
            sec = sectors.get(s, "Unknown")
            sector_count[sec] = sector_count.get(sec, 0) + 1

        committed = sum(o.shares * o.limit for o in orders.values())
        avail = cash - committed

        for sym, row in picks.iterrows():
            if slots <= 0:
                break
            sec = sectors.get(sym, "Unknown")
            if sector_count.get(sec, 0) >= p["max_per_sector"]:
                n_blocked_caps += 1
                continue
            limit = float(row["limit"])
            a = float(snap.loc[sym, "atr"])
            risk_per_share = p["stop_atr"] * a
            if risk_per_share <= 0:
                continue
            shares = int((equity * p["risk_frac"]) // risk_per_share)
            shares = min(shares, int((equity * p["max_pos_frac"]) // limit))
            shares = min(shares, int(avail // limit) if limit > 0 else 0)
            if shares <= 0:
                continue
            orders[sym] = Order(sym=sym, limit=limit, shares=shares,
                                place_day=di, expire_day=di + p["order_good_days"],
                                sector=sec, atr_at_signal=a)
            avail -= shares * limit
            sector_count[sec] = sector_count.get(sec, 0) + 1
            slots -= 1
            n_signals += 1

    eq = pd.DataFrame(equity_curve,
                      columns=["date", "equity", "cash", "n_pos", "n_ord"]
                      ).set_index("date")
    tr = pd.DataFrame([t.__dict__ for t in trades])
    meta = dict(signals=n_signals, expired=n_expired,
                sector_blocked=n_blocked_caps,
                still_open=len(positions), still_pending=len(orders))
    if verbose:
        print("  orders placed %d | expired unfilled %d | trades closed %d | "
              "open at end %d" % (n_signals, n_expired, len(tr), len(positions)))
    return eq, tr, meta


# ======================================================================
# statistics
# ======================================================================

def _cagr(eq):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    if yrs <= 0 or eq.iloc[0] <= 0:
        return float("nan")
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1


def _maxdd(eq):
    return float((eq / eq.cummax() - 1.0).min())


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(q):
    # Acklam's rational approximation; plenty accurate for this use
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if q < pl:
        x = math.sqrt(-2 * math.log(q))
        return (((((c[0]*x+c[1])*x+c[2])*x+c[3])*x+c[4])*x+c[5]) / \
               ((((d[0]*x+d[1])*x+d[2])*x+d[3])*x+1)
    if q > ph:
        x = math.sqrt(-2 * math.log(1 - q))
        return -(((((c[0]*x+c[1])*x+c[2])*x+c[3])*x+c[4])*x+c[5]) / \
                ((((d[0]*x+d[1])*x+d[2])*x+d[3])*x+1)
    x = q - 0.5
    r = x * x
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*x / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def deflated_sharpe(daily_rets, n_trials, trial_sr_var=None):
    """
    Bailey & Lopez de Prado's Deflated Sharpe Ratio.

    Plain language: "given that we tried n_trials different versions, and given
    how lumpy these returns are, what is the probability the true Sharpe is
    above zero?" Below 0.95 means the result is consistent with luck.

    trial_sr_var: variance of the Sharpe ratios across the versions tried. If
    only one version has been run there is nothing to measure, so a
    conservative stand-in is used.
    """
    r = pd.Series(daily_rets).dropna()
    T = len(r)
    if T < 30 or r.std(ddof=1) == 0:
        return float("nan"), float("nan"), float("nan")
    sr = r.mean() / r.std(ddof=1)                 # per-day Sharpe
    g3 = float(r.skew())
    g4 = float(r.kurt()) + 3.0                    # pandas gives excess kurtosis

    n = max(int(n_trials), 1)
    if n == 1:
        sr0 = 0.0
    else:
        v = trial_sr_var if trial_sr_var and trial_sr_var > 0 else (1.0 / T)
        gamma = 0.5772156649
        sr0 = math.sqrt(v) * ((1 - gamma) * _norm_ppf(1 - 1.0 / n) +
                              gamma * _norm_ppf(1 - 1.0 / (n * math.e)))
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2))
    dsr = _norm_cdf((sr - sr0) * math.sqrt(T - 1) / denom)
    return dsr, sr * math.sqrt(252), sr0 * math.sqrt(252)


def log_trial(name, sharpe_daily):
    """Every run gets recorded. n_trials in the deflated Sharpe is then a fact,
    not a number we choose after the event."""
    log = []
    if os.path.exists(TRIALS_LOG):
        try:
            log = json.load(open(TRIALS_LOG))
        except Exception:
            log = []
    log.append({"name": name, "sr_daily": float(sharpe_daily),
                "ts": pd.Timestamp.now().isoformat(timespec="seconds")})
    json.dump(log, open(TRIALS_LOG, "w"), indent=1)
    srs = [x["sr_daily"] for x in log]
    var = float(np.var(srs, ddof=1)) if len(srs) > 1 else None
    return len(log), var


def report(eq, tr, meta, spy, label, count_trial=True):
    """Print the scorecard. Returns a dict of the numbers."""
    e = eq["equity"]
    rets = e.pct_change().dropna()
    win = spy.loc[(spy.index >= eq.index[0]) & (spy.index <= eq.index[-1]), "Close"]
    spy_rets = win.pct_change().dropna()

    # Excess-over-SPY returns. This matters more than the raw series: a
    # long-only strategy in a rising market has a positive Sharpe simply for
    # being long, and the deflated Sharpe tests against ZERO, not against the
    # index. Beating zero is not the goal; beating buy-and-hold is.
    ex = (rets - spy_rets.reindex(rets.index)).dropna()

    sr_daily = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) > 0 else 0.0
    sr_ex_daily = ex.mean() / ex.std(ddof=1) if len(ex) > 2 and ex.std(ddof=1) > 0 else 0.0
    n_trials, var = (log_trial(label, sr_ex_daily) if count_trial else (1, None))
    dsr, sr_ann, sr0_ann = deflated_sharpe(rets, n_trials, var)
    dsr_ex, sr_ex_ann, _ = deflated_sharpe(ex, n_trials, var)

    res = dict(
        label=label,
        start=str(eq.index[0].date()), end=str(eq.index[-1].date()),
        trades=len(tr),
        cagr=_cagr(e), maxdd=_maxdd(e),
        spy_cagr=_cagr(win), spy_maxdd=_maxdd(win),
        sharpe=sr_ann, dsr=dsr, sharpe_ex=sr_ex_ann, dsr_ex=dsr_ex,
        n_trials=n_trials,
        exposure=float(eq["n_pos"].mean()),
        final_equity=float(e.iloc[-1]),
    )

    print("\n" + "=" * 66)
    print("  %s   %s -> %s" % (label, res["start"], res["end"]))
    print("=" * 66)

    if len(tr):
        wins = tr[tr.pnl > 0]
        loss = tr[tr.pnl <= 0]
        pf = wins.pnl.sum() / abs(loss.pnl.sum()) if len(loss) and loss.pnl.sum() != 0 else float("inf")
        res.update(win_rate=len(wins) / len(tr), profit_factor=pf,
                   mean_ret=float(tr.ret_pct.mean()),
                   mean_r=float(tr.r_multiple.mean()),
                   total_pnl=float(tr.pnl.sum()),
                   pnl_ex_best5=float(tr.pnl.sum() - tr.pnl.nlargest(5).sum()))
        print("  trades resolved   %d   (stop %d / target %d / time %d / delisted %d)"
              % (len(tr), (tr.reason == "stop").sum(),
                 (tr.reason == "target").sum(), (tr.reason == "time").sum(),
                 (tr.reason == "delisted").sum()))
        print("  win rate          %.1f%%" % (100 * res["win_rate"]))
        print("  mean per trade    %+.2f%%   median %+.2f%%   mean R %+.2f"
              % (res["mean_ret"], tr.ret_pct.median(), res["mean_r"]))
        print("  profit factor     %.2f" % pf)
        print("  median bars held  %.0f" % tr.bars_held.median())
        print("  total P&L         ${:+,.0f}   without best 5 trades  ${:+,.0f}"
              .format(res["total_pnl"], res["pnl_ex_best5"]))
    else:
        print("  NO TRADES")

    print("  -" * 32)
    print("  CAGR              %+.2f%%      SPY %+.2f%%   (price only, no dividends)"
          % (100 * res["cagr"], 100 * res["spy_cagr"]))
    print("  max drawdown      %.1f%%       SPY %.1f%%"
          % (100 * res["maxdd"], 100 * res["spy_maxdd"]))
    print("  Sharpe (annual)   %.2f" % sr_ann)
    print("  avg positions     %.2f of %d   (capital mostly idle if this is low)"
          % (res["exposure"], DEFAULTS["max_positions"]))
    print("  orders that never filled: %d" % meta["expired"])
    print("  -" * 32)
    print("  DEFLATED SHARPE, versions tried = %d" % n_trials)
    print("    vs cash   %.3f   is the return above zero?   %s"
          % (dsr, "yes" if dsr >= 0.95 else "not established"))
    print("    vs SPY    %.3f   is there edge BEYOND being  %s"
          % (dsr_ex, "yes" if dsr_ex >= 0.95 else "NO"))
    print("                    long a rising market?")
    print("     %s" % ("PASS: the edge over the index is unlikely to be luck."
                       if dsr_ex >= 0.95 else
                       "FAIL: nothing here beats holding the index. A long-only "
                       "strategy in a bull market scores well against cash "
                       "for free; that is not edge."))
    return res


def check_criteria(res, tr):
    """strategy_spec_v1.md section 8, checked mechanically so it cannot be
    reinterpreted after seeing the result."""
    c = [
        ("resolved trades >= 100", res["trades"] >= 100, "%d" % res["trades"]),
        ("CAGR > SPY + 3pp",
         res["cagr"] > res["spy_cagr"] + 0.03,
         "%.2f%% vs %.2f%%" % (100 * res["cagr"], 100 * res["spy_cagr"] + 3)),
        ("max drawdown < SPY",
         res["maxdd"] > res["spy_maxdd"],
         "%.1f%% vs %.1f%%" % (100 * res["maxdd"], 100 * res["spy_maxdd"])),
        ("profit factor >= 1.3",
         res.get("profit_factor", 0) >= 1.3, "%.2f" % res.get("profit_factor", 0)),
        ("positive without best 5 trades",
         res.get("pnl_ex_best5", -1) > 0,
         "${:+,.0f}".format(res.get("pnl_ex_best5", 0))),
    ]
    print("\n  PRE-REGISTERED SUCCESS CRITERIA (spec section 8)")
    for name, ok, detail in c:
        print("    [%s] %-32s %s" % ("PASS" if ok else "FAIL", name, detail))
    allok = all(x[1] for x in c)
    print("\n  VERDICT: %s" % ("PASSES the build window -- one run on 2026 is authorised"
                               if allok else
                               "FAILS the build window. Per spec section 8 we do not tune it "
                               "into passing."))
    return allok


# ======================================================================
# THE STRATEGY -- this is the only part meant to change
# ======================================================================

def weakness_reversion(snap, ctx, p):
    """
    Buy the most beaten-down names in the index, but only while the broad
    market is healthy, and only when they are down rather than collapsing.

    snap : one row per candidate symbol, today's indicator values
    ctx  : {'regime_ok': bool, 'day': Timestamp}
    p    : parameters
    returns: the chosen rows with a 'limit' column added

    Four rules, per spec section 4:
      1. RSI(14) <= 40                    weakness -- the one verified edge
      2. close in the top 40% of the       not a falling knife
         252-day range
      3. 1.5% <= ATR <= 6% of price,       tradeable and liquid
         price > $10, ADV > $20M,
         not near earnings
      4. SPY above its 200-day average     regime gate
    Then take the 5 lowest RSI names and place a resting limit 0.5 ATR below
    the close, good for 10 trading days.
    """
    if not ctx["regime_ok"]:
        return None

    ok = snap[
        (snap["rsi"] <= p["rsi_max"]) &
        (snap["rngpos"] >= p["min_range_pos"]) &
        (snap["atrpct"] >= p["atr_pct_min"]) &
        (snap["atrpct"] <= p["atr_pct_max"]) &
        (snap["close"] > p["min_price"]) &
        (snap["adv"] >= p["min_adv"]) &
        (~snap["earn_block"])
    ]
    if ok.empty:
        return None

    picks = ok.nsmallest(p["n_picks"], "rsi").copy()
    picks["limit"] = picks["close"] - p["limit_atr"] * picks["atr"]
    return picks
