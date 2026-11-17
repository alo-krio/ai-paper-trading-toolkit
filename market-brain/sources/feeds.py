"""Fast free feeds for all books (Nov 17, 2026).
  python3 feeds.py headlines [--min 120] [--grep NVDA]  FinancialJuice headline relay (macro + company squawk), last N minutes
  python3 feeds.py chatter [--log]                      Reddit crowd attention (ApeWisdom), top names + mention spikes
  python3 feeds.py halts [--today]                       Nasdaq Trader halts/LULD pauses (all US listings), reason + resumption
Headlines are a RELAY: treat as VERIFY until the primary source (filing, release, Fed, data agency) or a second outlet confirms.
Failed fetch = UNKNOWN, never 'no news'."""
import sys,urllib.request,urllib.error,xml.etree.ElementTree as ET,datetime as dt,email.utils,re
UA={'User-Agent':'Mozilla/5.0'}
import os,time,hashlib
def get(u,ttl=120):
    """Cached fetch (feeds rate-limit hard: reuse a copy younger than ttl seconds, retry once on 429)."""
    p='/tmp/feedcache_'+hashlib.md5(u.encode()).hexdigest()
    if os.path.exists(p) and time.time()-os.path.getmtime(p)<ttl: return open(p,'rb').read()
    for i in range(2):
        try:
            b=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=20).read(); open(p,'wb').write(b); return b
        except urllib.error.HTTPError as e:
            if e.code!=429 or i: 
                if os.path.exists(p) and time.time()-os.path.getmtime(p)<1800: print('# using cached copy, age',int(time.time()-os.path.getmtime(p)),'s'); return open(p,'rb').read()
                raise
            time.sleep(8)
def arg(name,default=None):
    a=sys.argv
    return a[a.index(name)+1] if name in a else default
def headlines():
    mins=int(arg('--min',120)); g=arg('--grep')
    try: x=ET.fromstring(get('https://www.financialjuice.com/feed.ashx?xy=rss'))
    except Exception as e: print('DATA WARNING: FinancialJuice feed failed ->',e,'(UNKNOWN)'); return
    now=dt.datetime.now(dt.timezone.utc); n=0
    for it in x.iter('item'):
        t=it.findtext('title','').replace('FinancialJuice: ','')
        p=email.utils.parsedate_to_datetime(it.findtext('pubDate'))
        if (now-p).total_seconds()>mins*60: continue
        if g and not re.search(g,t,re.I): continue
        et=p.astimezone(dt.timezone(dt.timedelta(hours=-5))).strftime('%H:%M ET')
        print(et,'|',t); n+=1
    print(f'# {n} headlines in last {mins} min (feed holds only the newest ~100)')
def halts():
    ns={'n':'http://www.nasdaqtrader.com/'}
    try: x=ET.fromstring(get('https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts'))
    except Exception as e: print('DATA WARNING: halts feed failed ->',e,'(UNKNOWN)'); return
    today=dt.date.today().strftime('%m/%d/%Y')
    codes={'T1':'news pending','T2':'news released','LUDP':'volatility pause','LUDS':'volatility pause (straddle)','H10':'SEC suspension','T12':'info requested','M':'volatility pause','H4':'non-compliance','H11':'regulatory concern'}
    for it in x.iter('item'):
        d=it.findtext('n:HaltDate',namespaces=ns)
        if '--today' in sys.argv and d!=today: continue
        c=it.findtext('n:ReasonCode',namespaces=ns)
        print(d,it.findtext('n:HaltTime',namespaces=ns)[:8],it.findtext('n:IssueSymbol',namespaces=ns),'|',c,codes.get(c,''),'| resume',it.findtext('n:ResumptionTradeTime',namespaces=ns) or '-','|',it.findtext('n:IssueName',namespaces=ns))
def chatter():
    """Reddit crowd attention (ApeWisdom: mentions across r/wallstreetbets, r/stocks, r/investing, etc. over 24h).
    Prints the top names and the biggest mention spikes vs 24h ago. --log appends a snapshot to chatter/snapshots.csv.
    Evidence (see SOURCES.md): crowd chatter is REACTIVE; bullish peaks precede reversals; following it gave no alpha.
    Use as a heat gauge: a name at peak chatter is a fade/chase risk, not a buy reason."""
    import json,csv
    rows=[]
    try:
        for p in (1,2):
            d=json.loads(get(f'https://apewisdom.io/api/v1.0/filter/all-stocks/page/{p}',ttl=600)); rows+=d['results']
    except Exception as e: print('DATA WARNING: chatter feed failed ->',e,'(UNKNOWN)'); return
    for r in rows:
        m0=r.get('mentions_24h_ago') or 0; r['spike']=round((r['mentions']+5)/(m0+5),2)
    print('TOP CHATTER:',', '.join(f"{r['ticker']} {r['mentions']}" for r in rows[:12]))
    sp=[r for r in rows if r['mentions']>=25]; sp.sort(key=lambda r:-r['spike'])
    print('SPIKES (>=25 mentions, x vs 24h ago):',', '.join(f"{r['ticker']} x{r['spike']} ({r['mentions']})" for r in sp[:10]))
    if '--log' in sys.argv:
        d=os.path.join(os.path.dirname(os.path.abspath(__file__)),'chatter'); os.makedirs(d,exist_ok=True)
        f=os.path.join(d,'snapshots.csv'); new=not os.path.exists(f)
        ts=dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).strftime('%Y-%m-%d %H:%M')
        with open(f,'a',newline='') as fh:
            w=csv.writer(fh)
            if new: w.writerow(['ts_et','rank','ticker','mentions','mentions_24h_ago','upvotes','spike'])
            for r in rows: w.writerow([ts,r['rank'],r['ticker'],r['mentions'],r.get('mentions_24h_ago'),r.get('upvotes'),r['spike']])
        print('# logged',len(rows),'rows ->',f)
if __name__=='__main__':
    {'headlines':headlines,'halts':halts,'chatter':chatter}[sys.argv[1]]()
