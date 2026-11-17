#!/usr/bin/env python3
"""5-sleeve PAPER day-trading bake-off (the owner approved Nov 10, 2026). PAPER ONLY: never places real trades and never touches
the Alpaca mirror or any broker. Market data only (Alpaca IEX via data.alpaca.markets; Nasdaq daily bars via rotate.bars()).
Rules are FROZEN for 29 sessions, Thu 2026-11-12 to the 2026-12-23 evening window. Full rules and the pre-registered pass mark: sleeves/README.md.
Rules tightened before the freeze on 2026-11-11 (the owner): RSI2 gates/filters/protections, ORB gap band/volume/width/SPY filter/risk sizing/
half-off at 1R, SPY-momentum 15:00-15:30 confirmation sizing + FOMC tags. All mechanical; no discretion and no LLM calls.

Sleeve 5 "runup" (pre-earnings run-up with stock selection) added 2026-11-11 before the freeze (the owner); same dates, costs and pass mark.

Sleeve 1 "v44" = the existing book (book/, rotate.py); read-only here. Sleeves 2-5 live in sleeves/<name>/ (state.json, trades.csv, daily.csv),
each starting at $100,000 cash on 2026-11-12, 0.05% per side.

  bakeoff.py spymom am       settle every finished session's SPY 15:30->16:00 trade from 5-min bars (prior day; same day after 16:05)
  bakeoff.py mark am|pm      one daily.csv row per sleeve per window (am at the 9:45 price, pm at the 3:45 price)
  bakeoff.py rsi2 am         RSI2 exits at the 9:45 price
  bakeoff.py orb pm          settle today's (and any missed) ORB-15 gapper trades from 5-min bars (after 15:36)
  bakeoff.py rsi2 pm         RSI2 exits at the 15:30 price, then entries at the 3:45 quote (entries refuse before 15:43 ET)
  bakeoff.py runup pm        runup pre-report exits at the 15:30 price (stops too), then entries at the 3:45 quote (entries refuse before 15:43 ET)
  bakeoff.py runup am        runup hold-through exits and stops at the 9:45 price
  bakeoff.py score           5-sleeve table since Nov 12 with PASS/FAIL so far
  bakeoff.py status          state of each sleeve

Testing: --dry --date YYYY-MM-DD [--start YYYY-MM-DD] [--dir /tmp/x] replays a past date from historical bars into a temp dir
(default /tmp/bakeoff_dry). Without --dry the code refuses to trade before 2026-11-12 and refuses --date.
"""
import csv, json, os, re, sys, math, subprocess, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); os.chdir(ROOT)
import rotate, prices as P

ET = ZoneInfo("America/New_York")
START = "2026-11-12"; END = "2026-12-23"; CASH0 = 100000.0; COST = 0.0005
NEW = ("rsi2", "orb", "spymom", "runup")
# 2026-11-14 cleanup (Owner: "only keep the ones that are worth it"): last trading session for retired sleeves. Evidence: 3-yr backtests
# research/bt3y_orb_2026-11-12.md (-13.5%), bt3y_rsi2_spymom_2026-11-12.md (spymom -15.2%, rsi2 full +1.8%), bt3y_combo_fix_2026-11-13.md.
# orb/spymom settle sessions through this date only; rsi2 takes no new entries after it but runs exits until flat. Files kept as the record.
RETIRED = {"orb": "2026-11-13", "spymom": "2026-11-13", "rsi2": "2026-11-13"}   # runup added 2026-11-11 before the freeze (the owner)
RSI_IN, RSI_OUT, RSI_SLOTS, RSI_MAXSESS, RSI_EARN = 10, 70, 6, 5, 3
# 2026-11-11 tightening (the owner), RSI2
RSI_MINPX, RSI_MINADV, RSI_SECTOR_MAX, RSI_COOLDOWN = 10.0, 50e6, 2, 3
RSI_SHOCK_DAY, RSI_SHOCK_GAP, RSI_SHOCK_SESS = -0.10, -0.06, 3
RSI_ATR_N, RSI_ATR_K = 14, 3.0
RSI_DD, RSI_DD_SESS = 0.10, 5
RSI_SEC_ETF_3D, RSI_REL_PTS = -0.04, 0.03
RSI_NEWS_SESS, RSI_SEC_SESS = 3, 5
RSI_SEC_ITEMS = ("1.03", "2.06", "3.01", "4.01", "4.02", "5.02")
NEWS_KW = ["downgrade", "cuts guidance", "lowers guidance", "guidance cut", "withdraws guidance", "misses", "profit warning", "investigation",
           "subpoena", "SEC charges", "restatement", "going concern", "bankruptcy", "chapter 11", "delisting", "recall", "FDA rejects",
           "complete response letter", "CEO resigns", "CFO resigns", "steps down", "secondary offering", "dilution", "short report"]
NEWS_RX = re.compile("|".join(r"\b" + re.escape(k) for k in NEWS_KW), re.I)   # word start; "downgrade" also matches "downgrades/downgraded"
SEC_UA = os.environ.get("SEC_USER_AGENT","your-name your-email@example.com")
# 2026-11-11 second batch (the owner): dividend, supply, M&A, correlation, tax-loss season
RSI_DIV_SESS, RSI_LOCKUP_DAYS, RSI_LOCKUP_SESS, RSI_SUPPLY_SESS, RSI_MNA_DAYS = 2, 180, 5, 5, 60
RSI_MAX_CORR, RSI_CORR_N, RSI_TAXLOSS = 0.8, 60, -0.30
OFFER_RX = re.compile(r"\boffering\b|\bpricing of\b|\bsecondary\b", re.I)
SPDEL_RX = re.compile(r"(removed|deleted|dropped)\s+from\s+(the\s+)?S&P|to be removed from|replac\w*\s.{0,80}\b(in|on)\s+the\s+S&P\s*(500|MidCap 400|SmallCap 600)", re.I)
MNA_RX = re.compile(r"to be acquired|definitive agreement to be acquired|agrees to be acquired|merger agreement|tender offer", re.I)
MNA_TARGETS = {"LITE"}   # standing deal-target list from notes/desk_inbox_log.md (2026-10-29: LITE = deal target, never buy)
NEWS_PY = __import__("os").path.join(__import__("os").environ.get("DESK_DIR", "../trading-desk"), "trader-skill/trader-news")
ORB_MAX, ORB_W, ORB_LAST = 4, 0.25, "11:30"
# 2026-11-11 tightening (the owner), ORB
ORB_GAP_LO, ORB_GAP_HI, ORB_MINPX, ORB_MINADV = 0.02, 0.12, 10.0, 20e6
ORB_VOLX, ORB_VOL_SESS, ORB_VOL_FALLBACK = 2.0, 10, 0.15
ORB_W_LO, ORB_W_HI, ORB_SPY_MIN, ORB_RISK = 0.005, 0.04, -0.005, 0.005
# Market calendar: NYSE half days (1 PM close) and full holidays in/around the bake-off
HALF_DAYS = {"2025-11-28", "2025-12-24", "2026-07-02", "2026-11-27", "2026-12-24"}
HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01"}
try:
    import edge; IM_TH = edge.IM_TH          # 0.25 (%), edge.py uses >= / <=
except Exception:
    IM_TH = 0.25
TCOLS = ["date", "time", "action", "ticker", "shares", "price", "value", "cost", "weight", "pnl", "ret", "entry_date", "entry_time", "reason", "basis", "tag"]
SKCOLS = ["date", "ticker", "rank", "rsi2", "blocked_by", "all_blocks", "detail"]
DCOLS = ["date", "window", "equity", "cash", "long_gross", "short_gross", "n_pos", "spy", "prev_session", "prev_close_equity", "spy_prev_close", "note"]

# ---------------- args / clock ----------------
A = sys.argv[1:]
def _opt(k, default=None):
    if k in A: i = A.index(k); v = A[i + 1]; del A[i:i + 2]; return v
    return default
DRY = "--dry" in A
if DRY: A.remove("--dry")
DAY = _opt("--date"); START = _opt("--start", START) if DRY else START
DIR = _opt("--dir", "/tmp/bakeoff_dry" if DRY else os.path.join(ROOT, "sleeves"))
REAL_NOW = dt.datetime.now(ET)
if DAY and not DRY: sys.exit("--date is for --dry replays only")
REPLAY = bool(DAY)
TODAY = DAY or str(REAL_NOW.date())
def now_hm(win=None):
    """Clock in ET. In a replay the clock sits just after the window (am 09:46, pm 15:46; spymom checks use 16:10 only when replaying a past day)."""
    if not REPLAY: return REAL_NOW.strftime("%H:%M")
    return {"am": "09:46", "pm": "15:46"}.get(win, "16:10")

def guard():
    if not DRY and TODAY < START: sys.exit(f"REFUSED: the bake-off starts {START}; nothing is traded before then (use --dry to test)")

# ---------------- time + data ----------------
_TS = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s*(AM|PM)")
def et(t):
    """Alpaca bar/trade timestamp -> (YYYY-MM-DD, HH:MM) in ET. Handles ISO Z strings and the gateway's 'Mon 2026-11-09 3:45 PM EST' form."""
    m = _TS.search(t)
    if m:
        h = int(m.group(2)) % 12 + (12 if m.group(4) == "PM" else 0)
        return m.group(1), f"{h:02d}:{m.group(3)}"
    x = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(ET)
    return str(x.date()), x.strftime("%H:%M")
def utc(day, hm):
    h, m = map(int, hm.split(":"))
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def addm(hm, k):
    h, m = map(int, hm.split(":")); t = h * 60 + m + k; return f"{t // 60:02d}:{t % 60:02d}"
def aget(path, **q):
    u = "https://data.alpaca.markets" + path + "?" + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u), timeout=30) as r: return json.load(r)
        except Exception as e:
            err = e
            import time; time.sleep(2 * (i + 1))
    raise err
def bars5(syms, day, a="09:30", b="15:55", feed="iex"):
    """{sym: [(HH:MM, bar), ...]} 5-min IEX bars for day with start time between a and b (inclusive), multi-symbol, paginated."""
    out = {}
    syms = sorted(set(syms))
    for i in range(0, len(syms), 100):
        tok = None
        while True:
            q = dict(symbols=",".join(syms[i:i + 100]), timeframe="5Min", start=utc(day, a), end=utc(day, b), feed=feed, limit=10000, adjustment="raw")
            if tok: q["page_token"] = tok
            r = aget("/v2/stocks/bars", **q)
            for s, bs in (r.get("bars") or {}).items():
                for x in bs:
                    d, hm = et(x["t"])
                    if d == day and a <= hm <= b: out.setdefault(s, []).append((hm, x))
            tok = r.get("next_page_token")
            if not tok: break
    for s in out: out[s].sort(key=lambda z: z[0])
    return out
def px_at(syms, day, hm):
    """Price of each symbol at HH:MM ET on day. Live run within 6 min of hm -> latest IEX trade (today's only);
    otherwise the open of the 5-min bar starting at hm, else the open of the next bar within 15 min, else the close of the last
    regular-session bar before it (within 30 min)."""
    syms = sorted(set(syms)); out = {}
    if not syms: return out
    live = not REPLAY and day == str(REAL_NOW.date()) and REAL_NOW.strftime("%H:%M") < addm(hm, 6)
    if live:
        for i in range(0, len(syms), 200):
            tr = aget("/v2/stocks/trades/latest", symbols=",".join(syms[i:i + 200]), feed="iex").get("trades", {})
            for s, x in tr.items():
                if x.get("p") and et(x["t"])[0] == day: out[s] = float(x["p"])
        miss = [s for s in syms if s not in out]
        if miss:  # thin IEX names: fall back to the newest bar
            for s, bs in bars5(miss, day, addm(hm, -30), hm).items():
                if bs: out[s] = float(bs[-1][1]["c"])
        return out
    for s, bs in bars5(syms, day, max("09:30", addm(hm, -30)), min("15:55", addm(hm, 15))).items():
        at = [x for h, x in bs if h == hm]; after = [x for h, x in bs if h > hm]; before = [x for h, x in bs if h < hm]
        if at: out[s] = float(at[0]["o"])
        elif after: out[s] = float(after[0]["o"])      # next IEX trade after hm (where a market order would fill), max 15 min
        elif before: out[s] = float(before[-1]["c"])
    return out
def daily(t):
    """Nasdaq daily rows [date, o, h, l, c, v] (rotate.bars cache), strictly before TODAY."""
    return [r for r in rotate.bars(t) if r[0] < TODAY]
def sessions():
    """Trading sessions: SPY daily dates before TODAY, plus TODAY if it is a weekday."""
    s = [r[0] for r in daily("SPY")]
    if dt.date.fromisoformat(TODAY).weekday() < 5: s.append(TODAY)
    return s
def rsi(cl, n=2):
    """Wilder RSI, identical to screen.rsi (rotate.rsi2 uses cl[-60:])."""
    cl = cl[-60:]
    if len(cl) <= n: return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = cl[i] - cl[i - 1]; g += max(d, 0); l += max(-d, 0)
    g /= n; l /= n
    for i in range(n + 1, len(cl)):
        d = cl[i] - cl[i - 1]; g = (g * (n - 1) + max(d, 0)) / n; l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)
_CAL = {}
def cal(day):
    if day not in _CAL:
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"]) or {}
        _CAL[day] = [(r["symbol"].replace(".", "-"), r.get("time", "")) for r in ((d.get("data") or {}).get("rows") or [])]
    return _CAL[day]
def next_session(day):
    d = dt.date.fromisoformat(day)
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and str(d) not in HOLIDAYS: return str(d)
def earnings_soon(day, k=RSI_EARN):
    """Names reporting after today's close (or time not supplied today) or on any of the next k sessions (weekends and holidays skipped)."""
    out = {t for t, w in cal(day) if w != "time-pre-market"}
    d = day
    for _ in range(k):
        d = next_session(d); out |= {t for t, _ in cal(d)}
    return out
def daily_before(t, d):
    """Nasdaq daily rows strictly before date d (for catch-up days earlier than TODAY)."""
    return [r for r in rotate.bars(t) if r[0] < d]
def is_half(day, bs=None):
    """NYSE 1 PM close: listed in HALF_DAYS, or (when SPY bars are given) no regular bar at/after 13:00."""
    if day in HALF_DAYS: return True
    return bs is not None and bool(bs) and max(h for h, _ in bs) < "13:00"
def sma(x, n): return sum(x[-n:]) / n if len(x) >= n else None

# ---------------- sleeve state ----------------
def sd(name): p = os.path.join(DIR, name); os.makedirs(p, exist_ok=True); return p
def load(name):
    f = os.path.join(sd(name), "state.json")
    if os.path.exists(f): return json.load(open(f))
    return dict(sleeve=name, start=START, cash=CASH0, holdings=[], settled={}, marked=None, entered=None, costs=0.0)
def save(name, s):
    f = os.path.join(sd(name), "state.json"); tmp = f + ".tmp"
    with open(tmp, "w") as o: json.dump(s, o, indent=1)
    os.replace(tmp, f)   # atomic: a killed run never leaves a half-written state.json
def ensure_files(name):
    for f, cols in (("trades.csv", TCOLS), ("daily.csv", DCOLS)):
        p = os.path.join(sd(name), f)
        if not os.path.exists(p): csv.writer(open(p, "w", newline="")).writerow(cols)
def row(name, f, d):
    ensure_files(name)
    with open(os.path.join(sd(name), f), "a", newline="") as o:
        csv.DictWriter(o, TCOLS if f == "trades.csv" else DCOLS, extrasaction="ignore").writerow(d)
def hval(h, p):
    return h["shares"] * p * (1 - COST) if h["side"] == "long" else -h["shares"] * p * (1 + COST)
def equity(s, q):
    return s["cash"] + sum(hval(h, q.get(h["ticker"], h["price"])) for h in s["holdings"])
def open_pos(name, s, t, side, p, amt, day, hm, w, why, tag="", **extra):
    if side == "long": sh = amt * (1 - COST) / p; s["cash"] -= amt; act = "BUY"
    else: sh = amt / p; s["cash"] += amt * (1 - COST); act = "SHORT"
    c = amt * COST; s["costs"] = s.get("costs", 0) + c
    h = dict(ticker=t, side=side, shares=sh, price=round(p, 4), amt=round(amt, 2), date=day, time=hm, weight=round(w, 4), why=why, tag=tag, **extra)
    s["holdings"].append(h)
    row(name, "trades.csv", dict(date=day, time=hm, action=act, ticker=t, shares=round(sh, 6), price=round(p, 4), value=round(amt, 2), cost=round(c, 2),
                                 weight=round(w, 4), entry_date=day, entry_time=hm, reason=why, basis=round(amt, 2), tag=tag))
    print(f"[{name}] {act} {t} {sh:.4f} sh @ {p:.2f} (${amt:,.0f}, {100*w:.0f}% of equity) {day} {hm} | {why}")
    return h
def split_pos(s, h, frac):
    """Carve frac of holding h into a new holding (same entry) so it can be closed on its own, e.g. ORB's half-off at +1R."""
    k = dict(h); k["shares"] = h["shares"] * frac; k["amt"] = h["amt"] * frac; k["weight"] = h["weight"] * frac
    h["shares"] -= k["shares"]; h["amt"] -= k["amt"]; h["weight"] -= k["weight"]
    s["holdings"].append(k); return k
def close_pos(name, s, h, p, day, hm, why, tag=None):
    if h["side"] == "long": val = h["shares"] * p * (1 - COST); s["cash"] += val; pnl = val - h["amt"]; act = "SELL"
    else: val = h["shares"] * p * (1 + COST); s["cash"] -= val; pnl = h["amt"] * (1 - COST) - val; act = "COVER"
    c = h["shares"] * p * COST; s["costs"] = s.get("costs", 0) + c
    s["holdings"] = [x for x in s["holdings"] if x is not h]
    row(name, "trades.csv", dict(date=day, time=hm, action=act, ticker=h["ticker"], shares=round(h["shares"], 6), price=round(p, 4), value=round(val, 2),
                                 cost=round(c, 2), weight=h["weight"], pnl=round(pnl, 2), ret=round(pnl / h["amt"], 5),
                                 entry_date=h["date"], entry_time=h["time"], reason=why, basis=round(h["amt"], 2),
                                 tag=h.get("tag", "") if tag is None else tag))
    print(f"[{name}] {act} {h['ticker']} {h['price']}->{p:.2f} pnl ${pnl:,.2f} ({100*pnl/h['amt']:+.2f}% net) {day} {hm} | {why}")

# ---------------- sleeve 2: RSI2 (rules tightened 2026-11-11, the owner) ----------------
def sess_ago(day, n):
    """The session n sessions before day (SPY daily dates; holidays have no bar)."""
    prior = [r[0] for r in rotate.bars("SPY") if r[0] < day]
    return prior[-n] if len(prior) >= n else prior[0]
def ets(t):
    d, hm = et(t); return f"{d} {hm}"
NEWS_PAGES = 20
def news_all(t, a, b):
    """[(ts, headline)] Benzinga headlines (Alpaca news, the source scripts/alpaca_data.py news reads) tagged with t, created in (a, b]
    ('YYYY-MM-DD HH:MM' ET), newest first, at most NEWS_PAGES x 50. Raises if the source fails."""
    out, tok = [], None
    ad, ah = a.split(); bd, bh = b.split()
    for _ in range(NEWS_PAGES):
        q = dict(symbols=t, start=utc(ad, ah), end=utc(bd, bh), limit=50, sort="desc")
        if tok: q["page_token"] = tok
        r = aget("/v1beta1/news", **q)
        for n in r.get("news") or []:
            ts = ets(n["created_at"])
            if a < ts <= b: out.append((ts, n.get("headline") or ""))
        tok = r.get("next_page_token")
        if not tok: break
    return out
def rx_hits(items, rx, a="0000"):
    return [(ts, m.group(0), h[:120]) for ts, h in items if ts > a for m in [rx.search(h)] if m]
def news_hits(t, a, b):
    """Headlines in (a, b] that match NEWS_KW. Raises if the source fails (callers fail closed for entries, keep holdings)."""
    return rx_hits(news_all(t, a, b), NEWS_RX)
_DIV = {}
def divs_for(syms, day):
    """{sym: [(ex_date, cash)]} cash dividends (Alpaca corporate actions, data.alpaca.markets) with ex-dates from ~400 days before day to
    10 days after. Raises on failure. Replays see ex-dates declared after the replay day (minor look-ahead, replays only)."""
    need = sorted(set(syms) - set(_DIV))
    a = str(dt.date.fromisoformat(day) - dt.timedelta(days=400)); b = str(dt.date.fromisoformat(day) + dt.timedelta(days=10))
    for i in range(0, len(need), 200):
        chunk = need[i:i + 200]; tok = None
        for t in chunk: _DIV[t] = []
        while True:
            q = dict(symbols=",".join(chunk), types="cash_dividend", start=a, end=b, limit=1000)
            if tok: q["page_token"] = tok
            r = aget("/v1/corporate-actions", **q)
            for x in ((r.get("corporate_actions") or {}).get("cash_dividends") or []):
                if x.get("symbol") in _DIV and x.get("ex_date") and x.get("rate"): _DIV[x["symbol"]].append((x["ex_date"], float(x["rate"])))
            tok = r.get("next_page_token")
            if not tok: break
    return {t: _DIV.get(t, []) for t in syms}
def div_adjust(df, dv, day):
    """Back-adjust daily rows for cash dividends with ex-date <= day: rows before the ex-date are scaled by (1 - cash / prior close)."""
    if not dv: return df
    rows = [list(r) for r in df]
    for ex, cash in dv:
        if ex > day: continue
        idx = [i for i, r in enumerate(rows) if r[0] < ex]
        if not idx or idx[-1] == 0 and len(rows) == 1: continue
        pc = rows[idx[-1]][4]
        if pc <= 0 or cash >= pc: continue
        f = 1 - cash / pc
        for i in idx:
            for k in (1, 2, 3, 4): rows[i][k] *= f
    return rows
_IPO = {}
def lockups(day):
    """{ticker: lockup_expiry} approximated as IPO priced date + 180 calendar days (Nasdaq IPO calendar, priced deals ~5-7 months back).
    Returns None if the calendar cannot be read (the check is then skipped and logged, per the rule)."""
    if "x" in _IPO: return _IPO["x"]
    d0 = dt.date.fromisoformat(day); months = set()
    for k in range(RSI_LOCKUP_DAYS - 15, RSI_LOCKUP_DAYS + 16, 5): months.add((d0 - dt.timedelta(days=k)).strftime("%Y-%m"))
    out = {}; ok = 0
    for m in sorted(months):
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/ipo/calendar?date={m}"]) or {}
        rows = (((d.get("data") or {}).get("priced") or {}).get("rows"))
        if rows is None: continue
        ok += 1
        for r in rows:
            try: pdt = dt.datetime.strptime(r["pricedDate"], "%m/%d/%Y").date()
            except Exception: continue
            out[r["proposedTickerSymbol"].replace(".", "-")] = str(pdt + dt.timedelta(days=RSI_LOCKUP_DAYS))
    _IPO["x"] = out if ok == len(months) else None
    return _IPO["x"]
def wdays_between(a, b):
    """Signed count of weekdays (not holidays) from date a to date b."""
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b); sg = 1 if db >= da else -1; n = 0; d = da
    while d != db:
        d += dt.timedelta(days=sg)
        if d.weekday() < 5 and str(d) not in HOLIDAYS: n += sg
    return n
def corr(a, b):
    n = len(a); ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb) if va and vb else 0.0
def rets60(df):
    m = [(r[0], r[4]) for r in df[-(RSI_CORR_N + 1):]]
    return {m[i][0]: m[i][1] / m[i - 1][1] - 1 for i in range(1, len(m))}
_SEC = {}
def sec_hits(t, a, b):
    """8-K / 8-K/A filings for t in (a, b] ET carrying any RSI_SEC_ITEMS item (via trader-news news.py, SEC EDGAR Atom feed).
    5.02 cannot be narrowed to CEO/CFO from the feed, so ANY 5.02 counts. Raises on failure. No CIK: ETFs pass, stocks raise."""
    if "f" not in _SEC:
        sys.path.insert(0, NEWS_PY); import news as N
        os.environ.setdefault("SEC_USER_AGENT", SEC_UA)
        _SEC["N"] = N; _SEC["f"] = N.Fetcher(sec_ua=SEC_UA, pause=0.15); _SEC["st"] = {}
    N, f = _SEC["N"], _SEC["f"]
    cik = N.cik_map(f, _SEC["st"]).get(t.replace("-", "."))
    if not cik:
        if t in rotate.ETFS: return []
        raise RuntimeError(f"no SEC CIK for {t}")
    key = ("feed", cik)
    if key not in _SEC: _SEC[key] = N.parse_sec_atom(f.get(N.SEC_FEED % (cik, "8-K", 20), "sec.xml", sec=True), t)
    out = []
    for it in _SEC[key]:
        if not it["time"] or not str(it.get("form", "")).startswith("8-K"): continue
        ts = it["time"].astimezone(ET).strftime("%Y-%m-%d %H:%M")
        bad = sorted(set(it.get("items") or []) & set(RSI_SEC_ITEMS))
        if a < ts <= b and bad: out.append((ts, ",".join(bad), it["title"][:100]))
    return out
def skiplog(day, t, rank, r2, blocks, detail=""):
    p = os.path.join(sd("rsi2"), "skips.csv"); new = not os.path.exists(p)
    with open(p, "a", newline="") as o:
        w = csv.DictWriter(o, SKCOLS)
        if new: w.writeheader()
        w.writerow(dict(date=day, ticker=t, rank=rank, rsi2="" if r2 is None else round(r2, 2), blocked_by=blocks[0] if blocks else "",
                        all_blocks="|".join(blocks), detail=detail[:300]))
def atr(df, n=RSI_ATR_N):
    return sum(max(df[i][2], df[i - 1][4]) - min(df[i][3], df[i - 1][4]) for i in range(-n, 0)) / n
def earn_exit(t, day, win):
    """Force-exit at the last window before a report. Unknown report time is treated as pre-market (conservative)."""
    tod = dict(cal(day)); nxt_d = next_session(day); nxt = dict(cal(nxt_d))
    if t in tod and (win == "pm" or tod[t] != "time-after-hours"):
        return f"EXIT earnings: reports {day} ({tod[t] or 'time n/a'}); last window before the report"
    if win == "pm" and t in nxt and nxt[t] != "time-after-hours":
        return f"EXIT earnings: reports {nxt_d} ({nxt[t] or 'time n/a'}, treated as pre-market); last window before the report"
    return None
def market_gates(day, s, V):
    """RSI2 entry gates on the whole sleeve: SPY<200DMA, drawdown circuit breaker."""
    g = []
    spy = [r[4] for r in daily("SPY")]
    if spy[-1] < sma(spy, 200): g.append(("spy_below_200dma", f"SPY prior close {spy[-1]:.2f} < 200DMA {sma(spy, 200):.2f}"))
    # credit gate removed 2026-11-11 (owner, before freeze): it blocked every entry Nov 2-10 and would starve the 40-trade bar
    s["peak"] = max(s.get("peak", CASH0), V)
    cb = s.get("cb_day")
    if cb and len([d for d in sessions() if cb < d <= day]) >= RSI_DD_SESS: cb = s["cb_day"] = None
    if not cb and V < (1 - RSI_DD) * s["peak"]: cb = s["cb_day"] = day
    if cb: g.append(("circuit_breaker", f"equity fell >{100*RSI_DD:.0f}% below peak ${s['peak']:,.0f} on {cb}; no entries for {RSI_DD_SESS} sessions"))
    return g

def rsi2(win):
    guard(); name = "rsi2"; s = load(name); ensure_files(name); day = TODAY
    if win == "am" and s.get("marked") != f"{day}:am": mark("am"); s = load(name)
    hm = "09:45" if win == "am" else "15:30"
    if not REPLAY and now_hm() < hm: sys.exit(f"rsi2 {win}: too early, exits are priced at {hm} ET")
    ses = sessions(); s.setdefault("last_exit", {})
    nb = f"{sess_ago(day, RSI_NEWS_SESS)} 00:00"; sb = f"{sess_ago(day, RSI_SEC_SESS)} 00:00"; now_ts = f"{day} {hm}"
    if s["holdings"]:
        q = px_at([h["ticker"] for h in s["holdings"]], day, hm)
        try: hdv = divs_for([h["ticker"] for h in s["holdings"]], day)
        except Exception as e: hdv = {}; print(f"[rsi2] dividend data unavailable for holdings ({e}): exits use unadjusted closes")
        for h in list(s["holdings"]):
            t = h["ticker"]; p = q.get(t)
            if not p: print(f"[rsi2] NO PRICE {t} at {hm}: kept"); continue
            cl = [r[4] for r in div_adjust(daily(t), hdv.get(t), day)]; sma5 = sum(cl[-5:]) / 5; r2 = rsi(cl + [p]); n = len([d for d in ses if d > h["date"]])
            why = earn_exit(t, day, win)
            if not why and h.get("stop") and p < h["stop"]: why = f"EXIT catastrophic stop: {p:.2f} < entry - {RSI_ATR_K:g} x ATR14 = {h['stop']:.2f}"
            if not why:
                ent = f"{h['date']} {h['time']}"
                try:
                    hh = news_hits(t, max(nb, ent), now_ts)
                    if hh: why = f"EXIT headline after entry: '{hh[0][1]}' {hh[0][0]}: {hh[0][2]}"
                except Exception as e:
                    print(f"[rsi2] news source failed for holding {t}: kept ({e})"); skiplog(day, t, "held", r2, ["holding_news_fail"], str(e))
                if not why:
                    try:
                        sh = sec_hits(t, max(sb, ent), now_ts)
                        if sh: why = f"EXIT SEC 8-K item {sh[0][1]} filed {sh[0][0]}: {sh[0][2]}"
                    except Exception as e:
                        print(f"[rsi2] SEC source failed for holding {t}: kept ({e})"); skiplog(day, t, "held", r2, ["holding_sec_fail"], str(e))
            if not why:
                if p > sma5: why = f"EXIT price {p:.2f} > 5-day SMA {sma5:.2f} (prior closes)"
                elif r2 is not None and r2 > RSI_OUT: why = f"EXIT RSI2 {r2:.1f} > {RSI_OUT}"
                elif n >= RSI_MAXSESS: why = f"EXIT time: {n} sessions held (max {RSI_MAXSESS})"
            if why:
                close_pos(name, s, h, p, day, hm, f"{why}; RSI2 {r2:.1f}, {n} sess, {win} window"); s["last_exit"][t] = day
            else: print(f"[rsi2] HOLD {t} {p:.2f} vs 5d SMA {sma5:.2f}, RSI2 {r2:.1f}, {n} sess, stop {h.get('stop', 0):.2f}")
    save(name, s)
    if win != "pm": return
    if day > END: print("[rsi2] bake-off over: no new entries after", END); return
    if day > RETIRED.get("rsi2", END): print("[rsi2] RETIRED 2026-11-14: no new entries; exits run until flat"); return
    if s.get("entered") == day: print("[rsi2] entries already done today"); return
    if not REPLAY and now_hm() < "15:43": print("[rsi2] entries wait for the 3:45 quote (run again at 15:43-15:55 ET)"); return
    uni = rotate.universe(); names = [t for t in uni if t not in rotate.NO_LONG]; held = {h["ticker"] for h in s["holdings"]}
    with ThreadPoolExecutor(16) as ex: dd = dict(zip(names, ex.map(lambda t: daily(t) if t not in held else [], names)))
    pre = {}
    for t, df in dd.items():   # base screen (unchanged): 210+ bars, ADV >= $20M, close >= $4; the $10/$50M floor is applied as a logged filter
        if len(df) < 210: continue
        adv = sum(r[4] * r[5] for r in df[-20:]) / 20
        if adv >= 2e7 and df[-1][4] >= 4: pre[t] = (df, adv)
    etfs = sorted(set(rotate.SECTOR_ETF.values()) | {"SPY"})
    q = px_at(list(pre) + list(held) + etfs, day, "15:45")
    V = equity(s, q); gates = market_gates(day, s, V); save(name, s)
    try: dv = divs_for(list(pre) + list(held), day); div_ok = True
    except Exception as e: dv = {}; div_ok = False; print(f"[rsi2] dividend data unavailable ({e}): unadjusted math; every candidate fails the ex-dividend check (fail closed)")
    pre = {t: (div_adjust(df, dv.get(t), day), adv) for t, (df, adv) in pre.items()}
    sig = []
    for t, (df, adv) in pre.items():
        p = q.get(t)
        if not p or p < 5: continue
        c = [r[4] for r in df] + [p]; r2 = rsi(c); s200 = sum(c[-200:]) / 200
        if r2 is not None and r2 < RSI_IN and p > s200: sig.append((r2, -adv, t, p, s200, adv, df))
    sig.sort()   # lowest RSI2 first; ties to the higher 20-day dollar volume
    free = RSI_SLOTS - len(s["holdings"])
    print(f"[rsi2] universe {len(names)} | base-liquid {len(pre)} | priced {len(q)} | raw signals {len(sig)} | free slots {free} | equity ${V:,.2f} | gates {[g[0] for g in gates] or 'open'}")
    if not sig: s["entered"] = day; save(name, s); return
    earn = earnings_soon(day)
    edf = {e: daily(e) for e in etfs}
    op = {}
    try:
        for t, bs in bars5([x[2] for x in sig], day, "09:30", "09:40").items():
            if bs: op[t] = float(bs[0][1]["o"])
    except Exception as e: print(f"[rsi2] today's open unavailable ({e}); gap check uses prior sessions only")
    seccnt = {}
    for h in s["holdings"]: seccnt[h.get("sector", uni.get(h["ticker"], "Other"))] = seccnt.get(h.get("sector", uni.get(h["ticker"], "Other")), 0) + 1
    slot = V / RSI_SLOTS; taken = 0
    divwin = {sess_ago(day, 2), sess_ago(day, 1), day}; d_ = day
    for _ in range(RSI_DIV_SESS): d_ = next_session(d_); divwin.add(d_)
    try: lock = lockups(day)
    except Exception: lock = None
    if lock is None: print("[rsi2] IPO calendar unavailable: lockup check skipped today"); skiplog(day, "*", "", None, ["lockup_check_skipped"], "Nasdaq IPO calendar unavailable (check skipped, not blocking)")
    hret = {h["ticker"]: rets60(div_adjust(daily(h["ticker"]), dv.get(h["ticker"]), day)) for h in s["holdings"]}
    for k, (r2, _, t, p, s200, adv, df) in enumerate(sig):
        rank = k + 1; blocks = [g[0] for g in gates]; det = [g[1] for g in gates]; sec = uni.get(t, "Other")
        if p < RSI_MINPX or adv < RSI_MINADV: blocks.append("liquidity"); det.append(f"price {p:.2f}, ADV ${adv/1e6:.0f}M (need >= ${RSI_MINPX:g}, >= ${RSI_MINADV/1e6:.0f}M)")
        if t in earn: blocks.append("earnings"); det.append(f"report within {RSI_EARN} sessions")
        lx = s["last_exit"].get(t)
        if lx and len([d for d in ses if lx < d <= day]) <= RSI_COOLDOWN: blocks.append("cooldown"); det.append(f"exited {lx}")
        cl = [r[4] for r in df]; shock = []
        for i in range(-RSI_SHOCK_SESS, 0):
            dr = df[i][4] / df[i - 1][4] - 1; gp = df[i][1] / df[i - 1][4] - 1
            if dr < RSI_SHOCK_DAY or gp < RSI_SHOCK_GAP: shock.append(f"{df[i][0]} day {100*dr:+.1f}% gap {100*gp:+.1f}%")
        if p / cl[-1] - 1 < RSI_SHOCK_DAY: shock.append(f"today {100*(p/cl[-1]-1):+.1f}% to 3:45")
        if t in op and op[t] / cl[-1] - 1 < RSI_SHOCK_GAP: shock.append(f"today gap {100*(op[t]/cl[-1]-1):+.1f}%")
        if shock: blocks.append("news_shock"); det.append("; ".join(shock))
        etf = rotate.SECTOR_ETF.get(sec, "SPY"); pe = q.get(etf); ec = [r[4] for r in edf.get(etf, [])]
        s3 = p / cl[-3] - 1
        if not pe or len(ec) < 200: blocks.append("sector_data_missing"); det.append(f"{etf} price/history missing")
        else:
            e200 = sum((ec + [pe])[-200:]) / 200; e3 = pe / ec[-3] - 1
            if pe < e200: blocks.append("sector_below_200dma"); det.append(f"{etf} {pe:.2f} < 200DMA {e200:.2f}")
            if e3 < RSI_SEC_ETF_3D: blocks.append("sector_selloff"); det.append(f"{etf} 3-day {100*e3:+.1f}%")
            if s3 > e3 - RSI_REL_PTS: blocks.append("not_relative_dip"); det.append(f"3-day {100*s3:+.1f}% vs {etf} {100*e3:+.1f}% (need <= {100*(e3-RSI_REL_PTS):+.1f}%)")
        if seccnt.get(sec, 0) >= RSI_SECTOR_MAX: blocks.append("sector_cap"); det.append(f"{seccnt.get(sec)} already held in {sec}")
        if not div_ok: blocks.append("dividend_data_fail"); det.append("corporate actions unavailable")
        else:
            near = [ex for ex, _ in dv.get(t, []) if ex in divwin]
            if near: blocks.append("ex_dividend"); det.append(f"ex-date {near[0]} within {RSI_DIV_SESS} sessions")
        if lock is not None and t in lock and abs(wdays_between(day, lock[t])) <= RSI_LOCKUP_SESS:
            blocks.append("ipo_lockup"); det.append(f"lockup ~{lock[t]} (IPO + {RSI_LOCKUP_DAYS}d)")
        if t in MNA_TARGETS: blocks.append("mna_target"); det.append("desk deal-target list")
        if day[5:] >= "11-01":
            ys = [r for r in df if r[0] < day[:4] + "-01-01"]; base = ys[-1][4] if ys else next((r[4] for r in df if r[0] >= day[:4]), None)
            if base and p / base - 1 < RSI_TAXLOSS: blocks.append("tax_loss"); det.append(f"YTD {100*(p/base-1):+.0f}% (base {base:.2f})")
        rt = rets60(df); hc = []
        for ht, hr in hret.items():
            ds = sorted(set(rt) & set(hr))
            if len(ds) >= 40:
                c_ = corr([rt[d] for d in ds], [hr[d] for d in ds])
                if c_ > RSI_MAX_CORR: hc.append(f"{ht} {c_:.2f}")
        if hc: blocks.append("correlation"); det.append("60d corr > 0.8 with " + ", ".join(hc))
        if blocks: skiplog(day, t, rank, r2, blocks, "; ".join(det)); continue
        if taken >= free: skiplog(day, t, rank, r2, ["slots_full"], f"{len(s['holdings'])} held"); continue
        try:
            ma_from = f"{dt.date.fromisoformat(day) - dt.timedelta(days=RSI_MNA_DAYS)} 00:00"; sup = f"{sess_ago(day, RSI_SUPPLY_SESS)} 00:00"
            items = news_all(t, ma_from, f"{day} 15:45")
            for code, rx, a_ in (("headline", NEWS_RX, nb), ("offering", OFFER_RX, sup), ("sp_deletion", SPDEL_RX, sup), ("mna_target", MNA_RX, ma_from)):
                hh = rx_hits(items, rx, a_)
                if hh: blocks.append(code); det.append(f"'{hh[0][1]}' {hh[0][0]}: {hh[0][2]}")
            if len(items) >= NEWS_PAGES * 50: det.append(f"news capped at {len(items)} items (oldest part of the 60-day M&A window not read)")
        except Exception as e: blocks.append("news_source_fail"); det.append(str(e)[:120])
        if not blocks:
            try:
                sh = sec_hits(t, sb, f"{day} 15:45")
                if sh: blocks.append("sec_8k"); det.append(f"item {sh[0][1]} {sh[0][0]}: {sh[0][2]}")
            except Exception as e: blocks.append("sec_source_fail"); det.append(str(e)[:120])
        if blocks: skiplog(day, t, rank, r2, blocks, "; ".join(det)); print(f"[rsi2] skip {t} (rank {rank}): {blocks[0]} {det[-1]}"); continue
        amt = min(slot, s["cash"])
        if amt < 0.5 * slot: skiplog(day, t, rank, r2, ["cash"], f"cash ${s['cash']:,.0f} below half a slot"); break
        a14 = atr(df); stop = p - RSI_ATR_K * a14
        open_pos(name, s, t, "long", p, amt, day, "15:45", amt / V,
                 f"ENTRY RSI2 {r2:.1f} < {RSI_IN}, price {p:.2f} > 200DMA {s200:.2f}, ADV ${adv/1e6:.0f}M, 3-day {100*s3:+.1f}% vs {etf}, "
                 f"no earnings in {RSI_EARN} sessions, passed dividend/supply/M&A/correlation/tax-loss/headline/8-K checks, rank {rank} of {len(sig)}; stop {stop:.2f} (3 x ATR14 {a14:.2f})",
                 sector=sec, stop=round(stop, 4), atr14=round(a14, 4))
        seccnt[sec] = seccnt.get(sec, 0) + 1; taken += 1; hret[t] = rt
        skiplog(day, t, rank, r2, [], "ENTERED")
    s["entered"] = day; save(name, s)

# ---------------- sleeve 3: ORB-15 earnings gappers (rules tightened 2026-11-11, the owner) ----------------
_SP = {}
def sp500():
    if not _SP:
        import screen; _SP.update(screen.sp500() or {})
    return _SP
def orb_list(day):
    """S&P 500 names reporting after hours on the prior session or pre-market today (Nasdaq calendar), as {ticker: source}.
    A report whose time the calendar does not supply ("time-not-supplied") on either day also counts (Nasdaq drops report times
    for past dates, and some live rows lack them); the +2..+12% open-gap band then decides. Names in shadow/gaps.csv for the day are added."""
    prev = sess_ago(day, 1); sp = sp500(); out = {}
    for d, keep in ((prev, ("time-after-hours", "time-not-supplied", "")), (day, ("time-pre-market", "time-not-supplied", ""))):
        for t, w in cal(d):
            if w in keep and (not sp or t in sp): out.setdefault(t, f"{d} {w or 'time n/a'}")
    gp = os.path.join(ROOT, "shadow/gaps.csv")
    if os.path.exists(gp):
        for r in csv.DictReader(open(gp)):
            if r["date"] == day: out.setdefault(r["ticker"], "gaps.csv")
    return out
def orb_trade(bt, i, e, mid):
    """Legs after entry on bar i at close e: initial stop = OR mid; at +1R sell half and move the rest's stop to entry (breakeven).
    Stop fills at min(bar open, stop); a bar touching both stop and target counts as the stop; if the +1R bar also trades back to
    entry, the remaining half is assumed stopped at breakeven in that bar (conservative). Remainder exits at the 15:30 bar open."""
    R = e - mid; tgt = e + R; stop = mid; frac = 1.0; half = False; legs = []
    for h2, y in bt[i + 1:]:
        if h2 >= "15:30": break
        if y["l"] <= stop:
            legs.append((frac, min(y["o"], stop), h2, f"STOP {'breakeven ' if half else 'range mid '}{stop:.2f}")); frac = 0; break
        if not half and y["h"] >= tgt:
            legs.append((0.5, tgt, h2, f"PARTIAL half at +1R {tgt:.2f}; stop to breakeven {e:.2f}")); frac = 0.5; half = True; stop = e
            if y["l"] <= e: legs.append((0.5, e, h2, f"STOP breakeven {e:.2f} (same bar as +1R, conservative)")); frac = 0; break
    if frac > 0:
        b1530 = next((x for h, x in bt if h == "15:30"), None)
        if b1530: legs.append((frac, b1530["o"], "15:30", "TIME exit 15:30"))
        else: legs.append((frac, bt[-1][1]["c"], addm(bt[-1][0], 5), "TIME exit at last bar"))
    return legs
def or_volume(names, day, today_sip):
    """{t: (ok, detail)} 9:30-9:45 volume test on SIP 5-min bars (delayed SIP history is available at settlement):
    today's 9:30-9:45 volume >= 2x its average over the prior 10 sessions (needs >= 5 sessions with bars).
    Fallback (no intraday history): today's 9:30-9:45 volume >= 15% of the 20-day average daily volume."""
    prior = [r[0] for r in rotate.bars("SPY") if r[0] < day][-ORB_VOL_SESS:]
    hist = {t: [] for t in names}
    for d in prior:
        try: bb = bars5(names, d, "09:30", "09:40", feed="sip")
        except Exception: continue
        for t in names:
            if bb.get(t): hist[t].append(sum(x["v"] for _, x in bb[t]))
    out = {}
    for t in names:
        v = sum(x["v"] for _, x in today_sip.get(t, []))
        if len(hist[t]) >= 5:
            avg = sum(hist[t]) / len(hist[t]); out[t] = (v >= ORB_VOLX * avg, f"OR vol {v:,.0f} vs {ORB_VOL_SESS}-session avg {avg:,.0f} ({v/avg if avg else 0:.1f}x, primary)")
        else:
            df = daily_before(t, day)[-20:]; adv = sum(r[5] for r in df) / max(1, len(df))
            out[t] = (v >= ORB_VOL_FALLBACK * adv, f"OR vol {v:,.0f} vs 20d avg daily vol {adv:,.0f} ({100*v/adv if adv else 0:.0f}%, FALLBACK)")
    return out
def orb_day(s, day):
    name = "orb"
    if is_half(day): print(f"[orb] {day}: half day, skipped"); return "half day: skipped"
    rep = orb_list(day)
    if not rep: print(f"[orb] {day}: no S&P 500 earnings reporters"); return "no reporters"
    prev = sess_ago(day, 1); info = {}
    with ThreadPoolExecutor(16) as ex: dfs = dict(zip(rep, ex.map(lambda t: daily_before(t, day), list(rep))))
    for t in rep:
        df = dfs[t]
        if not df or df[-1][0] != prev: continue
        info[t] = (df[-1][4], sum(r[4] * r[5] for r in df[-20:]) / max(1, len(df[-20:])))
    bb = bars5(list(info) + ["SPY"], day)
    spyb = bb.get("SPY", [])
    if is_half(day, spyb): print(f"[orb] {day}: half day (no SPY bar after 13:00), skipped"); return "half day: skipped"
    so = [x for h, x in spyb if "09:30" <= h < "09:45"]
    spy_or = so[-1]["c"] / so[0]["o"] - 1 if len(so) == 3 else None
    cand = {}
    for t, (pc, adv) in info.items():
        bt = bb.get(t, []); f0 = [x for h, x in bt if h < "09:45"]
        if not f0: print(f"[orb] {day} {t}: no 9:30-9:45 IEX bars, skipped"); continue
        g = f0[0]["o"] / pc - 1
        if not (ORB_GAP_LO <= g <= ORB_GAP_HI): continue
        if pc < ORB_MINPX or adv < ORB_MINADV: print(f"[orb] {day} {t} gap {100*g:+.1f}%: liquidity (close {pc:.2f}, ADV ${adv/1e6:.0f}M)"); continue
        cand[t] = (g, bt)
    print(f"[orb] {day}: {len(rep)} reporters | {len(cand)} in the +2..+12% open-gap band and liquid | SPY 9:30-9:45 {'n/a' if spy_or is None else f'{100*spy_or:+.2f}%'}")
    if spy_or is None or spy_or < ORB_SPY_MIN:
        why = "SPY 9:30-9:45 data missing" if spy_or is None else f"SPY 9:30-9:45 {100*spy_or:+.2f}% < {100*ORB_SPY_MIN:.1f}%"
        print(f"[orb] {day}: market filter, no entries ({why})"); return f"market filter: {why}; {len(cand)} candidates"
    if not cand: return "no candidates in band"
    try: sip = bars5(list(cand), day, "09:30", "09:40", feed="sip")
    except Exception as e: sip = None; print(f"[orb] {day}: SIP bars failed ({e}); using IEX volume for both sides")
    vol = or_volume(list(cand), day, sip) if sip is not None else {t: (True, "volume test unavailable")} 
    trig = []
    for t, (g, bt) in cand.items():
        rng = [x for h, x in bt if "09:30" <= h < "09:45"]; hi = max(x["h"] for x in rng); lo = min(x["l"] for x in rng); mid = (hi + lo) / 2
        ok, vd = vol.get(t, (False, "no volume"))
        if not ok: print(f"[orb] {day} {t} gap {100*g:+.1f}%: volume filter: {vd}"); continue
        w = (hi - lo) / rng[-1]["c"]
        if not (ORB_W_LO <= w <= ORB_W_HI): print(f"[orb] {day} {t} gap {100*g:+.1f}%: range width {100*w:.2f}% outside 0.5-4%"); continue
        for i, (h, x) in enumerate(bt):
            if "09:45" <= h <= ORB_LAST and x["c"] > hi:
                trig.append((addm(h, 5), -g, t, i, x["c"], hi, mid, vd, w)); break
        else: print(f"[orb] {day} {t} gap {100*g:+.1f}%: no close above range high {hi:.2f} by {ORB_LAST}")
    trig.sort(); V0 = s["cash"] if not s["holdings"] else equity(s, {}); n = 0; used = 0.0
    for tt, ng, t, i, e, hi, mid, vd, w in trig[:ORB_MAX]:
        amt = min(ORB_RISK * V0 / (e - mid) * e, ORB_W * V0, V0 - used)
        if amt <= 0: break
        used += amt; bt = cand[t][1]
        h = open_pos(name, s, t, "long", e, amt, day, tt, amt / V0,
                     f"ENTRY ORB-15: open gap {-100*ng:+.1f}%, 5-min close {e:.2f} > OR high {hi:.2f}; stop {mid:.2f}, +1R {2*e-mid:.2f}; "
                     f"risk {100*ORB_RISK:.1f}% -> {100*amt/V0:.1f}% notional; width {100*w:.2f}%; {vd}")
        for frac, px, xt, why in orb_trade(bt, i, e, mid):
            if why.startswith("PARTIAL"):   # half-off at +1R: carve the half out of the full position, the rest stays open
                k = split_pos(s, h, frac); close_pos(name, s, k, px, day, xt, why, tag="PARTIAL")
            else: close_pos(name, s, h, px, day, xt, why)
        n += 1
    for tt, ng, t, *_ in trig[ORB_MAX:]: print(f"[orb] {day} {t}: triggered {tt} but max {ORB_MAX} trades already taken")
    return f"{len(rep)} reporters, {len(cand)} in band, {len(trig)} triggered, {n} traded"
def orb(win="pm"):
    guard(); s = load("orb"); ensure_files("orb"); nowt = now_hm(win)
    for d in sessions():
        if d < START or d > END or d > RETIRED.get("orb", END) or d in s["settled"]: continue
        if d == TODAY and nowt < "15:36": print(f"[orb] {d}: settles after 15:36 ET"); continue
        s["settled"][d] = orb_day(s, d); save("orb", s)
    save("orb", s); print(f"[orb] cash ${s['cash']:,.2f}")

# ---------------- sleeve 4: SPY intraday momentum (rules tightened 2026-11-11, the owner) ----------------
FOMC = set(getattr(edge, "FOMC", [])) if "edge" in globals() else set()
def spymom(win="am"):
    guard(); name = "spymom"; s = load(name); ensure_files(name); nowt = now_hm(win)
    for d in sessions():
        if d < START or d > END or d > RETIRED.get(name, END) or d in s["settled"]: continue
        if d == TODAY and nowt < "16:05": continue
        bs = bars5(["SPY"], d).get("SPY", [])
        if not bs: s["settled"][d] = "no bars"; continue
        if is_half(d, bs): s["settled"][d] = "half day: skipped"; print(f"[spymom] {d}: half day, skipped"); continue
        bm = dict(bs); need = [addm("09:30", 5 * k) for k in range(6)]
        if any(h not in bm for h in need):
            s["settled"][d] = f"skipped: 9:30-10:00 bars incomplete ({len([h for h in need if h in bm])}/6)"; print(f"[spymom] {d}: {s['settled'][d]}"); continue
        r = 100 * (bm["09:55"]["c"] / bm["09:30"]["o"] - 1)
        if "15:30" not in bm or "15:55" not in bm:
            s["settled"][d] = f"flat: 15:30/15:55 bar missing (first30 {r:+.3f}%)"; print(f"[spymom] {d}: {s['settled'][d]}"); continue
        sig = "UP" if r >= IM_TH else "DOWN" if r <= -IM_TH else "FLAT"
        if sig == "FLAT":
            s["settled"][d] = f"FLAT {r:+.3f}%"; print(f"[spymom] {d}: SPY 9:30-10:00 {r:+.3f}% -> flat"); continue
        cn = [addm("15:00", 5 * k) for k in range(6)]
        if all(h in bm for h in cn):
            c = 100 * (bm["15:25"]["c"] / bm["15:00"]["o"] - 1)
            size = 0.5 if (c > 0 and sig == "DOWN") or (c < 0 and sig == "UP") else 1.0
            ctxt = f"15:00-15:30 {c:+.3f}% ({'opposite' if size < 1 else 'same sign' if c else 'zero'}) -> {100*size:.0f}%"
        else: size = 1.0; ctxt = "15:00-15:30 bars incomplete -> 100% (fallback)"
        tag = "FOMC" if d in FOMC else ""
        e, x = bm["15:30"]["o"], bm["15:55"]["c"]; V = s["cash"]
        h = open_pos(name, s, "SPY", "long" if sig == "UP" else "short", e, size * V, d, "15:30", size,
                     f"ENTRY {sig}: SPY 9:30-10:00 {r:+.3f}% {'>=' if sig == 'UP' else '<='} {'+' if sig == 'UP' else '-'}{IM_TH}%; {ctxt}"
                     f"{'; FOMC decision day' if tag else ''}", tag=tag)
        close_pos(name, s, h, x, d, "16:00", f"EXIT 16:00 (15:55 bar close); signal {sig}")
        s["settled"][d] = f"{sig} {r:+.3f}% size {size:.0%}{' FOMC' if tag else ''}"; save(name, s)
    save(name, s); print(f"[spymom] cash ${s['cash']:,.2f} | settled {len(s['settled'])} sessions")

# ---------------- sleeve 5: runup, pre-earnings run-up with stock selection (added 2026-11-11 before the freeze, the owner) ----------------
RU_MAX, RU_W, RU_SEC_MAX = 5, 0.20, 2              # max 5 positions, up to 20% of equity each, max 2 per sector
RU_LEAD = 5                                        # enter when the last pre-report close is exactly 5 sessions away (4 or 6 only if that window is missed)
RU_PEER_SESS, RU_PEER_MIN = 10, 2                  # peer read-through: same-sector reporters in the last 10 sessions, at least 2
RU_CHASE, RU_ATR_K, RU_NEWS_SESS = 0.08, 2.0, 3    # 10-day return <= +8%; stop entry - 2 x ATR14; headline/8-K lookback 3 sessions
RU_MINPX, RU_MINADV = 10.0, 50e6
RU_HT_PEER, RU_HT_GAIN = 0.02, 0.05                # hold half through only if beats 4/4, peer read-through >= +2%, gain since entry <= +5%
RU_TIMES = os.path.join(ROOT, "data", "runup_release_times.json")   # cache: Benzinga results-headline timing per (ticker, calendar date)
RUSKCOLS = ["date", "ticker", "report", "lead", "rank", "peer_rt", "n_peers", "rs20", "blocked_by", "all_blocks", "detail"]
NUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# results-headline patterns, same as research/earnings_runup/fetch.py
RU_PAT = re.compile(r"(\bEPS\b|Earnings Per Share|Reports? (Q[1-4]|(First|Second|Third|Fourth)[- ]Quarter|Fiscal)|Q[1-4] (Revenue|Sales))", re.I)
RU_STRONG = re.compile(r"\b(Q[1-4]|FY)\b.{0,40}\b(EPS|Loss|Sales|Revenue)\b.{0,60}(Beat|Miss|Estimate|In[- ]Line|\$)", re.I)
RU_NOT = re.compile(r"(Last Quarter|Repeat|Sees|Guidance|Raises|Lowers|Reaffirms|Preview|Expectations|Ahead Of|Scheduled|What To Expect|Prediction|Options|Estimate[s]? For|Earnings Call|Transcript|Whisper|Recap|Unusual)", re.I)
_RU = {}
def ru_universe():
    """{ticker: GICS sector} for S&P 500 + Nasdaq-100. S&P names use the S&P GICS sector; Nasdaq-100-only names use rotate.universe()'s map
    (screener sector mapped to GICS). Raises if either list is thin (entries then fail closed)."""
    if "u" in _RU: return _RU["u"]
    sp = sp500()
    if len(sp) < 450: raise RuntimeError(f"S&P 500 list thin ({len(sp)})")
    d = P._curl(["-H", "Accept: application/json", "https://api.nasdaq.com/api/quote/list-type/nasdaq100"]) or {}
    rows = (((d.get("data") or {}).get("data") or {}).get("rows")) or []
    if len(rows) < 95: raise RuntimeError(f"Nasdaq-100 list thin ({len(rows)})")
    u = dict(sp); ndx = [r["symbol"].strip().replace(".", "-") for r in rows]
    miss = [t for t in ndx if t not in u]
    if miss:
        try: scr = rotate.universe()
        except Exception: scr = {}
        for t in miss: u[t] = scr.get(t) if scr.get(t) not in (None, "", "ETF") else "Other"
    _RU["u"] = u; _RU["ndx"] = set(ndx); return u
_RCAL = {}
def ru_cal(day):
    """[(ticker, time)] Nasdaq earnings calendar rows for day. Raises if the calendar cannot be read (fail closed)."""
    if day not in _RCAL:
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"])
        if not d or "data" not in d: raise RuntimeError(f"Nasdaq earnings calendar unavailable for {day}")
        _RCAL[day] = [(r["symbol"].replace(".", "-"), r.get("time", "")) for r in ((d.get("data") or {}).get("rows") or [])]
    return _RCAL[day]
def prev_session(day):
    d = dt.date.fromisoformat(day)
    while True:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5 and str(d) not in HOLIDAYS: return str(d)
def ru_last_close(D, w):
    """Last pre-report close for a report on calendar date D: D itself for an after-hours report, the prior session for pre-market
    or unknown time (unknown treated conservatively as pre-market)."""
    return D if w == "time-after-hours" else prev_session(D)
def ru_upcoming(day, U, n=9):
    """{t: (report_date, time, last_pre_report_close)} for universe names on the calendar today through n sessions ahead (first listing wins)."""
    out = {}; d = day
    for i in range(n + 1):
        if i: d = next_session(d)
        for t, w in ru_cal(d):
            if t in U and t not in out: out[t] = (d, w, ru_last_close(d, w))
    return out
def _ru_times():
    if "times" not in _RU:
        _RU["times"] = json.load(open(RU_TIMES)) if os.path.exists(RU_TIMES) else {}
        seed = os.path.join(ROOT, "research/earnings_runup/data/news_times.csv")   # research study's headline times (NDX, Nov 2025-Nov 2026)
        if os.path.exists(seed):
            for r in csv.DictReader(open(seed)):
                k = f"{r['symbol']}:{r['cal_date']}"
                if k not in _RU["times"] and r["release_et"]: _RU["times"][k] = ru_classify(r["cal_date"], *et(r["release_et"]))
    return _RU["times"]
def ru_classify(D, d, hm):
    """Timing of a report on calendar date D from its results-headline time (d, hm ET): AMC, BMO or '' (unknown)."""
    if d == D: return "BMO" if hm < "09:30" else "AMC" if hm >= "16:00" else ""
    if d == prev_session(D) and hm >= "16:00": return "BMO"     # released the evening before: same anchor as a pre-market report on D
    if d == next_session(D) and hm < "09:30": return "AMC"
    return ""
def ru_release(t, D):
    """'AMC' / 'BMO' / '' for a PAST report, from the first Benzinga results headline (Alpaca news) near calendar date D. Cached."""
    T = _ru_times(); k = f"{t}:{D}"
    if k in T: return T[k]
    a = utc(prev_session(D), "12:00"); b = utc(next_session(D), "12:00"); best = None; tok = None
    try:
        for _ in range(3):
            q = dict(symbols=t.replace("-", "."), start=a, end=b, limit=50, sort="asc")
            if tok: q["page_token"] = tok
            r = aget("/v1beta1/news", **q)
            for n in r.get("news") or []:
                h = n.get("headline") or ""
                if RU_PAT.search(h) and not RU_NOT.search(h) and len(n.get("symbols", [])) <= 3:
                    d, hm = et(n["created_at"]); key = (0 if RU_STRONG.search(h) else 1, abs((dt.date.fromisoformat(d) - dt.date.fromisoformat(D)).days), d + hm)
                    if best is None or key < best[0]: best = (key, d, hm)
            tok = r.get("next_page_token")
            if not tok: break
    except Exception: return ""          # source failed: unknown timing (not cached, retried next run)
    T[k] = ru_classify(D, best[1], best[2]) if best else ""
    return T[k]
def ru_save_times():
    if "times" in _RU:
        tmp = RU_TIMES + ".tmp"; json.dump(_RU["times"], open(tmp, "w")); os.replace(tmp, RU_TIMES)
def ru_react(t, D, timing, day):
    """Reaction of a past report: last pre-report close -> next close. AMC: close D -> next session's close; BMO: prior close -> close D;
    unknown: the research fallback, close 2 sessions before D -> close of the session after D. None unless both closes exist before day."""
    spy = [r[0] for r in rotate.bars("SPY") if r[0] < day]
    if D not in spy: return None
    i = spy.index(D)
    a, b = {"AMC": (i, i + 1), "BMO": (i - 1, i)}.get(timing, (i - 2, i + 1))
    if a < 0 or b >= len(spy): return None
    c = {r[0]: r[4] for r in daily(t)}
    if spy[a] not in c or spy[b] not in c or not c[spy[a]]: return None
    return c[spy[b]] / c[spy[a]] - 1
def ru_peers(day, U, sectors):
    """{sector: [(t, D, timing, reaction)]} for universe names on the calendar in the last RU_PEER_SESS sessions before today whose reaction
    close is complete. Only the sectors asked for are fetched. Raises if a calendar day cannot be read."""
    ses = [r[0] for r in rotate.bars("SPY") if r[0] < day][-RU_PEER_SESS:]
    ev = {}
    for d in ses:
        for t, w in ru_cal(d):
            if t in U and U[t] in sectors: ev[t] = d
    with ThreadPoolExecutor(6) as ex: tm = dict(zip(ev, ex.map(lambda t: ru_release(t, ev[t]), list(ev))))
    ru_save_times()
    out = {s_: [] for s_ in sectors}
    for t, D in ev.items():
        r = ru_react(t, D, tm[t], day)
        if r is not None: out[U[t]].append((t, D, tm[t] or "n/a", r))
    return out
_BEAT = {}
def ru_beats(t, day):
    """(beats, quarters) over the last 4 reported quarters before day: Nasdaq earnings-surprise API (browser headers), beat = % surprise > 0
    (EPS > consensus if the % is missing). Raises on failure. Replays drop quarters reported on/after day and fill older ones from
    data/hist/earnings.csv (Nasdaq calendar surprise %), so a replay never sees the report it is trading into."""
    if t not in _BEAT:
        d = None
        for i in range(3):
            if os.environ.get("PPLX_PROXY_HOSTS"):  # Nov 16, 2026 transport fix only (py.sh blocks curl): same request via urllib
                try:
                    d = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://api.nasdaq.com/api/company/{t.replace('-', '.')}/earnings-surprise",
                        headers={"User-Agent": NUA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
                                 "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}), timeout=20).read()); break
                except Exception: import time; time.sleep(1.5 * (i + 1)); continue
            r = subprocess.run(["curl", "-s", "-m", "20", "-A", NUA, "-H", "Accept: application/json, text/plain, */*", "-H", "Accept-Language: en-US,en;q=0.9",
                                "-H", "Origin: https://www.nasdaq.com", "-H", "Referer: https://www.nasdaq.com/", f"https://api.nasdaq.com/api/company/{t.replace('-', '.')}/earnings-surprise"],
                               capture_output=True, text=True).stdout
            try: d = json.loads(r); break
            except Exception: import time; time.sleep(1.5 * (i + 1))
        rows = ((((d or {}).get("data") or {}).get("earningsSurpriseTable") or {}).get("rows"))
        if rows is None: raise RuntimeError(f"earnings-surprise unavailable for {t}")
        q = []
        for x in rows:
            try: rd = str(dt.datetime.strptime(x["dateReported"], "%m/%d/%Y").date())
            except Exception: continue
            ps = P._num(x.get("percentageSurprise")); e, f = P._num(x.get("eps")), P._num(x.get("consensusForecast"))
            b = ps > 0 if ps is not None else (e > f if e is not None and f is not None else None)
            if b is not None: q.append((rd, b))
        _BEAT[t] = sorted(q, reverse=True)
    q = [x for x in _BEAT[t] if x[0] < day][:4]
    if len(q) < 4 and REPLAY:
        if "hist" not in _RU:
            hh = {}
            for p_ in ("data/hist/earnings.csv", "research/earnings_runup/data/cal_new.csv"):
                if os.path.exists(p_):
                    for r in csv.DictReader(open(p_)):
                        v = P._num(r.get("surprise_pct"))
                        if r.get("symbol") and v is not None: hh.setdefault(r["symbol"], {})[r["date"]] = v > 0
            _RU["hist"] = hh
        old = min([x[0] for x in q], default=day)
        for d_, b in sorted(_RU["hist"].get(t, {}).items(), reverse=True):
            if len(q) >= 4: break
            if d_ < day and (dt.date.fromisoformat(old) - dt.date.fromisoformat(d_)).days >= 20: q.append((d_, b)); old = d_
    return sum(1 for _, b in q if b), len(q)
def ru_skip(day, t, ev, k, rank, pr, npr, rs, blocks, detail=""):
    p = os.path.join(sd("runup"), "skips.csv"); new = not os.path.exists(p)
    with open(p, "a", newline="") as o:
        w = csv.DictWriter(o, RUSKCOLS)
        if new: w.writeheader()
        w.writerow(dict(date=day, ticker=t, report=ev, lead=k, rank=rank, peer_rt="" if pr is None else round(pr, 5), n_peers=npr,
                        rs20="" if rs is None else round(rs, 5), blocked_by=blocks[0] if blocks else "", all_blocks="|".join(blocks), detail=detail[:400]))
def ru_exit_px(syms, day, hm):
    """Exit prices: the hm bar (px_at rules); on a 1 PM half day the evening window uses the last regular bar's close."""
    if hm == "15:30" and is_half(day):
        out = {}
        for t, bs in bars5(syms, day, "12:00", "12:55").items():
            if bs: out[t] = float(bs[-1][1]["c"])
        return out, "12:55 bar close (half day)"
    return px_at(syms, day, hm), f"{hm} bar"

def runup(win):
    guard(); name = "runup"; s = load(name); ensure_files(name); day = TODAY
    s.setdefault("seen", {}); s.setdefault("pm_days", [])
    hm = "09:45" if win == "am" else "15:30"
    if not REPLAY and now_hm() < hm: sys.exit(f"runup {win}: too early, exits are priced at {hm} ET")
    # ---- exits ----
    up = None
    if s["holdings"]:
        if win == "pm":
            try: up = ru_upcoming(day, {h["ticker"]: 1 for h in s["holdings"]})
            except Exception as e: print(f"[runup] calendar unavailable for holdings ({e}): stored report dates used")
        q, src = ru_exit_px([h["ticker"] for h in s["holdings"]], day, hm)
        for h in list(s["holdings"]):
            t = h["ticker"]; p = q.get(t)
            if up and t in up and up[t][2] < h["L"] and up[t][2] >= day:   # report moved earlier: exit earlier
                print(f"[runup] {t}: report moved, last pre-report close {h['L']} -> {up[t][2]}"); h["L"] = up[t][2]; h["report"] = f"{up[t][0]} {up[t][1] or 'time n/a'}"
            if not p: print(f"[runup] NO PRICE {t} at {hm}: kept"); continue
            g = p / h["price"] - 1; why = None
            if h.get("ht"):
                if day > h["L"]: why = f"EXIT hold-through half after the report ({h['report']}), {win} window {src}"
            elif p < h["stop"]: why = f"EXIT stop: {p:.2f} < entry - {RU_ATR_K:g} x ATR14 = {h['stop']:.2f} ({win} window)"
            elif day > h["L"]: why = f"EXIT missed pre-report window (last pre-report close was {h['L']}; report {h['report']}); {win} window {src}"
            elif day == h["L"] and win == "pm":
                ok = h.get("beats") == 4 and h.get("peer", -1) >= RU_HT_PEER and g <= RU_HT_GAIN
                if ok:
                    k = split_pos(s, h, 0.5); k["ht"] = True
                    close_pos(name, s, h, p, day, hm, f"EXIT half before report ({h['report']}) at {src}; other half held through (beats 4/4, peer read-through {100*h['peer']:+.2f}% >= +2%, gain {100*g:+.2f}% <= +5%)", tag="PARTIAL")
                    print(f"[runup] HOLD-THROUGH half {t} until the next morning window"); continue
                why = f"EXIT pre-report: last close before the report ({h['report']}) at {src}; gain {100*g:+.2f}%"
            if why: close_pos(name, s, h, p, day, hm, why, tag="HT" if h.get("ht") else None)
            else: print(f"[runup] HOLD {t} {p:.2f} ({100*g:+.2f}%), exit on {h['L']}, stop {h['stop']:.2f}{' [hold-through half]' if h.get('ht') else ''}")
    save(name, s)
    if win != "pm": return
    # ---- entries (15:45 price) ----
    if day > END: print("[runup] bake-off over: no new entries after", END); return
    if day in s["pm_days"]: print("[runup] entries already done today"); return
    if is_half(day): print(f"[runup] {day}: half day, no 15:45 window (no entries)"); return
    if not REPLAY and now_hm() < "15:43": print("[runup] entries wait for the 3:45 quote (run again at 15:43-15:55 ET)"); return
    try:
        U = ru_universe(); up = ru_upcoming(day, U)
    except Exception as e:
        ru_skip(day, "*", "", "", "", None, "", None, ["universe_or_calendar_fail"], str(e)); print(f"[runup] universe/calendar unavailable ({e}): no entries (fail closed)"); return
    missed_prev = prev_session(day) < START or prev_session(day) not in s["pm_days"] or is_half(prev_session(day))
    next_half = is_half(next_session(day))
    held = {h["ticker"] for h in s["holdings"]}; cands = []
    for t, (D, w, L) in up.items():
        k = wdays_between(day, L); key = f"{t}:{D}"
        if key in s["seen"] or t in held: continue
        if k == RU_LEAD or (k == RU_LEAD - 1 and missed_prev) or (k == RU_LEAD + 1 and next_half): cands.append((t, D, w, L, k))
    print(f"[runup] {day}: universe {len(U)} | upcoming reporters {len(up)} | candidates at lead 5 (4/6 if a window is missed) {len(cands)}")
    if not cands: s["pm_days"].append(day); save(name, s); return
    with ThreadPoolExecutor(16) as ex: dd = dict(zip([c[0] for c in cands], ex.map(lambda c: daily(c[0]), cands)))
    q = px_at([c[0] for c in cands] + list(held) + ["QQQ", "SPY"], day, "15:45")
    V = equity(s, q)
    spy = [r[4] for r in daily("SPY")]; qq = [r[4] for r in daily("QQQ")]; gate = []
    if len(spy) < 200 or spy[-1] <= sma(spy, 200): gate = ["spy_below_200dma"]
    qret = q["QQQ"] / qq[-20] - 1 if q.get("QQQ") and len(qq) >= 20 else None
    try: peers = ru_peers(day, U, {U[c[0]] for c in cands}); pfail = None
    except Exception as e: peers = {}; pfail = str(e)
    nbs = f"{sess_ago(day, RU_NEWS_SESS)} 00:00"; now_ts = f"{day} 15:45"
    def _try(f, *a):
        try: return f(*a)
        except Exception as e: return e
    with ThreadPoolExecutor(8) as ex:   # prefetch the per-name sources in parallel (each result or its exception)
        fb = dict(zip([c[0] for c in cands], ex.map(lambda c: _try(ru_beats, c[0], day), cands)))
        fn = dict(zip([c[0] for c in cands], ex.map(lambda c: _try(news_hits, c[0], nbs, now_ts), cands)))
    rows = []
    for t, D, w, L, k in cands:
        df = dd[t]; p = q.get(t); sec = U[t]; b = list(gate); det = [f"SPY prior close {spy[-1]:.2f} <= 200DMA {sma(spy, 200):.2f}"] if gate else []
        ev = f"{D} {w or 'time n/a'}"; pr = rs = None; npr = 0
        if not p or len(df) < 51: b.append("data_missing"); det.append(f"3:45 price {p}, {len(df)} daily bars")
        if p and df:
            adv = sum(r[4] * r[5] for r in df[-20:]) / 20
            if p < RU_MINPX or adv < RU_MINADV: b.append("liquidity"); det.append(f"price {p:.2f}, ADV ${adv/1e6:.0f}M (need >= ${RU_MINPX:g}, >= ${RU_MINADV/1e6:.0f}M)")
        if pfail: b.append("peer_data_fail"); det.append(pfail[:120])
        else:
            pl = [x for x in peers.get(sec, []) if x[0] != t]; npr = len(pl)
            if npr < RU_PEER_MIN: b.append("peer_too_few"); det.append(f"{npr} {sec} peers reported in the last {RU_PEER_SESS} sessions (need >= {RU_PEER_MIN})")
            else:
                pr = sum(x[3] for x in pl) / npr
                if pr <= 0: b.append("peer_readthrough"); det.append(f"{sec} peers avg reaction {100*pr:+.2f}% over {npr}")
        if p and len(df) >= 51:
            cl = [r[4] for r in df]; s50 = sum((cl + [p])[-50:]) / 50; r20 = p / cl[-20] - 1; r10 = p / cl[-10] - 1
            rs = r20 - qret if qret is not None else None
            if p <= s50: b.append("below_50dma"); det.append(f"{p:.2f} <= 50DMA {s50:.2f}")
            if rs is None: b.append("qqq_data_missing"); det.append("QQQ 20-day return unavailable")
            elif rs < 0: b.append("weak_rs"); det.append(f"20-day {100*r20:+.1f}% < QQQ {100*qret:+.1f}%")
            if r10 > RU_CHASE: b.append("chasing"); det.append(f"10-day {100*r10:+.1f}% > +{100*RU_CHASE:.0f}%")
        x = fb[t]; nb = None
        if isinstance(x, Exception): b.append("beats_data_fail"); det.append(str(x)[:100])
        else:
            nb, nq = x
            if nq < 4 or nb < 3: b.append("beat_history"); det.append(f"beat {nb} of {nq} (need >= 3 of 4)")
        x = fn[t]
        if isinstance(x, Exception): b.append("news_source_fail"); det.append(str(x)[:100])
        elif x: b.append("headline"); det.append(f"'{x[0][1]}' {x[0][0]}: {x[0][2]}")
        try:
            sh = sec_hits(t, nbs, now_ts)
            if sh: b.append("sec_8k"); det.append(f"item {sh[0][1]} {sh[0][0]}: {sh[0][2]}")
        except Exception as e: b.append("sec_source_fail"); det.append(str(e)[:100])
        s["seen"][f"{t}:{D}"] = day
        rows.append(dict(t=t, D=D, w=w, L=L, k=k, p=p, sec=sec, pr=pr, npr=npr, rs=rs, nb=nb, b=b, det=det, ev=ev, df=df))
    ok = sorted([r for r in rows if not r["b"]], key=lambda r: (-r["pr"], -(r["rs"] or 0)))
    for r in rows:
        if r["b"]: ru_skip(day, r["t"], r["ev"], r["k"], "", r["pr"], r["npr"], r["rs"], r["b"], "; ".join(r["det"]))
    seccnt = {}
    for h in s["holdings"]: seccnt[h["sector"]] = seccnt.get(h["sector"], 0) + 1
    n_open = len({(h["ticker"], h["date"]) for h in s["holdings"]}); slot = RU_W * V
    for i, r in enumerate(ok):
        rank = i + 1; t = r["t"]
        if seccnt.get(r["sec"], 0) >= RU_SEC_MAX: ru_skip(day, t, r["ev"], r["k"], rank, r["pr"], r["npr"], r["rs"], ["sector_cap"], f"{seccnt[r['sec']]} held in {r['sec']}"); continue
        if n_open >= RU_MAX: ru_skip(day, t, r["ev"], r["k"], rank, r["pr"], r["npr"], r["rs"], ["slots_full"], f"{n_open} positions"); continue
        amt = min(slot, s["cash"])
        if amt < 0.5 * slot: ru_skip(day, t, r["ev"], r["k"], rank, r["pr"], r["npr"], r["rs"], ["cash"], f"cash ${s['cash']:,.0f} below half a slot"); continue
        a14 = atr(r["df"]); stop = r["p"] - RU_ATR_K * a14
        open_pos(name, s, t, "long", r["p"], amt, day, "15:45", amt / V,
                 f"ENTRY run-up: report {r['ev']}, last pre-report close {r['L']} ({r['k']} sessions); {r['sec']} peer read-through {100*r['pr']:+.2f}% over {r['npr']}; "
                 f"20-day RS vs QQQ {100*r['rs']:+.1f} pts, above 50DMA, 10-day <= +8%; beat {r['nb']}/4; no keyword headline/8-K; rank {rank} of {len(ok)}; "
                 f"stop {stop:.2f} (2 x ATR14 {a14:.2f})",
                 sector=r["sec"], stop=round(stop, 4), atr14=round(a14, 4), L=r["L"], report=r["ev"], peer=round(r["pr"], 5), beats=r["nb"])
        seccnt[r["sec"]] = seccnt.get(r["sec"], 0) + 1; n_open += 1
        ru_skip(day, t, r["ev"], r["k"], rank, r["pr"], r["npr"], r["rs"], [], "ENTERED")
    s["pm_days"].append(day); save(name, s)
    print(f"[runup] {len(rows)} evaluated | {len(ok)} passed all filters | {len(s['holdings'])} holdings | cash ${s['cash']:,.2f}")

# ---------------- mark ----------------
def mark(win):
    guard(); assert win in ("am", "pm"); day = TODAY
    if win == "am": spymom("am")
    else: orb("pm")
    hm = "09:45" if win == "am" else "15:45"
    ses = sessions(); prev = max([d for d in ses if d < day], default=None)
    for name in NEW:
        s = load(name); ensure_files(name)
        if s.get("marked") == f"{day}:{win}": print(f"[{name}] already marked {day} {win}"); continue
        tks = [h["ticker"] for h in s["holdings"]]; q = px_at(tks + ["SPY"], day, hm)
        for t in tks:  # no IEX print at the mark time: carry the prior session's close
            if t not in q:
                c = daily(t); q[t] = c[-1][4] if c else next(h["price"] for h in s["holdings"] if h["ticker"] == t)
                print(f"[{name}] no IEX price for {t} at {hm}: marked at prior close {q[t]}")
        V = equity(s, q)
        lg = sum(h["shares"] * q.get(h["ticker"], h["price"]) for h in s["holdings"] if h["side"] == "long")
        sg = sum(h["shares"] * q.get(h["ticker"], h["price"]) for h in s["holdings"] if h["side"] == "short")
        r = dict(date=day, window=win, equity=round(V, 2), cash=round(s["cash"], 2), long_gross=round(lg, 2), short_gross=round(sg, 2),
                 n_pos=len(tks), spy=round(q.get("SPY", 0), 4), note=f"{win} mark at {hm} ET")
        if win == "am" and prev:
            pc = {t: next((x[4] for x in daily(t) if x[0] == prev), None) for t in tks + ["SPY"]}
            r.update(prev_session=prev, prev_close_equity=round(s["cash"] + sum(hval(h, pc.get(h["ticker"]) or h["price"]) for h in s["holdings"]), 2),
                     spy_prev_close=pc.get("SPY"))
        if name == "rsi2": s["peak"] = max(s.get("peak", CASH0), V)   # circuit-breaker peak (marks + entry windows)
        row(name, "daily.csv", r); s["marked"] = f"{day}:{win}"; save(name, s)
        print(f"[{name}] MARK {day} {win}: equity ${V:,.2f} ({100*(V/CASH0-1):+.2f}%) | {len(tks)} pos | gross long ${lg:,.0f} short ${sg:,.0f}")

# ---------------- score ----------------
def mm_fn(ses):
    idx = {d: i for i, d in enumerate(ses)}
    def mm(d, hm):
        if d not in idx: idx[d] = len([x for x in ses if x < d])
        h, m = map(int, hm.split(":")); k = max(0, min(390, h * 60 + m - 570)); return idx[d] * 390 + k
    return mm
def beta(pairs):
    if len(pairs) < 3: return None
    a = [x for x, _ in pairs]; b = [y for _, y in pairs]; ma, mb = sum(a) / len(a), sum(b) / len(b); vb = sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / vb if vb else None
def stats_of(rets):
    W = [x for x in rets if x > 0]; L = [x for x in rets if x <= 0]
    win = len(W) / len(rets) if rets else None
    pay = (sum(W) / len(W)) / abs(sum(L) / len(L)) if W and L and sum(L) else None
    return win, pay
def score_new(name, ses, spy_base):
    p = os.path.join(DIR, name)
    dr = list(csv.DictReader(open(os.path.join(p, "daily.csv")))) if os.path.exists(os.path.join(p, "daily.csv")) else []
    tr = list(csv.DictReader(open(os.path.join(p, "trades.csv")))) if os.path.exists(os.path.join(p, "trades.csv")) else []
    s = load(name) if os.path.exists(os.path.join(p, "state.json")) else None
    if not dr: return dict(name=name, note="not started")
    last = dr[-1]; V = float(last["equity"]); ret = V / CASH0 - 1
    spy_now = float(last["spy"] or 0); sret = spy_now / spy_base - 1 if spy_base and spy_now else None
    # session-close series from am rows (prior-session close equity), base = 100k at the close before START
    pts = [(None, CASH0, spy_base)] + [(r["prev_session"], float(r["prev_close_equity"]), float(r["spy_prev_close"]))
                                       for r in dr if r["window"] == "am" and r.get("prev_close_equity") and r["prev_session"] >= START]
    pairs = [(pts[i][1] / pts[i - 1][1] - 1, pts[i][2] / pts[i - 1][2] - 1) for i in range(1, len(pts)) if pts[i - 1][2]]
    mm = mm_fn(ses); t0 = mm(START, "09:30"); t1 = mm(last["date"], "09:45" if last["window"] == "am" else "15:45")
    exp = 0.0
    for r in tr:
        if r["action"] in ("SELL", "COVER"): exp += float(r["weight"]) * max(0, mm(r["date"], r["time"]) - mm(r["entry_date"], r["entry_time"]))
    for h in (s or {}).get("holdings", []): exp += h["weight"] * max(0, t1 - mm(h["date"], h["time"]))
    aexp = exp / (t1 - t0) if t1 > t0 else 0.0
    rt = {}   # round trips: ORB's half-off at +1R and its remainder are ONE trade (pnl summed over the legs' cost basis)
    for r in tr:
        if r["action"] in ("SELL", "COVER"):
            k = (r["ticker"], r["entry_date"], r["entry_time"]); b_ = float(r.get("basis") or 0) or (float(r["pnl"]) / float(r["ret"]) if float(r["ret"] or 0) else 0)
            x = rt.setdefault(k, [0.0, 0.0]); x[0] += float(r["pnl"]); x[1] += b_
    closed = [p_ / b_ for p_, b_ in rt.values() if b_]
    win, pay = stats_of(closed); costs = sum(float(r["cost"] or 0) for r in tr)
    out = dict(name=name, ret=ret, spy=sret, beta=beta(pairs), exp=aexp, n=len(closed), win=win, pay=pay, costs=costs, asof=f"{last['date']} {last['window']}", V=V)
    if name == "runup":   # own bar (owner, 2026-11-12): mean net per-trade return minus QQQ over the same span (daily closes: entry date -> last exit leg date)
        try:
            qc = {r[0]: r[4] for r in rotate.bars("QQQ")}; qd = sorted(qc); last_leg = {}
            for r in tr:
                if r["action"] in ("SELL", "COVER"):
                    k = (r["ticker"], r["entry_date"], r["entry_time"]); last_leg[k] = max(last_leg.get(k, ""), r["date"])
            def qclose(d): ds = [x for x in qd if x <= d]; return qc[ds[-1]] if ds else None
            ex = []
            for k, (p_, b_) in rt.items():
                if not b_: continue
                a, b = qclose(k[1]), qclose(last_leg[k])
                if a and b: ex.append(p_ / b_ - (b / a - 1))
            out["excess"] = sum(ex) / len(ex) if ex else None
        except Exception as e:
            out["excess"] = None
    return out
def score_book():
    rows = [r for r in csv.DictReader(open("book/daily.csv")) if r["date"] <= TODAY] if os.path.exists("book/daily.csv") else []
    i = next((k for k, r in enumerate(rows) if r["date"] >= "2026-11-11" and (r["date"] > "2026-11-11" or r["note"].startswith("pm"))), None) if not DRY else None
    if DRY:  # dry runs: start the book's window at the last pm mark before START
        i = max([k for k, r in enumerate(rows) if r["date"] < START and r["note"].startswith("pm")], default=None)
    if i is None: return dict(name="v44 (book)", note="starts at the 2026-11-11 pm mark")
    base = rows[i]; rs = rows[i:]; b0, s0 = float(base["book_value"]), float(base["spy_value"]); last = rs[-1]
    pm = [r for r in rs if r["note"].startswith("pm")]
    pairs = [(float(pm[k]["book_value"]) / float(pm[k - 1]["book_value"]) - 1, float(pm[k]["spy_value"]) / float(pm[k - 1]["spy_value"]) - 1) for k in range(1, len(pm))]
    lv = {"FULL": 1.0, "HALF": 1.0, "DEFENSIVE": 0.5, "BEAR": 0.7}
    exp = sum(lv.get(r["exposure_level"], 1.0) for r in rs[1:]) / max(1, len(rs) - 1) if len(rs) > 1 else lv.get(base["exposure_level"], 1.0)
    pos = list(csv.DictReader(open("book/positions.csv"))) if os.path.exists("book/positions.csv") else []
    bd = base["date"]
    closed = [float(r["ret"]) - 2 * COST for r in pos if r["ticker"] != "SGOV" and (r["date"] > bd or (r["date"] == bd and r["window"] == "pm"))]
    tr = list(csv.DictReader(open("book/trades.csv"))) if os.path.exists("book/trades.csv") else []
    costs = sum(float(r["value"]) * COST for r in tr if r["date"] > bd or (r["date"] == bd and r["window"] == "pm"))
    win, pay = stats_of(closed)
    return dict(name="v44 (book)", ret=float(last["book_value"]) / b0 - 1, spy=float(last["spy_value"]) / s0 - 1, beta=beta(pairs), exp=exp, n=len(closed),
                win=win, pay=pay, costs=costs, asof=f"{last['date']} {last['note'][:2]}", V=float(last["book_value"]), approx_exp=True)
def verdict(r):
    if "note" in r: return "-"
    if r["name"] in RETIRED: return f"RETIRED Nov 14 (3-yr backtest: no edge); last session {RETIRED[r['name']]}"
    rpe = r["ret"] / r["exp"] if r["exp"] > 1e-9 else None; r["rpe"] = rpe; fails = []
    if rpe is None or r["spy"] is None or rpe <= r["spy"]: fails.append("risk-adj <= SPY")
    if r["ret"] <= 0: fails.append("return <= 0")
    if r["name"] == "runup":   # own bar set 2026-11-12 (the owner), before any runup trade: >= 8 round trips AND mean per-trade excess vs QQQ > 0; a pass = lead to keep running into January, NOT a capital winner
        fails = []
        if r["n"] < 8: fails.append(f"trades {r['n']}/8")
        if r.get("excess") is None or r["excess"] <= 0: fails.append("per-trade vs QQQ <= 0" if r.get("excess") is not None else "per-trade vs QQQ n/a")
        return ("LEAD so far (not a capital winner)" if not fails else "FAIL so far (" + "; ".join(fails) + ")") + ("" if r.get("excess") is None else f" [avg vs QQQ {100*r['excess']:+.2f}%]")
    if r["n"] < 40: fails.append(f"trades {r['n']}/40")
    return "PASS so far" if not fails else "FAIL so far (" + "; ".join(fails) + ")"
def score():
    try:
        spyd = [r for r in rotate.bars("SPY")]; ses = [r[0] for r in spyd if r[0] < TODAY] + ([TODAY] if dt.date.fromisoformat(TODAY).weekday() < 5 else [])
        prior = [r for r in spyd if r[0] < START]; spy_base = prior[-1][4] if prior else None
        rows = [score_book()] + [score_new(n, ses, spy_base) for n in NEW]
    except Exception as e:
        print(f"bake-off score unavailable: {e}"); return
    f = lambda x, k=100, d=2, sfx="%": "-" if x is None else f"{k*x:+.{d}f}{sfx}"
    print(f"Bake-off {START} to {END} (29 sessions, rules frozen; PAPER). Pass = return per unit of exposure beats SPY AND return > 0 AND >= 40 closed trades, all net of 0.05%/side. runup has its own bar (>= 8 round trips AND average per-trade return beats QQQ; a pass is a lead, not a capital winner).")
    print("| Sleeve | As of | Return | SPY | Beta | Avg exposure | Ret/exposure | vs SPY (pts) | Trades | Win % | Payoff | Costs $ | Verdict |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    LABEL = {"v44 (book)": "Main 24h", "rsi2": "Dip Buyer", "runup": "Earnings Run-Up"}   # display names only (owner, 2026-11-12); code keys unchanged
    for r in rows:
        v = verdict(r); r = dict(r, name=LABEL.get(r["name"], r["name"]))
        if "note" in r: print(f"| {r['name']} | - | - | - | - | - | - | - | - | - | - | - | {r['note']} |"); continue
        rpe = r.get("rpe")
        print(f"| {r['name']} | {r['asof']} | {f(r['ret'])} | {f(r['spy'])} | {'-' if r['beta'] is None else round(r['beta'], 2)} | "
              f"{('~' if r.get('approx_exp') else '')}{100*r['exp']:.0f}% | {f(rpe)} | {'-' if rpe is None or r['spy'] is None else f'{100*(rpe-r['spy']):+.2f}'} | "
              f"{r['n']} | {'-' if r['win'] is None else f'{100*r['win']:.0f}%'} | {'-' if r['pay'] is None else f'{r['pay']:.2f}x'} | {r['costs']:,.0f} | {v} |")
    print("Notes: v44 exposure is approximated from its level cap (FULL/HALF 100%, DEFENSIVE 50%); new sleeves' exposure is capital-weighted market-hours time in the market. Beta needs 3+ sessions.")

def status():
    for n in NEW:
        if not os.path.exists(os.path.join(DIR, n, "state.json")): print(f"[{n}] not started (${CASH0:,.0f} cash from {START})"); continue
        s = load(n); print(f"[{n}] cash ${s['cash']:,.2f} | holdings {[(h['ticker'], h['date']) for h in s['holdings']]} | settled {len(s['settled'])} | marked {s.get('marked')}")

if __name__ == "__main__":
    cmd = A[0] if A else "score"; w = A[1] if len(A) > 1 else None
    if cmd == "rsi2": rsi2(w or "pm")
    elif cmd == "orb": orb(w or "pm")
    elif cmd == "spymom": spymom(w or "am")
    elif cmd == "runup": runup(w or "pm")
    elif cmd == "mark": mark(w or ("am" if int(now_hm()[:2]) < 12 else "pm"))
    elif cmd == "score": score()
    elif cmd == "status": status()
    else: sys.exit(__doc__)
