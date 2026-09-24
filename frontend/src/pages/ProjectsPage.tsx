import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Plus, Search } from "lucide-react";
import { api, ApiError, type Meta, type PlantType, type ProjectSummary } from "../lib/api";
import { PLANT_TYPE, int, sqft, statusOf, when } from "../lib/format";
import { PlantIcon } from "../components/Brand";
import NewProjectDrawer from "../components/NewProjectDrawer";

type Filter = "all" | PlantType;

function EmptyArt() {
  return (
    <svg width="148" height="84" viewBox="0 0 148 84" fill="none" aria-hidden="true">
      <path d="M4 80h140" stroke="var(--line-strong)" strokeWidth="2" />
      <path d="M22 80V38l52-24 52 24v42" stroke="var(--ink)" strokeWidth="3" strokeLinejoin="round" />
      <path d="M22 38h104M48 26v54M74 14v66M100 26v54" stroke="var(--line-strong)" strokeWidth="1.5" strokeDasharray="4 4" />
      <rect x="60" y="56" width="28" height="24" stroke="var(--ink)" strokeWidth="2.5" />
      <circle cx="126" cy="16" r="9" fill="var(--signal)" />
    </svg>
  );
}

export default function ProjectsPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.projects().then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
    api.meta().then(setMeta).catch(() => {});
  }, []);

  const shown = useMemo(() => (items ?? []).filter((p) =>
    (filter === "all" || p.plant_type === filter) &&
    `${p.name} ${p.city} ${p.country}`.toLowerCase().includes(q.trim().toLowerCase())), [items, filter, q]);

  const withModel = (items ?? []).filter((p) => p.status === "model_ready").length;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h1">Projects</h1>
          <p className="muted">
            {items === null ? "Loading projects…" : items.length === 0 ? "No projects yet." :
              `${items.length} ${items.length === 1 ? "project" : "projects"}, ${withModel} with a 3D model`}
          </p>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}><Plus size={17} /> New project</button>
      </div>

      {error && <div className="note" role="alert" style={{ marginBottom: 16 }}>{error}</div>}

      {items && items.length > 0 && (
        <div className="toolbar">
          <div className="search">
            <Search size={16} />
            <input className="input" placeholder="Search by name or location" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search projects" />
          </div>
          <div className="seg" role="group" aria-label="Filter by plant type">
            {(["all", "industrial", "retail", "egg_station"] as Filter[]).map((f) => (
              <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === "all" ? "All types" : PLANT_TYPE[f]}</button>
            ))}
          </div>
        </div>
      )}

      {items === null && !error && (
        <div className="table-wrap" style={{ padding: 16, display: "grid", gap: 12 }}>
          {[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 36 }} />)}
        </div>
      )}

      {items && items.length === 0 && (
        <div className="empty">
          <EmptyArt />
          <h2 className="h2">Start with your first plant</h2>
          <p>Upload a plant's AutoCAD drawing, or describe a new plant in a short brief, and get a 3D model with its layout, steel structure and member schedule.</p>
          <button className="btn primary" onClick={() => setCreating(true)}><Plus size={17} /> New project</button>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="table-wrap">
          <table className="list">
            <thead>
              <tr>
                <th>Project</th><th>Plant type</th><th>Location</th><th className="r">Built-up area</th><th>Status</th><th>Updated</th><th aria-label="Open" />
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id} onClick={() => nav(`/projects/${p.id}`)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && nav(`/projects/${p.id}`)}>
                  <td><span className="name">{p.name}</span>{p.mode === "brief" && <span className="concept-tag">Concept</span>}</td>
                  <td><span className="type-tag"><PlantIcon type={p.plant_type} />{PLANT_TYPE[p.plant_type]}</span></td>
                  <td className="muted">{[p.city, p.country].filter(Boolean).join(", ")}</td>
                  <td className="r num">{p.footprint_m2 ? <>{int(p.footprint_m2)} m² <span className="subtle">({sqft(p.footprint_m2)} sq ft)</span></> : <span className="subtle">Not built</span>}</td>
                  <td><span className={`badge ${statusOf(p).tone}`}>{statusOf(p).label}</span></td>
                  <td className="muted">{when(p.updated_at)}</td>
                  <td className="r row-open"><ChevronRight size={18} /></td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 28, cursor: "default" }}>No projects match this search.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <NewProjectDrawer meta={meta} onClose={() => setCreating(false)} onCreated={(id) => nav(`/projects/${id}`)} />
      )}
    </div>
  );
}
