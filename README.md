# Sentinel

Centralized operational data platform for a 300-store restaurant chain. Targets a 2–6% EBITDA improvement via automated labor optimization, inventory management, and delivery efficiency.

---

## Stack

| Layer | Technology |
|---|---|
| Monorepo | Turborepo + pnpm workspaces |
| Frontend | Svelte SPA (`apps/dash-web`, `apps/admin-web`) |
| API | Hono on Node.js via PM2 (`apps/core-api`, `apps/pos-api`) |
| Database | PostgreSQL via AWS RDS Proxy + Drizzle ORM |
| Auth | Vendored Session Auth (Lucia pattern, HTTP-only cookies) |
| Cache / Idempotency | Redis |
| Message Queue | Amazon SQS (POS webhook backpressure) |
| UI Components | Shadcn-Svelte (`packages/ui`) |

---

## Local Development

### Prerequisites
- Node.js v22+
- pnpm v9+
- Docker (for local Postgres + Redis)

### Setup

From the **project root** (one level above this directory):

```bash
# First time setup — boots Docker, installs deps, applies schema
bash setup.sh dev

# Start all apps in development mode
pnpm dev
```

### Individual apps

```bash
# Run all apps via Turborepo
pnpm dev

# Run a specific app
pnpm --filter @sentinel/core-api dev
pnpm --filter @sentinel/dash-web dev
```

---

## Workspace Structure

```
sentinel/
├── apps/
│   ├── dash-web/       # Svelte SPA — Manager Dashboard
│   ├── admin-web/      # Svelte SPA — Corporate Admin Portal
│   ├── core-api/       # Hono API — Core Business Logic (PM2)
│   └── pos-api/        # Hono API — POS Webhook Ingestion (PM2)
├── packages/
│   ├── db/             # Shared Drizzle ORM Schema + Migrations
│   ├── auth/           # Shared Session Auth (Vendored Lucia Pattern)
│   └── ui/             # Shared Shadcn-Svelte Component Library
├── docs/               # Living Architecture Documentation (AI engine)
└── scripts/            # Verification + PR quality scripts
```

---

## Verification Scripts

Run these before every PR (automated via Husky pre-commit + GitHub Actions):

```bash
bash scripts/build-review.sh      # Production build check (turbo build)
bash scripts/type-check.sh        # TypeScript strict check (turbo check)
bash scripts/db-verify.sh         # Drizzle schema vs migrations integrity
bash scripts/security-audit.sh    # franchise_id scoping + secret leak scan
node scripts/bundle-budget.js     # PM2 app memory budget check
```

---

## Documentation

All architectural decisions and module specs live in `docs/`. The `docs/README.md` is the AI agent entrypoint — always update it when adding a new module.

See [docs/README.md](docs/README.md) to get oriented.
