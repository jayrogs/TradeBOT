"""split_events.py -- one small file per name from the 4-year study, so the
name page can list every backburner that name ever had without loading the
835k-row events file.  Writes validation/name_events/<kind>_<sym>.json.

    python studies/split_events.py
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studies.backburner_study import CLASS_COST   # noqa: E402

OUT = os.path.join("validation", "name_events")
KEEP = ["tf", "t", "rsi", "units", "held", "ended", "ret", "ret_ride", "ride_end", "ride_held", "part",
        "move", "move3", "move7", "gap_days", "relvol", "own", "up1", "up2", "up1_os", "vs_ema", "half"]


def main():
    ev = pd.read_csv(os.path.join("validation", "backburner_events.csv.gz"), low_memory=False)
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    n = 0
    for (kind, sym), g in ev.groupby(["kind", "sym"]):
        cost = CLASS_COST.get(kind, 0.0005)
        g = g[KEEP].copy()
        g["net"] = g["ret_ride"] - cost
        g["hot"] = (g["move"].fillna(0) >= 0.10) | (g["move3"].fillna(0) >= 0.20)
        g = g.sort_values("t", ascending=False)
        rows = json.loads(g.to_json(orient="records"))
        json.dump(dict(sym=sym, kind=kind, cost=cost, rows=rows),
                  open(os.path.join(OUT, "%s_%s.json" % (kind, sym.replace("/", "_"))), "w"))
        n += 1
    print("  %d name files" % n)


if __name__ == "__main__":
    main()
