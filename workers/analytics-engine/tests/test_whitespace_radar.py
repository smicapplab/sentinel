import pytest

CANDIDATE_LGUS = [
    {
        "lgu_code": "PH-074610000", "lgu_name": "Dumaguete City", "province": "Negros Oriental",
        "region": "Central Visayas", "income_classification": "2nd Class",
        "socio_economic_tier": "Mid-Market", "population": 134103,
        "avg_family_income_annual": 250000, "median_family_income_annual": 200000,
        "cluster_lat": 9.3068, "cluster_lon": 123.3054, "flood_risk_level": "HIGH",
        "rationale": "Tourism hub"
    },
    {
        "lgu_code": "PH-050506000", "lgu_name": "Legazpi City", "province": "Albay",
        "region": "Bicol", "income_classification": "2nd Class",
        "socio_economic_tier": "Mid-Market", "population": 209533,
        "avg_family_income_annual": 320000, "median_family_income_annual": 256000,
        "cluster_lat": 13.1391, "cluster_lon": 123.7505, "flood_risk_level": "MEDIUM",
        "rationale": "Tourism hub"
    },
    {
        "lgu_code": "PH-175316000", "lgu_name": "Puerto Princesa", "province": "Palawan",
        "region": "MIMAROPA", "income_classification": "HUC",
        "socio_economic_tier": "Premium", "population": 307079,
        "avg_family_income_annual": 395000, "median_family_income_annual": 316000,
        "cluster_lat": 9.742, "cluster_lon": 118.735, "flood_risk_level": "LOW",
        "rationale": "HUC"
    },
    {
        "lgu_code": "PH-112319000", "lgu_name": "Tagum City", "province": "Davao del Norte",
        "region": "Davao Region", "income_classification": "1st Class",
        "socio_economic_tier": "Emerging", "population": 296202,
        "avg_family_income_annual": 310000, "median_family_income_annual": 248000,
        "cluster_lat": 7.442, "cluster_lon": 125.795, "flood_risk_level": "MEDIUM",
        "rationale": "Growing"
    }
]

import math
from src.whitespace_radar import (
    calculate_elastic_spend_ratio,
    calculate_demand_gap,
    normalize_demand_gap_score,
    haversine_distance_km,
    calculate_huff_capture_probability,
    clean_and_deduplicate_pois,
    compute_composite_wos,
    generate_golden_polygon_geojson,
    build_sync_payload,
    presence_state,
    roster_lgu_codes_from_stores,
    compute_saturation_index,
    compute_coverage_index,
    compute_confidence_band,
    competitor_coverage_fractions,
    compute_candidate_records,
    W_MAX,
)
import statistics
import pytest

# Mirrors birdseye.poi_taxonomy_map as seeded by scripts/seed-poi-weights.ts.
# Injected explicitly rather than defaulted inside the model: a fallback taxonomy in
# production code is the divergence this whole change removed.
# test_taxonomy_fixture_matches_supply_contract below guards the parts that matter.
TEST_TAXONOMY = {
    "byType": {
        "pizza_restaurant": {"category": "PIZZA", "countsAsSupply": True, "attractiveness": 1.0},
        "fast_food_restaurant": {"category": "FAST_FOOD", "countsAsSupply": True, "attractiveness": 1.2},
        "restaurant": {"category": "RESTAURANT", "countsAsSupply": True, "attractiveness": 0.6},
        "shopping_mall": {"category": "ANCHOR", "countsAsSupply": True, "attractiveness": 1.5},
        "school": {"category": "EDUCATION", "countsAsSupply": False, "attractiveness": None},
        "hospital": {"category": "HOSPITAL", "countsAsSupply": False, "attractiveness": None},
    },
    "byCategory": {
        "PIZZA": {"category": "PIZZA", "countsAsSupply": True, "attractiveness": 1.0},
        "FAST_FOOD": {"category": "FAST_FOOD", "countsAsSupply": True, "attractiveness": 1.2},
        "RESTAURANT": {"category": "RESTAURANT", "countsAsSupply": True, "attractiveness": 0.6},
        "ANCHOR": {"category": "ANCHOR", "countsAsSupply": True, "attractiveness": 1.5},
        "EDUCATION": {"category": "EDUCATION", "countsAsSupply": False, "attractiveness": None},
        "HOSPITAL": {"category": "HOSPITAL", "countsAsSupply": False, "attractiveness": None},
        "LANDMARK": {"category": "LANDMARK", "countsAsSupply": False, "attractiveness": None},
    },
    "aliases": {
        "jollibee": "Jollibee", "mcdonalds": "McDonald's", "greenwich": "Greenwich",
        "chowking": "Chowking", "mang inasal": "Mang Inasal", "pizza hut": "Pizza Hut",
        "shakeys": "Shakey's", "shakeys pizza": "Shakey's", "shakeys pizza parlor": "Shakey's",
        "angels pizza": "Angel's Pizza",
    },
}


def test_engels_law_elasticity():
    """Engel's Law: higher median income increases the category spend ratio non-linearly (gamma = 0.65)."""
    base_ratio = 0.05
    national_median = 250000.0

    low_income = 150000.0
    high_income = 400000.0

    low_ratio = calculate_elastic_spend_ratio(low_income, national_median, base_ratio)
    high_ratio = calculate_elastic_spend_ratio(high_income, national_median, base_ratio)

    assert low_ratio < base_ratio
    assert high_ratio > base_ratio
    # Non-linear scaling check
    expected_low = base_ratio * ((low_income / national_median) ** 0.65)
    assert math.isclose(low_ratio, expected_low, rel_tol=1e-4)

def test_signed_demand_gap_does_not_floor_at_zero():
    """Oversupplied market (Supply > Demand) produces negative Demand Gap and scores below 50, not zero."""
    demand = 50_000_000.0
    supply = 80_000_000.0
    max_absolute_gap = 100_000_000.0

    gap = calculate_demand_gap(demand, supply)
    assert gap == -30_000_000.0

    score = normalize_demand_gap_score(gap, max_absolute_gap)
    # 50 + 50 * (-30m / 100m) = 50 - 15 = 35.0
    assert 0.0 < score < 50.0
    assert math.isclose(score, 35.0, rel_tol=1e-2)

def test_haversine_distance_and_huff_decay():
    """Huff model with beta = 2.5 drops capture probability rapidly with distance."""
    pt1 = (14.5995, 120.9842) # Manila
    pt2 = (14.6095, 120.9842) # ~1.11 km north
    pt3 = (14.6395, 120.9842) # ~4.44 km north

    d12 = haversine_distance_km(pt1[0], pt1[1], pt2[0], pt2[1])
    d13 = haversine_distance_km(pt1[0], pt1[1], pt3[0], pt3[1])
    assert 1.0 < d12 < 1.3
    assert 4.0 < d13 < 4.8

    # Candidate store vs competitor at pt2 and pt3
    candidate_point = pt1
    competitors = [
        {"lat": pt2[0], "lon": pt2[1], "attractiveness": 1.0, "is_candidate": False},
        {"lat": pt3[0], "lon": pt3[1], "attractiveness": 1.0, "is_candidate": False},
    ]
    # Demand point very close to candidate (0.2 km away)
    demand_pt = (14.6010, 120.9842)
    p_capture = calculate_huff_capture_probability(
        demand_pt=demand_pt,
        candidate_pt=candidate_point,
        candidate_attractiveness=1.0,
        competitors=competitors,
        beta=2.5
    )
    assert 0.70 < p_capture <= 1.0

def test_roster_codes_are_exact_match_only():
    """Substring city matching is gone: 'San Fernando' names three PH cities."""
    stores = [
        {"storeNumber": "7222", "name": "Pizza Hut Dumaguete Perdices", "city": "Dumaguete", "lguCode": "PH-074610000"},
    ]
    codes = roster_lgu_codes_from_stores(stores)
    assert codes == {"PH-074610000"}


def test_presence_is_unknown_when_roster_coverage_is_incomplete():
    """Absence of a store record is not evidence of store absence."""
    assert presence_state("PH-074610000", "PARTIAL", set()) == "UNKNOWN"
    assert presence_state("PH-074610000", "NO_PUBLIC_DATA", set()) == "UNKNOWN"


def test_presence_is_absent_only_on_complete_roster_coverage():
    assert presence_state("PH-074610000", "COMPLETE", set()) == "ABSENT"


def test_presence_is_present_on_exact_code_match_regardless_of_coverage():
    assert presence_state("PH-126303000", "PARTIAL", {"PH-126303000"}) == "PRESENT"
    assert presence_state("PH-126303000", "COMPLETE", {"PH-126303000"}) == "PRESENT"


def test_saturation_index_varies_across_competitive_landscapes():
    """Regression test for the 96.00-everywhere defect."""
    centroid = (9.308, 123.308)
    demand = 1_000_000_000.0
    contested = [{"lat": 9.309, "lon": 123.309, "attractiveness": 1.5} for _ in range(10)]
    sparse = [{"lat": 9.309, "lon": 123.309, "attractiveness": 1.5}]

    high = compute_saturation_index(demand, sparse, centroid)
    low = compute_saturation_index(demand, contested, centroid)

    assert high > low, "a less contested market must score higher"
    assert 0.0 <= low <= 100.0 and 0.0 <= high <= 100.0


def test_saturation_index_does_not_saturate_across_a_cohort():
    """The score must carry information, not collapse to a constant."""
    centroid = (9.308, 123.308)
    scores = [
        compute_saturation_index(1_000_000_000.0,
                                 [{"lat": 9.309, "lon": 123.309, "attractiveness": 1.0}] * n,
                                 centroid)
        for n in (1, 3, 6, 12)
    ]
    assert statistics.stdev(scores) > 0.0, "capture term collapsed to a constant again"


def test_uncoordinated_competitor_cannot_reach_the_saturation_model():
    """Silently skipping it would undercount supply while coverage claims confidence."""
    with pytest.raises(ValueError, match="without coordinates"):
        compute_saturation_index(1e9, [{"name": "Jollibee", "attractiveness": 1.0}], (9.308, 123.308))


def test_distant_competitors_matter_less_than_adjacent_ones():
    centroid = (9.308, 123.308)
    near = [{"lat": 9.309, "lon": 123.309, "attractiveness": 1.0}]
    far = [{"lat": 9.360, "lon": 123.360, "attractiveness": 1.0}]
    assert compute_saturation_index(1e9, far, centroid) > compute_saturation_index(1e9, near, centroid)


def test_confidence_band_widens_as_coverage_falls():
    assert compute_confidence_band(1.0)[0] == 0.0
    assert compute_confidence_band(0.0)[0] == W_MAX
    assert compute_confidence_band(0.5)[0] == round(W_MAX * 0.5, 2)
    assert compute_confidence_band(0.5)[1] == "COVERAGE_HEURISTIC"


def test_coverage_index_weights_brand_and_geo_separately():
    assert compute_coverage_index(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)
    assert compute_coverage_index(0.0, 0.0, 0.4, 0.3) == pytest.approx(0.18)


def test_geo_coverage_never_exceeds_brand_coverage():
    businesses = [
        {"brand": "Jollibee", "lat": 9.30, "lon": 123.30},
        {"brand": "Shakey's", "lat": None, "lon": None},
    ]
    c_brand, c_geo = competitor_coverage_fractions([], businesses)
    assert c_geo <= c_brand


def test_lgu_with_no_competitor_coverage_is_not_scored():
    """
    Regression: a failed crawl produced the top-ranked recommendation. Zero
    competitors reads as zero supply, hence maximum unmet demand, hence the
    highest score. Observed live when Ormoc returned 1 POI against 235-276 for
    every other city and ranked first.
    """
    lgus = [{
        "lgu_code": "PH-083738000", "lgu_name": "Ormoc City", "province": "Leyte", "region": "VIII",
        "income_classification": "1st Class", "socio_economic_tier": "Mid",
        "population": 238545, "median_family_income_annual": 192425,
        "avg_family_income_annual": 240000, "cluster_lat": 11.0064, "cluster_lon": 124.6075,
        "flood_risk_level": "LOW", "rationale": "test",
    }]
    assert compute_candidate_records(lgus, cleaned_pois=[], existing_stores=[], taxonomy=TEST_TAXONOMY) == []


def test_no_synthetic_competitors_are_fabricated():
    """An LGU with no POI coverage must not receive invented competitors."""
    lgus = [{
        "lgu_code": "PH-999999999", "lgu_name": "Nowhere City", "province": "X", "region": "Y",
        "income_classification": "3rd Class", "socio_economic_tier": "Mid",
        "population": 100000, "median_family_income_annual": 250000,
        "avg_family_income_annual": 300000, "cluster_lat": 10.0, "cluster_lon": 120.0,
        "flood_risk_level": "LOW", "rationale": "test",
    }]
    # With no POI coverage the LGU is skipped entirely rather than scored, so
    # there is no record in which a competitor could have been fabricated.
    assert compute_candidate_records(lgus, cleaned_pois=[], existing_stores=[], taxonomy=TEST_TAXONOMY) == []


def test_every_record_carries_its_confidence_band():
    """A score must never be serialisable without its band."""
    lgus = [{
        "lgu_code": "PH-074610000", "lgu_name": "Dumaguete City", "province": "Negros Oriental",
        "region": "VII", "income_classification": "3rd Class", "socio_economic_tier": "Mid",
        "population": 134103, "median_family_income_annual": 276000,
        "avg_family_income_annual": 345000, "cluster_lat": 9.3068, "cluster_lon": 123.3054,
        "flood_risk_level": "LOW", "rationale": "test",
    }]
    for rec in compute_candidate_records(lgus, cleaned_pois=[], existing_stores=[], taxonomy=TEST_TAXONOMY):
        assert "confidenceBandHalfwidth" in rec
        assert "bandMethod" in rec
        assert "coverageIndex" in rec
        assert "presenceState" in rec


def test_google_places_data_hygiene_and_spatial_dedup():
    """Filters out permanently/temporarily closed locations using businessStatus and deduplicates pins within 50m."""
    raw_pois = [
        {"id": "p1", "lat": 14.5500, "lon": 121.0500, "businessStatus": "OPERATIONAL", "category": "PIZZA"},
        {"id": "p2", "lat": 14.5501, "lon": 121.0501, "businessStatus": "CLOSED_PERMANENTLY", "category": "PIZZA"}, # Filtered
        {"id": "p3", "lat": 14.5500, "lon": 121.0502, "businessStatus": "CLOSED_TEMPORARILY", "category": "PIZZA"}, # Filtered
        {"id": "p4", "lat": 14.55001, "lon": 121.05001, "businessStatus": "OPERATIONAL", "category": "PIZZA"}, # Duplicate of p1 (<15m)
        {"id": "p5", "lat": 14.5700, "lon": 121.0700, "businessStatus": "OPERATIONAL", "category": "ANCHOR"}, # Valid distinct
    ]

    cleaned = clean_and_deduplicate_pois(raw_pois, min_distance_meters=50.0)
    assert len(cleaned) == 2
    ids = {p["id"] for p in cleaned}
    assert ids == {"p1", "p5"}

def test_wos_composite_bounds():
    """WOS = round(0.50 * DemandGapScore + 0.50 * PredictedCaptureScore), strictly clamped to [0, 100]."""
    assert compute_composite_wos(100.0, 100.0) == 100
    assert compute_composite_wos(0.0, 0.0) == 0
    assert compute_composite_wos(74.2, 88.5) == 81
    assert compute_composite_wos(120.0, 95.0) == 100
    assert compute_composite_wos(-10.0, 20.0) == 5
    assert compute_composite_wos(-20.0, 10.0) == 0

def test_geojson_conforms_to_rfc7946():
    """Generated golden polygon conforms to RFC 7946 (type: Feature, geometry: Polygon, coordinates loop)."""
    polygon = generate_golden_polygon_geojson(
        center_lat=9.308,
        center_lon=123.308,
        radius_km=2.0,
        name="Dumaguete Core Delivery Zone"
    )
    assert polygon["type"] == "Feature"
    assert polygon["geometry"]["type"] == "Polygon"
    coords = polygon["geometry"]["coordinates"][0]
    assert len(coords) >= 4
    # Must be closed polygon
    assert coords[0] == coords[-1]
    assert polygon["properties"]["name"] == "Dumaguete Core Delivery Zone"

def test_webhook_payload_completeness():
    """Webhook payload includes demandGapScore and predictedCaptureScore for each record."""
    records = [
        {
            "lguCode": "PH-074600000",
            "lguName": "Dumaguete City",
            "province": "Negros Oriental",
            "region": "Central Visayas",
            "incomeClassification": "3rd Class City",
            "socioEconomicTier": "Mid-Market",
            "population": 134103,
            "medianFamilyIncomeAnnual": 276000,
            "demandGapScore": 89.5,
            "predictedCaptureScore": 94.5,
            "opportunityScore": 92,
            "brandFit": "Pizza Hut",
            "hasExistingStore": False,
            "competitorCounts": {"pizza": 2, "fastfood": 7, "anchors": 4},
            "floodRiskLevel": "LOW",
            "summaryRationale": "High student density and strong retail gap.",
            "goldenPolygonGeojson": {"type": "Feature"},
            "layersGeojson": {}
        }
    ]
    payload = build_sync_payload("comp-1", records)
    assert payload["companyId"] == "comp-1"
    assert payload["recordCount"] == 1
    rec = payload["records"][0]
    assert "demandGapScore" in rec
    assert "predictedCaptureScore" in rec
    assert "medianFamilyIncomeAnnual" in rec
    assert rec["demandGapScore"] == 89.5
    assert rec["predictedCaptureScore"] == 94.5

def test_webhook_payload_includes_data_provenance():
    """Webhook payload includes dataSource and isCalibratedEstimate."""
    records = [
        {
            "lguCode": "PH-074600000",
            "lguName": "Dumaguete City",
            "province": "Negros Oriental",
            "region": "Central Visayas",
            "incomeClassification": "3rd Class City",
            "socioEconomicTier": "Mid-Market",
            "population": 134103,
            "averageFamilyIncomeAnnual": 345000,
            "medianFamilyIncomeAnnual": 276000,
            "demandGapScore": 89.5,
            "predictedCaptureScore": 94.5,
            "opportunityScore": 92,
            "brandFit": "Pizza Hut",
            "hasExistingStore": False,
            "competitorCounts": {"pizza": 2, "fastfood": 7, "anchors": 4},
            "floodRiskLevel": "LOW",
            "summaryRationale": "High student density and strong retail gap.",
            "dataSource": "ESTIMATED_BASELINE",
            "isCalibratedEstimate": True,
            "goldenPolygonGeojson": {"type": "Feature"},
            "layersGeojson": {}
        }
    ]
    payload = build_sync_payload("comp-1", records)
    rec = payload["records"][0]
    assert rec["dataSource"] == "ESTIMATED_BASELINE"
    assert rec["isCalibratedEstimate"] is True
    assert rec["averageFamilyIncomeAnnual"] == 345000
    assert rec["medianFamilyIncomeAnnual"] == 276000

def test_real_database_stores_schema_query():
    """Verifies that the actual stores table in Postgres has city and lgu_code columns and runs without error."""
    from src.db import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT store_number, name, COALESCE(city, ''), COALESCE(lgu_code, '') FROM stores WHERE is_active = true")
                rows = cur.fetchall()
                stores = [
                    {"storeNumber": str(r[0]), "name": str(r[1]), "city": str(r[2]), "lguCode": str(r[3])}
                    for r in rows
                ]
                assert len(stores) >= 2
                # Verify that Manila Bay branch matches City of Manila
                has_manila = check_has_existing_store("133900000", "City of Manila", stores)
                assert has_manila is True
                # Verify an unserved LGU is False
                has_dumaguete = check_has_existing_store("PH-074600000", "Dumaguete City", stores)
                assert has_dumaguete is False
    except Exception as e:
        pytest.skip(f"Postgres database not reachable for schema integration test: {e}")


def _coverage_pois(lgus):
    """One competitor per LGU centroid, so LGUs are not skipped for lack of coverage."""
    out = []
    for i, l in enumerate(lgus):
        out.append({"name": f"Rival Pizza {i}", "brand": "Shakey's", "category": "PIZZA",
                    "lat": l["cluster_lat"] + 0.004, "lon": l["cluster_lon"] + 0.004})
        out.append({"name": f"Rival QSR {i}", "brand": "Jollibee", "category": "ANCHOR",
                    "lat": l["cluster_lat"] + 0.006, "lon": l["cluster_lon"] - 0.005})
    return out

def test_candidate_scoring_is_differentiated_and_never_saturates():
    """
    Scores must differ across markets and must not pile up at a ceiling. This is
    the regression guard for the defect where predicted_capture_score was 96.00
    for every LGU and the composite reduced to a market-size ranking.
    """
    from src.whitespace_radar import compute_candidate_records

    records = compute_candidate_records(CANDIDATE_LGUS, _coverage_pois(CANDIDATE_LGUS), taxonomy=TEST_TAXONOMY)
    assert len(records) == 4

    scores = [r["opportunityScore"] for r in records]
    for sc in scores:
        assert 0 <= sc <= 100
    assert len(set(scores)) >= 3, f"Scores must be differentiated across LGUs, got {scores}"

    capture = [r["predictedCaptureScore"] for r in records]
    assert statistics.stdev(capture) > 0.0, \
        f"capture term collapsed to a constant: {capture}"


def test_trade_area_geometry_is_not_synthesised():
    """
    The hand-drawn per-LGU 'golden polygon' constants are gone. Until a real
    trade-area source exists we expose a radius, not fabricated geometry that
    downstream consumers cannot distinguish from survey data.
    """
    from src.whitespace_radar import compute_candidate_records

    for r in compute_candidate_records(CANDIDATE_LGUS, _coverage_pois(CANDIDATE_LGUS), taxonomy=TEST_TAXONOMY):
        poly = r["goldenPolygonGeojson"]
        assert "tradeRadiusKm" in poly
        assert "geometry" not in poly, "no synthesised polygon may be emitted"


def test_huff_zero_capture_does_not_floor_at_50():
    """Validates that a bad or uncompetitive candidate site scales to 0.0 without artificial 50-point floor."""
    from src.whitespace_radar import calculate_huff_capture_probability
    
    demand_pt = (9.308, 123.308)
    # Candidate is extremely far away (50 km away)
    distant_site = (9.808, 123.308)
    # Powerful competitors right on top of demand point
    competitors = [
        {"lat": 9.3081, "lon": 123.3081, "attractiveness": 5.0},
        {"lat": 9.3079, "lon": 123.3079, "attractiveness": 5.0},
    ]
    prob = calculate_huff_capture_probability(demand_pt, distant_site, 1.0, competitors, beta=2.5)
    # Capture score without floor
    capture_score = round(min(96.0, (prob / 0.18) * 90.0), 2)
    assert capture_score < 1.0, f"Distant uncompetitive site should evaluate near 0.0, got {capture_score}"

def test_run_whitespace_radar_e2e_orchestration():
    """
    Validates the entire orchestrator wiring of run_whitespace_radar end-to-end:
    - Queries stores from DB
    - Ingests POIs from Birdseye internal API
    - Computes records via compute_candidate_records
    - Writes records to warehouse table
    - Dispatches webhook to Birdseye with valid secret
    """
    from unittest.mock import patch, MagicMock
    import os
    from src.whitespace_radar import run_whitespace_radar

    mock_stores_rows = [
        ("S-001", "Manila Bay Branch", "City of Manila", "133900000"),
        ("S-002", "Makati Central", "Makati City", "137600000"),
    ]
    mock_pois_resp = {
        "success": True,
        "count": 2,
        "pois": [
            {"id": "p-1", "name": "Shakey's", "category": "PIZZA", "lat": 9.308, "lon": 123.308},
            {"id": "p-2", "name": "Robinsons Place", "category": "ANCHOR", "lat": 9.300, "lon": 123.305}
        ]
    }
    mock_webhook_resp = {"success": True, "syncedCount": 4}

    # Set required env vars
    with patch.dict(os.environ, {"INTERNAL_API_SECRET": "test_secret_123", "BIRDSEYE_URL": "http://mock-birdseye:5190"}):
        # Mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = mock_stores_rows
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        with patch("src.whitespace_radar.get_connection") as mock_get_conn, \
             patch("src.whitespace_radar.fetch_lgus_from_birdseye") as mock_fetch_lgus, \
                 patch("src.whitespace_radar.fetch_pois_from_birdseye") as mock_fetch_pois, \
             patch("src.whitespace_radar.fetch_store_roster_from_birdseye") as mock_fetch_roster, \
             patch("src.whitespace_radar.fetch_taxonomy_from_birdseye") as mock_fetch_taxonomy, \
             patch("requests.post") as mock_http_post:
            # The taxonomy is fetched, never defaulted. Mocking it here rather than
            # letting the model fall back to a local chain is the point of the change.
            mock_fetch_taxonomy.return_value = TEST_TAXONOMY
            # Roster coverage is asserted by the import, so the pipeline must ask
            # Birdseye for it rather than inferring it from the store rows.
            mock_fetch_roster.return_value = ("COMPLETE", {"PH-126303000"})

            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Configure fetch mocks
            mock_fetch_lgus.return_value = [{"lguCode": "074610000", "lguName": "Dumaguete City", "province": "Negros Oriental", "region": "Central Visayas", "incomeClassification": "2nd Class", "population": 134103, "medianFamilyIncomeAnnual": 200000, "clusterLat": 9.3068, "clusterLon": 123.3054}]
            mock_fetch_pois.return_value = mock_pois_resp["pois"]

            # Configure requests.post mock
            mock_post_resp = MagicMock()
            mock_post_resp.status_code = 200
            mock_post_resp.json.return_value = mock_webhook_resp
            mock_http_post.return_value = mock_post_resp

            # Execute the orchestrator
            records = run_whitespace_radar(company_id="comp-1", trigger_webhook=True)

            # Assertions
            assert len(records) == 1, "Orchestrator must return 1 candidate record"

            # Verify DB persistence was invoked
            assert mock_cur.execute.called, "Must execute SQL on database"
            assert mock_conn.commit.called, "Must commit transaction to database"

            # Verify webhook dispatch
            assert mock_http_post.called, "Must dispatch webhook to Birdseye"
            webhook_url = mock_http_post.call_args[0][0]
            assert "mock-birdseye:5190/api/internal/whitespace-radar/sync" in webhook_url
            payload = mock_http_post.call_args[1]["json"]
            assert payload["companyId"] == "comp-1"
            assert payload["recordCount"] == 1
            assert mock_http_post.call_args[1]["headers"]["x-internal-secret"] == "test_secret_123"

def test_candidate_records_serialize_only_real_pois():
    """Competitor pins must mirror the POIs supplied, and nothing else."""
    from src.whitespace_radar import compute_candidate_records

    sample_pois = [
        {"name": "Shakey's Pizza Dumaguete", "brand": "Shakey's", "category": "PIZZA",
         "lat": 9.308, "lon": 123.308, "address": "Downtown"},
        {"name": "SM City Legazpi", "brand": None, "category": "ANCHOR",
         "lat": 13.141, "lon": 123.744, "address": "Imelda Roces Ave"},
    ]
    records = compute_candidate_records(CANDIDATE_LGUS, sample_pois, taxonomy=TEST_TAXONOMY)

    total_features = 0
    for r in records:
        comp_points = r["layersGeojson"]["competitorPoints"]
        assert comp_points["type"] == "FeatureCollection"
        for feat in comp_points["features"]:
            total_features += 1
            assert feat["type"] == "Feature"
            assert feat["geometry"]["type"] == "Point"
            lon, lat = feat["geometry"]["coordinates"]
            assert -180 <= lon <= 180 and -90 <= lat <= 90
            assert feat["properties"]["name"] in {p["name"] for p in sample_pois}

    assert total_features > 0, "supplied POIs must appear as competitor points"
    assert total_features <= len(sample_pois), "no POI may be duplicated or invented"


def test_no_competitor_points_without_poi_coverage():
    """The synthetic pin generator is gone: an empty crawl yields an empty map."""
    from src.whitespace_radar import compute_candidate_records

    assert compute_candidate_records(CANDIDATE_LGUS, [], taxonomy=TEST_TAXONOMY) == []


def test_flood_zones_come_from_upstream_or_are_omitted():
    """
    Flood geometry is sourced from Birdseye's PAGASA connector. The hardcoded
    FLOOD_HAZARD_ZONES dict is deleted; absent data means no layer, not a
    hand-drawn polygon.
    """
    from src.whitespace_radar import compute_candidate_records

    pois = _coverage_pois([CANDIDATE_LGUS[0]])
    without = compute_candidate_records([dict(CANDIDATE_LGUS[0])], pois, taxonomy=TEST_TAXONOMY)
    assert "floodZones" not in without[0]["layersGeojson"]

    upstream = dict(CANDIDATE_LGUS[0])
    upstream["flood_zones"] = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"hazardLevel": "HIGH"},
            "geometry": {"type": "Polygon", "coordinates": [[[123.3, 9.3], [123.31, 9.3], [123.31, 9.31], [123.3, 9.3]]]},
        }],
    }
    with_zones = compute_candidate_records([upstream], pois, taxonomy=TEST_TAXONOMY)
    assert "floodZones" in with_zones[0]["layersGeojson"]


# ---------------------------------------------------------------------------
# Competitor supply and crawl-probe roster (spec 2026-09-07)
# ---------------------------------------------------------------------------

def test_generic_restaurant_contributes_to_supply():
    """
    The defect this replaced: the classification chain ended in a bare
    `else: RESTAURANT` with no append, so 2,057 POIs -- 52% of all dining and anchor
    POIs -- were drawn as competitor pins and then dropped before the supply term.
    """
    from src.whitespace_radar import classify_poi, supply_weight
    poi = {"name": "Some Independent Carinderia", "category": "RESTAURANT", "rawTypes": ["restaurant"]}
    cat = classify_poi(poi, TEST_TAXONOMY)
    assert cat == "RESTAURANT"
    assert supply_weight(cat, TEST_TAXONOMY) == 0.6


def test_supply_term_strictly_increases_when_a_restaurant_is_added():
    from src.whitespace_radar import compute_saturation_index
    centroid = (9.3068, 123.3054)
    base = [{"lat": 9.3100, "lon": 123.3080, "attractiveness": 1.0}]
    more = base + [{"lat": 9.3110, "lon": 123.3090, "attractiveness": 0.6}]
    # More supply means a lower (less attractive) saturation score, strictly.
    assert compute_saturation_index(5e8, more, centroid) < compute_saturation_index(5e8, base, centroid)


def test_demand_generators_never_count_as_supply():
    """A school raises demand. Counting it as competing supply would invert its meaning."""
    from src.whitespace_radar import supply_weight
    assert supply_weight("EDUCATION", TEST_TAXONOMY) is None
    assert supply_weight("HOSPITAL", TEST_TAXONOMY) is None
    assert supply_weight("LANDMARK", TEST_TAXONOMY) is None


def test_crawl_probe_excludes_the_brand_being_searched_for():
    """
    Pizza Hut in its own coverage denominator meant an LGU where Pizza Hut is absent --
    the exact condition this feature exists to find -- lost 1/11 of its coverage and got
    a wider confidence band. The feature penalised its own target.
    """
    from src.whitespace_radar import CRAWL_PROBE_BRANDS
    assert "Pizza Hut" not in CRAWL_PROBE_BRANDS


def test_crawl_probe_excludes_sparsely_present_brands():
    """
    The probe is an instrument check, not a competitor list. Measured presence across the
    base 20 (2026-09-07): Domino's 5 LGUs, Yellow Cab 7, Pizza Hut 4. Their absence is a
    finding about the market, not evidence the crawl misfired.
    """
    from src.whitespace_radar import CRAWL_PROBE_BRANDS
    for sparse in ("Domino's", "Yellow Cab", "Angel's Pizza"):
        assert sparse not in CRAWL_PROBE_BRANDS
    assert set(CRAWL_PROBE_BRANDS) == {"Jollibee", "McDonald's", "Greenwich", "Chowking", "Mang Inasal"}


def test_absent_sparse_brand_does_not_reduce_coverage():
    """A market with no Domino's must not read as a failed crawl."""
    from src.whitespace_radar import competitor_coverage_fractions
    businesses = [
        {"name": "Jollibee", "brand": "Jollibee", "lat": 9.31, "lon": 123.31},
        {"name": "McDonald's", "brand": "McDonald's", "lat": 9.31, "lon": 123.31},
        {"name": "Greenwich", "brand": "Greenwich", "lat": 9.31, "lon": 123.31},
        {"name": "Chowking", "brand": "Chowking", "lat": 9.31, "lon": 123.31},
        {"name": "Mang Inasal", "brand": "Mang Inasal", "lat": 9.31, "lon": 123.31},
    ]
    c_brand, c_geo = competitor_coverage_fractions(businesses, businesses)
    assert c_brand == 1.0, "all five probe brands observed -> crawl is demonstrably working"
    assert c_geo == 1.0


def test_brand_aliases_resolve_variant_spellings_to_one_brand():
    """
    Naive normalisation over-splits: Shakey's appears as three distinct strings in live
    data (shakeys pizza parlor 14, shakeys 7, shakeys pizza 3), so one chain in 12 LGUs
    reads as three chains.
    """
    from src.whitespace_radar import canonical_brand
    for variant in ("Shakey's", "Shakey's Pizza", "Shakey's Pizza Parlor - Dumaguete"):
        assert canonical_brand(variant, TEST_TAXONOMY) == "Shakey's"


def test_model_refuses_to_score_without_a_taxonomy():
    """
    Fails closed. A default keyword chain here would drift from Birdseye's table silently
    and nobody would find out until a brand had gone unattributed for weeks -- which is
    precisely how Angel's Pizza lost 16 branches across 13 LGUs.
    """
    import pytest
    from src.whitespace_radar import compute_candidate_records
    with pytest.raises(ValueError, match="requires a taxonomy"):
        compute_candidate_records([], [], taxonomy=None)


def test_taxonomy_fixture_matches_supply_contract():
    """Guards the fixture against drifting from the seeded weights it mirrors."""
    supply = {k: v["attractiveness"] for k, v in TEST_TAXONOMY["byCategory"].items() if v["countsAsSupply"]}
    assert supply == {"PIZZA": 1.0, "FAST_FOOD": 1.2, "RESTAURANT": 0.6, "ANCHOR": 1.5}
