"""Company-news check with Perplexity Decider (hosted Decisions API, key injected for api.perplexity.ai).
the owner, Oct 21, 2026. Headlines: Google News RSS, last 2 days. Each headline is asked: is it about this company,
direction (bullish/bearish/neutral, ~2 weeks), event type, and is it material (>2% move).
Per ticker: news_score = mean over relevant headlines of (p_bull - p_bear) * p_material, scaled x10 (range ~ -10..+10);
red_flag = any relevant headline with p_bear >= 0.6 and p_material >= 0.5.
Usage: python3 scripts/news_check.py --tag premarket|picks|close [--top N] [TICKERS...]
  no tickers: open picks (+ top N of today's screen by score if --top). Writes data/news/YYYY-MM-DD-<tag>.csv
Cost ~300 input tokens per headline at $0.02/M: negligible."""
import sys, csv, json, os, datetime, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
URL = "https://api.perplexity.ai/v1/decisions"; MODEL = "pplx-decider-latest"
UA = {"User-Agent": "Mozilla/5.0"}
EVENTS = {"earnings": "quarterly results", "guidance": "company outlook", "analyst_rating": "analyst upgrade, downgrade or price target",
 "capital_plan": "buyback, dividend, investment or financing plan", "customer_or_contract": "a customer order, deal or contract",
 "mna": "merger, acquisition or spin-off", "legal_regulatory": "lawsuit, regulation, tariff or probe", "management": "executive change",
 "product": "product launch, recall or outage", "macro_sector": "industry or economy-wide worry or trend",
 "opinion": "commentary, ranking or recap with no new facts"}
DAYS = 2
def news(t, n=12):
    q = urllib.parse.quote(f"{t} stock when:{DAYS}d")
    raw = urllib.request.urlopen(urllib.request.Request(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers=UA), timeout=20).read()
    bad = ("Stock Price, News, Quote", "stock price, news, quote", "Price & News", "Stock Quote")
    seen, out = set(), []
    for i in ET.fromstring(raw).iter("item"):
        h = i.findtext("title").rsplit(" - ", 1)[0]
        if any(b in h for b in bad) or h.lower() in seen: continue
        seen.add(h.lower()); out.append(h)
    return out[:n]
def decide(ticker, name, h):
    qs = {"about": {"type": "noul", "instructions": f"Is this headline mainly about {name} ({ticker}) itself, not just a passing mention or a list?"},
          "direction": {"type": "choice", "instructions": f"Is this news good or bad for {ticker}'s share price over the next two weeks?",
                        "criteria": {"bullish": "good for the stock", "bearish": "bad for the stock", "neutral": "no clear effect"}},
          "event": {"type": "choice", "instructions": "What kind of news is this?", "criteria": EVENTS},
          "material": {"type": "noul", "instructions": f"Is this new information likely to move {ticker} more than 2%?"}}
    body = json.dumps({"model": MODEL, "state": {"ticker": ticker, "company": name, "headline": h}, "questions": qs}).encode()
    for k in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json", "Authorization": "Bearer " + __import__("os").environ["PERPLEXITY_API_KEY"]}), timeout=60))["answers"]
            p = r["direction"]["probabilities"]
            return dict(h=h, about=r["about"]["noul"], bull=p["bullish"], bear=p["bearish"], event=r["event"]["choice"], material=r["material"]["noul"])
        except Exception as e:
            err = e; time.sleep(1.5 * (k + 1))
    return None
def names():
    m = {}
    for f in ("data/screen/%s.csv" % datetime.date.today(), "picks/picks.csv"):
        if os.path.exists(f):
            for r in csv.DictReader(open(f)): m.setdefault(r.get("ticker"), r.get("name") or r.get("ticker"))
    return m
def main():
    a = sys.argv[1:]; tag = "adhoc"; top = 0
    if "--tag" in a: i = a.index("--tag"); tag = a[i + 1]; del a[i:i + 2]
    global DAYS
    if "--days" in a: i = a.index("--days"); DAYS = int(a[i + 1]); del a[i:i + 2]  # Mondays: 3 to cover the weekend
    if "--top" in a: i = a.index("--top"); top = int(a[i + 1]); del a[i:i + 2]
    tick = a or sorted({r["ticker"] for r in csv.DictReader(open("picks/picks.csv")) if r["status"] == "open"})
    if top and not a:
        f = "data/screen/%s.csv" % datetime.date.today()
        if os.path.exists(f):
            rows = list(csv.DictReader(open(f))); key = "score" if "score" in rows[0] else list(rows[0])[-1]
            rows.sort(key=lambda r: -float(r.get(key) or -1e9))
            for r in rows[:top]:
                if r["ticker"] not in tick: tick.append(r["ticker"])
    nm = names(); jobs = []
    for t in tick:
        try: hs = news(t.replace(".TO", ""))
        except Exception: hs = []
        jobs += [(t, nm.get(t, t), h) for h in hs]
    with ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda j: (j[0], decide(*j)), jobs))
    out = []
    for t in tick:
        rs = [r for tt, r in res if tt == t and r]; rel = [r for r in rs if r["about"] >= 0.5]
        sc = round(10 * sum((r["bull"] - r["bear"]) * r["material"] for r in rel) / len(rel), 2) if rel else None
        flags = [r for r in rel if r["bear"] >= 0.6 and r["material"] >= 0.5]
        best = max(rel, key=lambda r: abs(r["bull"] - r["bear"]) * r["material"], default=None)
        out.append(dict(date=str(datetime.date.today()), tag=tag, ticker=t, headlines=len(rs), relevant=len(rel), news_score=sc,
                        red_flag=int(bool(flags)), flag_headline=(flags[0]["h"][:110] if flags else ""),
                        top_event=(best["event"] if best else ""), top_headline=(best["h"][:110] if best else "")))
    os.makedirs("data/news", exist_ok=True); f = f"data/news/{datetime.date.today()}-{tag}.csv"
    with open(f, "w", newline="") as o:
        w = csv.DictWriter(o, fieldnames=out[0].keys()); w.writeheader(); w.writerows(out)
    for r in sorted(out, key=lambda r: (r["news_score"] is None, r["news_score"] or 0)):
        print(f"{r['ticker']:7} score {r['news_score']!s:>6} rel {r['relevant']}/{r['headlines']} {'RED FLAG: ' + r['flag_headline'] if r['red_flag'] else ''} | {r['top_event']}: {r['top_headline']}")
    print("wrote", f, f"({len(jobs)} headlines)")
if __name__ == "__main__": main()
