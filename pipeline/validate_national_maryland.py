"""Replay the existing WHP source snapshot read-only; validate flood contracts.

Does not refresh sources, write caches, or modify Maryland output files.
Flood footprint/source replay is explicitly separate from contract validation.
"""
import hashlib
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import process_maryland_wildfire as wildfire
from config import CACHE, ROOT
from process_national_assessment import atomic_json, baseline_paths, hashes, validate_result


def cached_only(source, county, url, params):
    signature=hashlib.sha256(json.dumps([url,params],sort_keys=True).encode()).hexdigest()
    path=CACHE/'wildfire'/source/'24'/county/f'{signature}.json'
    if not path.exists():
        raise RuntimeError(f'Missing frozen Maryland request: {path}')
    return json.loads(path.read_text())


def no_download(*args,**kwargs):
    raise RuntimeError('Maryland validation is read-only; missing source cache')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geoid',choices=[geoid for geoid,_ in wildfire.MARYLAND_COUNTIES],
                        help='Read-only regression for one saved Maryland county')
    args=parser.parse_args()
    before=hashes(baseline_paths())
    checks=[]
    metadata=json.loads(next((CACHE/'wildfire/whp2023/24/metadata').glob('*.json')).read_text())
    with patch.object(wildfire,'cached_json',cached_only),patch.object(wildfire,'download',no_download),patch.object(wildfire,'atomic_json',no_download):
        frequencies=wildfire.national_frequency()
        for geoid,name in wildfire.MARYLAND_COUNTIES:
            if args.geoid and geoid!=args.geoid:
                continue
            stored=json.loads((wildfire.OUT/f'{geoid}.json').read_text())
            calculated=wildfire.calculate(geoid,name,frequencies,metadata)
            fields=('annualized_frequency','normalized_frequency','total_major_road_miles',
                    'wildfire_exposed_major_road_miles','transportation_exposure',
                    'transportation_consequence_raw_aadt','hpms_coverage_pct_of_exposed_length',
                    'transportation_stress')
            differences={}
            for field in fields:
                a,b=stored[field],calculated[field]
                if a is None or b is None:
                    assert a==b,(geoid,field,a,b)
                else:
                    differences[field]=abs(a-b)
                    assert abs(a-b)<=1e-8,(geoid,field,a,b)
            assert stored['whp_class_major_road_miles']==calculated['whp_class_major_road_miles'],geoid
            flood=json.loads((ROOT/'data/processed/counties'/f'{geoid}.json').read_text())
            validate_result(flood,'flood')
            road_difference=abs(flood['total_major_road_miles']-calculated['total_major_road_miles'])
            checks.append({'geoid':geoid,'wildfire_frozen_source_replay_passed':True,
                           'flood_contract_passed':True,'shared_road_total_difference_miles':road_difference,
                           'shared_road_total_matches':road_difference<1e-5,'absolute_differences':differences})
            print(geoid,'Maryland baseline validated',flush=True)
    assert hashes(baseline_paths())==before
    report={'passed':True,'county_count':len(checks),'maryland_sha256_unchanged':True,
            'wildfire_validation':f'Actual frozen road/raster/frequency/traffic requests replayed for {len(checks)} selected counties.',
            'flood_validation':'Existing contracts checked and road total differences recorded against the wildfire replay. Existing flood/wildfire road totals differ in some counties; neither baseline was changed. Flood hazard/AADT source caches are absent; full flood-source recomputation has not been performed.',
            'checks':checks,'baseline_hashes':before}
    filename=f'maryland-validation-{args.geoid}.json' if args.geoid else 'maryland-validation.json'
    atomic_json(ROOT/'data/processed/national-current'/filename,report)


if __name__=='__main__':
    main()
