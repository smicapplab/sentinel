/**
 * Sentinel Node Bundle Budget Verifier
 * Verifies that compiled Hono API applications and package bundles do not exceed process limits.
 */

const fs = require('fs');
const path = require('path');

console.log('[INFO] Running Node Bundle Budget Verification...');

// Placeholder for verification budget metrics
// In a mature project, this scans the dist/ or build/ directories of Hono APIs
// and asserts that individual bundle entry points are below defined budgets (e.g., 5MB).

const BUDGETS = {
  'apps/core-api': 5 * 1024 * 1024, // 5MB limit
  'apps/pos-api': 2 * 1024 * 1024   // 2MB limit
};

let budgetExceeded = false;

for (const [appPath, limit] of Object.entries(BUDGETS)) {
  const fullPath = path.resolve(__dirname, '..', appPath);
  if (fs.existsSync(fullPath)) {
    const distPath = path.join(fullPath, 'dist');
    if (fs.existsSync(distPath)) {
      const size = getFolderSize(distPath);
      console.log(`[INFO] ${appPath} size: ${(size / 1024 / 1024).toFixed(2)}MB (Limit: ${(limit / 1024 / 1024).toFixed(2)}MB)`);
      if (size > limit) {
        console.error(`[FAIL] ERROR: ${appPath} bundle size exceeds budget limit!`);
        budgetExceeded = true;
      }
    } else {
      console.log(`[SKIP] ${appPath}/dist not found. Build may not have run yet.`);
    }
  }
}

function getFolderSize(dir) {
  let size = 0;
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      size += getFolderSize(filePath);
    } else {
      size += stat.size;
    }
  }
  return size;
}

if (budgetExceeded) {
  process.exit(1);
}

console.log('[PASS] Bundle budget checks passed successfully.');
process.exit(0);
