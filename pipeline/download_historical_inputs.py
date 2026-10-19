"""Plan or remotely acquire annual road/boundary inputs, never hazard scores.

Without --execute this writes a small input plan only. Execution is Linux-only
and keeps a 5 GiB reserve, so it cannot start a bulk download on this Mac.
Downloads are streamed, source-identity keyed, retried, checkpointed and resumed
with HTTP ranges. Annual hazard sources/methods are deliberately not substituted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import time
import urllib.request
import zipfile
from process_national_assessment import Sources, atomic_json, digest


def make_plan(audit):
    assets=[]
    blocked=[]
    for record in audit['records']:
        for kind in ('roads','county_boundaries'):
            source=record[kind]
            assets.append({'id':f"{kind}-{record['state']}-{record['year']}",
                'observation_year':record['year'],'state':record['state'],'kind':kind,
                'url':source['url'],'probe_status':source['status'],
                'etag':source.get('etag'),'last_modified':source.get('last_modified')})
        traffic=record.get('traffic',{})
        if traffic.get('year_values_verified') and traffic.get('dataset_year_field'):
            assets.append({'id':f"traffic-{record['state']}-{record['year']}",
                'observation_year':record['year'],'state':record['state'],'kind':'traffic',
                'url':traffic['url'],'dataset_year_field':traffic['dataset_year_field'],
                'metadata_sha256':traffic['layer_metadata_sha256']})
        else:
            blocked.append({'year':record['year'],'kind':'traffic',
                            'reason':'Service/year values are not verified; no substitute year used'})
    return {'version':'historical-input-acquisition-v1','scope':'annual inputs only; no hazard scores',
            'candidate_years':[2021,2022,2023,2024,2025],'assets':assets,'unresolved_assets':blocked,
            'annual_method_approved':False,'five_year_calculation_ready':False,
            'blocked_inputs':['Annual flood/WHP observations and approved frequency rules',
                              'Complete annual AADT geometry and exposed-road match validation',
                              'Approved hurricane footprint and compound SPEI-R25 definitions']}


def verify_asset(asset):
    # Bound input identity, not a publication date masquerading as a data year.
    year=asset['observation_year']
    if year not in range(2021,2026) or asset['kind'] not in ('roads','county_boundaries','traffic'):
        raise ValueError('Only candidate annual TIGER inputs are supported')
    if asset['kind']=='traffic':
        prefix=f'https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_DE_{year}/FeatureServer/'
        if not asset['url'].startswith(prefix) or not asset['url'][len(prefix):].isdigit():
            raise ValueError('Traffic URL is not the verified official annual Delaware layer')
        return
    if not asset['url'].startswith(f'https://www2.census.gov/geo/tiger/TIGER{year}/'):
        raise ValueError('Official URL/version does not match the declared observation year')


def sha256(path):
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):
            value.update(chunk)
    return value.hexdigest()


def acquire(asset,cache,reserve):
    verify_asset(asset)
    if asset['kind']=='traffic':
        return acquire_traffic(asset,cache,reserve)
    key=digest(['historical-input-acquisition-v1',asset])
    target=cache/(key+'.zip')
    partial=cache/(key+'.part')
    receipt=cache/(key+'.json')
    identity={k:asset[k] for k in ('id','kind','observation_year','state','url')}
    if target.exists():
        saved=json.loads(receipt.read_text())
        if saved.get('status')!='complete' or saved.get('sha256')!=sha256(target):
            raise ValueError('Cached input integrity failed; original retained, use a new cache directory')
        return saved
    last=None
    for attempt in range(3):
        try:
            if shutil.disk_usage(cache).free<reserve+1024*1024:
                raise OSError('Insufficient storage reserve; no input deleted')
            offset=partial.stat().st_size if partial.exists() else 0
            headers={'User-Agent':'ClimateHistoricalInputAcquisition/1.0','Accept-Encoding':'identity'}
            validator=asset.get('etag') or asset.get('last_modified')
            if offset:
                if not validator:
                    raise ValueError('Partial input has no pinned validator; retain it and re-audit in a new cache')
                headers.update({'Range':f'bytes={offset}-','If-Range':validator})
            request=urllib.request.Request(asset['url'],headers=headers)
            with urllib.request.urlopen(request,timeout=30) as response:
                if offset and (response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                    raise ValueError('Source changed or ignored range; partial input retained')
                for field,header in [('etag','ETag'),('last_modified','Last-Modified')]:
                    if asset.get(field) and response.headers.get(header)!=asset[field]:
                        raise ValueError('Pinned source header changed; re-audit before downloading')
                total=offset+int(response.headers['Content-Length']) if response.headers.get('Content-Length') else None
                with partial.open('ab') as handle:
                    while True:
                        if shutil.disk_usage(cache).free<reserve+1024*1024:
                            raise OSError('Storage reserve reached; resumable partial retained')
                        chunk=response.read(1024*1024)
                        if not chunk: break
                        handle.write(chunk)
                    handle.flush();os.fsync(handle.fileno())
                if total is not None and partial.stat().st_size!=total:
                    raise OSError('Incomplete input; partial retained for resume')
            checksum=sha256(partial)
            if not zipfile.is_zipfile(partial):
                raise ValueError('Response is not a complete TIGER ZIP; partial retained, not a usable input')
            with zipfile.ZipFile(partial) as archive:
                if not archive.namelist() or archive.testzip() is not None:
                    raise ValueError('TIGER ZIP entry integrity failed; input retained for investigation')
            saved={'identity':identity,'source_signature':key,'status':'complete',
                   'bytes':partial.stat().st_size,'sha256':checksum,'assessment_output':False}
            partial.replace(target)
            atomic_json(receipt,saved)
            return saved
        except Exception as exc:
            last=exc
            atomic_json(receipt,{'identity':identity,'status':'blocked_or_partial','reason':str(exc),
                                'partial_bytes':partial.stat().st_size if partial.exists() else 0})
            if isinstance(exc,ValueError): break
            if attempt<2: time.sleep(2**attempt)
    raise RuntimeError(str(last))


def acquire_traffic(asset,cache,reserve):
    key=digest(['historical-input-acquisition-v1',asset])
    source=Sources(cache/'requests',reserve_mb=reserve//1024**2)
    meta=source.get(asset['url'],{'f':'json'})
    if digest(meta)!=asset['metadata_sha256']:
        raise ValueError('Traffic source metadata changed; re-audit before ingestion')
    fields={f['name'].lower():f['name'] for f in meta.get('fields',[])}
    functional=fields['f_system']
    # Download the state once. Do not trust the anomalous 2023 county_id values
    # to drop records; spatial county attribution is a later QA/adaptation step.
    features=source.arcgis(asset['url']+'/query',{'where':f'{functional} <= 4',
                            'outFields':'*','outSR':4326},batch_size=100)
    field=asset['dataset_year_field']
    if any(f['attributes'].get(field)!=asset['observation_year'] for f in features):
        raise ValueError('Traffic contains a missing/different dataset year; no year substitution')
    target=cache/(key+'.json')
    atomic_json(target,{'source':asset,'type':'raw_esri_traffic_features','features':features,
                        'source_requests':source.requests,'data_completeness_verified':False})
    receipt={'identity':asset,'status':'downloaded_unvalidated_traffic','sha256':sha256(target),
             'feature_count':len(features),'assessment_output':False,
             'remaining_work':'AADT measurement dates, missing geometry/traffic, spatial county attribution and road matching'}
    atomic_json(cache/(key+'.receipt.json'),receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--cache-dir',type=Path)
    args=parser.parse_args()
    plan=make_plan(json.loads(args.audit.read_text()))
    atomic_json(args.plan,plan)
    if not args.execute:
        print('Input plan saved. No bulk downloads or annual calculations started.')
        return
    if platform.system()!='Linux' or not args.cache_dir:
        raise SystemExit('Execute only on the approved Linux remote host with --cache-dir')
    args.cache_dir.mkdir(parents=True,exist_ok=True)
    reserve=5*1024**3
    failures=0
    for asset in plan['assets']:
        try:
            result=acquire(asset,args.cache_dir,reserve)
            print(asset['id'],result['status'],flush=True)
        except Exception as exc:
            failures+=1
            print(asset['id'],'blocked:',str(exc),flush=True)
    print('Input acquisition finished/blocked. No hazard calculation or five-year completion is implied.')
    if failures:
        raise SystemExit(1)


if __name__=='__main__':
    main()
