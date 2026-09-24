# ADR 0006: Quantities, BOQ, BOM and concept MEP

- Date: 24 Sep 2026
- Status: Accepted

## Decision
- Quantities are measured from the same plant model as the 3D view, never typed in.
  Every BOQ item carries a specification (from `config/specs/default.toml`) and a
  basis of measurement, so a reviewer can check each number.
- The Excel BOQ is tender-style: quantities filled, rates left blank (highlighted) for
  contractors or the cost library (v0.8), amounts and totals as live formulas.
- The BOM groups BOQ items by material and adds editable waste allowances.
- Concept MEP is rule-based and deterministic (routes along the hall and strip, drains to
  the sewer, fire ring around the building). It is a concept for visualisation and
  quantities; MEP engineers design the actual systems.
- Drawing projects: walls are drawn as two face lines, so wall areas are halved; finishes
  and MEP need room outlines and are not measured yet (planned).

## Consequences
Estimates (v0.8) will multiply these quantities by rates from a cost library, escalated
for inflation. Accuracy depends on the specification library and templates, both editable.
