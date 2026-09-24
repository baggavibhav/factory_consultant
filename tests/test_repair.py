from __future__ import annotations

import ezdxf

from fca.ingestion.repair import repair_dxf_file, repair_dxf_text


def test_joins_value_split_across_lines():
    broken = "  0\nMTEXT\n  1\nFIRST PART\nSECOND PART\n  7\nSTYLE\n"
    fixed, merged = repair_dxf_text(broken)
    assert merged == 1
    assert fixed.splitlines() == ["  0", "MTEXT", "  1", "FIRST PART SECOND PART", "  7", "STYLE"]


def test_valid_text_is_untouched():
    ok = "  0\nLINE\n  8\nWALL\n"
    fixed, merged = repair_dxf_text(ok)
    assert merged == 0 and fixed == ok


def test_repaired_file_opens(tmp_path):
    doc = ezdxf.new("R2018")
    doc.modelspace().add_mtext("TITLE", dxfattribs={"layer": "TB"})
    path = tmp_path / "t.dxf"
    doc.saveas(path)
    text = path.read_text(encoding="utf-8").replace("TITLE", "TITLE LINE ONE\nLINE TWO", 1)
    path.write_text(text, encoding="utf-8")
    assert repair_dxf_file(path) == 1
    mtext = ezdxf.readfile(path).modelspace().query("MTEXT")[0]
    assert "LINE TWO" in mtext.text
