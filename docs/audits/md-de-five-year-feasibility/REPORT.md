# Maryland and Delaware: five-year source feasibility

Checked October 18, 2026. Fixed target window: **2021–2025**; historical method not approved.
**Five comparable annual hazard assessments are not established by the existing
sources. Keep EC2 launch paused.** No historical method was selected, no annual
scores were produced, and no existing assessment outputs were refreshed.

**Current direction:** the user has since selected fixed-baseline pilot
preparation for 2021–2025. See the [pilot package](../../pilots/md-de-fixed-baseline/REVIEW.md).
Annual observed flood/fire datasets discussed here are not prerequisites for
that interpretation. Complete pinned baseline coverage and annual infrastructure
inputs are still required; score publication awaits Gina's review.

**Follow-up:** the [supplemental-source investigation](SUPPLEMENTAL-SOURCES.md)
found state segment AADT attributes for all five years, including 2025 in both
states, and USGS surface-water catalog samples for every state/year. These are
candidates requiring spatial/method validation, not completed historical results.
The original HPMS-catalog gap below remains specific to that catalog.

## Scope and evidence

The current assessment combines modeled/mapped hazard inputs with a road/traffic
snapshot. Its analysis date does not identify a year in which floods or fires
occurred. This audit starts with the endpoints in `pipeline/config.py`, then
examines official same-agency archives. Annual archived files are prospective
inputs, not proof that they reproduce the frozen Maryland assessment.

[Machine-readable evidence](metadata-samples.json) contains source URLs, live
capabilities, grouped counts, dataset-year values and at most three traffic line
features per state/year. The repeatable standard-library audit is
`pipeline/audit_md_de_archive_feasibility.py`; `--resume` reuses successful probes
and retries failed probes. Requests use three workers, 20-second timeouts and a
1 MiB per-response limit. ZIP files were probed with HEAD only. About 1.1 MB of
metadata/HTML/sample evidence was saved; no full datasets were downloaded.
Headers and samples cannot establish complete county geometry or road matching.

## Exact sources, releases and represented time

| Existing input | Official archive/live finding | Annual comparability |
|---|---|---|
| Census TIGERweb roads, layers 2/6; county boundaries | Archived TIGER/Line primary/secondary-road files for both states and national county files respond HTTP 200 for every year 2021–2025. | Five **editions**, not five verified observations of road construction. Census states legal boundaries/names are as of January 1 for the 2025 edition. Geometry, classifications, revisions and clipping need year-specific QA. Saved live TIGERweb retrievals do not pin an annual edition. |
| FHWA HPMS 2024, Socrata `42um-tgh5` | Exact endpoint has `year_record=2024` in the selected MD/DE counts. Its description says the spatial full join with ARNOLD includes a section when just one data item exists. DOT Hosted archives expose MD and DE services for 2021–2024; none named 2025 in the queried catalog. | A section is not proof of AADT. Annual archives change field names, segmentation and metadata. The Socrata catalog search returned 2024 products plus 2016 dynamically segmented data; it did not establish five annual equivalents to the exact endpoint. |
| FEMA NFHL Flood Hazard Zones, layer 28 | Exact service reports `isDataVersioned=false`, `timeInfo=null` and `supportsQueryWithHistoricMoment=false`. MSC offers effective/historical map products, but its archive page could not be retrieved reliably in this audit. | The current endpoint cannot reconstruct five annual snapshots. Historical FIRM/panel effective dates describe map revisions, not observed floods. County-by-year archive completeness and geodatabase availability remain unverified. Do not infer that no historical maps exist. |
| USDA WHP classified ImageServer | Exact metadata identifies **WHP2023**, based on landscape conditions at end-2020. Official product page gives June 2024 release; archive lists 2020, 2018, 2014 and WFP2012. | Irregular modeled products, not annual fire observations. Different model/fuels inputs and older product definitions prevent treating those releases as consecutive observation years. Keep classes High/Very High (4/5); do not substitute NHS/burn-probability layers. |
| FEMA NRI county frequency | Exact endpoint returns 27 MD/DE records with `NRI_VER=December 2025`. No time dimension or historical version query is advertised. Official technical-documentation archives include v1.18.1 and v1.17.0; update documentation describes changed periods of record and wildfire modeling inputs. | `IFLD_AFREQ` and `WFIR_AFREQ` are long-run/annualized estimates, not events in the release year. Annual counts cannot be obtained by relabeling releases. Five comparable yearly frequencies were not found; complete release inventory remains unverified because FEMA archive access was unreliable. |

The live NRI version is evidence about today's service, **not proof of the version
used in saved Maryland results**. Those results do not record an NRI version.
Howard's saved flood frequency equals the current live value, but one equal
value cannot establish release identity. Do not silently update the baseline or
its national frequency extrema.

WHP2023 also uses past fire locations from approximately 1992–2020; neither that
input interval nor the June 2024 release identifies a year of observed exposure.
The saved baseline does not pin county-specific flood-map effective dates or
the exact NRI hazard-specific source periods. Those periods and their changes
between releases remain unverified here; archive/documentation access must be
resolved before a release-to-release comparison is proposed as comparable.

## Annual traffic availability and coverage

Counts below are source records with `f_system <= 4`, **not road miles, unique
routes, AADT match rates or completed counties**. Invalid means null or negative
AADT, counted independently of geometry. Zero AADT is not included in this
category and needs separate source-definition review. Dataset-year distinct
values agree with each service's named year for all eight available services.

| Dataset year | MD records / missing-invalid AADT | DE records / missing-invalid AADT | Coverage finding |
|---|---:|---:|---|
| 2021 | 47,757 / 5,982 | 10,562 / 305 | MD has all 24 county FIPS groups plus a null group (5,942 records); DE has three county groups. |
| 2022 | 47,815 / 5,955 | 15,712 / 4,820 | MD has 24 county groups; DE has three. Presence is not spatial coverage validation. |
| 2023 | 47,934 / 5,962 | 15,644 / 4,782 | County IDs are inconsistent with FIPS in **both** states; MD has 12 groups including null, DE has codes 1, 4 and 70. County-code filtering alone is unreliable. |
| 2024 | 61,060 / 7,306 | 16,326 / 4,903 | MD has all 24 county groups plus 330 null-county records; DE has three groups. Exact Socrata selected-record totals equal these Hosted totals, which does not establish feature/attribute equivalence. |
| 2025 | Not listed in queried DOT Hosted catalog | Not listed in queried DOT Hosted catalog | No verified segment-level geometry/AADT source from these queries. This is not proof that state agencies have none. |

[County-by-year declared-ID counts](county-year-source-counts.csv) list all 27
county equivalents for each candidate year. Empty or suspect ID groups remain
unknown; they are never converted into zero road exposure. A whole-state spatial
county assignment would be needed to resolve incorrect/null IDs without dropping
roads. This audit does not implement that historical processing.

All 24 sampled traffic features (3 × 2 states × 4 years) returned nonempty paths;
that is not a full validity/coverage check. Samples are bounded API records,
not a representative statistical sample. Some 2024 samples have null AADT and
null AADT date metadata. MD2022 samples carry 2022 dates; DE2022 samples include
stored dates in 2000 and 2019, and DE2023 samples include 2000, 2019 and null.
For the **exact** 2024 Socrata endpoint, nonnull MD `aadt_d` spans only
2024-12-31; DE spans 2000-01-01 to 2024-01-01. These extrema exclude nulls.

These are stored metadata dates, not verified original counter dates. A 2000
value may be a source convention/default; its meaning needs confirmation.
FHWA defines AADT as a reporting-year estimate and permits growth adjustments
for sections not counted that year. Thus an older stored date alone neither
invalidates the annual estimate nor proves it was adjusted correctly. Year-field
agreement does not establish same-year direct measurements.

Reuse of the earlier [Maryland 2020–2022 geometry audit](../maryland-history-2020-2022/audit-report.md)
avoided new downloads. It found S1100+S1200 road-to-positive-AADT proximity match
coverage of **65.49% (2021)** and **65.64% (2022)** statewide, with county ranges
18.40–93.57% and 18.61–93.67%. Those are all-road 25 m proximity audit metrics,
not current hazard-exposed-road consequence coverage. They do not validate
Delaware or 2023–2025. New full geometry and exposed-road match rates remain
unavailable for those county-years.

## Method differences and recommendations for review

1. **Closest to the current assessment:** annual TIGER/HPMS against one explicitly
   frozen WHP/NFHL/NRI baseline. This measures infrastructure/traffic changes,
   not changing annual hazard conditions. Resolve traffic gaps, pin source
   hashes/vintages and approve fixed versus within-year national rankings first.
   Keep the target **2021–2025**. State segment AADT supplements now offer a
   possible 2025 input; validate coverage and source compatibility rather than
   substituting an older year. See the follow-up investigation above.
2. **Observed yearly events:** evaluate MTBS wildfire perimeters and a separately
   validated annual flood-inundation source. MTBS includes prescribed fires and
   uses a 500-acre eastern threshold, so a missing polygon cannot mean no fire.
   Its current availability notice still describes 2023–2025 mapping in progress;
   an expected completion date is not evidence of completion. FEMA/NFHL does not
   fill the annual observed-flood-footprint gap. NOAA event reports or gauges
   may support event checks but are not equivalent road-intersection polygons.
   This option changes hazard footprints, frequency definitions and possibly
   normalization; Gina's review is required before implementation.

Research wording specifies S1100 primary roads, while the existing Maryland app
uses S1100+S1200. Preserve the existing baseline and surface this discrepancy for
review; do not silently change road scope in a historical comparison. Preserve
the existing flood `SFHA_TF='T'` treatment as well, including its coastal/tidal
classes. No alternative is selected and no annual dashboard years are enabled.

## Launch gate and remaining blockers

Keep EC2 launch paused until Gina reviews the interpretation and sources
are demonstrated adequate within 2021–2025. Unvalidated 2025 supplemental
traffic coverage, anomalous/null county IDs,
unverified archive snapshots, incomplete AADT matches and an unvalidated annual
flood footprint are data/method blockers; larger compute does not resolve them.
No claim of five-year or nationwide completion is supported. The prepared
Delaware benchmark performs only the existing **current** assessment and cannot
automatically collect five historical years. No remote job was launched.

Validation: audit JSON parses; expected 10 state/year road probes, 5 boundary
probes and 8 three-feature traffic samples pass; all 51 saved preservation
baseline hashes match. No county outputs, hazard methods or caches were modified.

## Official references

- [Census 2025 TIGER/Line definitions](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2025.html) and [annual file archive](https://www2.census.gov/geo/tiger/).
- [DOT Hosted service catalog](https://geo.dot.gov/server/rest/services/Hosted?f=json) and [exact HPMS 2024 metadata](https://data.transportation.gov/api/views/42um-tgh5.json).
- [FHWA HPMS AADT guidance](https://www.fhwa.dot.gov/policyinformation/hpms/fieldmanual/page07.cfm) and [public-release geometry cautions](https://www.fhwa.dot.gov/policyinformation/hpms/shapefiles.cfm).
- [Exact NFHL layer capabilities](https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28?f=pjson) and [MSC archive/product search](https://msc.fema.gov/portal/advanceSearch) (archive access unverified).
- [USDA WHP source and represented conditions](https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential) and [archived versions](https://research.fs.usda.gov/firelab/products/dataandtools/wildfire-hazard-potential-archived-products).
- [Exact NRI county layer](https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0), [FEMA update documentation](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index-data-version-and-update-documentation.pdf), [v1.18.1 archive documentation](https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/Archive/v118_1/fema_national-risk-index_technical-documentation.pdf), and [current technical documentation](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf). FEMA PDF details were checked through official indexed excerpts; complete PDFs were not downloaded.
- [MTBS coverage and fire types](https://www.mtbs.gov/) and [current mapping availability](https://www.mtbs.gov/data-availability).
