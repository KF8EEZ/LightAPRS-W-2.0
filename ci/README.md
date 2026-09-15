# CI / compile-check toolchain

Headless `arduino-cli` setup for verifying that the sketches in this repo still
compile for the board they target (ATSAMD21G18 / **Arduino M0**,
FQBN `arduino:samd:mzero_bl`).

This is **compile verification only**. For editing and flashing over USB, use the
GUI Arduino IDE container at <https://github.com/anielsen001/arduino-container>.

## Files

| file | purpose |
|---|---|
| `Containerfile` | debian-slim + `arduino-cli` 1.1.1 + `arduino:samd` core 1.8.14 (pulls arm-none-eabi-gcc) |
| `compile.sh` | wrapper: runs `arduino-cli compile` with the right FQBN and `--libraries ./libraries` |

## Usage

The image is published at **`ghcr.io/kf8eez/arduino-cli-samd`** (public, linked to
this repo). Pull it instead of building locally:

```bash
podman pull ghcr.io/kf8eez/arduino-cli-samd:latest
IMAGE=ghcr.io/kf8eez/arduino-cli-samd:latest ci/compile.sh   # compile.sh honours IMAGE=
```

Or build it yourself from `ci/Containerfile` (from the repo root):

```bash
podman build -t arduino-cli-samd ci/      # or: docker build -t arduino-cli-samd ci/
```

There is **no CI workflow** that publishes this automatically — it's a manual
`podman build` + `podman push` when `ci/Containerfile` changes (versions: pin bumps
to `ARDUINO_CLI_VERSION` / `SAMD_VERSION`). Tags used: `latest` and the short commit
SHA of the `ci/` change.

Compile the pico-balloon sketch:

```bash
ci/compile.sh
```

Expected tail on success:

```
Sketch uses NNNNN bytes (25%) of program storage space. Maximum is 262144 bytes.
Global variables use NNNN bytes (19%) of dynamic memory, ...
```

The first run downloads the core + toolchain into the image; subsequent
`compile.sh` runs reuse it and take ~20-40 s.

## Notes

- The bundled libraries under `../libraries/` are passed with `--libraries`, so no
  copying into a sketchbook is needed. Several are renamed forks (`LightAPRS_*`)
  that shadow the stock Arduino libraries of the same header name.
- `arduino-cli` prints a harmless warning that `ZeroAPRS` claims architecture
  `samd21` while the M0 FQBN reports `samd`; it still builds.
- Pre-existing warnings (string-literal→`char*`, the stray `;` after
  `#include <MemoryFree.h>`, ZeroSi4463 narrowing, `NULL`→`setTime`) are from
  upstream, not from local changes.
- To target a different board, override `FQBN`, e.g.
  `FQBN=arduino:samd:mzero_pro_bl ci/compile.sh`.
