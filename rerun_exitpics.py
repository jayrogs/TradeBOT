"""Random example charts under four exits, 2 per timeframe each (all on the same seed, so the same
trades where the entry matches). pythonw rerun_exitpics.py"""
import subprocess, sys, os, time, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
M = ["chandelier 5 bars under the high, from the start",
     "chandelier 3 bars under the high, from the start",
     "the line, wick rule 1.5 bars wide",
     None]
slug = lambda m: "graded" if m is None else re.sub(r"[^a-z0-9]+", "_", m.lower()).strip("_")
with open("logs/rerun_exitpics.log", "a") as f:
    for m in M:
        out = os.path.join("validation", "exit_cases", slug(m))
        args = ["pics_ride.py", "--seed", "20260907", "--per-tf", "2", "--out", out, "--log", "logs/exitpics_%s.log" % slug(m)]
        if m: args += ["--manager", m]
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), slug(m))); f.flush()
        r = subprocess.run([sys.executable] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
