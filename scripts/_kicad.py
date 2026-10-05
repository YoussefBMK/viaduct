"""Shared plumbing for the scripts: locating kicad-cli, the board file, and the design."""

from __future__ import annotations

import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS_DIR = PROJECT_ROOT / "layouts"
REPORTS_DIR = PROJECT_ROOT / "build" / "reports"

# The SKiDL script that defines the circuit, and the board name derived from it.
DEFAULT_DESIGN = "viaduct_v0.py"
DEFAULT_BOARD = "viaduct_v0"


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


def find_pcb(board: str = DEFAULT_BOARD) -> Path:
    """Return the .kicad_pcb for a board.

    There is no scripted netlist-to-board path -- `kicad-cli pcb import` only converts
    foreign PCB formats, not netlists -- so the board file is created once by hand in
    KiCad's PCB Editor and then kept in sync by re-importing the netlist. See the README.
    """
    candidates = [
        LAYOUTS_DIR / board / f"{board}.kicad_pcb",
        LAYOUTS_DIR / f"{board}.kicad_pcb",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    loose = sorted(LAYOUTS_DIR.glob("*/*.kicad_pcb")) + sorted(LAYOUTS_DIR.glob("*.kicad_pcb"))
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        raise KicadError(f"Multiple .kicad_pcb files under {LAYOUTS_DIR}; pass --pcb to pick one")

    raise KicadError(
        f"No layout found for board '{board}'. Looked in:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + f"\nCreate it by importing {DEFAULT_DESIGN.removesuffix('.py')}.net into a new board "
        "in KiCad's PCB Editor -- see the README."
    )


def load_design(design: Path) -> list:
    """Execute a SKiDL design script and hand back the parts it created.

    run_name is deliberately not "__main__", so the script defines the circuit without also
    running ERC and regenerating the netlist as a side effect.
    """
    sys.path.insert(0, str(design.parent))
    runpy.run_path(str(design), run_name="scripts._kicad.design")
    import builtins

    return list(builtins.default_circuit.parts)


def report_path(name: str, suffix: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"{name}{suffix}"
