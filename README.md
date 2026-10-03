# Viaduct

Hardware project built with [atopile](https://atopile.io) and KiCad.

No circuit has been written yet — this repo is the tooling scaffold. `main.ato` is a two-test-point
smoke-test fixture that exists only to give the toolchain something to build.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and KiCad 10.x. uv will fetch Python 3.14 itself.

```bash
uv sync
```

If `kicad-cli` is not on your `PATH`, either add it or set `KICAD_CLI` to its full path.

## Usage

```bash
uv run ato build                         # solve the design into layouts/default/
uv run python -m scripts.drc             # design rules check -> build/reports/
uv run python -m scripts.erc             # electrical rules check (needs a .kicad_sch)
uv run python -m scripts.gerbers         # Gerbers + drills -> build/fab/default.zip
uv run python -m benchmarks.bench_build  # time the pipeline
```

Each accepts `--help`. Exit codes: `0` pass, `1` violations, `2` bad input, `3` not applicable
(nothing was checked — not a pass). See [CLAUDE.md](CLAUDE.md) for how the pieces fit together
and which checks atopile already performs on its own.

## Windows setup

**Use WSL2, not native Windows.** Install Ubuntu (`wsl --install -d Ubuntu`), then inside it
install `git`, `build-essential`, KiCad 10 and uv, and keep the working copy on the Linux
filesystem (`~/projects/Viaduct`, not `/mnt/c/...` — the 9p mount is slow and mangles file
modes). Run everything through `wsl -d Ubuntu -- bash -lc '...'` or just a WSL shell.

Native Windows was attempted first and is a dead end for two independent reasons:

1. **atopile crashes on CPUs without AVX-512.** The Windows wheels bundle a Zig-compiled
   native core (`pyzig*.pyd`) built for the build machine's CPU, so `ato --version` dies on
   import with `0xC000001D` STATUS_ILLEGAL_INSTRUCTION — see
   [atopile#1838](https://github.com/atopile/atopile/issues/1838). Not fixable by
   configuration. The Linux wheels are built without those instructions.

2. **`zstd` has no Python 3.14 Windows wheel**, so `uv sync` has to compile it, which means
   installing Visual Studio Build Tools (MSVC v143 + Windows SDK). Version `1.5.7.3` *does*
   publish a cp314 `win_amd64` wheel but is yanked as not thread-safe.

### The `NoDefaultCurrentDirectoryInExePath` trap

If you do build `zstd` on Windows and setuptools reports *"Unable to find a compatible Visual
Studio installation"* even though Build Tools is installed, the cause is likely the
`NoDefaultCurrentDirectoryInExePath=1` environment variable. `VsDevCmd.bat` `pushd`es into the
VS Installer directory and then invokes `vswhere.exe` bare, relying on cmd.exe searching the
current directory. With that variable set, cmd.exe refuses, and the resulting localized error
text corrupts the UTF-16LE stream setuptools parses — producing an empty environment dict and
exactly that misleading message. Unset the variable (and/or put the VS Installer directory on
`PATH`) for the build command.
