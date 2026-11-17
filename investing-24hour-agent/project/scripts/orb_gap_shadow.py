#!/usr/bin/env python3
"""SILENT shadow test (owner, Nov 7, 2026; logging starts Nov 12, 2026, 20 sessions).
Never used for picks. For each morning gapper in shadow/gaps.csv on a date, compare:
  e945 = buy 9:45 open -> 15:30, e1000 = buy 10:00 -> 15:30 (current timing),
  orb = ORB-15: first 5-min close above the 9:30-9:45 high (9:45-11:30), stop range mid, 1R target, else 15:30.
Costs 0.10% round trip. Log: data/side/orb_gap.csv.
Usage: orb_gap_shadow.py log [YYYY-MM-DD]   (default today ET; run in evening window after 3:30)
       orb_gap_shadow.py summary
"""
import csv, json, os, sys, urllib.request, urllib.parse, statistics as st
from datetime import datetime
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York"); C = 0.001
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data/side/orb_gap.csv")
COLS = ["date", "ticker", "e945", "e1000", "orb", "orb_triggered"]

def bars(sym, day):
    q = dict(timeframe="5Min", start=f"{day}T12:00:00Z", end=f"{day}T22:00:00Z", feed="iex", limit=300)
    u = f"https://data.alpaca.markets/v2/stocks/{sym}/bars?" + urllib.parse.urlencode(q)
    b = json.load(urllib.request.urlopen(u, timeout=20)).get("bars") or []
    return [(datetime.fromisoformat(x["t"].replace("Z", "+00:00")).astimezone(ET).strftime("%H:%M"), x) for x in b]

def one(sym, day):
    bt = bars(sym, day); at = lambda hm: next((x for h, x in bt if h == hm), None)
    b945, b10, b1530 = at("09:45"), at("10:00"), at("15:30")
    if not (b945 and b10 and b1530): return None
    ex = b1530["o"]; rng = [x for h, x in bt if "09:30" <= h < "09:45"]
    hi = max(x["h"] for x in rng); mid = (hi + min(x["l"] for x in rng)) / 2
    orb = ""
    for i, (h, x) in enumerate(bt):
        if "09:45" <= h <= "11:30" and x["c"] > hi:
            e = x["c"]; tgt = e + (e - mid); out = ex
            for h2, y in bt[i + 1:]:
                if h2 >= "15:30": break
                if y["l"] <= mid: out = mid; break
                if y["h"] >= tgt: out = tgt; break
            orb = round((out / e - 1 - C) * 100, 3); break
    return dict(date=day, ticker=sym, e945=round((ex / b945["o"] - 1 - C) * 100, 3),
                e1000=round((ex / b10["o"] - 1 - C) * 100, 3), orb=orb, orb_triggered=int(orb != ""))

def log(day):
    done = set()
    if os.path.exists(OUT): done = {(r["date"], r["ticker"]) for r in csv.DictReader(open(OUT))}
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "shadow/gaps.csv"))) if r["date"] == day and (day, r["ticker"]) not in done]
    new = os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, COLS)
        if not new: w.writeheader()
        for r in rows:
            try: res = one(r["ticker"], day)
            except Exception as e: print("skip", r["ticker"], e); continue
            if res: w.writerow(res); print(res)
    print(f"logged {len(rows)} gapper(s) for {day}")

def summary():
    rs = list(csv.DictReader(open(OUT))) if os.path.exists(OUT) else []
    if not rs: return print("orb_gap: no rows yet")
    def s(v):
        v = [float(x) for x in v if x != ""]
        return f"n={len(v)} mean {st.mean(v):+.2f}% win {sum(x > 0 for x in v) / len(v):.0%}" if v else "n=0"
    days = len({r['date'] for r in rs})
    print(f"orb_gap ({days} sessions): 9:45 {s(r['e945'] for r in rs)} | 10:00 {s(r['e1000'] for r in rs)} | ORB-15 {s(r['orb'] for r in rs)} (skips count 0: {sum(float(r['orb'] or 0) for r in rs) / len(rs):+.2f}%/gapper)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "log": log(sys.argv[2] if len(sys.argv) > 2 else datetime.now(ET).strftime("%Y-%m-%d"))
    else: summary()
