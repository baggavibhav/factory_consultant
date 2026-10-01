import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Trash2, X } from "lucide-react";
import { api, type Finding, type Label, type PlanDiff, type Project, type Variant } from "../lib/api";
import { dec } from "../lib/format";
import Viewer3D, { LAYERS, type CameraSync, type Highlight, type LayerKey } from "./Viewer3D";
import PlanView from "./PlanView";

const GREEN = "#1f9d55", RED = "#d63030", AMBER = "#e0a400";
const COMPARE_LAYERS = Object.fromEntries(
  LAYERS.map((l) => [l.key, l.group === "Architecture" ? l.key !== "roof" : l.key === "frames"]),
) as Record<LayerKey, boolean>;

interface Props { project: Project; variant: Variant; busy: boolean; onAccept: () => void; onDiscard: () => void; onClose: () => void }

export default function CompareView({ project, variant, busy, onAccept, onDiscard, onClose }: Props) {
  const id = project.id;
  const [mode, setMode] = useState<"3d" | "plan">("3d");
  const [diff, setDiff] = useState<PlanDiff | null>(null);
  const [labels, setLabels] = useState<{ before: Label[]; after: Label[] }>({ before: [], after: [] });
  const [issues, setIssues] = useState<{ fixed: Finding[]; added: Finding[] } | null>(null);
  const sync = useRef<CameraSync>({ pos: null, tgt: null, v: 0, from: "" }).current;

  useEffect(() => {
    api.diff(id, variant.id).then(setDiff).catch(() => setDiff(null));
    Promise.all([api.labels(id), fetch(api.variantFile(id, variant.id, "labels")).then((r) => r.json())])
      .then(([before, after]) => setLabels({ before, after })).catch(() => {});
    Promise.all([api.checks(id), api.checks(id, api.variantFile(id, variant.id, "checks"))])
      .then(([a, b]) => {
        const ids = (l: Finding[]) => new Set(l.map((f) => f.id));
        const ia = ids(a), ib = ids(b);
        setIssues({ fixed: a.filter((f) => !ib.has(f.id)), added: b.filter((f) => !ia.has(f.id)) });
      }).catch(() => setIssues(null));
  }, [id, variant.id]);

  const centre = (b: number[]): [number, number] => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
  const hiAfter: Highlight | null = useMemo(() => diff && {
    origin: centre(diff.building_after),
    rooms: [...diff.rooms_added.map((r) => ({ points: r.points, color: GREEN })), ...diff.rooms_resized.map((r) => ({ points: r.points, color: AMBER }))],
    markers: [...diff.openings_added.map((o) => ({ x: o.x, y: o.y, color: GREEN })), ...diff.columns_added.map(([x, y]) => ({ x, y, color: GREEN }))],
  }, [diff]);
  const hiBefore: Highlight | null = useMemo(() => diff && {
    origin: centre(diff.building_before),
    rooms: diff.rooms_removed.map((r) => ({ points: r.points, color: RED })),
    markers: [...diff.openings_removed.map((o) => ({ x: o.x, y: o.y, color: RED })), ...diff.columns_removed.map(([x, y]) => ({ x, y, color: RED }))],
  }, [diff]);

  const main = project.latest_build!;
  const vb = variant.build!;
  const changes = vb.changes ?? [];
  const counts = diff && {
    added: diff.rooms_added.length + diff.openings_added.length + diff.columns_added.length,
    removed: diff.rooms_removed.length + diff.openings_removed.length + diff.columns_removed.length,
    resized: diff.rooms_resized.length + (diff.building_changed ? 1 : 0),
  };

  return (
    <div className="compare">
      <div className="cmp-bar">
        <div>
          <span className="ttl">Compare: current design vs “{variant.name}”</span>
          {counts && <span className="subtle" style={{ marginLeft: 10, fontSize: 12.5 }}>{counts.added} added, {counts.removed} removed, {counts.resized} resized</span>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div className="seg" role="group" aria-label="Compare mode">
            <button aria-pressed={mode === "3d"} onClick={() => setMode("3d")}>3D</button>
            <button aria-pressed={mode === "plan"} onClick={() => setMode("plan")}>Plan</button>
          </div>
          <button className="btn sm primary" onClick={onAccept} disabled={busy}><Check size={14} /> Use this variant</button>
          <button className="btn sm" onClick={onDiscard} disabled={busy}><Trash2 size={14} /> Discard</button>
          <button className="btn sm ghost icon-btn" onClick={onClose} aria-label="Close compare"><X size={16} /></button>
        </div>
      </div>
      <div className="cmp-panes">
        <div className="cmp-pane">
          <span className="cmp-tag">Before: current design</span>
          {mode === "3d" ? (
            <Viewer3D url={api.modelUrl(id, main.id)} labels={labels.before} size={main.facts.building_m} layers={COMPARE_LAYERS}
              xray={false} showLabels={false} view="iso" sync={sync} highlight={hiBefore} />
          ) : (
            <PlanView projectId={id} buildId={main.id} concept compact diff={diff} side="before" />
          )}
          <div className="cmp-legend"><span><i style={{ background: RED }} />Removed</span></div>
        </div>
        <div className="cmp-pane">
          <span className="cmp-tag after">After: {variant.name}</span>
          {mode === "3d" ? (
            <Viewer3D url={`${api.variantFile(id, variant.id, "model.glb")}?b=${vb.id}`} labels={labels.after} size={vb.facts.building_m}
              layers={COMPARE_LAYERS} xray={false} showLabels={false} view="iso" sync={sync} highlight={hiAfter} />
          ) : (
            <PlanView projectId={id} buildId={vb.id} concept compact url={api.variantFile(id, variant.id, "plan")} diff={diff} side="after" />
          )}
          <div className="cmp-legend"><span><i style={{ background: GREEN }} />Added</span><span><i style={{ background: AMBER }} />Resized</span></div>
        </div>
      </div>
      <div className="cmp-changes">
        <table>
          <thead><tr><th>What changed</th><th>Before</th><th>After</th><th>Change</th></tr></thead>
          <tbody>
            {diff?.moved_m && (
              <tr>
                <td>Building position</td>
                <td colSpan={3}>Moved {[
                  diff.moved_m[0] ? `${dec(Math.abs(diff.moved_m[0]))} m ${diff.moved_m[0] > 0 ? "east" : "west"}` : "",
                  diff.moved_m[1] ? `${dec(Math.abs(diff.moved_m[1]))} m ${diff.moved_m[1] > 0 ? "north" : "south"}` : "",
                ].filter(Boolean).join(" and ")} on the plot</td>
              </tr>
            )}
            {changes.length === 0 && !diff?.moved_m && <tr><td colSpan={4} className="muted">No change in the key figures.</td></tr>}
            {changes.map((c) => (
              <tr key={c.label}>
                <td>{c.label}</td><td>{dec(c.before)} {c.unit}</td><td><strong>{dec(c.after)} {c.unit}</strong></td>
                <td className={c.after > c.before ? "up" : "down"}>{c.change_pct != null ? `${c.change_pct > 0 ? "+" : ""}${dec(c.change_pct)}%` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {issues && (issues.fixed.length > 0 || issues.added.length > 0) && (
          <p style={{ fontSize: 12.5, margin: "8px 0 0" }}>
            {issues.fixed.length > 0 && <span style={{ color: "var(--ok)" }}>Resolves: {issues.fixed.map((f) => f.title).join("; ")}. </span>}
            {issues.added.length > 0 && <span style={{ color: "var(--bad)" }}>New issues: {issues.added.map((f) => f.title).join("; ")}.</span>}
          </p>
        )}
      </div>
    </div>
  );
}
