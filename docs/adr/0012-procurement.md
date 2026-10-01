# ADR 0012: Procurement and quote comparison

- Date: 30 Sep 2026
- Status: Accepted

## Decision
- Suppliers are discovered from public sources and entered as prospects with their source;
  a vetting checklist gates approval (commercial registration and references at minimum).
- RFQs are generated per package from the priced BOQ as Excel files with fixed rows and
  hidden line ids, so returned quotes import reliably without an LLM. PDF quotes will be
  read by the agent layer later.
- Quotes are compared like for like (excl. VAT, allowances for excluded delivery and
  installation, gaps filled at library rates) and scored for best value, not lowest price.
  The app recommends; a person awards.
- Accepted quotes update the shared rate library as "quoted", so every estimate improves.

## Consequences
Estimates move from allowances to quoted prices as packages are tendered. Contractor bid
evaluation can reuse the same comparison engine.
