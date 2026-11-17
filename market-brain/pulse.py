#!/usr/bin/env python3
"""World pulse: what is moving in markets and the world, where to look, and which desks are needed (owner, Nov 16, 2026).
PAPER ONLY. Information only: never a trade signal.

Owner: "you should have the proactivity and ability to call upon new helpers as broad market news evolves. This also
means that you need to have a pulse of what's going on in the world to know where to look and what new helpers you
might need. Build a system around that."

Each run:
 1. TAPE: every US-listed stock from the Nasdaq screener in one call (price change, market cap, sector, industry):
    market-cap-weighted sector and industry moves, big-cap movers (>= $10B, |move| >= 4%), breadth; plus cross-asset
    ETF proxies (rates, credit, dollar, oil, gold, bitcoin, small caps, vol) via the book's price module.
 2. NEWS: broad feeds (CNBC top/markets/economy/tech/world/politics, MarketWatch, FT markets) + Google News queries on
    macro themes. Everything goes through the brain cache (3h), so repeat runs are cheap.
 3. TOPICS: headlines are embedded and clustered into topics; each topic gets entities, sources, novelty (share of
    headlines never seen before), market link (moves of its entities/industries), book reach (ripple links to holdings
    and candidates) and a heat score. Topics are stored daily, so the pulse knows what is NEW, RISING or FADING.
 4. COVERAGE: each hot topic is matched against the desk registry (desks.py). Output: COVERED by <desk> /
    UNCOVERED (suggested desk with a create command). Also flags industries moving hard that no desk watches.
Output: /home/user/workspace/investing-3-6month-agent/project/data/pulse/YYYY-MM-DD-HHMM.md (ingested by the brain).
Usage: python3 /home/user/workspace/market-brain/pulse.py [--top 12] [--no-tape]
"""
import os, sys, re, json, html, hashlib, datetime as dt, xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brain, desks
PROJ = "/home/user/workspace/investing-3-6month-agent/project"
sys.path.insert(0, f"{PROJ}/scripts")

FEEDS = {
    "CNBC top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC finance": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "CNBC investing": "https://www.cnbc.com/id/15839069/device/rss/rss.html",
    "CNBC economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "CNBC world": "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "CNBC politics": "https://www.cnbc.com/id/10000113/device/rss/rss.html",
    "CNBC business": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "MarketWatch top": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch pulse": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "FT markets": "https://www.ft.com/markets?format=rss",
}
QUERIES = ["stock market today", "Federal Reserve rates", "Treasury yields", "oil prices", "tariffs trade", "AI stocks",
           "earnings guidance", "geopolitics markets", "China economy", "jobs report inflation", "merger acquisition",
           "regulation antitrust", "Bank of Canada", "credit markets", "crypto bitcoin", "commodities copper gold"]
ETFS = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "small caps", "RSP": "equal weight", "TLT": "long Treasuries",
        "HYG": "high yield", "UUP": "US dollar", "USO": "oil", "GLD": "gold", "IBIT": "bitcoin", "VIXY": "volatility",
        "SMH": "semis", "XLE": "energy", "XLV": "health care", "XLF": "financials", "XLI": "industrials", "XLY": "discretionary",
        "XLP": "staples", "XLU": "utilities", "XLRE": "real estate", "XLB": "materials", "XLC": "comm services", "XLK": "tech"}
UA = {"User-Agent": "Mozilla/5.0"}
MACRO = {r"\b(fed|fomc|rate hike|rate cut|treasury|yields?|powell|warsh|goolsbee|waller)\b": "US 10y yield",
         r"\b(oil|brent|crude|opec)\b": "Brent crude", r"\b(iran|hormuz)\b": "Iran war", r"\btariffs?\b": "Tariffs",
         r"\b(data cent(er|re)s?)\b": "DC permitting/moratoria", r"\b(capex|hyperscaler)\b": "Hyperscaler capex",
         r"\b(defen[cs]e budget|stopgap|continuing resolution|pentagon)\b": "US defense topline",
         r"\b(bank of canada|macklem|loonie|canadian dollar)\b": "Bank of Canada"}

def f(x):
    try: return float(str(x).replace("$", "").replace(",", "").replace("%", ""))
    except Exception: return None

# ---------- tape ----------
def tape():
    import prices as P
    body = brain.cached_get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true", 900,
                            kind="nasdaq", fetch=lambda u, h: json.dumps(P._curl(["-H", "Accept: application/json", u])).encode())
    rows = []
    try: rows = json.loads(body)["data"]["rows"]
    except Exception: pass
    st = [r for r in rows if f(r.get("marketCap")) and f(r.get("pctchange")) is not None]
    if len(st) < 3000:
        return {"ok": False, "n": len(st)}
    sec, ind = {}, {}
    for r in st:
        mc, ch = f(r["marketCap"]), f(r["pctchange"])
        if mc < 2e9 or abs(ch) > 60: continue
        for dct, k in ((sec, r.get("sector") or "?"), (ind, r.get("industry") or "?")):
            a = dct.setdefault(k, [0, 0, 0]); a[0] += mc * ch; a[1] += mc; a[2] += 1
    sec = sorted(((k, v[0] / v[1], v[2]) for k, v in sec.items() if v[1]), key=lambda x: x[1])
    ind = sorted(((k, v[0] / v[1], v[2]) for k, v in ind.items() if v[1] and v[2] >= 4), key=lambda x: x[1])
    big = [r for r in st if f(r["marketCap"]) >= 1e10]
    movers = sorted([r for r in big if abs(f(r["pctchange"])) >= 4], key=lambda r: -abs(f(r["pctchange"])))
    adv = sum(1 for r in big if f(r["pctchange"]) > 0)
    etf = {}
    for t in ETFS:
        try:
            h = P.history(t); d = sorted(h)
            if len(d) >= 6: etf[t] = (100 * (h[d[-1]] / h[d[-2]] - 1), 100 * (h[d[-1]] / h[d[-6]] - 1))
        except Exception: pass
    return {"ok": True, "n": len(st), "sectors": sec, "industries": ind, "movers": movers[:30], "breadth": (adv, len(big)), "etf": etf}

# ---------- news ----------
def parse_rss(raw, src):
    out = []
    try:
        for it in ET.fromstring(raw).iter("item"):
            t = html.unescape(it.findtext("title") or "").strip()
            if not t: continue
            s = src
            if src.startswith("GN:") and " - " in t: t, s = t.rsplit(" - ", 1)[0], t.rsplit(" - ", 1)[1]
            out.append({"title": t, "src": s, "date": (it.findtext("pubDate") or "")[5:22], "_pub": it.findtext("pubDate") or "",
                        "desc": re.sub("<[^>]+>", "", html.unescape(it.findtext("description") or ""))[:240]})
    except Exception:
        pass
    return out

def news():
    import requests
    def fetch(u, h):
        s = requests.Session(); s.trust_env = False
        return s.get(u, headers=UA, timeout=20).content
    items, failed = [], []
    for name, u in FEEDS.items():
        raw = brain.cached_get(u, kind="news", raw=True, fetch=fetch)
        got = parse_rss(raw, name) if raw else []
        if not got: failed.append(name)
        items += got
    import urllib.parse
    for q in QUERIES:
        u = f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:1d')}&hl=en-US&gl=US&ceid=US:en"
        raw = brain.cached_get(u, kind="news", raw=True, fetch=fetch)
        got = parse_rss(raw, "GN:" + q)[:12] if raw else []
        if not got: failed.append("GN:" + q)
        items += got
    import email.utils
    cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)
    fluff = re.compile(r"(top wall street analysts|stocks? to buy|best .* stocks|dividend stocks for|motley fool|should you buy|is it time to buy|price prediction|\d+ (stocks|reasons)|millionaire|retire|social security|my favorite|screaming buy|cd rates|mortgage rates|savings rates|credit card|best high-yield)", re.I)
    kept = []
    for it in items:
        try:
            d = email.utils.parsedate_to_datetime(it.get("_pub") or "")
            if d and d.tzinfo and d < cut: continue
        except Exception:
            pass
        if fluff.search(it["title"]): continue
        kept.append(it)
    items = kept
    seen_t, out = set(), []
    for it in items:
        k = re.sub(r"[^a-z0-9 ]", "", it["title"].lower())[:70]
        if k in seen_t: continue
        seen_t.add(k); it["key"] = "pulse:" + hashlib.sha1(k.encode()).hexdigest()[:16]; out.append(it)
    return out, failed

# ---------- topics ----------
def cluster(items, thr=0.58):
    import numpy as np
    if not items: return []
    V = brain.embed([i["title"] + ". " + i["desc"][:120] for i in items])
    topics = []
    for i, v in enumerate(V):
        best, bs = None, thr
        for t in topics:
            s = float(t["c"] @ v)
            if s > bs: best, bs = t, s
        if best is None: topics.append({"c": v.copy(), "m": [i]})
        else:
            best["m"].append(i); c = best["c"] * (len(best["m"]) - 1) + v; best["c"] = c / (np.linalg.norm(c) + 1e-9)
    return [(t["c"], [items[i] for i in t["m"]]) for t in topics]

def merge(cl, thr=0.45):
    """merge clusters whose centroids are close and that share a named company"""
    import numpy as np
    ents = [set(brain.entities(" | ".join(i["title"] for i in its[:6]))) for _, its in cl]
    out = []
    for k, (v, its) in enumerate(cl):
        for o in out:
            if (o[2] & ents[k]) and float(o[0] @ v) > (0.3 if len(o[1]) >= 5 else thr):
                o[1].extend(its); c = o[0] + v; o[0][:] = c / (np.linalg.norm(c) + 1e-9); o[2] |= ents[k]; break
        else:
            out.append([v.copy(), list(its), set(ents[k])])
    return [(v, its) for v, its, _ in out]

def history_table():
    c = brain.con()
    c.execute("CREATE TABLE IF NOT EXISTS pulse_topics(day TEXT, label TEXT, entities TEXT, heat REAL, n INTEGER, vec BLOB)")
    c.commit(); return c

def score_topics(cl, tp):
    import numpy as np
    pos, cand = desks.book_names()
    moves = {}
    if tp.get("ok"):
        for r in tp["movers"]: moves[r["symbol"]] = f(r["pctchange"])
    c = history_table()
    prev = c.execute("SELECT day, label, heat, vec FROM pulse_topics WHERE day >= ? AND day < ?",
                     ((dt.date.today() - dt.timedelta(days=7)).isoformat(), dt.date.today().isoformat())).fetchall()
    PV = np.frombuffer(b"".join(p[3] for p in prev), dtype="float32").reshape(len(prev), -1) if prev else None
    out = []
    for vec, its in cl:
        srcs = {i["src"] for i in its}
        text = " | ".join(i["title"] for i in its[:8])
        ents = set(brain.entities(text))
        low = text.lower()
        for kw, node in MACRO.items():
            if re.search(kw, low): ents.add(node)
        seen = brain.seen([i["key"] for i in its])
        novelty = 1 - len(seen) / len(its)
        mkt = sum(abs(moves.get(e, 0)) for e in ents)
        reach = set()
        for e in list(ents)[:6]:
            if e in pos or e in cand: reach.add(f"{e} direct")
            try:
                res, _ = brain.ripple(e, 1)
                for n, how, ex, se, no, desk in res["first"]:
                    if (n in pos or n in cand) and brain.SENS.get(se, 1) >= 2: reach.add(f"{n} via {e}")
            except Exception: pass
        heat = len(srcs) * 1.0 + len(its) * 0.4 + min(mkt, 20) * 0.3 + len(reach) * 0.8 + novelty * 1.5
        trend = "NEW"
        if PV is not None:
            sims = PV @ vec; j = int(np.argmax(sims))
            if sims[j] > 0.6:
                trend = f"RISING (was {prev[j][2]:.1f} on {prev[j][0]})" if heat > prev[j][2] * 1.2 else \
                        f"FADING (was {prev[j][2]:.1f} on {prev[j][0]})" if heat < prev[j][2] * 0.7 else f"ONGOING (since {prev[j][0]})"
        ents_l, reach_l, scores = desks.match(text, list(ents))
        cov = None
        if scores and scores[0][0] >= 3: cov = scores[0][1]
        out.append({"label": its[0]["title"], "items": its, "srcs": srcs, "ents": sorted(ents), "novelty": novelty,
                    "mkt": mkt, "reach": sorted(reach), "heat": heat, "trend": trend, "covered": cov, "vec": vec,
                    "desk_scores": scores[:2]})
    out.sort(key=lambda x: -x["heat"])
    return out, c

def slugify(s): return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40]

def main():
    a = sys.argv[1:]; top = int(a[a.index("--top") + 1]) if "--top" in a else 12
    now = dt.datetime.now(); L = [f"# World pulse, {now:%Y-%m-%d %H:%M} ET", "Information only. Use it to decide where to look and which desks to call; never a trade signal.", ""]
    tp = {"ok": False} if "--no-tape" in a else tape()
    if tp.get("ok"):
        adv, n = tp["breadth"]
        L.append(f"## Tape ({tp['n']} US stocks; big caps advancing {adv}/{n})")
        L.append("Cross-asset (1d / 5d): " + ", ".join(f"{ETFS[t]} {v[0]:+.1f}/{v[1]:+.1f}" for t, v in tp["etf"].items()))
        L.append("Sectors (cap-weighted, >= $2B): " + ", ".join(f"{k} {v:+.1f}%" for k, v, nn in tp["sectors"]))
        L.append("Weakest industries: " + "; ".join(f"{k} {v:+.1f}% ({nn})" for k, v, nn in tp["industries"][:6]))
        L.append("Strongest industries: " + "; ".join(f"{k} {v:+.1f}% ({nn})" for k, v, nn in tp["industries"][-6:][::-1]))
        L.append("Big-cap movers (>= $10B, |move| >= 4%): " + ", ".join(f"{r['symbol']} {f(r['pctchange']):+.1f}%" for r in tp["movers"][:20]))
        # industries moving hard that no desk watches (by any mover in it)
        watched = {w.upper() for d in desks.active(desks.load()).values() for w in d.get("watch", [])}
        try:
            c0 = brain.con(); watched |= {x.upper() for (x,) in c0.execute("SELECT source FROM edges UNION SELECT target FROM edges")}; c0.close()
        except Exception: pass
        orphan = [r for r in tp["movers"] if r["symbol"].upper() not in watched and f(r["marketCap"]) >= 2e10]
        if orphan:
            L.append("Large movers no desk or ripple map covers: " + ", ".join(f"{r['symbol']} {f(r['pctchange']):+.1f}% ({r.get('industry','')[:40]})" for r in orphan[:10]))
    else:
        L.append(f"## Tape: UNKNOWN (screener returned {tp.get('n', 0)} rows); not used as evidence")
    items, failed = news()
    L.append(f"\n## Topics ({len(items)} unique headlines from {len(FEEDS) + len(QUERIES) - len(failed)} feeds/queries; failed: {', '.join(failed) or 'none'})")
    topics, c = score_topics(merge(sorted(cluster(items), key=lambda x: -len(x[1]))), tp)
    uncovered = []
    for i, t in enumerate(topics[:top], 1):
        cov = f"COVERED by {t['covered']}" if t["covered"] else "UNCOVERED"
        L.append(f"\n### {i}. {t['label']}")
        L.append(f"- heat {t['heat']:.1f} | {t['trend']} | {len(t['items'])} headlines, {len(t['srcs'])} sources | novelty {100*t['novelty']:.0f}% | {cov}")
        L.append(f"- entities: {', '.join(t['ents']) or '-'} | book reach: {', '.join(t['reach'][:8]) or 'none'}")
        for it in t["items"][:4]: L.append(f"  - {it['title']} ({it['src']}, {it['date']})")
        if not t["covered"] and (t["reach"] or t["heat"] >= 6):
            uncovered.append(t)
            L.append(f"- SUGGESTED DESK: `python3 /home/user/workspace/market-brain/desks.py create {slugify(t['label'])} --kind event "
                     f"--title \"...\" --scope \"...\" --watch {','.join(t['ents'][:8]) or 'TICKERS'} --expires {(dt.date.today()+dt.timedelta(days=10)).isoformat()}`")
    L.append("\n## Where to look")
    L.append("- Hottest topics touching the book: " + ("; ".join(f"{t['label'][:70]} -> {', '.join(t['reach'][:4])}" for t in topics[:top] if t["reach"]) or "none"))
    L.append("- Uncovered and hot: " + ("; ".join(t["label"][:80] for t in uncovered) or "none"))
    rising = [t for t in topics[:top] if t["trend"].startswith(("NEW", "RISING"))]
    L.append("- New or rising: " + ("; ".join(t["label"][:70] for t in rising[:6]) or "none"))
    # persist
    day = dt.date.today().isoformat()
    c.execute("DELETE FROM pulse_topics WHERE day=?", (day,))
    for t in topics[:40]:
        c.execute("INSERT INTO pulse_topics VALUES(?,?,?,?,?,?)", (day, t["label"], " ".join(t["ents"]), t["heat"], len(t["items"]), t["vec"].tobytes()))
    c.commit(); c.close()
    brain.mark_seen([i["key"] for i in items])
    doc = "\n".join(L) + "\n"
    os.makedirs(f"{PROJ}/data/pulse", exist_ok=True)
    out = f"{PROJ}/data/pulse/{now:%Y-%m-%d-%H%M}.md"; open(out, "w").write(doc)
    print(doc); print(f"saved {out}")

if __name__ == "__main__":
    main()
