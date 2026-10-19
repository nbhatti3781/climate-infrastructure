"""Offline annual-stage tests; fixtures never enter assessment data directories."""
import unittest
from unittest.mock import patch
import io
import zipfile
import tempfile
from pathlib import Path
from shapely.geometry import LineString, box
from download_historical_inputs import make_plan, verify_asset, acquire
from process_historical_exposure import measure, verify_review
from audit_historical_sources import traffic_audit


class HistoryTests(unittest.TestCase):
    def test_completed_input_is_reused_only_when_its_hash_matches(self):
        asset={'id':'roads-10-2021','state':'10','observation_year':2021,'kind':'roads',
               'url':'https://www2.census.gov/geo/tiger/TIGER2021/test.zip','etag':'pinned'}
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as archive: archive.writestr('fixture.txt','unit-test input only')
        raw=payload.getvalue();response=io.BytesIO(raw)
        response.status=200;response.headers={'ETag':'pinned','Content-Length':str(len(raw))}
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)
            with patch('download_historical_inputs.urllib.request.urlopen',return_value=response) as request:
                first=acquire(asset,cache,0)
                second=acquire(asset,cache,0)
                self.assertEqual(first['sha256'],second['sha256'])
                self.assertEqual(request.call_count,1)
            next(cache.glob('*.zip')).write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'integrity failed'):
                acquire(asset,cache,0)

    def test_range_ignored_does_not_corrupt_partial_input(self):
        asset={'id':'roads-10-2021','state':'10','observation_year':2021,'kind':'roads',
               'url':'https://www2.census.gov/geo/tiger/TIGER2021/test.zip','etag':'pinned'}
        from process_national_assessment import digest
        key=digest(['historical-input-acquisition-v1',asset])
        response=io.BytesIO(b'not downloaded')
        response.status=200;response.headers={'ETag':'pinned'}
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory);partial=cache/(key+'.part');partial.write_bytes(b'partial')
            with patch('download_historical_inputs.urllib.request.urlopen',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'ignored range'):
                    acquire(asset,cache,0)
            self.assertEqual(partial.read_bytes(),b'partial')
            self.assertFalse((cache/(key+'.zip')).exists())

    def test_html_error_cannot_become_completed_zip(self):
        asset={'id':'roads-10-2021','state':'10','observation_year':2021,'kind':'roads',
               'url':'https://www2.census.gov/geo/tiger/TIGER2021/test.zip','etag':'pinned'}
        response=io.BytesIO(b'<html>source unavailable</html>')
        response.status=200;response.headers={'ETag':'pinned'}
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)
            with patch('download_historical_inputs.urllib.request.urlopen',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'not a complete TIGER ZIP'):
                    acquire(asset,cache,0)
            self.assertFalse(list(cache.glob('*.zip')))

    def test_does_not_guess_absent_traffic_service(self):
        result=traffic_audit({'services':[]},'10','DE',2025)
        self.assertEqual(result['status'],'not_listed_in_dot_hosted_catalog')
        self.assertIn('Not proof',result['interpretation'])

    def test_plan_is_not_an_annual_assessment(self):
        probe={'url':'https://www2.census.gov/geo/tiger/TIGER2021/test.zip','status':'file_header_available'}
        result=make_plan({'records':[{'year':2021,'state':'10','roads':probe,'county_boundaries':probe}]})
        self.assertFalse(result['five_year_calculation_ready'])
        self.assertFalse(result['annual_method_approved'])
        self.assertEqual(len(result['assets']),2)

    def test_download_year_cannot_masquerade_as_another_year(self):
        with self.assertRaises(ValueError):
            verify_asset({'observation_year':2021,'kind':'roads','url':'https://www2.census.gov/geo/tiger/TIGER2024/file.zip'})

    def test_no_annual_calculation_without_research_review(self):
        with self.assertRaisesRegex(ValueError,'Scientific review'):
            verify_review({'methodology_review':{'status':'pending'}})

    def test_missing_hazard_coverage_is_not_zero(self):
        roads=LineString([(0,0),(100,0)])
        with self.assertRaisesRegex(ValueError,'Missing annual source coverage'):
            measure(roads,box(200,200,201,201),box(0,-1,50,1),[])

    def test_zero_exposure_keeps_consequence_null(self):
        result=measure(LineString([(0,0),(100,0)]),box(200,200,201,201),box(-1,-1,101,1),[])
        self.assertEqual(result['status'],'verified_zero_selected_exposure')
        self.assertIsNone(result['transportation_consequence_raw_aadt'])

    def test_missing_traffic_is_not_a_measured_zero_aadt(self):
        result=measure(LineString([(0,0),(100,0)]),box(-1,-1,101,1),box(-1,-1,101,1),[])
        self.assertEqual(result['status'],'missing_traffic')
        self.assertIsNone(result['transportation_consequence_raw_aadt'])

    def test_exposure_and_length_weighted_traffic(self):
        roads=LineString([(0,0),(100,0)])
        result=measure(roads,box(-1,-1,50,1),box(-1,-1,101,1),
            [(LineString([(0,0),(20,0)]),100),(LineString([(20,0),(50,0)]),200)])
        self.assertEqual(result['transportation_exposure'],0.5)
        self.assertEqual(result['transportation_consequence_raw_aadt'],160)


if __name__=='__main__':
    unittest.main()
