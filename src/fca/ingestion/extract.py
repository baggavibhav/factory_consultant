"""Extract walls, panels, openings and room labels from a DXF plan."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing
from ezdxf.entities import DXFGraphic

from fca.ingestion.layers import LINEAR_CATEGORIES, OPENING_CATEGORIES, PlantConfig
from fca.model.schema import BBox, Category, CategoryStats, PlantGeometry, RoomLabel, Segment

log = logging.getLogger(__name__)

MIN_SEGMENT_M = 0.05
MAX_BLOCK_DEPTH = 6
INSUNITS_NAMES = {1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres", 6: "metres"}


def read_dxf(path: Path) -> Drawing:
    """Read a DXF file, repairing minor structural problems if needed."""
    try:
        return ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        log.warning("DXF structure errors in %s; using recovery mode", path)
        doc, _auditor = recover.readfile(path)
        return doc


def _lines(entity: DXFGraphic, depth: int = 0) -> Iterator[tuple[float, float, float, float]]:
    """Yield straight segments (x1, y1, x2, y2) from lines, polylines and blocks."""
    kind = entity.dxftype()
    if kind == "LINE":
        s, e = entity.dxf.start, entity.dxf.end
        yield s.x, s.y, e.x, e.y
    elif kind == "LWPOLYLINE":
        pts = [(v.x, v.y) for v in entity.vertices_in_wcs()]
        if entity.closed and pts:
            pts.append(pts[0])
        for (x1, y1), (x2, y2) in pairwise(pts):
            yield x1, y1, x2, y2
    elif kind == "INSERT" and depth < MAX_BLOCK_DEPTH:
        try:
            for child in entity.virtual_entities():
                yield from _lines(child, depth + 1)
        except Exception as exc:  # malformed blocks should not stop extraction
            log.debug("Skipping block %s: %s", entity.dxf.handle, exc)


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_geometry(doc: Drawing, config: PlantConfig, source_file: str) -> PlantGeometry:
    """Extract categorised geometry from ``doc`` according to ``config``."""
    msp = doc.modelspace()
    scale = config.unit_to_metre
    region = config.region
    warnings: list[str] = []

    insunits = doc.header.get("$INSUNITS", 0)
    if insunits == 4 and scale == 1.0:
        warnings.append(
            "File header says millimetres but config uses 1 unit = 1 m; "
            "confirm against a known dimension."
        )

    def in_region(x: float, y: float) -> bool:
        return region is None or region.contains(x, y)

    segments: list[Segment] = []
    opening_counts = {c: 0 for c in OPENING_CATEGORIES}
    labels: list[RoomLabel] = []

    for entity in msp:
        layer = entity.dxf.layer
        category = config.category_of(layer)

        if category in OPENING_CATEGORIES and entity.dxftype() == "INSERT":
            p = entity.dxf.insert
            if in_region(p.x, p.y):
                opening_counts[category] += 1
            continue

        if category in LINEAR_CATEGORIES:
            for x1, y1, x2, y2 in _lines(entity):
                if not (in_region(x1, y1) and in_region(x2, y2)):
                    continue
                seg = Segment(
                    x1=x1 * scale,
                    y1=y1 * scale,
                    x2=x2 * scale,
                    y2=y2 * scale,
                    category=category,
                    layer=layer,
                )
                if seg.length >= MIN_SEGMENT_M:
                    segments.append(seg)
            continue

        if layer in config.label_layers and entity.dxftype() in ("TEXT", "MTEXT"):
            p = entity.dxf.insert
            raw = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
            text = _clean_label(raw)
            if text and text not in config.ignore_labels and in_region(p.x, p.y):
                labels.append(RoomLabel(text=text, x=p.x * scale, y=p.y * scale, layer=layer))

    stats: dict[Category, CategoryStats] = {}
    for c in LINEAR_CATEGORIES:
        segs = [s for s in segments if s.category == c]
        stats[c] = CategoryStats(
            count=len(segs), line_length_m=round(sum(s.length for s in segs), 2)
        )
    for c, n in opening_counts.items():
        stats[c] = CategoryStats(count=n, line_length_m=0.0)

    building = config.building or _wall_bbox(segments)
    if not segments:
        warnings.append("No wall or panel lines found: check the layer mapping in the config.")

    return PlantGeometry(
        source_file=source_file,
        extracted_at=datetime.now(UTC),
        unit_to_metre=scale,
        region=region,
        building_bbox=building,
        segments=segments,
        labels=labels,
        stats=stats,
        warnings=warnings,
    )


def _wall_bbox(segments: list[Segment]) -> BBox | None:
    walls = [s for s in segments if s.category == Category.WALL]
    if not walls:
        return None
    xs = [v for s in walls for v in (s.x1, s.x2)]
    ys = [v for s in walls for v in (s.y1, s.y2)]
    return BBox(xmin=min(xs), ymin=min(ys), xmax=max(xs), ymax=max(ys))


def header_units(doc: Drawing) -> str:
    """Human-readable units declared in the DXF header."""
    code = doc.header.get("$INSUNITS", 0)
    return INSUNITS_NAMES.get(code, f"unitless/other (code {code})")
