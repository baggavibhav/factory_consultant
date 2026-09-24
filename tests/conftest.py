"""Shared fixtures: a small synthetic plan drawn with ezdxf (no real drawings needed)."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from fca.ingestion.layers import PlantConfig
from fca.model.schema import BBox, Category

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = REPO_ROOT / "data" / "reference"


@pytest.fixture
def sample_dxf(tmp_path: Path) -> Path:
    """A 20 x 10 m building: outer walls, one partition, a cold room block,
    one door, one window, two labels, and one wall outside the plan region."""
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (20, 0), (20, 10), (0, 10)], close=True, dxfattribs={"layer": "WALL"}
    )
    msp.add_line((10, 0), (10, 10), dxfattribs={"layer": "WALL"})
    msp.add_line((0, 0), (0.01, 0), dxfattribs={"layer": "WALL"})  # too short, dropped

    panel = doc.blocks.new("COLDROOM")
    panel.add_line((0, 0), (4, 0), dxfattribs={"layer": "PANEL"})
    panel.add_line((4, 0), (4, 3), dxfattribs={"layer": "PANEL"})
    msp.add_blockref("COLDROOM", (12, 2), dxfattribs={"layer": "PANEL"})

    door = doc.blocks.new("DOOR")
    door.add_arc((0, 0), 1, 0, 90)
    msp.add_blockref("DOOR", (5, 0), dxfattribs={"layer": "DOOR"})
    win = doc.blocks.new("WIN")
    win.add_line((0, 0), (1.5, 0))
    msp.add_blockref("WIN", (15, 10), dxfattribs={"layer": "WIN"})

    msp.add_text("PRODUCTION  AREA", dxfattribs={"layer": "ROOMS", "insert": (3, 5)})
    msp.add_mtext("COLD STORE\\P-18°C", dxfattribs={"layer": "ROOMS", "insert": (13, 3)})
    msp.add_text("UP", dxfattribs={"layer": "ROOMS", "insert": (8, 8)})

    msp.add_line((100, 100), (110, 100), dxfattribs={"layer": "WALL"})  # outside region

    path = tmp_path / "sample.dxf"
    doc.saveas(path)
    return path


@pytest.fixture
def sample_config() -> PlantConfig:
    return PlantConfig(
        name="sample",
        unit_to_metre=1.0,
        layers={
            Category.WALL: ("WALL",),
            Category.COLD_PANEL: ("PANEL",),
            Category.DOOR: ("DOOR",),
            Category.WINDOW: ("WIN",),
        },
        label_layers=("ROOMS",),
        region=BBox(xmin=-5, ymin=-5, xmax=30, ymax=20),
        ignore_labels=frozenset({"UP"}),
    )
