"""Export fabrication Gerbers and Excellon drill files for a build, optionally zipped.

atopile's `mfg-data` build target already produces a <build>.gerber.zip. Use this wrapper when
you need to control the layer list, drill format or plot options directly -- e.g. matching a
specific fab house's requirements.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ._kicad import DEFAULT_BUILD, PROJECT_ROOT, KicadError, find_pcb, run

# Two-layer default. Override with --layers for 4+ layer stackups, e.g.
# F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,...
DEFAULT_LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-b", "--build", default=DEFAULT_BUILD, help="atopile build target name")
    parser.add_argument("--pcb", type=Path, help="explicit .kicad_pcb path")
    parser.add_argument("-o", "--output", type=Path, help="output directory for the plot files")
    parser.add_argument(
        "--layers",
        default=DEFAULT_LAYERS,
        help=f"comma-separated KiCad layer names (default: {DEFAULT_LAYERS})",
    )
    parser.add_argument(
        "--board-plot-params",
        action="store_true",
        help="use the plot settings stored in the board file instead of --layers",
    )
    parser.add_argument(
        "--drill-origin",
        choices=("absolute", "plot"),
        default="absolute",
        help="drill file coordinate origin",
    )
    parser.add_argument(
        "--separate-drill-files",
        action="store_true",
        help="emit independent PTH and NPTH drill files (required by some fabs)",
    )
    parser.add_argument("--no-zip", action="store_true", help="leave the plot files unarchived")
    args = parser.parse_args(argv)

    try:
        pcb = args.pcb or find_pcb(args.build)
    except KicadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not pcb.is_file():
        print(f"error: no such board: {pcb}", file=sys.stderr)
        return 2

    out_dir = args.output or PROJECT_ROOT / "build" / "fab" / args.build
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    gerber_args = [
        "pcb",
        "export",
        "gerbers",
        str(pcb),
        "--output",
        str(out_dir),
        "--subtract-soldermask",
        "--check-zones",
        "--precision",
        "6",
    ]
    if args.board_plot_params:
        gerber_args.append("--board-plot-params")
    else:
        gerber_args += ["--layers", args.layers]

    if run(gerber_args).returncode != 0:
        print("error: Gerber export failed", file=sys.stderr)
        return 1

    drill_args = [
        "pcb",
        "export",
        "drill",
        str(pcb),
        "--output",
        str(out_dir),
        "--format",
        "excellon",
        "--drill-origin",
        args.drill_origin,
        "--excellon-units",
        "mm",
        "--excellon-zeros-format",
        "decimal",
        "--generate-map",
        "--map-format",
        "gerberx2",
    ]
    if args.separate_drill_files:
        drill_args.append("--excellon-separate-th")

    if run(drill_args).returncode != 0:
        print("error: drill export failed", file=sys.stderr)
        return 1

    files = sorted(p for p in out_dir.iterdir() if p.is_file())
    print(f"Exported {len(files)} file(s) to {out_dir}")

    if not args.no_zip:
        archive = shutil.make_archive(str(out_dir), "zip", root_dir=out_dir)
        print(f"Packaged {archive}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
