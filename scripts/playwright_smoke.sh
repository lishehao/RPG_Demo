#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required for Playwright CLI wrapper."
  exit 1
fi

if [ ! -x "$PWCLI" ]; then
  echo "Playwright wrapper not found at: $PWCLI"
  exit 1
fi

echo "Opening Swagger UI for smoke at $BASE_URL/docs"
"$PWCLI" open "$BASE_URL/docs"
"$PWCLI" snapshot
"$PWCLI" screenshot output/playwright/swagger-smoke.png

echo "Playwright smoke completed. Screenshot: output/playwright/swagger-smoke.png"
