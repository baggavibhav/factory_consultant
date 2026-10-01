"""Procurement API: supplier directory, RFQ packages, quotes, comparison and acceptance."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from fca.procurement.engine import (
    DEFAULT_ALLOWANCES,
    DEFAULT_WEIGHTS,
    PACKAGES,
    QuoteError,
    compare,
    package_lines,
    packages,
    read_quote,
    write_rfq,
)
from fca.settings import PROJECT_ROOT

Status = Literal["prospect", "vetting", "approved", "rejected"]
CHECKS = ("cr_verified", "iso_9001", "food_grade", "references", "financials", "site_visit")


class Supplier(BaseModel):
    id: str = ""
    name: str = Field(min_length=2, max_length=120)
    categories: list[str] = []
    country: str = "Saudi Arabia"
    city: str = ""
    website: str = ""
    source: str = ""
    contact: str = ""
    email: str = ""
    phone: str = ""
    cr_number: str = ""
    status: Status = "prospect"
    checks: dict[str, bool] = {}
    notes: str = ""
    created_at: str = ""


class Invite(BaseModel):
    supplier_ids: list[str]


class ProcurementSettings(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    allowances: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_ALLOWANCES))


def register(app: FastAPI, store, get_project, overrides_path: Path, recalc) -> None:
    sup_path = store.root / "_suppliers.json"

    def load_suppliers() -> list[dict]:
        if not sup_path.is_file():
            seed = json.loads(
                (PROJECT_ROOT / "config" / "suppliers" / "sa_prospects.json").read_text()
            )
            items = [
                Supplier(
                    **{**s, "id": uuid.uuid4().hex[:8], "created_at": datetime.now(UTC).isoformat()}
                ).model_dump()
                for s in seed["suppliers"]
            ]
            sup_path.write_text(json.dumps(items, indent=1))
        return json.loads(sup_path.read_text())

    def save_suppliers(items: list[dict]) -> None:
        sup_path.write_text(json.dumps(items, indent=1))

    def proc(project) -> dict:
        return project.procurement.setdefault("packages", {})

    def cost_of(project_id: str) -> dict:
        path = store.outputs(project_id) / "model.cost.json"
        if not path.is_file():
            raise HTTPException(
                409, "Build the model first: RFQs are generated from the priced BOQ"
            )
        cost = json.loads(path.read_text())
        if cost.get("available") is False:
            raise HTTPException(409, cost.get("reason", "No cost estimate"))
        return cost

    def check_pkg(key: str) -> None:
        if key not in PACKAGES:
            raise HTTPException(404, "Unknown package")

    # -- suppliers ------------------------------------------------------------------
    @app.get("/api/suppliers")
    def suppliers() -> dict:
        return {
            "suppliers": load_suppliers(),
            "categories": {k: v[0] for k, v in PACKAGES.items()},
            "checks": list(CHECKS),
        }

    @app.post("/api/suppliers", status_code=201)
    def add_supplier(body: Supplier) -> dict:
        items = load_suppliers()
        s = body.model_dump() | {
            "id": uuid.uuid4().hex[:8],
            "created_at": datetime.now(UTC).isoformat(),
        }
        items.append(s)
        save_suppliers(items)
        return s

    @app.patch("/api/suppliers/{sid}")
    def edit_supplier(sid: str, body: dict[str, Any]) -> dict:
        items = load_suppliers()
        s = next((x for x in items if x["id"] == sid), None)
        if s is None:
            raise HTTPException(404, "Supplier not found")
        merged = Supplier(
            **{**s, **{k: v for k, v in body.items() if k not in ("id", "created_at")}}
        )
        if merged.status == "approved" and not all(
            merged.checks.get(c) for c in ("cr_verified", "references")
        ):
            raise HTTPException(
                422, "Approve only after the commercial registration and references are checked"
            )
        s.update(merged.model_dump() | {"id": sid, "created_at": s["created_at"]})
        save_suppliers(items)
        return s

    @app.delete("/api/suppliers/{sid}")
    def delete_supplier(sid: str) -> dict:
        save_suppliers([x for x in load_suppliers() if x["id"] != sid])
        return {"deleted": sid}

    # -- packages and RFQs ----------------------------------------------------------------
    @app.get("/api/projects/{project_id}/procurement")
    def procurement(project_id: str) -> dict:
        project = get_project(project_id)
        cost = cost_of(project_id)
        state = proc(project)
        sups = {s["id"]: s for s in load_suppliers()}
        out = []
        for p in packages(cost):
            st = state.get(p["key"], {})
            quotes = st.get("quotes", [])
            accepted = next((q for q in quotes if q.get("accepted")), None)
            out.append(
                {
                    **p,
                    "invited": [sups[i] for i in st.get("invited", []) if i in sups],
                    "quotes": len(quotes),
                    "accepted": {
                        "supplier": sups.get(accepted.get("supplier_id") or "", {}).get("name")
                        or accepted.get("supplier_name"),
                        "id": accepted["id"],
                    }
                    if accepted
                    else None,
                    "suggested": [
                        s
                        for s in sups.values()
                        if p["key"] in s["categories"] and s["status"] != "rejected"
                    ],
                }
            )
        return {
            "packages": out,
            "currency": cost["currency"],
            "settings": project.procurement.get("settings") or ProcurementSettings().model_dump(),
        }

    @app.put("/api/projects/{project_id}/procurement/settings")
    def procurement_settings(project_id: str, body: ProcurementSettings) -> dict:
        project = get_project(project_id)
        project.procurement["settings"] = body.model_dump()
        store.save(project, None)
        return body.model_dump()

    @app.post("/api/projects/{project_id}/procurement/{key}/invite")
    def invite(project_id: str, key: str, body: Invite) -> dict:
        check_pkg(key)
        project = get_project(project_id)
        st = proc(project).setdefault(key, {"invited": [], "quotes": []})
        st["invited"] = sorted(set(st.get("invited", [])) | set(body.supplier_ids))
        store.save(
            project,
            ("procurement", f"{len(body.supplier_ids)} supplier(s) invited for {PACKAGES[key][0]}"),
        )
        return st

    @app.get("/api/projects/{project_id}/procurement/{key}/rfq.xlsx")
    def rfq(project_id: str, key: str) -> FileResponse:
        check_pkg(key)
        project = get_project(project_id)
        cost = cost_of(project_id)
        lines = package_lines(cost, key)
        boq = json.loads((store.outputs(project_id) / "model.boq.json").read_text())
        specs = {i["description"]: i["spec"] for s in boq["sections"] for i in s["items"]}
        path = store.outputs(project_id) / f"rfq_{key}.xlsx"
        write_rfq(
            path,
            {
                "id": project.id,
                "name": project.name,
                "city": project.city,
                "country": project.country,
            },
            key,
            lines,
            date.today(),
            specs,
        )
        safe = "".join(c if c.isalnum() else "_" for c in f"{project.name}_RFQ_{PACKAGES[key][0]}")
        return FileResponse(
            path,
            filename=f"{safe}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # -- quotes -----------------------------------------------------------------------------
    @app.post("/api/projects/{project_id}/procurement/{key}/quotes", status_code=201)
    async def upload_quote(
        project_id: str,
        key: str,
        file: Annotated[UploadFile, File()],
        supplier_id: Annotated[str, Form()] = "",
    ) -> dict:
        check_pkg(key)
        project = get_project(project_id)
        if not (file.filename or "").lower().endswith(".xlsx"):
            raise HTTPException(415, "Upload the returned RFQ Excel file (.xlsx)")
        qid = uuid.uuid4().hex[:8]
        qdir = store.outputs(project_id) / "quotes"
        qdir.mkdir(parents=True, exist_ok=True)
        path = qdir / f"{key}_{qid}.xlsx"
        path.write_bytes(await file.read())
        try:
            q = read_quote(path, key)
        except QuoteError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(422, f"Could not read this file: {exc}") from exc
        if not any(v["unit_price"] is not None for v in q["lines"].values()):
            path.unlink(missing_ok=True)
            raise HTTPException(422, "No unit prices were filled in this file")
        if not supplier_id and q["supplier_name"]:  # link to the directory by the name in the file
            wanted = q["supplier_name"].strip().lower()
            match = next((x for x in load_suppliers() if x["name"].strip().lower() == wanted), None)
            supplier_id = match["id"] if match else ""
        q |= {
            "id": qid,
            "supplier_id": supplier_id or None,
            "file": path.name,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "accepted": False,
        }
        st = proc(project).setdefault(key, {"invited": [], "quotes": []})
        st.setdefault("quotes", []).append(q)
        name = q["supplier_name"] or "a supplier"
        store.save(project, ("procurement", f"Quote received from {name} for {PACKAGES[key][0]}"))
        return {
            "id": qid,
            "supplier_name": q["supplier_name"],
            "priced": sum(1 for v in q["lines"].values() if v["unit_price"] is not None),
        }

    @app.delete("/api/projects/{project_id}/procurement/{key}/quotes/{qid}")
    def delete_quote(project_id: str, key: str, qid: str) -> dict:
        project = get_project(project_id)
        st = proc(project).get(key, {})
        st["quotes"] = [q for q in st.get("quotes", []) if q["id"] != qid]
        store.save(project, None)
        return {"deleted": qid}

    @app.get("/api/projects/{project_id}/procurement/{key}/compare")
    def compare_quotes(project_id: str, key: str) -> dict:
        check_pkg(key)
        project = get_project(project_id)
        cost = cost_of(project_id)
        st = proc(project).get(key, {})
        settings = project.procurement.get("settings") or {}
        sups = {s["id"]: s for s in load_suppliers()}
        result = compare(
            st.get("quotes", []),
            package_lines(cost, key),
            sups,
            settings.get("weights"),
            settings.get("allowances"),
        )
        return {"package": PACKAGES[key][0], "currency": cost["currency"], **result}

    @app.post("/api/projects/{project_id}/procurement/{key}/quotes/{qid}/accept")
    def accept_quote(project_id: str, key: str, qid: str):
        project = get_project(project_id)
        cost = cost_of(project_id)
        st = proc(project).get(key, {})
        quote = next((q for q in st.get("quotes", []) if q["id"] == qid), None)
        if quote is None:
            raise HTTPException(404, "Quote not found")
        settings = project.procurement.get("settings") or {}
        sups = {s["id"]: s for s in load_suppliers()}
        result = compare(
            [quote],
            package_lines(cost, key),
            sups,
            settings.get("weights"),
            settings.get("allowances"),
        )
        row = result["quotes"][0]
        keys: dict[str, list[float]] = {}
        by_desc = {ln["description"]: ln for ln in package_lines(cost, key)}
        for x in row["lines"]:
            if x["gap"]:
                continue
            rk = by_desc[x["description"]]["key"]
            if rk:
                agg = keys.setdefault(rk, [0.0, 0.0])
                agg[0] += x["amount"]
                agg[1] += x["qty"]
        edits = json.loads(overrides_path.read_text()) if overrides_path.is_file() else {}
        name = row["supplier"]
        for rk, (amount, qty) in keys.items():
            if qty <= 0:
                continue
            r = round(amount / qty, 2)
            edits[rk] = {
                "rate": r,
                "supply": None,
                "low": round(r * 0.95, 2),
                "high": round(r * 1.1, 2),
                "confidence": "quoted",
                "source": f"Quote from {name}"
                + (f", ref {quote['reference']}" if quote.get("reference") else ""),
                "date": quote.get("quote_date") or date.today().isoformat(),
                "url": "",
                "note": f"Accepted for {PACKAGES[key][0]} on project {project.name}",
            }
        overrides_path.write_text(json.dumps(edits, indent=1))
        for q in st["quotes"]:
            q["accepted"] = q["id"] == qid
        store.save(
            project,
            (
                "procurement",
                f"Quote from {name} accepted for {PACKAGES[key][0]}; {len(keys)} rate(s) updated",
            ),
        )
        return recalc(project)
