# ADR 0009: Design checks and before/after variants

- Date: 25 Sep 2026
- Status: Accepted

## Decision
- Design checks are deterministic rules in code, run on the plan data of every build
  (concept and drawing). Each finding has severity, area, explanation, suggestion, an
  optional location and, for concept projects, an optional fix expressed as brief changes.
- A fix becomes a variant: a full, separate build of the concept with that change. Variants
  are compared with the current design side by side (3D with linked cameras, or plan), with
  a plan diff that highlights added, removed and resized elements and reports shifts once.
- Accepting a variant makes it the design; rebuilding the design clears stale variants.
- The LLM agent (later) will choose and explain fixes; the checks themselves stay in code.

## Consequences
Management sees the effect of every suggestion before deciding. Checks support the design
team and are not a code-compliance certificate. Variants for drawing projects follow once
drawing profiles are automatic (v0.9).
