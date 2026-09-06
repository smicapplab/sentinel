"""
Rainfall-flood classification from DOST Project NOAH indicators.

These tests exist because the first rule shipped weighted flood_hazard_max_class_1km, and
that metric cannot discriminate: measured across the base 20 it is 3 for seventeen LGUs and
never below 2, since a Philippine city centre is nearly always within 1km of a river or
drainage channel. It labelled 17 of 20 HIGH and gave Tagbilaran (1.23% of trade area at
high hazard) the same verdict as Butuan (87.45%).
"""
import pytest
from src.whitespace_radar import (
    determine_flood_risk_level,
    FLOOD_AREA_HIGH_PCT, FLOOD_AREA_MEDIUM_PCT, FLOOD_AREA_MEDIUM_HIGH_PCT,
)


def ind(high=0.0, med=0.0, low=0.0, core=None):
    d = {"flood_hazard_high_pct_6km": high, "flood_hazard_medium_pct_6km": med,
         "flood_hazard_low_pct_6km": low}
    if core is not None:
        d["flood_hazard_max_class_1km"] = core
    return d


def test_missing_coverage_is_unassessed_never_low():
    """Absence of data is not evidence of safety."""
    assert determine_flood_risk_level({}) == "UNASSESSED"
    assert determine_flood_risk_level(None) == "UNASSESSED"
    assert determine_flood_risk_level({"flood_hazard_medium_pct_6km": 10.0}) == "UNASSESSED"


def test_separates_butuan_from_tagbilaran():
    """The regression that motivated the rewrite: 87.45% and 1.23% must not tie."""
    butuan = determine_flood_risk_level(ind(high=87.45, med=3.22, low=1.80, core=3))
    tagbilaran = determine_flood_risk_level(ind(high=1.23, med=3.97, low=5.04, core=3))
    assert butuan == "HIGH"
    assert tagbilaran == "LOW"
    assert butuan != tagbilaran


def test_core_class_no_longer_drives_the_verdict():
    """
    Identical area shares must classify identically regardless of centroid hazard class.
    Core class stays a reported indicator; it is not the classifier.
    """
    assert determine_flood_risk_level(ind(high=1.0, med=1.0, core=3)) == \
           determine_flood_risk_level(ind(high=1.0, med=1.0, core=0))


def test_high_band_is_driven_by_high_area_share():
    assert determine_flood_risk_level(ind(high=FLOOD_AREA_HIGH_PCT)) == "HIGH"
    assert determine_flood_risk_level(ind(high=FLOOD_AREA_HIGH_PCT - 0.01)) != "HIGH"


def test_medium_band_from_either_material_high_or_broad_medium():
    assert determine_flood_risk_level(ind(high=FLOOD_AREA_MEDIUM_HIGH_PCT)) == "MEDIUM"
    assert determine_flood_risk_level(ind(high=0.0, med=FLOOD_AREA_MEDIUM_PCT)) == "MEDIUM"
    # Roxas: modest high share, broad medium share.
    assert determine_flood_risk_level(ind(high=5.42, med=28.34, low=22.17)) == "MEDIUM"


def test_low_only_when_both_shares_are_small():
    assert determine_flood_risk_level(ind(high=0.57, med=3.07, low=5.85)) == "LOW"


def test_thresholds_are_ordered_and_declared():
    assert FLOOD_AREA_MEDIUM_HIGH_PCT < FLOOD_AREA_HIGH_PCT
    for c in (FLOOD_AREA_HIGH_PCT, FLOOD_AREA_MEDIUM_PCT, FLOOD_AREA_MEDIUM_HIGH_PCT):
        assert 0 < c <= 100


def test_scope_is_rainfall_only_and_says_so():
    """
    Storm surge is not ingested. Tacloban reads LOW on rainfall flood while being the city
    Haiyan destroyed by surge, so the docstring must warn any consumer about the scope.
    """
    doc = determine_flood_risk_level.__doc__ or ""
    assert "storm surge" in doc.lower()
    assert "rainfall" in doc.lower()
