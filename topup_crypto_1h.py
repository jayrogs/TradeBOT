"""topup_crypto_1h.py -- extend every history/<SYM>_1h.csv.gz to now.
The 4h and daily crypto charts are built from these, so this refreshes them too.
Resumable, threads (network-bound). pythonw topup_crypto_1h.py --log logs/topup_1h.log"""
import glob, os, sys, time, warnings
import pandas as pd
import crypto
warnings.filterwarnings("ignore")
if "--log" in sys.argv:
    sys.stdout = sys.stderr = open(sys.argv[sys.argv.index("--log") + 1], "a", buffering=1)


def topup(f):
    sym = os.path.basename(f).split("_1h")[0]
    try:
        old = pd.read_csv(f, index_col=0, parse_dates=True)
        gap_h = (pd.Timestamp.utcnow().tz_localize(None) - old.index[-1]).total_seconds() / 3600
        if gap_h < 3:
            return sym, len(old), "fresh"
        bars = int(min(6000, gap_h + 50))
        new = None
        try:
            new = crypto._coinbase(sym, "1h", bars)
        except Exception:
            pass
        if new is None or len(new) < 5:
            try:
                new = crypto._okx(sym, "1h", bars)
            except Exception:
                new = None
        if new is None or len(new) < 5:
            return sym, len(old), "no source"
        new = new[["Open", "High", "Low", "Close", "Volume"]]
        new = new[new.index > old.index[-1]]
        if new.empty:
            return sym, len(old), "nothing new"
        out = pd.concat([old, new]).sort_index()
        out = out[~out.index.duplicated(keep="last")]
        out.to_csv(f)
        return sym, len(out), "+%d bars to %s" % (len(new), out.index[-1])
    except Exception as ex:
        return sym, 0, "ERR %s" % ex


def main():
    files = sorted(glob.glob(os.path.join("history", "*_1h.csv.gz")))
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sym, n, how in ex.map(topup, files):
            print("  %-8s %7d  %s" % (sym, n, how), flush=True)
    print("done %d files in %.0fs" % (len(files), time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
