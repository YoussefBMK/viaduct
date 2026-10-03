"""Run KiCad's Electrical Rules Check over a build's schematic.

Caveat: atopile builds do not produce a .kicad_sch. atopile runs its own graph-level ERC
during `ato build` (shorted interfaces, undefined power voltages, incompatible connections),
which is the check that actually covers an .ato design. This wrapper is only useful when a
schematic exists alongside the layout -- e.g. one authored or imported by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._kicad import DEFAULT_BUILD, KicadError, find_sch, report_path, run


def summarize(report: Path) -> int:
    """Print a per-severity tally from a JSON ERC report. Returns the violation count."""
    data = json.loads(report.read_text(encoding="utf-8"))
    violations = [v for sheet in data.get("sheets", []) for v in sheet.get("violations", [])]

    counts: dict[str, int] = {}
    for violation in violations:
        severity = violation.get("severity", "unknown")
        counts[severity] = counts.get(severity, 0) + 1

    if counts:
        summary = ", ".join(f"{n} {sev}" for sev, n in sorted(counts.items()))
        print(f"ERC: {summary} -- see {report}")
    else:
        print(f"ERC: clean -- see {report}")
    return len(violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-b", "--build", default=DEFAULT_BUILD, help="atopile build target name")
    parser.add_argument("--sch", type=Path, help="explicit .kicad_sch path")
    parser.add_argument(
        "--warnings-are-errors",
        action="store_true",
        help="fail on warnings too, not just errors",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="exit 0 instead of failing when no schematic exists (useful in CI)",
    )
    args = parser.parse_args(argv)

    try:
        schematic = args.sch or find_sch(args.build)
    except KicadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.sch is not None and not args.sch.is_file():
        print(f"error: no such schematic: {args.sch}", file=sys.stderr)
        return 2

    if schematic is None:
        message = (
            f"ERC NOT RUN (not applicable): no .kicad_sch found for build '{args.build}'. "
            "This is NOT a pass -- nothing was checked. atopile does not generate a "
            "schematic; the ERC that `ato build` runs is the one that covers an .ato design."
        )
        if args.allow_missing:
            print(f"{message} Treated as success because --allow-missing was given.")
            return 0
        print(message, file=sys.stderr)
        return 3

    report = report_path(f"erc-{args.build}", ".json")
    severity = ["--severity-error"]
    if args.warnings_are_errors:
        severity.append("--severity-warning")

    result = run(
        [
            "sch",
            "erc",
            str(schematic),
            "--output",
            str(report),
            "--format",
            "json",
            "--units",
            "mm",
            *severity,
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
