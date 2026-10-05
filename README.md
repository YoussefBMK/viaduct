# Viaduct

Hardware project built with [SKiDL](https://devbisme.github.io/skidl/) — Python as the
hardware description language — and KiCad 10.

`viaduct_v0.py` is the circuit: an ESP32-S3-WROOM-1 with a BME280 on I²C, USB-C power and
native USB, an AP2112K-3.3 LDO and a USBLC6-2 ESD array. Every part is a stock KiCad 10
symbol with a stock KiCad 10 footprint, and every pin assignment and component value carries
a datasheet or specification citation in a comment next to it.

The project previously used [atopile](https://atopile.io); it was dropped after the package
registry host `packages.atopileapi.com` started returning NXDOMAIN. See
[CLAUDE.md](CLAUDE.md) for the details worth remembering.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and KiCad 10.x. uv will fetch Python 3.14 itself.

```bash
uv sync
```

If `kicad-cli` is not on your `PATH`, either add it or set `KICAD_CLI` to its full path.

## Usage

```bash
uv run python viaduct_v0.py                 # run ERC, write viaduct_v0.net
uv run python -m scripts.erc                # SKiDL ERC standalone, with an exit code
uv run python -m scripts.check_footprints   # footprints exist and pads match pins
uv run python -m scripts.drc                # design rules check -> build/reports/
uv run python -m scripts.gerbers            # Gerbers + drills -> build/fab/
uv run python -m benchmarks.bench_build     # time the pipeline
```

Each accepts `--help`. Exit codes: `0` pass, `1` violations, `2` bad input.

`viaduct_v0.py` needs no shell setup: it sets `KICAD10_SYMBOL_DIR=/usr/share/kicad/symbols`
itself before importing SKiDL (SKiDL reads that variable at import time and silently searches
nothing if it is unset). Override it by exporting a different value first.

Outputs:

| File | Committed | Purpose |
| --- | --- | --- |
| `viaduct_v0.net` | yes | KiCad netlist — the handoff to the PCB editor |
| `viaduct_v0_sklib.py` | yes | SKiDL's snapshot of every symbol used (pins, types, footprints) |
| `viaduct_v0.erc`, `viaduct_v0.log` | no (gitignored) | SKiDL drops these in the CWD on every run |

## Checking footprints

SKiDL cannot see footprint libraries. It warns `fp-lib-table file was not found. Component
footprints are not available.` and then accepts any footprint string you hand it, so a typo
in a library nickname — or a footprint whose pads do not line up with the symbol's pins —
passes ERC and lands in the netlist. KiCad only objects at import time.

```bash
uv run python -m scripts.check_footprints           # exit 1 on any problem
uv run python -m scripts.check_footprints --strict  # also fail on pads with no symbol pin
```

It resolves each `Lib:Name` against the installed `*.pretty` directories (reading a real
`fp-lib-table` when one exists, so libraries outside the main footprint directory are found
too) and asserts that every symbol pin number has a pad with that number. Set
`KICAD10_FOOTPRINT_DIR` if the libraries are not in a standard location.

## Importing the netlist into KiCad on Windows

There is no schematic — SKiDL's `generate_schematic()` fails on this design with
`RoutingFailure` — and `kicad-cli pcb import` only converts foreign *PCB* formats, not
netlists. So the board file is created once by hand and then kept in sync by re-importing.
SKiDL's own `ERC()` is the electrical check; it runs on every invocation of the script and
standalone via `scripts/erc.py`.

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
6. Draw a board outline on **Edge.Cuts**. Netlist import does not create one, and DRC fails
   with `invalid_outline: Board has malformed outline` until it exists.
7. Save it as `layouts/viaduct_v0/viaduct_v0.kicad_pcb` so `scripts/drc.py` and
   `scripts/gerbers.py` find it without `--pcb`.

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

The scripts' default search paths for KiCad symbols and footprints are the Linux ones
(`/usr/share/kicad/{symbols,footprints}`), with Windows and macOS locations as fallbacks.

Native Windows was attempted first, while the project still used atopile, and was a dead end
for two independent reasons. Only the second still applies to a SKiDL-only tree:

1. **atopile crashed on CPUs without AVX-512.** The Windows wheels bundled a Zig-compiled
   native core (`pyzig*.pyd`) built for the build machine's CPU, so `ato --version` died on
   import with `0xC000001D` STATUS_ILLEGAL_INSTRUCTION — see
   [atopile#1838](https://github.com/atopile/atopile/issues/1838). Not fixable by
   configuration.

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
