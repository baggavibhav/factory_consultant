# Factory Consultant Agent

Switz Group agent that turns a plant brief and drawings into a 3D plant model,
BOM/BOQ, an inflation-adjusted cost estimate, and a contractor recommendation.

**Current stage (v0.7.0):** detailed service routing to every fitting, plus web app; plants from a drawing or a brief; editable design options with change comparison; 2D plan view of rooms and services; rooms read from DWG drawings; MEP concept layers; quantities, BOQ (Excel) and BOM.

- Ingestion: convert AutoCAD DWG to DXF (with automatic repair), extract walls,
  cold-room panels, openings and room labels.
- Structure: read the column grid, align it to the floor plan, and generate the
  steel portal frame: columns, rafters, eave beams, purlins, girts, bracing and
  foundation pads, with a member schedule. Layout follows the drawings; member
  sizes are indicative until structural drawings are loaded.
- Start from a brief (no drawing): enter the built-up area (m² or sq ft) and
  whatever else is known; get a space program, a concept layout in process-flow
  order, the steel structure and the 3D model. Every default used is listed.
- Edit and compare (concept projects): structure option (clear span or internal column
  line), span, bay spacing, roof pitch, yard depths, zone sizes, staff mix. Every rebuild
  shows what changed in size, steel, concrete, cladding and services.
- Plan view: rooms, walls, columns, doors, docks and each MEP service on a 2D plan, with
  one-service-at-a-time mode, lengths and sizes on hover, zoom and pan.
- Rooms from drawings: room outlines and names are read from the DWG (door gaps closed;
  open-plan zones estimated), giving finishes and fittings per room.
- Detailed routing (concept projects): lighting circuits along every row of luminaires,
  socket circuits, process power to each line, fire alarm loop, cold and hot water to every
  outlet, sprinkler pipework to every head, supply/extract/AC ductwork, air drops and gas
  branches. All runs are orthogonal and measured into the BOQ. In the plan view, pick a
  service, then a run type (e.g. lighting circuits) to see only those runs.
- MEP (concept projects): electrical, water, drainage, fire, refrigeration and
  ventilation, compressed air and gas, laid out by rule and shown as 3D layers.
- Quantities: every build measures a BOQ (13 trade sections, with specification and
  basis per item) and a bill of materials, downloadable as a tender-style Excel file
  with rate cells, live totals and contingency.
- Web app: create projects, upload drawings, build and explore the 3D model with
  layers, camera views and the member schedule, in light or dark mode.
- 3D: export a glTF model (`.glb`, opens in Windows 3D Viewer, Blender, etc.) and
  a single-file HTML viewer that works offline.

## Setup on Windows (one time)

1. Install the tools (PowerShell):

   ```powershell
   winget install -e --id Python.Python.3.12
   winget install -e --id Git.Git
   winget install -e --id Microsoft.VisualStudioCode
   ```

   Close and reopen PowerShell afterwards so the new commands are found.

2. Put this project folder somewhere simple, for example
   `C:\Projects\factory-consultant-agent`, and open it in VS Code
   (File > Open Folder). Accept "Install recommended extensions".

3. In the VS Code terminal (Terminal > New Terminal), run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   ```

   This creates the virtual environment in `.venv`, installs the project,
   downloads the LibreDWG converter into `tools\libredwg`, and runs the tests.

4. Select the interpreter: Ctrl+Shift+P > "Python: Select Interpreter" >
   `.venv\Scripts\python.exe`. New terminals then activate it automatically.

5. Start version control:

   ```powershell
   git init
   git add .
   git commit -m "Initial commit: ingestion tools v0.1.0"
   ```

## Start the web app

```powershell
fca serve
```

Then open http://127.0.0.1:8000 in your browser. Projects (drawings and models)
are stored in the `projects` folder, which stays out of git. Stop with Ctrl+C.

## Frontend development (only when changing the web app)

The built web app ships inside the Python package (`src/fca/web`), so running it
needs no Node.js. To change it, install Node.js 20 or newer
(`winget install -e --id OpenJS.NodeJS.LTS`), then in two terminals:

```powershell
fca serve --dev                 # terminal 1: API on port 8000
cd frontend; npm install; npm run dev   # terminal 2: http://localhost:5173 with live reload
```

When done, run `npm run build` in `frontend` to update `src/fca/web`, and commit both.

## Command-line tools

```powershell
# Convert a drawing
fca convert data\reference\Architectural_plans_as_built.dwg

# See which layers it uses (needed to write its config)
fca inspect data\reference\Architectural_plans_as_built.dxf

# Extract geometry using the plant's layer mapping
fca extract data\reference\Architectural_plans_as_built.dxf -c config\plants\ref-plant-01.toml -o outputs\ref-plant-01.geometry.json

# List level annotations in a sections drawing (to fill [levels] in the config)
fca levels data\reference\A-201_SECTIONS.dxf

# Build the 3D model, structure and viewer
fca build-3d data\reference\Architectural_plans_as_built.dxf -c config\plants\ref-plant-01.toml -o outputs
# then double-click outputs\ref-plant-01.viewer.html

# Quality checks
pytest
ruff check .
ruff format .
```

For a new drawing: copy `config/plants/_template.toml`, run `fca inspect`, and
fill in which layers are walls, panels, doors, windows and room labels.

## Concept design templates

`config/templates/<plant type>.toml` hold the design rules for concept layouts:
zone proportions, building depth and bay spacing, setbacks, office and amenity
sizing. They are plain text so engineering can tune them to Switz standards;
changes take effect on the next build and are tracked in git.

## Material specifications

`config/specs/default.toml` defines the grade and product used for every BOQ
item (concrete, steel sections, panels, cables, pipes, equipment). Edit it to
match Switz standards; the next build uses the new specifications.

## Troubleshooting

- **`fca` is not recognized / `No module named ...`**: the virtual environment
  is not active. Run `.venv\Scripts\Activate.ps1` (the prompt then starts with
  `(.venv)`). If PowerShell says running scripts is disabled, run once:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **File not found**: check the file name. Avoid spaces in file names; use
  underscores. `fca extract` and `fca build-3d` need the `.dxf`, so run
  `fca convert` on the `.dwg` first.
- **Opening a `.dwg` in VS Code shows "unsupported text encoding"**: expected,
  it is a binary file. Close the tab.

## Project layout

```
config/plants/        layer mapping per drawing (TOML)
data/                 drawings and outputs, local only (git-ignored)
docs/                 architecture decisions (adr/) and work log
scripts/setup.ps1     one-time Windows setup
src/fca/ingestion/    DWG to DXF (+ repair), layer mapping, geometry extraction
src/fca/model/        data contracts (schema) and building settings (levels, roof, zones)
src/fca/structure/    column grid alignment and portal-frame generation
src/fca/model3d/      glTF model builder
src/fca/viewer/       offline HTML viewer (three.js, MIT, vendored)
src/fca/concept/      brief, space program, concept layout and MEP
src/fca/quantities/   quantity takeoff, BOM and Excel BOQ
config/specs/         material specification library (TOML)
config/templates/     design rules per plant type (TOML)
src/fca/pipeline.py   end-to-end build used by the CLI, API and (later) the agents
src/fca/api/          FastAPI app: projects, uploads, builds, model files
src/fca/web/          built web app (generated by `npm run build`, committed)
frontend/             React + TypeScript source of the web app
src/fca/cli.py        `fca` command
tests/                pytest suite; reference tests run when data/reference has the drawing
```

## Rules

- Drawings, costs and outputs stay in `data/` and `outputs/` and never go into git.
- API keys go in `.env` (copy `.env.example`), never in code.
- Every change: tests pass, `ruff check` is clean, the work log is updated.
