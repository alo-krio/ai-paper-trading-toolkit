#!/usr/bin/env python3
"""Price source without Yahoo (Yahoo spark/chart 429s from this host, Oct 2026).
history(t) -> {date: close} for ~1y of daily closes, INCLUDING today's bar:
  - during the session (9:30-16:00 ET) today's bar = live last price (so a 3:15 PM run sees the real current price)
  - after the close = today's regular-session close
US stocks/ETFs: api.nasdaq.com (historical + info). TSX (.TO): app-money.tmx.com GraphQL.
Index/futures symbols (^VIX, ^TNX, BZ=F, CL=F, DX-Y.NYB...) fall back to Yahoo chart (may 429).
live(t) -> (price, timestamp_str) current price only.
"""
import json, subprocess, time, datetime as dt
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
_cache, _cls = {}, {}

def _curl_via_urllib(args, tries=3):
    """Nov 16, 2026: inside py.sh, curl subprocesses fail (HTTP 000); urllib goes through the platform shim instead,
    which is the platform's intended path for public hosts. Same contract as _curl: parsed JSON or None."""
    import urllib.request
    hdrs, url, i = {"User-Agent": UA}, None, 0
    while i < len(args):
        if args[i] == "-H": k, _, v = args[i + 1].partition(":"); hdrs[k.strip()] = v.strip(); i += 2
        elif args[i] == "-d": i += 2
        else: url = args[i]; i += 1
    for j in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=20).read())
        except Exception:
            time.sleep(1.5 * (j + 1))
    return None

def _curl(args, tries=3):
    import os
    if os.environ.get("PPLX_PROXY_HOSTS") and "-d" not in args: return _curl_via_urllib(args, tries)
    for i in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "20", "-A", UA, "-w", "\n%{http_code}"] + args, capture_output=True)
        body, _, code = r.stdout.rpartition(b"\n")
        if code == b"200":
            try: return json.loads(body)
            except Exception: pass
        time.sleep(1.5 * (i + 1))
    return None

def _num(s):
    try: return float(str(s).replace("$", "").replace(",", ""))
    except Exception: return None

def _now(): return dt.datetime.now(ET)

def _session_state():
    n = _now()
    if n.weekday() >= 5: return "closed"
    t = n.hour * 60 + n.minute
    return "pre" if t < 570 else ("open" if t < 960 else "post")

def _nasdaq_sym(t): return t.replace("-", ".")

def _nasdaq_hist(t):
    s = _nasdaq_sym(t); frm = (_now().date() - dt.timedelta(days=400)).isoformat(); to = _now().date().isoformat()
    for cls in ([_cls[t]] if t in _cls else ["stocks", "etf"]):
        d = _curl(["-H", "Accept: application/json",
                   f"https://api.nasdaq.com/api/quote/{s}/historical?assetclass={cls}&fromdate={frm}&todate={to}&limit=400"])
        rows = (((d or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
        if rows:
            _cls[t] = cls
            out = {}
            for r in rows:
                c = _num(r.get("close"))
                if c: out[dt.datetime.strptime(r["date"], "%m/%d/%Y").date()] = c
            return out
    return {}

def _nasdaq_live(t):
    if alpaca_first():
        p, ts = alpaca_live(t)
        if p: return p, ts
    cls = _cls.get(t, "stocks")
    for c in [cls] + (["etf"] if cls == "stocks" else []):
        d = _curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/quote/{_nasdaq_sym(t)}/info?assetclass={c}"])
        data = (d or {}).get("data") or {}
        if data.get("primaryData"):
            st = _session_state()
            p, s = data.get("primaryData") or {}, data.get("secondaryData") or {}
            # after hours: primary = extended-hours trade, secondary = regular close
            src = s if (st == "post" and s.get("lastSalePrice")) else p
            return _num(src.get("lastSalePrice")), src.get("lastTradeTimestamp")
    return alpaca_live(t)

# Nov 16, 2026 fix (Owner: "fix the errors, use Alpaca if needed"): inside py.sh the curl subprocess to api.nasdaq.com
# fails (HTTP 000 through the credential proxy), which broke live quotes, rotate.py mark/review and daily bars.
# Fallback: Alpaca market data via urllib (py.sh routes data.alpaca.markets through the credential proxy).
# Live = IEX latest trade (real time); daily bars = SIP (completed sessions), split-adjusted like Nasdaq's closes.
def _alpaca_get(path, q):
    import os, urllib.request, urllib.parse
    k, sec = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not k or not sec: return None
    try:
        req = urllib.request.Request("https://data.alpaca.markets" + path + "?" + urllib.parse.urlencode(q),
                                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": sec})
        return json.load(urllib.request.urlopen(req, timeout=30))
    except Exception:
        return None

def _alpaca_sym(t): return t.replace("-", ".")

def alpaca_first():
    """True inside py.sh (Alpaca credentials injected, Nasdaq curl blocked): try Alpaca before Nasdaq."""
    import os
    return "data.alpaca.markets" in os.environ.get("PPLX_PROXY_HOSTS", "") and bool(os.environ.get("APCA_API_KEY_ID"))

def alpaca_live(t):
    d = _alpaca_get(f"/v2/stocks/{_alpaca_sym(t)}/trades/latest", {"feed": "iex"})
    tr = (d or {}).get("trade") or {}
    if tr.get("p"):
        ts = dt.datetime.fromisoformat(tr["t"][:19]).replace(tzinfo=dt.timezone.utc).astimezone(ET)
        return float(tr["p"]), ts.strftime("%b %d, %Y %-I:%M %p ET") + " (alpaca iex)"
    return None, None

def alpaca_bars(t, days=400):
    """[[date, open, high, low, close, volume], ...] completed daily bars, oldest first."""
    start = (_now().date() - dt.timedelta(days=days)).isoformat()
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, tok = [], None
    for _ in range(5):
        q = {"timeframe": "1Day", "start": start, "end": end, "limit": 10000, "adjustment": "split", "feed": "sip"}
        if tok: q["page_token"] = tok
        d = _alpaca_get(f"/v2/stocks/{_alpaca_sym(t)}/bars", q)
        if not d: break
        for b in d.get("bars") or []:
            day = dt.datetime.fromisoformat(b["t"][:19]).replace(tzinfo=dt.timezone.utc).astimezone(ET).date()
            rows.append([day.isoformat(), b["o"], b["h"], b["l"], b["c"], b["v"]])
        tok = d.get("next_page_token")
        if not tok: break
    today = _now().date().isoformat()
    return [r for r in rows if r[0] < today or _session_state() == "post"]

def _tmx_sym(t): return t[:-3].replace("-", ".")

def _tmx(query, variables, op):
    return _curl(["-H", "Content-Type: application/json", "-H", "Origin: https://money.tmx.com",
                  "-H", "Referer: https://money.tmx.com/", "https://app-money.tmx.com/graphql",
                  "-d", json.dumps({"operationName": op, "variables": variables, "query": query})])

def _tmx_hist(t):
    import re
    q = ("query getTimeSeriesData($symbol: String!, $freq: String, $interval: Int, $start: String, $end: String, $startDateTime: Int, $endDateTime: Int) "
         "{ getTimeSeriesData(symbol: $symbol, freq: $freq, interval: $interval, start: $start, end: $end, startDateTime: $startDateTime, endDateTime: $endDateTime) { dateTime close } }")
    v = {"symbol": _tmx_sym(t), "freq": "day", "start": (_now().date() - dt.timedelta(days=400)).isoformat(), "end": _now().date().isoformat()}
    d = _tmx(q, v, "getTimeSeriesData")
    rows = ((d or {}).get("data") or {}).get("getTimeSeriesData") or []
    out = {}
    for r in rows:
        m = re.search(r"\d{4}-\d{2}-\d{2}", str(r.get("dateTime")))
        if m and r.get("close"): out[dt.date.fromisoformat(m.group())] = r["close"]
    return out

def _tmx_live(t):
    q = "query getQuoteBySymbol($symbol: String, $locale: String) { getQuoteBySymbol(symbol: $symbol, locale: $locale) { symbol price prevClose } }"
    d = _tmx(q, {"symbol": _tmx_sym(t), "locale": "en"}, "getQuoteBySymbol")
    r = ((d or {}).get("data") or {}).get("getQuoteBySymbol") or {}
    return r.get("price"), _now().strftime("%Y-%m-%d %H:%M ET")

def _yahoo_hist(t):
    for h in ("query2", "query1"):
        d = _curl([f"https://{h}.finance.yahoo.com/v8/finance/chart/{t}?range=1y&interval=1d"], tries=2)
        try:
            res = d["chart"]["result"][0]; out = {}
            for ts, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
                if c is not None: out[dt.datetime.fromtimestamp(ts, ET).date()] = c
            return out
        except Exception: continue
    return {}

def is_tsx(t): return t.endswith(".TO")
def is_yahoo_only(t): return t.startswith("^") or "=" in t or t.endswith(".NYB")

def live(t):
    if is_tsx(t): return _tmx_live(t)
    if is_yahoo_only(t):
        h = history(t); return (h[max(h)], "yahoo") if h else (None, None)
    return _nasdaq_live(t)

CACHE_DIR = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))), "data", "prices")

def _prev_weekday(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d

def _load(t):
    import os
    f = os.path.join(CACHE_DIR, t.replace("^", "_").replace("=", "_") + ".json")
    try: return f, {dt.date.fromisoformat(k): v for k, v in json.load(open(f)).items()}
    except Exception: return f, {}

def _save(f, data):
    import os
    os.makedirs(CACHE_DIR, exist_ok=True)
    keep = sorted(data)[-300:]
    json.dump({d.isoformat(): data[d] for d in keep}, open(f, "w"))

def history(t):
    """Cached daily closes (data/prices/<t>.json, completed days only) + today's live/close bar.
    Normal day: 0 history calls, 1 live call per ticker. Full ~1y fetch only when the cache is missing/stale."""
    if t in _cache: return _cache[t]
    today = _now().date(); st = _session_state()
    if is_yahoo_only(t):
        out = _yahoo_hist(t); _cache[t] = out; return out
    f, cached = _load(t)
    last_done = today if st == "post" else _prev_weekday(today)  # newest completed session we expect
    have = max(cached) if cached else None
    if not cached or len(cached) < 210 or have < last_done or _prev_weekday(today) not in cached:  # Nov 16 gap fix
        fresh = {} if (alpaca_first() and not is_tsx(t)) else (_tmx_hist(t) if is_tsx(t) else _nasdaq_hist(t))
        if not fresh and not is_tsx(t):
            fresh = {dt.date.fromisoformat(r[0]): r[4] for r in alpaca_bars(t)}
        if fresh:
            cached.update({d: c for d, c in fresh.items() if d < today or st == "post"})
    out = dict(cached)
    if st in ("open", "post") and (today not in out or st == "open"):
        p, _ = live(t)
        if p: out[today] = p
    # persist completed sessions only (today's bar only after the close)
    persist = {d: c for d, c in out.items() if d < today or st == "post"}
    if persist: _save(f, persist)
    _cache[t] = out
    return out

if __name__ == "__main__":
    import sys
    for t in sys.argv[1:] or ["AAPL", "SPY", "BRK-B", "RY.TO", "TECK-B.TO", "XIU.TO"]:
        h = history(t)
        if h: d = max(h); print(t, len(h), d, h[d], "live:", live(t))
        else: print(t, "NO DATA")
