# Maryland/Delaware pilot for Gina’s review

**Infrastructure exposure by year — fixed hazard baseline.**

The user selected this interpretation for pilot preparation. Gina has not yet
reviewed it for annual score publication or nationwide processing. Scope is
**2021–2025**, 24 Maryland county equivalents and three Delaware counties,
inland flood and wildfire: 135 county-years / 270 hazard jobs. EC2 stays paused.

The question is: how did roads and estimated traffic exposed to the same mapped
hazards change? Differences reflect infrastructure, traffic, and potentially
inventory revisions. They do **not** measure annual changes in floods or fires.
A baseline published after an observation year is a retrospective fixed-map
comparison, not a reconstruction of what was known in that year.

## Preparation delivered and validation completed

- [Pinned input/readiness manifest](manifest.json) and
  [270-job county/year readiness table](county-year-readiness.csv).
- `python3 pipeline/prepare_fixed_baseline_pilot.py` recreates the package
  **offline**, hashes existing assets, checks source-year mappings and preserves
  the dashboard. It neither downloads data nor starts a processing job.
- National NRI source cache: **3,232** distinct records, declared December 2025.
  Exact cached payload/request bytes are pinned. Duplicated cached responses
  are checked for conflicting values. The two hazard min/max references are
  fixed for all five years. All **48 Maryland county/hazard frequency and
  normalization comparisons** match the saved current assessment.
- Existing Maryland WHP2023: **24 county raster files**, export requests and
  cached service metadata pinned by SHA-256. Grid coverage must still be checked
  against the annual roads, particularly any boundary/edge differences.
- Maryland 2021/2022 TIGER road ZIPs: fingerprints match the prior official-source
  audit, required shapefile components exist, and ZIP CRC checks pass. No
  additional road files were downloaded.
- Previously completed Maryland geometry audit found no missing/invalid TIGER
  road geometry in 2021/2022, but HPMS geometry and AADT gaps. Its S1100+S1200
  all-road positive-AADT proximity coverage was **65.49%** and **65.64%**;
  county ranges were 18.40–93.57% and 18.61–93.67%. Those are prior all-road
  checks, not this pilot's hazard-exposed coverage or route-identity validation.
- [State metadata and three-feature samples](../../audits/md-de-five-year-feasibility/supplemental-metadata.json)
  verify 2021–2025 AADT fields in both states; they do not pin complete traffic
  payloads or establish coverage. Maryland's current field is anchored to the
  explicit 2025 description. Delaware aliases and `CURRENT_YEAR=2025` anchor
  its rolling historical fields. Changed anchors must fail, not shift years.

**Not completed:** a full fixed-baseline spatial pilot. No annual county metrics
or annual stress scores have been generated. The original Maryland flood
geometry cache is unavailable; output JSONs cannot reconstruct it. The manifest
does not pretend metadata hashes are full hazard or traffic snapshots.

## Method to review

| Component | Pilot specification |
|---|---|
| Roads | Each year's official TIGER primary/secondary roads, preserving the Maryland implementation's S1100+S1200 selection and line union/length treatment. The research document's narrower primary-road wording remains an explicit review discrepancy. |
| Geography | Propose one verified county-boundary reference for all years, with annual-boundary comparisons to detect changes. The final boundary snapshot is not pinned yet. Do not let boundary revisions masquerade as road changes. |
| Flood baseline | One pinned NFHL geometry/coverage snapshot, `SFHA_TF='T'`, preserving tidal/coastal classes and the current inland-flood method. Recover original Maryland source bytes if possible. Otherwise declare a separately dated pilot NFHL snapshot, retain current outputs, and quantify differences; do not claim it reproduces the original footprint. |
| Wildfire baseline | WHP2023 High/Very High classes 4/5, retaining the existing 270 m service grid/export and EPSG:26918 length calculations. End-2020 landscape conditions, not annual burn observations. Reuse original Maryland bytes; acquire and pin corresponding complete Delaware coverage. |
| Frequency | Use pinned NRI `IFLD_AFREQ` / `WFIR_AFREQ` values and the same national min/max for every pilot year. No annual event frequency is substituted. |
| Exposure | Annual selected-road length intersecting the fixed footprint ÷ that year's total selected-road length. Measure actual new, removed and reclassified road features separately from geometry corrections. |
| Traffic | Year-specific HPMS where available is the research source. Evaluate state segment AADT as a supplement or consistent alternative, **not yet a selected replacement**. Preserve the 25 m matching operation and exposed-length-weighted AADT formula; document source priority, units, functional-class crosswalk and duplicate/direction handling. |
| Consequence normalization | Proposed fixed national reference across all years; review the reference population and exact mapping rule before calculating annual normalized values. No pilot-only or independent within-year ranking. |
| Stress | Fixed normalized frequency × annual exposure × consistently normalized consequence. Withhold all annual stress scores until Gina review, source/coverage validation and a complete national consequence reference. |

The historic experimental `process_historical_exposure.py` is **not this pilot's
runner**: it expects same-year hazard geometry and an approved annual-event
definition, is Delaware-only, and does not implement fixed-baseline frequency
or ranking. It stays disabled. The current-only EC2 service also does not run
this pilot. This package prepares inputs, validation and review; neither
existing command should be presented as an executable five-year assessment.

## Acquisition and processing plan

1. Freeze the package ID and preserve all 51 current baseline hashes. Create a
   separate pilot cache/staging namespace; never overwrite current county JSONs.
   Keep hazard snapshot identity independent of year; all years reference the
   same verified bytes and known-coverage masks. Save source URL, retrieval time,
   release/represented time, CRS, layer/field definitions, response counts and
   SHA-256. Pin the complete county list and source request IDs as well.
2. Acquire state-wide annual TIGER roads and same-year traffic in shared batches,
   not repeated county requests. Reuse the two cached Maryland road ZIPs and
   prior audit caches where their hashes/years agree. Eight other state/year
   road ZIPs and all selected complete traffic payloads remain unacquired for
   this package. Annual county-boundary files need only supply the MD/DE subset;
   metadata availability alone is not a geometry check.
3. Pin complete flood zones **and mapped/unmapped coverage**, WHP categorical
   pixels/NoData and NRI frequencies. Verify source-ID pagination, geometry
   types/CRS, bounds, missing/invalid shapes and seam coverage before clipping.
   For NFHL, overlapping DFIRM/LOMR revisions need the existing source's effective
   geometry semantics; a state-prefix-only download is insufficient evidence.
4. Build explicit traffic county/route crosswalks. Maryland state codes are not
   FIPS; Delaware's queried history layer lacks a county field. Use spatial
   county assignment and route/milepoint validation. Compare HPMS and state
   AADT in overlapping 2021–2024 samples before any source mixing. DelDOT's
   new 2025 urban/rural growth-factor groups require a documented sensitivity
   check. Older original count dates may still yield legitimate annual estimates.
5. Compare annual road geometries: length by class/county, added/removed lines,
   alignment drift, reclassification, duplicates, boundary coincidences and
   divided roads. Compare traffic historical segment lineage to each year's
   TIGER road network. A historical AADT column on current geometry does not
   validate historical alignment. Record discrepancies instead of repairing
   source values by interpolation or copying adjacent years.
6. Validate Howard (24027) first: replay original frozen wildfire sources; verify
   annual road geometry against known coverage; then include a saved Maryland
   county with positive WHP exposure and each Delaware county. Freeze this QA
   sample before expanding to all 27 counties and five years. For flood, compare
   original outputs only where source identity is established; otherwise label
   replay unavailable and quantify separately dated baseline differences.
7. For every county/year/hazard report exposed-length traffic coverage, unmatched
   miles and source counts. Reconcile all-road versus exposed-road coverage,
   road-weighted versus traffic-line-weighted length, and overlapping matches
   against Maryland's exact operations before accepting the pilot's raw values.
   Do not claim partial matches measure all exposed traffic. No arbitrary
   completeness threshold is approved here; Gina must review the coverage rule.
8. Use bounded concurrency and shared source caches, with rate-limit-aware
   retries, immutable request-ID batches, atomic `.part`→complete commits and
   per-source/per-county checkpoints. Resume signatures include code version,
   baseline pins, year-specific inputs, boundary, traffic policy and normalization
   reference. A missing/changed asset invalidates its checkpoint. A checkpoint
   means verified completed work, not merely a successful API response.
9. Write review-only results/checkpoints under a separate pilot staging directory,
   retaining the existing county metric names. Store period/baseline/coverage
   provenance in a separate manifest. Default annual normalized consequence and
   stress to null. Existing dashboard publication gates and available-year
   options remain unchanged; no automatic publication or nationwide run follows.

## Missing values and normalization

- Unmapped NFHL, WHP NoData, incomplete geometry or source failures are unknown
  exposure, not zero. Compute verified zero only after confirming all relevant
  selected-road length has known hazard coverage. New annual roads outside a
  cached raster footprint must block that result rather than inherit zero.
- Verified zero exposure has no segment AADT mean (null consequence). Its
  mathematical stress is zero, but annual score publication is still held for
  review. Exposed roads without usable traffic keep consequence/stress unavailable.
- The NRI frequency reference has 3,232 valid source records. Preserve this
  existing population rather than silently restricting frequency normalization
  to 27 pilot counties or the processing manifest's narrower national scope.
- A complete national consequence cohort is not available. Re-ranking each year
  would change the scale, and ranks across just MD/DE are not national ranks.
  Gina should review a fixed national reference population and how new values
  map to it, including ties/out-of-range values. Until defined and computed,
  expose raw AADT/coverage in review artifacts only and keep normalized
  consequence/stress null. The national reference prerequisite does not authorize
  nationwide processing before this pilot is reviewed.

## Readiness and review questions

Preparation/checkpoint specification is ready for review; **inputs and the full
processing runner are not ready**. Current blockers are missing pinned complete
NFHL/Delaware WHP coverage, remaining annual payloads, historical traffic geometry
and source compatibility, unvalidated exposed-road matches, and the consequence
reference definition. Local free space remains very limited, so no bulk download
or new GIS installation was attempted. This does not authorize EC2 launch.

Gina's review should confirm: the retrospective fixed-map interpretation; road
scope; the explicitly dated flood baseline if original bytes cannot be recovered;
traffic supplement policy and completeness criteria; county geography; and fixed
national normalization. Her approval must refer to the concrete versioned package
and its validation evidence, not a general statement that archives exist.

No message has been sent to Gina. The existing current assessment, inland-flood
calculation, output schema and current dashboard year availability are unchanged.
No EC2 instance or nationwide process has been launched.
