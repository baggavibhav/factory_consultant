"""Command-line interface: ``fca convert | inspect | extract``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from fca import __version__
from fca.ingestion.convert import ConversionError, dwg_to_dxf
from fca.ingestion.extract import extract_geometry, header_units, read_dxf
from fca.ingestion.layers import layer_inventory, load_config


def _cmd_convert(args: argparse.Namespace) -> int:
    out = dwg_to_dxf(Path(args.dwg), Path(args.out) if args.out else None)
    print(f"DXF written: {out}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    doc = read_dxf(Path(args.dxf))
    inventory = layer_inventory(doc)
    print(f"Header units: {header_units(doc)}")
    print(f"Layers used: {len(inventory)}   Entities: {sum(n for _, n in inventory)}")
    for layer, n in inventory[: args.top]:
        print(f"{n:7d}  {layer}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    doc = read_dxf(Path(args.dxf))
    geometry = extract_geometry(doc, config, source_file=Path(args.dxf).name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(geometry.model_dump_json(indent=2), encoding="utf-8")

    print(f"Plant config: {config.name}")
    for category, s in geometry.stats.items():
        extra = f", {s.line_length_m:,.1f} m of drawn lines" if s.line_length_m else ""
        print(f"  {category.value:<11} {s.count:6d}{extra}")
    print(f"  labels      {len(geometry.labels):6d}")
    if geometry.building_bbox:
        b = geometry.building_bbox
        print(f"Building: {b.width:.1f} x {b.depth:.1f} m (approx. {b.width * b.depth:,.0f} m2)")
    for w in geometry.warnings:
        print(f"WARNING: {w}")
    print(f"Geometry written: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fca", description="Factory Consultant Agent tools")
    parser.add_argument("--version", action="version", version=f"fca {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("convert", help="convert a DWG file to DXF")
    p.add_argument("dwg")
    p.add_argument("-o", "--out", help="output .dxf path")
    p.set_defaults(func=_cmd_convert)

    p = sub.add_parser("inspect", help="list layers and entity counts in a DXF")
    p.add_argument("dxf")
    p.add_argument("--top", type=int, default=40, help="number of layers to show")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("extract", help="extract plant geometry to JSON")
    p.add_argument("dxf")
    p.add_argument("-c", "--config", required=True, help="plant layer-mapping TOML")
    p.add_argument("-o", "--out", required=True, help="output JSON path")
    p.set_defaults(func=_cmd_extract)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (ConversionError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
