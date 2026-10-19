"""Reviewed annual exposure/AADT stage, separate from current assessment.

Consumes hash-pinned, prepared annual GeoJSON inputs on a remote Linux host.
It does not manufacture annual hazard maps, frequency values or national ranks.
Actual source-to-GeoJSON adapters and scientific approval are prerequisites.
No annual input or approved method is supplied with this repository yet.
"""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import platform
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import unary_union
from process_national_assessment import ROOT, atomic_json, digest, transform

VERSION='reviewed-annual-exposure-aadt-v1'
MILE=1609.344


def verify_review(manifest):
    review=manifest.get('methodology_review',{})
    if review.get('status')!='approved' or not review.get('reference'):
        raise ValueError('Scientific review of the annual definition is required; current WHP/NFHL/NRI are not annual observations')
    for field in ('annual_hazard_definition','frequency_decision','road_scope','prescribed_fire_handling','coverage_definition'):
        if not review.get(field):
            raise ValueError('Missing reviewed decision: '+field)
    if review['road_scope']!='S1100+S1200':
        raise ValueError('This stage preserves the current selected-road scope; scope changes need separate implementation')


def load_input(asset,year,base):
    if asset.get('observation_year')!=year or asset.get('coverage_reviewed') is not True:
        raise ValueError('Input year/coverage not verified; no substitution from another year')
    path=(base/asset['file']).resolve()
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=asset['sha256']:
        raise ValueError('Annual input fingerprint mismatch: '+str(path))
    value=json.loads(raw)
    if value.get('type')!='FeatureCollection':
        raise ValueError('Prepared input must be a WGS84 GeoJSON FeatureCollection')
    if value.get('crs'):
        raise ValueError('Transform prepared inputs to WGS84; nonstandard GeoJSON CRS is not accepted')
    features=value['features']
    if any(not f.get('geometry') or not shape(f['geometry']).is_valid for f in features):
        raise ValueError('Missing/invalid geometry is not measured zero exposure')
    return features


def measure(roads,footprint,known_coverage,traffic):
    total=roads.length
    if total==0:
        return {'status':'no_selected_roads','total_major_road_miles':0.0,
                'exposed_road_miles':None,'transportation_exposure':None,
                'transportation_consequence_raw_aadt':None,'hpms_coverage_pct_of_exposed_length':None}
    unknown=roads.difference(known_coverage).length
    if unknown>.01:
        raise ValueError(f'Missing annual source coverage on {unknown/MILE:.6f} road miles')
    exposed=roads.intersection(footprint)
    if exposed.is_empty or exposed.length==0:
        return {'status':'verified_zero_selected_exposure','total_major_road_miles':total/MILE,
                'exposed_road_miles':0.0,'transportation_exposure':0.0,
                'transportation_consequence_raw_aadt':None,'hpms_coverage_pct_of_exposed_length':None}
    weighted=length=0.0
    pieces=[]
    missing=0
    for line,value in traffic:
        try:
            value=float(value)
        except (TypeError,ValueError):
            missing+=1; continue
        if not math.isfinite(value) or value<0:
            missing+=1; continue
        # Preserve the existing Maryland HPMS/road 25m spatial match operation.
        piece=line.intersection(footprint).intersection(roads.buffer(25))
        weighted+=value*piece.length
        length+=piece.length
        pieces.append(piece)
    raw=weighted/length if length else None
    coverage=100*exposed.intersection(unary_union(pieces).buffer(25)).length/exposed.length
    return {'status':'missing_traffic' if raw is None else 'partial_traffic' if coverage<99.999 else 'local_metrics_complete',
            'total_major_road_miles':total/MILE,'exposed_road_miles':exposed.length/MILE,
            'transportation_exposure':exposed.length/total,'transportation_consequence_raw_aadt':raw,
            'hpms_coverage_pct_of_exposed_length':coverage,'missing_or_invalid_aadt_records':missing}


def calculate(entry,base):
    year=entry['year'];geoid=entry['geoid']
    if year not in range(2021,2026) or geoid not in ('10001','10003','10005'):
        raise ValueError('Only the candidate annual Delaware scope is prepared')
    assets={name:load_input(entry['inputs'][name],year,base)
            for name in ('boundary','roads','hazard','known_coverage','traffic')}
    for name,features in assets.items():
        allowed=('LineString','MultiLineString') if name in ('roads','traffic') else ('Polygon','MultiPolygon')
        if any(f['geometry']['type'] not in allowed for f in features):
            raise ValueError('Wrong geometry type for '+name)
    boundary=unary_union([shape(f['geometry']) for f in assets['boundary']])
    if boundary.is_empty or boundary.bounds[2]-boundary.bounds[0]>180:
        raise ValueError('Missing boundary or unsupported antimeridian geometry')
    centre=boundary.centroid
    projection=Transformer.from_crs(4326,f'+proj=aeqd +lat_0={centre.y} +lon_0={centre.x} +datum=NAD83 +units=m',always_xy=True)
    county=transform(projection.transform,boundary)
    def local(features):
        return unary_union([transform(projection.transform,shape(f['geometry'])).intersection(county) for f in features])
    if any(f['properties'].get('MTFCC') not in ('S1100','S1200') for f in assets['roads']):
        raise ValueError('Prepared road input contains another road classification')
    roads=local(assets['roads'])
    traffic=[(transform(projection.transform,shape(f['geometry'])).intersection(county),f['properties'].get('AADT')) for f in assets['traffic']]
    result=measure(roads,local(assets['hazard']),local(assets['known_coverage']),traffic)
    return {'geoid':geoid,'year':year,'assessment_period':str(year),'hazard':entry['hazard'],
            'method_version':VERSION,'analysis_date':date.today().isoformat(),**result,
            'transportation_exposure_percent':100*result['transportation_exposure'] if result['transportation_exposure'] is not None else None,
            ('wildfire_exposed_major_road_miles' if entry['hazard']=='wildfire' else 'flood_exposed_major_road_miles'
             if entry['hazard']=='flood' else 'hazard_exposed_major_road_miles'):result['exposed_road_miles'],
            'road_scope':'S1100+S1200','road_length_unit':'miles','traffic_unit':'vehicles/day (AADT)',
            'annualized_frequency':None,'normalized_frequency':None,
            'transportation_consequence_normalized':None,'transportation_stress':None,
            'interpretation':'Reviewed annual exposure stage only; frequency and national normalization are not implemented.',
            'sources':{name:asset['sha256'] for name,asset in entry['inputs'].items()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    verify_review(manifest)
    if platform.system()!='Linux':
        raise SystemExit('Annual GIS execution is reserved for the approved remote Linux job')
    entries=manifest.get('entries',[])
    if not entries:
        raise SystemExit('No verified annual input entries; no calculations started')
    out=ROOT/'data/processed/historical-staging'
    ledger_path=out/'checkpoints.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    for entry in entries:
        if entry['hazard'] not in ('flood','wildfire','hurricane','compound'):
            raise ValueError('Unknown annual hazard')
        key=f"{entry['year']}:{entry['hazard']}:{entry['geoid']}"
        signature=digest([VERSION,Path(__file__).read_text(),manifest['methodology_review'],entry])
        path=out/str(entry['year'])/entry['hazard']/f"{entry['geoid']}.json"
        prior=ledger.get(key,{})
        if prior.get('signature')==signature and path.exists() and prior.get('sha256')==hashlib.sha256(path.read_bytes()).hexdigest():
            # Verify source bytes as well as their declared names/fingerprints.
            for asset in entry['inputs'].values(): load_input(asset,entry['year'],args.manifest.parent)
            continue
        try:
            result=calculate(entry,args.manifest.parent)
            atomic_json(path,result)
            ledger[key]={'signature':signature,'status':result['status'],
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        except Exception as exc:
            ledger[key]={'signature':signature,'status':'blocked','reason':str(exc)}
        atomic_json(ledger_path,ledger)
        print(key,ledger[key]['status'],flush=True)
    if any(v['status']=='blocked' for v in ledger.values()): raise SystemExit(1)


if __name__=='__main__':
    main()
