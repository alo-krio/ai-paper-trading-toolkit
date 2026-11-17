"""Replay every v4 position closed Oct 28-Nov 6, 2026 under the v5 proposals (Nov 7, 2026). Daily Nasdaq bars:
am window ~ open, pm window ~ close; peak = highs of completed sessions after entry. 0.05%/side on extra trims."""
import sys, csv, json, statistics as st
sys.path.insert(0, "scripts"); import rotate as R
VIX = {}
for l in open("/tmp/vix.csv"):
    m, d, y = l.split(",")[0].split("/"); VIX[f"{y}-{m}-{d}"] = float(l.split(",")[4])
def macro(d):
    try:
        rs = [r for r in csv.DictReader(open(f"data/news/{d}-macro-pm.csv")) if float(r["market"]) >= .5]
        return 10 * sum((float(r["bull"]) - float(r["bear"])) * float(r["material"]) for r in rs) / len(rs)
    except Exception: return 0.0
spy = R.bars("SPY"); SD = [r[0] for r in spy]
def beta_at(t, d):
    b = {r[0]: r[4] for r in R.bars(t)}; s = {r[0]: r[4] for r in spy}
    ds = [x for x in SD if x < d and x in b][-61:]
    a = [b[ds[i]]/b[ds[i-1]]-1 for i in range(1, len(ds))]; m = [s[ds[i]]/s[ds[i-1]]-1 for i in range(1, len(ds))]
    ma, mm = st.mean(a), st.mean(m); cov = sum((x-ma)*(y-mm) for x, y in zip(a, m)); var = sum((y-mm)**2 for y in m)
    return cov / var
def spy_below20(d):
    c = [r[4] for r in spy if r[0] < d]; return c[-1] < sum(c[-20:]) / 20
P = [r for r in csv.DictReader(open("book/positions.csv")) if r["date"] >= "2026-10-28"]
out = []; C = 0.0005
for p in P:
    t = p["ticker"]; e = float(p["buy_price"]); bd, bw = p["bought"], p["window"]; v4 = float(p["ret"]); xd, xw = p["date"], p["window"]
    bt = beta_at(t, bd); lo, hi = (1.0, 1.8) if spy_below20(bd) else (1.2, 2.5)
    rows = {r[0]: r for r in R.bars(t)}
    # checkpoints after entry: (date, win, price)
    cps = []
    for d in SD:
        if d < bd or d > xd or d not in rows: continue
        for w, px in (("am", rows[d][1]), ("pm", rows[d][4])):
            if (d, w) <= (bd, bw): continue
            if (d, w) > (xd, xw): continue
            cps.append((d, w, px))
    size, pnl, peak, trimmed, why = 1.0, 0.0, 0.0, False, "same exit"
    last_px = e; nsess = 0; exited = False
    for i, (d, w, px) in enumerate(cps):
        prev = rows[d]
        # overnight leg: from previous pm to this am, size halved if switch said HALF
        night = size
        if w == "am" and i > 0 and cps[i-1][1] == "pm":
            pd = cps[i-1][0]
            if VIX.get(pd, 99) >= 20 or macro(pd) <= -2: night = size * 0.5; pnl -= size*0.5*2*C  # trim+rebuy
        pnl += night * (px / last_px - 1) if w == "am" else size * (px / last_px - 1)
        last_px = px
        if w == "am": nsess += 1
        ret = px / e - 1
        done = [r for r in R.bars(t) if bd < r[0] < d]
        peak = max([r[2]/e-1 for r in done] + [ret, peak])
        if w == "am" and not trimmed and i > 0:
            pc = [r for r in R.bars(t) if r[0] < d][-1][4]
            if px / pc - 1 >= .03 and (d, w) != (xd, xw):
                pnl -= size*0.5*C; size *= .5; trimmed = True; why = "gap trim"
        if (d, w) == (xd, xw): break
        if (peak >= .05 and ret < .5*peak) or (peak >= .03 and ret < .001):
            why = f"v5 stop {d} {w}"; exited = True; break
    if not exited: pnl += size * (float(p["sell_price"]) / last_px - 1)
    ok = lo <= bt <= hi
    out.append(dict(t=t, bd=bd, beta=round(bt, 2), band=f"{lo}-{hi}", in_band=ok, v4=round(100*v4, 2), v5_exits=round(100*pnl, 2),
                    v5_all=round(100*pnl, 2) if ok else 0.0, note=why if ok else why + "; SKIPPED by beta band"))
for o in out: print(o)
for k in ("v4", "v5_exits", "v5_all"):
    v = [o[k] for o in out]; w = [x for x in v if x > 0]; l = [x for x in v if x < 0]
    print(k, "sum", round(sum(v), 2), "mean", round(st.mean(v), 2), "wins", len(w), "losses", len(l), "avgW", round(st.mean(w), 2) if w else 0, "avgL", round(st.mean(l), 2) if l else 0)
