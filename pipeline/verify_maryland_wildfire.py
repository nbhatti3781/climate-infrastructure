"""Verify the shipped Maryland wildfire outputs without accessing GIS services."""

import json
import math

from config import PROCESSED
from process_maryland_wildfire import CLASSES, MILE, OUT, complete, atomic_json
from process_maryland_flood import MARYLAND_COUNTIES


def main():
    expected = {geoid for geoid, _ in MARYLAND_COUNTIES}
    assert {
        path.stem for path in OUT.glob("*.json")
    } == expected, "Expected all 24 Maryland county equivalents"
    results = []
    for geoid in sorted(expected):
        path = OUT / f"{geoid}.json"
        assert complete(path), f"Incomplete checkpoint: {geoid}"
        result = json.loads(path.read_text())
        total = result["total_major_road_miles"]
        exposed = result["wildfire_exposed_major_road_miles"]
        classes = result["whp_class_major_road_miles"]
        assert set(classes) == set(CLASSES.values()), geoid
        assert all(math.isfinite(v) and v >= 0 for v in classes.values()), geoid
        assert 0 <= exposed <= total, geoid
        assert abs(sum(classes.values()) - total) < 1e-5, geoid
        assert abs(classes["high"] + classes["very_high"] - exposed) < 1e-6, geoid
        assert result["whp_nodata_major_road_miles"] <= 0.01 / MILE, geoid
        assert 0 <= result["normalized_frequency"] <= 1, geoid
        assert 0 <= result["annualized_frequency"] <= 1, geoid
        assert result["transportation_consequence_normalized"] is None, geoid
        assert result["transportation_stress"] == (
            0.0 if total > 0 and exposed == 0 else None
        ), geoid
        coverage = result["hpms_coverage_pct_of_exposed_length"]
        assert coverage is None or 0 <= coverage <= 100, geoid
        aadt = result["transportation_consequence_raw_aadt"]
        if not exposed:
            assert aadt is None and result["aadt_status"] == (
                "null_confirmed_zero_exposure" if total > 0 else "null_no_major_roads"
            ), geoid
        if aadt is not None:
            assert math.isfinite(aadt) and aadt >= 0 and coverage > 0, geoid
        if total:
            assert (
                abs(result["transportation_exposure"] - exposed / total) < 1e-10
            ), geoid
        results.append(result)
    howard = next(r for r in results if r["geoid"] == "24027")
    flood = json.loads((PROCESSED / "counties" / "24027.json").read_text())
    assert (
        abs(howard["total_major_road_miles"] - flood["total_major_road_miles"]) < 1e-6
    )
    assert howard["validation"]["passed"]
    report = {
        "passed": True,
        "county_count": len(results),
        "howard_validation": howard["validation"],
        "howard_road_total_matches_flood_baseline": True,
        "checks": [
            "all 24 Maryland county equivalents",
            "flat checkpoint schema",
            "seven-class length partition",
            "High/Very High selection",
            "NoData road coverage",
            "frequency and exposure ranges",
            "null national ranks; zero stress only for confirmed zero exposure with a road network",
            "traffic coverage and null semantics",
        ],
        "counties_with_high_very_high_exposure": [
            {
                "geoid": r["geoid"],
                "county": r["county"],
                "exposed_miles": r["wildfire_exposed_major_road_miles"],
                "hpms_coverage_percent": r["hpms_coverage_pct_of_exposed_length"],
                "aadt_status": r["aadt_status"],
            }
            for r in results
            if r["wildfire_exposed_major_road_miles"] > 0
        ],
    }
    atomic_json(PROCESSED / "maryland_wildfire_qa_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
