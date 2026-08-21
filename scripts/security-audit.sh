#!/bin/bash

# Sentinel Security & Leak Detection Audit
# Enforces rules defined in .agents/AGENTS.md

echo "[INFO] Running Sentinel Security Audit..."
EXIT_CODE=0

# 1. Secret Isolation Check
echo "[INFO] Checking for raw process.env usage in client workspaces..."
# Scan only apps/dash-web and apps/admin-web for process.env (should be Hono-only or build-time env)
if [ -d "apps/dash-web" ] || [ -d "apps/admin-web" ]; then
  if grep -rn "process.env" apps/dash-web/src apps/admin-web/src 2>/dev/null; then
    echo "[FAIL] ERROR: process.env found in frontend apps! Enforce strict frontend/backend boundary."
    EXIT_CODE=1
  else
    echo "[PASS] Secret Isolation Check passed (frontends clean of process.env)"
  fi
else
  echo "[SKIP] Frontend apps not created yet. Skipping frontend process.env check."
fi

# 2. Hardcoded Tokens Check
echo "[INFO] Checking for potential hardcoded tokens or secrets in all source directories..."
TARGETS="apps packages"
FOUND_SECRET=0
for target in $TARGETS; do
  if [ -d "$target" ]; then
    if grep -rnEi "(Bearer\s+[a-zA-Z0-9_\-\.]{30,}|api_key\s*=\s*['\"][a-zA-Z0-9_\-\.]{15,}['\"]|secret\s*=\s*['\"][a-zA-Z0-9_\-\.]{15,}['\"])" "$target" 2>/dev/null; then
      FOUND_SECRET=1
    fi
  fi
done

if [ $FOUND_SECRET -eq 1 ]; then
  echo "[FAIL] ERROR: Potential hardcoded secret or token found in source code."
  EXIT_CODE=1
else
  echo "[PASS] Hardcoded Tokens Check passed"
fi

# 3. Franchise Data Leak Detection (Basic Heuristic)
echo "[INFO] Checking for unscoped database operations in Hono route handlers..."
# Any query in apps/core-api or apps/pos-api performing db operations must check for 'franchise_id'.
UNSCOPED_QUERIES=0
if [ -d "apps" ]; then
  for file in $(find apps -type f -name "*.ts" 2>/dev/null); do
    # Skip test files and setup/config files
    if [[ "$file" == *"test"* ]] || [[ "$file" == *"spec"* ]] || [[ "$file" == *"config"* ]]; then
      continue
    fi

    if grep -qE "db\.(select|update|delete|insert)" "$file" 2>/dev/null; then
      if ! grep -q "franchise_id" "$file" 2>/dev/null && ! grep -q "public" "$file" 2>/dev/null; then
        echo "[WARN] WARNING: $file performs database operations but does not reference 'franchise_id'. Verify that queries are explicitly scoped to avoid cross-franchise data leaks."
      fi
    fi
  done
  echo "[PASS] Franchise Data Scope Check completed"
else
  echo "[SKIP] Apps directory not created yet. Skipping DB scope check."
fi

if [ $EXIT_CODE -eq 1 ]; then
  echo "[FAIL] Security Audit Failed!"
  exit $EXIT_CODE
fi

echo "[PASS] Security Audit completed successfully."
exit 0
