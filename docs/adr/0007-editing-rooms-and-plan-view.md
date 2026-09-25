# ADR 0007: Design editing, rooms from drawings and the plan view

- Date: 24 Sep 2026
- Status: Accepted

## Context
Management needs to change a design and see the consequences, read services on a plan,
and see room-level detail (hygiene stations, prayer rooms, changing) as in real drawings.

## Decision
- Editing works through the brief: design options are brief fields, so every edit is saved,
  rebuilds deterministically, and can be compared. The API stores the previous build's key
  figures and reports the differences ("what changed").
- The plan view is 2D (SVG) from a plan file written at build time, because engineers and
  managers read services on plans; 3D stays for overall understanding.
- Rooms are read from drawings geometrically: door-sized gaps between collinear wall ends
  are closed, the wall network is polygonised, and each label takes the smallest enclosing
  polygon. Open-plan zones without enclosing walls share the remaining floor by nearest
  label and are marked estimated.
- The concept generator adopts the design review: truck yards, docks, exits, haunched frames,
  sizing by span and bay, intermediate bracing, ground beams and plinth walls.

## Consequences
Drawing projects get per-room finishes and fittings; routed MEP for drawings is a later step.
Direct drag-editing in the plan is possible later on top of the same brief-based model.
