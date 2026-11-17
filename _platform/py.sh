#!/bin/bash
# Run a Python script with market-data credentials taken from your environment.
# Required: APCA_DATA_KEY_ID, APCA_DATA_SECRET_KEY (Alpaca market data; a free paper account works).
# Optional: PERPLEXITY_API_KEY (news/story scoring), SEC_USER_AGENT ("Your Name you@example.com", required by SEC EDGAR).
# Usage (from a book's project/ folder): sh /home/user/workspace/_platform/py.sh scripts/<name>.py [args...]
: "${APCA_DATA_KEY_ID:?set APCA_DATA_KEY_ID}"; : "${APCA_DATA_SECRET_KEY:?set APCA_DATA_SECRET_KEY}"
export APCA_API_KEY_ID="${APCA_API_KEY_ID:-$APCA_DATA_KEY_ID}" APCA_API_SECRET_KEY="${APCA_API_SECRET_KEY:-$APCA_DATA_SECRET_KEY}"
export SEC_USER_AGENT="${SEC_USER_AGENT:-your-name your-email@example.com}"
exec python3 "$@"
