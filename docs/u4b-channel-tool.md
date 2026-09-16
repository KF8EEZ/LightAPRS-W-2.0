# Picking a U4B channel

Status: **tool verified against 3 known-good reference vectors; channel not yet
registered.** Before flight, replace the placeholder values in
`LightAPRS-W-2-pico-balloon.ino`'s "U4B protocol channel identity" config block
with real ones derived from a channel you've actually registered.

## Why a channel number, not four separate constants

The sketch's WSPR config specifies four independent values — `U4B_ID1`,
`U4B_ID3`, `WSPR_START_MINUTE`, `WSPR_LANE_FREQ` — because that's what the
firmware needs at the bit level. But the pico-balloon community coordinates
channel assignments by a single **channel number** (0–599 per band), as listed
in the table at [traquito.github.io/channelmap](https://traquito.github.io/channelmap/).
`u4b/u4b_channel.py` bridges the two: give it a channel number, it prints the
four values ready to paste in.

The mapping from channel number to those four values isn't a simple
divide/modulo — it includes a **per-band rotation** of which minute goes with
which frequency lane (so a multi-band flight doesn't transmit at the same
minute on every band), which isn't documented anywhere in prose, only in the
reference implementation's source. This tool is a direct port of that source
([traquito/WsprEncoded](https://github.com/traquito/WsprEncoded)'s
`WsprChannelMap.h`, `Wspr.h`, `WsprUtl.h`), not a reimplementation from a
description — and it re-checks itself against 3 known-good vectors from that
project's own unit tests on every run, refusing to print an answer if that
check ever fails.

## Usage

```bash
cd u4b
uv sync                              # one-time
uv run u4b_channel.py --channel 226  # or whatever channel you register
```

Output:

```
Channel 226 on 20m:
  id1        = '1'
  id3        = '1'
  id13       = "11"
  minute     = 0  (Regular msg starts here; Basic Telemetry follows +2 min)
  lane       = 2 of 4
  freq       = 14097060 Hz  (dial 14095600 Hz + audio offset)

Paste into LightAPRS-W-2-pico-balloon.ino's U4B protocol channel identity block:
  #define U4B_ID1            '1'
  #define U4B_ID3            '1'
  #define WSPR_START_MINUTE  0
  #define WSPR_LANE_FREQ     14097060UL
```

Copy those four `#define` lines directly into the sketch, replacing the
placeholders.

`--band` defaults to `20m` — the only band this firmware currently transmits
WSPR on. `--list-bands` shows every band the calculator supports (matching the
reference implementation's full band table) and flags which ones aren't wired
up in the `.ino` yet.

## Getting a channel number in the first place

Register at [traquito.github.io/channelmap](https://traquito.github.io/channelmap/)
(or the older [qrp-labs.com/u4b](https://qrp-labs.com/u4b)). Don't fly with a
channel you haven't actually registered, and don't reuse someone else's --
two trackers sharing a channel collide on-air and corrupt both balloons'
decodes for everyone listening.

## If you ever change bands

The sketch only has 20m wired up today (`WSPR_LANE_FREQ`'s legal values are
documented in the sketch as the 4 lanes for that band). If that ever changes,
`u4b_channel.py --band <name> --channel N` already computes the right values
for any of the 17 bands the reference implementation supports — the firmware
side is the part that would need extending, not this tool.
