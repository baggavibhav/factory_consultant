"""DWG to DXF conversion using the LibreDWG command-line tool."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from fca.ingestion.repair import repair_dxf_file
from fca.settings import find_dwg2dxf

log = logging.getLogger(__name__)


class ConversionError(RuntimeError):
    """Raised when a DWG file cannot be converted."""


def dwg_to_dxf(
    dwg_path: Path,
    dxf_path: Path | None = None,
    *,
    dwg2dxf: Path | None = None,
    timeout_s: int = 300,
) -> Path:
    """Convert ``dwg_path`` to DXF and return the DXF path.

    Args:
        dwg_path: Input AutoCAD drawing.
        dxf_path: Output file. Defaults to the input path with a ``.dxf`` suffix.
        dwg2dxf: Converter executable. Found automatically when omitted.
        timeout_s: Abort if conversion takes longer than this.
    """
    dwg_path = Path(dwg_path)
    if not dwg_path.is_file():
        raise ConversionError(f"DWG file not found: {dwg_path}")
    exe = dwg2dxf or find_dwg2dxf()
    if exe is None:
        raise ConversionError(
            "dwg2dxf not found. Run scripts/setup.ps1, or set FCA_DWG2DXF in .env "
            "to the full path of dwg2dxf.exe."
        )
    out = Path(dxf_path) if dxf_path else dwg_path.with_suffix(".dxf")
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(exe), "-y", "-o", str(out), str(dwg_path)]
    log.info("Converting %s -> %s", dwg_path.name, out)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(f"Conversion timed out after {timeout_s}s") from exc

    # LibreDWG prints many harmless warnings; only fail when no usable file appears.
    if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
        raise ConversionError(
            f"dwg2dxf failed (exit {result.returncode}) for {dwg_path.name}: " + " | ".join(tail)
        )
    repair_dxf_file(out)  # fix text values LibreDWG sometimes writes across lines
    return out
