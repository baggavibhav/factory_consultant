"""Room outlines from a DXF plan.

Walls are drawn as lines with gaps at doors, so rooms are not closed shapes.
We close door-sized gaps between collinear wall ends, build polygons from the
wall network, and give each room label the smallest polygon around it.
Open-plan hall zones (production, stores) often have no closed outline; the
remaining floor inside the building is split between their labels
(nearest-label regions) and marked as estimated.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise

from ezdxf.document import Drawing
from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.ops import polygonize, unary_union, voronoi_diagram

from fca.ingestion.layers import PlantConfig
from fca.model.schema import BBox

GAP_MIN, GAP_MAX = 0.5, 2.1  # door and double-door openings, metres
COLLINEAR = 0.985  # cos of the allowed angle between wall direction and gap
MIN_ROOM_M2 = 3.0

CATEGORY_WORDS = [
    ("cold", ("FREEZER", "COLD STORE", "CHILLER", "-18", "-40")),
    ("dispatch", ("MARSHALLING", "DISPATCH", "LOADING")),
    ("production", ("PRODUCTION AREA", "COOLING", "PACKAGING", "CARTONING", "MIXING", "BAKING")),
    ("storage", ("RM STORE", "PM STORE", "FILMS", "STORE +", "WAREHOUSE")),
    ("office", ("OFFICE", "RECEPTION", "QA", "LABORATORY", "SAMPLE", "SERVER")),
    (
        "amenity",
        (
            "CHANGING",
            "TOILET",
            "TOL",
            "HYGIENE",
            "ABLUTION",
            "PRAYER",
            "DINING",
            "HAND WASH",
            "SHOES",
            "FIRST AID",
            "UTENSIL",
            "WASH",
        ),
    ),
    (
        "utility",
        (
            "ELECTRICAL",
            "LT PANEL",
            "CO2",
            "COMPRESSOR",
            "PUMP",
            "MAINTENANCE",
            "GUARD",
            "SCECO",
            "GENERATOR",
            "LPG",
        ),
    ),
    ("circulation", ("PASSAGE", "CORRIDOR", "ENTRY", "LOBBY")),
]
IGNORE = {"IN", "UP", "ROOM", "SH", "CH", "1.2M WIDE", "N E I G H B O R", "PLOT LIMIT"}


@dataclass
class DrawnRoom:
    name: str
    category: str
    polygon: Polygon
    estimated: bool = False
    temp_c: float | None = None
    labels: list[str] = field(default_factory=list)

    @property
    def area_m2(self) -> float:
        return self.polygon.area

    @property
    def rect(self) -> BBox:
        x0, y0, x1, y1 = self.polygon.bounds
        return BBox(xmin=x0, ymin=y0, xmax=x1, ymax=y1)


def categorise(name: str) -> str | None:
    up = name.upper()
    for cat, words in CATEGORY_WORDS:
        if any(w in up for w in words):
            return cat
    return None


def _temperature(name: str) -> float | None:
    m = re.search(r"([+-−]?\d+)\s*°C", name)
    return float(m.group(1).replace("−", "-")) if m else None


def _segments(doc: Drawing, layers: set[str], region: BBox, scale: float):
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []

    def inside(p):
        return region.contains(p[0], p[1])

    def walk(e, depth=0):
        kind = e.dxftype()
        if kind == "LINE":
            a = (e.dxf.start.x, e.dxf.start.y)
            b = (e.dxf.end.x, e.dxf.end.y)
            if inside(a) and inside(b) and math.dist(a, b) > 0.02:
                out.append(((a[0] * scale, a[1] * scale), (b[0] * scale, b[1] * scale)))
        elif kind == "LWPOLYLINE":
            v = [(p.x, p.y) for p in e.vertices_in_wcs()]
            if e.closed and v:
                v.append(v[0])
            for a, b in pairwise(v):
                if inside(a) and inside(b) and math.dist(a, b) > 0.02:
                    out.append(((a[0] * scale, a[1] * scale), (b[0] * scale, b[1] * scale)))
        elif kind == "INSERT" and depth < 5:
            try:
                for child in e.virtual_entities():
                    walk(child, depth + 1)
            except Exception:  # malformed blocks are skipped
                pass

    for e in doc.modelspace():
        if e.dxf.layer in layers:
            walk(e)
    return out


def _closers(segs):
    """Connect wall ends across door-sized gaps when both walls point at each other."""
    ends = []
    for i, (a, b) in enumerate(segs):
        length = math.dist(a, b)
        u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        ends.append((a, (-u[0], -u[1]), i))
        ends.append((b, u, i))
    grid = defaultdict(list)
    for k, (p, _, _) in enumerate(ends):
        grid[(int(p[0] // GAP_MAX), int(p[1] // GAP_MAX))].append(k)
    out = []
    for k, (p, u, i) in enumerate(ends):
        gx, gy = int(p[0] // GAP_MAX), int(p[1] // GAP_MAX)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k2 in grid[(gx + dx, gy + dy)]:
                    if k2 <= k:
                        continue
                    q, v, j = ends[k2]
                    if j == i:
                        continue
                    d = math.dist(p, q)
                    if not GAP_MIN <= d <= GAP_MAX:
                        continue
                    g = ((q[0] - p[0]) / d, (q[1] - p[1]) / d)
                    if (
                        u[0] * g[0] + u[1] * g[1] > COLLINEAR
                        and -(v[0] * g[0] + v[1] * g[1]) > COLLINEAR
                    ):
                        out.append((p, q))
    return out


def extract_rooms(doc: Drawing, config: PlantConfig, building: BBox) -> list[DrawnRoom]:
    """Rooms (named polygons) from the plan. Labels come from the config's label layers."""
    from fca.model.schema import Category

    if config.region is None:
        return []
    scale = config.unit_to_metre
    layers = set(config.layers.get(Category.WALL, ())) | set(
        config.layers.get(Category.COLD_PANEL, ())
    )
    layers |= set(config.layers.get(Category.WINDOW, ()))
    segs = _segments(doc, layers, config.region, scale)
    lines = [LineString(s) for s in segs] + [LineString(c) for c in _closers(segs)]
    polys = [p for p in polygonize(unary_union(lines)) if p.area >= MIN_ROOM_M2]

    labels = []
    for e in doc.modelspace().query("TEXT MTEXT"):
        if e.dxf.layer not in config.label_layers:
            continue
        p = e.dxf.insert
        if not config.region.contains(p.x, p.y):
            continue
        raw = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        text = re.sub(r"\s+", " ", raw).strip()
        if text.upper() in IGNORE or not categorise(text):
            continue
        labels.append((text, Point(p.x * scale + 0.4, p.y * scale + 0.15)))

    rooms: dict[int, DrawnRoom] = {}
    unmatched = []
    for text, pt in labels:
        around = [p for p in polys if p.contains(pt)]
        if around:
            poly = min(around, key=lambda p: p.area)
            key = id(poly)
            if key in rooms:
                rooms[key].labels.append(text)
            else:
                rooms[key] = DrawnRoom(
                    text, categorise(text), poly, temp_c=_temperature(text), labels=[text]
                )
        else:
            unmatched.append((text, pt))

    # Open-plan zones inside the building: split the remaining floor between labels.
    shell = box(building.xmin, building.ymin, building.xmax, building.ymax)
    inside = [(t, p) for t, p in unmatched if shell.contains(p)]
    taken = unary_union([r.polygon for r in rooms.values()]) if rooms else Polygon()
    rest = shell.difference(taken.buffer(0.3))
    if inside and not rest.is_empty:
        pts = MultiPoint([p for _, p in inside])
        cells = voronoi_diagram(pts, envelope=shell) if len(inside) > 1 else shell
        cell_list = list(cells.geoms) if hasattr(cells, "geoms") else [cells]
        for text, pt in inside:
            cell = next((c for c in cell_list if c.contains(pt)), None)
            if cell is None:
                continue
            area = cell.intersection(rest)
            if area.is_empty:
                continue
            if area.geom_type == "MultiPolygon":  # keep the part around the label
                area = next(
                    (g for g in area.geoms if g.buffer(0.5).contains(pt)),
                    max(area.geoms, key=lambda g: g.area),
                )
            if area.area >= MIN_ROOM_M2:
                rooms[id(area)] = DrawnRoom(
                    text,
                    categorise(text),
                    area,
                    estimated=True,
                    temp_c=_temperature(text),
                    labels=[text],
                )
    return sorted(rooms.values(), key=lambda r: (r.polygon.centroid.x, r.polygon.centroid.y))
