"""Data gather for the pre-earnings run-up study (RESEARCH ONLY, GET requests only, never trades).
Writes into research/earnings_runup/data/:
  ndx.csv        current Nasdaq-100 constituents (api.nasdaq.com list-type/nasdaq100)
  cal_new.csv    Nasdaq earnings calendar rows for days after data/hist/earnings.csv ends (2026-10-28..today)
  bars.csv       Alpaca SIP daily bars (adjustment=all) for NDX + SPY + QQQ, 2025-03-01..yesterday
  news_times.csv first Benzinga earnings-release headline timestamp per (symbol, calendar date) -> BMO/AMC
"""
import os, sys, csv, json, re, subprocess, time, datetime as dt
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "backtest")); sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pull_history as PH, alpaca_data as A
D = os.path.join(HERE, "data"); os.makedirs(D, exist_ok=True)
ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TODAY = dt.date(2026, 11, 11)

def nasdaq(url):
    for k in range(3):
        r = subprocess.run(["curl", "-s", "-m", "25", "-A", UA, "-H", "Accept: application/json", url], capture_output=True, text=True).stdout
        try: return json.loads(r)
        except Exception: time.sleep(2 + 3 * k)
    return None

def ndx():
    d = nasdaq("https://api.nasdaq.com/api/quote/list-type/nasdaq100")
    rows = d["data"]["data"]["rows"]
    with open(os.path.join(D, "ndx.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["symbol", "name"])
        for r in rows: w.writerow([r["symbol"].replace(".", "-"), r["companyName"]])
    print("ndx", len(rows))

def cal_new():
    days = []; d0 = dt.date(2026, 10, 28)
    while d0 <= TODAY:
        if d0.weekday() < 5: days.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    with open(os.path.join(D, "cal_new.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "symbol", "eps", "eps_forecast", "surprise_pct", "time"])
        for d in days:
            j = nasdaq(f"https://api.nasdaq.com/api/calendar/earnings?date={d}") or {}
            for r in ((j.get("data") or {}).get("rows") or []):
                w.writerow([d, r["symbol"].replace(".", "-"), r.get("eps", ""), r.get("epsForecast", ""), r.get("surprise", ""), r.get("time", "")])
    print("cal_new days", len(days))

def bars():
    syms = [r["symbol"] for r in csv.DictReader(open(os.path.join(D, "ndx.csv")))] + ["SPY", "QQQ"]
    n = 0
    with open(os.path.join(D, "bars.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["symbol", "date", "o", "h", "l", "c", "v"])
        for i in range(0, len(syms), 50):
            for s, b in PH.bars(syms[i:i + 50], "1Day", "2025-03-01", end=f"{TODAY}T00:00:00Z"):
                w.writerow([s, b["t"][:10], b["o"], b["h"], b["l"], b["c"], b["v"]]); n += 1
    print("bars rows", n)

PAT = re.compile(r"(\bEPS\b|Earnings Per Share|Reports? (Q[1-4]|(First|Second|Third|Fourth)[- ]Quarter|Fiscal)|Q[1-4] (Revenue|Sales))", re.I)
STRONG = re.compile(r"\b(Q[1-4]|FY)\b.{0,40}\b(EPS|Loss|Sales|Revenue)\b.{0,60}(Beat|Miss|Estimate|In[- ]Line|\$)", re.I)
NOT = re.compile(r"(Last Quarter|Repeat|Sees|Guidance|Raises|Lowers|Reaffirms|Preview|Expectations|Ahead Of|Scheduled|What To Expect|Prediction|Options|Estimate[s]? For|Earnings Call|Transcript|Whisper|Recap|Unusual)", re.I)

def news_one(sym, day):
    d = dt.date.fromisoformat(day)
    a = dt.datetime.combine(d - dt.timedelta(days=4), dt.time(12), ET).astimezone(dt.timezone.utc)
    b = dt.datetime.combine(d + dt.timedelta(days=2), dt.time(12), ET).astimezone(dt.timezone.utc)
    best = None; tok = None
    for _ in range(4):
        q = dict(symbols=sym.replace("-", "."), start=a.strftime("%Y-%m-%dT%H:%M:%SZ"), end=b.strftime("%Y-%m-%dT%H:%M:%SZ"), limit=50, sort="asc")
        if tok: q["page_token"] = tok
        for k in range(3):
            try: j = A.get("/v1beta1/news", **q); break
            except Exception: time.sleep(2 + 2 * k)
        else: return sym, day, "", "fetch_failed"
        for n in j.get("news", []):
            h = n["headline"]
            # must name only this company (or few) and look like a results headline
            if PAT.search(h) and not NOT.search(h) and len(n.get("symbols", [])) <= 3:
                t = dt.datetime.fromisoformat(n["created_at"].replace("Z", "+00:00")).astimezone(ET)
                key = (0 if STRONG.search(h) else 1, abs((t.date() - d).days), t)   # strong results headline, nearest the calendar date, earliest
                if best is None or key < best[2]: best = (t, h, key)
        tok = j.get("next_page_token")
        if not tok: break
    if not best: return sym, day, "", "no_headline"
    return sym, day, best[0].isoformat(), best[1][:140]

def news(events_csv):
    ev = [(r["symbol"], r["date"]) for r in csv.DictReader(open(events_csv))]
    out = os.path.join(D, "news_times_" + os.path.basename(events_csv))
    with ThreadPoolExecutor(4) as ex, open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["symbol", "cal_date", "release_et", "headline"])
        for r in ex.map(lambda x: news_one(*x), ev): w.writerow(r)
    print("news events", len(ev))

if __name__ == "__main__":
    {"ndx": ndx, "cal": cal_new, "bars": bars, "news": lambda: news(sys.argv[2])}[sys.argv[1]]()
