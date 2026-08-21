# Sentinel Living Documentation Engine

This directory is the cross-referenced living documentation for the Sentinel monorepo.
It links every module's spec, plan, source code, and tests into a single navigable system.

Rules:
- Every module must have an entry in this index. No exceptions.
- Module docs are updated before, during, and after implementation (see AGENTS.md Rule 1).
- Use `_template.md` as the base for every new module doc.
- Do not write implementation docs anywhere else in the monorepo.

---

## Index

### Foundation

| Doc | Description | Status |
|---|---|---|
| [sentinel.md](../../docs/sentinel.md) | 180-Day Data Transformation Roadmap & Phase 1 Data Truth Audit | Reference |

### Active Modules

*No active modules yet. Add a row here each time a new module doc is created.*

| Doc | Spec | Plan | Status |
|---|---|---|---|
| (none) | | | |

---

## Document Lifecycle

Each module doc passes through three mandatory states:

1. **Design** — Spec and API contract written before any code is touched
2. **In Progress** — Updated per plan step as implementation proceeds; deviations from spec are logged
3. **Complete** — Reflects final implementation, all acceptance criteria marked, linked to merged PR

---

## Cross-Reference Map

When a module doc is complete, it must link to:

- Its origin spec in `../../superpowers/spec/`
- Its origin plan in `../../superpowers/plan/`
- Its Drizzle schema table(s) in `../packages/db/src/schema.ts`
- Its Hono route handler(s) in `../apps/core-api/src/routes/` or `../apps/pos-api/src/routes/`
- Its test file(s) ending in `.test.ts` alongside the implementation

---

## Template

New module docs must use [_template.md](_template.md) as their base.
