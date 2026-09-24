"""Building-level settings for the 3D model: levels, roof, heights, zones, structure.

Values come from the plant's TOML config. Anything read from the drawings is
marked there with its source; anything assumed is marked as an assumption.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fca.model.schema import BBox


@dataclass(frozen=True)
class Levels:
    ffl: float
    eaves_south: float
    eaves_north: float
    ridge: float
    mezzanine: float | None = None


@dataclass(frozen=True)
class WallHeights:
    internal_low: float = 4.0
    internal_high: float = 7.2
    cold_panel: float = 7.2
    outbuilding: float = 3.5
    boundary: float = 2.4


@dataclass(frozen=True)
class MemberSize:
    width: float
    depth: float


DEFAULT_SIZES = {
    "column": MemberSize(0.25, 0.45),
    "gable_column": MemberSize(0.2, 0.3),
    "rafter": MemberSize(0.2, 0.55),
    "eave_beam": MemberSize(0.15, 0.3),
    "purlin": MemberSize(0.07, 0.2),
    "girt": MemberSize(0.07, 0.2),
    "bracing": MemberSize(0.03, 0.03),
    "foundation": MemberSize(1.8, 0.6),
}


@dataclass(frozen=True)
class StructureConfig:
    # Grid source fields are used when reading a drawing; a concept design
    # generates its grid directly and leaves them empty.
    grid_region: BBox | None = None
    grid_layers: tuple[str, ...] = ()
    align_layer: str = ""
    frame_x: tuple[float, ...] = ()
    column_rows_y: tuple[float, ...] = ()
    gable_y: tuple[float, ...] = ()
    purlin_spacing: float = 1.5
    girt_heights: tuple[float, ...] = (2.5, 5.0, 7.0)
    brace_end_bays: bool = True
    sizes: dict[str, MemberSize] = field(default_factory=lambda: dict(DEFAULT_SIZES))
    sizes_are_indicative: bool = True


@dataclass(frozen=True)
class BuildingConfig:
    envelope: BBox
    levels: Levels
    ridge_y: float
    heights: WallHeights
    low_wall_zones: tuple[BBox, ...]
    mezzanine_zones: tuple[BBox, ...]
    structure: StructureConfig | None
    label_include: tuple[str, ...] = ()


def _bbox(v: dict | list) -> BBox:
    if isinstance(v, list):
        return BBox(xmin=v[0], ymin=v[1], xmax=v[2], ymax=v[3])
    return BBox(**v)


def load_building_config(path: Path) -> BuildingConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    lv = data["levels"]
    levels = Levels(
        ffl=lv["ffl"],
        eaves_south=lv["eaves_south"],
        eaves_north=lv["eaves_north"],
        ridge=lv["ridge"],
        mezzanine=lv.get("mezzanine"),
    )
    zones = data.get("zones", {})
    structure = None
    if "structure" in data:
        s = data["structure"]
        sizes = dict(DEFAULT_SIZES)
        for name, (w, d) in s.get("sizes", {}).items():
            sizes[name] = MemberSize(w, d)
        structure = StructureConfig(
            grid_region=_bbox(s["grid_region"]),
            grid_layers=tuple(s["grid_layers"]),
            align_layer=s["align_layer"],
            frame_x=tuple(s["frame_x"]),
            column_rows_y=tuple(s["column_rows_y"]),
            gable_y=tuple(s.get("gable_y", [])),
            purlin_spacing=s.get("purlin_spacing", 1.5),
            girt_heights=tuple(s.get("girt_heights", [2.5, 5.0, 7.0])),
            brace_end_bays=s.get("brace_end_bays", True),
            sizes=sizes,
            sizes_are_indicative=s.get("sizes_are_indicative", True),
        )
    return BuildingConfig(
        envelope=_bbox(data["building"]),
        levels=levels,
        ridge_y=data["roof"]["ridge_y"],
        heights=WallHeights(**data.get("wall_heights", {})),
        low_wall_zones=tuple(_bbox(z) for z in zones.get("low_walls", [])),
        mezzanine_zones=tuple(_bbox(z) for z in zones.get("mezzanine", [])),
        structure=structure,
        label_include=tuple(data.get("viewer", {}).get("label_include", [])),
    )


def roof_height(cfg: BuildingConfig, y: float) -> float:
    """Top of roof at plan position ``y`` (duo-pitch roof, ridge along x)."""
    env, lv = cfg.envelope, cfg.levels
    y = min(max(y, env.ymin), env.ymax)
    if y <= cfg.ridge_y:
        t = (y - env.ymin) / (cfg.ridge_y - env.ymin)
        return lv.eaves_south + (lv.ridge - lv.eaves_south) * t
    t = (y - cfg.ridge_y) / (env.ymax - cfg.ridge_y)
    return lv.ridge + (lv.eaves_north - lv.ridge) * t
