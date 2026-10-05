# Benchmarks

Wall-clock timing for the build pipeline. The point is to catch build-cost regressions as the
design grows — SKiDL parses the KiCad symbol libraries on every run, so `netlist` and `erc`
cost scales with the number of distinct symbols, not the number of parts.

```bash
uv run python -m benchmarks.bench_build              # default stages, 3 runs each
uv run python -m benchmarks.bench_build -n 5         # more repeats
uv run python -m benchmarks.bench_build --stages drc gerbers
```

`drc` and `gerbers` need a `.kicad_pcb` and are excluded by default; name them explicitly
once a board exists under `layouts/`.

Results land in `benchmarks/results/bench-<timestamp>.json` (gitignored). Stages are timed as
subprocesses, so the numbers include interpreter and `kicad-cli` startup — that is deliberate,
since CI pays those costs too.

Caveats when comparing runs:

- `netlist` and `erc` both load the design from scratch, so they each pay full symbol-library
  parsing. Their timings are not additive with a single combined run.
- `drc` timing depends on whether zones are refilled (`--no-refill-zones` skips it).
- A nonzero exit code in the output means the stage failed — those timings are noise.
