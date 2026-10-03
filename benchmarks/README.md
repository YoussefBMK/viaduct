# Benchmarks

Wall-clock timing for the build pipeline. The point is to catch build-cost regressions as the
design grows — atopile's solver and part picker dominate `ato build` time, and that cost scales
with the number of parameterised components.

```bash
uv run python -m benchmarks.bench_build              # all stages, 3 runs each
uv run python -m benchmarks.bench_build -n 5         # more repeats
uv run python -m benchmarks.bench_build --stages drc gerbers
```

Results land in `benchmarks/results/bench-<timestamp>.json` (gitignored). Stages are timed as
subprocesses, so the numbers include interpreter and `kicad-cli` startup — that is deliberate,
since CI pays those costs too.

Caveats when comparing runs:

- The first `ato build` after a dependency change pays for solving and part picking from cold.
  Run once to warm up before recording numbers you intend to compare.
- `drc` timing depends on whether zones are refilled (`--no-refill-zones` skips it).
- A nonzero exit code in the output means the stage failed — those timings are noise.
