"""Bounded MD/DE archive audit: headers, metadata, counts and <=3 line samples.

Does not download source datasets, calculate scores, or publish county outputs.
Run from repository root. Failed probes remain unknown, never measured zero.
"""
import concurrent.futures
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

DOT = 'https://geo.dot.gov/server/rest/services/'
CENSUS = 'https://www2.census.gov/geo/tiger/'


def read_json(url, params=None):
    if params:
        url += '?' + urllib.parse.urlencode({'f': 'json', **params})
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Response exceeds 1 MiB metadata budget')
    value = json.loads(raw)
    if isinstance(value, dict) and 'error' in value:
        raise ValueError(str(value['error']))
    return value


def probe(url):
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=20) as response:
        return {'status': 'header_available_only', 'url': url, 'http_status': response.status,
                'bytes': response.headers.get('Content-Length'),
                'last_modified': response.headers.get('Last-Modified'),
                'geometry_coverage_verified': False}

OUT = Path('docs/audits/md-de-five-year-feasibility')


def write_county_counts(report):
    """Declared identifiers only: absent group stays blank, never measured zero."""
    rows = []
    scopes = [('MD', '24', [c for c in range(1, 48, 2) if c != 7] + [510]),
              ('DE', '10', [1, 3, 5])]
    for state, prefix, counties in scopes:
        for year in range(2021, 2026):
            source = report['results'].get(f'{state}-{year}-traffic', {})
            groups = {f['attributes']['county_id']: f['attributes']['record_count']
                      for f in source.get('county_counts', {}).get('features', [])}
            missing = {f['attributes']['county_id']: f['attributes']['record_count']
                       for f in source.get('null_or_negative_aadt_counts', {}).get('features', [])}
            for county in counties:
                rows.append({'geoid': prefix + f'{county:03}', 'year': year,
                    'declared_id_records': groups.get(county, ''),
                    'null_or_negative_aadt_records': missing.get(county, ''),
                    'county_assignment': 'suspect_identifiers' if year == 2023 else 'not_spatially_validated',
                    'source_status': source.get('status', 'unknown'),
                    'geometry_coverage': 'unverified', 'exposed_road_match_rate': ''})
    target = OUT / 'county-year-source-counts.csv'
    temporary = target.with_suffix('.tmp')
    with temporary.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(target)


def traffic(catalog, state, year):
    name = f'Hosted/HPMS_FULL_{state}_{year}'
    if not any(s['name'] == name and s['type'] == 'FeatureServer'
               for s in catalog.get('services', [])):
        return {'status': 'not_listed_in_queried_catalog', 'service': name}
    base = DOT + name + '/FeatureServer'
    definition = read_json(base, {'f': 'json'})
    layers = [x for x in definition.get('layers', [])
              if x.get('geometryType') == 'esriGeometryPolyline']
    if len(layers) != 1:
        raise ValueError('Expected one polyline layer')
    url = base + '/' + str(layers[0]['id'])
    meta = read_json(url, {'f': 'json'})
    fields = {x['name'].lower(): x['name'] for x in meta['fields']}
    county = fields.get('county_id') or fields.get('county_code')
    aadt, functional = fields['aadt'], fields['f_system']
    year_field = next((fields[k] for k in ('year_record', 'datayear', 'data_year', 'year')
                       if k in fields), None)
    stats = json.dumps([{'statisticType': 'count', 'onStatisticField': meta['objectIdField'],
                         'outStatisticFieldName': 'record_count'}])
    counts = read_json(url + '/query', {'where': f'{functional} <= 4',
        'groupByFieldsForStatistics': county, 'outStatistics': stats,
        'returnGeometry': 'false'})
    missing = read_json(url + '/query', {'where': f'{functional} <= 4 AND '
        f'({aadt} IS NULL OR {aadt} < 0)', 'groupByFieldsForStatistics': county,
        'outStatistics': stats, 'returnGeometry': 'false'})
    years = read_json(url + '/query', {'where': '1=1', 'outFields': year_field,
        'returnDistinctValues': 'true', 'returnGeometry': 'false'}) if year_field else None
    date_fields = [v for k, v in fields.items() if 'aadt' in k and k != 'aadt']
    selected = list(dict.fromkeys([meta['objectIdField'], county, functional, aadt]
                                  + ([year_field] if year_field else []) + date_fields))
    sample = read_json(url + '/query', {'where': f'{functional} <= 4',
        'outFields': ','.join(selected), 'returnGeometry': 'true', 'outSR': '4326',
        'resultRecordCount': 3})
    if len(sample.get('features', [])) > 3:
        raise ValueError('Server ignored three-feature sample limit')
    if counts.get('exceededTransferLimit') or missing.get('exceededTransferLimit'):
        raise ValueError('Grouped count response was truncated; county coverage unknown')
    return {'status': 'metadata_counts_and_sample_only', 'url': url,
        'dataset_year_field': year_field, 'year_values': years,
        'county_counts': counts, 'null_or_negative_aadt_counts': missing,
        'date_related_fields': date_fields, 'geometry_sample': sample,
        'metadata_sha256': hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest(),
        'all_county_geometry_verified': False, 'aadt_measurement_year_verified': False,
        'exposed_road_aadt_match_rate': None}


def bounded_text(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Response exceeds 1 MiB metadata budget')
    return {'url': url, 'bytes': len(raw), 'text': raw.decode('utf-8')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', action='store_true', help='Reuse successful metadata checkpoints')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = read_json(DOT + 'Hosted', {'f': 'json'})
    tasks = {}
    for state, code in [('MD', '24'), ('DE', '10')]:
        for year in range(2021, 2026):
            tasks[f'{state}-{year}-roads'] = (probe, (f'{CENSUS}TIGER{year}/PRISECROADS/tl_{year}_{code}_prisecroads.zip',))
            tasks[f'{state}-{year}-traffic'] = (traffic, (catalog, state, year))
    tasks['whp-archive'] = (bounded_text, ('https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential-archived-products',))
    tasks['socrata-catalog'] = (read_json, ('https://api.us.socrata.com/api/catalog/v1?' +
        urllib.parse.urlencode({'search_context': 'data.transportation.gov', 'q': 'HPMS Spatial', 'limit': 20}),))
    nri = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0/query'
    tasks['live-nri-md-de'] = (read_json, (nri, {'where': "STATEABBRV IN ('MD','DE')",
        'outFields': 'STCOFIPS,NRI_VER,WFIR_AFREQ,IFLD_AFREQ', 'returnGeometry': 'false'}))
    for name, url in {
        'nfhl-layer-metadata': 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28',
        'nri-layer-metadata': nri.removesuffix('/query'),
        'whp-layer-metadata': 'https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer',
        'exact-socrata-2024-metadata': 'https://data.transportation.gov/api/views/42um-tgh5.json',
    }.items():
        tasks[name] = (read_json, (url, {'f': 'json'}))
    for year in range(2021, 2026):
        tasks[f'{year}-county-boundaries'] = (probe, (f'{CENSUS}TIGER{year}/COUNTY/tl_{year}_us_county.zip',))
    for state, code in [('MD', '24'), ('DE', '10')]:
        query = urllib.parse.urlencode({'$select': 'year_record,count(*),min(aadt),max(aadt),min(aadt_d),max(aadt_d)',
            '$where': f'stateid={code} AND f_system<=4', '$group': 'year_record'})
        tasks[f'exact-socrata-2024-{state}'] = (read_json, ('https://data.transportation.gov/resource/42um-tgh5.json?' + query,))
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'MD and DE; candidate 2021–2025; metadata and tiny samples only',
        'traffic_catalog_url': DOT + 'Hosted?f=json',
        'discovered_md_de_services': [s for s in catalog.get('services', [])
            if s['name'].startswith(('Hosted/HPMS_FULL_MD_', 'Hosted/HPMS_FULL_DE_'))],
        'annual_method_selected': False, 'full_datasets_downloaded': False,
        'geometry_sample_limit_per_state_year': 3, 'results': {}}
    target = OUT / 'metadata-samples.json'
    if args.resume and target.exists():
        previous = json.loads(target.read_text())
        report['previous_check_started_at'] = previous['checked_at']
        report['results'] = {key: value for key, value in previous['results'].items()
                             if not isinstance(value, dict) or
                             value.get('status') != 'unverified_access_or_query_error'}
        tasks = {key: value for key, value in tasks.items() if key not in report['results']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn, *args): key for key, (fn, args) in tasks.items()}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                value = future.result()
            except Exception as exc:
                value = {'status': 'unverified_access_or_query_error', 'reason': str(exc)}
            report['results'][key] = value
            target = OUT / 'metadata-samples.json'
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(report, indent=2) + '\n')
            temporary.replace(target)
            print(key, value.get('status', 'metadata_received') if isinstance(value, dict) else 'metadata_received', flush=True)
    write_county_counts(report)


if __name__ == '__main__':
    main()
