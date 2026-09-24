from __future__ import annotations

import ezdxf
import pytest

from fca.model.schema import BBox
from fca.structure.grid import GridError, alignment_offset, cluster, extract_grid, pick

PLAN = BBox(xmin=0, ymin=0, xmax=100, ymax=60)
ROOF = BBox(xmin=0, ymin=-100, xmax=100, ymax=-40)


@pytest.fixture
def sheet():
    """Ground floor plan at y 0..60 and a roof plan with the grid at y -100..-40."""
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(5, 5), (95, 5), (95, 55), (5, 55)], close=True, dxfattribs={"layer": "BOUNDARY"}
    )
    msp.add_lwpolyline(
        [(6, -95), (96, -95), (96, -45), (6, -45)], close=True, dxfattribs={"layer": "BOUNDARY"}
    )
    for x in (20, 30, 30.02, 40):
        msp.add_line((x, -98), (x, -42), dxfattribs={"layer": "GRID"})
    for y in (-90, -60):
        msp.add_line((2, y), (98, y), dxfattribs={"layer": "GRID"})
    msp.add_line((20, -98), (21, -99), dxfattribs={"layer": "GRID"})  # bubble leader
    return doc


def test_cluster_merges_close_values():
    assert cluster([3.0, 1.0, 1.03, 2.0]) == (1.0, 2.0, 3.0)


def test_extract_grid_ignores_short_lines(sheet):
    grid = extract_grid(sheet, ("GRID",), ROOF)
    assert grid.xs == (20.0, 30.0, 40.0)
    assert grid.ys == (-90.0, -60.0)


def test_alignment_offset_from_boundary(sheet):
    assert alignment_offset(sheet, "BOUNDARY", ROOF, PLAN) == (-1.0, 100.0)


def test_alignment_refuses_mismatched_outlines(sheet):
    sheet.modelspace().add_line((10, -50), (99, -50), dxfattribs={"layer": "BOUNDARY"})
    with pytest.raises(GridError, match="differ in size"):
        alignment_offset(sheet, "BOUNDARY", ROOF, PLAN)


def test_pick_rejects_unknown_grid_line():
    assert pick((20.0, 30.0), [30.01]) == (30.0,)
    with pytest.raises(GridError):
        pick((20.0, 30.0), [25.0])
