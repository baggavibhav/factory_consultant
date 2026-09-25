"""Regression tests on reference plant #1.

Runs only when data/reference/Architectural_plans_as_built.dxf exists
(create it with `fca convert data/reference/Architectural_plans_as_built.dwg`).
Expected values were measured on 24 Sep 2026; if a code change moves them,
investigate before updating.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fca.ingestion.extract import extract_geometry, read_dxf
from fca.ingestion.layers import load_config
from fca.model.schema import Category

from .conftest import REFERENCE_DIR, REPO_ROOT


def _find_reference() -> Path:
    for name in ("Architectural_plans_as_built.dxf", "Architectural plans as built.dxf"):
        if (REFERENCE_DIR / name).is_file():
            return REFERENCE_DIR / name
    return REFERENCE_DIR / "Architectural_plans_as_built.dxf"


DXF = _find_reference()

pytestmark = [
    pytest.mark.reference,
    pytest.mark.skipif(not DXF.is_file(), reason="reference drawing not in data/reference"),
]


@pytest.fixture(scope="module")
def geometry():
    config = load_config(REPO_ROOT / "config" / "plants" / "ref-plant-01.toml")
    return extract_geometry(read_dxf(DXF), config, source_file=DXF.name)


def test_line_counts(geometry):
    assert geometry.stats[Category.WALL].count == 1484
    assert geometry.stats[Category.COLD_PANEL].count == 156
    assert geometry.stats[Category.BOUNDARY].count == 12


def test_building_size(geometry):
    b = geometry.building_bbox
    assert b.width == pytest.approx(78.2, abs=0.1)
    assert b.depth == pytest.approx(40.1, abs=0.1)


def test_key_rooms_found(geometry):
    texts = {label.text for label in geometry.labels}
    for room in ("PRODUCTION AREA +23°C", "COLD STORE -18°C", "PACKAGING AREA +23°C"):
        assert room in texts


def test_units_warning_raised(geometry):
    assert any("millimetres" in w for w in geometry.warnings)


def test_build_3d_structure(tmp_path):
    import json

    from fca.pipeline import build_3d

    result = build_3d(DXF, REPO_ROOT / "config" / "plants" / "ref-plant-01.toml", tmp_path)
    assert result.alignment_offset == pytest.approx((-1.37, 74.47), abs=0.01)
    lay = result.layout
    assert len(lay.frame_x) == 9
    assert lay.frame_x[-1] - lay.frame_x[0] == pytest.approx(73.76, abs=0.01)
    assert lay.north_y - lay.south_y == pytest.approx(39.27, abs=0.01)
    # Outer column rows must sit inside the building's south and north walls.
    b = geometry_bbox()
    assert b.ymin < lay.south_y < b.ymin + 0.6
    assert b.ymax - 0.6 < lay.north_y < b.ymax
    assert result.member_schedule["column"]["count"] == 18
    report = json.loads(result.report.read_text())
    assert report["sizes_indicative"] is True
    assert result.glb.stat().st_size > 50_000


def geometry_bbox():
    config = load_config(REPO_ROOT / "config" / "plants" / "ref-plant-01.toml")
    return config.building


def test_rooms_read_from_drawing():
    from fca.ingestion.rooms import extract_rooms

    config = load_config(REPO_ROOT / "config" / "plants" / "ref-plant-01.toml")
    rooms = extract_rooms(read_dxf(DXF), config, config.building)
    names = [r.name for r in rooms]
    assert len(rooms) >= 40
    for n in (
        "FEMALE HYGIENE STATION",
        "MALE HYGIENE STATION",
        "QA / QC LABORATORY",
        "FIRST AID ROOM",
        "COLD STORE -18°C",
    ):
        assert n in names
    exact = {r.name: r for r in rooms if not r.estimated}
    assert 10 < exact["FEMALE HYGIENE STATION"].area_m2 < 16
    assert 110 < exact["COLD STORE -18°C"].area_m2 < 135
    assert any(r.estimated and r.name.startswith("PRODUCTION AREA") for r in rooms)
