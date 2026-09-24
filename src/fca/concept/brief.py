"""The plant brief: what the user tells us when there is no drawing.

Every field except area and plant type has a default. Defaults used are
reported back as assumptions, so the user knows what to confirm.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlantKind = Literal["industrial", "retail", "egg_station"]

DEFAULTS: dict[str, dict] = {
    "industrial": {"staff_per_shift": 60, "office_staff": 12, "lines_now": 2, "lines_future": 1},
    "retail": {"staff_per_shift": 20, "office_staff": 4, "lines_now": 1, "lines_future": 0},
    "egg_station": {"staff_per_shift": 25, "office_staff": 5, "lines_now": 1, "lines_future": 0},
}


class Brief(BaseModel):
    """Inputs for a concept design. Areas and lengths in metric units."""

    plant_type: PlantKind
    built_up_area_m2: float = Field(gt=150, le=100_000, description="Main building footprint")
    plot_width_m: float | None = Field(default=None, gt=10, le=2000, description="Street frontage")
    plot_depth_m: float | None = Field(default=None, gt=10, le=2000)
    products: str = Field(default="", max_length=300)
    output_tonnes_per_day: float | None = Field(default=None, ge=0, le=5000)
    shifts_per_day: int | None = Field(default=None, ge=1, le=3)
    lines_now: int | None = Field(default=None, ge=0, le=40)
    lines_future: int | None = Field(default=None, ge=0, le=40)
    cold_storage: bool | None = None
    blast_freezer: bool | None = None
    staff_per_shift: int | None = Field(default=None, ge=1, le=5000)
    office_staff: int | None = Field(default=None, ge=0, le=1000)
    qa_lab: bool | None = None
    mezzanine: bool | None = None
    clear_height_m: float | None = Field(default=None, ge=3, le=20)


def resolve(brief: Brief) -> tuple[dict, list[str]]:
    """Fill defaults. Returns (values, assumptions stated in plain language)."""
    d = DEFAULTS[brief.plant_type]
    v = brief.model_dump()
    notes: list[str] = []

    def default(key: str, value, text: str) -> None:
        if v[key] is None:
            v[key] = value
            notes.append(text)

    default("lines_now", d["lines_now"], f"{d['lines_now']} production line(s) now")
    default("lines_future", d["lines_future"], f"space for {d['lines_future']} future line(s)")
    default(
        "staff_per_shift",
        d["staff_per_shift"],
        f"{d['staff_per_shift']} staff on the busiest shift",
    )
    default("office_staff", d["office_staff"], f"{d['office_staff']} office staff")
    default("shifts_per_day", 2, "2 shifts per day")
    default(
        "cold_storage",
        brief.plant_type != "retail",
        "cold storage included" if brief.plant_type != "retail" else "no cold storage",
    )
    default("blast_freezer", False, "no blast freezer")
    default("qa_lab", True, "QA laboratory included")
    default(
        "mezzanine",
        brief.plant_type == "industrial",
        "mezzanine over the offices" if brief.plant_type == "industrial" else "no mezzanine",
    )
    default(
        "clear_height_m",
        7.5 if brief.plant_type == "industrial" else 5.5,
        "clear height of 7.5 m under the roof"
        if brief.plant_type == "industrial"
        else "clear height of 5.5 m under the roof",
    )
    if brief.plot_width_m is None or brief.plot_depth_m is None:
        notes.append("plot sized to fit the building with standard setbacks")
    return v, notes
