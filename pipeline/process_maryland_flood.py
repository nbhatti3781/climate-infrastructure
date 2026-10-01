"""Process inland-flood road exposure for all 24 Maryland county equivalents.

Methodology:
  Step 1 — Hazard Frequency: FEMA NRI IFLD_AFREQ, national min-max normalized.
  Step 2 — Road Exposure: FEMA NFHL SFHA (SFHA_TF='T') intersected with Census
            TIGERweb Primary Roads clipped to county boundary. Proportion =
            flood-exposed road length / total primary-road length.
  Step 3 — Traffic Consequence: length-weighted AADT on exposed road segments
            from FHWA HPMS 2024, filtered to f_system <= 4 (primary roads).
            Normalized consequence (percentile rank) remains pending until all
            counties have been processed nationally.
  Final   — Transportation Stress: pending national consequence ranking.

Run:
    cd pipeline/
    ../.venv/bin/python process_maryland_flood.py

    # Force re-run of all counties (ignores existing checkpoints):
    ../.venv/bin/python process_maryland_flood.py --force

    # Validate Howard County against existing baseline, then process remainder:
    ../.venv/bin/python process_maryland_flood.py --validate-howard

Outputs:
    data/processed/counties/<GEOID>.json          — per-county compact result
    data/processed/maryland_flood_report.json     — summary across all 24 counties

Resumable: counties with an existing complete checkpoint are skipped unless
--force is supplied.

Cache layout:
    data/cache/tiger/<GEOID>_county.json
    data/cache/tiger/<GEOID>_roads.json
    data/cache/nfhl/<GEOID>_sfha.json       (features as list)
    data/cache/hpms/<GEOID>_aadt.json
    data/cache/nri/national_afreq.json      (shared across all counties)
    data/cache/nri/<GEOID>_nri.json

NFHL pagination strategy:
    The NFHL MapServer/28 layer returns a 500 error when offset pagination is
    used beyond the 2000-record maxRecordCount for counties with many SFHA
    features. Instead, this script uses returnIdsOnly to retrieve all matching
    object IDs, then fetches features in batches of at most 200 IDs using an
    OBJECTID IN (...) filter. This is independent of the offset mechanism and
    does not hit the 500 error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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

# ---------------------------------------------------------------------------
# Path resolution — works whether invoked from repo root or pipeline/
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from config import (
    ANALYSIS_SRID,
    CACHE,
    FEMA_NFHL,
    FEMA_NRI_COUNTIES,
    HPMS_2024,
    TIGER_COUNTIES,
    TIGER_PRIMARY_ROADS,
    TIGER_SECONDARY_ROADS,
    PROCESSED,
)
from metrics import (
    annualized_exposed_length,
    annualized_relative_exposure,
    min_max_normalize,
)
from process_counties import checkpoint_path, is_complete, save_checkpoint

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
METRES_PER_MILE = 1609.344
TODAY = date.today().isoformat()

# Maryland county GEOIDs derived from Census TIGERweb STATE='24'.
# 23 counties + Baltimore city.  HPMS county_id = int(GEOID[2:]).
MARYLAND_COUNTIES: list[tuple[str, str]] = [
    ("24001", "Allegany County"),
    ("24003", "Anne Arundel County"),
    ("24005", "Baltimore County"),
    ("24009", "Calvert County"),
    ("24011", "Caroline County"),
    ("24013", "Carroll County"),
    ("24015", "Cecil County"),
    ("24017", "Charles County"),
    ("24019", "Dorchester County"),
    ("24021", "Frederick County"),
    ("24023", "Garrett County"),
    ("24025", "Harford County"),
    ("24027", "Howard County"),
    ("24029", "Kent County"),
    ("24031", "Montgomery County"),
    ("24033", "Prince George's County"),
    ("24035", "Queen Anne's County"),
    ("24037", "St. Mary's County"),
    ("24039", "Somerset County"),
    ("24041", "Talbot County"),
    ("24043", "Washington County"),
    ("24045", "Wicomico County"),
    ("24047", "Worcester County"),
    ("24510", "Baltimore city"),
]

# Howard County baseline from the Sept-23 validated run.  Used for
# cross-check when --validate-howard is supplied.
HOWARD_BASELINE = {
    "annualized_frequency": 2.5714285714285716,
    "frequency_min_national": 0.0,
    "frequency_max_national": 12.964285714285714,
    "normalized_frequency": 0.19834710743801656,
    "total_primary_road_miles": 108.7627750614346,
    "flood_exposed_primary_road_miles": 2.432870836162559,
    "transportation_exposure": 0.022368598399483217,
    "transportation_consequence_raw_aadt": 78851.59247681827,
    "feature_counts": {
        "primary_road_features_returned": 98,
        "sfha_features_returned": 273,
        "hpms_primary_road_features_returned": 2257,
        "national_counties_in_frequency_normalization": 3232,
    },
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_post(url: str, params: dict, timeout: int = 120) -> bytes:
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _retry(fn, attempts: int = 4, base_delay: float = 3.0):
    """Retry with exponential back-off; re-raise on final failure."""
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"    [retry {attempt+1}/{attempts-1}] {type(exc).__name__}: {exc}. Waiting {delay:.0f}s…")
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_get(path: Path) -> dict | list | None:
    """Load cached data; discard HTML error pages and ArcGIS error objects."""
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if raw.lstrip().startswith("<"):
        print(f"    [cache] Discarding HTML error page at {path.name}")
        path.unlink()
        return None
    data = json.loads(raw)
    if isinstance(data, dict) and "error" in data:
        print(f"    [cache] Discarding cached ArcGIS error at {path.name}")
        path.unlink()
        return None
    return data


def _cache_put(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# ArcGIS REST helpers
# ---------------------------------------------------------------------------

def _arcgis_post(url: str, params: dict) -> dict:
    """POST a single ArcGIS request; raise on ArcGIS error objects."""
    raw = _retry(lambda: _fetch_post(url, {**params, "f": "json"}))
    payload = json.loads(raw)
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(
            f"ArcGIS error from {url}: {payload['error']}"
        )
    return payload


def arcgis_all_offset(url: str, params: dict, page_size: int = 1000) -> list[dict]:
    """Retrieve all features via resultOffset pagination (for layers that support it)."""
    features: list[dict] = []
    offset = 0
    while True:
        page = _arcgis_post(
            url, {**params, "resultOffset": offset, "resultRecordCount": page_size}
        )
        batch = page.get("features", [])
        features.extend(batch)
        exceeded = page.get("exceededTransferLimit", False)
        if not batch or (len(batch) < page_size and not exceeded):
            break
        offset += len(batch)
    return features


def arcgis_all_by_ids(
    url: str,
    id_filter_params: dict,
    fetch_params: dict,
    batch_size: int = 200,
) -> list[dict]:
    """Retrieve all features by first fetching IDs, then batching by OBJECTID IN (...).

    Avoids the ArcGIS 500 error that occurs with offset pagination on large
    result sets in the NFHL service.

    Parameters
    ----------
    url:              Layer query endpoint.
    id_filter_params: Params for the returnIdsOnly call (where, geometry, etc.).
    fetch_params:     Params for feature fetches (outFields, returnGeometry, outSR).
    batch_size:       Max IDs per batch request.  200 is conservative.
    """
    # Step 1: get all matching IDs
    ids_payload = _arcgis_post(url, {**id_filter_params, "returnIdsOnly": "true"})
    if "error" in ids_payload:
        raise RuntimeError(f"returnIdsOnly failed: {ids_payload['error']}")
    all_ids: list[int] = ids_payload.get("objectIds") or []
    if not all_ids:
        return []

    print(f"    returnIdsOnly: {len(all_ids)} IDs in range "
          f"{min(all_ids)}–{max(all_ids)}")

    # Step 2: fetch features in batches with adaptive size on 500 errors
    features: list[dict] = []
    current_batch_size = batch_size
    i = 0
    while i < len(all_ids):
        batch_ids = all_ids[i : i + current_batch_size]
        id_list = ",".join(str(x) for x in batch_ids)
        batch_params = {**fetch_params, "where": f"OBJECTID IN ({id_list})"}
        try:
            page = _arcgis_post(url, batch_params)
            batch = page.get("features", [])
            features.extend(batch)
            print(f"    batch {i//batch_size + 1}: requested {len(batch_ids)}, "
                  f"received {len(batch)} (total so far: {len(features)})")
            i += current_batch_size
            # Reset batch size after successful fetch if it was reduced
            if current_batch_size < batch_size:
                current_batch_size = batch_size
        except RuntimeError as exc:
            if "500" in str(exc) and current_batch_size > 5:
                current_batch_size = max(5, current_batch_size // 2)
                print(f"    500 error — retrying with batch_size={current_batch_size}")
                time.sleep(2)
            else:
                raise

    if len(features) != len(all_ids):
        print(f"    WARNING: expected {len(all_ids)} features, retrieved {len(features)}")

    return features


def socrata_all(url: str, params: dict, page_size: int = 5000) -> list[dict]:
    """Paginate a Socrata dataset endpoint."""
    rows: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {**params, "$limit": page_size, "$offset": offset}
        )
        raw = _retry(lambda u=f"{url}?{query}": _fetch_get(u))
        batch = json.loads(raw)
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return rows


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def polygon_from_esri(geometry: dict):
    """Convert an Esri JSON polygon to a Shapely geometry."""
    rings = [ring for ring in geometry.get("rings", []) if len(ring) >= 4]

    def signed_area(ring):
        return sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(ring, ring[1:])
        ) / 2

    outer_rings = [r for r in rings if signed_area(r) < 0]
    hole_rings  = [r for r in rings if signed_area(r) >= 0]
    if not outer_rings:
        return unary_union([Polygon(r).buffer(0) for r in rings])

    holes_by_outer: list[list] = [[] for _ in outer_rings]
    outer_shells = [Polygon(r) for r in outer_rings]
    for hole in hole_rings:
        probe = Point(hole[0])
        for idx, shell in enumerate(outer_shells):
            if shell.covers(probe):
                holes_by_outer[idx].append(hole)
                break
    parts = [
        Polygon(shell, holes=holes_by_outer[idx]).buffer(0)
        for idx, shell in enumerate(outer_shells)
    ]
    return unary_union(parts)


def line_from_esri(geometry: dict):
    """Convert an Esri JSON polyline to a Shapely geometry."""
    paths = [LineString(p) for p in geometry.get("paths", []) if len(p) >= 2]
    if not paths:
        return LineString()
    return paths[0] if len(paths) == 1 else MultiLineString(paths)


# ---------------------------------------------------------------------------
# Shared national data
# ---------------------------------------------------------------------------

def load_national_nri() -> tuple[list[float], float, float]:
    """Return (all_frequencies, freq_min, freq_max) from FEMA NRI, cached."""
    cache_path = CACHE / "nri" / "national_afreq.json"
    cached = _cache_get(cache_path)
    if cached is not None:
        print("  [cache] National NRI IFLD_AFREQ loaded from disk")
        frequencies = cached
    else:
        print("  Fetching national FEMA NRI IFLD_AFREQ…")
        all_nri = arcgis_all_offset(
            FEMA_NRI_COUNTIES,
            {
                "where": "IFLD_AFREQ IS NOT NULL",
                "outFields": "STCOFIPS,IFLD_AFREQ",
                "returnGeometry": "false",
                "orderByFields": "STCOFIPS",
            },
        )
        frequencies = [float(f["attributes"]["IFLD_AFREQ"]) for f in all_nri]
        _cache_put(cache_path, frequencies)
        print(f"  Cached {len(frequencies)} national IFLD_AFREQ values")

    freq_min = min(frequencies)
    freq_max = max(frequencies)
    return frequencies, freq_min, freq_max


# ---------------------------------------------------------------------------
# Per-county processing
# ---------------------------------------------------------------------------

def process_county(
    geoid: str,
    county_name: str,
    freq_min: float,
    freq_max: float,
    national_count: int,
) -> dict:
    """Run inland-flood preprocessing for one county.  Returns the result dict."""
    county_id = int(geoid[2:])   # HPMS county_id (e.g. 27 for Howard, 510 for Baltimore city)

    # -----------------------------------------------------------------------
    # 1. County boundary
    # -----------------------------------------------------------------------
    tiger_cache = CACHE / "tiger" / f"{geoid}_county.json"
    county_payload = _cache_get(tiger_cache)
    if county_payload is not None:
        print(f"  [cache] County boundary")
    else:
        print(f"  Fetching county boundary…")
        county_payload = _arcgis_post(
            TIGER_COUNTIES,
            {
                "where": f"GEOID='{geoid}'",
                "outFields": "GEOID,NAME",
                "returnGeometry": "true",
                "outSR": ANALYSIS_SRID,
            },
        )
        _cache_put(tiger_cache, county_payload)

    if not county_payload.get("features"):
        raise RuntimeError(f"No county boundary returned for GEOID {geoid}")

    county = polygon_from_esri(county_payload["features"][0]["geometry"])
    if not county.is_valid:
        county = county.buffer(0)  # attempt repair

    # Bounding box in WGS-84 for spatial filter queries
    to_wgs84    = Transformer.from_crs(ANALYSIS_SRID, 4326, always_xy=True)
    to_analysis = Transformer.from_crs(4326, ANALYSIS_SRID, always_xy=True)
    minx, miny, maxx, maxy = county.bounds
    west, south = to_wgs84.transform(minx, miny)
    east, north = to_wgs84.transform(maxx, maxy)
    wgs84_envelope = f"{west},{south},{east},{north}"

    # -----------------------------------------------------------------------
    # 2. Major roads (S1100 + S1200) — bounding-box query each layer
    #    separately, then union before clipping to county polygon.
    #    Layer 2 = S1100 (limited-access highways).
    #    Layer 6 = S1200 (state routes / main arteries).
    #    The two layers have no MTFCC overlap so no deduplication is needed.
    # -----------------------------------------------------------------------
    road_params = {
        "where": "1=1",
        "geometry": wgs84_envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,NAME,MTFCC,RTTYP",
        "returnGeometry": "true",
        "outSR": ANALYSIS_SRID,
    }

    # S1100 cache (key unchanged — preserves any already-fetched data)
    s1100_cache = CACHE / "tiger" / f"{geoid}_roads.json"
    s1100_features = _cache_get(s1100_cache)
    if s1100_features is not None:
        print(f"  [cache] S1100 roads ({len(s1100_features)} features)")
    else:
        print(f"  Fetching S1100 roads (layer 2)…")
        s1100_features = arcgis_all_offset(
            TIGER_PRIMARY_ROADS, road_params, page_size=5000,
        )
        _cache_put(s1100_cache, s1100_features)

    # S1200 cache (separate key — avoids collision with S1100 cache)
    s1200_cache = CACHE / "tiger" / f"{geoid}_roads_s1200.json"
    s1200_features = _cache_get(s1200_cache)
    if s1200_features is not None:
        print(f"  [cache] S1200 roads ({len(s1200_features)} features)")
    else:
        print(f"  Fetching S1200 roads (layer 6)…")
        s1200_features = arcgis_all_offset(
            TIGER_SECONDARY_ROADS, road_params, page_size=5000,
        )
        _cache_put(s1200_cache, s1200_features)

    road_features = s1100_features + s1200_features
    s1100_count   = len(s1100_features)
    s1200_count   = len(s1200_features)

    # Clip each road to the county polygon — drops bbox-only intersections
    clipped_roads = []
    for feature in road_features:
        clipped = line_from_esri(feature["geometry"]).intersection(county)
        if not clipped.is_empty:
            clipped_roads.append(clipped)

    # -----------------------------------------------------------------------
    # Initialise all output variables (always-defined regardless of path taken)
    # -----------------------------------------------------------------------
    total_miles: float | None       = None
    exposed_miles: float | None     = None
    exposure_ratio: float | None    = None
    sfha_count: int                 = 0
    consequence_raw_aadt: float | None = None
    hpms_count: int                 = 0
    road_feature_count: int         = len(road_features)
    notes: list[str]                = []

    if not clipped_roads:
        status = "no_major_roads"
        notes.append(
            f"Bounding-box query returned {s1100_count} S1100 and {s1200_count} S1200 features; "
            "none intersect the county polygon after clipping. "
            "This county has no Census-classified major roads (S1100 or S1200)."
        )
    else:
        road_network = unary_union(clipped_roads)
        total_miles  = road_network.length / METRES_PER_MILE

        # -------------------------------------------------------------------
        # 3. SFHA flood footprint — fetch via returnIdsOnly + batched OBJECTID
        # -------------------------------------------------------------------
        nfhl_cache = CACHE / "nfhl" / f"{geoid}_sfha.json"
        flood_features = _cache_get(nfhl_cache)
        if flood_features is not None:
            print(f"  [cache] NFHL SFHA ({len(flood_features)} features)")
        else:
            print(f"  Fetching FEMA NFHL SFHA features (returnIdsOnly strategy)…")

            # Shared spatial filter params (no returnGeometry, no outFields)
            spatial_filter = {
                "where": "SFHA_TF='T'",
                "geometry": wgs84_envelope,
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
            }
            # Params for the actual feature batches
            feature_params = {
                "outFields": "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF",
                "returnGeometry": "true",
                "outSR": ANALYSIS_SRID,
            }

            # Batch size 20 is conservative but reliable.  The NFHL service
            # returns 500 for OBJECTID IN (...) queries when the ID range spans
            # large gaps (e.g. 26M–28M range), even with only 50 IDs.  20 IDs
            # per batch stays well within observed limits.
            flood_features = arcgis_all_by_ids(
                url=f"{FEMA_NFHL}/28/query",
                id_filter_params=spatial_filter,
                fetch_params=feature_params,
                batch_size=20,
            )
            _cache_put(nfhl_cache, flood_features)

        sfha_count = len(flood_features)

        if not flood_features:
            # No SFHA coverage in the bounding box — exposure is genuinely zero.
            exposed_miles  = 0.0
            exposure_ratio = 0.0
            consequence_raw_aadt = None  # not applicable; no exposed roads
            notes.append(
                "No SFHA features returned for county bounding box. "
                "Flood exposure is zero, not missing."
            )
            status = "national_consequence_rank_pending"
        else:
            flood_footprint = unary_union(
                [polygon_from_esri(f["geometry"]) for f in flood_features]
            ).intersection(county)

            exposed_geometry = road_network.intersection(flood_footprint)
            exposed_miles    = exposed_geometry.length / METRES_PER_MILE
            exposure_ratio   = exposed_miles / total_miles if total_miles > 0 else 0.0

            # ---------------------------------------------------------------
            # 4. HPMS AADT on exposed road segments
            # ---------------------------------------------------------------
            hpms_cache = CACHE / "hpms" / f"{geoid}_aadt.json"
            hpms_rows = _cache_get(hpms_cache)
            if hpms_rows is not None:
                print(f"  [cache] HPMS AADT ({len(hpms_rows)} rows)")
            else:
                print(f"  Fetching HPMS AADT (county_id={county_id})…")
                hpms_rows = socrata_all(
                    HPMS_2024,
                    {
                        "$select": "aadt,county_id,stateid,f_system,sectionlength,line",
                        "$where": (
                            f"stateid=24 AND county_id={county_id} "
                            f"AND aadt IS NOT NULL AND f_system <= 4"
                        ),
                    },
                )
                _cache_put(hpms_cache, hpms_rows)

            hpms_count = len(hpms_rows)

            # 25-metre buffer around the primary-road network to match HPMS
            # segments (which may be offset slightly from the TIGERweb geometry)
            primary_road_buffer = road_network.buffer(25)
            weighted_traffic  = 0.0
            hpms_exposed_m    = 0.0
            skipped_no_geom   = 0

            for row in hpms_rows:
                try:
                    line_wgs84 = shape(row["line"])
                except Exception:
                    skipped_no_geom += 1
                    continue
                line_proj    = transform(to_analysis.transform, line_wgs84)
                exposed_piece = (
                    line_proj
                    .intersection(county)
                    .intersection(flood_footprint)
                    .intersection(primary_road_buffer)
                )
                length = exposed_piece.length
                if length > 0:
                    aadt              = float(row["aadt"])
                    weighted_traffic  += aadt * length
                    hpms_exposed_m    += length

            if skipped_no_geom:
                notes.append(
                    f"{skipped_no_geom} of {hpms_count} HPMS rows had unparseable geometry and were skipped."
                )

            if hpms_exposed_m > 0:
                consequence_raw_aadt = weighted_traffic / hpms_exposed_m
            else:
                consequence_raw_aadt = None
                notes.append(
                    "No HPMS segments matched the exposed road network. "
                    "Raw AADT consequence is null (not zero)."
                )

            status = "national_consequence_rank_pending"

    # -----------------------------------------------------------------------
    # 5. NRI frequency for this county
    # -----------------------------------------------------------------------
    nri_cache = CACHE / "nri" / f"{geoid}_nri.json"
    nri_attrs = _cache_get(nri_cache)
    if nri_attrs is None:
        nri_payload = _arcgis_post(
            FEMA_NRI_COUNTIES,
            {
                "where": f"STCOFIPS='{geoid}'",
                "outFields": "STCOFIPS,COUNTY,STATE,IFLD_AFREQ",
                "returnGeometry": "false",
            },
        )
        if not nri_payload.get("features"):
            raise RuntimeError(f"No NRI record for GEOID {geoid}")
        nri_attrs = nri_payload["features"][0]["attributes"]
        _cache_put(nri_cache, nri_attrs)

    raw_freq = nri_attrs.get("IFLD_AFREQ")
    frequency = float(raw_freq) if raw_freq is not None else 0.0
    normalized_frequency = min_max_normalize(frequency, freq_min, freq_max)

    # -----------------------------------------------------------------------
    # 6. Derived metrics (only when roads exist)
    # -----------------------------------------------------------------------
    if total_miles is not None and exposed_miles is not None:
        aael     = annualized_exposed_length(frequency, exposed_miles)
        relative = annualized_relative_exposure(aael, total_miles) if total_miles > 0 else 0.0
    else:
        aael     = None
        relative = None

    # -----------------------------------------------------------------------
    # Assemble result
    # -----------------------------------------------------------------------
    result: dict = {
        "geoid":   geoid,
        "county":  county_name,
        "state":   "Maryland",
        "hazard":  "inland_flood",
        "status":  status,
        "analysis_date": TODAY,
        "analysis_crs":  f"EPSG:{ANALYSIS_SRID}",
        "road_scope":     "Census TIGERweb Major Roads (MTFCC S1100 + S1200 — MapServer layers 2 and 6)",
        "road_metric":    "major-road exposure",
        "hazard_footprint": "FEMA NFHL Special Flood Hazard Area (SFHA_TF='T')",
        # Frequency (Step 1)
        "annualized_frequency":    frequency,
        "frequency_min_national":  freq_min,
        "frequency_max_national":  freq_max,
        "normalized_frequency":    round(normalized_frequency, 10),
        # Exposure (Step 2) — null when county has no major roads
        "total_major_road_miles":          total_miles,
        "flood_exposed_major_road_miles":  exposed_miles,
        "transportation_exposure":           (
            round(exposure_ratio, 10) if exposure_ratio is not None else None
        ),
        "transportation_exposure_percent":   (
            round(exposure_ratio * 100, 6) if exposure_ratio is not None else None
        ),
        # Consequence (Step 3) — null until national ranking
        "transportation_consequence_raw_aadt":     consequence_raw_aadt,
        "transportation_consequence_normalized":   None,
        # Final stress — pending
        "transportation_stress": None,
        # Annualised metrics
        "annualized_exposed_road_miles_per_year": aael,
        "annualized_relative_road_exposure":       (
            round(relative, 10) if relative is not None else None
        ),
        "annualized_relative_road_exposure_percent": (
            round(relative * 100, 6) if relative is not None else None
        ),
        # Provenance
        "feature_counts": {
            "s1100_features_in_bbox":               s1100_count,
            "s1200_features_in_bbox":               s1200_count,
            "primary_road_features_in_bbox":        road_feature_count,
            "primary_road_features_clipped":        len(clipped_roads),
            "sfha_features_returned":               sfha_count,
            "hpms_primary_road_features_returned":  hpms_count,
            "national_counties_in_frequency_normalization": national_count,
        },
        "formulas": {
            "aael":     "annualized_frequency × flood_exposed_primary_road_miles",
            "relative": "annualized_exposed_road_miles_per_year ÷ total_primary_road_miles",
        },
        "sources": {
            "county_and_roads": "U.S. Census Bureau TIGERweb",
            "flood_footprint":  "FEMA National Flood Hazard Layer",
            "frequency":        "FEMA National Risk Index Counties",
            "hpms_traffic":     "FHWA Highway Performance Monitoring System 2024",
        },
        "interpretation": (
            "Transportation exposure and traffic intensity indicators; "
            "not damage, closure, loss, or engineering risk."
        ),
        "remaining_dependency": (
            "National flood-exposed HPMS consequence values are required before "
            "percentile ranking and final Transportation Stress can be calculated."
        ),
    }

    if notes:
        result["notes"] = notes

    return result


# ---------------------------------------------------------------------------
# Howard County validation
# ---------------------------------------------------------------------------

def validate_howard(freq_min: float, freq_max: float, national_count: int) -> bool:
    """Recompute Howard County using the new code and compare against the
    Sept-23 baseline.  Returns True if all fields match within tolerance."""

    print("=== Howard County Validation ===")
    print("Forcing recompute of GEOID 24027 (ignoring checkpoint)…")

    # Temporarily rename checkpoint so process_county can't load it
    ck = checkpoint_path("24027")
    backup = ck.with_suffix(".bak")
    if ck.exists():
        ck.rename(backup)
        print(f"  Existing checkpoint saved to {backup.name}")

    try:
        result = process_county("24027", "Howard County", freq_min, freq_max, national_count)
    except Exception as exc:
        import traceback
        print(f"  Howard recompute FAILED: {exc}")
        traceback.print_exc()
        if backup.exists():
            backup.rename(ck)
        return False

    # Restore backup; overwrite only on success
    if backup.exists():
        backup.unlink()

    save_checkpoint("24027", result)

    # Comparison
    b = HOWARD_BASELINE
    checks = [
        ("annualized_frequency",              b["annualized_frequency"],              1e-9),
        ("frequency_min_national",            b["frequency_min_national"],            1e-9),
        ("frequency_max_national",            b["frequency_max_national"],            1e-9),
        ("normalized_frequency",              b["normalized_frequency"],              1e-6),
        ("total_primary_road_miles",          b["total_primary_road_miles"],          1e-4),
        ("flood_exposed_primary_road_miles",  b["flood_exposed_primary_road_miles"],  1e-4),
        ("transportation_exposure",           b["transportation_exposure"],           1e-4),
        ("transportation_consequence_raw_aadt",
            b["transportation_consequence_raw_aadt"], 0.01),   # allow 1% tolerance for AADT
    ]
    count_checks = [
        ("sfha_features_returned",
            b["feature_counts"]["sfha_features_returned"]),
        ("hpms_primary_road_features_returned",
            b["feature_counts"]["hpms_primary_road_features_returned"]),
        ("national_counties_in_frequency_normalization",
            b["feature_counts"]["national_counties_in_frequency_normalization"]),
    ]

    all_pass = True
    print()
    print("  Field comparisons (baseline vs new run):")
    for field, expected, tol in checks:
        actual = result.get(field)
        if actual is None:
            flag = "FAIL (null)"
            all_pass = False
        else:
            rel_diff = abs(actual - expected) / max(abs(expected), 1e-12)
            if rel_diff <= tol:
                flag = f"PASS (rel diff {rel_diff:.2e})"
            else:
                flag = f"FAIL (expected {expected}, got {actual}, rel diff {rel_diff:.4f})"
                all_pass = False
        print(f"    {field:<45} {flag}")

    print()
    print("  Feature count comparisons:")
    fc = result.get("feature_counts", {})
    for field, expected in count_checks:
        actual = fc.get(field)
        flag = "PASS" if actual == expected else f"FAIL (expected {expected}, got {actual})"
        if actual != expected:
            all_pass = False
        print(f"    {field:<45} {flag}")

    print()
    if all_pass:
        print("  VALIDATION PASSED — new pipeline reproduces Howard County baseline.")
    else:
        print("  VALIDATION FAILED — investigate differences before proceeding.")

    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(force: bool = False, validate_howard_flag: bool = False) -> None:
    print("=== Maryland Inland Flood Pipeline ===")
    print(f"Analysis date: {TODAY}")
    print(f"Counties to process: {len(MARYLAND_COUNTIES)}")
    print()

    # Load national NRI data once (cached after first run)
    print("Step 0: Loading national FEMA NRI IFLD_AFREQ…")
    frequencies, freq_min, freq_max = load_national_nri()
    national_count = len(frequencies)
    print(f"  {national_count} counties, min={freq_min}, max={freq_max}")
    print()

    # Optional Howard validation before processing remaining counties
    if validate_howard_flag:
        ok = validate_howard(freq_min, freq_max, national_count)
        print()
        if not ok:
            print("Halting — fix validation failures before continuing.")
            sys.exit(1)

    results: list[dict]  = []
    errors:  list[dict]  = []

    for geoid, county_name in MARYLAND_COUNTIES:
        print(f"--- {geoid} {county_name} ---")

        # Resume: skip valid complete checkpoints unless --force
        if not force and is_complete(geoid):
            existing = json.loads(checkpoint_path(geoid).read_text(encoding="utf-8"))
            if (
                "normalized_frequency" in existing
                and "total_major_road_miles" in existing
                and existing.get("status") != "error"
            ):
                print(f"  [skip] Already processed ({existing.get('analysis_date', '?')})")
                results.append(existing)
                print()
                continue

        try:
            result = process_county(
                geoid=geoid,
                county_name=county_name,
                freq_min=freq_min,
                freq_max=freq_max,
                national_count=national_count,
            )
            save_checkpoint(geoid, result)
            results.append(result)

            tm   = result.get("total_major_road_miles")
            em   = result.get("flood_exposed_major_road_miles")
            ep   = result.get("transportation_exposure_percent")
            ra   = result.get("transportation_consequence_raw_aadt")
            nf   = result["normalized_frequency"]
            st   = result["status"]

            if tm is None:
                print(f"  ✓ no_major_roads  norm_freq={nf:.3f}  [{st}]")
            else:
                print(
                    f"  ✓ total={tm:.2f}mi  exposed={em:.2f}mi  "
                    f"exposure={ep:.2f}%  raw_aadt={ra if ra is not None else 'null'}  "
                    f"norm_freq={nf:.3f}  [{st}]"
                )

        except Exception as exc:
            import traceback
            print(f"  ✗ FAILED: {exc}")
            traceback.print_exc()
            error_record = {
                "geoid":         geoid,
                "county":        county_name,
                "status":        "error",
                "error":         str(exc),
                "analysis_date": TODAY,
            }
            errors.append(error_record)
            save_checkpoint(geoid, error_record)

        print()

    # -----------------------------------------------------------------------
    # Write consolidated report
    # -----------------------------------------------------------------------
    report = {
        "pipeline":            "maryland_inland_flood",
        "report_date":         TODAY,
        "counties_attempted":  len(MARYLAND_COUNTIES),
        "counties_succeeded":  len(results),
        "counties_failed":     len(errors),
        "national_nri_county_count":  national_count,
        "national_ifld_afreq_min":    freq_min,
        "national_ifld_afreq_max":    freq_max,
        "remaining_dependency": (
            "National flood-exposed HPMS AADT consequence ranking requires running "
            "this pipeline for all U.S. counties. Maryland HPMS data alone is not "
            "sufficient. consequence_normalized and transportation_stress remain null."
        ),
        "no_major_roads_note": (
            "Counties where total_major_road_miles is null have no Census-classified "
            "major roads (MTFCC S1100 + S1200, MapServer layers 2 and 6) intersecting "
            "the county polygon. This is a characteristic of the road network "
            "classification, not a data gap. Exposure fields for those counties are null, not zero."
        ),
        "errors": errors,
        "counties": [
            {
                "geoid":    r["geoid"],
                "county":   r["county"],
                "status":   r.get("status", "unknown"),
                "normalized_frequency":             r.get("normalized_frequency"),
                "total_major_road_miles":           r.get("total_major_road_miles"),
                "flood_exposed_major_road_miles":   r.get("flood_exposed_major_road_miles"),
                "transportation_exposure_percent":  r.get("transportation_exposure_percent"),
                "transportation_consequence_raw_aadt": r.get("transportation_consequence_raw_aadt"),
                "transportation_consequence_normalized": r.get("transportation_consequence_normalized"),
                "transportation_stress":            r.get("transportation_stress"),
                "notes":                            r.get("notes"),
            }
            for r in results
        ],
    }

    report_path = PROCESSED / "maryland_flood_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {report_path}")

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    print()
    print("=== Summary ===")
    print(f"{'GEOID':<8} {'County':<30} {'nfreq':>6} {'total_mi':>9} "
          f"{'exp_mi':>7} {'exp_%':>6} {'raw_aadt':>10} {'status'}")
    print("-" * 100)
    for r in results:
        if r.get("status") == "error":
            print(f"{r['geoid']:<8} {r['county']:<30}  ERROR")
        else:
            tm  = r.get("total_major_road_miles")
            em  = r.get("flood_exposed_major_road_miles")
            ep  = r.get("transportation_exposure_percent")
            ra  = r.get("transportation_consequence_raw_aadt")
            nf  = r.get("normalized_frequency", 0)
            st  = r.get("status","?")
            if tm is None:
                print(f"{r['geoid']:<8} {r['county']:<30} {nf:>6.3f} "
                      f"{'null':>9} {'null':>7} {'null':>6} {'null':>10}  {st}")
            else:
                ra_str = f"{ra:.0f}" if ra is not None else "null"
                print(f"{r['geoid']:<8} {r['county']:<30} {nf:>6.3f} "
                      f"{tm:>9.2f} {em:>7.2f} {ep:>6.2f} {ra_str:>10}  {st}")

    if errors:
        print()
        print(f"FAILED ({len(errors)}):")
        for e in errors:
            print(f"  {e['geoid']} {e['county']}: {e.get('error','')[:120]}")

    print()
    print(f"Succeeded: {len(results)}  Failed: {len(errors)}  "
          f"Total attempted: {len(MARYLAND_COUNTIES)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Maryland inland flood preprocessing")
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all counties, ignoring existing checkpoints",
    )
    parser.add_argument(
        "--validate-howard", action="store_true",
        help="Force-recompute Howard County and compare against baseline before continuing",
    )
    args = parser.parse_args()
    main(force=args.force, validate_howard_flag=args.validate_howard)
