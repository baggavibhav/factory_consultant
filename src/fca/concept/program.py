"""Space program: how the built-up area is split into zones, from a template."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fca.settings import PROJECT_ROOT

TEMPLATE_DIR = PROJECT_ROOT / "config" / "templates"


@dataclass(frozen=True)
class HallZone:
    group: int
    name: str
    share: float
    category: str
    temp_c: float | None = None
    requires: str | None = None


@dataclass(frozen=True)
class Template:
    name: str
    building: dict
    site: dict
    strip: dict
    production: dict
    hall: tuple[HallZone, ...]


def load_template(plant_type: str, directory: Path | None = None) -> Template:
    path = Path(directory or TEMPLATE_DIR) / f"{plant_type}.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    hall = tuple(HallZone(**z) for z in data["hall"])
    return Template(
        data["name"], data["building"], data["site"], data["strip"], data["production"], hall
    )


@dataclass
class Space:
    name: str
    category: str
    area_m2: float
    temp_c: float | None = None
    group: int | None = None  # hall slice; None = street strip


@dataclass
class Program:
    strip: list[Space]
    hall: list[Space]
    warnings: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[Space]:
        return self.strip + self.hall


def build_program(values: dict, tpl: Template) -> Program:
    area = values["built_up_area_m2"]
    s = tpl.strip
    office = s["office_base_m2"] + s["office_m2_per_person"] * values["office_staff"]
    strip = [Space("Offices", "office", office)]
    if values["qa_lab"]:
        strip.append(Space("QA laboratory", "office", s["qa_lab_m2"]))
    amen = s["amenity_base_m2"] + s["amenity_m2_per_staff"] * values["staff_per_shift"]
    strip += [
        Space("Changing and hygiene", "amenity", amen * 0.6),
        Space("Dining and prayer", "amenity", amen * 0.4),
        Space("Utilities and services", "utility", area * s["utilities_share"]),
    ]
    warnings: list[str] = []
    strip_total = sum(x.area_m2 for x in strip)
    if strip_total > area * 0.4:
        warnings.append(
            "Offices, amenities and utilities take over 40% of the area; check staff numbers "
            "or increase the built-up area."
        )
    hall_area = area - strip_total
    zones = [z for z in tpl.hall if not z.requires or values.get(z.requires)]
    total_share = sum(z.share for z in zones)
    hall = [
        Space(z.name, z.category, hall_area * z.share / total_share, z.temp_c, z.group)
        for z in zones
    ]
    lines = values["lines_now"] + values["lines_future"]
    prod = sum(x.area_m2 for x in hall if x.category == "production")
    need = lines * tpl.production["min_m2_per_line"]
    if lines and prod < need:
        warnings.append(
            f"Production space ({prod:,.0f} m²) is below the typical {need:,.0f} m² for "
            f"{lines} line(s); consider a larger building."
        )
    return Program(strip, hall, warnings)
