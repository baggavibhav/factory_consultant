from __future__ import annotations

import json

import pytest
from openpyxl import load_workbook

from fca.concept.brief import Brief
from fca.cost.estimate import load_library, price_items
from fca.pipeline import build_concept


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("cost")
    r = build_concept(
        Brief(plant_type="industrial", built_up_area_m2=4000),
        out,
        project={"name": "Cost test", "country": "Saudi Arabia"},
    )
    return r, out


def _lines(out):
    return {
        ln["description"]: ln for ln in json.loads((out / "model.cost.json").read_text())["lines"]
    }


def test_every_boq_item_is_priced(built):
    _, out = built
    est = json.loads((out / "model.cost.json").read_text())
    assert est["unpriced"] == []


@pytest.mark.parametrize(
    "text,key",
    [
        ("Excavate for pad foundations", "excavation"),
        ("Pad foundations", "pad_concrete"),
        ("Reinforcement to pad foundations", "rebar"),
        ("Portal frame columns", "steel_main"),
        ("Roof purlins", "steel_secondary"),
        ("Insulated roof panels", "roof_panel"),
        ("Hand-wash stations", "handwash"),
        ("Lighting circuits", "lighting_circuits"),
        ("Distribution transformer", "transformer"),
    ],
)
def test_items_get_the_right_rate(built, text, key):
    _, out = built
    matches = [ln for d, ln in _lines(out).items() if d.startswith(text)]
    assert matches and all(ln["key"] == key for ln in matches), text


def test_sized_rates_scale_with_capacity():
    lib = load_library("Saudi Arabia")
    small, big = price_items(
        [
            {
                "section": "Electrical",
                "description": "Distribution transformer 500 kVA",
                "unit": "nr",
                "qty": 1,
                "material": "",
            },
            {
                "section": "Electrical",
                "description": "Distribution transformer 1600 kVA",
                "unit": "nr",
                "qty": 1,
                "material": "",
            },
        ],
        lib,
    )
    assert big.rate > small.rate and small.rate == pytest.approx(40000 + 110 * 500)


def test_range_and_build_up(built):
    r, out = built
    est = json.loads((out / "model.cost.json").read_text())
    lk = est["likely"]
    assert est["low"]["total"] < lk["total"] < est["high"]["total"]
    assert lk["vat"] == pytest.approx(lk["before_vat"] * 0.15, rel=1e-3)
    assert r.facts["cost"]["per_m2"] > 1000
    assert abs(sum(est["coverage"].values()) - 1) < 1e-3


def test_excel_matches_the_app(built, tmp_path):
    import shutil
    import subprocess

    _, out = built
    wb = load_workbook(out / "model.boq.xlsx")
    ws = wb["BOQ"]
    assert ws["J4"].value.startswith("Rate source")
    priced = [ws.cell(r, 6).value for r in range(5, ws.max_row + 1) if ws.cell(r, 9).value]
    assert priced and all(isinstance(v, int | float) for v in priced)  # rates pre-filled
    recalc = "/mnt/skills/public/xlsx/scripts/recalc.py"
    if not shutil.which("soffice") and not shutil.which("libreoffice"):
        pytest.skip("LibreOffice not available to recalculate")
    copy = tmp_path / "b.xlsx"
    shutil.copy(out / "model.boq.xlsx", copy)
    subprocess.run(["python3", recalc, str(copy), "60"], check=False, capture_output=True)
    sm = load_workbook(copy, data_only=True)["Summary"]
    total = next(
        sm.cell(r, 2).value
        for r in range(1, sm.max_row + 1)
        if sm.cell(r, 1).value == "Total including VAT"
    )
    est = json.loads((out / "model.cost.json").read_text())
    assert total == pytest.approx(est["likely"]["total"], rel=1e-4)


def test_other_countries_are_not_priced_in_saudi_riyal(tmp_path):
    r = build_concept(
        Brief(plant_type="retail", built_up_area_m2=1200),
        tmp_path,
        project={"name": "UAE", "country": "United Arab Emirates"},
    )
    assert r.facts["cost"]["available"] is False
