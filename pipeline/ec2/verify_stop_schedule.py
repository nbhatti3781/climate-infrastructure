"""Read-only AWS verification; run with the local CLI after approved launch.

Writes evidence only after the live schedule and persistent volume checks pass.
This is not the disconnect/restart test; those still require separate evidence.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from prepare_shutdown import prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance-id',required=True)
    parser.add_argument('--profile',default='climate-infrastructure')
    parser.add_argument('--role-name',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    def aws(*words):
        command=['aws',*words,'--profile',args.profile,'--region','us-east-2','--output','json']
        return json.loads(subprocess.check_output(command,text=True))
    identity=aws('sts','get-caller-identity')
    reservation=aws('ec2','describe-instances','--instance-ids',args.instance_id)
    instance=reservation['Reservations'][0]['Instances'][0]
    assert instance['State']['Name']=='running','Instance must be running for preflight'
    expected=prepare(args.instance_id,identity['Account'],args.role_name,instance['LaunchTime'])
    schedule=aws('scheduler','get-schedule','--name',expected['stop-schedule']['Name'],'--group-name','default')
    for key in ('ScheduleExpression','ScheduleExpressionTimezone','State','FlexibleTimeWindow'):
        assert schedule[key]==expected['stop-schedule'][key],f'Schedule {key} mismatch'
    for key in ('Arn','RoleArn','RetryPolicy'):
        assert schedule['Target'][key]==expected['stop-schedule']['Target'][key],f'Target {key} mismatch'
    assert json.loads(schedule['Target']['Input'])=={'InstanceIds':[args.instance_id]}
    deadline=datetime.fromisoformat(instance['LaunchTime'].replace('Z','+00:00'))+timedelta(hours=2,minutes=3)
    assert datetime.now(timezone.utc)<deadline,'Stop deadline has already passed'
    behavior=aws('ec2','describe-instance-attribute','--instance-id',args.instance_id,'--attribute','instanceInitiatedShutdownBehavior')
    assert behavior['InstanceInitiatedShutdownBehavior']['Value']=='stop'
    assert instance['MetadataOptions']['HttpTokens']=='required'
    root=next(b['Ebs'] for b in instance['BlockDeviceMappings'] if b['DeviceName']==instance['RootDeviceName'])
    assert root['DeleteOnTermination'] is False,'Root volume must be retained'
    volume=aws('ec2','describe-volumes','--volume-ids',root['VolumeId'])['Volumes'][0]
    assert volume['Encrypted'] and volume['VolumeType']=='gp3' and volume['Size']==100
    assert volume['Iops']==3000 and volume['Throughput']==125
    role_policy=aws('iam','get-role-policy','--role-name',args.role_name,'--policy-name','climate-benchmark-stop')
    assert role_policy['PolicyDocument']==expected['stop-policy'],'Stop permission mismatch'
    role=aws('iam','get-role','--role-name',args.role_name)['Role']
    assert role['AssumeRolePolicyDocument']==expected['trust-policy'],'Scheduler trust policy mismatch'
    evidence={'verified_at':datetime.now(timezone.utc).isoformat(),'instance_id':args.instance_id,
              'region':'us-east-2','launch_time':instance['LaunchTime'],'schedule_arn':schedule['Arn'],
              'deadline':deadline.isoformat(),'volume_id':root['VolumeId'],
              'verified':True,'disconnect_survival_verified':False,'restart_persistence_verified':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    print('Read-only stop/storage preflight passed. Disconnect and restart verification still pending.')


if __name__=='__main__':
    main()
