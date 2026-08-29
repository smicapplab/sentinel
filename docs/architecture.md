# Sentinel Architecture & Cross-Service Integrations

## 1. Overview
Sentinel is the operational intelligence platform across 300+ branch stores. To preserve transactional isolation and clear operational boundaries, Sentinel avoids direct cross-database queries into other Araneta platforms.

## 2. External & Upstream Dependencies

### Birdseye Weather & Event Hazards (`GET /api/internal/weather/active-hazards`)
- **Producer:** Birdseye (`birdseye-web` / Hono service)
- **Consumer:** Sentinel Core API (`@sentinel/core-api`)
- **Protocol:** HTTP REST
- **Endpoint:** `GET /api/internal/weather/active-hazards`
- **Purpose:** Supplies materialized Open-Meteo precipitation aggregates (`isHeavyRainfall`) and DOST-PAGASA severe weather/event suspensions (`isSuspension`) per branch.
- **Caching:** Sentinel Core API caches this payload in-memory with a 5-minute TTL (`CACHE_TTL = 300000ms`) to avoid hammering Birdseye on concurrent store map renders.
- **Data Joining:** Sentinel Core API joins the external weather status with local topographical polygon vectors (`stores.hazardPolygons`) stored in Sentinel's Postgres schema.

## 3. Geospatial Visualization (`dash-web`)
- **Component:** `src/components/FloodRiskMap.svelte`
- **Library:** Leaflet
- **Data Source:** Sentinel Core API endpoint `/api/v1/hazards`
- **Reactivity:** Dynamically shades hazard polygons across three operational severity tiers:
  - **Normal / Blue:** Low rainfall, regular dispatch.
  - **Amber / Orange:** Heavy rainfall (>15mm/day) alert.
  - **Red / Severe:** Heavy rainfall coupled with government/PAGASA operational suspension.
