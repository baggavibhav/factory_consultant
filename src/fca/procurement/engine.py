"""Procurement engine.

- Packages: the priced BOQ grouped into the trades suppliers quote for.
- RFQ: an Excel workbook per package that suppliers fill in (prices, compliance,
  commercial terms). Hidden cells identify the project, package and lines.
- Quote import: reads a returned RFQ workbook.
- Normalisation: excludes VAT, adds allowances for delivery/installation when a quote
  excludes them, prices missing lines at library rates, so quotes compare like for like.
- Scoring: best value = price, compliance, lead time and completeness (weights editable),
  with flags for outliers, gaps, expired validity and unapproved suppliers.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

PACKAGES: dict[str, tuple[str, list[str]]] = {
    "civil": ("Civil works and concrete", ["Substructure", "External works"]),
    "steel": ("Structural steel", ["Structural steel frame"]),
    "envelope": ("Building envelope and doors", ["Building envelope"]),
    "internal": (
        "Partitions, cold rooms and mezzanine",
        ["Internal walls, cold rooms and mezzanine"],
    ),
    "finishes": ("Floor finishes", ["Floor finishes"]),
    "electrical": ("Electrical", ["Electrical"]),
    "plumbing": ("Water supply and drainage", ["Water supply", "Drainage"]),
    "fire": ("Fire protection", ["Fire protection"]),
    "hvac": ("Refrigeration and ventilation", ["Refrigeration and ventilation"]),
    "utilities": ("Compressed air and gas", ["Compressed air", "Gas"]),
}
DEFAULT_WEIGHTS = {"price": 0.6, "compliance": 0.2, "lead_time": 0.1, "completeness": 0.1}
DEFAULT_ALLOWANCES = {"delivery": 0.03, "installation": 0.30}

FONT = "Arial"
INPUT = PatternFill("solid", fgColor="FFF2B3")
HEAD = PatternFill("solid", fgColor="17222C")


def package_lines(cost: dict, key: str) -> list[dict]:
    sections = PACKAGES[key][1]
    return [ln for ln in cost.get("lines", []) if ln["section"] in sections]


def packages(cost: dict) -> list[dict]:
    out = []
    for key, (name, _) in PACKAGES.items():
        lines = package_lines(cost, key)
        if lines:
            out.append(
                {
                    "key": key,
                    "name": name,
                    "lines": len(lines),
                    "estimate": round(sum(ln["amount"] for ln in lines), 0),
                }
            )
    return out


# ---------------------------------------------------------------------------- RFQ
def write_rfq(
    path: Path, project: dict, key: str, lines: list[dict], issued: date, specs: dict[str, str]
) -> Path:
    name = PACKAGES[key][0]
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    ins.sheet_view.showGridLines = False
    ins.column_dimensions["A"].width = 30
    ins.column_dimensions["B"].width = 80
    ins["A1"] = f"Request for quotation: {name}"
    ins["A1"].font = Font(name=FONT, bold=True, size=15)
    rows = [
        ("Project", project["name"]),
        ("Location", ", ".join(x for x in (project.get("city"), project.get("country")) if x)),
        ("Package", name),
        ("Issued", issued.isoformat()),
        ("Please return by", (issued + timedelta(days=14)).isoformat()),
        ("Prices", "In SAR, excluding VAT, per unit, for the specification stated on each line."),
        ("Validity requested", "90 days from your quote date."),
        (
            "How to reply",
            "Fill in the yellow cells on the Prices and Commercial sheets only, save, "
            "and return this file. Do not add, remove or reorder rows.",
        ),
        (
            "Alternatives",
            "If you offer a different product, answer 'No' under 'Complies' and "
            "describe the alternative in the remarks column.",
        ),
        (
            "Quantities",
            "Quantities are measured from a concept design and may change. Confirm "
            "your unit prices hold for ±20% quantity changes.",
        ),
    ]
    for i, (k, v) in enumerate(rows, start=3):
        ins.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True)
        c = ins.cell(row=i, column=2, value=v)
        c.font = Font(name=FONT)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("Prices")
    ws.sheet_view.showGridLines = False
    hdr = [
        "Ref",
        "Description",
        "Specification",
        "Unit",
        "Quantity",
        "Unit price (SAR, excl. VAT)",
        "Amount (SAR)",
        "Complies with specification? (Yes/No)",
        "Remarks / alternative offered",
        "line_id",
    ]
    widths = [6, 44, 56, 7, 12, 16, 16, 16, 40, 4]
    for i, (h, w) in enumerate(zip(hdr, widths, strict=True), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[1].height = 34
    yn = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws.add_data_validation(yn)
    for r, ln in enumerate(lines, start=2):
        values = [
            r - 1,
            ln["description"],
            specs.get(ln["description"], ""),
            ln["unit"],
            ln["qty"],
            None,
            f'=IF(F{r}="","",E{r}*F{r})',
            None,
            None,
            f"{ln['section']}|{ln['description']}",
        ]
        for col, v in enumerate(values, start=1):
            c = ws.cell(row=r, column=col, value=v)
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(wrap_text=col in (2, 3, 9), vertical="top")
        for col in (6, 8, 9):
            ws.cell(row=r, column=col).fill = INPUT
        ws.cell(row=r, column=5).number_format = "#,##0.00"
        ws.cell(row=r, column=6).number_format = "#,##0.00"
        ws.cell(row=r, column=7).number_format = "#,##0.00"
        yn.add(ws.cell(row=r, column=8))
    last = len(lines) + 1
    ws.cell(row=last + 1, column=2, value="Total (SAR, excl. VAT)").font = Font(
        name=FONT, bold=True
    )
    t = ws.cell(row=last + 1, column=7, value=f"=SUM(G2:G{last})")
    t.font = Font(name=FONT, bold=True)
    t.number_format = "#,##0.00"
    ws.column_dimensions["J"].hidden = True
    ws.freeze_panes = "C2"

    cm = wb.create_sheet("Commercial")
    cm.sheet_view.showGridLines = False
    cm.column_dimensions["A"].width = 44
    cm.column_dimensions["B"].width = 44
    fields = [
        "Supplier name",
        "Commercial registration (CR) number",
        "Quote reference",
        "Quote date",
        "Valid until (date)",
        "Lead time (weeks from order)",
        "Delivery to site included? (Yes/No)",
        "Installation included? (Yes/No)",
        "VAT included in unit prices? (Yes/No)",
        "Payment terms",
        "Contact name, phone and email",
    ]
    cm["A1"] = "Commercial terms"
    cm["A1"].font = Font(name=FONT, bold=True, size=13)
    for i, f in enumerate(fields, start=3):
        cm.cell(row=i, column=1, value=f).font = Font(name=FONT)
        cm.cell(row=i, column=2).fill = INPUT
    meta = wb.create_sheet("_meta")
    meta["A1"], meta["B1"] = "project_id", project.get("id", "")
    meta["A2"], meta["B2"] = "package", key
    meta["A3"], meta["B3"] = "issued", issued.isoformat()
    meta.sheet_state = "hidden"
    wb.save(path)
    return path


# ----------------------------------------------------------------------- quote import
class QuoteError(ValueError):
    pass


def _yes(v) -> bool | None:
    if v is None or str(v).strip() == "":
        return None
    return str(v).strip().lower() in ("yes", "y", "true", "1", "نعم")


def _date(v) -> str | None:
    if v is None or v == "":
        return None
    if hasattr(v, "isoformat"):
        return v.date().isoformat() if hasattr(v, "date") else v.isoformat()
    try:
        return date.fromisoformat(str(v).strip()[:10]).isoformat()
    except ValueError:
        return None


def read_quote(path: Path, key: str) -> dict:
    wb = load_workbook(path, data_only=False)
    if "Prices" not in wb.sheetnames or "Commercial" not in wb.sheetnames:
        raise QuoteError("This is not a returned RFQ file from Factory Consultant.")
    if "_meta" in wb.sheetnames and wb["_meta"]["B2"].value not in (None, key):
        raise QuoteError(f"This file is the RFQ for another package ({wb['_meta']['B2'].value}).")
    ws = wb["Prices"]
    lines = {}
    for r in range(2, ws.max_row + 1):
        lid = ws.cell(row=r, column=10).value
        if not lid:
            continue
        price = ws.cell(row=r, column=6).value
        try:
            price = float(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        lines[lid] = {
            "unit_price": price,
            "complies": _yes(ws.cell(row=r, column=8).value),
            "remarks": ws.cell(row=r, column=9).value or "",
        }
    cm = wb["Commercial"]
    v = [cm.cell(row=i, column=2).value for i in range(3, 14)]
    try:
        lead = float(v[5]) if v[5] not in (None, "") else None
    except (TypeError, ValueError):
        lead = None
    return {
        "supplier_name": v[0] or "",
        "cr_number": str(v[1] or ""),
        "reference": str(v[2] or ""),
        "quote_date": _date(v[3]),
        "valid_until": _date(v[4]),
        "lead_time_weeks": lead,
        "delivery_included": _yes(v[6]),
        "installation_included": _yes(v[7]),
        "vat_included": _yes(v[8]),
        "payment_terms": str(v[9] or ""),
        "contact": str(v[10] or ""),
        "lines": lines,
    }


# ------------------------------------------------------------ normalise and compare
def normalise(quote: dict, lines: list[dict], allowances: dict, vat: float = 0.15) -> dict:
    """Comparable total (SAR excl. VAT, delivered and installed) plus per-line prices."""
    total = gaps = 0.0
    priced = 0
    out_lines = []
    adj = 1.0
    if quote.get("vat_included"):
        adj /= 1 + vat
    extra = 0.0
    if quote.get("delivery_included") is False:
        extra += allowances.get("delivery", 0.03)
    if quote.get("installation_included") is False:
        extra += allowances.get("installation", 0.30)
    for ln in lines:
        lid = f"{ln['section']}|{ln['description']}"
        q = quote["lines"].get(lid, {})
        up = q.get("unit_price")
        if up is not None:
            unit = up * adj * (1 + extra)
            amount = unit * ln["qty"]
            priced += 1
        else:
            unit = ln["rate"] or 0
            amount = unit * ln["qty"]
            gaps += amount
        total += amount
        out_lines.append(
            {
                "id": lid,
                "description": ln["description"],
                "qty": ln["qty"],
                "unit": ln["unit"],
                "quoted": up,
                "normalised_rate": round(unit, 2),
                "amount": round(amount, 2),
                "gap": up is None,
                "complies": q.get("complies"),
                "remarks": q.get("remarks", ""),
                "library_rate": ln["rate"],
            }
        )
    return {
        "total": round(total, 2),
        "gaps_value": round(gaps, 2),
        "priced_lines": priced,
        "lines": out_lines,
        "adjustment": {"vat_removed": bool(quote.get("vat_included")), "allowance_added": extra},
    }


def compare(
    quotes: list[dict],
    lines: list[dict],
    suppliers: dict[str, dict],
    weights: dict | None = None,
    allowances: dict | None = None,
    today: date | None = None,
) -> dict:
    """Score quotes for one package and recommend the best value."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    allowances = {**DEFAULT_ALLOWANCES, **(allowances or {})}
    today = today or date.today()
    if not quotes:
        return {"quotes": [], "recommended": None}
    norm = {q["id"]: normalise(q, lines, allowances) for q in quotes}
    totals = [n["total"] for n in norm.values() if n["total"] > 0]
    best_total = min(totals) if totals else 0
    leads = [q["lead_time_weeks"] for q in quotes if q.get("lead_time_weeks")]
    best_lead = min(leads) if leads else None
    medians = {}
    for ln in lines:
        lid = f"{ln['section']}|{ln['description']}"
        vals = [
            n["lines"][i]["normalised_rate"]
            for n in norm.values()
            for i, x in enumerate(n["lines"])
            if x["id"] == lid and not x["gap"]
        ]
        medians[lid] = statistics.median(vals) if vals else None
    rows = []
    n_lines = max(len(lines), 1)
    for q in quotes:
        n = norm[q["id"]]
        flags = []
        sup = suppliers.get(q.get("supplier_id") or "", {})
        if sup.get("status") != "approved":
            flags.append("Supplier not yet approved (vetting incomplete)")
        if q.get("valid_until") and date.fromisoformat(q["valid_until"]) < today:
            flags.append(f"Quote expired on {q['valid_until']}")
        gaps = [x for x in n["lines"] if x["gap"]]
        if gaps:
            flags.append(f"{len(gaps)} line(s) not priced; filled at library rates for comparison")
        non = [x for x in n["lines"] if x["complies"] is False]
        if non:
            flags.append(f"{len(non)} line(s) do not comply with the specification")
        for x in n["lines"]:
            ref = medians.get(x["id"]) or x["library_rate"]
            if (
                not x["gap"]
                and ref
                and (x["normalised_rate"] < 0.6 * ref or x["normalised_rate"] > 1.6 * ref)
            ):
                flags.append(
                    f"Check price: {x['description']} ({x['normalised_rate']:,.0f} vs "
                    f"typical {ref:,.0f})"
                )
        if n["adjustment"]["allowance_added"]:
            flags.append(
                f"Allowance of {n['adjustment']['allowance_added']:.0%} added for delivery/"
                "installation not included"
            )
        confirmed = sum(1 for x in n["lines"] if x["complies"] is True)
        scores = {
            "price": 100 * best_total / n["total"] if n["total"] else 0,
            "compliance": 100
            * (
                confirmed
                + 0.5 * sum(1 for x in n["lines"] if x["complies"] is None and not x["gap"])
            )
            / n_lines,
            "lead_time": 100 * best_lead / q["lead_time_weeks"]
            if best_lead and q.get("lead_time_weeks")
            else 50,
            "completeness": 100 * n["priced_lines"] / n_lines,
        }
        score = sum(weights[k] * scores[k] for k in weights)
        if any(f.startswith("Quote expired") for f in flags):
            score *= 0.5
        rows.append(
            {
                "quote_id": q["id"],
                "supplier_id": q.get("supplier_id"),
                "supplier": sup.get("name") or q.get("supplier_name") or "Unknown supplier",
                "total": n["total"],
                "gaps_value": n["gaps_value"],
                "lead_time_weeks": q.get("lead_time_weeks"),
                "valid_until": q.get("valid_until"),
                "scores": {k: round(v, 1) for k, v in scores.items()},
                "score": round(score, 1),
                "flags": flags,
                "lines": n["lines"],
            }
        )
    rows.sort(key=lambda r: -r["score"])
    top = rows[0]
    cheapest = min(rows, key=lambda r: r["total"])
    reasons = [f"highest overall score ({top['score']:.0f}/100)"]
    if top is cheapest:
        reasons.append("lowest comparable price")
    else:
        weaker = (
            "compliance"
            if top["scores"]["compliance"] > cheapest["scores"]["compliance"]
            else "lead time or completeness"
        )
        reasons.append(
            f"{(top['total'] / cheapest['total'] - 1):.0%} above the cheapest, which "
            f"scores lower on {weaker}"
        )
    if top["scores"]["completeness"] == 100:
        reasons.append("prices every line")
    return {
        "quotes": rows,
        "recommended": top["quote_id"],
        "reasons": reasons,
        "weights": weights,
        "allowances": allowances,
        "library_total": round(sum(ln["amount"] for ln in lines), 0),
    }
