"""Meet Kevin feed: list new YouTube uploads (main + clips channel) since the last run.
Usage: python3 ingest.py new   -> prints new videos as JSON lines and records them in videos.csv
       python3 ingest.py score -> re-scores calls.csv into calls_scored.csv (run via _platform/py.sh)
Rules: content is opinion and narrative, never evidence. Verify every factual claim elsewhere."""
import sys,csv,os,urllib.request,xml.etree.ElementTree as ET,json
HERE=os.path.dirname(os.path.abspath(__file__))
CH={'main':'UCUvvj5lwue7PspotMDjk5UA','clips':'UCPk6nJE8pBZPLCW2DAvaZOA'}
NS={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015','m':'http://search.yahoo.com/mrss/'}
VF=os.path.join(HERE,'videos.csv')
def seen():
    if not os.path.exists(VF): return set()
    return {r['video_id'] for r in csv.DictReader(open(VF))}
def new():
    s=seen(); rows=[]
    for name,cid in CH.items():
        x=ET.fromstring(urllib.request.urlopen(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}',timeout=20).read())
        for e in x.findall('a:entry',NS):
            vid=e.find('yt:videoId',NS).text
            if vid in s: continue
            d=e.find('m:group/m:description',NS)
            rows.append(dict(video_id=vid,channel=name,published=e.find('a:published',NS).text,title=e.find('a:title',NS).text,
                             url=f'https://www.youtube.com/watch?v={vid}',desc=(d.text or '')[:400].replace('\n',' ') if d is not None else ''))
    new_file=not os.path.exists(VF)
    with open(VF,'a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['video_id','channel','published','title','url','desc'])
        if new_file: w.writeheader()
        w.writerows(sorted(rows,key=lambda r:r['published']))
    for r in rows: print(json.dumps(r))
    print(f'# {len(rows)} new videos',file=sys.stderr)
if __name__=='__main__':
    if sys.argv[1]=='new': new()
    elif sys.argv[1]=='score':
        os.chdir(HERE); exec(open(os.path.join(HERE,'score_calls.py')).read())
