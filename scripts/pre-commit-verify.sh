#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=================================================="
echo "🛡️ Running Sentinel Pre-Commit Quality Checks..."
echo "=================================================="

EXIT_CODE=0

# 1. Type Check (Turbo check across all packages)
echo ""
echo "[1/4] Running TypeScript Compilation Check..."
if bash scripts/type-check.sh; then
  echo "✅ Type Check Passed cleanly."
else
  echo "❌ ERROR: TypeScript type errors detected."
  EXIT_CODE=1
fi

# 2. Fast Python Syntax & Static Analysis Check (No DB / No Network)
echo ""
echo "[2/4] Running Python Syntax Static Verification..."
if python3 -m py_compile workers/analytics-engine/src/*.py workers/analytics-engine/main.py 2>/dev/null; then
  echo "✅ Python static syntax check passed cleanly."
else
  echo "❌ ERROR: Python syntax errors detected."
  EXIT_CODE=1
fi

# 3. Check for unscoped console.log in packages (excluding seed scripts)
echo ""
echo "[3/4] Scanning for unscoped console.log statements..."
CONSOLE_LOG_MATCHES=$(grep -rnE "\bconsole\.log\s*\(" packages/ --include="*.ts" | grep -v "seed\.ts:" || true)
if [ -n "$CONSOLE_LOG_MATCHES" ]; then
  echo "❌ ERROR: Unscoped console.log statements found in packages/:"
  echo "$CONSOLE_LOG_MATCHES"
  EXIT_CODE=1
else
  echo "✅ Zero unscoped console.log statements found in packages/."
fi

# 4. Check for forbidden markdown proliferation outside superpowers/
echo ""
echo "[4/4] Scanning for forbidden markdown files outside superpowers/..."
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
if [ -d "$REPO_ROOT/superpowers" ]; then
  SCAN_ROOT="$REPO_ROOT"
else
  SCAN_ROOT="$PROJECT_ROOT"
fi

ROGUE_MD=$(find "$SCAN_ROOT" -type f -name "*.md" \
  ! -path "*/node_modules/*" \
  ! -path "*/dist/*" \
  ! -path "*/build/*" \
  ! -path "*/.svelte-kit/*" \
  ! -path "*/venv/*" \
  ! -path "*/.venv/*" \
  ! -path "*/.superpowers/*" \
  ! -path "$SCAN_ROOT/superpowers/*" \
  ! -path "$SCAN_ROOT/.agents/*" \
  ! -path "$SCAN_ROOT/.claude/*" \
  ! -path "$SCAN_ROOT/.gemini/*" \
  ! -path "$SCAN_ROOT/AGENTS.md" \
  ! -path "$SCAN_ROOT/GEMINI.md" \
  ! -path "$SCAN_ROOT/CLAUDE.md" \
  ! -path "*/README.md" \
  ! -path "*/docs/*" \
  ! -path "*/manual-src/*" || true)

if [ -n "$ROGUE_MD" ]; then
  echo "❌ ERROR: Forbidden markdown files found outside superpowers/:"
  echo "$ROGUE_MD"
  echo "All AI-generated markdown documents must be stored in superpowers/."
  EXIT_CODE=1
else
  echo "✅ Zero forbidden markdown files found."
fi

echo ""
echo "=================================================="
if [ $EXIT_CODE -eq 0 ]; then
  echo "🎉 Sentinel Pre-Commit Quality Audit Completed Successfully!"
  exit 0
else
  echo "💥 Sentinel Pre-Commit Quality Audit Failed! Please fix errors above."
  exit 1
fi
