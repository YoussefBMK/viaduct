# Viaduct

An [atopile](https://atopile.io) hardware project. The board is described in `.ato` source;
`ato build` solves it into a KiCad layout. `scripts/` wraps `kicad-cli` for checks and
fabrication output; `benchmarks/` times the pipeline.

**No circuit has been written yet.** `ato.yaml` points `builds.default.entry` at
`main.ato:App`, which does not exist. Create it before expecting `ato build` to work.

## Layout

| Path | Contents |
| --- | --- |
| `main.ato` | Entry point (not yet created) — `paths.src` is the repo root |
| `layouts/default/` | KiCad layout for the `default` build; created on first build |
| `build/` | Build artifacts, reports and fab output — all gitignored |
| `scripts/` | `kicad-cli` wrappers (`erc`, `drc`, `gerbers`) |
| `benchmarks/` | Build-pipeline timing harness |

## Commands

Dependencies are managed with **uv**. atopile 0.15 requires Python 3.14; uv downloads it.

```bash
uv sync                                  # create .venv, install atopile
uv run ato build                         # solve the design, update layouts/default/
uv run python -m scripts.drc             # design rules check
uv run python -m scripts.erc             # electrical rules check (see caveat below)
uv run python -m scripts.gerbers         # Gerbers + Excellon drills, zipped
uv run python -m benchmarks.bench_build  # time each stage
uv run ruff check .                      # lint
```

All script entry points support `-b/--build <name>` for non-`default` build targets and
`--help` for the full flag list.

## Things that will trip you up

**atopile does not generate a `.kicad_sch`.** It builds the netlist into the board directly.
So `kicad-cli sch erc` has nothing to run against, and `scripts/erc.py` will report that a
schematic is missing unless one was authored by hand. The check that actually covers an `.ato`
design is atopile's own graph-level ERC, which runs during `ato build` (shorted interfaces,
undefined power voltages, incompatible connections). Do not treat a skipped `scripts.erc` as
"ERC passed". For the same reason `scripts/drc.py` leaves `--schematic-parity` off by default.

**`ato build` edits `layouts/default/default.kicad_pcb` in place.** That file is the source of
truth for the physical layout and is committed. A copy only appears under `build/builds/` once
the `mfg-data` target runs, so the scripts prefer `layouts/`.

**`targets:` in `ato.yaml` is additive, not a replacement.** The `default` target set always
runs; use `exclude_targets:` to trim it. `mfg-data` (Gerbers, pick-and-place, STEP) is *not* in
`default` — `ato build --target mfg-data` or `--target all` to get it.

**atopile already does much of what `scripts/` does.** DRC runs inside every build, and
`mfg-data` emits a `.gerber.zip`. The wrappers exist for standalone CI invocation, JSON reports
with explicit exit codes, and control over layer lists and drill formats when a fab house wants
something specific. Prefer the atopile target unless you need that control.

**`kicad-cli` discovery.** `scripts/_kicad.py` checks `$KICAD_CLI`, then `PATH`, then standard
install locations. Development here is on Windows with KiCad 10.0.3 under
`C:\Program Files\KiCad\10.0\bin\`, which is not on `PATH` by default — the glob fallback
handles it. Flags differ between KiCad major versions; these wrappers target 10.x.

## Conventions

- Scripts are run as modules (`python -m scripts.drc`) so the relative import of `_kicad` works.
- Wrappers exit `0` clean, `1` on violations, `2` on missing inputs or a missing `kicad-cli`.
- Reports are JSON under `build/reports/`; fab output under `build/fab/<build>/`.
- `DEFAULT_LAYERS` in `scripts/gerbers.py` assumes a 2-layer stackup. Update it, or pass
  `--layers`, when inner layers are added.
