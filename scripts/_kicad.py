"""Shared plumbing for the kicad-cli wrappers: locating the binary and the build artifacts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS_DIR = PROJECT_ROOT / "layouts"
BUILDS_DIR = PROJECT_ROOT / "build" / "builds"
REPORTS_DIR = PROJECT_ROOT / "build" / "reports"

DEFAULT_BUILD = "default"


class KicadError(RuntimeError):
    """Raised when kicad-cli is missing, or an input file cannot be found."""


def kicad_cli() -> Path:
    """Locate kicad-cli: $KICAD_CLI, then PATH, then the usual per-platform install dirs."""
    override = os.environ.get("KICAD_CLI")
    if override:
        path = Path(override)
        if not path.is_file():
            raise KicadError(f"KICAD_CLI is set to {path}, which does not exist")
        return path

    on_path = shutil.which("kicad-cli")
    if on_path:
        return Path(on_path)

    candidates: list[Path] = []
    if sys.platform == "win32":
        for program_files in ("C:/Program Files", "C:/Program Files (x86)"):
            candidates += sorted(Path(program_files).glob("KiCad/*/bin/kicad-cli.exe"))
    elif sys.platform == "darwin":
        candidates += sorted(Path("/Applications").glob("KiCad/KiCad.app/Contents/MacOS/kicad-cli"))

    # Highest version directory wins.
    if candidates:
        return candidates[-1]

    raise KicadError(
        "kicad-cli not found. Add it to PATH or set the KICAD_CLI environment variable."
    )


def run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Invoke kicad-cli, streaming nothing but capturing output so callers can report on it."""
    cmd = [str(kicad_cli()), *args]
    print(f"$ {subprocess.list2cmdline(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if check and result.returncode != 0:
        raise KicadError(f"kicad-cli exited with code {result.returncode}")
    return result


def find_pcb(build: str = DEFAULT_BUILD) -> Path:
    """Return the .kicad_pcb for a build target.

    `ato build` edits the layout in place under layouts/<build>/, so that is the live board.
    The copy under build/builds/<build>/ only exists once the mfg-data target has run.
    """
    candidates = [
        LAYOUTS_DIR / build / f"{build}.kicad_pcb",
        BUILDS_DIR / build / f"{build}.kicad_pcb",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    loose = sorted((LAYOUTS_DIR / build).glob("*.kicad_pcb"))
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        raise KicadError(
            f"Multiple .kicad_pcb files in {LAYOUTS_DIR / build}; pass --pcb to disambiguate"
        )

    raise KicadError(
        f"No layout found for build '{build}'. Looked in:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + "\nRun `uv run ato build` first."
    )


def find_sch(build: str = DEFAULT_BUILD) -> Path | None:
    """Return a .kicad_sch for a build target, or None.

    atopile does not emit a schematic -- it drives the PCB netlist directly -- so this only
    finds something if a schematic was authored or imported by hand.
    """
    for candidate in (
        LAYOUTS_DIR / build / f"{build}.kicad_sch",
        BUILDS_DIR / build / f"{build}.kicad_sch",
    ):
        if candidate.is_file():
            return candidate

    loose = sorted((LAYOUTS_DIR / build).glob("*.kicad_sch"))
    return loose[0] if len(loose) == 1 else None


def report_path(name: str, suffix: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"{name}{suffix}"
