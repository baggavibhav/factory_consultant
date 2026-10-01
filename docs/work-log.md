# Work log

Times are Dubai time (GST, UTC+4). The full log lives in the Claude project
document "Factory Consultant Agent - Project Log"; this file mirrors code-related entries.

| Date | Time | Change |
| --- | --- | --- |
| 24 Sep 2026 | 13:03 | v0.1.0: repo skeleton, DWG to DXF conversion, layer inventory, geometry extraction, CLI, 19 tests (15 unit, 4 reference), Windows setup script, VS Code settings, ADR 0001 and 0002 |
| 24 Sep 2026 | 14:22 | v0.1.0 verified on Windows (19/19 tests) |
| 24 Sep 2026 | 14:40 | v0.2.0: DXF repair (sections file now opens), `fca levels`, column grid extraction and plan alignment, portal-frame structure generator with member schedule, glTF 3D export, offline HTML viewer, `fca build-3d`, clearer file-not-found errors, README troubleshooting, ADR 0003; 35 tests |
| 24 Sep 2026 | 15:22 | v0.3.0: FastAPI backend (projects, drawing upload with conversion, builds, model/labels/viewer downloads), React web app (projects list, new-project drawer, workspace with progress steps, 3D viewer with views/layers/x-ray/room names, overview, structure schedule, files, activity), light/dark/system theme, `fca serve`; 42 Python tests; end-to-end UI test with the reference drawing |
| 24 Sep 2026 | 15:50 | v0.4.0: start from a brief (brief form, templates, space program, concept layout, structure and 3D), Program tab, dark-mode switch fix, ADR 0005; 56 tests; browser-tested |
| 24 Sep 2026 | 16:12 | v0.5.0: concept MEP (7 services, 3D layers, Services view), quantity takeoff for concept and drawing projects, specification library, BOQ and BOM in the app and as Excel (formulas verified: 166 formulas, 0 errors, test rates reconcile), ADR 0006; 65 tests; browser-tested |
| 24 Sep 2026 | 17:01 | v0.6.0: design options and what-changed comparison, 2D plan view with services, rooms from DWG, Gulf amenity program, design review fixes (yards, docks, exits, haunches, sizing by span/bay, bracing, ground beams, plinth, mezzanine steel); ADR 0007; 76 tests; browser-tested |
| 25 Sep 2026 | 10:18 | v0.7.0: detailed service routing to every fitting, measured into the BOQ; plan view run types with isolate; orthogonal runs enforced by test; .gitattributes; ADR 0008; 83 tests; browser-tested |
| 25 Sep 2026 | 11:14 | v0.8.0: design checks (both project types) and variants with before/after compare (3D linked cameras, plan diff), accept/discard; generator fixes found by the checks; ADR 0009; 92 tests; browser-tested |
| 25 Sep 2026 | 11:25 | v0.8.1: sample production equipment per line with conveyors, future lines as ghosts, and service connections to machines (power, water, air, gas, oven extract); 93 tests; browser-tested |
| 28 Sep 2026 | 13:33 | v0.9.0: detailed MEP geometry (fittings, supports, valves, trays with cables, devices, sanitary fixtures by type), all devices counted, door openings, walkthrough with mini-map and VR; ADR 0010; 94 tests; browser-tested |
| 30 Sep 2026 | 14:56 | v1.0.0: cost estimate from a cited Saudi rate library (95 rates: 1 official, 14 published, 80 allowances), range, on-costs, escalation, VAT, benchmark check, priced Excel reconciling with the app, Cost view, editable Cost library; ADR 0011; 109 tests; browser-tested |
| 30 Sep 2026 | 15:55 | v1.2.0: supplier directory (18 prospects from public sources, vetting), procurement packages, RFQ Excel, quote import, normalised comparison and best-value recommendation, accept updates rate library and re-prices; no-cache page shell; ADR 0012; 115 tests; browser-tested |
| 01 Oct 2026 | 18:49 | v1.2.1: hosting for a public demo (Dockerfile with LibreDWG, Render Blueprint, deploy guide), demo mode with sample projects and banner, optional password, no-index; container start verified without Docker (converter install and demo server); 117 tests |
