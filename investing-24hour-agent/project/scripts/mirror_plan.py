#!/usr/bin/env python3
"""Paper-mirror planner for the Alpaca CONNECTOR (Perplexity Teammate, Nov 13, 2026). Replaces alpaca_mirror.py's
network calls: the agent fetches positions with the Alpaca connector (isPaperAPI: true ALWAYS) and places the
orders this prints, then logs them. Same target logic as alpaca_mirror.py (book/state.json is the record).
Usage:
  mirror_plan.py plan data/alpaca_positions.json   -> prints one action per line: CLOSE T qty | BUY T qty | SELL T qty
  mirror_plan.py log T side qty status order_id [note]  -> appends to book/alpaca_orders.csv
positions JSON = the connector's list_positions result (list of objects with symbol, qty)."""
import csv, json, os, sys
from datetime import datetime, timezone
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); LOG = os.path.join(ROOT, "book", "alpaca_orders.csv")
def targets():
    s = json.load(open(os.path.join(ROOT, "book", "state.json"))); t = {}
    for h in s["holdings"]:
        t[h["ticker"]] = t.get(h["ticker"], 0) + h["shares"] * (1 if h.get("side", "long") == "long" else -1)
    return t
def load_pos(p):
    d = json.load(open(p))
    if isinstance(d, dict): d = d.get("result") or d.get("positions") or d.get("data") or []
    return {x["symbol"]: float(x["qty"]) for x in d if isinstance(x, dict) and "symbol" in x}
def plan(p):
    tgt, pos = targets(), load_pos(p); n = 0
    for t in sorted(set(tgt) | set(pos)):
        cur, want = pos.get(t, 0), tgt.get(t, 0); diff = round(want - cur, 6)
        if abs(diff) < 1e-4: continue
        if cur * want < 0: print(f"CLOSE {t} {cur}  # flatten before flip"); cur = 0; diff = round(want, 6)
        if want == 0 and cur != 0: print(f"CLOSE {t} {cur}"); n += 1; continue
        qty = abs(diff)
        if want < 0: qty = float(int(qty))  # shorts: whole shares only
        if qty <= 0: continue
        print(f"{'BUY' if diff > 0 else 'SELL'} {t} {round(qty, 6)}"); n += 1
    print(f"# {n} action(s); book {len(tgt)} names, alpaca {len(pos)} names")
def log(a):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["utc", "ticker", "side", "qty", "status", "order_id", "note"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds")] + a[:5] + [" ".join(a[5:]) or "via connector"])
if __name__ == "__main__":
    {"plan": lambda: plan(sys.argv[2]), "log": lambda: log(sys.argv[2:])}[sys.argv[1]]()
