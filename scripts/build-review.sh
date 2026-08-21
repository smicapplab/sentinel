#!/bin/bash

# Sentinel Build Verification Script
# Enforces production build checks across all Turborepo workspaces

echo "[INFO] Running production build review for Sentinel..."

if [ ! -f "package.json" ]; then
  echo "[WARN] package.json not found at the root. Skipping actual build check until workspaces are initialized."
  exit 0
fi

# Run build via Turborepo
npx turbo run build
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[PASS] Production build review passed successfully."
else
  echo "[FAIL] Production build review failed!"
fi

exit $EXIT_CODE
