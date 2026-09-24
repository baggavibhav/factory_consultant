# ADR 0005: Concept design from a brief

- Date: 24 Sep 2026
- Status: Accepted

## Context
Most future plants have no drawings yet. The agent must produce a sensible
concept from a brief, and the LLM provider decision is still pending.

## Decision
- A rule-based concept generator comes before the LLM conversation. The LLM
  will later ask the questions and drive this same generator.
- Design rules live in `config/templates/*.toml` (data, not code) so engineering
  can adjust proportions without programming.
- Layout strategy: offices, amenities and utilities in a strip on the street side;
  production hall zones as west-to-east slices in process-flow order; zones that
  work together (packaging and PM store, cold store and blast freezer) stacked in
  one slice. Regular bays near the template's target spacing.
- If the requested area does not fit the plot, the concept uses the maximum that
  fits and says so; it never silently overhangs the plot.
- Every default and every check is shown to the user.

## Consequences
Concepts are only as good as the templates. Templates start from reference plant
#1 and general practice; they improve as Switz plants and engineering input are added.
