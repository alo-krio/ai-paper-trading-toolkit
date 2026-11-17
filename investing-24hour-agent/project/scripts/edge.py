#!/usr/bin/env python3
"""v4.4 edge helpers (owner, Oct 28, 2026). Paper research only, never trades.
  edge.py im          SPY first-half-hour (9:30-10:00 ET) return -> UP / DOWN / FLAT for the 3:30 window; logs data/side/intraday_mom.csv
  edge.py im score    fill in yesterday's (and older) last-half-hour (3:30-4:00 ET) SPY return in the log
  edge.py cal         calendar flags: day before an FOMC decision, turn of month (last session + first 3 sessions)
  edge.py peers T..   sector peers of a leader that just reported: 1d/3d move, beta, next earnings (sympathy candidates)
"""
import csv, datetime as dt, os, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alpaca_data as A
ET = ZoneInfo("America/New_York")
IM_TH = 0.25   # % threshold for UP / DOWN
# FOMC decision days (second day of each meeting). Update yearly from federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
LOG = "data/side/intraday_mom.csv"

def day_bars(d):
    start = dt.datetime.combine(d, dt.time(9, 30), ET).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    try: raw = A.bars("SPY", "5Min", 100, start)
    except Exception: raw = []
    for b in raw:
        t = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET)
        if t.date() == d and dt.time(9, 30) <= t.time() < dt.time(16, 0): out.append((t.time(), b))
    out.sort(key=lambda x: x[0]); return out

def seg(bs, a, b):
    xs = [x for t, x in bs if a <= t < b]
    return round(100 * (xs[-1]["c"] / xs[0]["o"] - 1), 3) if xs else None

def im():
    d = dt.datetime.now(ET).date(); bs = day_bars(d)
    r = seg(bs, dt.time(9, 30), dt.time(10, 0))
    if r is None: print("IM n/a (no bars yet)"); return
    sig = "UP" if r >= IM_TH else "DOWN" if r <= -IM_TH else "FLAT"
    day = seg(bs, dt.time(9, 30), dt.time(15, 30))
    print(f"IM {sig} | SPY 9:30-10:00 {r:+.2f}% | 9:30-3:30 {day if day is not None else 0:+.2f}% | "
          + {"UP": "expect firm close: buy early (3:43-3:45)", "DOWN": "expect weak close: delay buys to ~3:55 for better prices",
             "FLAT": "no edge: normal 3:45"}[sig])
    os.makedirs("data/side", exist_ok=True); new = not os.path.exists(LOG)
    rows = list(csv.reader(open(LOG))) if not new else [["date", "first30", "signal", "to330", "last30"]]
    rows = [x for x in rows if x[0] != str(d)] + [[str(d), r, sig, day, ""]]
    csv.writer(open(LOG, "w", newline="")).writerows(rows)

def im_score():
    if not os.path.exists(LOG): print("no log"); return
    rows = list(csv.reader(open(LOG))); today = dt.datetime.now(ET).date(); n = 0
    for x in rows[1:]:
        if x[4] == "" and x[0] < str(today) or (x[0] == str(today) and dt.datetime.now(ET).time() > dt.time(16, 5) and x[4] == ""):
            v = seg(day_bars(dt.date.fromisoformat(x[0])), dt.time(15, 30), dt.time(16, 0))
            if v is not None: x[4] = v; n += 1
    csv.writer(open(LOG, "w", newline="")).writerows(rows)
    sc = [x for x in rows[1:] if x[4] not in ("", None) and x[2] != "FLAT"]
    hit = sum(1 for x in sc if (float(x[4]) > 0) == (x[2] == "UP"))
    print(f"scored {n} | signal days {len(sc)} | last-30 followed the signal {hit}/{len(sc)}")

def sessions(d0, k):
    d, out = d0, []
    while len(out) < k:
        d += dt.timedelta(days=1 if k > 0 else -1)
        if d.weekday() < 5: out.append(d)
    return out

def cal():
    d = dt.datetime.now(ET).date(); flags = []
    nxt = sessions(d, 1)[0]
    if str(nxt) in FOMC: flags.append(f"PRE-FOMC (decision {nxt}): historically firm day, tie-breaker toward staying fully invested")
    if str(d) in FOMC: flags.append("FOMC DECISION TODAY 2:00 PM ET: expect a volatile last 2 hours; let macro_check lead")
    if nxt.month != d.month: flags.append("LAST SESSION OF MONTH: turn-of-month window opens (tie-breaker toward buying)")
    if d in sessions(dt.date(d.year, d.month, 1) - dt.timedelta(days=1), 3):
        flags.append("FIRST 3 SESSIONS OF MONTH: turn-of-month inflows (tie-breaker toward staying invested)")
    print("CAL " + (" | ".join(flags) if flags else "no calendar edge today"))

def peers(leaders):
    import rotate as R
    sec = R.universe(); earn = R.earnings_ahead()
    for L in leaders:
        sc = sec.get(L)
        if not sc: print(f"{L}: not in universe"); continue
        names = [t for t, s in sec.items() if s == sc and t != L]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(16) as ex: rows = [r for r in ex.map(R.one, names) if r]
        lr = R.one(L) or {}
        rows = [r for r in rows if (r.get("beta") or 0) >= R.MIN_BETA and r["price"] > r["s200"]]
        rows.sort(key=lambda r: r["r1"])
        print(f"{L} ({sc}) 1d {lr.get('r1', 0):+.1f}% | lagging peers (beta >= {R.MIN_BETA}, above 200DMA), weakest 1d first:")
        for r in rows[:12]:
            e = earn.get(r["ticker"])
            print(f"  {r['ticker']:6} 1d {r['r1']:+.1f}% 3d {r['r3']:+.1f}% beta {r['beta']} rsi2 {r['rsi2']} earnings {e[0] + ' (' + str(e[1]) + ' sess)' if e else '-'}")

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "cal"
    if c == "im": im_score() if sys.argv[2:3] == ["score"] else im()
    elif c == "cal": cal()
    elif c == "peers": peers([t.upper() for t in sys.argv[2:]])
