"""Random example charts under four exits, 2 per timeframe each (all on the same seed, so the same
trades where the entry matches). pythonw rerun_exitpics.py"""
import subprocess, sys, os, time, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
M = ["chandelier 12 bars under the highest close",
     "chandelier that tightens with profit: 5 bars, 3 once up 5R, 2 once up 10R",
     "the second lower high (pure structure)",
     "trail 15% under the highest close"]
slug = lambda m: "graded" if m is None else re.sub(r"[^a-z0-9]+", "_", m.lower()).strip("_")
with open("logs/rerun_exitpics2.log", "a") as f:
    for m in M:
        out = os.path.join("validation", "exit_cases", slug(m))
        args = ["pics_ride.py", "--seed", "20260907", "--per-tf", "2", "--out", out, "--log", "logs/exitpics_%s.log" % slug(m)]
        if m: args += ["--manager", m]
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), slug(m))); f.flush()
        r = subprocess.run([sys.executable] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
