"""Run SKiDL's Electrical Rules Check over the design.

The design is the SKiDL script, not a schematic -- `generate_schematic()` fails with a
RoutingFailure on this board, so there is no .kicad_sch for `kicad-cli sch erc` to read.
SKiDL's own ERC is the check that covers the circuit: it flags unconnected pins, pin-type
conflicts, nets with no driver, and nets with multiple drivers.

The design script runs its own ERC under `if __name__ == "__main__"`. This wrapper exists so
CI can run the same check with a machine-readable report and a meaningful exit code.

    uv run python -m scripts.erc
    uv run python -m scripts.erc --warnings-are-errors --json

Exit 0 clean, 1 violations, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._kicad import DEFAULT_DESIGN, PROJECT_ROOT, load_design, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--design",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_DESIGN,
        help=f"SKiDL design to check (default: {DEFAULT_DESIGN})",
    )
    parser.add_argument(
        "--warnings-are-errors",
        action="store_true",
        help="fail on warnings too, not just errors",
    )
    parser.add_argument("--json", action="store_true", help="also write a JSON report")
    args = parser.parse_args(argv)

    if not args.design.is_file():
        print(f"error: no such design: {args.design}", file=sys.stderr)
        return 2

    load_design(args.design)

    import builtins

    from skidl import erc_logger

    builtins.default_circuit.ERC()

    # ERC() resets these counters before it runs, so they describe this run only.
    # SKiDL splits each severity into a traced and a "bare" (untraced) variant.
    errors = erc_logger.error.count + erc_logger.bare_error.count
    warnings = erc_logger.warning.count + erc_logger.bare_warning.count

    # SKiDL mirrors every ERC message into <script>.erc next to the design.
    log = args.design.with_suffix(".erc")
    detail = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""

    print(f"ERC: {errors} error(s), {warnings} warning(s)")

    if args.json:
        report = report_path("erc", ".json")
        report.write_text(
            json.dumps(
                {
                    "design": str(args.design),
                    "errors": errors,
                    "warnings": warnings,
                    "log": detail,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Report: {report}")

    return 1 if errors or (warnings and args.warnings_are_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
