"""FastAPI application: projects, drawing upload, 3D builds, model files, web app."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fca import __version__
from fca.api.models import (
    BuildInfo,
    DrawingInfo,
    Meta,
    PlantType,
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectSummary,
    ProjectUpdate,
)
from fca.api.store import NotFound, ProjectStore, now, safe_filename
from fca.concept.brief import Brief, resolve
from fca.ingestion.convert import ConversionError, dwg_to_dxf
from fca.settings import PROJECT_ROOT, find_dwg2dxf

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
ALLOWED = {".dwg", ".dxf"}
PLANT_TYPE_LABELS = {
    PlantType.INDUSTRIAL: "Industrial manufacturing",
    PlantType.RETAIL: "Retail manufacturing",
    PlantType.EGG_STATION: "Egg station",
}
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(
    data_dir: Path | None = None,
    config_dir: Path | None = None,
    web_dir: Path | None = WEB_DIR,
    dev_cors: bool = False,
) -> FastAPI:
    store = ProjectStore(data_dir or PROJECT_ROOT / "projects")
    configs = Path(config_dir or PROJECT_ROOT / "config" / "plants")
    app = FastAPI(title="Factory Consultant API", version=__version__)
    app.state.store = store

    if dev_cors:  # Vite dev server on :5173 during frontend development
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def get_project(project_id: str) -> Project:
        try:
            return store.get(project_id)
        except NotFound:
            raise HTTPException(404, "Project not found") from None

    def config_names() -> list[str]:
        return sorted(p.stem for p in configs.glob("*.toml") if not p.stem.startswith("_"))

    # -- meta ---------------------------------------------------------------
    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/meta", response_model=Meta)
    def meta() -> Meta:
        return Meta(
            version=__version__,
            plant_types=[{"value": k.value, "label": v} for k, v in PLANT_TYPE_LABELS.items()],
            configs=config_names(),
            converter_available=find_dwg2dxf() is not None,
        )

    # -- projects -----------------------------------------------------------
    @app.get("/api/projects", response_model=list[ProjectSummary])
    def list_projects() -> list[ProjectSummary]:
        return store.list()

    @app.post("/api/projects", response_model=Project, status_code=201)
    def create_project(body: ProjectCreate) -> Project:
        if body.mode == "drawing" and body.config not in config_names():
            raise HTTPException(422, f"Unknown plant config '{body.config}'")
        return store.create(body)

    @app.get("/api/projects/{project_id}", response_model=Project)
    def read_project(project_id: str) -> Project:
        return get_project(project_id)

    @app.patch("/api/projects/{project_id}", response_model=Project)
    def update_project(project_id: str, body: ProjectUpdate) -> Project:
        project = get_project(project_id)
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(project, key, value)
        return store.save(project, ("updated", "Project details updated"))

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: str) -> None:
        get_project(project_id)
        store.delete(project_id)

    # -- brief --------------------------------------------------------------
    @app.get("/api/brief-defaults/{plant_type}")
    def brief_defaults(plant_type: PlantType) -> dict:
        values, _ = resolve(Brief(plant_type=plant_type.value, built_up_area_m2=1000))
        values.pop("built_up_area_m2")
        return values

    @app.put("/api/projects/{project_id}/brief", response_model=Project)
    def save_brief(project_id: str, body: Brief) -> Project:
        project = get_project(project_id)
        if project.mode != "brief":
            raise HTTPException(409, "This project starts from a drawing, not a brief")
        if body.plant_type != project.plant_type.value:
            raise HTTPException(422, "The brief's plant type must match the project")
        project.brief = body
        project.status = ProjectStatus.BRIEF_READY
        return store.save(project, ("brief", f"Brief saved: {body.built_up_area_m2:,.0f} m²"))

    # -- drawing ------------------------------------------------------------
    @app.post("/api/projects/{project_id}/drawing", response_model=Project)
    async def upload_drawing(project_id: str, file: UploadFile) -> Project:
        project = get_project(project_id)
        if project.mode != "drawing":
            raise HTTPException(409, "This project starts from a brief; drawings aren't used")
        name = safe_filename(file.filename or "drawing")
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED:
            raise HTTPException(422, "Upload an AutoCAD .dwg or .dxf file")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File is larger than 200 MB")
        if not data:
            raise HTTPException(422, "The uploaded file is empty")

        uploads = store.uploads(project_id)
        for old in uploads.iterdir():
            old.unlink()
        path = uploads / name
        path.write_bytes(data)

        dxf_name = name if ext == ".dxf" else None
        if ext == ".dwg":
            try:
                dxf = await run_in_threadpool(dwg_to_dxf, path)
                dxf_name = dxf.name
            except ConversionError as exc:
                project.status = ProjectStatus.FAILED
                store.save(project, ("error", f"Conversion failed: {exc}"))
                raise HTTPException(422, f"Could not convert the drawing: {exc}") from exc

        project.drawing = DrawingInfo(
            filename=name,
            kind=ext.lstrip("."),
            size_bytes=len(data),
            uploaded_at=now(),
            dxf_filename=dxf_name,
        )
        project.status = ProjectStatus.DRAWING_READY
        project.latest_build = None
        msg = f"Drawing uploaded: {name}" + (" (converted to DXF)" if ext == ".dwg" else "")
        return store.save(project, ("drawing", msg))

    # -- builds -------------------------------------------------------------
    @app.post("/api/projects/{project_id}/builds", response_model=Project)
    async def build(project_id: str) -> Project:
        from fca.pipeline import build_3d, build_concept  # heavy imports only when building

        project = get_project(project_id)
        out = store.outputs(project_id)
        if project.mode == "brief":
            if not project.brief:
                raise HTTPException(409, "Fill in the brief before building the model")
            job, args = build_concept, (project.brief, out, "model")
        else:
            if not project.drawing or not project.drawing.dxf_filename:
                raise HTTPException(409, "Upload a drawing before building the model")
            dxf = store.uploads(project_id) / project.drawing.dxf_filename
            job, args = build_3d, (dxf, configs / f"{project.config}.toml", out, "model")
        started, t0 = now(), time.perf_counter()
        try:
            result = await run_in_threadpool(job, *args)
        except Exception as exc:  # report any pipeline error to the user
            log.exception("Build failed for %s", project_id)
            project.status = ProjectStatus.FAILED
            store.save(project, ("error", f"Build failed: {exc}"))
            raise HTTPException(422, f"Build failed: {exc}") from exc
        project.latest_build = BuildInfo(
            id=uuid.uuid4().hex[:8],
            started_at=started,
            finished_at=now(),
            duration_s=round(time.perf_counter() - t0, 1),
            facts=result.facts,
            warnings=result.warnings,
        )
        project.builds += 1
        project.status = ProjectStatus.MODEL_READY
        frames = result.facts.get("frames", 0)
        kind = "Concept model" if project.mode == "brief" else "3D model"
        return store.save(project, ("build", f"{kind} built: {frames} frames"))

    def output_file(project_id: str, name: str, media: str) -> FileResponse:
        get_project(project_id)
        path = store.outputs(project_id) / name
        if not path.is_file():
            raise HTTPException(404, "Build the model first")
        return FileResponse(path, media_type=media, headers={"Cache-Control": "no-store"})

    @app.get("/api/projects/{project_id}/model.glb")
    def model_glb(project_id: str) -> FileResponse:
        return output_file(project_id, "model.glb", "model/gltf-binary")

    @app.get("/api/projects/{project_id}/labels")
    def model_labels(project_id: str) -> FileResponse:
        return output_file(project_id, "model.labels.json", "application/json")

    @app.get("/api/projects/{project_id}/viewer.html")
    def standalone_viewer(project_id: str) -> FileResponse:
        resp = output_file(project_id, "model.viewer.html", "text/html")
        project = get_project(project_id)
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="{safe_filename(project.name)}_3d_viewer.html"'
        )
        return resp

    @app.exception_handler(NotFound)
    async def not_found(_request, _exc) -> JSONResponse:
        return JSONResponse({"detail": "Project not found"}, status_code=404)

    # -- web app ------------------------------------------------------------
    if web_dir and (web_dir / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = web_dir / path
            if path and candidate.is_file() and web_dir in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(web_dir / "index.html")

    return app
