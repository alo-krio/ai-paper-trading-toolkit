#!/usr/bin/env python3
"""Nightly numbers in one cheap pass (token saver, Oct 17, 2026).
Run from project root (3:15 PM picks run or after the close; today's bar = live price intraday, close after 4 PM):
  python3 scripts/nightly.py --quote T1 T2 -> live price + timestamp (entry price for picks, logged at suggestion time)
  python3 scripts/nightly.py            -> fills blank entries, closes due picks (picks.csv and shadow.csv),
                                           prints risk dashboard + compact scorecard
  python3 scripts/nightly.py --shadow   -> also appends tonight's shadow picks (top 5 of today's screen
                                           not currently open in shadow.csv; run screen.py first)
Prices: scripts/prices.py (Nasdaq/TMX; Yahoo only for index/futures symbols). Prints only compact lines so the agent reads little.
"""
import csv, json, os, sys, subprocess, time, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
_cache = {}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # Nasdaq (US) + TMX (TSX) + Yahoo fallback for ^/=F symbols; includes today's live/close bar

def closes(t):
    if t not in _cache: _cache[t] = prices.history(t)
    return _cache[t]

def quote(tks):
    """--quote: live price + timestamp per ticker (the pick-time entry price, the owner Oct 19, 2026)."""
    for t in tks:
        p, ts = prices.live(t)
        print(f"QUOTE {t} {p if p is None else round(p, 2)} @ {ts}")

def on_or_after(series, day):
    ds = sorted(x for x in series if x >= day)
    return (ds[0], series[ds[0]]) if ds else (None, None)

def last(series):
    d = max(series); return d, series[d]

def pct(a, b): return 100*(a/b-1)

def process(path):
    if not os.path.exists(path): return []
    rows = list(csv.DictReader(open(path)))
    if not rows: return rows
    cols = list(rows[0].keys())
    spy, tq = closes("SPY"), closes("TQQQ")
    today = max(spy)
    for r in rows:
        pd = dt.date.fromisoformat(r["pick_date"])
        if not r["entry_close"]:
            c = closes(r["ticker"]).get(pd); r["entry_close"] = f"{c:.2f}" if c else ""
        if not r["spy_entry"] and pd in spy: r["spy_entry"] = f"{spy[pd]:.2f}"
        if not r.get("tqqq_entry") and pd in tq: r["tqqq_entry"] = f"{tq[pd]:.2f}"
        if r["status"] == "open" and dt.date.fromisoformat(r["target_date"]) <= today:
            xd, xc = on_or_after(closes(r["ticker"]), dt.date.fromisoformat(r["target_date"]))
            if xd:
                r["exit_close"] = f"{xc:.2f}"; r["spy_exit"] = f"{spy[xd]:.2f}"; r["tqqq_exit"] = f"{tq[xd]:.2f}"
                rr = pct(xc, float(r["entry_close"])); sr = pct(spy[xd], float(r["spy_entry"]))
                r["return_pct"] = f"{rr:.2f}"; r["spy_return_pct"] = f"{sr:.2f}"; r["excess_pct"] = f"{rr-sr:.2f}"
                r["status"] = "closed"; r["_closed_today"] = "1"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    return rows

def scorecard(rows, label):
    spy, tq = closes("SPY"), closes("TQQQ")
    _, spy_now = last(spy); _, tq_now = last(tq)
    closed = [r for r in rows if r["status"] == "closed" and r.get("thesis_tag") != "cash"]
    print(f"== {label} ==")
    for r in rows:
        if r.get("_closed_today"):
            print(f"CLOSED TODAY {r['ticker']} {r['pick_date']}: {float(r['return_pct']):+.2f}% vs SPY {float(r['spy_return_pct']):+.2f}% (excess {float(r['excess_pct']):+.2f})")
    if closed:
        ex = [float(r["excess_pct"]) for r in closed]
        print(f"closed n={len(closed)} hit-rate vs SPY {100*sum(e>0 for e in ex)/len(ex):.0f}% avg excess {sum(ex)/len(ex):+.2f}")
        tags = {}
        for r in closed: tags.setdefault(r["thesis_tag"], []).append(float(r["excess_pct"]))
        print("by tag: " + "; ".join(f"{k} n={len(v)} {sum(v)/len(v):+.2f}" for k, v in sorted(tags.items(), key=lambda x: -sum(x[1])/len(x[1]))))
    opn = [r for r in rows if r["status"] == "open" and r["entry_close"]]
    rets, beat_spy, beat_tq = [], 0, 0
    for r in opn:
        s = closes(r["ticker"])
        if not s: continue
        rr = pct(last(s)[1], float(r["entry_close"])); sr = pct(spy_now, float(r["spy_entry"])); tr = pct(tq_now, float(r["tqqq_entry"]))
        rets.append((r["ticker"], rr, sr, tr)); beat_spy += rr > sr; beat_tq += rr > tr
    if rets:
        n = len(rets)
        print(f"open n={n} beating SPY {beat_spy}/{n}, beating TQQQ {beat_tq}/{n}; eq-wt avg {sum(x[1] for x in rets)/n:+.2f}% vs SPY {sum(x[2] for x in rets)/n:+.2f}% vs TQQQ {sum(x[3] for x in rets)/n:+.2f}%")
        srt = sorted(rets, key=lambda x: x[1]-x[2])
        print("best vs SPY: " + ", ".join(f"{t} {r-s:+.2f}" for t, r, s, _ in srt[::-1][:3]))
        print("worst vs SPY: " + ", ".join(f"{t} {r-s:+.2f}" for t, r, s, _ in srt[:3]))

def dashboard():
    print("== DASHBOARD (last close, 1d %, vs 20dma %) ==")
    for t in ["SPY","QQQ","^IXIC","DIA","IWM","MDY","RSP","TQQQ","XLK","XLF","XLE","XLV","XLY","XLP","XLI","XLB","XLU","XLRE","XLC",
              "^TNX","BZ=F","CL=F","^VIX","DX-Y.NYB","HYG","LQD","SGOV"]:
        s = closes(t)
        if len(s) < 21: print(t, "n/a"); continue
        ds = sorted(s); c = s[ds[-1]]; p = s[ds[-2]]; sma20 = sum(s[d] for d in ds[-20:])/20
        print(f"{t:9} {ds[-1]} {c:.2f} {pct(c,p):+.2f}% vs20dma {pct(c,sma20):+.1f}%")
    h, l = closes("HYG"), closes("LQD")
    common = sorted(set(h) & set(l))
    if len(common) > 21:
        ratio = [h[d]/l[d] for d in common]
        print(f"CREDIT HYG/LQD ratio 5d {pct(ratio[-1], ratio[-6]):+.2f}% 20d {pct(ratio[-1], ratio[-21]):+.2f}%")

def add_shadow():
    today = max(closes("SPY")); sc = f"{ROOT}/data/screen/{today.isoformat()}.csv"
    if not os.path.exists(sc): print("no screen file for", today, "- run screen.py first"); return
    path = f"{ROOT}/picks/shadow.csv"
    cols = ["pick_date","ticker","sector","thesis_tag","entry_close","spy_entry","target_date","exit_close","spy_exit",
            "tqqq_entry","tqqq_exit","return_pct","spy_return_pct","excess_pct","status"]
    rows = list(csv.DictReader(open(path))) if os.path.exists(path) else []
    if any(r["pick_date"] == today.isoformat() for r in rows): print("shadow already logged today"); return
    openset = {r["ticker"] for r in rows if r["status"] == "open"}
    spy, tq = closes("SPY"), closes("TQQQ"); added = []; per_sector = {}
    for r in csv.DictReader(open(sc)):
        if r["ticker"] in openset or r["ticker"] in ("SPY", "RSP", "IWM"): continue
        if per_sector.get(r["sector"], 0) >= 2: continue
        per_sector[r["sector"]] = per_sector.get(r["sector"], 0) + 1
        added.append(dict(pick_date=today.isoformat(), ticker=r["ticker"], sector=r["sector"], thesis_tag="shadow-screen",
                          entry_close=r["close"], spy_entry=f"{spy[today]:.2f}", tqqq_entry=f"{tq[today]:.2f}",
                          target_date=(today+dt.timedelta(days=14)).isoformat(), status="open"))
        if len(added) == 5: break
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows + added)
    print("shadow added: " + ", ".join(a["ticker"] for a in added))

if __name__ == "__main__":
    if "--quote" in sys.argv:
        quote([a for a in sys.argv[1:] if not a.startswith("--")]); sys.exit()
    picks = process(f"{ROOT}/picks/picks.csv")
    shadow = process(f"{ROOT}/picks/shadow.csv")
    dashboard()
    scorecard(picks, "OUR PICKS")
    if shadow: scorecard(shadow, "SHADOW (plain screen top 5)")
    vetoes = process(f"{ROOT}/picks/vetoes.csv")
    if vetoes: scorecard(vetoes, "VETOED (dropped for news red flag)")
    if "--shadow" in sys.argv: add_shadow()
