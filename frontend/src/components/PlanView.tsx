import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import { Loader2, Maximize } from "lucide-react";
import { api, ApiError, type Plan } from "../lib/api";
import { ZONE_COLOURS, dec, int } from "../lib/format";

const SERVICES: { key: string; label: string; colour: string }[] = [
  { key: "electrical", label: "Electrical", colour: "#e0a400" },
  { key: "water", label: "Water supply", colour: "#2e87de" },
  { key: "drainage", label: "Drainage", colour: "#8a5a2b" },
  { key: "fire", label: "Fire protection", colour: "#d63030" },
  { key: "hvac", label: "Refrigeration and ventilation", colour: "#009e9e" },
  { key: "air", label: "Compressed air", colour: "#6b7f95" },
  { key: "gas", label: "Gas", colour: "#f28019" },
];
const OPENING_COLOUR: Record<string, string> = { dock_in: "#17222c", dock_out: "#17222c", fire_exit: "#1f9d55", entrance: "#2f6fa8", silo: "#8a98a6" };
const OPENING_LABEL: Record<string, string> = { dock_in: "Goods-in dock", dock_out: "Dispatch dock", fire_exit: "Fire exit", entrance: "Main entrance", silo: "Flour silo" };

type Tip = { x: number; y: number; lines: string[] } | null;

export default function PlanView({ projectId, buildId, concept }: { projectId: string; buildId: string; concept: boolean }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [on, setOn] = useState<Record<string, boolean>>({ rooms: true, names: true, columns: true, openings: true, electrical: true, water: false, drainage: false, fire: false, hvac: false, air: false, gas: false });
  const [solo, setSolo] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip>(null);
  const [view, setView] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const drag = useRef<{ px: number; py: number; vx: number; vy: number } | null>(null);
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    setPlan(null); setError(null);
    api.plan(projectId).then(setPlan).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [projectId, buildId]);

  const full = useMemo(() => {
    if (!plan) return null;
    const [x0, y0, x1, y1] = plan.plot;
    const pad = Math.max(x1 - x0, y1 - y0) * 0.04;
    return { x: x0 - pad, y: -(y1 + pad), w: x1 - x0 + 2 * pad, h: y1 - y0 + 2 * pad };
  }, [plan]);
  useEffect(() => { setView(full); }, [full]);

  if (error) {
    return <div className="stage-center"><div className="panel-card"><h2 className="h2">No plan for this build yet</h2><p>This model was built before the plan view existed. Rebuild it to see the plan.</p></div></div>;
  }
  if (!plan || !view || !full) return <div className="v-loading"><Loader2 className="spin" size={22} /> Loading plan</div>;

  const scale = view.w / 1000; // stroke widths relative to zoom
  const shown = (k: string) => (solo ? solo === k : on[k]);
  const routeLen = (svc: string) => plan.routes.filter((r) => r.service === svc).reduce((s, r) => s + r.length_m, 0);
  const services = SERVICES.filter((s) => plan.routes.some((r) => r.service === s.key) || plan.items.some((i) => i.service === s.key));

  function zoom(e: WheelEvent) {
    const r = svg.current!.getBoundingClientRect();
    const mx = view!.x + ((e.clientX - r.left) / r.width) * view!.w;
    const my = view!.y + ((e.clientY - r.top) / r.height) * view!.h;
    const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const w = Math.min(full!.w * 2, Math.max(full!.w / 40, view!.w * k));
    const h = (w / view!.w) * view!.h;
    setView({ x: mx - ((mx - view!.x) * w) / view!.w, y: my - ((my - view!.y) * h) / view!.h, w, h });
  }
  function down(e: PointerEvent) { drag.current = { px: e.clientX, py: e.clientY, vx: view!.x, vy: view!.y }; (e.target as Element).setPointerCapture?.(e.pointerId); }
  function move(e: PointerEvent) {
    if (!drag.current) return;
    const r = svg.current!.getBoundingClientRect();
    setView({ ...view!, x: drag.current.vx - ((e.clientX - drag.current.px) / r.width) * view!.w, y: drag.current.vy - ((e.clientY - drag.current.py) / r.height) * view!.h });
  }
  const show = (e: PointerEvent | React.MouseEvent, lines: string[]) => {
    const r = svg.current!.getBoundingClientRect();
    setTip({ x: e.clientX - r.left + 14, y: e.clientY - r.top + 14, lines });
  };

  return (
    <div className="plan">
      <svg ref={svg} className="plan-svg" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} preserveAspectRatio="xMidYMid meet"
        onWheel={zoom} onPointerDown={down} onPointerMove={move} onPointerUp={() => (drag.current = null)} onPointerLeave={() => { drag.current = null; setTip(null); }}
        role="img" aria-label="Plant plan with rooms and services">
        <g transform="scale(1,-1)">
          <rect x={plan.plot[0]} y={plan.plot[1]} width={plan.plot[2] - plan.plot[0]} height={plan.plot[3] - plan.plot[1]} className="p-plot" strokeWidth={scale * 1.5} />
          <rect x={plan.building[0]} y={plan.building[1]} width={plan.building[2] - plan.building[0]} height={plan.building[3] - plan.building[1]} className="p-building" />
          {on.rooms && plan.rooms.map((r, i) => (
            <polygon key={i} points={r.points.map((p) => p.join(",")).join(" ")} fill={ZONE_COLOURS[r.category] ?? "#ddd"} fillOpacity={r.estimated ? 0.35 : 0.6}
              stroke={r.estimated ? "var(--ink-3)" : "none"} strokeDasharray={r.estimated ? `${scale * 4} ${scale * 3}` : undefined} strokeWidth={scale * 0.8}
              onPointerMove={(e) => show(e, [r.name, `${int(r.area_m2)} m²${r.estimated ? " (estimated boundary)" : ""}`])} />
          ))}
          {plan.walls.map((w, i) => (
            <line key={i} x1={w[0]} y1={w[1]} x2={w[2]} y2={w[3]} className={w[4] === "cold" ? "p-cold" : "p-wall"} strokeWidth={scale * (w[4] === "cold" ? 1.6 : 1.1)} />
          ))}
          {on.columns && plan.columns.map((c, i) => (
            <rect key={i} x={c[0] - 0.3} y={c[1] - 0.3} width={0.6} height={0.6} className="p-col" />
          ))}
          {services.map((s) => shown(s.key) && (
            <g key={s.key}>
              {plan.routes.filter((r) => r.service === s.key).map((r, i) => (
                <polyline key={i} points={r.points.map((p) => p.join(",")).join(" ")} fill="none" stroke={s.colour}
                  strokeWidth={scale * (r.kind.toLowerCase().includes("tray") ? 4 : Math.max(1.6, r.size_mm / 40))}
                  strokeDasharray={r.underground ? `${scale * 6} ${scale * 3}` : undefined} strokeLinecap="round" strokeLinejoin="round" opacity={0.9}
                  onPointerMove={(e) => show(e, [`${s.label}: ${r.kind}`, `${r.size_mm} mm, ${dec(r.length_m)} m${r.underground ? ", underground" : ""}`])} />
              ))}
              {plan.items.filter((it) => it.service === s.key).map((it, i) => (
                <rect key={i} x={it.x - Math.max(it.w, 0.35) / 2} y={it.y - Math.max(it.d, 0.35) / 2} width={Math.max(it.w, 0.35)} height={Math.max(it.d, 0.35)}
                  fill={s.colour} stroke="var(--surface)" strokeWidth={scale * 0.5}
                  onPointerMove={(e) => show(e, [it.kind, s.label])} />
              ))}
            </g>
          ))}
          {on.openings && plan.openings.map((o, i) => {
            if (o.kind === "silo") return <circle key={i} cx={o.x} cy={o.y} r={1.7} fill={OPENING_COLOUR.silo} onPointerMove={(e) => show(e, [OPENING_LABEL.silo])} />;
            const w = o.kind === "fire_exit" ? 1.8 : o.kind === "entrance" ? 2.4 : 3.0;
            const vertical = o.side === "west" || o.side === "east";
            return <rect key={i} x={vertical ? o.x - 0.5 : o.x - w / 2} y={vertical ? o.y - w / 2 : o.y - 0.5} width={vertical ? 1 : w} height={vertical ? w : 1}
              fill={OPENING_COLOUR[o.kind]} onPointerMove={(e) => show(e, [OPENING_LABEL[o.kind]])} />;
          })}
        </g>
        {on.names && plan.rooms.filter((r) => r.area_m2 > 6).map((r, i) => {
          const xs = r.points.map((p) => p[0]); const ys = r.points.map((p) => p[1]);
          const cx = (Math.min(...xs) + Math.max(...xs)) / 2; const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
          const w = Math.max(...xs) - Math.min(...xs);
          const fs = Math.min(scale * 17, Math.max(scale * 8, (w / Math.max(6, r.name.length)) * 1.7));
          if (fs * r.name.length * 0.55 > w * 1.15) return null; // too small to label legibly at this zoom
          return <text key={i} x={cx} y={-cy} fontSize={fs} textAnchor="middle" dominantBaseline="middle" className="p-name">{r.name}</text>;
        })}
      </svg>

      <div className="plan-panel">
        <div className="section-title">Show</div>
        {[["rooms", "Rooms"], ["names", "Room names"], ["columns", "Columns"], ["openings", "Doors, docks and silos"]].map(([k, l]) => (
          <label className="toggle" key={k}><span>{l}</span><span className="switch"><input type="checkbox" checked={on[k]} onChange={(e) => setOn({ ...on, [k]: e.target.checked })} /><span /></span></label>
        ))}
        {services.length > 0 ? (
          <>
            <div className="section-title" style={{ marginTop: 12 }}>Services <span className="subtle" style={{ fontWeight: 450 }}>click a name to show it alone</span></div>
            {services.map((s) => (
              <div className={`svc${solo === s.key ? " solo" : ""}`} key={s.key}>
                <button className="svc-name" onClick={() => setSolo(solo === s.key ? null : s.key)} aria-pressed={solo === s.key}>
                  <span className="svc-line" style={{ background: s.colour }} />{s.label}
                  <span className="subtle num">{int(routeLen(s.key))} m</span>
                </button>
                <span className="switch"><input type="checkbox" aria-label={`Show ${s.label}`} checked={!!on[s.key]} disabled={!!solo} onChange={(e) => setOn({ ...on, [s.key]: e.target.checked })} /><span /></span>
              </div>
            ))}
            <p className="subtle" style={{ fontSize: 12, margin: "10px 0 0" }}>Dashed lines run underground. Hover any line or item for its size and length.</p>
          </>
        ) : (
          <p className="subtle" style={{ fontSize: 12.5 }}>{concept ? "No services in this build." : "Service routes are generated for concept projects. For drawings, fittings are counted per room in the BOQ."}</p>
        )}
        <button className="btn sm" style={{ marginTop: 12 }} onClick={() => setView(full)}><Maximize size={14} /> Fit to plot</button>
      </div>

      {tip && <div className="plan-tip" style={{ left: tip.x, top: tip.y }}>{tip.lines.map((l, i) => <div key={i} className={i === 0 ? "t1" : ""}>{l}</div>)}</div>}
      <div className="v-hint">Scroll to zoom, drag to pan</div>
    </div>
  );
}
