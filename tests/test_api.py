from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fca.api.app import create_app
from fca.api.store import safe_filename

from .conftest import REFERENCE_DIR, REPO_ROOT


@pytest.fixture
def client(tmp_path):
    app = create_app(
        data_dir=tmp_path / "projects", config_dir=REPO_ROOT / "config" / "plants", web_dir=None
    )
    return TestClient(app)


def _create(client, **over):
    body = {
        "name": "Riyadh bakery",
        "plant_type": "industrial",
        "country": "Saudi Arabia",
        "city": "Riyadh",
        "config": "ref-plant-01",
    } | over
    return client.post("/api/projects", json=body)


def test_meta_lists_configs_and_types(client):
    meta = client.get("/api/meta").json()
    assert "ref-plant-01" in meta["configs"]
    assert "_template" not in meta["configs"]
    assert {t["value"] for t in meta["plant_types"]} == {"industrial", "retail", "egg_station"}


def test_create_list_update_delete(client):
    created = _create(client)
    assert created.status_code == 201
    pid = created.json()["id"]
    assert client.get("/api/projects").json()[0]["id"] == pid
    updated = client.patch(f"/api/projects/{pid}", json={"city": "Jeddah"}).json()
    assert updated["city"] == "Jeddah"
    assert [e["kind"] for e in updated["events"]] == ["created", "updated"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_validation_errors(client):
    assert _create(client, config="nope").status_code == 422
    assert _create(client, plant_type="factory").status_code == 422
    assert client.get("/api/projects/../../etc").status_code == 404


def test_upload_rejects_wrong_type_and_build_needs_drawing(client):
    pid = _create(client).json()["id"]
    bad = client.post(f"/api/projects/{pid}/drawing", files={"file": ("x.pdf", b"%PDF", "a/b")})
    assert bad.status_code == 422
    assert client.post(f"/api/projects/{pid}/builds").status_code == 409
    assert client.get(f"/api/projects/{pid}/model.glb").status_code == 404


def test_upload_dxf(client, sample_dxf):
    pid = _create(client).json()["id"]
    with sample_dxf.open("rb") as fh:
        res = client.post(f"/api/projects/{pid}/drawing", files={"file": ("my plan.dxf", fh)})
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "drawing_ready"
    assert body["drawing"]["filename"] == "my_plan.dxf"  # spaces replaced


def test_safe_filename():
    assert safe_filename("../../evil name.dwg") == "evil_name.dwg"
    assert safe_filename("???") == "drawing"


REF = REFERENCE_DIR / "Architectural_plans_as_built.dxf"


@pytest.mark.reference
@pytest.mark.skipif(not REF.is_file(), reason="reference drawing not in data/reference")
def test_full_build_flow(client):
    pid = _create(client).json()["id"]
    with REF.open("rb") as fh:
        uploaded = client.post(f"/api/projects/{pid}/drawing", files={"file": (REF.name, fh)})
    assert uploaded.is_success
    built = client.post(f"/api/projects/{pid}/builds").json()
    assert built["status"] == "model_ready"
    assert built["latest_build"]["facts"]["frames"] == 9
    glb = client.get(f"/api/projects/{pid}/model.glb")
    assert glb.status_code == 200 and glb.content[:4] == b"glTF"
    assert any(
        lab["text"].startswith("PRODUCTION AREA")
        for lab in client.get(f"/api/projects/{pid}/labels").json()
    )
    summary = client.get("/api/projects").json()[0]
    assert summary["frames"] == 9 and summary["footprint_m2"] > 3000


def test_brief_flow(client):
    body = {
        "name": "Dammam concept",
        "plant_type": "industrial",
        "country": "Saudi Arabia",
        "mode": "brief",
    }
    created = client.post("/api/projects", json=body)
    assert created.status_code == 201
    pid = created.json()["id"]
    assert client.post(f"/api/projects/{pid}/builds").status_code == 409  # no brief yet
    wrong = client.put(
        f"/api/projects/{pid}/brief", json={"plant_type": "retail", "built_up_area_m2": 2000}
    )
    assert wrong.status_code == 422
    saved = client.put(
        f"/api/projects/{pid}/brief",
        json={"plant_type": "industrial", "built_up_area_m2": 4000, "cold_storage": True},
    )
    assert saved.json()["status"] == "brief_ready"
    built = client.post(f"/api/projects/{pid}/builds").json()
    facts = built["latest_build"]["facts"]
    assert built["status"] == "model_ready"
    assert facts["mode"] == "concept"
    assert abs(facts["footprint_m2"] - 4000) < 5
    assert any(z["name"] == "Cold store" for z in facts["program"])
    assert client.get(f"/api/projects/{pid}/model.glb").content[:4] == b"glTF"
    no_upload = client.post(f"/api/projects/{pid}/drawing", files={"file": ("a.dxf", b"0")})
    assert no_upload.status_code == 409


def test_drawing_mode_needs_profile(client):
    body = {"name": "No profile", "plant_type": "industrial", "country": "Oman"}
    assert client.post("/api/projects", json=body).status_code == 422


def test_brief_defaults(client):
    d = client.get("/api/brief-defaults/retail").json()
    assert d["cold_storage"] is False and d["clear_height_m"] == 5.5


def test_summary_reports_mode(client):
    client.post(
        "/api/projects",
        json={"name": "Brief one", "plant_type": "retail", "country": "Oman", "mode": "brief"},
    )
    assert client.get("/api/projects").json()[0]["mode"] == "brief"


def test_concept_build_produces_boq(client):
    pid = client.post(
        "/api/projects",
        json={
            "name": "BOQ test",
            "plant_type": "industrial",
            "country": "Saudi Arabia",
            "mode": "brief",
        },
    ).json()["id"]
    client.put(
        f"/api/projects/{pid}/brief", json={"plant_type": "industrial", "built_up_area_m2": 3000}
    )
    built = client.post(f"/api/projects/{pid}/builds").json()
    assert built["latest_build"]["facts"]["quantities"]["steel_t"] > 30
    boq = client.get(f"/api/projects/{pid}/boq").json()
    assert boq["currency"] == "SAR"
    names = [s["name"] for s in boq["sections"]]
    assert names[0] == "Substructure" and "Electrical" in names and "Drainage" in names
    xlsx = client.get(f"/api/projects/{pid}/boq.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert "BOQ_test_BOQ.xlsx" in xlsx.headers["content-disposition"]


def test_edit_and_rebuild_reports_changes(client):
    pid = client.post(
        "/api/projects",
        json={"name": "Edit test", "plant_type": "industrial", "country": "Oman", "mode": "brief"},
    ).json()["id"]
    brief = {"plant_type": "industrial", "built_up_area_m2": 3000}
    client.put(f"/api/projects/{pid}/brief", json=brief)
    first = client.post(f"/api/projects/{pid}/builds").json()
    assert first["latest_build"]["changes"] == []
    client.put(
        f"/api/projects/{pid}/brief",
        json=brief | {"built_up_area_m2": 3600, "structure_option": "two_span"},
    )
    second = client.post(f"/api/projects/{pid}/builds").json()
    labels = {c["label"]: c for c in second["latest_build"]["changes"]}
    assert labels["Footprint"]["after"] > labels["Footprint"]["before"]
    assert "Structural steel" in labels
    plan = client.get(f"/api/projects/{pid}/plan").json()
    assert plan["rooms"] and plan["routes"] and plan["columns"]
    assert any(o["kind"] == "dock_out" for o in plan["openings"])


def test_brief_defaults_include_design_options(client):
    d = client.get("/api/brief-defaults/industrial").json()
    assert "Production area" in d["hall_zones"]
    assert d["dispatch_yard_m"] >= 30 and d["span_m"] == 40.0
