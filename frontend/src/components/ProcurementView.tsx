import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Award, Download, Loader2, Trash2, Upload, UserPlus, X } from "lucide-react";
import { api, ApiError, type Comparison, type ProcPackage, type Project } from "../lib/api";
import { int } from "../lib/format";

interface Props { project: Project; onProject: (p: Project) => void; onToast: (t: string, bad?: boolean) => void }

export default function ProcurementView({ project, onProject, onToast }: Props) {
  const id = project.id;
  const [pk, setPk] = useState<ProcPackage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inviting, setInviting] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [cmp, setCmp] = useState<{ key: string; data: Comparison } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadFor, setUploadFor] = useState<{ key: string; supplier: string } | null>(null);

  const load = () => api.procurement(id).then((r) => setPk(r.packages)).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  useEffect(() => { load(); }, [id, project.latest_build?.id]);

  async function openCompare(key: string) {
    try { setCmp({ key, data: await api.compareQuotes(id, key) }); }
    catch (e) { onToast(e instanceof ApiError ? e.message : "Could not compare.", true); }
  }
  async function upload(f: File) {
    if (!uploadFor) return;
    setBusy(true);
    try {
      const r = await api.uploadQuote(id, uploadFor.key, f, uploadFor.supplier);
      onToast(`Quote read: ${r.supplier_name || "supplier"}, ${r.priced} lines priced`);
      await load();
      await openCompare(uploadFor.key);
    } catch (e) { onToast(e instanceof ApiError ? e.message : "Could not read the quote.", true); }
    finally { setBusy(false); setUploadFor(null); if (fileRef.current) fileRef.current.value = ""; }
  }
  async function accept(key: string, qid: string) {
    setBusy(true);
    try { const p = await api.acceptQuote(id, key, qid); onProject(p); onToast("Quote accepted: rates updated and the estimate recalculated"); await load(); await openCompare(key); }
    catch (e) { onToast(e instanceof ApiError ? e.message : "Could not accept.", true); }
    finally { setBusy(false); }
  }

  if (error) return <div className="stage-center"><div className="panel-card"><h2 className="h2">Procurement unavailable</h2><p>{error}</p></div></div>;
  if (!pk) return <div className="v-loading"><Loader2 className="spin" size={22} /> Loading packages</div>;

  return (
    <div className="stage-scroll">
      <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <div className="boq">
        <div className="boq-head">
          <div>
            <h2 className="h2">Procurement</h2>
            <p className="muted">The priced BOQ split into supplier packages. Invite suppliers, send each the RFQ Excel, upload their filled-in files, and compare. Accepting a quote replaces allowances with quoted rates. Manage suppliers in <Link to="/suppliers">Suppliers</Link>.</p>
          </div>
        </div>
        <div className="table-wrap boq-table">
          <table className="list" style={{ minWidth: 860 }}>
            <thead><tr><th>Package</th><th className="r">Estimate (SAR)</th><th>Invited</th><th className="r">Quotes</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {pk.map((p) => (
                <tr key={p.key}>
                  <td><div className="it">{p.name}</div><div className="bs">{p.lines} lines</div></td>
                  <td className="r num">{int(p.estimate)}</td>
                  <td>{p.invited.length ? p.invited.map((s) => <span key={s.id} className="chip-s">{s.name}</span>) : <span className="subtle">None yet</span>}</td>
                  <td className="r num">{p.quotes}</td>
                  <td>{p.accepted ? <span className="badge ok">Accepted: {p.accepted.supplier}</span> : p.quotes ? <span className="badge warn">Comparing</span> : <span className="badge">Open</span>}</td>
                  <td>
                    <div className="acts" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="btn sm" onClick={() => { setInviting(p.key); setPicked(p.invited.map((s) => s.id)); }}><UserPlus size={14} /> Invite</button>
                      <a className="btn sm" href={api.rfqUrl(id, p.key)}><Download size={14} /> RFQ</a>
                      <button className="btn sm" disabled={busy} onClick={() => { setUploadFor({ key: p.key, supplier: "" }); }}><Upload size={14} /> Quote</button>
                      {p.quotes > 0 && <button className="btn sm primary" onClick={() => openCompare(p.key)}>Compare</button>}
                    </div>
                    {inviting === p.key && (
                      <div className="pop">
                        <div className="section-title">Suppliers for {p.name}</div>
                        {p.suggested.length === 0 && <p className="subtle">No suppliers in this category yet. Add them on the Suppliers page.</p>}
                        {p.suggested.map((s) => (
                          <label key={s.id} className="chip-check" style={{ display: "flex" }}>
                            <input type="checkbox" checked={picked.includes(s.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, s.id] : picked.filter((x) => x !== s.id))} />
                            {s.name} <span className="subtle">({s.status})</span>
                          </label>
                        ))}
                        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                          <button className="btn sm primary" onClick={async () => { await api.invite(id, p.key, picked); setInviting(null); load(); onToast("Suppliers invited. Download the RFQ and send it to them."); }}>Save</button>
                          <button className="btn sm" onClick={() => setInviting(null)}>Cancel</button>
                        </div>
                      </div>
                    )}
                    {uploadFor?.key === p.key && (
                      <div className="pop">
                        <div className="section-title">Upload a returned RFQ</div>
                        <select className="select" value={uploadFor.supplier} onChange={(e) => setUploadFor({ ...uploadFor, supplier: e.target.value })} aria-label="Supplier">
                          <option value="">Supplier named in the file</option>
                          {[...p.invited, ...p.suggested.filter((s) => !p.invited.some((i) => i.id === s.id))].map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                        </select>
                        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                          <button className="btn sm primary" onClick={() => fileRef.current?.click()} disabled={busy}>{busy ? <Loader2 className="spin" size={14} /> : <Upload size={14} />} Choose file</button>
                          <button className="btn sm" onClick={() => setUploadFor(null)}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {cmp && (
          <div className="cmp-card">
            <div className="boq-head" style={{ paddingTop: 16 }}>
              <div>
                <h3 className="h2" style={{ fontSize: 18 }}>Quote comparison: {cmp.data.package}</h3>
                <p className="muted" style={{ fontSize: 13 }}>Totals are comparable: excluding VAT, with allowances where delivery or installation is excluded, and missing lines filled at library rates. Library estimate for this package: SAR {int(cmp.data.library_total ?? 0)}.</p>
              </div>
              <button className="btn sm ghost icon-btn" onClick={() => setCmp(null)} aria-label="Close comparison"><X size={16} /></button>
            </div>
            {cmp.data.quotes.length === 0 ? <p className="muted" style={{ padding: "0 22px 18px" }}>No quotes yet.</p> : (
              <>
                {cmp.data.reasons && <div className="note" style={{ margin: "0 22px 12px" }}><Award size={14} style={{ verticalAlign: "-2px" }} /> <strong>Recommended: {cmp.data.quotes.find((q) => q.quote_id === cmp.data.recommended)?.supplier}</strong> — {cmp.data.reasons.join("; ")}.</div>}
                <div className="table-wrap boq-table">
                  <table className="list" style={{ minWidth: 860 }}>
                    <thead><tr><th>Supplier</th><th className="r">Comparable total</th><th className="r">vs estimate</th><th className="r">Lead time</th><th>Scores</th><th>Flags</th><th /></tr></thead>
                    <tbody>
                      {cmp.data.quotes.map((q) => (
                        <tr key={q.quote_id} className={q.quote_id === cmp.data.recommended ? "rec" : ""}>
                          <td><div className="it">{q.supplier}</div>{q.quote_id === cmp.data.recommended && <span className="badge ok">Best value</span>}</td>
                          <td className="r num"><strong>{int(q.total)}</strong>{q.gaps_value > 0 && <div className="bs">incl. {int(q.gaps_value)} gap-filled</div>}</td>
                          <td className="r num">{cmp.data.library_total ? `${Math.round((q.total / cmp.data.library_total - 1) * 100)}%` : ""}</td>
                          <td className="r num">{q.lead_time_weeks ? `${q.lead_time_weeks} wk` : "–"}</td>
                          <td style={{ minWidth: 170 }}>
                            <div className="score"><strong>{Math.round(q.score)}</strong>/100</div>
                            <div className="bs">price {Math.round(q.scores.price)} · compliance {Math.round(q.scores.compliance)} · lead {Math.round(q.scores.lead_time)} · complete {Math.round(q.scores.completeness)}</div>
                          </td>
                          <td style={{ maxWidth: 320 }}>{q.flags.length ? <ul className="flags">{q.flags.slice(0, 5).map((f, i) => <li key={i}>{f}</li>)}</ul> : <span className="subtle">None</span>}</td>
                          <td>
                            <div style={{ display: "grid", gap: 4 }}>
                              <button className="btn sm primary" disabled={busy} onClick={() => accept(cmp.key, q.quote_id)}>Accept</button>
                              <button className="btn sm ghost danger" onClick={async () => { await api.deleteQuote(id, cmp.key, q.quote_id); load(); openCompare(cmp.key); }}><Trash2 size={13} /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="subtle boq-foot">Scores: price {Math.round((cmp.data.weights?.price ?? 0.6) * 100)}%, compliance {Math.round((cmp.data.weights?.compliance ?? 0.2) * 100)}%, lead time {Math.round((cmp.data.weights?.lead_time ?? 0.1) * 100)}%, completeness {Math.round((cmp.data.weights?.completeness ?? 0.1) * 100)}%. Expired quotes are halved. The recommendation supports the decision; the award is yours.</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
