"""names_map.py -- ticker -> full name, for the pages. Writes validation/names_map.json.

    python names_map.py

Stocks/ETFs from the Nasdaq symbol files, crypto from CoinGecko (top 1000 by
volume), futures roots and currency codes from fixed lists.
"""

import json
import os
import time

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0"}
FUT = {"ES": "S&P 500 E-mini", "NQ": "Nasdaq 100 E-mini", "YM": "Dow E-mini", "RTY": "Russell 2000 E-mini",
       "NKD": "Nikkei 225 (dollar)", "ZB": "30-year T-Bond", "ZN": "10-year T-Note", "ZF": "5-year T-Note",
       "ZT": "2-year T-Note", "UB": "Ultra T-Bond", "6E": "Euro FX", "6J": "Japanese Yen", "6B": "British Pound",
       "6A": "Australian Dollar", "6C": "Canadian Dollar", "6S": "Swiss Franc", "6N": "New Zealand Dollar",
       "6M": "Mexican Peso", "6L": "Brazilian Real", "BTC": "Bitcoin futures", "ETH": "Ether futures",
       "MES": "Micro S&P 500", "MNQ": "Micro Nasdaq 100", "M2K": "Micro Russell 2000", "MYM": "Micro Dow",
       "SI": "Silver", "CL": "Crude Oil (WTI)", "BZ": "Brent Crude", "NG": "Natural Gas", "RB": "RBOB Gasoline",
       "HO": "Heating Oil", "QM": "Mini Crude", "QG": "Mini Natural Gas", "GC": "Gold", "MGC": "Micro Gold",
       "SIL": "Micro Silver", "HG": "Copper", "PL": "Platinum", "PA": "Palladium", "ALI": "Aluminum",
       "ZC": "Corn", "ZS": "Soybeans", "ZW": "Wheat (Chicago)", "ZM": "Soybean Meal", "ZL": "Soybean Oil",
       "ZO": "Oats", "ZR": "Rough Rice", "KE": "Wheat (Kansas City)", "KC": "Coffee", "SB": "Sugar #11",
       "CC": "Cocoa", "CT": "Cotton", "OJ": "Orange Juice", "LE": "Live Cattle", "GF": "Feeder Cattle",
       "HE": "Lean Hogs", "DC": "Class III Milk"}
CCY = {"USD": "US Dollar", "EUR": "Euro", "JPY": "Japanese Yen", "GBP": "British Pound", "AUD": "Australian Dollar",
       "CAD": "Canadian Dollar", "CHF": "Swiss Franc", "NZD": "New Zealand Dollar", "MXN": "Mexican Peso",
       "ZAR": "South African Rand", "SEK": "Swedish Krona", "NOK": "Norwegian Krone", "SGD": "Singapore Dollar",
       "HKD": "Hong Kong Dollar", "TRY": "Turkish Lira", "PLN": "Polish Zloty", "INR": "Indian Rupee"}


def stocks():
    out = {}
    for url, col in (("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol"),
                     ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol")):
        try:
            d = pd.read_csv(url, sep="|")
            for s, n in zip(d[col].astype(str), d["Security Name"].astype(str)):
                out[s] = n.split(" - ")[0].strip()
        except Exception as ex:
            print("  %s: %s" % (url.rsplit("/", 1)[-1], ex))
    return out


def crypto():
    out = {}
    for page in range(1, 5):
        try:
            r = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                             params={"vs_currency": "usd", "order": "volume_desc", "per_page": 250, "page": page},
                             headers=UA, timeout=30).json()
        except Exception:
            break
        if not isinstance(r, list):
            break
        for x in r:
            s = str(x.get("symbol", "")).upper()
            out.setdefault(s, x.get("name"))
        time.sleep(1.5)
    return out


if __name__ == "__main__":
    m = {"stock": stocks(), "crypto": crypto(),
         "futures": {"%s_F" % k: v for k, v in FUT.items()},
         "forex": {"%s%s_X" % (a, b): "%s / %s" % (CCY.get(a, a), CCY.get(b, b))
                   for a in CCY for b in CCY if a != b}}
    os.makedirs("validation", exist_ok=True)
    json.dump(m, open(os.path.join("validation", "names_map.json"), "w"))
    print("  names: %d stocks/ETFs, %d crypto, %d futures, %d fx" % (
        len(m["stock"]), len(m["crypto"]), len(m["futures"]), len(m["forex"])))
