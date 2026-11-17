"""Shared Alpaca market-data helper for window_tests (PAPER research; data only, never trades)."""
import urllib.request, urllib.parse, urllib.error, json, os, time
BASE = "https://data.alpaca.markets"
import threading
_L = threading.Lock(); _next = [0.0]
RATE = float(os.environ.get('WT_RATE', '190'))  # requests/min (Alpaca data plan limit is 200/min)
def _wait():
    with _L:
        now = time.time(); t = max(now, _next[0]); _next[0] = t + 60.0 / RATE
    if t > now: time.sleep(t - now)
def get(path, **q):
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    for k in range(20):
        _wait()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"APCA-API-KEY-ID": os.environ["APCA_DATA_KEY_ID"], "APCA-API-SECRET-KEY": os.environ["APCA_DATA_SECRET_KEY"]}), timeout=90)
            return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # global pause until the window resets (429s also burn quota)
                try: rs = float(e.headers.get('x-ratelimit-reset'))
                except Exception: rs = time.time() + 5
                with _L: _next[0] = max(_next[0], min(rs, time.time() + 61) + 0.5)
                continue
            if e.code >= 500: time.sleep(3); continue
            raise
        except Exception:
            time.sleep(3)
    raise RuntimeError("failed " + url[:200])
def bars_all(**q):
    """multi-symbol /v2/stocks/bars with pagination -> list of dict rows with 'S'."""
    out = []; tok = None
    while True:
        qq = dict(q, limit=10000)
        if tok: qq['page_token'] = tok
        j = get('/v2/stocks/bars', **qq)
        for s, bs in (j.get('bars') or {}).items():
            for b in bs: b['S'] = s; out.append(b)
        tok = j.get('next_page_token')
        if not tok: return out
UNIV = '/home/user/workspace/market-brain/market_map/clusters.csv'
CACHE = os.path.dirname(os.path.abspath(__file__)) + '/cache'
