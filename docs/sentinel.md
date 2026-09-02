[200~# Project Sentinel: 180-Day Data Transformation Roadmap

## 1. Executive Summary
This document outlines the 180-day technical transition for a 300-store restaurant chain from manual reporting to a centralized operational data platform. The primary financial objective is a targeted 2–6% EBITDA improvement on PHP 12 Billion in annual system sales. By replacing static spreadsheets with an automated daily operational briefing, the system will detect and flag anomalies—such as food cost spikes or labor variances—in real time. This pilot serves as the technical blueprint for a subsequent conglomerate-wide rollout.

## 2. Financial Objectives and ROI Levers
The initiative focuses on three operational levers designed for immediate margin expansion:
*   **Labor Optimization (1–3%):** High-precision demand forecasting to align staffing levels with actual store-level requirements, specifically targeting overtime misuse.
*   **Inventory Reduction (1–2%):** Algorithmic stock management for high-value SKUs (e.g., dough, cheese, chicken) to minimize spoilage and emergency store-to-store transfers.
*   **Delivery Efficiency (1–3%):** Dispatch logic and rider allocation optimization to reduce idle time and customer churn.

## 3. Resourcing and Governance Structure
A lean Transformation Office will lead the initial 180-day technical execution, governed by an internal Council. To prove ROI before expanding headcount, technical execution is highly consolidated.

**Staffing Requirements**
*   **Principal Architect / Technical Lead (100% Allocation):** Single point of technical execution for the 180-day pilot. Responsible for roadmap management, unified schema design, infrastructure provisioning, and dashboard development.
*   **Executive Sponsor(s):** Top executives providing strategic alignment, roadblock removal, and high-level use case prioritization.
*   **Internal BA / SA (Borrowed Resource):** Strictly manages enterprise compliance, secures API keys/access, chases down legacy system owners, and handles documentation to shield the Technical Lead from bureaucratic delays.
*   **Field Operations Lead (Borrowed Resource):** Dedicated ground-level manager responsible for driving store-level adoption. They will validate dashboard data alongside shift managers and push the workflow transition across the pilot stores.
*   **Nominated Internal Developers:** Granted repository access to act initially as QA and Deployment Administrators. They will pull the codebase locally, spin up environments, and manually execute deployment pipelines to build structural familiarity. Transition to feature development will occur later, governed by a strict PR review process by the Technical Lead.

**Council Mandate**
The cross-functional Council is responsible for:
*   **Workflow Redesign:** Identifying specific repetitive, analytical, and creative tasks per department for system integration.
*   **ROI Prioritization:** Finalizing the sequence of high-impact use cases.
*   **Governance:** Establishing strict data policies and regional compliance standards.

## 4. Recommended Developer Environment
To optimize development speed during the pilot, the following setup is recommended:
*   **Workstations:** Mac Mini (M-Series) or Linux-based environments.
*   **Productivity:** AI coding assistant subscriptions for technical staff.
*   **Infrastructure:** Amazon Web Services (AWS) utilizing Node.js (v22+) on ARM64 (Graviton2) to optimize performance-per-watt.
*   **Version Control:** GitHub for monorepo management and CI/CD pipelines.

## 5. Unified Data Layer Architecture
The architecture relies on a monorepo foundation to ensure shared logic and schema synchronization across the stack.
*   **Project Structure:** Turborepo and pnpm workspaces for shared logic. Internal NPM publishing is strictly prohibited to preserve developer velocity; all shared code relies on local workspace symlinks.
*   **Design System:** Shadcn-Svelte utilized within a shared `packages/ui` workspace. This provides accessible, enterprise-grade components out-of-the-box without the overhead of building complex headless UI logic from scratch.
*   **ORM:** Drizzle ORM within a shared database package. Types are auto-inferred and consumed directly by the Svelte frontend to ensure end-to-end type safety.
*   **Compute Topology:** A simplified, monolithic virtual machine deployment. The Svelte frontend is deployed as a static SPA, while API gateways, webhook ingestion (via Hono), and background jobs run as Node.js processes managed by **PM2**. Redis is utilized for idempotency caching to protect against webhook floods.

## 6. Critical Architectural Implementations
The following components are strictly required for production stability:
*   **Amazon SQS:** Managing webhook backpressure to ensure ingestion resilience during peak store hours.
*   **AWS RDS Proxy:** Efficient connection pooling to the PostgreSQL instance to prevent connection exhaustion from serverless functions.
*   **Data Segregation & Security:** Application-level security utilizing explicit Drizzle ORM query scoping (e.g., `where(eq(table.franchise_id, currentFranchiseId))`). Row-Level Security (RLS) is explicitly avoided to prevent RDS Proxy session bleed and maintain compatibility with future vector search extensions.
*   **Staged CI/CD:** "Expand-and-contract" deployment patterns for zero-downtime database migrations. Schema changes must be applied and verified before application code deploys.

## 7. Legacy Integration and Data Ingestion
Extraction from legacy systems utilizes a read-only safety layer to protect production stability.
*   **Security Layer:** Direct SQL queries to the legacy database are prohibited.
*   **Integration Methods:** Transactional data is acquired via RFC (Remote Function Call) to invoke standard BAPIs. Master data is consumed via OData Services.
*   **Hybrid Ingestion Strategy:**
    *   **Batch Processing:** EventBridge and ECS Tasks handle high-volume systems of record for daily planning.
    *   **Real-Time Streaming:** SQS and the Hono PM2 process ingest POS sales and delivery status via webhooks. Redis ensures strict idempotency to protect the database from network retry floods.

## 8. 180-Day Execution Timeline
*   **Phase 1: The 1-Month Data Truth Audit (Days 0–30):**
    *   **Objective:** Inspect underlying feeds across POS, SAP, Inventory, HR, and Logistics systems to establish a factual baseline. No user-facing chatbots or generative UI during this phase.
    *   **Priority Ingestion Feeds:**
        1. *Sales / POS Data:* Transaction timestamps, fulfillment times, ticket sizes, promo usage.
        2. *Labor Data:* Clock-in/out, shift schedules, overtime, hourly staffing.
        3. *Inventory & Waste:* Spoilage, stockouts, variances across high-value SKUs.
        4. *Logistics / Fulfillment:* Dispatch times, weather/situational impacts, completion metrics.
        5. *Financial (SAP):* Store/unit-level EBITDA, cash variances.
    *   **Phase 1 Tooling Strategy:**
        * *Schema Reverse-Engineering:* SchemaSpy & DBeaver for live POS DB read-replica inspection (generating browsable ER diagrams and FK relationship maps). SAP discovery routed exclusively through the BA/SA + Basis Admin via RFC/BAPI & OData API Business Hub docs (no direct SQL). HRIS & Logistics profiled via SQL read replicas or REST API specifications.
        * *Opportunity Discovery & Rapid Analytics:* DuckDB for fast ad hoc profiling of raw CSV/API extracts before normalization into Postgres. Self-hosted Metabase for rapid store-level variance visualization (doubling as a live prototype of the daily briefing for leadership). dbt for version-controlled analytical models (overtime-by-store, spoilage-by-SKU) that transition directly into Phase 2 core pipelines.
        * *Discovery Governance & Privacy:* Metabase and DuckDB discovery environments are restricted strictly to local developer environments or encrypted, access-controlled internal VPCs. Raw data extracts must exclude customer PII (names, phone numbers) and employee personal data via SQL view-level exclusions (for database feeds) or field-level extraction filters (for API/OData feeds) during initial replication to comply with RA 10173 during the Phase 1 audit window.
    *   **Deliverable:** Strategic presentation to executive leadership (Sir Mar) presenting a project matrix categorized by Low-Hanging Fruit, High Importance / Foundational, Margin (EBITDA) Drivers, and Revenue Potential to guide Phase 2 execution.
*   **Phase 2: Operational Pipelines & Core System Execution (Days 31–180):** Deployment of automated daily operational briefings and prioritized features selected by leadership during the Phase 1 presentation. Mandates a 2-to-4 week dual-running verification period with store managers and Field Operations Lead.

## 9. Risk Management and Mitigation
*   **Hero Dependency:** Acknowledged risk due to solo technical execution. Mitigated by enforcing strict documentation standards and forcing Nominated Internal Developers to handle application deployments and environment configuration from the start, ensuring operational redundancy.
*   **Enterprise Bureaucracy:** Legacy system access will cause timeline drift. Mitigated by the Internal BA/SA initiating access requests for all 5 systems on Day 1, while the Technical Lead focuses purely on accessible POS data for initial Week 1 ingestion.
*   **Managerial Friction:** Mitigated by the Field Operations Lead actively driving adoption on the ground, utilizing the dual-running verification period to ensure alerts are highly accurate and actionable.

## 10. Compliance and Data Governance
*   **Regulatory Framework:** Strict adherence to the Philippines' Data Privacy Act of 2012 (RA 10173).
*   **Technical Controls:** Mandatory anonymization and masking at the ingestion layer for all customer and financial data. Phase 1 discovery extracts (DuckDB/Metabase) operate under identical RA 10173 legal controls; unmasked PII is strictly excluded at the replication/extraction layer (via SQL views or API transformation filters). Access is strictly controlled via application-level query scoping and table partitioning.

---

## 11. Appendix A: Day 1 IT & HR Provisioning Checklist
To ensure the Technical Lead can execute immediately on the 180-day timeline, the following access and hardware must be provisioned and verified prior to Day 1:

### Hardware & Local Environment
*   **Workstation:** M-Series Mac or Linux equivalent, ready for immediate pickup or delivery.
*   **Permissions:** Full local administrator rights on the provided workstation to install necessary development environments, Node.js runtimes, and virtualization tools without IT ticketing delays.

### Software Licenses & Accounts
*   **Corporate Email & SSO:** Fully active corporate identity to authenticate into third-party tools.
*   **AI Developer License:** Active subscription to enterprise AI coding assistant.

### Cloud & Infrastructure Access
*   **AWS Environment:** Administrator IAM access to the designated AWS organizational account to begin provisioning VPCs, RDS, and ECS resources.
*   **Version Control:** Organization Owner or Admin access to the corporate GitHub account to establish the monorepo and CI/CD pipelines.

### Legacy System & Network Access (All 5 Target Feeds)
*   **VPN/Network:** Full remote and on-site VPN access to the corporate intranet.
*   **POS Database Access:** Development or read-only production credentials for the primary POS database.
*   **SAP Sandbox:** Connection parameters and development credentials for SAP RFC/OData test environment + direct contact for SAP Basis administrator.
*   **HRIS / Labor System Access:** Read-only DB credentials or API keys for employee clock-in/out and shift scheduling data.
*   **Inventory & Waste Feeds:** Read-only credentials/dumps for store inventory management and SKU waste logging.
*   **Logistics & Dispatch Feeds:** API credentials or database access for store delivery dispatch and rider completion metrics.
