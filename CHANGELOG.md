# Changelog

## 0.5.0 — 24 Sep 2026
### Added
- Concept MEP: electrical (supply, substation, generator, LV board, distribution boards, trays,
  feeders, lighting by lux), water (tank, pumps, mains, outlets), drainage (gullies, branches,
  collectors, chambers, grease trap, sewer), fire (tank, pumps, hydrant ring, hydrants,
  sprinklers, detectors), refrigeration and ventilation, compressed air, gas. 3D layers and a
  Services view.
- Quantity takeoff for concept and drawing projects: substructure, steel (tonnage by member),
  envelope, partitions, cold rooms, mezzanine, finishes, external works, MEP.
- Material specification library `config/specs/default.toml`.
- BOQ and BOM in the web app (search, by-trade and by-material views) and as Excel: Summary with
  section totals and contingency, BOQ with rate cells and formulas, BOM with waste allowance,
  Design basis and assumptions.
### Fixed
- Cold-room outlines no longer counted twice (as partitions and as cold-room panels).
- Builds from older versions offer a rebuild instead of a broken BOQ download.

## 0.4.0 — 24 Sep 2026
### Added
- Start from a brief: new projects choose "From a brief" or "From a drawing".
- Brief form (area in m² or sq ft, plot, production, cold chain, people, building); blanks use
  stated defaults, listed back as assumptions.
- Concept generator: space program from editable templates (industrial, retail, egg station),
  building sized to area and plot (reduced with a warning if it doesn't fit), zones in
  process-flow order, walls, cold-room panels, plot boundary, regular column grid, portal-frame
  structure, coloured floor zones in 3D.
- Program tab (zones, areas, sizes, assumptions, checks), Edit brief, Floor zones layer.
### Fixed
- Layer switches were hard to read in dark mode.

## 0.3.0 — 24 Sep 2026
### Added
- Web app (`fca serve`, http://127.0.0.1:8000): projects list with search and type filter,
  new-project form, project workspace with progress steps, drawing upload (DWG/DXF, auto
  conversion), one-click 3D build, 3D viewer (3D/Structure/Plan/Street/Inside views, layer
  toggles, x-ray walls, room names), overview metrics, member schedule, files, activity log,
  downloadable offline viewer, light/dark/system theme, responsive layout.
- FastAPI backend under `/api` with OpenAPI docs at `/docs`.
- File-based project store (`projects/`).
### Changed
- Build pipeline also writes room labels as JSON for the web viewer.
### New dependencies
- fastapi, uvicorn, python-multipart; dev: httpx. Frontend: React, three.js, lucide-react.

## 0.2.0 — 24 Sep 2026
### Added
- `fca build-3d`: plan DXF + plant config -> `.glb` 3D model, offline HTML viewer, structure report (JSON).
- Structural model: column grid read from the drawing and aligned to the floor plan; portal frames,
  gable columns, rafters, eave beams, purlins, girts, end-bay bracing, foundation pads; member schedule.
- `fca levels`: lists level annotations (e.g. +8.30M) in a sections drawing.
- DXF repair after conversion (LibreDWG can split text values across lines).
- Plant config sections: `[levels]`, `[roof]`, `[wall_heights]`, `[zones]`, `[structure]`, `[viewer]`.
### Changed
- Clearer errors when a DXF or config is missing; README troubleshooting.
- Reference tests accept the drawing name with spaces or underscores.
### New dependency
- trimesh (glTF export).

## 0.1.0 — 24 Sep 2026
- Repo skeleton, DWG to DXF conversion, layer inventory, geometry extraction, CLI, Windows setup.
