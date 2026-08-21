#!/bin/bash

# Sentinel Database Verification Script
# Validates that Drizzle schemas match migration files

echo "[INFO] Running Drizzle database migration integrity audit..."

# Check if packages/db directory exists yet
if [ ! -d "packages/db" ]; then
  echo "[WARN] packages/db not found. Skipping Drizzle integrity check until database package is set up."
  exit 0
fi

# In a mature Turborepo, this would run drizzle-kit check or compare schema files
echo "[INFO] Running drizzle-kit check..."
npx turbo run db:check
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[PASS] Database schema/migration integrity verification passed."
else
  echo "[FAIL] Database verification failed! Migrations do not match schema."
fi

exit $EXIT_CODE
