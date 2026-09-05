# Sentinel Whitespace Radar Engine

**Module:** `sentinel` (Downstream AI & Computational Engine)  
**Location:** `workers/analytics-engine/src/whitespace_radar.py`  
**Status:** Production-Ready  

---

## 1. Overview
The **Whitespace Radar Engine** is Sentinel's retail geomarketing pipeline. It answers two
questions, in strict order:

1. **Where is Pizza Hut not present yet?** A filter, not a score.
2. **Among those, which is the best site?** A ranking over the filtered set.

Question 1 dominates. A false "Pizza Hut is absent here" sends a site team to build beside
an existing branch, which costs capital; a missed opportunity only costs delay. The store
roster is therefore the single most important input to the feature.

The pipeline:
1. **Presence partition (Step 0)**: Classifies every candidate LGU as `PRESENT`, `ABSENT`, or
   `UNKNOWN` against the Pizza Hut store roster fetched from Birdseye. `ABSENT` is only
   reachable when roster coverage is `COMPLETE`; absence of a store *record* is not evidence
   of store *absence*.
2. **Retail Gap / Leakage Analysis**: Signed unmet demand from PSA population and FIES income,
   scaled by an Engel's Law elasticity ($\gamma = 0.65$).
3. **Competitive Saturation Index**: Attractiveness-weighted, distance-decayed competitor
   supply measured against demand. See 3.2 for why this replaced the Huff capture term.
4. **Confidence band**: Every score carries a derived uncertainty interval. A score is never
   emitted without one.
5. **Persistence & Synchronization**: Writes to `whitespace_opportunities` and fires a
   completion webhook to Birdseye.

### 1.1 Invariants

- Sentinel makes **zero** direct external HTTP calls. All third-party data is ingested by
  Birdseye and read over the internal API.
- **No fabricated data.** There is no synthetic competitor fallback, no hand-drawn flood or
  trade-area geometry, and no hardcoded store roster. Missing data yields an omitted layer or
  a widened band, never an invented value.
- **Absence of evidence is not evidence of absence.** An LGU with no POI coverage is not an
  LGU with no competitors.

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

### 3.2 Competitive Saturation Index

$$\text{WeightedSupply} = \sum_{d_j \le R} \frac{A_j}{(1 + d_j)^{\beta}}, \quad \beta = 2.5,\ R = 6\text{ km}$$
$$\text{Saturation} = 100 \times \left(1 - e^{-\frac{\text{Demand}}{(\text{WeightedSupply} + 1)\, D_{ref}}}\right) \quad \in [0, 100]$$

Higher means less contested.

**Why this replaced the Huff gravity model.** A single-site Huff model answers "what share
would a store at point X capture?". We rank **LGUs**, not sites, and there is no candidate
site — so one had to be fabricated 157 m from the demand centroid, where it always dominated
the Huff denominator. Every LGU clamped to the same ceiling (`predicted_capture_score = 96.00`
across all 20), the composite collapsed to a market-size ranking, and the score carried no
information. The saturation index has no candidate site, so it cannot saturate that way.

`calculate_huff_capture_probability` is retained in the module but is **not called by the LGU
pipeline**. It is reserved for future site-level drill-down, where real candidate parcels
exist and the model is the right instrument.

$D_{ref}$ (`D_REF_PHP_PER_SUPPLY_UNIT`) is the one asserted constant in the scoring path.
It is uncalibrated pending POS data. A sensitivity sweep across a 16x range leaves the top 5
whitespace ranking unchanged, so the ordering is usable while absolute scores are not.

### 3.3 Presence Partition

`presence_state(lgu_code, roster_coverage, roster_lgu_codes)` returns:

| State | Meaning |
|---|---|
| `PRESENT` | Exact `lgu_code` match in the roster |
| `ABSENT` | Not in roster **and** roster coverage is `COMPLETE` |
| `UNKNOWN` | Not in roster, coverage below `COMPLETE` — cannot assert absence |

Matching is exact `lgu_code` membership only. Substring city matching is deliberately not
used: "San Fernando" names three Philippine cities, and an exclusion filter with asymmetric
error cost must not guess.

### 3.4 Confidence Band

$$C = 0.3\,c_{brand} + 0.2\,c_{geo} + 0.3\,c_{inc} + 0.2\,c_{cal}$$
$$\text{BandHalfwidth} = W_{max}(1 - C), \quad W_{max} = 25$$

| Factor | Meaning |
|---|---|
| $c_{brand}$ | Roster brands observed in this LGU / roster size |
| $c_{geo}$ | Brands observed **with usable coordinates** / roster size |
| $c_{inc}$ | `1.0` PSA city actual, `0.7` PSA provincial proxy, `0.4` model estimate |
| $c_{cal}$ | `1.0` if POS-calibrated for the region, else `0.3` |

$c_{brand}$ and $c_{geo}$ are separate because only the latter can feed a distance-weighted
computation. Collapsing them would let a verified-but-unlocated competitor raise coverage,
narrow the band, and then be silently dropped by the trade-radius filter — undercounting
supply while asserting confidence.

`band_method` records which regime produced the interval: `COVERAGE_HEURISTIC` today,
`EMPIRICAL_RESIDUAL` once POS backtesting replaces $W_{max}$ with a measured residual spread.

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

### ADR-04: Multi-Category POI Taxonomy, UP-NOAH Flood Polygons & Live Traffic Flow
- **Status:** APPROVED for v1 Production.
- **Context:** Executive review required granular visibility into specific POI classes (separating direct pizza competitors from fast food, dining, retail anchors, and educational institutions), functional flood hazard risk zones, and live traffic congestion.
- **Decision:**
  1. **Taxonomy Separation**: Disaggregated POI taxonomy into `PIZZA`, `FAST_FOOD`, `RESTAURANT`, `ANCHOR`, `EDUCATION`, `HOSPITAL`, and `LANDMARK`. Huff Gravity competition scoring strictly isolates QSR/dining anchors without skewing pizza supply calculations.
  2. **UP-NOAH Flood Zones**: Hydrological geohazard polygons (riverine inundation, coastal surge) are serialized under `layersGeojson["floodZones"]` for all candidate LGUs with explicit severity tiers (`LOW`, `MEDIUM`, `HIGH`).
  3. **Mapbox Traffic & Sleek Pins**: The UI renders custom drop-shadowed SVG teardrop pins and overlays real-time Mapbox vector traffic flow (`mapbox/traffic-day-v2`), retiring the obstructive 3km delivery circles.
