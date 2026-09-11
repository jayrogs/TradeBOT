"""Redraw every chart set (after a chartkit change). pythonw rerun_allpics.py"""
import subprocess, sys, os, time, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
slug = lambda m: "graded" if m is None else re.sub(r"[^a-z0-9]+", "_", m.lower()).strip("_")
M = [None, "chandelier 5 bars under the high, from the start", "chandelier 3 bars under the high, from the start",
     "the line, wick rule 1.5 bars wide", "chandelier 12 bars under the highest close",
     "chandelier that tightens with profit: 5 bars, 3 once up 5R, 2 once up 10R",
     "the second lower high (pure structure)", "trail 15% under the highest close"]
jobs = [["pics_idea.py"], ["pics_cases.py", "--log", "logs/pics_cases.log"], ["pics_ride.py", "--log", "logs/pics_ride.log"],
        ["pics_eq.py", "--log", "logs/pics_eq.log"],
        ["pics_eqcoil.py", "--per-tf", "4", "--log", "logs/pics_eqcoil.log"],
        ["pics_eqtrade.py", "--per-tf", "4", "--log", "logs/pics_eqtrade.log"],
        ["pics_eqfree.py", "--per-tf", "4", "--log", "logs/pics_eqfree.log"]]
for m in M:
    a = ["pics_ride.py", "--seed", "20260907", "--per-tf", "2", "--out", os.path.join("validation", "exit_cases", slug(m)), "--log", "logs/exitpics_%s.log" % slug(m)]
    if m: a += ["--manager", m]
    jobs.append(a)
with open("logs/rerun_allpics.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j[:1] + j[-1:]))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
