from __future__ import annotations

import pytest

from fca.concept.brief import Brief, resolve
from fca.concept.layout import build_layout, max_area_on_plot
from fca.concept.program import build_program, load_template
from fca.pipeline import build_concept


def _layout(**kw):
    values, notes = resolve(Brief(**kw))
    tpl = load_template(values["plant_type"])
    return build_layout(values, build_program(values, tpl), tpl), values, notes


@pytest.mark.parametrize("plant_type", ["industrial", "retail", "egg_station"])
def test_program_fills_the_area(plant_type):
    values, _ = resolve(Brief(plant_type=plant_type, built_up_area_m2=3000))
    program = build_program(values, load_template(plant_type))
    assert sum(s.area_m2 for s in program.all) == pytest.approx(3000)


def test_defaults_are_reported():
    _, notes = resolve(Brief(plant_type="industrial", built_up_area_m2=3000, lines_now=3))
    assert "2 shifts per day" in notes
    assert not any("production line(s) now" in n for n in notes)  # given, so not assumed


def test_rooms_tile_the_building_without_overlap():
    lay, _, _ = _layout(plant_type="industrial", built_up_area_m2=5000)
    b = lay.building
    assert sum(r.area_m2 for r in lay.rooms) == pytest.approx(b.width * b.depth, rel=1e-6)
    for r in lay.rooms:
        assert b.xmin - 1e-6 <= r.rect.xmin < r.rect.xmax <= b.xmax + 1e-6
        assert b.ymin - 1e-6 <= r.rect.ymin < r.rect.ymax <= b.ymax + 1e-6
    for i, a in enumerate(lay.rooms):
        for c in lay.rooms[i + 1 :]:
            ox = min(a.rect.xmax, c.rect.xmax) - max(a.rect.xmin, c.rect.xmin)
            oy = min(a.rect.ymax, c.rect.ymax) - max(a.rect.ymin, c.rect.ymin)
            assert ox <= 1e-6 or oy <= 1e-6, f"{a.name} overlaps {c.name}"


def test_process_flow_order_west_to_east():
    lay, _, _ = _layout(plant_type="industrial", built_up_area_m2=5000)
    x = {r.name: r.rect.xmin for r in lay.rooms}
    assert x["RM store"] < x["Production area"] < x["Cooling area"] < x["Packaging area"]
    assert x["Packaging area"] < x["Cold store"] < x["Marshalling and dispatch"]


def test_building_fits_plot_and_grid_is_regular():
    lay, _, _ = _layout(
        plant_type="industrial", built_up_area_m2=2400, plot_width_m=100, plot_depth_m=70
    )
    assert lay.plot.contains(lay.building.xmax, lay.building.ymax)
    bays = [b - a for a, b in zip(lay.frame.frame_x, lay.frame.frame_x[1:], strict=False)]
    assert max(bays) - min(bays) < 0.01 and 7 < bays[0] < 11  # rounded to mm


def test_optional_zones_follow_the_brief():
    with_cold, _, _ = _layout(plant_type="industrial", built_up_area_m2=3000, blast_freezer=True)
    without, _, _ = _layout(plant_type="industrial", built_up_area_m2=3000, cold_storage=False)
    assert "Blast freezer" in {r.name for r in with_cold.rooms}
    assert "Cold store" not in {r.name for r in without.rooms}


def test_oversized_request_is_reduced_with_warning(tmp_path):
    values, _ = resolve(
        Brief(plant_type="industrial", built_up_area_m2=5000, plot_width_m=80, plot_depth_m=60)
    )
    assert max_area_on_plot(values, load_template("industrial")) == pytest.approx(59 * 44)
    result = build_concept(
        Brief(plant_type="industrial", built_up_area_m2=5000, plot_width_m=80, plot_depth_m=60),
        tmp_path,
    )
    assert result.facts["footprint_m2"] == 2596
    assert "does not fit" in result.warnings[0]


def test_tiny_plot_is_rejected():
    values, _ = resolve(
        Brief(plant_type="industrial", built_up_area_m2=500, plot_width_m=15, plot_depth_m=15)
    )
    with pytest.raises(ValueError, match="too small"):
        max_area_on_plot(values, load_template("industrial"))
