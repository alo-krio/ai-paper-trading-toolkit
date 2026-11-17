#!/usr/bin/env python3
"""Silent side tests (owner, Oct 22, 2026): do the Perplexity news score and Kronos 1-day forecasts predict next-day returns (and kronos_vol the next-day high-low range)?
Logged on every day's 20 finalists; NEVER used to pick names (only the red-flag veto is live).
  python3 scripts/sidelog.py news            -> copies today's news_score per finalist from data/news/<date>-rot.csv into data/side/log.csv
  python3 scripts/sidelog.py kronos          -> Kronos-small 1-day forecast (pred return close->next close) per finalist (run setup_kronos.sh first)
  python3 scripts/sidelog.py score           -> fills next-day actual returns (official closes) and prints rank IC + top-5 vs bottom-5 for each signal
Decision point: ~20 sessions (mid-Nov 2026). Keep a signal only if mean rank IC > ~0.05 with a consistent sign."""
import csv, os, sys, json, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "scripts")
import rotate
LOG = "data/side/log.csv"; COLS = ["date", "ticker", "signal", "value", "actual_next"]
def today(): return str(rotate.today())
def finalists():
    f = f"data/cands/{today()}.csv"
    return [r["ticker"] for r in csv.DictReader(open(f))][:20] if os.path.exists(f) else []
def rows():
    return list(csv.DictReader(open(LOG))) if os.path.exists(LOG) else []
def write(rs):
    os.makedirs("data/side", exist_ok=True)
    with open(LOG, "w", newline="") as f: w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rs)
def add(sig, vals):
    rs = [r for r in rows() if not (r["date"] == today() and r["signal"] == sig)]
    rs += [dict(date=today(), ticker=t, signal=sig, value=round(v, 5), actual_next="") for t, v in vals.items() if v is not None]
    write(rs); print(f"logged {sig} for {len(vals)} names")
def news():
    f = f"data/news/{today()}-rot.csv"
    if not os.path.exists(f): print("no news file today"); return
    add("news", {r["ticker"]: (float(r["news_score"]) if r["news_score"] not in ("", "None") else None) for r in csv.DictReader(open(f))})
def kronos():
    import pandas as pd, torch
    torch.set_num_threads(2); torch.manual_seed(0)
    from kronos_model import Kronos, KronosTokenizer, KronosPredictor
    p = KronosPredictor(Kronos.from_pretrained("NeoQuasar/Kronos-small"), KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base"), device="cpu", max_context=512)
    out, vol = {}, {}
    for t in finalists():
        try:
            b = [r for r in rotate.bars(t) if r[0] < today()]
            lp, _ = rotate.live(t)
            if len(b) < 260 or not lp: continue
            hi = max(b[-1][4], lp); lo = min(b[-1][4], lp)
            b = b[-259:] + [[today(), b[-1][4], hi, lo, lp, b[-1][5]]]  # today's partial bar approximated at the live price
            x = pd.DataFrame(b, columns=["date", "open", "high", "low", "close", "volume"])
            ts = pd.to_datetime(x["date"]); nxt = pd.Series(pd.bdate_range(ts.iloc[-1] + pd.Timedelta(days=1), periods=1))
            o = p.predict(df=x[["open", "high", "low", "close", "volume"]], x_timestamp=ts, y_timestamp=nxt, pred_len=1, T=1.0, top_p=0.9, sample_count=20, verbose=False)  # 20 paths averaged (owner, Oct 22: was 3, too noisy)
            out[t] = float(o["close"].iloc[-1]) / lp - 1
            vol[t] = (float(o["high"].iloc[-1]) - float(o["low"].iloc[-1])) / lp
        except Exception as e:
            print("kronos fail", t, e)
    add("kronos", out); add("kronos_vol", vol)
def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for k, i in enumerate(s): r[i] = k
    return r
def corr(a, b):
    n = len(a); ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b)); da = sum((x - ma) ** 2 for x in a) ** .5; db = sum((y - mb) ** 2 for y in b) ** .5
    return num / (da * db) if da and db else 0.0
def score():
    rs = rows()
    for r in rs:
        if r["actual_next"]: continue
        b = rotate.bars(r["ticker"]); ds = [x[0] for x in b]
        if r["date"] not in ds: continue
        i = ds.index(r["date"])
        if i + 1 < len(b) and b[i + 1][0] < today():
            n = b[i + 1]  # kronos_vol is scored against the next day's actual high-low range
            r["actual_next"] = round((n[2] - n[3]) / b[i][4] if r["signal"] == "kronos_vol" else n[4] / b[i][4] - 1, 5)
    write(rs)
    for sig in ("news", "kronos", "kronos_vol"):
        ics, spread = [], []
        for d in sorted({r["date"] for r in rs if r["signal"] == sig}):
            g = [r for r in rs if r["signal"] == sig and r["date"] == d and r["actual_next"] != ""]
            if len(g) < 8: continue
            v = [float(r["value"]) for r in g]; a = [float(r["actual_next"]) for r in g]
            ics.append(corr(rank(v), rank(a)))
            g2 = sorted(zip(v, a)); spread.append(sum(x for _, x in g2[-5:]) / 5 - sum(x for _, x in g2[:5]) / 5)
        if ics: print(f"SIDE {sig}: {len(ics)} days | mean rank IC {sum(ics)/len(ics):+.3f} | top5 minus bottom5 next-day {100*sum(spread)/len(spread):+.2f}%")
        else: print(f"SIDE {sig}: no scored days yet")
if __name__ == "__main__":
    {"news": news, "kronos": kronos, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "score"]()
