"""Read the structural column grid and align it to the ground floor plan.

Architectural sheets often draw the grid on a different plan (here the roof
plan) placed elsewhere on the sheet. We align that plan to the ground floor
plan by matching an element drawn on both, such as the plot boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from ezdxf import bbox as ezbbox
from ezdxf.document import Drawing

from fca.model.schema import BBox

AXIS_TOLERANCE = 0.01  # a line counts as vertical/horizontal within 1 cm
MIN_GRID_LINE_LENGTH = 10.0  # shorter lines are bubble leaders, not grid lines


class GridError(ValueError):
    """Raised when the grid cannot be read or aligned."""


@dataclass(frozen=True)
class Grid:
    """Grid line positions in drawing units. ``xs`` are vertical lines, ``ys`` horizontal."""

    xs: tuple[float, ...]
    ys: tuple[float, ...]

    def shifted(self, dx: float, dy: float) -> Grid:
        return Grid(tuple(x + dx for x in self.xs), tuple(y + dy for y in self.ys))


def cluster(values: list[float], tol: float = 0.05) -> tuple[float, ...]:
    """Sort values and merge any within ``tol`` of the previous kept value."""
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return tuple(round(v, 3) for v in out)


def extract_grid(doc: Drawing, layers: tuple[str, ...], region: BBox) -> Grid:
    """Collect long vertical and horizontal lines on ``layers`` inside ``region``."""
    xs: list[float] = []
    ys: list[float] = []
    for e in doc.modelspace():
        if e.dxf.layer not in layers or e.dxftype() != "LINE":
            continue
        s, t = e.dxf.start, e.dxf.end
        if not (region.contains(s.x, s.y) and region.contains(t.x, t.y)):
            continue
        if abs(s.x - t.x) < AXIS_TOLERANCE and abs(s.y - t.y) >= MIN_GRID_LINE_LENGTH:
            xs.append(s.x)
        elif abs(s.y - t.y) < AXIS_TOLERANCE and abs(s.x - t.x) >= MIN_GRID_LINE_LENGTH:
            ys.append(s.y)
    if not xs or not ys:
        raise GridError(f"No grid lines found on layers {layers} in the grid region")
    return Grid(cluster(xs), cluster(ys))


def _layer_bbox_in(doc: Drawing, layer: str, region: BBox) -> BBox:
    boxes = []
    for e in doc.modelspace():
        if e.dxf.layer != layer:
            continue
        ext = ezbbox.extents([e], fast=True)
        if not ext.has_data:
            continue
        lo, hi = ext.extmin, ext.extmax
        if region.contains(lo.x, lo.y) and region.contains(hi.x, hi.y):
            boxes.append((lo.x, lo.y, hi.x, hi.y))
    if not boxes:
        raise GridError(f"Layer '{layer}' has nothing inside region {region}")
    return BBox(
        xmin=min(b[0] for b in boxes),
        ymin=min(b[1] for b in boxes),
        xmax=max(b[2] for b in boxes),
        ymax=max(b[3] for b in boxes),
    )


def alignment_offset(
    doc: Drawing, layer: str, source: BBox, target: BBox, size_tolerance: float = 0.1
) -> tuple[float, float]:
    """Offset that moves the ``source`` plan onto the ``target`` plan.

    Both plans must contain the same outline on ``layer`` (e.g. the plot
    boundary); its size must match within ``size_tolerance`` or we refuse.
    """
    a = _layer_bbox_in(doc, layer, source)
    b = _layer_bbox_in(doc, layer, target)
    if abs(a.width - b.width) > size_tolerance or abs(a.depth - b.depth) > size_tolerance:
        raise GridError(
            f"Reference outlines differ in size ({a.width:.2f} x {a.depth:.2f} vs "
            f"{b.width:.2f} x {b.depth:.2f}); cannot align plans"
        )
    return round(b.xmin - a.xmin, 4), round(b.ymin - a.ymin, 4)


def pick(values: tuple[float, ...], wanted: list[float], tol: float = 0.05) -> tuple[float, ...]:
    """Return the grid positions matching ``wanted``; fail if any is not a grid line."""
    chosen = []
    for w in wanted:
        match = [v for v in values if abs(v - w) <= tol]
        if not match:
            raise GridError(f"Configured grid line {w} is not in the drawing's grid")
        chosen.append(match[0])
    return tuple(chosen)
