from __future__ import annotations

import pytest
from openpyxl import load_workbook

from fca.concept.brief import Brief, resolve
from fca.concept.layout import build_layout
from fca.concept.mep import build_mep
from fca.concept.program import build_program, load_template
from fca.pipeline import build_concept
from fca.quantities.takeoff import SECTIONS, bill_of_materials, takeoff
from fca.structure.frame import generate_frame


@pytest.fixture(scope="module")
def concept():
    values, _ = resolve(Brief(plant_type="industrial", built_up_area_m2=4000, blast_freezer=True))
    tpl = load_template("industrial")
    lay = build_layout(values, build_program(values, tpl), tpl)
    members = generate_frame(lay.config, lay.frame)
    mep = build_mep(lay, values, "industrial")
    items = takeoff(
        lay.config, members, lay.segments, "concept", rooms=lay.rooms, mep=mep, plot=lay.plot
    )
    return lay, members, mep, items


def _qty(items, text):
    return sum(i.qty for i in items if text in i.description)


def test_slab_and_roof_follow_the_footprint(concept):
    lay, _, _, items = concept
    area = lay.building.width * lay.building.depth
    assert _qty(items, "Ground-bearing floor slab") == pytest.approx(area * 0.2, rel=1e-3)
    assert area < _qty(items, "roof panels") < area * 1.01  # sloped area slightly larger


def test_steel_tonnage_matches_member_lengths(concept):
    _, members, _, items = concept
    cols = sum(m.length for m in members if m.kind == "column")
    # 40 m clear span -> column section from the span table (UB 533x210x101, 101 kg/m)
    assert _qty(items, "Portal frame columns") == pytest.approx(cols * 101.0 / 1000, rel=1e-3)
    assert _qty(items, "Rafter haunches") > 0
    steel = sum(i.qty for i in items if i.section == "Structural steel frame")
    assert 15 < steel / 4 < 45  # kg/m² band typical of portal-frame plants (t per 1,000 m²)


def test_every_item_has_spec_and_basis(concept):
    *_, items = concept
    for i in items:
        assert i.basis, i.description
        assert i.section in SECTIONS
        if i.section != "External works":
            assert i.spec, i.description


def test_mep_sections_present(concept):
    *_, items = concept
    sections = {i.section for i in items}
    for s in (
        "Electrical",
        "Water supply",
        "Drainage",
        "Fire protection",
        "Refrigeration and ventilation",
        "Compressed air",
        "Gas",
    ):
        assert s in sections


def test_mep_rules(concept):
    lay, _, mep, _ = concept
    assert mep.facts["electrical"]["transformer_kva"] >= mep.facts["electrical"]["design_kva"]
    assert mep.facts["fire"]["hydrants"] >= 4
    hydrant_ring = next(r for r in mep.routes if r.kind == "Hydrant ring main")
    assert all(lay.plot.contains(x, y) for x, y, _ in hydrant_ring.points)


def test_cold_room_walls_not_double_counted(concept):
    lay, members, _mep, items = concept
    without_rooms = takeoff(lay.config, members, lay.segments, "concept", rooms=[], mep=None)
    assert _qty(items, "hygienic partitions") < _qty(without_rooms, "hygienic partitions")


def test_bom_groups_and_keeps_totals(concept):
    *_, items = concept
    bom = bill_of_materials(items)
    assert sum(g["qty"] for g in bom if g["unit"] == "t") == pytest.approx(
        sum(i.qty for i in items if i.unit == "t"), rel=1e-6
    )


def test_excel_workbook_structure(tmp_path):
    build_concept(
        Brief(plant_type="retail", built_up_area_m2=1200),
        tmp_path,
        project={"name": "Retail test", "country": "Oman"},
    )
    wb = load_workbook(tmp_path / "model.boq.xlsx")
    assert wb.sheetnames == ["Summary", "BOQ", "BOM", "Design basis"]
    ws = wb["BOQ"]
    assert ws["F4"].value == "Rate (OMR)"
    formulas = [c.value for c in ws["G"] if isinstance(c.value, str) and c.value.startswith("=")]
    assert any(f.startswith("=IF(F") for f in formulas)
    assert any(f.startswith("=SUM(G") for f in formulas)
