"""Repair DXF files that converters wrote with broken tag structure.

LibreDWG can write a multi-line MTEXT value with a raw line break inside it.
DXF is a sequence of (group code, value) line pairs, so the stray line is then
read as a group code and the file fails to load. This module re-joins such
lines onto the value they belong to.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _is_group_code(line: str) -> bool:
    stripped = line.strip()
    return stripped.lstrip("-").isdigit() and len(stripped) <= 6


def repair_dxf_text(text: str) -> tuple[str, int]:
    """Return (repaired text, number of stray lines merged)."""
    lines = text.splitlines()
    out: list[str] = []
    merged = 0
    i = 0
    while i < len(lines):
        code = lines[i]
        if not _is_group_code(code):
            if out:  # stray continuation of the previous value
                out[-1] = f"{out[-1]} {code.strip()}"
                merged += 1
            i += 1
            continue
        value = lines[i + 1] if i + 1 < len(lines) else ""
        out.extend((code, value))
        i += 2
    return "\n".join(out) + "\n", merged


def repair_dxf_file(path: Path) -> int:
    """Repair ``path`` in place if needed. Returns the number of lines merged."""
    path = Path(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    repaired, merged = repair_dxf_text(text)
    if merged:
        path.write_bytes(repaired.encode("utf-8", errors="surrogateescape"))
        log.warning("Repaired %d broken text line(s) in %s", merged, path.name)
    return merged
