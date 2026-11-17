#!/usr/bin/env python3
"""Desk registry: flexible, reactive research subagents (owner, Nov 16, 2026). PAPER ONLY.

Owner: "We might keep needing new subagents based on new topics and events as they come. So make the system flexible
and reactive."

Desks are research subagents with a written scope. Three kinds:
  sector  standing industry desks (semis, cloud, healthcare, industrials, energy...). Live until retired.
  theme   multi-week cross-industry topics (Iran/oil geopolitics, AI-lab financing, GLP-1 pricing...). Expire.
  event   one catalyst (an earnings print, an IPO, an OPEC meeting, a Fed decision). Expire a few days after the event;
          on retirement their lasting findings are folded into the owning sector desk and the brain.
Registry: desks.json (next to this file). Every desk writes research/<sector: industries | theme/event: events>/<slug>.md,
optionally data/ripple_graph/<slug>.csv (merged into the ripple map automatically), and stores facts in the brain.

CLI (python3 /home/user/workspace/market-brain/desks.py ...):
  list [--all]                          active desks (or all incl. retired)
  route "event text" [--tickers A,B]    which desk(s) should handle this; suggests a NEW desk when nothing covers it
  create SLUG --kind event|theme|sector --title "..." --scope "..." --watch A,B,C [--expires YYYY-MM-DD]
         [--parent SECTOR_SLUG] [--book 3-6M]
  prompt SLUG --task "..."              full spawn prompt (standard template: recall first, files, remember, report)
  ran SLUG                              mark a run (for staleness tracking)
  retire SLUG [--note "..."]            retire (event/theme desks: fold findings into the parent first)
  review                                expired / stale / unused desks + coverage gaps (held or candidate names no desk watches)
Rules of thumb (see rules.md "Reactive desks"): at most 6 desk spawns per routine run; prefer an existing desk;
create an event desk only when the event can move a holding or candidate through a med/high ripple link.
"""
import os, sys, json, re, csv, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "desks.json")
PROJ = "/home/user/workspace/investing-3-6month-agent/project"
BOOK_FILES = {"3-6M": PROJ}

def load():
    return json.load(open(REG)) if os.path.exists(REG) else {"desks": {}}

def save(r):
    json.dump(r, open(REG + ".tmp", "w"), indent=1); os.replace(REG + ".tmp", REG)

def today(): return dt.date.today().isoformat()

def book_names(book="3-6M"):
    p = BOOK_FILES.get(book, PROJ)
    pos = {x["ticker"] for x in csv.DictReader(open(f"{p}/book/positions.csv")) if x.get("status") == "open"} - {"SGOV", "SPY"}
    cand = {x["ticker"] for x in csv.DictReader(open(f"{p}/book/targets.csv"))} - pos
    return pos, cand

def paths(d):
    folder = "industries" if d["kind"] == "sector" else "events"
    return f"research/{folder}/{d['slug']}.md", f"data/ripple_graph/{d['slug']}.csv"

def active(r):
    out = {}
    for s, d in r["desks"].items():
        if d.get("status") != "active": continue
        out[s] = d
    return out

def expired(d):
    return d.get("expires") and d["expires"] < today()

STOPW = {"and", "the", "for", "with", "from", "that", "this", "into", "over", "after", "before", "about", "its", "their", "new",
         "announces", "says", "said", "will", "has", "have", "are", "was", "were", "deal", "stock", "shares", "up", "down", "vs"}
def words(t): return {w for w in re.findall(r"[a-z0-9.]+", t.lower()) if len(w) > 2 and w not in STOPW}

def match(text, tickers=None):
    """returns (entities, book_reach, [(score, slug, overlap, keywords)]) without printing"""
    r = load(); tickers = {t.strip().upper() for t in (tickers or []) if t.strip()}
    sys.path.insert(0, HERE)
    try:
        import brain; tickers |= {e.upper() for e in brain.entities(text)}
    except Exception:
        pass
    tw = words(text); scores = []
    graph = {}
    try:
        import brain, sqlite3
        c = brain.con(); brain.import_graph()
        for desk, a, b in c.execute("SELECT desk, source, target FROM edges"):
            graph.setdefault(desk, set()).update({a.upper(), b.upper()})
        c.close()
    except Exception:
        pass
    for s, d in active(r).items():
        watch = {w.upper() for w in d.get("watch", [])}
        ov = tickers & watch
        gov = (tickers & graph.get(s, set())) - ov
        kw = tw & (words(d.get("scope", "")) | words(d.get("title", "")) | set(x.lower() for x in d.get("keywords", [])))
        score = 3 * len(ov) + 2 * len(gov) + len(kw) + (2 if d["kind"] == "event" and ov else 0)
        if score: scores.append((score, s, sorted(ov), sorted(kw)[:6]))
    scores.sort(reverse=True)
    # ripple reach: does it touch the book?
    reach = set()
    try:
        import brain
        pos, cand = book_names()
        for t in tickers:
            res, _ = brain.ripple(t, 1)
            for n, how, ex, se, no, desk in res["first"]:
                if (n in pos or n in cand) and brain.SENS.get(se, 1) >= 2: reach.add(f"{n} ({how} {t}, {se})")
            if t in pos or t in cand: reach.add(f"{t} (direct)")
    except Exception:
        pass
    return tickers, reach, scores

def route(text, tickers=None):
    r = load(); tickers, reach, scores = match(text, tickers)
    print(f"entities: {', '.join(sorted(tickers)) or '-'}")
    print(f"book reach (med/high links): {', '.join(sorted(reach)) or 'none found'}")
    if scores:
        print("matching desks:")
        for sc, s, ov, kw in scores[:4]:
            d = r["desks"][s]
            print(f"  {s} [{d['kind']}] score {sc}; watch overlap {ov or '-'}; keywords {kw or '-'}{' (EXPIRED)' if expired(d) else ''}")
    best = scores[0][0] if scores else 0
    if best < 3:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower())[:40].strip("_")
        print(f"no desk covers this well -> consider: desks.py create {slug} --kind event --title \"...\" --scope \"...\" "
              f"--watch {','.join(sorted(tickers)) or 'TICKERS'} --expires {(dt.date.today()+dt.timedelta(days=10)).isoformat()} "
              f"(only if book reach is non-empty)")

def create(slug, kind, title, scope, watch, expires=None, parent=None, book="3-6M", keywords=None):
    r = load()
    if slug in r["desks"] and r["desks"][slug].get("status") == "active":
        print(f"{slug} already active; use prompt/ran"); return
    if kind in ("event", "theme") and not expires:
        expires = (dt.date.today() + dt.timedelta(days=10 if kind == "event" else 60)).isoformat()
    r["desks"][slug] = {"slug": slug, "kind": kind, "title": title, "scope": scope, "watch": watch, "keywords": keywords or [],
                        "expires": expires, "parent": parent, "book": book, "status": "active", "created": today(),
                        "last_run": None, "runs": 0}
    save(r); md, g = paths(r["desks"][slug])
    print(f"created {slug} [{kind}] expires {expires or 'never'}; files {md}, {g}")

TEMPLATE = """You are the "{title}" desk ({kind} desk, slug {slug}) for the owner's {book} PAPER trading book. Paper only: never trade, never touch a brokerage. Today is {today} (ET).
Scope: {scope}
Watch list: {watch}{parent_line}{expiry_line}
Working folder: {proj}. You may edit ONLY {md} and {g} (create them if missing) plus brain facts. The book runs on "Trader framework v3: judgement over triggers": you supply information, synthesis and ideas; decisions stay with the book.

1. RECALL FIRST: read your existing {md} if present; run `python3 /home/user/workspace/market-brain/brain.py recall "<your key questions>"` and `brain.py facts <TICKER>` for the main names; `python3 scripts/ripple.py <TICKER>` for who is connected. Research only what memory doesn't answer or what has expired.
2. GATHER what is new: `python3 scripts/brief.py <tickers>` (consensus, revisions, ratings, insiders, filings, new headlines), primary sources (filings, transcripts, press releases), the finance tools, web search. Cite a URL for every material number; failed or partial data is UNKNOWN, never evidence.
3. YOUR TASK THIS RUN: {task}
4. WRITE {md}: Summary (3-5 lines, dated) / What happened and what it means (sourced) / Ripple: who wins and loses among suppliers, customers, competitors, adjacent industries, and how fast / What the market seems to have priced vs not / What would change the view / Dates to watch / Ideas outside the book (max 3, ideas only). Keep earlier dated sections below the new one (newest first) so the file is a running log.
5. GRAPH: add or refresh rows in {g} (header exactly: source,target,relation,exposure,sensitivity,note,source_url,as_of; relation in supplier_to, customer_of, competitor_of, adjacent_to, input_cost_for) for links this work revealed that the ripple map lacks. Skip if none.
6. REMEMBER: store each material finding with `python3 /home/user/workspace/market-brain/brain.py fact --entity T --topic X --claim "..." --source URL --ttl DAYS --by {slug}` (ttl 5-10 days for event specifics, 30 for positioning/prices, 90+ for structural facts). Then run `python3 /home/user/workspace/market-brain/desks.py ran {slug}` and `python3 /home/user/workspace/market-brain/brain.py ingest`.
7. REPORT back to the agent that spawned you (not to the owner): 5-8 bullets of implications for the book's holdings/candidates with sources, what is not priced in, any suggestion to create/retire a desk, up to 3 ideas. Under 400 words."""

def prompt(slug, task):
    r = load(); d = r["desks"].get(slug)
    if not d: print(f"unknown desk {slug}; create it first"); return
    md, g = paths(d)
    print(TEMPLATE.format(title=d["title"], kind=d["kind"], slug=slug, book=d.get("book", "3-6M"), today=today(), scope=d["scope"],
                          watch=", ".join(d.get("watch", [])) or "-",
                          parent_line=f"\nParent sector desk: {d['parent']} (read research/industries/{d['parent']}.md first)" if d.get("parent") else "",
                          expiry_line=f"\nThis desk expires {d['expires']}." if d.get("expires") else "",
                          proj=BOOK_FILES.get(d.get("book", "3-6M"), PROJ), md=md, g=g, task=task))

def ran(slug):
    r = load(); d = r["desks"][slug]; d["last_run"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M"); d["runs"] = d.get("runs", 0) + 1; save(r); print(f"{slug} run #{d['runs']} logged")

def retire(slug, note=""):
    r = load(); d = r["desks"][slug]; d["status"] = "retired"; d["retired"] = today(); d["retire_note"] = note; save(r)
    print(f"retired {slug}" + (f"; fold lasting findings into research/industries/{d['parent']}.md" if d.get("parent") else ""))

def review():
    r = load(); pos, cand = book_names(); act = active(r)
    print("EXPIRED (retire; fold lasting findings into the parent sector desk and the brain):")
    for s, d in act.items():
        if expired(d): print(f"  {s} [{d['kind']}] expired {d['expires']}")
    print("STALE (sector desks not run in 8+ days):")
    for s, d in act.items():
        lr = (d.get("last_run") or "2000-01-01")[:10]
        if d["kind"] == "sector" and (dt.date.today() - dt.date.fromisoformat(lr)).days >= 8: print(f"  {s} last run {d.get('last_run')}")
    covered = {w.upper() for d in act.values() for w in d.get("watch", [])}
    gaps = sorted((pos | cand) - covered)
    print(f"COVERAGE GAPS (held/candidate names no active desk watches): {', '.join(gaps) or 'none'}")
    print(f"ACTIVE: {len(act)} desks ({', '.join(f'{s}[{d['kind']}]' for s, d in act.items())})")

def ls(all_=False):
    r = load()
    for s, d in r["desks"].items():
        if not all_ and d.get("status") != "active": continue
        print(f"{s:28s} {d['kind']:6s} {d.get('status'):8s} exp {d.get('expires') or '-':10s} runs {d.get('runs', 0):2d} last {d.get('last_run') or '-':16s} watch {','.join(d.get('watch', []))[:70]}")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    opt = lambda k, dflt=None: a[a.index(k) + 1] if k in a else dflt
    c = a[0]
    if c == "list": ls("--all" in a)
    elif c == "route": route(a[1], (opt("--tickers", "") or "").split(","))
    elif c == "create": create(a[1], opt("--kind", "event"), opt("--title", a[1]), opt("--scope", ""), [x.strip() for x in (opt("--watch", "") or "").split(",") if x.strip()],
                               opt("--expires"), opt("--parent"), opt("--book", "3-6M"), [x.strip() for x in (opt("--keywords", "") or "").split(",") if x.strip()])
    elif c == "prompt": prompt(a[1], opt("--task", "routine refresh of your scope"))
    elif c == "ran": ran(a[1])
    elif c == "retire": retire(a[1], opt("--note", ""))
    elif c == "review": review()
    else: print(__doc__)

if __name__ == "__main__":
    main()
