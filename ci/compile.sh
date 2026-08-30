#!/usr/bin/env bash
# Compile-check a LightAPRS-W 2.0 sketch for the Arduino M0 (ATSAMD21) target
# with the headless arduino-cli container defined in ci/Containerfile.
#
# One-time image build (from the repo root):
#   podman build -t arduino-cli-samd ci/
#
# Usage (from anywhere in the repo):
#   ci/compile.sh                              # compiles LightAPRS-W-2-pico-balloon
#   ci/compile.sh LightAPRS-W-2-pico-balloon   # explicit sketch dir (repo-relative)
#
# Env overrides:
#   IMAGE   container image tag           (default: arduino-cli-samd)
#   FQBN    fully-qualified board name    (default: arduino:samd:mzero_bl = Arduino M0)
#   ENGINE  podman|docker                 (default: whichever is on PATH)
set -euo pipefail

SKETCH="${1:-LightAPRS-W-2-pico-balloon}"
IMAGE="${IMAGE:-arduino-cli-samd}"
FQBN="${FQBN:-arduino:samd:mzero_bl}"
ENGINE="${ENGINE:-$(command -v podman || command -v docker || true)}"

if [[ -z "$ENGINE" ]]; then
  echo "ci/compile.sh: need podman or docker on PATH" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$ENGINE" run --rm -v "$REPO_ROOT":/work:Z "$IMAGE" \
  compile \
  --fqbn "$FQBN" \
  --libraries /work/libraries \
  --warnings default \
  "/work/$SKETCH"
