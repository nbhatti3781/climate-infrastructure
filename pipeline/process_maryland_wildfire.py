"""Maryland-only WHP road exposure; Howard is validated before other counties.

Run with Python 3.12+: process_maryland_wildfire.py [--howard-only] [--force].
No flood outputs or flood cache files are written by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import rasterio
from rasterio.features import shapes
from pyproj import Transformer
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

from config import (
    CACHE,
    PROCESSED,
    TIGER_COUNTIES,
    TIGER_PRIMARY_ROADS,
    TIGER_SECONDARY_ROADS,
    FEMA_NRI_COUNTIES,
    HPMS_2024,
)
from metrics import min_max_normalize, annualized_exposed_length
from process_maryland_flood import MARYLAND_COUNTIES, polygon_from_esri, line_from_esri

WHP = "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer"
METHOD = "whp2023-high-very-high-v2"
CLASSES = {
    1: "very_low",
    2: "low",
    3: "moderate",
    4: "high",
    5: "very_high",
    6: "non_burnable",
    7: "water",
}
MILE = 1609.344
OUT = PROCESSED / "wildfire" / "counties"
TO_ANALYSIS = Transformer.from_crs(3857, 26918, always_xy=True)


def line_parts(geometry) -> list:
    """Drop point-only boundary touches before unioning a road network."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [
        part for child in getattr(geometry, "geoms", []) for part in line_parts(child)
    ]


def apply_stress_policy(result: dict) -> dict:
    """Resolve confirmed zero exposure without inventing a traffic measurement."""
    result = dict(result)
    result["transportation_stress"] = None
    result["transportation_consequence_normalized"] = None
    if result["total_major_road_miles"] == 0:
        result["status"] = "no_major_roads"
        result["transportation_consequence_raw_aadt"] = None
        result["aadt_status"] = "null_no_major_roads"
        result["remaining_dependency"] = "Not applicable: no major-road network."
    elif (
        result["wildfire_exposed_major_road_miles"] == 0
        and result["transportation_exposure"] == 0
        and result["whp_nodata_major_road_miles"] <= 0.01 / MILE
    ):
        result["transportation_stress"] = 0.0
        result["transportation_consequence_raw_aadt"] = None
        result["aadt_status"] = "null_confirmed_zero_exposure"
        result["status"] = "zero_exposure_complete"
        result["remaining_dependency"] = (
            "None for this threshold: confirmed zero exposure gives zero stress; lower WHP classes may still have wildfire potential."
        )
    else:
        result["status"] = "national_consequence_rank_pending"
        result["remaining_dependency"] = (
            "National wildfire-exposed HPMS consequence values are required before percentile ranking and final Transportation Stress can be calculated."
        )
    return result


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def download(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Download failed")


def cached_json(source: str, county: str, url: str, params: dict):
    signature = hashlib.sha256(
        json.dumps([url, params], sort_keys=True).encode()
    ).hexdigest()
    path = CACHE / "wildfire" / source / "24" / county / f"{signature}.json"
    if path.exists():
        return json.loads(path.read_text())
    payload = json.loads(download(url + "?" + urllib.parse.urlencode(params)))
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(f"{url}: {payload['error']}")
    atomic_json(path, payload)
    return payload


def features(source: str, county: str, url: str, params: dict) -> list:
    result = []
    offset = 0
    while True:
        page = cached_json(
            source,
            county,
            url,
            {"f": "json", **params, "resultOffset": offset, "resultRecordCount": 1000},
        )
        batch = page.get("features", [])
        if not batch and page.get("exceededTransferLimit"):
            raise RuntimeError("Incomplete ArcGIS pagination")
        result.extend(batch)
        if not page.get("exceededTransferLimit") and len(batch) < 1000:
            return result
        offset += len(batch)


def national_frequency() -> dict:
    rows = features(
        "nri",
        "national",
        FEMA_NRI_COUNTIES,
        {
            "where": "WFIR_AFREQ IS NOT NULL AND WFIR_AFREQ >= 0",
            "outFields": "STCOFIPS,WFIR_AFREQ",
            "returnGeometry": "false",
            "orderByFields": "STCOFIPS",
        },
    )
    values = {
        r["attributes"]["STCOFIPS"]: float(r["attributes"]["WFIR_AFREQ"]) for r in rows
    }
    if len(values) < 3000 or any(
        not math.isfinite(v) or not 0 <= v <= 1 for v in values.values()
    ):
        raise ValueError("Incomplete or invalid national wildfire probability data")
    return values


def raster_path(geoid: str, county, metadata: dict) -> Path:
    # Align exports to the service's native grid; never export a rendered RGB map.
    bounds = transform(
        Transformer.from_crs(26918, 3857, always_xy=True).transform, county
    ).bounds
    origin_x, origin_y = metadata["extent"]["xmin"], metadata["extent"]["ymax"]
    pixel = metadata["pixelSizeX"]
    left = origin_x + math.floor((bounds[0] - origin_x) / pixel) * pixel
    right = origin_x + math.ceil((bounds[2] - origin_x) / pixel) * pixel
    bottom = origin_y + math.floor((bounds[1] - origin_y) / pixel) * pixel
    top = origin_y + math.ceil((bounds[3] - origin_y) / pixel) * pixel
    width, height = round((right - left) / pixel), round((top - bottom) / pixel)
    params = {
        "bbox": f"{left},{bottom},{right},{top}",
        "bboxSR": 3857,
        "imageSR": 3857,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "U8",
        "interpolation": "RSP_NearestNeighbor",
        "renderingRule": json.dumps({"rasterFunction": "None"}),
        "f": "image",
    }
    signature = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    path = CACHE / "wildfire" / "whp2023" / "24" / geoid / f"{signature}.tif"
    if not path.exists():
        raw = download(WHP + "/exportImage?" + urllib.parse.urlencode(params))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        with rasterio.open(tmp) as dataset:
            if (
                dataset.count != 1
                or dataset.crs.to_epsg() != 3857
                or dataset.width != width
                or dataset.height != height
            ):
                raise ValueError("Unexpected WHP export grid")
        tmp.replace(path)
        atomic_json(
            path.with_suffix(".request.json"),
            {"url": WHP + "/exportImage", "params": params},
        )
    return path


def footprints(path: Path, county) -> tuple[dict, dict]:
    with rasterio.open(path) as dataset:
        cells = dataset.read(1)
        valid = np.isin(cells, list(CLASSES))
        if not valid.any():
            raise ValueError("WHP raster has no valid hazard data")
        if not np.isin(cells, [*CLASSES, 255]).all():
            raise ValueError("Unknown WHP class codes")
        groups = {code: [] for code in CLASSES}
        for geometry, value in shapes(cells, mask=valid, transform=dataset.transform):
            # Preserve intermediate grid vertices when projecting long polygon
            # edges, so adjacent classes share the same projected boundaries.
            # Roads and HPMS are already county-clipped. Clipping class polygons
            # a second time can lose roads coincident with the county boundary.
            groups[int(value)].append(
                transform(TO_ANALYSIS.transform, shape(geometry).segmentize(27))
            )
        grids = {code: unary_union(parts) for code, parts in groups.items()}
        audit = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "export_crs": str(dataset.crs),
            "export_pixel_size": list(dataset.res),
            "source_resolution_metres": 270,
            "valid_cell_count": int(valid.sum()),
            "nodata_cell_count": int((~valid).sum()),
        }
        return grids, audit


def calculate(geoid: str, name: str, frequencies: dict, metadata: dict) -> dict:
    boundary = features(
        "tiger",
        geoid,
        TIGER_COUNTIES,
        {
            "where": f"GEOID='{geoid}'",
            "outFields": "GEOID,NAME",
            "returnGeometry": "true",
            "outSR": 26918,
        },
    )
    if len(boundary) != 1:
        raise ValueError("Expected one county boundary")
    county = polygon_from_esri(boundary[0]["geometry"])
    envelope = ",".join(str(v) for v in county.bounds)
    params = {
        "where": "1=1",
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 26918,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,MTFCC",
        "returnGeometry": "true",
        "outSR": 26918,
    }
    road_features = features("tiger", geoid, TIGER_PRIMARY_ROADS, params) + features(
        "tiger", geoid, TIGER_SECONDARY_ROADS, params
    )
    roads = unary_union(
        [
            part
            for f in road_features
            for part in line_parts(line_from_esri(f["geometry"]).intersection(county))
        ]
    )
    path = raster_path(geoid, county, metadata)
    grids, audit = footprints(path, county)
    class_lengths = {
        CLASSES[code]: roads.intersection(grid).length / MILE
        for code, grid in grids.items()
    }
    known = unary_union(list(grids.values()))
    unknown_length = roads.difference(known).length
    if unknown_length > 0.01:
        raise ValueError(
            f"WHP NoData intersects {unknown_length / MILE:.6f} road miles; refusing to count it as unexposed"
        )
    footprint = grids[4].union(grids[5])
    exposed = roads.intersection(footprint)
    total, exposed_miles = roads.length / MILE, exposed.length / MILE
    probability = frequencies[geoid]
    low, high = min(frequencies.values()), max(frequencies.values())
    aadt, weighted, matched = None, 0.0, 0.0
    hpms = []
    if exposed.length > 0:
        offset = 0
        while True:
            page = cached_json(
                "hpms",
                geoid,
                HPMS_2024,
                {
                    "$select": "aadt,line",
                    "$where": f"stateid=24 AND county_id={int(geoid[2:])} AND aadt IS NOT NULL AND f_system <= 4",
                    "$order": ":id",
                    "$limit": 5000,
                    "$offset": offset,
                },
            )
            if not isinstance(page, list):
                raise ValueError("Invalid HPMS response")
            hpms.extend(page)
            if len(page) < 5000:
                break
            offset += len(page)
        to_analysis = Transformer.from_crs(4326, 26918, always_xy=True)
        pieces = []
        road_buffer = roads.buffer(25)
        for row in hpms:
            traffic = float(row["aadt"])
            if not math.isfinite(traffic) or traffic < 0:
                raise ValueError("Invalid HPMS AADT")
            piece = (
                transform(to_analysis.transform, shape(row["line"]))
                .intersection(county)
                .intersection(footprint)
                .intersection(road_buffer)
            )
            weighted += traffic * piece.length
            matched += piece.length
            pieces.append(piece)
        aadt = weighted / matched if matched else None
        # Coverage on TIGER exposure, not summed HPMS lengths (which can overlap).
        covered = exposed.intersection(unary_union(pieces).buffer(25)).length
    else:
        covered = 0
    ratio = exposed.length / roads.length if roads.length else None
    result = {
        "geoid": geoid,
        "county": name,
        "state": "Maryland",
        "hazard": "wildfire",
        "hazard_label": "High / Very High wildfire hazard potential",
        "method_version": METHOD,
        "status": "national_consequence_rank_pending" if total else "no_major_roads",
        "analysis_date": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
        "analysis_crs": "EPSG:26918",
        "road_scope": "Census TIGERweb Major Roads (MTFCC S1100 + S1200 — MapServer layers 2 and 6)",
        "road_metric": "major-road exposure",
        "hazard_footprint": "USDA Forest Service WHP 2023 classified cells: High (4) and Very High (5)",
        "annualized_frequency": probability,
        "frequency_metric": "FEMA NRI WFIR_AFREQ: annual wildfire probability (not events/year)",
        "frequency_min_national": low,
        "frequency_max_national": high,
        "normalized_frequency": min_max_normalize(probability, low, high),
        "total_major_road_miles": total,
        "wildfire_exposed_major_road_miles": exposed_miles,
        "transportation_exposure": ratio,
        "transportation_exposure_percent": ratio * 100 if ratio is not None else None,
        "transportation_consequence_raw_aadt": aadt,
        "transportation_consequence_normalized": None,
        "transportation_stress": None,
        "hpms_coverage_pct_of_exposed_length": (
            100 * covered / exposed.length if exposed.length else None
        ),
        "aadt_status": (
            "available"
            if aadt is not None
            else (
                "null_confirmed_zero_exposure"
                if not exposed.length
                else "null_no_hpms_match"
            )
        ),
        "annualized_exposed_road_miles_per_year": annualized_exposed_length(
            probability, exposed_miles
        ),
        "annualized_relative_road_exposure": (
            probability * ratio if ratio is not None else None
        ),
        "whp_class_major_road_miles": class_lengths,
        "whp_nodata_major_road_miles": unknown_length / MILE,
        "raster_audit": audit,
        "feature_counts": {
            "major_road_features_in_bbox": len(road_features),
            "hpms_features_returned": len(hpms),
            "national_counties_in_frequency_normalization": len(frequencies),
        },
        "sources": {
            "wildfire_footprint": WHP,
            "frequency": FEMA_NRI_COUNTIES,
            "county_and_roads": "U.S. Census Bureau TIGERweb",
            "hpms_traffic": "FHWA Highway Performance Monitoring System 2024",
        },
        "formulas": {
            "stress": "normalized_frequency × transportation_exposure × national wildfire-exposed AADT percentile",
            "exposure": "High/Very High WHP-exposed major-road length ÷ total major-road length",
        },
        "interpretation": "Transportation exposure and traffic intensity indicators; not damage, closure, loss, or engineering risk.",
        "qa_notes": [
            "270-m source raster; nearest-neighbor export on aligned 270-unit EPSG:3857 service grid. Road lengths measured in EPSG:26918.",
            "WHP reflects landscape conditions at end of 2020; not a seasonal forecast.",
            "FEMA frequency and WHP footprint are separate hazard indicators; their product is a screening index, not a road-specific burn probability.",
        ],
        "remaining_dependency": "National wildfire-exposed HPMS consequence values are required before percentile ranking and final Transportation Stress can be calculated.",
    }
    result = apply_stress_policy(result)
    if geoid == "24027":
        result["validation"] = validate_howard(result, roads, path)
    return result


def validate_howard(result: dict, roads, path: Path) -> dict:
    # Independent cell-by-cell overlay checks polygonization and class selection.
    by_cell = 0.0
    with rasterio.open(path) as dataset:
        cells = dataset.read(1)
        for row, col in zip(*np.where(np.isin(cells, [4, 5]))):
            left, top = dataset.transform * (int(col), int(row))
            right, bottom = dataset.transform * (int(col) + 1, int(row) + 1)
            cell = transform(
                TO_ANALYSIS.transform, box(left, bottom, right, top).segmentize(27)
            )
            by_cell += roads.intersection(cell).length / MILE
    error = abs(by_cell - result["wildfire_exposed_major_road_miles"])
    partition_error = abs(
        sum(result["whp_class_major_road_miles"].values())
        - result["total_major_road_miles"]
    )
    if error > 1e-6 or partition_error > 1e-5:
        raise ValueError(
            f"Howard independent overlay validation failed: {error}, {partition_error}"
        )
    return {
        "passed": True,
        "independent_cell_overlay_miles": by_cell,
        "overlay_absolute_error_miles": error,
        "class_partition_error_miles": partition_error,
        "checks": [
            "independent High/Very High cell overlay",
            "seven-class road-length partition",
            "no road length in NoData",
            "national frequency range",
            "no substituted national consequence rank",
        ],
    }


def complete(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        value = json.loads(path.read_text())
        required = (
            "total_major_road_miles",
            "wildfire_exposed_major_road_miles",
            "normalized_frequency",
            "raster_audit",
            "whp_class_major_road_miles",
            "transportation_consequence_normalized",
            "transportation_stress",
        )
        return (
            all(key in value for key in required)
            and value["geoid"] == path.stem
            and value["method_version"] == METHOD
            and value["hazard"] == "wildfire"
            and value["status"]
            in {
                "national_consequence_rank_pending",
                "no_major_roads",
                "zero_exposure_complete",
            }
            and (
                value["geoid"] != "24027"
                or value.get("validation", {}).get("passed") is True
            )
        )
    except (ValueError, KeyError, TypeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--howard-only", action="store_true")
    parser.add_argument(
        "--county",
        action="append",
        choices=[g for g, _ in MARYLAND_COUNTIES],
        help="Process selected Maryland GEOIDs; Howard validation still runs first",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute results using cached source data",
    )
    args = parser.parse_args()
    report = {
        "method_version": METHOD,
        "scope": "Maryland's 23 counties and Baltimore city",
        "completed": [],
        "failed": {},
    }
    metadata = cached_json("whp2023", "metadata", WHP, {"f": "json"})
    if "2023" not in metadata.get("description", "") or metadata["pixelType"] != "U8":
        raise ValueError("Unexpected wildfire dataset version or pixel type")
    frequencies = national_frequency()
    ordered = [("24027", "Howard County")] + [
        (g, n)
        for g, n in MARYLAND_COUNTIES
        if g != "24027" and (not args.county or g in args.county)
    ]
    report["requested_counties"] = (
        [g for g, _ in ordered[:1] if args.howard_only]
        if args.howard_only
        else [g for g, _ in ordered]
    )
    for geoid, name in ordered[:1] if args.howard_only else ordered:
        path = OUT / f"{geoid}.json"
        try:
            if not args.force and complete(path):
                print(f"{geoid}: checkpoint reused", flush=True)
            else:
                print(f"{geoid}: processing {name}", flush=True)
                result = calculate(geoid, name, frequencies, metadata)
                atomic_json(path, result)
                print(
                    f"  {result['wildfire_exposed_major_road_miles']:.6f} / {result['total_major_road_miles']:.6f} exposed miles",
                    flush=True,
                )
            report["completed"].append(geoid)
        except Exception as exc:
            report["failed"][geoid] = str(exc)
            print(f"{geoid}: FAILED {exc}", flush=True)
            if geoid == "24027":
                atomic_json(PROCESSED / "maryland_wildfire_report.json", report)
                raise RuntimeError(
                    "Howard validation must succeed before processing other counties"
                ) from exc
        atomic_json(PROCESSED / "maryland_wildfire_report.json", report)
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
