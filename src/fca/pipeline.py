"""End-to-end pipelines that chain the tools. Agents will call these."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from fca.ingestion.extract import extract_geometry, read_dxf
from fca.ingestion.layers import load_config
from fca.model.building import BuildingConfig, load_building_config
from fca.model3d.build import build_model
from fca.structure.frame import FrameLayout, Member, generate_frame, schedule
from fca.structure.grid import alignment_offset, extract_grid, pick
from fca.viewer.html import render_viewer

log = logging.getLogger(__name__)


@dataclass
class Build3DResult:
    glb: Path
    viewer: Path
    report: Path
    member_schedule: dict
    layout: FrameLayout | None
    alignment_offset: tuple[float, float] | None
    warnings: list[str]
    facts: dict
    labels: list[dict]


def _frame_layout(doc, plant, cfg: BuildingConfig) -> tuple[FrameLayout, tuple[float, float]]:
    s = cfg.structure
    grid = extract_grid(doc, s.grid_layers, s.grid_region)
    if plant.region is None:
        raise ValueError("Plant config needs a [region] for the plan to align the grid to")
    dx, dy = alignment_offset(doc, s.align_layer, s.grid_region, plant.region)
    k = plant.unit_to_metre
    xs = tuple((x + dx) * k for x in pick(grid.xs, list(s.frame_x)))
    south, north = ((y + dy) * k for y in pick(grid.ys, list(s.column_rows_y)))
    gable = tuple((y + dy) * k for y in pick(grid.ys, list(s.gable_y)))
    return FrameLayout(frame_x=xs, south_y=south, north_y=north, gable_y=gable), (dx, dy)


def _labels(geometry, cfg: BuildingConfig, builder) -> list[dict]:
    chosen: list[dict] = []
    for lab in geometry.labels:
        if cfg.label_include and not any(lab.text.startswith(p) for p in cfg.label_include):
            continue
        if any(
            c["text"] == lab.text and math.dist((c["px"], c["py"]), (lab.x, lab.y)) < 20
            for c in chosen
        ):
            continue
        pos = builder.to_gltf([[lab.x + 1.5, lab.y, cfg.levels.ffl + 1.9]])[0]
        cold = "-18" in lab.text or "-40" in lab.text or "\u2212" in lab.text
        chosen.append(
            {
                "text": lab.text,
                "px": lab.x,
                "py": lab.y,
                "pos": [round(float(v), 2) for v in pos],
                "cold": cold,
            }
        )
    return chosen


def build_3d(
    plan_dxf: Path, config_path: Path, out_dir: Path, name: str | None = None
) -> Build3DResult:
    """Drawing -> geometry -> structure -> glTF model + viewer + structure report."""
    plant = load_config(config_path)
    cfg = load_building_config(config_path)
    doc = read_dxf(Path(plan_dxf))
    geometry = extract_geometry(doc, plant, source_file=Path(plan_dxf).name)
    warnings = list(geometry.warnings)

    members: list[Member] = []
    layout = offset = None
    if cfg.structure is not None:
        layout, offset = _frame_layout(doc, plant, cfg)
        members = generate_frame(cfg, layout)
        if cfg.structure.sizes_are_indicative:
            warnings.append("Structural member sizes are indicative, not engineered.")

    builder = build_model(cfg, geometry, members)
    name = name or plant.name
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    glb_path = out_dir / f"{name}.glb"
    glb_bytes = builder.glb()
    glb_path.write_bytes(glb_bytes)

    sched = schedule(members)
    env = cfg.envelope
    facts = {
        "plant": name,
        "source_file": geometry.source_file,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "building_m": [round(env.width, 1), round(env.depth, 1)],
        "footprint_m2": round(env.width * env.depth),
        "levels": asdict(cfg.levels),
        "wall_lines": geometry.stats["wall"].count,
        "frames": len(layout.frame_x) if layout else 0,
        "bays_m": [
            round(b - a, 2) for a, b in zip(layout.frame_x, layout.frame_x[1:], strict=False)
        ]
        if layout
        else [],
        "span_m": round(layout.north_y - layout.south_y, 2) if layout else None,
        "member_schedule": sched,
        "sizes_indicative": bool(cfg.structure and cfg.structure.sizes_are_indicative),
        "warnings": warnings,
    }
    report_path = out_dir / f"{name}.structure.json"
    report_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")

    labels = _labels(geometry, cfg, builder)
    (out_dir / f"{name}.labels.json").write_text(json.dumps(labels, indent=1), encoding="utf-8")

    viewer_path = out_dir / f"{name}.viewer.html"
    viewer_path.write_text(render_viewer(glb_bytes, facts, labels), encoding="utf-8")
    return Build3DResult(
        glb_path, viewer_path, report_path, sched, layout, offset, warnings, facts, labels
    )


def build_concept(brief, out_dir: Path, name: str = "model") -> Build3DResult:
    """Brief -> space program -> concept layout -> structure -> glTF + viewer + report."""
    from fca.concept.brief import resolve
    from fca.concept.layout import build_layout, max_area_on_plot
    from fca.concept.program import build_program, load_template
    from fca.model.schema import Category, CategoryStats, PlantGeometry

    values, assumptions = resolve(brief)
    tpl = load_template(brief.plant_type)
    fit_warnings = []
    limit = max_area_on_plot(values, tpl)
    if limit is not None and values["built_up_area_m2"] > limit:
        fit_warnings.append(
            f"The requested {values['built_up_area_m2']:,.0f} m² does not fit on this plot as one "
            f"building; the concept uses the maximum of {limit:,.0f} m². Enlarge the plot, "
            "reduce setbacks or consider a mezzanine or second floor."
        )
        values["built_up_area_m2"] = round(limit, 1)
    program = build_program(values, tpl)
    lay = build_layout(values, program, tpl)
    cfg = lay.config

    geometry = PlantGeometry(
        source_file="concept brief",
        extracted_at=datetime.now(UTC),
        unit_to_metre=1.0,
        building_bbox=lay.building,
        segments=lay.segments,
        labels=[],
        stats={Category.WALL: CategoryStats(count=len(lay.segments), line_length_m=0.0)},
    )
    members = generate_frame(cfg, lay.frame)
    builder = build_model(cfg, geometry, members)
    for room in lay.rooms:
        builder.add_zone(room.category, room.rect)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    glb_path = out_dir / f"{name}.glb"
    glb_bytes = builder.glb()
    glb_path.write_bytes(glb_bytes)

    warnings = [
        *fit_warnings,
        *lay.warnings,
        "Concept design: layout and structure are proposals, not "
        "engineered designs; member sizes are indicative.",
    ]
    env = lay.building
    sched = schedule(members)
    rooms = [
        {
            "name": r.name,
            "category": r.category,
            "area_m2": round(r.area_m2, 1),
            "temp_c": r.temp_c,
            "width_m": round(r.rect.width, 2),
            "depth_m": round(r.rect.depth, 2),
        }
        for r in lay.rooms
    ]
    facts = {
        "mode": "concept",
        "plant": name,
        "template": tpl.name,
        "source_file": "concept brief",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "building_m": [round(env.width, 1), round(env.depth, 1)],
        "footprint_m2": round(env.width * env.depth),
        "plot_m": [round(lay.plot.width, 1), round(lay.plot.depth, 1)],
        "levels": asdict(cfg.levels),
        "wall_lines": len(lay.segments),
        "frames": len(lay.frame.frame_x),
        "bays_m": [
            round(b - a, 2) for a, b in zip(lay.frame.frame_x, lay.frame.frame_x[1:], strict=False)
        ],
        "span_m": round(lay.frame.north_y - lay.frame.south_y, 2),
        "member_schedule": sched,
        "sizes_indicative": True,
        "program": rooms,
        "assumptions": assumptions,
        "warnings": warnings,
    }
    report_path = out_dir / f"{name}.structure.json"
    report_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")

    labels = []
    for r in lay.rooms:
        c = r.rect
        pos = builder.to_gltf(
            [[(c.xmin + c.xmax) / 2, (c.ymin + c.ymax) / 2, cfg.levels.ffl + 1.9]]
        )[0]
        labels.append(
            {
                "text": r.label,
                "px": (c.xmin + c.xmax) / 2,
                "py": (c.ymin + c.ymax) / 2,
                "pos": [round(float(v), 2) for v in pos],
                "cold": r.category == "cold",
            }
        )
    (out_dir / f"{name}.labels.json").write_text(json.dumps(labels, indent=1), encoding="utf-8")
    viewer_path = out_dir / f"{name}.viewer.html"
    viewer_path.write_text(render_viewer(glb_bytes, facts, labels), encoding="utf-8")
    return Build3DResult(
        glb_path, viewer_path, report_path, sched, lay.frame, None, warnings, facts, labels
    )
