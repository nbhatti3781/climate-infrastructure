# Delaware benchmark: compact handoff

Last checked October 18, 2026. **Prepared, not launched.** No billable resources,
plan upgrade, nationwide run, push, or data/cache deletion performed.

## Saved changes and validation

- All **51** hashes in `data/cache/session-handoff/2026-10-07/preservation-baseline.json`
  match, including Maryland county files and the original inland-flood code.
- Howard County 24027 frozen-source wildfire replay passed with zero metric
  differences; flood contract and shared road total passed. Independent flood
  geometry/traffic replay remains unavailable because its old caches are absent.
  Report: `data/processed/national-current/maryland-validation-24027.json`.
- Saved state/national runners, caching/checkpoint identity, safe county writes,
  explicit missing/partial traffic status, and flood-coverage diagnostics.
  State NFHL selection now uses the county-style spatial query rather than a
  Delaware DFIRM_ID prefix alone. Old caches/checkpoints remain intact;
  incompatible fingerprints require recalculation.
- Saved period-aware dashboard/API/export filenames, no fallback from annual
  requests to the baseline, validated publication index, and Delaware publisher.
  Staged benchmark files remain excluded from dashboard publication.
- Six county API checks passed again: Maryland flood/wildfire response bodies
  unchanged, missing annual/Delaware results unavailable, invalid period rejected,
  and current-period export filename correct. Shell syntax and Python syntax
  checks passed. Earlier TypeScript/lint and pipeline regression checks passed.
- Remote setup, systemd service, guest stop timer, independent Scheduler plan,
  cloud preflight verifier, boot/expiry guard, disconnect test and checksum export
  are saved in `pipeline/ec2/`. Linux/cloud runtime tests remain pending.

## Actual Delaware coverage

- Kent (10001) and New Castle (10003): no completed outputs.
- Sussex (10005): previous experimental wildfire zero-exposure result; latest
  code/source selection validation pending. Flood previously blocked on 8.759185
  road miles with unknown coverage. The cached 11,657 map attributes were audited;
  possible adjoining-jurisdiction omissions need spatial reconciliation, not a
  claim that the gap is fixed. Unknown coverage is never zero exposure.
- No Delaware benchmark has been published as validated dashboard data.

Use Maryland's existing NRI/TIGER S1100+S1200/NFHL/WHP/HPMS collection and metric
framework. Preserve High/Very High WHP, 25-metre traffic matching, weighted AADT,
and national hazard-specific average-tie normalization. Do not use BTS NHS.
Positive-exposure final stress remains pending national comparison. Existing
flood VE/tidal AE inclusion is preserved and documented.

## Fresh AWS eligibility and prices

Profile `climate-infrastructure`, project/workload Region **us-east-2** (Ohio).
Fresh CLI identity check succeeded. Free Tier API returned **ACTIVE FREE**, USD
**100** remaining credits. EC2 returned `FreeTierEligible=true` for
**m7i-flex.large (2 vCPU / 8 GiB)** and confirmed it is offered in Ohio. Standard
On-Demand vCPU quota is **32**. These verify plan eligibility and the quota value;
they do not guarantee capacity or validate all future IAM creation requests.
No paid-plan upgrade is proposed. The 16 GiB m7i.xlarge option is not Free Tier
eligible and is not the approved proposal.

Small Price List API queries freshly verified Ohio Linux On-Demand
**USD 0.09576/hour**, and gp3 **USD 0.08/GB-month**. Prices were queried via the
supported us-east-1 pricing endpoint, selecting Ohio products. Toolkit discovery
also uses us-east-1 because its catalog/MCP endpoint is hosted there; no workload
resource is proposed outside Ohio. Toolkit catalog/profile configuration was
verified earlier; live MCP tool invocation still requires a coding-tool restart.

## Exact proposal awaiting approval

One official Ubuntu 24.04 x86_64 **m7i-flex.large** instance; **100 GiB encrypted
retained gp3**, **3,000 IOPS / 125 MiB/s**; one auto-assigned public IPv4;
SSM-only access/no inbound SSH; no NAT, paid endpoints, snapshots or paid log
export. SSM instance profile plus a separate Scheduler role permitted only
`ec2:StopInstances` on this instance, with restricted Scheduler trust. No static
credentials on the host. Instance shutdown behavior must be **stop** and EBS
`DeleteOnTermination=false`.

Delaware current flood/wildfire only, two download workers and one county
calculation. Persistent outputs/cache/checkpoints/logs on EBS; no automatic job
restart on boot. RAM sufficiency is a benchmark question, not an established
minimum. No further large local downloads or local assessment run.

Guest timer: **boot time + 2 hours**, up to **90 seconds checkpoint grace**.
Independent Ohio Scheduler: **EC2 LaunchTime + 2 hours 3 minutes**, no flexible
window, retry age 60 seconds/one retry, self-deletes after firing. Report the
actual UTC deadlines after the real instance exists. AWS execution/shutdown
latency means these are not second-perfect billing cutoffs.

Proposed **USD 1 allowance before credits/tax**, not a hard-enforced cap.
Calculated total **USD 0.585763**, rounded **USD 0.59**, includes:

| Item | USD |
|---|---:|
| Compute for 2h05m | 0.199500 |
| 100 GiB gp3 for 2h05m | 0.022831 |
| Public IPv4 for 2h05m | 0.010417 |
| Two Scheduler invocations before free allowance | 0.000002 |
| Up to 1 GB paid result egress allowance | 0.090000 |
| Additional 24-hour volume retention | 0.263014 |

Retained storage thereafter continues at **USD 8/month**. IAM has no separate
hourly charge. Scheduler should fit its free invocation allowance. No deduction
for credits or free transfer allowances is assumed. Full configuration and source
links: `pipeline/ec2/README.md`; deterministic costs:
`pipeline/ec2/benchmark-cost-estimate.json`.

## Next actions after explicit approval

Create only the proposed Ohio benchmark resources; arm and read back the external
stop before processing. Transfer saved working files/manifest/caches directly to
EC2 without a large local archive; a GitHub clone alone omits uncommitted files
and ignored data. Exclude Mac virtual environments, node_modules, .next and AWS
credentials. Prepare Ubuntu, verify both stop controls, perform the synthetic
disconnect test and actual-job reconnect check, then report exact UTC deadlines.
Verify saved county/checkpoint integrity after stop/restart. A new boot requires
rearming/reverifying the independent stop schedule before another run.

**No remote job exists yet. Do not say it is safe to turn off the laptop expecting
work to continue until remote independence is demonstrated.** Local Codex does
not work through laptop shutdown. Once verified, the remote system service and
AWS Scheduler operate independently of the laptop.

Historical 2021–2025 source audit is in
`docs/audits/history-2021-2025-readiness.md`. Five complete comparable annual
datasets are not verified; WHP/NRI/NFHL baseline values cannot be copied into
annual observations. Hurricane wind/inundation and compound SPEI timescale,
annual aggregation and frequency rules need research review. No annual scores
were populated. After Delaware, benchmark a representative small sample before
national runtime/cost estimates or separate nationwide approval.

Before cleanup, export outputs, manifests, checkpoints, logs and methodology;
verify an accessible copy outside AWS and the processing instance with hashes,
and confirm dashboard loading. Never delete the only copy. No created resource
IDs exist for cleanup yet.


## Historical work update

Historical inputs were audited using small official metadata/count requests; no bulk source files downloaded. See docs/audits/HISTORICAL-WORKFLOW-STATUS.md for source findings, new downloader/calculation-stage scripts, and their explicit limitations. The Delaware EC2 service still runs only the current assessment. Five-year end-to-end calculations, hazard adapters/frequency/normalization, scientific review, and remote execution remain pending. No five-year job will start automatically when the laptop closes.


## Gina review direction

The user requested both five-year interpretations briefly for Gina, with availability limitations and changes from Maryland. Neither interpretation is selected or authorized for implementation. See docs/GINA-FIVE-YEAR-OPTIONS.md. Five-year publications now require explicit approved-methodology, validated-source and matching-year attestations as well as the original hash/validation gate. Delaware current benchmark remains separately scoped to state 10 using the Maryland baseline. Ubuntu preparation handles transferred cache ownership without changing content. API gates, TypeScript, lint, shell syntax, current-only service command and all 51 preservation hashes passed. No EC2 job launched or historical method implemented in this update.


## Maryland/Delaware five-year feasibility priority

EC2 launch remains paused at the user's request. Completed small metadata/COUNT/HEAD queries and three-feature samples per available state/year; no full GIS downloads. See `docs/audits/md-de-five-year-feasibility/REPORT.md`, metadata evidence and 135-row county-year declared-ID CSV. Both states have road archive headers for 2021–2025 and listed HPMS services for 2021–2024; neither has a verified 2025 traffic service in the queried catalog. Both 2023 services have suspect county IDs, and traffic gaps remain. Exact NFHL cannot query historical snapshots; WHP archive versions are irregular modeled products; current NRI is December 2025 and is not an annual event series. Stored AADT dates need interpretation under FHWA annual-estimation rules. Gina's brief is updated; neither historical option is selected. No annual outputs enabled, no remote job launched. Audit consistency checks and Python compilation passed; all 51 preservation hashes still match.


## Supplemental source investigation: target fixed at 2021–2025

EC2 stays paused. See `docs/audits/md-de-five-year-feasibility/SUPPLEMENTAL-SOURCES.md` and saved bounded metadata/validation. State GIS segment sources now verify 2025 AADT and historical 2021–2024 attributes for Maryland and Delaware; HPMS equivalence, current-versus-historical geometry, county codes and exposed-road coverage still require QA. DelDOT changed growth-factor groups in 2025. USGS DSWE catalog samples exist for both state bounding boxes in all five years, but surface-water observations are not validated flood-event footprints. OPERA DSWx-HLS lacks 2021/2022 and early 2023. WFIGS zero DE feature counts cannot imply no fires: Delaware reports eight wildfire assists in 2025. Complete annual flood/fire exposure remains unsupported in all five years. No older-year substitution, historical method selection, full source download or current-result change. All 51 preservation hashes match.


## Selected fixed-baseline pilot preparation

The user selected MD/DE 2021–2025 infrastructure/traffic comparison against fixed NFHL/WHP/NRI for pilot preparation; Gina review precedes annual stress publication and nationwide processing. Label: Infrastructure exposure by year — fixed hazard baseline. See `docs/pilots/md-de-fixed-baseline/REVIEW.md`, manifest, 270-job readiness CSV and validation. Offline preparation pins 24 existing MD WHP rasters, cached December 2025 national NRI bytes (3,232 records) and two MD annual road ZIPs (2021/2022, matching prior source hashes and CRC). All 48 Maryland frequency/normalization comparisons match. Original MD flood geometry unavailable; DE WHP completeness, remaining annual input payloads, traffic alignment/coverage and national consequence-reference policy remain blockers. No full spatial pilot jobs completed, no annual scores published, no downloads or EC2 launch. Eight preparation and eleven existing historical tests passed; compilation and all 51 preservation hashes passed. Existing annual-event experimental utility is not the fixed-baseline runner and remains disabled.
