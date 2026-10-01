"""Differences between two plans, for highlighting changes in the compare view."""

from __future__ import annotations

import math


def _key(o: dict) -> tuple:
    return (o["kind"], round(o["x"], 0), round(o["y"], 0))


def plan_diff(before: dict, after: dict) -> dict:
    """Rooms, openings and columns added, removed or resized between two plans."""
    b_rooms = {r["name"]: r for r in before.get("rooms", [])}
    a_rooms = {r["name"]: r for r in after.get("rooms", [])}
    resized = []
    for name, r in a_rooms.items():
        if name in b_rooms:
            old = b_rooms[name]["area_m2"]
            if old and abs(r["area_m2"] - old) / old > 0.02:
                resized.append(
                    {"name": name, "before": old, "after": r["area_m2"], "points": r["points"]}
                )
    added = [
        {"name": n, "points": r["points"], "area_m2": r["area_m2"]}
        for n, r in a_rooms.items()
        if n not in b_rooms
    ]
    removed = [
        {"name": n, "points": r["points"], "area_m2": r["area_m2"]}
        for n, r in b_rooms.items()
        if n not in a_rooms
    ]
    bb, ab = before["building"], after["building"]
    # If the building only moved on the plot, compare everything relative to it,
    # so a shift is reported once instead of every door and column "changing".
    same_size = math.isclose(bb[2] - bb[0], ab[2] - ab[0], abs_tol=0.05) and math.isclose(
        bb[3] - bb[1], ab[3] - ab[1], abs_tol=0.05
    )
    dx, dy = (ab[0] - bb[0], ab[1] - bb[1]) if same_size else (0.0, 0.0)

    def shifted(o: dict) -> dict:
        return {**o, "x": o["x"] - dx, "y": o["y"] - dy}

    b_open = {_key(o): o for o in before.get("openings", [])}
    a_open = {_key(shifted(o)): o for o in after.get("openings", [])}
    b_cols = {(round(x, 1), round(y, 1)) for x, y in before.get("columns", [])}
    a_map = {(round(x - dx, 1), round(y - dy, 1)): (x, y) for x, y in after.get("columns", [])}
    a_cols = set(a_map)
    return {
        "building_before": bb,
        "building_after": ab,
        "building_changed": any(
            not math.isclose(p, q, abs_tol=0.05) for p, q in zip(bb, ab, strict=True)
        ),
        "rooms_added": added,
        "rooms_removed": removed,
        "rooms_resized": resized,
        "openings_added": [a_open[k] for k in a_open.keys() - b_open.keys()],
        "openings_removed": [b_open[k] for k in b_open.keys() - a_open.keys()],
        "moved_m": [round(dx, 2), round(dy, 2)] if (abs(dx) > 0.05 or abs(dy) > 0.05) else None,
        "columns_added": sorted(a_map[k] for k in a_cols - b_cols),
        "columns_removed": sorted(b_cols - a_cols),
    }
