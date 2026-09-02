# AI Project Proposal: 9 Candidate Projects (Pizza Hut Focus)

## Purpose

This document proposes 9 vetted candidate AI/data projects for Council (mancomm) review and selection. It is a prioritized menu, not a commitment — mancomm picks one (or a small set), and a proof-of-concept demo follows 30 days after selection.

Ranking order follows the stated commercial priority: **revenue generation first, cost saving / margin defense second**. Cost-saving has a hard ceiling ($\le 100\%$, practically 1–3% of a cost line). Revenue has no ceiling — average ticket size, corporate channels, and demand-timed promos can compound indefinitely. That is why 6 of the 9 ideas below are direct top-line revenue plays.

## Scope & Operational Invariants for this Round

- **Pizza Hut first.** Araneta Group's platform serves multiple tenant brands, but this round is scoped strictly to Pizza Hut stores.
- **Zero new software licensing for 60 days.** Every POC below is demonstrable using internal POS/warehouse data, free/open third-party feeds (e.g. radar nowcasting, OpenStreetMap), and existing Google/AWS cloud capacity. Paid enrichments (e.g. Apollo) are tagged as **Phase 2 options**.
- **The 30-day demo is a Proof-of-Concept, not a production release.** Its job is to prove mathematical viability and business lift on real historical data.
- **Audited Cross-Tenant Signals:** Where an idea draws on Gateway Mall / Coliseum foot-traffic data (Ideas #5), it relies on an audited, one-directional read exception (Pizza Hut reads mall foot-traffic/event signals; the reverse never happens), preserving Birdseye tenant isolation.
- **Explicit Execution Surfaces:** Every revenue idea explicitly defines how recommendations reach the customer (Kiosk, Web, Aggregator, or Cashier) and highlights what requires store-IT confirmation.

**Data tier key:** 🟢 free / internal (POS sync data, open datasets, internal mall signals) · 🔵 covered by existing cloud access · 🟡 Phase 2 paid enhancement.

---

## Revenue Generation

### 1. Weather-Triggered Demand & Dispatch Engine

**Why:** Philippine delivery demand is strongly weather-elastic (rain → delivery surge). Today, store responses are reactive and promos run on a fixed, static calendar.

**Execution Surface:** 
- *Staffing/Riders:* Store Manager tablet alert / SMS dispatch.
- *Promos:* Aggregator (Grab/foodpanda) ad boosts and web ordering banner switches (requires 1–2 hr lead time).

**How:** 🟢 POS sync (`pos_daily_store_sales` / `pos_hourly_sales_summary`) + 🟢 10-minute real-time radar nowcasting (RainViewer / PAGASA radar) for live dispatch, paired with a manual Store Manager "Rain Surge" one-tap trigger to sidestep forecast lag. 3–6 hr forecasts are used for kitchen dough prep.

**POC (30 days):** Backtest the correlation between local rain events and delivery sales across 5–10 high-delivery stores over the last 12 months; simulate projected incremental revenue from weather-timed channel promos vs. the actual static calendar.

---

### 2. Corporate & B2B Catering Lead Radar (Transaction Mining)

**Why:** Bulk and corporate orders are high-margin B2B revenue with zero proactive prospecting today. 

**Execution Surface:** B2B Sales / Store Area Manager outbound outreach list.

**How:** 
1. 🟢 **Primary Mechanism (Internal Data Mining):** Scan 12 months of POS line items (`TLOGRCP`) for recurring high-ticket orders ($\ge$ ₱5,000), regular Friday lunch spikes, and corporate BIR TINs to identify existing, unmanaged B2B corporate buyers already ordering from stores.
2. 🟢 **Secondary Enrichment:** Map delivery addresses against nearby office towers (using OpenStreetMap POI data) to cluster B2B demand by building.
3. 🟡 **Phase 2 (Post-Budget):** Apollo.io enrichment to auto-discover procurement/admin contacts for those identified towers.

**POC (30 days):** Extract and rank the top 50 unmanaged corporate accounts currently ordering from 3 pilot stores, showing historical spend, order frequency, and delivery destinations.

---

### 3. The Blowout Bundle: Loyalty-Gated Corporate Perks Program

**Why:** In Philippine office culture, the birthday celebrant treats their team (the "blowout"). That is a recurring, socially-obligated bulk purchase. The generic "birthday email discount" fails because the celebrant wants a generous, easy bundle for their group, not 10% off an individual meal. Gating this bundle behind loyalty registration converts deal-seekers into verified, owned customer records.

**Execution Surface:** Web ordering QR landing page + Formal Corporate Perks distribution.

**How:**
- 🟢 **Distribution:** Package as a formal **Corporate Perks Partnership** (negotiated corporate discount benefit for BPO/office tenants in Cyberpark/Eastwood), bypassing internal HR solicitation rules.
- 🟢 **Capture:** The QR code routes to a lightweight mobile loyalty web signup (Name, Mobile, Birthdate). The bundle discount code unlocks upon signup.
- **Second-Order Asset (RFM Win-Back):** The captured customer identity enables automated dormant-customer win-back campaigns once order frequency lapses.

**POC (30 days):** Partner with 2 pilot office accounts from Idea #2; deploy the minimal signup-to-bundle redeem flow; measure signups, redemption rate, and Average Order Value (AOV).

---

### 4. Next-Best-Item (NBI) AOV Booster (Market Basket Analysis)

**Why:** The fastest way to grow revenue on PHP 12B in sales is expanding the ticket size of existing transactions. A ₱25 lift in average order value across 15M annual transactions generates **~₱375M in top-line growth**.

**Margin Guardrail:** The model must optimize for **incremental gross profit (Δ margin ₱)**, not raw basket size. A recommendation that swaps an 85%-margin ala-carte drink for a 20%-margin side lifts AOV while destroying profit — that's the classic upsell trap. Pairings are ranked by margin contribution per recommendation slot, not conversion rate alone.

**Execution Surface:** 
- *Primary:* Digital Self-Service Kiosks (e.g. `Kiosk 1` mapped in `tbl_NewSegment`) and Web Ordering checkout screens.
- *Secondary:* Static weekly cashier pairing cheat-sheets (e.g., "Prompt Garlic Bread with Family Combos"). *Note: Real-time dynamic cashier POS prompts require store-IT API verification.*

**How:** 🟢 POS line-item stream (`TLOGRCP`) joined to item-level cost/margin data. Apply Association Rule Mining (Apriori / FP-Growth) across 12 months of receipts to isolate pairing affinities, then re-rank by margin contribution per pairing, by channel, daypart, and basket size.

**POC (30 days):** Process 3 months of line-item data across 5 pilot stores; generate the top 10 highest-*margin-weighted* recommendation pairs segmented by channel (Dine-in vs Grab) and daypart (Lunch vs Dinner) — explicitly show which conversion-leading pairs got demoted or cut once margin was factored in.

---

### 5. Araneta Center Event & Foot-Traffic Surge Trigger

**Why:** Pizza Hut branches near Araneta Center sit within walking distance of Smart Araneta Coliseum and New Frontier Theater (15,000–25,000 attendees per event). Gateway Mall and Araneta Center Retail already generate foot-traffic and event data inside Birdseye today.

**Execution Surface:** Store prep scheduling, localized aggregator promo banners, and mall digital signage.

**How:** 🟢 Correlate the internal Gateway Mall / Coliseum event and foot-traffic feeds (via an audited, one-directional read exception) against hourly sales at surrounding Pizza Hut branches. Supplement with public TicketNet event schedules.

**POC (30 days):** Correlate the last 20 major Coliseum/New Frontier events against hourly sales of the 4 nearest Pizza Hut branches; quantify the revenue left on the table during past sellouts (stockouts, long wait times) to prove the financial case for automated prep/promo triggers.

---

### 6. "Dead-Hour" Merienda Yield Activator (2:00 PM – 5:00 PM)

**Why:** Fixed store overheads (rent, base labor, utilities) are paid 24/7. Stores run at ~20% capacity between 2 PM and 5 PM. Filling this dead hour with high-margin solo/duo snack bundles generates pure incremental margin.

**Execution Surface:** Targeted afternoon aggregator promos (Grab/foodpanda) and digital kiosk home-screen takeovers during the 2–5 PM window.

**How:** 🟢 POS hourly/daypart data (`pos_hourly_sales_summary`). Map capacity utilization valleys across stores; model high-margin *Merienda Solo/Pair Combos* (Personal Pan + Beverage/Side) aimed at nearby students and BPO workers.

**POC (30 days):** Hourly capacity utilization heatmaps for 10 pilot stores during 2–5 PM, paired with a backtested financial model demonstrating net margin at 3%, 5%, and 8% traffic lift.

---

## Margin & Leakage Defense

### 7. Discount & Void Fraud Anomaly Radar

**Why:** Senior Citizen / PWD discounts and manager transaction voids are purely descriptive in reports today. Statistically abnormal cashier or manager override rates represent direct cash leakage. A 0.5% reduction in unauthorized overrides on ₱12B recovers **~₱60M straight to bottom-line EBITDA**.

**Legal Guardrail:** SC/PWD discounts are a legal mandate (RA 9994 / RA 10754 — 20% discount + VAT exemption), not a controllable variable. Stores near hospitals or retirement-heavy areas will legitimately run a 25–35% SC/PWD transaction mix — a naive chain-wide z-score would flag those honest managers as fraud outliers. The model must baseline each store against peers with similar demographic/hospital-proximity profiles, never against a single blanket average.

**Execution Surface:** Sentinel Store Operations & Audit Dashboard (Automated Weekly Manager Outlier Flags).

**How:** 🟢 POS data only (`TLOGRCP` discounts, voids, cashier IDs, manager approval codes). Cluster stores by SC/PWD-mix baseline (hospital/retirement-area proximity) first, then run statistical outlier models (Z-score, IQR, Isolation Forest) comparing cashiers against their in-cluster peers — not the chain-wide average.

**POC (30 days):** Ingest 6 months of historical void/discount data; establish store peer clusters; produce an anomaly leaderboard flagging the top 10 outlier cashiers/stores *within their cluster* and quantifying direct peso exposure.

---

### 8. Aggregator Menu Optimization (formerly "Channel Margin Arbitrage")

**Why:** Third-party aggregators (Grab / foodpanda) charge 20–30% commissions, eating margin on a growing share of orders.

**Legal Caveat — verify before pitching as "steer demand off Grab":** Aggregator merchant agreements commonly include price-parity/MFN-style terms that can penalize search ranking or merchant tier if direct-channel prices undercut the aggregator price. Neither this document nor prior review has actually read Pizza Hut PH's signed Grab/foodpanda merchant agreements — that claim needs confirmation from whoever holds those contracts before it's stated as fact to Mancomm. Absent that confirmation, the safer, still-valuable framing below doesn't depend on the answer either way.

**Execution Surface:** Aggregator-exclusive menu/combo configuration inside the Grab/foodpanda merchant portal — no direct-channel price change involved, which sidesteps the parity question entirely.

**How:** 🟢 POS channel-split data (`tbl_NewSegment` / `pos_daily_store_sales`). Compute net contribution margin per ticket *after* aggregator commission, by store/daypart/ticket-size, to find which existing combos already clear a profitable margin even after a 20–30% commission — that's the set to package as aggregator-exclusive bundles, not a price fight with the platform.

**POC (30 days):** Backtest 6 months of delivery transactions; identify which menu items/combos clear a profitable post-commission margin; size 2–3 candidate aggregator-exclusive bundles from that set and project their commission-adjusted contribution.

---

### 9. SKU Spoilage & Waste Anomaly Detection

**Why:** Balances spoilage (over-ordering) vs stockouts (under-ordering) on high-value SKUs (dough, mozzarella cheese, meat/chicken).

**Data Caveat — confirmed, not hypothetical:** No Bill-of-Materials/recipe-decomposition table exists in the documented warehouse schema (`pizzahut.ts` — verified directly, not assumed). Back-calculating ingredient depletion from menu-item sales (e.g. grams of cheese implied by pizzas sold) requires a recipe mapping that isn't present today, and where BOM data exists at all in chains like this it typically lives in spreadsheets that go stale against promos, stuffed-crust overrides, and combo swaps. Building on that would produce confident-looking noise, not a signal.

**Execution Surface:** Weekly Commissary & Store Inventory Ordering Recommendation, scoped to bulk whole-unit SKUs only.

**How:** 🟢 Skip recipe decomposition entirely for this round. Track only bulk whole-unit SKUs with a direct, unambiguous count (whole cheese blocks, dough trays) against commissary shipment and depletion records — no recipe mapping required. Flag statistical variance per store/SKU directly on those units.

**POC (30 days):** Backtest shipment-vs-depletion variance for whole cheese blocks and dough trays across 5 stores over 90 days; isolate the top waste-variance stores. Recipe-level (per-topping) granularity is an explicit later-phase item, contingent on a verified, current BOM source being confirmed to exist.

---

## Appendix: Deferred to Later Rounds

* **Labor / Overtime Demand Forecasting:** Deferred until direct HRIS/timekeeping punch-clock feeds are integrated into the warehouse.
* **New-Site Expansion Scorer:** A valid multi-month capital allocation tool (Google Places competitor density + PSA demographics), but not a 30-day revenue POC.
* **Store Health / Portfolio Early-Warning:** Long-term lease and closure risk modeling; best suited for annual operational reviews rather than Phase 1 revenue acceleration.

---

## Next Steps for Mancomm

1. **Selection:** Mancomm selects 1 primary project (and 1 secondary fallback) from the 9 candidate projects.
2. **30-Day Execution:** Technical Lead builds and deploys the working proof-of-concept on historical data.
3. **Review & Gate:** Mancomm reviews POC accuracy and projected peso ROI to approve production rollout and budget.

**A note on risk, given a single Technical Lead:** #4 (NBI AOV) and #7 (Discount/Void Radar) run entirely on historical POS data already inside the warehouse — no external partner, no cross-tenant access approval, no aggregator negotiation. They are the lowest-risk primary pick for a guaranteed 30-day delivery. #3 (Blowout Bundle) and #5 (Event Surge) have higher revenue upside but depend on securing external commitments (a corporate perks partner, cross-tenant data access sign-off) that a single technical lead cannot unilaterally close within the 30-day window — those are better positioned as the *secondary fallback* or a fast-follow, not the primary bet, unless that external dependency is resolved before the clock starts.
