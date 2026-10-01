import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Hammer, Loader2 } from "lucide-react";
import { api, type Brief, type PlantType } from "../lib/api";
import { M2_PER_SQFT, int } from "../lib/format";

type Defaults = Record<string, number | boolean | null | string | string[]>;
type Unit = "m2" | "sqft";
interface Props {
  plantType: PlantType;
  initial: Brief | null;
  busy: boolean;
  onSubmit: (brief: Brief) => void;
  onCancel?: () => void;
  onVariant?: (brief: Brief) => void;
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));
const txt = (v: number | null | undefined) => (v == null ? "" : String(v));

function Field({ id, label, hint, children, className }: { id: string; label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`field ${className ?? ""}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

function YesNo({ id, value, def, onChange }: { id: string; value: boolean | null | undefined; def: unknown; onChange: (v: boolean | null) => void }) {
  const current = value == null ? "" : value ? "yes" : "no";
  return (
    <select id={id} className="select" value={current} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "yes")}>
      <option value="">Not sure (use {def ? "yes" : "no"})</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </select>
  );
}

export default function BriefForm({ plantType, initial, busy, onSubmit, onCancel, onVariant }: Props) {
  const [d, setD] = useState<Defaults>({});
  const [unit, setUnit] = useState<Unit>("m2");
  const [area, setArea] = useState(initial ? String(Math.round(initial.built_up_area_m2)) : "");
  const [b, setB] = useState<Partial<Brief>>(initial ?? {});
  const [areaErr, setAreaErr] = useState<string | null>(null);

  useEffect(() => { api.briefDefaults(plantType).then(setD).catch(() => setD({})); }, [plantType]);
  const set = <K extends keyof Brief>(k: K, v: Brief[K]) => setB((x) => ({ ...x, [k]: v }));
  const ph = (k: string, suffix = "") => (d[k] != null ? `Default ${d[k]}${suffix}` : "Optional");
  const zones = (d.hall_zones as string[] | undefined) ?? [];
  const zoneSize = (z: string) => Math.round((b.zone_sizes?.[z] ?? 1) * 100);
  const setZone = (z: string, pct: number) => {
    const next = { ...(b.zone_sizes ?? {}) };
    if (pct === 100) delete next[z]; else next[z] = pct / 100;
    set("zone_sizes", next);
  };

  function switchUnit(u: Unit) {
    if (u === unit) return;
    const v = Number(area);
    if (area && v > 0) setArea(String(Math.round(u === "sqft" ? v / M2_PER_SQFT : v * M2_PER_SQFT)));
    setUnit(u);
  }

  function submit(e: FormEvent, asVariant = false) {
    e.preventDefault();
    const raw = Number(area);
    const m2 = unit === "sqft" ? raw * M2_PER_SQFT : raw;
    if (!area || !(m2 > 150)) {
      setAreaErr(`Enter the built-up area: at least 150 m² (${int(150 / M2_PER_SQFT)} sq ft).`);
      document.getElementById("bf-area")?.focus();
      return;
    }
    const brief = { ...b, plant_type: plantType, built_up_area_m2: Math.round(m2 * 10) / 10 } as Brief;
    if (asVariant && onVariant) onVariant(brief); else onSubmit(brief);
  }

  const areaM2 = Number(area) > 0 ? (unit === "sqft" ? Number(area) * M2_PER_SQFT : Number(area)) : null;

  return (
    <form className="brief" onSubmit={submit} noValidate>
      <div className="brief-head">
        <h2 className="h2">Plant brief</h2>
        <p>Only the built-up area is required. Anything you leave blank uses the default shown, and the model lists every default it used so the team can confirm them.</p>
      </div>

      <div className="brief-section">
        <h3>Site and size</h3>
        <div className="grid3">
          <Field id="bf-area" label="Built-up area" className="span2" hint={areaM2 ? (unit === "sqft" ? `≈ ${int(areaM2)} m²` : `≈ ${int(areaM2 / M2_PER_SQFT)} sq ft`) : "Main building footprint"}>
            <div className="area-input">
              <input id="bf-area" className="input num" inputMode="decimal" value={area} aria-invalid={!!areaErr} aria-describedby="bf-area-err"
                onChange={(e) => { setArea(e.target.value.replace(/[^0-9.]/g, "")); setAreaErr(null); }} placeholder={unit === "m2" ? "e.g. 5000" : "e.g. 54000"} />
              <div className="seg" role="group" aria-label="Area unit">
                <button type="button" aria-pressed={unit === "m2"} onClick={() => switchUnit("m2")}>m²</button>
                <button type="button" aria-pressed={unit === "sqft"} onClick={() => switchUnit("sqft")}>sq ft</button>
              </div>
            </div>
            {areaErr && <span className="err" id="bf-area-err">{areaErr}</span>}
          </Field>
          <Field id="bf-height" label="Clear height (m)" hint="Under the roof steel">
            <input id="bf-height" className="input num" inputMode="decimal" value={txt(b.clear_height_m)} placeholder={ph("clear_height_m", " m")} onChange={(e) => set("clear_height_m", num(e.target.value))} />
          </Field>
          <Field id="bf-pw" label="Plot frontage (m)" hint="Width along the street">
            <input id="bf-pw" className="input num" inputMode="decimal" value={txt(b.plot_width_m)} placeholder="Optional" onChange={(e) => set("plot_width_m", num(e.target.value))} />
          </Field>
          <Field id="bf-pd" label="Plot depth (m)" hint="Away from the street">
            <input id="bf-pd" className="input num" inputMode="decimal" value={txt(b.plot_depth_m)} placeholder="Optional" onChange={(e) => set("plot_depth_m", num(e.target.value))} />
          </Field>
          <Field id="bf-mezz" label="Mezzanine over offices">
            <YesNo id="bf-mezz" value={b.mezzanine} def={d.mezzanine} onChange={(v) => set("mezzanine", v)} />
          </Field>
        </div>
      </div>

      <div className="brief-section">
        <h3>Production</h3>
        <div className="grid3">
          <Field id="bf-products" label="Products" className="span2">
            <input id="bf-products" className="input" value={b.products ?? ""} placeholder="e.g. sliced bread, buns, frozen dough" onChange={(e) => set("products", e.target.value)} />
          </Field>
          <Field id="bf-output" label="Output (tonnes/day)">
            <input id="bf-output" className="input num" inputMode="decimal" value={txt(b.output_tonnes_per_day)} placeholder="Optional" onChange={(e) => set("output_tonnes_per_day", num(e.target.value))} />
          </Field>
          <Field id="bf-lines" label="Lines now">
            <input id="bf-lines" className="input num" inputMode="numeric" value={txt(b.lines_now)} placeholder={ph("lines_now")} onChange={(e) => set("lines_now", num(e.target.value))} />
          </Field>
          <Field id="bf-future" label="Future lines">
            <input id="bf-future" className="input num" inputMode="numeric" value={txt(b.lines_future)} placeholder={ph("lines_future")} onChange={(e) => set("lines_future", num(e.target.value))} />
          </Field>
          <Field id="bf-shifts" label="Shifts per day">
            <select id="bf-shifts" className="select" value={txt(b.shifts_per_day)} onChange={(e) => set("shifts_per_day", num(e.target.value))}>
              <option value="">Not sure (use {String(d.shifts_per_day ?? 2)})</option>
              <option value="1">1</option><option value="2">2</option><option value="3">3</option>
            </select>
          </Field>
        </div>
      </div>

      <div className="brief-section">
        <h3>Storage and cold chain</h3>
        <div className="grid3">
          <Field id="bf-cold" label="Cold storage">
            <YesNo id="bf-cold" value={b.cold_storage} def={d.cold_storage} onChange={(v) => set("cold_storage", v)} />
          </Field>
          <Field id="bf-blast" label="Blast freezer">
            <YesNo id="bf-blast" value={b.blast_freezer} def={d.blast_freezer} onChange={(v) => set("blast_freezer", v)} />
          </Field>
          <Field id="bf-qa" label="QA laboratory">
            <YesNo id="bf-qa" value={b.qa_lab} def={d.qa_lab} onChange={(v) => set("qa_lab", v)} />
          </Field>
          <Field id="bf-silos" label="Outdoor flour silos">
            <YesNo id="bf-silos" value={b.flour_silos} def={d.flour_silos} onChange={(v) => set("flour_silos", v)} />
          </Field>
        </div>
      </div>

      <div className="brief-section">
        <h3>People</h3>
        <div className="grid3">
          <Field id="bf-staff" label="Staff on the busiest shift" hint="Sizes changing rooms, prayer and dining">
            <input id="bf-staff" className="input num" inputMode="numeric" value={txt(b.staff_per_shift)} placeholder={ph("staff_per_shift")} onChange={(e) => set("staff_per_shift", num(e.target.value))} />
          </Field>
          <Field id="bf-office" label="Office staff">
            <input id="bf-office" className="input num" inputMode="numeric" value={txt(b.office_staff)} placeholder={ph("office_staff")} onChange={(e) => set("office_staff", num(e.target.value))} />
          </Field>
          <Field id="bf-female" label="Women in production (%)" hint="Sizes separate changing, hygiene and prayer rooms">
            <input id="bf-female" className="input num" inputMode="numeric" value={b.female_staff_share == null ? "" : String(Math.round(b.female_staff_share * 100))}
              placeholder={d.female_staff_share != null ? `Default ${Math.round(Number(d.female_staff_share) * 100)}%` : "Optional"}
              onChange={(e) => { const v = num(e.target.value); set("female_staff_share", v == null ? null : Math.min(100, Math.max(0, v)) / 100); }} />
          </Field>
        </div>
      </div>

      <div className="brief-section">
        <h3>Design options</h3>
        <p className="muted" style={{ margin: "-6px 0 12px", fontSize: 13 }}>Change any of these and rebuild to compare. The Overview then shows what changed in size, steel, concrete and services.</p>
        <div className="grid3">
          <Field id="bf-struct" label="Structure">
            <select id="bf-struct" className="select" value={b.structure_option ?? ""} onChange={(e) => set("structure_option", (e.target.value || null) as Brief["structure_option"])}>
              <option value="">Default (clear span)</option>
              <option value="clear_span">Clear span, no internal columns</option>
              <option value="two_span">Internal column line (two spans)</option>
            </select>
          </Field>
          <Field id="bf-span" label="Building depth / span (m)">
            <input id="bf-span" className="input num" inputMode="decimal" value={txt(b.span_m)} placeholder={ph("span_m", " m")} onChange={(e) => set("span_m", num(e.target.value))} />
          </Field>
          <Field id="bf-bay" label="Bay spacing (m)">
            <input id="bf-bay" className="input num" inputMode="decimal" value={txt(b.bay_m)} placeholder={ph("bay_m", " m")} onChange={(e) => set("bay_m", num(e.target.value))} />
          </Field>
          <Field id="bf-pitch" label="Roof pitch (°)">
            <input id="bf-pitch" className="input num" inputMode="decimal" value={txt(b.roof_pitch_deg)} placeholder={ph("roof_pitch_deg", "°")} onChange={(e) => set("roof_pitch_deg", num(e.target.value))} />
          </Field>
          <Field id="bf-gin" label="Goods-in yard (m)" hint="West side, raw-material trucks">
            <input id="bf-gin" className="input num" inputMode="decimal" value={txt(b.goods_in_yard_m)} placeholder={ph("goods_in_yard_m", " m")} onChange={(e) => set("goods_in_yard_m", num(e.target.value))} />
          </Field>
          <Field id="bf-disp" label="Dispatch apron (m)" hint="East side, trucks turning and docking">
            <input id="bf-disp" className="input num" inputMode="decimal" value={txt(b.dispatch_yard_m)} placeholder={ph("dispatch_yard_m", " m")} onChange={(e) => set("dispatch_yard_m", num(e.target.value))} />
          </Field>
        </div>
        {zones.length > 0 && (
          <>
            <h3 style={{ marginTop: 18 }}>Zone sizes</h3>
            <p className="muted" style={{ margin: "-6px 0 10px", fontSize: 13 }}>Make a zone larger or smaller relative to the others. The hall area is shared out again on rebuild.</p>
            <div className="zone-sliders">
              {zones.map((z) => (
                <label className="zone-slider" key={z}>
                  <span>{z}</span>
                  <input type="range" min={50} max={200} step={10} value={zoneSize(z)} onChange={(e) => setZone(z, Number(e.target.value))} aria-label={`${z} size`} />
                  <span className="num">{zoneSize(z)}%</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="brief-foot">
        <span className="muted">The concept is a starting point for your architects and engineers, not a construction design.</span>
        <div style={{ display: "flex", gap: 8 }}>
          {onCancel && <button type="button" className="btn" onClick={onCancel} disabled={busy}>Cancel</button>}
          {onVariant && <button type="button" className="btn" onClick={(e) => submit(e, true)} disabled={busy}>Save as variant to compare</button>}
          <button type="submit" className="btn primary" disabled={busy}>
            {busy ? <Loader2 className="spin" size={16} /> : <Hammer size={16} />} Save and build concept
          </button>
        </div>
      </div>
    </form>
  );
}
