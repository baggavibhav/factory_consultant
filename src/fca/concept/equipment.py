"""Sample production equipment: an indicative line of typical machines per production line.

This is a visual sample so management can picture the plant and see how services reach
the machines. Machine types, sizes and positions are typical examples, not a process
design, and equipment is not included in the BOQ (it is normally owner-supplied).
"""

from __future__ import annotations

from dataclasses import dataclass

from fca.concept.layout import ConceptLayout, Room

# name, length (along the line), width, height, needs (power, water, air, gas, extract)
BAKERY_PRODUCTION = [
    ("Spiral mixer", 2.2, 1.6, 1.8, {"water"}),
    ("Divider-rounder", 2.6, 1.3, 1.8, set()),
    ("Intermediate proofer", 4.0, 2.2, 2.5, set()),
    ("Moulder", 2.2, 1.2, 1.5, set()),
    ("Final proofer", 8.0, 3.0, 3.0, {"water"}),
    ("Tunnel oven", 18.0, 2.6, 2.2, {"gas", "extract"}),
]
BAKERY_COOLING = [("Spiral cooler", 6.0, 6.0, 4.0, set())]
BAKERY_PACKING = [
    ("Slicer", 2.6, 1.3, 1.7, {"air"}),
    ("Metal detector", 1.6, 1.0, 1.3, set()),
    ("Bagger", 3.2, 1.4, 1.9, {"air"}),
    ("Case packer", 3.0, 2.2, 2.2, {"air"}),
]
EGG_LINE = [
    ("Egg loader", 3.0, 2.0, 1.6, {"air"}),
    ("Egg washer and dryer", 4.5, 2.0, 1.8, {"water"}),
    ("Candling booth", 2.0, 2.0, 2.0, set()),
    ("Egg grader", 9.0, 3.0, 1.9, {"air"}),
    ("Egg packer", 4.0, 2.2, 1.8, {"air"}),
]
GAP = 1.4  # clear space between machines along the line
MARGIN = 2.5  # clear space at each end of a room


@dataclass
class Machine:
    name: str
    line: int
    future: bool
    x0: float
    x1: float
    y: float
    width: float
    height: float
    needs: set

    @property
    def x(self) -> float:
        return (self.x0 + self.x1) / 2


def _room(lay: ConceptLayout, *starts: str) -> Room | None:
    return next((r for r in lay.rooms if r.name.lower().startswith(starts)), None)


def _place(room: Room, spec: list, line: int, lines: int, future: bool) -> list[Machine]:
    q = room.rect
    pitch = q.depth / lines
    y = q.ymin + pitch * (line + 0.5)
    avail = q.width - 2 * MARGIN
    need = sum(s[1] for s in spec) + GAP * (len(spec) - 1)
    scale = min(1.0, max(0.35, (avail - GAP * (len(spec) - 1)) / max(sum(s[1] for s in spec), 0.1)))
    out, x = [], q.xmin + MARGIN + max(0.0, (avail - need) / 2) * (1 if scale >= 1 else 0)
    for name, length, width, height, needs in spec:
        ln = length * scale
        w = min(width, pitch * 0.7)
        out.append(Machine(name, line, future, x, x + ln, y, w, height, needs))
        x += ln + GAP
    return out


def sample_equipment(lay: ConceptLayout, values: dict, plant_type: str) -> list[Machine]:
    now, fut = values["lines_now"], values["lines_future"]
    total = now + fut
    if total <= 0:
        return []
    machines: list[Machine] = []
    for k in range(total):
        future = k >= now
        if plant_type == "egg_station":
            room = _room(lay, "grading")
            if room:
                machines += _place(room, EGG_LINE, k, total, future)
            continue
        prod = _room(lay, "production area")
        if prod:
            spec = [list(s) for s in BAKERY_PRODUCTION]
            if plant_type == "retail":
                spec[-1][1] = 9.0  # smaller oven
            machines += _place(prod, [tuple(s) for s in spec], k, total, future)
        cool = _room(lay, "cooling")
        if cool and "packing" in cool.name.lower():  # retail: cooling and packing share a room
            side = min(4.0, cool.rect.depth / total * 0.7)
            machines += _place(
                cool, [("Spiral cooler", side, side, 3.5, set()), *BAKERY_PACKING], k, total, future
            )
            continue
        if cool:
            side = min(6.0, cool.rect.width - 2 * MARGIN + 1, cool.rect.depth / total * 0.8)
            machines += _place(
                cool,
                [("Spiral cooler", max(side, 2.0), max(side, 2.0), 4.0, set())],
                k,
                total,
                future,
            )
        pack = _room(lay, "packaging", "cooling and packing")
        if pack and pack is not cool:
            machines += _place(pack, BAKERY_PACKING, k, total, future)
    return machines
