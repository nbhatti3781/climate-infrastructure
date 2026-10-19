# Supplemental sources: Maryland and Delaware, 2021–2025

Checked October 18, 2026. **The target stays 2021–2025. No older year is a
substitute. EC2 launch remains paused.** This supplements the original
[exact-source audit](REPORT.md); it does not revise the current assessment.

The 2025 traffic gap is now narrower: authoritative state GIS services contain
2025 segment AADT and historical AADT attributes for every target year. Their
coverage and equivalence to HPMS remain unvalidated. Annual observed flood/fire
exposure is still unsupported as a complete five-year county assessment.

## Traffic: concrete supplemental inputs found

The official [Maryland GIS traffic page](https://roads.maryland.gov/mdotsha/pages/index.aspx?PageId=838)
links road-segment and count-location products. Its segment service describes
the current data as **2025**, has historical `AADT_2021` through `AADT_2024`,
and uses `AADT` for current-year values. It is a polyline service, not just
station points. The official [DelDOT traffic page](https://deldot.gov/Publications/manuals/traffic_counts/index.shtml)
links its interactive map; that map's configuration resolves to FirstMap
`DE_Assets/FeatureServer/10`, **TRAFFIC COUNTS LAST 10 YEARS**. Its explicit
field aliases map `CURRENT_AADT` to 2025 and `_LAST_YEAR_1` through `_4` to
2024 through 2021. A grouped query confirms `CURRENT_YEAR=2025`.

| AADT estimate year | MD positive-AADT line records | DE positive-AADT line records | Readiness |
|---|---:|---:|---|
| 2021 | 9,939 | 4,070 | Real annual attributes; selected-road spatial coverage unverified |
| 2022 | 9,939 | 4,099 | Same limitation |
| 2023 | 9,941 | 4,113 | Same limitation |
| 2024 | 9,947 | 4,094 | Same limitation |
| 2025 | 10,013 | 4,134 | Year verified from metadata/current-year field; equivalence unverified |

These are counts across each state product, **without the baseline HPMS
functional-class filter**, not road miles, unique routes, or complete counties.
Maryland has 10,013 total segment records and 24 named county groups; Delaware
has 4,134 total segment records. All six bounded sample features have nonempty
line paths and values for all five years. Three samples per state cannot
establish geometry validity, statewide coverage, or road identity. Positive
record counts exclude null, zero and negative values, without asserting what
zero means. Lower historical counts indicate missing history on some current
segments, not zero historical traffic.

Direct definitions and query evidence:

- [Maryland segment layer](https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_SHA_Annual_Average_Daily_Traffic/FeatureServer/1).
- [Delaware historical segment layer](https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Transportation/DE_Assets/FeatureServer/10).
- [Saved metadata, counts, samples and exact query parameters](supplemental-metadata.json).

**Comparability checks required before using these inputs:**

1. Maryland county IDs are state codes, not Census FIPS: the live grouped query
   maps code 5 to Caroline and 15 to Montgomery, for example. Use county names
   plus an explicit verified crosswalk and spatial validation. Delaware needs
   county assignment from roadway identifiers or spatial clipping; the queried
   historical line layer has no county field. Do not reuse HPMS county filters.
2. Historical AADT columns are attached to a currently published segment
   geometry. They do **not** establish historical alignment, segmentation or
   roads that have disappeared. Match against each year's existing TIGER
   S1100+S1200 files; test changed routes and overlaps, preserve the 25 m rule
   for comparison, and report unmatched exposed length. Do not relabel current
   geometry as a contemporaneous historical road inventory.
3. Preserve AADT as annual estimates, including agency factored estimates.
   Maryland samples distinguish counted/factored values. Delaware samples
   have last-count years such as 2005/2017 while reporting 2025 estimates.
   DelDOT's [2025 methods introduction](https://deldot.gov/Publications/manuals/traffic_counts/pdfs/2025/Vehicle%20Volume%20Summary%20Book%20Introduction.pdf)
   explains annual growth adjustments and introduces **new urban/rural growth
   factor groups in 2025**. That is a potential series break to assess, not
   evidence that the old count was freshly measured in 2025.
4. Reconcile product populations and both directions of divided roads before
   joining. DelDOT's introduction contains differing inventory totals (3,648
   and 3,614); neither equals the 4,134 live GIS features. Splits, duplicates,
   scope changes or revisions must be checked rather than assumed.
5. Compare state AADT against HPMS in overlapping years on matched routes and
   exposed segments, retaining functional-class restrictions where applicable.
   Maryland exposes functional class; the queried Delaware history layer does
   not. Supplementing missing HPMS with state values changes the named traffic
   source and requires a documented join/priority policy and Gina's review.

**Conclusion:** 2025 traffic is no longer an unlocated source for either state.
It is an **available supplemental annual-estimate candidate**, not a validated
replacement for HPMS. No existing traffic calculation was changed.

## Flood: five-year imagery exists; annual flood exposure needs a new method

**Best candidate for review: USGS Landsat Collection 2 Level-3 DSWE.** Its
[official definition](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-3-dynamic-surface-water-extent-science-product)
describes 30 m, acquisition-based surface-water classifications with quality
masks. The [USGS STAC collection](https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l3-dswe)
advertises a record beginning in 1982. Ten bounded catalog searches returned
one acquisition-dated item for **each state bounding box in each year
2021–2025**. A bounding-box hit may cover only part of a state or neighboring
land; it does not establish observations for every county, road or flood event.
No raster was downloaded and no pixel-quality coverage was measured.

This is surface water, not an annual flood-event inventory. A proposed flood
method must separate permanent/seasonal water and tides from newly inundated
land, define event windows and valid observations, and address cloudy or
between-pass flood peaks. The product includes cloud/shadow/snow and land-cover
masking; developed-area masking and 30 m pixels require particular road-level
validation. Absence of detected water cannot be assumed to mean no flooding.

Supplement with [NOAA Storm Events](https://www.ncei.noaa.gov/access/storm-events-database/search)
for reported event dates/locations in the target years and
[USGS flood-inundation libraries](https://apps.usgs.gov/fim/)
and streamgage observations for local checks. NOAA event reports are not full
inundation polygons. USGS libraries depict selected reaches and modeled stages,
not wall-to-wall annual observed floods. Any stage reconstruction must use
calendar-year observation windows; a water-year annual peak is not a
calendar-year event series. Neither is a direct NFHL replacement.

[NASA OPERA DSWx-HLS](https://www.jpl.nasa.gov/go/opera/products/) is a useful
later-period cross-check, but its record starts **April 2023**: no 2021/2022
support, and no January–March 2023 support from this product. Do not fill those
gaps with a current map or stitch different sensors without comparison/QA.

**Method change:** observed inundation would replace mapped SFHA exposure.
Annual event frequency cannot silently replace FEMA `IFLD_AFREQ`. Both the
footprint and frequency require approval. All five years remain unsupported
as validated county flood scores, despite imagery catalog availability.

## Wildfire: supplemental perimeters reveal incomplete coverage

[NIFC WFIGS](https://data-nifc.opendata.arcgis.com/pages/d6ef1367fadc4405b5f09c98e52ed972)
is an authoritative perimeter candidate. Small COUNT queries on its
[full perimeter service](https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/WFIGS_Interagency_Perimeters/FeatureServer/0)
filtered discovery dates to each target year, incident category `WF`, and
origin state MD/DE. Returned feature counts were:

| Origin state | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| Maryland | 0 | 3 | 4 | 5 | 10 |
| Delaware | 0 | 0 | 0 | 0 | 0 |

These are **query feature counts, not complete incident counts or exposure**.
Origin-state filters miss cross-border fires and records with missing state
attributes. A spatial intersection and incident-ID deduplication are needed.
No fire polygons were downloaded or tested for completeness here.

Zero returned features are especially unsafe as hazard zeros:
[Delaware Forest Service](https://agriculture.delaware.gov/forest-service/wildland-fire/)
reports assisting with **eight wildfires in 2025**, while this WFIGS query
returns none. That establishes a coverage/definition mismatch, not zero fires.
Maryland's [2025 Forest Service report](https://dnr.maryland.gov/forests/Documents/fire/2025-Annual-Wildfire-Report.pdf)
reports 172 wildfire responses and explicitly excludes some statewide wildfire
statistics. It points to MFIRS for statewide statistics. State response reports
can check inventory coverage but do not supply complete road-intersection
polygons. Incident-level state geometry/access remains unverified; no agency
was contacted.

[MTBS](https://www.mtbs.gov/) remains a consistent large-fire candidate, with
a 500-acre eastern threshold and both wildfire and prescribed-fire records.
Its [availability notice](https://www.mtbs.gov/data-availability) still describes
2023–2025 mapping in progress. A projected completion date does not establish
completion. Earlier-year products do not establish complete all-fire coverage
for MD/DE. Prescribed burns must be kept distinguishable; no inclusion policy
was selected here.

**Method change:** unioned observed fire footprints would replace WHP High/Very
High potential. Incident matching, overlaps, prescribed-fire rules and frequency
definitions require review. Event perimeters and counts cannot be substituted
for either WHP or `WFIR_AFREQ` without changing the assessed question. Complete
annual county wildfire exposure remains unsupported for every target year.

## What remains supported, unsupported and unchanged

| Input or result | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| MD/DE annual TIGER file headers | Available | Available | Available | Available | Available |
| MD/DE state annual AADT attributes | Available; match QA pending | Same | Same | Same | Available; method/coverage QA pending |
| MD/DE DSWE bbox catalog samples | Found; pixel/event QA pending | Same | Same | Same | Same |
| Complete observed annual flood footprint | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported |
| Complete observed annual wildfire footprint | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported |
| Annual hazard frequency, national rank and stress | Not validated | Not validated | Not validated | Not validated | Not validated |

“Unsupported” describes current evidence/readiness, not proof that further
agency records cannot help. There are no published annual county scores.
The research document specifies NFHL, WHP, NRI frequency and HPMS traffic;
state traffic supplements preserve AADT units and can preserve the exposed-length
weighted formula, but change the source. Observed footprints change the hazard
metric. Keep the existing national min–max frequency scaling, hazard-specific
rank framework and stress formula unchanged in the current assessment. A
two-state audit cannot establish nationwide annual comparison ranks.

The research's primary-road wording versus the saved Maryland S1100+S1200 scope
is still a review discrepancy; no source alternative silently resolves it.
No current snapshot is relabeled as annual data and no year is substituted.

Recommended next review: state-traffic supplementation first; DSWE plus event/
gage checks for flood; WFIGS plus MTBS/state inventory reconciliation for fire.
Approve definitions and a small event/road validation sample before any full
download or historical processing. These are recommendations, not a selected
historical method. EC2 remains paused and the current Maryland results and
inland-flood calculation remain unchanged.

Saved evidence is under 0.6 MB. Validation checks query counts, five-year field
mappings, sample limits and acquisition years; they do not validate hazard maps.
All 51 existing preservation-baseline file hashes still match.
