"""Concept MEP layout: rule-based routes, equipment and quantities per service.

Services: electrical, water supply, drainage, fire protection, refrigeration and
ventilation (HVAC), compressed air and gas. Routes follow simple, explainable
rules (trays along the hall, mains along the street strip, drains falling to the
sewer, a fire ring around the building). The result is a concept for
visualisation and quantities; MEP engineers develop the actual design.

Plan coordinates in metres (x east, y north, z height above ground).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import pairwise

from fca.concept.layout import ConceptLayout, Room

Pt = tuple[float, float, float]

SERVICES = ("electrical", "water", "drainage", "fire", "hvac", "air", "gas")
SERVICE_NAMES = {
    "electrical": "Electrical",
    "water": "Water supply",
    "drainage": "Drainage",
    "fire": "Fire protection",
    "hvac": "Refrigeration and ventilation",
    "air": "Compressed air",
    "gas": "Gas",
    "equipment": "Production equipment (sample)",
}

LUX = {
    "production": 500,
    "cold": 200,
    "storage": 200,
    "dispatch": 300,
    "office": 500,
    "amenity": 200,
    "utility": 200,
    "circulation": 150,
}
LOAD_W_M2 = {
    "production": 250,
    "cold": 120,
    "storage": 25,
    "dispatch": 40,
    "office": 60,
    "amenity": 40,
    "utility": 150,
    "circulation": 10,
}


def wet_outlets(name: str, category: str, area: float) -> int:
    """Water outlets (basins, WCs, showers, taps, sinks) a room needs, by room type."""
    n = name.lower()
    if "changing" in n or "toilet" in n:
        return max(3, math.ceil(area / 5))
    if "hygiene" in n or "hand wash" in n:
        return max(3, math.ceil(area / 3))
    if "ablution" in n:
        return max(4, math.ceil(area / 5))
    if "dining" in n or "utensil" in n:
        return 4
    if "qa" in n or "laboratory" in n:
        return 3
    if "sample" in n or "first aid" in n:
        return 1
    if category == "production":
        return max(1, math.ceil(area / 150))
    return 0


FIXTURES = ("WC", "Wash basin", "Shower", "Hand-wash station", "Ablution tap", "Sink", "Lab sink")


def fixture_kinds(name: str, category: str, n: int) -> list[str]:
    """What each water outlet in a room actually is (WC, basin, shower, sink...)."""
    low = name.lower()
    if "changing" in low or "toilet" in low:
        cycle = ["WC", "Wash basin", "Shower"]
        return [cycle[i % 3] for i in range(n)]
    if "ablution" in low:
        return ["Ablution tap"] * n
    if "dining" in low or "utensil" in low:
        return ["Sink"] * n
    if "qa" in low or "laboratory" in low or "sample" in low:
        return ["Lab sink"] * n
    if "first aid" in low:
        return ["Wash basin"] * n
    return ["Hand-wash station"] * n


FIXTURE_SIZE = {
    "WC": (0.4, 0.7, 0.8),
    "Wash basin": (0.55, 0.45, 0.2),
    "Shower": (0.9, 0.9, 0.1),
    "Hand-wash station": (0.8, 0.5, 0.9),
    "Ablution tap": (0.3, 0.3, 0.3),
    "Sink": (1.2, 0.6, 0.9),
    "Lab sink": (1.0, 0.6, 0.9),
}


def floor_drains(name: str, category: str, area: float) -> int:
    """Floor gullies a room needs, by room type."""
    n = name.lower()
    if "changing" in n or "toilet" in n:
        return max(2, math.ceil(area / 15))
    if any(
        k in n
        for k in ("hygiene", "hand wash", "ablution", "dining", "utensil", "qa", "laboratory")
    ):
        return 2
    if category == "production":
        return max(1, math.ceil(area / 60))
    if category == "dispatch":
        return max(1, math.ceil(area / 250))
    if category == "cold":
        return 1  # condensate / wash drain outside the cold room
    if any(k in n for k in ("compressor", "co2", "maintenance")):
        return max(1, math.ceil(area / 80))
    return 0


TRANSFORMERS_KVA = (315, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150)
GENERATORS_KVA = (200, 250, 400, 500, 630, 800, 1000, 1250, 1600)
UTILISATION = 0.55  # utilisation x maintenance factor for lighting counts


@dataclass
class Route:
    service: str
    kind: str
    points: list[Pt]
    size_mm: float

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in pairwise(self.points))


@dataclass
class Item:
    service: str
    kind: str
    at: Pt
    size: tuple[float, float, float] = (0.4, 0.4, 0.4)


@dataclass
class Qty:
    service: str
    description: str
    unit: str
    qty: float
    spec: str
    basis: str


@dataclass
class MepModel:
    routes: list[Route] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    quantities: list[Qty] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    machines: list = field(default_factory=list)

    def route(self, service, kind, pts, size_mm) -> Route:
        r = Route(service, kind, [tuple(round(v, 3) for v in p) for p in pts], size_mm)
        self.routes.append(r)
        return r

    def item(self, service, kind, at, size=(0.4, 0.4, 0.4)) -> None:
        self.items.append(Item(service, kind, tuple(round(v, 3) for v in at), size))

    def qty(self, service, description, unit, qty, spec, basis) -> None:
        if qty:
            self.quantities.append(Qty(service, description, unit, round(qty, 1), spec, basis))


def _centre(r: Room) -> tuple[float, float]:
    return (r.rect.xmin + r.rect.xmax) / 2, (r.rect.ymin + r.rect.ymax) / 2


def _grid(r: Room, count: int, z: float, margin: float = 1.5) -> list[Pt]:
    """Spread ``count`` points evenly over a room."""
    margin = min(margin, r.rect.width / 4, r.rect.depth / 4)  # small rooms still get fittings
    w, d = r.rect.width - 2 * margin, r.rect.depth - 2 * margin
    if count <= 0 or w <= 0 or d <= 0:
        return []
    nx = max(1, round(math.sqrt(count * w / d)))
    ny = max(1, math.ceil(count / nx))
    return [
        (r.rect.xmin + margin + w * (i + 0.5) / nx, r.rect.ymin + margin + d * (j + 0.5) / ny, z)
        for i in range(nx)
        for j in range(ny)
    ][:count]


def orthogonal(points: list[Pt]) -> list[Pt]:
    """Insert corners so a run goes along x then y, like pipes and cables on site."""
    out: list[Pt] = []
    for p in points:
        if out:
            a = out[-1]
            if abs(a[0] - p[0]) > 1e-6 and abs(a[1] - p[1]) > 1e-6:
                out.append((p[0], a[1], a[2]))
        out.append(p)
    return out


def _next(sizes: tuple[int, ...], value: float) -> int:
    return next((s for s in sizes if s >= value), sizes[-1])


def build_mep(lay: ConceptLayout, values: dict, plant_type: str) -> MepModel:
    m = MepModel()
    b, cfg = lay.building, lay.config
    ffl = cfg.levels.ffl
    eaves = min(cfg.levels.eaves_south, cfg.levels.eaves_north)
    hall_y0 = b.ymin + lay.strip_depth
    strip_mid = (b.ymin + hall_y0) / 2
    hall = [r for r in lay.rooms if r.rect.ymin >= hall_y0 - 1e-6]
    strip = [r for r in lay.rooms if r not in hall]
    util = next(
        (r for r in strip if r.name.lower().startswith("lt panel")),
        next((r for r in strip if r.category == "utility"), strip[-1]),
    )
    comp = next((r for r in strip if "compressor" in r.name.lower()), util)
    ux, _ = _centre(util)
    staff = values["staff_per_shift"]
    shifts = values["shifts_per_day"]

    # ---------------- Electrical ----------------
    supply = (ux, 0.5, 0.0)
    sub = (ux, b.ymin - 5.0, 0.0)
    gen = (ux + 6.0, b.ymin - 5.0, 0.0)
    panel = (ux, hall_y0 - 0.6, ffl + 1.2)
    m.item("electrical", "Utility supply point", (supply[0], supply[1], 0.6), (0.8, 0.5, 1.2))
    m.item("electrical", "Substation / transformer", (sub[0], sub[1], 1.25), (3.5, 3.0, 2.5))
    m.item("electrical", "Standby generator", (gen[0], gen[1], 1.2), (4.0, 1.8, 2.4))
    m.item("electrical", "Main LV switchboard", panel, (3.0, 0.8, 2.2))
    m.route(
        "electrical",
        "HV/LV duct",
        [
            (supply[0], supply[1], -0.8),
            (sub[0], sub[1], -0.8),
            (ux, b.ymin, -0.8),
            (ux, panel[1], -0.8),
        ],
        150,
    )
    tray_z = eaves - 1.6
    spine_y = hall_y0 + 1.0
    m.route(
        "electrical",
        "Cable tray (hall)",
        [(b.xmin + 1, spine_y, tray_z), (b.xmax - 1, spine_y, tray_z)],
        300,
    )
    m.route(
        "electrical",
        "Cable tray (strip)",
        [(b.xmin + 1, strip_mid, ffl + 3.2), (b.xmax - 1, strip_mid, ffl + 3.2)],
        300,
    )
    m.route(
        "electrical", "Riser to tray", [(ux, hall_y0 - 0.6, ffl + 2.3), (ux, spine_y, tray_z)], 300
    )
    feeder = 0.0
    dbs = 0
    for r in lay.rooms:
        in_hall = r in hall
        x = r.rect.xmin + 1.0
        y = r.rect.ymin + 0.35 if in_hall else r.rect.ymax - 0.35
        m.item("electrical", "Distribution board", (x, y, ffl + 1.4), (0.8, 0.3, 1.2))
        dbs += 1
        run_z = tray_z if in_hall else ffl + 3.2
        feeder += abs(x - ux) + abs(y - panel[1]) + 2 * (run_z - ffl - 1.4) + 5.0
        if in_hall:
            m.route("electrical", "Tray drop", [(x, spine_y, tray_z), (x, y, ffl + 2.0)], 150)
    light_counts = {"LED high-bay": 0, "LED panel": 0, "LED low-temperature luminaire": 0}
    for r in lay.rooms:
        in_hall = r in hall
        if r.category == "cold":
            kind, lm, z = "LED low-temperature luminaire", 8000, ffl + cfg.heights.cold_panel - 0.3
        elif in_hall:
            kind, lm, z = "LED high-bay", 20000, eaves - 2.0
        else:
            kind, lm, z = "LED panel", 4000, ffl + 3.0
        n = max(1, math.ceil(LUX[r.category] * r.area_m2 / (lm * UTILISATION)))
        light_counts[kind] += n
        for p in _grid(r, n, z, margin=1.0):
            m.item("electrical", kind, p, (0.5, 0.5, 0.15))
    load_kw = sum(LOAD_W_M2[r.category] * r.area_m2 for r in lay.rooms) / 1000
    kva = load_kw * 0.8 / 0.85
    tx = _next(TRANSFORMERS_KVA, kva)
    gx = _next(GENERATORS_KVA, kva * 0.6)
    trays = sum(
        rt.length for rt in m.routes if rt.service == "electrical" and "tray" in rt.kind.lower()
    )
    m.facts["electrical"] = {
        "connected_load_kw": round(load_kw),
        "design_kva": round(kva),
        "transformer_kva": tx,
        "generator_kva": gx,
    }
    m.qty(
        "electrical",
        f"Distribution transformer {tx} kVA",
        "nr",
        1,
        "electrical.transformer",
        f"Connected load ≈ {load_kw:,.0f} kW by zone (W/m² rules), 0.8 diversity, 0.85 pf",
    )
    m.qty(
        "electrical",
        f"Standby generator {gx} kVA",
        "nr",
        1,
        "electrical.generator",
        "Covers ~60% of design load: cold rooms, lighting, IT and critical process",
    )
    m.qty("electrical", "Main LV switchboard", "nr", 1, "electrical.main_panel", "One per plant")
    m.qty("electrical", "Distribution boards", "nr", dbs, "electrical.db", "One per zone")
    m.qty(
        "electrical",
        "Cable tray / ladder 300 mm",
        "m",
        trays,
        "electrical.cable_tray",
        "Hall spine and strip tray, drops to each board (measured)",
    )
    m.qty(
        "electrical",
        "Sub-main feeder cables",
        "m",
        feeder,
        "electrical.feeder_cable",
        "Panel to each board along trays, plus 5 m terminations (measured)",
    )
    m.qty(
        "electrical",
        "Incoming HV/LV cable duct",
        "m",
        next(rt.length for rt in m.routes if rt.kind == "HV/LV duct"),
        "electrical.feeder_cable",
        "Street supply point to substation and main switchboard (measured)",
    )
    for kind, n in light_counts.items():
        spec = {
            "LED high-bay": "electrical.light_highbay",
            "LED panel": "electrical.light_panel",
            "LED low-temperature luminaire": "electrical.light_cold",
        }[kind]
        m.qty(
            "electrical",
            kind.replace("luminaire", "").strip() + " luminaires",
            "nr",
            n,
            spec,
            "Lux targets per zone (production 500, offices 500, stores 200) at UF×MF 0.55",
        )

    # ---------------- Water supply ----------------
    inlet = (b.xmin + 3.0, 0.5, 0.0)
    tank_at = (max(2.5, b.xmin - 3.5), b.ymin - 4.0, 0.0)
    pump_at = (tank_at[0], b.ymin - 1.5, 0.0)
    tank_m3 = 60 * staff * shifts * 2 / 1000
    if values.get("output_tonnes_per_day"):
        tank_m3 += values["output_tonnes_per_day"] * 1.0 * 2
    tank_m3 = max(20, math.ceil(tank_m3 / 5) * 5)
    m.item("water", "Water inlet and meter", (inlet[0], inlet[1], 0.5), (0.8, 0.5, 1.0))
    m.item("water", "Water tank", (tank_at[0], tank_at[1], 1.0), (4.0, 3.0, 2.0))
    m.item("water", "Booster pump set", (pump_at[0], pump_at[1], 0.6), (1.6, 1.0, 1.2))
    m.route(
        "water",
        "Incoming main",
        [(inlet[0], inlet[1], -0.8), (inlet[0], tank_at[1], -0.8), (tank_at[0], tank_at[1], -0.8)],
        63,
    )
    main_z = ffl + 3.4
    m.route(
        "water",
        "Distribution main",
        [
            (pump_at[0], pump_at[1], 0.5),
            (pump_at[0], strip_mid, 0.5),
            (b.xmin, strip_mid, 0.5),
            (b.xmin, strip_mid, main_z),
            (b.xmax - 2, strip_mid, main_z),
        ],
        63,
    )
    outlets = 0
    for r in lay.rooms:
        cx, cy = _centre(r)
        n = wet_outlets(r.name, r.category, r.area_m2)
        if not n:
            continue
        outlets += n
        top = eaves - 2.4 if r in hall else main_z
        raw = sorted(_grid(r, n, ffl + 0.9, margin=0.8), key=lambda q: (round(q[1], 1), q[0]))
        rows: dict[float, list[Pt]] = {}
        for q in raw:
            rows.setdefault(round(q[1], 1), []).append(q)
        pts = [
            q
            for i, (_, row) in enumerate(sorted(rows.items()))
            for q in (row if i % 2 == 0 else row[::-1])
        ]  # serpentine through the rows
        # Tee off the main, drop into the room, then run past every outlet in turn.
        chain = [(cx, strip_mid, main_z), (cx, cy, top)]
        if pts:
            chain += [(pts[0][0], pts[0][1], top)]
            chain += [(q[0], q[1], ffl + 1.1) for q in pts]
        m.route("water", "Cold water branch", orthogonal(chain), 32)
        for q, kind in zip(pts, fixture_kinds(r.name, r.category, len(pts)), strict=True):
            w, d, h = FIXTURE_SIZE[kind]
            z = (
                ffl + 0.05
                if kind == "Shower"
                else ffl + (0.9 if kind in ("Wash basin", "Ablution tap") else h / 2)
            )
            m.item("water", kind, (q[0], q[1], z), (w, d, h))
    pipes = sum(rt.length for rt in m.routes if rt.service == "water")
    m.facts["water"] = {"tank_m3": tank_m3, "outlets": outlets}
    m.qty(
        "water",
        f"Water storage tank {tank_m3} m³",
        "nr",
        1,
        "plumbing.tank",
        f"60 L/person/day × {staff} staff × {shifts} shifts × 2 days"
        + (" + process water 1 m³/t × 2 days" if values.get("output_tonnes_per_day") else ""),
    )
    m.qty("water", "Booster pump set (duty/standby)", "nr", 1, "plumbing.pump", "One per plant")
    m.qty(
        "water",
        "Water pipework (PP-R), mains 63 mm and branches 32 mm",
        "m",
        pipes,
        "plumbing.pipe",
        "Measured along routes",
    )

    # ---------------- Drainage ----------------
    main_y = b.ymin - 2.0
    hall_col_y = (hall_y0 + b.ymax) / 2
    sewer = (b.xmax - 3.0, 0.5)
    drains = 0
    branch_len = 0.0
    for r in lay.rooms:
        n = floor_drains(r.name, r.category, r.area_m2)
        if not n:
            continue
        pts = _grid(r, n, ffl + 0.02, margin=1.2)
        drains += len(pts)
        for x, y, _ in pts:
            m.item("drainage", "Floor gully", (x, y, ffl + 0.03), (0.3, 0.3, 0.06))
            target = hall_col_y if r in hall else main_y
            m.route("drainage", "Branch", [(x, y, -0.4), (x, target, -0.6)], 100)
            branch_len += abs(y - target)
    m.route(
        "drainage",
        "Hall collector",
        [(b.xmin + 2, hall_col_y, -0.7), (b.xmax - 2, hall_col_y, -0.9)],
        150,
    )
    for f in (0.33, 0.66):
        x = b.xmin + b.width * f
        m.route("drainage", "Lateral", [(x, hall_col_y, -0.9), (x, main_y, -1.1)], 150)
    main = m.route(
        "drainage",
        "Main sewer",
        [(b.xmin - 2, main_y, -0.9), (sewer[0], main_y, -1.3), (sewer[0], sewer[1], -1.5)],
        200 if drains > 40 else 150,
    )
    chambers = max(2, math.ceil(main.length / 30)) + 2
    for i in range(chambers - 2):
        m.item(
            "drainage",
            "Inspection chamber",
            (b.xmin + (sewer[0] - b.xmin) * (i + 0.5) / (chambers - 2), main_y, -0.2),
            (1.0, 1.0, 0.4),
        )
    m.item("drainage", "Grease interceptor", (sewer[0] - 4, main_y - 1.5, -0.2), (2.5, 1.5, 0.4))
    m.item("drainage", "Sewer connection", (sewer[0], sewer[1], -0.2), (1.0, 1.0, 0.4))
    by_size = {}
    for rt in m.routes:
        if rt.service == "drainage":
            by_size[rt.size_mm] = by_size.get(rt.size_mm, 0) + rt.length
    m.facts["drainage"] = {"gullies": drains, "chambers": chambers}
    m.qty(
        "drainage",
        "Stainless steel hygienic floor gullies",
        "nr",
        drains,
        "drainage.floor_drain",
        "Production 1 per 60 m², changing 1 per 15 m², hygiene/ablution/dining/lab 2 each, "
        "dispatch 1 per 250 m², cold rooms 1 each",
    )
    for size, length in sorted(by_size.items()):
        m.qty(
            "drainage",
            f"Underground drainage pipe {size:.0f} mm",
            "m",
            length,
            "drainage.pipe",
            "Measured along routes; falls 1:80 to sewer",
        )
    m.qty(
        "drainage",
        "Inspection chambers",
        "nr",
        chambers,
        "drainage.chamber",
        "Every 30 m on the main and at junctions",
    )
    m.qty(
        "drainage", "Grease interceptor", "nr", 1, "drainage.grease_trap", "Before sewer connection"
    )

    # ---------------- Fire protection ----------------
    off = 6.0
    ring = [
        (max(1, b.xmin - off), max(1, b.ymin - off)),
        (min(lay.plot.xmax - 1, b.xmax + off), max(1, b.ymin - off)),
        (min(lay.plot.xmax - 1, b.xmax + off), min(lay.plot.ymax - 1, b.ymax + off)),
        (max(1, b.xmin - off), min(lay.plot.ymax - 1, b.ymax + off)),
    ]
    ring_route = m.route(
        "fire", "Hydrant ring main", [(x, y, -0.9) for x, y in ring + ring[:1]], 150
    )
    hydrants = max(4, math.ceil(ring_route.length / 45))
    pts = ring + ring[:1]
    seg_lengths = [math.dist(a, c) for a, c in pairwise(pts)]
    for k in range(hydrants):
        d = ring_route.length * k / hydrants
        for (a, c), L in zip(pairwise(pts), seg_lengths, strict=True):
            if d <= L:
                t = d / L
                m.item(
                    "fire",
                    "Hydrant",
                    (a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t, 0.5),
                    (0.35, 0.35, 1.0),
                )
                break
            d -= L
    fire_at = (min(lay.plot.xmax - 3, b.xmax + 7), b.ymin - 4.0)
    m.item("fire", "Fire water tank", (fire_at[0], fire_at[1], 1.5), (6.0, 4.0, 3.0))
    m.item("fire", "Fire pump room", (fire_at[0], fire_at[1] + 4.0, 1.4), (4.0, 3.0, 2.8))
    sprinklers = 0
    for r in lay.rooms:
        if r.category in ("storage", "dispatch"):
            n = math.ceil(r.area_m2 / 12)
            sprinklers += n
            for p in _grid(r, n, eaves - 1.0, margin=1.0):
                m.item("fire", "Sprinkler", p, (0.15, 0.15, 0.15))
    detectors = sum(math.ceil(r.area_m2 / 60) for r in lay.rooms)
    fire_m3 = math.ceil((1900 * 60 + (260 * 7.5 * 60 if sprinklers else 0)) / 1000 / 10) * 10
    m.facts["fire"] = {"tank_m3": fire_m3, "hydrants": hydrants, "sprinklers": sprinklers}
    m.qty(
        "fire",
        f"Fire water tank {fire_m3} m³",
        "nr",
        1,
        "fire.tank",
        "Hydrants 1,900 L/min × 60 min + sprinklers 7.5 mm/min over 260 m² × 60 min; "
        "verify with Civil Defense",
    )
    m.qty("fire", "Fire pump set (electric, diesel, jockey)", "nr", 1, "fire.pump", "One per plant")
    m.qty(
        "fire",
        "Underground hydrant ring main 150 mm",
        "m",
        ring_route.length,
        "fire.ring_main",
        "6 m outside the building line (measured)",
    )
    m.qty("fire", "Pillar hydrants", "nr", hydrants, "fire.hydrant", "Every 45 m along the ring")
    m.qty(
        "fire",
        "Sprinkler heads in stores and dispatch",
        "nr",
        sprinklers,
        "fire.sprinkler",
        "1 per 12 m² in storage and dispatch zones",
    )
    m.qty("fire", "Fire alarm detectors", "nr", detectors, "fire.detector", "1 per 60 m² of floor")

    # ---------------- Refrigeration and ventilation ----------------
    cold_kw = 0.0
    evaps = 0
    fans = 0
    for r in lay.rooms:
        cx, cy = _centre(r)
        if r.category == "cold":
            t = r.temp_c if r.temp_c is not None else 2
            w_m2 = 300 if t <= -30 else 90 if t <= -10 else 50
            kw = r.area_m2 * w_m2 / 1000
            cold_kw += kw
            unit = (cx, b.ymax + 2.5, 0.9)
            m.item("hvac", "Condensing unit", unit, (3.0, 1.2, 1.8))
            n = max(1, math.ceil(r.area_m2 / 60))
            evaps += n
            ez = ffl + cfg.heights.cold_panel - 0.6
            for p in _grid(r, n, ez, margin=1.0):
                m.item("hvac", "Evaporator", (p[0], r.rect.ymax - 0.8, ez), (1.8, 0.7, 0.6))
            m.route(
                "hvac",
                "Refrigerant pipework",
                [
                    (cx, b.ymax + 2.0, 1.5),
                    (cx, b.ymax + 0.5, ez + 0.5),
                    (cx, r.rect.ymax - 0.8, ez + 0.5),
                ],
                42,
            )
        elif r.category == "production":
            n = max(1, math.ceil(r.area_m2 / 150))
            fans += n
            from fca.model.building import roof_height

            for p in _grid(r, n, 0, margin=2.0):
                m.item(
                    "hvac",
                    "Roof extract fan",
                    (p[0], p[1], roof_height(cfg, p[1]) + 0.5),
                    (1.2, 1.2, 0.9),
                )
    if cold_kw:
        m.facts["hvac"] = {"refrigeration_kw": round(cold_kw)}
        m.qty(
            "hvac",
            f"Condensing units (total ≈ {cold_kw:,.0f} kW refrigeration)",
            "nr",
            sum(1 for r in lay.rooms if r.category == "cold"),
            "hvac.condensing_unit",
            "One per cold room; load 50 W/m² chill, 90 W/m² frozen, 300 W/m² blast",
        )
        m.qty(
            "hvac",
            "Evaporator unit coolers",
            "nr",
            evaps,
            "hvac.evaporator",
            "1 per 60 m² of cold room",
        )
        m.qty(
            "hvac",
            "Refrigerant pipework",
            "m",
            sum(rt.length for rt in m.routes if rt.service == "hvac") * 2,
            "hvac.condensing_unit",
            "Suction and liquid lines along routes (measured × 2)",
        )
    m.qty(
        "hvac",
        "Roof extract fans over production",
        "nr",
        fans,
        "hvac.extract_fan",
        "1 per 150 m² of production for oven heat",
    )

    # ---------------- Compressed air ----------------
    prod = [r for r in hall if r.category == "production"]
    if prod:
        x0 = min(r.rect.xmin for r in prod) + 1
        x1 = max(r.rect.xmax for r in prod) - 1
        z = eaves - 2.6
        m.item(
            "air",
            "Air compressor and dryer",
            (_centre(comp)[0], _centre(comp)[1], ffl + 0.9),
            (2.2, 1.2, 1.8),
        )
        m.route(
            "air",
            "Air ring main",
            [
                (x0, hall_y0 + 2, z),
                (x1, hall_y0 + 2, z),
                (x1, b.ymax - 2, z),
                (x0, b.ymax - 2, z),
                (x0, hall_y0 + 2, z),
            ],
            40,
        )
        m.route(
            "air",
            "Air feeder",
            [
                (_centre(comp)[0], _centre(comp)[1], ffl + 2.0),
                (_centre(comp)[0], hall_y0 + 2, z),
                (x1, hall_y0 + 2, z),
            ],
            40,
        )
        air_len = sum(rt.length for rt in m.routes if rt.service == "air")
        m.qty(
            "air", "Air compressor with dryer", "nr", 1, "air.compressor", "Duty unit in utilities"
        )
        m.qty(
            "air",
            "Compressed-air ring main 40 mm",
            "m",
            air_len,
            "air.pipe",
            "Around production, packaging and cooling (measured)",
        )

    # ---------------- Gas ----------------
    ovens = [r for r in hall if r.name.lower().startswith("production")]
    if ovens and plant_type in ("industrial", "retail"):
        p = ovens[0]
        cx, cy = _centre(p)
        tank = (max(2.5, b.xmin - 4.0), cy, 0.0)
        m.item("gas", "LPG tank (underground)", (tank[0], tank[1], 0.3), (2.0, 5.0, 0.6))
        gr = m.route(
            "gas",
            "Gas pipe",
            [
                (tank[0], tank[1], -0.6),
                (b.xmin, cy, -0.6),
                (b.xmin, cy, eaves - 3.0),
                (cx, cy, eaves - 3.0),
            ],
            50,
        )
        m.qty("gas", "Underground LPG tank with vaporiser", "nr", 1, "gas.tank", "For oven burners")
        m.qty(
            "gas", "Gas pipework 50 mm", "m", gr.length, "gas.pipe", "Tank to production (measured)"
        )

    from fca.concept.routing import add_detailed_routes

    add_detailed_routes(m, lay, values, plant_type)
    return m
