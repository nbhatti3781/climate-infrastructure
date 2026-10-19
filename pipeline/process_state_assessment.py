"""Shared-source state batches for the current assessment; never writes Maryland.

Benchmark explicitly before nationwide restart:
  .venv-wildfire/bin/python pipeline/process_state_assessment.py --state 10 --benchmark
Each state has an independent checkpoint/benchmark report. Request caches are
shared with the original runner; county calculation and source masks are reused.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time

from pyproj import Transformer
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree

from process_national_assessment import (
    ROOT, Sources, Blocked, StorageBlocked, NATIONAL_COUNTIES,
    TIGER_PRIMARY_ROADS, TIGER_SECONDARY_ROADS, FEMA_NFHL, FEMA_NRI_COUNTIES,
    HPMS_2024, calculate, atomic_json, baseline_paths, hashes, digest,
    polygon_from_esri, line_from_esri, checkpoint_valid, transform, VERSION)

STATE_VERSION='state-shared-current-v1'
CODE_HASH=digest([Path(__file__).read_text(),Path(__file__).with_name('process_national_assessment.py').read_text()])


def esri_polygon(geometry):
    polygons=[geometry] if geometry.geom_type=='Polygon' else list(geometry.geoms)
    rings=[]
    for polygon in polygons:
        polygon=orient(polygon,sign=-1)
        rings.append(list(polygon.exterior.coords))
        rings.extend(list(r.coords) for r in polygon.interiors)
    return {'rings':rings}


class IndexedLayer:
    def __init__(self,features,polygon=False):
        self.features=features
        self.geometries=[f.get('_shape_wgs84') if f.get('_shape_wgs84') is not None else
                         polygon_from_esri(f['geometry']) if polygon else line_from_esri(f['geometry']) for f in features]
        self.tree=STRtree(self.geometries)

    def query(self,params):
        value=params['geometry']
        if params['geometryType']=='esriGeometryPolygon':
            geometry=polygon_from_esri(json.loads(value))
        else:
            from shapely.geometry import box
            geometry=box(*map(float,value.split(',')))
        return [self.features[int(i)] for i in self.tree.query(geometry,predicate='intersects')]


class StateSources(Sources):
    def __init__(self,cache,reserve,county_features,roads,traffic_rows,flood,shared_requests,flood_error):
        super().__init__(cache,reserve)
        self.counties={str(f['attributes']['GEOID']):f for f in county_features}
        self.roads=roads
        self.traffic=defaultdict(list)
        for row in traffic_rows:
            self.traffic[int(row['county_id'])].append(row)
        self.flood=flood
        self.flood_error=flood_error
        self.requests.update(shared_requests)

    def arcgis(self,url,params,**kwargs):
        if url==NATIONAL_COUNTIES:
            geoid=re.search(r"GEOID='(\d+)'",params['where']).group(1)
            return [self.counties[geoid]]
        if url in self.roads:
            return self.roads[url].query(params)
        if url==FEMA_NFHL+'/28/query':
            if self.flood_error:
                raise Blocked('Shared state NFHL layer unavailable: '+self.flood_error)
            return self.flood.query(params)
        return super().arcgis(url,params,**kwargs)

    def get(self,url,params,binary=False):
        if url==HPMS_2024 and 'county_id=' in params.get('$where',''):
            county=int(re.search(r'county_id=(\d+)',params['$where']).group(1))
            rows=self.traffic[county]
            if params['$select']=='count(*) AS n':
                return [{'n':str(len(rows))}]
            offset=int(params.get('$offset',0))
            return rows[offset:offset+int(params.get('$limit',5000))]
        return super().get(url,params,binary)


def load_state(state,cache,reserve,workers):
    source=Sources(cache,reserve)
    started=time.monotonic()
    county_features=source.arcgis(NATIONAL_COUNTIES,
        {'where':f"GEOID LIKE '{state}%'",'outFields':'GEOID,NAME,STATE','outSR':4326},batch_size=100)
    if not county_features:
        raise Blocked('No county equivalents in requested state')
    geographic=unary_union([polygon_from_esri(f['geometry']) for f in county_features])
    envelope=','.join(map(str,geographic.bounds))
    road_params={'where':'1=1','geometry':envelope,'geometryType':'esriGeometryEnvelope',
                 'inSR':4326,'spatialRel':'esriSpatialRelIntersects','outFields':'OBJECTID,MTFCC','outSR':4326}
    stats=[dict(source.stats)]
    shared=dict(source.requests)

    def fetch(kind):
        adapter=Sources(cache,reserve)
        stamp=time.monotonic()
        error=None
        value=[]
        try:
            if kind in ('primary','secondary'):
                value=adapter.arcgis(TIGER_PRIMARY_ROADS if kind=='primary' else TIGER_SECONDARY_ROADS,road_params,batch_size=1000)
            elif kind=='traffic':
                where=f'stateid={int(state)} AND f_system <= 4'
                expected=int(adapter.get(HPMS_2024,{'$select':'count(*) AS n','$where':where})[0]['n'])
                for offset in range(0,expected,5000):
                    value.extend(adapter.get(HPMS_2024,{'$select':':id,county_id,aadt,line','$where':where,
                                    '$order':':id','$offset':offset,'$limit':5000}))
                if len(value)!=expected or len({r[':id'] for r in value})!=expected:
                    raise Blocked('Incomplete state HPMS rows')
            else:
                # Fetch native NAD83 geometry once; reproject locally to avoid
                # repeating server-side reprojection for every county.
                # Match the county runner's spatial selection. DFIRM_ID prefixes
                # alone can omit adjoining mapping jurisdictions at state edges.
                value=adapter.arcgis(FEMA_NFHL+'/28/query',{'where':'1=1',
                    'geometry':envelope,'geometryType':'esriGeometryEnvelope','inSR':4326,
                    'spatialRel':'esriSpatialRelIntersects',
                    'outFields':'OBJECTID,DFIRM_ID,FLD_ZONE,ZONE_SUBTY,SFHA_TF','outSR':4269},batch_size=100)
                to_wgs=Transformer.from_crs(4269,4326,always_xy=True)
                for feature in value:
                    feature['_shape_wgs84']=transform(to_wgs.transform,polygon_from_esri(feature['geometry']))
        except StorageBlocked:
            raise
        except Exception as exc:
            if kind!='flood':
                raise
            error=str(exc)
        return kind,value,error,dict(adapter.requests),dict(adapter.stats),time.monotonic()-stamp

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(fetch,['primary','secondary','traffic','flood']))
    layers={}
    durations={}
    for kind,value,error,requests,measurements,elapsed in results:
        layers[kind]=(value,error)
        shared.update(requests)
        stats.append(measurements)
        durations[kind]={'elapsed_seconds':elapsed,'records':len(value),'error':error}
    roads={TIGER_PRIMARY_ROADS:IndexedLayer(layers['primary'][0]),
           TIGER_SECONDARY_ROADS:IndexedLayer(layers['secondary'][0])}
    flood=IndexedLayer(layers['flood'][0],polygon=True) if not layers['flood'][1] else None
    adapter=StateSources(cache,reserve,county_features,roads,layers['traffic'][0],flood,shared,layers['flood'][1])
    return adapter,{'elapsed_seconds':time.monotonic()-started,'layers':durations,
                    'source_stats':{k:sum(s[k] for s in stats) for k in stats[0]}},shared


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',action='append',required=True,help='Two-digit state FIPS; explicit state list prevents an accidental national restart')
    parser.add_argument('--benchmark',action='store_true')
    parser.add_argument('--workers',type=int,choices=[1,2],default=2,help='Maximum simultaneous source download tasks; county GIS calculations remain bounded to one')
    parser.add_argument('--reserve-mb',type=int,default=64)
    parser.add_argument('--cache-dir',type=Path,default=ROOT/'data/cache/national-current')
    args=parser.parse_args()
    if args.reserve_mb<32 or any(not re.fullmatch(r'\d{2}',s) for s in args.state):
        parser.error('Use two-digit states and at least 32 MiB reserve')
    if '24' in args.state:
        parser.error('Maryland is preserved and validated by validate_national_maryland.py; this runner never replaces it')
    before=hashes(baseline_paths())
    root=ROOT/'data/processed/national-current'
    master=json.loads((root/'manifest.json').read_text())
    nri_source=Sources(args.cache_dir,args.reserve_mb)
    nri=nri_source.arcgis(FEMA_NRI_COUNTIES,{'where':'1=1','outFields':'STCOFIPS,STATE,IFLD_AFREQ,WFIR_AFREQ,NRI_VER'},geometry=False,batch_size=1000)
    frequencies={str(f['attributes']['STCOFIPS']):f['attributes'] for f in nri}
    for state in args.state:
        started=time.monotonic()
        out=root/('benchmarks' if args.benchmark else 'states')/state
        out.mkdir(parents=True,exist_ok=True)
        import fcntl
        lock=(out/'runner.lock').open('a')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        checkpoint=out/'checkpoints.json'
        ledger=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        entries=[m for m in master if m['geoid'].startswith(state)]
        if not entries:
            raise Blocked('State is absent from the frozen county manifest')
        sizes_before=sum(p.stat().st_size for p in args.cache_dir.glob('*/*'))
        try:
            source,timing,shared=load_state(state,args.cache_dir,args.reserve_mb,args.workers)
            timings=[]
            for entry in entries:
                entry={**entry,'state':frequencies.get(entry['geoid'],{}).get('STATE') or entry['state']}
                for hazard in ('wildfire','flood'):
                    key=hazard+':'+entry['geoid']
                    path=out/hazard/'counties'/f"{entry['geoid']}.json"
                    fingerprint=digest([CODE_HASH,entry,hazard,shared,nri])
                    identity={'geoid':entry['geoid'],'hazard':hazard,
                              'assessment_period':'current','method_version':VERSION,
                              'source_fingerprint':digest([shared,nri])}
                    if checkpoint_valid(ledger.get(key,{}),path,fingerprint,args.cache_dir):
                        print(key,'state checkpoint reused',flush=True)
                        continue
                    stamp=time.monotonic()
                    source.requests=dict(shared)
                    try:
                        result=calculate(source,entry,hazard,frequencies)
                        atomic_json(path,result)
                        ledger[key]={'status':result['status'],'fingerprint':fingerprint,'output':str(path),
                                     'identity':identity,
                                     'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                     'source_requests':dict(source.requests)}
                    except StorageBlocked:
                        raise
                    except Exception as exc:
                        details=getattr(exc,'diagnostics',None)
                        ledger[key]={'status':'missing_hazard_coverage' if details else 'blocked_source_or_geometry',
                                     'reason':str(exc),'identity':identity,'fingerprint':fingerprint,
                                     'source_requests':dict(source.requests)}
                        if details:
                            diagnostic_path=out/'diagnostics'/f"{entry['geoid']}-{hazard}-coverage.json"
                            atomic_json(diagnostic_path,{'identity':identity,**details})
                            ledger[key]['diagnostic_output']=str(diagnostic_path)
                    elapsed=time.monotonic()-stamp
                    timings.append({'county':entry['geoid'],'hazard':hazard,'seconds':elapsed})
                    atomic_json(checkpoint,ledger)
                    print(key,ledger[key]['status'],f'{elapsed:.2f}s',flush=True)
            sizes_after=sum(p.stat().st_size for p in args.cache_dir.glob('*/*'))
            report={'state':state,'county_count':len(entries),'method':STATE_VERSION,'benchmark_only':args.benchmark,
                    'elapsed_seconds':time.monotonic()-started,'shared_source_load':timing,
                    'county_timings':timings,'incremental_cache_bytes':sizes_after-sizes_before,
                    'tile_and_other_county_source_stats':source.stats,
                    'status_counts':dict(Counter(v['status'] for v in ledger.values())),
                    'maryland_unchanged':hashes(baseline_paths())==before,
                    'national_restart_authorized_by_this_command':False,
                    'limitations':['This state is not a representative sample of large western/Alaska counties.',
                                   'Shared-layer failure prevents a complete runtime estimate for that hazard.',
                                   'Available-only consequence ranks are not published as full national rankings.']}
            atomic_json(out/'benchmark-report.json',report)
            print(json.dumps(report,indent=2),flush=True)
        except (Exception,KeyboardInterrupt) as exc:
            atomic_json(out/'benchmark-report.json',{'state':state,'benchmark_only':args.benchmark,
                        'status':'blocked_or_interrupted','reason':str(exc),'elapsed_seconds':time.monotonic()-started,
                        'completed_checkpoints':ledger,'maryland_unchanged':hashes(baseline_paths())==before})
            raise
        finally:
            lock.close()
    assert hashes(baseline_paths())==before


if __name__=='__main__':
    main()
