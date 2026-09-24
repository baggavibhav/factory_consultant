"""Command-line interface: ``fca convert | inspect | extract``."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter
from pathlib import Path

from fca import __version__
from fca.ingestion.convert import ConversionError, dwg_to_dxf
from fca.ingestion.extract import extract_geometry, header_units, read_dxf
from fca.ingestion.layers import layer_inventory, load_config

LEVEL_PATTERN = re.compile(r"[+±-]\s?\d+\.\d+\s?M\b", re.IGNORECASE)


def _require(path: Path, hint: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found. {hint}")
    return path


def _dxf(arg: str) -> Path:
    return _require(Path(arg), "If you only have the DWG, run `fca convert <file.dwg>` first.")


def _cmd_convert(args: argparse.Namespace) -> int:
    out = dwg_to_dxf(Path(args.dwg), Path(args.out) if args.out else None)
    print(f"DXF written: {out}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    doc = read_dxf(_dxf(args.dxf))
    inventory = layer_inventory(doc)
    print(f"Header units: {header_units(doc)}")
    print(f"Layers used: {len(inventory)}   Entities: {sum(n for _, n in inventory)}")
    for layer, n in inventory[: args.top]:
        print(f"{n:7d}  {layer}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    config = load_config(_require(Path(args.config), "Check the path to the plant config."))
    doc = read_dxf(_dxf(args.dxf))
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


def _cmd_levels(args: argparse.Namespace) -> int:
    doc = read_dxf(_dxf(args.dxf))
    found: Counter[str] = Counter()
    for e in doc.modelspace().query("TEXT MTEXT"):
        text = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        for m in LEVEL_PATTERN.findall(text):
            found[re.sub(r"\s+", "", m.upper())] += 1
    if not found:
        print("No level annotations (like +8.30M) found.")
        return 0
    print("Level annotations found (confirm them in the plant config [levels]):")
    for level, n in sorted(found.items(), key=lambda kv: float(kv[0].strip("M±+"))):
        print(f"  {level:>9}  x{n}")
    return 0


def _cmd_build_3d(args: argparse.Namespace) -> int:
    from fca.pipeline import build_3d  # heavier imports only when needed

    config = _require(Path(args.config), "Check the path to the plant config.")
    result = build_3d(_dxf(args.dxf), config, Path(args.out))
    print(f"3D model:   {result.glb}")
    print(f"Viewer:     {result.viewer}   (double-click to open in a browser)")
    print(f"Report:     {result.report}")
    if result.layout:
        lay = result.layout
        print(
            f"Structure:  {len(lay.frame_x)} portal frames, span {lay.north_y - lay.south_y:.2f} m"
        )
        for kind, v in result.member_schedule.items():
            print(f"  {kind:<13} {v['count']:5d}  {v['length_m']:9,.1f} m")
    for w in result.warnings:
        print(f"WARNING: {w}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from fca.api.app import create_app

    app = create_app(data_dir=Path(args.data) if args.data else None, dev_cors=args.dev)
    url = f"http://{args.host}:{args.port}"
    print(f"Factory Consultant running at {url}  (Ctrl+C to stop)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
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

    p = sub.add_parser("levels", help="list level annotations (e.g. +8.30M) in a sections DXF")
    p.add_argument("dxf")
    p.set_defaults(func=_cmd_levels)

    p = sub.add_parser("build-3d", help="build the 3D model, structure and viewer")
    p.add_argument("dxf", help="plan DXF")
    p.add_argument("-c", "--config", required=True, help="plant config TOML")
    p.add_argument("-o", "--out", default="outputs", help="output folder")
    p.set_defaults(func=_cmd_build_3d)

    p = sub.add_parser("serve", help="start the web app and API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--data", help="projects folder (default: ./projects)")
    p.add_argument("--dev", action="store_true", help="allow the Vite dev server (port 5173)")
    p.set_defaults(func=_cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (ConversionError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
