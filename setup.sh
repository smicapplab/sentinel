#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Change directory to the script's location for consistent relative paths
cd "$(dirname "$0")"

MODE=${1:-dev}

if [ "$MODE" != "prod" ] && [ "$MODE" != "dev" ]; then
  echo "[ERROR] Invalid setup mode [${MODE}]. Must be 'prod' or 'dev'."
  echo "Usage: $0 [prod|dev]"
  exit 1
fi

echo "========================================="
echo " Starting Sentinel Setup: MODE=[${MODE}]"
echo "========================================="

# 1. Boot local Docker containers in dev mode
if [ "$MODE" = "dev" ]; then
  echo "[INFO] Dev mode: Booting local Docker containers (Postgres, Redis)..."
  docker compose up -d
  echo "[INFO] Waiting for Postgres to be ready..."
  sleep 3
fi

# 2. Install dependencies
echo "[INFO] Installing Sentinel dependencies..."
pnpm install

# 3. Apply database schema
if [ -f "packages/db/package.json" ]; then
  echo "[INFO] Applying database schema..."
  pnpm --filter @sentinel/db db:push
else
  echo "[SKIP] packages/db not yet initialized. Skipping schema push."
fi

# 4. Seed development data
if [ "$MODE" = "dev" ] && [ -f "packages/db/src/seed.ts" ]; then
  echo "[INFO] Seeding database with development data..."
  pnpm --filter @sentinel/db db:seed
else
  echo "[SKIP] No seed script found. Skipping."
fi

echo "========================================="
echo " Sentinel Setup completed successfully."
echo "========================================="
echo ""
echo "Next steps:"
echo "  pnpm dev    # Start all apps"
