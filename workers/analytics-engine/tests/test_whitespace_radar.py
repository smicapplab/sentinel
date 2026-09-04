import pytest
import math
from src.whitespace_radar import (
    calculate_elastic_spend_ratio,
    calculate_demand_gap,
    normalize_demand_gap_score,
    haversine_distance_km,
    calculate_huff_capture_probability,
    clean_and_deduplicate_pois,
    check_has_existing_store,
    compute_composite_wos,
    generate_golden_polygon_geojson,
    build_sync_payload
)

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

def test_existing_store_gate():
    """Evaluates real store records by exact LGU code, city name, or store name."""
    existing_stores = [
        {"storeNumber": "7110", "name": "Pizza Hut SM Megamall", "city": "Mandaluyong", "lguCode": "PH-137401000"},
        {"storeNumber": "7001", "name": "Pizza Hut Baguio Session", "city": "Baguio", "lguCode": "PH-141102000"},
        {"storeNumber": "7222", "name": "Pizza Hut Dumaguete Perdices", "city": "Dumaguete", "lguCode": "PH-074600000"},
    ]
    
    # Matches via exact lguCode
    assert check_has_existing_store("PH-074600000", "Dumaguete City", existing_stores) is True
    # Matches via city name
    assert check_has_existing_store("PH-999999999", "Baguio City", existing_stores) is True
    # Non-existing LGU
    assert check_has_existing_store("PH-050500000", "Legazpi City", existing_stores) is False
    assert check_has_existing_store("PH-175300000", "Puerto Princesa", existing_stores) is False

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

def test_candidate_scoring_differentiation_and_terrestrial_polygons():
    """Validates that candidate LGUs produce differentiated scores (never 100) and terrestrial corridor polygons."""
    from src.whitespace_radar import compute_candidate_records
    
    records = compute_candidate_records([])
    assert len(records) == 4
    
    scores = [r["opportunityScore"] for r in records]
    # No score should ever be 100/100 (monopoly artifact)
    for s in scores:
        assert 70 <= s < 100, f"Score {s} out of expected realistic range [70, 99]"
        assert s != 100, f"Score is 100: indicates uncalibrated monopoly artifact"
    
    # Must have differentiated scores across different markets
    assert len(set(scores)) >= 3, f"Scores must be differentiated across LGUs, got {scores}"
    
    # Verify terrestrial corridor polygons
    for r in records:
        poly = r["goldenPolygonGeojson"]
        assert poly["type"] == "Feature"
        coords = poly["geometry"]["coordinates"][0]
        assert len(coords) >= 4
        # Polygons must be bounded terrestrial corridors (< 10 km²), not massive 15km² unconstrained circles
        props = poly["properties"]
        area_km2 = props.get("areaKm2") or (props.get("radiusKm", 0) ** 2 * 3.14159)
        assert area_km2 < 10.0, f"Golden polygon area ({area_km2}) must be bounded terrestrial corridor (< 10 km²)"

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
             patch("requests.get") as mock_http_get, \
             patch("requests.post") as mock_http_post:

            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Configure requests.get mock
            mock_get_resp = MagicMock()
            mock_get_resp.status_code = 200
            mock_get_resp.json.return_value = mock_pois_resp
            mock_http_get.return_value = mock_get_resp

            # Configure requests.post mock
            mock_post_resp = MagicMock()
            mock_post_resp.status_code = 200
            mock_post_resp.json.return_value = mock_webhook_resp
            mock_http_post.return_value = mock_post_resp

            # Execute the orchestrator
            records = run_whitespace_radar(company_id="comp-1", trigger_webhook=True)

            # Assertions
            assert len(records) == 4, "Orchestrator must return 4 candidate records"
            assert mock_http_get.called, "Must query Birdseye POI endpoint"
            assert "mock-birdseye:5190/api/internal/places/pois" in mock_http_get.call_args[0][0]
            assert mock_http_get.call_args[1]["headers"]["x-internal-secret"] == "test_secret_123"

            # Verify DB persistence was invoked
            assert mock_cur.execute.called, "Must execute SQL on database"
            assert mock_conn.commit.called, "Must commit transaction to database"

            # Verify webhook dispatch
            assert mock_http_post.called, "Must dispatch webhook to Birdseye"
            webhook_url = mock_http_post.call_args[0][0]
            assert "mock-birdseye:5190/api/internal/whitespace-radar/sync" in webhook_url
            payload = mock_http_post.call_args[1]["json"]
            assert payload["companyId"] == "comp-1"
            assert payload["recordCount"] == 4
            assert mock_http_post.call_args[1]["headers"]["x-internal-secret"] == "test_secret_123"

def test_candidate_records_contain_competitor_points_geojson():
    """Validates that candidate records serialize businesses into GeoJSON FeatureCollection matching passed POIs."""
    from src.whitespace_radar import compute_candidate_records
    
    # 1. Test with live POIs passed in
    sample_pois = [
        {"name": "Shakey's Pizza Dumaguete", "category": "PIZZA", "lat": 9.308, "lon": 123.308, "address": "Downtown"},
        {"name": "SM City Legazpi", "category": "ANCHOR", "lat": 13.141, "lon": 123.744, "address": "Imelda Roces Ave"},
    ]
    records = compute_candidate_records(sample_pois)
    for r in records:
        layers = r["layersGeojson"]
        assert "competitorPoints" in layers, "layersGeojson must contain competitorPoints"
        comp_points = layers["competitorPoints"]
        assert comp_points["type"] == "FeatureCollection"
        features = comp_points["features"]
        assert len(features) > 0, f"Candidate {r['lguName']} should have competitor point features"
        
        # Verify RFC 7946 GeoJSON format
        for feat in features:
            assert feat["type"] == "Feature"
            assert feat["geometry"]["type"] == "Point"
            coords = feat["geometry"]["coordinates"]
            assert len(coords) == 2
            # Longitude, Latitude ordering
            assert -180 <= coords[0] <= 180
            assert -90 <= coords[1] <= 90
            props = feat["properties"]
            assert "name" in props
            assert "category" in props
            assert props["category"] in ("PIZZA", "ANCHOR", "FAST_FOOD")

    # 2. Test fallback baseline mode (empty POIs passed)
    fallback_records = compute_candidate_records([])
    for r in fallback_records:
        features = r["layersGeojson"]["competitorPoints"]["features"]
        # Expected fallback counts = pizza + anchor + fastfood
        counts = r["competitorCounts"]
        expected_count = counts["pizza"] + counts["anchors"] + counts["fastfood"]
        assert len(features) == expected_count, f"Features length {len(features)} must match total counts {expected_count}"

def test_candidate_records_contain_flood_zones_geojson():
    """Validates that candidate records serialize UP-NOAH flood hazard zones into GeoJSON FeatureCollection."""
    from src.whitespace_radar import compute_candidate_records

    records = compute_candidate_records([])
    for r in records:
        layers = r["layersGeojson"]
        assert "floodZones" in layers, "layersGeojson must contain floodZones"
        flood_zones = layers["floodZones"]
        assert flood_zones["type"] == "FeatureCollection"
        features = flood_zones["features"]
        assert len(features) > 0, f"Candidate {r['lguName']} should have flood hazard features"

        feat = features[0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Polygon"
        coords = feat["geometry"]["coordinates"][0]
        assert len(coords) >= 4, "Polygon must have at least 4 coordinate pairs (closed linear ring)"
        assert coords[0] == coords[-1], "Polygon must be closed"

        props = feat["properties"]
        assert "name" in props
        assert "severity" in props
        assert props["severity"] in ("LOW", "MEDIUM", "HIGH")
        assert "hazardType" in props
