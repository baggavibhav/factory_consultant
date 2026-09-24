/** Portal-frame mark: two columns and a pitched rafter, the shape every plant starts from. */
export function Mark({ size = 30 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#F2B705" />
      <path d="M7 25V13.2L16 8l9 5.2V25" fill="none" stroke="#17222C" strokeWidth="3" strokeLinejoin="round" />
      <path d="M12 25v-7h8v7" fill="none" stroke="#17222C" strokeWidth="2.4" strokeLinejoin="round" />
    </svg>
  );
}

export function PlantIcon({ type, size = 16 }: { type: string; size?: number }) {
  const s = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinejoin: "round" as const, strokeLinecap: "round" as const, "aria-hidden": true };
  if (type === "retail")
    return (
      <svg {...s}><path d="M4 10v10h16V10" /><path d="M3 10l2-5h14l2 5z" /><path d="M10 20v-5h4v5" /></svg>
    );
  if (type === "egg_station")
    return (
      <svg {...s}><path d="M12 3c3.5 0 6 5 6 9a6 6 0 0 1-12 0c0-4 2.5-9 6-9z" /><path d="M9 13.5h6" /></svg>
    );
  return (
    <svg {...s}><path d="M3 20V10l6 3V10l6 3V7l6 3v10z" /><path d="M7 20v-3h3v3M14 20v-3h3v3" /></svg>
  );
}
