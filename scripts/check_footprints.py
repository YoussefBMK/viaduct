"""Check every part's footprint against the installed KiCad footprint libraries.

SKiDL cannot do this itself. It warns `fp-lib-table file was not found. Component
footprints are not available.` and then accepts any footprint string you hand it, so a typo
in a library nickname or a footprint whose pads do not line up with the symbol's pins sails
straight through ERC and into the netlist. KiCad only complains at import time, which is far
too late to be useful.

Two checks per part:

1. The footprint `Lib:Name` resolves to a real `Name.kicad_mod` inside a real `Lib.pretty`.
2. Every pin number on the symbol has a pad with that number in the footprint.

Check 2 is the one that matters for the symbols KiCad ships with an empty footprint field
(`Device:R`, `Device:C`, `Device:LED`, `Switch:SW_Push`,
`Connector:USB_C_Receptacle_USB2.0_16P`), where the pairing is the designer's choice and
nothing upstream validates it.

    uv run python -m scripts.check_footprints
    uv run python -m scripts.check_footprints --design viaduct_v0.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import sys
from pathlib import Path

from ._kicad import PROJECT_ROOT, KicadError, report_path

DEFAULT_DESIGN = "viaduct_v0.py"

# Pads carrying no number (mechanical, thermal relief, castellation keep-outs) are not
# electrical connections, so they are never expected to match a pin.
PAD_RE = re.compile(r'\(pad\s+(?:"((?:[^"\\]|\\.)*)"|([^\s()]+))')

# fp-lib-table URIs are written against this variable rather than an absolute path.
FOOTPRINT_DIR_VAR = "KICAD10_FOOTPRINT_DIR"

FOOTPRINT_DIR_FALLBACKS = (
    "/usr/share/kicad/footprints",
    "/usr/local/share/kicad/footprints",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",
    "C:/Program Files/KiCad/10.0/share/kicad/footprints",
)

# Where KiCad keeps the global fp-lib-table once the GUI has been run at least once, plus
# the template a fresh install copies it from. Reading it is what lets this check see
# libraries installed outside the main footprint directory.
FP_LIB_TABLE_DIRS = (
    "~/.config/kicad/10.0",
    "~/.config/kicad",
    "~/Library/Preferences/kicad/10.0",
    "~/Library/Preferences/kicad",
    os.path.expandvars("$APPDATA/kicad/10.0"),
    os.path.expandvars("$APPDATA/kicad"),
    "/usr/share/kicad/template",
    "/usr/local/share/kicad/template",
)

LIB_RE = re.compile(r'\(lib\s+\(name\s+"?([^")]+)"?\)\s+.*?\(uri\s+"?([^")]+)"?\)', re.S)


def footprint_dir() -> Path:
    """Resolve the root directory holding the *.pretty footprint libraries."""
    override = os.environ.get(FOOTPRINT_DIR_VAR)
    if override:
        path = Path(override)
        if not path.is_dir():
            raise KicadError(f"{FOOTPRINT_DIR_VAR} is set to {path}, which is not a directory")
        return path

    for candidate in FOOTPRINT_DIR_FALLBACKS:
        if Path(candidate).is_dir():
            return Path(candidate)

    raise KicadError(
        "No KiCad footprint directory found. Set "
        f"{FOOTPRINT_DIR_VAR} to the directory containing the *.pretty libraries."
    )


def library_map(root: Path) -> dict[str, Path]:
    """Map library nickname -> .pretty directory.

    Prefers a real fp-lib-table so libraries installed outside `root` are still found, and
    falls back to the flat `<root>/<nickname>.pretty` convention a stock install uses.
    """
    libs: dict[str, Path] = {
        entry.stem: entry for entry in sorted(root.glob("*.pretty")) if entry.is_dir()
    }

    for directory in FP_LIB_TABLE_DIRS:
        table = Path(directory).expanduser() / "fp-lib-table"
        if not table.is_file():
            continue
        text = table.read_text(encoding="utf-8", errors="replace")
        for nickname, uri in LIB_RE.findall(text):
            expanded = uri.replace(f"${{{FOOTPRINT_DIR_VAR}}}", str(root))
            path = Path(os.path.expandvars(expanded)).expanduser()
            if path.is_dir():
                libs[nickname] = path
        break  # First table found wins, exactly as KiCad resolves it.

    return libs


def pad_numbers(module: Path) -> set[str]:
    """Return the set of numbered pads in a .kicad_mod file."""
    text = module.read_text(encoding="utf-8", errors="replace")
    pads = {quoted or bare for quoted, bare in PAD_RE.findall(text)}
    pads.discard("")
    return pads


def load_parts(design: Path) -> list:
    """Execute the design script and hand back the parts it created.

    run_name is deliberately not "__main__", so the script defines the circuit without also
    running ERC and regenerating the netlist as a side effect.
    """
    sys.path.insert(0, str(design.parent))
    runpy.run_path(str(design), run_name="scripts.check_footprints.design")
    import builtins

    return list(builtins.default_circuit.parts)


def check(design: Path) -> tuple[list[str], list[str]]:
    """Return (errors, notes) for every part in the design."""
    root = footprint_dir()
    libs = library_map(root)
    errors: list[str] = []
    notes: list[str] = []

    for part in sorted(load_parts(design), key=lambda p: str(p.ref)):
        ref = part.ref
        footprint = (getattr(part, "footprint", "") or "").strip()

        if not footprint:
            errors.append(f"{ref}: no footprint assigned")
            continue

        if ":" not in footprint:
            errors.append(f"{ref}: footprint {footprint!r} is not in Library:Name form")
            continue

        nickname, name = footprint.split(":", 1)
        library = libs.get(nickname)
        if library is None:
            errors.append(f"{ref}: no footprint library nicknamed {nickname!r} (from {footprint})")
            continue

        module = library / f"{name}.kicad_mod"
        if not module.is_file():
            errors.append(f"{ref}: {footprint} not found -- no {module.name} in {library}")
            continue

        pads = pad_numbers(module)
        pins = {str(pin.num) for pin in part.pins}

        unmatched = sorted(pins - pads)
        if unmatched:
            errors.append(
                f"{ref}: {footprint} has no pad for pin(s) {', '.join(unmatched)} "
                f"(footprint pads: {', '.join(sorted(pads)) or 'none'})"
            )
            continue

        spare = sorted(pads - pins)
        if spare:
            notes.append(f"{ref}: {footprint} has pad(s) {', '.join(spare)} with no symbol pin")

    return errors, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--design",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_DESIGN,
        help=f"SKiDL design to check (default: {DEFAULT_DESIGN})",
    )
    parser.add_argument("--json", action="store_true", help="also write a JSON report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat pads with no matching symbol pin as failures too",
    )
    args = parser.parse_args(argv)

    if not args.design.is_file():
        print(f"error: no such design: {args.design}", file=sys.stderr)
        return 2

    try:
        errors, notes = check(args.design)
    except KicadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for note in notes:
        print(f"note:  {note}")
    for error in errors:
        print(f"FAIL:  {error}", file=sys.stderr)

    failed = errors or (notes if args.strict else [])

    if args.json:
        report = report_path("check-footprints", ".json")
        report.write_text(
            json.dumps({"errors": errors, "notes": notes}, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Report: {report}")

    if failed:
        print(f"\nFOOTPRINTS: {len(failed)} problem(s) found", file=sys.stderr)
        return 1

    print(f"\nFOOTPRINTS: all parts resolve and every pin has a pad ({len(notes)} note(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
