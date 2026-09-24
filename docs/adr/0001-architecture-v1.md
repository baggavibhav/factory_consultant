# ADR 0001: Architecture v1

- Date: 24 Sep 2026
- Status: Proposed

## Context
The agent must turn plant briefs and drawings into a 3D model, BOQ, cost
estimate and contractor ranking for three plant categories: industrial,
retail and egg station. Only one reference plant's drawings exist so far.

## Decision
- Multi-agent: one orchestrator plus specialist agents (ingestion, model, BOQ, cost, bid).
- Geometry, quantities and arithmetic are computed by tested Python tools, never by the LLM.
  The LLM interprets, chooses, flags and explains.
- One versioned data contract (`fca.model.schema`) connects every stage.
- People approve layer mappings, the BOQ, the budget and the contract award.
- Build order: ingestion (drawings to geometry) first, then 3D model, quantities, BOQ, cost, bids.

## Consequences
Outputs are reproducible and auditable. New drawings need a layer-mapping
config (the ingestion agent will propose it; a person confirms).
