"""Build the NDX event list: Nasdaq calendar dates for current Nasdaq-100 names, 2025-11-11..2026-11-10 (reaction close must exist)."""
import csv, os, datetime as dt
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
nd = set(pd.read_csv(f"{HERE}/data/ndx.csv").symbol)
e = pd.concat([pd.read_csv(f"{ROOT}/data/hist/earnings.csv"), pd.read_csv(f"{HERE}/data/cal_new.csv")])
e = e[e.symbol.isin(nd)].drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])
e.to_csv(f"{HERE}/data/ndx_cal_all.csv", index=False)   # full 2016+ history for these names (beat history, 10y check)
w = e[(e.date >= "2025-11-11") & (e.date <= "2026-11-10")].copy()
# drop repeat listings of the same report within 20 days
keep = []; last = {}
for r in w.itertuples():
    d = dt.date.fromisoformat(r.date)
    if r.symbol in last and (d - last[r.symbol]).days < 20: continue
    last[r.symbol] = d; keep.append(r.Index)
w = w.loc[keep]
w[["symbol", "date", "time", "surprise_pct"]].to_csv(f"{HERE}/data/events.csv", index=False)
print(len(w), "events,", w.symbol.nunique(), "symbols;", sorted(nd - set(w.symbol)), "missing")
print(w.groupby("symbol").size().value_counts())
