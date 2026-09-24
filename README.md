# Factory Consultant Agent

Switz Group agent that turns a plant brief and drawings into a 3D plant model,
BOM/BOQ, an inflation-adjusted cost estimate, and a contractor recommendation.

**Current stage (v0.1.0):** ingestion tools. They convert AutoCAD DWG drawings
to DXF and extract walls, cold-room panels, openings and room labels into a
versioned JSON format that later tools (3D model, quantities, BOQ) build on.

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

## Everyday use

```powershell
# Convert a drawing
fca convert data\reference\Architectural_plans_as_built.dwg

# See which layers it uses (needed to write its config)
fca inspect data\reference\Architectural_plans_as_built.dxf

# Extract geometry using the plant's layer mapping
fca extract data\reference\Architectural_plans_as_built.dxf -c config\plants\ref-plant-01.toml -o outputs\ref-plant-01.geometry.json

# Quality checks
pytest
ruff check .
ruff format .
```

For a new drawing: copy `config/plants/_template.toml`, run `fca inspect`, and
fill in which layers are walls, panels, doors, windows and room labels.

## Project layout

```
config/plants/        layer mapping per drawing (TOML)
data/                 drawings and outputs, local only (git-ignored)
docs/                 architecture decisions (adr/) and work log
scripts/setup.ps1     one-time Windows setup
src/fca/ingestion/    DWG to DXF, layer mapping, geometry extraction
src/fca/model/        data contracts (Pydantic schema)
src/fca/cli.py        `fca` command
tests/                pytest suite; reference tests run when data/reference has the drawing
```

## Rules

- Drawings, costs and outputs stay in `data/` and `outputs/` and never go into git.
- API keys go in `.env` (copy `.env.example`), never in code.
- Every change: tests pass, `ruff check` is clean, the work log is updated.
