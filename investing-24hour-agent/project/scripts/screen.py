#!/usr/bin/env python3
"""Nightly systematic screen (thesis rules 16-17).
Ranks S&P 500 constituents + 11 sector ETFs on trend/momentum and writes
data/screen/YYYY-MM-DD.csv plus a breadth summary (% above 50dma/200dma, RSP vs SPY).
Usage: python3 scripts/screen.py   (run from project root)
Valuation (forward P/E vs peers) and earnings dates are checked by hand on finalists."""
import csv, io, json, os, sys, time, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
ETFS = ["XLK","XLF","XLE","XLV","XLY","XLP","XLI","XLB","XLU","XLRE","XLC","RSP","SPY","IWM"]

# Canadian large caps (TSX, Yahoo .TO). Sector prefixed "CA " so they stay out of US breadth.
# Opportunity-only: no TSX quota (owner, Oct 18, 2026). "*" in comment = also listed in New York.
CA = {"RY.TO":"CA Financials","TD.TO":"CA Financials","BNS.TO":"CA Financials","BMO.TO":"CA Financials","CM.TO":"CA Financials",
      "NA.TO":"CA Financials","MFC.TO":"CA Financials","SLF.TO":"CA Financials","BN.TO":"CA Financials","IFC.TO":"CA Financials",
      "ENB.TO":"CA Energy","TRP.TO":"CA Energy","CNQ.TO":"CA Energy","SU.TO":"CA Energy","CVE.TO":"CA Energy","TOU.TO":"CA Energy",
      "PPL.TO":"CA Energy","CCO.TO":"CA Energy","CP.TO":"CA Industrials","CNR.TO":"CA Industrials","WCN.TO":"CA Industrials",
      "WSP.TO":"CA Industrials","TRI.TO":"CA Industrials","CLS.TO":"CA Technology","SHOP.TO":"CA Technology","CSU.TO":"CA Technology",
      "OTEX.TO":"CA Technology","AEM.TO":"CA Materials","ABX.TO":"CA Materials","WPM.TO":"CA Materials","FNV.TO":"CA Materials",
      "NTR.TO":"CA Materials","TECK-B.TO":"CA Materials","K.TO":"CA Materials","ATD.TO":"CA Cons Staples","L.TO":"CA Cons Staples",
      "DOL.TO":"CA Cons Discretionary","QSR.TO":"CA Cons Discretionary","FTS.TO":"CA Utilities","EMA.TO":"CA Utilities",
      "H.TO":"CA Utilities","BCE.TO":"CA Communication","T.TO":"CA Communication","XIU.TO":"CA ETF"}

# Large US-listed names outside the S&P 500 (owner, Oct 19, 2026): Nasdaq-100 members not in the S&P + TSM ADR.
# Sector prefixed "X " so they stay out of S&P breadth. Refresh from api.nasdaq.com/api/quote/list-type/nasdaq100 if NDX changes.
EXTRA = {"ASML":"X Information Technology","ARM":"X Information Technology","ALAB":"X Information Technology","TSM":"X Information Technology",
         "NBIS":"X Information Technology","CRWV":"X Information Technology","MSTR":"X Information Technology",
         "MELI":"X Consumer Discretionary","PDD":"X Consumer Discretionary","ALNY":"X Health Care","CCEP":"X Consumer Staples",
         "FER":"X Industrials","RKLB":"X Industrials","SPCX":"X Industrials",
         "SONY":"X Communication Services"}  # SONY added Oct 20 (radar: GTA 6 / PlayStation Store thesis)

def get(url, tries=3):
    import subprocess, time
    if os.environ.get("PPLX_PROXY_HOSTS"):  # Nov 16, 2026: inside py.sh curl fails; use urllib (platform shim)
        for i in range(tries):
            try: return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}), timeout=20).read()
            except Exception as e: err = e; time.sleep(2 * (i + 1))
        raise RuntimeError(f"HTTP fail {err!r} for {url}")
    for i in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "20", "-A", UA["User-Agent"], "-w", "\n%{http_code}", url], capture_output=True)
        body, _, code = r.stdout.rpartition(b"\n")
        if code == b"200": return body
        time.sleep(2*(i+1))
    raise RuntimeError(f"HTTP {code!r} for {url}")

SP500_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ref", "sp500_constituents.csv")

def sp500():
    """S&P 500 {ticker: GICS sector}. Data-integrity rule (owner, Nov 16, 2026: never decide on a fetch error):
    a good fetch (>= 450 rows) refreshes data/ref/sp500_constituents.csv; a failed or short fetch falls back to that
    last-good copy (membership changes a few names a quarter). Only with no copy at all does it return {} (callers
    must then treat breadth as UNKNOWN, never as 0%)."""
    try:
        raw = get("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv").decode()
        rows = list(csv.DictReader(io.StringIO(raw)))
        out = {r["Symbol"].replace(".", "-"): r.get("GICS Sector", "") for r in rows if r.get("Symbol")}
        if len(out) >= 450:
            os.makedirs(os.path.dirname(SP500_CACHE), exist_ok=True)
            with open(SP500_CACHE, "w") as f: f.write(raw)
            return out
        print(f"constituents fetch short ({len(out)} rows); using cached list")
    except Exception as e:
        print("constituents fetch failed:", e, "; using cached list")
    try:
        rows = list(csv.DictReader(open(SP500_CACHE)))
        age = (time.time() - os.path.getmtime(SP500_CACHE)) / 86400
        print(f"constituents: cached copy, {len(rows)} names, {age:.0f} days old" + (" (STALE > 45 days: refresh)" if age > 45 else ""))
        return {r["Symbol"].replace(".", "-"): r.get("GICS Sector", "") for r in rows if r.get("Symbol")}
    except Exception as e:
        print("DATA ERROR: no S&P 500 list (fetch failed, no cached copy):", e); return {}

def rsi(cl, n=14):
    if len(cl) <= n: return None
    g = l = 0
    for i in range(1, n+1):
        d = cl[i]-cl[i-1]; g += max(d, 0); l += max(-d, 0)
    g /= n; l /= n
    for i in range(n+1, len(cl)):
        d = cl[i]-cl[i-1]; g = (g*(n-1)+max(d, 0))/n; l = (l*(n-1)+max(-d, 0))/n
    return 100.0 if l == 0 else 100-100/(1+g/l)

def series_batch(tks):
    """Daily closes per ticker via scripts/prices.py (Nasdaq for US, TMX for .TO); Yahoo spark 429s from this host.
    Intraday, the last bar is the live price, so a 3:15 PM run screens on near-final numbers."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import prices
    out, fails = {}, []
    def one(t):
        h = prices.history(t)
        return t, [h[d] for d in sorted(h)]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for t, cl in ex.map(one, tks):
            if cl: out[t] = cl
            else: fails.append(t)
    if fails: print(f"no data for {len(fails)}: {' '.join(fails[:20])}")
    return out

def stats(t, cl):
    try:
        if len(cl) < 60: return None
        c = cl[-1]; s20 = sum(cl[-20:])/20; s50 = sum(cl[-50:])/50
        s200 = sum(cl[-200:])/200 if len(cl) >= 200 else None
        r5 = 100*(c/cl[-6]-1); r21 = 100*(c/cl[-22]-1)
        return dict(ticker=t, close=round(c, 2), ret_5d=round(r5, 2), ret_1m=round(r21, 2),
                    vs_20dma=round(100*(c/s20-1), 2), vs_50dma=round(100*(c/s50-1), 2),
                    above_200=(None if s200 is None else c > s200), sma20_rising=s20 > sum(cl[-25:-5])/20,
                    rsi14=round(rsi(cl), 1))
    except Exception:
        return None

def main():
    sectors = sp500()
    sectors.update(CA)
    sectors.update(EXTRA)
    tickers = list(sectors) + ETFS
    data = series_batch(tickers)
    res = [r for r in (stats(t, cl) for t, cl in data.items()) if r]
    for r in res:
        r["sector"] = sectors.get(r["ticker"], "ETF")
        # trend+momentum score; penalise overbought (rule 4) and broken trends (rule 6)
        sc = 0.4*r["ret_1m"] + 0.3*r["ret_5d"] + 0.3*r["vs_50dma"]
        if r["vs_20dma"] > 0 and r["vs_50dma"] > 0 and r["sma20_rising"]: sc += 3
        if r["vs_20dma"] < 0 and r["vs_50dma"] < 0: sc -= 5
        if r["rsi14"] and r["rsi14"] > 70: sc -= 4
        r["score"] = round(sc, 2)
    res.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(res, 1): r["rank"] = i
    os.makedirs("data/screen", exist_ok=True)
    out = f"data/screen/{datetime.date.today().isoformat()}.csv"
    cols = ["rank","ticker","sector","score","close","ret_5d","ret_1m","vs_20dma","vs_50dma","above_200","rsi14"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(res)
    stocks = [r for r in res if r["sector"] != "ETF" and not r["sector"].startswith(("CA ", "X "))]
    a50 = 100*sum(r["vs_50dma"] > 0 for r in stocks)/max(len(stocks), 1)
    s200 = [r for r in stocks if r["above_200"] is not None]
    a200 = 100*sum(r["above_200"] for r in s200)/max(len(s200), 1)
    bym = {r["ticker"]: r for r in res}
    rsp_spy = (bym["RSP"]["ret_5d"]-bym["SPY"]["ret_5d"]) if "RSP" in bym and "SPY" in bym else None
    print(f"wrote {out}: {len(res)} rows ({len(stocks)} stocks)")
    print(f"BREADTH % S&P above 50dma: {a50:.1f}% | above 200dma: {a200:.1f}% | RSP minus SPY 5d: {rsp_spy if rsp_spy is None else round(rsp_spy,2)} pts")
    ca = [r for r in res if r["sector"].startswith("CA ") and r["sector"] != "CA ETF"]
    if "XIU.TO" in bym: print(f"TSX (XIU) 5d {bym['XIU.TO']['ret_5d']:+.1f}% 1m {bym['XIU.TO']['ret_1m']:+.1f}%")
    print("TOP 5 CANADA (opportunity only, no quota): " + ", ".join(f"{r['ticker']} #{r['rank']} rsi={r['rsi14']}" for r in ca[:5]))
    print("TOP 25:")
    for r in res[:25]:
        print(f"{r['rank']:>3} {r['ticker']:6} {r['sector'][:22]:22} score={r['score']:>6} 5d={r['ret_5d']:+.1f}% 1m={r['ret_1m']:+.1f}% rsi={r['rsi14']}")

if __name__ == "__main__":
    main()
