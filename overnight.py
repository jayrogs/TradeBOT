"""overnight.py -- wait for every data pull to finish, then rerun the
backburner study, the test battery, and write a morning report.

    python overnight.py            # blocks; launch detached (run via WMI like the server)

Watches the pull logs for their finish markers (or the 8-hour deadline),
then runs studies/backburner_study.py, run_tests.py, and writes
logs/morning_report.txt: what data landed, the by-timeframe / by-class
tables, and the conditions that held. The dashboard's study card and /study
read the refreshed json directly.
"""

import glob
import json
import os
import subprocess
import sys
import time

import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))
DEADLINE_H = 9
PULLS = {                       # log -> marker that means "finished"
    os.path.join("logs", "backfill_crypto_15m.log"): "  done",
    os.path.join("logs", "backfill_crypto_5m_all.log"): "  done",
    os.path.join("logs", "backfill_crypto_extra.log"): "  done",
    os.path.join("logs", "backfill_okx.log"): "  done",
    os.path.join("logs", "bf300_1d.log"): "done:",
    os.path.join("logs", "bf600_1d.log"): "done:",
    os.path.join("logs", "backfill_dukascopy.log"): "  done",
    os.path.join("logs", "backfill_databento.log"): "  done",
}


def finished(path, marker):
    try:
        return marker in open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return False


def log(msg):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)


def inventory():
    rows = []
    for label, pat in (("crypto hourly", "history/*_1h.csv.gz"),
                       ("crypto 15m", "history/crypto_15m/*.csv.gz"),
                       ("crypto 5m", "history/crypto_5m/*.csv.gz"),
                       ("stocks hourly", "history/stocks/*_1h.csv.gz"),
                       ("stocks 15m", "history/stocks/*_15m.csv.gz"),
                       ("stocks 5m", "history/stocks/*_5m.csv.gz"),
                       ("stocks daily", "history/stocks/*_1d.csv.gz"),
                       ("futures 5m (Databento)", "history/futures/*_5m.csv.gz"),
                       ("futures hourly", "history/futures/*_1h.csv.gz"),
                       ("forex 5m (Dukascopy)", "history/forex/*_5m.csv.gz"),
                       ("forex hourly", "history/forex/*_1h.csv.gz"),
                       ("CFD proxies hourly", "history/futures_cfd/*_1h.csv.gz")):
        rows.append("  %-26s %4d files" % (label, len(glob.glob(pat))))
    return "\n".join(rows)


def main():
    t0 = time.time()
    log("overnight: waiting for the data pulls (deadline %dh)" % DEADLINE_H)
    while time.time() - t0 < DEADLINE_H * 3600:
        left = [p for p, m in PULLS.items() if not finished(p, m)]
        if not left:
            break
        time.sleep(120)
    left = [p for p, m in PULLS.items() if not finished(p, m)]
    log("pulls finished" if not left else "deadline: still running %s" % [os.path.basename(p) for p in left])

    log("running the backburner study")
    r = subprocess.run([sys.executable, "-u", os.path.join("studies", "backburner_study.py")],
                       capture_output=True, text=True)
    study_out = r.stdout[r.stdout.find("BACKBURNER STUDY"):] if "BACKBURNER STUDY" in r.stdout else r.stdout[-3000:]
    log("study exit %d" % r.returncode)

    log("running the test battery")
    t = subprocess.run([sys.executable, "run_tests.py"], capture_output=True, text=True)
    log("tests exit %d" % t.returncode)

    # by-class table from the json, in plain words
    classes = ""
    try:
        d = json.load(open(os.path.join("validation", "backburner_study.json")))
        lines = ["  %-8s %8s  %10s %10s %10s  %5s %5s" % ("class", "campaigns", "sell-all", "12EMA-ride", "trend-ride", "win", "bad")]
        for k, b in d["conditions"]["asset"].items():
            lines.append("  %-8s %8d  %+9.2f%% %+9.2f%% %+9.2f%%  %4.0f%% %4.0f%%" % (
                k, b["n"], 100 * b["dw"], 100 * b["ride_dw"], 100 * b["trend_dw"], 100 * b["win"], 100 * b["bad"]))
        classes = "\n".join(lines)
    except Exception as ex:
        classes = "  (no json: %s)" % ex

    report = "\n".join([
        "MORNING REPORT  %s" % time.strftime("%Y-%m-%d %H:%M"),
        "",
        "DATA ON DISK",
        inventory(),
        "",
        "PULLS STILL RUNNING AT REPORT TIME: %s" % (", ".join(os.path.basename(p) for p in left) or "none"),
        "",
        "TESTS: %s" % ("all pass" if t.returncode == 0 else "FAILURES -- see logs/tests_last.txt"),
        t.stdout.strip(),
        "",
        "BACKBURNER STUDY (money-weighted, after costs)",
        study_out.strip(),
        "",
        "BY CLASS",
        classes,
        "",
        "Pages: /study for every table, / for the dashboard.",
    ])
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "morning_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(report)
    log("morning report written")


if __name__ == "__main__":
    main()
