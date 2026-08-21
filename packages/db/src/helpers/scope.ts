import { eq, and, type SQL } from 'drizzle-orm';
import type { PgColumn } from 'drizzle-orm/pg-core';

/**
 * Sentinel Franchise Scoping Helpers
 * Required by 00-security-audit-spec.md to prevent cross-tenant data leaks.
 */

export function eqFranchiseId<T extends PgColumn>(column: T, franchiseId: string): SQL {
  return eq(column, franchiseId);
}

export function withFranchiseScope<T extends PgColumn>(
  franchiseColumn: T,
  franchiseId: string,
  extraCondition?: SQL
): SQL {
  const franchiseCondition = eq(franchiseColumn, franchiseId);
  if (!extraCondition) {
    return franchiseCondition;
  }
  return and(franchiseCondition, extraCondition)!;
}
