import type { Mode, PlantType, ProjectStatus } from "./api";

export const PLANT_TYPE: Record<PlantType, string> = {
  industrial: "Industrial",
  retail: "Retail",
  egg_station: "Egg station",
};

export const STATUS: Record<ProjectStatus, { label: string; tone: "neutral" | "info" | "ok" | "bad" }> = {
  draft: { label: "Needs drawing", tone: "neutral" },
  drawing_ready: { label: "Ready to build", tone: "info" },
  brief_ready: { label: "Ready to build", tone: "info" },
  model_ready: { label: "Model ready", tone: "ok" },
  failed: { label: "Needs attention", tone: "bad" },
};

const nf0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });
export const int = (n: number) => nf0.format(n);
export const dec = (n: number) => nf1.format(n);
export const sqft = (m2: number) => nf0.format(m2 * 10.7639);

export function bytes(n: number): string {
  if (n < 1024 * 1024) return `${nf1.format(n / 1024)} KB`;
  return `${nf1.format(n / 1024 / 1024)} MB`;
}

export function when(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function stamp(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export const MEMBER_NAMES: Record<string, string> = {
  foundation: "Foundation pads",
  column: "Columns",
  gable_column: "Gable columns",
  rafter: "Rafters",
  eave_beam: "Eave beams",
  purlin: "Purlins",
  girt: "Girts",
  bracing: "Bracing",
};

export function statusOf(p: { status: ProjectStatus; mode: Mode }) {
  if (p.status === "draft") return { label: p.mode === "brief" ? "Needs brief" : "Needs drawing", tone: "neutral" as const };
  return STATUS[p.status];
}

export const ZONE_COLOURS: Record<string, string> = {
  production: "#f2d48c",
  storage: "#cbdbb8",
  cold: "#9ec7eb",
  dispatch: "#edbd99",
  office: "#c7c2e6",
  amenity: "#e6c7db",
  utility: "#bfbfba",
  circulation: "#dcdcd6",
};
export const M2_PER_SQFT = 0.09290304;
