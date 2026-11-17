#!/usr/bin/env python3
"""SILENT intraday AI-call test (owner, Oct 22, 2026, after an Instagram reel of an AI scalping Nasdaq futures). PAPER/LOG ONLY, never traded.
QQQ stands in for Nasdaq futures. Each weekday ~9:50 AM ET the Perplexity Decider sees the setup (gap, first 15-20 min move, trend, top market
headlines) and calls the rest of the session: up / down / flat. Scored at the 3:30 PM ET sell with the live QQQ price.
  python3 scripts/aicall.py call    -> logs data/side/aicall.csv
  python3 scripts/aicall.py score   -> fills today's exit, prints hit rate and the call's cumulative return vs always-long"""
import os, sys, csv, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "scripts")
import rotate
F = "data/side/aicall.csv"; COLS = ["date", "time", "entry", "p_up", "p_down", "p_flat", "call", "exit", "ret", "call_ret"]
URL = "https://api.perplexity.ai/v1/decisions"
def heads(n=8):
    q = urllib.parse.quote("stock market today when:1d")
    raw = urllib.request.urlopen(urllib.request.Request(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
    return [i.findtext("title").rsplit(" - ", 1)[0] for i in ET.fromstring(raw).iter("item")][:n]
def rows(): return list(csv.DictReader(open(F))) if os.path.exists(F) else []
def save(rs):
    with open(F, "w", newline="") as f: w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rs)
def call():
    d = str(rotate.today()); rs = [r for r in rows() if r["date"] != d]
    b = [x for x in rotate.bars("QQQ") if x[0] < d]; cl = [x[4] for x in b]
    p, ts = rotate.live("QQQ"); o = None
    state = {"instrument": "QQQ (Nasdaq-100 ETF), as a stand-in for Nasdaq futures", "time_now": ts, "price_now": round(p, 2),
             "prior_close": cl[-1], "move_since_prior_close_pct": round(100 * (p / cl[-1] - 1), 2),
             "last_5_days_pct": round(100 * (cl[-1] / cl[-6] - 1), 2), "vs_20_day_avg_pct": round(100 * (cl[-1] / (sum(cl[-20:]) / 20) - 1), 2),
             "headlines": heads()}
    qs = {"call": {"type": "choice", "instructions": "You are an intraday trader. From now until 3:30 PM ET today, will QQQ end higher than the current price by more than 0.2%, lower by more than 0.2%, or within 0.2%?",
                   "criteria": {"up": "higher by more than 0.2%", "down": "lower by more than 0.2%", "flat": "within 0.2% either way"}}}
    body = json.dumps({"model": "pplx-decider-latest", "state": state, "questions": qs}).encode()
    a = json.load(urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json", "Authorization": "Bearer " + __import__("os").environ["PERPLEXITY_API_KEY"]}), timeout=60))["answers"]["call"]
    pr = a["probabilities"]
    rs.append(dict(date=d, time=ts, entry=round(p, 4), p_up=round(pr["up"], 3), p_down=round(pr["down"], 3), p_flat=round(pr["flat"], 3), call=a["choice"], exit="", ret="", call_ret=""))
    save(rs); print(f"AI CALL {d}: {a['choice']} (up {pr['up']:.2f} / down {pr['down']:.2f} / flat {pr['flat']:.2f}) QQQ {p:.2f} @ {ts}")
def score(fill=True):
    rs = rows(); d = str(rotate.today())
    for r in (rs if fill else []):
        if r["date"] == d and not r["exit"]:
            p, _ = rotate.live("QQQ"); r["exit"] = round(p, 4); ret = p / float(r["entry"]) - 1
            r["ret"] = round(ret, 5); r["call_ret"] = round({"up": 1, "down": -1}.get(r["call"], 0) * ret, 5)
    if fill: save(rs)
    done = [r for r in rs if str(r["ret"]) != ""]
    if not done: print("AI CALL: no scored days yet"); return
    dirc = [r for r in done if r["call"] != "flat"]
    hit = sum(float(r["call_ret"]) > 0 for r in dirc) / len(dirc) if dirc else 0
    print(f"AI CALL {len(done)} days | hit {100*hit:.0f}% on {len(dirc)} up/down calls | cum call {100*sum(float(r['call_ret']) for r in done):+.2f}% vs always-long {100*sum(float(r['ret']) for r in done):+.2f}% (QQQ 9:50->3:30, no costs)")
if __name__ == "__main__": {"call": call, "score": score, "summary": lambda: score(False)}[sys.argv[1]]()
