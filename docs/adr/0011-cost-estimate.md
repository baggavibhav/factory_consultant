# ADR 0011: Cost estimate and rate library

- Date: 30 Sep 2026
- Status: Accepted

## Context
Switz has no historical priced BOQs yet. Management needs a cost figure now, with honesty
about how firm it is.

## Decision
- A rate library per country in `config/rates/<code>.toml`. Every rate records its source,
  date and confidence: official (GASTAT material prices), published (supplier or market
  price pages) or allowance (estimator figure with no public source). Supply prices convert
  to installed rates with a stated factor.
- The estimate multiplies measured BOQ quantities by library rates, gives low/likely/high,
  applies preliminaries, overhead and profit, contingency, escalation (GASTAT CCI trend,
  2%/year default) to the construction midpoint and VAT, and checks cost per m² against a
  published benchmark range.
- The app shows the share of cost resting on each confidence level, so allowances are
  visible and can be replaced by quotes (Cost library edits, then Recalculate).
- Only Saudi Arabia is priced; other countries are not priced in SAR.

## Consequences
The first estimates rest largely on allowances (about 70% of cost for a concept). Accuracy
improves as quotes replace allowances; v1.2 procurement will feed accepted quotes directly
into the library.
