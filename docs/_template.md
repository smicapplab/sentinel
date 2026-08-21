# Module: [Module Name]

**Status:** Design | In Progress | Complete
**Module tag:** `sentinel-[module-name]` (used in Stratos task tags)

---

## 1. Origin References

| Artifact | Path |
|---|---|
| Spec | `../../superpowers/spec/[XX]-[module-name]-spec.md` |
| Plan | `../../superpowers/plan/[XX]-[module-name]-plan.md` |
| Stratos Epic | (Stratos Epic ID — filled in after sync-plan.js runs) |

---

## 2. Source Files

| File | Purpose |
|---|---|
| `../packages/db/src/schema.ts` | Drizzle table definitions owned by this module |
| `../apps/core-api/src/routes/[module].ts` | Hono route handler |
| `../apps/core-api/src/routes/[module].test.ts` | Vitest unit tests |
| `../apps/core-api/src/services/[module].ts` | Business logic service (if applicable) |
| `../apps/core-api/src/services/[module].test.ts` | Service unit tests |

*Add or remove rows as the actual file structure takes shape.*

---

## 3. Drizzle Schema

Document the table(s) this module owns or directly depends on.

```ts
// packages/db/src/schema.ts
export const [tableName] = pgTable('[table_name]', {
  id: uuid('id').defaultRandom().primaryKey(),
  franchiseId: uuid('franchise_id').notNull(), // Always present — cross-franchise isolation
  // ... other fields
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});
```

**Index notes:** List any indexes required by this module's query patterns (e.g., `franchise_id + created_at` for time-range queries).

---

## 4. API Contract

Document each Hono route this module exposes.

### GET /api/v1/[resource]

**Auth:** Required (HTTP-only session cookie)
**Query params:**
- `franchiseId` — string (UUID), required

**Response 200:**
```ts
[
  {
    id: string;
    franchiseId: string;
    // ... other fields
    createdAt: string; // ISO-8601 UTC
  }
]
```

**Response 403:** `{ error: 'Forbidden' }` — franchise_id mismatch
**Response 500:** `{ error: string }`

### POST /api/v1/[resource]

*(Repeat pattern for each route)*

---

## 5. Business Logic Decisions

Document the *why* behind non-obvious implementation choices.
Each entry should explain the decision and the trade-off considered.

| Decision | Rationale |
|---|---|
| (example) franchise_id checked at route handler, not service layer | Fail fast before hitting the DB — avoids wasting a connection on an unauthorized request |
| | |

---

## 6. Testable Acceptance Criteria

Copied from the spec. Updated in-place as tests are written and pass.

| # | Criterion | Test file | Status |
|---|---|---|---|
| 1 | Returns 403 when request franchise_id does not match authenticated session | `[module].test.ts` | Not started |
| 2 | Returns 200 with correctly scoped data for valid franchise_id | `[module].test.ts` | Not started |
| 3 | (Add criteria from spec here) | | Not started |

Status values: Not started | Written (failing) | Passing | Skipped (reason)

---

## 7. Deviations from Spec

Log any implementation decision that diverged from the original spec.
This is not a failure — it is expected. Document it honestly.

| Spec said | Implementation did | Reason |
|---|---|---|
| (none yet) | | |

---

## 8. Open Questions / Technical Debt

Track unresolved questions or known shortcuts taken under time pressure.

- [ ] (example) Pagination not yet implemented on GET /api/v1/[resource] — returns all rows. Add cursor-based pagination before production load.

---

*Last updated: [YYYY-MM-DD] — [brief description of what changed]*
