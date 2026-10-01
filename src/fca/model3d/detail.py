"""Detailed MEP geometry for the 3D model: services the way they look on site.

Pipes are round with joints at bends, couplings along straight runs, hangers to the
roof steel and valves at branch take-offs. Cable trays are ladders carrying cables.
Ducts are rectangular with flanges. Devices get recognisable shapes.

Each service is split into three parts so the viewer can colour and toggle them:
``mep_<service>`` (pipes, ducts, trays), ``mep_<service>_fitting`` (joints, valves,
flanges) and ``mep_<service>_support`` (hangers and clamps).
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import trimesh

from fca.model.building import roof_height

HANGER_SPACING = 3.0
COUPLING_SPACING = 6.0
RUNG_SPACING = 0.35
VALVED = (
    "Cold water branch",
    "Hot water",
    "Gas branch to oven",
    "Sprinkler cross main",
    "Process water to machine",
    "Air to machine",
    "Air drop",
)
CIRCUITS = ("circuit", "drop", "feeder", "loop", "machine power", "duct")  # conduit-sized runs


def _radius(service: str, kind: str, size_mm: float) -> float:
    k = kind.lower()
    if service == "electrical" and "duct" not in k:
        return 0.018 if "feeder" not in k else 0.03
    if service == "fire" and "loop" in k:
        return 0.012
    return max(size_mm / 2000.0, 0.014)


class DetailBuilder:
    def __init__(self, builder):
        self.b = builder
        self.cfg = builder.cfg
        self.ffl = self.cfg.levels.ffl

    # -- primitives ---------------------------------------------------------------
    def cyl(self, part: str, p1, p2, r: float, sections: int = 8) -> None:
        p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
        if np.linalg.norm(p2 - p1) < 1e-4:
            return
        c = trimesh.creation.cylinder(radius=r, segment=np.vstack([p1, p2]), sections=sections)
        self.b._part(part).add(np.asarray(c.vertices), np.asarray(c.faces))

    def ball(self, part: str, p, r: float) -> None:
        s = trimesh.creation.icosphere(subdivisions=0, radius=r)
        self.b._part(part).add(np.asarray(s.vertices) + np.asarray(p, float), np.asarray(s.faces))

    def box(self, part: str, p, size) -> None:
        (x, y, z), (w, d, h) = p, size
        self.b.box(part, x - w / 2, y - d / 2, z - h / 2, x + w / 2, y + d / 2, z + h / 2)

    def beam(self, part: str, p1, p2, w: float, d: float) -> None:
        from fca.structure.frame import Member

        self.b.member(part, Member("mep", tuple(p1), tuple(p2), w, d))

    # -- runs ---------------------------------------------------------------------
    def pipe(self, svc: str, kind: str, pts, size_mm: float) -> None:
        r = _radius(svc, kind, size_mm)
        part, fit, sup = f"mep_{svc}", f"mep_{svc}_fitting", f"mep_{svc}_support"
        conduit = svc == "electrical" or (svc == "fire" and "loop" in kind.lower())
        for a, c in pairwise(pts):
            self.cyl(part, a, c, r, 6 if conduit else 10)
            seg = np.asarray(c, float) - np.asarray(a, float)
            length = float(np.linalg.norm(seg))
            horizontal = abs(seg[2]) < 1e-3 and length > 0.5
            if not horizontal:
                continue
            u = seg / length
            overhead = a[2] > self.ffl + 2.2
            if overhead:
                d = 0.8
                while d < length - 0.3:
                    p = np.asarray(a, float) + u * d
                    top = roof_height(self.cfg, p[1]) - 0.35
                    if top > p[2] + 0.2:
                        self.cyl(sup, p + np.array([0, 0, r]), [p[0], p[1], top], 0.008, 5)
                        self.cyl(sup, p - u * 0.03, p + u * 0.03, r * 1.45, 8)  # clamp
                    d += HANGER_SPACING
            if not conduit and length > COUPLING_SPACING:
                d = COUPLING_SPACING
                while d < length - 0.5:
                    p = np.asarray(a, float) + u * d
                    self.cyl(fit, p - u * 0.05, p + u * 0.05, r * 1.3, 10)
                    d += COUPLING_SPACING
        for p in pts[1:-1]:  # elbows and tees at every change of direction
            self.ball(fit, p, r * (1.25 if conduit else 1.5))
        if kind in VALVED and len(pts) > 1:
            a, c = np.asarray(pts[0], float), np.asarray(pts[1], float)
            seg = c - a
            length = float(np.linalg.norm(seg))
            if length > 0.2:
                p = a + seg / length * min(0.4, length / 2)
                s = max(r * 3.2, 0.07)
                self.box(fit, p, (s, s, s))
                self.cyl(
                    fit, p + np.array([0, 0, s * 0.6]), p + np.array([0, 0, s * 1.3]), 0.012, 6
                )  # stem
                self.cyl(
                    fit, p + np.array([0, 0, s * 1.3]), p + np.array([0, 0, s * 1.36]), s * 0.9, 12
                )  # handwheel

    def tray(self, svc: str, pts, width: float = 0.3) -> None:
        part, sup = f"mep_{svc}", f"mep_{svc}_support"
        for a, c in pairwise(pts):
            a, c = np.asarray(a, float), np.asarray(c, float)
            seg = c - a
            length = float(np.linalg.norm(seg))
            if length < 1e-3:
                continue
            u = seg / length
            side = np.cross(u, [0, 0, 1.0])
            if np.linalg.norm(side) < 1e-6:  # vertical riser: draw as a closed duct
                self.beam(part, a, c, width, 0.1)
                continue
            side /= np.linalg.norm(side)
            for s in (-1, 1):  # side rails
                off = side * s * width / 2
                self.beam(part, a + off, c + off, 0.02, 0.08)
            d = 0.0
            while d <= length:
                p = a + u * d
                self.beam(part, p - side * width / 2, p + side * width / 2, 0.03, 0.015)  # rung
                d += RUNG_SPACING
            for k in range(5):  # cables laid in the tray
                off = side * (-width / 2 + width * (k + 0.5) / 5) + np.array([0, 0, 0.02])
                self.cyl(f"mep_{svc}_fitting", a + off, c + off, 0.011, 5)
            d = 0.75
            while d < length - 0.2:
                p = a + u * d
                top = roof_height(self.cfg, p[1]) - 0.35
                for s in (-1, 1):
                    q = p + side * s * (width / 2 + 0.03)
                    if top > q[2] + 0.2:
                        self.cyl(sup, q, [q[0], q[1], top], 0.008, 5)
                d += 1.5

    def duct(self, svc: str, pts, size_mm: float) -> None:
        w = size_mm / 1000
        h = w * 0.5 if w >= 0.4 else w
        part, fit = f"mep_{svc}", f"mep_{svc}_fitting"
        for a, c in pairwise(pts):
            self.beam(part, a, c, w, h)
            a_, c_ = np.asarray(a, float), np.asarray(c, float)
            seg = c_ - a_
            length = float(np.linalg.norm(seg))
            if length < 1e-3:
                continue
            u = seg / length
            d = 1.5
            while d < length - 0.2:
                p = a_ + u * d
                self.beam(fit, p - u * 0.03, p + u * 0.03, w + 0.06, h + 0.06)  # flange
                d += 1.5
        for p in pts[1:-1]:
            self.box(fit, p, (w + 0.08, w + 0.08, h + 0.08))  # bend

    # -- devices --------------------------------------------------------------------
    def device(self, it) -> None:
        svc, kind, (x, y, z), (w, d, h) = it.service, it.kind, it.at, it.size
        part = f"mep_{svc}"
        fit = f"mep_{svc}_fitting" if not svc.startswith("equipment") else part
        if kind == "Sprinkler":
            self.cyl(fit, (x, y, z + 0.25), (x, y, z), 0.012, 6)
            self.cyl(part, (x, y, z - 0.01), (x, y, z - 0.03), 0.045, 12)
        elif kind in ("Fire detector", "Alarm sounder"):
            self.cyl(part, (x, y, z + 0.03), (x, y, z - 0.04), 0.07, 14)
        elif kind == "LED high-bay":
            self.cyl(part, (x, y, z + 0.2), (x, y, z), 0.06, 8)
            self.cyl(part, (x, y, z), (x, y, z - 0.18), 0.22, 16)
        elif kind == "Fire extinguisher":
            self.cyl(part, (x, y, z - h / 2), (x, y, z + h / 2 - 0.1), 0.08, 12)
            self.cyl(fit, (x, y, z + h / 2 - 0.1), (x, y, z + h / 2), 0.03, 8)
        elif kind in ("Water heater",):
            self.cyl(part, (x, y, z - h / 2), (x, y, z + h / 2), w / 2, 14)
        elif kind == "WC":
            self.box(part, (x, y - d * 0.2, z - h * 0.2), (w, d * 0.6, h * 0.55))  # bowl
            self.box(part, (x, y + d * 0.35, z + h * 0.1), (w, d * 0.25, h * 0.8))  # cistern
        else:
            self.box(part, (x, y, z), (w, d, h))


def add_mep_detailed(builder, mep) -> None:
    """Replace the simple MEP boxes with detailed pipes, trays, ducts and devices."""
    db = DetailBuilder(builder)
    for r in mep.routes:
        k = r.kind.lower()
        if "tray" in k:
            db.tray(r.service, r.points, 0.4 if "hall" in k else 0.3)
        elif r.size_mm >= 200:
            db.duct(r.service, r.points, r.size_mm)
        else:
            db.pipe(r.service, r.kind, r.points, r.size_mm)
    for it in mep.items:
        db.device(it)


def detail_materials(base: dict) -> dict:
    """Fitting and support materials for every service, derived from the service colour."""
    out = {}
    for name, (color, _metal, _rough) in base.items():
        if not name.startswith("mep_") or name.endswith(("_fitting", "_support")):
            continue
        r, g, b, _alpha = color
        out[f"{name}_fitting"] = ((r * 0.62, g * 0.62, b * 0.62, 1.0), 0.5, 0.4)
        out[f"{name}_support"] = ((0.62, 0.64, 0.66, 1.0), 0.8, 0.35)
    return out
