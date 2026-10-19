"""Render an independent Ohio stop schedule and scoped IAM policies; no AWS calls.

After an authorized launch, supply its real boot/launch time and identifiers.
The generated files must be reviewed and applied separately before processing.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re


def prepare(instance_id, account_id, role_name, boot_time):
    if not re.fullmatch(r'i-[0-9a-f]{8,17}', instance_id):
        raise ValueError('Expected an actual EC2 instance ID')
    if not re.fullmatch(r'\d{12}', account_id) or not re.fullmatch(r'[\w+=,.@-]{1,64}', role_name):
        raise ValueError('Invalid project identifier or role name')
    boot = datetime.fromisoformat(boot_time.replace('Z', '+00:00'))
    if boot.tzinfo is None:
        raise ValueError('Boot time must include a timezone')
    # The guest timer starts shutdown at 2h, with 90s checkpoint grace. The
    # independent AWS control-plane stop begins at 2h03m if the guest hangs.
    deadline = (boot + timedelta(hours=2, minutes=3)).astimezone(timezone.utc)
    instance_arn = f'arn:aws:ec2:us-east-2:{account_id}:instance/{instance_id}'
    trust = {'Version': '2012-10-17', 'Statement': [{
        'Effect': 'Allow', 'Principal': {'Service': 'scheduler.amazonaws.com'},
        'Action': 'sts:AssumeRole', 'Condition': {
            'StringEquals': {'aws:SourceAccount': account_id},
            'ArnEquals': {'aws:SourceArn': f'arn:aws:scheduler:us-east-2:{account_id}:schedule-group/default'}}}]}
    policy = {'Version': '2012-10-17', 'Statement': [{
        'Effect': 'Allow', 'Action': 'ec2:StopInstances', 'Resource': instance_arn}]}
    schedule = {
        'Name': f'climate-stop-{instance_id}', 'GroupName': 'default',
        'ScheduleExpression': 'at(' + deadline.strftime('%Y-%m-%dT%H:%M:%S') + ')',
        'ScheduleExpressionTimezone': 'UTC', 'FlexibleTimeWindow': {'Mode': 'OFF'},
        'ActionAfterCompletion': 'DELETE', 'State': 'ENABLED',
        'Target': {'Arn': 'arn:aws:scheduler:::aws-sdk:ec2:stopInstances',
                   'RoleArn': f'arn:aws:iam::{account_id}:role/{role_name}',
                   'Input': json.dumps({'InstanceIds': [instance_id]}),
                   'RetryPolicy': {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 1}}}
    return {'trust-policy': trust, 'stop-policy': policy, 'stop-schedule': schedule}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('instance-id', 'account-id', 'role-name', 'boot-time'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    payloads = prepare(args.instance_id, args.account_id, args.role_name, args.boot_time)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = args.output_dir / (name + '.json')
        if path.exists():
            raise SystemExit(f'Refusing to overwrite an existing plan: {path}')
        path.write_text(json.dumps(payload, indent=2) + '\n')
    print('Prepared files only. No IAM role, schedule, instance, or job created.')
