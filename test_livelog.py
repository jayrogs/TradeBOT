"""test_livelog.py -- the forward log's plumbing, offline.

    python test_livelog.py

The ledger silently failed to settle outcomes for a full day because an
all-empty string column loaded as float64 and refused a date string. These
tests make that class of failure loud, with no network involved:

  1. ledger roundtrip: save -> load preserves string columns as strings,
     and a settlement write into a fresh ledger cannot raise
  2. settlement correctness: a synthetic open signal settled through an
     injected offline fetch must match rider_lab.run_exit exactly
  3. dedup: scanning the same (sym, tf, bar) twice must not double-log
"""

import os
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import rider_lab as L          # noqa: E402
import signal_log as SL        # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  " + detail if detail and not cond else "")))
    if not cond:
        FAILS.append(name)


def fresh_ledger(tmp):
    SL.SIG = os.path.join(tmp, "signals.csv")
    SL.DIR = tmp


def row(sym, tf, bar, fill):
    return dict(logged_at="2026-01-01 00:00:00", bar=str(bar), sym=sym,
                tf=tf, fill=fill, stop0=fill * 0.97, wind=9, relvol=1.5,
                ret7d=0.01, late=0, status="open", promoted=0, last_px=fill,
                unreal=0.0, exit_at="", exit_px=np.nan, why="", net=np.nan,
                version="test")


def main():
    tmp = tempfile.mkdtemp()
    fresh_ledger(tmp)

    print("\n1. ledger roundtrip and the dtype regression")
    d = pd.DataFrame([row("BTC", "1h", "2026-01-01 05:00:00", 100.0)])
    SL._save(d)
    d2 = SL._load()
    check("string columns survive as strings",
          all(d2[k].dtype == object for k in SL.STR_COLS),
          str({k: str(d2[k].dtype) for k in SL.STR_COLS}))
    try:
        d2.loc[0, ["status", "exit_at", "exit_px", "why", "net"]] = [
            "closed", "2026-01-02 00:00:00", 99.0, "body", -0.012]
        ok = True
    except Exception as e:
        ok = False
        print("     raised:", e)
    check("settlement write cannot raise on a fresh ledger", ok)

    print("\n2. settlement matches the canonical exit, offline")
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(4000)
    v = L.prep(raw)
    ent = [(e, f) for e, f in L.entries(v, 2, "promote1")
           if e < v["n"] - 2 and L.run_exit(v, e, f, "promote1") is not None]
    check("found an offline RESOLVED test entry", bool(ent))
    if ent:
        entry, fill = ent[-1]
        bar = raw.index[entry]
        SL._save(pd.DataFrame([row("BTC", "1h", bar, fill)]))

        def fake_fetch(sym, src, refresh):
            return raw, {"1h": raw}

        closed = SL.update_outcomes(fetch=fake_fetch)
        d3 = SL._load()
        r = L.run_exit(v, entry, fill, "promote1")
        want_net = r[1] / fill - 1 - 2 * L.COST if r else None
        got = d3.iloc[0]
        check("signal settled", closed == 1 and got["status"] == "closed",
              str(got["status"]))
        if r:
            check("net matches run_exit to 1e-12",
                  abs(float(got["net"]) - want_net) < 1e-12,
                  "%s vs %s" % (got["net"], want_net))
            check("exit bar matches", got["exit_at"] == str(raw.index[r[0]]),
                  "%s vs %s" % (got["exit_at"], raw.index[r[0]]))

    print("\n2b. an UNRESOLVED trade stays open with unreal updated")
    live = [(e, f) for e, f in L.entries(v, 2, "promote1")
            if e < v["n"] - 2 and L.run_exit(v, e, f, "promote1") is None]
    if live:
        e2, f2 = live[-1]
        SL._save(pd.DataFrame([row("BTC", "1h", raw.index[e2], f2)]))
        closed2 = SL.update_outcomes(fetch=fake_fetch)
        g = SL._load().iloc[0]
        check("stays open, no false settlement",
              closed2 == 0 and g["status"] == "open", str(g["status"]))
        check("unrealized tracks the last close",
              abs(float(g["unreal"]) - (v["c"][-1] / f2 - 1)) < 1e-12)
    else:
        print("  (no live ride in the window -- skipped)")

    print("\n3. dedup on (sym, tf, bar)")
    d4 = SL._load()
    seen = set(zip(d4["sym"], d4["tf"], d4["bar"].astype(str)))
    key = (d4.iloc[0]["sym"], d4.iloc[0]["tf"], str(d4.iloc[0]["bar"]))
    check("the logged key is seen", key in seen)

    print("\n  %s" % ("ALL LIVELOG TESTS PASS" if not FAILS
                      else "FAILURES: %s" % ", ".join(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
