export type PlantType = "industrial" | "retail" | "egg_station";
export type ProjectStatus = "draft" | "drawing_ready" | "brief_ready" | "model_ready" | "failed";
export type Mode = "drawing" | "brief";

export interface MemberStat { count: number; length_m: number }
export interface Facts {
  plant: string;
  source_file: string;
  generated_at: string;
  building_m: [number, number];
  footprint_m2: number;
  levels: { ffl: number; eaves_south: number; eaves_north: number; ridge: number; mezzanine: number | null };
  wall_lines: number;
  frames: number;
  bays_m: number[];
  span_m: number | null;
  member_schedule: Record<string, MemberStat>;
  sizes_indicative: boolean;
  warnings: string[];
  mode?: "concept";
  template?: string;
  plot_m?: [number, number];
  program?: ProgramRoom[];
  assumptions?: string[];
  quantities?: { steel_t: number; concrete_m3: number; roof_m2: number; wall_m2: number; items: number };
  cost?: CostSummary;
  mep?: Record<string, Record<string, number>>;
}
export interface BoqItem { section: string; description: string; unit: string; qty: number; spec: string; basis: string; material: string; waste: number }
export interface BomLine { material: string; unit: string; qty: number; waste: number; spec: string; section: string }
export interface Boq {
  currency: string;
  sections: { name: string; items: BoqItem[] }[];
  bom: BomLine[];
  headline: { steel_t: number; concrete_m3: number; roof_m2: number; wall_m2: number; items: number };
  mep: Record<string, Record<string, number>>;
}
export interface ProgramRoom { name: string; category: string; area_m2: number; temp_c: number | null; width_m: number; depth_m: number; estimated?: boolean }
export interface Brief {
  plant_type: PlantType;
  built_up_area_m2: number;
  plot_width_m?: number | null;
  plot_depth_m?: number | null;
  products?: string;
  output_tonnes_per_day?: number | null;
  shifts_per_day?: number | null;
  lines_now?: number | null;
  lines_future?: number | null;
  cold_storage?: boolean | null;
  blast_freezer?: boolean | null;
  staff_per_shift?: number | null;
  office_staff?: number | null;
  qa_lab?: boolean | null;
  mezzanine?: boolean | null;
  clear_height_m?: number | null;
  female_staff_share?: number | null;
  flour_silos?: boolean | null;
  structure_option?: "clear_span" | "two_span" | null;
  span_m?: number | null;
  bay_m?: number | null;
  roof_pitch_deg?: number | null;
  goods_in_yard_m?: number | null;
  dispatch_yard_m?: number | null;
  zone_sizes?: Record<string, number>;
}
export interface Change { label: string; before: number; after: number; unit: string; change_pct: number | null }
export interface BuildInfo { id: string; started_at: string; finished_at: string; duration_s: number; facts: Facts; warnings: string[]; changes?: Change[] }
export interface CostSummary { available: boolean; reason?: string; currency?: string; total?: number; low?: number; high?: number; before_vat?: number; per_m2?: number; per_sqft?: number; coverage?: Record<string, number> }
export interface BuildUp { direct: number; preliminaries: number; overhead_profit: number; contingency: number; escalation: number; before_vat: number; vat: number; total: number }
export interface CostLine { section: string; description: string; unit: string; qty: number; rate: number | null; amount: number; low: number; high: number; key: string | null; confidence: string; source: string; url: string; date: string }
export interface Estimate {
  available?: boolean; reason?: string;
  currency: string; library: string; rate_date: string;
  settings: { preliminaries: number; overhead_profit: number; contingency: number; vat: number; escalation_per_year?: number; construction_start: string; construction_months: number; escalation: number };
  likely: BuildUp; low: BuildUp; high: BuildUp; per_m2: number | null; per_sqft: number | null;
  sections: { name: string; amount: number }[]; coverage: Record<string, number>;
  benchmarks: { name: string; low_per_m2: number; high_per_m2: number; note: string; status: string | null }[];
  unpriced: string[]; lines: CostLine[];
}
export interface RateEntry { key: string; match: string[]; unit: string; installed: number; rate: number | null; supply: number | null; factor: number; low: number | null; high: number | null; per: string | null; per_value: number; confidence: string; source: string; url: string; date: string; note: string; edited: boolean }
export interface RateLibrary { name: string; currency: string; rate_date: string; escalation_per_year: number; defaults: Record<string, number>; rates: RateEntry[] }
export interface Supplier {
  id: string; name: string; categories: string[]; country: string; city: string; website: string; source: string;
  contact: string; email: string; phone: string; cr_number: string; status: "prospect" | "vetting" | "approved" | "rejected";
  checks: Record<string, boolean>; notes: string; created_at: string;
}
export interface ProcPackage { key: string; name: string; lines: number; estimate: number; invited: Supplier[]; quotes: number; accepted: { supplier: string; id: string } | null; suggested: Supplier[] }
export interface QuoteRow {
  quote_id: string; supplier_id: string | null; supplier: string; total: number; gaps_value: number; lead_time_weeks: number | null;
  valid_until: string | null; scores: Record<string, number>; score: number; flags: string[];
  lines: { id: string; description: string; qty: number; unit: string; quoted: number | null; normalised_rate: number; amount: number; gap: boolean; complies: boolean | null; remarks: string; library_rate: number | null }[];
}
export interface Comparison { package: string; currency: string; quotes: QuoteRow[]; recommended: string | null; reasons?: string[]; weights?: Record<string, number>; library_total?: number }
export interface Finding {
  id: string; severity: "critical" | "major" | "minor" | "info"; area: string; title: string; detail: string;
  suggestion: string; at: [number, number] | null; fix: Record<string, unknown> | null; fix_label: string | null;
}
export interface Variant { id: string; name: string; brief: Brief; created_at: string; source: string | null; build: BuildInfo | null }
export interface PlanDiff {
  building_before: number[]; building_after: number[]; building_changed: boolean; moved_m: [number, number] | null;
  rooms_added: { name: string; points: [number, number][]; area_m2: number }[];
  rooms_removed: { name: string; points: [number, number][]; area_m2: number }[];
  rooms_resized: { name: string; before: number; after: number; points: [number, number][] }[];
  openings_added: { kind: string; x: number; y: number }[];
  openings_removed: { kind: string; x: number; y: number }[];
  columns_added: [number, number][];
  columns_removed: [number, number][];
}
export interface Plan {
  plot: [number, number, number, number];
  building: [number, number, number, number];
  walls: [number, number, number, number, string][];
  rooms: { name: string; category: string; area_m2: number; estimated: boolean; points: [number, number][] }[];
  columns: [number, number][];
  openings: { kind: string; x: number; y: number; side: string }[];
  routes: { service: string; kind: string; size_mm: number; length_m: number; underground: boolean; points: [number, number][] }[];
  items: { service: string; kind: string; x: number; y: number; w: number; d: number }[];
}
export interface DrawingInfo { filename: string; kind: string; size_bytes: number; uploaded_at: string; dxf_filename: string | null }
export interface ProjectEvent { at: string; kind: string; message: string }
export interface Project {
  id: string; name: string; mode: Mode; plant_type: PlantType; country: string; city: string; config: string | null; notes: string;
  brief: Brief | null; status: ProjectStatus; created_at: string; updated_at: string; drawing: DrawingInfo | null;
  latest_build: BuildInfo | null; builds: number; events: ProjectEvent[]; variants?: Variant[];
}
export interface ProjectSummary {
  id: string; name: string; mode: Mode; plant_type: PlantType; country: string; city: string; status: ProjectStatus;
  updated_at: string; footprint_m2: number | null; frames: number | null;
}
export interface Meta { version: string; plant_types: { value: PlantType; label: string }[]; configs: string[]; converter_available: boolean; demo?: boolean }
export interface Label { text: string; pos: [number, number, number]; cold: boolean }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Can't reach the Factory Consultant server. Check that `fca serve` is running.", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch { /* keep default message */ }
    throw new ApiError(detail, res.status);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  meta: () => request<Meta>("/api/meta"),
  projects: () => request<ProjectSummary[]>("/api/projects"),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (body: { name: string; mode: Mode; plant_type: PlantType; country: string; city: string; config: string | null; notes: string }) =>
    request<Project>("/api/projects", { method: "POST", ...json(body) }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  uploadDrawing: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Project>(`/api/projects/${id}/drawing`, { method: "POST", body: form });
  },
  saveBrief: (id: string, brief: Brief) =>
    request<Project>(`/api/projects/${id}/brief`, { method: "PUT", ...json(brief) }),
  briefDefaults: (type: PlantType) => request<Record<string, number | boolean | null | string | string[]>>(`/api/brief-defaults/${type}`),
  cost: (id: string) => request<Estimate>(`/api/projects/${id}/cost`),
  costSettings: (id: string, body: Record<string, unknown>) => request<Project>(`/api/projects/${id}/cost-settings`, { method: "PUT", ...json(body) }),
  recalc: (id: string) => request<Project>(`/api/projects/${id}/cost/recalculate`, { method: "POST" }),
  rates: () => request<RateLibrary>("/api/rates"),
  editRate: (key: string, body: { rate?: number; low?: number; high?: number; note?: string }) => request<unknown>(`/api/rates/${key}`, { method: "PUT", ...json(body) }),
  resetRate: (key: string) => request<unknown>(`/api/rates/${key}`, { method: "DELETE" }),
  suppliers: () => request<{ suppliers: Supplier[]; categories: Record<string, string>; checks: string[] }>("/api/suppliers"),
  addSupplier: (body: Partial<Supplier>) => request<Supplier>("/api/suppliers", { method: "POST", ...json(body) }),
  editSupplier: (sid: string, body: Partial<Supplier>) => request<Supplier>(`/api/suppliers/${sid}`, { method: "PATCH", ...json(body) }),
  deleteSupplier: (sid: string) => request<unknown>(`/api/suppliers/${sid}`, { method: "DELETE" }),
  procurement: (id: string) => request<{ packages: ProcPackage[]; currency: string }>(`/api/projects/${id}/procurement`),
  invite: (id: string, key: string, ids: string[]) => request<unknown>(`/api/projects/${id}/procurement/${key}/invite`, { method: "POST", ...json({ supplier_ids: ids }) }),
  rfqUrl: (id: string, key: string) => `/api/projects/${id}/procurement/${key}/rfq.xlsx`,
  uploadQuote: (id: string, key: string, file: File, supplierId: string) => {
    const fd = new FormData(); fd.append("file", file); fd.append("supplier_id", supplierId);
    return request<{ id: string; supplier_name: string; priced: number }>(`/api/projects/${id}/procurement/${key}/quotes`, { method: "POST", body: fd });
  },
  deleteQuote: (id: string, key: string, qid: string) => request<unknown>(`/api/projects/${id}/procurement/${key}/quotes/${qid}`, { method: "DELETE" }),
  compareQuotes: (id: string, key: string) => request<Comparison>(`/api/projects/${id}/procurement/${key}/compare`),
  acceptQuote: (id: string, key: string, qid: string) => request<Project>(`/api/projects/${id}/procurement/${key}/quotes/${qid}/accept`, { method: "POST" }),
  plan: (id: string, url?: string) => request<Plan>(url ?? `/api/projects/${id}/plan`),
  checks: (id: string, url?: string) => request<Finding[]>(url ?? `/api/projects/${id}/checks`),
  createVariant: (id: string, body: { name: string; changes?: Record<string, unknown>; brief?: Brief; source?: string | null }) =>
    request<Project>(`/api/projects/${id}/variants`, { method: "POST", ...json(body) }),
  acceptVariant: (id: string, vid: string) => request<Project>(`/api/projects/${id}/variants/${vid}/accept`, { method: "POST" }),
  deleteVariant: (id: string, vid: string) => request<Project>(`/api/projects/${id}/variants/${vid}`, { method: "DELETE" }),
  variantFile: (id: string, vid: string, file: "model.glb" | "plan" | "diff" | "labels" | "checks" | "boq") => `/api/projects/${id}/variants/${vid}/${file}`,
  diff: (id: string, vid: string) => request<PlanDiff>(`/api/projects/${id}/variants/${vid}/diff`),
  build: (id: string) => request<Project>(`/api/projects/${id}/builds`, { method: "POST" }),
  labels: (id: string) => request<Label[]>(`/api/projects/${id}/labels`),
  modelUrl: (id: string, build?: string) => `/api/projects/${id}/model.glb${build ? `?b=${build}` : ""}`,
  boq: (id: string) => request<Boq>(`/api/projects/${id}/boq`),
  boqXlsxUrl: (id: string) => `/api/projects/${id}/boq.xlsx`,
  viewerUrl: (id: string) => `/api/projects/${id}/viewer.html`,
};
