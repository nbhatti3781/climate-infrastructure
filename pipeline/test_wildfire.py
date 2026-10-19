"""Offline geometry and checkpoint regression checks; fixtures never ship as data."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box
from shapely.ops import transform, unary_union

from process_maryland_wildfire import (
    CLASSES,
    MILE,
    METHOD,
    TO_ANALYSIS,
    complete,
    footprints,
    line_parts,
    validate_howard,
    apply_stress_policy,
)


class WildfireTests(unittest.TestCase):
    def test_zero_exposure_has_zero_stress_and_null_traffic(self):
        result = apply_stress_policy(
            {
                "total_major_road_miles": 10,
                "wildfire_exposed_major_road_miles": 0,
                "transportation_exposure": 0,
                "whp_nodata_major_road_miles": 0,
                "transportation_consequence_raw_aadt": 0.0,
            }
        )
        self.assertEqual(result["transportation_stress"], 0)
        self.assertIsNone(result["transportation_consequence_raw_aadt"])
        self.assertIsNone(result["transportation_consequence_normalized"])
        self.assertEqual(result["status"], "zero_exposure_complete")

    def test_exposed_roads_without_traffic_do_not_get_zero_stress(self):
        result = apply_stress_policy(
            {
                "total_major_road_miles": 10,
                "wildfire_exposed_major_road_miles": 1,
                "transportation_exposure": 0.1,
                "whp_nodata_major_road_miles": 0,
                "transportation_consequence_raw_aadt": None,
            }
        )
        self.assertIsNone(result["transportation_stress"])
        self.assertIsNone(result["transportation_consequence_raw_aadt"])

    def test_no_road_network_remains_not_applicable(self):
        result = apply_stress_policy(
            {
                "total_major_road_miles": 0,
                "wildfire_exposed_major_road_miles": 0,
                "transportation_exposure": None,
                "whp_nodata_major_road_miles": 0,
            }
        )
        self.assertIsNone(result["transportation_stress"])
        self.assertEqual(result["status"], "no_major_roads")

    def raster(self, directory, cells):
        path = Path(directory) / "classes.tif"
        cells = np.array(cells, dtype="uint8")
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=cells.shape[0],
            width=cells.shape[1],
            count=1,
            dtype="uint8",
            crs="EPSG:3857",
            transform=from_origin(-8580000, 4770000, 270, 270),
            nodata=255,
        ) as dataset:
            dataset.write(cells, 1)
        return path

    def test_class_overlay_includes_only_high_and_very_high(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.raster(directory, [[1, 2, 3, 4, 5, 6, 7]])
            road = transform(
                TO_ANALYSIS.transform,
                LineString([(-8580000, 4769865), (-8578110, 4769865)]).segmentize(27),
            )
            grids, audit = footprints(path, box(0, 0, 1, 1))
            lengths = {
                CLASSES[k]: road.intersection(v).length / MILE for k, v in grids.items()
            }
            result = {
                "wildfire_exposed_major_road_miles": road.intersection(
                    grids[4].union(grids[5])
                ).length
                / MILE,
                "whp_class_major_road_miles": lengths,
                "total_major_road_miles": road.length / MILE,
            }
            self.assertGreater(result["wildfire_exposed_major_road_miles"], 0)
            self.assertLess(
                result["wildfire_exposed_major_road_miles"],
                result["total_major_road_miles"],
            )
            self.assertEqual(audit["nodata_cell_count"], 0)
            self.assertTrue(validate_howard(result, road, path)["passed"])

    def test_missing_and_unknown_raster_values_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            for cells in ([[255]], [[1, 99]]):
                with self.assertRaises(ValueError):
                    footprints(self.raster(directory, cells), box(0, 0, 1, 1))

    def test_point_only_road_touches_are_removed(self):
        geometry = unary_union([LineString([(0, 0), (1, 0)]), box(2, 2, 3, 3).centroid])
        self.assertEqual(len(line_parts(geometry)), 1)

    def test_flood_and_partial_checkpoints_never_skip_wildfire(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "24027.json"
            for value in (
                {"hazard": "inland_flood"},
                {
                    "geoid": "24027",
                    "hazard": "wildfire",
                    "method_version": METHOD,
                    "status": "national_consequence_rank_pending",
                    "validation": {"passed": True},
                },
            ):
                path.write_text(json.dumps(value))
                self.assertFalse(complete(path))
            path.write_text("{invalid")
            self.assertFalse(complete(path))


if __name__ == "__main__":
    unittest.main()
