"""Offline pilot-preparation contracts; no downloads or publication fixtures."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from prepare_fixed_baseline_pilot import (
    ROOT, YEARS, county_ids, frequency_reference, load_nri, prepare, verify_year_mapping,
)


class FixedBaselinePilotTests(unittest.TestCase):
    def test_scope_keeps_all_five_target_years_and_27_real_counties(self):
        self.assertEqual(YEARS, (2021, 2022, 2023, 2024, 2025))
        self.assertEqual(len(set(county_ids())), 27)
        self.assertNotIn('24007', county_ids())

    def test_does_not_accept_an_older_year(self):
        with self.assertRaises(ValueError):
            verify_year_mapping('MD', 2020, 'AADT_2020', '2025', 2025)

    def test_rolling_field_cannot_silently_move_to_next_year(self):
        with self.assertRaisesRegex(ValueError, 'anchor changed'):
            verify_year_mapping('DE', 2025, 'CURRENT_AADT', '', 2026)

    def test_current_field_needs_a_verified_year(self):
        with self.assertRaisesRegex(ValueError, 'source definition'):
            verify_year_mapping('MD', 2025, 'AADT', 'current snapshot', 2025)

    def test_wrong_year_field_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_year_mapping('MD', 2021, 'AADT_2024', '2025', 2025)

    def test_two_state_sample_cannot_become_national_reference(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            frequency_reference({'test': {'IFLD_AFREQ': 1.0}}, 'IFLD_AFREQ')

    def test_conflicting_source_snapshots_are_not_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in (1, 2):
                path = root/'data/cache/national-current'/str(index)
                path.mkdir(parents=True)
                (path/'request.request.json').write_text(json.dumps({
                    'url': 'National_Risk_Index', 'params': {'outFields': 'IFLD_AFREQ'}}))
                with gzip.open(path/'request.gz', 'wt') as stream:
                    json.dump({'features': [{'attributes': {'STCOFIPS': 'fixture',
                        'IFLD_AFREQ': index, 'WFIR_AFREQ': 0, 'NRI_VER': 'fixture'}}]}, stream)
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                load_nri(root)

    def test_real_preparation_has_no_publishable_scores(self):
        result = prepare(ROOT)
        self.assertEqual(len(result['jobs']), 270)
        self.assertEqual(len(result['annual_inputs']), 10)
        self.assertFalse(result['publication_allowed'])
        self.assertTrue(result['ec2_launch_paused'])
        self.assertIsNone(result['normalization']['annual_stress'])
        self.assertIsNone(result['baselines']['nfhl']['complete_md_de_geometry_pin'])
        self.assertTrue(all(not x['publishable'] for x in result['jobs']))
        comparisons = result['baselines']['nri']['maryland_compatibility']
        self.assertEqual(len(comparisons), 48)
        self.assertTrue(all(x['frequency_matches_saved_baseline'] for x in comparisons))


if __name__ == '__main__':
    unittest.main()
