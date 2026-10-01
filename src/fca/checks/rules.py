"""Design checks: find problems in a plant plan automatically.

Each check is a deterministic rule on the plan (rooms, openings, site) and the build
facts (span, bays, levels). A finding says what is wrong, where, why it matters and
what to do; when the fix is a design option of a concept project it also carries
the change, so the app can build a variant and show before and after.

Checks support engineers; they are not a code-compliance certificate.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from shapely.geometry import Point, Polygon

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "info": 3}
EXIT_TRAVEL_LIMIT_M = 45.0  # conservative typical limit; confirm with Civil Defense
TRAVEL_FACTOR = 1.2  # travel distance ≈ 1.2 × straight line through corridors and aisles


@dataclass
class Finding:
    id: str
    severity: str  # critical, major, minor, info
    area: str  # site, fire, hygiene, layout, structure, services
    title: str
    detail: str
    suggestion: str
    at: list[float] | None = None  # plan x, y to highlight
    fix: dict | None = None  # brief changes for a concept variant
    fix_label: str | None = None
    refs: list[str] = field(default_factory=list)


def _poly(room: dict) -> Polygon:
    return Polygon(room["points"])


def _touch(a: Polygon, b: Polygon, min_len: float = 1.0) -> bool:
    """True when two rooms share at least ``min_len`` metres of wall."""
    shared = a.buffer(0.15).intersection(b.buffer(0.15))
    return shared.area / 0.3 >= min_len


def _named(rooms: list[dict], *words: str) -> list[dict]:
    return [r for r in rooms if any(w in r["name"].lower() for w in words)]


def run_checks(plan: dict, facts: dict, mode: str) -> list[Finding]:
    out: list[Finding] = []
    rooms = plan.get("rooms", [])
    x0, y0, x1, y1 = plan["building"]
    px0, _, px1, _ = plan["plot"]
    openings = plan.get("openings", [])
    concept = mode == "concept"

    def add(*args, **kw):
        out.append(Finding(*args, **kw))

    # ---------------- Site ----------------
    for w in facts.get("warnings", []):
        if "does not fit" in w:
            add(
                "site.plot_fit",
                "major",
                "site",
                "Requested area does not fit the plot",
                w,
                "Enlarge the plot, reduce yards or consider a mezzanine or second floor.",
            )
    if concept:
        west, east = x0 - px0, px1 - x1
        need_in, need_out = facts.get("site_minimums", [15.0, 30.0])
        if west < need_in:
            add(
                "site.goods_in_yard",
                "major",
                "site",
                "Goods-in yard too small for trucks",
                f"The yard beside the raw-material docks is {west:.0f} m deep; delivery trucks "
                f"for this plant type need at least {need_in:.0f} m.",
                f"Widen the goods-in yard to at least {need_in:.0f} m.",
                [x0 - west / 2, (y0 + y1) / 2],
                {"goods_in_yard_m": round(need_in + 5)},
                f"Widen goods-in yard to {need_in + 5:.0f} m",
            )
        if east < need_out:
            add(
                "site.dispatch_apron",
                "major",
                "site",
                "Dispatch apron too shallow",
                f"The apron in front of the dispatch docks is {east:.0f} m deep; trucks for this "
                f"plant type need at least {need_out:.0f} m to turn and reverse onto a dock.",
                f"Deepen the dispatch apron to at least {need_out:.0f} m.",
                [x1 + east / 2, (y0 + y1) / 2],
                {"dispatch_yard_m": round(need_out + 5)},
                f"Deepen dispatch apron to {need_out + 5:.0f} m",
            )
    docks = [o for o in openings if o["kind"].startswith("dock")]
    if concept and not any(o["kind"] == "dock_out" for o in docks):
        add(
            "site.no_dispatch_docks",
            "major",
            "site",
            "No dispatch docks",
            "Finished goods have no loading dock.",
            "Add dock doors on the dispatch side.",
        )

    # ---------------- Fire ----------------
    exits = [
        (o["x"], o["y"])
        for o in openings
        if o["kind"] in ("fire_exit", "entrance", "dock_out", "dock_in")
    ]
    if exits:
        worst = None
        for r in rooms:
            if r["category"] == "circulation":
                continue
            for x, y in r["points"]:
                d = min(math.dist((x, y), e) for e in exits) * TRAVEL_FACTOR
                if worst is None or d > worst[0]:
                    worst = (d, r["name"], (x, y))
        if worst and worst[0] > EXIT_TRAVEL_LIMIT_M:
            add(
                "fire.travel_distance",
                "major",
                "fire",
                "Long escape distance",
                f"From the far corner of {worst[1]} the estimated travel distance to an exit is "
                f"{worst[0]:.0f} m (limit used: {EXIT_TRAVEL_LIMIT_M:.0f} m).",
                "Add an exit door nearer this area; confirm the permitted distance with Civil "
                "Defense for the occupancy and sprinkler status.",
                list(worst[2]),
            )
    elif rooms:
        add(
            "fire.exits_unknown",
            "info",
            "fire",
            "Exit doors not checked",
            "Doors are not read from this drawing yet, so escape distances cannot be checked.",
            "Check exit positions against the travel-distance limit manually.",
        )
    footprint = facts.get("footprint_m2") or (x1 - x0) * (y1 - y0)
    sprinkler_rooms = {r["name"] for r in rooms if r["category"] in ("storage", "dispatch")}
    if footprint > 4000:
        add(
            "fire.compartment",
            "minor",
            "fire",
            "Large single fire compartment",
            f"About {footprint:,.0f} m² under one roof with sprinklers only in "
            f"{', '.join(sorted(sprinkler_rooms)) or 'stores'}.",
            "Confirm compartment limits with Civil Defense; options are fire walls between "
            "zones or sprinklers throughout.",
        )

    # ---------------- Hygiene ----------------
    polys = [(r, _poly(r)) for r in rooms]
    production = [(r, p) for r, p in polys if r["category"] == "production"]
    hygiene = [(r, p) for r, p in polys if "hygiene" in r["name"].lower()]
    if production and not hygiene:
        add(
            "hygiene.no_station",
            "critical",
            "hygiene",
            "No hygiene station",
            "Staff can reach production without a hand-wash and boot-wash station.",
            "Add a hygiene station at every staff entry to production.",
        )
    elif (
        production
        and hygiene
        and not any(_touch(hp, pp) for _, hp in hygiene for _, pp in production)
    ):
        r0 = hygiene[0][0]
        c = hygiene[0][1].centroid
        add(
            "hygiene.station_not_at_entry",
            "major",
            "hygiene",
            "Hygiene station is not at the production entry",
            f"{r0['name']} does not open directly onto a production zone, so staff could "
            "bypass it.",
            "Place the hygiene stations where staff enter production.",
            [c.x, c.y],
        )
    for r, p in polys:
        n = r["name"].lower()
        toilet = "toilet" in n or "tol" in n.replace(".", " ").split()
        if not concept and toilet and any(_touch(p, pp, 1.5) for _, pp in production):
            # Concept layouts open wet rooms onto the corridor; drawings need their doors checked.
            c = p.centroid
            add(
                f"hygiene.toilet_next_to_production.{len(out)}",
                "minor",
                "hygiene",
                "Check toilet doors next to production",
                f"{r['name']} shares a wall with a production zone. Toilets must never open "
                "directly into a food area.",
                "Confirm the doors open only onto a lobby or corridor.",
                [c.x, c.y],
            )
    raw = [(r, p) for r, p in polys if r["name"].lower().startswith(("rm store", "egg receiving"))]
    post = [(r, p) for r, p in polys if any(k in r["name"].lower() for k in ("packag", "cooling"))]
    for ra, pa in raw:
        for rb, pb in post:
            if _touch(pa, pb):
                c = pa.intersection(pb.buffer(0.3)).centroid
                add(
                    "hygiene.raw_next_to_finished",
                    "major",
                    "hygiene",
                    "Raw materials next to finished product",
                    f"{ra['name']} adjoins {rb['name']}: raw and post-bake areas should be "
                    "separated to avoid contamination.",
                    "Keep raw-material stores on the mixing side of the process.",
                    [c.x, c.y],
                )

    # ---------------- Layout ----------------
    cold = [(r, p) for r, p in polys if r["category"] == "cold"]
    dispatch = [(r, p) for r, p in polys if r["category"] == "dispatch"]
    if cold and dispatch:
        far = [r for r, p in cold if min(p.distance(dp) for _, dp in dispatch) > 3]
        if far:
            add(
                "layout.cold_far_from_dispatch",
                "minor",
                "layout",
                "Cold room away from dispatch",
                f"{', '.join(r['name'] for r in far)} is not next to dispatch, so frozen and "
                "chilled goods travel further through ambient areas.",
                "Place cold rooms beside the dispatch zone.",
            )
    required = [("changing", "Changing rooms"), ("first aid", "First aid room")]
    for word, label in required:
        if production and not _named(rooms, word):
            add(
                f"layout.missing.{word.replace(' ', '_')}",
                "major",
                "layout",
                f"{label} missing",
                f"No room named like '{label.lower()}' was found.",
                f"Add {label.lower()}.",
            )
    if production and not _named(rooms, "prayer"):
        add(
            "layout.missing.prayer",
            "minor",
            "layout",
            "No prayer room",
            "Gulf plants normally provide prayer rooms with ablution for staff.",
            "Add prayer rooms with ablution (separate for men and women where needed).",
        )
    lines = facts.get("lines")
    prod_area = sum(r["area_m2"] for r in rooms if r["name"].lower().startswith("production"))
    if lines and prod_area and prod_area / lines < 350:
        add(
            "layout.production_tight",
            "major",
            "layout",
            "Production space tight per line",
            f"About {prod_area / lines:,.0f} m² of production per line.",
            "Increase the production zone or the built-up area.",
            None,
            {"zone_sizes": {"Production area": 1.3}},
            "Enlarge production by 30%",
        )

    # ---------------- Structure ----------------
    span = facts.get("span_m") or 0
    two_span = "internal_column" in (facts.get("member_schedule") or {})
    eff = span / 2 if two_span else span
    if eff > 45:
        add(
            "structure.span_too_long",
            "major",
            "structure",
            "Span beyond economic range",
            f"Clear span of {eff:.0f} m needs very heavy frames.",
            "Add an internal column line or make the building narrower.",
            None,
            {"structure_option": "two_span"},
            "Add internal column line",
        )
    elif eff > 36 and concept:
        add(
            "structure.span_heavy",
            "minor",
            "structure",
            "Long clear span",
            f"A {eff:.0f} m clear span keeps production free of columns but uses more steel.",
            "Compare with an internal column line, which usually saves steel.",
            None,
            {"structure_option": "two_span"},
            "Try an internal column line",
        )
    bays = facts.get("bays_m") or []
    if bays and max(bays) > 10:
        add(
            "structure.bay_long",
            "minor",
            "structure",
            "Long bays",
            f"Bays up to {max(bays):.1f} m need heavy purlins and girts.",
            "Use bays of about 7.5–9 m.",
            None,
            {"bay_m": 9},
            "Use 9 m bays",
        )

    # ---------------- Services ----------------
    if concept:
        drains = [(i["x"], i["y"]) for i in plan.get("items", []) if i["kind"] == "Floor gully"]
        for r, p in polys:
            n = r["name"].lower()
            wet = (
                any(k in n for k in ("changing", "hygiene", "ablution"))
                or r["category"] == "production"
            )
            if wet and not any(p.buffer(0.2).contains(Point(d)) for d in drains):
                c = p.centroid
                add(
                    f"services.no_drain.{len(out)}",
                    "major",
                    "services",
                    "Wet room without drainage",
                    f"{r['name']} has no floor gully.",
                    "Add floor gullies falling to drain.",
                    [c.x, c.y],
                )

    out.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.area, f.title))
    return out


def as_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]


def summary(findings: list[Finding]) -> dict[str, int]:
    s = {k: 0 for k in SEVERITY_ORDER}
    for f in findings:
        s[f.severity] += 1
    return s
