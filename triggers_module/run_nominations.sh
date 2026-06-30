#!/usr/bin/env bash
# run_nominations.sh — Local launcher for the BD Watch nominations scraper.
# Usage: ./run_nominations.sh [--dry-run] [--lookback 48] [--min-score 0.4]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "BD Watch — Nominations Module"
echo "=============================="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi

# Install deps quietly if missing
python3 -c "import feedparser" 2>/dev/null || pip install -q feedparser
python3 -c "import yaml" 2>/dev/null || pip install -q pyyaml

cd "$SCRIPT_DIR"
python3 nominations_scraper.py "$@"
