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
    CostSettings,
    DrawingInfo,
    Meta,
    PlantType,
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectSummary,
    ProjectUpdate,
    RateEdit,
    Variant,
    VariantCreate,
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


CHANGE_FIELDS = [
    ("Footprint", lambda f: f.get("footprint_m2"), "m²"),
    ("Building length", lambda f: f["building_m"][0], "m"),
    ("Building depth", lambda f: f["building_m"][1], "m"),
    ("Portal frames", lambda f: f.get("frames"), ""),
    ("Structural steel", lambda f: (f.get("quantities") or {}).get("steel_t"), "t"),
    ("Concrete", lambda f: (f.get("quantities") or {}).get("concrete_m3"), "m³"),
    ("Roof panels", lambda f: (f.get("quantities") or {}).get("roof_m2"), "m²"),
    ("Wall cladding", lambda f: (f.get("quantities") or {}).get("wall_m2"), "m²"),
    (
        "Transformer",
        lambda f: ((f.get("mep") or {}).get("electrical") or {}).get("transformer_kva"),
        "kVA",
    ),
    ("Fire water tank", lambda f: ((f.get("mep") or {}).get("fire") or {}).get("tank_m3"), "m³"),
    ("Estimated cost incl. VAT", lambda f: (f.get("cost") or {}).get("total"), "SAR"),
]


def compare_builds(before: dict, after: dict) -> list[dict]:
    """Key figures that changed between two builds (for 'what changed' after an edit)."""
    out = []
    for label, get, unit in CHANGE_FIELDS:
        try:
            a, b = get(before), get(after)
        except (KeyError, TypeError, IndexError):
            continue
        if a is None or b is None or abs(float(b) - float(a)) < 0.05:
            continue
        pct = (float(b) - float(a)) / float(a) * 100 if a else None
        out.append(
            {
                "label": label,
                "before": a,
                "after": b,
                "unit": unit,
                "change_pct": round(pct, 1) if pct is not None else None,
            }
        )
    return out


def create_app(
    data_dir: Path | None = None,
    config_dir: Path | None = None,
    web_dir: Path | None = WEB_DIR,
    dev_cors: bool = False,
    demo: bool | None = None,
) -> FastAPI:
    """Build the app. ``demo`` (or env FCA_DEMO=1) marks a public demo: a banner is shown and
    sample projects are created when the projects folder is empty. Env FCA_DEMO_PASSWORD
    optionally protects the whole site with a shared password (off when unset)."""
    import os

    demo = demo if demo is not None else os.environ.get("FCA_DEMO") == "1"
    demo_password = os.environ.get("FCA_DEMO_PASSWORD", "")
    store = ProjectStore(data_dir or PROJECT_ROOT / "projects")
    overrides_path = store.root / "_rate_overrides.json"
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

    @app.middleware("http")
    async def public_safety(request, call_next):
        if demo_password and request.url.path != "/api/health":
            import base64
            import secrets

            from fastapi.responses import Response

            auth = request.headers.get("authorization", "")
            ok = False
            if auth.lower().startswith("basic "):
                try:
                    _, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
                    ok = secrets.compare_digest(pw, demo_password)
                except Exception:
                    ok = False
            if not ok:
                return Response(
                    "Password required",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Factory Consultant demo"'},
                )
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = (
            "noindex, nofollow"  # keep the demo out of search engines
        )
        return response

    @app.get("/robots.txt", include_in_schema=False)
    def robots():
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse("User-agent: *\nDisallow: /\n")

    @app.get("/api/meta", response_model=Meta)
    def meta() -> Meta:
        return Meta(
            version=__version__,
            plant_types=[{"value": k.value, "label": v} for k, v in PLANT_TYPE_LABELS.items()],
            configs=config_names(),
            converter_available=find_dwg2dxf() is not None,
            demo=demo,
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
        from fca.concept.program import hall_zone_names, load_template

        values, _ = resolve(Brief(plant_type=plant_type.value, built_up_area_m2=1000))
        values.pop("built_up_area_m2")
        tpl = load_template(plant_type.value)
        values |= {
            "hall_zones": hall_zone_names(tpl),
            "span_m": tpl.building["target_depth_m"],
            "bay_m": tpl.building["bay_m"],
            "roof_pitch_deg": tpl.building["roof_pitch_deg"],
            "goods_in_yard_m": tpl.site["setback_west_m"],
            "dispatch_yard_m": tpl.site["setback_east_m"],
        }
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
        info = {
            "name": project.name,
            "country": project.country,
            "city": project.city,
            "plant_type_label": PLANT_TYPE_LABELS[project.plant_type],
            "cost_settings": project.cost_settings,
            "rate_overrides": str(overrides_path),
        }
        if project.mode == "brief":
            if not project.brief:
                raise HTTPException(409, "Fill in the brief before building the model")
            job, args = build_concept, (project.brief, out, "model", info)
        else:
            if not project.drawing or not project.drawing.dxf_filename:
                raise HTTPException(409, "Upload a drawing before building the model")
            dxf = store.uploads(project_id) / project.drawing.dxf_filename
            job, args = build_3d, (dxf, configs / f"{project.config}.toml", out, "model", info)
        started, t0 = now(), time.perf_counter()
        try:
            result = await run_in_threadpool(job, *args)
        except Exception as exc:  # report any pipeline error to the user
            log.exception("Build failed for %s", project_id)
            project.status = ProjectStatus.FAILED
            store.save(project, ("error", f"Build failed: {exc}"))
            raise HTTPException(422, f"Build failed: {exc}") from exc
        previous = project.latest_build.facts if project.latest_build else None
        project.latest_build = BuildInfo(
            id=uuid.uuid4().hex[:8],
            started_at=started,
            finished_at=now(),
            duration_s=round(time.perf_counter() - t0, 1),
            facts=result.facts,
            warnings=result.warnings,
            changes=compare_builds(previous, result.facts) if previous else [],
        )
        project.builds += 1
        project.status = ProjectStatus.MODEL_READY
        if project.variants:  # variants compare against the old design; clear them
            import shutil

            shutil.rmtree(store.outputs(project_id) / "variants", ignore_errors=True)
            project.variants = []
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

    @app.get("/api/projects/{project_id}/plan")
    def plan(project_id: str) -> FileResponse:
        return output_file(project_id, "model.plan.json", "application/json")

    @app.get("/api/projects/{project_id}/checks")
    def checks(project_id: str) -> FileResponse:
        return output_file(project_id, "model.checks.json", "application/json")

    # -- variants (concept projects) ---------------------------------------------
    def variant_dir(project_id: str, variant_id: str) -> Path:
        return store.outputs(project_id) / "variants" / variant_id

    def find_variant(project: Project, variant_id: str) -> Variant:
        v = next((v for v in project.variants if v.id == variant_id), None)
        if v is None:
            raise HTTPException(404, "Variant not found")
        return v

    @app.post("/api/projects/{project_id}/variants", response_model=Project, status_code=201)
    async def create_variant(project_id: str, body: VariantCreate) -> Project:
        import json as _json

        from fca.checks.diff import plan_diff
        from fca.pipeline import build_concept

        project = get_project(project_id)
        if project.mode != "brief" or not project.brief or not project.latest_build:
            raise HTTPException(409, "Variants need a built concept project")
        if body.brief is not None:
            brief = body.brief
        else:
            data = project.brief.model_dump()
            for key, value in body.changes.items():
                if key == "zone_sizes" and isinstance(value, dict):
                    data["zone_sizes"] = {**(data.get("zone_sizes") or {}), **value}
                else:
                    data[key] = value
            try:
                brief = Brief.model_validate(data)
            except ValueError as exc:
                raise HTTPException(422, f"Invalid change: {exc}") from exc
        vid = uuid.uuid4().hex[:8]
        out = variant_dir(project_id, vid)
        info = {
            "name": f"{project.name} – {body.name}",
            "country": project.country,
            "city": project.city,
            "plant_type_label": PLANT_TYPE_LABELS[project.plant_type],
        }
        started, t0 = now(), time.perf_counter()
        try:
            result = await run_in_threadpool(build_concept, brief, out, "model", info)
        except Exception as exc:
            raise HTTPException(422, f"Variant build failed: {exc}") from exc
        base_plan = _json.loads((store.outputs(project_id) / "model.plan.json").read_text())
        new_plan = _json.loads((out / "model.plan.json").read_text())
        (out / "model.diff.json").write_text(_json.dumps(plan_diff(base_plan, new_plan)))
        variant = Variant(
            id=vid,
            name=body.name,
            brief=brief,
            created_at=now(),
            source=body.source,
            build=BuildInfo(
                id=uuid.uuid4().hex[:8],
                started_at=started,
                finished_at=now(),
                duration_s=round(time.perf_counter() - t0, 1),
                facts=result.facts,
                warnings=result.warnings,
                changes=compare_builds(project.latest_build.facts, result.facts),
            ),
        )
        project.variants.append(variant)
        return store.save(project, ("variant", f"Variant built: {body.name}"))

    @app.get("/api/projects/{project_id}/variants/{variant_id}/{filename}")
    def variant_file(project_id: str, variant_id: str, filename: str) -> FileResponse:
        media = {
            "model.glb": "model/gltf-binary",
            "plan": "application/json",
            "diff": "application/json",
            "labels": "application/json",
            "checks": "application/json",
            "boq": "application/json",
        }
        files = {
            "model.glb": "model.glb",
            "plan": "model.plan.json",
            "diff": "model.diff.json",
            "labels": "model.labels.json",
            "checks": "model.checks.json",
            "boq": "model.boq.json",
        }
        project = get_project(project_id)
        find_variant(project, variant_id)
        if filename not in files:
            raise HTTPException(404, "Unknown file")
        path = variant_dir(project_id, variant_id) / files[filename]
        if not path.is_file():
            raise HTTPException(404, "Variant file missing")
        return FileResponse(path, media_type=media[filename], headers={"Cache-Control": "no-store"})

    @app.post("/api/projects/{project_id}/variants/{variant_id}/accept", response_model=Project)
    def accept_variant(project_id: str, variant_id: str) -> Project:
        import shutil

        project = get_project(project_id)
        v = find_variant(project, variant_id)
        out = store.outputs(project_id)
        src = variant_dir(project_id, variant_id)
        for f in src.iterdir():
            if f.name != "model.diff.json":
                shutil.copy2(f, out / f.name)
        project.brief = v.brief
        project.latest_build = v.build
        project.builds += 1
        shutil.rmtree(src, ignore_errors=True)
        project.variants = [x for x in project.variants if x.id != variant_id]
        return store.save(project, ("build", f"Variant accepted as the design: {v.name}"))

    @app.delete("/api/projects/{project_id}/variants/{variant_id}", response_model=Project)
    def delete_variant(project_id: str, variant_id: str) -> Project:
        import shutil

        project = get_project(project_id)
        v = find_variant(project, variant_id)
        shutil.rmtree(variant_dir(project_id, variant_id), ignore_errors=True)
        project.variants = [x for x in project.variants if x.id != variant_id]
        return store.save(project, ("variant", f"Variant discarded: {v.name}"))

    # -- cost -------------------------------------------------------------------------
    @app.get("/api/projects/{project_id}/cost")
    def cost(project_id: str) -> FileResponse:
        return output_file(project_id, "model.cost.json", "application/json")

    def recalc(project: Project) -> Project:
        from fca.cost.service import write_cost

        out = store.outputs(project.id)
        if not project.latest_build or not (out / "model.boq.json").is_file():
            raise HTTPException(409, "Build the model first")
        summary = write_cost(out, "model", project.cost_settings, overrides_path)
        project.latest_build.facts["cost"] = summary
        return store.save(project, ("cost", "Cost estimate recalculated"))

    @app.put("/api/projects/{project_id}/cost-settings", response_model=Project)
    def cost_settings(project_id: str, body: CostSettings) -> Project:
        project = get_project(project_id)
        project.cost_settings = body.model_dump(exclude_none=True)
        return recalc(project)

    @app.post("/api/projects/{project_id}/cost/recalculate", response_model=Project)
    def cost_recalculate(project_id: str) -> Project:
        return recalc(get_project(project_id))

    from fca.api.procurement import register as register_procurement

    register_procurement(app, store, get_project, overrides_path, recalc)

    @app.get("/api/rates")
    def rates(country: str = "Saudi Arabia") -> dict:
        from dataclasses import asdict

        from fca.cost.estimate import COUNTRY_LIBRARY, load_library

        if country not in COUNTRY_LIBRARY:
            raise HTTPException(404, f"No rate library for {country} yet")
        lib = load_library(country, overrides_path)
        return {
            "name": lib.name,
            "currency": lib.currency,
            "rate_date": lib.rate_date,
            "escalation_per_year": lib.escalation_per_year,
            "defaults": lib.defaults,
            "benchmarks": lib.benchmarks,
            "rates": [{**asdict(r), "installed": r.installed} for r in lib.rates],
        }

    @app.put("/api/rates/{key}")
    def edit_rate(key: str, body: RateEdit) -> dict:
        import json as _json

        from fca.cost.estimate import load_library

        lib = load_library("Saudi Arabia")
        if key not in {r.key for r in lib.rates}:
            raise HTTPException(404, "Unknown rate")
        edits = _json.loads(overrides_path.read_text()) if overrides_path.is_file() else {}
        change = body.model_dump(exclude_none=True)
        if "rate" in change:  # an edited installed rate replaces the supply-based calculation
            change["supply"] = None
        edits[key] = {**edits.get(key, {}), **change}
        overrides_path.write_text(_json.dumps(edits, indent=1))
        return {"key": key, "edited": edits[key]}

    @app.delete("/api/rates/{key}")
    def reset_rate(key: str) -> dict:
        import json as _json

        edits = _json.loads(overrides_path.read_text()) if overrides_path.is_file() else {}
        edits.pop(key, None)
        overrides_path.write_text(_json.dumps(edits, indent=1))
        return {"key": key, "reset": True}

    @app.get("/api/projects/{project_id}/boq")
    def boq(project_id: str) -> FileResponse:
        return output_file(project_id, "model.boq.json", "application/json")

    @app.get("/api/projects/{project_id}/boq.xlsx")
    def boq_xlsx(project_id: str) -> FileResponse:
        resp = output_file(
            project_id,
            "model.boq.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        project = get_project(project_id)
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="{safe_filename(project.name)}_BOQ.xlsx"'
        )
        return resp

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
            # Never cache the page shell, so a new version loads right after an update.
            return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-cache"})

    if demo:
        import asyncio
        import logging

        demo_log = logging.getLogger("fca.demo")
        samples = [
            (
                ProjectCreate(
                    name="Demo: Jeddah industrial bakery",
                    plant_type="industrial",
                    country="Saudi Arabia",
                    city="Jeddah",
                    mode="brief",
                    notes="Sample project for the demo.",
                ),
                {
                    "plant_type": "industrial",
                    "built_up_area_m2": 5017,
                    "plot_width_m": 150,
                    "plot_depth_m": 70,
                    "lines_now": 3,
                    "lines_future": 1,
                    "blast_freezer": True,
                    "staff_per_shift": 80,
                    "office_staff": 15,
                },
            ),
            (
                ProjectCreate(
                    name="Demo: Riyadh retail bakery",
                    plant_type="retail",
                    country="Saudi Arabia",
                    city="Riyadh",
                    mode="brief",
                    notes="Sample project for the demo.",
                ),
                {"plant_type": "retail", "built_up_area_m2": 1500, "staff_per_shift": 30},
            ),
            (
                ProjectCreate(
                    name="Demo: Dammam egg station",
                    plant_type="egg_station",
                    country="Saudi Arabia",
                    city="Dammam",
                    mode="brief",
                    notes="Sample project for the demo.",
                ),
                {
                    "plant_type": "egg_station",
                    "built_up_area_m2": 2500,
                    "cold_storage": True,
                    "staff_per_shift": 30,
                },
            ),
        ]

        async def seed() -> None:
            if store.list():
                return
            for create, brief in samples:
                try:
                    p = create_project(create)
                    save_brief(p.id, Brief(**brief))
                    await build(p.id)
                except Exception as exc:  # a failed sample must not stop the server
                    demo_log.warning("Demo project failed: %s", exc)

        @app.on_event("startup")
        async def _seed_demo() -> None:
            asyncio.get_running_loop().create_task(seed())

    return app
