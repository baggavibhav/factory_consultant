"""Layer mapping config and layer inventory for DXF drawings."""

from __future__ import annotations

import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ezdxf.document import Drawing

from fca.model.schema import BBox, Category

LINEAR_CATEGORIES = (Category.WALL, Category.COLD_PANEL, Category.BOUNDARY)
OPENING_CATEGORIES = (Category.DOOR, Category.WINDOW)


@dataclass(frozen=True)
class PlantConfig:
    """How to read one drawing: which layers mean what, units and regions."""

    name: str
    unit_to_metre: float
    layers: dict[Category, tuple[str, ...]]
    label_layers: tuple[str, ...]
    region: BBox | None = None
    building: BBox | None = None
    ignore_labels: frozenset[str] = field(default_factory=frozenset)

    def category_of(self, layer: str) -> Category | None:
        for category, names in self.layers.items():
            if layer in names:
                return category
        return None


def _bbox(raw: dict | None) -> BBox | None:
    return BBox(**raw) if raw else None


def load_config(path: Path) -> PlantConfig:
    """Load a plant layer-mapping config from a TOML file."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    layers = {Category(k): tuple(v) for k, v in data.get("layers", {}).items()}
    labels = data.get("labels", {})
    return PlantConfig(
        name=data["name"],
        unit_to_metre=float(data.get("unit_to_metre", 1.0)),
        layers=layers,
        label_layers=tuple(labels.get("layers", [])),
        region=_bbox(data.get("region")),
        building=_bbox(data.get("building")),
        ignore_labels=frozenset(labels.get("ignore", [])),
    )


def layer_inventory(doc: Drawing) -> list[tuple[str, int]]:
    """Return (layer, entity count) for modelspace, most used first."""
    counts = Counter(entity.dxf.layer for entity in doc.modelspace())
    return counts.most_common()
