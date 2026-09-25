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
  latest_build: BuildInfo | null; builds: number; events: ProjectEvent[];
}
export interface ProjectSummary {
  id: string; name: string; mode: Mode; plant_type: PlantType; country: string; city: string; status: ProjectStatus;
  updated_at: string; footprint_m2: number | null; frames: number | null;
}
export interface Meta { version: string; plant_types: { value: PlantType; label: string }[]; configs: string[]; converter_available: boolean }
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
  plan: (id: string) => request<Plan>(`/api/projects/${id}/plan`),
  build: (id: string) => request<Project>(`/api/projects/${id}/builds`, { method: "POST" }),
  labels: (id: string) => request<Label[]>(`/api/projects/${id}/labels`),
  modelUrl: (id: string, build?: string) => `/api/projects/${id}/model.glb${build ? `?b=${build}` : ""}`,
  boq: (id: string) => request<Boq>(`/api/projects/${id}/boq`),
  boqXlsxUrl: (id: string) => `/api/projects/${id}/boq.xlsx`,
  viewerUrl: (id: string) => `/api/projects/${id}/viewer.html`,
};
