import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { BookOpen, Building2, Calculator, FolderKanban, Monitor, Moon, Sun } from "lucide-react";
import { Mark } from "./Brand";
import { api } from "../lib/api";

type Theme = "system" | "light" | "dark";

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem("fca-theme") as Theme) || "system"; } catch { return "system"; }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try { localStorage.setItem("fca-theme", theme); } catch { /* storage unavailable */ }
  }, [theme]);
  return [theme, setTheme];
}

export default function Shell({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useTheme();
  const [server, setServer] = useState<{ ok: boolean; version?: string; demo?: boolean }>({ ok: false });

  useEffect(() => {
    let alive = true;
    const check = () => api.meta().then((m) => alive && setServer({ ok: true, version: m.version, demo: m.demo })).catch(() => alive && setServer({ ok: false }));
    check();
    const t = setInterval(check, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Main">
        <NavLink to="/" className="brand">
          <Mark />
          <span>
            <span className="brand-name">Factory Consultant</span>
            <br />
            <span className="brand-org">Switz Group plants</span>
          </span>
        </NavLink>
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          <FolderKanban size={17} /> Projects
        </NavLink>
        <NavLink to="/cost-library" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          <Calculator size={17} /> Cost library
        </NavLink>
        <NavLink to="/suppliers" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
          <Building2 size={17} /> Suppliers
        </NavLink>
        <div className="nav-section">Coming next</div>
        <span className="nav-link disabled" aria-disabled="true"><BookOpen size={17} /> Agent assistant <span className="soon">v1.1</span></span>
        <div className="rail-foot">
          <div className="theme-toggle" role="group" aria-label="Colour theme">
            <button aria-pressed={theme === "light"} onClick={() => setTheme("light")} title="Light"><Sun size={14} /><span className="sr-only">Light</span></button>
            <button aria-pressed={theme === "system"} onClick={() => setTheme("system")} title="Match system"><Monitor size={14} /><span className="sr-only">Match system</span></button>
            <button aria-pressed={theme === "dark"} onClick={() => setTheme("dark")} title="Dark"><Moon size={14} /><span className="sr-only">Dark</span></button>
          </div>
          <div className="conn">
            <span className={`dot ${server.ok ? "ok" : "bad"}`} />
            {server.ok ? `Server connected, v${server.version}` : "Server not reachable"}
          </div>
        </div>
      </nav>
      <main className="main">
        {server.demo && (
          <div className="demo-banner" role="note">Public demo with sample projects. Please don't enter confidential data; projects may reset when the demo restarts.</div>
        )}{children}</main>
    </div>
  );
}
