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
