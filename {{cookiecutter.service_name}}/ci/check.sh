#!/usr/bin/env sh
set -e

REQUIRED_FILES="docker-compose.yml .env.example README.md"
for f in $REQUIRED_FILES; do
  [ -f "$f" ] || { echo "Missing $f"; exit 1; }
done

REQUIRED_VARS="SERVICE_NAME BASE_DOMAIN TZ PUID PGID"
for v in $REQUIRED_VARS; do
  grep -q "^$v=" .env.example || { echo "Missing var $v in .env.example"; exit 1; }
done

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --no-git
else
  echo "Gitleaks not installed"; exit 1;
fi

echo "CI checks passed"