#!/usr/bin/env python3
"""9:45 AM ET morning check (owner, Oct 22, 2026). PAPER ONLY. Run from project root.
  python3 scripts/morning.py check   -> news red-flag scan on the open basket (Mondays: 3-day window for weekend news), prints RED FLAG tickers
                                        (then run: python3 scripts/rotate.py exit T...)
  python3 scripts/morning.py gaps    -> TEST ONLY, never traded: S&P 500 names that reported last night after hours or this morning pre-market
                                        and are up >= 3% vs yesterday's close at ~9:45. Logged to shadow/gaps.csv at the 9:45 price.
  python3 scripts/morning.py score   -> fills same-day close and 5-session close for logged gaps, prints the test's averages"""
import csv, os, sys, subprocess, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "scripts")
import rotate, prices as P
GAP = 0.03; F = "shadow/gaps.csv"
HDR = ["date", "ticker", "when", "prev_close", "entry_945", "gap", "close_d0", "ret_d0", "close_d5", "ret_d5"]
def ensure_header():
    """Fix (Nov 13, 2026): rotate.append writes rows without a header, so a new/empty gaps.csv made score() read the
    first data row as the header -> KeyError 'ret_d5'. Write the header if the file is missing or headerless."""
    os.makedirs(os.path.dirname(F), exist_ok=True)
    if not os.path.exists(F) or os.path.getsize(F) == 0:
        with open(F, "w", newline="") as f: csv.writer(f).writerow(HDR)
        return
    with open(F, newline="") as f: rows = list(csv.reader(f))
    if rows and rows[0][:2] != HDR[:2]:
        with open(F, "w", newline="") as f: w = csv.writer(f); w.writerow(HDR); w.writerows(rows)
def check():
    s = rotate.load_state(); tks = [h["ticker"] for h in s["holdings"] if h["ticker"] not in ("SGOV", "SH")]
    if not tks: print("NO HOLDINGS"); return
    days = "3" if rotate.today().weekday() == 0 else "2"
    subprocess.run([sys.executable, "scripts/news_check.py", "--tag", "am", "--days", days] + tks, check=True)
    f = f"data/news/{rotate.today()}-am.csv"
    flags = [r["ticker"] for r in csv.DictReader(open(f)) if r["red_flag"] == "1"]
    print("RED FLAGS:", " ".join(flags) if flags else "none")
def universe():
    f = sorted(x for x in os.listdir("data/cands") if x.endswith(".csv")) if os.path.isdir("data/cands") else []
    import screen
    try: return set(screen.sp500()) if hasattr(screen, "sp500") else None
    except Exception: return None
def gaps():
    t0 = rotate.today(); prev = t0 - dt.timedelta(days=1)
    while prev.weekday() >= 5: prev -= dt.timedelta(days=1)
    rep = []
    for day, keep in ((prev, "time-after-hours"), (t0, "time-pre-market")):
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"]) or {}
        rep += [(r["symbol"].replace(".", "-"), keep) for r in ((d.get("data") or {}).get("rows") or []) if r.get("time") == keep]
    uni = universe()
    if uni: rep = [x for x in rep if x[0] in uni]
    done = {(r["date"], r["ticker"]) for r in csv.DictReader(open(F))}; n = 0
    for t, when in rep:
        if (str(t0), t) in done: continue
        try:
            b = [x for x in rotate.bars(t) if x[0] < str(t0)]; p, _ = rotate.live(t)
        except Exception: continue
        if not b or not p or b[-1][4] < 5: continue
        g = p / b[-1][4] - 1
        if g >= GAP:
            ensure_header(); rotate.append(F, [str(t0), t, when, b[-1][4], round(p, 4), round(g, 4), "", "", "", ""]); n += 1
            print(f"GAP {t} {100*g:+.1f}% ({when})")
    print(f"reported {len(rep)} | logged {n} gap-ups >= {100*GAP:.0f}%")
def score():
    ensure_header(); rs = list(csv.DictReader(open(F))); t0 = str(rotate.today())
    for r in rs:
        if r.get("ret_d5"): continue
        b = rotate.bars(r["ticker"]); ds = [x[0] for x in b]
        if r["date"] not in ds or r["date"] >= t0: continue
        i = ds.index(r["date"]); e = float(r["entry_945"])
        r["close_d0"] = b[i][4]; r["ret_d0"] = round(b[i][4] / e - 1, 5)
        if i + 5 < len(b) and b[i + 5][0] < t0: r["close_d5"] = b[i + 5][4]; r["ret_d5"] = round(b[i + 5][4] / e - 1, 5)
    if rs:  # never rewrite an empty file without its header (root cause of the ret_d5 KeyError)
        with open(F, "w", newline="") as f: w = csv.DictWriter(f, fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)
    d0 = [float(r["ret_d0"]) for r in rs if r.get("ret_d0")]; d5 = [float(r["ret_d5"]) for r in rs if r.get("ret_d5")]
    print(f"GAPS {len(rs)} logged | 9:45->close avg {100*sum(d0)/len(d0):+.2f}% (n={len(d0)})" if d0 else f"GAPS {len(rs)} logged | none scored yet",
          f"| 9:45->5 sessions avg {100*sum(d5)/len(d5):+.2f}% (n={len(d5)}, win {100*sum(x>0 for x in d5)/len(d5):.0f}%)" if d5 else "")
if __name__ == "__main__":
    {"check": check, "gaps": gaps, "score": score}[sys.argv[1]]()
