"""Run-Up + idle cash in SPY: no-capital SHADOW for the January 2027 plan (owner, Nov 13 2026).
Derived from the frozen bake-off Run-Up sleeve (sleeves/runup/daily.csv): same Run-Up trades, plus the sleeve's
idle cash held in SPY, resized at each pm (15:45) mark at that mark's SPY price, 5 bp/side on SPY trades.
Stateless: recomputes from scratch each run. Never trades, never touches Alpaca or sleeves/.
Usage: python3 scripts/runup_spy_shadow.py [--bp 5]   -> writes shadow/runup_spy/daily.csv, prints summary."""
import csv, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bp = float(sys.argv[sys.argv.index("--bp") + 1]) if "--bp" in sys.argv else 5.0
rows = list(csv.DictReader(open(os.path.join(ROOT, "sleeves/runup/daily.csv"))))
out, sh, ov, last, spy0, costs, turns = [], 0.0, 0.0, None, None, 0.0, 0
for r in rows:
    eq_ru, cash, spy = float(r["equity"]), float(r["cash"]), float(r["spy"])
    if spy0 is None: spy0 = spy
    if last is not None: ov += sh * (spy - last)          # SPY sweep P&L since last mark
    last = spy
    E = eq_ru + ov                                       # shadow equity = Run-Up sleeve + sweep P&L
    if r["window"] == "pm":
        target = cash * (E / eq_ru) / spy                # idle cash, scaled to shadow size, into SPY
        d = abs(target - sh) * spy
        if d > 1: c = d * bp / 1e4; ov -= c; costs += c; turns += 1; E -= c
        sh = target
    out.append(dict(date=r["date"], window=r["window"], shadow_equity=round(E, 2), runup_equity=eq_ru,
                    spy_shares=round(sh, 4), spy_value=round(sh * spy, 2), spy=spy,
                    shadow_ret=round(E / 100000 - 1, 5), spy_ret=round(spy / spy0 - 1, 5)))
os.makedirs(os.path.join(ROOT, "shadow/runup_spy"), exist_ok=True)
with open(os.path.join(ROOT, "shadow/runup_spy/daily.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
o = out[-1]
print(f"Run-Up + SPY shadow ({o['date']} {o['window']}): equity {o['shadow_equity']:.2f} ({o['shadow_ret']*100:+.2f}%), "
      f"Run-Up alone {(o['runup_equity']/1e5-1)*100:+.2f}%, SPY {o['spy_ret']*100:+.2f}% since {out[0]['date']} {out[0]['window']}; "
      f"SPY sweep {o['spy_value']:.0f}; sweep costs {costs:.2f} over {turns} resizes")
