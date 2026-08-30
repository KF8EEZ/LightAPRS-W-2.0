# Build toolchain: headless `arduino-cli` compile checks

Status: **working and verified.** Branch: `ci-arduino-cli`. Files live in `ci/`.

## Why

Every firmware change (RM3100 magnetometer, WSPR extended telemetry, …) needs a
fast, reproducible "does it still build for the real board?" check before it ever
reaches hardware. The upstream README only documents the **GUI Arduino IDE**
workflow (install SAMD core by hand, copy `libraries/` into a sketchbook, click
Verify), which cannot run unattended and is awkward to reproduce.

This toolchain adds a **headless `arduino-cli`** path in a container: one command,
no display, no serial port, pinned versions.

## Two containers, two jobs

| | GUI Arduino IDE container | Headless `arduino-cli` (this) |
|---|---|---|
| Repo | <https://github.com/anielsen001/arduino-container> | `ci/` in this repo |
| Base | Ubuntu 24.04 + Arduino IDE 2.3.4 + X11 | `debian:bookworm-slim` + `arduino-cli` |
| Use | edit code, flash over USB from the desktop | compile verification, CI |
| Needs | X server, `/dev/tty*` | network at build time only |
| Board selection | Tools → Board → **Arduino M0** | FQBN `arduino:samd:mzero_bl` |

They are complementary. Nothing here replaces the GUI container for flashing.

## What the image contains

Built from `ci/Containerfile`:

| component | version | notes |
|---|---|---|
| base image | `debian:bookworm-slim` | |
| `arduino-cli` | **1.1.1** (2024-11-22) | version pinned via `sh -s ${ARDUINO_CLI_VERSION}` |
| `arduino:samd` core | **1.8.14** | pinned via `arduino-cli core install arduino:samd@${SAMD_VERSION}` |
| `arm-none-eabi-gcc` | **7.2.1** (7-2017-q4-major) | pulled automatically as a core tool dependency |
| also present | `bossac`, `openocd`, `avrdude`, CMSIS/CMSIS-Atmel | tool deps of the SAMD core — usable for a future flash path |

Resulting image: **~1.21 GB**, `localhost/arduino-cli-samd:latest` (local build; not
pushed to a registry).

### Board / FQBN

`arduino:samd:mzero_bl` = **Arduino M0**, matching the upstream README's
"select Arduino M0" instruction and the board's ATSAMD21G18 (Cortex-M0+). Other
SAMD FQBNs available in the same core if ever needed:

```
Arduino M0                          arduino:samd:mzero_bl        <- used
Arduino M0 Pro (Native USB Port)    arduino:samd:mzero_pro_bl
Arduino M0 Pro (Programming Port)   arduino:samd:mzero_pro_bl_dbg
Arduino Zero (Native USB Port)      arduino:samd:arduino_zero_native
Arduino Zero (Programming Port)     arduino:samd:arduino_zero_edbg
Arduino MKR Zero                    arduino:samd:mkrzero
```

`compile.sh` honours a `FQBN=` env override.

### Libraries

The sketch's dependencies are the vendored copies in `../libraries/`, passed with
`arduino-cli compile --libraries /work/libraries`. No sketchbook copy step. Several
of those folders are **renamed forks** (`LightAPRS_Si5351Arduino`,
`LightAPRS_JTEncode`, `LightAPRS_TinyGPSPlus-0.95`, …) whose `library.properties`
still carries the original upstream `name=`; `arduino-cli` resolves them by the
header each `src/` provides, so `#include <si5351.h>` picks up the fork rather than
any stock library of the same name.

## Usage

One-time image build (from the repo root):

```bash
podman build -t arduino-cli-samd ci/          # or docker
```

Compile check:

```bash
ci/compile.sh                                 # LightAPRS-W-2-pico-balloon
ci/compile.sh LightAPRS-W-2-pico-balloon      # explicit sketch dir (repo-relative)
```

Env overrides: `IMAGE`, `FQBN`, `ENGINE` (see the header of `ci/compile.sh`).

First `compile.sh` after a build caches nothing extra; subsequent runs are
**~20-40 s**. The container mounts the repo read-write at `/work` with the podman
`:Z` SELinux relabel flag; build artefacts are written under
`LightAPRS-W-2-pico-balloon/build/` on the host (git-ignored — see below).

## Verification performed

`arduino-cli compile`, SAMD core 1.8.14, FQBN `arduino:samd:mzero_bl`:

| sketch / branch | flash | global RAM | result |
|---|---|---|---|
| `LightAPRS-W-2-pico-balloon` @ `main` | 65 832 B / 262 144 (25 %) | 6 280 B / 32 768 (19 %) | ✅ builds |
| same @ `rm3100-i2c-magnetometer` | 66 336 B (+504) | 6 280 B (±0) | ✅ builds, no new warnings |

### Warnings emitted (all pre-existing, upstream)

- `library ZeroAPRS claims to run on samd21 … may be incompatible with … samd` —
  benign: the M0 FQBN reports architecture `samd`, `ZeroAPRS/library.properties`
  says `samd21`. Builds and links fine. Fixable upstream by adding `samd` to that
  `architectures=` line.
- `extra tokens at end of #include directive` — the stray `;` on
  `#include <MemoryFree.h>;` (line 17 of the sketch).
- `ISO C++ forbids converting a string constant to 'char*'` — the `APRS_setPath*`
  / `APRS_setDestination` calls pass string literals to `char *` parameters.
- `passing NULL to non-pointer argument … of 'void setTime(int, …)'` — `setTime(...
  NULL, NULL, NULL)` in `updateGpsData()`.
- `narrowing conversion … inside { }` — `ZeroSi4463::setFrequency()` brace-init of
  `uint8_t` arrays from wider ints.
- linker: `changing start of section .bss by 4 bytes` — harmless alignment note
  from the SAMD linker script.

None block compilation; none originate from local changes.

## Known limitations & decisions

1. **`install.sh` is fetched from `master`.** The `arduino-cli` *version* is
   pinned (`sh -s 1.1.1`) but the installer script is not. Low risk (it only
   downloads + unpacks a pinned tarball). Hardening options: vendor the script, or
   `curl` the release tarball from `downloads.arduino.cc` directly.
2. **Local image only.** Not published; each machine runs `podman build ci/`. A
   published image (GHCR) would make CI and onboarding faster — see next steps.
3. **No flash/upload path yet.** `bossac` and `openocd` are in the image, so
   `arduino-cli upload --fqbn … -p /dev/ttyACM0` could be added with a
   `--device` passthrough. Deliberately left out for now — flashing stays with the
   GUI container.
4. **Network required at build time** (`downloads.arduino.cc`, `github.com`,
   `raw.githubusercontent.com`). Compile runs afterward are offline.
5. **Container engine.** Developed against `podman` 4.9 (with the `docker` CLI
   shim). `compile.sh` auto-detects either; the `:Z` mount flag is a no-op on
   non-SELinux hosts and harmless under Docker.
6. **`build/` artefacts.** `arduino-cli` drops a `build/` dir next to the sketch.
   Add `LightAPRS-W-2-pico-balloon/build/` (or `*/build/`) to `.gitignore` — the
   repo's current `.gitignore` only covers `.DS_Store`.

## Next steps

- [ ] Add `*/build/` to `.gitignore`.
- [ ] `.github/workflows/compile.yml`: run `ci/compile.sh` (or `arduino-cli`
      directly via `arduino/setup-arduino-cli`) on push / PR, matrix over the
      sketch dirs.
- [ ] Optionally publish `arduino-cli-samd` to GHCR and have `compile.sh` /
      CI pull it instead of building.
- [ ] Fold `ci/` into `main` (currently isolated on `ci-arduino-cli`).
- [ ] Consider upstreaming the `ZeroAPRS` `architectures=samd21,samd` one-liner to
      silence the compatibility warning.

## References

- Board / library layout and the GUI build steps: `CLAUDE.md` (repo root),
  upstream `README.md`.
- `ci/README.md` — condensed usage.
- FQBN list: `arduino-cli board listall` inside the image.
