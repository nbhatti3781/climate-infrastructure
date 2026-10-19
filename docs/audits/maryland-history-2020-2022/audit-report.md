# Maryland 2020–2022 historical wildfire completeness audit

Read-only audit: 24 county equivalents × 3 years. No year selectors, scores, or application/pipeline changes. National fire attributes were screened, but county road/AADT analysis covers Maryland only.

## Files and geometry

Annual Census TIGER primary/secondary-road files and Maryland county boundaries were downloaded for each year. Official DOT HPMS_FULL_MD_2020, HPMS_FULL_MD_2021 and HPMS_FULL_MD_2022 layers supplied geometry and same-year AADT. MTBS supplied annual mapped burned-area boundaries. Download hashes are recorded in summary.json and source-cache-manifest.json.

| Year | HPMS records checked | Missing geometry | Invalid geometry | Missing/invalid AADT | Zero AADT flagged | Mapped Maryland fire types |
|---|---:|---:|---:|---:|---:|---|
| 2020 | 106,762 | 155 | 0 | 12022 | 0 | {} |
| 2021 | 47,757 | 96 | 0 | 5969 | 0 | {} |
| 2022 | 47,815 | 118 | 0 | 5946 | 0 | {"Wildfire": 1} |

The missing/invalid AADT column counts records after the year and geometry
checks. Counting null AADT independently across all downloaded records gives
12,040 (2020), 5,982 (2021), and 5,955 (2022); some also have missing geometry.
These checks are sequential in the county CSV, so those categories should not
be read as independent totals.

All 19 retrieved regional MTBS polygons have geometry and are valid. This regional query also includes neighboring states; Maryland event counts above use actual boundary intersections. All 3,011 national fire attribute records have nonzero area and a centroid; that screen is not a national polygon-validity audit.

## Road coverage and AADT match rates

The research specifies S1100 primary roads; the current dashboard uses S1100+S1200. Both are measured separately without changing either. HPMS is restricted to functional classes ≤4 to align with the existing pipeline. Positive, valid AADT geometry is clipped to its reported county; coverage is road length within 25 metres of those lines. This proximity audit does not establish route identity or unique segment-to-AADT assignment. Zero-valued AADT is flagged separately rather than assumed to be measured traffic. No matching threshold is asserted to establish readiness.

| Year | Road scope | County-years with roads | Total road miles | State length-weighted AADT match | County match range |
|---|---|---:|---:|---:|---|
| 2020 | S1100 | 16/24 | 1,393.67 | 67.87% | 51.03–100.00% |
| 2020 | S1100+S1200 | 24/24 | 7,081.44 | 64.48% | 18.15–91.90% |
| 2021 | S1100 | 16/24 | 1,393.35 | 72.42% | 55.47–100.00% |
| 2021 | S1100+S1200 | 24/24 | 7,098.16 | 65.49% | 18.40–93.57% |
| 2022 | S1100 | 16/24 | 1,393.35 | 73.08% | 55.42–100.00% |
| 2022 | S1100+S1200 | 24/24 | 7,097.56 | 65.64% | 18.61–93.67% |

## Wildfire-exposed roads

Only FIRE_TYPE=Wildfire contributes to the audit footprint. Prescribed Fire and any other fire types are listed and excluded; ambiguous types are not relabeled. This is a proposed annual audit rule requiring Gina’s review, not a replacement for WHP.

| Year | County | Road scope | Wildfire-exposed miles | AADT match on exposed roads |
|---|---|---|---:|---|
| — | No audited road intersects a mapped Wildfire polygon | Both | 0 | Not applicable |

Zero exposed road miles means the exposed-road AADT match rate is not applicable. It does not show that a county had no fires or no wildfire potential. See county-year-audit.csv for every county/year/scope, including counties without S1100 roads.

## Remaining limitations and decisions

- MTBS maps large qualifying fires (at least 500 acres in the eastern U.S.), including prescribed fires. Its mapped inventory is not a census of all incidents. Independent event completeness against incident records remains unverified.
- This audit retrieves source records as currently published; it does not reconstruct historical publication vintages.
- Annual road geometry and AADT exist, but incomplete spatial match coverage and road-scope differences prevent declaring all county-years complete.
- The current WHP map describes modeled hazard potential. Annual burned-area boundaries describe mapped fires that occurred. FEMA WFIR_AFREQ is not an observed annual event count and cannot simply be relabeled 2020, 2021 or 2022.
- Gina must review the annual method, frequency definition, prescribed-fire policy and treatment of unmatched traffic before annual scores or dashboard year options are added.
- No national county consequence ranking, annual frequency, consequence or stress was calculated.

Verification at audit completion, before the subsequent assessment-label update: 144 unique scope-specific rows covering all 72 Maryland county-years; HPMS IDs are unique and match source record counts; 70 baseline application/pipeline/output files remained byte-for-byte unchanged.

## Authoritative sources

- MTBS scope: https://www.mtbs.gov/
- MTBS 2022 mapping release: https://www.mtbs.gov/articles/announcement/mtbs-2022-fire-quarterly-release-august-22-2024
- MTBS geometry service: https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/EDW_MTBS_v1/FeatureServer/0
- Census annual files: https://www2.census.gov/geo/tiger/
- DOT historical HPMS services: https://geo.dot.gov/server/rest/services/Hosted
