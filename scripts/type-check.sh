#!/bin/bash

# Sentinel Type Verification Script
# Enforces strict type checking across all Turborepo workspaces

echo "[INFO] Running TypeScript type verification..."

if [ ! -f "package.json" ]; then
  echo "[WARN] package.json not found at the root. Skipping type check until workspaces are initialized."
  exit 0
fi

# Run type check/check script via Turborepo
npx turbo run check
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[PASS] TypeScript type check passed successfully."
else
  echo "[FAIL] TypeScript type check failed!"
fi

exit $EXIT_CODE
