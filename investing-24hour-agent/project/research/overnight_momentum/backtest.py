#!/usr/bin/env python3
"""Overnight Momentum backtest (PAPER/RESEARCH ONLY; never trades, imports nothing from book/sleeves/scripts/bakeoff).
Window: decisions from 2023-11-13 through 2026-11-10 (last exit = 2026-11-11 open). the owner's rule: last 2-3 years only.
Data: data/hist/wide_daily.npz (Alpaca SIP, adjustment=all, 2016..2026-10-26) spliced with tail.parquet (pull_tail.py,
same feed/adjustment, to 2026-11-12) by rescaling old history to the tail's adjustment basis on the overlap.
Universe: point-in-time S&P 500 membership (fja05680, last snapshot 2026-08-18) incl. delisted members -> little survivorship bias.
Run: research/backtest/.venv/bin/python research/overnight_momentum/backtest.py"""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "backtest"))
import hist
START, END = "2023-11-13", "2026-11-11"      # END = last exit date (open)
COST = 0.0005; N = 10

W = hist.load(); dates = list(W["dates"]); syms = list(W["syms"]); si = {s: j for j, s in enumerate(syms)}
O, H, L, C, V = (W[k].astype(np.float64) for k in "ohlcv")
# ---- splice the tail
T = pd.read_parquet(os.path.join(HERE, "tail.parquet")); T = T[T.date <= END]
new_dates = sorted(d for d in T.date.unique() if d > dates[-1])
ext = lambda M: np.vstack([M, np.full((len(new_dates), M.shape[1]), np.nan)])
O, C, V = ext(O), ext(C), ext(V); alld = dates + new_dates; di = {d: i for i, d in enumerate(alld)}
nscaled = 0
for s, g in T.groupby("symbol"):
    j = si.get(s)
    if j is None: continue
    g = g.set_index("date")
    ov = [d for d in g.index if d in di and di[d] < len(dates) and np.isfinite(C[di[d], j])]
    if ov:
        r = np.median(g.loc[ov, "c"].values / C[[di[d] for d in ov], j])
        if abs(r - 1) > 1e-4:
            O[:, j] *= r; C[:, j] *= r; V[:, j] /= r; nscaled += 1
    for d in g.index:
        if d in new_dates:
            i = di[d]; O[i, j], C[i, j], V[i, j] = g.at[d, "o"], g.at[d, "c"], g.at[d, "v"]
dates = np.array(alld); nD = len(dates)
print("dates", dates[0], dates[-1], "rescaled", nscaled, "symbols")
mem = hist.sp500_membership(dates, syms, W["alias"])
# carry last membership snapshot forward (file ends 2026-08-18, fine) ; names without data after 2026-10-26 drop out naturally
spy = si["SPY"]
# ---- signals at close t
lag = lambda M, k: np.vstack([np.full((k, M.shape[1]), np.nan), M[:-k]])
mom = lag(C, 21) / lag(C, 252) - 1
dv = pd.DataFrame(C * V).rolling(20, min_periods=20).mean().values
ret = C / lag(C, 1) - 1
rs = ret[:, spy]
def beta60():
    R = pd.DataFrame(ret); m = pd.Series(rs)
    cov = R.rolling(60, min_periods=55).cov(m); var = m.rolling(60, min_periods=55).var()
    return (cov.values.T / var.values).T
B = beta60()
sma200 = pd.Series(C[:, spy]).rolling(200).mean().values
elig = mem & np.isfinite(mom) & (C >= 10) & (dv >= 50e6) & np.isfinite(C)
# ---- next-day legs
on = lag(O, -1) if False else np.vstack([O[1:] / C[:-1] - 1, np.full((1, C.shape[1]), np.nan)])           # close t -> open t+1
intr = np.vstack([C[1:] / O[1:] - 1, np.full((1, C.shape[1]), np.nan)])                               # open t+1 -> close t+1
cc = np.vstack([C[1:] / C[:-1] - 1, np.full((1, C.shape[1]), np.nan)])                                # close t -> close t+1
t0 = int(np.searchsorted(dates, START)); t1 = int(np.where(dates == END)[0][0]) - 1                  # decision days t0..t1
idx = np.arange(t0, t1 + 1); exitd = dates[idx + 1]

def picks(variant, t):
    e = elig[t].copy(); sc = mom[t].copy()
    if variant == "B": e &= np.isfinite(B[t]) & (B[t] >= 1.5) & (mom[t] > 0)
    if variant == "C" and not (C[t, spy] > sma200[t]): return np.array([], int)
    sc[~e] = -np.inf; o = np.argsort(-sc)[:N]; return o[np.isfinite(sc[o])]

def leg(M, p, fallback=None):
    x = M[p]
    if fallback is not None: x = np.where(np.isfinite(x), x, fallback[p])
    return np.where(np.isfinite(x), x, 0.0)

stats_missing = {"on": 0}
def run(variant):
    rows = []; prev = set()
    for t in idx:
        p = picks(variant, t); cur = set(p.tolist()); w = 1.0 / N
        miss = int(np.sum(~np.isfinite(on[t, p]))); stats_missing["on"] += miss
        g_on = w * leg(on[t], p, cc[t]).sum(); g_in = w * leg(intr[t], p).sum(); g_cc = w * leg(cc[t], p).sum()
        turn = w * (len(cur - prev) + len(prev - cur))         # sum |dw| (buys at close t + sells of dropped names)
        rows.append(dict(t=dates[t], exit=dates[t + 1], n=len(p), new=len(cur - prev), dropped=len(prev - cur),
                         on=g_on, intr=g_in, cc=g_cc, turn=turn, picks=",".join(syms[k] for k in p)))
        prev = cur
    df = pd.DataFrame(rows)
    df["inv"] = df.n / N
    df["net_turn"] = df.on - COST * df.turn                     # spec version: overnight leg, cost only on changes (NOT executable as pure overnight, see report)
    df["net_rt"] = df.on - 2 * COST * df.inv                    # every name sold 9:45-proxy, rebought 3:45-proxy daily
    df["cc_net"] = df.cc - COST * df.turn                       # hold-through: same names held close-to-close, cost on changes
    return df

def metrics(r, inv=None):
    r = pd.Series(np.asarray(r, float)); eq = (1 + r).cumprod()
    yrs = (pd.Timestamp(exitd[-1]) - pd.Timestamp(dates[t0])).days / 365.25 if len(r) == len(idx) else None
    tot = eq.iloc[-1] - 1
    out = dict(total=tot, sharpe=r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan, maxdd=(eq / eq.cummax() - 1).min())
    if yrs: out["cagr"] = (1 + tot) ** (1 / yrs) - 1
    act = r[inv > 0] if inv is not None else r
    out["win"] = (act > 0).mean(); out["avg_active"] = act.mean()
    return out

res = {}; dfs = {}
for v in "ABC": dfs[v] = run(v)
yrs = (pd.Timestamp(exitd[-1]) - pd.Timestamp(dates[t0])).days / 365.25
spy_cc = cc[idx, spy]; spy_on = on[idx, spy]; spy_in = intr[idx, spy]
def yearly(series, years):
    out = {}
    for y in ["2023", "2024", "2025", "2026"]:
        m = years == y
        if m.any():
            s = pd.Series(series[m]); eq = (1 + s).cumprod()
            out[y + (" (Nov13-Dec)" if y == "2023" else " YTD" if y == "2026" else "")] = dict(ret=eq.iloc[-1] - 1, sharpe=s.mean() / s.std() * np.sqrt(252) if s.std() > 0 else np.nan, maxdd=(eq / eq.cummax() - 1).min())
    return out
years = np.array([d[:4] for d in exitd])
table = {}
for v, df in dfs.items():
    inv = df.inv.values
    for col, lab in [("net_turn", "overnight, cost on changes only (spec)"), ("net_rt", "overnight, full daily round-trip"),
                     ("on", "overnight gross"), ("intr", "intraday leg gross (open->close of same picks)"),
                     ("cc", "close-to-close gross"), ("cc_net", "close-to-close, cost on changes")]:
        m = metrics(df[col].values, inv); m["pct_invested"] = (inv > 0).mean(); m["avg_exposure"] = inv.mean()
        m["yearly"] = yearly(df[col].values, years)
        table[f"{v} | {lab}"] = m
    table[f"{v} | _drag"] = dict(turn_drag_per_yr=COST * df.turn.sum() / yrs, rt_drag_per_yr=2 * COST * df.inv.sum() / yrs,
        new_names_per_session=df.new.mean(), new_last29=df.new.tail(29).sum(), dropped_last29=df.dropped.tail(29).sum(),
        roundtrips_29_turnover=df.new.mean() * 29, roundtrips_29_daily=(df.n.tail(29)).sum(),
        avg_names=df.n.mean(), days_lt10=(df.n < N).sum(), on_share_of_cc=df.on.sum() / df.cc.sum() if df.cc.sum() else np.nan)
for lab, s in [("SPY buy-and-hold (close-to-close)", spy_cc), ("SPY overnight-only gross", spy_on), ("SPY overnight-only, 0.1%/night round-trip", spy_on - 2 * COST), ("SPY intraday-only gross", spy_in)]:
    m = metrics(s); m["yearly"] = yearly(s, years); m["pct_invested"] = 1.0; table["BENCH | " + lab] = m
info = dict(window=[dates[t0], exitd[-1]], sessions=len(idx), years=yrs, missing_next_open=stats_missing["on"],
            members_with_data_frac=float(np.nanmean([(mem[t] & np.isfinite(C[t])).sum() / max(mem[t].sum(), 1) for t in idx])),
            eligible_median=float(np.median(elig[idx].sum(1))), B_eligible_median=float(np.median((elig & (B >= 1.5) & (mom > 0))[idx].sum(1))),
            C_days_on=float((C[idx, spy] > sma200[idx]).mean()))
json.dump(dict(info=info, table=table), open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
for v, df in dfs.items(): df.to_csv(os.path.join(HERE, f"daily_{v}.csv"), index=False)
print(json.dumps(info, default=float, indent=1))
for k, m in table.items():
    if "_drag" in k: print(k, {a: round(float(b), 4) for a, b in m.items()}); continue
    print(f"{k:70s} CAGR {m.get('cagr', np.nan):7.1%} tot {m['total']:7.1%} Sh {m['sharpe']:5.2f} DD {m['maxdd']:7.1%} win {m['win']:5.1%} avg {m['avg_active']*1e4:6.1f}bp inv {m['pct_invested']:5.1%} | " +
          " ".join(f"{y}:{d['ret']:.1%}" for y, d in m["yearly"].items()))
