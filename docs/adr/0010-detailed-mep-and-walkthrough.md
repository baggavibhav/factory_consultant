# ADR 0010: Detailed MEP geometry and walkthrough

- Date: 28 Sep 2026
- Status: Accepted

## Decision
- The 3D model shows services at installation-level detail (fittings, supports, valves,
  devices, fixtures) so management can see what goes into the building. Detail is generated
  by rules from the routed model; it is not a coordinated MEP design.
- Each service exports three parts (runs, fittings, supports) so layers toggle cleanly.
- Concept walls get door openings; the walkthrough uses the walls, cold-room panels and
  machines as colliders, slides along walls, and shows the current room and a mini-map.
- VR uses the WebXR standard (no plugin); the button appears only when a headset session is
  supported, which requires the app to be served over https.

## Consequences
Model size grows (about 4 MB and 200,000 faces for a 5,000 m² plant) but stays fast in a
browser. A video export was considered and dropped at the user's request.
