#!/usr/bin/env python3
"""Mirror book/state.json into the Alpaca PAPER account. Fake money only.
Our own ledger (book/) stays the record; Alpaca is a realistic-fill mirror + dashboard.
Auth is injected on the wire for paper-api.alpaca.markets. Hard-wired to the PAPER host.
Usage:
  alpaca_mirror.py status          account equity + positions vs our book
  alpaca_mirror.py sync            market orders so Alpaca holds the same shares as our book
                                   (only while the market is open; logs book/alpaca_orders.csv)
"""
import csv, json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
BASE = "https://paper-api.alpaca.markets"
assert "paper-api" in BASE  # never point this at a live account
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "book", "alpaca_orders.csv")

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json", "APCA-API-KEY-ID": __import__("os").environ["APCA_API_KEY_ID"], "APCA-API-SECRET-KEY": __import__("os").environ["APCA_API_SECRET_KEY"]})
    try:
        with urllib.request.urlopen(r, timeout=20) as f:
            t = f.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "message": e.read().decode()[:300]}

def book_targets():
    s = json.load(open(os.path.join(ROOT, "book", "state.json")))
    tgt = {}
    for h in s["holdings"]:
        q = h["shares"] * (1 if h.get("side", "long") == "long" else -1)
        tgt[h["ticker"]] = tgt.get(h["ticker"], 0) + q
    return tgt

def positions():
    return {p["symbol"]: float(p["qty"]) for p in req("GET", "/v2/positions") if isinstance(p, dict) and "symbol" in p}

def log(row):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["utc", "ticker", "side", "qty", "status", "order_id", "note"])
        w.writerow(row)

def status():
    a = req("GET", "/v2/account"); tgt = book_targets(); pos = positions()
    print(f"alpaca paper equity {a.get('equity')} cash {a.get('cash')} (account starts at $100k; mirror holds book-sized positions)")
    for t in sorted(set(tgt) | set(pos)):
        print(f"{t:6s} book {tgt.get(t, 0):10.4f}  alpaca {pos.get(t, 0):10.4f}")

def sync():
    clk = req("GET", "/v2/clock")
    if not clk.get("is_open"): print("market closed: no mirror orders"); return
    tgt = book_targets(); pos = positions(); now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for t in sorted(set(tgt) | set(pos)):
        diff = round(tgt.get(t, 0) - pos.get(t, 0), 6)
        if abs(diff) < 1e-4: continue
        cur, want = pos.get(t, 0), tgt.get(t, 0)
        if cur * want < 0:  # crossing zero: flatten first
            o = req("DELETE", f"/v2/positions/{t}"); log([now, t, "close", cur, o.get("status", o.get("error")), o.get("id", ""), "flatten before flip"])
            time.sleep(1); cur = 0; diff = round(want, 6)
        if want == 0 and cur != 0:
            o = req("DELETE", f"/v2/positions/{t}"); log([now, t, "close", cur, o.get("status", o.get("error")), o.get("id", ""), o.get("message", "")])
            print(f"CLOSE {t} {cur} -> {o.get('status', o)}"); continue
        side = "buy" if diff > 0 else "sell"; qty = abs(diff)
        if want < 0: qty = float(int(qty)) or 0  # Alpaca: shorts in whole shares only
        if qty <= 0: continue
        o = req("POST", "/v2/orders", dict(symbol=t, qty=str(round(qty, 6)), side=side, type="market", time_in_force="day"))
        log([now, t, side, qty, o.get("status", o.get("error")), o.get("id", ""), o.get("message", "")])
        print(f"{side.upper()} {t} {qty} -> {o.get('status', o)}")

if __name__ == "__main__":
    {"status": status, "sync": sync}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
