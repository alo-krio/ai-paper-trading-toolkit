#!/usr/bin/env python3
"""Per-trade review for Main 24h (PAPER). For every closed long in book/positions.csv: return, excess vs SPY over the hold,
best intraday high and best close AFTER the entry day, giveback, worst low, and the play tag from the buy reason.
Writes notes/trade_journal.csv (agent adds grade/lesson columns by hand in the evening window) and prints a summary.
Usage: python3 scripts/trade_review.py [--since YYYY-MM-DD]"""
import csv, json, os, sys, re, statistics as S
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else '0000'
spy = {r[0]: r[4] for r in json.load(open('data/ohlcv/SPY.json'))}
def sp(d):
    k = [x for x in spy if x <= d]; return spy[max(k)] if k else None
old = {}
if os.path.exists('notes/trade_journal.csv'):
    for r in csv.DictReader(open('notes/trade_journal.csv')): old[(r['ticker'], r['bought'])] = r
rows = []
for p in csv.DictReader(open('book/positions.csv')):
    t = p['ticker']
    if t == 'SGOV' or 'short' in t or p['bought'] < since: continue
    f = f'data/ohlcv/{t}.json'; bars = [r for r in json.load(open(f)) if p['bought'] < r[0] <= p['date']] if os.path.exists(f) else []
    bp = float(p['buy_price']); ret = 100 * float(p['ret'])
    s0, s1 = sp(p['bought']), sp(p['date']); ex = ret - 100 * (s1 / s0 - 1) if s0 and s1 else ''
    pk = 100 * (max(b[2] for b in bars) / bp - 1) if bars else ''; bc = 100 * (max(b[4] for b in bars) / bp - 1) if bars else ''
    lo = 100 * (min(b[3] for b in bars) / bp - 1) if bars else ''
    m = re.search(r'PLAY\s*:\s*([A-Za-z0-9_]+)', p['reason']); play = m.group(1) if m else ''
    mc = re.search(r'CONVICTION\s*:\s*([1-5])', p['reason']); conv = mc.group(1) if mc else ''
    mp = re.search(r'P_BEAT\s*:\s*(\d+)', p['reason']); pbeat = mp.group(1) if mp else ''
    o = old.get((t, p['bought']), {})
    rows.append(dict(ticker=t, bought=p['bought'], sold=p['date'], ret=round(ret, 2), excess_spy=round(ex, 2) if ex != '' else '',
                     best_high_after=round(pk, 2) if pk != '' else '', best_close_after=round(bc, 2) if bc != '' else '',
                     worst_low_after=round(lo, 2) if lo != '' else '', conviction=conv, p_beat=pbeat, giveback=round(pk - ret, 2) if pk != '' else '', play=play or o.get('play', ''),
                     category=o.get('category', ''), grade=o.get('grade', ''), lesson=o.get('lesson', ''), reason=p['reason'][:200]))
keys = list(rows[0]) if rows else []
with open('notes/trade_journal.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
if rows:
    e = [r['excess_spy'] for r in rows if r['excess_spy'] != '']
    print(f"TRADE REVIEW: {len(rows)} closed longs | avg ret {S.mean(r['ret'] for r in rows):+.2f}% | avg excess vs SPY {S.mean(e):+.2f} | beat SPY {sum(x>0 for x in e)}/{len(e)}")
    up = [r for r in rows if r['best_high_after'] != '' and r['best_high_after'] >= 4]
    if up: print(f"  reached +4% after entry day: {len(up)} | avg peak {S.mean(r['best_high_after'] for r in up):+.1f}% | avg exit {S.mean(r['ret'] for r in up):+.2f}% (giveback)")
    cats = {}
    for r in rows: cats.setdefault(r['category'] or r['play'] or 'untagged', []).append(r)
    for k, v in sorted(cats.items()):
        ee = [x['excess_spy'] for x in v if x['excess_spy'] != '']
        print(f"  {k:28s} n={len(v):2d} avg excess {S.mean(ee) if ee else 0:+.2f} beat {sum(x>0 for x in ee)}/{len(ee)}")
    cal = [r for r in rows if r['p_beat'] and r['excess_spy'] != '']
    if cal:
        br = S.mean((int(r['p_beat'])/100 - (1 if r['excess_spy'] > 0 else 0))**2 for r in cal)
        print(f"  CALIBRATION n={len(cal)} Brier {br:.3f} (0.25 = coin flip; lower is better)")
        for c in '12345':
            v = [r for r in cal if r['conviction'] == c]
            if v: print(f"    conviction {c}: n={len(v)} avg excess {S.mean(r['excess_spy'] for r in v):+.2f} beat {sum(r['excess_spy']>0 for r in v)}/{len(v)} avg P_BEAT {S.mean(int(r['p_beat']) for r in v):.0f}%")
    print('  ungraded:', ', '.join(f"{r['ticker']} {r['bought']}" for r in rows if not r['grade']) or 'none')
