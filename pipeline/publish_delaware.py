"""Publish reviewed current Delaware results locally; no uploads or GIS calls.

Never publishes benchmark files implicitly. Requires a separate QA report bound
to the exact county bytes and explicit validation of the declared methodology.
"""
import argparse
import hashlib
import json
from pathlib import Path
from config import ROOT
from process_national_assessment import atomic_bytes, atomic_json, validate_result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--county-file',type=Path,required=True)
    parser.add_argument('--qa-report',type=Path,required=True)
    args=parser.parse_args()
    raw=args.county_file.read_bytes()
    result=json.loads(raw)
    qa=json.loads(args.qa_report.read_text())
    geoid=result.get('geoid')
    if geoid not in ('10001','10003','10005'):
        raise SystemExit('Only current Delaware county equivalents may be published by this command')
    hazard='wildfire' if result.get('hazard')=='wildfire' else 'flood' if result.get('hazard')=='inland_flood' else None
    checksum=hashlib.sha256(raw).hexdigest()
    required=('geometry','source_coverage','traffic_semantics','maryland_regression','methodology')
    if (not hazard or qa.get('validation_status')!='validated' or qa.get('assessment_period')!='current'
        or qa.get('geoid')!=geoid or qa.get('hazard')!=hazard or qa.get('sha256')!=checksum
        or any(qa.get('checks',{}).get(check) is not True for check in required)):
        raise SystemExit('Missing or mismatched QA evidence; benchmark result remains unpublished')
    validate_result(result,hazard)
    if result.get('transportation_stress') is not None and result.get('status')!='zero_exposure_complete':
        raise SystemExit('National final ranks are not ready; a positive-exposure stress score cannot be published')
    target=ROOT/'data/processed/assessments/current'/hazard/'counties'/f'{geoid}.json'
    index_path=ROOT/'data/processed/assessment-publications.json'
    import fcntl
    lock_path=ROOT/'data/processed/assessment-publications.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        index=json.loads(index_path.read_text()) if index_path.exists() else {}
        atomic_bytes(target,raw)
        index[f'current:{hazard}:{geoid}']={'validation_status':'validated','sha256':checksum,
            'qa_report_sha256':hashlib.sha256(args.qa_report.read_bytes()).hexdigest(),
            'assessment_period':'current','method_version':result.get('method_version'),
            'status':result['status']}
        atomic_json(index_path,index)
    print('Published reviewed Delaware county locally:',target)


if __name__=='__main__':
    main()
