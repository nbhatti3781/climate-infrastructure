"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Database,
  Layers3,
  MapPin,
  Search,
} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

// ── types ────────────────────────────────────────────────────────────────────

type Hazard = "flood" | "wildfire" | "hurricane" | "compound";

type CountyFeature = {
  type: "Feature";
  properties: { GEOID: string; NAME: string; BASENAME: string; STATE: string };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};

type CountyResult = {
  geoid: string;
  county: string;
  state: string;
  status: string;
  hazard_label: string;
  normalized_frequency: number | null;
  total_major_road_miles: number | null;
  flood_exposed_major_road_miles: number | null;
  transportation_exposure_percent: number | null;
  transportation_consequence_raw_aadt: number | null;
  transportation_consequence_normalized: number | null;
  transportation_stress: number | null;
  hpms_coverage_pct_of_exposed_length: number | null;
  ve_zone_exposed_miles?: number | null;
  ve_zone_exposed_pct_of_sfha_exposure?: number | null;
  annualized_frequency: number | null;
  qa_notes?: string[];
  deployment_hold?: boolean;
};

// ── constants ────────────────────────────────────────────────────────────────

const hazards: { id: Hazard; label: string; short: string; color: string }[] = [
  { id: "flood",     label: "Inland flood",         short: "Flood",    color: "#2563eb" },
  { id: "wildfire",  label: "Wildfire",              short: "Fire",     color: "#e25822" },
  { id: "hurricane", label: "Hurricane inundation",  short: "Surge",    color: "#0891b2" },
  { id: "compound",  label: "Drought–heavy rain",    short: "Compound", color: "#b7791f" },
];

const states = [
  ["01","Alabama"],["02","Alaska"],["04","Arizona"],["05","Arkansas"],["06","California"],
  ["08","Colorado"],["09","Connecticut"],["10","Delaware"],["11","District of Columbia"],
  ["12","Florida"],["13","Georgia"],["15","Hawaii"],["16","Idaho"],["17","Illinois"],
  ["18","Indiana"],["19","Iowa"],["20","Kansas"],["21","Kentucky"],["22","Louisiana"],
  ["23","Maine"],["24","Maryland"],["25","Massachusetts"],["26","Michigan"],["27","Minnesota"],
  ["28","Mississippi"],["29","Missouri"],["30","Montana"],["31","Nebraska"],["32","Nevada"],
  ["33","New Hampshire"],["34","New Jersey"],["35","New Mexico"],["36","New York"],
  ["37","North Carolina"],["38","North Dakota"],["39","Ohio"],["40","Oklahoma"],["41","Oregon"],
  ["42","Pennsylvania"],["44","Rhode Island"],["45","South Carolina"],["46","South Dakota"],
  ["47","Tennessee"],["48","Texas"],["49","Utah"],["50","Vermont"],["51","Virginia"],
  ["53","Washington"],["54","West Virginia"],["55","Wisconsin"],["56","Wyoming"],
  ["60","American Samoa"],["66","Guam"],["69","Northern Mariana Islands"],
  ["72","Puerto Rico"],["78","U.S. Virgin Islands"],
] as const;

const LIMITATIONS = [
  {
    id: "scope",
    heading: "Major roads only (S1100 + S1200)",
    body: 'Analysis covers Census-classified major roads — S1100 limited-access highways and S1200 principal arterials (US/state routes) — from TIGERweb MapServer layers 2 and 6. Local roads (S1400) and ramps are excluded. All 24 Maryland counties now have road network data.',
  },
  {
    id: "sfha",
    heading: "Flood footprint includes coastal VE zones",
    body: 'The FEMA SFHA footprint contains both riverine/inland zones (AE, A, AO) and coastal velocity/wave zones (VE). In several Maryland counties, a portion of the exposed road length lies in VE zones. These outputs are labeled "FEMA SFHA road exposure" not "inland flood" until a scope decision is made. Excluding VE zones would not fully resolve the issue — AE zones in tidal counties also include estuarine flooding.',
  },
  {
    id: "stress",
    heading: "Stress score incomplete — no county comparisons yet",
    body: "Step 3 (traffic consequence) requires national percentile ranking across all U.S. counties. Raw AADT is shown but not normalized. Until that ranking runs, the final stress score cannot be computed and no valid county-to-county comparison is possible.",
  },
  {
    id: "exposure",
    heading: "Exposure ≠ damage or closure risk",
    body: "A road passing through a FEMA Special Flood Hazard Area is in a mapped 1%-annual-chance flood zone. It does not mean the road floods, closes, sustains damage, or fails. No engineering condition, road elevation, drainage design, or failure probability is modeled.",
  },
  {
    id: "coverage",
    heading: "HPMS traffic data: 56–100% of exposed road length matched",
    body: "Traffic counts (AADT) are matched from FHWA HPMS 2024 using a 25-meter spatial buffer. Unmatched segments contribute to exposure but not the AADT average.",
  },
  {
    id: "validated",
    heading: "Validated results: Maryland only",
    body: "The pipeline has been run and QA-reviewed for Maryland's 24 counties. Results for other states are not yet available.",
  },
];

// ── helpers ──────────────────────────────────────────────────────────────────

function rings(feature: CountyFeature): number[][][] {
  if (feature.geometry.type === "Polygon") return feature.geometry.coordinates as number[][][];
  return (feature.geometry.coordinates as number[][][][]).flat();
}

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtAadt(n: number | null | undefined): string {
  if (n == null) return "—";
  return Math.round(n).toLocaleString();
}

// ── sub-components ───────────────────────────────────────────────────────────

function LimitationsBanner() {
  const [open, setOpen] = useState(false);
  return (
    <div className="limitations-banner">
      <button
        className="limitations-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <AlertTriangle size={14} />
        <span>Preliminary data — known limitations and scope boundaries</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <ul className="limitations-list" role="list">
          {LIMITATIONS.map((l) => (
            <li key={l.id}>
              <strong>{l.heading}</strong>
              <p>{l.body}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CountyMap({
  features,
  selected,
  onSelect,
}: {
  features: CountyFeature[];
  selected?: string;
  onSelect: (f: CountyFeature) => void;
}) {
  const projection = useMemo(() => {
    const points = features.flatMap((f) => rings(f).flat());
    if (!points.length) return null;
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const width = Math.max(maxX - minX, 0.01);
    const height = Math.max(maxY - minY, 0.01);
    const scale = Math.min(920 / width, 500 / height);
    const ox = (960 - width * scale) / 2;
    const oy = (540 - height * scale) / 2;
    return (p: number[]) => [
      ox + (p[0] - minX) * scale,
      540 - (oy + (p[1] - minY) * scale),
    ];
  }, [features]);

  if (!projection) return <div className="map-loading">Loading county boundaries…</div>;

  const path = (f: CountyFeature) =>
    rings(f)
      .map((ring) =>
        ring.map((p, i) => `${i ? "L" : "M"}${projection(p).join(",")}`).join(" ") + " Z"
      )
      .join(" ");

  return (
    <svg className="county-map" viewBox="0 0 960 540" role="img" aria-label="Interactive county map">
      {features.map((f) => (
        <path
          key={f.properties.GEOID}
          d={path(f)}
          className={`county${selected === f.properties.GEOID ? " selected" : ""}`}
          onClick={() => onSelect(f)}
          tabIndex={0}
          role="button"
          aria-label={f.properties.NAME}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(f)}
        />
      ))}
    </svg>
  );
}

function StatusDot({ status }: { status: "done" | "working" | "pending" }) {
  return <span className={status === "done" ? "done" : status === "working" ? "working" : ""} />;
}

function CountyDetail({
  feature,
  result,
  loading,
  hazard,
}: {
  feature: CountyFeature;
  result: CountyResult | null;
  loading: boolean;
  hazard: Hazard;
}) {
  const isFlood = hazard === "flood";
  const hasData = isFlood && result && result.status !== "no_major_roads";
  const noMajorRoads = isFlood && result?.status === "no_major_roads";

  return (
    <>
      <div className="eyebrow">County profile</div>
      <h2>{feature.properties.NAME}</h2>
      <p className="geoid">GEOID {feature.properties.GEOID}</p>

      {loading && (
        <div className="metric-card">
          <span>Loading…</span>
          <strong>—</strong>
        </div>
      )}

      {!loading && hazard !== "flood" && (
        <div className="metric-card">
          <span>{hazards.find((h) => h.id === hazard)?.short} exposure</span>
          <strong>Pending</strong>
          <small>Preprocessing not yet available for this hazard</small>
        </div>
      )}

      {!loading && isFlood && !result && (
        <div className="metric-card">
          <span>Flood exposure</span>
          <strong>No data</strong>
          <small>County results not available for this state yet</small>
        </div>
      )}

      {!loading && noMajorRoads && (
        <>
          <div className="metric-card">
            <span>Final Flood Stress</span>
            <strong>N/A</strong>
            <small>No S1100/S1200 major roads intersect this county polygon</small>
          </div>
          <p className="metric-note">
            Census TIGERweb MapServer layers 2 and 6 returned no major road features
            clipped to this county boundary. Local roads are not included in this analysis.
            Frequency score: {fmt(result?.normalized_frequency, 3)}
          </p>
        </>
      )}

      {!loading && hasData && result && (
        <>
          <div className="metric-card">
            <span>Final Flood Stress</span>
            <strong>Pending</strong>
            <small>Requires nationwide AADT consequence ranking</small>
          </div>

          <div className="step-grid">
            <div className="step-card complete">
              <span>Step 1 · Frequency</span>
              <strong>{fmt(result.normalized_frequency, 3)}</strong>
              <small>Raw FEMA AFREQ: {fmt(result.annualized_frequency, 2)}/yr</small>
            </div>
            <div className="step-card complete">
              <span>Step 2 · Exposure</span>
              <strong>{fmt(result.transportation_exposure_percent, 2)}%</strong>
              <small>
                {fmt(result.flood_exposed_major_road_miles, 2)} of{" "}
                {fmt(result.total_major_road_miles, 2)} major-road miles
              </small>
            </div>
            <div className="step-card partial">
              <span>Step 3 · Consequence</span>
              <strong>
                {result.transportation_consequence_raw_aadt != null
                  ? fmtAadt(result.transportation_consequence_raw_aadt)
                  : "—"}
              </strong>
              <small>
                {result.transportation_consequence_raw_aadt != null
                  ? "Raw length-weighted AADT; national 0–1 rank required"
                  : "No HPMS match on exposed road length"}
              </small>
            </div>
          </div>

          {result.ve_zone_exposed_miles != null && result.ve_zone_exposed_miles > 0 && (
            <div className="ve-note">
              <AlertTriangle size={12} />
              <span>
                {fmt(result.ve_zone_exposed_miles, 2)} mi (
                {fmt(result.ve_zone_exposed_pct_of_sfha_exposure, 1)}% of SFHA exposure) in
                coastal VE zones
              </span>
            </div>
          )}

          <div className="formula">
            <span>Transportation Stress calculation</span>
            <code>Stress = normalized frequency × road exposure × normalized traffic consequence</code>
            <code>Exposure = flood-exposed major-road length ÷ total major-road length</code>
          </div>

          <p className="metric-note">
            Sources: FEMA NRI and NFHL, Census TIGERweb S1100+S1200 major roads, 2024 FHWA HPMS.
            {result.hpms_coverage_pct_of_exposed_length != null &&
              ` HPMS covers ${fmt(result.hpms_coverage_pct_of_exposed_length, 1)}% of exposed road length.`}{" "}
            Not damage, closure, or engineering risk.
          </p>
        </>
      )}

      {!loading && result && (
        <div className="status-list">
          <div>
            <StatusDot status={result.normalized_frequency != null ? "done" : "pending"} />
            Frequency normalization
            <strong>{result.normalized_frequency != null ? "Ready" : "Pending"}</strong>
          </div>
          <div>
            <StatusDot status={hasData ? "done" : noMajorRoads ? "pending" : "pending"} />
            Road exposure
            <strong>{hasData ? "Ready" : noMajorRoads ? "No major roads" : "Pending"}</strong>
          </div>
          <div>
            <StatusDot status={result.transportation_consequence_raw_aadt != null ? "working" : "pending"} />
            National AADT rank
            <strong>{result.transportation_consequence_raw_aadt != null ? "Required" : "Pending"}</strong>
          </div>
          <div>
            <StatusDot status="pending" />
            Final Flood Stress
            <strong>Pending</strong>
          </div>
        </div>
      )}
    </>
  );
}

// ── main page ────────────────────────────────────────────────────────────────

export default function Home() {
  const [stateFips, setStateFips] = useState("24");
  const [hazard, setHazard] = useState<Hazard>("flood");
  const [counties, setCounties] = useState<CountyFeature[]>([]);
  const [selected, setSelected] = useState<CountyFeature | null>(null);
  const [query, setQuery] = useState("");
  const [mapLoading, setMapLoading] = useState(true);
  const [mapError, setMapError] = useState("");

  // per-county data cache
  const [countyResults, setCountyResults] = useState<Record<string, CountyResult>>({});
  const [countyLoading, setCountyLoading] = useState(false);

  // Load county boundaries when state changes
  useEffect(() => {
    setMapLoading(true);
    setMapError("");
    setSelected(null);
    const params = new URLSearchParams({
      where: `STATE='${stateFips}'`,
      outFields: "GEOID,NAME,BASENAME,STATE",
      returnGeometry: "true",
      outSR: "4326",
      geometryPrecision: "3",
      maxAllowableOffset: "0.003",
      f: "geojson",
    });
    fetch(
      `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/57/query?${params}`,
      { headers: { Accept: "application/geo+json" } }
    )
      .then((r) => {
        if (!r.ok) throw new Error("Census county boundaries are temporarily unavailable");
        return r.json();
      })
      .then((data) => setCounties(data.features ?? []))
      .catch((e) => setMapError(e.message))
      .finally(() => setMapLoading(false));
  }, [stateFips]);

  // Load county result when a county is selected
  useEffect(() => {
    if (!selected) return;
    const geoid = selected.properties.GEOID;
    if (countyResults[geoid] !== undefined) return; // already cached

    setCountyLoading(true);
    fetch(`/api/county/${geoid}`)
      .then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error("Failed to load county data");
        return r.json();
      })
      .then((data) => {
        setCountyResults((prev) => ({ ...prev, [geoid]: data }));
      })
      .catch(() => {
        setCountyResults((prev) => ({ ...prev, [geoid]: null as unknown as CountyResult }));
      })
      .finally(() => setCountyLoading(false));
  }, [selected, countyResults]);

  const stateName = states.find(([id]) => id === stateFips)?.[1] ?? "State";
  const filtered = counties
    .filter((c) => c.properties.NAME.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 8);
  const activeHazard = hazards.find((h) => h.id === hazard)!;
  const selectedResult = selected ? countyResults[selected.properties.GEOID] ?? null : null;

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Layers3 size={19} /></span>
          <div>
            <strong>Climate Infrastructure</strong>
            <span>Transportation exposure</span>
          </div>
        </div>
        <div className="source-status"><span /> Official-source pipeline</div>
      </header>

      <LimitationsBanner />

      <section className="workspace">
        <aside className="controls">
          <div className="eyebrow">Explore the United States</div>
          <h1>Road exposure by county</h1>
          <p className="lede">
            Select a state, choose a hazard, then click a county to inspect its frequency,
            road exposure, traffic consequence, and stress score.
          </p>

          <label className="field-label">State or territory</label>
          <Select value={stateFips} onValueChange={setStateFips}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {states.map(([id, name]) => (
                <SelectItem key={id} value={id}>{name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <label className="field-label">Hazard layer</label>
          <div className="hazard-list">
            {hazards.map((h) => (
              <button
                key={h.id}
                className={hazard === h.id ? "hazard active" : "hazard"}
                onClick={() => setHazard(h.id)}
              >
                <span style={{ background: h.color }} />
                <div>
                  <strong>{h.label}</strong>
                  <small>{h.id === "compound" ? "SPEI-R25 event" : "Annualized exposure"}</small>
                </div>
                <ChevronRight size={16} />
              </button>
            ))}
          </div>

          <div className="method-note">
            <Database size={17} />
            <p>
              <strong>Precomputed, not downloaded on click.</strong> Raw GIS services feed a
              resumable pipeline; the dashboard receives compact county results.
            </p>
          </div>
        </aside>

        <section className="map-panel">
          <div className="map-toolbar">
            <div>
              <span className="eyebrow">{activeHazard.label}</span>
              <h2>{stateName} counties</h2>
            </div>
            <div className="search-wrap">
              <Search size={16} />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Find a county"
              />
            </div>
          </div>

          {query && (
            <div className="search-results">
              {filtered.map((c) => (
                <button
                  key={c.properties.GEOID}
                  onClick={() => { setSelected(c); setQuery(""); }}
                >
                  <MapPin size={15} />{c.properties.NAME}
                </button>
              ))}
            </div>
          )}

          <div
            className="map-stage"
            style={{ "--hazard": activeHazard.color } as React.CSSProperties}
          >
            {mapLoading ? (
              <div className="map-loading">Loading {stateName}…</div>
            ) : mapError ? (
              <div className="map-error"><AlertTriangle /> {mapError}</div>
            ) : (
              <CountyMap
                features={counties}
                selected={selected?.properties.GEOID}
                onSelect={setSelected}
              />
            )}
            <div className="legend">
              <span>Lower</span><i /><i /><i /><i /><i /><span>Higher</span>
            </div>
          </div>
          <p className="map-caption">
            County boundaries load on demand from the U.S. Census Bureau TIGERweb service.
            {stateFips === "24"
              ? " Flood exposure data available for all 24 Maryland counties."
              : " Flood exposure data available for Maryland only at this time."}
          </p>
        </section>

        <aside className="details">
          {selected ? (
            <CountyDetail
              feature={selected}
              result={selectedResult}
              loading={countyLoading && selectedResult === null}
              hazard={hazard}
            />
          ) : (
            <div className="empty-detail">
              <MapPin size={28} />
              <h2>Select a county</h2>
              <p>Click a county on the map to open its exposure profile and methodology details.</p>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}
