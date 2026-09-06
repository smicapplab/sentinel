"""
Sensitivity of the whitespace ranking to AVG_STAY_DAYS.

Required by spec 2026-09-08 section 5 BEFORE any value is adopted. AVG_STAY_DAYS is an
asserted constant, so the ranking's dependence on it must be measured, not assumed small.
Read-only: computes and prints, persists nothing.
"""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(__file__))
from src.whitespace_radar import (
    fetch_lgus_from_birdseye, fetch_pois_from_birdseye, fetch_taxonomy_from_birdseye,
    fetch_store_roster_from_birdseye, clean_and_deduplicate_pois, compute_candidate_records,
)

company = "comp-1"
lgus = fetch_lgus_from_birdseye(company)
taxonomy = fetch_taxonomy_from_birdseye()
coverage, roster = fetch_store_roster_from_birdseye(company)
pois = []
for l in lgus:
    pois.extend(fetch_pois_from_birdseye(company, l["lguCode"]))
cleaned = clean_and_deduplicate_pois(pois)

cands = [{
    "lgu_code": l.get("lguCode"), "lgu_name": l.get("lguName",""), "province": l.get("province",""),
    "region": l.get("region",""), "income_classification": l.get("incomeClassification","Unknown"),
    "population": l.get("population",100000), "median_family_income_annual": l.get("medianFamilyIncomeAnnual",250000),
    "income_data_provenance": l.get("incomeDataProvenance","MODEL_ESTIMATE"),
    "cluster_lat": l.get("clusterLat",0.0), "cluster_lon": l.get("clusterLon",0.0),
    "socio_economic_tier":"Unknown", "avg_family_income_annual": int(l.get("medianFamilyIncomeAnnual",0)*1.25),
    "flood_risk_level":"UNASSESSED", "rationale":"",
    "air_arrivals": l.get("air_arrivals"), "sea_arrivals": l.get("sea_arrivals"),
} for l in lgus]

def corr(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    den = (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** 0.5
    return num/den if den else 0.0

print(f"{'days':>5} {'corr(pop x income)':>20} {'top 6 UNKNOWN by score':<64}")
orders = {}
for days in (0.0, 1.0, 2.0, 3.0, 5.0, 7.0):
    recs = compute_candidate_records(cands, cleaned, roster_coverage=coverage,
                                     roster_lgu_codes=roster, taxonomy=taxonomy, avg_stay_days=days)
    unk = sorted([r for r in recs if r["presenceState"]=="UNKNOWN"], key=lambda r:-r["opportunityScore"])
    c = corr([r["opportunityScore"] for r in recs],
             [r["population"]*r["medianFamilyIncomeAnnual"] for r in recs])
    orders[days] = [r["lguName"] for r in unk]
    print(f"{days:>5.0f} {c:>20.4f} {', '.join(f'{r[chr(34)+chr(34)] if False else r[chr(108)+chr(103)+chr(117)+chr(78)+chr(97)+chr(109)+chr(101)]}' for r in unk[:6])[:64]}")

base = orders[0.0]
print("\nrank changes vs 0 days (baseline, transient demand off):")
for d in (1.0,2.0,3.0,5.0,7.0):
    moved = [n for i,n in enumerate(orders[d]) if base.index(n)!=i]
    print(f"  {d:>3.0f} days: {len(moved)} of {len(base)} LGUs change position" + (f" -> {', '.join(moved[:5])}" if moved else ""))
