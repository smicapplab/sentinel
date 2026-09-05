import os
import math
import json
import uuid
import requests
from datetime import datetime, timezone
try:
    from .db import get_connection
except (ImportError, ValueError):
    try:
        from src.db import get_connection
    except (ImportError, ValueError):
        from db import get_connection

EARTH_RADIUS_KM = 6371.0

# Initial candidate LGUs for Pizza Hut Whitespace Expansion

def calculate_elastic_spend_ratio(
    median_income: float,
    national_median: float = 250000.0,
    base_ratio: float = 0.05,
    gamma: float = 0.65
) -> float:
    """
    Engel's Law: category spend share is non-linear relative to income.
    Higher-income deciles spend an elastically larger share on dining out/QSR.
    """
    if national_median <= 0 or median_income <= 0:
        return base_ratio
    return base_ratio * ((median_income / national_median) ** gamma)

def calculate_demand_gap(demand: float, supply: float) -> float:
    """
    Signed Retail Gap: Demand - Supply.
    Do NOT floor at zero: oversupplied markets yield negative gaps to penalize saturation.
    """
    return demand - supply

def normalize_demand_gap_score(demand_gap: float, max_abs_gap: float = 100_000_000.0) -> float:
    """
    Normalizes signed demand gap to [0, 100].
    Gaps < 0 land below 50. Gaps > 0 land above 50.
    """
    if max_abs_gap <= 0:
        return 50.0
    normalized = 50.0 + 50.0 * (demand_gap / max_abs_gap)
    return max(0.0, min(100.0, round(normalized, 2)))

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c

def clean_and_deduplicate_pois(raw_pois: list[dict], min_distance_meters: float = 50.0) -> list[dict]:
    """
    Filters out permanently/temporarily closed locations and clusters
    closely-spaced duplicate pins within min_distance_meters.
    """
    cleaned: list[dict] = []
    min_dist_km = min_distance_meters / 1000.0

    for poi in raw_pois:
        # Check both Google Places businessStatus and legacy status
        status = str(poi.get("businessStatus") or poi.get("status") or "OPERATIONAL").upper()
        if "CLOSED" in status:
            continue

        lat = poi.get("lat")
        lon = poi.get("lon")
        if lat is None or lon is None:
            continue

        is_duplicate = False
        for existing in cleaned:
            d = haversine_distance_km(lat, lon, existing["lat"], existing["lon"])
            if d < min_dist_km:
                is_duplicate = True
                break

        if not is_duplicate:
            cleaned.append(poi)

    return cleaned

def calculate_huff_capture_probability(
    demand_pt: tuple[float, float],
    candidate_pt: tuple[float, float],
    candidate_attractiveness: float,
    competitors: list[dict],
    beta: float = 2.5,
    min_distance_km: float = 0.1
) -> float:
    """
    Huff Gravity Model:
    P_i = (A_cand / d_cand^beta) / [ (A_cand / d_cand^beta) + sum_j (A_j / d_j^beta) ]
    Uses steep beta=2.5 for Philippine provincial transit friction.
    """
    d_cand = max(min_distance_km, haversine_distance_km(demand_pt[0], demand_pt[1], candidate_pt[0], candidate_pt[1]))
    num = candidate_attractiveness / (d_cand ** beta)
    denom = num

    for comp in competitors:
        lat = comp.get("lat")
        lon = comp.get("lon")
        if lat is None or lon is None:
            continue
        d_j = max(min_distance_km, haversine_distance_km(demand_pt[0], demand_pt[1], lat, lon))
        a_j = float(comp.get("attractiveness", 1.0))
        denom += a_j / (d_j ** beta)

    if denom <= 0:
        return 0.0
    return min(1.0, max(0.0, num / denom))

def presence_state(lgu_code: str, roster_coverage: str, roster_lgu_codes: set[str]) -> str:
    """
    Three-way partition on Pizza Hut presence: PRESENT | ABSENT | UNKNOWN.

    We may only claim ABSENT when the store roster is complete enough to support
    the claim. A false 'absent' sends a site team to build beside an existing
    branch, which costs capital; a missed opportunity only costs delay. Absence of
    a store RECORD is not evidence of store ABSENCE.

    Exact lgu_code membership only. Substring city matching is deliberately not
    used: 'San Fernando' names three different Philippine cities, and an exclusion
    filter with asymmetric error cost must not guess.
    """
    if lgu_code in roster_lgu_codes:
        return "PRESENT"
    if roster_coverage != "COMPLETE":
        return "UNKNOWN"
    return "ABSENT"


# Reference demand supported per unit of attractiveness-weighted competitor supply.
# PROVISIONAL: replaced by the POS-derived value once pos_daily_store_sales has data.
# Declared here rather than buried inline so the one asserted constant is visible.
D_REF_PHP_PER_SUPPLY_UNIT = 400_000_000.0


def compute_saturation_index(
    potential_demand: float,
    competitors: list[dict],
    centroid: tuple[float, float],
    trade_radius_km: float = 6.0,
    beta: float = 2.5,
) -> float:
    """
    Attractiveness-weighted, distance-decayed competitor supply measured against
    demand. Higher means less contested.

    Replaces the single-site Huff capture term, which was the wrong instrument for
    LGU ranking: with no real candidate site, one had to be fabricated 157m from
    the demand centroid, where it always dominated the Huff denominator and drove
    every LGU to the same 96.00 ceiling. There is no candidate site here, so there
    is nothing to saturate.
    """
    weighted_supply = 0.0
    for c in competitors:
        # Callers pass only located competitors. Guard anyway: skipping an
        # unlocated row here while it counts toward coverage is precisely the
        # undercount-supply-overstate-confidence defect this design forbids.
        if c.get("lat") is None or c.get("lon") is None:
            raise ValueError(
                f"competitor {c.get('name')!r} reached the saturation model without "
                "coordinates; callers must pass only located rows"
            )
        d = haversine_distance_km(centroid[0], centroid[1], c["lat"], c["lon"])
        if d > trade_radius_km:
            continue
        weighted_supply += c.get("attractiveness", 1.0) / ((1.0 + d) ** beta)

    # Unmet demand per unit of effective supply. The +1.0 keeps a zero-competitor
    # LGU finite without an artificial floor.
    unmet_ratio = potential_demand / (weighted_supply + 1.0) / D_REF_PHP_PER_SUPPLY_UNIT

    # Bounded and strictly monotonic. No clamp that can saturate.
    return round(100.0 * (1.0 - math.exp(-unmet_ratio)), 2)


# The single asserted constant in the confidence-band path. Replaced by the
# empirical residual spread once POS backtesting is possible.
W_MAX = 25.0


def compute_coverage_index(c_brand: float, c_geo: float, c_inc: float, c_cal: float) -> float:
    """
    c_brand: roster brands VERIFIED present-or-absent here / roster size
    c_geo:   roster brands VERIFIED and carrying usable coordinates / roster size
    c_inc:   1.0 if income is government-sourced, 0.4 if modelled
    c_cal:   1.0 if POS-calibrated for this region, else 0.3

    c_brand and c_geo are separate because only the second can feed a
    distance-weighted computation.
    """
    return 0.3 * c_brand + 0.2 * c_geo + 0.3 * c_inc + 0.2 * c_cal


def compute_confidence_band(coverage_index: float, method: str = "COVERAGE_HEURISTIC") -> tuple[float, str]:
    """Band half-width derived from measured coverage, never asserted."""
    if method != "COVERAGE_HEURISTIC":
        raise ValueError(f"unsupported band method: {method}")
    bounded = max(0.0, min(1.0, coverage_index))
    return round(W_MAX * (1.0 - bounded), 2), method


BRAND_ROSTER = (
    "Jollibee", "McDonald's", "Shakey's", "KFC", "Chowking", "Mang Inasal",
    "Greenwich", "Domino's", "Yellow Cab", "Pizza Hut", "Angel's Pizza",
)


def roster_lgu_codes_from_stores(existing_stores: list[dict]) -> set[str]:
    """
    Exact lgu_code membership from the authoritative store table. The previous
    implementation also matched on substring city name and store name, which both
    over- and under-matched; see presence_state for why guessing is unacceptable
    in an exclusion filter.
    """
    return {
        str(s.get("lguCode") or s.get("lgu_code") or "").strip().upper()
        for s in existing_stores
        if (s.get("lguCode") or s.get("lgu_code"))
    }


def competitor_coverage_fractions(
    located_competitors: list[dict],
    businesses: list[dict],
) -> tuple[float, float]:
    """
    Returns (c_brand, c_geo) against BRAND_ROSTER.

    Competitor POIs currently originate from Google Places, which is unverified
    (PLACES_API), so these fractions measure observation, not verification. The
    residual uncertainty is carried by c_cal until a verified competitor source
    exists. Every Places POI carries coordinates by construction, so c_geo tracks
    c_brand today; they diverge once unlocated verified rows can enter.
    """
    if not BRAND_ROSTER:
        return 0.0, 0.0
    observed = {
        str(b.get("brand") or "").strip().lower()
        for b in businesses
        if b.get("brand")
    }
    located = {
        str(b.get("brand") or "").strip().lower()
        for b in businesses
        if b.get("brand") and b.get("lat") is not None and b.get("lon") is not None
    }
    roster = {b.lower() for b in BRAND_ROSTER}
    c_brand = len(observed & roster) / len(roster)
    c_geo = len(located & roster) / len(roster)
    return round(c_brand, 4), round(c_geo, 4)


def compute_composite_wos(
    demand_gap_score: float,
    predicted_capture_score: float,
    weight_gap: float = 0.5,
    weight_capture: float = 0.5
) -> int:
    """Computes composite Whitespace Opportunity Score [0, 100]."""
    score = round(weight_gap * demand_gap_score + weight_capture * predicted_capture_score)
    return max(0, min(100, int(score)))

def generate_golden_polygon_geojson(
    center_lat: float,
    center_lon: float,
    radius_km: float = 2.0,
    name: str = "Core Delivery Zone"
) -> dict:
    """Generates RFC 7946 Polygon Feature representing candidate delivery catchment."""
    coords = []
    num_points = 16
    for i in range(num_points):
        angle = (2.0 * math.pi * i) / num_points
        # Approx deg to km at Philippine latitude
        d_lat = (radius_km / 110.574) * math.cos(angle)
        d_lon = (radius_km / (111.320 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        coords.append([round(center_lon + d_lon, 5), round(center_lat + d_lat, 5)])
    
    # Close ring
    coords.append(coords[0])

    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "radiusKm": radius_km,
            "recommendation": "Prime Site (Drive-Thru / High Visibility Hub)"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords]
        }
    }

def build_trade_area_stub(trade_radius_km: float = 6.0) -> dict:
    """
    Trade-area geometry is NOT synthesised here. Birdseye exposes tradeRadiusKm and
    the centroid; the client draws the circle. A MODEL_ESTIMATE polygon persisted
    to the database and sent over the wire is indistinguishable from surveyed
    geometry to every downstream consumer.
    """
    return {"tradeRadiusKm": trade_radius_km}


def compute_candidate_records(
    candidate_lgus: list[dict],
    cleaned_pois: list[dict],
    existing_stores: list[dict] = None,
    avg_store_sales_proxy: float = 18_000_000.0,
    roster_coverage: str = "PARTIAL",
    roster_lgu_codes: set[str] = None,
) -> list[dict]:
    """
    Computes candidate scores and records using retail gap and Huff gravity modeling.
    Modular and pure for deterministic unit testing.
    """
    if existing_stores is None:
        existing_stores = []
    if roster_lgu_codes is None:
        roster_lgu_codes = roster_lgu_codes_from_stores(existing_stores)

    computed_records: list[dict] = []

    for lgu in candidate_lgus:
        lgu_code = lgu["lgu_code"]
        pop = lgu["population"]
        med_income = lgu["median_family_income_annual"]
        cluster_pt = (lgu["cluster_lat"], lgu["cluster_lon"])

        # Step 3: Retail Gap Analysis (Urban Catchment Population)
        is_huc = "HUC" in lgu["income_classification"] or "Special" in lgu["income_classification"]
        urban_share = 0.55 if is_huc else 0.50
        catchment_households = (pop * urban_share) / 4.2
        spend_ratio = calculate_elastic_spend_ratio(med_income)
        potential_demand = catchment_households * med_income * spend_ratio

        # Find nearby competitors & anchors in cleaned POIs within 5km of cluster
        nearby_competitors = []
        lgu_businesses = []
        pizza_count = 0
        fastfood_count = 0
        anchor_count = 0

        for p in cleaned_pois:
            dist = haversine_distance_km(cluster_pt[0], cluster_pt[1], p["lat"], p["lon"])
            if dist <= 6.0:
                cat = str(p.get("category", "")).upper()
                name = str(p.get("name", "")).upper()
                raw_types = [str(t).upper() for t in p.get("rawTypes", [])] if isinstance(p.get("rawTypes"), list) else []
                types_str = " ".join(raw_types)

                if "PIZZA" in cat or "PIZZA" in name:
                    classified_cat = "PIZZA"
                    pizza_count += 1
                    nearby_competitors.append({"lat": p["lat"], "lon": p["lon"], "attractiveness": 1.0})
                elif "ANCHOR" in cat or any(kw in name for kw in ["MALL", "SM ", "SM CITY", "ROBINSONS", "GAISANO", "LEE SUPER PLAZA", "UNITOP", "CANG'S"]):
                    classified_cat = "ANCHOR"
                    anchor_count += 1
                    nearby_competitors.append({"lat": p["lat"], "lon": p["lon"], "attractiveness": 1.5})
                elif any(kw in name for kw in ["JOLLIBEE", "MCDONALD", "KFC", "MANG INASAL", "CHOWKING", "BURGER KING"]) or "FAST_FOOD" in cat:
                    classified_cat = "FAST_FOOD"
                    fastfood_count += 1
                    nearby_competitors.append({"lat": p["lat"], "lon": p["lon"], "attractiveness": 1.2})
                elif "UNIVERSITY" in name or "COLLEGE" in name or "SCHOOL" in name or "EDUCATION" in cat or "UNIVERSITY" in types_str:
                    classified_cat = "EDUCATION"
                elif "HOSPITAL" in name or "MEDICAL" in name or "CLINIC" in name:
                    classified_cat = "HOSPITAL"
                elif any(kw in name for kw in ["PLAZA", "PARK", "CATHEDRAL", "CAPITOL", "CITY HALL", "BOULEVARD"]):
                    classified_cat = "LANDMARK"
                else:
                    classified_cat = "RESTAURANT"

                lgu_businesses.append({
                    "name": p.get("name", "Business"),
                    "category": classified_cat,
                    "brand": p.get("brand"),
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "address": p.get("address", "")
                })

        # Live POIs only. The synthetic competitor fallback that previously ran
        # here (a city-name if/elif chain plus generated pins in a circle around
        # downtown) is deleted: fabricated competitors on a map are worse than an
        # empty map, and 17 of 20 cities fell through to a generic 2/8/4 default.
        data_source = "LIVE_POI_INGESTION" if nearby_competitors else "NO_POI_COVERAGE"
        is_calibrated_estimate = not bool(nearby_competitors)

        existing_supply = pizza_count * avg_store_sales_proxy
        demand_gap = calculate_demand_gap(potential_demand, existing_supply)
        demand_gap_score = normalize_demand_gap_score(demand_gap, max_abs_gap=2_500_000_000.0)

        # Step 4: Competitive saturation. See compute_saturation_index for why the
        # single-site Huff capture term was removed from LGU-level ranking.
        predicted_capture_score = compute_saturation_index(
            potential_demand=potential_demand,
            competitors=nearby_competitors,
            centroid=cluster_pt,
        )

        opportunity_score = compute_composite_wos(demand_gap_score, predicted_capture_score)

        # Presence partition and confidence band.
        presence = presence_state(lgu_code, roster_coverage, roster_lgu_codes)
        c_brand, c_geo = competitor_coverage_fractions(nearby_competitors, lgu_businesses)
        # Income confidence by provenance tier. PSA_PROVINCIAL is government-
        # sourced but is the province figure standing in for a city, and cities
        # are richer than their provinces, so it earns partial credit rather than
        # full. An uncited claim earns the same as a model estimate.
        _prov = lgu.get("income_data_provenance")
        c_inc = 1.0 if _prov == "PSA_ACTUAL" else 0.7 if _prov == "PSA_PROVINCIAL" else 0.4
        coverage_index = compute_coverage_index(c_brand, c_geo, c_inc, c_cal=0.3)
        band_halfwidth, band_method = compute_confidence_band(coverage_index)

        # The "golden polygon" was a hand-drawn per-LGU constant (TERRESTRIAL_CORRIDORS),
        # deleted with the rest of the fabricated geometry. Until a real trade-area
        # source exists, expose the radius and let the client draw the circle.
        golden_polygon = lgu.get("trade_area") or build_trade_area_stub()

        # Package businesses into RFC 7946 GeoJSON FeatureCollection
        competitor_features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(b["lon"], 6), round(b["lat"], 6)]
                },
                "properties": {
                    "name": b["name"],
                    "category": b["category"],
                    "brand": b["brand"],
                    "address": b.get("address", "")
                }
            }
            for b in lgu_businesses
        ]

        layers_geojson = {
            "competitorPoints": {
                "type": "FeatureCollection",
                "features": competitor_features
            }
        }
        # Flood geometry comes from Birdseye's PAGASA connector, or not at all.
        flood_feature = lgu.get("flood_zones")
        if flood_feature:
            layers_geojson["floodZones"] = flood_feature

        # Key the disclaimer off the provenance field itself. It previously keyed
        # off income_classification, which master_ph_lgus does not carry, so the
        # .get() always returned "Unknown" and every row -- including PSA_ACTUAL
        # ones -- was stamped with the model-estimate caveat, contradicting the
        # provenance field beside it.
        rationale = lgu["rationale"]
        if lgu.get("income_data_provenance") != "PSA_ACTUAL":
            rationale = f"[DATA PROVENANCE: Median income is a calibrated model estimate; PSA does not publish FIES at the component city level.] {rationale}"

        if is_calibrated_estimate:
            rationale = f"[NO POI COVERAGE: Google Places crawl pending for this LGU] {rationale}"

        record = {
            "lguCode": lgu["lgu_code"],
            "lguName": lgu["lgu_name"],
            "province": lgu["province"],
            "region": lgu["region"],
            "incomeClassification": lgu["income_classification"],
            "socioEconomicTier": lgu["socio_economic_tier"],
            "population": pop,
            "medianFamilyIncomeAnnual": med_income,
            "averageFamilyIncomeAnnual": lgu["avg_family_income_annual"],
            "demandGapScore": demand_gap_score,
            "predictedCaptureScore": predicted_capture_score,
            "opportunityScore": opportunity_score,
            "brandFit": "Pizza Hut",
            "hasExistingStore": presence == "PRESENT",
            "presenceState": presence,
            "coverageIndex": round(coverage_index, 4),
            "confidenceBandHalfwidth": band_halfwidth,
            "bandMethod": band_method,
            "competitorCounts": {
                "pizza": pizza_count,
                "fastfood": fastfood_count,
                "anchors": anchor_count
            },
            "floodRiskLevel": lgu["flood_risk_level"],
            "summaryRationale": rationale,
            "dataSource": data_source,
            "isCalibratedEstimate": is_calibrated_estimate,
            "incomeDataProvenance": lgu.get("income_data_provenance", "MODEL_ESTIMATE"),
            "goldenPolygonGeojson": golden_polygon,
            "layersGeojson": layers_geojson
        }
        computed_records.append(record)

    computed_records.sort(key=lambda r: r["opportunityScore"], reverse=True)
    return computed_records

def build_sync_payload(company_id: str, records: list[dict]) -> dict:
    """Builds the webhook payload conforming to Birdseye API contract."""
    return {
        "companyId": company_id,
        "batchId": str(uuid.uuid4()),
        "recordCount": len(records),
        "records": records
    }
def fetch_pois_from_birdseye(company_id: str, lgu_code: str) -> list[dict]:
    """
    Fetches POIs for a SINGLE LGU. Scoped per-LGU rather than paginated: Birdseye
    bounds the result to the LGU trade radius, so the worker holds one LGU's POIs
    at a time by construction. No cursor protocol to get right on both ends.

    A non-200 is raised, never swallowed. An empty competitor set is a legitimate
    model input meaning "no competitors"; a failed fetch is not, and silently
    conflating them inflates every downstream opportunity score.
    """
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")
    if not internal_secret:
        raise RuntimeError("INTERNAL_API_SECRET environment variable is unset. Failing closed.")

    resp = requests.get(
        f"{birdseye_url}/api/internal/places/pois",
        params={"companyId": company_id, "lguCode": lgu_code},
        headers={"x-internal-secret": internal_secret},
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"POI fetch failed for {lgu_code}: HTTP {resp.status_code} {resp.text[:200]}"
        )
    return resp.json().get("pois", [])


def fetch_store_roster_from_birdseye(company_id: str) -> tuple[str, set[str]]:
    """
    Returns (coverage, lgu_codes) for the Pizza Hut store roster.

    Sourced from Birdseye, which owns ingestion, rather than Sentinel's own stores
    table: the two copies had diverged (9 attributed branches there against 2 rows
    here), and presence must be computed from the authoritative side.

    Coverage is asserted by the import, not inferred. A roster of 9 branches looks
    identical whether it is the complete national list or an arbitrary subset, and
    only the former licenses an ABSENT verdict.
    """
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")
    if not internal_secret:
        raise RuntimeError("INTERNAL_API_SECRET environment variable is unset. Failing closed.")

    resp = requests.get(
        f"{birdseye_url}/api/internal/stores/roster",
        params={"companyId": company_id},
        headers={"x-internal-secret": internal_secret},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("coverage", "PARTIAL"), {c for c in data.get("lguCodes", []) if c}


def fetch_lgus_from_birdseye(company_id: str, lgu_code: str = None) -> list[dict]:
    """
    Fetches the LGU registry from Birdseye, which is the single source of truth.

    The lguCode filter is applied server-side AND re-applied client-side. The
    redundancy is deliberate: if the server ever ignores the parameter, a targeted
    run must still score only the LGU that was requested, rather than silently
    recomputing the entire registry and reporting success.
    """
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")
    if not internal_secret:
        raise RuntimeError("INTERNAL_API_SECRET environment variable is unset. Failing closed.")

    params = {}
    if lgu_code:
        params["lguCode"] = lgu_code

    resp = requests.get(
        f"{birdseye_url}/api/internal/lgus",
        params=params,
        headers={"x-internal-secret": internal_secret},
        timeout=10.0,
    )
    resp.raise_for_status()
    lgus = resp.json().get("data", [])

    if lgu_code:
        lgus = [l for l in lgus if l.get("lguCode") == lgu_code]

    return lgus



def run_whitespace_radar(company_id: str = "comp-1", trigger_webhook: bool = True, lgu_code: str = None) -> list[dict]:
    """
    Main execution pipeline for Sentinel Whitespace Radar:
    1. Check existing stores from Sentinel database (Step 0).
    2. Ingest POIs from Birdseye internal API over HTTP, per LGU (Step 2).
    3. Compute retail gap and competitive saturation (Steps 3-4).
    4. Persist pre-computed records to Sentinel Postgres warehouse (Step 6).
    5. Dispatch completion webhook to Birdseye (Step 7).
    """
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")

    print(f"[Whitespace Radar] Starting execution pipeline for company: {company_id}" + (f" (LGU: {lgu_code})" if lgu_code else ""))

    # Step 0: Fetch existing stores with city and LGU metadata from Sentinel DB
    existing_stores: list[dict] = []
    avg_store_sales_proxy = 18_000_000.0  # Fallback standard PH QSR revenue benchmark
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT store_number, name, COALESCE(city, ''), COALESCE(lgu_code, '') FROM stores WHERE is_active = true")
                rows = cur.fetchall()
                existing_stores = [
                    {"storeNumber": str(r[0]), "name": str(r[1]), "city": str(r[2]), "lguCode": str(r[3])}
                    for r in rows
                ]
                print(f"[Whitespace Radar] Loaded {len(existing_stores)} active stores from Sentinel database.")

                cur.execute("SELECT AVG(net_sales) FROM pos_daily_store_sales")
                row = cur.fetchone()
                if row and row[0]:
                    avg_daily_sales = float(row[0])
                    if avg_daily_sales > 1000:
                        avg_store_sales_proxy = avg_daily_sales * 365.0
                        print(f"[Whitespace Radar] Dynamically calibrated avg store sales to PHP {avg_store_sales_proxy:,.2f} based on POS data.")
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR: Failed to query stores/POS from Sentinel database: {e}")
        raise RuntimeError(f"Database error querying Sentinel warehouse: {e}") from e

    # Step 2: Fetch Base LGUs from Birdseye Internal HTTP API
    try:
        fetched_lgus = fetch_lgus_from_birdseye(company_id, lgu_code)
        if not fetched_lgus:
            raise RuntimeError("Birdseye returned no LGUs for evaluation.")
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR fetching LGUs: {e}")
        raise RuntimeError(f"API error querying LGUs: {e}") from e

    candidate_lgus = []
    for flgu in fetched_lgus:
        candidate_lgus.append({
            "lgu_code": flgu.get("lguCode"),
            "lgu_name": flgu.get("lguName", ""),
            "province": flgu.get("province", ""),
            "region": flgu.get("region", ""),
            "income_classification": flgu.get("incomeClassification", "Unknown"),
            "population": flgu.get("population", 100000),
            "median_family_income_annual": flgu.get("medianFamilyIncomeAnnual", 250000),
            "income_data_provenance": flgu.get("incomeDataProvenance", "MODEL_ESTIMATE"),
            "cluster_lat": flgu.get("clusterLat", 0.0),
            "cluster_lon": flgu.get("clusterLon", 0.0),
            "socio_economic_tier": "Unknown",
            "avg_family_income_annual": int(flgu.get("medianFamilyIncomeAnnual", 0) * 1.25),
            "flood_risk_level": "UNASSESSED",
            "rationale": "Automated baseline generation."
        })

    # Step 2.5: Ingest competitor and anchor POIs from Birdseye, one LGU at a time.
    # A fetch failure is fatal. Previously it was swallowed and logged as
    # "Fetched 0 POIs", so a 401 or 500 fed an empty competitor set into the
    # retail-gap model and inflated every opportunity score.
    raw_pois: list[dict] = []
    for cl in candidate_lgus:
        pois = fetch_pois_from_birdseye(company_id, cl["lgu_code"])
        print(f"[Whitespace Radar] Fetched {len(pois)} POIs for {cl['lgu_code']} ({cl['lgu_name']}).")
        raw_pois.extend(pois)

    # Data hygiene & deduplication
    cleaned_pois = clean_and_deduplicate_pois(raw_pois)

    # Step 3 & 4: Retail gap and competitive saturation.
    #
    # roster_coverage gates the ABSENT verdict. It is PARTIAL until the Pizza Hut
    # store roster is loaded from an authoritative operational source; birdseye.stores
    # currently holds a handful of NCR rows against a national estate of roughly
    # 250-300 branches, so we cannot yet assert absence anywhere. Every LGU will
    # therefore report presenceState UNKNOWN, which is the honest answer.
    roster_coverage, roster_codes = fetch_store_roster_from_birdseye(company_id)
    if roster_coverage not in ("COMPLETE", "PARTIAL", "PRESENCE_ONLY", "NO_PUBLIC_DATA"):
        raise ValueError(f"Invalid roster coverage from Birdseye: {roster_coverage}")
    print(f"[Whitespace Radar] Store roster: {len(roster_codes)} LGU(s), coverage={roster_coverage}.")

    computed_records = compute_candidate_records(
        candidate_lgus=candidate_lgus,
        cleaned_pois=cleaned_pois,
        existing_stores=existing_stores,
        avg_store_sales_proxy=avg_store_sales_proxy,
        roster_coverage=roster_coverage,
        roster_lgu_codes=roster_codes,
    )
    print(
        f"[Whitespace Radar] Store roster coverage={roster_coverage}; "
        f"presence partition: "
        f"{sum(1 for r in computed_records if r['presenceState'] == 'ABSENT')} ABSENT, "
        f"{sum(1 for r in computed_records if r['presenceState'] == 'PRESENT')} PRESENT, "
        f"{sum(1 for r in computed_records if r['presenceState'] == 'UNKNOWN')} UNKNOWN."
    )


    # Step 6: Persist pre-computed records to Sentinel Postgres warehouse
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Upsert records
                for rec in computed_records:
                    cur.execute("""
                        INSERT INTO whitespace_opportunities (
                            company_id, lgu_code, lgu_name, province, region,
                            income_classification, socio_economic_tier, population,
                            avg_family_income_annual, median_family_income_annual,
                            demand_gap_score, predicted_capture_score,
                            opportunity_score, brand_fit, has_existing_store,
                            competitor_counts, flood_risk_level, golden_polygon_geojson,
                            layers_geojson, summary_rationale, data_source, is_calibrated_estimate, income_data_provenance,
                            presence_state, coverage_index, confidence_band_halfwidth, band_method, computed_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, NOW()
                        )
                        ON CONFLICT (company_id, lgu_code) DO UPDATE SET
                            opportunity_score = EXCLUDED.opportunity_score,
                            demand_gap_score = EXCLUDED.demand_gap_score,
                            predicted_capture_score = EXCLUDED.predicted_capture_score,
                            competitor_counts = EXCLUDED.competitor_counts,
                            has_existing_store = EXCLUDED.has_existing_store,
                            golden_polygon_geojson = EXCLUDED.golden_polygon_geojson,
                            summary_rationale = EXCLUDED.summary_rationale,
                            data_source = EXCLUDED.data_source,
                            is_calibrated_estimate = EXCLUDED.is_calibrated_estimate,
                            income_data_provenance = EXCLUDED.income_data_provenance,
                            presence_state = EXCLUDED.presence_state,
                            coverage_index = EXCLUDED.coverage_index,
                            confidence_band_halfwidth = EXCLUDED.confidence_band_halfwidth,
                            band_method = EXCLUDED.band_method,
                            computed_at = NOW()
                    """, (
                        company_id, rec["lguCode"], rec["lguName"], rec["province"], rec["region"],
                        rec["incomeClassification"], rec["socioEconomicTier"], rec["population"],
                        rec["averageFamilyIncomeAnnual"], rec["medianFamilyIncomeAnnual"],
                        rec["demandGapScore"], rec["predictedCaptureScore"],
                        rec["opportunityScore"], rec["brandFit"], rec["hasExistingStore"],
                        json.dumps(rec["competitorCounts"]), rec["floodRiskLevel"],
                        json.dumps(rec["goldenPolygonGeojson"]), json.dumps(rec["layersGeojson"]),
                        rec["summaryRationale"], rec["dataSource"], rec["isCalibratedEstimate"], rec["incomeDataProvenance"],
                        rec["presenceState"], rec["coverageIndex"], rec["confidenceBandHalfwidth"], rec["bandMethod"]
                    ))
                conn.commit()
                print(f"[Whitespace Radar] Persisted {len(computed_records)} opportunities to Sentinel warehouse.")
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR: Failed to persist opportunities to Sentinel warehouse: {e}")
        raise RuntimeError(f"Database error writing to whitespace_opportunities table: {e}") from e

    # Step 7: Dispatch completion webhook to Birdseye
    if trigger_webhook:
        if lgu_code:
            # Select the record BY CODE. Indexing [0] posted an arbitrary LGU's
            # record to the requested LGU's endpoint, which upserted the wrong row
            # while Birdseye marked the requested LGU COMPLETED - leaving it
            # permanently unscored and never re-queued.
            targeted = next((r for r in computed_records if r["lguCode"] == lgu_code), None)
            if targeted is None:
                raise ValueError(
                    f"No record computed for targeted LGU {lgu_code}. "
                    f"Computed {len(computed_records)} record(s) for: "
                    f"{[r['lguCode'] for r in computed_records]}"
                )
            score_url = f"{birdseye_url}/api/internal/lgus/{lgu_code}/score"
            try:
                print(f"[Whitespace Radar] Dispatching targeted score callback to: {score_url}")
                wh_resp = requests.post(
                    score_url,
                    json={"companyId": company_id, "record": targeted},
                    headers={
                        "Content-Type": "application/json",
                        "x-internal-secret": internal_secret
                    },
                    timeout=15.0
                )
                if wh_resp.status_code == 200:
                    print(f"[Whitespace Radar] Single-row score successfully acknowledged by Birdseye: {wh_resp.json()}")
                else:
                    raise RuntimeError(f"Birdseye score endpoint rejected payload with status {wh_resp.status_code}: {wh_resp.text}")
            except Exception as err:
                print(f"[Whitespace Radar] Targeted score dispatch error: {err}")
                raise err
        else:
            payload = build_sync_payload(company_id, computed_records)
            webhook_url = f"{birdseye_url}/api/internal/whitespace-radar/sync"
            try:
                print(f"[Whitespace Radar] Dispatching completion webhook to: {webhook_url}")
                wh_resp = requests.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-internal-secret": internal_secret
                    },
                    timeout=15.0
                )
                if wh_resp.status_code == 200:
                    print(f"[Whitespace Radar] Webhook successfully acknowledged by Birdseye: {wh_resp.json()}")
                else:
                    raise RuntimeError(f"Birdseye webhook rejected payload with status {wh_resp.status_code}: {wh_resp.text}")
            except Exception as err:
                print(f"[Whitespace Radar] Webhook dispatch error: {err}")
                raise err
    return computed_records

if __name__ == "__main__":
    run_whitespace_radar()
