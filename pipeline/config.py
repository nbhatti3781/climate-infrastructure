from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "cache"
PROCESSED = DATA / "processed"

TIGER_COUNTIES = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/57/query"
TIGER_PRIMARY_ROADS = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/2/query"
TIGER_SECONDARY_ROADS = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query"
FEMA_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
FEMA_NRI_COUNTIES = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0/query"
HPMS_2024 = "https://data.transportation.gov/resource/42um-tgh5.json"

# NAD83 / UTM zone 18N covers Howard County. Projected coordinates make
# Shapely length measurements meaningful in metres.
ANALYSIS_SRID = 26918

for directory in (CACHE, PROCESSED):
    directory.mkdir(parents=True, exist_ok=True)
