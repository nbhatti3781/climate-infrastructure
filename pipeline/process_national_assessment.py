"""Current SFHA/WHP assessment; resumable national staging, never writes Maryland.

Run with .venv-wildfire/bin/python pipeline/process_national_assessment.py.
Source snapshots, per-request compressed caches, county checkpoints and reports
are independent of the historical audit and existing Maryland output paths.
"""
from __future__ import annotations

import argparse
import fcntl
from collections import Counter
from datetime import date
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.parse
import urllib.request

import numpy as np
from pyproj import CRS, Geod, Transformer
import rasterio
from rasterio.features import shapes
from rasterio.io import MemoryFile
from shapely.geometry import box, shape, Polygon, Point
from shapely.ops import unary_union
from shapely import transform as vector_transform
from shapely.prepared import prep
from shapely.strtree import STRtree

from config import (ROOT, TIGER_COUNTIES, TIGER_PRIMARY_ROADS,
                    TIGER_SECONDARY_ROADS, FEMA_NRI_COUNTIES, FEMA_NFHL, HPMS_2024)
from process_maryland_flood import line_from_esri
from process_maryland_wildfire import CLASSES, WHP, MILE, line_parts

VERSION = 'national-current-sfha-whp2023-v1'
NATIONAL_COUNTIES = TIGER_COUNTIES.replace('/57/query','/1/query')
STATE_CODES = {f'{n:02}' for n in
               (1,2,4,5,6,8,9,10,11,12,13,15,16,17,18,19,20,21,22,23,24,
                25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,
                44,45,46,47,48,49,50,51,53,54,55,56)}
CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class Blocked(RuntimeError):
    pass


class StorageBlocked(Blocked):
    pass


class CoverageBlocked(Blocked):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def transform(fn,geometry):
    """Same coordinate operation, applied to arrays instead of Python vertices."""
    return vector_transform(geometry,fn,interleaved=False,include_z=geometry.has_z)


def polygon_from_esri(geometry):
    """Preserve Esri holes using coordinate shells, never Polygon(shell_object).

    This decoder is isolated from the preserved Maryland implementation.
    """
    rings=[r for r in geometry.get('rings',[]) if len(r)>=4]
    if not rings:
        raise Blocked('Missing polygon rings')
    def area(r):
        return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]))/2
    shells=[r for r in rings if area(r)<0]
    holes=[r for r in rings if area(r)>=0]
    if not shells and len(rings)==1:
        return Polygon(rings[0]).buffer(0)
    if not shells:
        raise Blocked('Ambiguous polygon ring orientation')
    shell_polygons=[Polygon(r) for r in shells]
    shell_tree=STRtree(shell_polygons)
    prepared_shells=[prep(p) for p in shell_polygons]
    shell_areas=[p.area for p in shell_polygons]
    assignments=[[] for _ in shells]
    for hole in holes:
        probe=Point(hole[0])
        candidates=[int(i) for i in shell_tree.query(probe) if prepared_shells[int(i)].covers(probe)]
        if not candidates:
            raise Blocked('Unassigned polygon hole')
        index=min(candidates,key=lambda i:shell_areas[i])
        assignments[index].append(hole)
    return unary_union([Polygon(coords,holes=assignments[i]).buffer(0) for i,coords in enumerate(shells)])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


class Sources:
    def __init__(self, cache, reserve_mb=256):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.reserve = reserve_mb * 1024**2
        self.requests = {}
        self.stats={'network_requests':0,'network_seconds':0.0,'network_bytes':0,'cache_hits':0}

    def capacity(self, size=0):
        if shutil.disk_usage(self.cache).free < self.reserve + size:
            raise StorageBlocked(f'Insufficient cache storage: reserve={self.reserve//1024**2} MiB, '
                                 f'free={shutil.disk_usage(self.cache).free//1024**2} MiB')

    def get(self, url, params, binary=False):
        decoded=None
        key = digest([url, params])
        path = self.cache / key[:2] / (key + '.gz')
        if path.exists():
            self.stats['cache_hits']+=1
            try:
                raw = gzip.decompress(path.read_bytes())
            except (OSError, EOFError):
                raise Blocked(f'Corrupt cached request {key}; use a fresh cache directory')
        else:
            self.capacity()
            full = url + '?' + urllib.parse.urlencode(params)
            for attempt in range(3):
                started=time.monotonic()
                try:
                    request = urllib.request.Request(
                        url if len(full)>1800 or '/NFHL/' in url and url.endswith('/query') else full,
                        data=urllib.parse.urlencode(params).encode() if len(full)>1800 or '/NFHL/' in url and url.endswith('/query') else None,
                        headers={'User-Agent':'ClimateInfrastructureAssessment/1.0'})
                    with urllib.request.urlopen(request, timeout=45) as response:
                        raw = response.read()
                    self.stats['network_bytes']+=len(raw)
                    if not binary:
                        payload = json.loads(raw)
                        decoded=payload
                        if isinstance(payload, dict) and 'error' in payload:
                            raise Blocked(f'Source error {url}: {payload["error"]}')
                    break
                except Exception as exc:
                    if isinstance(exc,Blocked):
                        raise
                    if attempt == 2:
                        raise
                    retry_after=getattr(exc,'headers',{}).get('Retry-After','')
                    time.sleep(min(60,float(retry_after)) if str(retry_after).isdigit() else 2**attempt)
                finally:
                    self.stats['network_requests']+=1
                    self.stats['network_seconds']+=time.monotonic()-started
            packed = gzip.compress(raw)
            self.capacity(len(packed))
            atomic_bytes(path, packed)
            atomic_json(path.with_suffix('.request.json'), {'url':url,'params':params,
                         'retrieved_at':time.time(),'sha256':hashlib.sha256(raw).hexdigest()})
        self.requests[key] = hashlib.sha256(raw).hexdigest()
        return raw if binary else decoded if decoded is not None else json.loads(raw)

    def arcgis(self, url, params, geometry=True, batch_size=100):
        # Snapshot and checkpoint the ID list; do not rely on unstable offsets.
        meta = self.get(url.rsplit('/query',1)[0], {'f':'json'})
        oid = meta.get('objectIdField') or meta.get('objectIdFieldName') or 'OBJECTID'
        filt = {k:v for k,v in params.items() if k not in ('outFields','outSR','returnGeometry','orderByFields')}
        ids_response = self.get(url, {'f':'json', **filt, 'returnIdsOnly':'true'})
        if 'objectIds' not in ids_response:
            raise Blocked(f'Missing object ID list: {url}')
        ids = sorted(ids_response['objectIds'] or [])
        if len(ids) != len(set(ids)):
            raise Blocked('Duplicate source object IDs')
        fields = params.get('outFields','*')
        if fields != '*' and oid.lower() not in fields.lower().split(','):
            fields += ',' + oid
        result = []
        def read_batch(batch):
            p = {'f':'json','where':f"{oid} IN ({','.join(map(str,batch))})",
                 'outFields':fields,'returnGeometry':str(geometry).lower()}
            if 'outSR' in params:
                p['outSR']=params['outSR']
            try:
                return self.get(url,p)
            except StorageBlocked:
                raise
            except Exception as exc:
                if len(batch)>1 and any(code in str(exc) for code in ('500','502','503','504','413')):
                    mid=len(batch)//2
                    left,right=read_batch(batch[:mid]),read_batch(batch[mid:])
                    return {'features':left.get('features',[])+right.get('features',[]),
                            'exceededTransferLimit':left.get('exceededTransferLimit',False) or right.get('exceededTransferLimit',False)}
                raise
        for offset in range(0, len(ids), batch_size):
            batch = ids[offset:offset+batch_size]
            page = read_batch(batch)
            features = page.get('features',[])
            received = [f['attributes'].get(oid) for f in features]
            if page.get('exceededTransferLimit') or set(received) != set(batch) or len(received)!=len(batch):
                raise Blocked(f'Incomplete source ID batch: {url}, offset {offset}')
            if geometry and any(not f.get('geometry') for f in features):
                raise Blocked(f'Missing geometry in {url}')
            result.extend(features)
        return result


def projected_county(boundary, geoid):
    geographic = polygon_from_esri(boundary)
    if geographic.is_empty or not geographic.is_valid:
        raise Blocked('Invalid county geometry')
    if geographic.bounds[2]-geographic.bounds[0] > 180:
        raise Blocked('Antimeridian county requires split geometry; no distorted lengths published')
    centre = geographic.centroid
    if geoid.startswith('24'):
        crs = CRS.from_epsg(26918)
    else:
        crs = CRS.from_proj4(f'+proj=aeqd +lat_0={centre.y} +lon_0={centre.x} +datum=NAD83 +units=m +no_defs')
    to_local = Transformer.from_crs(4326, crs, always_xy=True)
    return geographic, transform(to_local.transform, geographic), crs, to_local


def spatial_filter(geometry):
    return {'geometry':json.dumps({'rings':[list(geometry.exterior.coords)]}) if geometry.geom_type=='Polygon'
            else ','.join(map(str,geometry.bounds)),
            'geometryType':'esriGeometryPolygon' if geometry.geom_type=='Polygon' else 'esriGeometryEnvelope',
            'inSR':4326,'spatialRel':'esriSpatialRelIntersects'}


def road_network(source, county, geographic, to_local):
    params={'where':'1=1', **spatial_filter(geographic), 'outFields':'OBJECTID,MTFCC','outSR':4326}
    feats = source.arcgis(TIGER_PRIMARY_ROADS,params)+source.arcgis(TIGER_SECONDARY_ROADS,params)
    geodesic=Geod(ellps='GRS80')
    parts=[]
    geo_parts=[]
    for feature in feats:
        line=line_from_esri(feature['geometry'])
        if not line.is_valid:
            raise Blocked('Invalid TIGER road geometry')
        clipped=line.intersection(geographic)
        geo_parts.extend(line_parts(clipped))
        parts.extend(line_parts(transform(to_local.transform,line).intersection(county)))
    network=unary_union(parts)
    geo_network=unary_union(geo_parts)
    geodesic_length=sum(abs(geodesic.geometry_length(g)) for g in line_parts(geo_network))
    if geodesic_length and abs(network.length/geodesic_length-1) > .005:
        raise Blocked('Projected/geodesic road length discrepancy exceeds 0.5%')
    return network,len(feats)


def flood_footprint(source, geographic, county, to_local, roads):
    params={'where':'1=1',**spatial_filter(geographic),
            'outFields':'OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF','outSR':4326}
    feats=source.arcgis(FEMA_NFHL+'/28/query',params,batch_size=20)
    mapped=[]
    special=[]
    coastal=[]
    zone_counts=Counter()
    excluded=[]
    for feature in feats:
        attrs=feature['attributes']
        zone=str(attrs.get('FLD_ZONE') or '').upper()
        subtype=str(attrs.get('ZONE_SUBTY') or '').upper()
        zone_counts[zone or 'MISSING_ZONE']+=1
        geographic_polygon=feature.get('_shape_wgs84')
        if geographic_polygon is None:
            geographic_polygon=polygon_from_esri(feature['geometry'])
        polygon=transform(to_local.transform,geographic_polygon).intersection(county)
        if not polygon.is_valid:
            raise Blocked('Invalid NFHL polygon')
        # Zone D is undetermined; absence and excluded mapping areas are unknown.
        if not zone or zone=='D' or 'NOT INCLUDED' in subtype or 'UNMAPPED' in subtype:
            excluded.append(polygon)
            continue
        mapped.append(polygon)
        if attrs.get('SFHA_TF')=='T':
            special.append(polygon)
            if zone.startswith('V'):
                coastal.append(polygon)
    mapped=unary_union(mapped)
    unknown_geometry=roads.difference(mapped)
    unknown=unknown_geometry.length
    if unknown > .01:
        excluded_geometry=unary_union(excluded)
        raise CoverageBlocked(f'NFHL missing/unmapped/undetermined coverage on {unknown/MILE:.6f} road miles', {
            'hazard':'flood','total_road_miles':roads.length/MILE,
            'mapped_road_miles':roads.intersection(mapped).length/MILE,
            'unknown_road_miles':unknown/MILE,
            'explicitly_undetermined_or_unmapped_road_miles':unknown_geometry.intersection(excluded_geometry).length/MILE,
            'outside_any_returned_zone_road_miles':unknown_geometry.difference(excluded_geometry).length/MILE,
            'returned_zone_counts':dict(zone_counts),
            'unknown_road_bounds_in_analysis_crs':list(unknown_geometry.bounds),
            'interpretation':'Unknown source coverage; not measured zero exposure. Reconcile spatial source IDs before attributing cause.'})
    return unary_union(special),{'sfha_features_returned':len(special),
           'all_zone_features_returned':len(feats),'unknown_road_miles':unknown/MILE,
           've_geometry':unary_union(coastal)}


def whp_footprint(source, county, roads, crs):
    meta=source.get(WHP,{'f':'json'})
    if '2023' not in meta.get('description','') or meta.get('pixelType')!='U8':
        raise Blocked('Unexpected WHP source version/type')
    to_web=Transformer.from_crs(crs,3857,always_xy=True)
    to_local=Transformer.from_crs(3857,crs,always_xy=True)
    web_roads=transform(to_web.transform,roads)
    pixel=float(meta['pixelSizeX'])
    ox,oy=meta['extent']['xmin'],meta['extent']['ymax']
    bounds=web_roads.bounds
    # Globally fixed tiles are shared by adjacent counties and entire states.
    left=math.floor((math.floor((bounds[0]-ox)/pixel)-1)/512)*512
    right=math.ceil((math.ceil((bounds[2]-ox)/pixel)+1)/512)*512
    top=math.floor((math.floor((oy-bounds[3])/pixel)-1)/512)*512
    bottom=math.ceil((math.ceil((oy-bounds[1])/pixel)+1)/512)*512
    groups={code:[] for code in CLASSES}
    hashes=[]
    for x in range(left,right,512):
        for y in range(top,bottom,512):
            width,height=min(512,right-x),min(512,bottom-y)
            bbox=(ox+x*pixel,oy-(y+height)*pixel,ox+(x+width)*pixel,oy-y*pixel)
            if not web_roads.intersects(box(*bbox)):
                continue
            params={'bbox':','.join(map(str,bbox)),'bboxSR':3857,'imageSR':3857,
                    'size':f'{width},{height}','format':'tiff','pixelType':'U8',
                    'interpolation':'RSP_NearestNeighbor','renderingRule':json.dumps({'rasterFunction':'None'}),'f':'image'}
            raw=source.get(WHP+'/exportImage',params,binary=True)
            hashes.append(hashlib.sha256(raw).hexdigest())
            with MemoryFile(raw) as memory, memory.open() as dataset:
                if dataset.count!=1 or dataset.crs.to_epsg()!=3857 or (dataset.width,dataset.height)!=(width,height):
                    raise Blocked('Unexpected WHP tile grid')
                if not np.allclose(dataset.transform[:6],(pixel,0,bbox[0],0,-pixel,bbox[3]),atol=1e-6):
                    raise Blocked('WHP tile is not aligned to the native grid')
                cells=dataset.read(1)
                valid=np.isin(cells,list(CLASSES))
                if not np.isin(cells,[*CLASSES,255]).all():
                    raise Blocked('Unknown WHP class code')
                for geometry,code in shapes(cells,mask=valid,transform=dataset.transform):
                    groups[int(code)].append(transform(to_local.transform,shape(geometry).segmentize(27)))
    grids={code:unary_union(parts) for code,parts in groups.items()}
    known=unary_union(list(grids.values()))
    unknown=roads.difference(known).length
    if unknown>.01:
        raise Blocked(f'WHP NoData/unavailable coverage on {unknown/MILE:.6f} road miles')
    lengths={CLASSES[k]:roads.intersection(g).length/MILE for k,g in grids.items()}
    if abs(sum(lengths.values())-roads.length/MILE)>1e-5:
        raise Blocked('WHP class partition failed')
    return grids[4].union(grids[5]),{'whp_class_major_road_miles':lengths,
           'whp_nodata_major_road_miles':unknown/MILE,'raster_audit':{'tile_sha256':hashes,'source_resolution_metres':270}}


def traffic(source, geoid, county, footprint, roads, exposed, to_local):
    if exposed.length==0:
        return None,None,0,0
    where=f'stateid={int(geoid[:2])} AND county_id={int(geoid[2:])} AND f_system <= 4'
    count=source.get(HPMS_2024,{'$select':'count(*) AS n','$where':where})
    expected=int(count[0]['n'])
    rows=[]
    for offset in range(0,expected,5000):
        page=source.get(HPMS_2024,{'$select':':id,aadt,line','$where':where,'$order':':id','$limit':5000,'$offset':offset})
        if not isinstance(page,list):
            raise Blocked('Invalid HPMS response')
        rows.extend(page)
    if len(rows)!=expected or len({r.get(':id') for r in rows})!=expected:
        raise Blocked('Incomplete or duplicate HPMS records')
    weighted=length=0.0
    pieces=[]
    missing=0
    buffer=roads.buffer(25)
    prepared_county,prepared_footprint,prepared_buffer=prep(county),prep(footprint),prep(buffer)
    for row in rows:
        try:
            aadt=float(row['aadt'])
            line=shape(row['line'])
            if not math.isfinite(aadt) or aadt<0 or line.is_empty or not line.is_valid:
                raise ValueError('invalid HPMS input')
        except (KeyError,TypeError,ValueError):
            missing+=1
            continue
        local_line=transform(to_local.transform,line)
        if not prepared_county.intersects(local_line) or not prepared_footprint.intersects(local_line) or not prepared_buffer.intersects(local_line):
            continue
        piece=local_line.intersection(county).intersection(footprint).intersection(buffer)
        weighted+=aadt*piece.length
        length+=piece.length
        pieces.append(piece)
    covered=exposed.intersection(unary_union(pieces).buffer(25)).length
    return weighted/length if length else None,100*covered/exposed.length,len(rows),missing


def calculate(source, entry, hazard, frequencies):
    geoid=entry['geoid']
    field='WFIR_AFREQ' if hazard=='wildfire' else 'IFLD_AFREQ'
    value=frequencies.get(geoid,{}).get(field)
    if value is None or not math.isfinite(float(value)) or float(value)<0:
        raise Blocked(f'Missing/invalid FEMA {field}; not replaced with zero')
    value=float(value)
    population=[float(a[field]) for a in frequencies.values() if a.get(field) is not None and
                math.isfinite(float(a[field])) and float(a[field])>=0]
    low,high=min(population),max(population)
    if high<=low or (hazard=='wildfire' and value>1):
        raise Blocked('Invalid national frequency range')
    boundary=source.arcgis(NATIONAL_COUNTIES,{'where':f"GEOID='{geoid}'",'outFields':'GEOID,NAME','outSR':4326})
    if len(boundary)!=1:
        raise Blocked('Expected one county boundary')
    geographic,county,crs,to_local=projected_county(boundary[0]['geometry'],geoid)
    roads,road_count=road_network(source,county,geographic,to_local)
    audit={}
    if roads.is_empty:
        footprint=unary_union([])
    elif hazard=='wildfire':
        footprint,audit=whp_footprint(source,county,roads,crs)
    else:
        footprint,audit=flood_footprint(source,geographic,county,to_local,roads)
    exposed=roads.intersection(footprint)
    traffic_error=None
    try:
        raw,coverage,hpms_count,missing=traffic(source,geoid,county,footprint,roads,exposed,to_local)
    except StorageBlocked:
        raise
    except Exception as exc:
        raw,coverage,hpms_count,missing=None,None,0,0
        traffic_error=str(exc)
    total,exposed_miles=roads.length/MILE,exposed.length/MILE
    ratio=exposed.length/roads.length if roads.length else None
    normalized=(value-low)/(high-low)
    status=('no_major_roads' if not total else 'zero_exposure_complete' if not exposed_miles
            else 'traffic_source_unavailable' if traffic_error else 'missing_traffic' if raw is None
            else 'traffic_coverage_incomplete' if coverage is None or coverage<99.999
            else 'national_consequence_rank_pending')
    result={'geoid':geoid,'county':entry['county'],'state':entry['state'],
            'hazard':'wildfire' if hazard=='wildfire' else 'inland_flood',
            'status':status,'analysis_date':date.today().isoformat(),'analysis_crs':crs.to_string(),
            'road_scope':'Census TIGERweb Major Roads (MTFCC S1100 + S1200 — MapServer layers 2 and 6)',
            'road_metric':'major-road exposure','hazard_footprint':'USDA Forest Service WHP 2023 classified cells: High (4) and Very High (5)' if hazard=='wildfire' else "FEMA NFHL Special Flood Hazard Area (SFHA_TF='T')",
            'annualized_frequency':value,'frequency_min_national':low,'frequency_max_national':high,
            'normalized_frequency':normalized,'total_major_road_miles':total,
            ('wildfire_exposed_major_road_miles' if hazard=='wildfire' else 'flood_exposed_major_road_miles'):exposed_miles if total else None,
            'transportation_exposure':ratio,'transportation_exposure_percent':ratio*100 if ratio is not None else None,
            'transportation_consequence_raw_aadt':raw,'transportation_consequence_normalized':None,
            'transportation_stress':0.0 if hazard=='wildfire' and total and not exposed_miles else None,
            'hpms_coverage_pct_of_exposed_length':coverage,
            'annualized_exposed_road_miles_per_year':value*exposed_miles if total else None,
            'annualized_relative_road_exposure':value*ratio if ratio is not None else None,
            'feature_counts':{'major_road_features_in_bbox':road_count,'hpms_features_returned':hpms_count,
                              'hpms_missing_geometry_or_aadt':missing,'national_counties_in_frequency_normalization':len(population)},
            'sources':{'county_and_roads':'U.S. Census Bureau TIGERweb','frequency':FEMA_NRI_COUNTIES,
                       'hpms_traffic':'FHWA Highway Performance Monitoring System 2024',
                       'wildfire_footprint' if hazard=='wildfire' else 'flood_footprint':WHP if hazard=='wildfire' else FEMA_NFHL},
            'interpretation':'Transportation exposure and traffic intensity indicators; not damage, closure, loss, or engineering risk.',
            'remaining_dependency':'National hazard-specific comparison and coverage verification required.'}
    if hazard=='wildfire':
        result.update(audit)
        result['method_version']=VERSION
        result['hazard_label']='High / Very High wildfire hazard potential'
        result['aadt_status']=('null_no_major_roads' if not total else
                               'null_confirmed_zero_exposure' if not exposed_miles else
                               'source_unavailable' if traffic_error else
                               'null_no_hpms_match' if raw is None else
                               'partial_coverage' if coverage is None or coverage<99.999 else 'available')
    else:
        result['annualized_relative_road_exposure_percent']=value*ratio*100 if ratio is not None else None
        result['ve_zone_exposed_miles']=roads.intersection(audit.get('ve_geometry',unary_union([]))).length/MILE
        result['ve_zone_exposed_pct_of_sfha_exposure']=100*result['ve_zone_exposed_miles']/exposed_miles if exposed_miles else None
    result['formulas']={'stress':'normalized_frequency × transportation_exposure × national hazard-specific exposed AADT percentile',
                        'exposure':'selected hazard-exposed major-road length ÷ total major-road length'}
    if traffic_error:
        result['qa_notes']=[f'HPMS source unavailable/incomplete: {traffic_error}']
    validate_result(result,hazard)
    return result


def validate_result(result,hazard):
    total=result['total_major_road_miles']
    exposed=result['wildfire_exposed_major_road_miles' if hazard=='wildfire' else 'flood_exposed_major_road_miles']
    if total<0 or (exposed is not None and not 0<=exposed<=total+1e-8):
        raise Blocked('Road length range validation failed')
    if not 0<=result['normalized_frequency']<=1:
        raise Blocked('Frequency range validation failed')
    raw=result['transportation_consequence_raw_aadt']
    if raw is not None and (not math.isfinite(raw) or raw<0):
        raise Blocked('Traffic validation failed')
    coverage=result.get('hpms_coverage_pct_of_exposed_length')
    if coverage is not None and not 0<=coverage<=100.000001:
        raise Blocked('Traffic coverage validation failed')
    if total and abs(result['transportation_exposure']-exposed/total)>1e-9:
        raise Blocked('Exposure ratio validation failed')


def ranks(values):
    """Average-tie rank; caller must guard the national eligible population."""
    if len(values)<2:
        return {}
    ordered=sorted(values.items(),key=lambda item:item[1])
    result={}
    i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][1]==ordered[i][1]:
            j+=1
        rank=(i+1+j)/2
        for geoid,_ in ordered[i:j]:
            result[geoid]=(rank-1)/(len(ordered)-1)
        i=j
    return result


def baseline_paths():
    return sorted((ROOT/'data/processed/counties').glob('24*.json'))+sorted((ROOT/'data/processed/wildfire/counties').glob('24*.json'))


def hashes(paths):
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def checkpoint_valid(prior, path, fingerprint, cache):
    if prior.get('fingerprint')!=fingerprint or not path.exists():
        return False
    if prior.get('output_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
        return False
    for key,expected in prior.get('source_requests',{}).items():
        try:
            raw=gzip.decompress((Path(cache)/key[:2]/(key+'.gz')).read_bytes())
            if hashlib.sha256(raw).hexdigest()!=expected:
                return False
        except (OSError,EOFError):
            return False
    return prior.get('status') in ('local_metrics_complete','traffic_coverage_incomplete','no_major_roads','zero_exposure_complete')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir',type=Path,default=ROOT/'data/cache/national-current')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data/processed/national-current')
    parser.add_argument('--hazard',choices=['flood','wildfire','both'],default='both')
    parser.add_argument('--county',action='append',help='Targeted retries; complete manifest is always reported')
    parser.add_argument('--reserve-mb',type=int,default=256,help='Minimum free cache disk space; must be at least 32 MiB')
    args=parser.parse_args()
    if args.reserve_mb<32:
        parser.error('Reserve must be at least 32 MiB')
    out=args.output_dir.resolve()
    if out== (ROOT/'data/processed').resolve() or any(out.is_relative_to(p.parent.resolve()) for p in baseline_paths()):
        parser.error('National output must be separate from existing Maryland directories')
    before=hashes(baseline_paths())
    # Small manifest requests can run before the larger per-county disk guard.
    source=Sources(args.cache_dir,32)
    out.mkdir(parents=True,exist_ok=True)
    run_lock=(out/'runner.lock').open('a')
    try:
        fcntl.flock(run_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise Blocked('Another national runner holds this output-directory lock')
    manifest_path=out/'manifest.json'
    vintage_path=out/'manifest-vintage.json'
    if manifest_path.exists() and vintage_path.exists() and json.loads(vintage_path.read_text()).get('service')==NATIONAL_COUNTIES:
        manifest=json.loads(manifest_path.read_text())
    else:
        counties=source.arcgis(NATIONAL_COUNTIES,{'where':'1=1','outFields':'GEOID,NAME,STATE','returnGeometry':'false'},geometry=False,batch_size=1000)
        manifest=[{'geoid':str(f['attributes']['GEOID']),'county':f['attributes']['NAME'],
                   'state':str(f['attributes']['STATE'])} for f in counties if str(f['attributes']['GEOID'])[:2] in STATE_CODES]
        if len(manifest)<3000 or len({m['geoid'] for m in manifest})!=len(manifest):
            raise Blocked('Invalid national county manifest')
        atomic_json(manifest_path,manifest)
        atomic_json(vintage_path,{'service':NATIONAL_COUNTIES,'metadata':source.get(NATIONAL_COUNTIES.rsplit('/query',1)[0],{'f':'json'})})
    nri=source.arcgis(FEMA_NRI_COUNTIES,{'where':'1=1','outFields':'STCOFIPS,STATE,IFLD_AFREQ,WFIR_AFREQ,NRI_VER'},geometry=False,batch_size=1000)
    frequencies={str(f['attributes']['STCOFIPS']):f['attributes'] for f in nri}
    if len(frequencies)!=len(nri):
        raise Blocked('Duplicate FEMA county GEOIDs')
    atomic_json(out/'source-snapshot.json',{'method':VERSION,'code_sha256':CODE_HASH,
                'nri_versions':sorted({str(a.get('NRI_VER')) for a in frequencies.values()}),
                'source_requests':source.requests,'scope':'50 states and DC; territories excluded explicitly',
                'missing_nri_geoids':sorted({m['geoid'] for m in manifest}-set(frequencies))})
    snapshot=digest([manifest,nri])
    source.reserve=args.reserve_mb*1024**2
    for entry in manifest:
        entry['state']=frequencies.get(entry['geoid'],{}).get('STATE') or entry['state']
    hazards=['wildfire','flood'] if args.hazard=='both' else [args.hazard]
    ledger_path=out/'checkpoints.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    expected_keys={h+':'+m['geoid'] for h in hazards for m in manifest}
    ledger={k:v for k,v in ledger.items() if k in expected_keys}
    resources=None
    endpoint_errors=Counter()
    endpoint_blockers={}
    for entry in sorted(manifest,key=lambda m:(not m['geoid'].startswith('24'),m['geoid'])):
        geoid=entry['geoid']
        for hazard in hazards:
            key=hazard+':'+geoid
            path=out/hazard/'counties'/f'{geoid}.json'
            fingerprint=digest([CODE_HASH,snapshot,entry,hazard])
            identity={'geoid':geoid,'hazard':hazard,'assessment_period':'current',
                      'method_version':VERSION,'source_fingerprint':digest(snapshot)}
            prior=ledger.get(key,{})
            if geoid.startswith('24'):
                existing=ROOT/'data/processed'/('wildfire/counties' if hazard=='wildfire' else 'counties')/f'{geoid}.json'
                result=json.loads(existing.read_text())
                validate_result(result,hazard)
                ledger[key]={'status':'maryland_preserved','baseline_sha256':before[str(existing)],'output':str(existing)}
                continue
            if args.county and geoid not in args.county:
                ledger.setdefault(key,{'status':'not_processed','reason':'Outside targeted retry'})
                continue
            if resources:
                if prior.get('status') not in ('local_metrics_complete','traffic_coverage_incomplete','no_major_roads','zero_exposure_complete'):
                    ledger[key]={'status':'not_processed_resource_blocker','reason':resources}
                continue
            if checkpoint_valid(prior,path,fingerprint,args.cache_dir):
                print(key,'checkpoint reused',flush=True)
                continue
            if hazard in endpoint_blockers:
                ledger[key]={'status':'not_processed_endpoint_blocker','reason':endpoint_blockers[hazard]}
                continue
            ledger[key]={'status':'running','fingerprint':fingerprint,'identity':identity}
            atomic_json(ledger_path,ledger)
            source.requests={}
            try:
                result=calculate(source,entry,hazard,frequencies)
                atomic_json(path,result)
                state=result['status']
                ledger[key]={'status':'local_metrics_complete' if state=='national_consequence_rank_pending' else state,
                             'identity':identity,
                             'fingerprint':fingerprint,'output':str(path),'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'source_requests':dict(source.requests),'traffic_coverage_pct':result.get('hpms_coverage_pct_of_exposed_length')}
                print(key,ledger[key]['status'],flush=True)
                endpoint_errors[hazard]=0
            except StorageBlocked as exc:
                resources=str(exc)
                ledger[key]={'status':'not_processed_resource_blocker','reason':resources,'fingerprint':fingerprint}
                print(key,resources,flush=True)
            except Exception as exc:
                details=getattr(exc,'diagnostics',None)
                ledger[key]={'status':'missing_hazard_coverage' if details else 'blocked_source_or_geometry',
                             'reason':str(exc),'fingerprint':fingerprint,'identity':identity}
                if details:
                    atomic_json(out/'diagnostics'/f'{geoid}-{hazard}-coverage.json',{'identity':identity,**details})
                print(key,'blocked:',str(exc),flush=True)
                if any(code in str(exc) for code in ('500','502','503','504','403','timed out')):
                    endpoint_errors[hazard]+=1
                    if endpoint_errors[hazard]>=3:
                        endpoint_blockers[hazard]='Repeated source endpoint failure; remaining counties were not tested: '+str(exc)
            atomic_json(ledger_path,ledger)
    atomic_json(ledger_path,ledger)
    comparisons={}
    coverage={}
    for hazard in hazards:
        available={}
        counts=Counter()
        for entry in manifest:
            geoid=entry['geoid']
            checkpoint=ledger.get(hazard+':'+geoid,{'status':'not_processed'})
            counts[checkpoint['status']]+=1
            path=(ROOT/'data/processed'/('wildfire/counties' if hazard=='wildfire' else 'counties')/f'{geoid}.json'
                  if geoid.startswith('24') else out/hazard/'counties'/f'{geoid}.json')
            if path.exists() and checkpoint.get('status') not in ('blocked_source_or_geometry','not_processed_resource_blocker','not_processed_endpoint_blocker','not_processed','running'):
                result=json.loads(path.read_text())
                raw=result.get('transportation_consequence_raw_aadt')
                if raw is not None:
                    available[geoid]=raw
        comparison=ranks(available)
        # Do not present available-only ranks as the required complete national comparison.
        complete=all(ledger.get(hazard+':'+m['geoid'],{}).get('status') in
                     ('local_metrics_complete','no_major_roads','zero_exposure_complete','maryland_preserved') for m in manifest)
        for geoid in available:
            if geoid.startswith('24'):
                baseline=json.loads((ROOT/'data/processed'/('wildfire/counties' if hazard=='wildfire' else 'counties')/f'{geoid}.json').read_text())
                # Preserve Maryland's observed averages, but unknown or partial
                # traffic completeness cannot unlock a complete national rank.
                if (baseline.get('hpms_coverage_pct_of_exposed_length') or 0)<99.999:
                    complete=False
        comparisons[hazard]={'complete_national_comparison':complete,'eligible_available_count':len(available),
                             'status':'complete' if complete and comparison else 'incomplete_not_publishable',
                             'average_tie_ranks':comparison,'formula':'(average rank - 1) / (N - 1)',
                             'zero_exposure_policy':'No exposed traffic average; null consequence. Excluded from consequence ranking.',
                             'rank_population':'Counties with measured non-null raw consequence; comparison is provisional until coverage gates pass.'}
        if complete and comparison:
            for geoid,rank in comparison.items():
                if geoid.startswith('24'):
                    continue
                path=out/hazard/'counties'/f'{geoid}.json'
                result=json.loads(path.read_text())
                result['transportation_consequence_normalized']=rank
                result['transportation_stress']=result['normalized_frequency']*result['transportation_exposure']*rank
                result['status']='complete'
                result['remaining_dependency']='None.'
                atomic_json(path,result)
                ledger[hazard+':'+geoid]['output_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        coverage[hazard]={'expected_county_equivalents':len(manifest),'status_counts':dict(counts),
                          'national_comparison_complete':complete,'full_nationwide_coverage':False}
    assert hashes(baseline_paths())==before,'Maryland outputs changed'
    atomic_json(out/'national-comparisons.json',comparisons)
    atomic_json(ledger_path,ledger)
    atomic_json(out/'run-report.json',{'method':VERSION,'coverage':coverage,'resource_blocker':resources,
                'maryland_files_unchanged':True,'maryland_validation':'Existing numeric contracts verified; independent source replay reported separately.',
                'endpoint_blockers':endpoint_blockers,
                'blocked_counties':{k:v for k,v in ledger.items() if v['status'] in ('blocked_source_or_geometry','not_processed_resource_blocker','not_processed_endpoint_blocker')},
                'not_processed':[k for k,v in ledger.items() if v['status']=='not_processed'],
                'staging_only':True,'historical_audit_used':False})
    print(json.dumps(coverage,indent=2),flush=True)
    return 1 if resources or endpoint_blockers or any(v['status'] in ('blocked_source_or_geometry','not_processed_resource_blocker','traffic_coverage_incomplete') for v in ledger.values()) else 0


if __name__=='__main__':
    raise SystemExit(main())
