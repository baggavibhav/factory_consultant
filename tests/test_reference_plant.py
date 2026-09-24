"""Regression tests on reference plant #1.

Runs only when data/reference/Architectural_plans_as_built.dxf exists
(create it with `fca convert data/reference/Architectural_plans_as_built.dwg`).
Expected values were measured on 24 Sep 2026; if a code change moves them,
investigate before updating.
"""

from __future__ import annotations

import pytest

from fca.ingestion.extract import extract_geometry, read_dxf
from fca.ingestion.layers import load_config
from fca.model.schema import Category

from .conftest import REFERENCE_DIR, REPO_ROOT

DXF = REFERENCE_DIR / "Architectural_plans_as_built.dxf"

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
