# Viaduct

Hardware project built with [atopile](https://atopile.io) and KiCad.

No circuit has been written yet — this repo is the tooling scaffold.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and KiCad 10.x. uv will fetch Python 3.14 itself.

```bash
uv sync
```

If `kicad-cli` is not on your `PATH`, either add it or set `KICAD_CLI` to its full path.
On Windows it lives at `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`.

## Usage

```bash
uv run ato build                         # solve the design into layouts/default/
uv run python -m scripts.drc             # design rules check -> build/reports/
uv run python -m scripts.erc             # electrical rules check (needs a .kicad_sch)
uv run python -m scripts.gerbers         # Gerbers + drills -> build/fab/default.zip
uv run python -m benchmarks.bench_build  # time the pipeline
```

Each accepts `--help`. See [CLAUDE.md](CLAUDE.md) for how the pieces fit together and which
checks atopile already performs on its own.
