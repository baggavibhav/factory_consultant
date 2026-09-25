"""Space program: how the built-up area is split into rooms and zones, from a template."""

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
class StripRoom:
    name: str
    category: str
    row: str
    base_m2: float
    per_person: float = 0.0
    people: str | None = None
    requires: str | None = None
    per_area_m2: float = 0.0


@dataclass(frozen=True)
class Template:
    name: str
    building: dict
    site: dict
    strip: dict
    strip_rooms: tuple[StripRoom, ...]
    production: dict
    hall: tuple[HallZone, ...]


def load_template(plant_type: str, directory: Path | None = None) -> Template:
    path = Path(directory or TEMPLATE_DIR) / f"{plant_type}.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return Template(
        data["name"],
        data["building"],
        data["site"],
        data["strip"],
        tuple(StripRoom(**r) for r in data["strip_room"]),
        data["production"],
        tuple(HallZone(**z) for z in data["hall"]),
    )


@dataclass
class Space:
    name: str
    category: str
    area_m2: float
    temp_c: float | None = None
    group: int | None = None  # hall slice; None = street strip
    row: str | None = None  # "south" or "north" for strip rooms


@dataclass
class Program:
    strip: list[Space]
    hall: list[Space]
    warnings: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[Space]:
        return self.strip + self.hall


def hall_zone_names(tpl: Template) -> list[str]:
    return [z.name for z in tpl.hall]


def build_program(values: dict, tpl: Template) -> Program:
    area = values["built_up_area_m2"]
    staff = values["staff_per_shift"]
    female = round(staff * values["female_staff_share"])
    people = {
        "male": staff - female,
        "female": female,
        "all": staff,
        "office": values["office_staff"],
    }
    strip: list[Space] = []
    for r in tpl.strip_rooms:
        if r.requires and not values.get(r.requires):
            continue
        n = people.get(r.people or "", 0)
        if r.people in ("male", "female") and n == 0:
            continue  # no facilities for a group with no staff
        a = r.base_m2 + r.per_person * n + r.per_area_m2 * area
        strip.append(Space(r.name, r.category, a, None, None, r.row))

    warnings: list[str] = []
    strip_total = sum(x.area_m2 for x in strip)
    if strip_total > area * 0.4:
        warnings.append(
            "Offices, amenities and plant rooms take over 40% of the area; check staff numbers "
            "or increase the built-up area."
        )
    zones = [z for z in tpl.hall if not z.requires or values.get(z.requires)]
    sizes = values.get("zone_sizes") or {}
    weights = [z.share * sizes.get(z.name, 1.0) for z in zones]
    # Hall area is fixed by the layout (strip depth); areas here are provisional shares.
    hall_area = max(area - strip_total, area * 0.4)
    hall = [
        Space(z.name, z.category, hall_area * w / sum(weights), z.temp_c, z.group)
        for z, w in zip(zones, weights, strict=True)
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
