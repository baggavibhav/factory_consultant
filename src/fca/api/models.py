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


class Variant(BaseModel):
    """An alternative version of a concept design, built separately for comparison."""

    id: str
    name: str
    brief: Brief
    created_at: datetime
    source: str | None = None  # finding id when created from a check
    build: BuildInfo | None = None


class VariantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    changes: dict[str, Any] = Field(default_factory=dict, description="Brief fields to change")
    brief: Brief | None = Field(default=None, description="Full brief (instead of changes)")
    source: str | None = None


class CostSettings(BaseModel):
    preliminaries: float | None = Field(default=None, ge=0, le=0.5)
    overhead_profit: float | None = Field(default=None, ge=0, le=0.5)
    contingency: float | None = Field(default=None, ge=0, le=0.5)
    vat: float | None = Field(default=None, ge=0, le=0.3)
    escalation_per_year: float | None = Field(default=None, ge=0, le=0.3)
    construction_start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    construction_months: int | None = Field(default=None, ge=1, le=60)


class RateEdit(BaseModel):
    rate: float | None = Field(default=None, ge=0)
    low: float | None = Field(default=None, ge=0)
    high: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=300)


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
    variants: list[Variant] = []
    cost_settings: dict[str, Any] = {}
    procurement: dict[str, Any] = {}


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
    demo: bool = False
