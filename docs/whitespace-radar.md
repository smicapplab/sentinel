# Sentinel Whitespace Radar Engine

**Module:** `sentinel` (Downstream AI & Computational Engine)  
**Location:** `workers/analytics-engine/src/whitespace_radar.py`  
**Status:** Production-Ready  

---

## 1. Overview
The **Whitespace Radar Engine** is Sentinel's retail geomarketing and econometric pipeline. It computes the **Whitespace Opportunity Score (WOS)** for expansion candidate Local Government Units (LGUs) for Pizza Hut in the Philippines.

It processes:
1. **Existing Store Roster Check (Step 0)**: Evaluates whether candidate LGUs already possess active operating stores, ensuring zero false-positive recommendations.
2. **Retail Gap / Leakage Analysis**: Computes signed unmet demand using PSA population, FIES median family income deciles, and an Engel's Law elasticity scaling factor ($\gamma = 0.65$).
3. **Huff Gravity Model**: Computes spatial capture probability against nearby competitor chains (Shakey's, Domino's, Greenwich) and commercial anchors (Jollibee, McDonald's, SM/Robinsons Malls) using steep distance decay ($\beta = 2.5$) calibrated for Philippine transit friction.
4. **Decoupled Risk Overlay**: Assesses flood risk and commissary logistics distance as a separate categorical tier, preventing dilution of commercial upside.
5. **Persistence & Synchronization**: Persists all computed metrics and GeoJSON polygons to Sentinel's `whitespace_opportunities` warehouse table and fires an atomic completion webhook to Birdseye.

---

## 2. CLI Execution

Run the engine from `sentinel/workers/analytics-engine`:
```bash
# Run for Pizza Hut (default: comp-1)
python main.py whitespace comp-1

# Run in test/pytest environment
python -m pytest tests/test_whitespace_radar.py -v
```

---

## 3. Econometric & Spatial Formulas

### 3.1 Signed Retail Gap
$$\text{Demand} = \text{Population} \times \text{MedianIncome} \times \text{BaseRatio} \times \left(\frac{\text{MedianIncome}}{\text{NationalMedian}}\right)^{0.65}$$
$$\text{Supply} = \sum (\text{Competitors} \times \text{SalesProxy})$$
$$\text{DemandGap} = \text{Demand} - \text{Supply}$$
$$\text{DemandGapScore} = 50 + 50 \times \left(\frac{\text{DemandGap}}{\text{MaxAbsGap}}\right) \quad \in [0, 100]$$

### 3.2 Huff Gravity Model
$$P_i = \frac{A_{\text{candidate}} \cdot d(i, \text{candidate})^{-\beta}}{\sum_{j} A_j \cdot d(i, j)^{-\beta}}$$
- $\beta = 2.5$: Calibrated for tricycle/jeepney transit friction.
- $A_j$: Mall anchors = 1.5, Fast food anchors = 1.2, Competitors = 1.0.

> **v1 Known Limitation:** The distance term $d(i, j)$ uses straight-line Haversine rather than network routing distance (OSRM/Valhalla). Standing up a 24/7 self-hosted OSRM container or AWS Batch orchestration for a monthly batch run was deferred to v2 to avoid premature infrastructure tax. Topological barriers (e.g. rivers with a single bridge) are an acknowledged limitation in v1.

### 3.3 Composite WOS
$$\text{WOS} = \text{round}(0.50 \times \text{DemandGapScore} + 0.50 \times \text{PredictedCaptureScore}) \quad \in [0, 100]$$

---

## 4. Database Schema (`whitespace_opportunities`)

Defined in `@sentinel/db` (`packages/db/src/schema/whitespace.ts`):
- `id`: UUID primary key.
- `company_id`: Tenant company ID.
- `lgu_code`: Unique LGU identifier (`UNIQUE(company_id, lgu_code)`).
- `median_family_income_annual`: Median income per year.
- `demand_gap_score`: Signed normalized Retail Gap score.
- `predicted_capture_score`: Spatial capture probability score.
- `opportunity_score`: Composite WOS `[0, 100]`.
- `has_existing_store`: Boolean flag derived from Sentinel store roster.
- `golden_polygon_geojson`: RFC 7946 Polygon geometry.
- `computed_at`: Timestamp of computation run.

---

## 5. Webhook Handshake Contract
Upon successful persistence, Sentinel dispatches:
- **URL**: `POST {BIRDSEYE_URL}/api/internal/whitespace-radar/sync`
- **Header**: `x-internal-secret: <INTERNAL_API_SECRET>`
- **Payload**: Full JSON payload with array of computed opportunities.
- **Error Handling**: A non-2xx response from Birdseye is treated as a fatal pipeline failure.

---

## 6. Architecture Decision Records (ADRs) & Methodology Trade-offs

### ADR-01: Spatial Friction — Spherical Haversine ($\beta = 2.5$) vs OSRM / Valhalla Network Matrix
- **Status:** APPROVED for v1 Production.
- **Context:** `pizza-hut-expansion-data-strategy.md` proposed self-hosted OSRM/Valhalla for drive-time matrices.
- **Decision:** For v1 (Q3 2026 expansion report), Sentinel adopts **Spherical Haversine with a steep transit friction exponent $\beta = 2.5$**.
- **Rationale:**
  1. **Operational Overhead / Zero-Dual-Stack Tax:** Standing up, containerizing, and orchestrating a 24/7 self-hosted OSRM container with 4GB+ Philippine OpenStreetMap road graphs imposes unnecessary infrastructure cost and maintenance overhead for a batch pipeline.
  2. **Micro-Scale Physical Reality:** In compact provincial commercial cores ($< 3\text{ km}$ radius), great-circle distance with a steep $\beta = 2.5$ power decay accurately reflects pedestrian and delivery motorcycle transit resistance without road topology graph dependencies.
- **v2 Upgrade Trigger:** OSRM / Valhalla batch distance matrix is scheduled for v2 when cross-barangay inter-island river/bridge chokepoints and isochrone delivery polygons are deployed.

### ADR-02: Spatial Aggregation — Curated Commercial Centroids & Tiered Urban Share vs PSA Barangay Centroids & MAUP Buffers
- **Status:** APPROVED for v1 Production.
- **Context:** Philippine component cities and HUCs cover vast geographic expanses (hundreds of square kilometers of rural and agricultural terrain). Using geometric municipal centroids lands candidate sites in uninhabited mountains or farmland ("Centroid Fallacy"). Furthermore, evaluating total LGU population saturates the Retail Gap equation.
- **Decision:** For v1 (Top 4 Candidate Cities), Sentinel uses:
  1. **Curated Commercial Anchor Coordinates:** Explicit cluster centers located on primary commercial axes (Perdices St in Dumaguete, Landco/SM in Legazpi, Rizal Ave in PPC, Pioneer Ave in Tagum).
  2. **Tiered Urban Core Ratio:** $0.55$ for HUCs and $0.50$ for 1st-class component cities, dividing by average household size (4.2) to evaluate urban delivery/dining households.
- **v2 Upgrade Trigger:** In v2 (nationwide 1,488 LGU scaling), Sentinel will ingest PSA Census barangay-level shapefiles to calculate population-weighted gravity centers dynamically, alongside isochrone-based trade-area buffers to resolve the Modifiable Areal Unit Problem (MAUP).

### ADR-03: Business Layer Serialization & Read-Only In-Memory Cache Fallback
- **Status:** APPROVED for v1 Production.
- **Context:** Whitespace Radar requires real commercial businesses (competitor pizza chains, QSRs, and anchor malls) displayed on the interactive map when an executive selects an LGU.
- **Decision:**
  1. **Sentinel Serialization**: Sentinel serializes all businesses within 6.0km of the LGU commercial centroid into RFC 7946 GeoJSON FeatureCollections under `layersGeojson["competitorPoints"]` with full metadata (`name`, `category`, `brand`, `address`, `coordinates`).
  2. **Single Writer Invariant**: `mat_whitespace_radar` has exactly one writer: Sentinel's completion webhook. Birdseye's GET handler NEVER writes to `mat_whitespace_radar`.
  3. **Strictly Read-Only Cache Fallback**: If an un-synced row has empty `competitorPoints`, Birdseye enriches the in-memory response from `mat_google_places` (read-only, `business_status` filtered).
  4. **Zero Synchronous Outbound Calls**: Birdseye GET handler never calls Google Places or external APIs synchronously. If 0 cached places exist, it returns `syncPending: true` with an empty FeatureCollection, letting the offline batch worker handle future crawl cycles.
