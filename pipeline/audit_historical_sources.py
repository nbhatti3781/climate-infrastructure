"""Small metadata-only annual-input audit; never calculates hazard scores.

Discovers real DOT services/layers, probes annual TIGER files without downloading
them, and counts county traffic records. A service/file listing is not proof of
complete geometry, same-year AADT matches, or an approved annual hazard method.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
from process_national_assessment import atomic_json

DOT='https://geo.dot.gov/server/rest/services/'
CENSUS='https://www2.census.gov/geo/tiger/'
MAX_METADATA=2*1024*1024


def read_json(url,params=None):
    if params:
        url+='?'+urllib.parse.urlencode({'f':'json',**params})
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ClimateHistorySourceAudit/1.0'}),timeout=20) as response:
        raw=response.read(MAX_METADATA+1)
    if len(raw)>MAX_METADATA:
        raise ValueError('Metadata response exceeded 2 MiB; no full dataset downloaded')
    value=json.loads(raw)
    if 'error' in value:
        raise ValueError(str(value['error']))
    return value


def probe(url):
    try:
        request=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'ClimateHistorySourceAudit/1.0'})
        with urllib.request.urlopen(request,timeout=20) as response:
            return {'url':url,'status':'file_header_available','http_status':response.status,
                    'bytes':response.headers.get('Content-Length'),'etag':response.headers.get('ETag'),
                    'last_modified':response.headers.get('Last-Modified'),
                    'data_completeness_verified':False}
    except Exception as exc:
        return {'url':url,'status':'unverified_access_error','reason':str(exc),
                'data_completeness_verified':False}


def traffic_audit(catalog,state,abbreviation,year):
    # Catalog discovery is required; a guessed service/0 404 proves little.
    suffix=f'HPMS_FULL_{abbreviation}_{year}'
    services=[s for s in catalog.get('services',[]) if s['name'].split('/')[-1]==suffix and s['type']=='FeatureServer']
    if not services:
        return {'status':'not_listed_in_dot_hosted_catalog','searched_service':suffix,
                'interpretation':'Not proof that no other official source exists'}
    service=DOT+services[0]['name']+'/FeatureServer'
    try:
        definition=read_json(service,{'f':'json'})
        layers=[l for l in definition.get('layers',[]) if l.get('geometryType')=='esriGeometryPolyline']
        if len(layers)!=1:
            raise ValueError('Expected exactly one line layer; inspect service manually')
        endpoint=service+'/'+str(layers[0]['id'])
        meta=read_json(endpoint,{'f':'json'})
        fields={f['name'].lower():f['name'] for f in meta.get('fields',[])}
        functional=fields.get('f_system')
        aadt=fields.get('aadt')
        county=fields.get('county_id') or fields.get('county_code')
        if not all((functional,aadt,county)):
            raise ValueError('Missing functional-class, AADT or county field')
        counties={}
        for code in (1,3,5):
            where=f'{functional} <= 4 AND {county} = {code}'
            count=read_json(endpoint+'/query',{'where':where,'returnCountOnly':'true'})['count']
            missing=read_json(endpoint+'/query',{'where':where+f' AND ({aadt} IS NULL OR {aadt}<0)',
                                               'returnCountOnly':'true'})['count']
            counties[state+f'{code:03}']={'selected_traffic_records':count,'null_or_negative_aadt_records':missing,
                                        'geometry_and_road_match_rate':'not_audited'}
        year_field=next((fields[k] for k in ('year_record','datayear','data_year','year') if k in fields),None)
        observed_years=None
        if year_field:
            values=read_json(endpoint+'/query',{'where':'1=1','outFields':year_field,
                'returnGeometry':'false','returnDistinctValues':'true'})
            if not values.get('exceededTransferLimit'):
                observed_years=[f['attributes'][year_field] for f in values.get('features',[])]
        anomalies=[geoid for geoid,counts in counties.items() if not counts['selected_traffic_records']]
        return {'status':'county_coverage_requires_investigation' if anomalies else 'metadata_and_counts_available',
                'url':endpoint,'declared_service_year':year,'empty_county_id_queries':anomalies,
                'observed_year_values':observed_years,'year_values_verified':observed_years==[year],
                'dataset_year_field':year_field,
                'aadt_measurement_vintage_verified':False,
                'year_interpretation':'Dataset year only; AADT measurement-date fields and geometry require further audit.',
                'layer_metadata_sha256':hashlib.sha256(json.dumps(meta,sort_keys=True).encode()).hexdigest(),
                'counties':counties,'data_completeness_verified':False}
    except Exception as exc:
        return {'status':'unverified_service_error','url':service,'reason':str(exc)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        catalog=read_json(DOT+'Hosted',{'f':'json'})
        catalog_error=None
    except Exception as exc:
        catalog={}; catalog_error=str(exc)
    records=[]
    for year in range(2021,2026):
        records.append({'year':year,'state':'10',
            'roads':probe(f'{CENSUS}TIGER{year}/PRISECROADS/tl_{year}_10_prisecroads.zip'),
            'county_boundaries':probe(f'{CENSUS}TIGER{year}/COUNTY/tl_{year}_us_county.zip'),
            'traffic':traffic_audit(catalog,'10','DE',year) if not catalog_error else {'status':'catalog_unavailable','reason':catalog_error},
            'annual_hazard_calculation_ready':False})
        # Checkpoint after each year, including failures. No score files written.
        atomic_json(args.output,{'audit_type':'metadata_only','window':'2021-2025_candidate',
            'checked_at':datetime.now(timezone.utc).isoformat(),'records':records,
            'five_year_window_approved':False,'annual_scores_generated':False,
            'limitations':['HEAD proves access only, not annual completeness.',
                'County AADT counts do not prove valid geometry or road match rates.',
                'Current NFHL/WHP/NRI are not annual observations; separate scientific review required.']})
        print(year,records[-1]['roads']['status'],records[-1]['traffic']['status'],flush=True)


if __name__=='__main__':
    main()
