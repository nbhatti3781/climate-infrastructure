# National preprocessing pipeline

The dashboard reads compact county-level outputs. Raw GIS data is never downloaded in the browser.

The first validation script is `validate_howard.py`. It retrieves only Howard
County, Maryland (GEOID 24027), clips Census Primary Roads to FEMA NFHL Special
Flood Hazard Areas, retrieves FEMA NRI inland-flood annualized frequency, and
writes `data/processed/counties/24027.json`.

The Howard validation now calculates the complete local inputs: nationally
min-max-normalized FEMA `IFLD_AFREQ`, exposed-road proportion, and exposed-road
length-weighted HPMS AADT. The Step 3 percentile and final Transportation Stress
remain unset until the same exposed-road AADT calculation has been processed
for all counties; the pipeline never substitutes a state-only or county-wide
traffic ranking for the documented national, hazard-specific rank.

Planned processing order:

1. Query Census county boundaries and primary roads by state/county GEOID.
2. Query each hazard service using the county geometry or bounding box.
3. Intersect roads with the hazard footprint in an equal-distance/equal-area CRS.
4. Calculate exposed road length, AAEL, and annualized relative road exposure.
5. Write one checkpoint per county and a consolidated dashboard table.

Every task is resumable. API responses belong in `data/cache/{source}/{state}/{county}` and derived results in `data/processed`.

## Maryland wildfire

`process_maryland_wildfire.py` processes Maryland only: 23 counties plus
Baltimore city. Howard County (24027) is calculated and validated before any
other county. It does not call the flood calculation or write flood outputs.
The shared geometry helpers and Maryland county list are imported read-only.

### Official sources and metric

- Footprint: [USDA Forest Service Wildfire Hazard Potential, version 2023](https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential).
  WHP describes relative potential for high-intensity wildfire that can be
  difficult to manage. Its source resolution is 270 metres and it reflects
  landscape conditions at the end of 2020. It is not a seasonal forecast,
  burn probability, or engineering damage/closure model.
- Active [classified image service](https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer):
  class codes 1 Very Low, 2 Low, 3 Moderate, 4 High, 5 Very High,
  6 Non-burnable, 7 Water; 255 NoData. The old apps.fs.usda.gov service
  reports that it has migrated to GeoPlatform.
- Frequency: FEMA National Risk Index county `WFIR_AFREQ`, interpreted as
  annual wildfire probability, **not events/year**. See the
  [FEMA technical documentation](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf).
  Min-max normalization uses all national counties with non-null,
  nonnegative values, while spatial processing is confined to Maryland.
- Roads: Census TIGERweb layers 2 and 6 (S1100 + S1200), unioned and clipped
  to the county. Local roads and ramps are excluded, matching the flood scope.
- Consequence: FHWA HPMS 2024, county-filtered `f_system <= 4`, non-null
  AADT. Length-weighted AADT uses HPMS pieces inside the county and selected
  WHP footprint within 25 metres of the TIGER major-road network. Coverage
  is TIGER exposed length within 25 metres of matched HPMS pieces, avoiding
  inflated coverage from overlapping HPMS geometries.

The dashboard's selected footprint is **High + Very High (codes 4 and 5)**.
This threshold is an explicit dashboard screening choice, not a USDA road
failure threshold. Lower classes can also experience wildfire. All seven
classes' road lengths are provided for context.

`exposure = High/Very High-exposed major-road length / total major-road length`

`stress = national min-max WFIR_AFREQ × exposure × national wildfire-exposed AADT percentile`

Normalized consequence remains null until national wildfire-specific consequence
values exist. For a county with a major-road network and confirmed zero
High/Very High exposure, stress is 0 and raw consequence stays null:
there are no exposed segments to average. This is recorded as
`zero_exposure_complete`; lower WHP classes may still have wildfire potential.
Positive exposure without matching HPMS traffic leaves consequence and stress
null. Counties with no major-road network remain N/A, with null stress.
AAEL is probability times exposed road miles, a screening indicator expressed
as annualized miles; the county-average probability is not road-specific.

Raster exports request raw single-band U8 TIFFs (`rasterFunction=None`) with
nearest-neighbor interpolation, aligned to the service's 270-unit EPSG:3857
grid. This is a service representation of the 270-m source, not a finer ground
resolution claim. Class polygon edges are densified every 27 service units
before transformation; lengths are measured in EPSG:26918. Roads are clipped
once to avoid losing coincident county-boundary roads. NoData on road length
above 0.01 metre fails processing instead of being classified as unexposed.

### Run and resume

```bash
python3.12 -m venv .venv-wildfire
.venv-wildfire/bin/pip install -r pipeline/requirements-wildfire.txt
.venv-wildfire/bin/python pipeline/process_maryland_wildfire.py --howard-only
.venv-wildfire/bin/python pipeline/process_maryland_wildfire.py
.venv-wildfire/bin/python -m unittest discover -s pipeline -p test_wildfire.py
.venv-wildfire/bin/python pipeline/verify_maryland_wildfire.py
```

Source requests are cached under
`data/cache/wildfire/{source}/24/{county}/`, keyed by URL and exact query
parameters. Pagination pages are individually cached, so an interrupted
download resumes from completed pages. GeoTIFFs have request sidecars and a
SHA-256 in each compact result. JSON and raster checkpoint writes are atomic.
Completed wildfire checkpoints matching the method version are reused;
existing flood JSONs never count as wildfire checkpoints. `--force` recomputes
results from the same cached inputs. To refresh sources, archive the ignored
wildfire cache and use `--force`. Other counties' failures are recorded and do
not discard successes; a Howard failure stops the run. Any failure exits nonzero.
Use repeated `--county <Maryland GEOID>` flags for targeted retries; Howard is
always first. A full default rerun rebuilds the report for all 24 counties.

### County output contract

Wildfire outputs use `data/processed/wildfire/counties/<GEOID>.json`, retaining
the flat county JSON contract and common frequency, road-total, exposure,
AADT, stress, source, and QA fields. The hazard-specific length field is
`wildfire_exposed_major_road_miles`; `hazard` is `wildfire`. Additional fields
include `whp_class_major_road_miles`, `whp_nodata_major_road_miles`,
`raster_audit`, `method_version`, and Howard's independent `validation`.
The run report is `data/processed/maryland_wildfire_report.json`.

`GET /api/county/<GEOID>?hazard=wildfire` serves those compact results only for
Maryland. Omitting the query retains the existing flood response. Unsupported
hazards return 400 and unavailable results return 404. The browser cache is
keyed by hazard and GEOID to prevent stale flood metrics in the wildfire tab.

Howard validation independently intersects individual High/Very High cells
with roads, compares against polygonized exposure, and checks that all seven
classes partition the road length (tolerances: 1e-6 and 1e-5 miles). The validated
road total is 281.467736 miles, matching the existing major-road flood total;
High/Very High exposure is 0 miles. This does not imply no wildfire potential.

The Maryland output checks are recorded in
`data/processed/maryland_wildfire_qa_report.json`. The completed run found
High/Very High exposure in Dorchester (1.604289 mi), Somerset (4.868645 mi),
and Wicomico (2.198578 mi). Dorchester has no exposed-road HPMS match; Somerset
and Wicomico have only 5.03% and 25.26% traffic coverage, respectively. Raw
AADT averages describe the matched portions only. Final stress remains null
for these three exposed counties; the other 21 counties have confirmed zero
exposure and a stress score of 0 for the selected threshold.
All 24 outputs pass class-partition, coverage, range, and null-semantics checks.
