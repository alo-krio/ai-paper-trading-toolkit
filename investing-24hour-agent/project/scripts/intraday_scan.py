#!/usr/bin/env python3
"""INTRADAY OPPORTUNITY SCAN for Main 24h (owner, Nov 16, 2026: "get a good idea of catalysts, momentum, oversold or
overbought positions. That's where good intraday trades happen."). PAPER ONLY. Information, never an order.
Run with credentials:  sh /home/user/workspace/_platform/py.sh scripts/intraday_scan.py [scan|score] [--top 10]
scan  : live Alpaca snapshots for the liquid universe (~1,600 names: price >= $10, 20d $vol >= $50M, cached daily bars)
        + daily context (RSI2, RSI14, 3d/5d move, distance from 20dma in ATRs, 20d high/low) + catalysts (Nasdaq
        earnings calendar: reported last night / this morning, or reporting tonight; Benzinga headline count today).
        Ranks four boards and writes data/intraday/YYYY-MM-DD-HHMM.csv (every name, so scoring is unbiased):
          CATALYST  : earnings or >= 2 fresh headlines, moving >= 1.5 ATR-equivalent with pace volume >= 1.5x
          MOMENTUM  : up/down >= 2%, pace volume >= 2x, holding the move (top/bottom 30% of day range, beyond the open)
          OVERSOLD  : RSI2 <= 5 or 3d <= -8% or >= 2.5 ATR below 20dma, AND reversing intraday (off the low, above open)
          OVERBOUGHT: RSI2 >= 95 or 3d >= +10% or >= 2.5 ATR above 20dma, AND fading (in bottom 40% of range)
        OVERBOUGHT names are a 'do not chase / take profits / BEAR-gate short' list, not buys.
score : for each past scan row, return from the scan price to that day's close and to the next close, minus SPY's
        same legs, net of 16 bp; prints results per board so we learn which board actually works intraday."""
import os, sys, json, glob, math, csv, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, 'scripts')
OUT = 'data/intraday'; os.makedirs(OUT, exist_ok=True)
COST = 0.16

def daily():
    ctx = {}
    for f in glob.glob('data/ohlcv/*.json'):
        t = os.path.basename(f)[:-5]
        try: r = json.load(open(f))
        except Exception: continue
        if len(r) < 30: continue
        c = [x[4] for x in r]; h = [x[2] for x in r]; l = [x[3] for x in r]; v = [x[5] for x in r]
        adv = sum(c[i] * v[i] for i in range(-20, 0)) / 20
        if c[-1] < 10 or adv < 5e7: continue
        tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(-14, 0)]
        atr = sum(tr) / 14
        def rsi(n):
            g = [max(c[i] - c[i - 1], 0) for i in range(-n, 0)]; d = [max(c[i - 1] - c[i], 0) for i in range(-n, 0)]
            ag, ad = sum(g) / n, sum(d) / n; return 100.0 if ad == 0 else 100 - 100 / (1 + ag / ad)
        ma20 = sum(c[-20:]) / 20
        ctx[t] = dict(last_date=r[-1][0], close=c[-1], atr=atr, atrp=100 * atr / c[-1], rsi2=rsi(2), rsi14=rsi(14),
                      r3=100 * (c[-1] / c[-4] - 1), r5=100 * (c[-1] / c[-6] - 1), z20=(c[-1] - ma20) / atr if atr else 0,
                      hi20=max(h[-20:]), lo20=min(l[-20:]), adv=adv)
    return ctx

def earnings_today():
    import prices as P
    t0 = dt.date.today(); prev = t0 - dt.timedelta(days=1)
    while prev.weekday() >= 5: prev -= dt.timedelta(days=1)
    rep, tonight = {}, set()
    for day in (prev, t0):
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"]) or {}
        for r in ((d.get("data") or {}).get("rows") or []):
            s = r["symbol"].replace(".", "-"); tm = r.get("time", "")
            if day == prev and tm != "time-pre-market": rep[s] = "reported last night"
            if day == t0 and tm == "time-pre-market": rep[s] = "reported this morning"
            if day == t0 and tm == "time-after-hours": tonight.add(s)
    return rep, tonight

HEAD = {}
_MM = []
def MAPN(t, n=8):
    """Market-map neighbours for t (list of dicts), [] if the map is missing / stale-unreadable or t is not in it."""
    if not _MM:
        try:
            sys.path.insert(0, '/home/user/workspace/market-brain'); import market_map as M
            _MM.append(M if M.meta() else None)
            if not M.meta(): print("DATA WARNING: market map missing; ripples fall back to brain graph + industry peers")
        except Exception as e:
            _MM.append(None); print("DATA WARNING: market map unavailable; ripples fall back to brain graph + industry peers", e)
    M = _MM[0]
    if M is None: return []
    try:
        d = M.neighbors(t, n=n)
        d = d[d.brain_rel == ''] if len(d) else d          # brain edges are added separately (first)
        return d.head(n).to_dict('records') if len(d) else []
    except Exception: return []

def ripples(rows, top_leaders=12):
    """Ripple read-through: for each catalyst / big momentum leader, list linked names (brain graph edges: suppliers,
    customers, competitors, adjacent, with sensitivity, ALWAYS first; then the market map's ranked neighbours
    (market-brain/market_map.py: residual correlation, catalyst co-move, news co-mention, industry; Nov 16 2026
    out-of-sample test: map neighbours moved ~2x as much as plain industry peers on catalyst days). If the map is missing
    or the leader is not in it, falls back to same-industry peers from the Nasdaq screener) with how much they have
    followed. LAGGING = linked, liquid, and has moved under 30% of the leader in the same direction."""
    import sqlite3
    by = {r['ticker']: r for r in rows}
    ind = {}
    try:
        sys.path.insert(0, '/home/user/workspace/market-brain'); import brain, prices as P
        body = brain.cached_get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true", 6 * 3600,
                                kind="nasdaq", fetch=lambda u, h: json.dumps(P._curl(["-H", "Accept: application/json", u])).encode())
        for r in json.loads(body)["data"]["rows"]:
            try: ind[r["symbol"].replace("/", "-")] = (r.get("industry") or "", float(str(r.get("marketCap") or 0).replace(",", "") or 0))
            except Exception: pass
    except Exception as e: print("DATA WARNING: industry map unavailable (peer ripples skipped)", e)
    edges = []
    try:
        c = sqlite3.connect('/home/user/workspace/market-brain/brain.db')
        edges = c.execute("SELECT source,target,relation,sensitivity,note FROM edges").fetchall(); c.close()
    except Exception as e: print("DATA WARNING: brain graph unavailable (mapped ripples skipped)", e)
    lead = [r for r in rows if 'CATALYST' in r['boards']] + sorted([r for r in rows if 'MOMENTUM' in r['boards'] and ind.get(r['ticker'], ('', 0))[1] >= 5e9],
                                                                     key=lambda r: -abs(r['atr_move']))
    seen, out = set(), []
    for L in lead:
        if L['ticker'] in seen or len(out) >= top_leaders: continue
        seen.add(L['ticker']); links = {}
        for s_, t_, rel, sen, note in edges:
            if s_.upper() == t_.upper(): continue
            if s_.upper() == L['ticker']: links[t_] = (f"{rel} {t_}", sen)
            elif t_.upper() == L['ticker']: links[s_] = (f"{s_} {rel}", sen)
        mm = MAPN(L['ticker'])
        for nb in mm:
            # strong map links count like graph links (LAG); moderate/weak ones are 'lag?' (sen 'peer')
            typ = nb['type'].replace('peer/competitor', 'peer')
            links.setdefault(nb['neighbor'], (f"map {typ} s{nb['score']:.2f}: {nb['reason'][:70]}", 'map' if nb['strength'] == 'strong' else 'peer'))
        li, _ = ind.get(L['ticker'], ('', 0))
        if li and not mm:
            lm = ind.get(L['ticker'], ('', 0))[1] or 0
            peers = sorted([t for t, (i, m) in ind.items() if i == li and t != L['ticker'] and t in by and (not lm or 0.2 * lm <= m <= 5 * lm)],
                           key=lambda t: -ind[t][1])[:5]
            for t in peers: links.setdefault(t, ("same industry: " + li, "peer"))
        rowsL = []
        for t, (rel, sen) in links.items():
            r = by.get(t)
            if not r: continue
            follow = r['move'] / L['move'] if L['move'] else 0
            # ripple study (research/ripple_study, Nov 16): laggards drift only after GOOD news (+0.37 next3, t 2.1);
            # sympathy followers (>= 0.7 of the leader) fade over 3-5 days (-1.2 / -2.3, t -2.5)
            lag = 2 <= L['move'] <= 25 and follow < 0.3 and 'OVERBOUGHT' not in r['boards'] and 'compet' not in rel
            if 2 <= abs(L['move']) <= 25 and follow >= 0.7 and abs(r['move']) >= 2:
                if 'SYMPATHY_FADE' not in r['boards']: r['boards'] = (r['boards'] + '+' if r['boards'] else '') + 'SYMPATHY_FADE'
                r['ripple_from'] = L['ticker']
            if lag:
                tag = 'PEER_LAG' if sen == 'peer' else 'RIPPLE_LAG'
                if tag not in r['boards']: r['boards'] = (r['boards'] + '+' if r['boards'] else '') + tag
                r['ripple_from'] = L['ticker']
            rowsL.append((t, rel, sen, r['move'], follow, lag))
        out.append((L, rowsL, bool(links)))
    print(f"\nRIPPLES (leader -> linked names: brain edges first, then market-map neighbours (s = map score, market_map.py neighbors T for evidence), industry peers only if the map lacks the leader; LAG = graph edge or STRONG map link that followed < 30% of a leader UP move (catch-up drift is real only after good news); FADE = sympathy mover that followed >= 70% (these tend to reverse over 3-5 days); lag? = moderate/weak map link or same-industry peer, weaker evidence; moves > 25% treated as company-specific)")
    for L, rl, mapped in out:
        hl = HEAD.get(L['ticker'], [])
        print(f"  {L['ticker']} {L['move']:+.1f}% [{L['boards']}] {L['earnings']}{'  (company-specific size; no lag flags)' if abs(L['move']) > 25 else ''}")
        print("     NEWS: " + (" || ".join(h[:90] for h in hl[:3]) if hl else "no headline found: find the trigger before trading any ripple"))
        print("     -> classify the trigger and SCOPE (industry signal / company-specific / mixed) before using any link below")
        if not mapped: print("     UNMAPPED: no graph edges or industry peers; map it (brain.py fact / industry desk) if the story matters"); continue
        for t, rel, sen, mv, fo, lag in sorted(rl, key=lambda x: (not x[5], -abs(x[3])))[:8]:
            print(f"     {('LAG ' if sen != 'peer' else 'lag?') if lag else ('FADE' if fo >= 0.7 and abs(mv) >= 2 and 2 <= abs(L['move']) <= 25 else '    ')} {t:6s} {mv:+5.1f}% (follow {fo:+.1f}) {rel} [{sen}]")
    return rows

def scan(top=10):
    import alpaca_data as A
    ctx = daily(); syms = sorted(ctx)
    snaps = {}
    for i in range(0, len(syms), 200):
        try: snaps.update(A.get('/v2/stocks/snapshots', symbols=','.join(syms[i:i + 200]), feed='iex') or {})
        except Exception as e: print('DATA WARNING: snapshot batch failed', i, e)
    try: rep, tonight = earnings_today()
    except Exception as e: rep, tonight = {}, set(); print('DATA WARNING: earnings calendar failed (catalyst board partial)', e)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))
    mins = max(1, min(390, (now.hour * 60 + now.minute) - (9 * 60 + 30))); frac = mins / 390
    spy = snaps.get('SPY', {}); spy_move = 100 * (spy['latestTrade']['p'] / spy['prevDailyBar']['c'] - 1) if spy.get('latestTrade') and spy.get('prevDailyBar') else None
    rows = []
    for t in syms:
        s = snaps.get(t) or {}; db, pb, lt = s.get('dailyBar'), s.get('prevDailyBar'), s.get('latestTrade')
        if not (db and pb and lt) or not pb.get('c'): continue
        if db['t'][:10] != now.date().isoformat(): continue      # no bar today yet: UNKNOWN, skip
        x = ctx[t]; last = lt['p']; pc = pb['c']; o, h, l = db['o'], db['h'], db['l']
        move = 100 * (last / pc - 1); gap = 100 * (o / pc - 1); rng = (last - l) / (h - l) if h > l else 0.5
        pace = (db['v'] / frac) / pb['v'] if pb.get('v') else 0
        atr_move = (last - pc) / x['atr'] if x['atr'] else 0
        rows.append(dict(ticker=t, time=now.strftime('%H:%M'), last=round(last, 2), move=round(move, 2), gap=round(gap, 2),
                         from_open=round(100 * (last / o - 1), 2), range_pos=round(rng, 2), pace_vol=round(pace, 2),
                         atr_move=round(atr_move, 2), rsi2=round(x['rsi2'], 1), rsi14=round(x['rsi14'], 1), r3=round(x['r3'], 1),
                         z20=round(x['z20'], 2), earnings=rep.get(t, 'reports tonight' if t in tonight else ''), headlines=0,
                         vs_spy=round(move - spy_move, 2) if spy_move is not None else ''))
    # headline counts only for the names moving (keeps news calls small)
    movers = [r['ticker'] for r in sorted(rows, key=lambda r: -abs(r['atr_move']))[:120]]
    since = now.replace(hour=0, minute=0).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cnt = {}
    for i in range(0, len(movers), 40):
        try:
            for n in A.get('/v1beta1/news', symbols=','.join(movers[i:i + 40]), limit=50, start=since).get('news', []):
                for s in n.get('symbols', []):
                    cnt[s] = cnt.get(s, 0) + 1; HEAD.setdefault(s, []).append(n.get('headline', ''))
        except Exception as e: print('DATA WARNING: news batch failed', e)
    for r in rows:
        r['headlines'] = cnt.get(r['ticker'], 0); b = []
        cat = bool(r['earnings'] and r['earnings'] != 'reports tonight') or r['headlines'] >= 2
        if cat and abs(r['atr_move']) >= 1.5 and r['pace_vol'] >= 1.5: b.append('CATALYST')
        if abs(r['move']) >= 2 and r['pace_vol'] >= 2 and ((r['move'] > 0 and r['range_pos'] >= .7 and r['from_open'] > 0) or (r['move'] < 0 and r['range_pos'] <= .3 and r['from_open'] < 0)): b.append('MOMENTUM')
        if (r['rsi2'] <= 5 or r['r3'] <= -8 or r['z20'] <= -2.5) and r['range_pos'] >= .5 and r['from_open'] > 0: b.append('OVERSOLD')
        if r['rsi2'] >= 95 and (r['r3'] >= 8 or r['z20'] >= 2.5) and r['range_pos'] <= .4 and r['from_open'] < 0: b.append('OVERBOUGHT')
        r['boards'] = '+'.join(b); r['ripple_from'] = ''
    rows = ripples(rows)
    f = f"{OUT}/{now.strftime('%Y-%m-%d-%H%M')}.csv"
    if rows:
        with open(f, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"INTRADAY SCAN {now.strftime('%Y-%m-%d %H:%M')} ET | {len(rows)}/{len(syms)} names with a bar today | SPY {spy_move:+.2f}% | saved {f}" if spy_move is not None else f"INTRADAY SCAN {len(rows)} names | SPY UNKNOWN")
    if len(rows) < 0.8 * len(syms): print(f"DATA WARNING: only {len(rows)} of {len(syms)} names have today's bar; boards are partial")
    key = {'CATALYST': lambda r: -abs(r['atr_move']), 'MOMENTUM': lambda r: -abs(r['atr_move']) * min(r['pace_vol'], 5),
           'OVERSOLD': lambda r: r['rsi2'] - r['from_open'], 'OVERBOUGHT': lambda r: -r['rsi2'] - r['z20']}
    for bd in ('CATALYST', 'MOMENTUM', 'OVERSOLD', 'OVERBOUGHT'):
        v = sorted([r for r in rows if bd in r['boards']], key=key[bd])[:top]
        print(f"\n{bd} ({sum(bd in r['boards'] for r in rows)} names)")
        for r in v:
            print(f"  {r['ticker']:6s} {r['move']:+6.2f}% (gap {r['gap']:+.1f}, from open {r['from_open']:+.1f}, {r['atr_move']:+.1f} ATR) range {r['range_pos']:.2f} pace {r['pace_vol']:.1f}x RSI2(prior close) {r['rsi2']:.0f} 3d {r['r3']:+.1f}% z20 {r['z20']:+.1f} {r['earnings']} {('news ' + str(r['headlines'])) if r['headlines'] else ''}")
    tn = sorted([r for r in rows if r['earnings'] == 'reports tonight'], key=lambda r: -abs(r['vs_spy'] or 0))
    print(f"\nREPORTS TONIGHT ({len(tn)}): " + ', '.join(f"{r['ticker']} {r['move']:+.1f}%" for r in tn[:15]))
    stale = sorted({x['last_date'] for x in ctx.values()})[-1]
    if (now.date() - dt.date.fromisoformat(stale)).days > 4: print(f"DATA WARNING: daily context last bar {stale} is stale; RSI2/z20 UNKNOWN-quality (run rotate.py warm)")
    print("\nBoards are research prompts: a buy still needs the story, CONVICTION, P_BEAT, TARGET and devil's advocate (v6.2).")

def premarket(top=12):
    """Overnight catalyst digest for the morning window (run 9:15-9:45 ET). SIP 30-min bars are 15 minutes delayed on our
    plan, so this shows extended-hours moves up to ~15 min ago: prior 3:30-4:00 bar close -> latest pre-market bar,
    with last night's/this morning's reporters, headlines and the ripple block. Ripple study (Nov 16): leaders move ~+3.5%
    after hours and ~+8.5% by 9 AM; linked names only ~+0.8% by 9 AM and ~+0.3% more by 10 AM, so this is PREP for the
    9:45/10:00 decisions, not a reason to trade in thin pre-market liquidity."""
    import alpaca_data as A
    ctx = daily(); syms = sorted(ctx) + ['SPY']
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))); d = now.date()
    p = d - dt.timedelta(days=1)
    while p.weekday() >= 5: p -= dt.timedelta(days=1)
    def u(day, hh, mm): return (dt.datetime(day.year, day.month, day.day, hh, mm) + dt.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = (now - dt.timedelta(minutes=16)).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    bars = {}
    for i in range(0, len(syms), 100):
        tok = None
        while True:
            q = dict(symbols=','.join(syms[i:i + 100]), timeframe='30Min', start=u(p, 15, 30), end=end, feed='sip', limit=10000)
            if tok: q['page_token'] = tok
            try: r = A.get('/v2/stocks/bars', **q)
            except Exception as e: print('DATA WARNING: pre-market bars batch failed', i, e); break
            for k, v in (r.get('bars') or {}).items(): bars.setdefault(k, []).extend(v)
            tok = r.get('next_page_token')
            if not tok: break
    try: rep, tonight = earnings_today()
    except Exception as e: rep, tonight = {}, set(); print('DATA WARNING: earnings calendar failed', e)
    rows = []
    cutoff = u(d, 0, 0)
    for t in syms:
        b = bars.get(t, [])
        base = [x for x in b if x['t'] < cutoff]; ext = [x for x in b if x['t'] >= cutoff]
        if not base or not ext: continue
        c0 = base[0]['c']; last = ext[-1]['c']; vol = sum(x['v'] for x in ext)
        mv = 100 * (last / c0 - 1); x = ctx.get(t, {}); atr = x.get('atrp', 2) or 2
        rows.append(dict(ticker=t, time=now.strftime('%H:%M'), last=round(last, 2), move=round(mv, 2), gap=round(mv, 2), from_open=0, range_pos=.5,
                         pace_vol=0, atr_move=round(mv / atr, 2), rsi2=round(x.get('rsi2', 50), 1), rsi14=round(x.get('rsi14', 50), 1), r3=round(x.get('r3', 0), 1),
                         z20=round(x.get('z20', 0), 2), earnings=rep.get(t, 'reports tonight' if t in tonight else ''), headlines=0, vs_spy='', pm_dollar_vol=round(vol * last / 1e6, 1)))
    by = {r['ticker']: r for r in rows}
    movers = [r['ticker'] for r in sorted(rows, key=lambda r: -abs(r['atr_move']))[:120]]
    since = u(p, 16, 0)
    for i in range(0, len(movers), 40):
        try:
            for n in A.get('/v1beta1/news', symbols=','.join(movers[i:i + 40]), limit=50, start=since).get('news', []):
                for s_ in n.get('symbols', []):
                    if s_ in by: by[s_]['headlines'] += 1
                    HEAD.setdefault(s_, []).append(n.get('headline', ''))
        except Exception as e: print('DATA WARNING: news batch failed', e)
    for r in rows:
        b = []
        if (r['earnings'] and r['earnings'] != 'reports tonight' or r['headlines'] >= 1) and abs(r['move']) >= 3 and r['pm_dollar_vol'] >= 2: b.append('CATALYST')
        elif abs(r['move']) >= 4 and r['pm_dollar_vol'] >= 5: b.append('MOMENTUM')
        r['boards'] = '+'.join(b); r['ripple_from'] = ''
    spy = by.get('SPY', {}).get('move')
    print(f"PRE-MARKET DIGEST {now.strftime('%Y-%m-%d %H:%M')} ET (SIP bars to ~{(now - dt.timedelta(minutes=16)).strftime('%H:%M')}) | {len(rows)} names traded after hours/pre-market | SPY {spy:+.2f}%" if spy is not None else f"PRE-MARKET DIGEST {len(rows)} names | SPY UNKNOWN")
    for bd in ('CATALYST', 'MOMENTUM'):
        v = sorted([r for r in rows if bd in r['boards']], key=lambda r: -abs(r['move']))[:top]
        print(f"\n{bd} overnight ({sum(bd in r['boards'] for r in rows)})")
        for r in v: print(f"  {r['ticker']:6s} {r['move']:+6.2f}% ({r['atr_move']:+.1f} ATR) pre-mkt ${r['pm_dollar_vol']}M {r['earnings']} | " + ' || '.join(h[:80] for h in HEAD.get(r['ticker'], [])[:2]))
    ripples(rows)
    f = f"{OUT}/{now.strftime('%Y-%m-%d-%H%M')}-pre.csv"
    if rows:
        with open(f, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"\nsaved {f}. Use this to PREPARE the 9:45/10:00 decisions: classify each leader's trigger and scope, mark linked laggards and sympathy movers, then confirm at 9:50 with the live scan (does the leader hold its gap?).")

def score():
    import json as J
    def bars(t):
        f = f'data/ohlcv/{t}.json'
        return {r[0]: r[4] for r in J.load(open(f))} if os.path.exists(f) else {}
    spy = bars('SPY'); res = {}
    for f in sorted(g for g in glob.glob(f'{OUT}/*.csv') if not g.endswith('-pre.csv')):
        d = os.path.basename(f)[:10]
        days = sorted(k for k in spy if k >= d)
        if not days or days[0] != d: continue
        nxt = days[1] if len(days) > 1 else None
        rows = list(csv.DictReader(open(f))); spy_row = None
        spy_last = None
        for r in rows:
            if r['ticker'] == 'SPY': spy_last = float(r['last'])
        if not spy_last: continue
        for r in rows:
            b = bars(r['ticker']); 
            if d not in b: continue
            e0 = 100 * (b[d] / float(r['last']) - 1) - 100 * (spy[d] / spy_last - 1) - COST
            e1 = (100 * (b[nxt] / float(r['last']) - 1) - 100 * (spy[nxt] / spy_last - 1) - COST) if nxt and nxt in b else None
            for bd in (r['boards'].split('+') if r['boards'] else ['none']):
                res.setdefault(bd, []).append((e0, e1))
    print('INTRADAY BOARD SCORE (scan price -> close, and -> next close; vs SPY, net 16 bp)')
    for bd, v in sorted(res.items()):
        a = [x[0] for x in v]; b = [x[1] for x in v if x[1] is not None]
        print(f"  {bd:10s} n={len(a):5d} to close {sum(a)/len(a):+.2f} hit {100*sum(x>0 for x in a)/len(a):.0f}% | to next close {(sum(b)/len(b)) if b else float('nan'):+.2f} (n={len(b)})")
    if not res: print('  no scored scans yet (needs daily bars for the scan date)')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 10
    {'scan': lambda: scan(top), 'premarket': lambda: premarket(top), 'score': score}[cmd]()
