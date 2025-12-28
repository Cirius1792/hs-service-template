#!/usr/bin/env sh
set -e

if ! command -v semantic-release >/dev/null 2>&1; then
  echo "semantic-release not installed"
  exit 1
fi

semantic-release
