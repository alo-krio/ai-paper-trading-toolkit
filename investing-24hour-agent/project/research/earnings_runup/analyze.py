"""Pre-earnings run-up event study, Nasdaq-100 (current constituents), reports 2025-11-11..2026-11-10. RESEARCH ONLY.
Inputs (research/earnings_runup/data/): events.csv, news_times.csv, bars.csv, ndx_cal_all.csv; 10y check uses data/hist/wide_daily.npz.
Run: research/backtest/.venv/bin/python research/earnings_runup/analyze.py  -> prints markdown, writes out/*.csv
"""
import os, sys, datetime as dt
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
NS = [1, 2, 3, 5, 7, 10, 15, 20]
COST = 0.001                                         # 0.10% round trip
SPLIT = "2026-05-11"                                 # half-year boundary

# ---------- prices ----------
b = pd.read_csv(f"{HERE}/data/bars.csv")
C = b.pivot(index="date", columns="symbol", values="c").sort_index()
O = b.pivot(index="date", columns="symbol", values="o").sort_index()
dates = list(C.index); di = {d: i for i, d in enumerate(dates)}
qqq50 = C["QQQ"].rolling(50).mean()

# ---------- events + timing ----------
ev = pd.read_csv(f"{HERE}/data/events.csv")
nt = pd.read_csv(f"{HERE}/data/news_times.csv").rename(columns={"cal_date": "date"})
ev = ev.merge(nt[["symbol", "date", "release_et", "headline"]], on=["symbol", "date"], how="left")
cal = pd.read_csv(f"{HERE}/data/ndx_cal_all.csv")

def timing(rel):
    if not isinstance(rel, str) or len(rel) < 16: return "unknown"
    t = dt.time.fromisoformat(rel[11:16])
    return "BMO" if t < dt.time(9, 30) else ("AMC" if t >= dt.time(16, 0) else "intraday")

def nxt_session(d):           # first session on/after calendar date d
    for x in dates:
        if x >= d: return di[x]
    return None

rows = []
for r in ev.itertuples():
    if r.symbol not in C.columns: continue
    k = nxt_session(r.date)
    if k is None or dates[k] != r.date: k = None
    if k is None: continue
    tm = timing(r.release_et)
    if tm == "AMC": p, ro, rc = k, k + 1, k + 1
    elif tm in ("BMO", "intraday"): p, ro, rc = k - 1, k, k
    else: p, ro, rc = k - 2, k + 1, k + 1           # unknown: conservative pre-report close = close 2 sessions before report date
    if rc >= len(dates) or p - max(NS) < 0: continue
    c = C[r.symbol].values; o = O[r.symbol].values; q = C["QQQ"].values; s = C["SPY"].values
    if not np.isfinite(c[p]) or not np.isfinite(c[rc]): continue
    # beat history: surprises of up to 4 prior reports (Nasdaq calendar), before this report
    prior = cal[(cal.symbol == r.symbol) & (cal.date < r.date) & (cal.date >= (dt.date.fromisoformat(r.date) - dt.timedelta(days=420)).isoformat())].tail(4)
    sp = prior.surprise_pct.dropna()
    row = dict(symbol=r.symbol, date=r.date, timing=tm, pre_close_date=dates[p], react_date=dates[rc],
               beats4=int((sp > 0).sum()) if len(sp) >= 3 else np.nan, nbeat_obs=len(sp),
               react_close=c[rc] / c[p] - 1, react_open=o[ro] / c[p] - 1,
               react_close_xq=(c[rc] / c[p]) - (q[rc] / q[p]), react_close_xs=(c[rc] / c[p]) - (s[rc] / s[p]))
    for N in NS:
        e = p - N
        row[f"ru{N}"] = c[p] / c[e] - 1
        row[f"xq{N}"] = c[p] / c[e] - q[p] / q[e]
        row[f"xs{N}"] = c[p] / c[e] - s[p] / s[e]
        row[f"reg{N}"] = "up" if q[e] > qqq50.iloc[e] else "down"
        row[f"entry{N}"] = dates[e]
    rows.append(row)
E = pd.DataFrame(rows)
E["half"] = np.where(E.date < SPLIT, "H1 (Nov25-May26)", "H2 (May26-Nov26)")
E.to_csv(f"{OUT}/events_enriched.csv", index=False)

def stats(x):
    x = pd.Series(x).dropna()
    return dict(n=len(x), mean=x.mean(), med=x.median(), pos=(x > 0).mean(), t=x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan)

def tclust(x, week):          # t-stat with events averaged within report week (reports cluster in time)
    g = pd.Series(np.asarray(x)).groupby(np.asarray(week)).mean()
    return g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))

E["week"] = pd.to_datetime(E.date).dt.to_period("W").astype(str)
pc = lambda v: f"{100*v:+.2f}%"
P = []
P.append(f"Events: {len(E)} ({E.symbol.nunique()} symbols); timing: " + ", ".join(f"{k} {v}" for k, v in E.timing.value_counts().items()))
P.append(f"Window: report dates {E.date.min()} .. {E.date.max()}\n")

# ---------- 1. run-up ----------
P.append("## 1. Run-up (entry close N sessions before last pre-report close -> exit at that close), net 0.10% RT\n")
P.append("| N | raw mean | raw med | raw %pos | raw t | xQQQ mean | xQQQ med | xQQQ %pos | xQQQ t | xQQQ t (week-clustered) | xSPY mean | xSPY t | xQQQ per day |")
P.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
RU = []
for N in NS:
    raw = stats(E[f"ru{N}"] - COST); xq = stats(E[f"xq{N}"] - COST); xs = stats(E[f"xs{N}"] - COST)
    tc = tclust(E[f"xq{N}"] - COST, E.week)
    RU.append(dict(N=N, raw=raw["mean"], xq=xq["mean"], xq_day=xq["mean"] / N, xq_t=xq["t"], xq_tc=tc, xs=xs["mean"], raw_pos=raw["pos"]))
    P.append(f"| {N} | {pc(raw['mean'])} | {pc(raw['med'])} | {raw['pos']:.0%} | {raw['t']:.2f} | {pc(xq['mean'])} | {pc(xq['med'])} | {xq['pos']:.0%} | {xq['t']:.2f} | {tc:.2f} | {pc(xs['mean'])} | {xs['t']:.2f} | {100*xq['mean']/N:+.3f}% |")
# unconditional baseline: mean N-day QQQ-excess of the same 100 names over every start day in the window (survivorship/drift control)
syms = [x for x in E.symbol.unique()]
w0 = di[E[f"entry{max(NS)}"].min()]
P.append("\n**Survivorship/drift control.** Today's NDX members beat QQQ over this window on any random day, so the run-up must beat the same names' unconditional N-day excess:\n")
P.append("| N | event xQQQ mean | unconditional xQQQ mean (same names, all days) | event minus baseline | per day |")
P.append("|---|---|---|---|---|")
for r_ in RU:
    N = r_["N"]; cc = C[syms].values; qq = C["QQQ"].values[:, None]
    u = (cc[w0 + N:] / cc[w0:-N] - qq[w0 + N:] / qq[w0:-N]); base = np.nanmean(u) - COST
    r_["base"] = base; r_["edge"] = r_["xq"] - base; r_["edge_day"] = r_["edge"] / N
    P.append(f"| {N} | {pc(r_['xq'])} | {pc(base)} | {pc(r_['edge'])} | {100*r_['edge_day']:+.3f}% |")
RU = pd.DataFrame(RU); RU.to_csv(f"{OUT}/runup_grid.csv", index=False)
bestT = int(RU.loc[RU.xq.idxmax(), "N"]); bestD = int(RU.loc[RU.xq_day.idxmax(), "N"])
bestE = int(RU.loc[RU.edge.idxmax(), "N"]); bestED = int(RU.loc[RU.edge_day.idxmax(), "N"])
P.append(f"\nBest N by total QQQ-excess: **{bestT}**; by excess per day held: **{bestD}**. After subtracting the baseline: total **{bestE}**, per day **{bestED}**.\n")

# ---------- 2. reaction ----------
P.append("## 2. Earnings reaction (last pre-report close -> first post-report open / close)\n")
P.append("| measure | n | mean | median | %pos | avg |move| | 5th pct | 95th pct |")
P.append("|---|---|---|---|---|---|---|---|")
for lab, col in [("to open (raw)", "react_open"), ("to close (raw)", "react_close"), ("to close (xQQQ)", "react_close_xq")]:
    x = E[col].dropna()
    P.append(f"| {lab} | {len(x)} | {pc(x.mean())} | {pc(x.median())} | {(x>0).mean():.0%} | {100*x.abs().mean():.2f}% | {pc(x.quantile(.05))} | {pc(x.quantile(.95))} |")
P.append("\nBy timing (to close, raw): " + "; ".join(f"{k}: n={len(g)}, mean {pc(g.react_close.mean())}, |move| {100*g.react_close.abs().mean():.2f}%" for k, g in E.groupby("timing")))

# hold-through vs sell-before, at the two best Ns
P.append("\n**Sell before vs hold through** (net 0.10% RT either way; hold-through = run-up + reaction to close):\n")
P.append("| N | sell before: mean / med / 5th | hold through: mean / med / 5th | hold-through xQQQ mean |")
P.append("|---|---|---|---|")
for N in sorted({bestT, bestD, 5}):
    sb = E[f"ru{N}"] - COST; ht = (1 + E[f"ru{N}"]) * (1 + E.react_close) - 1 - COST
    htx = E[f"xq{N}"] + E.react_close_xq - COST
    P.append(f"| {N} | {pc(sb.mean())} / {pc(sb.median())} / {pc(sb.quantile(.05))} | {pc(ht.mean())} / {pc(ht.median())} / {pc(ht.quantile(.05))} | {pc(htx.mean())} (t {stats(htx)['t']:.2f}) |")

# ---------- 3. conviction ----------
P.append("\n## 3. Hold-through conviction tests (does anything known before the report predict the reaction?)\n")
P.append("| signal | bucket | n | reaction mean | median | %pos | xQQQ mean |")
P.append("|---|---|---|---|---|---|---|")
for N in sorted({bestT, bestD, 5}):
    tq = pd.qcut(E[f"xq{N}"], 3, labels=["bottom", "mid", "top"])
    for lab in ["top", "mid", "bottom"]:
        g = E[tq == lab]
        P.append(f"| run-up xQQQ N={N} tercile | {lab} | {len(g)} | {pc(g.react_close.mean())} | {pc(g.react_close.median())} | {(g.react_close>0).mean():.0%} | {pc(g.react_close_xq.mean())} |")
bh = E.dropna(subset=["beats4"])
for lab, m in [("4 of last 4 beat", bh.beats4 >= 4), ("<=3 of last 4 beat", bh.beats4 <= 3)]:
    g = bh[m]
    P.append(f"| beat history | {lab} | {len(g)} | {pc(g.react_close.mean())} | {pc(g.react_close.median())} | {(g.react_close>0).mean():.0%} | {pc(g.react_close_xq.mean())} |")
for N in [bestT]:
    cor = np.corrcoef(E[f"xq{N}"], E.react_close_xq)[0, 1]
    P.append(f"\nCorrelation of run-up (xQQQ, N={N}) with reaction (xQQQ): {cor:+.3f} (n={len(E)}).")

# ---------- 4. robustness ----------
P.append("\n## 4. Robustness (run-up xQQQ, net)\n")
P.append("| N | " + " | ".join(["H1 (Nov25-May26)", "H2 (May26-Nov26)", "QQQ > 50DMA at entry", "QQQ < 50DMA at entry"]) + " |")
P.append("|---|---|---|---|---|")
for N in NS:
    cells = []
    for m in [E.half.str.startswith("H1"), E.half.str.startswith("H2"), E[f"reg{N}"] == "up", E[f"reg{N}"] == "down"]:
        s = stats(E.loc[m, f"xq{N}"] - COST); cells.append(f"{pc(s['mean'])} (t {s['t']:.1f}, n {s['n']})")
    P.append(f"| {N} | " + " | ".join(cells) + " |")
P.append("\nReaction by half / regime (to close, raw mean; avg |move|): " + "; ".join(
    f"{k}: {pc(g.react_close.mean())}, {100*g.react_close.abs().mean():.2f}%" for k, g in E.groupby("half")) + "; " + "; ".join(
    f"QQQ {k} 50DMA: {pc(g.react_close.mean())}" for k, g in E.groupby(f"reg{bestT}")))

# ---------- 5. vs holding QQQ: daily portfolio sim ----------
P.append("\n## 5. Versus just holding QQQ (equal-weight book of all open run-up trades, cash when none, 0.10% RT)\n")
R = C.pct_change()
start = di[E[f"entry{max(NS)}"].min()] if False else di[E.pre_close_date.min()] - 1
P.append("| strategy | total return | days invested | ann. vol | max DD | mean daily ret when invested |")
P.append("|---|---|---|---|---|---|")
def book(N, hold=False):
    held = {i: [] for i in range(len(dates))}
    for r in E.itertuples():
        e = di[getattr(r, f"entry{N}")]; x = di[r.react_date] if hold else di[r.pre_close_date]
        for i in range(e + 1, x + 1): held[i].append((r.symbol, i == e + 1, i == x))
    eq = []; inv = 0
    for i in range(start + 1, len(dates)):
        h = held[i]
        if not h: eq.append(0.0); continue
        inv += 1
        eq.append(np.mean([R[s].iloc[i] - (COST / 2 if a else 0) - (COST / 2 if z else 0) for s, a, z in h]))
    return pd.Series(eq, index=dates[start + 1:]), inv
def line(lab, s, inv):
    cum = (1 + s.fillna(0)).cumprod(); dd = (cum / cum.cummax() - 1).min()
    return f"| {lab} | {pc(cum.iloc[-1]-1)} | {inv}/{len(s)} | {100*s.std()*np.sqrt(252):.1f}% | {pc(dd)} | {pc(s[s!=0].mean())} |"
q = R["QQQ"].iloc[start + 1:]
P.append(line("buy & hold QQQ", q, len(q)))
ew = R[syms].iloc[start + 1:].mean(axis=1); P.append(line("buy & hold equal-weight current NDX names (control)", ew, len(ew)))
for N in sorted({bestT, bestD, 5}):
    s, inv = book(N); P.append(line(f"run-up N={N}, sell before", s, inv))
    s, inv = book(N, True); P.append(line(f"run-up N={N}, hold through", s, inv))
P.append(f"\nSim window {dates[start+1]} .. {dates[-1]}.")

# ---------- 6. 10-year check (timing unknown: anchor = close 2 sessions before report date, both periods) ----------
if "--no10y" not in sys.argv:
    z = np.load(f"{ROOT}/data/hist/wide_daily.npz", allow_pickle=False)
    wd = list(z["dates"]); wdi = {d: i for i, d in enumerate(wd)}; ws = {s: j for j, s in enumerate(z["syms"])}; wc = z["c"]; qj = ws["QQQ"]
    hist = cal[(cal.date >= "2016-03-01") & (cal.date < "2025-11-11")]
    P.append("\n## 6. Ten-year check, same current NDX names, 2016-03..2025-11 (Nasdaq dates; anchor = close 2 sessions before report date)\n")
    P.append("| N | 10y n | 10y xQQQ mean | 10y med | 10y %pos | 10y t (month-clustered) | 10y unconditional baseline | 10y minus baseline | 12m xQQQ mean (same D-2 anchor) |")
    P.append("|---|---|---|---|---|---|---|---|---|")
    hs = [ws[x] for x in E.symbol.unique() if x in ws]; i0 = wdi[[d for d in wd if d >= "2016-03-01"][0]]; i1 = wdi[[d for d in wd if d < "2025-11-11"][-1]]
    E2 = {}
    for N in NS:
        xs_ = []; wk = []
        for r in hist.itertuples():
            j = ws.get(r.symbol); k = wdi.get(r.date)
            if j is None or k is None or k - 2 - N < 0: continue
            p = k - 2; e = p - N
            v = wc[p, j] / wc[e, j] - wc[p, qj] / wc[e, qj]
            if np.isfinite(v): xs_.append(v - COST); wk.append(r.date[:7])
        xs_ = np.array(xs_); s = stats(xs_)
        # 12m with the same D-2 anchor from fresh bars
        m12 = []
        for r in E.itertuples():
            k = di[r.date] if r.date in di else None
            if k is None or k - 2 - N < 0: continue
            p = k - 2; e = p - N
            m12.append(C[r.symbol].iloc[p] / C[r.symbol].iloc[e] - C["QQQ"].iloc[p] / C["QQQ"].iloc[e] - COST)
        cc = wc[i0:i1 + 1][:, hs]; qq = wc[i0:i1 + 1, qj][:, None]
        base = np.nanmean(cc[N:] / cc[:-N] - qq[N:] / qq[:-N]) - COST
        P.append(f"| {N} | {s['n']} | {pc(s['mean'])} | {pc(s['med'])} | {s['pos']:.0%} | {tclust(xs_, wk):.2f} | {pc(base)} | {pc(s['mean']-base)} | {pc(np.nanmean(m12))} |")
    P.append("\n(10y uses today's NDX members back in time: survivorship bias flatters the long side; the clustered t averages events within calendar months first.)")

txt = "\n".join(P); open(f"{OUT}/results.md", "w").write(txt); print(txt)
