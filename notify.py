"""notify.py -- a bot you don't have to open.

Every alert is appended to livelog/alerts.log (always). If livelog/alerts.json
has a webhook URL (Discord / Slack-style: POST {"content": text}), it is
posted there too. Failures never raise -- an alert channel must not be able
to crash the scanner or the forward log.

    livelog/alerts.json   {"webhook": "https://discord.com/api/webhooks/...",
                           "min_weight": 5}

    python notify.py --test      writes a test alert (and posts if configured)
"""

import argparse
import json
import os
import time

DIR = "livelog"
CFG = os.path.join(DIR, "alerts.json")
LOG = os.path.join(DIR, "alerts.log")


def config():
    try:
        return json.load(open(CFG))
    except Exception:
        return {}


def alert(text, kind="info"):
    os.makedirs(DIR, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = "%s  [%s]  %s" % (stamp, kind, text)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    url = (config().get("webhook") or "").strip()
    if url:
        try:
            import requests
            requests.post(url, json={"content": line}, timeout=10)
        except Exception:
            pass
    return line


def recent(n=50):
    try:
        with open(LOG, encoding="utf-8") as f:
            return f.read().splitlines()[-n:]
    except Exception:
        return []


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        print(alert("test alert from notify.py", "test"))
        print("webhook configured:", bool(config().get("webhook")))
