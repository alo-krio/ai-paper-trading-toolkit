#!/bin/bash
# Firecrawl Alexandria call (Polymarket and other providers). Requires FIRECRAWL_API_KEY in your environment.
# Usage: sh /home/user/workspace/_platform/alex.sh <provider> <capability> '<options JSON>' [out.json]
: "${FIRECRAWL_API_KEY:?set FIRECRAWL_API_KEY}"
P="$1"; C="$2"; O="${3:-{\}}"; OUT="${4:-}"
BODY=$(python3 -c 'import json,sys;print(json.dumps({"alexandria":{"provider":sys.argv[1],"capability":sys.argv[2],"options":json.loads(sys.argv[3])}}))' "$P" "$C" "$O")
R=$(curl -s -m 90 -X POST https://api.firecrawl.dev/v2/scrape -H "Content-Type: application/json" -H "Authorization: Bearer $FIRECRAWL_API_KEY" -d "$BODY")
if [ -n "$OUT" ]; then printf '%s' "$R" > "$OUT"; else printf '%s\n' "$R"; fi
