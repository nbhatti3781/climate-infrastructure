"""Offline preparation of the MD/DE 2021–2025 fixed-hazard pilot.

Pins existing source bytes, audits frequency compatibility and writes review-only
readiness manifests. No network, GIS downloads, county outputs or AWS operations.
Metadata/sample hashes are explicitly not complete source-data pins.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS = tuple(range(2021, 2026))
LABEL = 'Infrastructure exposure by year — fixed hazard baseline'


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def pin(path, root):
    return {'file': str(path.relative_to(root)), 'sha256': sha256(path),
            'bytes': path.stat().st_size}


def county_ids():
    return [f'24{code:03}' for code in range(1, 48, 2) if code != 7] + ['24510', '10001', '10003', '10005']


def frequency_reference(rows, field):
    values = [r[field] for r in rows.values()
              if isinstance(r.get(field), (int, float)) and
              math.isfinite(r[field]) and r[field] >= 0]
    if len(values) < 3000 or min(values) == max(values):
        raise ValueError('Incomplete or degenerate national frequency reference')
    return {'field': field, 'min': min(values), 'max': max(values),
            'valid_count': len(values), 'fixed_across_years': True}


def verify_year_mapping(state, year, field, description, current_year):
    if state not in ('MD', 'DE') or year not in YEARS:
        raise ValueError('Pilot scope is MD/DE, exactly 2021–2025')
    expected = ('AADT' if year == 2025 else f'AADT_{year}') if state == 'MD' else (
        'CURRENT_AADT' if year == 2025 else f'AADT_LAST_YEAR_{2025-year}')
    if field != expected or current_year != 2025:
        raise ValueError('Annual field mapping/source anchor changed; no rolling-year substitution')
    if state == 'MD' and year == 2025 and '2025' not in description:
        raise ValueError('Current AADT field has no verified 2025 source definition')


def load_nri(root):
    rows, sources = {}, []
    for request in sorted((root/'data/cache/national-current').glob('*/*.request.json')):
        meta = json.loads(request.read_text())
        if 'National_Risk_Index' not in meta.get('url', '') or 'IFLD_AFREQ' not in meta.get('params', {}).get('outFields', ''):
            continue
        payload = request.with_name(request.name.replace('.request.json', '.gz'))
        if not payload.exists():
            continue
        with gzip.open(payload, 'rt') as stream:
            data = json.load(stream)
        for feature in data.get('features', []):
            row = feature['attributes']; geoid = row['STCOFIPS']
            relevant = {key: row.get(key) for key in ('IFLD_AFREQ', 'WFIR_AFREQ', 'NRI_VER')}
            if geoid in rows and rows[geoid] != relevant:
                raise ValueError('Conflicting cached NRI snapshots: '+geoid)
            rows[geoid] = relevant
        sources.extend([pin(request, root), pin(payload, root)])
    return rows, sources


def prepare(root):
    audit = root/'docs/audits/md-de-five-year-feasibility'
    evidence = json.loads((audit/'supplemental-metadata.json').read_text())
    baseline = json.loads((root/'data/cache/session-handoff/2026-10-07/preservation-baseline.json').read_text())
    if any(sha256(root/name) != checksum for name, checksum in baseline.items()):
        raise ValueError('Saved current assessment preservation hash changed')
    rows, nri_sources = load_nri(root)
    refs = {hazard: frequency_reference(rows, field) for hazard, field in
            [('flood', 'IFLD_AFREQ'), ('wildfire', 'WFIR_AFREQ')]}
    comparisons = []
    for geoid in county_ids():
        if geoid not in rows:
            raise ValueError('Missing pilot NRI county '+geoid)
        if not geoid.startswith('24'):
            continue
        for hazard, folder in [('flood', 'data/processed/counties'), ('wildfire', 'data/processed/wildfire/counties')]:
            saved = json.loads((root/folder/f'{geoid}.json').read_text()); reference = refs[hazard]
            raw = rows[geoid][reference['field']]
            normalized = (raw-reference['min'])/(reference['max']-reference['min'])
            matches = (math.isclose(raw, saved['annualized_frequency'], abs_tol=1e-12, rel_tol=0)
                and math.isclose(reference['min'], saved['frequency_min_national'], abs_tol=1e-12, rel_tol=0)
                and math.isclose(reference['max'], saved['frequency_max_national'], abs_tol=1e-12, rel_tol=0)
                and math.isclose(normalized, saved['normalized_frequency'], abs_tol=1e-9, rel_tol=0))
            if not matches:
                raise ValueError('Cached NRI is incompatible with preserved Maryland frequency: '+geoid+'/'+hazard)
            comparisons.append({'geoid': geoid, 'hazard': hazard, 'frequency_matches_saved_baseline': matches})
    raster_pins = [pin(p, root) for p in sorted((root/'data/cache/wildfire/whp2023/24').glob('*/*.tif'))]
    source_pins = [pin(p, root) for p in sorted((root/'data/cache/wildfire/whp2023/24').glob('*/*.request.json'))]
    metadata_pins = [pin(p, root) for p in sorted((root/'data/cache/wildfire/whp2023/24/metadata').glob('*.json'))]
    annual_inputs = []
    prior_summary = json.loads((root/'docs/audits/maryland-history-2020-2022/summary.json').read_text())
    for state, prefix in [('MD', '24'), ('DE', '10')]:
        meta = evidence['md-aadt-lines' if state == 'MD' else 'de-traffic-10']['data']
        aliases = {f['name']: f.get('alias') for f in meta['fields']}
        for year in YEARS:
            field = ('AADT' if year == 2025 else f'AADT_{year}') if state == 'MD' else (
                'CURRENT_AADT' if year == 2025 else f'AADT_LAST_YEAR_{2025-year}')
            anchor = 2025 if state == 'MD' else evidence['DE-annual-aadt-counts']['data']['features'][0]['attributes']['CURRENT_YEAR']
            verify_year_mapping(state, year, field, meta.get('description', ''), anchor)
            if field not in aliases:
                raise ValueError('Missing annual AADT field '+field)
            if state == 'DE' and aliases[field] != f'AADT {year}':
                raise ValueError('Delaware rolling field alias changed')
            local = root/f'data/cache/historical-audit/maryland-2020-2022/tl_{year}_{prefix}_prisecroads.zip'
            road_pin = pin(local, root) if local.exists() else None
            if road_pin:
                archived = [s for s in prior_summary['sources'] if s.get('url', '').endswith(local.name)]
                if len(archived) != 1 or road_pin['sha256'] != archived[0]['sha256']:
                    raise ValueError('Annual road file differs from the prior official-source audit')
                with zipfile.ZipFile(local) as archive:
                    names = set(archive.namelist())
                    if not all(local.stem+ext in names for ext in ('.shp', '.shx', '.dbf', '.prj')) or archive.testzip():
                        raise ValueError('Annual road ZIP missing components or failed CRC')
            annual_inputs.append({'state': state, 'year': year, 'roads_url':
                f'https://www2.census.gov/geo/tiger/TIGER{year}/PRISECROADS/tl_{year}_{prefix}_prisecroads.zip',
                'roads_local_pin': road_pin,
                'roads_validation': 'prior_source_hash_and_zip_crc_match' if road_pin else 'payload_not_acquired',
                'traffic_url': evidence['md-aadt-lines' if state == 'MD' else 'de-traffic-10']['url'].split('?')[0],
                'traffic_role': 'state_supplement_candidate_for_overlap_validation_not_selected',
                'primary_traffic_source': 'annual HPMS where available; 2025 unverified',
                'aadt_field': field, 'aadt_estimate_year': year,
                'positive_traffic_source_records': evidence[f'{state}-{year}-positive-aadt-count']['data']['count'],
                'traffic_payload_pin': None, 'traffic_geometry_comparability': 'unvalidated',
                'exposed_road_traffic_coverage': None})
    jobs = [{'geoid': geoid, 'year': year, 'hazard': hazard,
             'status': 'input_validation_pending', 'publishable': False}
            for geoid in county_ids() for year in YEARS for hazard in ('flood', 'wildfire')]
    return {'label': LABEL, 'interpretation': 'Changes reflect roads and traffic against fixed mapped hazards, not annual hazard conditions.',
        'target_years': list(YEARS), 'states': ['MD', 'DE'], 'county_equivalents': 27,
        'preparation_status': 'blocked_inputs_not_ready', 'ec2_launch_paused': True,
        'gina_review_status': 'pending', 'publication_allowed': False,
        'preserved_current_files': baseline,
        'evidence_pin': pin(audit/'supplemental-metadata.json', root),
        'baselines': {
            'nri': {'status': 'cached_bytes_pinned', 'versions': sorted({x['NRI_VER'] for x in rows.values()}),
                    'county_count': len(rows), 'assets': nri_sources, 'national_frequency_reference': refs,
                    'pilot_county_frequency_values': {g: rows[g] for g in county_ids()},
                    'maryland_compatibility': comparisons},
            'whp': {'metric': 'WHP2023 High/Very High classes 4/5; end-2020 landscape conditions',
                    'status': 'maryland_rasters_pinned_delaware_pending', 'maryland_rasters': raster_pins,
                    'export_request_pins': source_pins, 'service_metadata_pins': metadata_pins,
                    'delaware_complete_coverage_pin': None},
            'nfhl': {'metric': "SFHA_TF='T'; retain current coastal/tidal classes",
                     'status': 'original_maryland_geometry_unavailable_snapshot_required',
                     'complete_md_de_geometry_pin': None}},
        'normalization': {'frequency': 'one pinned national min/max per hazard for all five years',
            'consequence': 'fixed national reference proposed for Gina; no within-year or MD/DE-only ranking',
            'national_consequence_reference_pin': None, 'annual_normalized_consequence': None,
            'annual_stress': None},
        'prior_geometry_audit_pin': pin(root/'docs/audits/maryland-history-2020-2022/audit-report.md', root),
        'annual_inputs': annual_inputs, 'jobs': jobs,
        'blockers': ['Complete pinned NFHL geometry and mapped-coverage layers unavailable; original MD flood replay blocked.',
            'Complete pinned Delaware WHP coverage not established.',
            'Eight annual state road payloads not acquired; all annual traffic payloads unacquired.',
            'Traffic geometry lineage, functional-class crosswalk and exposed-road coverage unvalidated.',
            'DelDOT 2025 growth-factor change requires overlap-year comparison.',
            'No complete fixed national consequence ranking reference; Gina review pending.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/pilots/md-de-fixed-baseline')
    args = parser.parse_args()
    # This utility cannot be used to overwrite the dashboard or its source cache.
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/pilots'):
        raise SystemExit('Preparation output must remain under docs/pilots')
    manifest = prepare(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    temp = output/'manifest.tmp'
    temp.write_text(json.dumps(manifest, indent=2)+'\n')
    temp.replace(output/'manifest.json')
    temp = output/'county-year-readiness.tmp'
    with temp.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest['jobs'][0]))
        writer.writeheader(); writer.writerows(manifest['jobs'])
    temp.replace(output/'county-year-readiness.csv')
    print(f"Prepared {len(manifest['jobs'])} review-only jobs; processing/publication blocked; EC2 paused.")
    print('Maryland frequency comparisons matching:', sum(x['frequency_matches_saved_baseline']
          for x in manifest['baselines']['nri']['maryland_compatibility']), '/ 48')


if __name__ == '__main__':
    main()
