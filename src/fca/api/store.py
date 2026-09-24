"""File-based project store: one folder per project with project.json, uploads and outputs.

Simple and transparent for a single-machine deployment; replaceable by a
database later without changing the API.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fca.api.models import Event, Project, ProjectCreate, ProjectSummary

_ID = re.compile(r"^[a-f0-9]{12}$")
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_EVENTS = 200


class NotFound(KeyError):
    pass


def now() -> datetime:
    return datetime.now(UTC)


def safe_filename(name: str) -> str:
    """Spaces become underscores; anything unusual is dropped (no paths)."""
    base = Path(name).name.strip().replace(" ", "_")
    cleaned = _SAFE.sub("", base).strip("._")
    return cleaned or "drawing"


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # -- paths --------------------------------------------------------------
    def dir(self, project_id: str) -> Path:
        if not _ID.match(project_id):
            raise NotFound(project_id)
        path = self.root / project_id
        if not (path / "project.json").is_file():
            raise NotFound(project_id)
        return path

    def uploads(self, project_id: str) -> Path:
        return self.dir(project_id) / "uploads"

    def outputs(self, project_id: str) -> Path:
        return self.dir(project_id) / "outputs"

    # -- CRUD ---------------------------------------------------------------
    def create(self, data: ProjectCreate) -> Project:
        with self._lock:
            pid = uuid.uuid4().hex[:12]
            ts = now()
            project = Project(id=pid, created_at=ts, updated_at=ts, **data.model_dump())
            path = self.root / pid
            (path / "uploads").mkdir(parents=True)
            (path / "outputs").mkdir()
            project.events.append(Event(at=ts, kind="created", message="Project created"))
            self._write(project)
            return project

    def get(self, project_id: str) -> Project:
        path = self.dir(project_id) / "project.json"
        return Project.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[ProjectSummary]:
        out = []
        for p in self.root.glob("*/project.json"):
            try:
                proj = Project.model_validate_json(p.read_text(encoding="utf-8"))
            except ValueError:
                continue  # skip unreadable folders rather than failing the list
            facts = proj.latest_build.facts if proj.latest_build else {}
            out.append(
                ProjectSummary(
                    id=proj.id,
                    mode=proj.mode,
                    name=proj.name,
                    plant_type=proj.plant_type,
                    country=proj.country,
                    city=proj.city,
                    status=proj.status,
                    updated_at=proj.updated_at,
                    footprint_m2=facts.get("footprint_m2"),
                    frames=facts.get("frames"),
                )
            )
        return sorted(out, key=lambda s: s.updated_at, reverse=True)

    def save(self, project: Project, event: tuple[str, str] | None = None) -> Project:
        with self._lock:
            project.updated_at = now()
            if event:
                project.events.append(Event(at=project.updated_at, kind=event[0], message=event[1]))
                project.events = project.events[-MAX_EVENTS:]
            self._write(project)
            return project

    def delete(self, project_id: str) -> None:
        with self._lock:
            shutil.rmtree(self.dir(project_id))

    def _write(self, project: Project) -> None:
        path = self.root / project.id / "project.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(project.model_dump(mode="json"), indent=2), encoding="utf-8")
        tmp.replace(path)
