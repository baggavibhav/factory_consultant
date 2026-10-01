"""Cost estimate: BOQ quantities × rates from the library, with a range, on-costs,
escalation to the construction midpoint and VAT, checked against a benchmark.

Every priced line keeps the rate's source, date and confidence, so the estimate can
say how much of the total rests on official, published or allowance prices.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from fca.settings import PROJECT_ROOT

RATES_DIR = PROJECT_ROOT / "config" / "rates"
COUNTRY_LIBRARY = {"Saudi Arabia": "sa"}


@dataclass
class Rate:
    key: str
    match: list[str]
    unit: str
    rate: float | None = None
    supply: float | None = None
    factor: float = 1.0
    low: float | None = None
    high: float | None = None
    per: str | None = None
    per_value: float = 0.0
    low_factor: float = 0.8
    high_factor: float = 1.25
    confidence: str = "allowance"
    source: str = ""
    url: str = ""
    date: str = ""
    note: str = ""
    edited: bool = False

    @property
    def installed(self) -> float:
        return self.rate if self.rate is not None else round((self.supply or 0) * self.factor, 2)


@dataclass
class Library:
    name: str
    currency: str
    rate_date: str
    escalation_per_year: float
    defaults: dict
    benchmarks: list[dict]
    rates: list[Rate]


def load_library(country: str, overrides: Path | None = None) -> Library:
    code = COUNTRY_LIBRARY.get(country, "sa")
    data = tomllib.loads((RATES_DIR / f"{code}.toml").read_text(encoding="utf-8"))
    rates = [Rate(**r) for r in data["rate"]]
    if overrides and overrides.is_file():
        edits = json.loads(overrides.read_text(encoding="utf-8"))
        for r in rates:
            if r.key in edits:
                for k, v in edits[r.key].items():
                    setattr(r, k, v)
                r.edited = True
    return Library(
        data["name"],
        data["currency"],
        data["rate_date"],
        data["escalation_per_year"],
        data["defaults"],
        data.get("benchmark", []),
        rates,
    )


def _find(lib: Library, text: str, unit: str) -> tuple[Rate, str] | None:
    """The rate whose match text is the longest one contained in ``text`` (same unit)."""
    low = text.lower()
    best = None
    for r in lib.rates:
        if r.unit != unit:
            continue
        for m in r.match:
            if m.lower() in low and (best is None or len(m) > len(best[1])):
                best = (r, m)
    return best


def _value(text: str, per: str) -> float | None:
    pattern = r"([\d,.]+)\s*kVA" if per == "kva" else r"([\d,.]+)\s*m³"
    m = re.search(pattern, text)
    return float(m.group(1).replace(",", "")) if m else None


@dataclass
class Line:
    section: str
    description: str
    unit: str
    qty: float
    rate: float | None
    low_rate: float | None
    high_rate: float | None
    amount: float
    low: float
    high: float
    key: str | None
    confidence: str
    source: str
    url: str
    date: str


def price_items(items: list[dict], lib: Library) -> list[Line]:
    out = []
    for it in items:
        found = _find(lib, f"{it['description']} {it.get('material', '')}", it["unit"])
        if not found:
            out.append(
                Line(
                    it["section"],
                    it["description"],
                    it["unit"],
                    it["qty"],
                    None,
                    None,
                    None,
                    0,
                    0,
                    0,
                    None,
                    "unpriced",
                    "No rate in the library",
                    "",
                    "",
                )
            )
            continue
        r, _ = found
        rate = r.installed
        lo, hi = r.low, r.high
        if r.per:
            v = _value(it["description"], r.per)
            if v is not None:
                rate = r.installed + r.per_value * v
            lo, hi = rate * r.low_factor, rate * r.high_factor
        lo = lo if lo is not None else rate * r.low_factor
        hi = hi if hi is not None else rate * r.high_factor
        q = it["qty"]
        out.append(
            Line(
                it["section"],
                it["description"],
                it["unit"],
                q,
                round(rate, 2),
                round(lo, 2),
                round(hi, 2),
                round(q * rate, 2),
                round(q * lo, 2),
                round(q * hi, 2),
                r.key,
                r.confidence + (" (edited)" if r.edited else ""),
                r.source,
                r.url,
                r.date or lib.rate_date,
            )
        )
    return out


def estimate(boq: dict, lib: Library, settings: dict, footprint_m2: float) -> dict:
    s = {**lib.defaults, **{k: v for k, v in (settings or {}).items() if v is not None}}
    items = [i for sec in boq["sections"] for i in sec["items"]]
    lines = price_items(items, lib)
    direct = sum(l_.amount for l_ in lines)
    direct_lo = sum(l_.low for l_ in lines)
    direct_hi = sum(l_.high for l_ in lines)

    # Escalation from the library's price date to the middle of construction.
    start = date.fromisoformat(s.get("construction_start") or _default_start())
    months = float(s.get("construction_months", 14))
    rate_date = date.fromisoformat(lib.rate_date)
    mid_years = ((start - rate_date).days + months * 30.4 / 2) / 365.25
    esc = (1 + s.get("escalation_per_year", lib.escalation_per_year)) ** max(mid_years, 0) - 1

    def build_up(base: float) -> dict:
        prelims = base * s["preliminaries"]
        ohp = (base + prelims) * s["overhead_profit"]
        cont = (base + prelims + ohp) * s["contingency"]
        subtotal = base + prelims + ohp + cont
        escal = subtotal * esc
        before_vat = subtotal + escal
        vat = before_vat * s["vat"]
        return {
            "direct": base,
            "preliminaries": prelims,
            "overhead_profit": ohp,
            "contingency": cont,
            "escalation": escal,
            "before_vat": before_vat,
            "vat": vat,
            "total": before_vat + vat,
        }

    likely, low, high = build_up(direct), build_up(direct_lo), build_up(direct_hi)
    sections: dict[str, float] = {}
    for l_ in lines:
        sections[l_.section] = sections.get(l_.section, 0) + l_.amount
    coverage: dict[str, float] = {}
    for l_ in lines:
        c = l_.confidence.replace(" (edited)", "")
        coverage[c] = coverage.get(c, 0) + l_.amount
    per_m2 = likely["before_vat"] / footprint_m2 if footprint_m2 else None
    bench = []
    for b in lib.benchmarks:
        status = None
        if per_m2 is not None:
            status = (
                "below"
                if per_m2 < b["low_per_m2"]
                else "above"
                if per_m2 > b["high_per_m2"]
                else "within"
            )
        bench.append({**b, "status": status})
    r2 = lambda d: {k: round(v, 0) for k, v in d.items()}  # noqa: E731
    return {
        "currency": lib.currency,
        "library": lib.name,
        "rate_date": lib.rate_date,
        "settings": {**s, "construction_start": start.isoformat(), "escalation": esc},
        "likely": r2(likely),
        "low": r2(low),
        "high": r2(high),
        "per_m2": round(per_m2, 0) if per_m2 else None,
        "per_sqft": round(per_m2 / 10.7639, 1) if per_m2 else None,
        "sections": [{"name": k, "amount": round(v, 0)} for k, v in sections.items()],
        "coverage": {k: round(v / direct, 4) if direct else 0 for k, v in coverage.items()},
        "benchmarks": bench,
        "unpriced": [l_.description for l_ in lines if l_.key is None],
        "lines": [asdict(l_) for l_ in lines],
    }


def _default_start() -> str:
    today = date.today()
    y, m = today.year + (today.month + 6 - 1) // 12, (today.month + 6 - 1) % 12 + 1
    return date(y, m, 1).isoformat()  # six months from now
