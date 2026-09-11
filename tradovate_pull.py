"""
tradovate_pull.py -- download ES bars and your own fills from Tradovate.

    python tradovate_pull.py bars ESU6 1 minute 20000
    python tradovate_pull.py fills

CREDENTIALS -- read this first
-----------------------------
This script reads your credentials from a local file called `.env` that YOU
create. Nothing is typed into a chat, nothing is sent anywhere except Tradovate,
and the file never leaves your machine. Create `.env` next to this script:

    TRADOVATE_NAME=your_username
    TRADOVATE_PASSWORD=your_password
    TRADOVATE_APPID=your_app_name
    TRADOVATE_CID=your_cid
    TRADOVATE_SEC=your_api_secret
    TRADOVATE_ENV=live          # or: demo

You get appId / cid / sec from Tradovate: Application Settings -> API Access.
Add `.env` to .gitignore. Never paste these values into a chat window.

WHAT YOU CAN ACTUALLY GET
-------------------------
Bars come from the market-data WebSocket, 4096 elements per request, walked
backwards with `closestTimestamp` until you have what you need. Tradovate's
historical depth through this endpoint is limited and it requires an active CME
market-data subscription on your account.

For deep history (years of 1-minute or tick data) a one-time purchase from
FirstRate Data or Kibot is faster and cheaper than paging this API. Tradovate's
real advantages are (a) YOUR OWN FILLS, which nobody else has, and (b) live data
going forward.

API reference: https://api.tradovate.com/
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = {"live": "https://live.tradovateapi.com/v1",
        "demo": "https://demo.tradovateapi.com/v1"}
MD_WS = "wss://md.tradovateapi.com/v1/websocket"


def load_env(path=".env"):
    if not os.path.exists(path):
        sys.exit("No .env file found. See the notes at the top of this script.")
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    need = ["TRADOVATE_NAME", "TRADOVATE_PASSWORD", "TRADOVATE_APPID",
            "TRADOVATE_CID", "TRADOVATE_SEC"]
    missing = [k for k in need if k not in env]
    if missing:
        sys.exit("Missing from .env: " + ", ".join(missing))
    return env


def auth(env):
    base = BASE[env.get("TRADOVATE_ENV", "live")]
    body = {"name": env["TRADOVATE_NAME"],
            "password": env["TRADOVATE_PASSWORD"],
            "appId": env["TRADOVATE_APPID"],
            "appVersion": "1.0",
            "cid": int(env["TRADOVATE_CID"]),
            "sec": env["TRADOVATE_SEC"]}
    r = requests.post(base + "/auth/accesstokenrequest", json=body, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "accessToken" not in j:
        sys.exit("Auth failed: %s" % j)
    print("authenticated, token expires %s" % j.get("expirationTime"))
    return base, j["accessToken"], j.get("mdAccessToken", j["accessToken"])


# ------------------------------------------------------------------ fills

def pull_fills(base, token):
    """Your own executed trades. This is the dataset nobody else has."""
    h = {"Authorization": "Bearer " + token}
    out = {}
    for ep in ["fill/list", "order/list", "execution/list", "position/list",
               "contract/list", "cashBalance/list"]:
        try:
            r = requests.get("%s/%s" % (base, ep), headers=h, timeout=60)
            if r.status_code == 200:
                d = pd.DataFrame(r.json())
                out[ep.split("/")[0]] = d
                print("  %-14s %5d rows" % (ep, len(d)))
            else:
                print("  %-14s HTTP %d" % (ep, r.status_code))
        except Exception as e:
            print("  %-14s %s" % (ep, type(e).__name__))
    for name, d in out.items():
        if len(d):
            d.to_csv("tradovate_%s.csv" % name, index=False)
    print("\nwrote tradovate_*.csv")
    return out


# ------------------------------------------------------------------ bars

def pull_bars(md_token, symbol, size, unit, n_elements):
    """
    Walk the chart endpoint backwards in 4096-element chunks.

    Tradovate's market-data socket uses a plain-text frame format:
        <endpoint>\\n<request id>\\n<query>\\n<json body>
    and replies arrive as SockJS-style 'a[...]' frames.
    """
    try:
        from websocket import create_connection
    except ImportError:
        sys.exit("pip install websocket-client")

    ws = create_connection(MD_WS, timeout=30)
    ws.recv()                                   # 'o' open frame
    ws.send("authorize\n1\n\n%s" % md_token)

    unit_map = {"tick": "Tick", "minute": "MinuteBar",
                "daily": "DailyBar", "second": "Tick"}
    bars, req = [], 2
    end = datetime.now(timezone.utc)

    while len(bars) < n_elements:
        body = {
            "symbol": symbol,
            "chartDescription": {
                "underlyingType": unit_map.get(unit, "MinuteBar"),
                "elementSize": int(size),
                "elementSizeUnit": "UnderlyingUnits",
                "withHistogram": False,
            },
            "timeRange": {
                "asMuchAsElements": 4096,
                "closestTimestamp": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        ws.send("md/getChart\n%d\n\n%s" % (req, json.dumps(body)))
        req += 1

        got = 0
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                msg = ws.recv()
            except Exception:
                break
            if not msg or msg[0] != "a":
                continue
            for frame in json.loads(msg[1:]):
                for pkt in frame.get("d", {}).get("bars", []) or []:
                    bars.append(pkt)
                    got += 1
            if got:
                break
        if got == 0:
            print("  no more data returned; stopping")
            break
        oldest = min(b["timestamp"] for b in bars)
        end = pd.Timestamp(oldest).to_pydatetime()
        print("  %d bars, back to %s" % (len(bars), oldest))

    ws.close()
    if not bars:
        sys.exit("No bars returned. Check your CME market-data subscription.")
    d = pd.DataFrame(bars).drop_duplicates("timestamp").sort_values("timestamp")
    d.to_csv("tradovate_%s_%s%s.csv" % (symbol, size, unit), index=False)
    print("wrote %d bars" % len(d))
    return d


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    env = load_env()
    base, token, md_token = auth(env)
    if sys.argv[1] == "fills":
        pull_fills(base, token)
    elif sys.argv[1] == "bars":
        sym = sys.argv[2] if len(sys.argv) > 2 else "ESU6"
        size = sys.argv[3] if len(sys.argv) > 3 else "1"
        unit = sys.argv[4] if len(sys.argv) > 4 else "minute"
        n = int(sys.argv[5]) if len(sys.argv) > 5 else 20000
        pull_bars(md_token, sym, size, unit, n)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
