#!/usr/bin/env python3
"""Daily post-mortem (owner, Oct 27, 2026: "every day you don't beat the market do a post mortem").
Run in the evening window AFTER `rotate.py mark` (and after any sells). PAPER ONLY. Usage: python3 scripts/postmortem.py [--force]
Prints today's book vs SPY (am + pm legs from book/daily.csv), each position's contribution since the prior close
(held names + names closed today), weighted book beta, sector contribution, and factor context (QQQ, IWM, RSP,
sector ETFs, TLT, USO). When the book lagged SPY today (or --force), appends a skeleton row to notes/bad_days.md;
the evening agent then fills in cause class, what we missed, and the lesson."""
import csv, json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rotate as R

def prev_close(t, d):
    rows = [r for r in R.bars(t) if r[0] < d]
    return rows[-1][4] if rows else None

def sector_map():
    m = {}
    for f in sorted(os.listdir("data/cands")) if os.path.isdir("data/cands") else []:
        if f.endswith(".csv"):
            for r in csv.DictReader(open(os.path.join("data/cands", f))): m[r["ticker"]] = r.get("sector") or "?"
    return m

def main():
    d = str(R.today()); force = "--force" in sys.argv
    rows = [r for r in csv.DictReader(open("book/daily.csv")) if r["date"] == d]
    if not rows: sys.exit(f"no marks for {d} yet: run rotate.py mark first")
    b = 1.0; s = 1.0
    for r in rows: b *= 1 + float(r["book_ret_net"]); s *= 1 + float(r["spy_ret"])
    exc = (b - 1) - (s - 1)
    print(f"POSTMORTEM {d}: book {100*(b-1):+.2f}% vs SPY {100*(s-1):+.2f}% -> excess {100*exc:+.2f} pts ({len(rows)} legs: "
          + ", ".join(f"{r['note'].split(' (')[0]} {100*float(r['ret_vs_spy']):+.2f}" for r in rows) + ")")
    st = R.load_state(); V = st.get("last_mark") or R.START_CASH; sec = sector_map(); pos = []
    from concurrent.futures import ThreadPoolExecutor as TP
    with TP(8) as ex: LV = dict(zip([h["ticker"] for h in st["holdings"]], ex.map(lambda h: R.live(h["ticker"])[0], st["holdings"])))
    for h in st["holdings"]:
        t = h["ticker"]; p = LV.get(t) or h["buy_price"]
        base = h["buy_price"] if h.get("date") == d else (prev_close(t, d) or h["buy_price"])
        r = p / base - 1; sgn = 1 if R.side(h) == "long" else -1; w = h["shares"] * p / V
        df = [x for x in R.bars(t) if x[0] < d]
        pos.append(dict(t=t, side=R.side(h), r=sgn * r, w=w, c=sgn * r * w, beta=R.beta60(df), sec=sec.get(t, "?"), st="held"))
    for r in csv.DictReader(open("book/positions.csv")) if os.path.exists("book/positions.csv") else []:
        vals = list(r.values())
        if vals[0] != d: continue
        t = vals[1].replace(" (short)", ""); short = "(short)" in vals[1]; sh, entry, ex = float(vals[2]), float(vals[3]), float(vals[4])
        base = entry if vals[6] == d else (prev_close(t, d) or entry); rr = ex / base - 1; sgn = -1 if short else 1
        df = [x for x in R.bars(t) if x[0] < d]
        pos.append(dict(t=t, side="short" if short else "long", r=sgn * rr, w=sh * ex / V, c=sgn * rr * sh * ex / V,
                        beta=R.beta60(df), sec=sec.get(t, "?"), st="closed today"))
    pos.sort(key=lambda x: x["c"])
    print("positions (contribution pts since prior close or entry):")
    for x in pos:
        print(f"  {x['t']:6} {x['side']:5} {x['st']:12} w {100*x['w']:4.0f}% ret {100*x['r']:+.2f}% contrib {100*x['c']:+.3f} beta {x['beta']} {x['sec']}")
    bb = sum((1 if x["side"] == "long" else -1) * x["w"] * (x["beta"] or 0) for x in pos if x["st"] == "held")
    gl = sum(x["w"] for x in pos if x["st"] == "held" and x["side"] == "long"); gs = sum(x["w"] for x in pos if x["st"] == "held" and x["side"] == "short")
    print(f"net book beta {bb:.2f} (long gross {100*gl:.0f}%, short gross {100*gs:.0f}%) -> a beta-only book would have made {100*bb*(s-1):+.2f}% today")
    bysec = {}
    for x in pos: bysec[x["sec"]] = bysec.get(x["sec"], 0) + x["c"]
    print("by sector:", " ".join(f"{k[:14]} {100*v:+.3f}" for k, v in sorted(bysec.items(), key=lambda kv: kv[1])))
    from concurrent.futures import ThreadPoolExecutor
    ets = ["SPY", "QQQ", "IWM", "RSP", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "TLT", "USO"]
    with ThreadPoolExecutor(8) as ex: lv = list(ex.map(lambda e: R.live(e)[0], ets))
    ctx = [f"{e} {100*(p/pc-1):+.2f}" for e, p in zip(ets, lv) for pc in [prev_close(e, d)] if pc and p]
    print("factor context (vs prior close):", " ".join(ctx))
    if exc < 0 or force:
        f = "notes/bad_days.md"
        if not os.path.exists(f):
            open(f, "w").write("# Bad days (book lagged SPY)\n\n| date | excess pts | net beta | cause class (factor tilt / stock-specific / timing / sizing) | cause | what we missed (signal we had before the window?) | lesson / rule candidate |\n|---|---|---|---|---|---|---|\n")
        if f"| {d} |" not in open(f).read():
            open(f, "a").write(f"| {d} | {100*exc:+.2f} | {bb:.2f} | TODO | TODO | TODO | TODO |\n")
            print(f"appended skeleton row to {f}: fill the TODOs")
    else:
        print("beat SPY today: no bad-day row")

if __name__ == "__main__":
    main()
