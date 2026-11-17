#!/usr/bin/env python3
"""One place to track everything (owner, Oct 22, 2026): rewrites SCOREBOARD.md from the logs. Run at the end of every cycle."""
import os, sys, csv, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "scripts")
import rotate
def run(*a):
    r = subprocess.run([sys.executable] + list(a), capture_output=True, text=True); return (r.stdout.strip() or r.stderr.strip()[-300:])
tr = list(csv.DictReader(open("book/trades.csv"))) if os.path.exists("book/trades.csv") else []
pos = list(csv.DictReader(open("book/positions.csv"))) if os.path.exists("book/positions.csv") else []
wins = sum(float(r["ret"]) > 0 for r in pos)
W = [float(r["ret"]) for r in pos if float(r["ret"]) > 0 and r["ticker"] not in ("SGOV",)]; L = [float(r["ret"]) for r in pos if float(r["ret"]) <= 0 and r["ticker"] not in ("SGOV",)]
payoff = (f" | avg winner {100*sum(W)/len(W):+.2f}% vs avg loser {100*sum(L)/len(L):+.2f}% (payoff {abs(sum(W)/len(W)/(sum(L)/len(L))):.2f}x; goal > 1.2x at ~50% hit rate)" if W and L else "")
out = [f"# 24-Hour Paper Trader scoreboard (updated {rotate.prices._now():%b %d, %Y %I:%M %p} ET)", "PAPER ONLY. $100,000 book, ~10 longs plus paper shorts across ~1,800 US stocks (v2 swing book), two decision windows a day (sell 9:45 / buy 10:00 AM ET, sell 3:30 / buy 3:45 PM ET). Controls: SPY and TQQQ, $100,000 each.", "",
       "## Main book vs controls", run("scripts/rotate.py", "stats"), "",
       "## Trades", f"{len(tr)} trades | {len(pos)} closed positions, {wins} winners ({100*wins/len(pos):.0f}%) | avg closed {100*sum(float(r['ret']) for r in pos)/len(pos):+.2f}%{payoff}" if pos else f"{len(tr)} trades, none closed yet", "",
       "## Tests (logged only, never traded)", "Open-to-close shadow is in the stats line above.", run("scripts/morning.py", "score"), run("scripts/sidelog.py", "score"), run("scripts/aicall.py", "summary"), run("scripts/orb.py", "summary"), "",
       "## Bake-off (Nov 12-Dec 23, 2026)", "5 frozen $100k PAPER sleeves (rules: sleeves/README.md).", run("scripts/bakeoff.py", "score"), "",
       "Decision dates: capture stats ~Nov 6, 2026 (10 sell days); side tests and gap test ~mid-Nov 2026 (~20 sessions)."]
open("SCOREBOARD.md", "w").write("\n".join(out) + "\n"); print("\n".join(out))
