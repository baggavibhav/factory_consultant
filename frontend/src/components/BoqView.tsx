import { useEffect, useMemo, useState } from "react";
import { Download, Loader2, RefreshCw, Search } from "lucide-react";
import { api, ApiError, type Boq } from "../lib/api";
import { dec, int } from "../lib/format";

type Tab = "boq" | "bom";

const fmt = (q: number, unit: string) => (unit === "nr" ? int(q) : q >= 100 ? int(q) : dec(q));

export default function BoqView({ projectId, buildId, concept, onRebuild }: { projectId: string; buildId: string; concept: boolean; onRebuild: () => void }) {
  const [boq, setBoq] = useState<Boq | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("boq");
  const [q, setQ] = useState("");

  useEffect(() => {
    setBoq(null);
    api.boq(projectId).then(setBoq).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [projectId, buildId]);

  const needle = q.trim().toLowerCase();
  const sections = useMemo(() => (boq?.sections ?? []).map((s) => ({
    ...s,
    items: s.items.filter((i) => !needle || `${i.description} ${i.spec}`.toLowerCase().includes(needle)),
  })).filter((s) => s.items.length), [boq, needle]);
  const bom = useMemo(() => (boq?.bom ?? []).filter((b) => !needle || `${b.material} ${b.spec}`.toLowerCase().includes(needle)), [boq, needle]);

  if (error) {
    return (
      <div className="stage-center">
        <div className="panel-card">
          <h2 className="h2">No quantities for this build yet</h2>
          <p>This model was built before quantities were added. Rebuild it to measure the BOQ and bill of materials.</p>
          <button className="btn primary" onClick={onRebuild}><RefreshCw size={16} /> Rebuild model</button>
        </div>
      </div>
    );
  }
  if (!boq) return <div className="v-loading"><Loader2 className="spin" size={22} /> Loading quantities</div>;
  const h = boq.headline;

  return (
    <div className="stage-scroll">
      <div className="boq">
        <div className="boq-head">
          <div>
            <h2 className="h2">Bill of quantities</h2>
            <p className="muted">
              {h.items} items measured from the {concept ? "concept model" : "drawing model"}. Download the Excel file to price it: rates go in the highlighted cells and totals calculate automatically ({boq.currency}).
            </p>
          </div>
          <a className="btn primary" href={api.boqXlsxUrl(projectId)}><Download size={16} /> Download Excel</a>
        </div>

        <div className="boq-metrics">
          <div className="metric"><div className="v">{dec(h.steel_t)} t</div><div className="k">Structural steel</div></div>
          <div className="metric"><div className="v">{int(h.concrete_m3)} m³</div><div className="k">Concrete</div></div>
          <div className="metric"><div className="v">{int(h.roof_m2)} m²</div><div className="k">Roof panels</div></div>
          <div className="metric"><div className="v">{int(h.wall_m2)} m²</div><div className="k">Wall cladding</div></div>
        </div>

        {concept && Object.keys(boq.mep).length > 0 && (
          <div className="boq-mep">
            {boq.mep.electrical && <span><strong>{boq.mep.electrical.transformer_kva} kVA</strong> transformer, {int(boq.mep.electrical.connected_load_kw)} kW connected</span>}
            {boq.mep.water && <span><strong>{boq.mep.water.tank_m3} m³</strong> water tank</span>}
            {boq.mep.fire && <span><strong>{boq.mep.fire.tank_m3} m³</strong> fire tank, {boq.mep.fire.hydrants} hydrants</span>}
            {boq.mep.drainage && <span><strong>{boq.mep.drainage.gullies}</strong> floor gullies</span>}
            {boq.mep.hvac && <span><strong>{boq.mep.hvac.refrigeration_kw} kW</strong> refrigeration</span>}
          </div>
        )}
        {!concept && (
          <div className="note" style={{ margin: "0 22px 14px" }}>
            <strong>Drawing projects:</strong> structure, slab, envelope, partitions and cold-room panels are measured. Floor finishes and MEP need room outlines from the drawing; they are measured for concept projects today.
          </div>
        )}

        <div className="boq-bar">
          <div className="seg" role="tablist" aria-label="Quantities view">
            <button role="tab" aria-pressed={tab === "boq"} aria-selected={tab === "boq"} onClick={() => setTab("boq")}>BOQ by trade</button>
            <button role="tab" aria-pressed={tab === "bom"} aria-selected={tab === "bom"} onClick={() => setTab("bom")}>Bill of materials</button>
          </div>
          <div className="search" style={{ maxWidth: 300 }}>
            <Search size={16} />
            <input className="input" placeholder="Search items or specifications" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search quantities" />
          </div>
        </div>

        {tab === "boq" ? (
          <div className="table-wrap boq-table">
            <table className="list" style={{ minWidth: 720 }}>
              <thead><tr><th style={{ width: 64 }}>Ref</th><th>Item and specification</th><th className="r">Quantity</th><th>Unit</th></tr></thead>
              <tbody>
                {sections.map((s) => {
                  const n = boq.sections.findIndex((x) => x.name === s.name) + 1;
                  return [
                    <tr key={s.name} className="sec"><td>{n}</td><td colSpan={3}>{s.name}</td></tr>,
                    ...s.items.map((i, k) => (
                      <tr key={`${s.name}-${k}`}>
                        <td className="subtle num">{n}.{String(boq.sections[n - 1].items.indexOf(i) + 1).padStart(2, "0")}</td>
                        <td>
                          <div className="it">{i.description}</div>
                          {i.spec && <div className="sp">{i.spec}</div>}
                          <div className="bs">{i.basis}</div>
                        </td>
                        <td className="r num">{fmt(i.qty, i.unit)}</td>
                        <td>{i.unit}</td>
                      </tr>
                    )),
                  ];
                })}
                {sections.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 24 }}>No items match this search.</td></tr>}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-wrap boq-table">
            <table className="list" style={{ minWidth: 720 }}>
              <thead><tr><th>Material</th><th className="r">Net</th><th>Unit</th><th className="r">Waste</th><th className="r">Order</th></tr></thead>
              <tbody>
                {bom.map((b, k) => (
                  <tr key={k}>
                    <td><div className="it">{b.material}</div>{b.spec && <div className="sp">{b.spec}</div>}</td>
                    <td className="r num">{fmt(b.qty, b.unit)}</td>
                    <td>{b.unit}</td>
                    <td className="r num subtle">{b.waste ? `${Math.round(b.waste * 100)}%` : "–"}</td>
                    <td className="r num"><strong>{int(Math.ceil(b.qty * (1 + b.waste)))}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="subtle boq-foot">
          Quantities are measured from the model or derived by the rule shown under each item. Member sizes are indicative and MEP routes are concept layouts; have engineers confirm before tender. Specifications come from the editable library in config/specs.
        </p>
      </div>
    </div>
  );
}
