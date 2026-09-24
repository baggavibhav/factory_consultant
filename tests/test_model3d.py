from __future__ import annotations

import io

import pytest
import trimesh

from fca.ingestion.extract import extract_geometry, read_dxf
from fca.model.building import BuildingConfig, Levels, WallHeights
from fca.model.schema import BBox
from fca.model3d.build import build_model
from fca.structure.frame import Member
from fca.viewer.html import render_viewer


def _cfg():
    return BuildingConfig(
        envelope=BBox(xmin=0, ymin=0, xmax=20, ymax=10),
        levels=Levels(ffl=0.6, eaves_south=6.0, eaves_north=6.0, ridge=7.0, mezzanine=3.5),
        ridge_y=5.0,
        heights=WallHeights(),
        low_wall_zones=(),
        mezzanine_zones=(BBox(xmin=0, ymin=0, xmax=5, ymax=5),),
        structure=None,
    )


def test_glb_contains_named_parts(sample_dxf, sample_config):
    geometry = extract_geometry(read_dxf(sample_dxf), sample_config, "sample.dxf")
    beam = Member("rafter", (0, 0, 5.5), (0, 5, 6.5), 0.2, 0.5)
    builder = build_model(_cfg(), geometry, [beam])
    scene = trimesh.load(io.BytesIO(builder.glb()), file_type="glb")
    names = set(scene.geometry)
    for expected in (
        "walls_external",
        "cold_panels",
        "floor_slab",
        "mezzanine",
        "roof",
        "str_rafter",
    ):
        assert expected in names


def test_building_is_centred_and_y_up(sample_dxf, sample_config):
    geometry = extract_geometry(read_dxf(sample_dxf), sample_config, "sample.dxf")
    builder = build_model(_cfg(), geometry, [])
    scene = trimesh.load(io.BytesIO(builder.glb()), file_type="glb")
    slab = scene.geometry["floor_slab"]
    lo, hi = slab.bounds
    assert (lo[0], hi[0]) == pytest.approx((-10, 10))  # x centred on the 20 m building
    assert (lo[1], hi[1]) == pytest.approx((0, 0.6))  # slab: ground to finished floor (float32)


def test_viewer_is_self_contained():
    html = render_viewer(b"glTF", {"plant": "x"}, [])
    assert "Z2xURg==" in html  # base64 of the model bytes
    assert "cdnjs" not in html and "unpkg" not in html
    assert "THREE.GLTFLoader" in html
