from __future__ import annotations

from pathlib import Path

import pytest

from fca.ingestion import convert
from fca.ingestion.convert import ConversionError, dwg_to_dxf


def test_missing_input_raises(tmp_path):
    with pytest.raises(ConversionError, match="not found"):
        dwg_to_dxf(tmp_path / "missing.dwg")


def test_missing_converter_raises(tmp_path, monkeypatch):
    dwg = tmp_path / "a.dwg"
    dwg.write_bytes(b"AC1032")
    monkeypatch.setattr(convert, "find_dwg2dxf", lambda: None)
    with pytest.raises(ConversionError, match="dwg2dxf not found"):
        dwg_to_dxf(dwg)


def test_failed_conversion_raises(tmp_path, monkeypatch):
    dwg = tmp_path / "a.dwg"
    dwg.write_bytes(b"AC1032")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "ERROR reading file"

    monkeypatch.setattr(convert.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(ConversionError, match="exit 1"):
        dwg_to_dxf(dwg, dwg2dxf=Path("dwg2dxf"))


def test_successful_conversion_returns_path(tmp_path, monkeypatch):
    dwg = tmp_path / "a.dwg"
    dwg.write_bytes(b"AC1032")
    out = tmp_path / "out" / "a.dxf"

    def fake_run(cmd, **kwargs):
        Path(cmd[cmd.index("-o") + 1]).write_text("0\nEOF\n")

        class Result:
            returncode = 0
            stdout = stderr = ""

        return Result()

    monkeypatch.setattr(convert.subprocess, "run", fake_run)
    assert dwg_to_dxf(dwg, out, dwg2dxf=Path("dwg2dxf")) == out
    assert out.is_file()
