import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Box, Check, ChevronLeft, Download, FileUp, Hammer, Layers3, Loader2, MapPin, Pencil, RefreshCw, Trash2, Upload,
} from "lucide-react";
import { api, ApiError, type Brief, type Label, type Project } from "../lib/api";
import { MEMBER_NAMES, PLANT_TYPE, ZONE_COLOURS, bytes, dec, int, sqft, stamp, statusOf } from "../lib/format";
import BriefForm from "../components/BriefForm";
import BoqView from "../components/BoqView";
import { PlantIcon } from "../components/Brand";
import { useToast } from "../components/Toasts";
import Viewer3D, { LAYERS, SERVICE_KEYS, type LayerKey, type ViewName } from "../components/Viewer3D";

type Tab = "overview" | "program" | "layers" | "structure" | "files" | "activity";
const BUILD_STEPS = ["Reading the drawing", "Aligning the column grid", "Generating the structure", "Exporting the 3D model"];
const CONCEPT_STEPS = ["Sizing the building", "Laying out the zones", "Generating the structure", "Exporting the 3D model"];
const VIEWS: { key: ViewName; label: string; concept?: boolean }[] = [
  { key: "iso", label: "3D" },
  { key: "structure", label: "Structure" },
  { key: "services", label: "Services", concept: true },
  { key: "plan", label: "Plan" },
  { key: "street", label: "Street" },
  { key: "inside", label: "Inside" },
];
const DEFAULT_LAYERS = Object.fromEntries(LAYERS.map((l) => [l.key, l.group !== "Services" && l.key !== "foundations"])) as Record<LayerKey, boolean>;
const allServices = (on: boolean) => Object.fromEntries(SERVICE_KEYS.map((k) => [k, on])) as Partial<Record<LayerKey, boolean>>;

function Steps({ project, panel, setPanel }: { project: Project; panel: "model" | "quantities"; setPanel: (p: "model" | "quantities") => void }) {
  const hasDrawing = project.mode === "brief" ? !!project.brief : !!project.drawing;
  const hasModel = project.status === "model_ready";
  const items = [
    { label: project.mode === "brief" ? "Brief" : "Drawing", done: hasDrawing, current: !hasDrawing },
    { label: project.mode === "brief" ? "Concept layout and structure" : "3D model and structure", done: hasModel, current: hasDrawing && !hasModel },
    { label: "Quantities and BOQ", done: hasModel && !!project.latest_build?.facts.quantities },
    { label: "Cost estimate", later: "v0.8" },
  ];
  return (
    <ol className="steps" aria-label="Project progress" style={{ listStyle: "none", margin: 0 }}>
      {items.map((s, i) => (
        <li key={s.label} className={`step${s.done ? " done" : ""}${s.current ? " current" : ""}`} aria-current={s.current ? "step" : undefined}>
          <span className="n">{s.done ? <Check size={13} strokeWidth={3} /> : i + 1}</span>
          {s.label}
          {s.later && <span className="later">{s.later}</span>}
        </li>
      ))}
      {hasModel && (
        <li className="stage-switch">
          <div className="seg" role="group" aria-label="Show">
            <button aria-pressed={panel === "model"} onClick={() => setPanel("model")}>3D model</button>
            <button aria-pressed={panel === "quantities"} onClick={() => setPanel("quantities")}>Quantities</button>
          </div>
        </li>
      )}
    </ol>
  );
}

function Dropzone({ onFile, busy }: { onFile: (f: File) => void; busy: boolean }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const drop = (e: DragEvent) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  return (
    <div className="stage-center">
      <div
        className={`drop${over ? " over" : ""}`}
        role="button" tabIndex={0}
        onClick={() => !busy && input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        aria-busy={busy}
      >
        {busy ? <Loader2 className="spin" size={30} /> : <FileUp size={30} />}
        <h2 className="h2">{busy ? "Uploading and converting the drawing…" : "Upload the plant drawing"}</h2>
        <p>{busy ? "Large AutoCAD files can take up to a minute to convert." : "Drop the architectural plan here, or click to choose it. We read its walls, cold rooms, room names and column grid."}</p>
        {!busy && <span className="btn primary"><Upload size={16} /> Choose file</span>}
        <div className="formats">AutoCAD .dwg or .dxf, up to 200 MB</div>
        <input ref={input} type="file" accept=".dwg,.dxf" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      </div>
    </div>
  );
}

function Building({ steps }: { steps: string[] }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 2600);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="stage-center">
      <div className="panel-card" aria-live="polite">
        <Loader2 className="spin" size={26} />
        <h2 className="h2">Building the model</h2>
        <p>This usually takes 10 to 30 seconds.</p>
        <div className="progress">
          <ul>
            {steps.map((s, k) => (
              <li key={s} className={k < i ? "done" : k === i ? "active" : ""}>
                {k < i ? <Check size={15} /> : k === i ? <Loader2 className="spin" size={15} /> : <span style={{ width: 15 }} />}
                {s}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ReadyToBuild({ project, onBuild }: { project: Project; onBuild: () => void }) {
  return (
    <div className="stage-center">
      <div className="panel-card">
        <Box size={26} />
        <h2 className="h2">Drawing ready</h2>
        <p>
          {project.drawing!.filename} is loaded. Build the model to generate the walls, roof, steel frame and member schedule.
        </p>
        <button className="btn primary" onClick={onBuild}><Hammer size={16} /> Build 3D model</button>
      </div>
    </div>
  );
}

export default function ProjectPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [labels, setLabels] = useState<Label[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [uploading, setUploading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [editingBrief, setEditingBrief] = useState(false);
  const [panel, setPanel] = useState<"model" | "quantities">("model");
  const [xray, setXray] = useState(false);
  const [showLabels, setShowLabels] = useState(true);
  const [view, setView] = useState<ViewName>("iso");

  const load = useCallback(() => {
    api.project(id).then(setProject).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [id]);
  useEffect(load, [load]);

  const buildId = project?.latest_build?.id;
  useEffect(() => {
    if (project?.status === "model_ready") api.labels(id).then(setLabels).catch(() => setLabels([]));
  }, [id, project?.status, buildId]);

  async function upload(file: File) {
    const ext = file.name.toLowerCase().split(".").pop();
    if (ext !== "dwg" && ext !== "dxf") { toast("Choose an AutoCAD .dwg or .dxf file.", true); return; }
    setUploading(true);
    try {
      const p = await api.uploadDrawing(id, file);
      setProject(p);
      toast(`Drawing uploaded: ${p.drawing?.filename}`);
      setTab("overview");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Upload failed.", true);
      load();
    } finally {
      setUploading(false);
    }
  }

  async function build() {
    setBuilding(true);
    try {
      const p = await api.build(id);
      setProject(p);
      setView("iso");
      toast(`3D model built: ${p.latest_build?.facts.frames} portal frames`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Build failed.", true);
      load();
    } finally {
      setBuilding(false);
    }
  }

  async function saveAndBuild(brief: Brief) {
    setBuilding(true);
    try {
      await api.saveBrief(id, brief);
      const p = await api.build(id);
      setProject(p);
      setEditingBrief(false);
      setView("iso");
      setTab("program");
      toast(`Concept model built: ${int(p.latest_build?.facts.footprint_m2 ?? 0)} m², ${p.latest_build?.facts.frames} frames`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Build failed.", true);
      load();
    } finally {
      setBuilding(false);
    }
  }

  function chooseView(v: ViewName) {
    setView(v);
    if (v === "structure") { setXray(true); setShowLabels(false); setLayers((l) => ({ ...l, roof: false, foundations: true, ...allServices(false) })); }
    else if (v === "services") { setXray(true); setShowLabels(false); setLayers((l) => ({ ...l, roof: false, foundations: false, secondary: false, bracing: false, ...allServices(true) })); }
    else if (v === "inside") { setXray(false); setShowLabels(false); setLayers((l) => ({ ...l, roof: true, foundations: false })); }
    else { setXray(false); setLayers((l) => ({ ...l, roof: v !== "plan", foundations: false, secondary: true, bracing: true, ...allServices(false) })); }
  }

  async function remove() {
    if (!project || !window.confirm(`Delete "${project.name}" and its drawing and model? This can't be undone.`)) return;
    try { await api.deleteProject(id); toast("Project deleted"); nav("/"); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Delete failed.", true); }
  }

  if (error) {
    return (
      <div className="center-page"><div>
        <h1 className="h1">{error === "Project not found" ? "Project not found" : "Couldn't open this project"}</h1>
        <p className="muted">{error}</p>
        <Link className="btn primary" to="/">Go to projects</Link>
      </div></div>
    );
  }
  if (!project) {
    return <div className="page"><div className="skeleton" style={{ height: 28, width: 280 }} /><div className="skeleton" style={{ height: 420, marginTop: 20 }} /></div>;
  }

  const b = project.latest_build;
  const f = b?.facts;
  const status = statusOf(project);
  const concept = project.mode === "brief";
  const tabs: Tab[] = concept ? ["overview", "program", "layers", "structure", "activity"] : ["overview", "layers", "structure", "files", "activity"];
  const ready = project.status === "model_ready" && !!f;
  const sched = f ? Object.entries(f.member_schedule) : [];
  const steelLen = sched.filter(([k]) => k !== "foundation").reduce((s, [, v]) => s + v.length_m, 0);

  return (
    <div className="ws">
      <header className="ws-head">
        <div style={{ minWidth: 0 }}>
          <Link to="/" className="crumb"><ChevronLeft size={15} /> Projects</Link>
          <h1 className="h1">{project.name}</h1>
          <div className="meta-row">
            <span className="type-tag"><PlantIcon type={project.plant_type} />{PLANT_TYPE[project.plant_type]}</span>
            <span className="sep" />
            <span className="type-tag"><MapPin size={15} />{[project.city, project.country].filter(Boolean).join(", ")}</span>
            <span className="sep" />
            <span className={`badge ${status.tone}`}>{status.label}</span>
            {concept && <><span className="sep" /><span className="concept-tag" style={{ marginLeft: 0 }}>Concept design</span></>}
          </div>
        </div>
        <div className="ws-actions">
          {ready && f?.quantities && <a className="btn" href={api.boqXlsxUrl(id)}><Download size={16} /> BOQ (Excel)</a>}
          {ready && <a className="btn" href={api.viewerUrl(id)}><Download size={16} /> 3D viewer</a>}
          {concept && ready && !editingBrief && (
            <button className="btn" onClick={() => setEditingBrief(true)} disabled={building}><Pencil size={16} /> Edit brief</button>
          )}
          {(concept ? !!project.brief && ready && !editingBrief : !!project.drawing) && (
            <button className={`btn ${ready ? "" : "primary"}`} onClick={build} disabled={building || uploading}>
              {building ? <Loader2 className="spin" size={16} /> : ready ? <RefreshCw size={16} /> : <Hammer size={16} />}
              {ready ? "Rebuild model" : "Build 3D model"}
            </button>
          )}
        </div>
      </header>

      <Steps project={project} panel={panel} setPanel={setPanel} />

      <div className="ws-body">
        <section className="stage" aria-label="3D model">
          {building ? <Building steps={concept ? CONCEPT_STEPS : BUILD_STEPS} /> :
            concept && (!ready || editingBrief) ? (
              <div className="stage-scroll">
                <BriefForm plantType={project.plant_type} initial={project.brief} busy={building}
                  onSubmit={saveAndBuild} onCancel={ready ? () => setEditingBrief(false) : undefined} />
              </div>
            ) :
            !concept && (!project.drawing || uploading) ? <Dropzone onFile={upload} busy={uploading} /> :
            ready && panel === "quantities" ? <BoqView projectId={id} buildId={b!.id} concept={concept} onRebuild={build} /> :
            !ready ? <ReadyToBuild project={project} onBuild={build} /> :
            <>
              <Viewer3D url={api.modelUrl(id, b!.id)} labels={labels} size={f!.building_m} layers={layers} xray={xray} showLabels={showLabels} view={view} />
              <div className="v-top">
                <div className="v-seg" role="group" aria-label="Camera view">
                  {VIEWS.filter((v) => !v.concept || concept).map((v) => <button key={v.key} aria-pressed={view === v.key} onClick={() => chooseView(v.key)}>{v.label}</button>)}
                </div>
                <div className="v-seg" role="group" aria-label="Display">
                  <button aria-pressed={xray} onClick={() => setXray(!xray)}>X-ray walls</button>
                  <button aria-pressed={showLabels} onClick={() => setShowLabels(!showLabels)}>Room names</button>
                </div>
              </div>
              <div className="v-hint">Drag to orbit, scroll to zoom, right-drag to pan</div>
            </>}
        </section>

        <aside className="inspector" aria-label="Project details">
          <div className="tabs" role="tablist">
            {tabs.map((t) => (
              <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <div className="tab-body" role="tabpanel">
            {tab === "overview" && (
              <>
                {ready ? (
                  <>
                    <div className="metric-row">
                      <div className="metric"><div className="v">{int(f!.footprint_m2)} m²</div><div className="k">{sqft(f!.footprint_m2)} sq ft footprint</div></div>
                      <div className="metric"><div className="v">{f!.building_m[0]} × {f!.building_m[1]} m</div><div className="k">Main building</div></div>
                      <div className="metric"><div className="v">{f!.frames}</div><div className="k">Portal frames, {f!.span_m} m span</div></div>
                      <div className="metric"><div className="v">{int(steelLen)} m</div><div className="k">Steel members, total length</div></div>
                    </div>
                    <div className="section">
                      <h3 className="section-title">Levels</h3>
                      <dl className="kv">
                        <dt>Finished floor</dt><dd>+{f!.levels.ffl.toFixed(2)} m</dd>
                        {f!.levels.mezzanine != null && <><dt>Mezzanine</dt><dd>+{f!.levels.mezzanine.toFixed(2)} m</dd></>}
                        <dt>Eaves</dt><dd>+{f!.levels.eaves_south.toFixed(2)} to +{f!.levels.eaves_north.toFixed(2)} m</dd>
                        <dt>Ridge</dt><dd>+{f!.levels.ridge.toFixed(2)} m</dd>
                      </dl>
                    </div>
                    <div className="section">
                      <h3 className="section-title">Bays</h3>
                      <p className="muted num" style={{ margin: 0, fontSize: 13 }}>{f!.bays_m.map((x) => dec(x)).join(", ")} m</p>
                    </div>
                  </>
                ) : (
                  <p className="muted" style={{ marginTop: 0 }}>
                    {concept ? "Fill in the brief to generate the concept layout, structure and 3D model." :
                      project.drawing ? "Build the model to see the building's size, levels and structure here." : "Upload the plant drawing to get started."}
                  </p>
                )}
                <div className="section">
                  <h3 className="section-title">Project</h3>
                  <dl className="kv">
                    {concept ? <><dt>Starting point</dt><dd>Brief</dd></> : <><dt>Drawing profile</dt><dd>{project.config}</dd></>}
                    {f?.plot_m && <><dt>Plot</dt><dd>{f.plot_m[0]} × {f.plot_m[1]} m</dd></>}
                    <dt>Created</dt><dd>{stamp(project.created_at)}</dd>
                    <dt>Builds</dt><dd>{project.builds}</dd>
                  </dl>
                  {project.notes && <p className="muted" style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{project.notes}</p>}
                </div>
                <div className="section">
                  <button className="btn sm danger ghost" onClick={remove}><Trash2 size={14} /> Delete project</button>
                </div>
              </>
            )}

            {tab === "program" && (
              ready && f?.program ? (
                <>
                  <div className="section">
                    <h3 className="section-title">Space program <span className="subtle" style={{ fontWeight: 450 }}>{f.template}</span></h3>
                    <table className="sched">
                      <thead><tr><th>Zone</th><th className="r">Area</th><th className="r">Size</th></tr></thead>
                      <tbody>
                        {f.program.map((z) => (
                          <tr key={z.name}>
                            <td><span className="zone-dot" style={{ background: ZONE_COLOURS[z.category] ?? "#ccc" }} />{z.name}{z.temp_c != null && <span className="subtle"> {z.temp_c > 0 ? "+" : ""}{z.temp_c}°C</span>}</td>
                            <td className="r">{int(z.area_m2)} m²</td>
                            <td className="r subtle">{dec(z.width_m)} × {dec(z.depth_m)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot><tr><td>Total</td><td className="r">{int(f.program.reduce((s, z) => s + z.area_m2, 0))} m²</td><td className="r subtle">{sqft(f.program.reduce((s, z) => s + z.area_m2, 0))} sq ft</td></tr></tfoot>
                    </table>
                  </div>
                  {f.warnings.filter((w) => !w.startsWith("Concept design")).length > 0 && (
                    <div className="section">
                      <div className="note"><strong>Check this.</strong>
                        <ul className="assume" style={{ color: "var(--ink)" }}>{f.warnings.filter((w) => !w.startsWith("Concept design")).map((w) => <li key={w}>{w}</li>)}</ul>
                      </div>
                    </div>
                  )}
                  {f.assumptions && f.assumptions.length > 0 && (
                    <div className="section">
                      <h3 className="section-title">Assumed, please confirm</h3>
                      <ul className="assume">{f.assumptions.map((a) => <li key={a}>{a[0].toUpperCase() + a.slice(1)}</li>)}</ul>
                      <button className="btn sm" style={{ marginTop: 12 }} onClick={() => setEditingBrief(true)}><Pencil size={14} /> Edit brief</button>
                    </div>
                  )}
                </>
              ) : <p className="muted" style={{ marginTop: 0 }}>The space program appears once the concept is built.</p>
            )}

            {tab === "layers" && (
              ready ? (
                <>
                  {(concept ? (["Architecture", "Structure", "Services"] as const) : (["Architecture", "Structure"] as const)).map((g) => (
                    <div className="section" key={g}>
                      <h3 className="section-title">{g}</h3>
                      {LAYERS.filter((l) => l.group === g).map((l) => (
                        <label className="toggle" key={l.key}>
                          <span className="sw"><span className="swatch" style={{ background: l.swatch }} />{l.label}</span>
                          <span className="switch">
                            <input type="checkbox" checked={layers[l.key]} onChange={(e) => setLayers({ ...layers, [l.key]: e.target.checked })} />
                            <span />
                          </span>
                        </label>
                      ))}
                    </div>
                  ))}
                  {!concept && (
                    <div className="section">
                      <h3 className="section-title">Services</h3>
                      <p className="muted" style={{ fontSize: 13, margin: 0 }}>MEP layers are generated for concept projects. For drawings they need room outlines, which is planned.</p>
                    </div>
                  )}
                </>
              ) : <p className="muted" style={{ marginTop: 0 }}><Layers3 size={16} style={{ verticalAlign: "-3px" }} /> Layers appear once the model is built.</p>
            )}

            {tab === "structure" && (
              ready ? (
                <>
                  {f!.sizes_indicative && (
                    <div className="note" style={{ marginBottom: 14 }}>
                      <strong>Indicative structure.</strong> {concept
                        ? `Frames are placed at regular ${dec(f!.bays_m[0])} m bays generated from the brief.`
                        : "Frame positions follow the drawing's column grid."} Member sizes, purlin and girt spacing and bracing are typical values and need a structural engineer's design.
                    </div>
                  )}
                  <h3 className="section-title">Member schedule</h3>
                  <table className="sched">
                    <thead><tr><th>Member</th><th className="r">Qty</th><th className="r">Length</th></tr></thead>
                    <tbody>
                      {sched.map(([k, v]) => (
                        <tr key={k}><td>{MEMBER_NAMES[k] ?? k}</td><td className="r">{v.count}</td><td className="r">{k === "foundation" ? "–" : `${int(v.length_m)} m`}</td></tr>
                      ))}
                    </tbody>
                    <tfoot><tr><td>Steel total</td><td className="r">{sched.filter(([k]) => k !== "foundation").reduce((s, [, v]) => s + v.count, 0)}</td><td className="r">{int(steelLen)} m</td></tr></tfoot>
                  </table>
                  {b!.warnings.length > 0 && (
                    <div className="section">
                      <h3 className="section-title">Checks</h3>
                      <ul className="warn-list">{b!.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                    </div>
                  )}
                </>
              ) : <p className="muted" style={{ marginTop: 0 }}>The member schedule appears once the model is built.</p>
            )}

            {tab === "files" && (
              <>
                {project.drawing ? (
                  <div className="file-card">
                    <span className="fi"><FileUp size={18} /></span>
                    <div style={{ minWidth: 0 }}>
                      <strong>{project.drawing.filename}</strong>
                      <span className="subtle" style={{ fontSize: 12.5 }}>{bytes(project.drawing.size_bytes)}, uploaded {stamp(project.drawing.uploaded_at)}</span>
                    </div>
                  </div>
                ) : <p className="muted" style={{ marginTop: 0 }}>No drawing uploaded yet.</p>}
                <div className="section">
                  <label className="btn sm" style={{ cursor: "pointer" }}>
                    <Upload size={14} /> {project.drawing ? "Replace drawing" : "Upload drawing"}
                    <input type="file" accept=".dwg,.dxf" hidden onChange={(e) => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = ""; }} />
                  </label>
                  {project.drawing && <p className="subtle" style={{ fontSize: 12.5 }}>Replacing the drawing clears the current model until you rebuild.</p>}
                </div>
              </>
            )}

            {tab === "activity" && (
              <ol className="timeline">
                {[...project.events].reverse().map((e, i) => (
                  <li key={i}><span className={`pin ${e.kind}`} /><div>{e.message}<time dateTime={e.at}>{stamp(e.at)}</time></div></li>
                ))}
              </ol>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
