from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from fca.api.app import create_app
from fca.procurement.engine import compare

from .conftest import REPO_ROOT


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    c = TestClient(
        create_app(
            data_dir=tmp_path_factory.mktemp("p"),
            config_dir=REPO_ROOT / "config" / "plants",
            web_dir=None,
        )
    )
    pid = c.post(
        "/api/projects",
        json={
            "name": "Procurement test",
            "plant_type": "industrial",
            "country": "Saudi Arabia",
            "mode": "brief",
        },
    ).json()["id"]
    c.put(f"/api/projects/{pid}/brief", json={"plant_type": "industrial", "built_up_area_m2": 3000})
    c.post(f"/api/projects/{pid}/builds")
    return c, pid


def _fill(
    xlsx: bytes,
    factor: float,
    supplier: str,
    lead: float,
    vat=False,
    skip=0,
    valid_days=60,
    install=True,
) -> bytes:
    wb = load_workbook(io.BytesIO(xlsx))
    ws = wb["Prices"]
    lib = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 10).value:
            lib[r] = ws.cell(r, 5).value
    rows = sorted(lib)
    for i, r in enumerate(rows):
        if i < skip:
            continue
        ws.cell(r, 6).value = 100.0 * factor
        ws.cell(r, 8).value = "Yes"
    cm = wb["Commercial"]
    vals = [
        supplier,
        "1010123456",
        "Q-1",
        date.today().isoformat(),
        (date.today() + timedelta(days=valid_days)).isoformat(),
        lead,
        "Yes",
        "Yes" if install else "No",
        "Yes" if vat else "No",
        "30% advance",
        "a@b.sa",
    ]
    for i, v in enumerate(vals, start=3):
        cm.cell(i, 2).value = v
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_suppliers_seeded_as_prospects(ctx):
    c, _ = ctx
    s = c.get("/api/suppliers").json()
    assert len(s["suppliers"]) >= 15
    assert all(x["status"] == "prospect" and x["source"] for x in s["suppliers"])


def test_approval_needs_checks(ctx):
    c, _ = ctx
    sid = c.get("/api/suppliers").json()["suppliers"][0]["id"]
    assert c.patch(f"/api/suppliers/{sid}", json={"status": "approved"}).status_code == 422
    ok = c.patch(
        f"/api/suppliers/{sid}",
        json={"status": "approved", "checks": {"cr_verified": True, "references": True}},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


def test_packages_rfq_quotes_compare_accept(ctx):
    c, pid = ctx
    pk = c.get(f"/api/projects/{pid}/procurement").json()["packages"]
    steel = next(p for p in pk if p["key"] == "steel")
    assert steel["estimate"] > 0 and steel["suggested"]
    rfq = c.get(f"/api/projects/{pid}/procurement/steel/rfq.xlsx")
    assert rfq.status_code == 200
    sups = c.get("/api/suppliers").json()["suppliers"]
    a, b = sups[0]["id"], sups[1]["id"]
    c.post(f"/api/projects/{pid}/procurement/steel/invite", json={"supplier_ids": [a, b]})
    # Supplier A: cheaper but misses a line and is slower; supplier B complete and faster.
    q1 = _fill(rfq.content, 60, "Supplier A", 16, skip=1)
    q2 = _fill(rfq.content, 66, "Supplier B", 8, vat=True)
    for data, sid in ((q1, a), (q2, b)):
        r = c.post(
            f"/api/projects/{pid}/procurement/steel/quotes",
            files={"file": ("q.xlsx", data)},
            data={"supplier_id": sid},
        )
        assert r.status_code == 201, r.text
    cmp = c.get(f"/api/projects/{pid}/procurement/steel/compare").json()
    assert len(cmp["quotes"]) == 2
    b_row = next(q for q in cmp["quotes"] if q["supplier_id"] == b)
    assert any("VAT" not in f for f in b_row["flags"])
    a_row = next(q for q in cmp["quotes"] if q["supplier_id"] == a)
    assert any("not priced" in f for f in a_row["flags"])
    assert cmp["recommended"] in (a_row["quote_id"], b_row["quote_id"]) and cmp["reasons"]
    before = c.get(f"/api/projects/{pid}").json()["latest_build"]["facts"]["cost"]
    after = c.post(
        f"/api/projects/{pid}/procurement/steel/quotes/{b_row['quote_id']}/accept"
    ).json()
    cost = after["latest_build"]["facts"]["cost"]
    assert cost["coverage"].get("quoted", 0) > 0
    assert cost["total"] != before["total"]
    rates = {r["key"]: r for r in c.get("/api/rates").json()["rates"]}
    assert rates["steel_main"]["confidence"] == "quoted"
    assert rates["steel_main"]["installed"] == pytest.approx(6600 / 1.15, rel=1e-3)


def test_wrong_file_rejected(ctx):
    c, pid = ctx
    bad = c.post(
        f"/api/projects/{pid}/procurement/steel/quotes", files={"file": ("x.xlsx", b"not excel")}
    )
    assert bad.status_code == 422


def test_scoring_prefers_complete_compliant_quotes():
    lines = [
        {
            "section": "S",
            "description": f"Item {i}",
            "qty": 10,
            "unit": "nr",
            "rate": 100.0,
            "amount": 1000.0,
        }
        for i in range(4)
    ]

    def q(qid, price, comply=True, missing=0, lead=10, valid=30):
        return {
            "id": qid,
            "supplier_id": qid,
            "lead_time_weeks": lead,
            "valid_until": (date.today() + timedelta(days=valid)).isoformat(),
            "lines": {
                f"S|Item {i}": {"unit_price": None if i < missing else price, "complies": comply}
                for i in range(4)
            },
        }

    res = compare(
        [q("cheap_non", 80, comply=False), q("fair", 90)],
        lines,
        {"fair": {"status": "approved"}, "cheap_non": {"status": "approved"}},
    )
    assert res["recommended"] == "fair"
    expired = compare([q("old", 80, valid=-1), q("ok", 95)], lines, {})
    assert expired["recommended"] == "ok"


def test_quote_linked_by_supplier_name(ctx):
    c, pid = ctx
    rfq = c.get(f"/api/projects/{pid}/procurement/fire/rfq.xlsx").content
    sup = next(s for s in c.get("/api/suppliers").json()["suppliers"] if "fire" in s["categories"])
    q = _fill(rfq, 50, sup["name"], 6)
    c.post(f"/api/projects/{pid}/procurement/fire/quotes", files={"file": ("q.xlsx", q)})
    cmp = c.get(f"/api/projects/{pid}/procurement/fire/compare").json()
    assert cmp["quotes"][0]["supplier_id"] == sup["id"]
