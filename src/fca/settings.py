"""Runtime settings: tool locations and project paths."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
DWG2DXF_ENV = "FCA_DWG2DXF"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file without overriding real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(PROJECT_ROOT / ".env")


def find_dwg2dxf() -> Path | None:
    """Locate the LibreDWG ``dwg2dxf`` executable.

    Search order: the ``FCA_DWG2DXF`` environment variable, the copy that
    ``scripts/setup.ps1`` downloads into ``tools/libredwg``, then ``PATH``.
    """
    configured = os.environ.get(DWG2DXF_ENV, "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_file() else None
    for name in ("dwg2dxf.exe", "dwg2dxf"):
        candidate = TOOLS_DIR / "libredwg" / name
        if candidate.is_file():
            return candidate
    found = shutil.which("dwg2dxf")
    return Path(found) if found else None
