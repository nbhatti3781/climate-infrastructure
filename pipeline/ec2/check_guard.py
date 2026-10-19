"""Refuse a benchmark if the external stop evidence is absent, stale or expired."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


def check(evidence, now, boot_time):
    if evidence.get('verified') is not True or evidence.get('region')!='us-east-2':
        raise ValueError('External Ohio stop/storage preflight is not verified')
    launch=datetime.fromisoformat(evidence['launch_time'].replace('Z','+00:00'))
    deadline=datetime.fromisoformat(evidence['deadline'].replace('Z','+00:00'))
    if abs((launch-boot_time).total_seconds())>300:
        raise ValueError('External stop evidence belongs to another boot; rearm and verify the schedule')
    if deadline<=now or deadline>launch+timedelta(hours=2,minutes=3):
        raise ValueError('Independent stop deadline is expired or too late')


if __name__=='__main__':
    evidence=json.loads(Path('data/benchmark-logs/external-stop-verification.json').read_text())
    now=datetime.now(timezone.utc)
    uptime=float(Path('/proc/uptime').read_text().split()[0])
    check(evidence,now,now-timedelta(seconds=uptime))
