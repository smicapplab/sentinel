#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENTINEL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENGINE_DIR="$SENTINEL_ROOT/workers/analytics-engine"

cd "$ENGINE_DIR"

# Bootstrap virtual environment if missing (for fresh clones or CI runners)
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
  echo "⚡ Creating Python virtual environment in workers/analytics-engine/.venv..."
  python3 -m venv .venv
  echo "📦 Installing analytics engine dependencies..."
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi

echo "🧪 Running analytics engine test suite with pytest..."
exec .venv/bin/python -m pytest tests/
