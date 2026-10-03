"""Time the build pipeline stage by stage, so regressions in build cost are visible.

Each stage is run as a real subprocess -- this measures wall-clock cost the way CI pays it,
including interpreter startup and kicad-cli process spawn.

    uv run python -m benchmarks.bench_build --repeat 3
    uv run python -m benchmarks.bench_build --stages drc gerbers
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

STAGES: dict[str, list[str]] = {
    "ato-build": ["ato", "build"],
    "erc": [sys.executable, "-m", "scripts.erc", "--allow-missing"],
    "drc": [sys.executable, "-m", "scripts.drc"],
    "gerbers": [sys.executable, "-m", "scripts.gerbers"],
}


def time_stage(command: list[str], repeat: int) -> dict[str, object]:
    durations: list[float] = []
    exit_codes: list[int] = []

    for _ in range(repeat):
        start = time.perf_counter()
        result = subprocess.run(
            command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
        )
        durations.append(time.perf_counter() - start)
        exit_codes.append(result.returncode)

    return {
        "command": subprocess.list2cmdline(command),
        "repeat": repeat,
        "exit_codes": exit_codes,
        "min_s": round(min(durations), 4),
        "median_s": round(statistics.median(durations), 4),
        "max_s": round(max(durations), 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-n", "--repeat", type=int, default=3, help="runs per stage")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=sorted(STAGES),
        default=sorted(STAGES),
        help="which stages to time",
    )
    parser.add_argument("-o", "--output", type=Path, help="write JSON results here")
    args = parser.parse_args(argv)

    results = {}
    for name in args.stages:
        print(f"--- {name} x{args.repeat}", flush=True)
        results[name] = time_stage(STAGES[name], args.repeat)
        print(f"    median {results[name]['median_s']}s  exits={results[name]['exit_codes']}")

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "stages": results,
    }

    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = RESULTS_DIR / f"bench-{stamp}.json"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {output}")

    # A nonzero exit anywhere means the numbers describe a failed run, not a real build.
    if any(code != 0 for stage in results.values() for code in stage["exit_codes"]):
        print("warning: at least one stage exited nonzero; timings may not be meaningful")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
