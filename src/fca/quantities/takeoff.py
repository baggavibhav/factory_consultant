"""Quantity takeoff from the plant model: every quantity is measured from the model
or derived by a stated rule, and carries its specification and basis.

Drawing mode: walls are drawn as two face lines, so wall and panel lengths are
halved to approximate the wall centreline; room-based items (finishes, MEP)
need room outlines and are not measured yet.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from fca.model.building import BuildingConfig, roof_height
from fca.model.schema import BBox, Category, Segment
from fca.model3d.build import ModelBuilder
from fca.settings import PROJECT_ROOT
from fca.structure.frame import Member

SPEC_FILE = PROJECT_ROOT / "config" / "specs" / "default.toml"

SECTIONS = [
    "Substructure",
    "Structural steel frame",
    "Building envelope",
    "Internal walls, cold rooms and mezzanine",
    "Floor finishes",
    "External works",
    "Electrical",
    "Water supply",
    "Drainage",
    "Fire protection",
    "Refrigeration and ventilation",
    "Compressed air",
    "Gas",
]
MEP_SECTION = {
    "electrical": "Electrical",
    "water": "Water supply",
    "drainage": "Drainage",
    "fire": "Fire protection",
    "hvac": "Refrigeration and ventilation",
    "air": "Compressed air",
    "gas": "Gas",
}
MEMBER_LABEL = {
    "column": "Portal frame columns",
    "gable_column": "Gable wind columns",
    "rafter": "Portal frame rafters",
    "eave_beam": "Eave beams / ties",
    "purlin": "Roof purlins",
    "girt": "Wall girts",
    "bracing": "Roof and wall bracing",
}


@dataclass
class BoqItem:
    section: str
    description: str
    unit: str
    qty: float
    spec: str
    basis: str
    material: str = ""  # BOM grouping key
    waste: float = 0.0  # BOM waste / cutting allowance


def load_specs(path: Path | None = None) -> dict:
    return tomllib.loads(Path(path or SPEC_FILE).read_text(encoding="utf-8"))


def spec_text(specs: dict, key: str) -> str:
    node = specs
    for part in key.split("."):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, str) else ""


def takeoff(
    cfg: BuildingConfig,
    members: list[Member],
    segments: list[Segment],
    mode: str,
    rooms: list | None = None,
    mep=None,
    plot: BBox | None = None,
    specs: dict | None = None,
) -> list[BoqItem]:
    specs = specs or load_specs()
    sp = lambda key: spec_text(specs, key)  # noqa: E731
    items: list[BoqItem] = []

    def add(section, desc, unit, qty, spec, basis, material="", waste=0.0):
        if qty and qty > 0:
            items.append(BoqItem(section, desc, unit, round(qty, 2), spec, basis, material, waste))

    env, lv = cfg.envelope, cfg.levels
    area = env.width * env.depth
    face = 0.5 if mode == "drawing" else 1.0

    # ---- Substructure --------------------------------------------------------
    pads = [m for m in members if m.kind == "foundation"]
    if pads:
        size, thick = pads[0].width, abs(pads[0].end[2] - pads[0].start[2])
        conc = len(pads) * size * size * thick
        add(
            "Substructure",
            f"Excavate for pad foundations ({len(pads)} nr)",
            "m³",
            len(pads) * (size + 0.6) ** 2 * (thick + 0.6),
            "Excavation in any material, trimming, disposal off site, backfill with selected fill",
            "Pad plan size + 300 mm working space each side, depth to 0.6 m below pad",
        )
        add(
            "Substructure",
            "Blinding under pads, 75 mm",
            "m²",
            len(pads) * size * size,
            sp("concrete.blinding"),
            "Pad plan area",
            "Concrete C15 (blinding)",
            0.05,
        )
        add(
            "Substructure",
            f"Pad foundations {size:.1f} × {size:.1f} × {thick:.1f} m",
            "m³",
            conc,
            sp("concrete.foundations"),
            f"{len(pads)} pads under every column (measured)",
            "Concrete C32/40 SRC (foundations)",
            0.05,
        )
        add(
            "Substructure",
            "Reinforcement to pad foundations",
            "kg",
            conc * specs["concrete"]["rebar_kg_per_m3_pads"],
            sp("concrete.rebar"),
            f"{specs['concrete']['rebar_kg_per_m3_pads']} kg/m³ of pad concrete (allowance)",
            "Reinforcement bar",
            0.05,
        )
    add(
        "Substructure",
        "Ground-bearing floor slab, 200 mm",
        "m³",
        area * 0.2,
        sp("concrete.slab"),
        f"Building footprint {area:,.0f} m² × 0.2 m",
        "Concrete C30/37 (slab)",
        0.05,
    )
    add(
        "Substructure",
        "Slab reinforcement mesh, two layers",
        "m²",
        area * 2,
        sp("concrete.mesh"),
        "Footprint × 2 layers",
        "Welded mesh A393",
        0.10,
    )
    add(
        "Substructure",
        "Damp-proof membrane under slab",
        "m²",
        area,
        sp("concrete.dpm"),
        "Footprint",
        "DPM 1000-gauge",
        0.10,
    )

    # ---- Steel frame --------------------------------------------------------
    profiles = specs["steel"]["profiles"]
    main_t = 0.0
    for kind, label in MEMBER_LABEL.items():
        mm = [m for m in members if m.kind == kind]
        if not mm:
            continue
        section, kg_m = profiles[kind]
        length = sum(m.length for m in mm)
        tonnes = length * kg_m / 1000
        secondary = kind in ("purlin", "girt", "bracing")
        if not secondary:
            main_t += tonnes
        add(
            "Structural steel frame",
            f"{label}, {section} (indicative)",
            "t",
            tonnes,
            sp("steel.secondary") if secondary else sp("steel.grade"),
            f"{len(mm)} nr, {length:,.0f} m × {kg_m} kg/m (measured length, indicative section)",
            f"Steel {section}",
            0.03,
        )
    add(
        "Structural steel frame",
        "Connections, base plates, bolts and fittings",
        "t",
        main_t * specs["steel"]["connection_allowance"],
        sp("steel.bolts"),
        f"{specs['steel']['connection_allowance']:.0%} of main frame tonnage (allowance)",
        "Steel plates and bolts",
        0.0,
    )

    # ---- Envelope ------------------------------------------------------------
    h0, hr, h1 = (roof_height(cfg, y) for y in (env.ymin, cfg.ridge_y, env.ymax))
    s1 = math.hypot(cfg.ridge_y - env.ymin, hr - h0)
    s2 = math.hypot(env.ymax - cfg.ridge_y, hr - h1)
    add(
        "Building envelope",
        "Insulated roof panels",
        "m²",
        env.width * (s1 + s2),
        sp("envelope.roof"),
        "Sloped roof area over the building footprint (measured)",
        "Roof sandwich panel PIR 100",
        0.05,
    )
    cold_rects = [r.rect for r in (rooms or []) if r.category == "cold"]

    def on_cold_edge(s: Segment) -> float:
        """Length of an axis-aligned wall that coincides with a cold-room outline."""
        total = 0.0
        for q in cold_rects:
            if abs(s.y1 - s.y2) < 1e-6 and any(abs(s.y1 - e) < 0.02 for e in (q.ymin, q.ymax)):
                lo, hi = sorted((s.x1, s.x2))
                total += max(0.0, min(hi, q.xmax) - max(lo, q.xmin))
            elif abs(s.x1 - s.x2) < 1e-6 and any(abs(s.x1 - e) < 0.02 for e in (q.xmin, q.xmax)):
                lo, hi = sorted((s.y1, s.y2))
                total += max(0.0, min(hi, q.ymax) - max(lo, q.ymin))
        return min(total, s.length)

    builder = ModelBuilder(cfg)
    wall_area = {"walls_external": 0.0, "low": 0.0, "high": 0.0, "cold_panels": 0.0}
    for s in segments:
        if s.category == Category.BOUNDARY:
            continue
        name, z0, ta, tb = builder.classify(s, env, cfg.heights, lv.ffl)
        a = s.length * ((ta + tb) / 2 - z0)
        if name == "walls_external":
            wall_area["walls_external"] += a * face
        elif name == "cold_panels":
            wall_area["cold_panels"] += a * face
        elif name == "walls_internal":
            low = max(ta, tb) <= lv.ffl + cfg.heights.internal_low + 0.01
            share = (
                1 - on_cold_edge(s) / s.length if cold_rects else 1.0
            )  # panels listed separately
            wall_area["low" if low else "high"] += a * face * share
    add(
        "Building envelope",
        "Insulated wall cladding panels",
        "m²",
        wall_area["walls_external"],
        sp("envelope.walls"),
        "External wall length × height to eaves (measured; openings not deducted)",
        "Wall sandwich panel PIR 80",
        0.05,
    )
    add(
        "Building envelope",
        "Ridge, eave and verge flashings",
        "m",
        env.width * 3 + 2 * (s1 + s2),
        sp("envelope.flashing"),
        "Ridge + two eaves + two verges",
        "Flashings",
        0.10,
    )
    add(
        "Building envelope",
        "Eave gutters",
        "m",
        env.width * 2,
        sp("envelope.gutters"),
        "Both eaves",
        "Gutters",
        0.05,
    )
    add(
        "Building envelope",
        "Rainwater downpipes",
        "nr",
        math.ceil(env.width * 2 / 15),
        sp("envelope.downpipes"),
        "One per 15 m of gutter",
        "Downpipes 150 mm",
    )

    # ---- Internal ------------------------------------------------------------
    sec = "Internal walls, cold rooms and mezzanine"
    add(
        sec,
        "Full-height hygienic partitions",
        "m²",
        wall_area["high"],
        sp("internal.partition_high"),
        "Internal wall length × height (measured)",
        "Partition sandwich panel PIR 80",
        0.05,
    )
    add(
        sec,
        "Office and amenity partitions",
        "m²",
        wall_area["low"],
        sp("internal.partition_low"),
        "Internal wall length × height (measured)",
        "Blockwork / partitions",
        0.05,
    )
    if rooms:
        for r in [r for r in rooms if r.category == "cold"]:
            t = r.temp_c if r.temp_c is not None else 2
            key = (
                "cold_panel_blast"
                if t <= -30
                else "cold_panel_freezer"
                if t <= -10
                else "cold_panel_chill"
            )
            perim = 2 * (r.rect.width + r.rect.depth)
            add(
                sec,
                f"{r.name}: insulated walls and ceiling",
                "m²",
                perim * cfg.heights.cold_panel + r.area_m2,
                sp(f"internal.{key}"),
                f"Perimeter {perim:,.0f} m × {cfg.heights.cold_panel:.1f} m"
                f" + ceiling {r.area_m2:,.0f} m²",
                f"Cold-room panel ({key.split('_')[-1]})",
                0.05,
            )
            if t <= -10:
                add(
                    sec,
                    f"{r.name}: insulated heated floor",
                    "m²",
                    r.area_m2,
                    sp("internal.freezer_floor"),
                    "Room area",
                    "Freezer floor build-up",
                    0.05,
                )
    else:
        add(
            sec,
            "Insulated cold-room panels (walls)",
            "m²",
            wall_area["cold_panels"],
            sp("internal.cold_panel_freezer"),
            "Panel length × height, face lines halved (measured from drawing)",
            "Cold-room panel",
            0.05,
        )
    for z in cfg.mezzanine_zones:
        add(
            sec,
            "Mezzanine floor",
            "m²",
            z.width * z.depth,
            sp("internal.mezzanine"),
            "Mezzanine zone area",
            "Composite deck mezzanine",
            0.05,
        )

    # ---- Finishes --------------------------------------------------------------
    if rooms:
        by_cat: dict[str, float] = {}
        for r in rooms:
            by_cat[r.category] = by_cat.get(r.category, 0) + r.area_m2
        names = {
            "production": "Production, cooling and packaging floors",
            "storage": "Store floors",
            "cold": "Cold-room floor finish",
            "dispatch": "Dispatch floors",
            "office": "Office and lab floors",
            "amenity": "Changing, dining and prayer floors",
            "utility": "Plant room floors",
        }
        for cat, a in by_cat.items():
            add(
                "Floor finishes",
                names.get(cat, cat),
                "m²",
                a,
                sp(f"finishes.{cat}"),
                "Zone areas from the layout",
                f"Floor finish ({cat})",
                0.05,
            )

    # ---- External works -------------------------------------------------------
    if plot:
        add(
            "External works",
            "Boundary wall, 2.4 m",
            "m",
            2 * (plot.width + plot.depth),
            "Blockwork or precast boundary wall with gates",
            "Plot perimeter",
            "Boundary wall",
            0.02,
        )
        add(
            "External works",
            "Yard paving and roads",
            "m²",
            plot.width * plot.depth - area,
            "Asphalt roads and interlocking pavers on sub-base",
            "Plot area minus building (allowance; landscaping not deducted)",
            "Paving",
            0.05,
        )

    # ---- MEP ---------------------------------------------------------------------
    if mep:
        for q in mep.quantities:
            add(
                MEP_SECTION[q.service],
                q.description,
                q.unit,
                q.qty,
                sp(q.spec),
                q.basis,
                q.description if q.unit != "nr" else "",
                0.10 if q.unit == "m" else 0.0,
            )
    items.sort(key=lambda i: SECTIONS.index(i.section))
    return items


def bill_of_materials(items: list[BoqItem]) -> list[dict]:
    """Group BOQ items by material with a waste allowance for ordering."""
    groups: dict[tuple[str, str], dict] = {}
    for it in items:
        key = (it.material or it.description, it.unit)
        g = groups.setdefault(
            key,
            {
                "material": key[0],
                "unit": it.unit,
                "qty": 0.0,
                "waste": it.waste,
                "spec": it.spec,
                "section": it.section,
            },
        )
        g["qty"] += it.qty
    return [{**g, "qty": round(g["qty"], 2)} for g in groups.values()]


def as_dicts(items: list[BoqItem]) -> list[dict]:
    return [asdict(i) for i in items]
