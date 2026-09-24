# ADR 0003: Structural model in the 3D output

- Date: 24 Sep 2026
- Status: Accepted

## Context
The 3D output must show the structural system (columns, beams, frames and so on)
the way a professional model would. Reference plant #1 has only architectural
drawings: a column grid on the roof plan, levels on the sections, and no member
sizes.

## Decision
- Layout comes from the drawings: portal frames on configured grid lines, which
  must exist in the drawing's grid (the tool refuses otherwise).
- The grid plan is aligned to the floor plan using an outline drawn on both
  (the plot boundary); mismatched outlines stop the build.
- Secondary members (purlins, girts, bracing) and all member sizes are typical
  values in the plant config, marked indicative in every output.
- When structural drawings arrive, their members replace the generated ones.
- The model is for visualisation and quantities. Structural design and sign-off
  remain with a structural engineer.

## Consequences
Every 3D model carries a member schedule (count and length per type), the first
input to the steel BOQ. Assumptions are tagged [ASSUMED] in the plant config.
