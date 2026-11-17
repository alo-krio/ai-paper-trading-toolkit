"""Daily OHLCV from Nasdaq API (US only), cached to data/ohlcv/<T>.json. Usage: ohlcv.get(t)->DataFrame"""
import json, os, datetime as dt, sys
sys.path.insert(0, os.path.dirname(__file__))
import prices as P
import pandas as pd
D = os.path.join(os.path.dirname(__file__), "..", "data", "ohlcv")
def get(t, refresh=False):
    f = os.path.join(D, t + ".json")
    if os.path.exists(f) and not refresh and (dt.date.today() - dt.date.fromtimestamp(os.path.getmtime(f))).days < 1:
        rows = json.load(open(f))
    else:
        s = P._nasdaq_sym(t); frm = (dt.date.today() - dt.timedelta(days=760)).isoformat(); to = dt.date.today().isoformat()
        rows = []
        for cls in ["stocks", "etf"]:
            d = P._curl(["-H", "Accept: application/json", f"https://api.nasdaq.com/api/quote/{s}/historical?assetclass={cls}&fromdate={frm}&todate={to}&limit=600"])
            rr = (((d or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
            if rr:
                for r in rr:
                    try:
                        rows.append([dt.datetime.strptime(r["date"], "%m/%d/%Y").date().isoformat(), P._num(r["open"]), P._num(r["high"]), P._num(r["low"]), P._num(r["close"]), P._num(r["volume"])])
                    except Exception: pass
                break
        rows.sort()
        if rows: json.dump(rows, open(f, "w"))
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"]).dropna()
    df["timestamps"] = pd.to_datetime(df["date"]); return df.reset_index(drop=True)
