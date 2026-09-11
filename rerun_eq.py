"""Range (EQ) study, full then focus. pythonw rerun_eq.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/eq_study.py", "--procs", "20", "--log", "logs/eq_study.log"],
        ["studies/eq_study.py", "--focus", "--procs", "20", "--log", "logs/eq_study_focus.log"]]
with open("logs/rerun_eq.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
