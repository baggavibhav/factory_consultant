# ADR 0002: Development environment

- Date: 24 Sep 2026
- Status: Accepted

## Decision
- Windows, VS Code (without Claude Code), Python 3.12, local git repository.
- Code is written and tested in the Claude project, delivered as files, and run locally.
- Quality gates: pytest, Ruff lint and format, type hints; secrets only in `.env`.
- DWG conversion with LibreDWG 0.13.3 (open source), downloaded by `scripts/setup.ps1`.
- A private GitHub repository may be added later; none exists today.
