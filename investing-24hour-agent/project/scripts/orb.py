#!/usr/bin/env python3
"""SILENT test (never traded; the owner, Oct 22, 2026): the "first 5-minute candle vs 12 EMA" Nasdaq idea from his reel, simplified.
Rule: the 9:30-9:35 ET QQQ 5-min candle closes above the 12-period EMA of 5-min closes -> long, below -> short.
Entry at that candle's close (9:35). Exit at the 3:30 PM bar close (our evening window) and, separately, the 3:55 bar close.
No trailing stop (our book can't trail minute by minute). Cost 0.05% per side. Data: Yahoo 5-min chart (query1; 60 days max).
  python3 scripts/orb.py log       -> today's signal (run after 9:35 ET) and score any finished days
  python3 scripts/orb.py backfill  -> rebuild history from the last ~60 sessions
  python3 scripts/orb.py summary   -> one line for the scoreboard
File: data/side/orb.csv (date,signal,entry,ema12,exit_330,ret_330,exit_close,ret_close,qqq_day)."""
import csv, json, os, sys, subprocess, datetime as dt
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
ET = ZoneInfo("America/New_York"); COST = 0.0005; F = "data/side/orb.csv"
COLS = ["date", "signal", "entry", "ema12", "exit_330", "ret_330", "exit_close", "ret_close", "qqq_day"]

def bars(rng="60d"):
    for h in ("query1", "query2"):
        r = subprocess.run(["curl", "-s", "-m", "25", "-A", "Mozilla/5.0", f"https://{h}.finance.yahoo.com/v8/finance/chart/QQQ?interval=5m&range={rng}"], capture_output=True)
        try:
            res = json.loads(r.stdout)["chart"]["result"][0]; q = res["indicators"]["quote"][0]; out = []
            for ts, o, c in zip(res["timestamp"], q["open"], q["close"]):
                t = dt.datetime.fromtimestamp(ts, ET)
                if c is not None and dt.time(9, 30) <= t.time() < dt.time(16, 0): out.append((t, o, c))
            if out: return out
        except Exception: continue
    sys.exit("no 5-min data")

def days(b):
    """Per session: signal from the 9:30 bar vs EMA12 (EMA runs over regular-hours 5-min closes, carried across days)."""
    ema = None; k = 2 / 13; out = {}
    for t, o, c in b:
        ema = c if ema is None else c * k + ema * (1 - k)
        d = str(t.date()); r = out.setdefault(d, {"date": d})
        if t.time() == dt.time(9, 30):
            r.update(signal="long" if c > ema else "short", entry=round(c, 4), ema12=round(ema, 4), open=o)
        if t.time() == dt.time(15, 25): r["exit_330"] = round(c, 4)   # bar 3:25-3:30 closes at 3:30
        if t.time() == dt.time(15, 55): r["exit_close"] = round(c, 4)
    for r in out.values():
        if "entry" not in r: continue
        s = 1 if r["signal"] == "long" else -1
        for k_ in ("330", "close"):
            x = r.get("exit_" + k_)
            if x: r["ret_" + k_] = round(s * (x / r["entry"] - 1) - 2 * COST, 5)
        if r.get("exit_close"): r["qqq_day"] = round(r["exit_close"] / r["open"] - 1, 5)
    return {d: r for d, r in out.items() if "entry" in r}

def save(rows):
    os.makedirs(os.path.dirname(F), exist_ok=True); old = {}
    if os.path.exists(F): old = {r["date"]: r for r in csv.DictReader(open(F))}
    old.update({d: {c: r.get(c, "") for c in COLS} for d, r in rows.items()})
    with open(F, "w", newline="") as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); [w.writerow(old[d]) for d in sorted(old)]

def summary():
    if not os.path.exists(F): print("ORB test: no data"); return
    rr = [r for r in csv.DictReader(open(F)) if r["ret_330"]]
    if not rr: print("ORB test: no scored days"); return
    for k in ("ret_330", "ret_close"):
        x = [float(r[k]) for r in rr if r[k]]; g = sum(v for v in x if v > 0); l = -sum(v for v in x if v < 0)
        cum = 1
        for v in x: cum *= 1 + v
        print(f"ORB {k[4:]}: {len(x)} days | win {100*sum(v>0 for v in x)/len(x):.0f}% | avg {100*sum(x)/len(x):+.3f}%/day net | PF {g/l if l else float('inf'):.2f} | cum {100*(cum-1):+.1f}% (unlevered QQQ, net 0.1%/day)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd in ("log", "backfill"):
        rows = days(bars("60d" if cmd == "backfill" else "5d")); save(rows)
        t = str(dt.datetime.now(ET).date())
        if t in rows: print("TODAY", {k: rows[t].get(k) for k in COLS})
        summary()
    else: summary()
