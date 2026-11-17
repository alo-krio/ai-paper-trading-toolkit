"""Perplexity Decider (hosted Decisions API). Key injected by proxy for api.perplexity.ai.
Usage: python scripts/pplx_decide.py "headline" ...   (no args = the 4-headline test from kev_test.py)"""
import json, sys, time, urllib.request, os
sys.path.insert(0, os.path.dirname(__file__))
URL = "https://api.perplexity.ai/v1/decisions"; MODEL = "pplx-decider-latest"
H=["Oracle Stock Is Falling as AI Spending Worries Mount. Most Analysts Think ORCL Could Rebound",
"KR Stock Inches Higher On A $5B Investment Plan To Improve Value, Gather Market Share",
"Nvidia Stock Rises in Wednesday Premarket as Elon Musk Says SpaceX Is Adding 200,000 Chips",
"What Amazon must do to get its stumbling stock back to record highs and beyond"]
Q={"direction":{"type":"choice","instructions":"For the stock named in this headline, is the news good or bad for its price over the next two weeks?","criteria":{"bullish":"good for the stock","bearish":"bad for the stock","neutral":"no clear effect"}},
"event":{"type":"choice","instructions":"What kind of news is this?","criteria":{"earnings":"quarterly results","guidance":"company outlook","analyst_rating":"analyst upgrade, downgrade or target","capital_plan":"buyback, dividend or investment plan","customer_or_contract":"a customer order, deal or contract","legal_regulatory":"lawsuit, regulation or probe","macro_sector":"industry or economy-wide worry or trend","opinion":"commentary or recap with no new facts"}},
"material":{"type":"noul","instructions":"Is this new information likely to move the stock more than 2%?"}}
def decide(text, questions=Q):
    body = json.dumps({"model": MODEL, "state": {"headline": text}, "questions": questions}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json", "Authorization": "Bearer " + __import__("os").environ["PERPLEXITY_API_KEY"]})
    return json.load(urllib.request.urlopen(req, timeout=60))
if __name__ == "__main__":
    for h in (sys.argv[1:] or H):
        t = time.time(); r = decide(h)
        print(f"{time.time()-t:.2f}s", h[:60]); print(json.dumps(r, indent=1)[:1500])
