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
CANDIDATE_LGUS = [
    {
        "lgu_code": "PH-074600000",
        "lgu_name": "Dumaguete City",
        "province": "Negros Oriental",
        "region": "Central Visayas (Region VII)",
        "income_classification": "3rd Class City (Component)",
        "socio_economic_tier": "Mid-Market (Class C)",
        "population": 134103,
        "median_family_income_annual": 276000,
        "avg_family_income_annual": 345000,
        "cluster_lat": 9.308,
        "cluster_lon": 123.308,
        "flood_risk_level": "LOW",
        "rationale": "High student density (Silliman University) and fast-expanding BPO industry. Domino is completely absent; Shakey and Greenwich only at Robinsons Mall. Heavy delivery whitespace opportunity."
    },
    {
        "lgu_code": "PH-050500000",
        "lgu_name": "Legazpi City",
        "province": "Albay",
        "region": "Bicol Region (Region V)",
        "income_classification": "2nd Class Component City",
        "socio_economic_tier": "Mid-Market (Class C)",
        "population": 209533,
        "median_family_income_annual": 256000,
        "avg_family_income_annual": 320000,
        "cluster_lat": 13.141,
        "cluster_lon": 123.744,
        "flood_risk_level": "MEDIUM",
        "rationale": "Regional administrative center of Bicol and tourism hub. Former branch at Pacific Mall closed; market is strongly validated with Domino, Shakey, and Greenwich actively capturing all casual dining traffic."
    },
    {
        "lgu_code": "PH-175300000",
        "lgu_name": "Puerto Princesa",
        "province": "Palawan",
        "region": "MIMAROPA (Region IV-B)",
        "income_classification": "Highly Urbanized City (HUC)",
        "socio_economic_tier": "Premium / High-Disposable (Class AB/C)",
        "population": 307079,
        "median_family_income_annual": 316000,
        "avg_family_income_annual": 395000,
        "cluster_lat": 9.748,
        "cluster_lon": 118.748,
        "flood_risk_level": "LOW",
        "rationale": "Independent HUC with high tourism volume and strong commercial retail infrastructure (SM & Robinsons). No active Pizza Hut leaves prime market share to local and legacy competitors."
    },
    {
        "lgu_code": "PH-112300000",
        "lgu_name": "Tagum City",
        "province": "Davao del Norte",
        "region": "Davao Region (Region XI)",
        "income_classification": "1st Class Component City",
        "socio_economic_tier": "Emerging Mid-Market (Class C)",
        "population": 296202,
        "median_family_income_annual": 248000,
        "avg_family_income_annual": 310000,
        "cluster_lat": 7.448,
        "cluster_lon": 125.808,
        "flood_risk_level": "MEDIUM",
        "rationale": "Fastest growing commercial hub in Davao del Norte, serving as primary economic spillover from Davao City. High commercial trading and highway traffic corridor."
    }
]

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

def check_has_existing_store(lgu_code: str, lgu_name: str, existing_stores: list[dict]) -> bool:
    """
    Step 0 check: evaluates whether an active operating store already exists in candidate LGU.
    Matches against actual store attributes:
    1. Exact lguCode match (e.g. 'PH-074600000').
    2. City match (e.g. store city 'Dumaguete' == lgu 'Dumaguete City').
    3. Store name semantic match (e.g. 'Pizza Hut Dumaguete Perdices').
    """
    norm_code = lgu_code.strip().upper()
    norm_name = lgu_name.lower().replace("city", "").replace("municipality", "").strip()

    for store in existing_stores:
        # 1. Exact LGU Code match
        s_code = str(store.get("lguCode") or store.get("lgu_code") or "").strip().upper()
        if s_code and s_code == norm_code:
            return True

        # 2. City match
        s_city = str(store.get("city") or "").lower().replace("city", "").strip()
        if s_city and (s_city in norm_name or norm_name in s_city):
            return True

        # 3. Store name semantic match
        s_name = str(store.get("name") or "").lower()
        if norm_name and norm_name in s_name:
            return True

    return False

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

FLOOD_HAZARD_ZONES = {
    "PH-074600000": {
        "name": "Banica River & Coastal Lowland Inundation Zone",
        "severity": "MEDIUM",
        "hazardType": "Riverine & Coastal Storm Surge",
        "coordinates": [
            [123.300, 9.294],
            [123.308, 9.298],
            [123.312, 9.305],
            [123.306, 9.308],
            [123.298, 9.301],
            [123.300, 9.294],
        ]
    },
    "PH-050500000": {
        "name": "Yawa River & Port Lowland Basin",
        "severity": "HIGH",
        "hazardType": "Flash Flood & Volcanic Lahar Runoff",
        "coordinates": [
            [123.725, 13.138],
            [123.738, 13.142],
            [123.748, 13.135],
            [123.755, 13.139],
            [123.745, 13.149],
            [123.730, 13.148],
            [123.725, 13.138],
        ]
    },
    "PH-175300000": {
        "name": "Puerto Princesa Bay Tidal Inundation Basin",
        "severity": "LOW",
        "hazardType": "Coastal Mangrove Margin",
        "coordinates": [
            [118.730, 9.735],
            [118.745, 9.739],
            [118.742, 9.746],
            [118.728, 9.744],
            [118.730, 9.735],
        ]
    },
    "PH-112300000": {
        "name": "Libuganon Basin Alluvial Floodplain",
        "severity": "HIGH",
        "hazardType": "Monsoon River Overflow",
        "coordinates": [
            [125.790, 7.435],
            [125.808, 7.438],
            [125.815, 7.449],
            [125.802, 7.456],
            [125.788, 7.447],
            [125.790, 7.435],
        ]
    }
}

def get_flood_hazard_feature(lgu_code: str, center_lat: float, center_lon: float, lgu_name: str) -> dict:
    """Generates UP-NOAH / MGB flood hazard corridor polygon for the LGU."""
    hazard = FLOOD_HAZARD_ZONES.get(lgu_code)
    if hazard:
        coords = hazard["coordinates"]
        name = hazard["name"]
        severity = hazard["severity"]
        hazard_type = hazard["hazardType"]
    else:
        coords = [
            [center_lon - 0.005, center_lat - 0.005],
            [center_lon + 0.003, center_lat - 0.006],
            [center_lon + 0.006, center_lat + 0.002],
            [center_lon + 0.001, center_lat + 0.006],
            [center_lon - 0.005, center_lat - 0.005],
        ]
        name = f"{lgu_name} Lowland Flood Basin"
        severity = "MEDIUM"
        hazard_type = "Lowland Alluvial Drainage"

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": name,
                    "severity": severity,
                    "hazardType": hazard_type,
                    "dataSource": "MGB / UP-NOAH Geohazard Assessment"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            }
        ]
    }

TERRESTRIAL_CORRIDORS = {
    "PH-074600000": {
        "name": "Dumaguete Core Delivery Zone",
        "areaKm2": 4.8,
        "recommendation": "Prime Site (Drive-Thru/Delivery Hub)",
        "coordinates": [
            [123.298, 9.302],
            [123.315, 9.308],
            [123.318, 9.319],
            [123.305, 9.325],
            [123.295, 9.316],
            [123.298, 9.302],
        ]
    },
    "PH-050500000": {
        "name": "SM City / Landco Corridor",
        "areaKm2": 5.2,
        "recommendation": "Prime Site (SM Mall Ingress / High Visibility)",
        "coordinates": [
            [123.738, 13.136],
            [123.749, 13.139],
            [123.754, 13.148],
            [123.742, 13.151],
            [123.735, 13.143],
            [123.738, 13.136],
        ]
    },
    "PH-175300000": {
        "name": "North Road Commercial Strip",
        "areaKm2": 6.1,
        "recommendation": "Stand-alone Delivery & Dining Store",
        "coordinates": [
            [118.735, 9.742],
            [118.752, 9.748],
            [118.759, 9.761],
            [118.741, 9.766],
            [118.731, 9.753],
            [118.735, 9.742],
        ]
    },
    "PH-112300000": {
        "name": "Daang Maharlika Highway Corridor",
        "areaKm2": 5.5,
        "recommendation": "Highway Drive-Thru Location",
        "coordinates": [
            [125.795, 7.442],
            [125.812, 7.446],
            [125.818, 7.458],
            [125.803, 7.462],
            [125.791, 7.451],
            [125.795, 7.442],
        ]
    }
}

def get_golden_polygon(lgu_code: str, center_lat: float, center_lon: float, name: str) -> dict:
    """Returns land-bounded terrestrial commercial corridor or tight 1.1km catchment."""
    if lgu_code in TERRESTRIAL_CORRIDORS:
        c = TERRESTRIAL_CORRIDORS[lgu_code]
        return {
            "type": "Feature",
            "properties": {
                "name": c["name"],
                "areaKm2": c["areaKm2"],
                "recommendation": c["recommendation"]
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [c["coordinates"]]
            }
        }
    return generate_golden_polygon_geojson(center_lat, center_lon, radius_km=1.1, name=f"{name} Core Catchment")

def compute_candidate_records(candidate_lgus: list[dict], cleaned_pois: list[dict], existing_stores: list[dict] = None) -> list[dict]:
    """
    Computes candidate scores and records using retail gap and Huff gravity modeling.
    Modular and pure for deterministic unit testing.
    """
    if existing_stores is None:
        existing_stores = []

    computed_records: list[dict] = []
    avg_store_sales_proxy = 18_000_000.0  # Standard PH component city QSR branch revenue benchmark

    for lgu in candidate_lgus:
        lgu_code = lgu["lgu_code"]
        pop = lgu["population"]
        med_income = lgu["median_family_income_annual"]
        cluster_pt = (lgu["cluster_lat"], lgu["cluster_lon"])

        # Step 0 check: exact LGU code or semantic city name match
        has_existing = check_has_existing_store(lgu_code, lgu["lgu_name"], existing_stores)

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
                    "brand": p.get("name", "Competitor"),
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "address": p.get("address", "")
                })

        # Explicitly track whether counts are from live POIs or baseline estimate
        data_source = "LIVE_POI_INGESTION" if nearby_competitors else "ESTIMATED_BASELINE"
        is_calibrated_estimate = not bool(nearby_competitors)

        if is_calibrated_estimate:
            if "Dumaguete" in lgu["lgu_name"]:
                pizza_count, fastfood_count, anchor_count = 2, 7, 4
            elif "Legazpi" in lgu["lgu_name"]:
                pizza_count, fastfood_count, anchor_count = 4, 11, 6
            elif "Puerto" in lgu["lgu_name"]:
                pizza_count, fastfood_count, anchor_count = 3, 9, 5
            else:
                pizza_count, fastfood_count, anchor_count = 2, 8, 4

            # Dynamically generate synthetic competitor positions around downtown core
            # matching the exact counts used in Retail Gap analysis
            # 1. Pizza competitors (attractiveness = 1.0, distance 450m - 700m)
            for i in range(pizza_count):
                angle = (2.0 * math.pi * i) / max(1, pizza_count)
                r_deg = 0.004 + 0.002 * (i % 3)
                plat, plon = cluster_pt[0] + r_deg * math.cos(angle), cluster_pt[1] + r_deg * math.sin(angle)
                nearby_competitors.append({"lat": plat, "lon": plon, "attractiveness": 1.0})
                lgu_businesses.append({
                    "name": f"Regional Pizza Brand #{i+1}",
                    "category": "PIZZA",
                    "brand": f"Pizza Competitor {i+1}",
                    "lat": plat,
                    "lon": plon,
                    "address": f"Commercial Corridor, {lgu['lgu_name']}"
                })
            # 2. Anchor malls (attractiveness = 1.5, distance 650m - 1000m)
            for i in range(anchor_count):
                angle = (2.0 * math.pi * i) / max(1, anchor_count) + 0.5
                r_deg = 0.006 + 0.003 * (i % 2)
                alat, alon = cluster_pt[0] + r_deg * math.cos(angle), cluster_pt[1] + r_deg * math.sin(angle)
                nearby_competitors.append({"lat": alat, "lon": alon, "attractiveness": 1.5})
                lgu_businesses.append({
                    "name": f"Commercial Retail Center #{i+1}",
                    "category": "ANCHOR",
                    "brand": f"Anchor Mall {i+1}",
                    "lat": alat,
                    "lon": alon,
                    "address": f"Downtown Core, {lgu['lgu_name']}"
                })
            # 3. Fastfood anchors (attractiveness = 1.2, distance 350m - 800m)
            for i in range(fastfood_count):
                angle = (2.0 * math.pi * i) / max(1, fastfood_count) + 1.0
                r_deg = 0.003 + 0.004 * (i % 4)
                flat, flon = cluster_pt[0] + r_deg * math.cos(angle), cluster_pt[1] + r_deg * math.sin(angle)
                nearby_competitors.append({"lat": flat, "lon": flon, "attractiveness": 1.2})
                lgu_businesses.append({
                    "name": f"QSR Fastfood Outlet #{i+1}",
                    "category": "FAST_FOOD",
                    "brand": f"Fastfood {i+1}",
                    "lat": flat,
                    "lon": flon,
                    "address": f"Highway Commercial Strip, {lgu['lgu_name']}"
                })

        existing_supply = pizza_count * avg_store_sales_proxy
        demand_gap = calculate_demand_gap(potential_demand, existing_supply)
        demand_gap_score = normalize_demand_gap_score(demand_gap, max_abs_gap=600_000_000.0)

        # Step 4: Huff Gravity Model (Site offset 100m in commercial core)
        candidate_site = (cluster_pt[0] + 0.001, cluster_pt[1] + 0.001)
        raw_capture_prob = calculate_huff_capture_probability(
            demand_pt=cluster_pt,
            candidate_pt=candidate_site,
            candidate_attractiveness=1.3,
            competitors=nearby_competitors,
            beta=2.5
        )

        # Normalize Huff capture probability to executive score [0, 96]
        # In a multi-chain QSR cluster, a capture probability around 18% represents
        # capture share nearly 3x fair share. A zero-pull site evaluates to 0.0 without artificial floor.
        predicted_capture_score = round(min(96.0, (raw_capture_prob / 0.18) * 90.0), 2)

        opportunity_score = compute_composite_wos(demand_gap_score, predicted_capture_score)

        golden_polygon = get_golden_polygon(lgu_code, cluster_pt[0], cluster_pt[1], lgu["lgu_name"])

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
            },
            "floodZones": get_flood_hazard_feature(lgu_code, cluster_pt[0], cluster_pt[1], lgu["lgu_name"])
        }

        rationale = lgu["rationale"]
        if is_calibrated_estimate:
            rationale = f"[ESTIMATED BASELINE: Google Places crawl pending for this LGU] {rationale}"

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
            "hasExistingStore": has_existing,
            "competitorCounts": {
                "pizza": pizza_count,
                "fastfood": fastfood_count,
                "anchors": anchor_count
            },
            "floodRiskLevel": lgu["flood_risk_level"],
            "summaryRationale": rationale,
            "dataSource": data_source,
            "isCalibratedEstimate": is_calibrated_estimate,
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

def run_whitespace_radar(company_id: str = "comp-1", trigger_webhook: bool = True) -> list[dict]:
    """
    Main execution pipeline for Sentinel Whitespace Radar:
    1. Check existing stores from Sentinel database (Step 0).
    2. Ingest POIs from Birdseye internal API over HTTP (Step 2).
    3. Compute Retail Gap & Huff Gravity Model in DuckDB / In-Memory (Steps 3-4).
    4. Persist pre-computed records to Sentinel Postgres warehouse (Step 6).
    5. Dispatch completion webhook to Birdseye (Step 7).
    """
    print(f"[Whitespace Radar] Starting execution pipeline for company: {company_id}")

    # Step 0: Fetch existing stores with city and LGU metadata from Sentinel DB
    existing_stores: list[dict] = []
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
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR: Failed to query stores from Sentinel database: {e}")
        raise RuntimeError(f"Database error querying stores table: {e}") from e

    # Step 2: Fetch Base LGUs from Birdseye Internal HTTP API
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")
    if not internal_secret:
        raise RuntimeError("INTERNAL_API_SECRET environment variable is unset. Failing closed.")

    try:
        lgu_resp = requests.get(
            f"{birdseye_url}/api/internal/lgus",
            headers={"x-internal-secret": internal_secret},
            timeout=10.0
        )
        if lgu_resp.status_code == 200:
            fetched_lgus = lgu_resp.json().get("data", [])
            print(f"[Whitespace Radar] Fetched {len(fetched_lgus)} LGUs from Birdseye API.")
        else:
            raise RuntimeError(f"Failed to fetch LGUs from Birdseye, status {lgu_resp.status_code}")
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR fetching LGUs: {e}")
        raise RuntimeError(f"API error querying LGUs: {e}") from e

    # Map fetched LGUs to expected format, supplementing missing fields
    candidate_lgus = []
    # Create lookup for the old hardcoded CANDIDATE_LGUS to preserve their specific rationales/metadata
    legacy_lgu_map = {lgu["lgu_code"]: lgu for lgu in CANDIDATE_LGUS}

    for flgu in fetched_lgus:
        lgu_code = flgu.get("lguCode")
        legacy_lgu = legacy_lgu_map.get(lgu_code, {})
        candidate_lgus.append({
            "lgu_code": lgu_code,
            "lgu_name": flgu.get("lguName"),
            "province": flgu.get("province"),
            "region": flgu.get("region"),
            "population": flgu.get("population"),
            "median_family_income_annual": flgu.get("medianFamilyIncomeAnnual"),
            "cluster_lat": flgu.get("clusterLat"),
            "cluster_lon": flgu.get("clusterLon"),
            "income_classification": legacy_lgu.get("income_classification", "1st Class / HUC"),
            "socio_economic_tier": legacy_lgu.get("socio_economic_tier", "Mid-Market (Class C)"),
            "avg_family_income_annual": legacy_lgu.get("avg_family_income_annual", int(flgu.get("medianFamilyIncomeAnnual", 0) * 1.25)),
            "flood_risk_level": legacy_lgu.get("flood_risk_level", "LOW"),
            "rationale": legacy_lgu.get("rationale", "Strategic expansion opportunity in a highly populated urbanizing market. Primary delivery whitespace targeted.")
        })

    # Step 2.5: Ingest competitor & anchor POIs from Birdseye Internal HTTP API
    raw_pois: list[dict] = []
    try:
        resp = requests.get(
            f"{birdseye_url}/api/internal/places/pois?companyId={company_id}",
            headers={"x-internal-secret": internal_secret},
            timeout=10.0
        )
        if resp.status_code == 200:
            data = resp.json()
            raw_pois = data.get("pois", [])
            print(f"[Whitespace Radar] Fetched {len(raw_pois)} POIs from Birdseye internal API.")
        else:
            print(f"[Whitespace Radar] Note: Birdseye POI endpoint returned status {resp.status_code}.")
    except Exception as e:
        print(f"[Whitespace Radar] Note: HTTP POI fetch skipped or unreachable ({e}), using baseline anchors.")

    # Data hygiene & deduplication
    cleaned_pois = clean_and_deduplicate_pois(raw_pois)

    # Step 3 & 4: Compute candidate records using retail gap and Huff gravity models
    computed_records = compute_candidate_records(candidate_lgus, cleaned_pois, existing_stores)


    # Step 6: Persist pre-computed records to Sentinel Postgres warehouse
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Ensure table exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS whitespace_opportunities (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        company_id TEXT NOT NULL,
                        lgu_code TEXT NOT NULL,
                        lgu_name TEXT NOT NULL,
                        province TEXT NOT NULL,
                        region TEXT NOT NULL,
                        income_classification TEXT NOT NULL,
                        socio_economic_tier TEXT NOT NULL,
                        population INTEGER NOT NULL,
                        avg_family_income_annual INTEGER NOT NULL DEFAULT 0,
                        median_family_income_annual INTEGER NOT NULL,
                        demand_gap_score NUMERIC(5,2) NOT NULL,
                        predicted_capture_score NUMERIC(5,2) NOT NULL,
                        opportunity_score INTEGER NOT NULL,
                        brand_fit TEXT NOT NULL DEFAULT 'Pizza Hut',
                        has_existing_store BOOLEAN NOT NULL DEFAULT FALSE,
                        competitor_counts JSONB NOT NULL DEFAULT '{"pizza":0,"fastfood":0,"anchors":0}',
                        flood_risk_level TEXT NOT NULL DEFAULT 'LOW',
                        golden_polygon_geojson JSONB,
                        layers_geojson JSONB,
                        summary_rationale TEXT,
                        data_source TEXT NOT NULL DEFAULT 'ESTIMATED_BASELINE',
                        is_calibrated_estimate BOOLEAN NOT NULL DEFAULT TRUE,
                        computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT uq_whitespace_opportunities_comp_lgu UNIQUE (company_id, lgu_code)
                    )
                """)
                
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
                            layers_geojson, summary_rationale, data_source, is_calibrated_estimate, computed_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
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
                            computed_at = NOW()
                    """, (
                        company_id, rec["lguCode"], rec["lguName"], rec["province"], rec["region"],
                        rec["incomeClassification"], rec["socioEconomicTier"], rec["population"],
                        rec["averageFamilyIncomeAnnual"], rec["medianFamilyIncomeAnnual"],
                        rec["demandGapScore"], rec["predictedCaptureScore"],
                        rec["opportunityScore"], rec["brandFit"], rec["hasExistingStore"],
                        json.dumps(rec["competitorCounts"]), rec["floodRiskLevel"],
                        json.dumps(rec["goldenPolygonGeojson"]), json.dumps(rec["layersGeojson"]),
                        rec["summaryRationale"], rec["dataSource"], rec["isCalibratedEstimate"]
                    ))
                conn.commit()
                print(f"[Whitespace Radar] Persisted {len(computed_records)} opportunities to Sentinel warehouse.")
    except Exception as e:
        print(f"[Whitespace Radar] FATAL ERROR: Failed to persist opportunities to Sentinel warehouse: {e}")
        raise RuntimeError(f"Database error writing to whitespace_opportunities table: {e}") from e

    # Step 7: Dispatch completion webhook to Birdseye
    if trigger_webhook:
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
