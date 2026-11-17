#!/usr/bin/env python3
"""v5 news-first learning score (Nov 13, 2026 strategy review). Read-only.
Joins closed positions (book/positions.csv) to their BUY reason (book/trades.csv; the why.json line) and scores
by story TYPE, by RIPPLE (first-order vs read-through) and by MOVED bucket (how much of the story's move was
already in the price at entry). Net of the book's 0.05%/side cost already in 'ret'. Judge a TYPE at 30+ closed.
Usage: python3 scripts/story_score.py [--since 2026-11-13]"""
import csv, os, re, sys, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else '2026-11-13'
buys = {}
for r in csv.DictReader(open('book/trades.csv')):
    if r['side'] in ('BUY', 'SHORT'): buys[(r['ticker'], r['date'])] = r.get('reason', '')
def field(why, key):
    m = re.search(key + r'\s*:\s*([^|]+)', why, re.I); return m.group(1).strip() if m else ''
def bucket(moved):
    m = re.search(r'(-?\d+(?:\.\d+)?)\s*%', moved or '')
    if not m: return 'moved n/a'
    v = abs(float(m.group(1))); return 'moved <2%' if v < 2 else 'moved 2-5%' if v < 5 else 'moved >5%'
rows = []
for p in csv.DictReader(open('book/positions.csv')):
    if p.get('bought', '') < since or p['ticker'] in ('SGOV', 'SPY'): continue
    why = buys.get((p['ticker'], p['bought']), '')
    typ = (field(why, 'TYPE').split()[0].lower().strip('.,;') if field(why, 'TYPE') else 'untyped')
    rip = 'read-through' if re.search(r'read-?through|ripple|->', field(why, 'RIPPLE'), re.I) and 'first-order' not in field(why, 'RIPPLE').lower() else 'first-order'
    rows.append(dict(t=p['ticker'], ret=100 * float(p['ret']), type=typ, rip=rip, mv=bucket(field(why, 'MOVED'))))
def st(xs):
    n = len(xs)
    if not n: return 'n=0'
    m = sum(xs) / n; sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0
    w = [x for x in xs if x > 0]; l = [x for x in xs if x <= 0]
    pay = (sum(w) / len(w)) / abs(sum(l) / len(l)) if w and l and sum(l) else float('nan')
    return f"n={n:3d} avg {m:+.2f}% win {100 * len(w) / n:3.0f}% payoff {pay:.2f}x t {m / (sd / math.sqrt(n)) if n > 1 and sd else 0:+.1f}"
print(f"# v5 story score since {since} (closed positions; judge a group at 30+)")
print("All     ", st([r['ret'] for r in rows]))
for key, lab in (('type', 'TYPE'), ('rip', 'RIPPLE'), ('mv', 'MOVED')):
    g = {}
    for r in rows: g.setdefault(r[key], []).append(r['ret'])
    for k in sorted(g, key=lambda k: -len(g[k])): print(f"{lab:7s} {k:14s}", st(g[k]))
