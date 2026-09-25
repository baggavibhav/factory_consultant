"""Build a glTF 3D model of the plant: walls, slab, mezzanine, roof and structure.

Plan coordinates (x east, y north, z up, metres) are converted to glTF
(y up) and centred on the building so the model opens in any viewer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

from fca.model.building import BuildingConfig, roof_height
from fca.model.schema import BBox, Category, PlantGeometry, Segment
from fca.structure.frame import Member

EDGE_TOLERANCE = 0.6

# name: (RGBA 0-1, metallic, roughness)
MATERIALS: dict[str, tuple[tuple[float, float, float, float], float, float]] = {
    "walls_external": ((0.84, 0.81, 0.75, 1.0), 0.0, 0.9),
    "walls_internal": ((0.93, 0.91, 0.86, 1.0), 0.0, 0.9),
    "cold_panels": ((0.56, 0.73, 0.83, 1.0), 0.1, 0.6),
    "outbuildings": ((0.81, 0.78, 0.72, 1.0), 0.0, 0.9),
    "boundary_wall": ((0.72, 0.70, 0.64, 1.0), 0.0, 0.95),
    "floor_slab": ((0.80, 0.78, 0.71, 1.0), 0.0, 0.95),
    "mezzanine": ((0.78, 0.70, 0.56, 0.92), 0.0, 0.8),
    "roof": ((0.60, 0.64, 0.68, 0.45), 0.3, 0.5),
    "zone_production": ((0.95, 0.83, 0.55, 1.0), 0.0, 0.9),
    "zone_storage": ((0.80, 0.86, 0.72, 1.0), 0.0, 0.9),
    "zone_cold": ((0.62, 0.78, 0.92, 1.0), 0.0, 0.9),
    "zone_dispatch": ((0.93, 0.74, 0.60, 1.0), 0.0, 0.9),
    "zone_office": ((0.78, 0.76, 0.90, 1.0), 0.0, 0.9),
    "zone_amenity": ((0.90, 0.78, 0.86, 1.0), 0.0, 0.9),
    "zone_utility": ((0.75, 0.75, 0.73, 1.0), 0.0, 0.9),
    "zone_circulation": ((0.86, 0.86, 0.84, 1.0), 0.0, 0.9),
    "mep_electrical": ((0.93, 0.70, 0.05, 1.0), 0.3, 0.5),
    "mep_water": ((0.18, 0.53, 0.87, 1.0), 0.3, 0.4),
    "mep_drainage": ((0.45, 0.33, 0.20, 1.0), 0.1, 0.7),
    "mep_fire": ((0.84, 0.19, 0.19, 1.0), 0.3, 0.4),
    "mep_hvac": ((0.00, 0.62, 0.62, 1.0), 0.3, 0.4),
    "mep_air": ((0.45, 0.52, 0.60, 1.0), 0.5, 0.4),
    "mep_gas": ((0.95, 0.50, 0.10, 1.0), 0.3, 0.4),
    "str_foundation": ((0.62, 0.62, 0.60, 1.0), 0.0, 0.95),
    "str_column": ((0.78, 0.33, 0.16, 1.0), 0.6, 0.45),
    "str_gable_column": ((0.78, 0.33, 0.16, 1.0), 0.6, 0.45),
    "str_rafter": ((0.78, 0.33, 0.16, 1.0), 0.6, 0.45),
    "str_haunch": ((0.78, 0.33, 0.16, 1.0), 0.6, 0.45),
    "str_internal_column": ((0.78, 0.33, 0.16, 1.0), 0.6, 0.45),
    "str_mezz_beam": ((0.55, 0.45, 0.35, 1.0), 0.6, 0.45),
    "str_mezz_column": ((0.55, 0.45, 0.35, 1.0), 0.6, 0.45),
    "plinth": ((0.70, 0.70, 0.68, 1.0), 0.0, 0.95),
    "openings": ((0.30, 0.36, 0.42, 1.0), 0.4, 0.5),
    "exits": ((0.16, 0.62, 0.36, 1.0), 0.2, 0.5),
    "silos": ((0.80, 0.82, 0.84, 1.0), 0.7, 0.35),
    "str_eave_beam": ((0.85, 0.52, 0.20, 1.0), 0.6, 0.45),
    "str_purlin": ((0.35, 0.47, 0.60, 1.0), 0.6, 0.45),
    "str_girt": ((0.35, 0.47, 0.60, 1.0), 0.6, 0.45),
    "str_bracing": ((0.20, 0.22, 0.25, 1.0), 0.6, 0.45),
}

_UNIT_BOX = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
_BOX_V = np.asarray(_UNIT_BOX.vertices)
_BOX_F = np.asarray(_UNIT_BOX.faces)


@dataclass
class _Part:
    vertices: list[np.ndarray]
    faces: list[np.ndarray]
    count: int = 0

    def add(self, v: np.ndarray, f: np.ndarray) -> None:
        self.faces.append(f + self.count)
        self.vertices.append(v)
        self.count += len(v)


class ModelBuilder:
    def __init__(self, cfg: BuildingConfig):
        self.cfg = cfg
        env = cfg.envelope
        self.cx = (env.xmin + env.xmax) / 2
        self.cy = (env.ymin + env.ymax) / 2
        self.parts: dict[str, _Part] = {}

    # -- coordinates -------------------------------------------------------
    def to_gltf(self, pts: np.ndarray) -> np.ndarray:
        """Plan (x, y, z) -> glTF (x, y-up, z) centred on the building."""
        p = np.asarray(pts, dtype=float)
        return np.column_stack([p[:, 0] - self.cx, p[:, 2], -(p[:, 1] - self.cy)])

    def _part(self, name: str) -> _Part:
        return self.parts.setdefault(name, _Part([], []))

    # -- primitives --------------------------------------------------------
    def quad(self, name: str, a, b, c, d) -> None:
        self._part(name).add(np.array([a, b, c, d], float), np.array([[0, 1, 2], [0, 2, 3]]))

    def wall(self, name: str, x1, y1, x2, y2, z0, z1a, z1b) -> None:
        self.quad(name, (x1, y1, z0), (x2, y2, z0), (x2, y2, z1b), (x1, y1, z1a))

    def box(self, name: str, xmin, ymin, zmin, xmax, ymax, zmax) -> None:
        c = np.array([(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2])
        size = np.array([xmax - xmin, ymax - ymin, zmax - zmin])
        self._part(name).add(c + _BOX_V * size, _BOX_F.copy())

    def member(self, name: str, m: Member) -> None:
        p1, p2 = np.array(m.start, float), np.array(m.end, float)
        axis = p2 - p1
        length = float(np.linalg.norm(axis))
        if length < 1e-6:
            return
        u = axis / length
        if abs(u[2]) > 0.99:  # vertical: width along plan x, depth along plan y
            w = np.array([1.0, 0.0, 0.0])
        else:  # depth stays in the vertical plane through the member
            up = np.array([0.0, 0.0, 1.0])
            v = up - u * np.dot(up, u)
            v /= np.linalg.norm(v)
            w = np.cross(v, u)
        v = np.cross(u, w)
        c = (p1 + p2) / 2
        verts = (
            c
            + np.outer(_BOX_V[:, 0] * length, u)
            + np.outer(_BOX_V[:, 1] * m.width, w)
            + np.outer(_BOX_V[:, 2] * m.depth, v)
        )
        self._part(name).add(verts, _BOX_F.copy())

    # -- building elements -------------------------------------------------
    def add_walls(self, geometry: PlantGeometry) -> None:
        cfg, env, h = self.cfg, self.cfg.envelope, self.cfg.heights
        ffl = cfg.levels.ffl
        for s in geometry.segments:
            name, z0, top_a, top_b = self.classify(s, env, h, ffl)
            self.wall(name, s.x1, s.y1, s.x2, s.y2, z0, top_a, top_b)

    def classify(self, s: Segment, env: BBox, h, ffl: float):
        cfg = self.cfg
        if s.category == Category.BOUNDARY:
            return "boundary_wall", 0.0, h.boundary, h.boundary
        inside = all(
            env.xmin - EDGE_TOLERANCE <= x <= env.xmax + EDGE_TOLERANCE for x in (s.x1, s.x2)
        ) and all(env.ymin - EDGE_TOLERANCE <= y <= env.ymax + EDGE_TOLERANCE for y in (s.y1, s.y2))
        if not inside:
            return "outbuildings", 0.15, h.outbuilding, h.outbuilding

        def near(a: float, b: float) -> bool:
            return abs(a - b) < EDGE_TOLERANCE

        on_edge = any(
            near(p, e) and near(q, e)
            for p, q, e in (
                (s.x1, s.x2, env.xmin),
                (s.x1, s.x2, env.xmax),
                (s.y1, s.y2, env.ymin),
                (s.y1, s.y2, env.ymax),
            )
        )
        if on_edge:
            return "walls_external", ffl, roof_height(cfg, s.y1), roof_height(cfg, s.y2)
        if s.category == Category.COLD_PANEL:
            return "cold_panels", ffl, ffl + h.cold_panel, ffl + h.cold_panel
        mx, my = max(s.x1, s.x2), max(s.y1, s.y2)
        if any(z.contains(mx, my) for z in cfg.low_wall_zones):
            return "walls_internal", ffl, ffl + h.internal_low, ffl + h.internal_low
        top_a = min(ffl + h.internal_high, roof_height(cfg, s.y1) - 0.4)
        top_b = min(ffl + h.internal_high, roof_height(cfg, s.y2) - 0.4)
        return "walls_internal", ffl, top_a, top_b

    def add_slabs(self) -> None:
        env, lv = self.cfg.envelope, self.cfg.levels
        self.box("floor_slab", env.xmin, env.ymin, 0.0, env.xmax, env.ymax, lv.ffl)
        if lv.mezzanine is not None:
            for z in self.cfg.mezzanine_zones:
                self.box(
                    "mezzanine", z.xmin, z.ymin, lv.mezzanine - 0.2, z.xmax, z.ymax, lv.mezzanine
                )

    def add_roof(self) -> None:
        env, cfg = self.cfg.envelope, self.cfg
        r = cfg.ridge_y
        h0, hr, h1 = (roof_height(cfg, y) + 0.01 for y in (env.ymin, r, env.ymax))
        self.quad(
            "roof",
            (env.xmin, env.ymin, h0),
            (env.xmax, env.ymin, h0),
            (env.xmax, r, hr),
            (env.xmin, r, hr),
        )
        self.quad(
            "roof",
            (env.xmin, r, hr),
            (env.xmax, r, hr),
            (env.xmax, env.ymax, h1),
            (env.xmin, env.ymax, h1),
        )

    def add_zone(self, category: str, rect: BBox) -> None:
        """Coloured floor finish showing a zone of a concept layout."""
        z = self.cfg.levels.ffl
        inset = 0.08
        self.box(
            f"zone_{category}",
            rect.xmin + inset,
            rect.ymin + inset,
            z,
            rect.xmax - inset,
            rect.ymax - inset,
            z + 0.03,
        )

    def add_plinth(self, height: float = 1.2, thickness: float = 0.25) -> None:
        """Hygienic plinth wall around the building base (concrete band under the cladding)."""
        e, top = self.cfg.envelope, self.cfg.levels.ffl + height
        t = thickness
        self.box("plinth", e.xmin - t, e.ymin - t, 0.0, e.xmax + t, e.ymin, top)
        self.box("plinth", e.xmin - t, e.ymax, 0.0, e.xmax + t, e.ymax + t, top)
        self.box("plinth", e.xmin - t, e.ymin, 0.0, e.xmin, e.ymax, top)
        self.box("plinth", e.xmax, e.ymin, 0.0, e.xmax + t, e.ymax, top)

    def cylinder(self, name: str, x: float, y: float, z0: float, z1: float, r: float) -> None:
        c = trimesh.creation.cylinder(radius=r, height=z1 - z0, sections=24)
        v = np.asarray(c.vertices) + np.array([x, y, (z0 + z1) / 2])
        self._part(name).add(v, np.asarray(c.faces))

    def add_openings(self, openings: list) -> None:
        """Dock doors, fire exits, entrance and silos from a concept layout."""
        ffl = self.cfg.levels.ffl
        for o in openings:
            if o.kind == "silo":
                self.cylinder("silos", o.x, o.y, 0.0, 14.0, 1.7)
                continue
            w, h, part = {
                "dock_in": (3.0, 3.2, "openings"),
                "dock_out": (3.0, 3.2, "openings"),
                "fire_exit": (1.8, 2.2, "exits"),
                "entrance": (2.4, 2.6, "openings"),
            }[o.kind]
            t = 0.35
            if o.side in ("west", "east"):
                self.box(part, o.x - t / 2, o.y - w / 2, ffl, o.x + t / 2, o.y + w / 2, ffl + h)
            else:
                self.box(part, o.x - w / 2, o.y - t / 2, ffl, o.x + w / 2, o.y + t / 2, ffl + h)

    def add_items(self, part: str, items: list) -> None:
        """Boxes given as (x, y, z-centre, w, d, h)."""
        for x, y, z, w, d, h in items:
            self.box(part, x - w / 2, y - d / 2, z - h / 2, x + w / 2, y + d / 2, z + h / 2)

    def add_mep(self, mep) -> None:
        """Concept MEP: routes as thin members, equipment and fittings as boxes."""
        for r in mep.routes:
            tray = "tray" in r.kind.lower()
            if tray:
                w = 0.4
            elif r.size_mm >= 200:  # ducts at their real width
                w = r.size_mm / 1000
            else:  # pipes and cables drawn larger than life so they stay readable
                w = max(r.size_mm / 1000 * 1.6, 0.1)
            d = 0.12 if tray else w
            for a, b in zip(r.points, r.points[1:], strict=False):
                self.member(f"mep_{r.service}", Member(r.service, a, b, w, d))
        for it in mep.items:
            (x, y, z), (w, d, h) = it.at, it.size
            self.box(
                f"mep_{it.service}",
                x - w / 2,
                y - d / 2,
                z - h / 2,
                x + w / 2,
                y + d / 2,
                z + h / 2,
            )

    def add_structure(self, members: list[Member]) -> None:
        for m in members:
            self.member(f"str_{m.kind}", m)

    # -- export ------------------------------------------------------------
    def scene(self) -> trimesh.Scene:
        scene = trimesh.Scene()
        for name, part in self.parts.items():
            if not part.vertices:
                continue
            verts = self.to_gltf(np.vstack(part.vertices))
            mesh = trimesh.Trimesh(verts, np.vstack(part.faces), process=False)
            color, metal, rough = MATERIALS[name]
            mesh.visual = trimesh.visual.TextureVisuals(
                material=PBRMaterial(
                    name=name,
                    baseColorFactor=[round(c * 255) for c in color],
                    metallicFactor=metal,
                    roughnessFactor=rough,
                    doubleSided=True,
                    alphaMode="BLEND" if color[3] < 1 else "OPAQUE",
                )
            )
            scene.add_geometry(mesh, node_name=name, geom_name=name)
        return scene

    def glb(self) -> bytes:
        return self.scene().export(file_type="glb")


def build_model(
    cfg: BuildingConfig, geometry: PlantGeometry, members: list[Member]
) -> ModelBuilder:
    builder = ModelBuilder(cfg)
    builder.add_walls(geometry)
    builder.add_slabs()
    builder.add_roof()
    builder.add_structure(members)
    return builder
