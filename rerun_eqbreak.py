"""Range (EQ) study, full then focus. pythonw rerun_eq.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/eq_break.py", "--procs", "20", "--log", "logs/eq_break.log"],
        ["studies/eq_break.py", "--focus", "--procs", "20", "--log", "logs/eq_break_focus.log"]]
with open("logs/rerun_eqbreak.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
