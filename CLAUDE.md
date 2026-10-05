# Viaduct

A [SKiDL](https://devbisme.github.io/skidl/) hardware project. The board is described in
Python (`viaduct_v0.py`), which runs ERC and emits a KiCad netlist. `scripts/` wraps
`kicad-cli` for checks and fabrication output; `benchmarks/` times the pipeline.

**The working copy lives at `~/projects/Viaduct` inside WSL2 Ubuntu.** Do not edit
`C:\Projects\Viaduct` — that is the stale pre-migration clone, and `~/projects/Viaduct`'s git
`origin` points at it only so the history could be carried over. Everything runs under Linux;
see "Why WSL2" below.

**V0 is `viaduct_v0.py`**: USB-C 5 V in → AP2112K-3.3 LDO → 3V3 → ESP32-S3-WROOM-1, with a
BME280 on I²C and native USB protected by a USBLC6-2. Every part is a stock KiCad 10 symbol
with a stock KiCad 10 footprint, and every value carries a datasheet or spec citation in a
comment next to it.

**The project used atopile until its package registry was decommissioned** (see "atopile is
gone" below). That history is in the git log; nothing in the tree depends on it any more.

## Layout

| Path | Contents |
| --- | --- |
| `viaduct_v0.py` | The circuit — ERC + netlist, no schematic |
| `viaduct_v0.net` | Generated KiCad netlist, committed so netlist diffs are reviewable |
| `viaduct_v0_sklib.py` | SKiDL's snapshot of every symbol used, committed for the same reason |
| `layouts/` | Hand-created KiCad board files, one directory per board |
| `build/` | Reports and fab output — all gitignored |
| `scripts/` | Checks and exports (`erc`, `drc`, `gerbers`, `check_footprints`) |
| `benchmarks/` | Pipeline timing harness |

## Commands

Dependencies are managed with **uv**.

```bash
uv sync                                     # create .venv, install skidl
uv run python viaduct_v0.py                 # run ERC and regenerate viaduct_v0.net
uv run python -m scripts.erc                # SKiDL ERC, standalone, with exit code
uv run python -m scripts.check_footprints   # footprints exist and pads match pins
uv run python -m scripts.drc                # design rules check (needs a board)
uv run python -m scripts.gerbers            # Gerbers + Excellon drills, zipped
uv run python -m benchmarks.bench_build     # time each stage
uv run ruff check . && uv run ruff format   # lint and format
```

`drc.py` and `gerbers.py` take `-b/--board <name>` to select a board under `layouts/`, or
`--pcb <path>` to point at one directly. All scripts support `--help`.

## Things that will trip you up

**There is no schematic, and no scripted way to get a board.** `generate_schematic()` fails
on this design with `RoutingFailure`, and `generate_svg()` needs the external `netlistsvg`
npm package, so `generate_netlist()` and `generate_xml()` are the only usable outputs.
`generate_pcb()` fails with `KeyError: 'Connector_USB'` at `kinet2pcb/kinet2pcb.py:314`, and
`kicad-cli pcb import` only converts *foreign PCB formats* — it cannot read a netlist. So the
board file is created once by hand in KiCad's PCB Editor (File → Import → Netlist) and kept
in sync by re-importing. Schematic generation is a possible later Viaduct feature.

**SKiDL cannot see footprint libraries.** It warns `fp-lib-table file was not found.
Component footprints are not available.` on every run and then accepts *any* footprint
string unvalidated — a mistyped library nickname sails through ERC and into the netlist, and
KiCad only complains at import time. `scripts/check_footprints.py` is what closes this gap:
it resolves every `Lib:Name` against the installed `*.pretty` libraries and asserts every
symbol pin number has a pad with that number. Run it after touching any footprint. It
matters most for the symbols KiCad ships with an *empty* footprint field (`Device:R`,
`Device:C`, `Device:LED`, `Switch:SW_Push`, `Connector:USB_C_Receptacle_USB2.0_16P`), where
the pairing is the designer's choice and nothing upstream validates it.

**Other SKiDL gotchas:**

- Symbol libraries are found *only* via `KICAD10_SYMBOL_DIR`. Unset, SKiDL searches nothing
  and reports missing *parts* rather than a missing *path*. `viaduct_v0.py` sets it
  internally at import time so the script is self-contained.
- `from skidl import NC` raises `ImportError`. SKiDL 2.3.0 injects `NC` and `default_circuit`
  into `builtins` instead of exporting them.
- Symbol and footprint libraries are **separate namespaces with colliding names**.
  `Button_Switch_SMD` is a footprint library and contains no symbols; the push-button symbol
  is `Switch:SW_Push`.
- Parts without an explicit `tag=` get a *random* tag each run, so the netlist churns and a
  re-import into KiCad creates duplicates instead of updating. Every part sets `tag=`.
- SKiDL writes `<script>.erc` and `<script>.log` into the CWD on every run — both gitignored.
- `skidl/tools/kicad10/lib.py` `get_fp_lib_tbl_dir()` is buggy: only the first entry of its
  paths tuple is an f-string, so the rest contain a literal un-interpolated
  `{kicad_version}`. Do not rely on SKiDL's own fp-lib-table discovery.

**atopile is gone.** `services.packages.url` defaulted to `https://packages.atopileapi.com`,
which returns an authoritative NXDOMAIN (confirmed via Cloudflare DNS-over-HTTPS, bypassing
the local resolver; the sibling `legacy.atopileapi.com` still resolves). `ato add <pkg>`
therefore failed with `ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]`, which looks like a
TLS or VPN problem but is not. The dangerous part was
`atopile/model/packages.py:search_registry_packages`, which wrapped the lookup in
`except Exception: return []` — **a dead network is indistinguishable from "no such
package"**. The general lesson outlives the tool: never treat an empty registry search as
evidence that a part does not exist.

**Why WSL2.** This started as an atopile constraint: atopile's Windows wheels shipped a
Zig-built native core compiled with AVX-512 — see
[atopile#1838](https://github.com/atopile/atopile/issues/1838) — and on a CPU without it
(e.g. an i5-12450H) `ato --version` died instantly with `0xC000001D`
STATUS_ILLEGAL_INSTRUCTION. The reason to *stay* in WSL2 is now KiCad: the libraries live at
`/usr/share/kicad/{symbols,footprints}` and the scripts' path fallbacks are written for that.

**`kicad-cli` discovery.** `scripts/_kicad.py` checks `$KICAD_CLI`, then `PATH`, then standard
install locations. In WSL it is `/usr/bin/kicad-cli` (10.0.6) and found on `PATH`; the glob
fallback covers the Windows `C:\Program Files\KiCad\10.0\bin\` case. Flags differ between
KiCad major versions; these wrappers target 10.x.

**A board needs an `Edge.Cuts` outline.** Without one, DRC fails with
`invalid_outline: Board has malformed outline`. Netlist import does not create an outline, so
draw it by hand after importing.

## Exit codes

Every script in `scripts/` uses the same scheme:

| Code | Meaning |
| --- | --- |
| `0` | Check ran and passed, or the export succeeded |
| `1` | Check ran and found violations |
| `2` | Bad input — missing or nonexistent `--pcb`/`--design`, unknown board, no `kicad-cli` |

There is no "not applicable" exit state any more: `erc.py` runs SKiDL's ERC against the
design itself, so it can always run.

## Conventions

- Scripts are run as modules (`python -m scripts.drc`) so the relative import of `_kicad` works.
- Reports are JSON under `build/reports/`; fab output under `build/fab/<board>/`.
- `DEFAULT_LAYERS` in `scripts/gerbers.py` assumes a 2-layer stackup. Update it, or pass
  `--layers`, when inner layers are added.
- **Never invent a part number, footprint or datasheet value.** Read it out of the
  manufacturer's PDF and cite section/page in a comment. If a part or package does not exist
  in the installed KiCad libraries, stop and say so rather than substituting something close.
- **Test fixtures must live inside this repo.** Never point a check or benchmark at a board
  from another project or anywhere outside the repo tree. A test that depends on an external
  path is not reproducible for anyone else and silently breaks when that path moves.
- `benchmarks/bench_build.py` excludes the `drc` and `gerbers` stages by default because they
  need a `.kicad_pcb`; ask for them explicitly once a board exists.
