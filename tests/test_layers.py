from __future__ import annotations

from pathlib import Path

from fca.ingestion.extract import read_dxf
from fca.ingestion.layers import layer_inventory, load_config
from fca.model.schema import Category

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_reference_config_loads():
    cfg = load_config(REPO_ROOT / "config" / "plants" / "ref-plant-01.toml")
    assert cfg.name == "ref-plant-01"
    assert cfg.category_of("WALL") is Category.WALL
    assert cfg.category_of("A-REFRIGERATION PANEL 200") is Category.COLD_PANEL
    assert cfg.category_of("SOMETHING ELSE") is None
    assert cfg.region is not None and cfg.building is not None


def test_template_config_loads():
    cfg = load_config(REPO_ROOT / "config" / "plants" / "_template.toml")
    assert cfg.layers[Category.WALL] == ("WALL",)


def test_layer_inventory_counts(sample_dxf):
    inventory = dict(layer_inventory(read_dxf(sample_dxf)))
    assert inventory["WALL"] == 4  # polyline + 2 lines + outside line
    assert inventory["ROOMS"] == 3
