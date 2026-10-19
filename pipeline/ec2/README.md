# Delaware benchmark prelaunch plan

Prepared October 18, 2026. Nothing in this directory has been deployed. No EC2
instance, shutdown timer, or assessment job has been started. Nationwide
processing is out of scope for this benchmark.

## Verified AWS state

- Profile `climate-infrastructure`; project Region `us-east-2` (Ohio).
- Project plan ACTIVE FREE, USD 100 remaining credit reported by Free Tier API.
- Standard On-Demand quota: 32 vCPUs. Both candidate sizes offered in Ohio.
- `m7i.xlarge`: 4 vCPU / 16 GiB; `FreeTierEligible=false`. Do not assume the
  current Free plan permits launching it; resolve eligibility before launch.
- `m7i-flex.large`: 2 vCPU / 8 GiB; `FreeTierEligible=true`. Its RAM sufficiency
  for this GIS benchmark remains untested. Do not upgrade the plan silently.
- Toolkit remote catalog query succeeded. Codex and Kiro MCP configuration points
  at `https://aws-mcp.us-east-1.api.aws/mcp` with
  `AWS_MCP_PROXY_PROFILES=climate-infrastructure`. Live MCP tool invocation is
  pending a coding-tool restart; this session exposes no AWS MCP tools.

The toolkit catalog/MCP endpoint is currently hosted in `us-east-1`, as required
by the [AWS setup instructions](https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md).
The read-only Price List API also uses a supported pricing endpoint there;
queries explicitly select Ohio prices. Neither call creates regional workload
resources. EC2, EBS and any future workload resources stay in `us-east-2`.

To use another project later, authenticate its named profile, add that profile
to the space-separated `AWS_MCP_PROXY_PROFILES` list, then restart the coding tool.
Do not copy local browser-session credentials to EC2.

## Proposed storage and network

Use an official Ubuntu 24.04 LTS x86_64 EBS-backed AMI (not Ubuntu Pro). One
**100 GiB encrypted gp3 root volume**, **3,000 IOPS / 125 MiB/s**, with
**DeleteOnTermination=false** and instance-initiated shutdown behavior explicitly
set to **stop**. Use the AWS-managed EBS key; no extra customer KMS key or snapshot.
Set IMDSv2 required, hop limit 1 for this host workload. Use a least-privilege
SSM instance profile and Session Manager, without inbound SSH rules. The cost
scenario assumes one auto-assigned public IPv4 with internet egress through an
internet gateway, no Elastic IP, NAT gateway, paid VPC endpoint, load balancer,
detailed monitoring or CloudWatch/S3 log export. Basic SSM access only.

Keep the entire transferred repository at `/srv/climate-assessment`, owned by
`ubuntu`, on that EBS filesystem:

| Content | Persistent path below repository |
|---|---|
| Shared source cache | `data/cache/national-current/` |
| Existing Maryland/cache snapshots | Original transferred paths |
| County outputs and checkpoints | `data/processed/national-current/benchmarks/10/` |
| Run/resource logs | `data/benchmark-logs/` |

No filesystem formatting, cache deletion, schema changes, hazard-method edits or
Maryland output replacement is performed by these scripts. Retention protects
against EC2 stop and termination, but is not a separate disaster-recovery backup.
Download outputs/checkpoints and record hashes before any later volume deletion.
Uncommitted files, the frozen manifest, and ignored caches must be transferred
from this Mac: a fresh GitHub clone alone is insufficient. No push is authorized.

## Costs before credits and tax

Prices checked October 18, 2026. Deterministic calculations are saved in
`benchmark-cost-estimate.json`. Storage hourly equivalents use 730 hours/month.

| Item | 16 GiB option: m7i.xlarge | 8 GiB option: m7i-flex.large |
|---|---:|---:|
| Linux On-Demand compute/hour | $0.20160 | $0.09576 |
| 100 GiB gp3/hour equivalent | $0.01096 | $0.01096 |
| One public IPv4/hour | $0.00500 | $0.00500 |
| Combined/hour | $0.21756 | $0.11172 |
| Two-hour scenario | **$0.43512** | **$0.22344** |
| Two hours plus five minutes for shutdown | $0.45325 | $0.23275 |
| Above plus $0.09 allowance for 1 GB paid internet egress | **$0.54325** | **$0.32275** |

Internet source downloads are inbound; no paid source subscriptions are assumed.
Result downloads can incur egress beyond applicable free allowances. The $0.09
line is an allowance, not a measured transfer charge or spending cap. Keep result
downloads small and verify pricing before transferring larger data. No S3,
snapshot, NAT, extra IOPS/throughput or paid log service is included because none
is proposed. Retained EBS continues at **$8/month**, about **$0.263/day**, even
when the instance is stopped; elapsed retention must be added to the scenario.
Credits may offset eligible usage but are not deducted from these estimates.
These are duration scenarios, not completion-time predictions or hard bill caps.

Sources:
- [Ohio public compute price list](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20%28Ohio%29/Linux/index.json)
- AWS Price List API `AmazonEC2`, `regionCode=us-east-2`, `volumeApiName=gp3`,
  `productFamily=Storage`: $0.08/GB-month, verified in this session.
- [EBS pricing](https://aws.amazon.com/ebs/pricing/)
- [Public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)

## Installation and start/resume (future approved EC2 only)

Prerequisites: transfer the saved working tree and manifest/caches; install
Python 3.12, python3-venv, time, curl and Ubuntu GIS prerequisites as needed.
Create `.venv-wildfire` and install `pipeline/requirements-wildfire.txt`. Existing
pins use shapely, pyproj and rasterio binary distributions. Installation of the
Python/system environment is not automated by the service installer below.
Confirm EBS, shutdown behavior, networking, instance eligibility and the 5 GiB
disk reserve before executing any start command.

```bash
cd /srv/climate-assessment
sudo bash pipeline/ec2/install-benchmark-services.sh
sudo systemctl enable --now climate-benchmark-stop.timer
sudo systemctl list-timers climate-benchmark-stop.timer
```

The enabled system timer uses `OnBootSec=2h`, `AccuracySec=1s`, with no random
delay. Arm it as early as prerequisites permit, before testing or processing.
If armed more than two hours after boot it fires immediately. At the deadline
it stops the benchmark (SIGINT, up to 90 seconds grace), syncs disk, and requests
`systemctl poweroff`. EC2 shutdown behavior **must be stop**, never terminate.
No instance-role stop permission is required by this OS shutdown mechanism.
The timer and job are owned by the system manager, independent of SSH/SSM shells.
The benchmark is not enabled for automatic startup after reboot; its stop timer
is. A stopped instance can be restarted later; the deadline then uses that boot.

One command to start or resume the same Delaware run after validation:

```bash
sudo systemctl start climate-delaware-benchmark.service
```

The command is fixed to `--state 10 --benchmark --workers 2 --reserve-mb 5120`;
there is no nationwide or Maryland option. Existing checkpoint hashes determine
reuse. `/usr/bin/time -v` logs resource use. A failed job is not restarted in a
loop; inspect the persistent log before retrying. While the timer still fires
after early completion/failure, the operator may stop EC2 earlier to save compute.
An unhealthy OS can defeat an in-guest timer. The independent AWS-side control
below is now prepared, but has not been configured or tested against a live
instance. Neither mechanism is a guaranteed monetary billing cap.

## Validation gates before assessment processing

1. Run the installer on Ubuntu: it runs `systemd-analyze verify`. On the Mac,
   only shell syntax and non-Linux guards have been tested; no Linux runtime
   success is claimed.
2. Confirm stop behavior and retained encrypted gp3 settings through the EC2
   control plane. Record the volume ID, instance ID and boot time.
3. Run `sudo bash pipeline/ec2/disconnect-smoke-test.sh`, disconnect SSH/SSM,
   wait at least 30 seconds, reconnect. Heartbeat timestamps must span the
   disconnected interval. This is explicitly synthetic orchestration evidence,
   not hazard output. The test is not yet executed.
4. Start the Delaware service, record `systemctl show
   climate-delaware-benchmark.service -p MainPID -p ActiveState`, disconnect,
   reconnect and confirm the same active PID plus advancing logs, or a clean
   completed result. If it finishes before reconnect, inspect exit status and
   durable output timestamps instead. This actual-job check remains pending.
5. Verify the timer initiates shutdown at the deadline; externally confirm EC2
   state `stopped`. After a deliberate restart, verify checkpoint/output hashes,
   parse all saved JSON and compare Maryland hashes. A stop during an incomplete
   county may discard that county's in-memory work; prior atomic outputs and
   checkpoints remain. Repeat source requests should reuse compatible caches.

Live disconnect survival, two-hour EC2 shutdown, persistence after restart and
benchmark peak resources are **not yet verified**, because no EC2 launch has
been authorized/performed. Existing Delaware flood missing/unmapped coverage is
still a data blocker; it cannot become measured zero. National final comparisons
and the full-state orchestration still require later work.

## Updated approval proposal: laptop-independent Delaware run

The candidate matching the current Free plan is **one m7i-flex.large (2 vCPU,
8 GiB)**, Ubuntu 24.04 LTS, the 100 GiB retained encrypted gp3 configuration
above, one auto-assigned IPv4, SSM-only access, two download workers and one
county calculation at a time. It remains an experiment: if it exceeds RAM or
source coverage fails, report the blocker; do not automatically resize or loop.
Use existing Ohio VPC/subnet/internet gateway if suitable; do not add NAT or paid
endpoints. Prepare the SSM instance profile and no-ingress security group only
after approval. IAM roles/profile have no separate hourly charge. No billable
resource or IAM role is created by any preparation command run so far.

**Proposed allowance: $1 before credits/tax**, covering one benchmark, five
minutes stop overhead, at most 1 GB paid result egress, two scheduler invocation
allowances and an additional 24 hours retained storage. Calculated 8 GiB
scenario: **$0.586**; 16 GiB scenario: **$0.806**, although that type is not
currently Free Tier eligible. Storage beyond this period and data egress beyond
the allowance increase cost. This is a proposed ceiling, not an AWS-enforced
spending limit; neither credits nor budget alerts are a precise stop switch.
Scheduler invocation price allowance is $1/million before free allowances,
less than $0.00001 for this one-shot control ([AWS pricing](https://aws.amazon.com/eventbridge/pricing/)).

Two separate shutdown mechanisms are required before any processing:

1. System timer initiates a graceful stop at boot + 2 hours. SIGINT reaches
   both the resource monitor and Python process; checkpoint grace is 90 seconds.
2. EventBridge Scheduler in **Ohio** independently invokes EC2 StopInstances at
   actual instance launch/boot time + **2 hours 3 minutes**. This runs on AWS
   even if the laptop is off and the guest process/OS is hung. Flexible time
   window is OFF; retry age is 60 seconds with one retry. Scheduler has
   minute-level timing and EC2 stopping can take additional time: no strict
   second-level or dollar cap is claimed. Its role can stop only this specific
   instance; no termination permission. The schedule deletes itself after firing.

`prepare_shutdown.py` renders the trust policy, least-privilege stop policy and
schedule JSON locally. It makes no AWS calls. After an authorized launch, use
the **real** instance ID, project identifier, role name and `LaunchTime`; then
review/apply those files. Scope IAM `PassRole` to that execution role and
`scheduler.amazonaws.com`. The policy name used by the verification script is
`climate-benchmark-stop`. No schedule should be armed against a made-up ID.
Read back the live role/policy and schedule using `verify_stop_schedule.py`;
it also checks live retained encrypted gp3, shutdown behavior and IMDSv2.
Transfer its generated `external-stop-verification.json` into
`data/benchmark-logs/` on EC2. The benchmark service refuses an expired guard or
one from another boot. Rearm and verify a new schedule before restarting a
stopped instance for another benchmark session.

`setup-ubuntu.sh` installs Ubuntu/Python/GIS dependencies, the pinned virtual
environment and system services, then runs offline tests. It only runs on
Ubuntu 24.04 as root, requires the externally verified stop evidence, and starts
no assessment. Copy the repository without Mac `.venv*`, `node_modules`, `.next`,
credentials or shell profiles. Transfer caches separately and preserve paths;
do not copy local AWS login tokens to the instance. The saved manifest and
Maryland baseline are required. The bootstrap arms the guest timer before pip
installation. The independent cloud timer must be armed before bootstrapping.

The Ubuntu setup normalizes ownership of the transferred project and caches to
the `ubuntu` service user without following symlinks or changing file contents.
The repository root must not be a symlink. This prevents preserved Mac numeric
UIDs/root-owned extraction from making mode-0600 cache files unreadable remotely.
This ownership operation is Linux-only and has not been run on the Mac.

The smoke and actual-job tests above remain mandatory. **Do not tell the user
it is safe to close the laptop until those real remote tests pass.** Local
Codex and a local GIS process stop when the laptop sleeps or turns off. The
prepared remote systemd process is intended to continue independently; this
has not been demonstrated on an instance yet.

After Delaware validation, benchmark a small resolved sample from the frozen
inventory: a large western county, a coastal/tidal county, an inland county,
a Connecticut planning region and AK/HI coverage/antimeridian edge cases.
Unsupported coverage is a legitimate outcome, not zero. Do not extrapolate
Delaware timing alone, nor start national processing under this approval.

## Publication, export and finite completion

Keep all new county files in benchmark staging until separate QA is bound to
their exact SHA256. `pipeline/publish_delaware.py` requires current Delaware
geography/hazard, unchanged original county schema, explicit successful geometry,
source-coverage, traffic-semantics, Maryland-regression and methodology checks,
and matching file hash. It writes to the dashboard publication tree and index
atomically. Positive-exposure final stress scores are refused until national
normalization is ready; a null score can still accompany reviewed local metrics.
The dashboard reads only those publications, never the benchmark directory.
The UI lists reviewed Delaware county/hazard entries explicitly; it does not
infer statewide completion. No Delaware result has been published yet.

`export_results.py` creates and verifies a portable ZIP of county outputs,
manifests, checkpoints, methodology/code and local logs, with per-file hashes and
a whole-archive SHA256. It excludes raw source caches, which remain on retained
EBS; preserve request/source fingerprints and transfer any necessary raw caches
separately. Copy the archive outside AWS, verify its hash and internal manifest,
and confirm the dashboard loads the copied publications before cleanup.
No export or outside-AWS copy of future benchmark results exists yet.

Current resources created for this task: **none**. Therefore there are no live
resource IDs for cleanup commands. After the approved run, record only actual
created IDs: verify off-instance export, stop the instance, and request approval
before deleting the retained EBS volume or any only copy. Remove only the
benchmark's own schedule, role policies/profile and security group after their
dependencies are gone; leave pre-existing network/resources untouched. Retained
storage charges continue until volume removal.
