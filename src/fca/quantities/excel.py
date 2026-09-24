"""Excel bill of quantities: tender-style BOQ with rate cells for pricing,
live formulas for amounts and totals, a bill of materials and the assumptions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from fca.quantities.takeoff import SECTIONS, BoqItem

CURRENCY = {
    "Saudi Arabia": "SAR",
    "United Arab Emirates": "AED",
    "Oman": "OMR",
    "Qatar": "QAR",
    "Bahrain": "BHD",
    "Kuwait": "KWD",
    "Sri Lanka": "LKR",
    "India": "INR",
}

FONT = "Arial"
INK = "17222C"
BAND = PatternFill("solid", fgColor="E8ECEF")
HEAD = PatternFill("solid", fgColor="17222C")
INPUT = PatternFill("solid", fgColor="FFF2B3")  # cells for the user/contractor to fill
THIN = Side(style="thin", color="C9D1D8")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)


def _f(bold=False, size=10, color=INK, italic=False):
    return Font(name=FONT, bold=bold, size=size, color=color, italic=italic)


def _header(ws: Worksheet, row: int, labels: list[str], widths: list[int]) -> None:
    for i, (label, w) in enumerate(zip(labels, widths, strict=True), start=1):
        c = ws.cell(row=row, column=i, value=label)
        c.font = _f(bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 22


def write_boq_xlsx(
    path: Path,
    items: list[BoqItem],
    bom: list[dict],
    project: dict,
    assumptions: list[str],
    design: dict,
) -> Path:
    cur = CURRENCY.get(project.get("country", ""), "USD")
    wb = Workbook()

    # ------------------------------------------------------------------ BOQ
    ws = wb.active
    ws.title = "BOQ"
    ws.sheet_view.showGridLines = False
    ws["A1"] = f"Bill of quantities: {project['name']}"
    ws["A1"].font = _f(bold=True, size=14)
    ws["A2"] = (
        "Quantities are measured from the plant model. Enter unit rates in the yellow "
        f"Rate column ({cur}); amounts and totals calculate automatically."
    )
    ws["A2"].font = _f(italic=True, color="4B5966")
    hdr = [
        "Ref",
        "Description",
        "Specification",
        "Unit",
        "Quantity",
        f"Rate ({cur})",
        f"Amount ({cur})",
        "Basis of measurement",
        "Section",
    ]
    _header(ws, 4, hdr, [7, 42, 52, 7, 12, 13, 16, 52, 4])
    ws.freeze_panes = "C5"
    row = 5
    section_rows: dict[str, tuple[int, int]] = {}
    for n, section in enumerate(
        [s for s in SECTIONS if any(i.section == s for i in items)], start=1
    ):
        c = ws.cell(row=row, column=1, value=n)
        ws.cell(row=row, column=2, value=section.upper())
        for col in range(1, 10):
            ws.cell(row=row, column=col).fill = BAND
            ws.cell(row=row, column=col).font = _f(bold=True)
        c.alignment = Alignment(horizontal="left")
        row += 1
        first = row
        for k, it in enumerate([i for i in items if i.section == section], start=1):
            values = [
                f"{n}.{k:02d}",
                it.description,
                it.spec,
                it.unit,
                it.qty,
                None,
                f'=IF(F{row}="","",E{row}*F{row})',
                it.basis,
                section,
            ]
            for col, v in enumerate(values, start=1):
                cell = ws.cell(row=row, column=col, value=v)
                cell.font = _f()
                cell.border = BOX
                cell.alignment = Alignment(vertical="top", wrap_text=col in (2, 3, 8))
            ws.cell(row=row, column=5).number_format = "#,##0.00"
            ws.cell(row=row, column=6).fill = INPUT
            ws.cell(row=row, column=6).number_format = "#,##0.00"
            ws.cell(row=row, column=7).number_format = "#,##0.00"
            ws.cell(row=row, column=9).font = _f(color="FFFFFF", size=6)
            row += 1
        last = row - 1
        section_rows[section] = (first, last)
        ws.cell(row=row, column=2, value=f"Total {section.lower()}").font = _f(bold=True)
        tot = ws.cell(row=row, column=7, value=f"=SUM(G{first}:G{last})")
        tot.font = _f(bold=True)
        tot.number_format = "#,##0.00"
        tot.border = Border(top=Side(style="thin", color=INK))
        row += 2
    ws.column_dimensions["I"].hidden = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "4:4"
    boq_last = row

    # --------------------------------------------------------------- Summary
    sm = wb.create_sheet("Summary", 0)
    sm.sheet_view.showGridLines = False
    sm.column_dimensions["A"].width = 44
    sm.column_dimensions["B"].width = 22
    sm.column_dimensions["C"].width = 60
    sm["A1"] = "Factory Consultant: cost summary"
    sm["A1"].font = _f(bold=True, size=16)
    info = [
        ("Project", project["name"]),
        ("Plant type", project.get("plant_type_label", "")),
        ("Location", ", ".join(x for x in (project.get("city"), project.get("country")) if x)),
        ("Basis", project.get("basis", "")),
        ("Generated", datetime.now().strftime("%d %b %Y %H:%M")),
        ("Currency", cur),
    ]
    for i, (k, v) in enumerate(info, start=3):
        sm.cell(row=i, column=1, value=k).font = _f(color="4B5966")
        sm.cell(row=i, column=2, value=v).font = _f(bold=True)
    r0 = 3 + len(info) + 1
    sm.cell(row=r0, column=1, value="How to use").font = _f(bold=True)
    sm.cell(
        row=r0 + 1,
        column=1,
        value=f"Enter unit rates in the yellow cells of the BOQ sheet (for example 450 for "
        f"{cur} 450 per m³). Section totals, contingency and the grand total below update "
        "automatically. Quantities come from a concept or drawing-based model: check the "
        "basis column and the Assumptions sheet before tender.",
    ).font = _f(color="4B5966")
    sm.merge_cells(start_row=r0 + 1, start_column=1, end_row=r0 + 1, end_column=3)
    sm.cell(row=r0 + 1, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    sm.row_dimensions[r0 + 1].height = 52
    t0 = r0 + 3
    _header(sm, t0, ["Section", f"Amount ({cur})", "Items"], [44, 22, 60])
    rr = t0 + 1
    for section, (first, last) in section_rows.items():
        sm.cell(row=rr, column=1, value=section).font = _f()
        a = sm.cell(
            row=rr, column=2, value=f"=SUMIF(BOQ!$I$5:$I${boq_last},A{rr},BOQ!$G$5:$G${boq_last})"
        )
        a.number_format = "#,##0.00"
        a.font = _f()
        sm.cell(row=rr, column=3, value=f"{last - first + 1} items").font = _f(color="4B5966")
        for col in (1, 2, 3):
            sm.cell(row=rr, column=col).border = BOX
        rr += 1
    sub = rr
    sm.cell(row=sub, column=1, value="Subtotal").font = _f(bold=True)
    c = sm.cell(row=sub, column=2, value=f"=SUM(B{t0 + 1}:B{sub - 1})")
    c.font = _f(bold=True)
    c.number_format = "#,##0.00"
    sm.cell(row=sub + 1, column=1, value="Contingency (edit the rate)").font = _f()
    pct = sm.cell(row=sub + 1, column=3, value=0.10)
    pct.fill = INPUT
    pct.number_format = "0%"
    pct.font = _f()
    c = sm.cell(row=sub + 1, column=2, value=f"=B{sub}*C{sub + 1}")
    c.number_format = "#,##0.00"
    c.font = _f()
    sm.cell(row=sub + 2, column=1, value="Total including contingency").font = _f(
        bold=True, size=11
    )
    c = sm.cell(row=sub + 2, column=2, value=f"=B{sub}+B{sub + 1}")
    c.number_format = "#,##0.00"
    c.font = _f(bold=True, size=11)
    c.border = Border(top=Side(style="medium", color=INK))
    note = sm.cell(
        row=sub + 4,
        column=1,
        value="Contingency 10% is a typical concept-stage allowance; adjust in the yellow cell.",
    )
    note.font = _f(italic=True, color="4B5966")

    # ------------------------------------------------------------------ BOM
    bm = wb.create_sheet("BOM")
    bm.sheet_view.showGridLines = False
    bm["A1"] = "Bill of materials"
    bm["A1"].font = _f(bold=True, size=14)
    bm["A2"] = (
        "Net quantities from the BOQ grouped by material; order quantity adds the waste "
        "allowance (yellow, editable)."
    )
    bm["A2"].font = _f(italic=True, color="4B5966")
    _header(
        bm,
        4,
        [
            "Material",
            "Specification",
            "Unit",
            "Net quantity",
            "Waste allowance",
            "Order quantity",
            "Used in",
        ],
        [40, 60, 7, 14, 14, 15, 30],
    )
    bm.freeze_panes = "B5"
    for i, g in enumerate(bom, start=5):
        vals = [
            g["material"],
            g["spec"],
            g["unit"],
            g["qty"],
            g["waste"],
            f"=ROUNDUP(D{i}*(1+E{i}),0)",
            g["section"],
        ]
        for col, v in enumerate(vals, start=1):
            cell = bm.cell(row=i, column=col, value=v)
            cell.font = _f()
            cell.border = BOX
            cell.alignment = Alignment(vertical="top", wrap_text=col in (1, 2))
        bm.cell(row=i, column=4).number_format = "#,##0.00"
        bm.cell(row=i, column=5).number_format = "0%"
        bm.cell(row=i, column=5).fill = INPUT
        bm.cell(row=i, column=6).number_format = "#,##0"

    # --------------------------------------------------------- Design basis
    ds = wb.create_sheet("Design basis")
    ds.sheet_view.showGridLines = False
    ds.column_dimensions["A"].width = 36
    ds.column_dimensions["B"].width = 70
    ds["A1"] = "Design basis and assumptions"
    ds["A1"].font = _f(bold=True, size=14)
    r = 3
    for group, values in design.items():
        ds.cell(row=r, column=1, value=group).font = _f(bold=True)
        r += 1
        for k, v in values.items():
            ds.cell(row=r, column=1, value=k).font = _f(color="4B5966")
            ds.cell(row=r, column=2, value=v).font = _f()
            r += 1
        r += 1
    ds.cell(row=r, column=1, value="Assumptions to confirm").font = _f(bold=True)
    r += 1
    for a in assumptions:
        cell = ds.cell(row=r, column=1, value=f"• {a}")
        cell.font = _f()
        ds.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        cell.alignment = Alignment(wrap_text=True)
        r += 1

    for sheet in wb.worksheets:
        sheet.sheet_properties.tabColor = "F2B705" if sheet.title == "Summary" else "17222C"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
