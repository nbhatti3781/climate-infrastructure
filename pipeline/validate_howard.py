"""Validate inland-flood road exposure for Howard County, Maryland.

Only county-sized ArcGIS REST responses are requested. The dashboard receives
the compact checkpoint written by this script, never the raw GIS geometry.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

VENDOR = Path("/tmp/gina-python")
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from shapely.geometry import LineString, MultiLineString, Point, Polygon, shape
from shapely.ops import transform, unary_union
from pyproj import Transformer

from config import (
    ANALYSIS_SRID,
    FEMA_NFHL,
    FEMA_NRI_COUNTIES,
    HPMS_2024,
    TIGER_COUNTIES,
    TIGER_PRIMARY_ROADS,
)
from metrics import annualized_exposed_length, annualized_relative_exposure, min_max_normalize
from process_counties import save_checkpoint

GEOID = "24027"
METRES_PER_MILE = 1609.344


def arcgis(url: str, params: dict[str, object]) -> dict:
    body = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(f"ArcGIS error from {url}: {payload['error']}")
    return payload


def polygon_from_esri(geometry: dict):
    rings = [ring for ring in geometry.get("rings", []) if len(ring) >= 4]

    def signed_area(ring):
        return sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(ring, ring[1:])
        ) / 2

    # Esri JSON uses clockwise exterior rings and counter-clockwise holes.
    outer_rings = [ring for ring in rings if signed_area(ring) < 0]
    hole_rings = [ring for ring in rings if signed_area(ring) >= 0]
    if not outer_rings:
        return unary_union([Polygon(ring).buffer(0) for ring in rings])

    holes_by_outer: list[list[list[list[float]]]] = [[] for _ in outer_rings]
    outer_shells = [Polygon(ring) for ring in outer_rings]
    for hole in hole_rings:
        probe = Point(hole[0])
        for index, shell in enumerate(outer_shells):
            if shell.covers(probe):
                holes_by_outer[index].append(hole)
                break
    parts = [
        Polygon(shell, holes=holes_by_outer[index]).buffer(0)
        for index, shell in enumerate(outer_rings)
    ]
    return unary_union(parts)


def line_from_esri(geometry: dict):
    paths = [LineString(path) for path in geometry.get("paths", []) if len(path) >= 2]
    return paths[0] if len(paths) == 1 else MultiLineString(paths)


def query_all(url: str, params: dict[str, object], page_size: int = 2000) -> list[dict]:
    features: list[dict] = []
    offset = 0
    while True:
        page = arcgis(url, {**params, "resultOffset": offset, "resultRecordCount": page_size})
        batch = page.get("features", [])
        features.extend(batch)
        if len(batch) < page_size and not page.get("exceededTransferLimit"):
            break
        if not batch:
            break
        offset += len(batch)
    return features


def socrata_all(url: str, params: dict[str, object], page_size: int = 5000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({**params, "$limit": page_size, "$offset": offset})
        with urllib.request.urlopen(f"{url}?{query}", timeout=120) as response:
            batch = json.load(response)
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return rows


def main() -> dict:
    county_feature = arcgis(
        TIGER_COUNTIES,
        {
            "f": "json",
            "where": f"GEOID='{GEOID}'",
            "outFields": "GEOID,NAME",
            "returnGeometry": "true",
            "outSR": ANALYSIS_SRID,
        },
    )["features"][0]
    county = polygon_from_esri(county_feature["geometry"])
    minx, miny, maxx, maxy = county.bounds
    to_wgs84 = Transformer.from_crs(ANALYSIS_SRID, 4326, always_xy=True)
    to_analysis = Transformer.from_crs(4326, ANALYSIS_SRID, always_xy=True)
    west, south = to_wgs84.transform(minx, miny)
    east, north = to_wgs84.transform(maxx, maxy)
    wgs84_envelope = f"{west},{south},{east},{north}"

    roads = query_all(
        TIGER_PRIMARY_ROADS,
        {
            "f": "json",
            "where": "1=1",
            "geometry": wgs84_envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OBJECTID,NAME,MTFCC,RTTYP",
            "returnGeometry": "true",
            "outSR": ANALYSIS_SRID,
        },
        page_size=5000,
    )
    clipped_roads = []
    for feature in roads:
        clipped = line_from_esri(feature["geometry"]).intersection(county)
        if not clipped.is_empty:
            clipped_roads.append(clipped)
    road_network = unary_union(clipped_roads)

    flood_features = query_all(
        f"{FEMA_NFHL}/28/query",
        {
            "f": "json",
            "where": "SFHA_TF='T'",
            "geometry": wgs84_envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF",
            "returnGeometry": "true",
            "outSR": ANALYSIS_SRID,
        },
        page_size=25,
    )
    flood_footprint = unary_union(
        [polygon_from_esri(feature["geometry"]) for feature in flood_features]
    ).intersection(county)
    exposed_roads = road_network.intersection(flood_footprint)

    nri = arcgis(
        FEMA_NRI_COUNTIES,
        {
            "f": "json",
            "where": f"STCOFIPS='{GEOID}'",
            "outFields": "STCOFIPS,COUNTY,STATE,IFLD_AFREQ",
            "returnGeometry": "false",
        },
    )["features"][0]["attributes"]

    all_nri = query_all(
        FEMA_NRI_COUNTIES,
        {
            "f": "json",
            "where": "IFLD_AFREQ IS NOT NULL",
            "outFields": "STCOFIPS,IFLD_AFREQ",
            "returnGeometry": "false",
            "orderByFields": "STCOFIPS",
        },
    )
    frequencies = [float(feature["attributes"]["IFLD_AFREQ"]) for feature in all_nri]
    frequency_min, frequency_max = min(frequencies), max(frequencies)

    hpms_rows = socrata_all(
        HPMS_2024,
        {
            "$select": "aadt,county_id,stateid,f_system,sectionlength,line",
            "$where": "stateid=24 AND county_id=27 AND aadt IS NOT NULL AND f_system <= 4",
        },
    )
    weighted_traffic = 0.0
    hpms_exposed_length = 0.0
    primary_road_match = road_network.buffer(25)
    for row in hpms_rows:
        line_wgs84 = shape(row["line"])
        line_projected = transform(to_analysis.transform, line_wgs84)
        exposed_piece = line_projected.intersection(county).intersection(flood_footprint).intersection(primary_road_match)
        length = exposed_piece.length
        if length > 0:
            aadt = float(row["aadt"])
            weighted_traffic += aadt * length
            hpms_exposed_length += length
    consequence_raw_aadt = weighted_traffic / hpms_exposed_length if hpms_exposed_length else 0.0

    total_miles = road_network.length / METRES_PER_MILE
    exposed_miles = exposed_roads.length / METRES_PER_MILE
    frequency = float(nri["IFLD_AFREQ"])
    normalized_frequency = min_max_normalize(frequency, frequency_min, frequency_max)
    exposure_ratio = exposed_miles / total_miles
    aael_miles_per_year = annualized_exposed_length(frequency, exposed_miles)
    relative = annualized_relative_exposure(aael_miles_per_year, total_miles)

    result = {
        "geoid": GEOID,
        "county": "Howard County",
        "state": "Maryland",
        "hazard": "inland_flood",
        "status": "national_consequence_rank_pending",
        "analysis_date": date.today().isoformat(),
        "analysis_crs": f"EPSG:{ANALYSIS_SRID}",
        "road_scope": "Census TIGERweb Primary Roads (MTFCC S1100/S1200)",
        "hazard_footprint": "FEMA NFHL Special Flood Hazard Area (SFHA_TF='T')",
        "annualized_frequency": frequency,
        "frequency_min_national": frequency_min,
        "frequency_max_national": frequency_max,
        "normalized_frequency": normalized_frequency,
        "total_primary_road_miles": total_miles,
        "flood_exposed_primary_road_miles": exposed_miles,
        "transportation_exposure": exposure_ratio,
        "transportation_exposure_percent": exposure_ratio * 100,
        "transportation_consequence_raw_aadt": consequence_raw_aadt,
        "transportation_consequence_normalized": None,
        "transportation_stress": None,
        "annualized_exposed_road_miles_per_year": aael_miles_per_year,
        "annualized_relative_road_exposure": relative,
        "annualized_relative_road_exposure_percent": relative * 100,
        "feature_counts": {
            "primary_road_features_returned": len(roads),
            "sfha_features_returned": len(flood_features),
            "hpms_primary_road_features_returned": len(hpms_rows),
            "national_counties_in_frequency_normalization": len(frequencies),
        },
        "formulas": {
            "aael": "annualized_frequency × flood_exposed_primary_road_miles",
            "relative": "annualized_exposed_road_miles_per_year ÷ total_primary_road_miles",
        },
        "sources": {
            "county_and_roads": "U.S. Census Bureau TIGERweb",
            "flood_footprint": "FEMA National Flood Hazard Layer",
            "frequency": "FEMA National Risk Index Counties",
        },
        "interpretation": "Transportation exposure and traffic intensity indicators; not damage, closure, loss, or engineering risk.",
        "remaining_dependency": "National flood-exposed HPMS consequence values are required before percentile ranking and final Transportation Stress can be calculated.",
    }
    save_checkpoint(GEOID, result)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
