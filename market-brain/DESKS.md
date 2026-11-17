Desk registry: flexible, reactive research subagents (owner, Nov 16, 2026). PAPER ONLY.

Owner: "We might keep needing new subagents based on new topics and events as they come. So make the system flexible
and reactive."

Desks are research subagents with a written scope. Three kinds:
  sector  standing industry desks (semis, cloud, healthcare, industrials, energy...). Live until retired.
  theme   multi-week cross-industry topics (Iran/oil geopolitics, AI-lab financing, GLP-1 pricing...). Expire.
  event   one catalyst (an earnings print, an IPO, an OPEC meeting, a Fed decision). Expire a few days after the event;
          on retirement their lasting findings are folded into the owning sector desk and the brain.
Registry: desks.json (next to this file). Every desk writes research/<sector: industries | theme/event: events>/<slug>.md,
optionally data/ripple_graph/<slug>.csv (merged into the ripple map automatically), and stores facts in the brain.

CLI (python3 /home/user/workspace/market-brain/desks.py ...):
  list [--all]                          active desks (or all incl. retired)
  route "event text" [--tickers A,B]    which desk(s) should handle this; suggests a NEW desk when nothing covers it
  create SLUG --kind event|theme|sector --title "..." --scope "..." --watch A,B,C [--expires YYYY-MM-DD]
         [--parent SECTOR_SLUG] [--book 3-6M]
  prompt SLUG --task "..."              full spawn prompt (standard template: recall first, files, remember, report)
  ran SLUG                              mark a run (for staleness tracking)
  retire SLUG [--note "..."]            retire (event/theme desks: fold findings into the parent first)
  review                                expired / stale / unused desks + coverage gaps (held or candidate names no desk watches)
Rules of thumb (see rules.md "Reactive desks"): at most 6 desk spawns per routine run; prefer an existing desk;
create an event desk only when the event can move a holding or candidate through a med/high ripple link.

