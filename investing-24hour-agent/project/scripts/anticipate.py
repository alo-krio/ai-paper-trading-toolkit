#!/usr/bin/env python3
"""ANTICIPATION ENGINE for the Main 24h PAPER book (owner, Nov 16, 2026). PAPER ONLY: never trades, never touches a broker.

Owner: "to be a great trader we need to anticipate events and outcomes ... understand the probability of each outcome and
then make bets based on that ... find arbitrage opportunities where things haven't been priced in by the market."

Run from project/ via the platform wrapper (Alpaca market data needs it):
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py calendar [--sessions 5]   events in the next 1-5 sessions
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py odds                      Polymarket odds for them (+ daily snapshot)
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py edge [--sa N]             ANTICIPATION SHEET (md + csv); N = max paid
                                                                                          stockanalysis history pulls (5 cr each, cached 30d)
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py sheet                     calendar + odds + edge in one go (the window job)
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py log [--slug S --p 0.7 --decision "..." --note "..."]
                                                                                          forecast ledger (auto from today's sheet if no --slug)
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py score                     resolve ledger rows (closed Polymarket markets +
                                                                                          post-event stock reaction), Brier ours vs Polymarket
  sh /home/user/workspace/_platform/py.sh scripts/anticipate.py backtest [--pages 30]     closed Polymarket earnings markets vs reactions

Sources: Polymarket through Firecrawl Alexandria (alex.sh, free); Polymarket CLOB public prices-history (free, read-only,
not in Alexandria) for odds paths; Nasdaq earnings/IPO calendars + earnings-surprise (free); forexfactory calendar and CME
FedWatch via Alexandria (5 credits each, cached per day); stockanalysis earnings history via Alexandria (5 credits, cached
30 days); Alpaca SIP daily bars + indicative option snapshots (data only); market-brain desks + ripple graph.
Data integrity: failed or partial data is UNKNOWN, never evidence; every gap prints a DATA WARNING line.
"""
import os, sys, re, json, csv, math, time, hashlib, subprocess, statistics as st, datetime as dt, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
ET = ZoneInfo("America/New_York")
D = os.path.join(ROOT, "data", "anticipate"); CACHE = os.path.join(D, "cache"); BARS = os.path.join(D, "bars")
for p in (D, CACHE, BARS, os.path.join(D, "sheets"), os.path.join(D, "backtest")): os.makedirs(p, exist_ok=True)
ALEX = "/home/user/workspace/_platform/alex.sh"
BRAIN = "/home/user/workspace/market-brain"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
WARN = []
SNAP = os.path.join(D, "polymarket_snapshots.csv"); LEDGER = os.path.join(D, "forecasts.csv"); CREDITS = os.path.join(D, "credits.csv")
HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
            "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}
FOMC = ["2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-11-17"]  # decision days (FedWatch list Nov 16)
SECTOR_ETF = {"Technology": "XLK", "Finance": "XLF", "Energy": "XLE", "Health Care": "XLV", "Consumer Discretionary": "XLY",
              "Consumer Staples": "XLP", "Industrials": "XLI", "Basic Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE",
              "Telecommunications": "XLC"}
SEMIS = {"NVDA", "AMD", "AVGO", "MU", "TSM", "AMAT", "LRCX", "KLAC", "ASML", "MRVL", "ARM", "INTC", "QCOM", "TXN", "ADI", "ON", "MCHP"}
# Polymarket topic map: keyword search -> linked tickers (macro channels). Brain desks add their own keywords + watch lists.
TOPICS = {
    "Fed decision December": ["TLT", "XLF", "KRE", "IWM", "XHB", "QQQ"],
    "CPI": ["TLT", "QQQ", "IWM", "XHB"], "inflation US": ["TLT", "QQQ"], "jobs report": ["TLT", "IWM", "XLF"],
    "unemployment rate": ["TLT", "IWM"], "recession": ["SPY", "IWM", "XLY"], "government shutdown": ["LMT", "RTX", "NOC", "KTOS", "AVAV"],
    "tariffs": ["XLI", "XLY", "AAPL", "CAT", "DE"], "OPEC": ["XLE", "USO", "XOM", "CVX", "COP"], "oil price": ["XLE", "USO", "XOM", "DAL"],
    "Iran": ["XLE", "USO", "LMT", "RTX", "DAL"], "Anthropic IPO": ["AMZN", "GOOGL", "MSFT", "AVGO", "NVDA"],
    "IPO": ["IPO"], "Nvidia": ["NVDA", "TSM", "MU", "AVGO", "AMD", "SMH"], "Bitcoin price": ["IBIT", "COIN", "MSTR"],
    "China": ["KWEB", "FXI", "NVDA", "AAPL"], "S&P 500": ["SPY"], "Treasury yields": ["TLT"],
}
FIN_TAGS = ["economy", "fed-rates", "tariffs", "equities", "ipos", "finance", "geopolitics"]

def warn(msg):
    if msg not in WARN: WARN.append(msg); print("DATA WARNING:", msg)

def now(): return dt.datetime.now(ET)
def today(): return now().date()
def iso(d): return d.isoformat() if hasattr(d, "isoformat") else str(d)
def fnum(x, default=None):
    try:
        if x is None or x == "": return default
        return float(str(x).replace("$", "").replace(",", "").replace("%", ""))
    except Exception: return default
def pct(x, nd=1): return "UNKNOWN" if x is None else f"{x*100:+.{nd}f}%"
def pp(x): return "UNKNOWN" if x is None else f"{x*100:.0f}%"

def is_session(d): return d.weekday() < 5 and iso(d) not in HOLIDAYS
def next_sessions(n, start=None):
    d, out = start or today(), []
    while len(out) < n:
        d += dt.timedelta(days=1)
        if is_session(d): out.append(d)
    return out
def prev_session(d):
    d -= dt.timedelta(days=1)
    while not is_session(d): d -= dt.timedelta(days=1)
    return d

# ---------------------------------------------------------------- HTTP / Alexandria
def http_json(url, headers=None, tries=3, timeout=25):
    h = {"User-Agent": UA, "Accept": "application/json"}; h.update(headers or {})
    for i in range(tries):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout).read())
        except Exception as e: err = e; time.sleep(1.2 * (i + 1))
    return None

def nasdaq(url): return http_json(url)

def alex(provider, cap, opts, ttl_h=6, tag=""):
    """Firecrawl Alexandria via alex.sh, cached on disk. Returns the data payload or None (with a DATA WARNING)."""
    key = hashlib.md5(json.dumps([provider, cap, opts], sort_keys=True).encode()).hexdigest()[:16]
    f = os.path.join(CACHE, f"{provider}__{cap.replace('/', '_')}__{key}.json")
    if os.path.exists(f) and time.time() - os.path.getmtime(f) < ttl_h * 3600:
        try: return json.load(open(f))
        except Exception: pass
    out = f + ".raw"
    for attempt in range(5):
        _throttle()
        r = subprocess.run(["sh", ALEX, provider, cap, json.dumps(opts), out], capture_output=True, text=True, timeout=150)
        m = re.search(r"credits:\s*([\d.]+|None|\?)", r.stderr or "")
        cr = m.group(1) if m else "?"
        with open(CREDITS, "a", newline="") as fh: csv.writer(fh).writerow([now().isoformat(timespec="seconds"), provider, cap, cr, tag])
        try:
            j = json.load(open(out)); a = (j.get("data") or {}).get("alexandria") or []
            if a and not a[0].get("error") and "data" in a[0]:
                json.dump(a[0]["data"], open(f, "w")); os.remove(out); return a[0]["data"]
            err = (a[0].get("error") if a else j.get("error"))
        except Exception as e: err = e
        if "rate limit" in str(err).lower(): time.sleep(25); continue   # Firecrawl ~12 req/min: wait, retry (no credits charged)
        if provider != "polymarket" or attempt >= 1: break   # never retry a paid call on a real error
        time.sleep(2)
    warn(f"Alexandria {provider}/{cap} {json.dumps(opts)[:90]} failed: {str(err)[:120]}")
    return None

RL = os.path.join(CACHE, ".ratelimit")
def _throttle(per_min=10):
    """Firecrawl allows ~12 requests/min per team (shared with other agents): keep this script under ~10/min."""
    while True:
        try: ts = [float(x) for x in open(RL).read().split()] if os.path.exists(RL) else []
        except Exception: ts = []
        ts = [t for t in ts if time.time() - t < 60]
        if len(ts) < per_min:
            open(RL, "w").write(" ".join(str(t) for t in ts + [time.time()])); return
        time.sleep(max(1.0, 60 - (time.time() - min(ts)) + 0.5))

def credits_used_today():
    tot = 0.0
    if os.path.exists(CREDITS):
        for r in csv.reader(open(CREDITS)):
            if r and r[0][:10] == iso(today()): tot += fnum(r[3], 0) or 0
    return tot

# ---------------------------------------------------------------- bars (Alpaca SIP daily, cached)
def _alpaca(path, q):
    k, s = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not k: return None
    return http_json("https://data.alpaca.markets" + path + "?" + urllib.parse.urlencode(q),
                     {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}, tries=2, timeout=40)

def _bars_fetch(syms, start):
    out = {s: [] for s in syms}; tok = None
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for _ in range(40):
        q = {"symbols": ",".join(syms), "timeframe": "1Day", "start": start, "end": end, "limit": 10000, "adjustment": "all", "feed": "sip"}
        if tok: q["page_token"] = tok
        d = _alpaca("/v2/stocks/bars", q)
        if d is None: return None
        for s, bl in (d.get("bars") or {}).items():
            for b in bl:
                day = dt.datetime.fromisoformat(b["t"][:19]).replace(tzinfo=dt.timezone.utc).astimezone(ET).date().isoformat()
                out.setdefault(s, []).append([day, b["o"], b["h"], b["l"], b["c"], b["v"]])
        tok = d.get("next_page_token")
        if not tok: break
    return out

_BC = {}
def bars(tickers, start="2023-06-01"):
    """{ticker: [[date,o,h,l,c,v],...]} oldest first. Disk cache refreshed when it lacks the last completed session."""
    if not os.environ.get("APCA_API_KEY_ID"):
        warn("no Alpaca data credentials (run via _platform/py.sh): price history UNKNOWN"); return {}
    st_ = now(); last_done = today() if (st_.hour, st_.minute) >= (16, 20) and is_session(today()) else prev_session(today())
    need, res = [], {}
    for t in set(tickers):
        if t in _BC: res[t] = _BC[t]; continue
        f = os.path.join(BARS, t.replace("/", "_") + ".json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("start", "9") <= start and (j.get("rows") and j["rows"][-1][0] >= iso(last_done) or j.get("checked") == iso(today())):
                res[t] = _BC[t] = j["rows"]; continue
        need.append(t)
    for i in range(0, len(need), 50):
        chunk = [t.replace("-", ".") for t in need[i:i + 50]]
        got = _bars_fetch(chunk, start)
        if got is None: warn(f"Alpaca bars failed for {len(chunk)} symbols (e.g. {chunk[:3]})"); continue
        for s in chunk:
            t = s.replace(".", "-") if s.replace(".", "-") in need else s
            rows = sorted({r[0]: r for r in got.get(s, [])}.values())
            json.dump({"start": start, "checked": iso(today()), "rows": rows}, open(os.path.join(BARS, t.replace("/", "_") + ".json"), "w"))
            res[t] = _BC[t] = rows
    return res

def idx(rows): return {r[0]: i for i, r in enumerate(rows)}
def close_on_or_before(rows, day):
    best = None
    for r in rows:
        if r[0] <= day: best = r
        else: break
    return best
def ret_window(rows, d0, d1, kind="cc"):
    """close(d0) -> close(d1) (cc) or close(d0) -> open(d1) (gap). None if a day is missing."""
    I = idx(rows)
    if d0 not in I or d1 not in I: return None
    a = rows[I[d0]][4]; b = rows[I[d1]][4] if kind == "cc" else rows[I[d1]][1]
    return b / a - 1 if a else None
def trading_days(rows): return [r[0] for r in rows]
def next_td(days, d):
    for x in days:
        if x > d: return x
    return None
def prev_td(days, d):
    p = None
    for x in days:
        if x >= d: return p
        p = x
    return p
def atr_pct(rows, n=14):
    if len(rows) < n + 2: return None
    tr = [max(r[2], p[4]) - min(r[3], p[4]) for p, r in zip(rows[-n - 1:-1], rows[-n:])]
    return sum(tr) / n / rows[-1][4]

# ---------------------------------------------------------------- calendar
def nasdaq_earnings(day):
    d = nasdaq(f"https://api.nasdaq.com/api/calendar/earnings?date={day}")
    if d is None: warn(f"Nasdaq earnings calendar {day} unavailable: reporters UNKNOWN"); return None
    out = []
    for r in ((d.get("data") or {}).get("rows") or []):
        tm = {"time-pre-market": "BMO", "time-after-hours": "AMC"}.get(r.get("time"), "TNS")
        out.append({"ticker": r["symbol"].replace(".", "-"), "name": r.get("name", ""), "date": iso(day), "time": tm,
                    "eps_cons": fnum(r.get("epsForecast")), "n_est": fnum(r.get("noOfEsts")), "mcap": fnum(r.get("marketCap"), 0) or 0,
                    "last_year_eps": fnum(r.get("lastYearEPS")), "fq": r.get("fiscalQuarterEnding", "")})
    return out

def forexfactory(days):
    out, weeks = [], sorted({d - dt.timedelta(days=d.weekday()) for d in [today()] + days})
    for w in weeks:
        x = alex("forexfactory-com", "economic-calendar/list_events",
                 {"currencies": ["USD"], "date": iso(w if w >= today() else today()), "impacts": ["high", "medium"], "view": "week"},
                 ttl_h=20, tag="calendar")
        if x is None: warn(f"forexfactory week of {w}: macro releases UNKNOWN"); continue
        for e in x.get("events") or []:
            t = dt.datetime.fromisoformat(e["datetime_utc"].replace("Z", "+00:00")).astimezone(ET) if e.get("datetime_utc") else None
            out.append({"date": t.date().isoformat() if t else e.get("date"), "time": t.strftime("%H:%M ET") if t else "?",
                        "name": e.get("name"), "impact": e.get("impact"), "forecast": e.get("forecast"), "previous": e.get("previous"),
                        "actual": e.get("actual")})
    seen, res = set(), []
    for e in out:
        k = (e["date"], e["name"])
        if k not in seen: seen.add(k); res.append(e)
    return res

def ipos():
    m = today().strftime("%Y-%m"); d = nasdaq(f"https://api.nasdaq.com/api/ipo/calendar?date={m}")
    if d is None: warn("Nasdaq IPO calendar unavailable"); return []
    out = []
    for sect in ("upcoming", "priced"):
        blk = (d.get("data") or {}).get(sect) or {}
        rows = blk.get("upcomingTable", {}).get("rows") if sect == "upcoming" else blk.get("rows")
        for r in rows or []:
            out.append({"status": sect, "ticker": r.get("proposedTickerSymbol"), "name": r.get("companyName"),
                        "date": r.get("expectedPriceDate") or r.get("pricedDate"), "price": r.get("proposedSharePrice"),
                        "amount": r.get("dollarValueOfSharesOffered")})
    return out

def desks():
    try: d = json.load(open(os.path.join(BRAIN, "desks.json")))["desks"]
    except Exception as e: warn(f"brain desks unavailable: {e}"); return []
    return [x for x in d.values() if x.get("status") == "active" and x.get("kind") in ("event", "theme")]

def cmd_calendar(n=5, quiet=False):
    days = next_sessions(n); cal = {"built": now().isoformat(timespec="seconds"), "sessions": [iso(d) for d in days]}
    # earnings: the rest of today (AMC) + next n sessions
    earn = []
    for d in ([today()] if is_session(today()) else []) + days:
        rows = nasdaq_earnings(d)
        if rows is None: continue
        if d == today(): rows = [r for r in rows if r["time"] != "BMO"]
        earn += rows
    cal["earnings"] = earn
    cal["macro"] = forexfactory(days)
    cal["fomc"] = [x for x in FOMC if x >= iso(today())][:2]
    cal["ipos"] = ipos()
    cal["desks"] = [{"slug": x["slug"], "title": x["title"], "kind": x["kind"], "expires": x.get("expires"), "watch": x.get("watch", []),
                     "keywords": x.get("keywords", [])} for x in desks()]
    json.dump(cal, open(os.path.join(D, f"calendar_{today()}.json"), "w"), indent=1)
    if not quiet:
        print(f"CALENDAR {today()} -> next {n} sessions {cal['sessions'][0]}..{cal['sessions'][-1]}")
        big = [e for e in earn if e["mcap"] >= 10e9]
        print(f"  EARNINGS: {len(earn)} reporters ({len(big)} >= $10B):")
        for e in sorted(big, key=lambda e: (e["date"], -e["mcap"]))[:40]:
            print(f"    {e['date']} {e['time']} {e['ticker']:6s} ${e['mcap']/1e9:,.0f}B cons EPS {e['eps_cons']} ({e['n_est'] or '?'} est)")
        print("  MACRO (forexfactory, ET):")
        for m in cal["macro"]: print(f"    {m['date']} {m['time']} [{m['impact']}] {m['name']} f/c {m['forecast']} prev {m['previous']}")
        print("  FOMC decision days:", ", ".join(cal["fomc"]))
        print("  IPOs:", "; ".join(f"{i['ticker']} {i['status']} {i['date']} {i['price']}" for i in cal["ipos"][:10]) or "none listed")
        print("  BRAIN EVENT/THEME DESKS:")
        for x in cal["desks"]: print(f"    {x['slug']}: {x['title']} (expires {x['expires']}) watch {','.join(x['watch'][:6])}")
    return cal

def load_calendar(n=5):
    f = os.path.join(D, f"calendar_{today()}.json")
    if os.path.exists(f) and time.time() - os.path.getmtime(f) < 4 * 3600: return json.load(open(f))
    return cmd_calendar(n, quiet=True)

# ---------------------------------------------------------------- Polymarket
def pm_list(opts, pages=1):
    out = []
    for p in range(pages):
        o = dict(opts); o["offset"] = p * o.get("limit", 100)
        x = alex("polymarket", "events/list", o, ttl_h=0.5 if not o.get("closed") else 12, tag="odds")
        if not x: break
        out += x
        if len(x) < o.get("limit", 100): break
    return out
def pm_search(q, n=10, status="active"):
    x = alex("polymarket", "search/query", {"q": q, "limit_per_type": n, "events_status": status}, ttl_h=0.5, tag="odds")
    return (x or {}).get("events") or []
def jl(s, default=None):
    try: return json.loads(s) if isinstance(s, str) else (s if s is not None else default)
    except Exception: return default
def ticker_of(title):
    m = re.search(r"\(([A-Z][A-Z0-9.\-]{0,6})\)", title or "")
    return m.group(1).replace(".", "-") if m else None
def strike_of(slug):
    m = re.search(r"eps-\d\d-\d\d-\d{4}-(neg)?(\d+)(?:pt(\d+))?$", slug or "")
    if not m: return None
    v = float(m.group(2) + ("." + m.group(3) if m.group(3) else "")); return -v if m.group(1) else v
def market_rows(e, category, linked):
    rows = []
    for m in e.get("markets") or []:
        if m.get("closed") and not e.get("closed"): continue
        oc, pr = jl(m.get("outcomes"), []), [fnum(x) for x in jl(m.get("outcomePrices"), [])]
        if not pr: continue
        yes = pr[0] if oc and oc[0] == "Yes" else None
        rows.append({"event_slug": e.get("slug"), "event_title": e.get("title"), "market_slug": m.get("slug"),
                     "label": m.get("groupItemTitle") or (m.get("question") if len(e.get("markets") or []) > 1 else "Yes"),
                     "question": m.get("question"), "yes": yes if yes is not None else pr[0], "outcomes": oc, "prices": pr,
                     "bid": fnum(m.get("bestBid")), "ask": fnum(m.get("bestAsk")), "last": fnum(m.get("lastTradePrice")),
                     "chg1d": fnum(m.get("oneDayPriceChange")), "chg1w": fnum(m.get("oneWeekPriceChange")),
                     "volume": fnum(m.get("volume"), 0), "vol24": fnum(m.get("volume24hr"), 0), "liq": fnum(m.get("liquidity"), 0),
                     "end": (m.get("endDate") or e.get("endDate") or "")[:16], "closed": bool(m.get("closed")),
                     "token": (jl(m.get("clobTokenIds"), []) or [None])[0], "category": category, "linked": linked,
                     "start": (m.get("startDate") or "")[:19]})
    return rows

def cmd_odds(quiet=False):
    cal = load_calendar(); rows = []
    # 1. per-company earnings-beat markets
    earn_ev = pm_list({"active": True, "closed": False, "limit": 100, "tag_slug": "earnings", "order": "endDate", "ascending": True}, pages=3)
    if not earn_ev: warn("Polymarket earnings markets unavailable: earnings odds UNKNOWN")
    ecal = {e["ticker"]: e for e in cal.get("earnings", [])}
    for e in earn_ev:
        t = ticker_of(e.get("title"))
        if not t or "beat" not in (e.get("title") or "").lower(): continue
        for r in market_rows(e, "earnings", [t]):
            r["ticker"] = t; r["strike"] = strike_of(e.get("slug")); r["cal"] = ecal.get(t)
            rows.append(r)
    # 2. macro / policy / company topics: curated keywords + brain desks + calendar macro names + big reporters
    queries = dict(TOPICS)
    for x in cal.get("desks", []):
        q = re.sub(r"\(.*?\)", "", x["title"]).split(":")[0].strip()
        queries.setdefault(q, x["watch"][:6])
    for m in cal.get("macro", []):
        n_ = (m["name"] or "").lower()
        for k, q in (("cpi", "CPI"), ("non-farm", "jobs report"), ("unemployment rate", "unemployment rate"), ("fomc", "Fed decision December"),
                     ("gdp", "GDP"), ("retail sales", "retail sales"), ("pce", "PCE inflation")):
            if k in n_: queries.setdefault(q, ["TLT", "IWM", "QQQ"])
    for e in sorted(cal.get("earnings", []), key=lambda e: -e["mcap"])[:6]:
        nm = re.sub(r"\b(Inc|Corporation|Corp|Company|Co|Ltd|Holdings|plc|N\.V\.)\b\.?,?", "", e["name"]).strip()
        if nm: queries.setdefault(nm.split()[0], [e["ticker"]])
    seen = {r["market_slug"] for r in rows}
    horizon = (today() + dt.timedelta(days=75)).isoformat()
    def add(e, cat, linked):
        if (e.get("endDate") or "9999")[:10] > horizon and (e.get("volume24hr") or 0) < 20000: return
        for r in market_rows(e, cat, linked):
            if r["market_slug"] in seen: continue
            if not relevant(r, cat): continue
            seen.add(r["market_slug"]); r["ticker"] = None; r["strike"] = None; r["cal"] = None; r["query"] = cat; rows.append(r)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda q: (q, pm_search(q, 8)), queries))
    for q, evs in res:
        for e in evs[:6]:
            if "earnings" in (e.get("slug") or "") and "beat" in (e.get("title") or "").lower(): continue
            add(e, "topic:" + q, queries[q])
    for tg in FIN_TAGS:
        for e in pm_list({"active": True, "closed": False, "limit": 25, "tag_slug": tg, "order": "volume24hr", "ascending": False}):
            if "beat quarterly earnings" in (e.get("title") or ""): continue
            add(e, "tag:" + tg, [])
    # snapshot
    ts = now().isoformat(timespec="minutes"); new = not os.path.exists(SNAP)
    with open(SNAP, "a", newline="") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["ts", "date", "category", "event_slug", "market_slug", "event_title", "label", "yes", "bid", "ask", "last",
                            "chg1d", "chg1w", "volume", "vol24", "liq", "end", "linked"])
        for r in rows:
            w.writerow([ts, iso(today()), r["category"], r["event_slug"], r["market_slug"], r["event_title"], r["label"], r["yes"], r["bid"],
                        r["ask"], r["last"], r["chg1d"], r["chg1w"], round(r["volume"]), round(r["vol24"]), round(r["liq"]), r["end"],
                        "|".join(r["linked"] or [])])
    json.dump(rows, open(os.path.join(D, f"odds_{today()}.json"), "w"), indent=1, default=str)
    if not quiet:
        print(f"ODDS {ts}: {len(rows)} Polymarket markets ({sum(r['category']=='earnings' for r in rows)} earnings-beat) -> {SNAP}")
        for r in sorted([r for r in rows if r["category"] == "earnings"], key=lambda r: r["end"]):
            print(f"  EARN {r['ticker']:6s} beat>{r['strike']} P(yes) {pp(r['yes'])} 24h {pct(r['chg1d'],0) if r['chg1d'] is not None else '?'} "
                  f"vol ${r['volume']:,.0f} liq ${r['liq']:,.0f} end {r['end']}")
        top = sorted([r for r in rows if r["category"] != "earnings"], key=lambda r: -abs(r["chg1d"] or 0) * math.log10(10 + r["vol24"]))[:25]
        print("  TOPIC MARKETS (largest 24h moves, volume-weighted):")
        for r in top: print(f"    {pp(r['yes']):>4} 24h {pct(r['chg1d'],0) if r['chg1d'] is not None else '?':>5} vol24 ${r['vol24']:,.0f} | {r['event_title'][:60]} :: {str(r['label'])[:40]}")
    return rows

def relevant(r, cat=None):
    """Keep topic markets that can inform a trade: some real volume, not a dead tail (0-3% / 97-100%) unless heavily traded."""
    cat = cat or r.get("category", ""); v = r.get("vol24") or 0; y = r.get("yes")
    if y is None: return False
    if v < (5000 if cat.startswith("tag:") else 500): return False
    if (y < 0.03 or y > 0.97) and v < 20000: return False
    return True

def snapshot_move(market_slug, hours=24):
    """Our own odds move from the snapshot file (complements Polymarket's oneDayPriceChange)."""
    if not os.path.exists(SNAP): return None
    cut = (now() - dt.timedelta(hours=hours)).isoformat(timespec="minutes"); old = new = None
    for r in csv.DictReader(open(SNAP)):
        if r["market_slug"] != market_slug: continue
        if r["ts"] <= cut: old = fnum(r["yes"])
        new = fnum(r["yes"])
    return None if old is None or new is None else new - old

def price_history(token, start_ts, end_ts, fidelity=60):
    if not token: return None
    f = os.path.join(CACHE, f"clob_{token[-14:]}_{start_ts}_{end_ts}_{fidelity}.json")
    if os.path.exists(f) and end_ts < time.time() - 86400: return json.load(open(f))
    d = http_json(f"https://clob.polymarket.com/prices-history?market={token}&startTs={start_ts}&endTs={end_ts}&fidelity={fidelity}", tries=3)
    if d is None or "history" not in d: return None
    h = [(x["t"], x["p"]) for x in d["history"]]
    if end_ts < time.time() - 86400: json.dump(h, open(f, "w"))
    return h
def p_at(hist, ts):
    best = None
    for t, p in hist or []:
        if t <= ts: best = p
        else: break
    return best

# ---------------------------------------------------------------- base rates
def surprise_history(t, allow_paid):
    """Past quarters [(date, eps_actual, eps_estimate)] newest first. stockanalysis (paid, 30d cache) if allowed, else Nasdaq (4q)."""
    if allow_paid:
        x = alex("stockanalysis-com", "securities/earnings", {"symbol": t.replace("-", ".")}, ttl_h=24 * 30, tag="edge")
        if x and x.get("reports"):
            rows = [(r["date"], r["eps_actual"], r["eps_estimate"], r.get("revenue_actual"), r.get("revenue_estimate"))
                    for r in x["reports"] if r.get("eps_actual") is not None and r.get("eps_estimate") is not None]
            if rows: return rows[:12], "stockanalysis 12q"
    d = nasdaq(f"https://api.nasdaq.com/api/company/{t.replace('-', '.')}/earnings-surprise")
    rows = []
    for r in ((((d or {}).get("data") or {}).get("earningsSurpriseTable") or {}).get("rows") or []):
        try:
            m, dd, y = r["dateReported"].split("/")
            rows.append((f"{y}-{int(m):02d}-{int(dd):02d}", fnum(r["eps"]), fnum(r["consensusForecast"]), None, None))
        except Exception: pass
    if not rows: warn(f"{t}: no earnings-surprise history (base rate UNKNOWN)")
    return rows, "nasdaq 4q"

def load_bt():
    f = os.path.join(D, "backtest", "events.csv")
    if not os.path.exists(f): return []
    return [r for r in csv.DictReader(open(f))]

def universe_base(bt):
    ys = [float(r["yes_won"]) for r in bt if r.get("yes_won") not in ("", None)]
    return (sum(ys) / len(ys), len(ys)) if len(ys) >= 50 else (0.75, 0)   # fallback: long-run S&P beat rate ~75-78% (FactSet)

PF = os.path.join(D, "backtest", "params.json")
PARAMS = json.load(open(PF)) if os.path.exists(PF) else {}

def bucket_stats(bt, p):
    """Cross-sectional reaction stats for Polymarket markets with a similar pre-event P(beat)."""
    lo, hi = (0, .5) if p < .5 else (.5, .7) if p < .7 else (.7, .85) if p < .85 else (.85, 1.01)
    xs = [r for r in bt if r.get("p_entry") and lo <= float(r["p_entry"]) < hi and r.get("xret") not in ("", None)]
    if len(xs) < 15: return None
    out = {"bucket": f"{lo:.2f}-{min(hi,1):.2f}", "n": len(xs)}
    for lab, sub in (("beat", [r for r in xs if r["yes_won"] == "1"]), ("miss", [r for r in xs if r["yes_won"] == "0"])):
        v = [float(r["xret"]) for r in sub]
        out[lab] = (st.mean(v) if v else None, len(v), sum(x < 0 for x in v) / len(v) if v else None)
    out["all"] = st.mean(float(r["xret"]) for r in xs)
    out["absmove"] = st.mean(abs(float(r["xret"])) for r in xs)
    return out

def implied_move(t, event_day, spot):
    """ATM straddle / spot for the first expiry on/after the reaction day (Alpaca indicative option snapshots)."""
    if not spot: return None, None
    for k in range(0, 8):
        exp = (dt.date.fromisoformat(event_day) + dt.timedelta(days=k))
        if exp.weekday() >= 5: continue
        d = _alpaca(f"/v1beta1/options/snapshots/{t.replace('-', '.')}", {"feed": "indicative", "limit": 200, "expiration_date": iso(exp),
                     "strike_price_gte": round(spot * 0.93, 2), "strike_price_lte": round(spot * 1.07, 2)})
        snaps = (d or {}).get("snapshots") or {}
        if not snaps: continue
        by = {}
        for sym, s in snaps.items():
            m = re.match(r".*(\d{6})([CP])(\d{8})$", sym)
            if not m: continue
            q = s.get("latestQuote") or {}
            if not q.get("bp") or not q.get("ap") or q["ap"] <= 0: continue
            by.setdefault(int(m.group(3)) / 1000, {})[m.group(2)] = (q["bp"] + q["ap"]) / 2
        both = [(abs(k_ - spot), k_, v) for k_, v in by.items() if "C" in v and "P" in v]
        if not both: continue
        _, k_, v = min(both)
        return (v["C"] + v["P"]) / spot, iso(exp)
    return None, None

def linked_names(t, k=10):
    import sqlite3
    try:
        c = sqlite3.connect(os.path.join(BRAIN, "brain.db"))
        e = c.execute("SELECT source,target,relation,sensitivity FROM edges WHERE upper(source)=? OR upper(target)=?", (t, t)).fetchall(); c.close()
    except Exception as ex: warn(f"brain graph unavailable: {ex}"); return []
    out, seen = [], set()
    order = {"high": 0, "med": 1, "low": 2}
    for s, tg, rel, sen in sorted(e, key=lambda x: order.get(x[3], 3)):
        o = tg if s.upper() == t else s
        if not re.fullmatch(r"[A-Z]{1,5}(-[A-Z])?|[A-Z]+\.TO", o or "") or o in seen or o == t: continue
        seen.add(o); out.append((o, (f"{t} {rel} {o}" if s.upper() == t else f"{o} {rel} {t}"), sen))
    return out[:k]

def stock_ctx(t, rows, spy, etf_rows):
    if not rows or len(rows) < 25: return {}
    c = [r[4] for r in rows]; sc = {r[0]: r[4] for r in spy}
    def xr(n):
        if len(rows) <= n: return None
        a, b = rows[-1 - n][0], rows[-1][0]
        if a not in sc or b not in sc: return None
        return c[-1] / c[-1 - n] - sc[b] / sc[a]
    ctx = {"last": c[-1], "last_day": rows[-1][0], "d1": c[-1] / c[-2] - 1, "x1": xr(1), "x5": xr(5), "x20": xr(20), "atr": atr_pct(rows)}
    if etf_rows and len(etf_rows) > 21:
        ec = [r[4] for r in etf_rows]; ctx["etf5"] = ec[-1] / ec[-6] - 1; ctx["etf20"] = ec[-1] / ec[-21] - 1
    return ctx

def past_reactions(t, hist, rows, spy):
    """2-day reaction close(D-1) -> close(D+1), excess vs SPY, around each past report date (covers BMO and AMC)."""
    if not rows: return []
    days = trading_days(rows); sc = {r[0]: r[4] for r in spy}; cc = {r[0]: r[4] for r in rows}; out = []
    for d, a, e, ra, re_ in hist:
        p0, p1 = prev_td(days, d), next_td(days, d) if d in cc else None
        if d not in cc: p1 = next_td(days, d)
        if not p0 or not p1 or p0 not in sc or p1 not in sc: continue
        x = cc[p1] / cc[p0] - (sc[p1] / sc[p0])
        out.append({"date": d, "beat": (a > e) if a is not None and e is not None else None, "surp": (a / e - 1) if e and e > 0 else None, "xret": x})
    return out

# ---------------------------------------------------------------- edge / sheet
def earnings_sheet(r, bt, allow_paid, spy, barsets, base):
    t = r["ticker"]; c = r.get("cal") or {}; strike = r["strike"]; cons = c.get("eps_cons")
    hist, src = surprise_history(t, allow_paid)
    rows = barsets.get(t) or []
    if not rows: warn(f"{t}: no price bars: reaction history and price action UNKNOWN")
    pr = past_reactions(t, hist, rows, spy)
    n = len(hist); beats = sum(1 for h in hist if h[1] is not None and h[2] is not None and h[1] > h[2])
    # P(EPS > strike): share of past quarters whose surprise would have cleared the strike's gap over today's consensus
    need = (strike / cons - 1) if (strike is not None and cons and cons > 0) else None
    surps = [h[1] / h[2] - 1 for h in hist if h[1] is not None and h[2] and h[2] > 0]
    gaap = "-gaap-eps" in (r["market_slug"] or "") and "nongaap" not in (r["market_slug"] or "")
    model_note = ""
    if gaap:
        model_note = "GAAP-EPS strike: our surprise history is adjusted EPS, so the history model does not apply"; surps = []
        warn(f"{t}: Polymarket strike is GAAP EPS; history model UNKNOWN (market odds only)")
    elif need is not None and abs(need) > 0.25:
        model_note = f"strike {strike} vs consensus {cons} differs {need*100:+.0f}% (split, basis or stale consensus): history model UNKNOWN"; surps = []
        warn(f"{t}: strike/consensus mismatch ({strike} vs {cons}); history model UNKNOWN")
    if surps and need is not None:
        k = sum(s > need + 0.005 / max(cons, 0.05) for s in surps)   # 'greater than' strike after rounding (~half a cent)
        a = 4.0; p_model = (k + a * base) / (len(surps) + a)
    elif surps:
        k = sum(s > 0 for s in surps); a = 4.0; p_model = (k + a * base) / (len(surps) + a); warn(f"{t}: current consensus UNKNOWN; model uses plain beat rate")
    else: k, p_model = None, None
    pm = r["yes"]
    # weight on our history model: Polymarket is well calibrated (backtest Brier 0.147 vs 0.196 base rate), so the crude
    # model only nudges it: 0.35 with 12 quarters of history, ~0.2 with Nasdaq's 4 quarters
    w = 0.5 * len(surps) / (len(surps) + 5) if surps else 0
    our = None if p_model is None else pm + w * (p_model - pm)
    ctx = stock_ctx(t, rows, spy, barsets.get(r.get("etf")) if r.get("etf") else None)
    beat_x = [x["xret"] for x in pr if x["beat"]]; miss_x = [x["xret"] for x in pr if x["beat"] is False]
    bs = bucket_stats(bt, pm)
    # reaction per outcome: own history shrunk 50/50 toward the cross-sectional bucket (when available)
    def blend(own, cross):
        if own and cross is not None: return 0.5 * st.mean(own) + 0.5 * cross
        if own: return st.mean(own)
        return cross
    e_beat = blend(beat_x, bs["beat"][0] if bs and bs["beat"][0] is not None else None)
    e_miss = blend(miss_x, bs["miss"][0] if bs and bs["miss"][0] is not None else None)
    ev_our = None if None in (e_beat, e_miss, our) else our * e_beat + (1 - our) * e_miss
    ev_mkt = None if None in (e_beat, e_miss) else pm * e_beat + (1 - pm) * e_miss
    beta = PARAMS.get("surprise_beta")
    ev_edge = None if (beta is None or our is None) else beta * (our - pm)   # backtest: reaction ~ beta x (outcome - p_market)
    rd = c.get("date") or r["end"][:10]
    im, im_exp = implied_move(t, rd, ctx.get("last")) if ctx.get("last") else (None, None)
    if im is None: warn(f"{t}: options-implied move UNKNOWN (no usable straddle quotes)")
    hist_abs = st.mean(abs(x["xret"]) for x in pr) if pr else None
    sold = (sum(x < 0 for x in beat_x) / len(beat_x)) if beat_x else None
    # priced-in read
    read = []
    if ctx.get("x20") is not None and ctx.get("atr"):
        ru = ctx["x20"]
        read.append(f"20d excess vs SPY {pct(ru)} ({'run-up' if ru > 2*ctx['atr'] else 'sell-off' if ru < -2*ctx['atr'] else 'flat-ish'} into print)")
    if im is not None and hist_abs is not None:
        read.append(f"options price +/-{im*100:.1f}% vs avg past 2-day excess move {hist_abs*100:.1f}% ({'options rich' if im > 1.25*hist_abs else 'options cheap' if im < 0.8*hist_abs else 'in line'})")
    if pm >= 0.85: read.append(f"beat is the consensus bet (P {pp(pm)}): a plain beat is priced; reaction depends on guide/size of beat")
    if bs: read.append(f"Polymarket bucket {bs['bucket']} (n={bs['n']}): beats moved {pct(bs['beat'][0])} vs SPY, {pp(bs['beat'][2])} of beats still fell; misses {pct(bs['miss'][0])}")
    gap = None if p_model is None else pm - p_model
    flags = []
    if gap is not None and abs(gap) >= 0.15: flags.append(f"BASE-RATE GAP: Polymarket {pp(pm)} vs history model {pp(p_model)} ({gap*100:+.0f} pts)")
    mv = r["chg1d"] if r["chg1d"] is not None else snapshot_move(r["market_slug"])
    if mv is not None and abs(mv) >= 0.10 and ctx.get("x1") is not None and ctx.get("atr") and abs(ctx["x1"]) < 0.5 * ctx["atr"] and r["vol24"] >= 1000:
        flags.append(f"ODDS MOVED, STOCK DIDN'T: P(beat) {mv*100:+.0f} pts in 24h but {t} {pct(ctx['x1'])} vs SPY (< 0.5 ATR)")
    if r["liq"] < 2000: flags.append(f"THIN MARKET: liquidity ${r['liq']:,.0f}, volume ${r['volume']:,.0f}: treat odds as soft")
    edge = None if our is None else our - pm
    if edge is None: dec = "UNKNOWN: base-rate history missing; no edge claim"
    elif abs(edge) < 0.08: dec = (f"NO EDGE INTO THE PRINT (ours {pp(our)} vs market {pp(pm)}; edge EV {pct(ev_edge)}): stay flat per rules "
                                 "(flat into binaries without edge); trade the reaction and ripples next window")
    elif edge > 0: dec = f"LEAN LONG INTO PRINT (play C) only with a written v6.2 case: ours {pp(our)} > market {pp(pm)}, edge EV {pct(ev_edge)} vs SPY"
    else: dec = f"LEAN AVOID/TRIM INTO PRINT: ours {pp(our)} < market {pp(pm)}, edge EV {pct(ev_edge)} vs SPY"
    tm = c.get("time")
    if tm not in ("BMO", "AMC") and r["end"][11:13].isdigit():   # Polymarket end time (UTC): 14:00Z = before the open
        tm = "BMO" if int(r["end"][11:13]) < 17 else "AMC"
    entry_day = prev_session(dt.date.fromisoformat(rd)) if tm == "BMO" else dt.date.fromisoformat(rd)
    entry_dt = dt.datetime.combine(entry_day, dt.time(15, 45), ET)
    if tm == "TNS": action = f"release time not specified: confirm BMO/AMC; last pre-print window is {entry_day} 3:45 pm (BMO) or {rd} 3:45 pm (AMC)"
    elif now() > entry_dt: action = f"PAST ENTRY WINDOW (last pre-print buy window was {entry_day} 3:45 pm ET): use for the reaction/ripple trade only"
    else: action = f"pre-print windows open until {entry_day} 3:45 pm ET"
    links = linked_names(t)
    if len(links) < 4 and t in SCREENER:
        ind, mc = SCREENER[t]
        peers = sorted([(m, x) for x, (i, m) in SCREENER.items() if i == ind and x != t and mc and 0.2 * mc <= m <= 5 * mc], reverse=True)[:5]
        links += [(x, f"same industry: {ind}", "peer") for m, x in peers if x not in {l[0] for l in links}]
    lm = []
    for o, rel, sen in links:
        cx = stock_ctx(o, barsets.get(o) or [], spy, None)
        lm.append((o, rel, sen, cx.get("x1"), cx.get("x5")))
    links = lm
    if action.startswith("PAST"): dec = "PAST WINDOW (no pre-print entry left; no extended-hours trading): " + dec
    late = None
    if mv is not None:
        late = (f"odds {mv*100:+.0f} pts in 24h: in the backtest, odds that FELL >= 5 pts into the print came with a 0.60 beat rate vs 0.80 when flat "
                "(late money is informative, t ~6); reaction effect itself not significant" if mv <= -0.05 else
                f"odds {mv*100:+.0f} pts in 24h (backtest: rising late odds -> beat rate 0.76; no reliable reaction effect)" if mv >= 0.05 else None)
    if late: read.append(late)
    rel = []
    nm = (r["event_title"] or "").split("(")[0].replace("Will", "").strip().lower()
    for o in ODDS_ALL:
        if o["category"] == "earnings" or not relevant(o) or (o["end"] and o["end"][:10] < iso(today())): continue
        if t in (o.get("linked") or []) or (len(nm) > 3 and nm in (o["event_title"] or "").lower()):
            rel.append(o)
    rel = sorted(rel, key=lambda o: -o["vol24"])[:6]
    sheet = {"related": [(o["event_title"], o["label"], o["yes"], o["chg1d"], o["vol24"], o["end"][:10]) for o in rel],"key": f"earn_{t}_{rd}", "action": action, "time": tm, "type": "earnings", "ticker": t, "event_date": rd,
             "title": r["event_title"], "market_slug": r["market_slug"], "strike": strike, "cons": cons, "pm": pm, "bid": r["bid"], "ask": r["ask"],
             "chg1d": mv, "volume": r["volume"], "liq": r["liq"], "hist_src": src, "n_hist": n, "beats": beats, "k_strike": k,
             "need": need, "p_model": p_model, "model_note": model_note, "our": our, "edge": edge, "e_beat": e_beat, "e_miss": e_miss, "n_beat": len(beat_x),
             "n_miss": len(miss_x), "sold_after_beat": sold, "ev_our": ev_our, "ev_mkt": ev_mkt, "ev_edge": ev_edge, "w_model": w, "im": im, "im_exp": im_exp,
             "hist_abs": hist_abs, "ctx": ctx, "read": read, "flags": flags, "decision": dec, "links": links, "bucket": bs,
             "past": pr[:8]}
    return sheet

def fed_sheet(odds):
    fw = None
    days_to = (dt.date.fromisoformat(FOMC[0]) - today()).days if FOMC else 99
    if today().weekday() == 0 or days_to <= 10 or "--fedwatch" in sys.argv:
        fw = alex("cmegroup-com", "fomc-rate-probabilities/fedwatch_meetings", {}, ttl_h=20, tag="edge")
    else:
        for f in sorted(os.listdir(CACHE)):
            if f.startswith("cmegroup-com__fomc"): fw = json.load(open(os.path.join(CACHE, f)))
        if fw: warn("FedWatch not refreshed today (only Mondays / within 10 days of FOMC): using last cached copy")
    mon = dt.date.fromisoformat(FOMC[0]).strftime("%B").lower()
    pmr = [r for r in odds if (r["event_slug"] or "").startswith(f"fed-decision-in-{mon}") and r.get("label")]
    nxt = dt.date.fromisoformat(FOMC[1]).strftime("%B").lower() if len(FOMC) > 1 else "x"
    pm_next = [(r["label"], r["yes"], r["chg1d"], r["vol24"]) for r in odds if (r["event_slug"] or "").startswith(f"fed-decision-in-{nxt}") and r.get("label")]
    out = {"pm": [(r["label"], r["yes"], r["chg1d"], r["vol24"]) for r in pmr], "fw": None, "flags": [], "title": pmr[0]["event_title"] if pmr else None,
           "next": pm_next, "next_meeting": FOMC[1] if len(FOMC) > 1 else None}
    if not pmr: warn("Polymarket Fed decision market not found")
    if fw:
        s = fw.get("selected_meeting") or {}; cur = [x for x in s.get("target_rates", []) if x.get("current")]
        lo = int(cur[0]["range_bps"].split("-")[0]) if cur else None; dist = {}
        for x in s.get("target_rates", []):
            if x.get("now_pct") is None or lo is None: continue
            dlt = int(x["range_bps"].split("-")[0]) - lo
            lab = "No change" if dlt == 0 else (f"{abs(dlt)} bps {'increase' if dlt > 0 else 'decrease'}")
            dist[lab] = dist.get(lab, 0) + x["now_pct"] / 100
        out["fw"] = {"asof": fw.get("data_as_of"), "meeting": s.get("meeting_date"), "dist": dist,
                     "wk": {x["range_bps"]: x.get("one_week_pct") for x in s.get("target_rates", []) if x.get("one_week_pct")}}
        def norm(l):
            l = l.lower().replace("+", "")
            if "no change" in l: return "No change"
            m = re.search(r"(\d+)\s*bps\s*(increase|decrease)", l)
            return f"{m.group(1)} bps {m.group(2)}" if m else l
        for lab, p, ch, v in out["pm"]:
            f_ = dist.get(norm(lab), 0.0 if dist else None)
            if f_ is not None and p is not None: out.setdefault("diffs", []).append(f"{lab} {(p-f_)*100:+.1f}")
            if f_ is not None and p is not None and abs(p - f_) >= 0.04:
                out["flags"].append(f"FED DIVERGENCE: '{lab}' Polymarket {p*100:.1f}% vs FedWatch {f_*100:.1f}% ({(p-f_)*100:+.1f} pts)")
    return out

def topic_sheet(odds, barsets, spy):
    out = []
    sc = {r[0]: r[4] for r in spy}
    for r in odds:
        if r["category"] == "earnings" or r["yes"] is None or not relevant(r): continue
        if r["end"] and r["end"][:10] < iso(today()): continue   # past end date: stale/awaiting resolution
        if not r.get("linked"): r["linked"] = title_links(r["event_title"])
        mv = r["chg1d"] if r["chg1d"] is not None else snapshot_move(r["market_slug"])
        moves = []
        for t in (r["linked"] or [])[:6]:
            b = barsets.get(t)
            if b and len(b) > 15 and b[-1][0] in sc and b[-2][0] in sc:
                moves.append((t, b[-1][4] / b[-2][4] - 1 - (sc[b[-1][0]] / sc[b[-2][0]] - 1), atr_pct(b)))
        flag = None
        if mv is not None and abs(mv) >= 0.10 and r["vol24"] >= 5000 and moves:
            quiet = [m for m in moves if m[2] and abs(m[1]) < 0.5 * m[2]]
            if len(quiet) >= max(1, len(moves) // 2):
                flag = f"ODDS MOVED, STOCKS QUIET (verify the headline and direction; may be priced in futures/elsewhere): '{r['event_title'][:60]} :: {str(r['label'])[:30]}' {mv*100:+.0f} pts in 24h (vol24 ${r['vol24']:,.0f}); linked {', '.join(f'{t} {x*100:+.1f}%' for t, x, _ in moves)} vs SPY"
        out.append({**{k: r[k] for k in ("category", "event_title", "label", "yes", "vol24", "liq", "end", "market_slug", "event_slug")},
                    "chg1d": mv, "moves": moves, "flag": flag})
    best = {}
    for t in out:
        if t["flag"] and (t["event_slug"] not in best or abs(t["chg1d"] or 0) > abs(best[t["event_slug"]]["chg1d"] or 0)): best[t["event_slug"]] = t
    for t in out:
        if t["flag"] and best.get(t["event_slug"]) is not t: t["flag"] = None
    return out

TITLE_LINKS = [(r"nvidia|jensen huang|\bnvda\b", ["NVDA", "SMH"]), (r"anthropic", ["AMZN", "GOOGL"]), (r"openai", ["MSFT", "ORCL"]),
               (r"bitcoin|\bbtc\b|crypto", ["IBIT", "COIN", "MSTR"]), (r"\bwti\b|crude|\boil\b|opec|\bgas\b", ["XLE", "USO"]),
               (r"iran|israel|gulf", ["XLE", "USO", "LMT"]), (r"china|beijing|xi jinping|taiwan", ["KWEB", "FXI"]),
               (r"home value|mortgage|housing", ["XHB", "ITB"]), (r"tesla|elon", ["TSLA"]), (r"apple\b", ["AAPL"]),
               (r"s&p 500|\bspy\b|nasdaq", ["SPY", "QQQ"]), (r"fed |interest rate|treasury|yield", ["TLT", "KRE"]),
               (r"tariff", ["XLI", "XLY"]), (r"shutdown|budget|debt ceiling", ["LMT", "RTX"]), (r"gold\b", ["GLD"])]
def title_links(title):
    t = (title or "").lower(); out = []
    for rx, tk in TITLE_LINKS:
        if re.search(rx, t): out += [x for x in tk if x not in out]
    return out[:6]

def cmd_edge(max_paid=8):
    cal = load_calendar()
    f = os.path.join(D, f"odds_{today()}.json")
    odds = json.load(open(f)) if os.path.exists(f) and time.time() - os.path.getmtime(f) < 3 * 3600 else cmd_odds(quiet=True)
    ODDS_ALL[:] = odds
    bt = load_bt(); base, nb = universe_base(bt)
    if not nb: warn("no backtest file yet: base rate falls back to 0.75 (long-run S&P beat rate); reaction buckets UNKNOWN")
    horizon = iso(next_sessions(5)[-1])
    er = [r for r in odds if r["category"] == "earnings" and r["end"][:10] >= iso(today()) and r["end"][:10] <= horizon and not r["closed"]]
    sym_sector = {}
    scr = http_json("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true")
    for x in (((scr or {}).get("data") or {}).get("rows") or []):
        sym_sector[x["symbol"].replace("/", "-")] = x.get("sector", "")
        SCREENER[x["symbol"].replace("/", "-")] = (x.get("industry") or "", fnum(x.get("marketCap"), 0) or 0)
    if not sym_sector: warn("Nasdaq screener unavailable: sector ETF context UNKNOWN")
    for r in er: r["etf"] = SECTOR_ETF.get(sym_sector.get(r["ticker"], ""), None); r["etf"] = "SMH" if r["ticker"] in SEMIS else r["etf"]
    need = {"SPY"} | {r["ticker"] for r in er} | {r["etf"] for r in er if r.get("etf")}
    for r in er:
        need |= {l[0] for l in linked_names(r["ticker"])}
        if r["ticker"] in SCREENER:
            ind, mc = SCREENER[r["ticker"]]
            need |= {x for m, x in sorted([(m, x) for x, (i, m) in SCREENER.items() if i == ind and x != r["ticker"] and mc and 0.2 * mc <= m <= 5 * mc], reverse=True)[:5]}
    for r in odds: need |= set((r.get("linked") or title_links(r.get("event_title")))[:6])
    need = {t for t in need if t and re.fullmatch(r"[A-Z]{1,5}(-[A-Z])?", t)}
    bs = bars(sorted(need)); spy = bs.get("SPY") or []
    if not spy: warn("SPY bars missing: all excess-return figures UNKNOWN")
    # paid history only for the most liquid / largest names
    er.sort(key=lambda r: -((r.get("cal") or {}).get("mcap") or 0) - r["volume"])
    sheets = []
    for i, r in enumerate(er):
        try: sheets.append(earnings_sheet(r, bt, i < max_paid, spy, bs, base))
        except Exception as ex: warn(f"{r['ticker']} sheet failed: {ex}")
    fed = fed_sheet(odds); topics = topic_sheet(odds, bs, spy)
    md = render(cal, sheets, fed, topics, base, nb)
    p_md = os.path.join(D, "sheets", f"sheet_{sheet_day()}.md"); open(p_md, "w").write(md)
    p_csv = os.path.join(D, "sheets", f"sheet_{sheet_day()}.csv")
    with open(p_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "type", "ticker", "event_date", "time", "outcome", "p_market", "p_model", "p_ours", "exp_reaction_vs_spy", "ev_edge", "ev_ours",
                    "ev_market", "implied_move", "hist_abs_move", "decision", "flags", "market_slug"])
        for s in sheets:
            for lab, pm_, pmod, po, er_ in (("beat", s["pm"], s["p_model"], s["our"], s["e_beat"]),
                                            ("miss", 1 - s["pm"], None if s["p_model"] is None else 1 - s["p_model"], None if s["our"] is None else 1 - s["our"], s["e_miss"])):
                w.writerow([s["key"], "earnings", s["ticker"], s["event_date"], s["time"], lab, round(pm_, 4), rnd(pmod), rnd(po), rnd(er_),
                            rnd(s["ev_edge"]), rnd(s["ev_our"]), rnd(s["ev_mkt"]), rnd(s["im"]), rnd(s["hist_abs"]), s["decision"], " | ".join(s["flags"]), s["market_slug"]])
        for lab, p, ch, v in fed["pm"]:
            w.writerow([f"fed_{FOMC[0]}", "fed", "", FOMC[0], "14:00 ET", lab, p, "", "", "", "", "", "", "", "", "", " | ".join(fed["flags"]), ""])
        for t in topics:
            w.writerow([t["event_slug"], t["category"], "", t["end"][:10], "", f"{t['event_title']} :: {t['label']}", t["yes"], "", "", "", "", "", "", "", "", "",
                        t["flag"] or "", t["market_slug"]])
    json.dump({"sheets": sheets, "fed": fed}, open(os.path.join(D, "sheets", f"sheet_{sheet_day()}.json"), "w"), indent=1, default=str)
    print(md); print(f"\nSaved: {p_md}\n       {p_csv}\nAlexandria credits logged today: {credits_used_today():.0f}")
    return sheets

SCREENER = {}
ODDS_ALL = []
def sheet_day():
    """The session a sheet is for: today before 4 pm on a session day, else the next session."""
    return today() if is_session(today()) and now().hour < 16 else next_sessions(1)[0]

def rnd(x, n=4): return "" if x is None else round(x, n)

def render(cal, sheets, fed, topics, base, nb):
    L = [f"# ANTICIPATION SHEET for session {sheet_day()} (built {now().strftime('%Y-%m-%d %H:%M ET')}) - PAPER ONLY",
         "Probabilities: Polymarket = market; model = company EPS-surprise history vs the market's strike, shrunk to the base rate; "
         "ours = market + w x (model - market), w <= 0.35 (Polymarket is well calibrated in the backtest). Reactions are 2-day excess vs SPY. Every number here is input to a v6.2 case, never a trigger.", ""]
    if WARN: L += ["## Data warnings"] + [f"- DATA WARNING: {w}" for w in WARN] + [""]
    L += ["## Arbitrage-like flags"]
    fl = [f"- {s['ticker']}: {f}" for s in sheets for f in s["flags"] if not f.startswith("THIN")] + [f"- {f}" for f in fed["flags"]] + \
         [f"- {t['flag']}" for t in topics if t["flag"]]
    L += fl or ["- none today (no odds-vs-stock or odds-vs-base-rate gap above threshold)"]
    L += ["", f"## Calendar (next sessions {cal['sessions'][0]}..{cal['sessions'][-1]})"]
    big = sorted([e for e in cal.get("earnings", []) if e["mcap"] >= 20e9], key=lambda e: (e["date"], -e["mcap"]))
    L += ["- Earnings ($20B+): " + "; ".join(f"{e['date'][5:]} {e['time']} {e['ticker']} (cons {e['eps_cons']})" for e in big[:30])]
    L += ["- Macro: " + "; ".join(f"{m['date'][5:]} {m['time']} {m['name']} (f/c {m['forecast']}, prev {m['previous']})" for m in cal.get("macro", []))]
    L += [f"- FOMC: {', '.join(cal.get('fomc', []))}; IPOs: " + ("; ".join(f"{i['ticker']} {i['date']} @{i['price']}" for i in cal.get("ipos", []) if i["status"] == "upcoming") or "none upcoming on Nasdaq calendar")]
    L += ["- Desks: " + "; ".join(f"{d['title']}" for d in cal.get("desks", []))]
    L += ["", f"## Earnings events with a Polymarket beat market (base rate {pp(base)}{' from '+str(nb)+' resolved Polymarket markets' if nb else ' fallback'})"]
    for s in sorted(sheets, key=lambda s: (s["event_date"], -(s["volume"] or 0))):
        c = s["ctx"]
        L += ["", f"### {s['ticker']} reports {s['event_date']} {s['time']}: {s['title']}",
              f"- Market: P(EPS > ${s['strike']}) = **{pp(s['pm'])}** (bid {s['bid']} / ask {s['ask']}; 24h {pct(s['chg1d'],0) if s['chg1d'] is not None else 'UNKNOWN'}; "
              f"vol ${s['volume']:,.0f}; liq ${s['liq']:,.0f}); consensus now {s['cons']} -> strike needs {pct(s['need'])} surprise; slug `{s['market_slug']}`",
              f"- Base rate ({s['hist_src']}): beat {s['beats']}/{s['n_hist']} quarters; {s['k_strike'] if s['k_strike'] is not None else '?'} would have cleared this strike gap -> model **{pp(s['p_model'])}**{(' (' + s['model_note'] + ')') if s.get('model_note') else ''}; ours {pp(s['our'])} (edge vs market {pct(s['edge'],0) if s['edge'] is not None else 'UNKNOWN'})",
              f"- Price action: last {c.get('last')} ({c.get('last_day')}); 1d {pct(c.get('x1'))}, 5d {pct(c.get('x5'))}, 20d {pct(c.get('x20'))} vs SPY; ATR {pct(c.get('atr'))}; "
              f"options-implied move +/-{'UNKNOWN' if s['im'] is None else f'{s['im']*100:.1f}% ({s['im_exp']} expiry)'}; avg past 2-day excess move {pct(s['hist_abs']) if s['hist_abs'] is not None else 'UNKNOWN'}",
              f"- Outcomes -> expected 2-day reaction vs SPY: BEAT {pp(s['our'])} -> {pct(s['e_beat'])} (own n={s['n_beat']}, {pp(s['sold_after_beat'])} of own beats fell); "
              f"MISS {pp(None if s['our'] is None else 1-s['our'])} -> {pct(s['e_miss'])} (own n={s['n_miss']})",
              f"- EV of holding through (vs SPY): from the edge {pct(s.get('ev_edge'))} (backtest beta {PARAMS.get('surprise_beta', 0)*100:.1f}% x (ours - market)); "
              f"outcome-weighted ours {pct(s['ev_our'])}, at market odds {pct(s['ev_mkt'])} (noisy: own history n<=12; model weight {s.get('w_model', 0):.2f})",
              "- Priced in? " + "; ".join(s["read"]) if s["read"] else "- Priced in? UNKNOWN",
              "- Past prints: " + ", ".join(f"{p['date']} {'B' if p['beat'] else 'M' if p['beat'] is False else '?'} {pct(p['surp'],0) if p['surp'] is not None else '?'} -> {pct(p['xret'])}" for p in s["past"]),
              "- Affected names (brain graph + same-industry peers; moves vs SPY): " + (", ".join(f"{o} [{sen}: {rel[:45]}] 1d {pct(x1)} 5d {pct(x5)}" for o, rel, sen, x1, x5 in s["links"][:9]) or "none mapped (UNMAPPED)"),
              "- Related Polymarket markets: " + ("; ".join(f"{a[:55]} :: {str(b)[:30]} {pp(y)} (24h {pct(c,0) if c is not None else '?'}, vol24 ${v:,.0f}, ends {e})" for a, b, y, c, v, e in s.get("related", [])) or "none found"),
              f"- Flags: {'; '.join(s['flags']) or 'none'}",
              f"- WHEN: {s.get('action')}",
              f"- READ: {s['decision']}"]
    L += ["", f"## Fed ({FOMC[0]} decision): Polymarket vs CME FedWatch"]
    if fed["fw"]: L += [f"- FedWatch {fed['fw']['asof']}: " + ", ".join(f"{k} {v*100:.1f}%" for k, v in fed["fw"]["dist"].items() if v)]
    else: L += ["- FedWatch: UNKNOWN"]
    L += [f"- Polymarket '{fed['title']}': " + ", ".join(f"{l} {p*100:.1f}% (24h {pct(c,1) if c is not None else '?'})" for l, p, c, v in fed["pm"] if p is not None)]
    L += [f"- {f}" for f in fed["flags"]] or ["- no divergence >= 4 pts"]
    if fed.get("diffs"): L += ["- Polymarket minus FedWatch (pts): " + ", ".join(fed["diffs"])]
    if fed.get("next"): L += [f"- Next meeting {fed['next_meeting']} (Polymarket only; FedWatch feed gives the nearest meeting): " +
                              ", ".join(f"{l} {p*100:.1f}%" for l, p, c, v in fed["next"] if p is not None and p >= 0.01)]
    L += ["", "## Other Polymarket markets tied to the calendar/brain (24h move, linked names' day move vs SPY)"]
    tp = sorted(topics, key=lambda t: -(abs(t["chg1d"] or 0) * math.log10(10 + t["vol24"])))
    for t in tp[:30]:
        L += [f"- {pp(t['yes'])} ({pct(t['chg1d'],0) if t['chg1d'] is not None else '?'} 24h, vol24 ${t['vol24']:,.0f}, ends {t['end'][:10]}) {t['event_title'][:70]} :: {str(t['label'])[:40]}"
              + (f" | linked {', '.join(f'{x} {m*100:+.1f}%' for x, m, _ in t['moves'][:4])}" if t["moves"] else "")]
    L += ["", "## How to use", "- An edge needs ALL of: ours vs market >= 8 pts or EV >= +1% vs SPY, a story (v6.2), and a liquid market. "
          "Write CONVICTION from the sheet (edge size x data quality), P_BEAT = P(position beats SPY) not P(EPS beat). "
          "Log it: `anticipate.py log --slug <market_slug> --p <ours> --decision \"...\"`. See notes/ANTICIPATION.md."]
    return "\n".join(L)

# ---------------------------------------------------------------- ledger
LCOLS = ["id", "logged", "event_key", "event_date", "type", "ticker", "question", "market_slug", "our_p", "model_p", "market_p",
         "decision", "entry_px", "entry_spy", "note", "resolved", "outcome", "resolved_on", "stock_ret", "spy_ret", "excess",
         "brier_ours", "brier_model", "brier_mkt", "decision_pnl"]
def ledger():
    return list(csv.DictReader(open(LEDGER))) if os.path.exists(LEDGER) else []
def save_ledger(rows):
    with open(LEDGER + ".tmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, LCOLS); w.writeheader(); [w.writerow({k: r.get(k, "") for k in LCOLS}) for r in rows]
    os.replace(LEDGER + ".tmp", LEDGER)

def cmd_log(args):
    rows = ledger(); have = {(r["event_key"], r["market_slug"]) for r in rows}
    f = os.path.join(D, "sheets", f"sheet_{sheet_day()}.json")
    sh = json.load(open(f))["sheets"] if os.path.exists(f) else []
    def arg(k, d=None):
        return args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else d
    slug = arg("--slug"); added = 0
    targets = [s for s in sh if (not slug or s["market_slug"] == slug)]
    if slug and not targets:   # a market not on the sheet (e.g. Fed / IPO): look it up
        m = alex("polymarket", "markets/by-slug", {"slug": slug}, ttl_h=0.2, tag="log")
        if not m: print("market not found"); return
        m = m[0] if isinstance(m, list) else m
        pr = [fnum(x) for x in jl(m.get("outcomePrices"), [])]
        targets = [{"key": f"pm_{slug}", "event_date": (m.get("endDate") or "")[:10], "type": "polymarket", "ticker": arg("--ticker", ""),
                    "title": m.get("question"), "market_slug": slug, "our": None, "p_model": None, "pm": pr[0] if pr else None, "decision": "", "ctx": {}}]
    for s in targets:
        if (s["key"], s["market_slug"]) in have and not slug: continue
        our = fnum(arg("--p")) if slug and arg("--p") else s.get("our")
        if our is None: continue
        rows.append({"id": f"F{len(rows)+1:04d}", "logged": now().isoformat(timespec="minutes"), "event_key": s["key"], "event_date": s["event_date"],
                     "type": s.get("type", "earnings"), "ticker": s.get("ticker", ""), "question": s.get("title", ""), "market_slug": s["market_slug"],
                     "our_p": rnd(our), "model_p": rnd(s.get("p_model")), "market_p": rnd(s.get("pm")),
                     "decision": arg("--decision", s.get("decision", ""))[:120], "entry_px": rnd((s.get("ctx") or {}).get("last")),
                     "note": arg("--note", ""), "resolved": "0"})
        added += 1
    save_ledger(rows); print(f"ledger: +{added} rows -> {LEDGER} ({len(rows)} total)")

def cmd_score():
    rows = ledger(); changed = 0
    for r in rows:
        if r.get("resolved") == "1" or not r.get("event_date") or r["event_date"] > iso(today()): continue
        m = alex("polymarket", "markets/by-slug", {"slug": r["market_slug"]}, ttl_h=1, tag="score")
        m = (m[0] if isinstance(m, list) and m else m) or {}
        pr = [fnum(x) for x in jl(m.get("outcomePrices"), [])]
        if not m.get("closed") or not pr or pr[0] not in (0.0, 1.0):
            print(f"  {r['id']} {r['market_slug'][:50]}: not resolved yet"); continue
        y = pr[0]; r["outcome"] = int(y); r["resolved_on"] = iso(today())
        for k, col in (("our_p", "brier_ours"), ("model_p", "brier_model"), ("market_p", "brier_mkt")):
            p = fnum(r.get(k)); r[col] = "" if p is None else round((p - y) ** 2, 4)
        if r.get("ticker") and r.get("type") == "earnings":
            b = bars([r["ticker"], "SPY"]); days = trading_days(b.get("SPY") or [])
            tm = "AMC" if "AMC" in r.get("decision", "") else None
            d0 = prev_td(days, r["event_date"]); d1 = next_td(days, r["event_date"])
            if d0 and d1 and b.get(r["ticker"]):
                sr = ret_window(b[r["ticker"]], d0, d1); spr = ret_window(b["SPY"], d0, d1)
                if sr is not None and spr is not None:
                    r["stock_ret"], r["spy_ret"], r["excess"] = round(sr, 4), round(spr, 4), round(sr - spr, 4)
                    dec = (r.get("decision") or "").upper()
                    r["decision_pnl"] = round(sr - spr, 4) if "LONG" in dec else (round(spr - sr, 4) if "SHORT" in dec else 0)
            else: warn(f"{r['id']}: reaction bars incomplete (UNKNOWN), will retry")
            if not r.get("excess"): continue
        r["resolved"] = "1"; changed += 1
    save_ledger(rows)
    res = [r for r in rows if r.get("resolved") == "1"]
    print(f"SCORE: {changed} newly resolved; {len(res)} resolved of {len(rows)} logged")
    for col in ("brier_ours", "brier_model", "brier_mkt"):
        v = [float(r[col]) for r in res if r.get(col) not in ("", None)]
        if v: print(f"  {col}: {st.mean(v):.4f} (n={len(v)}; lower is better)")
    for lo, hi in ((0, .5), (.5, .7), (.7, .85), (.85, 1.01)):
        sub = [r for r in res if r.get("our_p") and lo <= float(r["our_p"]) < hi]
        if sub: print(f"  ours {lo:.2f}-{hi:.2f}: n={len(sub)} hit {st.mean(float(r['outcome']) for r in sub):.2f} vs avg p {st.mean(float(r['our_p']) for r in sub):.2f}")
    bets = [float(r["decision_pnl"]) for r in res if r.get("decision_pnl") not in ("", None, "0", "0.0")]
    if bets: print(f"  edge bets taken: n={len(bets)} mean excess {st.mean(bets)*100:+.2f}% hit {sum(b>0 for b in bets)/len(bets):.0%}")

# ---------------------------------------------------------------- backtest
def tstat(v):
    if len(v) < 3: return None
    s = st.stdev(v); return st.mean(v) / (s / math.sqrt(len(v))) if s else None
def ols(x, y):
    n = len(x); mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x); sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    if not sxx: return None, None
    b = sxy / sxx; res = [b2 - (my + b * (a - mx)) for a, b2 in zip(x, y)]
    se = math.sqrt(sum(e * e for e in res) / (n - 2) / sxx) if n > 2 else None
    return b, (b / se if se else None)

def cmd_backtest(pages=40):
    print("BACKTEST: closed Polymarket earnings-beat markets vs post-earnings reaction (PAPER research only)")
    evs = []
    for p in range(pages):
        x = alex("polymarket", "events/list", {"closed": True, "limit": 100, "tag_slug": "earnings", "order": "endDate", "ascending": False,
                                               "offset": p * 100}, ttl_h=24 * 7 if p > 0 else 12, tag="backtest")
        if not x: break
        evs += x
        if len(x) < 100: break
    print(f"  closed earnings events fetched: {len(evs)} ({pages} page cap)")
    cand = []
    for e in evs:
        t = ticker_of(e.get("title")); ms = e.get("markets") or []
        if not t or "beat" not in (e.get("title") or "").lower() or len(ms) != 1: continue
        m = ms[0]; pr = [fnum(x) for x in jl(m.get("outcomePrices"), [])]
        if not pr or pr[0] not in (0.0, 1.0) or not m.get("endDate"): continue
        end = dt.datetime.fromisoformat(m["endDate"].replace("Z", "+00:00")).astimezone(ET)
        cand.append({"ticker": t, "slug": e["slug"], "end": end, "yes_won": int(pr[0]), "token": (jl(m.get("clobTokenIds"), []) or [None])[0],
                     "start": m.get("startDate"), "volume": fnum(m.get("volume"), 0)})
    print(f"  resolved single-market beat events: {len(cand)}")
    bs = bars(sorted({c["ticker"] for c in cand} | {"SPY"}), start="2025-01-01"); spy = bs.get("SPY") or []
    days = trading_days(spy)
    def one(c):
        rows = bs.get(c["ticker"])
        if not rows or len(rows) < 30: return {**c, "why": "no bars"}
        e = c["end"]; d = e.date().isoformat(); bmo = e.hour < 12
        if bmo: entry = prev_td(days, d); react = d if d in days else next_td(days, d)
        else: entry = d if d in days else prev_td(days, d); react = next_td(days, entry)
        if not entry or not react: return {**c, "why": "calendar"}
        ets = int(dt.datetime.fromisoformat(entry + "T15:30").replace(tzinfo=ET).timestamp())
        s0 = int(dt.datetime.fromisoformat(c["start"].replace("Z", "+00:00")).timestamp()) if c.get("start") else ets - 20 * 86400
        h = price_history(c["token"], s0, ets + 3600, 60)
        if not h: return {**c, "why": "no odds history"}
        pe = p_at(h, ets); p3 = p_at(h, ets - 3 * 86400); p1 = p_at(h, ets - 86400)
        sr = ret_window(rows, entry, react); spr = ret_window(spy, entry, react)
        gr = ret_window(rows, entry, react, "gap"); gs = ret_window(spy, entry, react, "gap")
        r5 = ret_window(rows, react, (days[days.index(react) + 3] if react in days and days.index(react) + 3 < len(days) else react))
        s5 = ret_window(spy, react, (days[days.index(react) + 3] if react in days and days.index(react) + 3 < len(days) else react))
        pre = ret_window(rows, days[max(0, days.index(entry) - 10)], entry) if entry in days else None
        spre = ret_window(spy, days[max(0, days.index(entry) - 10)], entry) if entry in days else None
        if pe is None or sr is None or spr is None: return {**c, "why": "missing point"}
        I = idx(rows); k = I.get(entry)
        adv = st.mean(r_[4] * r_[5] for r_ in rows[max(0, k - 20):k]) if k else None
        px = rows[k][4] if k is not None else None
        return {**c, "entry": entry, "react": react, "bmo": int(bmo), "p_entry": pe, "p_3d": p3, "p_1d": p1, "xret": sr - spr,
                "xgap": None if gr is None or gs is None else gr - gs, "xpost3": None if r5 is None or s5 is None else r5 - s5,
                "xpre10": None if pre is None or spre is None else pre - spre, "n_pts": len(h), "adv": adv, "px": px, "why": ""}
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(one, cand))
    ok = [r for r in out if not r["why"]]
    drop = {}
    for r in out:
        if r["why"]: drop[r["why"]] = drop.get(r["why"], 0) + 1
    print(f"  usable: {len(ok)}; dropped {drop}")
    f = os.path.join(D, "backtest", "events.csv")
    cols = ["ticker", "slug", "end", "entry", "react", "bmo", "yes_won", "p_entry", "p_3d", "p_1d", "xret", "xgap", "xpost3", "xpre10", "volume", "n_pts", "adv", "px"]
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for r in ok: w.writerow([r[k].isoformat() if k == "end" else rnd(r[k], 5) if isinstance(r[k], float) else r[k] for k in cols])
    rep = backtest_report(ok, drop, len(evs), len(cand))
    open(os.path.join(D, "backtest", "REPORT.md"), "w").write(rep); print(rep)

def backtest_report(ok, drop, n_ev, n_c):
    L = ["# Backtest: Polymarket earnings-beat odds vs post-earnings reaction", f"Built {now().strftime('%Y-%m-%d %H:%M ET')}. "
         f"{n_ev} closed earnings events -> {n_c} resolved single-market beat events -> {len(ok)} usable (dropped: {drop}).",
         "Entry = 3:30 pm ET on the last session before the release (prior day for BMO, same day for AMC); reaction = close(entry) -> close(first "
         "session after the release), minus SPY. p_entry = last Polymarket Yes trade price at/before entry (hourly CLOB history).", ""]
    if len(ok) < 30: return "\n".join(L + ["Too few usable events for any statistics."])
    y = [r["yes_won"] for r in ok]; p = [r["p_entry"] for r in ok]; x = [r["xret"] for r in ok]
    L += [f"## 1. Calibration of Polymarket beat odds", f"- Base rate (resolved Yes): {st.mean(y):.3f} (n={len(y)}); mean p_entry {st.mean(p):.3f}",
          f"- Brier: Polymarket {st.mean((a-b)**2 for a, b in zip(p, y)):.4f} vs constant base rate {st.mean((st.mean(y)-b)**2 for b in y):.4f}"]
    L += ["", "| p_entry bucket | n | mean p | hit rate | mean 2d excess | t | beats: n, mean, % fell | misses: n, mean |", "|---|---|---|---|---|---|---|---|"]
    for lo, hi in ((0, .3), (.3, .5), (.5, .7), (.7, .85), (.85, .95), (.95, 1.01)):
        sub = [r for r in ok if lo <= r["p_entry"] < hi]
        if not sub: continue
        bt_ = [r["xret"] for r in sub if r["yes_won"]]; ms = [r["xret"] for r in sub if not r["yes_won"]]
        ts = tstat([r["xret"] for r in sub])
        row = (f"| {lo:.2f}-{min(hi,1):.2f} | {len(sub)} | {st.mean(r['p_entry'] for r in sub):.2f} | {st.mean(r['yes_won'] for r in sub):.2f} | "
               f"{st.mean(r['xret'] for r in sub)*100:+.2f}% | {'n/a' if ts is None else f'{ts:.2f}'} | ")
        row += (f"{len(bt_)}, {st.mean(bt_)*100:+.2f}%, {sum(v<0 for v in bt_)/len(bt_):.0%} | " if bt_ else "0 | ")
        row += (f"{len(ms)}, {st.mean(ms)*100:+.2f}% |" if ms else "0 |")
        L.append(row)
    b, t_ = ols(p, x)
    L += ["", "## 2. Does pre-event P(beat) predict the reaction vs SPY?", f"- OLS 2d excess on p_entry: slope {b*100:+.2f}% per 1.0 of probability (t {t_:.2f}), n={len(x)}"]
    hiP = [r["xret"] for r in ok if r["p_entry"] >= .85]; loP = [r["xret"] for r in ok if r["p_entry"] < .5]
    if hiP and loP: L += [f"- p>=0.85: mean {st.mean(hiP)*100:+.2f}% (n={len(hiP)}, t {tstat(hiP) or 0:.2f}); p<0.5: mean {st.mean(loP)*100:+.2f}% (n={len(loP)}, t {tstat(loP) or 0:.2f})"]
    bw = [r["xret"] for r in ok if r["yes_won"]]; mw = [r["xret"] for r in ok if not r["yes_won"]]
    L += [f"- Outcome known (not tradeable, shows the size of the binary): beats {st.mean(bw)*100:+.2f}% (n={len(bw)}, {sum(v<0 for v in bw)/len(bw):.0%} fell), "
          f"misses {st.mean(mw)*100:+.2f}% (n={len(mw)}, {sum(v<0 for v in mw)/len(mw):.0%} fell)"]
    # surprise: outcome minus expectation
    sp = [r["yes_won"] - r["p_entry"] for r in ok]; b2, t2 = ols(sp, x)
    L += [f"- Reaction on the SURPRISE (outcome - p_entry): slope {b2*100:+.2f}% per unit (t {t2:.2f}): the market rewards the unexpected part"]
    ch = [r for r in ok if r["p_3d"] is not None]
    if len(ch) > 30:
        d3 = [r["p_entry"] - r["p_3d"] for r in ch]; b3, t3 = ols(d3, [r["xret"] for r in ch])
        up = [r["xret"] for r in ch if r["p_entry"] - r["p_3d"] >= .05]; dn = [r["xret"] for r in ch if r["p_entry"] - r["p_3d"] <= -.05]
        L += ["", "## 3. Does the odds change in the final 3 days predict the reaction?", f"- OLS 2d excess on (p_entry - p_3d): slope {b3*100:+.2f}% per 1.0 (t {t3:.2f}), n={len(ch)}"]
        if up: L += [f"- odds rose >= 5 pts: mean {st.mean(up)*100:+.2f}% (n={len(up)}, t {tstat(up) or 0:.2f}), beat rate {st.mean(r['yes_won'] for r in ch if r['p_entry']-r['p_3d']>=.05):.2f}"]
        if dn: L += [f"- odds fell >= 5 pts: mean {st.mean(dn)*100:+.2f}% (n={len(dn)}, t {tstat(dn) or 0:.2f}), beat rate {st.mean(r['yes_won'] for r in ch if r['p_entry']-r['p_3d']<=-.05):.2f}"]
        flat = [r for r in ch if abs(r["p_entry"] - r["p_3d"]) < .05]
        if flat: L += [f"- odds flat: mean {st.mean(r['xret'] for r in flat)*100:+.2f}% (n={len(flat)}), beat rate {st.mean(r['yes_won'] for r in flat):.2f}"]
        bb, tb = ols(d3, [r["yes_won"] for r in ch])
        L += [f"- odds change vs beat outcome (linear probability): slope {bb:+.2f} (t {tb:.2f}): {'late money was informative' if tb and tb > 2 else 'no reliable information in late moves'}"]
    pr = [r for r in ok if r["xpre10"] is not None]
    if len(pr) > 30:
        b4, t4 = ols([r["xpre10"] for r in pr], [r["xret"] for r in pr])
        hi_ru = [r for r in pr if r["xpre10"] > .05 and r["p_entry"] >= .7]
        L += ["", "## 4. Priced in? Pre-event run-up", f"- OLS 2d excess on 10-day pre-event excess run-up: slope {b4:+.3f} (t {t4:.2f}), n={len(pr)}"]
        if hi_ru: L += [f"- ran up > 5% vs SPY AND p>=0.7: n={len(hi_ru)}, beat rate {st.mean(r['yes_won'] for r in hi_ru):.2f}, mean reaction {st.mean(r['xret'] for r in hi_ru)*100:+.2f}%, "
                        f"{sum(r['xret']<0 for r in hi_ru if r['yes_won'])/max(1,sum(r['yes_won'] for r in hi_ru)):.0%} of beats fell"]
    po = [r for r in ok if r["xpost3"] is not None]
    if len(po) > 30:
        b5, t5 = ols([r["xret"] for r in po], [r["xpost3"] for r in po])
        L += ["", "## 5. Drift after the reaction", f"- next-3-session excess on the 2d reaction: slope {b5:+.3f} (t {t5:.2f}) ({'continuation' if b5 > 0 else 'reversal'}), n={len(po)}"]
    tr = [r for r in ok if (r.get("adv") or 0) >= 20e6 and (r.get("px") or 0) >= 5]
    if len(tr) > 30:
        yb = [r["yes_won"] for r in tr]; pb = [r["p_entry"] for r in tr]
        bt2 = [r["xret"] for r in tr if r["yes_won"]]; ms2 = [r["xret"] for r in tr if not r["yes_won"]]
        b6, t6 = ols([r["yes_won"] - r["p_entry"] for r in tr], [r["xret"] for r in tr])
        b7, t7 = ols(pb, [r["xret"] for r in tr])
        L += ["", "## 6. Book-tradeable subset (price >= $5, 20d ADV >= $20M)",
              f"- n={len(tr)}; base rate {st.mean(yb):.3f}; Brier Polymarket {st.mean((a-b)**2 for a, b in zip(pb, yb)):.4f} vs base {st.mean((st.mean(yb)-b)**2 for b in yb):.4f}",
              f"- beats {st.mean(bt2)*100:+.2f}% (n={len(bt2)}, {sum(v<0 for v in bt2)/len(bt2):.0%} fell); misses {st.mean(ms2)*100:+.2f}% (n={len(ms2)}, {sum(v<0 for v in ms2)/max(1,len(ms2)):.0%} fell)",
              f"- surprise slope {b6*100:+.2f}% per unit (t {t6:.2f}); level slope on p_entry {b7*100:+.2f}% (t {t7:.2f})",
              f"- mean |2d excess| {st.mean(abs(r['xret']) for r in tr)*100:.2f}%"]
        for lo, hi in ((0, .5), (.5, .7), (.7, .85), (.85, 1.01)):
            sub = [r for r in tr if lo <= r["p_entry"] < hi]
            if len(sub) >= 10:
                bb_ = [r["xret"] for r in sub if r["yes_won"]]
                L += [f"  - p {lo:.2f}-{min(hi,1):.2f}: n={len(sub)} hit {st.mean(r['yes_won'] for r in sub):.2f} (mean p {st.mean(r['p_entry'] for r in sub):.2f}); mean {st.mean(r['xret'] for r in sub)*100:+.2f}% (t {tstat([r['xret'] for r in sub]) or 0:.2f}); "
                      f"beat-but-fell {sum(v<0 for v in bb_)/max(1,len(bb_)):.0%} of {len(bb_)}"]
    json.dump({"surprise_beta": b2, "surprise_t": t2, "n": len(ok), "base": st.mean(y)}, open(os.path.join(D, "backtest", "params.json"), "w"))
    lv = sorted(r["volume"] for r in ok); med = lv[len(lv) // 2]
    L += ["", "## Caveats", f"- Polymarket earnings markets are thin (median volume ${med:,.0f}); hourly last-trade prices can be stale; markets open at a default 0.68.",
          f"- Sample spans {min(r['entry'] for r in ok)} to {max(r['entry'] for r in ok)} (about five earnings seasons); names skew to small/mid caps listed by Polymarket; overlapping dates share market shocks (t-stats overstate).",
          "- Strike = consensus at market creation, not at the print; 'beat' here is Polymarket's resolution, not revenue/guide.",
          "- Reaction window uses daily closes (no intraday fills); no costs; survivorship: delisted tickers drop out (no bars).",
          "- Six probability buckets and several cuts were examined: a single bucket at t~2 is what chance alone produces about one time in four; treat it as a hypothesis, not a rule."]
    return "\n".join(L)

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    a = sys.argv[1:] or ["sheet"]; c = a[0]
    def opt(k, d):
        return type(d)(a[a.index(k) + 1]) if k in a else d
    if c == "calendar": cmd_calendar(opt("--sessions", 5))
    elif c == "odds": cmd_odds()
    elif c == "edge": cmd_edge(opt("--sa", 8))
    elif c == "sheet": cmd_calendar(opt("--sessions", 5)); cmd_odds(); cmd_edge(opt("--sa", 8))
    elif c == "log": cmd_log(a[1:])
    elif c == "score": cmd_score()
    elif c == "backtest": cmd_backtest(opt("--pages", 40))
    else: print(__doc__)
    if WARN: print(f"\n{len(WARN)} DATA WARNING(s) this run (see above): treated as UNKNOWN, never evidence.")
