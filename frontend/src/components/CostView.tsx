import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Download, Loader2, RefreshCw } from "lucide-react";
import { api, ApiError, type Estimate, type Project } from "../lib/api";
import { int } from "../lib/format";

const CONF: Record<string, { label: string; colour: string }> = {
  official: { label: "Official (GASTAT)", colour: "#26815a" },
  published: { label: "Published prices", colour: "#2f7db8" },
  allowance: { label: "Estimator allowances", colour: "#e0a400" },
  quoted: { label: "Supplier quotes", colour: "#7a4fb3" },
  unpriced: { label: "Unpriced", colour: "#b8392d" },
};
const money = (v: number, cur: string) => `${cur} ${int(v)}`;
const mil = (v: number) => `${(v / 1e6).toFixed(v >= 1e7 ? 1 : 2)} M`;

interface Props { project: Project; onProject: (p: Project) => void; onToast: (t: string, bad?: boolean) => void }

export default function CostView({ project, onProject, onToast }: Props) {
  const id = project.id;
  const buildId = project.latest_build?.id;
  const [est, setEst] = useState<Estimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    setEst(null); setError(null);
    api.cost(id).then((e) => {
      setEst(e);
      if (e.settings) setForm({
        preliminaries: String(Math.round(e.settings.preliminaries * 1000) / 10),
        overhead_profit: String(Math.round(e.settings.overhead_profit * 1000) / 10),
        contingency: String(Math.round(e.settings.contingency * 1000) / 10),
        vat: String(Math.round(e.settings.vat * 1000) / 10),
        escalation_per_year: String(Math.round((e.settings.escalation_per_year ?? 0.02) * 1000) / 10),
        construction_start: e.settings.construction_start,
        construction_months: String(e.settings.construction_months),
      });
    }).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [id, buildId, project.latest_build?.facts.cost?.total]);

  async function apply(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const pct = (k: string) => (form[k] === "" ? undefined : Number(form[k]) / 100);
    try {
      const p = await api.costSettings(id, {
        preliminaries: pct("preliminaries"), overhead_profit: pct("overhead_profit"), contingency: pct("contingency"),
        vat: pct("vat"), escalation_per_year: pct("escalation_per_year"), construction_start: form.construction_start || undefined,
        construction_months: form.construction_months ? Number(form.construction_months) : undefined,
      });
      onProject(p); onToast("Estimate recalculated");
    } catch (err) { onToast(err instanceof ApiError ? err.message : "Could not recalculate.", true); }
    finally { setBusy(false); }
  }
  async function recalc() {
    setBusy(true);
    try { onProject(await api.recalc(id)); onToast("Estimate recalculated with the latest rates"); }
    catch (err) { onToast(err instanceof ApiError ? err.message : "Could not recalculate.", true); }
    finally { setBusy(false); }
  }

  if (error) return <div className="stage-center"><div className="panel-card"><h2 className="h2">No estimate for this build yet</h2><p>This model was built before cost estimates existed. Rebuild it to price the BOQ.</p></div></div>;
  if (!est) return <div className="v-loading"><Loader2 className="spin" size={22} /> Loading estimate</div>;
  if (est.available === false) return <div className="stage-center"><div className="panel-card"><h2 className="h2">Cost estimate not available</h2><p>{est.reason}</p></div></div>;

  const cur = est.currency;
  const L = est.likely;
  const bench = est.benchmarks[0];
  const top = [...est.lines].sort((a, b) => b.amount - a.amount).slice(0, 12);
  const maxSec = Math.max(...est.sections.map((s) => s.amount));
  const buildUp: [string, number][] = [
    ["Direct cost (BOQ × rates)", L.direct], ["Preliminaries", L.preliminaries], ["Overhead and profit", L.overhead_profit],
    ["Contingency", L.contingency], ["Escalation to construction midpoint", L.escalation], ["Total before VAT", L.before_vat], ["VAT", L.vat],
  ];

  return (
    <div className="stage-scroll">
      <div className="boq">
        <div className="boq-head">
          <div>
            <h2 className="h2">Cost estimate</h2>
            <p className="muted">{est.library}, prices dated {est.rate_date}. Concept-level estimate for decisions and budgeting, not a tender price.</p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={recalc} disabled={busy}><RefreshCw size={16} /> Recalculate</button>
            <a className="btn primary" href={api.boqXlsxUrl(id)}><Download size={16} /> Priced BOQ (Excel)</a>
          </div>
        </div>

        <div className="cost-hero">
          <div>
            <div className="k">Likely total including VAT</div>
            <div className="big">{money(L.total, cur)}</div>
            <div className="muted">Range {cur} {mil(est.low.total)} – {mil(est.high.total)} · before VAT {money(L.before_vat, cur)}</div>
          </div>
          <div className="cost-rates">
            <div><div className="v">{cur} {int(est.per_m2 ?? 0)}</div><div className="k">per m² (before VAT)</div></div>
            <div><div className="v">{cur} {est.per_sqft}</div><div className="k">per sq ft (before VAT)</div></div>
          </div>
        </div>

        {bench && est.per_m2 && (() => {
          const lo = bench.low_per_m2 * 0.6, hi = bench.high_per_m2 * 1.3;
          const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100))}%`;
          return (
            <div className="bench">
              <div className="section-title">Benchmark check <span className="subtle" style={{ fontWeight: 450 }}>{bench.name}</span></div>
              <div className="bench-bar">
                <span className="bench-range" style={{ left: pos(bench.low_per_m2), width: `calc(${pos(bench.high_per_m2)} - ${pos(bench.low_per_m2)})` }} />
                <span className="bench-me" style={{ left: pos(est.per_m2) }} />
              </div>
              <p className="subtle" style={{ fontSize: 12.5, margin: "6px 0 0" }}>
                {cur} {int(est.per_m2)}/m² is <strong>{bench.status}</strong> the published range of {cur} {int(bench.low_per_m2)}–{int(bench.high_per_m2)}/m². {bench.note}.
              </p>
            </div>
          );
        })()}

        <div className="cost-grid">
          <div>
            <h3 className="section-title">Cost by trade</h3>
            {[...est.sections].sort((a, b) => b.amount - a.amount).map((s) => (
              <div className="bar-row" key={s.name}>
                <span className="bar-label">{s.name}</span>
                <span className="bar"><i style={{ width: `${(s.amount / maxSec) * 100}%` }} /></span>
                <span className="bar-val num">{mil(s.amount)}</span>
                <span className="bar-pct num subtle">{Math.round((s.amount / L.direct) * 100)}%</span>
              </div>
            ))}
          </div>
          <div>
            <h3 className="section-title">Build-up</h3>
            <table className="sched">
              <tbody>
                {buildUp.map(([k, v]) => <tr key={k}><td>{k}</td><td className="r">{money(v, cur)}</td></tr>)}
              </tbody>
              <tfoot><tr><td>Total including VAT</td><td className="r">{money(L.total, cur)}</td></tr></tfoot>
            </table>
            <h3 className="section-title" style={{ marginTop: 18 }}>Where the rates come from</h3>
            <div className="cov-bar">
              {Object.entries(est.coverage).map(([k, v]) => <i key={k} style={{ width: `${v * 100}%`, background: CONF[k]?.colour ?? "#999" }} title={`${CONF[k]?.label ?? k}: ${Math.round(v * 100)}%`} />)}
            </div>
            <div className="cov-legend">
              {Object.entries(est.coverage).map(([k, v]) => <span key={k}><i style={{ background: CONF[k]?.colour }} />{CONF[k]?.label ?? k} {Math.round(v * 100)}%</span>)}
            </div>
            <p className="subtle" style={{ fontSize: 12.5 }}>Allowances are the estimator's figures where no public price exists. Replace them with quotes in the <Link to="/cost-library">Cost library</Link>, then Recalculate.</p>
          </div>
        </div>

        <form className="cost-settings" onSubmit={apply}>
          <h3 className="section-title">Assumptions</h3>
          <div className="grid3">
            {[["preliminaries", "Preliminaries (%)"], ["overhead_profit", "Overhead and profit (%)"], ["contingency", "Contingency (%)"],
              ["vat", "VAT (%)"], ["escalation_per_year", "Escalation per year (%)"], ["construction_months", "Construction (months)"]].map(([k, l]) => (
              <div className="field" key={k}>
                <label htmlFor={`cs-${k}`}>{l}</label>
                <input id={`cs-${k}`} className="input num" inputMode="decimal" value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
            <div className="field">
              <label htmlFor="cs-start">Construction start</label>
              <input id="cs-start" type="date" className="input" value={form.construction_start ?? ""} onChange={(e) => setForm({ ...form, construction_start: e.target.value })} />
            </div>
          </div>
          <p className="subtle" style={{ fontSize: 12.5 }}>Escalation applied: {(est.settings.escalation * 100).toFixed(1)}% from the price date to the middle of construction. Default escalation follows GASTAT's Construction Cost Index (+2% year on year).</p>
          <button className="btn primary" type="submit" disabled={busy}>{busy ? <Loader2 className="spin" size={16} /> : null} Apply and recalculate</button>
        </form>

        <div className="table-wrap boq-table">
          <table className="list" style={{ minWidth: 760 }}>
            <thead><tr><th>Largest items</th><th className="r">Quantity</th><th className="r">Rate</th><th className="r">Amount</th><th>Source</th></tr></thead>
            <tbody>
              {top.map((l) => (
                <tr key={`${l.section}-${l.description}`}>
                  <td><div className="it">{l.description}</div><div className="bs">{l.section}</div></td>
                  <td className="r num">{int(l.qty)} {l.unit}</td>
                  <td className="r num">{l.rate != null ? int(l.rate) : "–"}</td>
                  <td className="r num"><strong>{int(l.amount)}</strong></td>
                  <td><span className="conf" style={{ background: CONF[l.confidence.replace(" (edited)", "")]?.colour }} />{l.confidence}<div className="bs">{l.source}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="subtle boq-foot">All {est.lines.length} priced lines with their sources are in the Excel file (Rate source column).</p>
      </div>
    </div>
  );
}
