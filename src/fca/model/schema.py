"""Versioned schema for geometry extracted from plant drawings.

Every downstream tool (3D model, quantities, BOQ) reads this contract,
so changes here must bump ``SCHEMA_VERSION`` and be recorded in an ADR.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"


class Category(StrEnum):
    """What a drawing element represents, after layer mapping."""

    WALL = "wall"
    COLD_PANEL = "cold_panel"
    BOUNDARY = "boundary"
    DOOR = "door"
    WINDOW = "window"


class Segment(BaseModel):
    """A straight 2D line segment in metres, in drawing coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    category: Category
    layer: str

    @property
    def length(self) -> float:
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5


class RoomLabel(BaseModel):
    """A room name found as text inside the plan."""

    text: str
    x: float
    y: float
    layer: str


class BBox(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def depth(self) -> float:
        return self.ymax - self.ymin

    def contains(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax


class CategoryStats(BaseModel):
    count: int
    line_length_m: float = Field(
        description="Sum of drawn line lengths. Walls drawn as two face lines count twice."
    )


class PlantGeometry(BaseModel):
    """Geometry extracted from one plan drawing."""

    schema_version: str = SCHEMA_VERSION
    source_file: str
    extracted_at: datetime
    unit_to_metre: float
    region: BBox | None = None
    building_bbox: BBox | None = None
    segments: list[Segment]
    labels: list[RoomLabel]
    stats: dict[Category, CategoryStats]
    warnings: list[str] = Field(default_factory=list)
