#!/usr/bin/env python3
"""Market brain: shared memory for the paper-trading desk (owner, Nov 16, 2026). PAPER ONLY. Library + CLI.

Owner: "set it up in a way where we don't need to keep running ripple or keep pulling the same information. Think of
building some sort of brain, vector database or cache to help you recall information you might have already discovered."

One SQLite file (brain.db) with four layers:
  1. DOCS    every research note, thesis, report, brief, industry-desk file and insight line across the three books,
             chunked, entity-tagged and indexed twice: full text (FTS5/BM25) and vectors (local model2vec embeddings,
             no API). Ingest is incremental (only changed files are re-read).
  2. FACTS   short sourced claims ("AVGO has ~$43B of AI-lab backstops", source, date, expiry). Added by agents after
             research; recalled before research. Expired facts are shown as STALE, not deleted.
  3. CACHE   raw HTTP responses (Nasdaq analyst data, SEC filings, news RSS...) with a TTL per source, so scripts never
             pull the same thing twice within its freshness window. Also per-ticker snapshots so briefs show only
             what changed since last time.
  4. GRAPH   the industry desks' ripple graph (data/ripple_graph/*.csv imported on change) and a ripple cache keyed by
             the graph version, so neighbourhoods are computed once per graph change, not per question.

CLI (python3 /home/user/workspace/market-brain/brain.py ...):
  ingest                      index new/changed files (cheap; run at the end of every routine)
  recall "query" [--entity T] [--k 8] [--days N]   hybrid search over docs + facts, freshness shown
  facts T [--all]             current facts about an entity (--all includes stale/superseded)
  fact --entity T --topic X --claim "..." --source URL [--date YYYY-MM-DD] [--ttl DAYS] [--by NAME]
  ripple T [--hops 2]         cached ripple neighbourhood (recomputed only if the graph changed)
  exposure                    for every holding: the 2-hop set of names whose news touches it (cached)
  stale [--days 45]           facts past expiry and graph rows older than N days
  stats
Library: import brain; brain.cached_get(url, ttl_s, headers) ; brain.snapshot_diff(ticker, kind, dict) ;
         brain.recall(q) ; brain.add_fact(...) ; brain.seen(key) / brain.mark_seen(keys)
"""
import os, sys, re, json, time, glob, hashlib, sqlite3, datetime as dt, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "brain.db")
MODEL_DIR = os.path.join(HERE, "model", "potion-base-8M")
WS = "/home/user/workspace"
ROOTS = [f"{WS}/investing-3-6month-agent/project", f"{WS}/investing-3-6month-agent/AGENT.md",
         f"{WS}/investing-14day-agent/project", f"{WS}/investing-14day-agent/trading-desk",
         f"{WS}/investing-24hour-agent/project", f"{WS}/research", f"{WS}/strategy-review-2026-11-13.md"]
SKIP_DIRS = ("backup", "__pycache__", "node_modules", "trader-skill", "/skills/", "/.git", "routines_bak", "_bak", "/tests/")
EXT = (".md", ".txt")
TTL = {"nasdaq": 20 * 3600, "sec_sub": 6 * 3600, "sec_tickers": 7 * 86400, "news": 3 * 3600, "default": 12 * 3600}
STOP = {"A", "I", "AI", "US", "ET", "CEO", "CFO", "EPS", "FCF", "PE", "ETF", "IPO", "GDP", "CPI", "FY", "Q1", "Q2", "Q3", "Q4",
        "YTD", "USD", "CAD", "OK", "R", "THE", "AND", "FOR", "NOT", "BUY", "SELL", "HOLD", "TRIM", "EXIT", "ADD", "NEW", "SPX",
        "DMA", "SMA", "RSI", "ATR", "TTL", "API", "SEC", "FED", "FOMC", "NYSE", "TSX", "UNKNOWN", "PAPER", "ONLY", "NO", "YES",
        "LOW", "HIGH", "MED", "PM", "AM", "HBM", "DRAM", "GPU", "CPU", "EV", "PT", "RR", "ER", "DD", "GAP", "FIX", "KEY", "ONE", "MAIN", "LINE", "CASH", "EDGE", "TEAM", "BEAT", "PLAY", "RUN", "WELL", "VERY", "BIG", "ARE", "ALL", "CAN", "HAS", "OUT", "NEXT", "SEE", "GOOD", "BEST", "REAL", "FAST", "OPEN", "LIFE", "SAFE", "MOVE", "PLUS", "TRUE", "NICE", "LIVE", "WAY", "HE", "WE", "GO", "MS", "GS", "UK", "EU", "LP", "IV", "DC", "CO", "TV", "PC", "TOP", "IT", "IS", "ON", "IN", "AT", "OR", "TO", "OF", "BY", "AN", "BE", "AS", "UP", "SO", "DO"}

def con():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, hash TEXT, kind TEXT, indexed_at TEXT);
    CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, path TEXT, chunk INTEGER, heading TEXT, text TEXT, entities TEXT,
        kind TEXT, as_of TEXT, vec BLOB);
    CREATE INDEX IF NOT EXISTS docs_path ON docs(path);
    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(text, heading, entities, content='docs', content_rowid='id');
    CREATE TABLE IF NOT EXISTS facts(id INTEGER PRIMARY KEY, entity TEXT, topic TEXT, claim TEXT, source TEXT, source_date TEXT,
        added_at TEXT, expires_at TEXT, added_by TEXT, superseded_by INTEGER, vec BLOB);
    CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(entity, topic, claim, content='facts', content_rowid='id');
    CREATE TABLE IF NOT EXISTS http_cache(key TEXT PRIMARY KEY, url TEXT, body BLOB, fetched_at REAL, ttl REAL);
    CREATE TABLE IF NOT EXISTS snapshots(ticker TEXT, kind TEXT, taken_at TEXT, data TEXT, PRIMARY KEY(ticker, kind));
    CREATE TABLE IF NOT EXISTS seen(key TEXT PRIMARY KEY, first_seen TEXT);
    CREATE TABLE IF NOT EXISTS edges(source TEXT, target TEXT, relation TEXT, exposure TEXT, sensitivity TEXT, note TEXT,
        source_url TEXT, as_of TEXT, desk TEXT);
    CREATE TABLE IF NOT EXISTS ripple_cache(node TEXT, hops INTEGER, graph_version TEXT, result TEXT, PRIMARY KEY(node, hops));
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    """)
    return c

def now(): return dt.datetime.now().strftime("%Y-%m-%d %H:%M")
def today(): return dt.date.today().isoformat()

# ---------- embeddings ----------
_M = None
def embed(texts):
    global _M
    import numpy as np
    if _M is None:
        from model2vec import StaticModel
        _M = StaticModel.from_pretrained(MODEL_DIR)
    v = _M.encode(list(texts))
    v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    return v.astype("float32")

# ---------- entities ----------
_ALIAS = None
def aliases():
    """ticker -> set of name words; name phrase -> ticker. From SEC tickers (cached) + book files."""
    global _ALIAS
    if _ALIAS is not None: return _ALIAS
    tick, names = set(), {}
    try:
        js = json.loads(cached_get("https://www.sec.gov/files/company_tickers.json", TTL["sec_tickers"],
                                   {"User-Agent": os.environ.get("SEC_USER_AGENT","your-name your-email@example.com")}) or "{}")
        for v in js.values():
            t = v["ticker"].upper(); tick.add(t)
            n = re.sub(r"[,.]| (inc|corp|corporation|co|ltd|plc|holdings|group|company|the)\b", "", v["title"].lower()).strip()
            if len(n) >= 4 and n not in names: names[n] = t
    except Exception:
        pass
    # restrict company-NAME matching to listed caps >= $2B (screener cache, if present) to avoid word collisions
    try:
        c0 = con(); r0 = c0.execute("SELECT body FROM http_cache WHERE url LIKE 'https://api.nasdaq.com/api/screener/stocks%' ORDER BY fetched_at DESC LIMIT 1").fetchone(); c0.close()
        if r0:
            big = {x["symbol"].upper() for x in json.loads(r0[0])["data"]["rows"] if (lambda v: v and float(v) >= 2e9)(x.get("marketCap") or 0)}
            names = {n: t for n, t in names.items() if t in big}
    except Exception:
        pass
    for w in ("bullish", "perfect", "global", "first", "american", "united", "general", "national", "target", "visa", "block", "match", "booking"):
        names.pop(w, None)
    for extra in ("CNQ.TO", "XLE", "SPY", "QQQ", "TQQQ", "SGOV", "SMH", "SOXL", "RSP", "XLK", "XLV", "XLI", "ITA", "XLC", "XLY"):
        tick.add(extra)
    _ALIAS = (tick, names)
    return _ALIAS

def entities(text):
    tick, names = aliases()
    found = set()
    for m in re.findall(r"(?<![A-Za-z0-9])([A-Z]{1,5}(?:\.TO)?)(?![a-z0-9])", text):
        if m in tick and m not in STOP and len(m) >= 2: found.add(m)
    low = text.lower()
    lw = set(re.findall(r"[a-z0-9&'-]+", low))
    for n, t in names.items():  # SEC company names (one or two words, >= 5 chars), e.g. "shopify" -> SHOP
        if len(n) >= 5 and all(len(w) >= 3 for w in n.split()) and n.split()[0] in lw and (" " not in n or re.search(r"\b" + re.escape(n) + r"\b", low)) and len(n.split()) <= 2:
            found.add(t)
    for n in ("nvidia", "broadcom", "micron", "microsoft", "amazon", "alphabet", "google", "eli lilly", "intuitive surgical",
              "caterpillar", "lockheed", "zebra", "canadian natural", "taiwan semiconductor", "tsmc", "anthropic", "openai",
              "oracle", "meta", "aerovironment", "uber", "waymo", "deere", "novo nordisk", "sk hynix", "samsung", "asml"):
        if n in low:
            found.add({"nvidia": "NVDA", "broadcom": "AVGO", "micron": "MU", "microsoft": "MSFT", "amazon": "AMZN",
                       "alphabet": "GOOGL", "google": "GOOGL", "eli lilly": "LLY", "intuitive surgical": "ISRG",
                       "caterpillar": "CAT", "lockheed": "LMT", "zebra": "ZBRA", "canadian natural": "CNQ.TO",
                       "taiwan semiconductor": "TSM", "tsmc": "TSM", "anthropic": "Anthropic", "openai": "OpenAI",
                       "oracle": "ORCL", "meta": "META", "aerovironment": "AVAV", "uber": "UBER", "waymo": "Waymo",
                       "deere": "DE", "novo nordisk": "NVO", "sk hynix": "SK Hynix", "samsung": "Samsung", "asml": "ASML"}[n])
    return sorted(found)

# ---------- HTTP cache ----------
def cached_get(url, ttl_s=None, headers=None, kind="default", raw=False, fetch=None):
    """Return the body (str, or bytes if raw) from cache if fresh, else fetch, store and return. fetch(url, headers)->bytes
    may be supplied by the caller (e.g. a proxy-aware fetcher). Failed fetches are never cached; a stale copy is returned
    with a warning on stderr if the live fetch fails (marked so the caller can treat it as stale)."""
    ttl = ttl_s if ttl_s is not None else TTL.get(kind, TTL["default"])
    key = hashlib.sha1(url.encode()).hexdigest()
    c = con(); r = c.execute("SELECT body, fetched_at FROM http_cache WHERE key=?", (key,)).fetchone()
    if r and time.time() - r[1] < ttl:
        c.close(); return r[0] if raw else r[0].decode("utf-8", "replace")
    body = None
    try:
        if fetch: body = fetch(url, headers or {})
        else:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp: body = resp.read()
        if body and body[:2] == b"\x1f\x8b":
            import gzip; body = gzip.decompress(body)
    except Exception as e:
        body = None
        err = e
    if body:
        c.execute("REPLACE INTO http_cache VALUES(?,?,?,?,?)", (key, url, body, time.time(), ttl)); c.commit(); c.close()
        return body if raw else body.decode("utf-8", "replace")
    c.close()
    if r:
        sys.stderr.write(f"[brain] live fetch failed, using STALE cache ({(time.time()-r[1])/3600:.1f}h old): {url[:90]}\n")
        return r[0] if raw else r[0].decode("utf-8", "replace")
    return None

def snapshot_diff(ticker, kind, data):
    """Store the latest snapshot for (ticker, kind); return (previous_data, previous_time) for change reporting."""
    c = con(); r = c.execute("SELECT data, taken_at FROM snapshots WHERE ticker=? AND kind=?", (ticker, kind)).fetchone()
    c.execute("REPLACE INTO snapshots VALUES(?,?,?,?)", (ticker, kind, now(), json.dumps(data, default=str))); c.commit(); c.close()
    return (json.loads(r[0]), r[1]) if r else (None, None)

def seen(keys):
    c = con(); out = {k for (k,) in c.execute(f"SELECT key FROM seen WHERE key IN ({','.join('?'*len(keys))})", list(keys))} if keys else set()
    c.close(); return out

def mark_seen(keys):
    c = con(); c.executemany("INSERT OR IGNORE INTO seen VALUES(?,?)", [(k, now()) for k in keys]); c.commit(); c.close()

# ---------- docs ----------
def files():
    out = []
    for r in ROOTS:
        if os.path.isfile(r): out.append(r); continue
        for p in glob.glob(os.path.join(r, "**", "*"), recursive=True):
            if p.endswith(EXT) and os.path.isfile(p) and not any(s in p for s in SKIP_DIRS) and os.path.getsize(p) < 600_000:
                out.append(os.path.realpath(p))
    return sorted(set(out))

def kind_of(p):
    for k in ("theses", "industries", "briefs", "reports", "research", "notes", "insights", "radar", "routines"):
        if f"/{k}" in p: return k
    return "doc"

def chunks(text, size=1200):
    """split on markdown headings, then pack paragraphs to ~size chars; keep the heading with each chunk"""
    out, head, buf = [], "", ""
    for line in text.splitlines():
        if line.startswith("#"):
            if buf.strip(): out.append((head, buf.strip()))
            head, buf = line.strip("# ").strip()[:120], ""
            continue
        if len(buf) + len(line) > size and buf.strip():
            out.append((head, buf.strip())); buf = ""
        buf += line + "\n"
    if buf.strip(): out.append((head, buf.strip()))
    return out

def as_of(p, text):
    m = re.search(r"(20\d\d-\d\d-\d\d)", os.path.basename(p)) or re.search(r"(20\d\d-\d\d-\d\d)", text[:400])
    return m.group(1) if m else dt.date.fromtimestamp(os.path.getmtime(p)).isoformat()

def ingest(verbose=True, force=False):
    aliases()  # load the ticker universe before taking the write lock
    c = con()
    if force:
        c.executescript("DELETE FROM docs; DELETE FROM files; INSERT INTO docs_fts(docs_fts) VALUES('rebuild');")
    known = {p: (m, h) for p, m, h in c.execute("SELECT path, mtime, hash FROM files")}
    fs = files(); n_new = n_chunks = 0
    for p in fs:
        m = os.path.getmtime(p)
        if p in known and abs(known[p][0] - m) < 1e-6: continue
        text = open(p, encoding="utf-8", errors="replace").read()
        h = hashlib.sha1(text.encode()).hexdigest()
        if p in known and known[p][1] == h:
            c.execute("UPDATE files SET mtime=? WHERE path=?", (m, p)); continue
        old = [i for (i,) in c.execute("SELECT id FROM docs WHERE path=?", (p,))]
        for i in old:
            r = c.execute("SELECT text, heading, entities FROM docs WHERE id=?", (i,)).fetchone()
            c.execute("INSERT INTO docs_fts(docs_fts, rowid, text, heading, entities) VALUES('delete',?,?,?,?)", (i, *r))
        c.execute("DELETE FROM docs WHERE path=?", (p,))
        ch = chunks(text); k = kind_of(p); ao = as_of(p, text)
        if ch:
            vecs = embed([f"{hd}\n{t}" for hd, t in ch])
            for j, ((hd, t), v) in enumerate(zip(ch, vecs)):
                ents = " ".join(entities(hd + "\n" + t))
                cur = c.execute("INSERT INTO docs(path, chunk, heading, text, entities, kind, as_of, vec) VALUES(?,?,?,?,?,?,?,?)",
                                (p, j, hd, t, ents, k, ao, v.tobytes()))
                c.execute("INSERT INTO docs_fts(rowid, text, heading, entities) VALUES(?,?,?,?)", (cur.lastrowid, t, hd, ents))
        c.execute("REPLACE INTO files VALUES(?,?,?,?,?)", (p, m, h, k, now()))
        n_new += 1; n_chunks += len(ch)
    gone = set(known) - set(fs)
    for p in gone:
        for i in [i for (i,) in c.execute("SELECT id FROM docs WHERE path=?", (p,))]:
            r = c.execute("SELECT text, heading, entities FROM docs WHERE id=?", (i,)).fetchone()
            c.execute("INSERT INTO docs_fts(docs_fts, rowid, text, heading, entities) VALUES('delete',?,?,?,?)", (i, *r))
        c.execute("DELETE FROM docs WHERE path=?", (p,)); c.execute("DELETE FROM files WHERE path=?", (p,))
    c.commit(); c.close()
    g = import_graph()
    if verbose: print(f"ingest: {n_new} files (re)indexed, {n_chunks} chunks; {len(gone)} removed; graph: {g}")

# ---------- facts ----------
def add_fact(entity, topic, claim, source, source_date=None, ttl_days=30, by="agent"):
    c = con()
    v = embed([f"{entity} {topic}: {claim}"])[0]
    exp = (dt.date.today() + dt.timedelta(days=ttl_days)).isoformat()
    # supersede an older live fact with the same entity+topic
    prev = c.execute("SELECT id FROM facts WHERE entity=? AND topic=? AND superseded_by IS NULL", (entity, topic)).fetchall()
    cur = c.execute("INSERT INTO facts(entity, topic, claim, source, source_date, added_at, expires_at, added_by, vec) VALUES(?,?,?,?,?,?,?,?,?)",
                    (entity, topic, claim, source, source_date or today(), now(), exp, by, v.tobytes()))
    fid = cur.lastrowid
    c.execute("INSERT INTO facts_fts(rowid, entity, topic, claim) VALUES(?,?,?,?)", (fid, entity, topic, claim))
    for (i,) in prev: c.execute("UPDATE facts SET superseded_by=? WHERE id=?", (fid, i))
    c.commit(); c.close(); return fid

def facts_for(entity, include_all=False):
    c = con()
    q = "SELECT id, topic, claim, source, source_date, expires_at, superseded_by FROM facts WHERE entity=?"
    rows = c.execute(q + ("" if include_all else " AND superseded_by IS NULL") + " ORDER BY source_date DESC", (entity,)).fetchall()
    c.close(); return rows

# ---------- recall ----------
def _fts_q(q):
    toks = [t for t in re.findall(r"[A-Za-z0-9.]+", q) if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in toks) if toks else '""'

def recall(q, entity=None, k=8, days=None):
    import numpy as np
    c = con(); qv = embed([q])[0]
    res = {}
    cut = (dt.date.today() - dt.timedelta(days=days)).isoformat() if days else None
    # docs: BM25 candidates + vector scan (corpus is small enough for brute force)
    try:
        for (rid, bm) in c.execute("SELECT rowid, bm25(docs_fts) FROM docs_fts WHERE docs_fts MATCH ? ORDER BY bm25(docs_fts) LIMIT 60", (_fts_q(q),)):
            res[("d", rid)] = {"bm": -bm}
    except sqlite3.OperationalError:
        pass
    rows = c.execute("SELECT id, vec, entities, as_of FROM docs").fetchall()
    if rows:
        M = np.frombuffer(b"".join(r[1] for r in rows), dtype="float32").reshape(len(rows), -1)
        sims = M @ qv
        for i in np.argsort(-sims)[:60]:
            res.setdefault(("d", rows[i][0]), {})["vec"] = float(sims[i])
    frows = c.execute("SELECT id, vec FROM facts WHERE superseded_by IS NULL").fetchall()
    if frows:
        F = np.frombuffer(b"".join(r[1] for r in frows), dtype="float32").reshape(len(frows), -1)
        fs = F @ qv
        for i in np.argsort(-fs)[:20]: res.setdefault(("f", frows[i][0]), {})["vec"] = float(fs[i])
    try:
        for (rid, bm) in c.execute("SELECT rowid, bm25(facts_fts) FROM facts_fts WHERE facts_fts MATCH ? LIMIT 30", (_fts_q(q),)):
            res.setdefault(("f", rid), {})["bm"] = -bm
    except sqlite3.OperationalError:
        pass
    # hybrid score: normalised BM25 + vector, entity boost, recency boost
    bms = [v.get("bm", 0) for v in res.values()]; mx = max(bms) if bms and max(bms) > 0 else 1
    qents = set(entities(q)) | ({entity} if entity else set())
    out = []
    for (typ, rid), s in res.items():
        if typ == "d":
            r = c.execute("SELECT path, heading, text, entities, as_of, kind FROM docs WHERE id=?", (rid,)).fetchone()
            if not r: continue
            ents, ao = set(r[3].split()), r[4]
        else:
            r = c.execute("SELECT entity, topic, claim, source, source_date, expires_at FROM facts WHERE id=?", (rid,)).fetchone()
            if not r: continue
            ents, ao = {r[0]}, r[4]
        if entity and entity not in ents: continue
        if cut and ao and ao < cut: continue
        age = (dt.date.today() - dt.date.fromisoformat(ao[:10])).days if ao else 90
        score = 0.55 * (s.get("bm", 0) / mx) + 0.45 * max(s.get("vec", 0), 0) + (0.25 if qents & ents else 0) \
                + max(0, 0.15 - age * 0.005) + (0.1 if typ == "f" else 0)
        out.append((score, typ, r, age))
    c.close()
    out.sort(key=lambda x: -x[0])
    return out[:k]

def print_recall(q, entity=None, k=8, days=None):
    hits = recall(q, entity, k, days)
    if not hits: print("no memory hits: research it, then store the key facts (brain.py fact ...)"); return
    for score, typ, r, age in hits:
        if typ == "f":
            stale = " STALE" if r[5] and r[5] < today() else ""
            print(f"[FACT {r[4]}, {age}d old{stale}] {r[0]} / {r[1]}: {r[2]}  <{r[3]}>")
        else:
            rel = r[0].replace(WS + "/", "")
            txt = re.sub(r"\s+", " ", r[2])[:420]
            print(f"[DOC {r[4]}, {age}d old, {r[5]}] {rel} :: {r[1]}\n    {txt}")

# ---------- graph + ripple cache ----------
GRAPH_GLOBS = [f"{WS}/investing-3-6month-agent/project/data/ripple_graph/*.csv"]
FWD = {"supplier_to": "supplies", "customer_of": "buys from", "competitor_of": "competes with", "adjacent_to": "adjacent to", "input_cost_for": "is an input cost for"}
REV = {"supplier_to": "buys from", "customer_of": "supplies", "competitor_of": "competes with", "adjacent_to": "adjacent to", "input_cost_for": "has input cost"}
SENS = {"high": 3, "med": 2, "low": 1}

def import_graph():
    import csv
    fs = sorted(f for g in GRAPH_GLOBS for f in glob.glob(g))
    ver = hashlib.sha1("".join(f"{f}:{os.path.getmtime(f)}" for f in fs).encode()).hexdigest()[:12]
    c = con(); r = c.execute("SELECT v FROM meta WHERE k='graph_version'").fetchone()
    if r and r[0] == ver:
        n = c.execute("SELECT count(*) FROM edges").fetchone()[0]; c.close(); return f"{n} edges (unchanged, v{ver})"
    c.execute("DELETE FROM edges")
    for f in fs:
        desk = os.path.splitext(os.path.basename(f))[0]
        for e in csv.DictReader(open(f, encoding="utf-8", errors="replace")):
            if (e.get("source") or "").strip() and (e.get("target") or "").strip():
                c.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?,?)", (e["source"].strip(), e["target"].strip(), (e.get("relation") or "").strip(),
                          e.get("exposure", ""), (e.get("sensitivity") or "").strip().lower(), e.get("note", ""), e.get("source_url", ""), e.get("as_of", ""), desk))
    c.execute("REPLACE INTO meta VALUES('graph_version', ?)", (ver,)); c.execute("DELETE FROM ripple_cache")
    n = c.execute("SELECT count(*) FROM edges").fetchone()[0]; c.commit(); c.close()
    return f"{n} edges (re-imported, v{ver}; ripple cache cleared)"

def _neigh(c, node):
    out = []
    for s, t, rel, ex, se, no, desk in c.execute("SELECT source,target,relation,exposure,sensitivity,note,desk FROM edges WHERE upper(source)=upper(?) OR upper(target)=upper(?)", (node, node)):
        if s.upper() == node.upper(): out.append((t, FWD.get(rel, rel), ex, se, no, desk))
        else: out.append((s, REV.get(rel, rel), ex, se, no, desk))
    return out

def ripple(node, hops=2):
    import_graph()
    c = con(); ver = c.execute("SELECT v FROM meta WHERE k='graph_version'").fetchone()
    ver = ver[0] if ver else ""
    r = c.execute("SELECT result, graph_version FROM ripple_cache WHERE node=? AND hops=?", (node.upper(), hops)).fetchone()
    if r and r[1] == ver:
        c.close(); return json.loads(r[0]), True
    first = _neigh(c, node)
    res = {"node": node, "first": first, "second": {}}
    if hops >= 2:
        seen_ = {node.upper()} | {n.upper() for n, *_ in first}
        for n, how, ex, se, no, desk in first:
            if SENS.get(se, 1) < 2: continue
            for m, how2, ex2, se2, no2, d2 in _neigh(c, n):
                if m.upper() in seen_ or SENS.get(se2, 1) < 2: continue
                res["second"].setdefault(m, []).append(f"via {n} ({how2} {n})")
    c.execute("REPLACE INTO ripple_cache VALUES(?,?,?,?)", (node.upper(), hops, ver, json.dumps(res))); c.commit(); c.close()
    return res, False

def book_names():
    import csv
    p = f"{WS}/investing-3-6month-agent/project/book/positions.csv"; t = f"{WS}/investing-3-6month-agent/project/book/targets.csv"
    pos = {r["ticker"] for r in csv.DictReader(open(p)) if r.get("status") == "open"} - {"SGOV", "SPY"} if os.path.exists(p) else set()
    cand = ({r["ticker"] for r in csv.DictReader(open(t))} - pos) if os.path.exists(t) else set()
    return pos, cand

def print_ripple(node, hops=2):
    res, hit = ripple(node, hops); pos, cand = book_names()
    tag = lambda n: " [HELD]" if n in pos else " [CANDIDATE]" if n in cand else ""
    print(f"=== {node}{tag(node)} ({'from cache' if hit else 'computed and cached'}) ===")
    if not res["first"]:
        print("  no edges (UNKNOWN; the industry desk should map it)"); return
    by = {}
    for n, how, ex, se, no, desk in res["first"]: by.setdefault(how, []).append((n, ex, se, no, desk))
    for how in sorted(by):
        print(f"  {node} {how}:")
        for n, ex, se, no, desk in sorted(by[how], key=lambda x: -SENS.get(x[2], 1)):
            print(f"    - {n}{tag(n)} | {se} | {ex} | {no[:100]} ({desk})")
    h2 = {m: v for m, v in res["second"].items() if m in pos or m in cand}
    if h2:
        print("  second order, book/candidates:")
        for m, v in sorted(h2.items()): print(f"    - {m}{tag(m)}: {'; '.join(sorted(set(v)))[:200]}")
    oth = sorted(m for m in res["second"] if m not in h2)
    if oth: print(f"  second order, others: {', '.join(oth[:25])}")
    fx = facts_for(node)
    if fx:
        print("  remembered facts:")
        for f in fx[:6]: print(f"    - [{f[4]}{' STALE' if f[5] < today() else ''}] {f[1]}: {f[2]}")

def exposure():
    """for each holding, the 2-hop names (med/high links) whose news would touch it; cached via ripple()"""
    pos, cand = book_names(); out = {}
    for t in sorted(pos | cand):
        res, _ = ripple(t, 2)
        first = sorted({n for n, how, ex, se, no, d in res["first"] if SENS.get(se, 1) >= 2})
        out[t] = {"first": first, "second": sorted(res["second"])}
    return out

# ---------- CLI ----------
def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if cmd == "ingest": ingest(force="--force" in a)
    elif cmd == "recall": print_recall(a[1], opt("--entity"), int(opt("--k", 8)), int(opt("--days")) if opt("--days") else None)
    elif cmd == "facts":
        for f in facts_for(a[1], "--all" in a):
            print(f"#{f[0]} [{f[4]}, expires {f[5]}{', STALE' if f[5] < today() else ''}{', superseded by #'+str(f[6]) if f[6] else ''}] {f[1]}: {f[2]} <{f[3]}>")
    elif cmd == "fact":
        fid = add_fact(opt("--entity"), opt("--topic"), opt("--claim"), opt("--source", ""), opt("--date"), int(opt("--ttl", 30)), opt("--by", "agent"))
        print(f"fact #{fid} stored")
    elif cmd == "ripple": print_ripple(a[1], int(opt("--hops", 2)))
    elif cmd == "exposure":
        for t, v in exposure().items():
            print(f"{t}: direct {', '.join(v['first']) or '-'} | 2nd {', '.join(v['second'][:15]) or '-'}")
    elif cmd == "stale":
        days = int(opt("--days", 45)); c = con(); cut = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        for r in c.execute("SELECT id, entity, topic, expires_at FROM facts WHERE superseded_by IS NULL AND expires_at < ?", (today(),)):
            print(f"fact #{r[0]} {r[1]}/{r[2]} expired {r[3]}")
        for r in c.execute("SELECT desk, source, relation, target, as_of FROM edges WHERE as_of < ?", (cut,)):
            print(f"edge {r[0]}: {r[1]} {r[2]} {r[3]} (as_of {r[4]})")
    elif cmd == "stats":
        c = con()
        q = lambda s: c.execute(s).fetchone()[0]
        print(f"files {q('SELECT count(*) FROM files')}, chunks {q('SELECT count(*) FROM docs')}, facts live {q('SELECT count(*) FROM facts WHERE superseded_by IS NULL')}, "
              f"cache entries {q('SELECT count(*) FROM http_cache')}, snapshots {q('SELECT count(*) FROM snapshots')}, edges {q('SELECT count(*) FROM edges')}, "
              f"ripple cache {q('SELECT count(*) FROM ripple_cache')}, db {os.path.getsize(DB)/1e6:.1f} MB")
    else: print(__doc__)

if __name__ == "__main__":
    main()
