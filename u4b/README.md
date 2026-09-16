# u4b/ — U4B protocol host-side helpers

Small `uv`-managed Python project with tools for reasoning about the U4B
pico-balloon WSPR telemetry protocol on a computer, before anything touches
firmware or the air. Not part of the Arduino build — see `ci/` for the
compile-check toolchain.

| script | purpose |
|---|---|
| `u4b_wspr_selftest.py` | Validates the mixed-radix telemetry packing math (Basic + Extended Telemetry) against known-good reference vectors. Run after touching any `u4b*` encoding function in the `.ino`, before trusting it in firmware. |
| `u4b_channel.py` | Looks up a channel number (as listed at [traquito.github.io/channelmap](https://traquito.github.io/channelmap/)) and prints the derived `id1`/`id3`/start-minute/frequency, ready to paste into the sketch's config. User-facing usage: `../docs/u4b-channel-tool.md`. |

Both are 1:1 ports of the reference implementation
([traquito/WsprEncoded](https://github.com/traquito/WsprEncoded)), fetched and
transcribed directly from its raw source — not reimplemented from a written
description. That distinction mattered in practice: an initial pass based on a
research summary of the telemetry packing had a real bug (a missing voltage
rotation) that only surfaced once the self-test was checked against actual
source and real test vectors.

## Setup

```bash
cd u4b
uv sync
```

## Run

```bash
uv run u4b_wspr_selftest.py
uv run u4b_channel.py --channel 226
```

No external dependencies — stdlib only. `uv` here is for a reproducible,
pinned interpreter (`pyproject.toml` / `uv.lock`) and a consistent invocation
(`uv run ...`), not for package management.
