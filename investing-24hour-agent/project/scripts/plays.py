#!/usr/bin/env python3
"""v6 PLAYBOOK LEARNING ENGINE (Main 24h, Nov 16 2026). PAPER ONLY, information only.
Logs every play signal in the liquid US universe (traded or not), scores each at d1/d3/d5 vs SPY net of 16 bp round trip,
and prints per-play stats plus a size multiplier. Usage:
  python3 scripts/plays.py update [--refresh]   # morning step: log yesterday's signals, score matured ones, print report
  python3 scripts/plays.py backfill             # seed the ledger from the cached ~1 year of bars (source=backfill)
  python3 scripts/plays.py report               # stats only
Plays (signals from daily bars; entry = signal-day close unless noted):
  A_strongclose  day >= +3%, relvol >= 2, close in top 20% of range      (hold 1-3 sessions)
  B_flush        day <= -5%, relvol >= 2, close above 200dma              (hold 3-5 sessions)
  B2_flush_any   same, close at or below 200dma (tests whether the uptrend filter helps)
  D_gapup        open gap >= +4%, relvol >= 2.5, close > open             (hold 1-5 sessions)
  G_gapdown_oc   open gap <= -3%, relvol >= 1.5; scored OPEN->CLOSE (negative = a gap-down dip-buy at the open loses)
Multiplier: n < 30 signals: 1.0 (learning). Else 1 + shrunk mean d3 net excess (pts, shrink n/(n+30)), clipped 0.5-2.0 (above 1.0 only when day-clustered t >= 1);
paused (0.0) if day-clustered t <= -1.5 at n >= 60. New plays added to PLAYS start in learning."""
import os, sys, glob, json, csv, math, datetime as dt
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, 'scripts')
COST = 0.16; LEDGER = 'shadow/plays.csv'
def load(refresh=False):
    import ohlcv
    fr = []
    for f in glob.glob('data/ohlcv/*.json'):
        t = os.path.basename(f)[:-5]
        if refresh and t != 'SPY' and False: pass
        try: r = json.load(open(f))
        except Exception: continue
        if len(r) < 210: continue
        d = pd.DataFrame(r, columns=['date', 'o', 'h', 'l', 'c', 'v']); d['t'] = t; fr.append(d)
    D = pd.concat(fr); D['date'] = pd.to_datetime(D['date']); D = D.sort_values(['t', 'date']); g = D.groupby('t')
    D['pc'] = g['c'].shift(1); D['ret'] = D.c / D.pc - 1; D['gap'] = D.o / D.pc - 1
    D['rng'] = (D.c - D.l) / (D.h - D.l).replace(0, np.nan)
    D['adv'] = (D.c * D.v).groupby(D.t).transform(lambda s: s.rolling(20).mean()).shift(1)
    D['rv'] = D.v / D.v.groupby(D.t).transform(lambda s: s.rolling(20).mean()).shift(1)
    D['s200'] = D.groupby('t')['c'].transform(lambda s: s.rolling(200).mean())
    for k in (1, 3, 5): D[f'f{k}'] = g['c'].shift(-k) / D.c - 1
    D['oc'] = D.c / D.o - 1
    return D[(D.c >= 10) & (D.adv > 5e7)]
def signals(D):
    x = D[D.t != 'SPY']; out = []
    for name, m in (('A_strongclose', (x.ret > .03) & (x.rv >= 2) & (x.rng >= .8)),
                    ('B_flush', (x.ret < -.05) & (x.rv >= 2) & (x.c > x.s200)),
                    ('B2_flush_any', (x.ret < -.05) & (x.rv >= 2) & (x.c <= x.s200)),
                    ('D_gapup', (x.gap > .04) & (x.rv >= 2.5) & (x.c > x.o)),
                    ('G_gapdown_oc', (x.gap < -.03) & (x.rv >= 1.5))):
        s = x[m].copy(); s['play'] = name; out.append(s)
    return pd.concat(out)
def score(S, D):
    sp = D[D.t == 'SPY'].set_index('date'); S = S.copy()
    for k in (1, 3, 5): S[f'x{k}'] = (S[f'f{k}'] - sp[f'f{k}'].reindex(S.date).values) * 100 - COST
    S['xoc'] = (S.oc - sp['oc'].reindex(S.date).values) * 100 - COST
    return S
def write(S, source):
    old = pd.read_csv(LEDGER) if os.path.exists(LEDGER) else pd.DataFrame()
    S = S.assign(source=source, date=S.date.dt.strftime('%Y-%m-%d'))[['play', 't', 'date', 'ret', 'gap', 'rv', 'x1', 'x3', 'x5', 'xoc', 'source']]
    allr = pd.concat([old, S]).drop_duplicates(['play', 't', 'date'], keep='last'); allr.to_csv(LEDGER, index=False); return allr
def report(L=None):
    L = pd.read_csv(LEDGER) if L is None else L; rows = []
    print('PLAYBOOK LEDGER (net of 16 bp; excess vs SPY; day-clustered t = days as the sample)')
    for p, g in L.groupby('play'):
        k = 'xoc' if p.startswith('G_') else 'x3'; h = g.dropna(subset=[k]); n = len(h)
        if n == 0: print(p, 'no scored signals'); continue
        byd = h.groupby('date')[k].mean(); t = byd.mean() / (byd.std() / math.sqrt(len(byd))) if len(byd) > 2 and byd.std() > 0 else 0
        sh = h[k].mean() * n / (n + 30)
        mult = 1.0 if n < 30 else (0.0 if (t <= -1.5 and n >= 60) else float(np.clip(1 + sh, 0.5, 2.0)) if (sh < 0 or t >= 1.0) else 1.0)
        live = h[h.source != 'backfill']
        print(f"{p:14s} n={n:5d} (live {len(live):3d}) {k} {h[k].mean():+.2f} med {h[k].median():+.2f} hit {100*(h[k]>0).mean():.0f}% t(days) {t:+.1f} | d1 {h.x1.mean():+.2f} d5 {h.x5.mean():+.2f} | MULT {mult:.2f}{' (learning)' if n < 30 else ''}")
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'report'
    if cmd in ('backfill', 'update'):
        D = load('--refresh' in sys.argv); S = score(signals(D), D)
        if cmd == 'update':
            last = D.date.max(); S = S[S.date >= last - pd.Timedelta(days=14)]
            print('latest bar date', last.date(), '| signals on latest bar:', ', '.join(f"{r.play}:{r.t}" for r in S[S.date == last].itertuples())[:600])
        L = write(S, 'backfill' if cmd == 'backfill' else 'live'); report(L)
    else: report()
