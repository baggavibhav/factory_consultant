from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fca.api.app import create_app
from fca.concept.brief import Brief
from fca.pipeline import build_concept

from .conftest import REPO_ROOT


def _checks(tmp_path, **brief):
    build_concept(Brief(**brief), tmp_path)
    return {
        f["id"].split(".")[0] + "." + f["id"].split(".")[1]: f
        for f in json.loads((tmp_path / "model.checks.json").read_text())
    }


@pytest.mark.parametrize(
    "plant_type,area", [("industrial", 5000), ("retail", 1200), ("egg_station", 2500)]
)
def test_default_concepts_have_no_major_findings(tmp_path, plant_type, area):
    findings = _checks(tmp_path, plant_type=plant_type, built_up_area_m2=area)
    assert not [f for f in findings.values() if f["severity"] in ("critical", "major")]


def test_short_yards_are_flagged_with_fixes(tmp_path):
    f = _checks(
        tmp_path,
        plant_type="industrial",
        built_up_area_m2=3000,
        goods_in_yard_m=8,
        dispatch_yard_m=12,
    )
    assert f["site.goods_in_yard"]["fix"] == {"goods_in_yard_m": 20}
    assert f["site.dispatch_apron"]["fix"] == {"dispatch_yard_m": 35}
    assert f["site.dispatch_apron"]["at"] is not None


def test_long_span_suggests_internal_columns(tmp_path):
    f = _checks(tmp_path, plant_type="industrial", built_up_area_m2=5000)
    assert f["structure.span_heavy"]["fix"] == {"structure_option": "two_span"}


def test_drawing_checks(tmp_path):
    from .test_reference_plant import DXF

    if not DXF.is_file():
        pytest.skip("reference drawing not in data/reference")
    from fca.pipeline import build_3d

    build_3d(DXF, REPO_ROOT / "config" / "plants" / "ref-plant-01.toml", tmp_path, "m")
    ids = [f["id"] for f in json.loads((tmp_path / "m.checks.json").read_text())]
    assert "fire.exits_unknown" in ids  # doors are not read from drawings yet


@pytest.fixture
def client(tmp_path):
    return TestClient(
        create_app(
            data_dir=tmp_path / "p", config_dir=REPO_ROOT / "config" / "plants", web_dir=None
        )
    )


def test_variant_flow(client):
    pid = client.post(
        "/api/projects",
        json={
            "name": "Variant test",
            "plant_type": "industrial",
            "country": "Saudi Arabia",
            "mode": "brief",
        },
    ).json()["id"]
    client.put(
        f"/api/projects/{pid}/brief",
        json={
            "plant_type": "industrial",
            "built_up_area_m2": 3000,
            "dispatch_yard_m": 12,
            "plot_width_m": 120,
            "plot_depth_m": 70,
        },
    )
    client.post(f"/api/projects/{pid}/builds")
    checks = client.get(f"/api/projects/{pid}/checks").json()
    fix = next(f for f in checks if f["id"] == "site.dispatch_apron")
    res = client.post(
        f"/api/projects/{pid}/variants",
        json={"name": fix["fix_label"], "changes": fix["fix"], "source": fix["id"]},
    )
    assert res.status_code == 201
    v = res.json()["variants"][0]
    assert v["brief"]["dispatch_yard_m"] == 35
    diff = client.get(f"/api/projects/{pid}/variants/{v['id']}/diff").json()
    assert diff["building_changed"]  # a deeper apron shortens or moves the building on a fixed plot
    assert client.get(f"/api/projects/{pid}/variants/{v['id']}/model.glb").content[:4] == b"glTF"
    vchecks = client.get(f"/api/projects/{pid}/variants/{v['id']}/checks").json()
    assert "site.dispatch_apron" not in [f["id"] for f in vchecks]  # the fix resolves it
    accepted = client.post(f"/api/projects/{pid}/variants/{v['id']}/accept").json()
    assert accepted["brief"]["dispatch_yard_m"] == 35 and accepted["variants"] == []


def test_variants_only_for_built_concepts(client):
    pid = client.post(
        "/api/projects",
        json={
            "name": "Drawing test",
            "plant_type": "industrial",
            "country": "Oman",
            "config": "ref-plant-01",
        },
    ).json()["id"]
    assert client.post(f"/api/projects/{pid}/variants", json={"name": "Try"}).status_code == 409


def test_diff_reports_a_shift_once():
    from fca.checks.diff import plan_diff

    base = {
        "building": [10, 10, 60, 40],
        "rooms": [],
        "openings": [{"kind": "dock_in", "x": 10, "y": 20}],
        "columns": [[10, 10], [20, 10]],
    }
    moved = {
        "building": [22, 10, 72, 40],
        "rooms": [],
        "openings": [{"kind": "dock_in", "x": 22, "y": 20}],
        "columns": [[22, 10], [32, 10]],
    }
    d = plan_diff(base, moved)
    assert d["moved_m"] == [12, 0]
    assert d["openings_added"] == [] and d["columns_added"] == []
