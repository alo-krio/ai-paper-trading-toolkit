"""Attach the actual trigger to each catalyst in events.csv: Benzinga headlines (Alpaca news API) for the leader from
the prior session's 4 PM ET to the catalyst day's 4 PM ET, a trigger class from the headlines, and the headline text.
Writes catalysts_news.csv and events_news.csv (pairs joined to trigger). PAPER research only."""
import sys, re, csv, time, datetime as dt, pandas as pd
P = '/home/user/workspace/investing-24hour-agent/project'; sys.path.insert(0, P + '/scripts'); import alpaca_data as A
R = pd.read_csv(P + '/research/ripple_study/events.csv'); R['date'] = R.date.astype(str)
C = R.drop_duplicates(['leader', 'date'])[['leader', 'date', 'lead_x0', 'lead_n3']]
RULES = [  # order matters: first match wins
 ('guidance_cut', r'\b(cuts?|lowers?|slashes|reduces?|below)\b.{0,40}\b(guidance|outlook|forecast|guide)|(guidance|outlook|forecast).{0,30}\b(cut|lowered|below|disappoint|weak)'),
 ('guidance_raise', r'\b(raises?|lifts?|boosts?|hikes?|above)\b.{0,40}\b(guidance|outlook|forecast|guide)|(guidance|outlook|forecast).{0,30}\b(raised|above|strong|tops)'),
 ('earnings_miss', r'\b(miss(es|ed)?|falls? short|below (estimates|expectations)|disappoint)'),
 ('earnings_beat', r'\b(beats?|tops?|surpass|exceeds?|above (estimates|expectations)|record (revenue|quarter))'),
 ('earnings', r'\b(Q[1-4]|quarter|earnings|results|EPS|revenue)\b'),
 ('deal', r'\b(acquir|merger|to buy|takeover|buyout|deal to|stake in|spin-?off|divest)'),
 ('regulatory_legal', r'\b(FDA|approv|trial|tariff|export|ban|antitrust|DOJ|FTC|lawsuit|probe|investigation|sanction|regulat|court|ruling)'),
 ('analyst', r'\b(upgrade|downgrade|price target|initiat|overweight|underweight|outperform|neutral)'),
 ('management', r'\b(CEO|CFO|resign|steps down|appoint|succession)'),
 ('product_contract', r'\b(contract|order|launch|partnership|agreement|unveil|wins?)\b'),
]
def cls(text):
    for k, rx in RULES:
        if re.search(rx, text, re.I): return k
    return 'unclassified'
out = []
for i, c in enumerate(C.itertuples()):
    d = dt.date.fromisoformat(c.date); p = d - dt.timedelta(days=1)
    while p.weekday() >= 5: p -= dt.timedelta(days=1)
    try:
        n = A.get('/v1beta1/news', symbols=c.leader, start=f'{p}T21:00:00Z', end=f'{d}T21:00:00Z', limit=50, sort='asc').get('news', [])
    except Exception as e:
        n = []; time.sleep(2)
    hl = [x['headline'] for x in n if c.leader in x.get('symbols', [])]
    own = [h for h in hl if len(n) and True]
    joined = ' || '.join(hl[:12])
    # class from all headlines, priority = guidance > earnings > others (first rule that any headline hits)
    k = 'no_news' if not hl else 'unclassified'
    for name, rx in RULES:
        if any(re.search(rx, h, re.I) for h in hl): k = name; break
    out.append(dict(leader=c.leader, date=c.date, lead_x0=round(c.lead_x0, 2), lead_n3=c.lead_n3, trigger=k, n_headlines=len(hl), headlines=joined[:900]))
    if i % 100 == 0: print(i, len(C), flush=True)
N = pd.DataFrame(out); N.to_csv(P + '/research/ripple_study/catalysts_news.csv', index=False)
E = R.merge(N[['leader', 'date', 'trigger', 'n_headlines']], on=['leader', 'date'], how='left'); E.to_csv(P + '/research/ripple_study/events_news.csv', index=False)
print(N.trigger.value_counts().to_string())
