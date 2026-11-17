#!/usr/bin/env python3
"""Alpaca MARKET DATA only (free IEX feed + Benzinga news). Never trades.
Auth is injected on the wire for data.alpaca.markets (no keys in code).
Usage:
  alpaca_data.py quote SPY NVDA        latest IEX quote/trade
  alpaca_data.py bars SPY 5Min 20       recent intraday bars
  alpaca_data.py news NVDA,AMD 10       latest Benzinga headlines
"""
import json, sys, urllib.request, urllib.parse
BASE = "https://data.alpaca.markets"

def get(path, **q):
    url = BASE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"APCA-API-KEY-ID": __import__("os").environ["APCA_DATA_KEY_ID"], "APCA-API-SECRET-KEY": __import__("os").environ["APCA_DATA_SECRET_KEY"]}), timeout=20) as r:
        return json.load(r)

def trades(syms):
    return get("/v2/stocks/trades/latest", symbols=",".join(syms), feed="iex").get("trades", {})

def quotes(syms):
    return get("/v2/stocks/quotes/latest", symbols=",".join(syms), feed="iex").get("quotes", {})

def bars(sym, tf="5Min", limit=20, start=None):
    q = dict(timeframe=tf, limit=limit, feed="iex", sort="desc")
    if start: q["start"] = start
    return list(reversed(get(f"/v2/stocks/{sym}/bars", **q).get("bars") or []))

def news(syms, limit=10):
    return get("/v1beta1/news", symbols=syms, limit=limit).get("news", [])

if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "quote":
        t, q = trades(args), quotes(args)
        for s in args:
            print(s, "last", t.get(s, {}).get("p"), "bid", q.get(s, {}).get("bp"), "ask", q.get(s, {}).get("ap"))
    elif cmd == "bars":
        for b in bars(args[0], args[1] if len(args) > 1 else "5Min", int(args[2]) if len(args) > 2 else 20, "2026-01-01"):
            print(b["t"], b["o"], b["h"], b["l"], b["c"], b["v"])
    elif cmd == "news":
        for n in news(args[0], int(args[1]) if len(args) > 1 else 10):
            print(n["created_at"], ",".join(n.get("symbols", [])), "|", n["headline"])
