import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RotateCcw, Save, Search } from "lucide-react";
import { api, ApiError, type RateEntry, type RateLibrary } from "../lib/api";
import { int } from "../lib/format";
import { useToast } from "../components/Toasts";

const CONF: Record<string, string> = { official: "#26815a", published: "#2f7db8", allowance: "#e0a400", quoted: "#7a4fb3" };
type Filter = "all" | "official" | "published" | "allowance" | "edited";

export default function CostLibraryPage() {
  const toast = useToast();
  const [lib, setLib] = useState<RateLibrary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [edit, setEdit] = useState<Record<string, { rate: string; note: string }>>({});

  const load = () => api.rates().then(setLib).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  useEffect(() => { load(); }, []);

  const shown = useMemo(() => (lib?.rates ?? []).filter((r) =>
    (filter === "all" || (filter === "edited" ? r.edited : r.confidence === filter)) &&
    `${r.match.join(" ")} ${r.source}`.toLowerCase().includes(q.trim().toLowerCase())), [lib, q, filter]);

  async function save(r: RateEntry) {
    const e = edit[r.key];
    if (!e || e.rate === "" || isNaN(Number(e.rate))) { toast("Enter a rate first.", true); return; }
    try {
      await api.editRate(r.key, { rate: Number(e.rate), note: e.note || undefined });
      toast(`Rate saved: ${r.match[0]}. Recalculate projects to apply it.`);
      setEdit((x) => { const n = { ...x }; delete n[r.key]; return n; });
      load();
    } catch (err) { toast(err instanceof ApiError ? err.message : "Could not save.", true); }
  }
  async function reset(r: RateEntry) {
    await api.resetRate(r.key); toast(`Rate reset to the library value: ${r.match[0]}`); load();
  }

  const counts = (lib?.rates ?? []).reduce<Record<string, number>>((m, r) => { m[r.confidence] = (m[r.confidence] ?? 0) + 1; return m; }, {});

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h1">Cost library</h1>
          <p className="muted">
            {lib ? `${lib.name}: ${lib.rates.length} rates in ${lib.currency}, prices dated ${lib.rate_date}. ${counts.official ?? 0} official, ${counts.published ?? 0} from published prices, ${counts.allowance ?? 0} estimator allowances.` : "Loading rates…"}
          </p>
        </div>
      </div>
      {error && <div className="note" role="alert">{error}</div>}
      <div className="note" style={{ marginBottom: 14 }}>
        <strong>How to improve the estimate:</strong> replace allowances (amber) with real prices from quotes or past projects. Edited rates are marked, apply to every project when you press Recalculate, and can be reset at any time.
      </div>
      <div className="toolbar">
        <div className="search"><Search size={16} /><input className="input" placeholder="Search items or sources" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search rates" /></div>
        <div className="seg" role="group" aria-label="Filter">
          {(["all", "official", "published", "allowance", "edited"] as Filter[]).map((f) => (
            <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f[0].toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table className="list rate-table">
          <thead><tr><th>Item</th><th>Unit</th><th className="r">Installed rate</th><th className="r">Range</th><th>Source</th><th>Update</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.key}>
                <td>
                  <div className="it">{r.match[0]}</div>
                  {r.match.length > 1 && <div className="bs">also: {r.match.slice(1).join(", ")}</div>}
                  {r.per && <div className="bs">+ {r.per_value} per {r.per === "kva" ? "kVA" : "m³"}</div>}
                </td>
                <td>{r.unit}</td>
                <td className="r num"><strong>{int(r.installed)}</strong>{r.edited && <span className="edited-tag">edited</span>}</td>
                <td className="r num subtle">{r.low != null && r.high != null ? `${int(r.low)}–${int(r.high)}` : "±"}</td>
                <td className="src">
                  <span className="conf" style={{ background: CONF[r.confidence] }} />{r.confidence}{r.date ? `, ${r.date}` : ""}
                  <div className="bs">{r.source}{r.url && <> <a href={r.url} target="_blank" rel="noreferrer"><ExternalLink size={11} /></a></>}</div>
                  {r.supply != null && <div className="bs">supply {int(r.supply)} × {r.factor} to installed</div>}
                  {r.note && <div className="bs"><em>{r.note}</em></div>}
                </td>
                <td className="upd">
                  <input className="input num" inputMode="decimal" placeholder="New rate" aria-label={`New rate for ${r.match[0]}`}
                    value={edit[r.key]?.rate ?? ""} onChange={(e) => setEdit({ ...edit, [r.key]: { rate: e.target.value, note: edit[r.key]?.note ?? "" } })} />
                  <input className="input" placeholder="Source, e.g. quote from…" aria-label={`Source for ${r.match[0]}`}
                    value={edit[r.key]?.note ?? ""} onChange={(e) => setEdit({ ...edit, [r.key]: { rate: edit[r.key]?.rate ?? "", note: e.target.value } })} />
                  <div style={{ display: "flex", gap: 4 }}>
                    <button className="btn sm" onClick={() => save(r)}><Save size={13} /> Save</button>
                    {r.edited && <button className="btn sm ghost" onClick={() => reset(r)} title="Reset to library value"><RotateCcw size={13} /></button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
