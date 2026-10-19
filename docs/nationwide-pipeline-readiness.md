# Nationwide pipeline readiness — 2026-10-07

Status: assessment only. No nationwide batch has been implemented or run in
this work. Maryland county outputs and the inland-flood calculation remain
unchanged. National map navigation and national FEMA frequency normalization
do not establish national spatial-processing coverage.

## Current assessment and saved progress

- Dashboard results exist for Maryland's 23 counties and Baltimore city.
- Wildfire uses WHP 2023, High/Very High classes, reflecting end-of-2020
  landscape conditions, and FEMA `WFIR_AFREQ`. Flood uses FEMA NFHL SFHA
  (`SFHA_TF='T'`) and `IFLD_AFREQ`. Both use TIGERweb S1100+S1200 and HPMS 2024.
- The saved county results do not record the NRI, NFHL, or TIGERweb release
  vintage. Calculation dates are not source-vintage evidence. Do not infer
  those vintages from today's live service metadata.
- Flood and positive-exposure wildfire consequence ranks/stress await a
  national, hazard-specific comparison. Wildfire structural zero-exposure
  counties retain stress 0 and null consequence under the current method.
- The completed Maryland 2020–2022 completeness audit is saved in
  [audits/maryland-history-2020-2022/audit-report.md](audits/maryland-history-2020-2022/audit-report.md),
  with all 72 county-years (144 rows for two road scopes), JSON/CSV results and
  source-hash manifests. This audit produced no annual scores or dashboard
  year options. Raw source downloads remain in `/tmp/maryland-history-audit-2020-2022`;
  `/tmp` is temporary, so later reproduction must retrieve sources again or
  move the cache to a durable storage location.
- The annual audit's 25-metre proximity AADT coverage is incomplete. For
  S1100+S1200, statewide length-weighted match rates are 64.48%, 65.49% and
  65.64% in 2020, 2021 and 2022. Each year's HPMS also has missing geometry.
  These historical observations are not measurements of national HPMS 2024
  completeness.

## Implemented caching versus missing batch infrastructure

| Component | Present | Still needed for national processing |
|---|---|---|
| County enumeration | Hard-coded 24 Maryland counties in both processors | Frozen national county-equivalent manifest; explicit states/DC and territory scope; reconcile GEOIDs across Census, NRI and HPMS |
| State filters | HPMS `stateid=24`; wildfire cache namespace `24`; state output Maryland | Derive state from GEOID, partition caches by state/hazard, remove Maryland-only orchestration assumptions in a separate national runner |
| Length measurement | EPSG:26918 / UTM 18N for Maryland | Validated regional projection or geodesic strategy across the country, including Alaska, Hawaii and date-line geometries; retain Maryland's existing method/results |
| Flood resume | Per-county JSON; source caches; retry/backoff; NFHL ID batches | Atomic writes, method/source fingerprints, per-page and per-ID-batch checkpoints, strict missing-ID checks, durable error ledger |
| Wildfire resume | Atomic JSON/TIFF writes; request-keyed pages; method-version county reuse; TIFF hashes | Source-snapshot fingerprints on checkpoint reuse, national manifest, tiled raster checkpoints for large counties, restart/invalidation validation |
| National consequence | Not implemented for either hazard | Separate per-hazard aggregation and average-tie rank stage; explicit eligible county population, missing-data and zero-exposure policies |
| Publication | Existing Maryland JSON directories | Staged national outputs and verified coverage manifest; Maryland files stay untouched; publish only validated scope through existing flat county JSON contract |

The generic `process_counties.py` is a scaffold: its completion predicate only
checks file existence and its writes are not atomic. The Maryland flood runner
adds a small field/status check, but does not fingerprint method or inputs.
NFHL batches currently warn rather than fail when retrieved feature counts do
not match requested IDs. County success therefore needs a stronger national
verification gate without changing the flood metric.

## Proposed resumable run and checkpoints

1. **Preflight checkpoint.** Freeze a county-equivalent manifest and source
   snapshots. Record source release/effective dates, retrieval dates, URLs,
   query parameters, hashes, schema, coverage masks, road scope and method
   version. Reconcile county identifiers rather than assuming a fixed count.
   Connecticut's transition to planning-region county equivalents is one
   concrete case requiring verification against NRI and HPMS geography.
2. **Download checkpoints.** Cache each request page, NFHL object-ID list and
   batch, HPMS page and WHP raster tile independently using atomic writes.
   Validate counts/unique IDs and geometry before marking complete. Use bounded
   workers and retry/backoff. Missing coverage is a recorded blocker, not zero.
3. **County/hazard checkpoints.** Store staged local metrics, QA, source hashes
   and method fingerprint outside the Maryland output directories. Track
   queued, running, retryable failure, blocked, no selected roads, confirmed
   zero exposure, local metrics complete, and QA passed in a sidecar ledger.
   Resume only compatible checkpoints. Do not turn missing inputs into values.
4. **Independent validation checkpoint.** Keep Howard as a regression anchor;
   additionally sample positive and zero exposure, missing traffic, no roads,
   large western counties, coastal areas, independent cities, Alaska/Hawaii,
   raster edges and multipart/date-line boundaries. Verify lengths, ratios,
   clipping, NoData, frequency ranges, unique AADT assignment/coverage and
   consistency with independent overlays. Interrupt and resume test runs;
   compare with uninterrupted runs and test source/method invalidation.
5. **National comparison checkpoint.** Freeze each hazard's eligible county
   population after local metrics and coverage review. Apply the research's
   average-tie rank normalization `(rank - 1) / (N - 1)` with a documented
   definition of N and handling of missing consequence, structural zeros and
   N≤1. Never substitute Maryland-only ranks. Write ranking provenance to
   sidecars and keep the existing county JSON format.
6. **Release checkpoint.** Reconcile every expected county/hazard against the
   ledger and distinguish spatial results, valid traffic consequence, and final
   stress. Run schema and independent QA checks; verify Maryland output hashes
   unchanged. Coverage claims must match this ledger, not file existence or
   number of counties used in frequency normalization.

## Blockers before a nationwide coverage claim

- **Road-scope mismatch:** the uploaded wildfire research specifies S1100
  primary roads; the existing dashboard uses S1100+S1200. The annual audit finds
  eight Maryland counties without S1100 roads. Resolve the future national
  wildfire scope explicitly; do not silently revise either current assessment
  or inland flood.
- **Flood-footprint interpretation:** the current SFHA mask includes coastal
  VE zones and potentially tidal AE areas while frequency is inland-flood
  `IFLD_AFREQ`. Preserve the method, but describe its footprint accurately;
  nationwide results cannot automatically be called exclusively inland flood.
  An empty NFHL query also cannot establish zero hazard without mapped-area
  completeness checks. The existing empty-query branch needs a coverage gate
  in future national orchestration.
- **Source provenance/coverage:** missing recorded release vintages prevent a
  reproducible baseline claim. National NFHL mapped-area completeness, HPMS
  2024 geometry/AADT matches and WHP class/NoData coverage have not been audited.
  The Forest Service page says WHP includes Alaska/Hawaii from 2020 onward;
  the cached service description contains CONUS wording. Resolve actual tile
  coverage and metadata consistency before any all-states assertion. Territory
  support must be checked separately. Do not substitute BTS NHS/burn probability.
- **Traffic gaps:** even current Maryland wildfire exposed-road HPMS coverage
  is 0% in Dorchester, 5.03% in Somerset and 25.26% in Wicomico. Their matched
  AADT cannot establish full exposed-road traffic completeness. National
  matching coverage criteria, missing-data policies and eligibility for ranking
  remain unsettled.
- **National spatial/orchestration work:** state hard-coding, UTM 18N, county
  geography reconciliation, raster tiling, checkpoint integrity and national
  aggregation all need implementation and validation. Existing scripts cannot
  safely be called a nationwide runner.
- **Resources and access:** a disk-space error occurred during the historical
  audit; raw national data need a durable cache with measured disk/memory budgets.
  The subsequent production build succeeded but emitted an ENOSPC cache-write
  warning; the filesystem reported approximately 35 MiB available afterward.
  Provision storage before starting a national batch.
  Live-service timeouts, limits and earlier endpoint 403s need recorded retries
  and authoritative source alternatives. Access working for Maryland does not
  establish nationwide download feasibility.
- **Annual analysis remains separate:** WHP modeled potential and annual mapped
  fires are different measures. MTBS maps qualifying large wildfires and
  prescribed fires, not every incident. Gina's review is required before the
  annual footprint/frequency/prescribed-fire policy becomes a score. The current
  baseline method remains in place.

## Source definitions consulted

- [Forest Service WHP definition and vintages](https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential)
- [Current WHP service used by this pipeline](https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer)
- [Census Connecticut county-equivalent change](https://www.census.gov/programs-surveys/acs/technical-documentation/user-notes/2023-01.html)
- [MTBS mapping scope](https://www.mtbs.gov/)

Coverage/access uncertainties above are open checks, not assertions that those
datasets categorically lack a state or county. No national completeness claim
is made by this assessment.

## Checks for the assessment-label change

TypeScript, page ESLint, seven existing wildfire metric/overlay tests and a
webpack production build passed. The prerendered page contains the coverage
and vintage disclosures. All 69 pipeline/output files in the audit baseline
excluding the intentionally edited dashboard page remained byte-identical.
There is no diff to the inland-flood processor, shared configuration,
checkpoint scaffold or metric helpers. These checks validate this display and
documentation change; they do not validate nationwide processing.
