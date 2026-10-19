# Five-year historical assessment audit — October 18, 2026

**Candidate window only: 2021–2025 is not an adopted assessment period.** No
annual county results have been generated or validated. This source-definition
audit is separate from the saved Maryland 2020–2022 county-by-year audit. A
five-year county-file/AADT-match completeness audit is still pending. No large
historical source files were downloaded locally for this audit.

## Research definitions and discrepancies

The uploaded Transportation Logic research notes specify hazard-specific FEMA
NRI frequency min–max normalization; selected-road exposure divided by total
selected-road length; exposed-length weighted HPMS AADT; average-tie rank
`(rank - 1)/(N - 1)` across national counties for the same hazard; and their
product. The implementation remains the Maryland baseline, including S1100 plus
S1200 and 25-metre traffic matching. Research wording says primary roads only:
that S1100-only discrepancy is documented, not silently changed.

The notes distinguish a drought proxy from the compound **SPEI-R25** event:
daily precipitation **greater than 25 mm** during a month with **SPEI below -1**.
SPEI timescale, temporal pairing, aggregation of qualifying days into yearly
county exposure, missing-day rules and normalization reference population still
need research review. FEMA DRGT_AFREQ is drought frequency, not a validated
frequency for the compound event. No compound implementation exists yet.

The research hurricane footprint is **wind**, while the UI currently says
**Hurricane inundation**. IBTrACS track/intensity observations alone are neither
an inundation map nor a complete wind footprint: wind radii completeness and
the wind threshold/model must be specified before implementation. Preserve the
current placeholder view and flag this mismatch for Gina; do not invent surge
or wind exposure.

## Official source coverage and audit outcome

| Component | Source and observation definition | Coverage/changes and five-year finding |
|---|---|---|
| Current flood | [FEMA NFHL](https://hazards.fema.gov/femaportal/wps/portal/NFHLWMS), mapped SFHA; FEMA NRI IFLD_AFREQ is a long-term annualized rate | NFHL is a changing mapped hazard inventory, not five annual event observations. No comparable full national 2021–2025 snapshots verified. Preserve VE/tidal AE inclusion and identify as SFHA road exposure. Historical map effective dates are not event dates. FEMA page retrieval failed during this audit; saved source definitions/code remain available. |
| Current wildfire | [USDA WHP version 2023 metadata](https://research.fs.usda.gov/sites/default/files/2024-06/firelab-whp2023_cnt_conus_metadata.pdf), 270-m modeled potential, selected High/Very High classes; FEMA WFIR_AFREQ probability | WHP version/publication year does not represent annual observed fires. No five comparable annual WHP maps verified; do not copy this raster into 2021–2025. The metadata carries modeling uncertainty; national raster service coverage must be checked, especially AK/HI. |
| Alternative annual wildfire, requires review | [MTBS announcements](https://www.mtbs.gov/announcements), dated fire perimeters/burn severity | MTBS maps large fires, including prescribed fires ([FAQ](https://mtbs.gov/faqs)). Distinguish wildfire, wildland fire use and prescribed-fire codes; preserve unknown types. 2022 completion is explicitly announced; 2026 announcements still add 2023–2025 maps and describe migration reissues. Five complete, comparable years not demonstrated. Record mapping status, duplicates/reissues, missing geometry and fires below mapping thresholds. Zero mapped fires is not proof of no fires. This would change WHP-based methodology and needs Gina's approval. |
| Hurricane wind, proposed | [NOAA IBTrACS v4r01](https://www.ncei.noaa.gov/products/international-best-track-archive) and [technical details](https://www.ncei.noaa.gov/sites/g/files/anmtlf171/files/2024-07/IBTrACS_version4r01_Technical_Details.pdf) | Global historical tracks; catalog is updated regularly and contains provisional and best-track records. Pin the version/date; exclude spurs as documented. Audit 2021–2025 storm-level best-track status, wind radii and missing values. Threshold/footprint not specified in project; no county annual wind exposure verified. |
| Compound drought–heavy rain, proposed | [NOAA monthly SPEI directory](https://www.ncei.noaa.gov/pub/data/nidis/indices/nclimgrid-monthly/spei-pearson/) and [nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily) | nClimGrid-Daily covers CONUS from 1951 to present; cannot stand in for AK/HI. SPEI filename timescale and actual netCDF time coordinate must be audited. Directory fetch failed (503), daily THREDDS fetch timed out; 60 SPEI months and every required daily precipitation grid in 2021–2025 have not been verified. No annual compound scores authorized. |
| Roads and county equivalents | [Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | Official page lists 2021–2025 editions. This proves release availability, not completeness of selected roads in every county. Audit state road ZIPs and county geometry, classification codes, duplicates, topology, January reference dates, projection and coastal/antimeridian cases. CT changed county equivalents; either use a documented fixed geography or crosswalk annual units, never silently mix them. |
| Same-year AADT | [FHWA HPMS source page](https://www.fhwa.dot.gov/policyinformation/hpms/shapefiles.cfm) and the project's official HPMS 2024 endpoint | The linked legacy page describes 2018, despite a 2022 modification date: modification date is not observation year. It warns GIS may not cover all Federal-aid highways. Existing Maryland 2020–2022 caches do not prove Delaware/national 2021–2025 coverage. State-by-year files, YEAR_RECORD, valid AADT/geometry and matching on selected exposed roads remain to be checked, especially 2025. Never reuse HPMS 2024 as if it were measured in 2021–2025. |

## Defensible next scientific decision

Keep current modeled hazard potential/SFHA assessment as a separate baseline.
If annual comparison is required, propose an explicitly named observed-event
analysis where suitable event data exist, with new annual-frequency rules. It
must not replace NFHL mapped risk or WHP potential. Gina must review the
methodological change before any annual scores are populated. The strongest
immediate deliverable is validated current Delaware flood/wildfire exposure,
with uncertainty/traffic coverage and national-ranking dependencies visible.

Year selection is infrastructure only: the UI labels 2021–2025 as unavailable,
requests include `year`, cache keys include assessment period, and exports use
the chosen period. An annual request never falls back to current results.

Within-year national consequence ranks compare counties relative to that year's
eligible reference population. Changing the population or ranking separately
per year can change ranks without an absolute change in traffic. Cross-year
comparability therefore requires a declared fixed reference or an explicitly
relative interpretation; do not substitute a Maryland/Delaware-only rank for
the national normalization.


## Subsequent live input checks and prepared stages

See [historical workflow status](HISTORICAL-WORKFLOW-STATUS.md) and the county/year JSON audit for fresh Delaware 2021–2025 source checks. Annual TIGER file headers were verified; DOT HPMS dataset years 2021–2024 were verified, with a 2023 county-ID anomaly. No 2025 DE HPMS service was listed in the queried catalog. Metadata availability is not geometry or AADT-match completeness. Prepared download and annual exposure/AADT scripts remain separate from the current EC2 benchmark and are not a complete five-year pipeline.
