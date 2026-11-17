"""Market-wide news check (owner, Oct 23, 2026): the risk dial is price-based and lags shocks, so each window
asks Perplexity Decider about the last ~12h of macro/geopolitical headlines (Google News RSS).
Per headline: market-wide? direction for US stocks over 1-2 sessions, material (>1% SPY move)?
macro_score = mean over market-wide headlines of (p_bull - p_bear) * p_material, x10 (about -10..+10).
SHOCK = 2+ market-wide headlines with p_bear >= 0.7 and p_material >= 0.6 AND macro_score <= -2 (one recap headline is not a shock) -> step the risk level down one for this window.
Usage: python3 scripts/macro_check.py [--hours 12]   writes data/news/YYYY-MM-DD-macro-<am|pm>.csv"""
import sys, csv, json, os, datetime, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
URL = "https://api.perplexity.ai/v1/decisions"; MODEL = "pplx-decider-latest"; UA = {"User-Agent": "Mozilla/5.0"}
QUERIES = ["stock market", "Federal Reserve", "Treasury yields", "tariffs trade", "oil prices", "geopolitical war sanctions", "Nasdaq futures"]
def heads(q, hours):
    u = f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:1d')}&hl=en-US&gl=US&ceid=US:en"
    out = []
    for i in ET.fromstring(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20).read()).iter("item"):
        try: t = datetime.datetime.strptime(i.findtext("pubDate"), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=datetime.timezone.utc)
        except Exception: continue
        if (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() <= hours * 3600:
            out.append((t, i.findtext("title").rsplit(" - ", 1)[0]))
    return out[:8]
def decide(h):
    qs = {"market": {"type": "noul", "instructions": "Is this headline about the US economy, markets, central banks, trade, energy or geopolitics broadly (not one company)?"},
          "direction": {"type": "choice", "instructions": "Is this news good or bad for US stocks over the next one or two trading sessions?",
                        "criteria": {"bullish": "good for stocks", "bearish": "bad for stocks", "neutral": "no clear effect"}},
          "material": {"type": "noul", "instructions": "Is this new information likely to move the S&P 500 more than 1%?"}}
    body = json.dumps({"model": MODEL, "state": {"headline": h}, "questions": qs}).encode()
    for _ in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json", "Authorization": "Bearer " + __import__("os").environ["PERPLEXITY_API_KEY"]}), timeout=60))["answers"]
            p = r["direction"]["probabilities"]
            return dict(h=h, market=r["market"]["noul"], bull=p["bullish"], bear=p["bearish"], material=r["material"]["noul"])
        except Exception: pass
if __name__ == "__main__":
    hours = float(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 12
    seen, hs = set(), []
    for q in QUERIES:
        try:
            for t, h in heads(q, hours):
                if h.lower() not in seen: seen.add(h.lower()); hs.append(h)
        except Exception as e: print("rss fail", q, e)
    with ThreadPoolExecutor(8) as ex: rs = [r for r in ex.map(decide, hs) if r]
    mk = [r for r in rs if r["market"] >= 0.5]
    score = round(10 * sum((r["bull"] - r["bear"]) * r["material"] for r in mk) / len(mk), 2) if mk else 0.0
    shocks = [r for r in mk if r["bear"] >= 0.7 and r["material"] >= 0.6]
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))
    os.makedirs("data/news", exist_ok=True)
    fn = f"data/news/{now:%Y-%m-%d}-macro-{'am' if now.hour < 12 else 'pm'}.csv"
    with open(fn, "w", newline="") as f:
        w = csv.DictWriter(f, ["h", "market", "bull", "bear", "material"]); w.writeheader(); w.writerows(rs)
    print(f"MACRO score {score:+} | headlines {len(rs)} (market-wide {len(mk)}) | SHOCK {'YES' if (len(shocks) >= 2 and score <= -2) else 'no'} (bear-material headlines {len(shocks)})")
    for r in sorted(mk, key=lambda r: -r["bear"] * r["material"])[:5]:
        print(f"  bear {r['bear']:.2f} mat {r['material']:.2f}  {r['h'][:110]}")
    print("file", fn)
