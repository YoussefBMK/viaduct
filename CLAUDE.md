# Viaduct

An [atopile](https://atopile.io) hardware project. The board is described in `.ato` source;
`ato build` solves it into a KiCad layout. `scripts/` wraps `kicad-cli` for checks and
fabrication output; `benchmarks/` times the pipeline.

**The working copy lives at `~/projects/Viaduct` inside WSL2 Ubuntu.** Do not edit
`C:\Projects\Viaduct` — that is the stale pre-migration clone, and `~/projects/Viaduct`'s git
`origin` points at it only so the history could be carried over. Everything runs under Linux;
see "Why WSL2" below.

**No real circuit has been written yet.** `main.ato` is a smoke-test fixture (two bridged
test points) whose only job is to give `ato build`, the wrappers and the benchmarks something
to chew on. Replace it when actual circuit work starts.

## Layout

| Path | Contents |
| --- | --- |
| `main.ato` | Entry point / smoke-test fixture — `paths.src` is the repo root |
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
So `kicad-cli sch erc` has nothing to run against, and `scripts/erc.py` exits **3 — not
applicable** on this project. Exit 3 is *not* a pass: nothing was checked. The check that
actually covers an `.ato` design is atopile's own graph-level ERC, which runs during
`ato build` (shorted interfaces, undefined power voltages, incompatible connections). For the
same reason `scripts/drc.py` leaves `--schematic-parity` off by default.

**Part picking requires authentication.** Any component atopile has to resolve against its
parts database (a `Resistor` with a `resistance`, etc.) makes `ato build` demand
`ato auth login` and a network round-trip. That is why `main.ato` contains only `TestPoint`s —
a pick-free fixture is what keeps `ato build` runnable offline and unauthenticated in CI.

**Why WSL2.** atopile's Windows wheels ship a Zig-built native core compiled for the build
machine's CPU, which includes AVX-512 instructions — see
[atopile#1838](https://github.com/atopile/atopile/issues/1838). On a CPU without AVX-512
(e.g. an i5-12450H) `ato --version` dies instantly with `0xC000001D`
STATUS_ILLEGAL_INSTRUCTION inside `pyzig.cp314-win_amd64.pyd`'s module init. It is not
fixable by configuration. The Linux wheels are clean, so the project runs in WSL2.

**`ato validate` is broken in 0.15.9.** It raises
`ImportError: cannot import name 'front_end' from 'atopile.compiler'` at
`atopile/cli/cli.py:252`. Use `ato build` as the config validator instead.

**`ato build` warns about atopile's own bundled templates.** Three "Configuration Error"
warnings naming `site-packages/atopile/templates/.../ato.yaml` appear on every build. Those
files contain unrendered cookiecutter placeholders; the warnings are upstream noise and have
nothing to do with this repo's `ato.yaml`.

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
install locations. In WSL it is `/usr/bin/kicad-cli` (10.0.6) and found on `PATH`; the glob
fallback covers the Windows `C:\Program Files\KiCad\10.0\bin\` case. Flags differ between
KiCad major versions; these wrappers target 10.x.

## Exit codes

Every wrapper in `scripts/` uses the same scheme:

| Code | Meaning |
| --- | --- |
| `0` | Check ran and passed, or the export succeeded |
| `1` | Check ran and found violations |
| `2` | Bad input — missing or nonexistent `--pcb`/`--sch`, unknown build, no `kicad-cli` |
| `3` | **Not applicable** — the check could not run at all. Currently only `erc.py`, when no `.kicad_sch` exists. **Not a pass.** |

`erc.py --allow-missing` downgrades the exit-3 case to `0` for pipelines that cannot express
a third state; it still prints that nothing was checked.

## Conventions

- Scripts are run as modules (`python -m scripts.drc`) so the relative import of `_kicad` works.
- Reports are JSON under `build/reports/`; fab output under `build/fab/<build>/`.
- `DEFAULT_LAYERS` in `scripts/gerbers.py` assumes a 2-layer stackup. Update it, or pass
  `--layers`, when inner layers are added.
- **Test fixtures must live inside this repo.** Never point a check or benchmark at a board
  from another project or anywhere outside the repo tree. A test that depends on an external
  path is not reproducible for anyone else and silently breaks when that path moves. If a
  check needs a board, add a minimal one here (`main.ato` + `layouts/`) and build it.
- `layouts/default/default.kicad_pcb` carries a hand-added 20×20 mm `Edge.Cuts` rectangle.
  atopile generates no board outline, and without one DRC fails with
  `invalid_outline: Board has malformed outline`. `ato build` preserves it.
