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
    # 80 m frontage - 20 m goods-in yard - 35 m dispatch apron = 25 m; 60 - 10 - 6 = 44 m deep
    assert max_area_on_plot(values, load_template("industrial")) == pytest.approx(25 * 44)
    result = build_concept(
        Brief(plant_type="industrial", built_up_area_m2=5000, plot_width_m=80, plot_depth_m=60),
        tmp_path,
    )
    assert result.facts["footprint_m2"] == 1100
    assert "does not fit" in result.warnings[0]


def test_tiny_plot_is_rejected():
    values, _ = resolve(
        Brief(plant_type="industrial", built_up_area_m2=500, plot_width_m=15, plot_depth_m=15)
    )
    with pytest.raises(ValueError, match="too small"):
        max_area_on_plot(values, load_template("industrial"))


def test_gulf_amenity_rooms_split_by_gender():
    lay, _, _ = _layout(
        plant_type="industrial", built_up_area_m2=5000, staff_per_shift=100, female_staff_share=0.4
    )
    names = {r.name: r for r in lay.rooms}
    for n in (
        "Male changing, toilets and showers",
        "Female changing, toilets and showers",
        "Male prayer and ablution",
        "Female prayer and ablution",
        "Male hygiene station",
        "Female hygiene station",
        "Corridor",
    ):
        assert n in names
    assert (
        names["Male changing, toilets and showers"].area_m2
        > names["Female changing, toilets and showers"].area_m2
    )  # 60 men vs 40 women


def test_no_female_rooms_when_no_women():
    lay, _, _ = _layout(plant_type="industrial", built_up_area_m2=4000, female_staff_share=0)
    assert not any(r.name.startswith("Female") for r in lay.rooms)


def test_yards_docks_and_exits():
    lay, _, _ = _layout(plant_type="industrial", built_up_area_m2=5000)
    assert lay.building.xmin == 20 and lay.plot.xmax - lay.building.xmax == pytest.approx(35)
    kinds = [o.kind for o in lay.openings]
    assert kinds.count("dock_in") >= 1 and kinds.count("dock_out") >= 2
    assert kinds.count("fire_exit") >= 4 and "silo" in kinds


def test_short_yards_warn():
    lay, _, _ = _layout(
        plant_type="industrial", built_up_area_m2=3000, goods_in_yard_m=8, dispatch_yard_m=12
    )
    text = " ".join(lay.warnings)
    assert "goods-in yard" in text and "dispatch apron" in text


def test_zone_size_editing_changes_areas():
    base, _, _ = _layout(plant_type="industrial", built_up_area_m2=4000)
    bigger, _, _ = _layout(
        plant_type="industrial", built_up_area_m2=4000, zone_sizes={"Cold store": 2.0}
    )
    area = lambda lay, n: next(r.area_m2 for r in lay.rooms if r.name == n)  # noqa: E731
    assert area(bigger, "Cold store") > area(base, "Cold store") * 1.6


def test_two_span_adds_internal_columns(tmp_path):
    one = build_concept(Brief(plant_type="industrial", built_up_area_m2=4000), tmp_path / "a")
    two = build_concept(
        Brief(plant_type="industrial", built_up_area_m2=4000, structure_option="two_span"),
        tmp_path / "b",
    )
    assert "internal_column" not in one.member_schedule
    assert (
        two.member_schedule["internal_column"]["count"]
        == one.member_schedule["column"]["count"] // 2
    )
    assert two.facts["quantities"]["steel_t"] < one.facts["quantities"]["steel_t"]  # shorter spans


def test_design_overrides_apply():
    lay, _, _ = _layout(
        plant_type="industrial", built_up_area_m2=4000, span_m=30, bay_m=7.5, roof_pitch_deg=8
    )
    assert lay.building.depth == pytest.approx(30)
    bays = [b - a for a, b in zip(lay.frame.frame_x, lay.frame.frame_x[1:], strict=False)]
    assert 6.5 < bays[0] < 8.5
    assert lay.config.levels.ridge - lay.config.levels.eaves_south == pytest.approx(
        15 * 0.1405, abs=0.05
    )  # tan(8°) × half the span


def test_every_strip_room_has_a_door_and_hygiene_opens_to_production():
    from fca.model.schema import Category

    lay, _, _ = _layout(plant_type="industrial", built_up_area_m2=5000)
    walls = [s for s in lay.segments if s.category == Category.WALL]
    b = lay.building

    def open_at(x, y):  # no wall covers this point
        return not any(
            abs(s.y1 - y) < 0.05
            and abs(s.y2 - y) < 0.05
            and min(s.x1, s.x2) - 1e-6 <= x <= max(s.x1, s.x2) + 1e-6
            for s in walls
        )

    corridor = next(r for r in lay.rooms if r.name == "Corridor").rect
    hall_y0 = b.ymin + lay.strip_depth
    for r in lay.rooms:
        q = r.rect
        if r.name == "Corridor" or q.ymin >= hall_y0 - 1e-6:
            continue
        cx = (q.xmin + q.xmax) / 2
        edge = corridor.ymin if q.ymax <= corridor.ymin + 1e-6 else corridor.ymax
        assert open_at(cx, edge), f"{r.name} has no door onto the corridor"
        if "hygiene" in r.name.lower():
            assert open_at(cx, hall_y0), f"{r.name} has no door into production"
