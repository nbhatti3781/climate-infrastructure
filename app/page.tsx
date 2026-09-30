"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronRight, Database, Layers3, MapPin, Search } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

type Hazard = "flood" | "wildfire" | "hurricane" | "compound";
type CountyFeature = {
  type: "Feature";
  properties: { GEOID: string; NAME: string; BASENAME: string; STATE: string };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};

const hazards: { id: Hazard; label: string; short: string; color: string }[] = [
  { id: "flood", label: "Inland flood", short: "Flood", color: "#2563eb" },
  { id: "wildfire", label: "Wildfire", short: "Fire", color: "#e25822" },
  { id: "hurricane", label: "Hurricane inundation", short: "Surge", color: "#0891b2" },
  { id: "compound", label: "Drought–heavy rain", short: "Compound", color: "#b7791f" },
];

const states = [
  ["01","Alabama"],["02","Alaska"],["04","Arizona"],["05","Arkansas"],["06","California"],["08","Colorado"],["09","Connecticut"],["10","Delaware"],["11","District of Columbia"],["12","Florida"],["13","Georgia"],["15","Hawaii"],["16","Idaho"],["17","Illinois"],["18","Indiana"],["19","Iowa"],["20","Kansas"],["21","Kentucky"],["22","Louisiana"],["23","Maine"],["24","Maryland"],["25","Massachusetts"],["26","Michigan"],["27","Minnesota"],["28","Mississippi"],["29","Missouri"],["30","Montana"],["31","Nebraska"],["32","Nevada"],["33","New Hampshire"],["34","New Jersey"],["35","New Mexico"],["36","New York"],["37","North Carolina"],["38","North Dakota"],["39","Ohio"],["40","Oklahoma"],["41","Oregon"],["42","Pennsylvania"],["44","Rhode Island"],["45","South Carolina"],["46","South Dakota"],["47","Tennessee"],["48","Texas"],["49","Utah"],["50","Vermont"],["51","Virginia"],["53","Washington"],["54","West Virginia"],["55","Wisconsin"],["56","Wyoming"],["60","American Samoa"],["66","Guam"],["69","Northern Mariana Islands"],["72","Puerto Rico"],["78","U.S. Virgin Islands"]
] as const;

function rings(feature: CountyFeature): number[][][] {
  if (feature.geometry.type === "Polygon") return feature.geometry.coordinates as number[][][];
  return (feature.geometry.coordinates as number[][][][]).flat();
}

const howardFlood = {
  geoid: "24027",
  rawFrequency: 2.5714285714285716,
  normalizedFrequency: 0.19834710743801656,
  totalMiles: 108.7627750614346,
  exposedMiles: 2.432870836162559,
  exposure: 0.022368598399483217,
  consequenceRawAadt: 78851.59247681827,
  analysisDate: "September 23, 2026",
};

function CountyMap({ features, selected, validated, onSelect }: { features: CountyFeature[]; selected?: string; validated?: string; onSelect: (f: CountyFeature) => void }) {
  const projection = useMemo(() => {
    const points = features.flatMap((f) => rings(f).flat());
    if (!points.length) return null;
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const width = Math.max(maxX - minX, 0.01), height = Math.max(maxY - minY, 0.01);
    const scale = Math.min(920 / width, 500 / height);
    const ox = (960 - width * scale) / 2, oy = (540 - height * scale) / 2;
    return (p: number[]) => [ox + (p[0] - minX) * scale, 540 - (oy + (p[1] - minY) * scale)];
  }, [features]);

  if (!projection) return <div className="map-loading">Loading county boundaries…</div>;
  const path = (f: CountyFeature) => rings(f).map((ring) => ring.map((p, i) => `${i ? "L" : "M"}${projection(p).join(",")}`).join(" ") + " Z").join(" ");

  return (
    <svg className="county-map" viewBox="0 0 960 540" role="img" aria-label="Interactive county map">
      {features.map((f) => (
        <path key={f.properties.GEOID} d={path(f)} className={`county${validated === f.properties.GEOID ? " validated" : ""}${selected === f.properties.GEOID ? " selected" : ""}`}
          onClick={() => onSelect(f)} tabIndex={0} role="button" aria-label={f.properties.NAME}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(f)} />
      ))}
    </svg>
  );
}

export default function Home() {
  const [stateFips, setStateFips] = useState("24");
  const [hazard, setHazard] = useState<Hazard>("flood");
  const [counties, setCounties] = useState<CountyFeature[]>([]);
  const [selected, setSelected] = useState<CountyFeature | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true); setError(""); setSelected(null);
    const params = new URLSearchParams({
      where: `STATE='${stateFips}'`,
      outFields: "GEOID,NAME,BASENAME,STATE",
      returnGeometry: "true",
      outSR: "4326",
      geometryPrecision: "3",
      maxAllowableOffset: "0.003",
      f: "geojson",
    });
    const countyUrl = `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/57/query?${params}`;
    fetch(countyUrl, { headers: { Accept: "application/geo+json" } })
      .then((r) => { if (!r.ok) throw new Error("Census county boundaries are temporarily unavailable"); return r.json(); })
      .then((data) => setCounties(data.features ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [stateFips]);

  const stateName = states.find(([id]) => id === stateFips)?.[1] ?? "State";
  const filtered = counties.filter((c) => c.properties.NAME.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
  const activeHazard = hazards.find((h) => h.id === hazard)!;
  const validatedResult = hazard === "flood" && selected?.properties.GEOID === howardFlood.geoid;

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><Layers3 size={19}/></span><div><strong>Climate Infrastructure</strong><span>Transportation exposure</span></div></div>
        <div className="source-status"><span /> Official-source pipeline</div>
      </header>

      <section className="workspace">
        <aside className="controls">
          <div className="eyebrow">Explore the United States</div>
          <h1>Road exposure by county</h1>
          <p className="lede">Select a state, choose a hazard, then click a county to inspect its frequency, road exposure, traffic consequence, and stress score.</p>

          <label className="field-label">State or territory</label>
          <Select value={stateFips} onValueChange={setStateFips}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>{states.map(([id,name]) => <SelectItem key={id} value={id}>{name}</SelectItem>)}</SelectContent>
          </Select>

          <label className="field-label">Hazard layer</label>
          <div className="hazard-list">
            {hazards.map((h) => <button key={h.id} className={hazard === h.id ? "hazard active" : "hazard"} onClick={() => setHazard(h.id)}><span style={{background:h.color}}/><div><strong>{h.label}</strong><small>{h.id === "compound" ? "SPEI-R25 event" : "Annualized exposure"}</small></div><ChevronRight size={16}/></button>)}
          </div>

          <div className="method-note"><Database size={17}/><p><strong>Precomputed, not downloaded on click.</strong> Raw GIS services feed a resumable pipeline; the dashboard receives compact county results.</p></div>
        </aside>

        <section className="map-panel">
          <div className="map-toolbar">
            <div><span className="eyebrow">{activeHazard.label}</span><h2>{stateName} counties</h2></div>
            <div className="search-wrap"><Search size={16}/><Input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Find a county"/></div>
          </div>
          {query && <div className="search-results">{filtered.map((c)=><button key={c.properties.GEOID} onClick={()=>{setSelected(c);setQuery("")}}><MapPin size={15}/>{c.properties.NAME}</button>)}</div>}
          <div className="map-stage" style={{"--hazard": activeHazard.color} as React.CSSProperties}>
            {loading ? <div className="map-loading">Loading {stateName}…</div> : error ? <div className="map-error"><AlertTriangle/> {error}</div> : <CountyMap features={counties} selected={selected?.properties.GEOID} validated={hazard === "flood" && stateFips === "24" ? howardFlood.geoid : undefined} onSelect={setSelected}/>} 
            <div className="legend"><span>Lower</span><i/><i/><i/><i/><i/><span>Higher</span></div>
          </div>
          <p className="map-caption">County boundaries load on demand from the U.S. Census Bureau TIGERweb service. Exposure values will join by five-digit county GEOID after preprocessing.</p>
        </section>

        <aside className="details">
          {selected ? <>
            <div className="eyebrow">County profile</div><h2>{selected.properties.NAME}</h2><p className="geoid">GEOID {selected.properties.GEOID}</p>
            {validatedResult ? <>
              <div className="metric-card"><span>Final Flood Stress</span><strong>Pending</strong><small>Requires nationwide AADT consequence ranking</small></div>
              <div className="step-grid">
                <div className="step-card complete"><span>Step 1 · Frequency</span><strong>{howardFlood.normalizedFrequency.toFixed(3)}</strong><small>Raw FEMA AFREQ: {howardFlood.rawFrequency.toFixed(2)}/yr</small></div>
                <div className="step-card complete"><span>Step 2 · Exposure</span><strong>{(howardFlood.exposure * 100).toFixed(2)}%</strong><small>{howardFlood.exposedMiles.toFixed(2)} of {howardFlood.totalMiles.toFixed(2)} primary-road miles</small></div>
                <div className="step-card partial"><span>Step 3 · Consequence</span><strong>{Math.round(howardFlood.consequenceRawAadt).toLocaleString()}</strong><small>Raw length-weighted AADT; national 0–1 rank required</small></div>
              </div>
            </> : <div className="metric-card"><span>{activeHazard.short} exposure</span><strong>Pending</strong><small>Awaiting validated preprocessing</small></div>}
            <div className="formula"><span>Transportation Stress calculation</span><code>Stress = normalized frequency × road exposure × normalized traffic consequence</code><code>Exposure = flood-exposed road length ÷ total primary-road length</code></div>
            {validatedResult && <p className="metric-note">Sources: FEMA NRI and NFHL, Census TIGERweb Primary Roads, and 2024 FHWA HPMS AADT. The final score stays pending until Step 3 is ranked against every county nationally. It is not damage or a road-closure prediction.</p>}
            <div className="status-list"><div><span className="done"/>Frequency normalization<strong>Ready</strong></div><div><span className={validatedResult ? "done" : ""}/>Road exposure<strong>{validatedResult ? "Ready" : "Pipeline"}</strong></div><div><span className={validatedResult ? "working" : ""}/>National AADT rank<strong>{validatedResult ? "Required" : "Pipeline"}</strong></div><div><span/>Final Flood Stress<strong>Pending</strong></div></div>
          </> : <div className="empty-detail"><MapPin size={28}/><h2>Select a county</h2><p>Click a county on the map to open its exposure profile and methodology details.</p></div>}
        </aside>
      </section>
    </main>
  );
}
