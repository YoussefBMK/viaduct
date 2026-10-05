"""Run KiCad's Design Rules Check over the board layout.

A CI-friendly invocation with a JSON report and a nonzero exit on violations. Schematic
parity is off by default: the design lives in a SKiDL script, so there is no .kicad_sch to
compare the board against.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._kicad import DEFAULT_BOARD, KicadError, find_pcb, report_path, run


def summarize(report: Path) -> int:
    """Print a per-category tally from a JSON DRC report. Returns the total violation count."""
    data = json.loads(report.read_text(encoding="utf-8"))
    categories = {
        "violations": data.get("violations", []),
        "unconnected": data.get("unconnected_items", []),
        "parity": data.get("schematic_parity", []),
    }

    total = 0
    for name, items in categories.items():
        if not items:
            continue
        total += len(items)
        counts: dict[str, int] = {}
        for item in items:
            severity = item.get("severity", "unknown")
            counts[severity] = counts.get(severity, 0) + 1
        detail = ", ".join(f"{n} {sev}" for sev, n in sorted(counts.items()))
        print(f"DRC [{name}]: {detail}")

    print(f"DRC: {'clean' if total == 0 else f'{total} issue(s)'} -- see {report}")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-b", "--board", default=DEFAULT_BOARD, help="board name under layouts/")
    parser.add_argument("--pcb", type=Path, help="explicit .kicad_pcb path")
    parser.add_argument(
        "--warnings-are-errors",
        action="store_true",
        help="fail on warnings too, not just errors",
    )
    parser.add_argument(
        "--schematic-parity",
        action="store_true",
        help="compare the board against a .kicad_sch (only meaningful if one exists)",
    )
    parser.add_argument(
        "--no-refill-zones",
        action="store_true",
        help="skip refilling zones before checking; faster but can report stale clearances",
    )
    args = parser.parse_args(argv)

    try:
        pcb = args.pcb or find_pcb(args.board)
    except KicadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not pcb.is_file():
        print(f"error: no such board: {pcb}", file=sys.stderr)
        return 2

    report = report_path(f"drc-{args.board}", ".json")
    flags = ["--severity-error"]
    if args.warnings_are_errors:
        flags.append("--severity-warning")
    if args.schematic_parity:
        flags.append("--schematic-parity")
    if not args.no_refill_zones:
        flags.append("--refill-zones")

    result = run(
        [
            "pcb",
            "drc",
            str(pcb),
            "--output",
            str(report),
            "--format",
            "json",
            "--units",
            "mm",
            "--all-track-errors",
            *flags,
            "--exit-code-violations",
        ]
    )

    if not report.is_file():
        print(f"error: kicad-cli produced no report (exit {result.returncode})", file=sys.stderr)
        return result.returncode or 2

    violations = summarize(report)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
