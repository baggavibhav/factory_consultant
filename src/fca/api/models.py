"""API data models (request and response bodies, and what is stored on disk)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from fca.concept.brief import Brief


class PlantType(StrEnum):
    INDUSTRIAL = "industrial"
    RETAIL = "retail"
    EGG_STATION = "egg_station"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    DRAWING_READY = "drawing_ready"
    BRIEF_READY = "brief_ready"
    MODEL_READY = "model_ready"
    FAILED = "failed"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    plant_type: PlantType
    country: str = Field(min_length=2, max_length=60)
    city: str = Field(default="", max_length=60)
    mode: Literal["drawing", "brief"] = "drawing"
    config: str | None = Field(default=None, description="Drawing profile (config/plants)")
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _config_for_drawings(self) -> ProjectCreate:
        if self.mode == "drawing" and not self.config:
            raise ValueError("A drawing profile is required for projects that start from a drawing")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)


class DrawingInfo(BaseModel):
    filename: str
    kind: str
    size_bytes: int
    uploaded_at: datetime
    dxf_filename: str | None = None


class BuildInfo(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime
    duration_s: float
    facts: dict[str, Any]
    warnings: list[str] = []
    changes: list[dict[str, Any]] = []


class Event(BaseModel):
    at: datetime
    kind: str
    message: str


class Project(BaseModel):
    id: str
    name: str
    plant_type: PlantType
    country: str
    city: str = ""
    mode: Literal["drawing", "brief"] = "drawing"
    config: str | None = None
    notes: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    brief: Brief | None = None
    created_at: datetime
    updated_at: datetime
    drawing: DrawingInfo | None = None
    latest_build: BuildInfo | None = None
    builds: int = 0
    events: list[Event] = []


class ProjectSummary(BaseModel):
    id: str
    name: str
    mode: Literal["drawing", "brief"] = "drawing"
    plant_type: PlantType
    country: str
    city: str
    status: ProjectStatus
    updated_at: datetime
    footprint_m2: float | None = None
    frames: int | None = None


class Meta(BaseModel):
    version: str
    plant_types: list[dict[str, str]]
    configs: list[str]
    converter_available: bool
