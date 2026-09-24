from __future__ import annotations

import pytest

from fca.ingestion.extract import extract_geometry, read_dxf
from fca.model.schema import Category, PlantGeometry


@pytest.fixture
def geometry(sample_dxf, sample_config):
    return extract_geometry(read_dxf(sample_dxf), sample_config, source_file="sample.dxf")


def test_walls_extracted_inside_region_only(geometry):
    walls = geometry.stats[Category.WALL]
    assert walls.count == 5  # 4 outer + 1 partition; short and outside lines dropped
    assert walls.line_length_m == pytest.approx(70.0)


def test_block_contents_are_exploded(geometry):
    panels = geometry.stats[Category.COLD_PANEL]
    assert panels.count == 2
    assert panels.line_length_m == pytest.approx(7.0)
    xs = sorted({s.x1 for s in geometry.segments if s.category == Category.COLD_PANEL})
    assert xs == [12.0, 16.0]  # block placed at (12, 2), so coordinates are in world space


def test_openings_counted_not_drawn(geometry):
    assert geometry.stats[Category.DOOR].count == 1
    assert geometry.stats[Category.WINDOW].count == 1
    assert all(s.category not in (Category.DOOR, Category.WINDOW) for s in geometry.segments)


def test_labels_cleaned_and_filtered(geometry):
    texts = sorted(label.text for label in geometry.labels)
    assert texts == ["COLD STORE -18°C", "PRODUCTION AREA"]


def test_building_bbox_from_walls(geometry):
    b = geometry.building_bbox
    assert (b.width, b.depth) == (20.0, 10.0)


def test_unit_scale_applied(sample_dxf, sample_config):
    from dataclasses import replace

    half = replace(sample_config, unit_to_metre=0.5)  # e.g. a drawing at 1 unit = 0.5 m
    g = extract_geometry(read_dxf(sample_dxf), half, source_file="sample.dxf")
    assert g.building_bbox.width == pytest.approx(10.0)
    assert g.stats[Category.WALL].line_length_m == pytest.approx(35.0)


def test_output_round_trips_through_json(geometry):
    again = PlantGeometry.model_validate_json(geometry.model_dump_json())
    assert again.stats == geometry.stats
    assert len(again.segments) == len(geometry.segments)


def test_warns_when_no_walls(sample_dxf, sample_config):
    from dataclasses import replace

    empty = replace(sample_config, layers={Category.WALL: ("NOPE",)})
    g = extract_geometry(read_dxf(sample_dxf), empty, source_file="sample.dxf")
    assert any("No wall" in w for w in g.warnings)
