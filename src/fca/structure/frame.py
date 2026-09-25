"""Generate a steel portal-frame structure from the column grid.

Layout (where members go) follows the drawing's grid. Member sizes come from
config and are indicative unless taken from structural drawings. This is a
visual and quantity model, not a structural design: sizing and connections
must be checked by a structural engineer.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from fca.model.building import BuildingConfig, roof_height

Point = tuple[float, float, float]  # plan x, plan y, height z (metres)

KINDS = (
    "foundation",
    "column",
    "internal_column",
    "gable_column",
    "rafter",
    "haunch",
    "eave_beam",
    "purlin",
    "girt",
    "bracing",
    "mezz_column",
    "mezz_beam",
)


@dataclass(frozen=True)
class Member:
    kind: str
    start: Point
    end: Point
    width: float
    depth: float

    @property
    def length(self) -> float:
        return sum((a - b) ** 2 for a, b in zip(self.start, self.end, strict=True)) ** 0.5


@dataclass(frozen=True)
class FrameLayout:
    frame_x: tuple[float, ...]
    south_y: float
    north_y: float
    gable_y: tuple[float, ...]


def _slope_stations(y0: float, y1: float, spacing: float) -> list[float]:
    """Purlin positions from y0 to y1 inclusive, evenly spaced, at most ``spacing`` apart."""
    n = max(1, round(abs(y1 - y0) / spacing + 0.4999))
    return [y0 + (y1 - y0) * i / n for i in range(n + 1)]


def generate_frame(cfg: BuildingConfig, layout: FrameLayout) -> list[Member]:
    s = cfg.structure
    if s is None:
        raise ValueError("Plant config has no [structure] section")
    size = s.sizes
    ffl = cfg.levels.ffl
    rd = size["rafter"].depth
    ys, yn, ridge = layout.south_y, layout.north_y, cfg.ridge_y
    members: list[Member] = []

    def add(kind: str, a: Point, b: Point) -> None:
        members.append(Member(kind, a, b, size[kind].width, size[kind].depth))

    def rafter_z(y: float) -> float:  # rafter centreline sits under the roof sheeting
        return roof_height(cfg, y) - rd / 2 - 0.02

    def column_top(y: float) -> float:
        return roof_height(cfg, y) - rd - 0.02

    pad = size["foundation"]
    pad_top = -0.3

    def column(kind: str, x: float, y: float) -> None:
        add(kind, (x, y, ffl), (x, y, column_top(y)))
        members.append(
            Member("foundation", (x, y, pad_top - pad.depth), (x, y, pad_top), pad.width, pad.width)
        )

    # Portal frames: two columns and two rafters meeting at the ridge on each frame line.
    for x in layout.frame_x:
        for y in (ys, yn):
            column("column", x, y)
        add("rafter", (x, ys, rafter_z(ys)), (x, ridge, rafter_z(ridge)))
        add("rafter", (x, ridge, rafter_z(ridge)), (x, yn, rafter_z(yn)))

    # Haunches deepen the rafter at the eaves (10% of the span) and at the apex.
    if s.haunches:
        hd = size["haunch"].depth
        span = yn - ys
        for x in layout.frame_x:
            for y0, y1 in ((ys, ys + 0.1 * span), (yn, yn - 0.1 * span)):
                z0 = rafter_z(y0) - rd / 2 - hd / 2
                z1 = rafter_z(y1) - rd / 2 - hd / 2
                add("haunch", (x, y0, z0), (x, y1, z1))
            for y0, y1 in ((ridge - 0.04 * span, ridge), (ridge, ridge + 0.04 * span)):
                add(
                    "haunch",
                    (x, y0, rafter_z(y0) - rd / 2 - hd / 4),
                    (x, y1, rafter_z(y1) - rd / 2 - hd / 4),
                )

    # Optional internal column line under the ridge (two-span frame).
    if s.internal_columns:
        for x in layout.frame_x:
            add("internal_column", (x, ridge, ffl), (x, ridge, rafter_z(ridge) - rd / 2))
            members.append(
                Member(
                    "foundation",
                    (x, ridge, pad_top - pad.depth),
                    (x, ridge, pad_top),
                    pad.width,
                    pad.width,
                )
            )

    # Gable-end wind columns on the first and last frames.
    for x in (layout.frame_x[0], layout.frame_x[-1]):
        for y in layout.gable_y:
            if ys < y < yn:
                column("gable_column", x, y)

    purlin_z_offset = rd / 2 + size["purlin"].depth / 2
    stations = (
        _slope_stations(ys, ridge, s.purlin_spacing)
        + _slope_stations(ridge, yn, s.purlin_spacing)[1:]
    )
    wall_rows = (ys, yn)
    for xa, xb in pairwise(layout.frame_x):
        # Eave beams tie the column heads along each long side.
        for y in wall_rows:
            add("eave_beam", (xa, y, column_top(y)), (xb, y, column_top(y)))
        # Purlins span frame to frame on top of the rafters.
        for y in stations:
            z = rafter_z(y) + purlin_z_offset
            add("purlin", (xa, y, z), (xb, y, z))
        # Side-wall girts carry the wall cladding.
        for y in wall_rows:
            for h in s.girt_heights:
                z = ffl + h
                if z < column_top(y) - 0.3:
                    add("girt", (xa, y, z), (xb, y, z))

    # Gable girts between gable columns on the end frames.
    for x in (layout.frame_x[0], layout.frame_x[-1]):
        posts = [ys, *[y for y in layout.gable_y if ys < y < yn], yn]
        for ya, yb in pairwise(posts):
            for h in s.girt_heights:
                z = ffl + h
                if z < min(column_top(ya), column_top(yb)) - 0.3:
                    add("girt", (x, ya, z), (x, yb, z))

    # Cross bracing in the end bays, plus an intermediate braced bay at least every
    # ``bracing_spacing_m`` so wind and restraint forces have a short path to the ground.
    if s.brace_end_bays and len(layout.frame_x) >= 2:
        fx = layout.frame_x
        braced = {0, len(fx) - 2}
        last = fx[0]
        for i in range(1, len(fx) - 2):
            if fx[i + 1] - last > s.bracing_spacing_m:
                braced.add(i)
                last = fx[i + 1]
        for xa, xb in {(fx[i], fx[i + 1]) for i in sorted(braced)}:
            for y0, y1 in ((ys, ridge), (ridge, yn)):
                add("bracing", (xa, y0, rafter_z(y0)), (xb, y1, rafter_z(y1)))
                add("bracing", (xa, y1, rafter_z(y1)), (xb, y0, rafter_z(y0)))
            for y in wall_rows:
                top = column_top(y)
                add("bracing", (xa, y, ffl), (xb, y, top))
                add("bracing", (xa, y, top), (xb, y, ffl))
    return members


def schedule(members: list[Member]) -> dict[str, dict[str, float]]:
    """Count and total length per member kind (a first input to the steel BOQ)."""
    out: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "length_m": 0.0})
    for m in members:
        out[m.kind]["count"] += 1
        out[m.kind]["length_m"] += m.length
    return {
        k: {"count": v["count"], "length_m": round(v["length_m"], 1)}
        for k, v in sorted(out.items(), key=lambda kv: KINDS.index(kv[0]))
    }


def mezzanine_members(cfg: BuildingConfig, grid_m: float = 6.0) -> list[Member]:
    """Beams on a regular grid and columns under a mezzanine zone."""
    if cfg.levels.mezzanine is None or cfg.structure is None:
        return []
    size = cfg.structure.sizes
    out: list[Member] = []
    top = cfg.levels.mezzanine - 0.2
    for z in cfg.mezzanine_zones:
        nx = max(1, round(z.width / grid_m))
        ny = max(1, round(z.depth / grid_m))
        xs = [z.xmin + z.width * i / nx for i in range(nx + 1)]
        ys = [z.ymin + z.depth * j / ny for j in range(ny + 1)]
        b = size["mezz_beam"]
        for y in ys:
            out.append(
                Member(
                    "mezz_beam",
                    (xs[0], y, top - b.depth / 2),
                    (xs[-1], y, top - b.depth / 2),
                    b.width,
                    b.depth,
                )
            )
        for x in xs:
            out.append(
                Member(
                    "mezz_beam",
                    (x, ys[0], top - b.depth / 2),
                    (x, ys[-1], top - b.depth / 2),
                    b.width,
                    b.depth,
                )
            )
        c = size["mezz_column"]
        for x in xs[1:-1] or xs:
            for y in ys[1:-1] or ys:
                out.append(
                    Member(
                        "mezz_column",
                        (x, y, cfg.levels.ffl),
                        (x, y, top - b.depth),
                        c.width,
                        c.depth,
                    )
                )
    return out
