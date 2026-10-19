"""Offline checks; fixtures never enter assessment output directories."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from process_national_assessment import (Sources, Blocked, StorageBlocked,
                                         atomic_json, ranks, projected_county,
                                         flood_footprint, validate_result)
from shapely.geometry import box, LineString


class NationalAssessmentTests(unittest.TestCase):
    def test_average_ties_and_singleton(self):
        self.assertEqual(ranks({'a':10,'b':10,'c':30}),{'a':.25,'b':.25,'c':1})
        self.assertEqual(ranks({'a':10}),{})

    def test_atomic_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'county.json'
            atomic_json(path,{'status':'complete'})
            self.assertEqual(json.loads(path.read_text()),{'status':'complete'})
            self.assertEqual(list(path.parent.glob('*.tmp')),[])
            with self.assertRaises(ValueError):
                atomic_json(path,{'value':float('nan')})
            self.assertEqual(json.loads(path.read_text()),{'status':'complete'})

    def test_source_batch_cannot_silently_truncate(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Sources(directory,32)
            replies=[{'objectIdField':'OBJECTID'},{'objectIds':[1,2]},
                     {'features':[{'attributes':{'OBJECTID':1},'geometry':{'paths':[]}}]}]
            with patch.object(source,'get',side_effect=replies):
                with self.assertRaisesRegex(Blocked,'Incomplete source ID batch'):
                    source.arcgis('https://example.test/0/query',{'where':'1=1'})

    def test_missing_geometry_is_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Sources(directory,32)
            replies=[{'objectIdField':'OBJECTID'},{'objectIds':[1]},
                     {'features':[{'attributes':{'OBJECTID':1},'geometry':None}]}]
            with patch.object(source,'get',side_effect=replies):
                with self.assertRaisesRegex(Blocked,'Missing geometry'):
                    source.arcgis('https://example.test/0/query',{'where':'1=1'})

    def test_unmapped_flood_is_not_measured_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Sources(directory,32)
            with patch.object(source,'arcgis',return_value=[]):
                with self.assertRaisesRegex(Blocked,'unmapped'):
                    flood_footprint(source,box(0,0,2,2),box(0,0,2,2),
                                    type('Identity',(),{'transform':staticmethod(lambda x,y:(x,y))})(),
                                    LineString([(0,1),(2,1)]))

    def test_storage_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Sources(directory,32)
            with patch('process_national_assessment.shutil.disk_usage',return_value=type('Space',(),{'free':1024})()):
                with self.assertRaises(StorageBlocked):
                    source.capacity()

    def test_antimeridian_is_blocked(self):
        with self.assertRaisesRegex(Blocked,'Antimeridian'):
            projected_county({'rings':[[[-179,50],[179,50],[179,51],[-179,51],[-179,50]]]},'02016')

    def test_maryland_contracts_unchanged(self):
        from config import ROOT
        for hazard,subdir in [('flood','counties'),('wildfire','wildfire/counties')]:
            paths=[p for p in (ROOT/'data/processed'/subdir).glob('24*.json') if len(p.stem)==5 and p.stem.isdigit()]
            self.assertEqual(len(paths),24)
            for path in paths:
                validate_result(json.loads(path.read_text()),hazard)


if __name__=='__main__':
    unittest.main()
