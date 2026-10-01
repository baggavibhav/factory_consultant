"""Detailed concept routing: how each service reaches every fitting.

Adds, on top of the mains in ``fca.concept.mep``:
- electrical: lighting circuits along each row of luminaires, socket circuits
  around rooms, power drops to each production line, the fire alarm loop;
- water: hot water from point-of-use heaters to the outlets that need it;
- fire: sprinkler range pipes, cross mains and the feed main from the pump room;
- ventilation: production supply air ducts with diffusers, toilet/changing extract,
  ducted air conditioning to offices;
- compressed air drops and gas branches to each line.

Everything is measured, so cable, pipe and duct quantities come from the routes.
Rules are concept-level and stated in each quantity's basis.
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import pairwise

from fca.concept.layout import ConceptLayout, Room
from fca.concept.mep import FIXTURES, MepModel, Pt, orthogonal
from fca.model.building import roof_height

WET_HOT = ("changing", "hygiene", "dining", "utensil", "ablution", "hand wash")
WET_EXTRACT = ("changing", "toilet", "ablution", "hygiene")


def _inside(r: Room, x: float, y: float, pad: float = 0.5) -> bool:
    q = r.rect
    return q.xmin - pad <= x <= q.xmax + pad and q.ymin - pad <= y <= q.ymax + pad


def _rows(points: list[Pt], tol: float = 0.3) -> list[list[Pt]]:
    """Group points into rows of equal y, each sorted west to east."""
    rows: list[list[Pt]] = []
    for p in sorted(points, key=lambda q: (q[1], q[0])):
        if rows and abs(rows[-1][0][1] - p[1]) <= tol:
            rows[-1].append(p)
        else:
            rows.append([p])
    return [sorted(r, key=lambda q: q[0]) for r in rows]


def _nearest_path(start: Pt, points: list[Pt]) -> list[Pt]:
    """Visit all points, always going to the nearest unvisited one (loop cabling)."""
    left, path, cur = list(points), [], start
    while left:
        nxt = min(left, key=lambda q: math.dist(q[:2], cur[:2]))
        path.append(nxt)
        left.remove(nxt)
        cur = nxt
    return path


def add_detailed_routes(m: MepModel, lay: ConceptLayout, values: dict, plant_type: str) -> None:
    b, cfg = lay.building, lay.config
    ffl = cfg.levels.ffl
    eaves = min(cfg.levels.eaves_south, cfg.levels.eaves_north)
    hall_y0 = b.ymin + lay.strip_depth
    hall = [r for r in lay.rooms if r.rect.ymin >= hall_y0 - 1e-6]
    strip = [r for r in lay.rooms if r not in hall]

    def room_of(x: float, y: float, pad: float = 0.5) -> Room | None:
        return next((r for r in lay.rooms if _inside(r, x, y, pad)), None)

    boards = {}
    for it in m.items:
        if it.kind == "Distribution board":
            r = room_of(it.at[0], it.at[1], pad=0.0)  # boards sit just inside their own room
            if r is not None:
                boards[id(r)] = it.at

    # ---------------- Lighting circuits ----------------
    lights = defaultdict(list)
    for it in m.items:
        if it.service == "electrical" and it.kind.startswith("LED"):
            r = room_of(it.at[0], it.at[1], pad=0.1)
            if r is not None:
                lights[id(r)].append(it.at)
    rooms_by_id = {id(r): r for r in lay.rooms}
    lighting_len = 0.0
    circuits = 0
    for rid, pts in lights.items():
        db = boards.get(rid)
        if db is None:
            continue
        for row in _rows(pts):
            z = row[0][2] + 0.25
            path = [db, (db[0], db[1], z), (db[0], row[0][1], z), *[(p[0], p[1], z) for p in row]]
            lighting_len += m.route("electrical", "Lighting circuit", path, 20).length
            circuits += 1

    # ---------------- Small power (socket circuits) ----------------
    spacing = {
        "office": 6.0,
        "amenity": 10.0,
        "utility": 8.0,
        "production": 12.0,
        "storage": 20.0,
        "dispatch": 15.0,
    }
    sockets = 0
    power_len = 0.0
    for r in lay.rooms:
        step = spacing.get(r.category)
        db = boards.get(id(r))
        if step is None or db is None:
            continue
        q, inset, z = r.rect, 0.15, ffl + 0.4
        ring = [
            (q.xmin + inset, q.ymin + inset),
            (q.xmax - inset, q.ymin + inset),
            (q.xmax - inset, q.ymax - inset),
            (q.xmin + inset, q.ymax - inset),
            (q.xmin + inset, q.ymin + inset),
        ]
        perim = 2 * (q.width + q.depth)
        n = max(2, math.ceil(perim / step))
        # Socket positions spaced evenly around the room.
        seg = [math.dist(a, c) for a, c in pairwise(ring)]
        for k in range(n):
            d = perim * (k + 0.5) / n
            for (a, c), length in zip(pairwise(ring), seg, strict=True):
                if d <= length:
                    t = d / length
                    m.item(
                        "electrical",
                        "Socket outlet",
                        (a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t, z),
                        (0.2, 0.2, 0.15),
                    )
                    break
                d -= length
        sockets += n
        path = orthogonal([db, (db[0], db[1], z), *[(x, y, z) for x, y in ring]])
        power_len += m.route("electrical", "Socket circuit", path, 25).length

    # ---------------- Process power to production lines ----------------
    lines = values["lines_now"] + values["lines_future"]
    prod = next(
        (r for r in hall if r.name.lower().startswith("production")),
        next((r for r in hall if r.category == "production"), None),
    )
    process_len = 0.0
    line_points: list[tuple[float, float]] = []
    if prod and lines:
        q = prod.rect
        tray_z = eaves - 1.6
        spine_y = hall_y0 + 1.0
        for k in range(lines):
            y = q.ymin + q.depth * (k + 0.5) / lines
            x = q.xmin + q.width * 0.5
            line_points.append((x, y))
            future = k >= values["lines_now"]
            m.item(
                "electrical",
                "Line control panel (future)" if future else "Line control panel",
                (q.xmin + 2.0, y, ffl + 1.0),
                (1.2, 0.5, 2.0),
            )
            lv = next((it.at for it in m.items if it.kind == "Main LV switchboard"), None)
            start = [lv, (lv[0], lv[1], ffl + 2.3), (lv[0], spine_y, tray_z)] if lv else []
            path = [
                *start,
                (q.xmin + 2.0, spine_y, tray_z),
                (q.xmin + 2.0, y, tray_z),
                (q.xmin + 2.0, y, ffl + 2.0),
            ]
            process_len += m.route("electrical", "Process power feeder", path, 60).length

    # ---------------- Sample production equipment and its connections ----------------
    from fca.concept.equipment import sample_equipment

    machines = sample_equipment(lay, values, plant_type)
    m.machines = machines
    by_line: dict[int, list] = defaultdict(list)
    for mc in machines:
        svc = "equipment_future" if mc.future else "equipment"
        m.item(
            svc, mc.name, (mc.x, mc.y, ffl + mc.height / 2), (mc.x1 - mc.x0, mc.width, mc.height)
        )
        by_line[mc.line].append(mc)
    main_z = ffl + 3.4
    strip_mid = b.ymin + lay.strip_depth / 2
    ring_z = next((rt.points[0][2] for rt in m.routes if rt.kind == "Air ring main"), eaves - 2.6)
    machine_power = 0.0
    water_points = air_points = hoods = 0
    for mcs in by_line.values():
        mcs.sort(key=lambda mc: mc.x0)
        for a, c in pairwise(mcs):  # conveyors between machines
            if c.x0 - a.x1 > 0.2:
                if abs(a.y - c.y) < 0.05:
                    m.item(
                        "equipment_future" if a.future else "equipment",
                        "Conveyor",
                        ((a.x1 + c.x0) / 2, a.y, ffl + 0.9),
                        (c.x0 - a.x1, 0.6, 0.15),
                    )
                else:
                    xm = (a.x1 + c.x0) / 2
                    svc = "equipment_future" if a.future else "equipment"
                    m.item(
                        svc, "Conveyor", ((a.x1 + xm) / 2, a.y, ffl + 0.9), (xm - a.x1, 0.6, 0.15)
                    )
                    m.item(
                        svc,
                        "Conveyor",
                        (xm, (a.y + c.y) / 2, ffl + 0.9),
                        (0.6, abs(c.y - a.y) + 0.6, 0.15),
                    )
                    m.item(
                        svc, "Conveyor", ((xm + c.x0) / 2, c.y, ffl + 0.9), (c.x0 - xm, 0.6, 0.15)
                    )
        if mcs[0].future:
            continue
        # Power: from the line panel along the line at high level, with a drop to each machine.
        panel = next(
            (
                it.at
                for it in m.items
                if it.kind == "Line control panel" and abs(it.at[1] - mcs[0].y) < 0.6
            ),
            None,
        )
        zp = ffl + 4.4
        if panel:
            path = [(panel[0], panel[1], ffl + 2.0), (panel[0], panel[1], zp)]
            path += [(mc.x, mc.y, zp) for mc in mcs]
            machine_power += m.route("electrical", "Machine power", orthogonal(path), 30).length
            for mc in mcs:
                machine_power += m.route(
                    "electrical",
                    "Machine drop",
                    [(mc.x, mc.y, zp), (mc.x, mc.y, ffl + mc.height + 0.1)],
                    20,
                ).length
        for mc in mcs:
            top = ffl + mc.height + 0.1
            if "water" in mc.needs:
                m.route(
                    "water",
                    "Process water to machine",
                    orthogonal(
                        [(mc.x, strip_mid, main_z), (mc.x, mc.y, main_z), (mc.x, mc.y, top)]
                    ),
                    25,
                )
                water_points += 1
            if "air" in mc.needs:
                m.route(
                    "air",
                    "Air to machine",
                    orthogonal(
                        [(mc.x, hall_y0 + 2, ring_z), (mc.x, mc.y, ring_z), (mc.x, mc.y, top)]
                    ),
                    20,
                )
                air_points += 1
            if "extract" in mc.needs:
                hood_z = ffl + mc.height + 0.9
                m.item(
                    "hvac",
                    "Oven extract hood",
                    (mc.x, mc.y, hood_z),
                    ((mc.x1 - mc.x0) * 0.6, mc.width + 0.6, 0.6),
                )
                roof = roof_height(cfg, mc.y)
                m.route(
                    "hvac",
                    "Oven extract duct",
                    [(mc.x, mc.y, hood_z + 0.3), (mc.x, mc.y, roof + 0.4)],
                    500,
                )
                m.item("hvac", "Oven exhaust fan (roof)", (mc.x, mc.y, roof + 0.8), (1.2, 1.2, 0.9))
                hoods += 1
    m.facts["equipment"] = {
        "machines": sum(1 for mc in machines if not mc.future),
        "future_machines": sum(1 for mc in machines if mc.future),
    }

    # ---------------- Fire alarm loop ----------------
    panel_room = next((r for r in strip if r.name.lower().startswith("reception")), strip[0])
    fap = (panel_room.rect.xmin + 1.0, panel_room.rect.ymax - 0.5, ffl + 1.5)
    m.item("fire", "Fire alarm control panel", fap, (0.6, 0.25, 0.8))
    detectors: list[Pt] = []
    for r in lay.rooms:
        n = math.ceil(r.area_m2 / 60)
        z = (eaves - 0.8) if r in hall else ffl + 3.2
        q = r.rect
        nx = max(1, round(math.sqrt(n * q.width / max(q.depth, 0.1))))
        ny = max(1, math.ceil(n / nx))
        grid = [
            (q.xmin + q.width * (i + 0.5) / nx, q.ymin + q.depth * (j + 0.5) / ny, z)
            for i in range(nx)
            for j in range(ny)
        ][:n]
        for p in grid:
            detectors.append(p)
            m.item("fire", "Fire detector", p, (0.2, 0.2, 0.1))
    loop = orthogonal([fap, *_nearest_path(fap, detectors), fap])
    fa_len = m.route("fire", "Fire alarm loop", loop, 15).length

    # ---------------- Hot water ----------------
    heaters = 0
    hot_len = 0.0
    for r in lay.rooms:
        if not any(k in r.name.lower() for k in WET_HOT):
            continue
        outs = [
            it.at for it in m.items if it.kind in FIXTURES and _inside(r, it.at[0], it.at[1], 0.1)
        ]
        if not outs:
            continue
        heater = (r.rect.xmin + 0.6, r.rect.ymax - 0.6, ffl + 2.0)
        m.item("water", "Water heater", heater, (0.6, 0.6, 0.9))
        heaters += 1
        chain = orthogonal(
            [heater, *[(p[0], p[1] + 0.15, ffl + 1.2) for p in _nearest_path(heater, outs)]]
        )
        hot_len += m.route("water", "Hot water", chain, 20).length

    # ---------------- Sprinkler pipework ----------------
    heads = defaultdict(list)
    for it in m.items:
        if it.kind == "Sprinkler":
            r = room_of(it.at[0], it.at[1], pad=0.1)
            if r is not None:
                heads[id(r)].append(it.at)
    pump = next(
        (it.at for it in m.items if it.kind == "Fire pump room"), (b.xmax + 7, b.ymin - 4, 0)
    )
    feed_y = b.ymax - 1.5
    feed_z = eaves - 0.5
    sprinkler_len = 0.0
    if heads:
        xs = [rooms_by_id[rid].rect.xmin + 1.0 for rid in heads]
        feed = [
            (pump[0], pump[1], 0.5),
            (b.xmax, pump[1] + 4, 0.5),
            (b.xmax, feed_y, 0.5),
            (b.xmax, feed_y, feed_z),
            (min(xs), feed_y, feed_z),
        ]
        sprinkler_len += m.route("fire", "Sprinkler feed main", orthogonal(feed), 100).length
        for rid, pts in heads.items():
            r = rooms_by_id[rid]
            x0 = r.rect.xmin + 1.0
            rows = _rows(pts)
            cross = [(x0, feed_y, feed_z), (x0, rows[0][0][1], feed_z)] if rows else []
            if rows:
                cross.append((x0, rows[-1][0][1], feed_z))
                sprinkler_len += m.route("fire", "Sprinkler cross main", cross, 65).length
            for row in rows:
                path = [(x0, row[0][1], feed_z), *[(p[0], p[1], p[2] + 0.2) for p in row]]
                sprinkler_len += m.route("fire", "Sprinkler range pipe", path, 32).length

    # ---------------- Ventilation and air conditioning ----------------
    duct = {"supply": 0.0, "extract": 0.0, "ac": 0.0}  # duct surface area, m²
    diffusers = 0
    ahus = 0
    ac_units = 0
    for r in hall:
        if r.category != "production":
            continue
        q = r.rect
        y = (q.ymin + q.ymax) / 2
        z = eaves - 2.0
        roof = roof_height(cfg, y)
        ahu = (q.xmin + 2.5, y, roof + 1.0)
        m.item("hvac", "Air handling unit (roof)", ahu, (3.5, 2.0, 1.8))
        ahus += 1
        path = [ahu, (ahu[0], y, z), (q.xmax - 1.5, y, z)]
        w = 0.8
        rt = m.route("hvac", "Supply air duct", path, w * 1000)
        duct["supply"] += rt.length * 3 * w
        for k in range(max(1, int((q.width - 4) // 6))):
            m.item("hvac", "Supply diffuser", (q.xmin + 4 + 6 * k, y, z - 0.45), (0.6, 0.6, 0.15))
            diffusers += 1
    wet = [r for r in strip if any(k in r.name.lower() for k in WET_EXTRACT)]
    if wet:
        y = sum((r.rect.ymin + r.rect.ymax) / 2 for r in wet) / len(wet)
        z = ffl + 3.3
        x0 = min(r.rect.xmin for r in wet) + 1
        x1 = max(r.rect.xmax for r in wet) - 1
        fan = (x1, y, roof_height(cfg, y) + 0.6)
        m.item("hvac", "Toilet extract fan (roof)", fan, (1.0, 1.0, 0.8))
        rt = m.route("hvac", "Extract duct", [(x0, y, z), (x1, y, z), fan], 400)
        duct["extract"] += rt.length * 3 * 0.4
        for r in wet:
            cx = (r.rect.xmin + r.rect.xmax) / 2
            m.item("hvac", "Extract grille", (cx, y, z - 0.25), (0.4, 0.4, 0.1))
            diffusers += 1
    for r in strip:
        if r.category != "office":
            continue
        q = r.rect
        y = (q.ymin + q.ymax) / 2
        z = ffl + 3.1
        unit = (q.xmin + 1.0, y, z)
        m.item("hvac", "Ducted AC indoor unit", unit, (1.2, 0.7, 0.35))
        m.item(
            "hvac",
            "AC outdoor unit (roof)",
            (q.xmin + 1.0, y, roof_height(cfg, y) + 0.6),
            (1.0, 0.5, 0.9),
        )
        ac_units += 1
        rt = m.route("hvac", "AC supply duct", [unit, (q.xmax - 0.8, y, z)], 300)
        duct["ac"] += rt.length * 3 * 0.3
        for k in range(max(1, math.ceil(r.area_m2 / 15))):
            x = q.xmin + q.width * (k + 0.5) / max(1, math.ceil(r.area_m2 / 15))
            m.item("hvac", "AC diffuser", (x, y, z - 0.2), (0.5, 0.5, 0.1))
            diffusers += 1

    # ---------------- Compressed air drops and gas branches ----------------
    ring = next((rt for rt in m.routes if rt.kind == "Air ring main"), None)
    drops = 0
    if ring and line_points:
        z = ring.points[0][2]
        for x, y in line_points:
            m.route("air", "Air drop", [(x, y, z), (x, y, ffl + 1.5)], 25)
            m.item("air", "Filter-regulator drop", (x, y, ffl + 1.4), (0.3, 0.3, 0.4))
            drops += 1
    gas = next((rt for rt in m.routes if rt.kind == "Gas pipe"), None)
    trains = 0
    if gas and prod and line_points:
        q = prod.rect
        hz = gas.points[-1][2]
        ox = q.xmax - 4.0  # ovens towards the cooling end of each line
        header = [(gas.points[-1][0], gas.points[-1][1], hz), (ox, gas.points[-1][1], hz)]
        m.route("gas", "Gas header", header, 50)
        for _, y in line_points:
            m.route(
                "gas",
                "Gas branch to oven",
                [(ox, header[-1][1], hz), (ox, y, hz), (ox, y, ffl + 1.2)],
                32,
            )
            m.item("gas", "Oven gas valve train", (ox, y, ffl + 1.1), (0.6, 0.3, 0.5))
            trains += 1

    # ---------------- Devices: switches, boxes, isolators, safety equipment ----------------
    switches = jboxes = isolators = 0
    for r in lay.rooms:
        q = r.rect
        in_hall = r in hall
        south_row = not in_hall and q.ymin <= b.ymin + 1e-6
        y = q.ymin + 0.15 if in_hall else (q.ymax - 0.12 if south_row else q.ymin + 0.12)
        x = q.xmin + (1.5 if in_hall else 0.6)
        m.item("electrical", "Light switch", (x, y, ffl + 1.2), (0.09, 0.04, 0.09))
        top = (eaves - 1.8) if in_hall else ffl + 3.0
        m.route("electrical", "Switch drop", [(x, y, ffl + 1.25), (x, y, top)], 20)
        switches += 1
    for rt in [r for r in m.routes if r.kind == "Lighting circuit"]:
        p = rt.points[2] if len(rt.points) > 2 else rt.points[-1]
        m.item("electrical", "Junction box", p, (0.15, 0.15, 0.1))
        jboxes += 1
    for mc in machines:
        if not mc.future:
            m.item(
                "electrical",
                "Local isolator",
                (mc.x0 - 0.3, mc.y + mc.width / 2 + 0.25, ffl + 1.3),
                (0.2, 0.15, 0.3),
            )
            isolators += 1
    inward = {"north": (0, -0.35), "south": (0, 0.35), "west": (0.35, 0), "east": (-0.35, 0)}
    exits = [o for o in lay.openings if o.kind in ("fire_exit", "entrance")]
    signs = calls = extinguishers = reels = 0
    for k, o in enumerate(exits):
        dx, dy = inward[o.side]
        along = (1.2, 0) if o.side in ("north", "south") else (0, 1.2)
        m.item("fire", "Exit sign", (o.x + dx, o.y + dy, ffl + 2.5), (0.35, 0.06, 0.16))
        m.item(
            "fire",
            "Manual call point",
            (o.x + dx + along[0], o.y + dy + along[1], ffl + 1.4),
            (0.1, 0.06, 0.1),
        )
        m.item(
            "fire",
            "Fire extinguisher",
            (o.x + dx - along[0], o.y + dy - along[1], ffl + 0.35),
            (0.2, 0.2, 0.6),
        )
        signs += 1
        calls += 1
        extinguishers += 1
        if o.kind == "fire_exit" and k % 2 == 0:
            m.item(
                "fire",
                "Fire hose reel",
                (o.x + dx + 2.5 * along[0] / 1.2, o.y + dy + 2.5 * along[1] / 1.2, ffl + 1.3),
                (0.7, 0.25, 0.7),
            )
            reels += 1
    sounders = 0
    for d in detectors[:: max(1, 7)]:  # about one sounder per seven detectors
        m.item("fire", "Alarm sounder", (d[0] + 0.5, d[1], d[2]), (0.15, 0.15, 0.1))
        sounders += 1
    fixture_count: dict[str, int] = defaultdict(int)
    for it in m.items:
        if it.kind in FIXTURES:
            fixture_count[it.kind] += 1

    # ---------------- Quantities ----------------
    m.facts.setdefault("electrical", {}).update({"lighting_circuits": circuits, "sockets": sockets})
    m.qty(
        "electrical",
        "Lighting circuits, 3 × 2.5 mm² in containment",
        "m",
        lighting_len,
        "electrical.lighting_cable",
        f"{circuits} circuits, one per row of luminaires (measured)",
    )
    m.qty(
        "electrical",
        "Socket circuits, 3 × 4 mm² in containment",
        "m",
        power_len,
        "electrical.small_power_cable",
        "Ring around each room from its board (measured)",
    )
    m.qty(
        "electrical",
        "Socket outlets (twin, IP rated where needed)",
        "nr",
        sockets,
        "electrical.socket",
        "Offices every 6 m of wall, amenities 10 m, plant rooms 8 m, "
        "production 12 m, stores 20 m, dispatch 15 m",
    )
    if process_len:
        m.qty(
            "electrical",
            "Process power feeders to production lines",
            "m",
            process_len,
            "electrical.process_cable",
            f"{lines} lines including future, main LV board to each line panel (measured)",
        )
        m.qty(
            "electrical",
            "Line control panels / isolators",
            "nr",
            lines,
            "electrical.isolator",
            "One per production line",
        )
    m.qty("fire", "Fire alarm control panel", "nr", 1, "fire.panel", "At reception")
    m.qty(
        "fire",
        "Fire alarm loop cable",
        "m",
        fa_len,
        "fire.alarm_cable",
        "Loop through every detector and back (measured)",
    )
    m.qty(
        "fire",
        "Sprinkler pipework (feed, cross mains, ranges)",
        "m",
        sprinkler_len,
        "fire.sprinkler_pipe",
        "Measured along routes to every head",
    )
    m.qty(
        "water",
        "Point-of-use water heaters",
        "nr",
        heaters,
        "plumbing.heater",
        "One per changing, hygiene, ablution, dining and wash room",
    )
    m.qty(
        "water",
        "Hot water pipework 20 mm",
        "m",
        hot_len,
        "plumbing.pipe",
        "Heater to each outlet (measured)",
    )
    m.qty(
        "hvac",
        "Air handling units for production",
        "nr",
        ahus,
        "hvac.ahu",
        "One per production zone, roof mounted",
    )
    m.qty(
        "hvac",
        "Supply air ductwork (galvanised)",
        "m²",
        duct["supply"],
        "hvac.duct",
        "Duct length × perimeter (measured)",
    )
    m.qty(
        "hvac",
        "Extract ductwork (galvanised)",
        "m²",
        duct["extract"],
        "hvac.duct",
        "Toilet, changing and ablution extract (measured)",
    )
    m.qty(
        "hvac",
        "AC ductwork (insulated)",
        "m²",
        duct["ac"],
        "hvac.duct",
        "Office ducted AC (measured)",
    )
    m.qty(
        "hvac",
        "Ducted AC units (indoor + outdoor)",
        "nr",
        ac_units,
        "hvac.ac_unit",
        "One per office room",
    )
    m.qty(
        "hvac",
        "Diffusers and grilles",
        "nr",
        diffusers,
        "hvac.diffuser",
        "Supply every 6 m in production, 1 per 15 m² in offices, 1 extract per wet room",
    )
    m.qty(
        "air",
        "Compressed-air drops with filter-regulators",
        "nr",
        drops,
        "air.drop",
        "One per production line",
    )
    m.qty("gas", "Oven gas valve trains", "nr", trains, "gas.valve_train", "One per line")
    m.qty(
        "electrical",
        "Light switches",
        "nr",
        switches,
        "electrical.socket",
        "One per room at the entry",
    )
    m.qty(
        "electrical",
        "Junction boxes",
        "nr",
        jboxes,
        "electrical.lighting_cable",
        "One per lighting circuit",
    )
    m.qty(
        "electrical",
        "Local isolators at machines",
        "nr",
        isolators,
        "electrical.isolator",
        "One per machine in the sample layout",
    )
    m.qty("fire", "Emergency exit signs", "nr", signs, "fire.detector", "One at each exit")
    m.qty("fire", "Manual call points", "nr", calls, "fire.detector", "One beside each exit")
    m.qty(
        "fire", "Fire extinguishers", "nr", extinguishers, "fire.detector", "One beside each exit"
    )
    m.qty("fire", "Fire hose reels", "nr", reels, "fire.hydrant", "At alternate exits")
    m.qty(
        "fire", "Alarm sounders", "nr", sounders, "fire.detector", "About one per seven detectors"
    )
    for kind, n in sorted(fixture_count.items()):
        m.qty(
            "water",
            f"{kind}s" if not kind.endswith("h") else f"{kind}es",
            "nr",
            n,
            "plumbing.outlet",
            "Placed per room type (breakdown of sanitary outlets)",
        )
    basis = "Connections to the sample machine layout (machines themselves are not included)"
    m.qty(
        "electrical",
        "Machine power cabling and drops",
        "m",
        machine_power,
        "electrical.process_cable",
        basis,
    )
    m.qty(
        "water",
        "Process water connections to machines",
        "nr",
        water_points,
        "plumbing.outlet",
        basis + "; mixers and proofer humidifiers",
    )
    m.qty("air", "Compressed-air connections to machines", "nr", air_points, "air.drop", basis)
    m.qty(
        "hvac",
        "Oven extract hoods, ducts and roof fans",
        "nr",
        hoods,
        "hvac.extract_fan",
        basis + "; one per oven",
    )
