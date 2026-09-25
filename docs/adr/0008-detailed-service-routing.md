# ADR 0008: Detailed service routing

- Date: 25 Sep 2026
- Status: Accepted

## Decision
- Every fitting is connected by a measured run: lights by circuit rows, sockets by room
  rings, detectors by one loop, outlets and sprinkler heads by branch chains, lines by
  feeders and drops. Quantities for cables, pipes and ducts come from these runs.
- Runs are orthogonal (along x and y) and enforced by a test, because services on site
  follow walls, ceilings and trays.
- Rules are concept-level (circuit per row, fixed socket spacing by room type, one AHU per
  production zone, point-of-use water heaters) and stated in each BOQ item's basis.

## Consequences
The plan view can show exactly where each service travels. MEP engineers still size and
design the real systems; routing for drawing projects needs room outlines per floor and
is a later step.
