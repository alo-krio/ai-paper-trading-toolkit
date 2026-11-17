"""One-off 12-month check of the runup sleeve's frozen filters on the research data (RESEARCH ONLY, no trades, no tuning).
Data: research/earnings_runup/out/events_enriched.csv (387 NDX events Nov 2025-Nov 2026, Benzinga timing) + data/bars.csv (SIP daily, adj=all).
Rules as in sleeves/README.md "5. runup", with these approximations (daily data only):
  - entry at the CLOSE 5 sessions before the last pre-report close (live: 15:45 IEX price); exit at the last pre-report close (live: 15:30 bar);
  - stop entry - 2 x ATR14 checked on daily closes; hold-through half exits at the next OPEN (live: 9:45 bar);
  - universe and peers = current Nasdaq-100 only (live: S&P 500 + NDX, so far more peers); sectors from S&P GICS, else the Nasdaq screener;
  - filter (e) headlines/8-K NOT tested; beat history = research 'beats4' (prior 4 Nasdaq-calendar surprises, needs 4 observed);
  - SPY 200DMA gate only where 200 bars exist (bars start Mar 2025, so the gate is open by default before ~Dec 17, 2025).
Writes out/runup_sleeve_check.md. Run: python3 research/earnings_runup/runup_sleeve_check.py
"""
import os, sys, csv, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts")); os.chdir(ROOT)
COST = 0.0005
B = {}
for r in csv.DictReader(open(f"{HERE}/data/bars.csv")):
    B.setdefault(r["symbol"], []).append((r["date"], float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"])))
for s in B: B[s].sort()
ses = [x[0] for x in B["SPY"]]; IX = {d: i for i, d in enumerate(ses)}
def row(t, d):
    for x in B.get(t, []):
        if x[0] == d: return x
def hist(t, d):  # rows strictly before d
    return [x for x in B.get(t, []) if x[0] < d]
import screen, rotate
sp = screen.sp500()
try: scr = rotate.universe()
except Exception: scr = {}
ev = list(csv.DictReader(open(f"{HERE}/out/events_enriched.csv")))
SEC = {e["symbol"]: sp.get(e["symbol"]) or scr.get(e["symbol"]) or "Other" for e in ev}
for e in ev:   # reaction close date per timing
    e["L"] = e["pre_close_date"]; e["rc"] = float(e["react_close"]) if e["react_close"] else None
out, blocks = [], {}
cand = []
for e in ev:
    L = e["L"]
    if L not in IX or IX[L] < 5: continue
    E = ses[IX[L] - 5]; t = e["symbol"]; df = hist(t, E); er = row(t, E); b = []
    if not er or len(df) < 51: b.append("data_missing")
    else:
        p = er[4]; cl = [x[4] for x in df]; adv = sum(x[4] * x[5] for x in df[-20:]) / 20
        if p < 10 or adv < 50e6: b.append("liquidity")
        spy = [x[4] for x in hist("SPY", E)]
        if len(spy) >= 200 and spy[-1] <= sum(spy[-200:]) / 200: b.append("spy_below_200dma")
        peers = [x for x in ev if x["symbol"] != t and SEC[x["symbol"]] == SEC[t] and x["date"] in IX and IX[E] - 10 <= IX[x["date"]] < IX[E]
                 and x["react_date"] in IX and x["react_date"] < E and x["rc"] is not None]
        pr = sum(x["rc"] for x in peers) / len(peers) if len(peers) >= 2 else None
        if pr is None: b.append("peer_too_few")
        elif pr <= 0: b.append("peer_readthrough")
        s50 = sum((cl + [p])[-50:]) / 50; qc = [x[4] for x in hist("QQQ", E)]; qp = row("QQQ", E)[4]
        r20 = p / cl[-20] - 1; rs = r20 - (qp / qc[-20] - 1); r10 = p / cl[-10] - 1
        if p <= s50: b.append("below_50dma")
        if rs < 0: b.append("weak_rs")
        if r10 > 0.08: b.append("chasing")
        if e["beats4"] == "" or int(e["nbeat_obs"] or 0) < 4 or float(e["beats4"]) < 3: b.append("beat_history")
        a14 = sum(max(df[i][2], df[i - 1][4]) - min(df[i][3], df[i - 1][4]) for i in range(-14, 0)) / 14
    if b: blocks[b[0]] = blocks.get(b[0], 0) + 1; continue
    cand.append(dict(t=t, E=E, L=L, p=p, pr=pr, rs=rs, stop=p - 2 * a14, sec=SEC[t], beats=float(e["beats4"]), e=e))
# portfolio: max 5 open, max 2 per sector, 20% each; rank by peer read-through then RS within an entry day
cand.sort(key=lambda c: (c["E"], -c["pr"], -c["rs"])); openp = []; trades = []; skipped_cap = 0
for c in cand:
    openp = [o for o in openp if o["exit_d"] > c["E"]]
    if len(openp) >= 5 or sum(1 for o in openp if o["sec"] == c["sec"]) >= 2: skipped_cap += 1; continue
    t = c["t"]; xd, xp, why = c["L"], row(t, c["L"])[4], "pre-report"
    for d in ses[IX[c["E"]] + 1: IX[c["L"]] + 1]:
        x = row(t, d)
        if x and x[4] < c["stop"]: xd, xp, why = d, x[4], "stop"; break
    g = xp / c["p"] - 1; r = (1 - COST) * (xp / c["p"]) * (1 - COST) - 1
    ht = why == "pre-report" and c["beats"] == 4 and c["pr"] >= 0.02 and g <= 0.05
    if ht:
        nx = row(t, c["e"]["react_date"]); r2 = (1 - COST) * (nx[1] / c["p"]) * (1 - COST) - 1 if nx else r
        r = 0.5 * r + 0.5 * r2; xd = c["e"]["react_date"]
    c.update(exit_d=xd, ret=r, why="hold-through" if ht else why); openp.append(c); trades.append(c)
R = [c["ret"] for c in trades]
allbase = [float(e["ru5"]) - 2 * COST for e in ev if e["ru5"]]   # every event, same 5-session window, no filters
qqq = [float(e["xq5"]) for e in ev if e["xq5"]]
def tstat(x): return st.mean(x) / (st.stdev(x) / len(x) ** 0.5) if len(x) > 2 and st.stdev(x) else float("nan")
xq = []
for c in trades:
    q0 = row("QQQ", c["E"])[4]; q1 = row("QQQ", c["exit_d"])[4]; xq.append(c["ret"] - (q1 / q0 - 1))
L_ = [f"# runup sleeve filters, 12-month check on NDX research data (as-is, no tuning)", "",
      f"Events: {len(ev)} | passed every tested filter: {len(cand)} | taken after the 5-position / 2-per-sector caps: {len(trades)} (cap-skipped {skipped_cap})",
      f"First block counts: {dict(sorted(blocks.items(), key=lambda kv: -kv[1]))}", "",
      "| set | n | mean net | median | win % | t | mean minus QQQ same span |", "|---|---|---|---|---|---|---|"]
if R: L_.append(f"| runup filters (taken) | {len(R)} | {100*st.mean(R):+.2f}% | {100*st.median(R):+.2f}% | {100*sum(r>0 for r in R)/len(R):.0f}% | {tstat(R):.2f} | {100*st.mean(xq):+.2f}% |")
L_.append(f"| all events, 5-session run-up, no filters | {len(allbase)} | {100*st.mean(allbase):+.2f}% | {100*st.median(allbase):+.2f}% | {100*sum(r>0 for r in allbase)/len(allbase):.0f}% | {tstat(allbase):.2f} | - |")
L_.append(""); L_.append(f"Exits: {dict((w, sum(1 for c in trades if c['why']==w)) for w in ('pre-report','stop','hold-through'))}")
L_.append(""); L_.append("Trades: " + ", ".join(f"{c['t']} {c['E']}->{c['exit_d']} {100*c['ret']:+.1f}%" for c in trades))
open(f"{HERE}/out/runup_sleeve_check.md", "w").write("\n".join(L_) + "\n"); print("\n".join(L_))
