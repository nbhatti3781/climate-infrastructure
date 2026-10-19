# Historical workflow: what will actually run

Updated October 18, 2026. **2021–2025 remains a candidate, not an approved
five-year assessment.** No historical processing is scheduled on EC2 and no
annual county scores have been produced. Existing Maryland data/methods remain
unchanged.

## Current benchmark versus historical work

The proposed Delaware EC2 service runs exactly:

```bash
.venv-wildfire/bin/python pipeline/process_state_assessment.py --state 10 --benchmark --workers 2 --reserve-mb 5120
```

That is the **current** FEMA SFHA and WHP 2023 assessment, using existing NRI
frequency and HPMS 2024. It does not run the new historical scripts, download
five hazard years, or create annual frequency/normalization values. The previous
$1 benchmark allowance does not authorize a larger historical or nationwide run.

## Newly completed live metadata audit

`pipeline/audit_historical_sources.py` was executed against official sources,
using only small metadata/count responses and file HEAD requests. Its per-year
checkpoint is `delaware-history-2021-2025-source-audit.json`.

| Year | TIGER road and national county ZIP headers | DOT HPMS service/data-year field | Remaining issue |
|---|---|---|---|
| 2021 | Available | Verified 2021 | Missing/negative AADT exists; geometry/measurement dates/matches untested |
| 2022 | Available | Verified 2022 | Missing/negative AADT exists; geometry/measurement dates/matches untested |
| 2023 | Available | Verified 2023 | County-ID queries return records for Kent but none for New Castle/Sussex; investigate identifiers/spatial attribution, never infer zero exposure |
| 2024 | Available | Verified 2024 | Missing/negative AADT exists; geometry/measurement dates/matches untested |
| 2025 | Available | No DE 2025 service in the queried DOT Hosted catalog | DelDOT publishes 2025 summary PDFs, but a verified segment-level geometry/AADT source has not been obtained |

The catalog contains actual DE 2021–2024 services. Their field names change
(`year_record`, `datayear`, `data_year`); the audit discovers those names and
actual service layer IDs rather than assuming them. A guessed layer/0 initially
returned an error, but catalog/layer discovery subsequently succeeded. Dataset
year does not automatically prove that every AADT measurement is from that year.
Counts are preserved in the JSON; no AADT road-match rate is claimed.

File headers establish accessible files, not their contents/geometry completeness.
No road ZIP, traffic geometry collection, hazard raster or fire perimeter dataset
was bulk-downloaded locally. The road/boundary input header sizes sum to
423,158,833 bytes; these are proposed remote downloads, not local downloads.

## Prepared scripts and their limits

1. **Audit:** `pipeline/audit_historical_sources.py` probes sources and saves
   county/year availability without inventing unavailable values.
2. **Download:** `pipeline/download_historical_inputs.py` builds
   `delaware-history-download-plan.json`: 10 annual TIGER road/boundary inputs
   and four verified-year HPMS inputs. It records unresolved 2025 traffic.
   Execution is opt-in, Linux-only, and enforces a 5 GiB disk reserve. ZIP files
   stream to partial files, use pinned validators for range resume, retry safely,
   check ZIP integrity, and receive SHA256 receipts. HPMS uses shared request
   caches/checkpointed source-ID batches. Whole-state traffic is acquired so the
   2023 county attribute anomaly does not silently discard other counties.
   Downloaded inputs remain unvalidated source material, not dashboard results.
3. **Annual calculation stage:** `pipeline/process_historical_exposure.py`
   accepts reviewed, same-year, hash-pinned prepared GeoJSON inputs. It clips to
   county boundaries, unions duplicate selected roads, checks known source
   coverage, and calculates exposure/length-weighted AADT with the existing
   25-metre traffic match. It separates no roads, verified zero exposure, missing
   coverage and missing/partial traffic, and checkpoints by year/county/hazard,
   reviewed method and source identity. It writes only historical staging.
   It deliberately leaves annual frequency, national ranks and stress **null**:
   those annual definitions/reference populations are not implemented/approved.

There is **no approved annual input manifest** and no prepared annual hazard
GeoJSON. Source-specific conversions/QA, annual hazard acquisition, annual
frequency definitions, and national normalization still need implementation
after the scientific choice below. The calculation stage cannot run from the
download plan alone and refuses an unapproved method. It is not a completed
five-year pipeline. Nothing was added to the existing EC2 service command.

Example input-plan-only command (safe; no dataset download):

```bash
.venv-wildfire/bin/python pipeline/download_historical_inputs.py \
  --audit docs/audits/delaware-history-2021-2025-source-audit.json \
  --plan docs/audits/delaware-history-download-plan.json
```

Future approved remote acquisition requires adding `--execute --cache-dir`.
No such execution was performed. Annual calculation requires a separate approved
manifest with `methodology_review` (status, reference, annual hazard definition,
frequency decision, road scope, prescribed-fire handling and coverage definition)
plus per-county/year `inputs` for boundary, roads, hazard, known coverage and
traffic. Each input must declare observation year, verified coverage, local file
and SHA256. The code requires prepared WGS84 GeoJSON, matching years, supported
geometry types and unchanged S1100/S1200 scope. Synthetic tests stay outside all
assessment directories.

## Why five hazard years cannot yet be promised

- **Flood:** current NFHL mapped SFHA plus long-term NRI frequency is not an
  annual flood-event series. Five comparable historical map snapshots have not
  been verified. Do not substitute event footprints for mapped risk.
- **Wildfire:** WHP versions are modeled potential, not an annual series. The
  current model uses LANDFIRE 2020. MTBS large-fire perimeters are an alternative
  observed-event method, include prescribed fire, and are still receiving
  2023–2025 mapping/reissues. Five complete comparable years are not established.
- **Hurricane:** IBTrACS v4r01 is a real historical archive but track/radii/
  provisional-status checks and a reviewed footprint/threshold are needed.
  Research wind exposure and the UI inundation label are different definitions.
- **Drought–heavy rain:** the research SPEI-R25 thresholds are daily rain >25 mm
  and monthly SPEI <-1; SPEI timescale, distribution, day/month pairing, missing
  data and annual aggregation/frequency remain unresolved. NOAA offers multiple
  SPEI timescales and fittings. Validate actual time coordinates, not filenames
  or publication dates. Current gridded input proposals do not establish AK/HI
  coverage or five years of complete daily/monthly pairs.

Two scientifically distinct options need Gina's review:

1. **Annual infrastructure against a fixed hazard baseline:** annual roads/AADT
   with explicitly fixed WHP/NFHL/NRI vintage. This measures infrastructure/traffic
   changes against one hazard model, not past annual hazard conditions. No map
   copies labeled as annual observations. 2025 AADT is still a source blocker.
2. **Annual observed-event exposure:** reviewed dated event footprints/climate
   observations with new annual frequency rules. This changes the baseline
   method and needs separate scientific approval, source adapters and completed
   annual coverage. MTBS alone does not establish all fires or full mapping.

Neither option is silently selected. Neither is included in the current
benchmark. Five complete comparable years have **not** been confirmed.

## Remote independence and completion gates

After sources/methods are settled, finish source adapters and annual-frequency/
comparison calculations; test with actual inputs and Maryland regressions; create
a bounded historical job plan/cost for approval; transfer/run it on EC2 with
the retained data volume, independent stop controls and year-aware checkpoints.
Verify job/log progress across actual SSH/SSM disconnection and verify saved
outputs after stop/restart. Only then is it safe to close the laptop expecting
that already-running job to continue. Local Codex cannot research, implement
missing adapters or launch additional work while the Mac is off.

An input download finishing is not a scientific completeness check. Annual
results require county/year inventory reconciliation, source-coverage and
traffic-match checks, explicit unavailable states, declared ranking population,
and validated publication. A larger nationwide/five-year run stays on hold.

Official sources checked:
- [DOT Hosted service catalog](https://geo.dot.gov/server/rest/services/Hosted?f=json)
- [DelDOT HPMS reports](https://deldot.gov/Publications/reports/hpms/index.shtml)
- [USDA WHP definition](https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential)
- [MTBS releases and completion notices](https://www.mtbs.gov/announcements)
- [NOAA IBTrACS v4r01](https://www.ncei.noaa.gov/products/international-best-track-archive)
- [NOAA SPEI metadata/timescales](https://www.drought.gov/data-maps-tools/us-gridded-standardized-precipitation-index-spei-nclimgrid-monthly)
