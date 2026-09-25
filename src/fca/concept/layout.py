"""Concept layout: size and place the building, arrange rooms and zones, derive walls,
openings, the column grid and the building settings for the 3D model.

Plan coordinates in metres: x east along the street, y north away from it.
The street is on the south side (y = 0). Raw materials arrive in the goods-in
yard on the west side; finished goods leave from the dispatch apron on the east.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import accumulate, groupby, pairwise

from fca.concept.program import Program, Space, Template
from fca.model.building import BuildingConfig, Levels, MemberSize, StructureConfig, WallHeights
from fca.model.schema import BBox, Category, Segment
from fca.structure.frame import FrameLayout

COLD_INSET = 0.15  # insulated panels sit just inside the room outline
RAFTER_ALLOWANCE = 0.8  # rafter depth plus roof build-up above clear height
DOCK_PITCH = 4.5  # metres between dock door centres
EXIT_SPACING = 40.0  # fire exits along the long façade, metres apart


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
class Opening:
    kind: str  # dock_in, dock_out, fire_exit, entrance, silo
    x: float
    y: float
    side: str  # west, east, north or south


@dataclass
class ConceptLayout:
    plot: BBox
    building: BBox
    strip_depth: float
    rooms: list[Room]
    segments: list[Segment]
    frame: FrameLayout
    config: BuildingConfig
    openings: list[Opening] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def site_setbacks(values: dict, tpl: Template) -> dict:
    s = dict(tpl.site)
    if values.get("goods_in_yard_m") is not None:
        s["setback_west_m"] = values["goods_in_yard_m"]
    if values.get("dispatch_yard_m") is not None:
        s["setback_east_m"] = values["dispatch_yard_m"]
    return s


def max_area_on_plot(values: dict, tpl: Template) -> float | None:
    """Largest single-building footprint the plot allows with the site setbacks."""
    pw, pd = values.get("plot_width_m"), values.get("plot_depth_m")
    if not (pw and pd):
        return None
    site = site_setbacks(values, tpl)
    avail_len = pw - site["setback_west_m"] - site["setback_east_m"]
    avail_dep = pd - site["setback_front_m"] - site["setback_rear_m"]
    cap = values.get("span_m") or tpl.building["max_depth_m"] * (
        2 if values.get("structure_option") == "two_span" else 1
    )
    avail_dep = min(avail_dep, cap)
    if avail_len <= 0 or avail_dep <= 0:
        raise ValueError("The plot is too small for the yards and setbacks around the building")
    return avail_len * avail_dep


def _size_building(area: float, values: dict, tpl: Template, site: dict, warnings: list[str]):
    b = tpl.building
    if values.get("span_m"):
        depth = values["span_m"]
    else:
        depth = b["target_depth_m"]
        if area / depth < 1.2 * depth:  # keep the hall longer than it is deep
            depth = max(b["min_depth_m"], math.sqrt(area / 1.2))
    pw, pd = values.get("plot_width_m"), values.get("plot_depth_m")
    if pw and pd:
        avail_len = pw - site["setback_west_m"] - site["setback_east_m"]
        avail_dep = pd - site["setback_front_m"] - site["setback_rear_m"]
        if not values.get("span_m"):
            depth = min(depth, avail_dep)
            if area / depth > avail_len:
                depth = area / avail_len
    limit = b["max_depth_m"] * (2 if values.get("structure_option") == "two_span" else 1)
    if depth > limit + 0.01:
        warnings.append(
            f"Building depth {depth:.1f} m exceeds an economic span ({limit:.0f} m); "
            "choose the internal column option or a longer, narrower building."
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


def _row(
    spaces: list[Space], x0: float, length: float, y0: float, depth: float, filler: str
) -> list[Room]:
    """Rooms side by side in a row. Spare length becomes a flexible room placed before
    the plant rooms, so plant rooms stay at the east (yard) end."""
    items = [(s.name, s.category, s.area_m2 / depth, s.temp_c) for s in spaces]
    total = sum(w for _, _, w, _ in items)
    if total < length - 1.0:
        at = next((i for i, s in enumerate(spaces) if s.category == "utility"), len(spaces))
        items.insert(at, (filler, "office", length - total, None))
    scale = length / sum(w for _, _, w, _ in items)
    rooms, x = [], x0
    for name, cat, w, t in items:
        rooms.append(Room(name, cat, BBox(xmin=x, ymin=y0, xmax=x + w * scale, ymax=y0 + depth), t))
        x += w * scale
    return rooms


def _depth_for(table: list[tuple[float, float]], value: float) -> float:
    return next(d for limit, d in table if value <= limit)


def build_layout(values: dict, program: Program, tpl: Template) -> ConceptLayout:
    warnings = list(program.warnings)
    area = values["built_up_area_m2"]
    site = site_setbacks(values, tpl)
    length, depth, pw, pd = _size_building(area, values, tpl, site, warnings)
    x0, y0 = site["setback_west_m"], site["setback_front_m"]
    building = BBox(xmin=x0, ymin=y0, xmax=x0 + length, ymax=y0 + depth)
    plot = BBox(xmin=0, ymin=0, xmax=pw, ymax=pd)
    if site["setback_west_m"] < 15:
        warnings.append(
            "The goods-in yard is under 15 m: delivery trucks may not be able to "
            "reach the raw-material docks."
        )
    if site["setback_east_m"] < 30:
        warnings.append(
            "The dispatch apron is under 30 m: articulated trucks need about "
            "30–35 m to turn and reverse onto docks."
        )

    # --- Street strip: two rows of rooms with a corridor between them.
    st = tpl.strip
    corridor = st["corridor_m"]
    south = [s for s in program.strip if s.row == "south"]
    north = [s for s in program.strip if s.row == "north"]

    def row_depth(spaces: list[Space]) -> float:
        need = sum(s.area_m2 for s in spaces) / length
        if need > st["row_max_m"] + 0.01:
            warnings.append(
                "The building is short for the offices and amenities: rooms are "
                "compressed. Consider a longer building or a mezzanine."
            )
        return round(min(st["row_max_m"], max(st["row_min_m"], need)), 2)

    sd, nd = row_depth(south), row_depth(north)
    rooms = _row(south, x0, length, y0, sd, "Flexible offices")
    rooms.append(
        Room(
            "Corridor",
            "circulation",
            BBox(xmin=x0, ymin=y0 + sd, xmax=x0 + length, ymax=y0 + sd + corridor),
        )
    )
    rooms += _row(north, x0, length, y0 + sd + corridor, nd, "Stores and lockers")
    strip_depth = round(sd + corridor + nd, 2)
    hall_y0, hall_y1 = y0 + strip_depth, y0 + depth
    if hall_y1 - hall_y0 < 12:
        warnings.append("Very little depth is left for production after the offices strip.")

    # --- Hall: one slice per group, west to east; zones in a group stacked north-south.
    hall_area = length * (hall_y1 - hall_y0)
    k = hall_area / sum(s.area_m2 for s in program.hall)
    for s in program.hall:
        s.area_m2 *= k
    groups = [
        list(g)
        for _, g in groupby(sorted(program.hall, key=lambda s: s.group), key=lambda s: s.group)
    ]
    group_x = _slices(x0, length, [sum(s.area_m2 for s in g) for g in groups])
    stack_lines: list[tuple[float, float, float]] = []
    hall_rooms: list[Room] = []
    for g, (xa, xb) in zip(groups, group_x, strict=True):
        spans = _slices(hall_y0, hall_y1 - hall_y0, [s.area_m2 for s in g])
        for sp, (ya, yb) in zip(g, spans, strict=True):
            hall_rooms.append(
                Room(sp.name, sp.category, BBox(xmin=xa, ymin=ya, xmax=xb, ymax=yb), sp.temp_c)
            )
        stack_lines += [(xa, xb, ya) for ya, _ in spans[1:]]
    rooms += hall_rooms

    # --- Walls.
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
    for y in (y0 + sd, y0 + sd + corridor, hall_y0):
        wall(b.xmin, y, b.xmax, y)
    for r in rooms:
        in_strip = r.rect.ymax <= hall_y0 + 1e-6
        if in_strip and r.name != "Corridor" and r.rect.xmin > b.xmin + 1e-6:
            wall(r.rect.xmin, r.rect.ymin, r.rect.xmin, r.rect.ymax)
    for xa, _ in group_x[1:]:
        wall(xa, hall_y0, xa, hall_y1)
    for xa, xb, y in stack_lines:
        wall(xa, y, xb, y)
    for r in hall_rooms:
        if r.category == "cold":
            q, i = r.rect, COLD_INSET
            pts = [
                (q.xmin + i, q.ymin + i),
                (q.xmax - i, q.ymin + i),
                (q.xmax - i, q.ymax - i),
                (q.xmin + i, q.ymax - i),
            ]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1], strict=True):
                wall(xa, ya, xb, yb, Category.COLD_PANEL)
    for xa, ya, xb, yb in ((0, 0, pw, 0), (pw, 0, pw, pd), (pw, pd, 0, pd), (0, pd, 0, 0)):
        wall(xa, ya, xb, yb, Category.BOUNDARY)

    # --- Openings: docks on the goods-in and dispatch sides, exits, entrance, silos.
    openings: list[Opening] = []

    def docks(zone: list[Room], side: str, x: float, kind: str, per_m2: float, least: int):
        ya = min(r.rect.ymin for r in zone)
        yb = max(r.rect.ymax for r in zone)
        want = max(least, round(sum(r.area_m2 for r in zone) / per_m2))
        n = min(want, max(1, int((yb - ya - 2) // DOCK_PITCH)))
        for j in range(n):
            openings.append(Opening(kind, x, ya + (yb - ya) * (j + 0.5) / n, side))

    docks(
        [r for r in hall_rooms if r.rect.xmin <= b.xmin + 1e-6], "west", b.xmin, "dock_in", 250, 1
    )
    docks(
        [r for r in hall_rooms if r.rect.xmax >= b.xmax - 1e-6], "east", b.xmax, "dock_out", 90, 2
    )
    n_exit = max(1, math.ceil(length / EXIT_SPACING))
    for j in range(n_exit):
        openings.append(Opening("fire_exit", b.xmin + length * (j + 0.5) / n_exit, b.ymax, "north"))
    for x, side in ((b.xmin, "west"), (b.xmax, "east")):
        openings.append(Opening("fire_exit", x, (hall_y0 + hall_y1) / 2 + 3, side))
        openings.append(Opening("fire_exit", x, y0 + sd + corridor / 2, side))
    rec = next((r for r in rooms if r.name.startswith("Reception")), rooms[0])
    openings.append(Opening("entrance", (rec.rect.xmin + rec.rect.xmax) / 2, b.ymin, "south"))
    if values.get("flour_silos"):
        prod = next((r for r in hall_rooms if r.category == "production"), hall_rooms[0])
        for j in range(2):
            openings.append(Opening("silo", prod.rect.xmin + 3 + 5 * j, b.ymax + 3.5, "north"))
        if b.ymax + 6 > pd:
            warnings.append("The rear setback is too small for the flour silos.")

    # --- Column grid.
    bay = values.get("bay_m") or tpl.building["bay_m"]
    n = max(1, round(length / bay))
    frame_x = tuple(round(x0 + length * i / n, 3) for i in range(n + 1))
    m = max(1, round(depth / bay))
    gable_y = tuple(round(y0 + depth * j / m, 3) for j in range(1, m))
    frame = FrameLayout(frame_x=frame_x, south_y=y0, north_y=y0 + depth, gable_y=gable_y)
    real_bay = length / n
    two_span = values.get("structure_option") == "two_span"
    span = depth / 2 if two_span else depth
    if real_bay > 10:
        warnings.append(f"Bays of {real_bay:.1f} m need heavy purlins; 7.5–9 m is typical.")

    # --- Levels and structure settings.
    ffl = 0.6
    pitch = values.get("roof_pitch_deg") or tpl.building["roof_pitch_deg"]
    eaves = round(ffl + values["clear_height_m"] + RAFTER_ALLOWANCE, 2)
    ridge = round(eaves + math.tan(math.radians(pitch)) * depth / 2, 2)
    offices = [r.rect for r in rooms if r.category == "office" and r.rect.ymax <= y0 + sd + 1e-6]
    mezz_zones = ()
    if values["mezzanine"] and offices:
        mezz_zones = (
            BBox(
                xmin=min(o.xmin for o in offices),
                ymin=y0,
                xmax=max(o.xmax for o in offices),
                ymax=y0 + sd,
            ),
        )
    rafter_d = _depth_for([(25, 0.46), (32, 0.53), (40, 0.61), (1e9, 0.69)], span)
    purlin_d = _depth_for([(6, 0.2), (7.5, 0.25), (9.5, 0.3), (1e9, 0.35)], real_bay)
    sizes = dict(StructureConfig().sizes)
    sizes["rafter"] = MemberSize(0.23, rafter_d)
    sizes["haunch"] = MemberSize(0.23, rafter_d * 0.8)
    sizes["column"] = MemberSize(0.23, rafter_d * 0.9)
    sizes["purlin"] = MemberSize(0.08, purlin_d)
    sizes["girt"] = MemberSize(0.08, purlin_d)
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
        structure=StructureConfig(internal_columns=two_span, sizes=sizes),
    )
    return ConceptLayout(
        plot, building, strip_depth, rooms, segs, frame, config, openings, warnings
    )
