"""Concept layout: size and place the building, arrange zones in process-flow order,
derive walls, the column grid and the building settings for the 3D model.

Plan coordinates in metres: x east along the street, y north away from it.
The street is on the south side (y = 0) of the plot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import accumulate, groupby, pairwise

from fca.concept.program import Program, Template
from fca.model.building import BuildingConfig, Levels, StructureConfig, WallHeights
from fca.model.schema import BBox, Category, Segment
from fca.structure.frame import FrameLayout

COLD_INSET = 0.15  # insulated panels sit just inside the room outline
RAFTER_ALLOWANCE = 0.75  # rafter depth plus roof build-up above clear height


@dataclass
class Room:
    name: str
    category: str
    rect: BBox
    temp_c: float | None = None

    @property
    def area_m2(self) -> float:
        return self.rect.width * self.rect.depth

    @property
    def label(self) -> str:
        if self.temp_c is None:
            return self.name.upper()
        sign = "+" if self.temp_c > 0 else ""
        return f"{self.name.upper()} {sign}{self.temp_c:g}°C"


@dataclass
class ConceptLayout:
    plot: BBox
    building: BBox
    strip_depth: float
    rooms: list[Room]
    segments: list[Segment]
    frame: FrameLayout
    config: BuildingConfig
    warnings: list[str] = field(default_factory=list)


def max_area_on_plot(values: dict, tpl: Template) -> float | None:
    """Largest single-building footprint the plot allows with standard setbacks."""
    pw, pd = values.get("plot_width_m"), values.get("plot_depth_m")
    if not (pw and pd):
        return None
    site = tpl.site
    avail_len = pw - site["setback_west_m"] - site["setback_east_m"]
    avail_dep = min(
        pd - site["setback_front_m"] - site["setback_rear_m"], tpl.building["max_depth_m"]
    )
    if avail_len <= 0 or avail_dep <= 0:
        raise ValueError("The plot is too small for the standard setbacks around the building")
    return avail_len * avail_dep


def _size_building(area: float, values: dict, tpl: Template, warnings: list[str]):
    b, site = tpl.building, tpl.site
    depth = b["target_depth_m"]
    if area / depth < 1.2 * depth:  # keep the hall longer than it is deep
        depth = max(b["min_depth_m"], math.sqrt(area / 1.2))
    pw, pd = values.get("plot_width_m"), values.get("plot_depth_m")
    if pw and pd:
        avail_len = pw - site["setback_west_m"] - site["setback_east_m"]
        avail_dep = pd - site["setback_front_m"] - site["setback_rear_m"]
        if avail_len <= 0 or avail_dep <= 0:
            raise ValueError("The plot is too small for the standard setbacks")
        depth = min(depth, avail_dep)
        if area / depth > avail_len:
            depth = area / avail_len
        if depth > avail_dep + 0.01:
            warnings.append(
                f"{area:,.0f} m² does not fit on this plot as one building "
                f"(maximum about {avail_len * avail_dep:,.0f} m² with standard setbacks)."
            )
    if depth > b["max_depth_m"]:
        warnings.append(
            f"Building depth {depth:.1f} m exceeds an economic clear span "
            f"({b['max_depth_m']:.0f} m); internal columns would be needed."
        )
    length = area / depth
    if not (pw and pd):
        pw = length + site["setback_west_m"] + site["setback_east_m"]
        pd = depth + site["setback_front_m"] + site["setback_rear_m"]
    return round(length, 2), round(depth, 2), float(pw), float(pd)


def _slices(start: float, total: float, sizes: list[float]) -> list[tuple[float, float]]:
    """Split [start, start+total] into consecutive parts proportional to sizes."""
    s = sum(sizes)
    edges = [start] + [start + total * c / s for c in accumulate(sizes)]
    return list(pairwise(edges))


def build_layout(values: dict, program: Program, tpl: Template) -> ConceptLayout:
    warnings = list(program.warnings)
    area = values["built_up_area_m2"]
    length, depth, pw, pd = _size_building(area, values, tpl, warnings)
    site = tpl.site
    x0, y0 = site["setback_west_m"], site["setback_front_m"]
    building = BBox(xmin=x0, ymin=y0, xmax=x0 + length, ymax=y0 + depth)
    plot = BBox(xmin=0, ymin=0, xmax=pw, ymax=pd)

    lo, hi = tpl.building["street_strip_depth_m"]
    strip_area = sum(s.area_m2 for s in program.strip)
    sd = round(min(hi, max(lo, strip_area / length)), 2)
    rooms: list[Room] = []

    # Street strip: offices, lab, amenities, utilities side by side.
    for sp, (xa, xb) in zip(
        program.strip, _slices(x0, length, [s.area_m2 for s in program.strip]), strict=True
    ):
        rooms.append(
            Room(sp.name, sp.category, BBox(xmin=xa, ymin=y0, xmax=xb, ymax=y0 + sd), sp.temp_c)
        )

    # Hall: one slice per group, west to east; zones in a group stacked north-south.
    hall_y0, hall_y1 = y0 + sd, y0 + depth
    groups = [
        list(g)
        for _, g in groupby(sorted(program.hall, key=lambda s: s.group), key=lambda s: s.group)
    ]
    group_x = _slices(x0, length, [sum(s.area_m2 for s in g) for g in groups])
    hall_dividers_x = [xa for xa, _ in group_x[1:]]
    stack_lines: list[tuple[float, float, float]] = []
    for g, (xa, xb) in zip(groups, group_x, strict=True):
        spans = _slices(hall_y0, hall_y1 - hall_y0, [s.area_m2 for s in g])
        for sp, (ya, yb) in zip(g, spans, strict=True):
            rooms.append(
                Room(sp.name, sp.category, BBox(xmin=xa, ymin=ya, xmax=xb, ymax=yb), sp.temp_c)
            )
        stack_lines += [(xa, xb, ya) for ya, _ in spans[1:]]

    # Walls: envelope, strip/hall divider, room dividers, cold-room panels.
    segs: list[Segment] = []

    def wall(xa, ya, xb, yb, cat=Category.WALL):
        segs.append(Segment(x1=xa, y1=ya, x2=xb, y2=yb, category=cat, layer="concept"))

    b = building
    for xa, ya, xb, yb in (
        (b.xmin, b.ymin, b.xmax, b.ymin),
        (b.xmax, b.ymin, b.xmax, b.ymax),
        (b.xmax, b.ymax, b.xmin, b.ymax),
        (b.xmin, b.ymax, b.xmin, b.ymin),
    ):
        wall(xa, ya, xb, yb)
    wall(b.xmin, hall_y0, b.xmax, hall_y0)
    for r in rooms[1 : len(program.strip)]:
        wall(r.rect.xmin, y0, r.rect.xmin, hall_y0)
    for x in hall_dividers_x:
        wall(x, hall_y0, x, hall_y1)
    for xa, xb, y in stack_lines:
        wall(xa, y, xb, y)
    for r in rooms:
        if r.category == "cold":
            q = r.rect
            i = COLD_INSET
            pts = [
                (q.xmin + i, q.ymin + i),
                (q.xmax - i, q.ymin + i),
                (q.xmax - i, q.ymax - i),
                (q.xmin + i, q.ymax - i),
            ]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1], strict=True):
                wall(xa, ya, xb, yb, Category.COLD_PANEL)

    # Plot boundary wall.
    for xa, ya, xb, yb in ((0, 0, pw, 0), (pw, 0, pw, pd), (pw, pd, 0, pd), (0, pd, 0, 0)):
        wall(xa, ya, xb, yb, Category.BOUNDARY)

    # Column grid: frames at equal bays; gable columns roughly every bay.
    bay = tpl.building["bay_m"]
    n = max(1, round(length / bay))
    frame_x = tuple(round(x0 + length * i / n, 3) for i in range(n + 1))
    m = max(1, round(depth / bay))
    gable_y = tuple(round(y0 + depth * j / m, 3) for j in range(1, m))
    frame = FrameLayout(frame_x=frame_x, south_y=y0, north_y=y0 + depth, gable_y=gable_y)

    ffl = 0.6
    eaves = round(ffl + values["clear_height_m"] + RAFTER_ALLOWANCE, 2)
    ridge = round(eaves + math.tan(math.radians(tpl.building["roof_pitch_deg"])) * depth / 2, 2)
    offices = [r.rect for r in rooms if r.category == "office"]
    mezz_zones = ()
    if values["mezzanine"] and offices:
        mezz_zones = (
            BBox(
                xmin=min(o.xmin for o in offices),
                ymin=y0,
                xmax=max(o.xmax for o in offices),
                ymax=hall_y0,
            ),
        )
    config = BuildingConfig(
        envelope=building,
        levels=Levels(
            ffl=ffl,
            eaves_south=eaves,
            eaves_north=eaves,
            ridge=ridge,
            mezzanine=round(ffl + 3.4, 2) if mezz_zones else None,
        ),
        ridge_y=y0 + depth / 2,
        heights=WallHeights(
            internal_low=3.4 if mezz_zones else 3.6,
            internal_high=min(values["clear_height_m"] - 0.3, 7.2),
            cold_panel=min(values["clear_height_m"] - 0.5, 7.0),
        ),
        low_wall_zones=(BBox(xmin=b.xmin, ymin=y0, xmax=b.xmax, ymax=hall_y0 - 0.01),),
        mezzanine_zones=mezz_zones,
        structure=StructureConfig(),
    )
    return ConceptLayout(plot, building, sd, rooms, segs, frame, config, warnings)
