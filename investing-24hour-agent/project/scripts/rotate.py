#!/usr/bin/env python3
"""Two-window paper book (PAPER ONLY, never real trades). Run from project root. $100,000 (scaled from $5,000 on Oct 27, 2026), ~6 names (v4) held across windows.
Windows (owner, Oct 22, 2026): morning sell ~9:45 / buy ~10:00 ET, evening sell ~3:30 / buy ~3:45 ET. Each window: mark -> review -> sell -> buy.
Names are kept or replaced on thesis (technicals + news), not rotated by default; see notes/rules.md "Two-window playbook".
  python3 scripts/rotate.py regime                  -> risk flags + exposure level (FULL / HALF / DEFENSIVE)
  python3 scripts/rotate.py mark                    -> marks book + SPY/TQQQ controls, one row per window in book/daily.csv
  python3 scripts/rotate.py review                  -> each holding: entry, return, sessions held, RSI2, vs 50DMA, thesis
  python3 scripts/rotate.py candidates [N]          -> selection screen, top N to data/cands/<date>.csv
  python3 scripts/rotate.py sell T1 T2 --why "..."  -> sells named holdings at live prices (always before any buy)
  python3 scripts/rotate.py warm                    -> pre-fetch daily bars for the whole universe (run early in each window)
  python3 scripts/rotate.py buy LEVEL L1.. [--short S1..] [--why why.json] -> longs and paper shorts, $V/6 each (v4), then tops up longs to stay fully invested, within the level's gross caps
  (v2, the owner Oct 23, 2026: wider US universe, paper shorts, cut losers at -4%, let winners run on a trailing stop)
  python3 scripts/rotate.py shadow | stats
Every trade: book/trades.csv. Closed positions: book/positions.csv. Costs: 0.05% per side (COST)."""
import csv, json, os, sys, datetime as dt
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)
import prices
COST = 0.0005
START_CASH = 100000.0  # the owner, Oct 27, 2026: scaled x20 from $5,000; history restated
CONTROLS = ["SPY", "TQQQ"]  # buy-and-hold controls, $100,000 each (scaled from $5,000, Oct 27, 2026) (owner, Oct 22, 2026)
STATE = "book/state.json"
LEVELS = {  # v3.1 (owner, Oct 27, 2026: no SGOV/SPY/QQQ positions, beat the market with stocks): gross caps (max long, max short)
    "FULL": (1.0, 0.0), "HALF": (1.0, 0.0), "DEFENSIVE": (0.5, 0.0),
    "BEAR": (0.4, 0.3)}  # v4.1 (owner, Oct 28, 2026): shorts only on a high-conviction down call (rules.md "v4.1 BEAR gate"); gross 70%, never levered  # v4 (owner, Oct 28, 2026): never sit in cash; HALF = fully invested, DEFENSIVE 50% only on macro SHOCK
SLOTS = 6        # v4: concentrate in 6 names (~V/6 each)
MIN_BETA = 1.5   # v4: longs need 60d beta >= 1.5 (ETFs exempt) unless DEFENSIVE  # v3.2 (owner, Oct 27, 2026): shorts paused (backtest: shorts -88% of book 2016-26)
CORE = "SPY"; CORE_W = {"FULL": 0.0, "HALF": 0.0, "DEFENSIVE": 0.0}  # v3 core sleeve RETIRED same day (the owner): weight 0 sells any SPY held
NO_LONG = ("SPY", "QQQ", "SGOV", "RSP", "VOO", "IVV")  # the owner, Oct 27, 2026: never hold index/cash ETFs as longs
DEFENSIVE_SECTORS = ("Utilities", "Consumer Staples", "Real Estate")  # v3: no new longs here unless level is DEFENSIVE
HEDGE = ("SGOV", "SH", "SPY")  # legacy v1 hedge legs; sold at the first v2 window
STOP = None  # v3.2: -4% hard stop dropped (backtest: fills ~-5.7%, hurt in 3 of 4 tests); exit on TRAIL/TIME/BROKEN
TRAIL_ARM = 0.04; TRAIL_KEEP = 0.6; TIME_SESS = 5; TIME_MIN = 0.01
SCR_SECTOR = {"Technology": "Information Technology", "Finance": "Financials", "Energy": "Energy", "Health Care": "Health Care",
              "Consumer Discretionary": "Consumer Discretionary", "Consumer Staples": "Consumer Staples", "Industrials": "Industrials",
              "Basic Materials": "Materials", "Utilities": "Utilities", "Real Estate": "Real Estate", "Telecommunications": "Communication Services"}
ETFS = ["XLK","XLF","XLE","XLV","XLY","XLP","XLI","XLB","XLU","XLRE","XLC","SMH","IWM","QQQ","RSP","GLD",
        "SLV","TLT","USO","XBI","KRE","XHB","ARKK","KWEB","URA","XOP","ITB","IBIT"]
SECTOR_ETF = {"Information Technology":"XLK","Financials":"XLF","Energy":"XLE","Health Care":"XLV",
              "Consumer Discretionary":"XLY","Consumer Staples":"XLP","Industrials":"XLI","Materials":"XLB",
              "Utilities":"XLU","Real Estate":"XLRE","Communication Services":"XLC"}

def today(): return prices._now().date()
def window(): return "am" if prices._now().hour < 12 else "pm"  # two windows a day (owner, Oct 22): sell 9:45/buy 10:00, sell 3:30/buy 3:45 ET
def load_state():
    if os.path.exists(STATE): return json.load(open(STATE))
    return {"cash": START_CASH, "holdings": [], "level": None, "bought": None, "ctl": {}}
def save_state(s): json.dump(s, open(STATE, "w"), indent=1)
def append(path, row):
    with open(path, "a", newline="") as f: csv.writer(f).writerow(row)
def live(t):
    p, ts = prices.live(t)
    return p, ts
def sma(x, n): return sum(x[-n:]) / n if len(x) >= n else None


def bars(t, refresh=False):
    """Daily OHLCV rows [date, open, high, low, close, volume] from Nasdaq, cached in data/ohlcv/<T>.json (no pandas)."""
    P = prices; f = os.path.join("data", "ohlcv", t + ".json"); os.makedirs(os.path.dirname(f), exist_ok=True)
    if os.path.exists(f) and not refresh and dt.date.fromtimestamp(os.path.getmtime(f)) == dt.date.today():
        return json.load(open(f))
    s = P._nasdaq_sym(t); frm = (today() - dt.timedelta(days=400)).isoformat(); rows = []
    if P.alpaca_first() and not P.is_tsx(t): rows = P.alpaca_bars(t)
    for cls in ([] if rows else ["stocks", "etf"]):
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/quote/{s}/historical?assetclass={cls}&fromdate={frm}&todate={today()}&limit=400"])
        rr = (((d or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
        for r in rr:
            try:
                row = [dt.datetime.strptime(r["date"], "%m/%d/%Y").date().isoformat()] + [P._num(r[k]) for k in ("open", "high", "low", "close", "volume")]
                if None not in row: rows.append(row)
            except Exception: pass
        if rows: break
    if not rows and not P.is_tsx(t):
        rows = P.alpaca_bars(t)  # Nov 16, 2026: Alpaca fallback when the Nasdaq fetch fails (py.sh proxy)
    rows.sort()
    if rows: json.dump(rows, open(f, "w"))
    return rows

# ---------------- regime ----------------
def closes(t): h = prices.history(t); return [h[d] for d in sorted(h)]
def breadth():
    """% of S&P 500 above the 50DMA, or (None, note) when the data can't be trusted.
    Data-integrity rule (owner, Nov 16, 2026: never make a financial decision on a data error): needs >= 400 valid series;
    otherwise falls back to the last good reading from the previous 5 days (labelled stale), else UNKNOWN. Never 0%."""
    f = f"data/regime/breadth-{today()}.txt"
    if os.path.exists(f): return float(open(f).read()), "ok"
    import screen, glob
    sec = screen.sp500(); data = screen.series_batch(list(sec)) if sec else {}
    up = [cl[-1] > sma(cl, 50) for cl in data.values() if len(cl) >= 50]
    if len(up) >= 400:
        b = round(100 * sum(up) / len(up), 1)
        os.makedirs("data/regime", exist_ok=True); open(f, "w").write(str(b)); return b, "ok"
    prior = sorted(p for p in glob.glob("data/regime/breadth-*.txt") if p < f)
    if prior:
        d = dt.date.fromisoformat(prior[-1][-14:-4])
        if (today() - d).days <= 5:
            return float(open(prior[-1]).read()), f"STALE (only {len(up)} series today; using {d})"
    return None, f"UNKNOWN (only {len(up)} series, no reading in last 5 days)"
def regime():
    prev = load_state().get("level")
    spy = closes("SPY"); hyg = closes("HYG"); lqd = closes("LQD")
    if min(len(spy), len(hyg), len(lqd)) < 60:
        # Data-integrity rule (Nov 16, 2026): missing price history -> no regime change, keep yesterday's level
        lvl = prev or "FULL"
        out = dict(date=str(today()), level=lvl, data_quality=f"ERROR: price history short (SPY {len(spy)}, HYG {len(hyg)}, LQD {len(lqd)} bars); level held")
        os.makedirs("data/regime", exist_ok=True); json.dump(out, open(f"data/regime/{today()}.json", "w"), indent=1)
        print("DATA WARNING: regime inputs missing; level held at", lvl); print("REGIME", json.dumps(out)); return
    n = min(len(hyg), len(lqd)); ratio = [h / l for h, l in zip(hyg[-n:], lqd[-n:])]
    r_now, r_20, r_5ago = ratio[-1], sma(ratio, 20), ratio[-6]
    credit_falling = r_now < r_20 and (r_now / r_5ago - 1) <= -0.005
    b, bnote = breadth()
    flags = {"spy_below_20dma": spy[-1] < sma(spy, 20), "spy_below_50dma": spy[-1] < sma(spy, 50),
             "credit_falling": credit_falling, "breadth_weak": (None if b is None else b < 40.0)}
    nflags = sum(1 for v in flags.values() if v)
    # v3.1 (Oct 27, 2026): SPY below 20/50DMA did NOT predict weak next days over Sep 2025-Oct 2026 (next-day mean +0.16%/+0.21%
    # vs ~0% otherwise), so trend flags alone never de-risk. Step down only when credit AND breadth crack; DEFENSIVE if trend breaks too.
    stress = flags["credit_falling"] and flags["breadth_weak"]
    level = "FULL" if not stress else ("DEFENSIVE" if flags["spy_below_50dma"] else "HALF")
    if flags["breadth_weak"] is None and flags["credit_falling"] and prev:
        level = prev  # breadth unknown while credit cracks: can't tell stress from noise -> hold yesterday's level
    order = ["DEFENSIVE", "HALF", "FULL"]
    if prev in order and order.index(level) > order.index(prev) + 1:  # step up one level per day at most
        level = order[order.index(prev) + 1]
    out = dict(date=str(today()), level=level, nflags=nflags, flags=flags, spy=round(spy[-1], 2),
               spy_vs_20=round(100 * (spy[-1] / sma(spy, 20) - 1), 2), spy_vs_50=round(100 * (spy[-1] / sma(spy, 50) - 1), 2),
               hyg_lqd_5d=round(100 * (r_now / r_5ago - 1), 2), hyg_lqd_vs_20=round(100 * (r_now / r_20 - 1), 2), breadth_50dma=b, breadth_status=bnote,
               data_quality=("OK" if bnote == "ok" else "WARNING: breadth " + bnote))
    if bnote != "ok": print("DATA WARNING: breadth", bnote, "-> breadth flag", flags["breadth_weak"], "| level", level)
    os.makedirs("data/regime", exist_ok=True); json.dump(out, open(f"data/regime/{today()}.json", "w"), indent=1)
    print("REGIME", json.dumps(out))

# ---------------- sell ----------------
def value(s, quotes=None):
    """Book value = cash + holdings at live prices (net of the exit cost)."""
    q = quotes or {}; v = s["cash"]
    for h in s["holdings"]:
        p = q.get(h["ticker"]) or live(h["ticker"])[0] or h["buy_price"]; q[h["ticker"]] = p
        v += h["shares"] * p * (1 - COST) if side(h) == "long" else -h["shares"] * p * (1 + COST)
    return v, q
def side(h): return h.get("side", "long")
def pret(h, p): return p / h["buy_price"] - 1 if side(h) == "long" else 1 - p / h["buy_price"]
def gross(s, q, sd): return sum(h["shares"] * q.get(h["ticker"], h["buy_price"]) for h in s["holdings"] if side(h) == sd and h["ticker"] not in HEDGE)
def sessions_held(h):
    if not h.get("date"): return 0
    return len([x for x in bars("SPY") if h["date"] < x[0] < str(today())]) + (0 if h["date"] == str(today()) else 1)
def peak_ret(h, p):
    """Best side-adjusted return since entry: daily highs/lows after the entry day, plus the live price."""
    rows = [r for r in bars(h["ticker"]) if r[0] > h.get("date", "")]
    if side(h) == "long": best = max([r[2] for r in rows] + [p]); return best / h["buy_price"] - 1
    best = min([r[3] for r in rows] + [p]); return 1 - best / h["buy_price"]
def _earn_txt(t):
    try:
        e = earnings_ahead().get(t)
        return f"{e[0]} ({e[1]} sess, {e[2].replace('time-','')}) -> v4.3 decide SELL or HOLD-THROUGH before it" if e and e[1] <= 1 else (f"{e[0]} ({e[1]} sess)" if e else "none in 12 sess")
    except Exception: return "?"
def hint(h, p, r):
    """Mechanical exit hint for the v2 exits (rules.md 'Swing book v2'): STOP, TRAIL, TIME, or HOLD."""
    if h["ticker"] == CORE: return "SELL (index ETF not allowed; buy sells it)"
    if h["ticker"] in HEDGE: return "SELL (legacy hedge leg)"
    ret = pret(h, p); pk = max(peak_ret(h, p), ret); n = sessions_held(h)
    if side(h) == "short": return "COVER (v3.2: shorts paused)"
    if STOP is not None and ret <= STOP: return f"STOP ({100*ret:+.1f}%)"
    if pk >= TRAIL_ARM and ret < TRAIL_KEEP * pk: return f"TRAIL (peak {100*pk:+.1f}%, now {100*ret:+.1f}%)"
    if n >= TIME_SESS and ret < TIME_MIN and pk < TRAIL_ARM: return f"TIME ({n} sessions, {100*ret:+.1f}%)"
    if r and side(h) == "long" and r.get("s200") and r["price"] < r["s200"]: return "BROKEN (below 200DMA)"
    if r and side(h) == "short" and r.get("s50") and r["price"] > r["s50"]: return "BROKEN (short back above 50DMA)"
    return f"HOLD (peak {100*pk:+.1f}%{', trailing' if pk >= TRAIL_ARM else ''})"
def mark(note=""):
    """Step 1 of every window: mark book + controls at live prices, one row in book/daily.csv per window."""
    s = load_state(); d = str(today()); win = window()
    if s.get("marked") == f"{d}:{win}": print(f"already marked this window ({win})"); return
    if not s.get("ctl"): print(f"NOT STARTED: cash {s['cash']:.2f}, first buy sets the controls"); return
    v, q = value(s); prev = s.get("last_mark", v); book_ret = v / prev - 1
    ctl = {}
    for c in CONTROLS:
        cp, _ = live(c); pm = s["ctl"][c]["mark"]; val = s["ctl"][c]["shares"] * cp
        ctl[c] = (cp / pm - 1, val); s["ctl"][c]["mark"] = cp
        append(f"control/{c.lower()}.csv", [d, round(s["ctl"][c]["shares"], 6), round(cp, 4), round(val, 2)])
    spy_ret, spy_val = ctl["SPY"]; tq_ret, tq_val = ctl["TQQQ"]
    held = "overnight" if win == "am" else "day"
    append("book/daily.csv", [d, round(v, 2), round(spy_val, 2), round(tq_val, 2), round(book_ret, 5), round(spy_ret, 5),
                              round(tq_ret, 5), round(book_ret - spy_ret, 5), s["level"], f"{win} mark ({held} leg) {note}".strip()])
    s.update(last_mark=v, marked=f"{d}:{win}"); save_state(s)
    print(f"MARK {win} ({held} leg): book ${prev:.2f}->${v:.2f} ({100*book_ret:+.2f}%) | SPY {100*spy_ret:+.2f}% (${spy_val:.2f}) | TQQQ {100*tq_ret:+.2f}% (${tq_val:.2f}) | level {s['level']}")
def review():
    """Every holding with what's needed to decide keep or sell: return, sessions held, RSI2, vs 50DMA, 1d move."""
    s = load_state()
    if not s["holdings"]: print(f"NO HOLDINGS | cash {s['cash']:.2f}"); return
    q = {}
    for h in s["holdings"]:
        r = one(h["ticker"]) or {}; p = r.get("price") or live(h["ticker"])[0]; q[h["ticker"]] = p
        print(f"{h['ticker']:6} {side(h):5} entry {h['buy_price']} ({h.get('date','?')} {h.get('win','')}) now {p} {100*pret(h, p):+.2f}% | "
              f"sessions {sessions_held(h)} | beta {r.get('beta','-')} | rsi2 {r.get('rsi2','-')} | vs50 {r.get('vs50','-')}% | 1d {r.get('r1','-')}% | {hint(h, p, r)} | earnings {_earn_txt(h['ticker'])} | thesis: {h.get('why','')}")
    V, _ = value(s, q)
    print(f"cash {s['cash']:.2f} | level {s['level']} | book {V:.2f} | long gross {100*gross(s,q,'long')/V:.0f}% | short gross {100*gross(s,q,'short')/V:.0f}% | "
          f"core {CORE} {100*sum(h['shares']*q.get(h['ticker'],h['buy_price']) for h in s['holdings'] if h['ticker']==CORE)/V:.0f}% | "
          f"longs {len([h for h in s['holdings'] if side(h)=='long' and h['ticker'] not in HEDGE])} shorts {len([h for h in s['holdings'] if side(h)=='short'])}")
def sell(tks, reason=""):
    """Sell named holdings at live prices. Always run before any buy in a window (Owner: sell before buy)."""
    s = load_state(); d = str(today()); win = window(); keep = []
    for h in s["holdings"]:
        if h["ticker"] not in tks: keep.append(h); continue
        p, ts = live(h["ticker"])
        if not p: print(f"NO QUOTE {h['ticker']}: kept"); keep.append(h); continue
        ret = pret(h, p)
        if side(h) == "long": val = h["shares"] * p * (1 - COST); s["cash"] += val; act = "SELL"
        else: val = h["shares"] * p * (1 + COST); s["cash"] -= val; act = "COVER"
        tk = h["ticker"] if side(h) == "long" else h["ticker"] + " (short)"
        append("book/positions.csv", [d, tk, round(h["shares"], 6), h["buy_price"], round(p, 4), round(ret, 5), h.get("date", ""), win, reason])
        append("book/trades.csv", [d, ts, win, act, h["ticker"], round(h["shares"], 6), round(p, 4), round(val, 2), reason])
        print(f"{act} {h['ticker']} {h['buy_price']}->{p:.2f} {100*ret:+.2f}% @ {ts} ({reason})")
    s["holdings"] = keep; s["sold_at"] = f"{d}:{win}"; save_state(s)
    print(f"cash {s['cash']:.2f} | holding {len(keep)}")
VOL_REF = 3.0   # v4.4 (owner, Oct 28, 2026): volatility sizing, weight = VOL_REF / 14d ATR%, clipped 0.6-1.5, normalised to mean 1
def vol_w(ticks):
    raw = {}
    for t in ticks:
        a = (one(t) or {}).get("atr") or VOL_REF
        raw[t] = max(0.6, min(1.5, VOL_REF / max(a, 0.5)))
    m = sum(raw.values()) / len(raw) if raw else 1
    return {t: round(w / m, 3) for t, w in raw.items()}
TOPUP_ONLY = None  # v5-news (Nov 13, 2026): set by --topup T1,T2 (only these holdings get top-ups) or --no-topup (empty set)
def _conv_mult(w):
    """v6.2 (Nov 17, 2026): size by CONVICTION in the why line: 5 -> 1.5x, 4 -> 1.0x, 3 -> 0.5x; missing -> 1.0x."""
    import re as _re
    m = _re.search(r'CONVICTION\s*:\s*([1-5])', w or '')
    return {5: 1.5, 4: 1.0, 3: 0.5}.get(int(m.group(1)), 0.0) if m else 1.0
def buy(level, tks, why=None, shorts=()):
    """v2: open longs (tks) and paper shorts at $V/SLOTS each (v4: 6), within the level's gross caps (LEVELS). Legacy SGOV/SH legs are sold first.
    Refuses if this window has not been marked (mark -> sell -> buy)."""
    level = level.upper(); assert level in LEVELS, level
    s = load_state(); d = str(today()); win = window(); why = why or {}
    if s.get("ctl") and s.get("marked") != f"{d}:{win}": sys.exit("mark this window first (mark -> sell -> buy)")
    leg = [h["ticker"] for h in s["holdings"] if h["ticker"] in HEDGE and h["ticker"] != CORE]
    if leg: sell(leg, "v2: hedge legs retired, shorts replace them"); s = load_state()
    cap_l, cap_s = LEVELS[level]
    V, q = value(s); slot = V / SLOTS
    # v3 core sleeve: bring SPY to CORE_W[level] of book (only if off by > 2% of book)
    cp, cts = live(CORE); tgt = CORE_W[level] * V
    ch = next((h for h in s["holdings"] if h["ticker"] == CORE), None); cur = ch["shares"] * cp if (ch and cp) else 0.0
    if cp and abs(tgt - cur) > 0.02 * V:
        q[CORE] = cp
        if tgt > cur:
            amt = min(tgt - cur, max(s["cash"], 0)); sh = amt * (1 - COST) / cp
            if amt > 1:
                if ch: ch["buy_price"] = round((ch["shares"] * ch["buy_price"] + sh * cp) / (ch["shares"] + sh), 4); ch["shares"] += sh
                else: s["holdings"].append(dict(ticker=CORE, side="long", shares=sh, buy_price=round(cp, 4), date=d, win=win, why="core sleeve"))
                s["cash"] -= amt; append("book/trades.csv", [d, cts, win, "BUY", CORE, round(sh, 6), round(cp, 4), round(amt, 2), f"core to {100*CORE_W[level]:.0f}%"])
                print(f"CORE BUY {CORE} {sh:.4f} sh @ {cp:.2f} (${amt:.2f})")
        else:
            sh = min((cur - tgt) / cp, ch["shares"]); val = sh * cp * (1 - COST); ch["shares"] -= sh; s["cash"] += val
            append("book/positions.csv", [d, CORE, round(sh, 6), ch["buy_price"], round(cp, 4), round(cp / ch["buy_price"] - 1, 5), ch.get("date", ""), win, f"core trim to {100*CORE_W[level]:.0f}%"])
            append("book/trades.csv", [d, cts, win, "SELL", CORE, round(sh, 6), round(cp, 4), round(val, 2), f"core trim to {100*CORE_W[level]:.0f}%"])
            print(f"CORE SELL {CORE} {sh:.4f} sh @ {cp:.2f} (${val:.2f})")
            if ch["shares"] < 1e-6: s["holdings"].remove(ch)
    held = {h["ticker"] for h in s["holdings"]}
    W = vol_w([h["ticker"] for h in s["holdings"] if side(h) == "long" and h["ticker"] not in HEDGE] + [t for t in tks if t not in held] + list(shorts))
    if W: print("v4.4 vol weights: " + ", ".join(f"{t} {w}" for t, w in W.items()))
    for sd, names, cap in (("long", tks, cap_l), ("short", shorts, cap_s)):
        for t in names:
            if t in held or (sd == "long" and t in NO_LONG): print(f"SKIP {t} (held, or index/cash ETF not allowed)"); continue
            room = cap * V - gross(s, q, sd)
            p, ts = live(t); sl = slot * W.get(t, 1) * _conv_mult(why.get(t, "")); amt = min(sl, room, s["cash"]) if sd == "long" else min(sl, room)
            if not p or amt < 0.25 * slot: print(f"SKIP {t} ({'no quote' if not p else 'no room under ' + level + ' ' + sd + ' cap'})"); continue
            q[t] = p
            if sd == "long": sh = amt * (1 - COST) / p; s["cash"] -= amt; act = "BUY"
            else: sh = amt / p; s["cash"] += amt * (1 - COST); act = "SHORT"
            s["holdings"].append(dict(ticker=t, side=sd, shares=sh, buy_price=round(p, 4), date=d, win=win, why=why.get(t, "")))
            held.add(t)
            append("book/trades.csv", [d, ts, win, act, t, round(sh, 6), round(p, 4), round(amt, 2), why.get(t, "")])
            print(f"{act} {t} {sh:.4f} sh @ {p:.2f} (${amt:.2f}) {ts}")
    # v4: never sit in cash. Top up existing longs toward equal weight with leftover cash, up to the long cap.
    longs = [h for h in s["holdings"] if side(h) == "long" and h["ticker"] not in HEDGE]
    if TOPUP_ONLY is not None:
        longs = [h for h in longs if h["ticker"] in TOPUP_ONLY or h["ticker"] in tks]
        print("v5-news top-up limited to: " + (", ".join(h["ticker"] for h in longs) or "none (cash kept)"))
    for _ in range(3):
        room = min(cap_l * V - gross(s, q, "long"), s["cash"])
        if room < 0.02 * V or not longs: break
        tgt = (gross(s, q, "long") + room) / max(len(longs), SLOTS) if len(longs) >= SLOTS else slot
        for h in sorted(longs, key=lambda h: h["shares"] * q.get(h["ticker"], h["buy_price"])):
            cur = h["shares"] * q.get(h["ticker"], h["buy_price"])
            add = min(tgt * W.get(h["ticker"], 1) * _conv_mult(h.get("why", "")) - cur, min(cap_l * V - gross(s, q, "long"), s["cash"]))
            if add < 0.01 * V: continue
            p, ts = live(h["ticker"])
            if not p: continue
            q[h["ticker"]] = p; sh = add * (1 - COST) / p
            h["buy_price"] = round((h["shares"] * h["buy_price"] + sh * p) / (h["shares"] + sh), 4); h["shares"] += sh; s["cash"] -= add
            append("book/trades.csv", [d, ts, win, "BUY", h["ticker"], round(sh, 6), round(p, 4), round(add, 2), "v4 top-up: stay fully invested (v4.4 vol-weighted)"])
            print(f"TOPUP {h['ticker']} {sh:.4f} sh @ {p:.2f} (${add:.2f})")
    s.setdefault("ctl", {})
    for c in CONTROLS:
        cp, _ = live(c)
        if c not in s["ctl"]:
            s["ctl"][c] = dict(shares=START_CASH / cp, mark=cp, start=cp)
            append(f"control/{c.lower()}.csv", [d, round(START_CASH / cp, 6), round(cp, 4), START_CASH]); print(f"CONTROL {c} {START_CASH/cp:.4f} sh @ {cp:.2f}")
    V2, q = value(s, q); s.update(level=level, last_mark=V2)
    if win == "pm": s.setdefault("baskets", {})[d] = dict(level=level, tickers=[h["ticker"] for h in s["holdings"]],
        weights=[(1 if side(h) == "long" else -1) * h["shares"] * h["buy_price"] / V2 for h in s["holdings"]])
    save_state(s)
    print(f"LEVEL {level} | book ${V2:.2f} | cash ${s['cash']:.2f} | long gross {100*gross(s,q,'long')/V2:.0f}% (cap {100*cap_l:.0f}%) | short gross {100*gross(s,q,'short')/V2:.0f}% (cap {100*cap_s:.0f}%)")

# ---------------- candidates ----------------
def earnings_block():
    """Names reporting after today's close or before the next session opens."""
    import prices as P
    t0 = today(); nxt = t0 + dt.timedelta(days=1)
    while nxt.weekday() >= 5: nxt += dt.timedelta(days=1)
    out = set()
    for day, skip_pre in ((t0, True), (nxt, False)):
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"]) or {}
        for r in ((d.get("data") or {}).get("rows") or []):
            if skip_pre and r.get("time") == "time-pre-market": continue
            if not skip_pre and r.get("time") == "time-after-hours": continue
            out.add(r["symbol"].replace(".", "-"))
    return out
_EA = {}
def earnings_ahead(sessions=12):
    """v4.3: {ticker: (date, sessions_until, time)} for reports in the next N sessions (nasdaq calendar, cached per day)."""
    if _EA: return _EA
    import prices as P
    f = f"data/earn_ahead_{today()}.json"
    if os.path.exists(f):
        _EA.update({k: tuple(v) for k, v in json.load(open(f)).items()}); return _EA
    d0 = today(); k = 0; day = d0
    while k < sessions:
        day += dt.timedelta(days=1)
        if day.weekday() >= 5: continue
        k += 1
        d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/calendar/earnings?date={day}"]) or {}
        for r in ((d.get("data") or {}).get("rows") or []):
            t = r["symbol"].replace(".", "-")
            if t not in _EA: _EA[t] = (str(day), k, r.get("time", ""))
    os.makedirs("data", exist_ok=True); json.dump(_EA, open(f, "w"))
    return _EA
def rsi2(cl):
    import screen
    return screen.rsi(cl[-60:], 2)
def one(t, fast=False):
    """fast=True prices off the screener's last sale (can be the prior close); candidates() re-prices survivors live."""
    try:
        df = [r for r in bars(t) if r[0] < str(today())]
        hi = [r[2] for r in df]; lo = [r[3] for r in df]
        if len(df) < 210: return None
        cl = [r[4] for r in df]; vol = [r[5] for r in df]; op = [r[1] for r in df]
        p = (QUOTE.get(t) if fast else None) or live(t)[0]
        if not p: return None
        c = cl + [p]
        adv = sum(v * x for v, x in zip(vol[-20:], cl[-20:])) / 20
        return dict(ticker=t, price=round(p, 2), adv_m=round(adv / 1e6, 1), s50=sma(c, 50), s200=sma(c, 200),
                    vs50=round(100 * (p / sma(c, 50) - 1), 2), r1=round(100 * (p / cl[-1] - 1), 2), r3=round(100 * (p / cl[-3] - 1), 2),
                    r21=round(100 * (p / c[-22] - 1), 2), rsi2=round(rsi2(c), 1), relvol=round(vol[-1] / (sum(vol[-21:-1]) / 20), 2),
                    gap_last=round(100 * (op[-1] / cl[-2] - 1), 2), last_day=round(100 * (cl[-1] / cl[-2] - 1), 2),
                    atr=round(100 * sum(max(hi[i], cl[i-1]) - min(lo[i], cl[i-1]) for i in range(-14, 0)) / 14 / cl[-1], 2),
                    hi20=p >= max(hi[-20:]), lo20=p <= min(lo[-20:]), beta=beta60(df))
    except Exception:
        return None
_SPYC = {}
def beta60(df):
    """v3: 60-day daily beta vs SPY from cached bars (None if not enough overlap)."""
    try:
        if not _SPYC: _SPYC.update({r[0]: r[4] for r in bars("SPY")})
        sp = _SPYC; ds = [r[0] for r in df if r[0] in sp][-61:]; m = {r[0]: r[4] for r in df}
        if len(ds) < 40: return None
        a = [m[ds[i]] / m[ds[i-1]] - 1 for i in range(1, len(ds))]; b = [sp[ds[i]] / sp[ds[i-1]] - 1 for i in range(1, len(ds))]
        ma, mb = sum(a) / len(a), sum(b) / len(b); vb = sum((x - mb) ** 2 for x in b)
        return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / vb, 2) if vb else None
    except Exception: return None
QUOTE = {}  # screener last sale, used by candidates() instead of one live call per name
def universe():
    """v2 universe (owner, Oct 23, 2026: wider swings across many more stocks): every US-listed stock on the Nasdaq screener with
    price >= $5, market cap >= $2B and >= $20M traded today, plus liquid ETFs. Sector: S&P GICS where known, else the screener's."""
    import screen, prices as P
    sp = screen.sp500(); out = {}
    d = P._curl(["-H", "Accept: application/json", "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"]) or {}
    num = lambda x: P._num(str(x).replace("$", "")) or 0
    for r in ((d.get("data") or {}).get("rows") or []):
        t = r["symbol"].strip()
        if any(c in t for c in "^/ ") or num(r["lastsale"]) < 5 or num(r["marketCap"]) < 2e9 or num(r["volume"]) * num(r["lastsale"]) < 2e7: continue
        t = t.replace(".", "-"); QUOTE[t] = num(r["lastsale"]); out[t] = sp.get(t) or SCR_SECTOR.get(r.get("sector", ""), r.get("sector") or "Other")
    if len(out) < 600: print(f"screener thin ({len(out)}), adding S&P 500"); out.update({k: v for k, v in sp.items() if k not in out})
    for e in ETFS: out[e] = "ETF"
    return out
def warm():
    u = universe()
    with ThreadPoolExecutor(16) as ex: ok = sum(1 for r in ex.map(bars, list(u)) if len(r) >= 210)
    print(f"warmed {ok}/{len(u)} names with 210+ daily bars")
def candidates(n=25):
    """Longs (pullback in uptrend, or volume breakout) to data/cands/<date>.csv and shorts (bounce in downtrend) to <date>-short.csv."""
    sec = universe(); tick = list(sec)
    with ThreadPoolExecutor(16) as ex: pre = [r for r in ex.map(lambda t: one(t, True), tick) if r]
    keep = [r["ticker"] for r in pre if r["ticker"] in ETFS or (r["s50"] > r["s200"] and r["price"] > r["s200"])
            or (r["s50"] < r["s200"] and r["price"] < 1.03 * r["s50"])]  # trend structure, with slack
    with ThreadPoolExecutor(16) as ex: rows = [r for r in ex.map(one, keep) if r]   # live prices for the survivors
    by = {r["ticker"]: r for r in rows}; spy = by.get("SPY") or one("SPY")
    blocked = earnings_block(); earn = earnings_ahead(); longs, shorts = [], []; lvl = load_state().get("level", "FULL")
    for r in rows:
        r["sector"] = sec.get(r["ticker"], "ETF")
        if r["price"] < 5 or r["adv_m"] < 25 or r["ticker"] in NO_LONG: continue
        if r["ticker"] in blocked: r["earn"] = 1; continue
        se = by.get(SECTOR_ETF.get(r["sector"], ""))
        r["sec_rs"] = round((se["r21"] - spy["r21"]) if se and spy else 0.0, 2)
        swing = min(r["atr"] / 2, 3) * 0.5               # wider swings: +0.5 per 2% daily range, up to +1.5
        ea = earn.get(r["ticker"]); r["earn_date"] = ea[0] if ea else ""; r["earn_in"] = ea[1] if ea else ""
        lng_ok = r["sector"] == "ETF" or lvl in ("DEFENSIVE", "BEAR") or ((r.get("beta") or 0) >= MIN_BETA and r["sector"] not in DEFENSIVE_SECTORS)
        if (lng_ok and r["s50"] > r["s200"] and r["price"] > r["s200"] and r["rsi2"] < 10
                and (-15 <= r["r1"] <= -6 or -18 <= r["r3"] <= -8)):
            # v4.3 FLUSH (owner, Oct 28, 2026): sharp oversold drop inside an intact long-term uptrend; buy only if news says overreaction
            sc = (10 - r["rsi2"]) / 10 * 3 + min(-min(r["r1"], r["r3"]), 15) / 15 * 1.5
            sc += max(-1, min(1, r["sec_rs"] / 5))
            r["setup"] = "flush"; r["score"] = round(sc + swing, 2); longs.append(r); continue
        if r["price"] > r["s50"] > r["s200"] and r["r1"] >= -8 and r["r3"] >= -12:
            if lvl not in ("DEFENSIVE", "BEAR") and r["sector"] in DEFENSIVE_SECTORS: continue      # v3: no defensive longs unless DEFENSIVE
            if lvl not in ("DEFENSIVE", "BEAR") and r["sector"] != "ETF" and (r.get("beta") or 0) < MIN_BETA: continue   # v4: beta >= 1.5
            sc = max(0, 20 - r["rsi2"]) / 20 * 3          # RSI2 pullback, up to +3
            if -8 <= r["r3"] <= -1: sc += 1.5              # 1-3 day dip in an uptrend
            sc += min(r["vs50"], 15) / 15 * 1.5            # trend strength, up to +1.5
            sc += max(-1, min(1, r["sec_rs"] / 5))         # sector strength
            sc += max(-1, min(1.5, (r["r21"] - (spy["r21"] if spy else 0)) / 10))   # v3: relative strength vs SPY, up to +1.5
            if r["hi20"] and r["relvol"] >= 1.5 and 0 < r["r1"] <= 10 and r["r3"] <= 15: continue   # v4: no breakout buys (backtest: -17% of book)
            r["setup"] = "pullback"
            if ea and 3 <= ea[1] <= 10 and r["r21"] > 0:   # v4.3 RUNUP: pre-earnings drift window, decide sell-or-hold before the report
                sc += 1.5; r["setup"] = "runup"
            if r["relvol"] >= 1.5 and r["last_day"] < -3: sc -= 1.5
            if r["rsi2"] > 90 and r.get("setup") != "breakout": sc -= 1
            r["score"] = round(sc + swing, 2); longs.append(r)
        elif r["price"] < r["s50"] < r["s200"] and r["price"] >= 10 and r["adv_m"] >= 50 and r["r1"] <= 15 and r["sector"] != "ETF" or (
                r["sector"] == "ETF" and r["price"] < r["s50"] < r["s200"]):
            sc = max(0, r["rsi2"] - 80) / 20 * 3          # RSI2 bounce into resistance, up to +3
            if 1 <= r["r3"] <= 8: sc += 1.5                # 1-3 day bounce in a downtrend
            sc += min(-r["vs50"], 15) / 15 * 1.5           # downtrend strength
            sc += max(-1, min(1, -r["sec_rs"] / 5))        # weak sector
            if r["lo20"] and r["relvol"] >= 1.5 and -10 <= r["r1"] < 0 and r["r3"] >= -15: sc += 2; r["setup"] = "breakdown"  # 20-day low on volume
            else: r["setup"] = "bounce"
            if r["rsi2"] < 10 and r.get("setup") != "breakdown": sc -= 1   # already washed out: squeeze risk
            r["score"] = round(sc + swing, 2); shorts.append(r)
    os.makedirs("data/cands", exist_ok=True)
    cols = ["ticker","sector","setup","score","beta","price","rsi2","r1","r3","r21","vs50","atr","relvol","last_day","sec_rs","adv_m","earn_date","earn_in"]
    for lab, lst, f in (("LONG", longs, f"data/cands/{today()}.csv"), ("SHORT", shorts, f"data/cands/{today()}-short.csv")):
        lst.sort(key=lambda r: -r["score"]); cnt, final = {}, []
        for r in lst:  # max 3 per sector
            if cnt.get(r["sector"], 0) >= 3: continue
            cnt[r["sector"]] = cnt.get(r["sector"], 0) + 1; final.append(r)
            if len(final) >= (n if lab == "LONG" else max(10, n // 2)): break
        with open(f, "w", newline="") as o:
            w = csv.DictWriter(o, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(final)
        print(f"{lab}: eligible {len(lst)} | wrote {f}")
        for r in final:
            print(f"  {r['ticker']:6} {r['sector'][:16]:16} {r['setup']:9} sc={r['score']:>5} rsi2={r['rsi2']:>5} 1d={r['r1']:+.1f}% 3d={r['r3']:+.1f}% vs50={r['vs50']:+.1f}% atr={r['atr']}% rv={r['relvol']} secRS={r['sec_rs']:+.1f}")
    print(f"universe {len(tick)} | scored {len(rows)} | earnings-blocked {len(blocked & set(by))}")

# ---------------- shadow (open-to-close next session) ----------------
def shadow():
    s = load_state(); done = {r["date"] for r in csv.DictReader(open("shadow/daily.csv"))}
    val = START_CASH
    rows = list(csv.DictReader(open("shadow/daily.csv")))
    if rows: val = float(rows[-1]["book_value"])
    for bd in sorted(s.get("baskets", {})):
        b = s["baskets"][bd]
        sess = [r[0] for r in bars("SPY") if r[0] > bd]
        if not sess or sess[0] >= str(today()): continue  # next session not finished yet
        day = sess[0]
        if day in done: continue
        tot = 0.0
        for t, w in zip(b["tickers"], b["weights"]):
            r = [x for x in bars(t) if x[0] == day]
            if not r: continue
            o, c = r[0][1], r[0][4]; ret = c / o - 1
            tot += w * ret - abs(w) * 2 * COST
            append("shadow/open_close.csv", [day, t, round(val * w / o, 6), o, c, round(ret if w >= 0 else -ret, 5)])
        val *= (1 + tot)
        append("shadow/daily.csv", [day, round(val, 2), round(tot, 5), round(tot, 5)])
        print(f"SHADOW {day} (basket of {bd}, {b['level']}): {100*tot:+.2f}% net -> ${val:.2f}")

# ---------------- stats ----------------
def stats():
    rows = list(csv.DictReader(open("book/daily.csv")))
    if not rows: print("no completed days yet"); return
    b = [float(r["book_ret_net"]) for r in rows]; m = [float(r["spy_ret"]) for r in rows]
    last = rows[-1]; n = len(rows)
    cum_b = float(last["book_value"]) / START_CASH - 1; cum_s = float(last["spy_value"]) / START_CASH - 1; cum_t = float(last["tqqq_value"]) / START_CASH - 1
    tq = [float(r["tqqq_ret"]) for r in rows]
    hit = sum(x > y for x, y in zip(b, m)) / n
    print(f"DAYS {n} | today book {100*b[-1]:+.2f}% vs SPY {100*m[-1]:+.2f}% vs TQQQ {100*tq[-1]:+.2f}% | cum book {100*cum_b:+.2f}% (${float(last['book_value']):.2f}) vs SPY {100*cum_s:+.2f}% vs TQQQ {100*cum_t:+.2f}% | beat SPY {100*hit:.0f}% of days")
    sh = list(csv.DictReader(open("shadow/daily.csv")))
    if sh: print(f"SHADOW open-to-close: last {sh[-1]['date']} {100*float(sh[-1]['day_ret']):+.2f}% | cum {100*(float(sh[-1]['book_value'])/START_CASH-1):+.2f}%")
    for w in ("am", "pm"):
        ws = [float(r["book_ret_net"]) for r in rows if r["note"].startswith(w)]; wm = [float(r["spy_ret"]) for r in rows if r["note"].startswith(w)]
        if ws:
            cb = 1.0; cm = 1.0
            for x in ws: cb *= 1 + x
            for x in wm: cm *= 1 + x
            print(f"LEG {'overnight (3:45 PM->9:45 AM)' if w == 'am' else 'day (10:00 AM->3:30 PM)'}: {len(ws)} runs | book {100*(cb-1):+.2f}% vs SPY {100*(cm-1):+.2f}% | beat SPY {100*sum(x > y for x, y in zip(ws, wm))/len(ws):.0f}%")
    if n >= 10:
        up = [(x, y) for x, y in zip(b, m) if y > 0]; dn = [(x, y) for x, y in zip(b, m) if y < 0]
        uc = (sum(x for x, _ in up) / sum(y for _, y in up)) if up else None
        dc = (sum(x for x, _ in dn) / sum(y for _, y in dn)) if dn else None
        print(f"CAPTURE up {uc if uc is None else round(100*uc)}% ({len(up)} up days) | down {dc if dc is None else round(100*dc)}% ({len(dn)} down days) | goal: down < 100%, up as high as possible")

if __name__ == "__main__":
    a = sys.argv[1:]; cmd = a[0] if a else "stats"
    if cmd == "regime": regime()
    elif cmd == "mark": mark()
    elif cmd == "review": review()
    elif cmd == "sell":
        r = ""; 
        if "--why" in a: i = a.index("--why"); r = a[i + 1]; del a[i:i + 2]
        sell(a[1:], r)
    elif cmd == "candidates": candidates(int(a[1]) if len(a) > 1 else 25)
    elif cmd == "buy":
        why = {}
        if "--why" in a: i = a.index("--why"); why = json.load(open(a[i + 1])); del a[i:i + 2]
        if "--no-topup" in a: a.remove("--no-topup"); TOPUP_ONLY = set()
        if "--topup" in a: i = a.index("--topup"); TOPUP_ONLY = set(x for x in a[i + 1].upper().split(",") if x); del a[i:i + 2]
        sh = []
        if "--short" in a: i = a.index("--short"); sh = a[i + 1:]; del a[i:]
        buy(a[1], a[2:], why, sh)
    elif cmd == "shadow": shadow()
    elif cmd == "warm": warm()
    else: stats()
