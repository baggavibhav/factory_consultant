# Changelog

## 1.2.1 — 01 Oct 2026
### Added
- Hosting: `Dockerfile` (builds the LibreDWG converter on Linux), `.dockerignore`, Render
  Blueprint (`render.yaml`) and `docs/deploy.md` (private GitHub repo → Render).
- Demo mode (`FCA_DEMO=1`): banner, and three sample projects created and built when the
  projects folder is empty (so a free Render instance never shows an empty app).
- Optional shared password for the whole site (`FCA_DEMO_PASSWORD`, off when unset).
- Search engines are told not to index the site (`X-Robots-Tag`, `robots.txt`).
### Changed
- Official rebar rate links to the specific GASTAT price series instead of the homepage.

## 1.2.0 — 30 Sep 2026
### Added
- Supplier directory with 18 prospect suppliers from public sources (steel, panels, cold rooms,
  refrigeration, fire protection, electrical, MEP), status and vetting checklist.
- Procurement packages from the priced BOQ; RFQ Excel per package (prices, compliance,
  commercial terms, hidden line ids); quote upload and validation; comparison with
  normalisation, best-value scoring, flags and a recommendation with reasons; accept a quote
  to update the rate library ("quoted" confidence) and re-price the project.
- Supplier quotes shown in the cost source mix and the Cost library.
### Changed
- The web page shell is served with no-cache, so updates load without a hard refresh.
- The v1.1 agent layer follows this release (needs the LLM key).

## 1.0.0 — 30 Sep 2026
### Added
- Saudi rate library (95 rates) with source, date and confidence per rate; supply-to-installed
  conversion factors; capacity-scaled rates (transformers, generators, tanks).
- Cost estimate on every build: likely, low and high totals; preliminaries, overhead and profit,
  contingency, escalation to the construction midpoint, VAT; cost per m² and sq ft; cost by trade;
  share of cost by source confidence; benchmark check against a published food-plant range.
- Priced Excel BOQ: rates pre-filled (still editable) with a Rate source column; Summary with
  editable on-cost percentages and VAT; totals reconcile with the app.
- Cost view with editable assumptions and instant recalculation; Cost library page to review and
  edit rates (with a note of the new source), reset edits; estimated cost in Overview and in
  "What changed" comparisons (variants show cost differences).
- Countries without a library are not priced in the wrong currency.
### Fixed
- Excavation was matched to the concrete rate (longest-match rule); now pinned by tests.

## 0.9.0 — 28 Sep 2026
### Added
- Detailed MEP geometry: round pipes and conduits, joints at bends and tees, couplings, hangers
  with clamps to the roof steel, valves with handwheels at branch take-offs, ladder cable trays
  with rungs, supports and cables, flanged ducts, shaped devices (sprinkler heads, detectors,
  high-bays, extinguishers, heaters, WCs).
- Every device placed and counted: light switches, junction boxes, local isolators at machines,
  exit signs, manual call points, extinguishers, hose reels, alarm sounders; sanitary fixtures by
  type (WCs, basins, showers, hand-wash stations, ablution taps, sinks, lab sinks).
- Door openings in concept walls (rooms to corridor, hygiene stations into production, between
  hall zones, cold rooms, entrance, exits and docks).
- Walkthrough mode with collisions and wall sliding, mini-map, current room, keyboard/mouse/touch
  controls; WebXR VR with thumbstick movement when a headset is available.
- White model display toggle.

## 0.8.1 — 25 Sep 2026
### Added
- Sample production equipment per line (not a process design, not in the BOQ): bakery lines
  with mixer, divider-rounder, proofers, moulder, tunnel oven, spiral cooler, slicer, metal
  detector, bagger and case packer; egg grading lines for egg stations; conveyors between
  machines; future lines shown as ghost outlines.
- Connections to the machines: power drops from each line panel, process water to mixers and
  proofers, compressed air to packaging and grading machines, gas to ovens, oven extract hoods
  with ducts and roof fans; measured into the BOQ as connections.
- "Production equipment (sample)" layer in 3D and "Machines (sample)" on the plan.

## 0.8.0 — 25 Sep 2026
### Added
- Design checks engine (site, fire, hygiene, layout, structure, services) for concept and
  drawing projects; Checks tab with severity summary, suggestions, Show on plan, and fixes.
- Variants for concept projects: build a fix or a custom change as a separate version, compare
  it with the current design (3D with linked cameras, or plan), accept or discard.
- Plan diff with highlighted additions, removals and resizes; building shifts reported once.
- Compare view lists what changed and which issues the variant resolves or introduces.
### Fixed (found by the new checks)
- Small wet rooms received no floor gullies or outlets.
- Offices in long buildings were too far from an exit (street-side exits added).
- Hygiene stations now sit where staff enter production.
- Yard warnings use the truck sizes of each plant type.
### Changed
- Activity moved to the Overview tab; Checks tab added.

## 0.7.0 — 25 Sep 2026
### Added
- Detailed service routing: lighting circuits per row of luminaires, socket outlets and
  socket circuits per room, process power from the main LV board to each production line,
  fire alarm panel and loop through every detector, point-of-use water heaters and hot water
  runs, cold water through every outlet, sprinkler feed main, cross mains and range pipes to
  every head, production air handling units with supply ducts and diffusers, toilet and
  changing extract, ducted office AC, compressed-air drops and gas branches with valve trains.
- BOQ items measured from these runs (cables, pipes, duct area, sockets, diffusers, units).
- Plan view: per-service list of run types with counts and lengths; click to isolate one type.
- `.gitattributes` to normalise line endings (removes the LF/CRLF warnings).
### Changed
- All chained runs are orthogonal (no diagonal pipes or cables).
- Ducts drawn at real width in 3D.
- Sprinkler pipework is now measured instead of an allowance per head.

## 0.6.0 — 24 Sep 2026
### Added
- Design options in the brief (structure option, span, bay, roof pitch, goods-in yard, dispatch
  apron, zone sizes, women in production, flour silos) and a "What changed" comparison after
  every rebuild.
- 2D plan view: rooms, walls, columns, openings and MEP services with legend, solo mode,
  tooltips (size, length, underground), zoom and pan.
- Room outlines read from DWG drawings (door-gap closing, polygonisation, estimated open-plan
  zones); Rooms tab; per-room finishes and fittings in the BOQ for drawing projects.
- Gulf amenity program for concepts: separate male/female changing, hygiene stations, prayer
  and ablution, dining, first aid, QA and sample test, server room, LT panel, compressor and
  CO2 rooms, laid out in two rows with a corridor.
- Design review fixes: goods-in yard (20 m) and dispatch apron (35 m) with docks and levellers,
  fire exits, main entrance, flour silos; haunched rafters; 5° default pitch; sections sized by
  span and purlins by bay; intermediate bracing about every 45 m; optional internal column
  line; ground beams and 1.2 m hygienic plinth wall; mezzanine steel; cold-room ceiling hangers.
- Room-type rules for water outlets and floor drains; no drains in electrical rooms.
### Changed
- MEP routes drawn thicker in 3D; new Doors, docks and exits layer.
- Brief form fields align regardless of hint text.

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
