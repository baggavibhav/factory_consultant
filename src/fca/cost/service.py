"""Write (or recompute) a project's cost estimate from its saved BOQ."""

from __future__ import annotations

import json
from pathlib import Path

from fca.cost.estimate import COUNTRY_LIBRARY, estimate, load_library


def summary(est: dict) -> dict:
    return {
        "available": True,
        "currency": est["currency"],
        "total": est["likely"]["total"],
        "low": est["low"]["total"],
        "high": est["high"]["total"],
        "before_vat": est["likely"]["before_vat"],
        "per_m2": est["per_m2"],
        "per_sqft": est["per_sqft"],
        "coverage": est["coverage"],
    }


def write_cost(
    out_dir: Path, name: str, settings: dict | None = None, overrides: Path | None = None
) -> dict:
    """Estimate from ``<name>.boq.json``; write ``<name>.cost.json`` and a priced Excel BOQ."""
    from fca.quantities.excel import write_boq_xlsx
    from fca.quantities.takeoff import BoqItem

    out_dir = Path(out_dir)
    boq = json.loads((out_dir / f"{name}.boq.json").read_text(encoding="utf-8"))
    project = boq.get("project", {})
    country = project.get("country", "")
    items = [BoqItem(**d) for sec in boq["sections"] for d in sec["items"]]
    if country not in COUNTRY_LIBRARY:
        result = {
            "available": False,
            "reason": f"No rate library for {country or 'this country'} yet; Saudi Arabia is "
            "supported. The BOQ can still be priced by hand in Excel.",
        }
        (out_dir / f"{name}.cost.json").write_text(json.dumps(result), encoding="utf-8")
        write_boq_xlsx(
            out_dir / f"{name}.boq.xlsx",
            items,
            boq["bom"],
            project,
            boq.get("assumptions", []),
            boq.get("design", {}),
            None,
        )
        return result
    lib = load_library(country, overrides)
    est = estimate(boq, lib, settings or {}, boq.get("footprint_m2") or 0)
    (out_dir / f"{name}.cost.json").write_text(json.dumps(est, indent=1), encoding="utf-8")
    write_boq_xlsx(
        out_dir / f"{name}.boq.xlsx",
        items,
        boq["bom"],
        project,
        boq.get("assumptions", []),
        boq.get("design", {}),
        est,
    )
    return summary(est)
