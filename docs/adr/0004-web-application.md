# ADR 0004: Web application architecture

- Date: 24 Sep 2026
- Status: Accepted

## Decision
- Backend: FastAPI (`fca.api`). The same pipeline functions serve the CLI, the web
  app and, later, the agents.
- Frontend: React + TypeScript + Vite, three.js for 3D. No UI framework; a small
  design system in `frontend/src/styles.css` (concrete, slate and safety-yellow
  palette; Archivo typeface bundled locally so it works offline).
- The production build is written into `src/fca/web` and committed, so running the
  app needs Python only. Node.js is needed only to change the frontend.
- Projects are stored as folders (`projects/<id>/project.json`, uploads, outputs).
  Simple for one machine; replace with a database before multi-user production.
- Uploaded file names are sanitised (spaces to underscores, no paths).

## Consequences
One command (`fca serve`) runs everything locally. For production we add
authentication, a database and a Docker image (see open questions on hosting).
