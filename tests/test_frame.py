from __future__ import annotations

import pytest

from fca.model.building import (
    BuildingConfig,
    Levels,
    StructureConfig,
    WallHeights,
    roof_height,
)
from fca.model.schema import BBox
from fca.structure.frame import FrameLayout, generate_frame, schedule


@pytest.fixture
def cfg():
    return BuildingConfig(
        envelope=BBox(xmin=0, ymin=0, xmax=30, ymax=20),
        levels=Levels(ffl=0.5, eaves_south=7.0, eaves_north=7.0, ridge=8.0),
        ridge_y=10.0,
        heights=WallHeights(),
        low_wall_zones=(),
        mezzanine_zones=(),
        structure=StructureConfig(
            grid_region=BBox(xmin=0, ymin=0, xmax=1, ymax=1),
            grid_layers=("G",),
            align_layer="B",
            frame_x=(0, 10, 20, 30),
            column_rows_y=(0, 20),
            gable_y=(10,),
            purlin_spacing=2.5,
            girt_heights=(2.0, 4.0),
        ),
    )


@pytest.fixture
def members(cfg):
    layout = FrameLayout(frame_x=(0, 10, 20, 30), south_y=0, north_y=20, gable_y=(10,))
    return generate_frame(cfg, layout)


def test_roof_height_profile(cfg):
    assert roof_height(cfg, 0) == pytest.approx(7.0)
    assert roof_height(cfg, 10) == pytest.approx(8.0)
    assert roof_height(cfg, 5) == pytest.approx(7.5)


def test_member_counts(members):
    s = schedule(members)
    assert s["column"]["count"] == 8  # 4 frames x 2 sides
    assert s["gable_column"]["count"] == 2  # one per gable end
    assert s["foundation"]["count"] == 10  # under every column
    assert s["rafter"]["count"] == 8
    assert s["eave_beam"]["count"] == 6  # 3 bays x 2 sides
    assert s["purlin"]["count"] == 3 * 9  # 3 bays x (5 + 4) stations
    assert s["bracing"]["count"] == 16  # 2 end bays x (4 roof + 4 wall)


def test_columns_stop_under_rafters(cfg, members):
    rd = cfg.structure.sizes["rafter"].depth
    for m in members:
        if m.kind == "column":
            assert m.start[2] == pytest.approx(0.5)
            assert m.end[2] == pytest.approx(roof_height(cfg, m.start[1]) - rd - 0.02)


def test_girts_below_eaves(members):
    for m in members:
        if m.kind == "girt":
            assert m.start[2] < 7.0


def test_haunches_and_intermediate_bracing(cfg):
    from dataclasses import replace

    long = FrameLayout(
        frame_x=tuple(float(x) for x in range(0, 121, 10)), south_y=0, north_y=20, gable_y=()
    )
    members = generate_frame(
        replace(cfg, structure=replace(cfg.structure, bracing_spacing_m=45)), long
    )
    s = schedule(members)
    assert s["haunch"]["count"] == 13 * 4  # two eaves + two apex pieces per frame
    braced_bays = s["bracing"]["count"] // 8
    assert braced_bays >= 4  # both ends plus intermediate bays in a 120 m building
