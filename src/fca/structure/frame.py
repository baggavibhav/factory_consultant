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

KINDS = ("foundation", "column", "gable_column", "rafter", "eave_beam", "purlin", "girt", "bracing")


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

    # Cross bracing in the end bays: roof planes and both side walls.
    if s.brace_end_bays and len(layout.frame_x) >= 2:
        fx = layout.frame_x
        for xa, xb in {(fx[0], fx[1]), (fx[-2], fx[-1])}:
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
