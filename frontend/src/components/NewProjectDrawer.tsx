import { useEffect, useRef, useState, type FormEvent } from "react";
import { ClipboardList, FileUp, X } from "lucide-react";
import { api, ApiError, type Meta, type Mode, type PlantType } from "../lib/api";
import { PlantIcon } from "./Brand";

const COUNTRIES = ["Saudi Arabia", "United Arab Emirates", "Oman", "Qatar", "Bahrain", "Kuwait", "Sri Lanka", "India", "Other"];
const TYPE_HELP: Record<PlantType, string> = {
  industrial: "Large-scale production and cold chain",
  retail: "Bakery production for shops",
  egg_station: "Egg grading and packing",
};

interface Props { meta: Meta | null; onClose: () => void; onCreated: (id: string) => void }

export default function NewProjectDrawer({ meta, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [mode, setMode] = useState<Mode>("brief");
  const [type, setType] = useState<PlantType>("industrial");
  const [country, setCountry] = useState("Saudi Arabia");
  const [city, setCity] = useState("");
  const [config, setConfig] = useState(meta?.configs[0] ?? "");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => { first.current?.focus(); }, []);
  useEffect(() => { if (!config && meta?.configs.length) setConfig(meta.configs[0]); }, [meta, config]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) { setNameError("Give the project a name of at least 2 characters."); first.current?.focus(); return; }
    setBusy(true); setError(null);
    try {
      const p = await api.createProject({ name: name.trim(), mode, plant_type: type, country, city: city.trim(), config: mode === "drawing" ? config : null, notes });
      onCreated(p.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the project.");
      setBusy(false);
    }
  }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <form className="drawer" role="dialog" aria-modal="true" aria-labelledby="np-title" onSubmit={submit} noValidate>
        <div className="drawer-head">
          <div>
            <h2 className="h2" id="np-title">New plant project</h2>
            <p className="muted">{mode === "drawing" ? "You'll upload the drawing on the next screen." : "You'll fill in the plant brief on the next screen."}</p>
          </div>
          <button type="button" className="btn ghost icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="drawer-body">
          <div className="field">
            <label htmlFor="np-name">Project name</label>
            <input id="np-name" ref={first} className="input" value={name} placeholder="e.g. Riyadh central bakery"
              onChange={(e) => { setName(e.target.value); setNameError(null); }} aria-invalid={!!nameError} aria-describedby="np-name-err" />
            {nameError && <span className="err" id="np-name-err">{nameError}</span>}
          </div>
          <div className="field">
            <span className="label" id="np-start">Starting point</span>
            <div className="start-options" role="group" aria-labelledby="np-start">
              <button type="button" className="type-option" aria-pressed={mode === "brief"} onClick={() => setMode("brief")}>
                <ClipboardList size={20} />
                <strong>From a brief</strong>
                <span className="subtle" style={{ fontSize: 12 }}>No drawing yet. Describe the plant and get a concept design.</span>
              </button>
              <button type="button" className="type-option" aria-pressed={mode === "drawing"} onClick={() => setMode("drawing")}>
                <FileUp size={20} />
                <strong>From a drawing</strong>
                <span className="subtle" style={{ fontSize: 12 }}>Upload the plant's AutoCAD plan and model it as drawn.</span>
              </button>
            </div>
          </div>
          <div className="field">
            <span className="label" id="np-type">Plant type</span>
            <div className="type-options" role="group" aria-labelledby="np-type">
              {(meta?.plant_types ?? []).map((t) => (
                <button type="button" key={t.value} className="type-option" aria-pressed={type === t.value} onClick={() => setType(t.value)}>
                  <PlantIcon type={t.value} size={20} />
                  <strong>{t.label}</strong>
                  <span className="subtle" style={{ fontSize: 12 }}>{TYPE_HELP[t.value]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="two">
            <div className="field">
              <label htmlFor="np-country">Country</label>
              <select id="np-country" className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
                {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="np-city">City</label>
              <input id="np-city" className="input" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Optional" />
            </div>
          </div>
          {mode === "drawing" && <div className="field">
            <label htmlFor="np-config">Drawing profile</label>
            <select id="np-config" className="select" value={config} onChange={(e) => setConfig(e.target.value)}>
              {(meta?.configs ?? []).map((c) => <option key={c}>{c}</option>)}
            </select>
            <span className="hint">Tells the model which drawing layers are walls, panels and grid, plus levels and structure settings.</span>
          </div>}
          <div className="field">
            <label htmlFor="np-notes">Notes</label>
            <textarea id="np-notes" className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Capacity, products, anything the team should know" />
          </div>
          {error && <div className="note" role="alert" style={{ borderColor: "var(--bad)" }}>{error}</div>}
        </div>
        <div className="drawer-foot">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary" disabled={busy || !meta}>{busy ? "Creating…" : "Create project"}</button>
        </div>
      </form>
    </>
  );
}
