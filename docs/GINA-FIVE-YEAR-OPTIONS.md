# Five-year options for Gina’s review

**Selected by the user for pilot preparation:** annual roads/AADT against one
fixed hazard baseline, for Maryland and Delaware in **2021–2025**. Gina's review
is pending before annual stress publication or nationwide processing. Five
complete comparable years have not been validated. The saved Maryland current
assessment remains separate and unchanged.

**Label:** “Infrastructure exposure by year — fixed hazard baseline.” Changes
describe roads/traffic exposed to fixed mapped hazards, not annual changes in
floods or fires. See the [concrete pilot package](pilots/md-de-fixed-baseline/REVIEW.md),
[pinned manifest](pilots/md-de-fixed-baseline/manifest.json) and 270-job readiness
table. National NRI cached bytes are pinned; all 48 Maryland frequency comparisons
match the current results. Original flood geometry remains a blocking gap.

| | 1. Selected for pilot preparation: fixed hazard maps | 2. Deferred alternative: observed events |
|---|---|---|
| Question answered | How did roads/traffic exposed to one fixed modeled hazard baseline change? | Which roads/traffic intersected qualifying observed hazards in each year? |
| Retained from Maryland | S1100/S1200 roads; exposed-road/total-road ratio; 25 m traffic matching and length-weighted AADT; hazard-specific comparison framework. | The same selected-road, spatial-overlay and traffic calculations can be retained. |
| Changes from Maryland | Replace the single road/AADT snapshot with verified year-specific infrastructure. Freeze and label WHP/NFHL/NRI vintages explicitly. Annual frequency is **not** re-estimated; this is not historical annual hazard risk. | Replace modeled WHP potential with dated fire observations, and mapped NFHL risk with an explicitly chosen annual flood-observation product. Annual frequency, event thresholds, inclusion rules and normalization require new definitions. Do not silently replace the Maryland method. |
| Main interpretation limit | Changing outputs reflect infrastructure/traffic changes against fixed hazard maps, not changing annual wildfire/flood conditions. | Mapped events reflect detection/mapping thresholds and incomplete observations; absence of a mapped event is not automatically zero exposure. |

**Data availability (MD and DE, October 18 follow-up):** TIGER road/boundary ZIP
headers are available for 2021–2025. HPMS services were verified for 2021–2024;
2025 was not listed in the queried DOT catalog. **State GIS segment services now
provide verified 2025 AADT and historical attributes for 2021–2024 in both
states.** Their exposed-road match coverage and equivalence to HPMS are still
unvalidated. Maryland uses state-specific county codes; Delaware needs spatial/
route county assignment. Current segment geometry is not proof of historical
alignment. DelDOT changed growth-factor groups in 2025, requiring comparison.
Agency factored AADT estimates are not same-year direct counts.
This limits **both** options. Baseline FEMA/TIGER release vintages were not
recorded in the saved assessment, so any fixed-map series needs pinned sources.
The exact flood service cannot query historical snapshots. WHP archives are
irregular modeled releases, and NRI frequencies are long-run estimates, not
release-year events. Five annual hazard observations are not established.

**Deferred observed-event notes (not prerequisites for this fixed-baseline pilot):**
WHP/NRI are not annual observed series. USGS DSWE
catalog samples exist for both state bounding boxes in all five years, but
surface water needs flood attribution, valid-observation coverage and event
checks. OPERA DSWx-HLS starts April 2023 and cannot fill 2021–2022. WFIGS has
incomplete coverage: the DE query returned no 2025 perimeters despite the state
reporting wildfire responses. MTBS large-fire products include prescribed fires
and recent years remain in mapping. Complete annual flood/fire footprints are
unvalidated for every target year. Research hurricane **wind** exposure differs from the
dashboard’s **inundation** label. SPEI-R25 means daily rain >25 mm during a month
with SPEI <-1, but timescale, pairing, aggregation and frequency remain unresolved.
Neither hurricane nor compound exposure has an implemented Maryland baseline
calculation to carry forward unchanged.

**Review decisions:** confirm the selected pilot interpretation, hazard baselines and
source coverage within the fixed 2021–2025 window; declare how missing
data and prescribed fire are handled; and specify whether national rankings use
a fixed reference or within-year populations. Within-year ranks alone do not
establish absolute change across years.

**Status:** fixed-baseline pilot preparation is authorized; the observed-event
alternative is deferred. All five-year dashboard results remain unavailable
until inputs are validated and the interpretation is reviewed.
Existing experimental annual utilities are not scheduled and must not be treated
as an approved historical method. **EC2 launch remains paused** while feasibility
and review take priority. The prepared Delaware benchmark remains current-only,
using Maryland’s baseline methodology; it cannot collect five years automatically.

Evidence and official source links:
[supplemental-source findings](audits/md-de-five-year-feasibility/SUPPLEMENTAL-SOURCES.md),
[MD/DE five-year feasibility report](audits/md-de-five-year-feasibility/REPORT.md),
[source audit](audits/delaware-history-2021-2025-source-audit.json),
[workflow limitations](audits/HISTORICAL-WORKFLOW-STATUS.md).
