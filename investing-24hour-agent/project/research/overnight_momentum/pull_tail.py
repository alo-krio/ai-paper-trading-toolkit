#!/usr/bin/env python3
"""DATA ONLY. Pull daily SIP bars (adjustment=all) 2026-09-01..now for current S&P 500 members + SPY, to extend data/hist
(which ends 2026-10-26) through the latest session. Writes research/overnight_momentum/tail.parquet (data/hist is untouched)."""
import os, sys, csv
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "backtest"))
import pull_history as ph
rows = list(csv.reader(open(os.path.join(ph.HIST, "sp500_hist_components.csv"))))[1:]
syms = set()
for d, t in rows:
    if d >= "2026-01-01": syms |= {x.strip().replace(".", "-") for x in t.split(",") if x.strip()}
syms = sorted(syms) + ["SPY"]
out = []
for i in range(0, len(syms), 100):
    b = syms[i:i + 100]
    try:
        out += [(s, x["t"][:10], x["o"], x["h"], x["l"], x["c"], x["v"], x.get("vw") or x["c"], x.get("n") or 0) for s, x in ph.bars(b, "1Day", "2026-09-01T00:00:00Z")]
    except Exception as e:
        print("batch fail", i, e); 
        for s in b:
            try: out += [(s, x["t"][:10], x["o"], x["h"], x["l"], x["c"], x["v"], x.get("vw") or x["c"], x.get("n") or 0) for s_, x in ph.bars([s], "1Day", "2026-09-01T00:00:00Z")]
            except Exception as e2: print("rejected", s, e2)
ph._write(out, os.path.join(HERE, "tail.parquet")); print(len(syms), "syms", len(out), "bars", max(r[1] for r in out))
