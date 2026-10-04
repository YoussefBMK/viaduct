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

## SKiDL spike (branch `spike/skidl`)

atopile's package registry host (`packages.atopileapi.com`) now returns NXDOMAIN and its CLI is
in maintenance mode, so this branch evaluates [SKiDL](https://devbisme.github.io/skidl/) —
Python as the hardware description language — as a replacement front end.

`viaduct_v0.py` is the first real circuit: an ESP32-S3-WROOM-1 with a BME280 on I²C, USB-C
power and native USB, an AP2112K-3.3 LDO and a USBLC6-2 ESD array. Every part is a stock
KiCad 10 symbol with a stock KiCad 10 footprint, and every pin assignment carries a datasheet
citation in a comment.

```bash
uv run python viaduct_v0.py    # runs ERC, writes viaduct_v0.net
```

It needs no shell setup: the script sets `KICAD10_SYMBOL_DIR=/usr/share/kicad/symbols` itself
before importing SKiDL (SKiDL reads that variable at import time and silently searches nothing
if it is unset). Override it by exporting a different value first.

Outputs:

| File | Committed | Purpose |
| --- | --- | --- |
| `viaduct_v0.net` | yes | KiCad netlist — the handoff to the PCB editor |
| `viaduct_v0_sklib.py` | yes | SKiDL's snapshot of every symbol used (pins, types, footprints) |
| `viaduct_v0.erc`, `viaduct_v0.log` | no (gitignored) | SKiDL drops these in the CWD on every run |

### Importing the netlist into KiCad on Windows

There is no schematic. SKiDL's `generate_schematic()` fails on this design with
`RoutingFailure`, so the netlist goes straight into the PCB editor — the same workflow atopile
used, and the same consequence: `kicad-cli sch erc` has nothing to check, so
`scripts/erc.py` still exits 3. SKiDL's own `ERC()` is the electrical check, and it runs on
every invocation of the script above.

The repo lives on the WSL2 filesystem, reachable from Windows at
`\\wsl.localhost\Ubuntu\home\<user>\projects\Viaduct`. KiCad on Windows can open that path
directly; copy the file to a local drive first if the UNC path is slow.

1. Open **KiCad → PCB Editor** (standalone — do *not* open it through a project, since there
   is no `.kicad_sch` to be out of sync with).
2. **File → Import → Netlist…**
3. Set *Netlist file* to `viaduct_v0.net`.
4. Options that matter for a schematic-less flow:
   - *Match Method*: **Keep existing symbol to footprint associations** → change to
     **Re-associate footprints by reference**. References (`U1`…`R7`) are the only stable key
     here; there are no schematic timestamps to match on.
   - *Footprint Assignment*: **Replace footprint with those specified in netlist** — the
     netlist is the source of truth for footprints.
   - *Unconnected Tracks*: **Keep** on the first import (nothing is routed yet).
   - *Unmatched Footprints*: **Delete** only once you are sure the board holds nothing
     hand-placed that the netlist does not know about.
5. **Update PCB**. All 22 footprints land in a stack at the origin with a ratsnest; drag them
   apart and route by hand.

Re-running `viaduct_v0.py` produces a byte-identical netlist apart from the date stamp (every
part carries an explicit `tag=`, so SKiDL does not invent random ones), which is what makes a
second import an update rather than a pile of duplicates.

The footprint libraries must be registered in KiCad's **Preferences → Manage Footprint
Libraries** under the same nicknames the netlist uses (`Resistor_SMD`, `Capacitor_SMD`,
`RF_Module`, `Connector_USB`, `Package_TO_SOT_SMD`, `Package_LGA`, `Button_Switch_SMD`,
`LED_SMD`). A stock KiCad 10 install has all of them in the global table already.

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
