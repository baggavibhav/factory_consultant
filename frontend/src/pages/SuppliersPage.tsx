import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Plus, Search, Trash2 } from "lucide-react";
import { api, ApiError, type Supplier } from "../lib/api";
import { useToast } from "../components/Toasts";

const STATUS: Record<Supplier["status"], { label: string; cls: string }> = {
  prospect: { label: "Prospect", cls: "badge" },
  vetting: { label: "Vetting", cls: "badge warn" },
  approved: { label: "Approved", cls: "badge ok" },
  rejected: { label: "Rejected", cls: "badge bad" },
};
const CHECK_LABEL: Record<string, string> = {
  cr_verified: "Commercial registration verified", iso_9001: "ISO 9001 certificate", food_grade: "Food-grade / SASO compliance",
  references: "References checked", financials: "Financial standing checked", site_visit: "Factory or site visit",
};

export default function SuppliersPage() {
  const toast = useToast();
  const [data, setData] = useState<{ suppliers: Supplier[]; categories: Record<string, string>; checks: string[] } | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<Partial<Supplier>>({ name: "", categories: [], city: "", website: "" });

  const load = () => api.suppliers().then(setData).catch((e) => toast(e instanceof ApiError ? e.message : String(e), true));
  useEffect(() => { load(); }, []);

  const shown = useMemo(() => (data?.suppliers ?? []).filter((s) =>
    (!cat || s.categories.includes(cat)) && `${s.name} ${s.city} ${s.source}`.toLowerCase().includes(q.trim().toLowerCase())), [data, q, cat]);

  async function patch(s: Supplier, body: Partial<Supplier>) {
    try { await api.editSupplier(s.id, body); load(); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Could not save.", true); }
  }
  async function add() {
    if (!draft.name || draft.name.length < 2) { toast("Enter the supplier name.", true); return; }
    try { await api.addSupplier(draft); setAdding(false); setDraft({ name: "", categories: [], city: "", website: "" }); load(); toast("Supplier added as a prospect"); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Could not add.", true); }
  }

  if (!data) return <div className="page"><p className="muted">Loading suppliers…</p></div>;
  const cats = data.categories;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h1">Suppliers</h1>
          <p className="muted">{data.suppliers.length} suppliers · {data.suppliers.filter((s) => s.status === "approved").length} approved. Prospects were found in public sources; vet them before approving.</p>
        </div>
        <button className="btn primary" onClick={() => setAdding(!adding)}><Plus size={16} /> Add supplier</button>
      </div>
      {adding && (
        <div className="panel-card" style={{ maxWidth: "none", marginBottom: 14 }}>
          <div className="grid3">
            <div className="field"><label htmlFor="ns-name">Name</label><input id="ns-name" className="input" value={draft.name ?? ""} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="ns-city">City</label><input id="ns-city" className="input" value={draft.city ?? ""} onChange={(e) => setDraft({ ...draft, city: e.target.value })} /></div>
            <div className="field"><label htmlFor="ns-web">Website</label><input id="ns-web" className="input" value={draft.website ?? ""} onChange={(e) => setDraft({ ...draft, website: e.target.value })} /></div>
          </div>
          <div className="chips" style={{ margin: "10px 0" }}>
            {Object.entries(cats).map(([k, v]) => (
              <label key={k} className="chip-check"><input type="checkbox" checked={draft.categories?.includes(k) ?? false}
                onChange={(e) => setDraft({ ...draft, categories: e.target.checked ? [...(draft.categories ?? []), k] : (draft.categories ?? []).filter((c) => c !== k) })} /> {v}</label>
            ))}
          </div>
          <button className="btn primary" onClick={add}>Save supplier</button>
        </div>
      )}
      <div className="toolbar">
        <div className="search"><Search size={16} /><input className="input" placeholder="Search suppliers" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search suppliers" /></div>
        <select className="select" style={{ maxWidth: 280 }} value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {Object.entries(cats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="sup-list">
        {shown.map((s) => (
          <div className={`sup${open === s.id ? " open" : ""}`} key={s.id}>
            <button className="sup-row" onClick={() => setOpen(open === s.id ? null : s.id)} aria-expanded={open === s.id}>
              <span className="sup-name">{s.name}</span>
              <span className="subtle">{s.categories.map((c) => cats[c] ?? c).join(" · ")}</span>
              <span className="subtle">{s.city}</span>
              <span className={STATUS[s.status].cls}>{STATUS[s.status].label}</span>
            </button>
            {open === s.id && (
              <div className="sup-body">
                <p className="subtle" style={{ margin: "0 0 10px" }}>{s.source} {s.website && <a href={s.website} target="_blank" rel="noreferrer">Open source <ExternalLink size={11} /></a>}</p>
                <div className="grid3">
                  {(["contact", "email", "phone", "cr_number"] as const).map((k) => (
                    <div className="field" key={k}>
                      <label htmlFor={`s-${s.id}-${k}`}>{{ contact: "Contact person", email: "Email", phone: "Phone", cr_number: "CR number" }[k]}</label>
                      <input id={`s-${s.id}-${k}`} className="input" defaultValue={s[k]} onBlur={(e) => e.target.value !== s[k] && patch(s, { [k]: e.target.value })} />
                    </div>
                  ))}
                  <div className="field">
                    <label htmlFor={`s-${s.id}-status`}>Status</label>
                    <select id={`s-${s.id}-status`} className="select" value={s.status} onChange={(e) => patch(s, { status: e.target.value as Supplier["status"] })}>
                      {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>
                  </div>
                </div>
                <div className="section-title" style={{ marginTop: 12 }}>Vetting checklist</div>
                <div className="checks">
                  {data.checks.map((c) => (
                    <label key={c} className="chip-check"><input type="checkbox" checked={!!s.checks[c]} onChange={(e) => patch(s, { checks: { ...s.checks, [c]: e.target.checked } })} /> {CHECK_LABEL[c] ?? c}</label>
                  ))}
                </div>
                <p className="subtle" style={{ fontSize: 12 }}>A supplier can be approved once the commercial registration and references are checked.</p>
                <div className="field" style={{ marginTop: 8 }}>
                  <label htmlFor={`s-${s.id}-notes`}>Notes</label>
                  <textarea id={`s-${s.id}-notes`} className="textarea" defaultValue={s.notes} onBlur={(e) => e.target.value !== s.notes && patch(s, { notes: e.target.value })} />
                </div>
                <button className="btn sm ghost danger" style={{ marginTop: 8 }} onClick={async () => { await api.deleteSupplier(s.id); load(); }}><Trash2 size={14} /> Remove</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
